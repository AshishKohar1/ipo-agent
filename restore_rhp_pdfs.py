"""Re-fetch the RHP PDFs that died with the Windows laptop's disk (2026-11-02).

The PDFs were gitignored (`_local/`), so `main` carries their provenance but not their
bytes: `data/rhp_progress.csv` (418 rows at status=done), `data/rhp_sources.csv` (the
manual set) and `data/verified_rhp_manifest.csv` (8 rows with a recorded SHA-256). This
script turns that provenance back into files.

H9 batch: one item at a time, >= 3 s per SEBI request (B2/H47 rule 3 - this is a restore,
not a bulk harvest of anything new), append-only checkpoint after every item, a commit
every COMMIT_EVERY items, resumable, and safe to kill at any moment.

RULE 3: no DRHPs. `data/rhp_sources.csv` carries four rows marked DRHP and they are
EXCLUDED here rather than quietly fetched - see `reports/RHP_RESTORE.md`. The old text
cache was 446 documents = 418 + 28, so excluding them means the rebuild tops out at 442
and the 446 figure cannot be reproduced. That is reported, not papered over.

A SHA-256 mismatch is never used: the file goes to `_local/rhp_quarantine/` and the row is
flagged. A row with no recorded hash is fetched, verified as a prospectus, and flagged
`no_hash` - fetching it is not the same as trusting it.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

import fetch_rhp
from repo_paths import repo_file
from fetch_rhp import PDFS, _pdf_bytes, _session, _verify_is_prospectus

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
QUARANTINE = ROOT / "_local" / "rhp_quarantine"
PROGRESS = DATA / "rhp_restore_progress.csv"

SEBI_MIN_GAP = 3.0          # seconds between SEBI requests (B2 floor, applied to SEBI too)
COMMIT_EVERY = 10
# H52 excluded these four: SEBI publishes neither an RHP nor a final prospectus for them,
# only a DRHP, which rule 3 forbids. Identified by the SHA-256 the fetch log recorded, not
# by name - H28 is explicit that a name cannot identify a company, and one of the four was
# fetched from the issuer's own website rather than SEBI.
H52_EXCLUDED_SHA = {
    "57cc42cfc1ec3dba990ff917febd5220459d5e1d6e57004999959f638d9ca764",  # Allied Blenders
    "067e731d86cad8392d54f308942f15c004a060f68522c65d44198f0df505d3ec",  # Amanta Healthcare
    "5ecc5e25ee3dacc838382c1bf6f0389cce9901c4b03f581bc1e687e7eabc88e4",  # Northern Arc
    "6e0ab67de48b6fab6a8cf74be87cf27d681c025c20c6319039f431a75a6641a7",  # Sri Lotus
}

COLS = ["list", "company", "doc_type", "url", "expected_sha", "got_sha", "status",
        "path", "bytes", "note", "ran_at"]

_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = SEBI_MIN_GAP - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _verify_name_for(company: str) -> str:
    """The name to look for on the cover, from the name the fetch log recorded.

    The fetch log carries working labels, not cover names: `IKIO Technologies Limited
    (formerly IKIO Lighting Limited)`, `Macrotech Developers Limited (Lodha Group)`,
    `Apeejay Surrendra Group (conglomerate)`. A `formerly X` parenthetical IS the name on
    the cover (H28), so it wins; any other parenthetical is an annotation and is dropped.
    """
    m = re.search(r"\(\s*formerly\s+(?:known\s+as\s+)?([^)]+?)\s*\)", company, re.I)
    if m:
        return m.group(1).strip()
    # `Affle (India) Ltd` -> the parenthetical is part of the name, so only drop a
    # parenthetical that is a whole annotation word or phrase, never a bracketed word
    # that sits inside the name.
    stripped = re.sub(r"\s*\((?:conglomerate|group|lodha group|[^)]*\bgroup\b[^)]*)\)\s*",
                      " ", company, flags=re.I)
    return stripped.strip()


def worklist() -> pd.DataFrame:
    """The three provenance lists, de-duplicated on the recorded SHA-256.

    Order matters: `verified_rhp_manifest.csv` is the most-verified list (it records a
    re-download check), so it is taken first and `rhp_progress.csv` only adds hashes the
    manifest does not already carry.
    """
    rows = []

    m = pd.read_csv(DATA / "verified_rhp_manifest.csv")
    for _, r in m.iterrows():
        rows.append({"list": "verified_rhp_manifest", "company": r["company"],
                     "verify_name": r["company"],
                     "doc_type": r["doc_type"], "url": r["url"],
                     "expected_sha": r["sha256"],
                     "target": Path(str(r["local_file"])).name})

    p = pd.read_csv(DATA / "rhp_progress.csv")
    for _, r in p[p["status"] == "done"].iterrows():
        sha = str(r["sha256"])
        rows.append({"list": "rhp_progress", "company": r["company"],
                     "verify_name": r["company"],
                     "doc_type": r["doc_type"], "url": r["url"], "expected_sha": sha,
                     "target": f"{sha[:16]}_{r['doc_type']}.pdf"})

    s = pd.read_csv(DATA / "rhp_sources.csv")
    for _, r in s.iterrows():
        if str(r["doc_type"]).upper() == "DRHP":
            continue                                    # rule 3
        # H28: the cover carries the name the company had AT FILING, and
        # `actual_company_name_on_document` is exactly that - Eternal Limited's RHP says
        # Zomato Limited, Acutaas Chemicals' says Ami Organics. Verifying against the
        # current name rejected four good documents on the first pass.
        rows.append({"list": "rhp_sources", "company": r["csv_company_name"],
                     "verify_name": (r["actual_company_name_on_document"]
                                     if pd.notna(r["actual_company_name_on_document"])
                                     else r["csv_company_name"]),
                     "doc_type": r["doc_type"], "url": r["source_url"],
                     "expected_sha": None, "target": None})

    # FOURTH list, added last so the dedup below keeps the more-verified lists first.
    # `rhp_valuation_fetch.csv` is the index the text cache is actually built from, and
    # 16 documents appear in NO other provenance list. Each carries a URL and a recorded
    # SHA-256. Only rows whose recorded file is absent are queued: this list is 450 rows
    # and re-fetching the 430 already on disk would be pointless traffic.
    v = pd.read_csv(DATA / "rhp_valuation_fetch.csv")
    v = v[v["status"].astype(str).str.startswith("ok")].drop_duplicates("company", keep="last")
    for _, r in v.iterrows():
        if str(r["sha256_recorded"]) in H52_EXCLUDED_SHA:
            continue                                    # rule 3, via H52
        if repo_file(r["path"]).exists():
            continue
        rows.append({"list": "rhp_valuation_fetch", "company": r["company"],
                     "verify_name": _verify_name_for(str(r["company"])),
                     "doc_type": "RHP", "url": r["url"],
                     "expected_sha": r["sha256_recorded"],
                     "target": repo_file(r["path"]).name,
                     # This list's files must land where the fetch log says they are,
                     # because `build_text_cache.py` reads that column to find them.
                     "dest": str(repo_file(r["path"]).parent.relative_to(ROOT))})

    df = pd.DataFrame(rows)
    if "dest" not in df.columns:
        df["dest"] = None
    hashed = df[df["expected_sha"].notna()].drop_duplicates(subset="expected_sha", keep="first")
    unhashed = df[df["expected_sha"].isna()]
    return pd.concat([hashed, unhashed], ignore_index=True)


def _done_keys() -> set[str]:
    """URLs already finished, from the checkpoint. A quarantined or failed row is NOT
    done: a re-run should try it again."""
    if not PROGRESS.exists():
        return set()
    d = pd.read_csv(PROGRESS)
    ok = d[d["status"].isin(["ok", "ok_no_hash"])]
    keys = set()
    for _, r in ok.iterrows():
        path = repo_file(r["path"]) if pd.notna(r["path"]) else None
        if path is not None and path.exists():
            keys.add(str(r["url"]))
    return keys


def _append(row: dict) -> None:
    row = {c: row.get(c) for c in COLS}
    header = not PROGRESS.exists()
    pd.DataFrame([row]).to_csv(PROGRESS, mode="a", header=header, index=False)


def _resolve_filing_page(sess, url: str) -> tuple[str | None, str]:
    """A `data/rhp_sources.csv` row points at a SEBI filing PAGE, not a PDF. Same
    extraction as `fetch_rhp.resolve_sebi`, deliberately: one PDF per filing or nothing."""
    _throttle()
    page = sess.get(url, timeout=30).text
    pdfs = list(dict.fromkeys(re.findall(r"file=([^'\"&]+\.pdf)", page, re.I)))
    if not pdfs:
        return None, "filing page has no PDF"
    if len(pdfs) > 1:
        return None, f"filing split into {len(pdfs)} PDFs - not handled"
    u = pdfs[0] if pdfs[0].startswith("http") else "https://www.sebi.gov.in" + pdfs[0]
    return u, "resolved from filing page"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, check=False,
                          capture_output=True, text=True)


def _commit(n: int) -> None:
    """Commit the checkpoint and push it (the user's instruction of 2026-11-02).

    Chained separately, never with `&&` (F2). The push is deliberately NOT retried with
    `pull --rebase --autostash`: the live workflow can be pushing to main at the same
    time, and an autostash would reach into a working tree this session may be editing.
    A rejected push is printed loudly and left for the session to reconcile - the commit
    is already safe on disk, and a lost push is visible, which a silently rebased working
    tree would not be.
    """
    _git("add", str(PROGRESS.relative_to(ROOT)))
    _git("commit", "-q", "-m",
         f"Task 3 (H9 batch): {n} RHP PDFs restored\n\n"
         f"Checkpoint only - the PDFs themselves are gitignored under _local/.\n\n"
         f"Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    r = _git("push", "origin", "HEAD:main")
    if r.returncode:
        print(f"    !! PUSH REJECTED at {n} items: "
              f"{(r.stderr or '').strip().splitlines()[-1:] or 'no stderr'}", flush=True)
    else:
        print(f"    pushed at {n} items", flush=True)


def run(limit: int | None = None) -> int:
    PDFS.mkdir(parents=True, exist_ok=True)
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    work = worklist()
    done = _done_keys()
    todo = work[~work["url"].isin(done)]
    if limit:
        todo = todo.head(limit)
    print(f"worklist {len(work)} | already restored {len(done)} | to do {len(todo)}",
          flush=True)

    sess = _session()
    completed = 0
    for i, (_, r) in enumerate(todo.iterrows(), 1):
        company, url = str(r["company"]), str(r["url"])
        expected = r["expected_sha"] if pd.notna(r["expected_sha"]) else None
        note = ""
        try:
            pdf_url = url
            if "/filings/" in url or url.lower().endswith((".html", ".htm")):
                pdf_url, note = _resolve_filing_page(sess, url)
                if pdf_url is None:
                    _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                             "url": url, "expected_sha": expected, "status": "failed",
                             "note": note, "ran_at": pd.Timestamp.now()})
                    print(f"[{i}/{len(todo)}] FAILED {company}: {note}", flush=True)
                    continue
            _throttle()
            # Streamed, with a read timeout rather than a whole-request one. 22 of the
            # first 137 documents died as ChunkedEncodingError/IncompleteRead - SEBI
            # drops the connection part-way through a large PDF - and this is ONE more
            # patient attempt, not a retry: still a single request per document per run,
            # which is what H47 rule 5 constrains.
            resp = sess.get(pdf_url, timeout=(30, 300), stream=True)
            if resp.status_code != 200:
                _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                         "url": url, "expected_sha": expected, "status": "failed",
                         "note": f"HTTP {resp.status_code}", "ran_at": pd.Timestamp.now()})
                print(f"[{i}/{len(todo)}] FAILED {company}: HTTP {resp.status_code}", flush=True)
                continue
            chunks = []
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if chunk:
                    chunks.append(chunk)
            body, pnote = _pdf_bytes(b"".join(chunks))
            if body is None:
                _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                         "url": url, "expected_sha": expected, "status": "failed",
                         "note": pnote, "ran_at": pd.Timestamp.now()})
                print(f"[{i}/{len(todo)}] FAILED {company}: {pnote}", flush=True)
                continue

            got = hashlib.sha256(body).hexdigest()
            vname = str(r["verify_name"]) if pd.notna(r["verify_name"]) else company
            ok_doc, why = _verify_is_prospectus(body, vname)
            # `or` is wrong here: pandas stores the absent target as NaN, and a NaN
            # float is TRUTHY, so `r["target"] or ...` returned NaN and every one of the
            # 24 unhashed rows died as `PosixPath / float`. Ask pandas, not truthiness.
            target = (f"{got[:16]}_{r['doc_type']}.pdf"
                      if pd.isna(r["target"]) else str(r["target"]))

            if expected and got != expected:
                q = QUARANTINE / target
                q.write_bytes(body)
                _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                         "url": url, "expected_sha": expected, "got_sha": got,
                         "status": "sha_mismatch", "path": str(q.relative_to(ROOT)),
                         "bytes": len(body),
                         "note": f"QUARANTINED, not used; verify_is_prospectus={ok_doc} ({why})",
                         "ran_at": pd.Timestamp.now()})
                print(f"[{i}/{len(todo)}] SHA MISMATCH {company} -> quarantined", flush=True)
                continue

            if not ok_doc:
                _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                         "url": url, "expected_sha": expected, "got_sha": got,
                         "status": "failed", "bytes": len(body),
                         "note": f"verify_is_prospectus rejected (cover name tried: "
                                 f"{vname!r}): {why}",
                         "ran_at": pd.Timestamp.now()})
                print(f"[{i}/{len(todo)}] REJECTED {company}: {why}", flush=True)
                continue

            dest = (PDFS if pd.isna(r.get("dest")) else ROOT / str(r["dest"]))
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / target
            path.write_bytes(body)
            _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                     "url": url, "expected_sha": expected, "got_sha": got,
                     "status": "ok" if expected else "ok_no_hash",
                     "path": str(path.relative_to(ROOT)), "bytes": len(body),
                     "note": (note + ("; " if note else "") +
                              ("sha matches the recorded hash" if expected
                               else "NO RECORDED HASH - first sight, flagged")).strip("; "),
                     "ran_at": pd.Timestamp.now()})
            completed += 1
            print(f"[{i}/{len(todo)}] ok {company} ({len(body)/1e6:.1f} MB)", flush=True)
            if completed % COMMIT_EVERY == 0:
                _commit(completed)
        except Exception as e:                                  # noqa: BLE001
            _append({"list": r["list"], "company": company, "doc_type": r["doc_type"],
                     "url": url, "expected_sha": expected, "status": "failed",
                     "note": f"{type(e).__name__}: {e}", "ran_at": pd.Timestamp.now()})
            print(f"[{i}/{len(todo)}] FAILED {company}: {type(e).__name__}: {e}", flush=True)

    if completed % COMMIT_EVERY:
        _commit(completed)
    return 0


def summary() -> pd.DataFrame:
    """The Task 3 table: one row per provenance list."""
    work = worklist()
    cols = ["expected", "fetched", "sha match", "mismatch", "no hash", "failed"]
    out = pd.DataFrame(0, index=sorted(work["list"].unique()) + ["TOTAL"], columns=cols)
    for name, g in work.groupby("list"):
        out.loc[name, "expected"] = len(g)
    if PROGRESS.exists():
        d = pd.read_csv(PROGRESS).drop_duplicates(subset="url", keep="last")
        for name, g in d.groupby("list"):
            out.loc[name, "fetched"] = int(g["status"].isin(["ok", "ok_no_hash"]).sum())
            out.loc[name, "sha match"] = int((g["status"] == "ok").sum())
            out.loc[name, "mismatch"] = int((g["status"] == "sha_mismatch").sum())
            out.loc[name, "no hash"] = int((g["status"] == "ok_no_hash").sum())
            out.loc[name, "failed"] = int((g["status"] == "failed").sum())
    out.loc["TOTAL"] = out.drop(index="TOTAL").sum()
    return out


def self_test() -> int:
    passed = failed = 0

    def chk(label, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1; print(f"  PASS  {label}")
        else:
            failed += 1; print(f"  FAIL  {label}  {detail}")

    print("[1] the worklist obeys rule 3 and de-duplicates on the hash")
    w = worklist()
    chk("no DRHP row survives", (w["doc_type"].str.upper() != "DRHP").all(),
        str(w[w["doc_type"].str.upper() == "DRHP"]))
    src = pd.read_csv(DATA / "rhp_sources.csv")
    n_drhp = int((src["doc_type"].str.upper() == "DRHP").sum())
    chk("the four DRHPs are the only rhp_sources rows dropped",
        len(w[w["list"] == "rhp_sources"]) == len(src) - n_drhp,
        f"{len(w[w['list'] == 'rhp_sources'])} vs {len(src)}-{n_drhp}")
    hashed = w[w["expected_sha"].notna()]
    chk("every recorded hash appears once", hashed["expected_sha"].is_unique)
    chk("the manifest wins a hash collision with rhp_progress",
        set(w[w["list"] == "verified_rhp_manifest"]["expected_sha"])
        <= set(hashed["expected_sha"]))

    # everything below self_test's own source, so an assertion cannot match its own
    # label string
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]

    print("[2] naming matches what fetch_rhp itself writes")
    p = pd.read_csv(DATA / "rhp_progress.csv")
    r0 = p[p["status"] == "done"].iloc[0]
    want = f"{str(r0['sha256'])[:16]}_{r0['doc_type']}.pdf"
    chk("sha16_DOCTYPE.pdf, as fetch_rhp line 354 does",
        want in set(w["target"].dropna()), want)
    chk("an unhashed row has no target until its bytes are seen",
        w[w["list"] == "rhp_sources"]["target"].isna().all())
    # the absent target arrives from pandas as NaN, which is TRUTHY - `x or default`
    # therefore yields NaN and the path join dies. All 24 unhashed rows failed this way
    # on the first full pass.
    _absent = w[w["list"] == "rhp_sources"]["target"].iloc[0]
    chk("the absent target is NaN, and NaN is truthy - so `or` must not be used",
        pd.isna(_absent) and bool(_absent) is True)
    chk("the target fallback asks pd.isna, not truthiness",
        'if pd.isna(r["target"])' in body
        and 'target = r["target"] or' not in body)

    chk("a renamed company is verified against the name ON the document (H28)",
        str(w[w["company"] == "Eternal Limited"]["verify_name"].iloc[0]) == "Zomato Limited",
        str(w[w["company"] == "Eternal Limited"]["verify_name"].tolist()))
    chk("and an un-renamed row verifies against its own name",
        (w[w["list"] == "rhp_progress"]["verify_name"]
         == w[w["list"] == "rhp_progress"]["company"]).all())

    print("[3] it cannot be mistaken for a bulk harvester")
    chk("one throttle constant, >= 3 s", SEBI_MIN_GAP >= 3.0, str(SEBI_MIN_GAP))
    chk("every request goes through _throttle", body.count("sess.get(") == body.count("_throttle()") - 1)
    chk("no attempt loop wrapping a request", "for attempt in" not in body and "while " not in body)
    chk("a non-200 is recorded and abandoned, not re-tried",
        'f"HTTP {resp.status_code}"' in body and body.count("sess.get(") == 2)
    chk("prospectus verification is fetch_rhp's own, not a copy",
        _verify_is_prospectus is fetch_rhp._verify_is_prospectus)
    chk("prospectus verification is not optional", "_verify_is_prospectus(body, vname)" in body)

    print("[4] a mismatch is quarantined, never used")
    chk("quarantine is outside the fetched tree", QUARANTINE.name != PDFS.name)
    chk("the mismatch branch writes to QUARANTINE", "QUARANTINE / target" in body)
    # The store line was `path = PDFS / target` until the fourth provenance list needed
    # its own destination; the anchor is now `path = dest / target`. This test failing on
    # that rename is the test working.
    chk("the mismatch branch never reaches the store",
        body.index("QUARANTINE / target") < body.index("path = dest / target"))
    chk("the destination is per-row, so a list's files land where its index says",
        "dest = (PDFS if pd.isna(r.get(\"dest\"))" in body)

    print("[5] the checkpoint is append-only and resumable")
    chk("append mode", 'mode="a"' in body)
    chk("only ok rows count as done", '"ok", "ok_no_hash"' in body)
    chk("a quarantined row is retried", "sha_mismatch" not in body.split("def _done_keys")[1].split("def ")[0])
    chk("exactly one to_csv in the module, and it is the checkpoint",
        body.count("to_csv(") == 1 and "to_csv(PROGRESS" in body)
    chk("the FOUR provenance lists are only ever read, never written",
        body.count("read_csv(DATA /") == 4 and "PROGRESS = DATA /" in body)

    print("\n[6] rule 3: a DRHP is rejected on its title line, an RHP is not")
    from fetch_rhp import _title_kind
    # Real covers, transcribed from the cached text of the documents named.
    chk("Mahindra Logistics' Aug-2017 draft is a DRHP",
        _title_kind(["DRAFT RED HERRING PROSPECTUS\nDated August 3, 2017\n"
                     "(This Draft Red Herring Prospectus will be updated upon filing "
                     "with the RoC)"]) == "DRHP")
    chk("Nippon Life India AMC's Aug-2017 draft is a DRHP",
        _title_kind(["DRAFT RED HERRING PROSPECTUS\nDated August 18, 2017\n"
                     "(This Draft Red Herring Prospectus will be updated upon filing "
                     "with the RoC)"]) == "DRHP")
    chk("Bharti Hexacom's RHP is NOT a DRHP, though its cover names the draft",
        _title_kind(["RED HERRING PROSPECTUS\nDated March 22, 2024\n"
                     "(Please read Section 32 of the Companies Act, 2013)"]) == "RHP")
    # The regression the first version of this rule caused: presence anywhere in the
    # window flagged 37 of 430 documents, 35 of them genuine RHPs.
    chk("an RHP whose cover back-references its draft high up is still an RHP",
        _title_kind(["ni.sserpnretsew.www\nRED HERRING PROSPECTUS\n"
                     "Dated: September 11, 2020\n"
                     "The Draft Red Herring Prospectus was filed with SEBI"]) == "RHP")
    chk("a final prospectus is PROSPECTUS, which rule 3 permits when labelled",
        _title_kind(["PROSPECTUS\nDATED: SEPTEMBER 20, 2024"]) == "PROSPECTUS")
    chk("Hathway's cover has no spaces between the words and still reads as an RHP",
        _title_kind(["REDHERRINGPROSPECTUS\nDATEDJANUARY27,2010"]) == "RHP")
    chk("a scanned cover gives UNCLEAR, which is NOT a rejection",
        _title_kind(["TABLE OF CONTENTS\nSECTION I - GENERAL"]) == "UNCLEAR")
    chk("leading blank pages are skipped to the first page with text",
        _title_kind(["", "   ", "RED HERRING PROSPECTUS"]) == "RHP")

    print("\n[6b] a scanned cover is settled by how the document refers to ITSELF")
    from fetch_rhp import _self_reference_kind
    chk("a document that says 'this Red Herring Prospectus' is an RHP",
        _self_reference_kind(["Unless the context otherwise indicates, terms in this "
                              "Red Herring Prospectus have the meanings given below."])
        == "RHP")
    chk("one that says 'this Draft Red Herring Prospectus' is a DRHP",
        _self_reference_kind(["Terms used in this Draft Red Herring Prospectus have "
                              "the meanings given below."]) == "DRHP")
    chk("a DRAFT self-reference anywhere wins, even against many RHP ones",
        _self_reference_kind(["this Red Herring Prospectus " * 40
                              + " this Draft Red Herring Prospectus"]) == "DRHP")
    chk("no self-reference at all stays UNCLEAR, and is not promoted",
        _self_reference_kind(["TABLE OF CONTENTS", "SECTION I - GENERAL"]) == "UNCLEAR")
    chk("a mention of the RHP that is not about THIS document does not count",
        _self_reference_kind(["The Red Herring Prospectus of another issuer"])
        == "UNCLEAR")

    print("\n[7] the fourth provenance list, and its names")
    chk("rhp_valuation_fetch is in the worklist",
        "rhp_valuation_fetch" in set(worklist()["list"]))
    chk("the four H52 exclusions are identified by SHA-256, not by name",
        len(H52_EXCLUDED_SHA) == 4 and all(len(h) == 64 for h in H52_EXCLUDED_SHA))
    chk("a `formerly X` label verifies against X, the name on the cover (H28)",
        _verify_name_for("IKIO Technologies Limited (formerly IKIO Lighting Limited)")
        == "IKIO Lighting Limited")
    chk("a `(Lodha Group)` annotation is dropped",
        _verify_name_for("Macrotech Developers Limited (Lodha Group)")
        == "Macrotech Developers Limited")
    chk("`(conglomerate)` is dropped",
        _verify_name_for("Apeejay Surrendra Group (conglomerate)")
        == "Apeejay Surrendra Group")
    chk("but `Affle (India) Ltd` keeps its bracketed word, part of the name",
        _verify_name_for("Affle (India) Ltd") == "Affle (India) Ltd")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    if a.summary:
        print(summary().to_string())
        sys.exit(0)
    sys.exit(run(a.limit))

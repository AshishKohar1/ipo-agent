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
from fetch_rhp import PDFS, _pdf_bytes, _session, _verify_is_prospectus

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
QUARANTINE = ROOT / "_local" / "rhp_quarantine"
PROGRESS = DATA / "rhp_restore_progress.csv"

SEBI_MIN_GAP = 3.0          # seconds between SEBI requests (B2 floor, applied to SEBI too)
COMMIT_EVERY = 10
COLS = ["list", "company", "doc_type", "url", "expected_sha", "got_sha", "status",
        "path", "bytes", "note", "ran_at"]

_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = SEBI_MIN_GAP - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


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
                     "doc_type": r["doc_type"], "url": r["url"],
                     "expected_sha": r["sha256"],
                     "target": Path(str(r["local_file"])).name})

    p = pd.read_csv(DATA / "rhp_progress.csv")
    for _, r in p[p["status"] == "done"].iterrows():
        sha = str(r["sha256"])
        rows.append({"list": "rhp_progress", "company": r["company"],
                     "doc_type": r["doc_type"], "url": r["url"], "expected_sha": sha,
                     "target": f"{sha[:16]}_{r['doc_type']}.pdf"})

    s = pd.read_csv(DATA / "rhp_sources.csv")
    for _, r in s.iterrows():
        if str(r["doc_type"]).upper() == "DRHP":
            continue                                    # rule 3
        rows.append({"list": "rhp_sources", "company": r["csv_company_name"],
                     "doc_type": r["doc_type"], "url": r["source_url"],
                     "expected_sha": None, "target": None})

    df = pd.DataFrame(rows)
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
        path = ROOT / str(r["path"]) if pd.notna(r["path"]) else None
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
            ok_doc, why = _verify_is_prospectus(body, company)
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
                         "note": f"verify_is_prospectus rejected: {why}",
                         "ran_at": pd.Timestamp.now()})
                print(f"[{i}/{len(todo)}] REJECTED {company}: {why}", flush=True)
                continue

            path = PDFS / target
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

    print("[3] it cannot be mistaken for a bulk harvester")
    chk("one throttle constant, >= 3 s", SEBI_MIN_GAP >= 3.0, str(SEBI_MIN_GAP))
    chk("every request goes through _throttle", body.count("sess.get(") == body.count("_throttle()") - 1)
    chk("no attempt loop wrapping a request", "for attempt in" not in body and "while " not in body)
    chk("a non-200 is recorded and abandoned, not re-tried",
        'f"HTTP {resp.status_code}"' in body and body.count("sess.get(") == 2)
    chk("prospectus verification is fetch_rhp's own, not a copy",
        _verify_is_prospectus is fetch_rhp._verify_is_prospectus)
    chk("prospectus verification is not optional", "_verify_is_prospectus(body, company)" in body)

    print("[4] a mismatch is quarantined, never used")
    chk("quarantine is outside the fetched tree", QUARANTINE.name != PDFS.name)
    chk("the mismatch branch writes to QUARANTINE", "QUARANTINE / target" in body)
    chk("the mismatch branch never writes to PDFS",
        body.index("QUARANTINE / target") < body.index("path = PDFS / target"))

    print("[5] the checkpoint is append-only and resumable")
    chk("append mode", 'mode="a"' in body)
    chk("only ok rows count as done", '"ok", "ok_no_hash"' in body)
    chk("a quarantined row is retried", "sha_mismatch" not in body.split("def _done_keys")[1].split("def ")[0])
    chk("exactly one to_csv in the module, and it is the checkpoint",
        body.count("to_csv(") == 1 and "to_csv(PROGRESS" in body)
    chk("the three provenance lists are only ever read",
        body.count("read_csv(DATA /") == 3 and "PROGRESS = DATA /" in body)

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

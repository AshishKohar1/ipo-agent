"""
rhp_valuation.py — Priority 1: valuation ratios at listing, from the prospectuses.

Two stages, strictly sequential and independently resumable (H9):

  fetch     re-download each prospectus from the SEBI URL already on record, verify its
            SHA-256 against the one recorded when it was first seen, and keep it on disk
  extract   pull the "Basis for Issue Price" block, the restated financials and the
            post-issue share count, each value with its page and the quoted line (rule 2)

Why re-download rather than re-resolve
--------------------------------------
`data/rhp_progress.csv` already holds a SEBI URL **and a SHA-256** for 418 companies, of
which 416 have a corrected 1y target. Re-running the resolver would ask SEBI to search for
documents it has already told us about, and would risk resolving to a different filing than
the one the recorded SHA-256 describes. So the URL is taken from the record and the hash is
**verified**: a mismatch means SEBI replaced the file at that URL and the row is flagged
rather than silently extracted from a different document.

Memory
------
A previous run of the RHP batch reached **3.4 GB** resident because it held every opened
document. Here one PDF is in memory at a time: `fetch` streams to disk in chunks and never
holds the whole body, `extract` opens, reads, closes and deletes before the next company,
and the per-company rows are flushed to CSV every few items rather than accumulated.

    python rhp_valuation.py --stage fetch
    python rhp_valuation.py --stage extract
    python rhp_valuation.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import gc
import hashlib
import inspect
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                  # noqa: E402

DATA = ROOT / "data"
PDF_DIR = ROOT / "_local" / "rhp_valuation"      # gitignored: *.pdf and _local/
PROGRESS = DATA / "rhp_progress.csv"
FETCH_LOG = DATA / "rhp_valuation_fetch.csv"
VALUES = DATA / "rhp_valuation_values.csv"

GAP_S = 3.2
CHUNK = 1 << 16
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"),
      "Accept": "application/pdf,*/*"}

FETCH_COLS = ["company", "listing_date", "symbol", "url", "sha256_recorded",
              "sha256_now", "hash_matches", "bytes", "pages", "path",
              "fetched_at_ist", "status", "note"]


# ------------------------------------------------------------------ the work list
def targets() -> pd.DataFrame:
    """Every IPO with a corrected 1y target that has a prospectus URL on record."""
    import model_h_targets as MT
    t = MT.latest("1y")
    t = t[t["excess_corrected_pp"].notna()].copy()
    m = dataio.load_master_with_symbols()
    sym2comp = {str(r["symbol"]): r["company"] for _, r in m.iterrows()
                if pd.notna(r.get("symbol"))}
    t["company"] = t["symbol"].astype(str).map(sym2comp)
    t["_n"] = t["company"].map(lambda c: dataio.norm_name(c) if pd.notna(c) else "")

    p = pd.read_csv(PROGRESS)
    p["_n"] = p["company"].map(dataio.norm_name)
    ok = p[(p["status"] == "done") & p["url"].notna() & p["sha256"].notna()]
    ok = ok.drop_duplicates("_n")[["_n", "company", "url", "sha256", "doc_type",
                                   "source", "pages"]]
    ok = ok.rename(columns={"company": "company_progress"})
    j = t.merge(ok, on="_n", how="left")
    j["has_url"] = j["url"].notna()
    return j[["company", "symbol", "listing_date", "url", "sha256", "doc_type",
              "source", "has_url", "_n"]]


def not_on_sebi_by_year(j: pd.DataFrame | None = None) -> pd.DataFrame:
    """found / not-on-SEBI, by listing year - the table Task 1.1 asks for."""
    j = j if j is not None else targets()
    j = j.copy()
    j["year"] = pd.to_datetime(j["listing_date"], errors="coerce").dt.year
    g = j.groupby("year").agg(ipos=("company", "size"),
                              with_url=("has_url", "sum")).reset_index()
    g["not_on_sebi"] = g["ipos"] - g["with_url"]
    g["pct_found"] = (100 * g["with_url"] / g["ipos"]).round(1)
    return g


# ------------------------------------------------------------------ stage: fetch
def _sha_of(path: Path) -> str:
    """Hash by streaming the file, so a 40 MB prospectus never sits in memory whole."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(CHUNK), b""):
            h.update(blk)
    return h.hexdigest()


def _page_count(path: Path) -> int | None:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:                                          # noqa: BLE001
        return None


def fetch(limit: int | None = None, deadline=None) -> pd.DataFrame:
    """Download one prospectus at a time, >= 3.2 s apart, verifying the recorded hash.

    `deadline` is an IST timestamp after which the stage stops cleanly, so a hard stop can
    be honoured without losing what has already been written.
    """
    import requests
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    j = targets()
    j = j[j["has_url"]]
    done = set()
    if FETCH_LOG.exists():
        prev = pd.read_csv(FETCH_LOG)
        done = set(prev.loc[prev["status"] == "ok", "company"].astype(str))
    pend = [r for _, r in j.iterrows() if str(r["company"]) not in done]
    if limit:
        pend = pend[:limit]
    print(f"{len(j)} with a URL, {len(done)} already on disk, {len(pend)} to fetch")
    s = requests.Session()
    s.headers.update(UA)
    rows, last = [], 0.0
    for i, r in enumerate(pend, 1):
        if deadline is not None and pd.Timestamp.now() >= pd.Timestamp(deadline):
            print(f"  HARD STOP at {deadline} reached after {i - 1} fetches")
            break
        gap = GAP_S - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
        last = time.time()
        comp, url = str(r["company"]), str(r["url"])
        safe = "".join(ch if ch.isalnum() else "_" for ch in comp)[:60]
        dest = PDF_DIR / f"{safe}.pdf"
        rec = {c: None for c in FETCH_COLS}
        rec.update({"company": comp, "symbol": r.get("symbol"),
                    "listing_date": str(r.get("listing_date"))[:10], "url": url,
                    "sha256_recorded": r.get("sha256"),
                    "fetched_at_ist": str(pd.Timestamp.now())})
        # SEBI drops a long stream often enough that one attempt loses roughly two
        # prospectuses in three. Three tries with a widening wait; the politeness gap is
        # re-applied before each, so a retry is never a burst.
        n, err = None, None
        for attempt, wait in enumerate((0, 5, 15)):
            if wait:
                time.sleep(wait)
                last = time.time()
            try:
                # Streamed to disk in 64 KB blocks. The body is never held whole - that
                # is what took the earlier batch to 3.4 GB resident.
                with s.get(url, timeout=300, stream=True) as resp:
                    rec["status"] = f"HTTP {resp.status_code}"
                    if resp.status_code != 200:
                        err = f"HTTP {resp.status_code}"
                        break
                    got = 0
                    with open(dest, "wb") as fh:
                        for blk in resp.iter_content(CHUNK):
                            if blk:
                                fh.write(blk)
                                got += len(blk)
                n, err = got, None
                break
            except Exception as e:                             # noqa: BLE001
                err = f"{type(e).__name__}: {str(e)[:90]}"
                rec["note"] = f"attempt {attempt + 1}: {err}"
        if n is None:
            rec["status"] = f"error after 3 attempts ({err.split(':')[0]})"
            rows.append(rec)
            continue
        try:
            rec["bytes"] = n
            rec["path"] = str(dest.relative_to(ROOT))
            rec["sha256_now"] = _sha_of(dest)
            rec["hash_matches"] = bool(rec["sha256_now"] == str(r.get("sha256")))
            rec["pages"] = _page_count(dest)
            if not rec["hash_matches"]:
                # Not an error - a FACT about the document. SEBI replaced the file at this
                # URL since it was first seen, so anything extracted from it is being read
                # out of a different document than the one on record.
                rec["status"] = "ok_hash_differs"
                rec["note"] = ("SHA-256 does not match the hash recorded when this URL "
                               "was first fetched; the document at this URL has changed")
            else:
                rec["status"] = "ok"
        except Exception as e:                                 # noqa: BLE001
            rec["status"] = f"error {type(e).__name__}"
            rec["note"] = str(e)[:120]
        rows.append(rec)
        if i % 10 == 0 or i == len(pend):
            pd.DataFrame(rows, columns=FETCH_COLS).to_csv(
                FETCH_LOG, mode="a", header=not FETCH_LOG.exists(), index=False,
                encoding="utf-8")
            ok = sum(1 for x in rows if str(x["status"]).startswith("ok"))
            print(f"  {i}/{len(pend)}  {ok} ok in this chunk")
            rows = []
            gc.collect()
    if rows:
        pd.DataFrame(rows, columns=FETCH_COLS).to_csv(
            FETCH_LOG, mode="a", header=not FETCH_LOG.exists(), index=False,
            encoding="utf-8")
    d = pd.read_csv(FETCH_LOG) if FETCH_LOG.exists() else pd.DataFrame(columns=FETCH_COLS)
    print(f"{FETCH_LOG.name}: {len(d)} attempts, "
          f"{int(d['status'].astype(str).str.startswith('ok').sum())} on disk, "
          f"{int((d['hash_matches'] == False).sum())} with a changed hash")  # noqa: E712
    return d


# ------------------------------------------------------------------ stage: extract
def extract(limit: int | None = None, deadline=None, only: list[str] | None = None,
            write: bool = True) -> pd.DataFrame:
    """Run the valuation extractor over the prospectuses on disk, one at a time.

    One document in memory at a time. Each is opened, read section by section, and the
    Doc plus its page texts are deleted before the next; `gc.collect()` runs at every
    flush. The earlier batch reached 3.4 GB resident by holding opened documents, and the
    only defence that works is not holding them.
    """
    import extract.base as B
    from extract import valuation as V

    f = pd.read_csv(FETCH_LOG)
    f = f[f["status"].astype(str).str.startswith("ok")]
    if only:
        f = f[f["company"].astype(str).isin(only)]
    done = set()
    if VALUES.exists():
        done = set(pd.read_csv(VALUES, usecols=["company"])["company"].astype(str))
    pend = [r for _, r in f.iterrows() if str(r["company"]) not in done]
    if limit:
        pend = pend[:limit]
    print(f"{len(f)} documents on disk, {len(done)} already extracted, "
          f"{len(pend)} to do")
    rows, t0 = [], time.time()
    for i, r in enumerate(pend, 1):
        if deadline is not None and pd.Timestamp.now() >= pd.Timestamp(deadline):
            print(f"  HARD STOP at {deadline} reached after {i - 1} documents")
            break
        pdf = ROOT / str(r["path"])
        comp = str(r["company"])
        if not pdf.exists():
            rows.append({"company": comp, "variable": "_document", "value": None,
                         "status": "not_found", "note": "PDF not on disk",
                         "missing_reason": "document_unavailable"})
            continue
        try:
            n_pages = int(r["pages"]) if pd.notna(r.get("pages")) else 0
            toc = B.parse_toc(pdf, n_pages)
            off = B.measure_offset(pdf, n_pages)
            doc = B.Doc(pdf, comp, str(r.get("doc_type") or "RHP"),
                        str(r["sha256_now"]), str(r["url"]), n_pages, off, toc)
            vals = V.extract(doc)
            for v in vals:
                d = v.as_row()
                d["listing_date"] = str(r.get("listing_date"))[:10]
                d["symbol"] = r.get("symbol")
                d["hash_matches"] = r.get("hash_matches")
                rows.append(d)
            n_ok = sum(1 for v in vals if v.status == "ok")
            del doc, vals, toc
        except Exception as e:                                 # noqa: BLE001
            n_ok = 0
            rows.append({"company": comp, "variable": "_document", "value": None,
                         "status": "unreadable",
                         "note": f"{type(e).__name__}: {str(e)[:120]}",
                         "missing_reason": "present_but_unparsed"})
        if i % 5 == 0 or i == len(pend):
            if write and rows:
                pd.DataFrame(rows).to_csv(VALUES, mode="a",
                                          header=not VALUES.exists(), index=False,
                                          encoding="utf-8")
                rows = []
            el = time.time() - t0
            print(f"  {i}/{len(pend)}  last doc {n_ok} ok  "
                  f"({el / max(i, 1):.0f}s/doc, {el / 60:.0f} min elapsed)")
            gc.collect()
    if write and rows:
        pd.DataFrame(rows).to_csv(VALUES, mode="a", header=not VALUES.exists(),
                                  index=False, encoding="utf-8")
    if not VALUES.exists():
        return pd.DataFrame()
    d = pd.read_csv(VALUES, low_memory=False)
    print(f"{VALUES.name}: {len(d)} rows, {d['company'].nunique()} companies, "
          f"{int((d['status'] == 'ok').sum())} values extracted")
    return d


def coverage() -> pd.DataFrame:
    """variable | rows | % | first year | withheld count and top reason (Task 1.5)."""
    if not VALUES.exists():
        return pd.DataFrame()
    d = pd.read_csv(VALUES, low_memory=False)
    n_docs = d["company"].nunique()
    out = []
    for var, g in d.groupby("variable"):
        if str(var).startswith("_"):
            continue
        ok = g[g["status"] == "ok"]
        wh = g[g["status"] != "ok"]
        yr = pd.to_datetime(ok.get("listing_date"), errors="coerce").dt.year
        reasons = wh["missing_reason"].value_counts().head(2).to_dict()
        out.append({"variable": var, "rows": len(ok),
                    "pct": round(100 * len(ok) / max(n_docs, 1), 1),
                    "first_year": None if yr.dropna().empty else int(yr.min()),
                    "withheld": len(wh),
                    "top_reasons": "; ".join(f"{k}={v}" for k, v in reasons.items())})
    return pd.DataFrame(out).sort_values("pct", ascending=False)


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  ok   {name}")
        else:
            fail += 1
            print(f"  FAIL {name} {extra}")

    print("[1] the work list is the corrected-target set, not every RHP on disk")
    j = targets()
    import model_h_targets as MT
    n_t = int(MT.latest("1y")["excess_corrected_pp"].notna().sum())
    chk("one row per IPO with a corrected 1y target", len(j) == n_t, (len(j), n_t))
    chk("and a useful majority have a SEBI URL on record",
        int(j["has_url"].sum()) > 400, int(j["has_url"].sum()))
    chk("the rest are counted, not dropped",
        int((~j["has_url"]).sum()) == n_t - int(j["has_url"].sum()))
    g = not_on_sebi_by_year(j)
    chk("the found/not-found table covers every listing year",
        len(g) >= 15 and g["ipos"].sum() == n_t, (len(g), int(g["ipos"].sum())))

    print(chr(10) + "[1b] the extract stage holds one document at a time")
    esrc = inspect.getsource(extract)
    chk("the Doc and its values are deleted before the next document",
        "del doc, vals, toc" in esrc)
    chk("rows are flushed to CSV, not accumulated", 'mode="a"' in esrc)
    chk("and the collector runs at each flush", "gc.collect()" in esrc)
    chk("it is resumable on company", "already extracted" in esrc)
    chk("and it honours a deadline", "HARD STOP" in esrc)

    print(chr(10) + "[2] hashing streams, so a large PDF never sits in memory whole")
    src = inspect.getsource(_sha_of)
    chk("the hash is computed block by block", "iter(lambda: f.read(CHUNK)" in src)
    fsrc = inspect.getsource(fetch)
    chk("the download streams to disk", "stream=True" in fsrc
        and "iter_content(CHUNK)" in fsrc)
    chk("nothing holds resp.content", ".content" not in fsrc)
    chk("and rows are flushed, not accumulated to the end",
        'mode="a"' in fsrc and "gc.collect()" in fsrc)

    print(chr(10) + "[3] a changed document is a fact, not an error")
    chk("a hash mismatch gets its own status", "ok_hash_differs" in fsrc)
    chk("and says what it means", "has changed" in fsrc)
    chk("the recorded hash and the new one are BOTH kept",
        "sha256_recorded" in FETCH_COLS and "sha256_now" in FETCH_COLS)

    chk("a dropped stream is retried, not lost",
        "for attempt, wait in ((0, 5, 15))" in fsrc.replace(" ", "")
        .replace("(0,5,15)", "((0, 5, 15))").replace("  ", " ")
        or "(0, 5, 15)" in fsrc)
    chk("and the gap is re-applied before a retry, so it is never a burst",
        "last = time.time()" in fsrc)
    chk("three failures are recorded as such, with the exception named",
        "error after 3 attempts" in fsrc)

    print(chr(10) + "[4] the hard stop can be honoured without losing work")
    chk("fetch takes a deadline", "deadline" in fsrc)
    chk("and it breaks rather than raising", "HARD STOP" in fsrc)
    chk("the politeness gap is at least 3 s (rule 9)", GAP_S >= 3.0)
    chk("PDFs go under _local, which is gitignored",
        PDF_DIR.is_relative_to(ROOT / "_local"))

    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fetch", "extract"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--deadline", help="IST timestamp to stop at, e.g. '2026-10-14 08:00'")
    ap.add_argument("--found-table", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.found_table:
        print(not_on_sebi_by_year().to_string(index=False))
    if a.stage == "fetch":
        fetch(limit=a.limit, deadline=a.deadline)
    if a.stage == "extract":
        extract(limit=a.limit, deadline=a.deadline)
    if a.coverage:
        print(coverage().to_string(index=False))

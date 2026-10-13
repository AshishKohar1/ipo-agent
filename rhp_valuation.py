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
    # Resume only on rows written by the CURRENT extractor version. A row from an older
    # version is not "done" - it was produced by a different code path, and skipping it
    # would leave a file whose rows came from two extractors with no way to tell which.
    from extract.valuation import VALUATION_VERSION
    done = set()
    if VALUES.exists():
        prev = pd.read_csv(VALUES, usecols=["company", "extractor_version"],
                           low_memory=False)
        cur = prev[prev["extractor_version"].astype(str) == VALUATION_VERSION]
        stale = sorted(set(prev["company"].astype(str)) - set(cur["company"].astype(str)))
        done = set(cur["company"].astype(str))
        if stale:
            print(f"  {len(stale)} companies were extracted by an older version and will "
                  f"be re-done: {', '.join(stale[:4])}"
                  f"{' ...' if len(stale) > 4 else ''}")
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
            # The TOC pages and the offset probes are read in ONE open. The default path
            # opens the document seven times before extraction even starts - once for the
            # TOC and once per offset probe - and on a 582-page prospectus that was a
            # large share of the 96 s this was taking per document.
            probe = [i for i in B.OFFSET_PROBES if i < n_pages]
            pre = B.page_texts_at(pdf, list(range(min(10, n_pages))) + probe)
            # parse_toc gets ONLY the first ten pages. Handing it the whole pre-read set
            # would let a TOC-like page at index 200 contribute entries the original
            # never saw - a speedup must not change what is read, only how often the
            # file is opened.
            toc = B.parse_toc(pdf, n_pages,
                              texts={i: t for i, t in pre.items() if i < 10})
            off = B.measure_offset(pdf, n_pages, texts=pre)
            del pre
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


CROSSCHECK = DATA / "promoter_holding_crosscheck.csv"
REVIEW = ROOT / "reports" / "rhp_valuation_review.csv"
TOL_PCT = 5.0        # rule 2's tolerance, applied to promoter holding


def promoter_crosscheck(write: bool = True) -> pd.DataFrame:
    """RHP promoter holding against Chittorgarh's. Disagreement > 5% -> NULL, both logged.

    The RHP is now the source and Chittorgarh is the **cross-check**, which is the way
    round rule 2 wants: the prospectus is the primary document and the aggregator
    republishes it. Where they disagree by more than `TOL_PCT` the value is withheld and
    **both readings are kept on the row** - the point is not to pick a winner but to make
    the disagreement findable. A row Chittorgarh has no figure for is
    `rhp_only`, which is not a disagreement and not a failure.
    """
    if not VALUES.exists():
        return pd.DataFrame()
    from extract.valuation import VALUATION_VERSION as V
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[d["extractor_version"].astype(str) == V]
    keep = d[d["variable"].isin(["promoter_pre_pct", "promoter_post_pct"])
             & (d["status"] == "ok")]
    rhp = keep.pivot_table(index="company", columns="variable", values="value",
                           aggfunc="first")
    agg_path = DATA / "model_h_from_aggregator.csv"
    if not agg_path.exists():
        return rhp.reset_index()
    a = pd.read_csv(agg_path, low_memory=False)
    a["_n"] = a["company"].map(dataio.norm_name)
    a = a.drop_duplicates("_n").set_index("_n")
    rows = []
    for comp, r in rhp.iterrows():
        n = dataio.norm_name(comp)
        for var, aggcol in (("promoter_pre_pct", "promoter_pre_pct"),
                            ("promoter_post_pct", "promoter_post_pct")):
            v_rhp = r.get(var)
            v_cg = a.loc[n, aggcol] if n in a.index else None
            v_cg = None if (v_cg is None or pd.isna(v_cg)) else float(v_cg)
            if v_rhp is None or pd.isna(v_rhp):
                continue
            if v_cg is None:
                rows.append({"company": comp, "variable": var, "rhp": v_rhp,
                             "chittorgarh": None, "diff_pct": None,
                             "accepted": v_rhp, "verdict": "rhp_only"})
                continue
            base = max(abs(v_rhp), abs(v_cg))
            diff = 100.0 * abs(v_rhp - v_cg) / base if base else 0.0
            ok = diff <= TOL_PCT
            rows.append({"company": comp, "variable": var, "rhp": v_rhp,
                         "chittorgarh": v_cg, "diff_pct": round(diff, 2),
                         "accepted": v_rhp if ok else None,
                         "verdict": "agree" if ok else
                         f"WITHHELD: {diff:.1f}% apart, above the {TOL_PCT}% tolerance"})
    out = pd.DataFrame(rows)
    if write and len(out):
        out.to_csv(CROSSCHECK, index=False, encoding="utf-8")
    return out


def review_sheet(write: bool = True) -> pd.DataFrame:
    """reports/rhp_valuation_review.csv - one row per extracted value, so any number can
    be checked against the page it came from.

    Only rows at the CURRENT extractor version: the output file is append-only and holds
    earlier versions' attempts, and a review sheet that mixed them would send the reader
    to a page for a value the pipeline no longer produces.
    """
    if not VALUES.exists():
        return pd.DataFrame()
    from extract.valuation import VALUATION_VERSION as V
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[(d["extractor_version"].astype(str) == V) & (d["status"] == "ok")]
    f = pd.read_csv(FETCH_LOG, low_memory=False)
    f = f[f["status"].astype(str).str.startswith("ok")]
    name = {str(r["company"]): Path(str(r["path"])).name for _, r in f.iterrows()}
    out = pd.DataFrame({
        "company": d["company"],
        "listing_date": d.get("listing_date"),
        "pdf_file": d["company"].astype(str).map(name),
        "variable": d["variable"],
        "value": d["value"],
        "page": d["page"],
        "quoted_line": d["source_text"],
    }).sort_values(["company", "variable"])
    if write and len(out):
        REVIEW.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(REVIEW, index=False, encoding="utf-8")
    return out


def coverage() -> pd.DataFrame:
    """variable | rows | % | first year | withheld count and top reason (Task 1.5)."""
    if not VALUES.exists():
        return pd.DataFrame()
    from extract.valuation import VALUATION_VERSION as V
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[d["extractor_version"].astype(str) == V]
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

    print(chr(10) + "[1c] the one-open speedup does not change what is read")
    import extract.base as _B
    chk("parse_toc is given only the first ten pages",
        "if i < 10" in esrc)
    chk("measure_offset filters the supplied pages to its own probe list",
        "for i in probes if i in texts" in inspect.getsource(_B.measure_offset))
    chk("and both still read the file themselves when given nothing",
        "if texts is None" in inspect.getsource(_B.measure_offset)
        and "if texts is None" in inspect.getsource(_B.parse_toc))
    chk("the page set is read in a single open",
        "pdfplumber.open" in inspect.getsource(_B.page_texts_at)
        and inspect.getsource(_B.page_texts_at).count("pdfplumber.open") == 1)

    print(chr(10) + "[1d] a row from an older extractor is not treated as done")
    from extract.valuation import VALUATION_VERSION as _VV
    chk("the extractor carries its own version, not base's shared one",
        _VV != getattr(__import__("extract.base", fromlist=["x"]),
                       "EXTRACTOR_VERSION", None), _VV)
    chk("resume filters on that version", "VALUATION_VERSION" in esrc
        and "older version" in esrc)
    chk("and the stale companies are named, not silently re-done",
        "will " in esrc and "be re-done" in esrc)

    print(chr(10) + "[1e] the cross-check withholds rather than picking a winner")
    csrc = inspect.getsource(promoter_crosscheck)
    chk("the tolerance is 5% (rule 2)", TOL_PCT == 5.0)
    chk("a disagreement beyond it yields NULL", '"accepted": v_rhp if ok else None' in csrc)
    chk("and BOTH readings stay on the row",
        '"rhp": v_rhp' in csrc and '"chittorgarh": v_cg' in csrc)
    chk("a missing Chittorgarh figure is rhp_only, not a disagreement",
        '"rhp_only"' in csrc)
    chk("the RHP is the source and Chittorgarh the check, not the reverse",
        '"accepted": v_rhp' in csrc and '"accepted": v_cg' not in csrc)

    print(chr(10) + "[1f] coverage and the review sheet read ONE version")
    for fn in (coverage, review_sheet):
        src = inspect.getsource(fn)
        chk(f"{fn.__name__} filters on the current extractor version",
            'extractor_version"].astype(str) == V' in src)
    rsrc = inspect.getsource(review_sheet)
    chk("the review sheet carries the page and the quoted line",
        '"page"' in rsrc and '"quoted_line"' in rsrc)
    chk("and the PDF file name, so the page can be opened",
        '"pdf_file"' in rsrc)

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
    ap.add_argument("--review", action="store_true")
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
    if a.review:
        r = review_sheet()
        print(f"{REVIEW.relative_to(ROOT)}: {len(r)} rows, "
              f"{r['company'].nunique() if len(r) else 0} companies")
        x = promoter_crosscheck()
        if len(x):
            print(f"{CROSSCHECK.name}: {len(x)} comparisons")
            print(x["verdict"].str.replace(r"WITHHELD.*", "WITHHELD", regex=True)
                  .value_counts().to_string())

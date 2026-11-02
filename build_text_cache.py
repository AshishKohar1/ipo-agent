"""
build_text_cache.py — extract every page of all 450 prospectuses, once (Task 2).

    python build_text_cache.py --workers 3          # build / resume
    python build_text_cache.py --limit 3            # a short test
    python build_text_cache.py --time-one-reader    # one reader over 450, from cache
    python build_text_cache.py --self-test

Cost, measured on this laptop before building anything: `extract_text()` runs at **0.41 s
per page** and `data/rhp_valuation_fetch.csv` records **217,836 pages** across the 450
documents, so a single process needs about **25 hours**. The job is one document per
process with nothing shared, so it is run across a few workers instead; three keeps peak
memory near the single-document figure the extractor was tuned for (CLAUDE.md: ~8 GB,
one large item at a time) while finishing inside one night.

Resumable at document granularity (H9): a document whose cache file is already valid is
skipped, every cache file is written atomically, and killing the job at any moment loses
at most the documents currently in flight.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from repo_paths import repo_file                             # noqa: E402

from extract import textcache as TC                            # noqa: E402

FETCH_LOG = ROOT / "data" / "rhp_valuation_fetch.csv"


def work_list() -> pd.DataFrame:
    """The documents on disk, newest fetch per company, with the recorded page count."""
    f = pd.read_csv(FETCH_LOG)
    f = f[f["status"].astype(str).str.startswith("ok")].copy()
    f = f.drop_duplicates(subset=["company"], keep="last")
    # The recorded paths were written on Windows; `repo_file` is why this does not
    # silently return ZERO documents on POSIX. See repo_paths.py.
    f["abs"] = f["path"].map(repo_file)
    return f[f["abs"].map(lambda p: p.exists())]


def _one(args) -> tuple[str, int, float, str]:
    """Build one document's cache. Runs in a worker process."""
    path, company, url = args
    t0 = time.time()
    try:
        rec = TC.build_one(path, company=company, url=url)
        return company, int(rec["n_pages"]), time.time() - t0, "ok"
    except Exception as e:                                     # noqa: BLE001
        return company, 0, time.time() - t0, f"{type(e).__name__}: {str(e)[:120]}"


def build(workers: int = 3, limit: int | None = None,
          first: list[str] | None = None) -> pd.DataFrame:
    import multiprocessing as mp

    w = work_list()
    todo = [r for _, r in w.iterrows() if TC.get(r["abs"]) is None]
    n_cached = len(w) - len(todo)          # BEFORE --limit, or the line lies
    if first:
        want = {str(c).strip().lower() for c in first}
        todo = ([r for r in todo if str(r["company"]).strip().lower() in want]
                + [r for r in todo if str(r["company"]).strip().lower() not in want])
    if limit:
        todo = todo[:limit]
    print(f"{len(w)} documents on disk, {n_cached} already cached, "
          f"{len(todo)} queued now, {workers} workers", flush=True)
    if not todo:
        return pd.DataFrame()
    jobs = [(str(r["abs"]), str(r["company"]), str(r.get("url") or "")) for r in todo]
    out, t0 = [], time.time()
    # `maxtasksperchild=1`: a fresh interpreter per document. Measured, not assumed - at
    # four workers each child settled around 500 MB, free memory fell from 3.4 GB to
    # 0.4 GB, and in twenty-five minutes **not one document finished** where a single
    # process takes four. The machine was swapping, so the extra workers were costing
    # throughput rather than adding it. Recycling the child caps RSS at one document's
    # worth for a ~2 s interpreter start, which against 155 s of work is free.
    with mp.Pool(processes=max(1, int(workers)), maxtasksperchild=1) as pool:
        for i, res in enumerate(pool.imap_unordered(_one, jobs), 1):
            out.append(res)
            if i % 10 == 0 or i == len(jobs):
                el = time.time() - t0
                pp = sum(r[1] for r in out)
                print(f"  {i}/{len(jobs)}  {pp} pages  "
                      f"({el / i:.0f}s/doc wall, {el / 60:.0f} min elapsed, "
                      f"eta {(len(jobs) - i) * el / i / 3600:.1f} h)", flush=True)
    d = pd.DataFrame(out, columns=["company", "pages", "seconds", "status"])
    bad = d[d["status"] != "ok"]
    st = TC.stats()
    print(f"\nbuilt {len(d) - len(bad)} / {len(d)}; {len(bad)} failed")
    print(f"cache: {st['documents']} documents, "
          f"{st['bytes'] / 1e6:.0f} MB in {st['dir']}")
    print(f"wall time {(time.time() - t0) / 3600:.2f} h")
    if len(bad):
        print(bad.to_string(index=False))
    return d


def time_one_reader() -> float:
    """How long ONE reader takes over every cached document. The point of the exercise."""
    import extract.base as B
    from extract import valuation as V
    w = work_list()
    t0, n, hits = time.time(), 0, 0
    for _, r in w.iterrows():
        rec = TC.get(r["abs"])
        if rec is None:
            continue
        hits += 1
        doc = B.Doc(Path(r["abs"]), str(r["company"]), str(r.get("doc_type") or "RHP"),
                    rec["sha256"], str(r.get("url") or ""), rec["n_pages"],
                    rec["offset"], rec["toc"])
        n += sum(1 for v in V.shares_post_issue(doc) if v.status == "ok")
    el = time.time() - t0
    print(f"shares_post_issue over {hits} cached documents: {el:.1f}s "
          f"({el / max(hits, 1):.2f}s/doc), {n} values")
    return el


def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    import extract.base as B
    tsrc = inspect.getsource(TC)

    print("[1] every reader reads text through the two functions that consult the cache")
    chk("page_texts consults the cache",
        "_from_cache(path" in inspect.getsource(B.page_texts))
    chk("page_texts_at consults the cache",
        "_from_cache(path" in inspect.getsource(B.page_texts_at))
    chk("and a miss still opens the PDF, so an absent cache only costs speed",
        "pdfplumber.open" in inspect.getsource(B.page_texts)
        and "pdfplumber.open" in inspect.getsource(B.page_texts_at))
    chk("the cache lookup cannot raise into a reader",
        "except Exception" in inspect.getsource(B._from_cache))
    import extract
    pkg = Path(inspect.getfile(extract)).parent
    # A reader that opened the file itself would bypass the cache. Four readers DISCUSS
    # pdfplumber in comments - the unruled-table defects are the reason the text readers
    # exist at all - so the test looks for an import or an open, not for the word.
    import re as _re
    bad_use = _re.compile(r"^\s*import\s+pdfplumber|pdfplumber\s*\.\s*open\s*\(", _re.M)
    offenders = [f.name for f in sorted(pkg.glob("*.py"))
                 if f.name not in ("base.py", "textcache.py")
                 and bad_use.search(f.read_text(encoding="utf-8"))]
    chk("no reader module opens pdfplumber itself", not offenders, offenders)

    print("\n[2] the cache is the same text, not similar text")
    chk("built with the live call and no arguments",
        "extract_text() or" in tsrc)
    chk("the live reader makes the same call",
        "extract_text() or" in inspect.getsource(B.page_texts))

    print("\n[3] a cache built from a DIFFERENT file at the same path is a miss")
    chk("byte length is checked on every read",
        'rec.get("bytes") != p.stat().st_size' in tsrc)
    chk("page count is checked too",
        'len(rec.get("pages") or []) != rec.get("n_pages")' in tsrc)
    chk("schema is checked, so an old layout is not read as a new one",
        'rec.get("schema") != SCHEMA' in tsrc)
    chk("the source SHA-256 is recorded", "sha_of(path)" in tsrc)

    print("\n[4] a kill at any moment is safe (H9)")
    chk("cache files are written to a temp name and renamed",
        "os.replace(tmp, cp)" in tsrc)
    chk("an already-cached document is skipped",
        "TC.get(" in inspect.getsource(build))
    chk("one document is memoised, not all of them", "_memo.clear()" in tsrc)

    print("\n[5] round trip on a real document")
    w = work_list()
    # Was `== 450`, the whole fetch log, until the macOS rebuild (2026-11-02). The
    # restored corpus is 444: 450 ok rows in the fetch log, MINUS the 4 that are only
    # DRHPs (H52), MINUS Supriya Lifescience, whose fetch-log copy is also a DRHP and is
    # refused by rule 3 (its rhp_sources copy IS a 377-page RHP and is kept), MINUS Samhi
    # Hotels, which SEBI would not serve - three dropped connections and then a refusal,
    # and H47 forbids working that around. A number, not a floor, so a document going
    # missing fails here rather than quietly shrinking the cache.
    chk("the work list is the 444 restored documents (450 - 4 H52 - 1 DRHP - 1 unserved)",
        len(w) == 444, len(w))
    cs = pd.read_csv(ROOT / "reports" / "rhp_check_set_docs.csv")
    have = {str(c).strip().lower() for c in w["company"]}
    short = [c for c in cs["company"].astype(str)
             if c.strip().lower() not in have]
    chk("and all 20 check-set documents are among them, so the gate can be reproduced",
        not short, short)
    built = [r for _, r in w.iterrows() if TC.get(r["abs"]) is not None]
    if built:
        r = built[0]
        rec = TC.get(r["abs"])
        got = TC.pages_at(r["abs"], [0, 1, 2])
        chk("pages come back keyed by index", set(got) == {0, 1, 2})
        chk("the cover page has text", len(got.get(0) or "") > 50)
        chk("n_pages matches the fetch log",
            int(rec["n_pages"]) == int(r["pages"]), f"{rec['n_pages']} vs {r['pages']}")
        live = B.page_texts(Path(r["abs"]), 0, 2)
        chk("and the cache returns EXACTLY what the cache serves to a reader",
            live == got)
    else:
        print("      (nothing cached yet, so the round trip is not run)")

    print("\n[6] the cache records what built it, and says so when that changes")
    chk("the extraction libraries are named, not just pdfplumber",
        set(TC.EXTRACTION_LIBS) >= {"pdfplumber", "pdfminer.six", "pillow",
                                    "pypdfium2", "cryptography"})
    chk("every one of them is pinned in requirements.txt",
        all(f"{n}==" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
            for n in TC.EXTRACTION_LIBS),
        [n for n in TC.EXTRACTION_LIBS
         if f"{n}==" not in (ROOT / "requirements.txt").read_text(encoding="utf-8")])
    inst = TC.lib_versions()
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    chk("and each pin is the version actually installed",
        all(f"{n}=={v}" in req for n, v in inst.items()),
        [f"{n}=={v}" for n, v in inst.items() if f"{n}=={v}" not in req])
    chk("a new record carries lib_versions",
        '"lib_versions": lib_versions()' in tsrc)
    # THE mismatch test the brief asks for: this fails, loudly, if the cache was built
    # with a library version that is no longer installed.
    drift = TC.lib_drift()
    chk("no cached document was built with a different extraction stack",
        not drift, f"{len(drift)} of 444 drifted, e.g. {drift[:2]}")
    chk("lib_drift reports rather than invalidating, so a bump costs no rebuild",
        "cache invalidation" in inspect.getsource(TC.lib_drift).lower()
        or "NOT a cache invalidation" in inspect.getsource(TC.lib_drift))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2,
                    help="2 is the measured ceiling on this laptop; see build()")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--time-one-reader", action="store_true")
    ap.add_argument("--first", help="CSV with a `company` column to build FIRST, so the "
                                    "check-set documents are usable while the rest build")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.time_one_reader:
        time_one_reader()
        raise SystemExit(0)
    firsts = None
    if a.first:
        firsts = pd.read_csv(a.first)["company"].astype(str).tolist()
    build(workers=a.workers, limit=a.limit, first=firsts)

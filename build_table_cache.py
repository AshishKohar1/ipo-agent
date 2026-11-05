"""
build_table_cache.py — every table on every page of every prospectus, parsed once (H9).

    python build_table_cache.py --workers 6      # build / resume
    python build_table_cache.py --limit 3        # a short test
    python build_table_cache.py --self-test
    python build_table_cache.py --stats

Why
---
`extract/textcache.py` removed the need to open a PDF for TEXT. A reader that needs table
STRUCTURE - which cell sits in which column, which is the whole problem with an unruled
financial statement - still had to. This removes that too, so adding a variable means
writing a reader against the cache and re-running only that reader. PDFs are opened again
only for new IPOs.

Measured before building, not estimated: `extract_tables` with the text strategy runs at
**0.080 s per page** and the corpus is ~214,000 pages, so 4.8 core-hours, about 1.5 h
across six workers. Gzipped output is **0.42 GB** for every table on every page, against
0.35 GB if prose pages were filtered out - 0.07 GB is not worth the risk of having
discarded a page some later reader needs, so nothing is filtered.

What the strategy does, and what it does not
--------------------------------------------
`{"vertical_strategy": "text", "horizontal_strategy": "text"}` infers columns from the
alignment of words, because an Indian RHP's financial statements have no ruling lines.
That is the right setting for the tables that matter and the WRONG one for prose: on a
page of running text it returns the paragraph chopped into arbitrary columns. 79% of pages
in the worked document look tabular; the rest is noise and is stored anyway, flagged.
Every table carries `looks_tabular` - at least three rows in which two or more cells
contain a digit - so a reader can skip the noise in one comparison rather than re-parsing.

Resumable at document granularity (H9): a document whose cache file is valid for its
bytes is skipped, every file is written atomically, and a kill loses at most the documents
in flight. The settings and the extraction library versions are recorded in every file, so
a cache built under different settings is a MISS rather than a silent mixture.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import gzip
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from repo_paths import repo_file                                    # noqa: E402
from extract import textcache as TC                                 # noqa: E402

CACHE = ROOT / "_local" / "rhp_table_cache"
SCHEMA = 1
# Recorded in every file. A later run with different settings must MISS, not blend.
SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}
NUM = re.compile(r"\d")


def looks_tabular(table) -> bool:
    """Three or more rows with two or more digit-bearing cells: a table, not prose."""
    if not table:
        return False
    good = sum(1 for row in table
               if sum(1 for c in row if c and NUM.search(c)) >= 2)
    return good >= 3


def cache_path(sha: str) -> Path:
    return CACHE / f"{sha[:16]}.json.gz"


def get(sha: str, n_pages: int | None = None) -> dict | None:
    """The cached record for this document's SHA-256, or None.

    A record built under different SETTINGS, a different SCHEMA or a different extraction
    stack is a MISS: serving tables parsed by another strategy as if they were these
    would be the quiet wrong answer rule 1 exists to prevent.
    """
    cp = cache_path(sha)
    if not cp.exists():
        return None
    try:
        with gzip.open(cp, "rt", encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception:                                               # noqa: BLE001
        return None
    if rec.get("schema") != SCHEMA or rec.get("settings") != SETTINGS:
        return None
    if rec.get("sha256") != sha:
        return None
    if n_pages is not None and rec.get("n_pages") != n_pages:
        return None
    if len(rec.get("pages") or {}) != rec.get("n_pages"):
        return None
    return rec


def tables_at(sha: str, pages: list[int]) -> dict:
    """`{page_index: [table, ...]}` for the pages asked for. The reader-facing call."""
    rec = get(sha)
    if rec is None:
        return {}
    return {i: rec["pages"].get(str(i), []) for i in pages}


def build_one(path, sha: str, company: str | None = None) -> dict:
    """Parse every page of one document. Runs in a worker process."""
    import pdfplumber
    path = Path(path)
    pages: dict[str, list] = {}
    flags: dict[str, list] = {}
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in range(n):
            try:
                tbs = pdf.pages[i].extract_tables(SETTINGS) or []
            except Exception as e:                                  # noqa: BLE001
                # One unreadable page must not lose the document. Rule 1: record it.
                pages[str(i)] = []
                flags[str(i)] = [f"unreadable: {type(e).__name__}"]
                continue
            pages[str(i)] = tbs
            flags[str(i)] = [looks_tabular(t) for t in tbs]
            # pdfplumber keeps every parsed page object on the PDF; without this a
            # 700-page document climbs past a gigabyte. Measured on the text cache.
            pdf.pages[i].flush_cache()
    rec = {"schema": SCHEMA, "sha256": sha, "stem": path.stem, "company": company,
           "n_pages": n, "settings": SETTINGS,
           "lib_versions": TC.lib_versions(),
           "extractor": "pdfplumber.extract_tables(text/text)",
           "pages": pages, "looks_tabular": flags}
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = cache_path(sha)
    tmp = cp.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(rec, fh)
    os.replace(tmp, cp)                 # atomic: a kill leaves no half-valid file
    return {"company": company, "n_pages": n,
            "tables": sum(len(v) for v in pages.values()),
            "tabular": sum(sum(1 for x in v if x is True) for v in flags.values()),
            "bytes": cp.stat().st_size}


def work_list() -> pd.DataFrame:
    """The documents the text cache holds, with their SHA-256 — rule 3 enforced.

    Driven by the text cache rather than the fetch log, so the two caches cover exactly
    the same corpus. `data/rhp_doc_type.csv` excludes the two DRHPs found by H57.
    """
    import build_text_cache as B
    w = B.work_list().copy()
    rows = []
    for _, r in w.iterrows():
        rec = TC.get(r["abs"])
        if rec is None:
            continue
        rows.append({"company": r["company"], "abs": r["abs"],
                     "sha256": rec["sha256"], "n_pages": rec["n_pages"]})
    d = pd.DataFrame(rows)
    dt = ROOT / "data" / "rhp_doc_type.csv"
    if dt.exists() and not d.empty:
        t = pd.read_csv(dt)
        banned = set(t[~t["allowed_under_rule_3"].astype(bool)]["sha256"].astype(str))
        d = d[~d["sha256"].astype(str).isin(banned)]
    return d.reset_index(drop=True)


def _one(args):
    path, sha, company = args
    t0 = time.time()
    try:
        out = build_one(path, sha, company)
        out["secs"] = time.time() - t0
        out["status"] = "ok"
        return out
    except Exception as e:                                          # noqa: BLE001
        return {"company": company, "n_pages": 0, "tables": 0, "tabular": 0,
                "bytes": 0, "secs": time.time() - t0,
                "status": f"{type(e).__name__}: {str(e)[:120]}"}


def build(workers: int = 6, limit: int | None = None) -> pd.DataFrame:
    import multiprocessing as mp
    w = work_list()
    todo = [r for _, r in w.iterrows()
            if get(str(r["sha256"]), int(r["n_pages"])) is None]
    n_cached = len(w) - len(todo)
    if limit:
        todo = todo[:limit]
    print(f"{len(w)} documents, {n_cached} already cached, {len(todo)} queued now, "
          f"{workers} workers", flush=True)
    if not todo:
        return pd.DataFrame()
    jobs = [(str(r["abs"]), str(r["sha256"]), str(r["company"])) for r in todo]
    out, t0 = [], time.time()
    # maxtasksperchild=1 for the same reason the text cache uses it: a fresh interpreter
    # per document caps RSS at one document's worth.
    with mp.Pool(processes=max(1, int(workers)), maxtasksperchild=1) as pool:
        for i, res in enumerate(pool.imap_unordered(_one, jobs), 1):
            out.append(res)
            if i % 10 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f"  {i}/{len(jobs)}  "
                      f"{sum(r['n_pages'] for r in out)} pages  "
                      f"{sum(r['tables'] for r in out)} tables  "
                      f"{sum(r['bytes'] for r in out)/1e6:.0f} MB  "
                      f"({el/i:.1f}s/doc, {el/60:.0f} min, "
                      f"eta {(len(jobs)-i)*el/i/3600:.1f} h)", flush=True)
    d = pd.DataFrame(out)
    bad = d[d["status"] != "ok"]
    print(f"\nbuilt {len(d)-len(bad)} / {len(d)}; {len(bad)} failed")
    print(f"wall time {(time.time()-t0)/3600:.2f} h")
    if len(bad):
        print(bad[["company", "status"]].to_string(index=False))
    return d


def stats() -> dict:
    files = list(CACHE.glob("*.json.gz")) if CACHE.exists() else []
    return {"documents": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "dir": str(CACHE)}


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]

    print("[1] looks_tabular separates a financial table from chopped prose")
    fin = [["Particulars", "2020", "2019"], ["Revenue", "1,234.5", "1,100.2"],
           ["PAT", "123.4", "98.7"], ["EPS", "12.3", "9.9"]]
    prose = [["(2) SCSBs will", "be entitled to a p", "fee of Rs 10"],
             ["the Bid cum", "Application Form p", "ed by the mem"]]
    chk("a statement with figures is tabular", looks_tabular(fin))
    chk("two lines of chopped prose are not", not looks_tabular(prose))
    chk("an empty table is not", not looks_tabular([]))
    chk("a header-only table is not", not looks_tabular([["a", "b", "c"]]))
    chk("None cells do not raise", looks_tabular([[None, "1", "2"]] * 3) is not None)

    print("\n[2] the cache is keyed by SHA-256 and records what parsed it")
    chk("the filename is the document's hash, not its name",
        cache_path("a" * 64).name.startswith("a" * 16))
    chk("the settings are recorded in every record", '"settings": SETTINGS' in body)
    chk("and the extraction library versions too", '"lib_versions": TC.lib_versions()' in body)
    chk("the strategy is text/text, for unruled financial tables",
        SETTINGS == {"vertical_strategy": "text", "horizontal_strategy": "text"})

    print("\n[3] a record parsed differently is a MISS, never a silent mixture")
    chk("different settings miss", 'rec.get("settings") != SETTINGS' in body)
    chk("a different schema misses", 'rec.get("schema") != SCHEMA' in body)
    chk("a different document at the same hash misses",
        'rec.get("sha256") != sha' in body)
    chk("a truncated record misses",
        'len(rec.get("pages") or {}) != rec.get("n_pages")' in body)
    chk("a page-count change misses", 'rec.get("n_pages") != n_pages' in body)

    print("\n[4] a kill at any moment is safe (H9)")
    chk("written to a temp name and renamed", "os.replace(tmp, cp)" in body)
    chk("an already-cached document is skipped", "if get(str(r[\"sha256\"])" in body)
    chk("page objects are flushed, so a 700-page document does not grow unbounded",
        "flush_cache()" in body)
    chk("one unreadable page is recorded, not fatal to the document",
        "unreadable: " in body)

    print("\n[5] rule 3: the two DRHPs are not in the work list")
    w = work_list()
    chk("the work list is driven by the text cache", len(w) > 0, len(w))
    dt = ROOT / "data" / "rhp_doc_type.csv"
    if dt.exists():
        t = pd.read_csv(dt)
        banned = set(t[~t["allowed_under_rule_3"].astype(bool)]["sha256"].astype(str))
        chk("any DRHP is excluded from the work list", not (set(w["sha256"]) & banned),
            set(w["sha256"]) & banned)
        # Was `== 2` while Mahindra Logistics and Nippon Life India AMC sat in the corpus.
        # Both were replaced by their final prospectuses on 2026-11-05, so the right
        # assertion is now that NONE is left - a DRHP reappearing must fail here.
        chk("and no DRHP is left in the corpus at all", len(banned) == 0, len(banned))
        chk("so the work list is the whole classified corpus",
            len(w) == len(t) - len(banned), f"{len(w)} vs {len(t)}-{len(banned)}")

    print("\n[6] round trip on a real document, if one is built")
    built = [r for _, r in w.iterrows() if get(str(r["sha256"])) is not None]
    if built:
        r = built[0]
        rec = get(str(r["sha256"]))
        chk("every page has an entry, even those with no table",
            len(rec["pages"]) == rec["n_pages"])
        got = tables_at(str(r["sha256"]), [0, 1, 2])
        chk("tables_at returns the pages asked for", set(got) == {0, 1, 2})
        chk("the flags line up with the tables, one per table",
            all(len(rec["looks_tabular"][k]) == len(v)
                for k, v in rec["pages"].items()))
        chk("the record names the same document the text cache does",
            rec["sha256"] == r["sha256"])
    else:
        print("      (nothing built yet, so the round trip is not run)")

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.stats:
        s = stats()
        print(f"{s['documents']} documents, {s['bytes']/1e6:.0f} MB in {s['dir']}")
        raise SystemExit(0)
    build(workers=a.workers, limit=a.limit)

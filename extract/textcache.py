"""
extract/textcache.py — every page of every prospectus, extracted once and kept.

Why
---
A reader fix used to cost a full pass over the PDFs. Measured on this laptop:
`extract_text()` runs at **0.41 s per page** and the 450 documents hold **217,836
pages**, so reading them all is ~25 hours single-threaded. That is why a one-line change
to a regex was taking a night, and why two readers were landing in different extractor
versions (1.8.0 and 1.8.1) — nobody could afford to re-run the first one.

So the text is extracted once into a per-document cache and every reader runs on the
cache. A reader fix then re-runs in minutes, and the version split goes away.

What is cached, and what is not
-------------------------------
Cached: the text of every page, plus the table of contents and the measured printed-page
offset, which are what `locate()` needs to find a section at all.

**Not** cached: `extract_tables()`. It is a further 0.27 s per page, it would roughly
double both the build and the size, and the unruled-table family of defects (the Basis
block, the restated financials, the promoter block, the capital structure) was fixed by
moving those readers onto TEXT lines. The table paths that remain are fallbacks and still
open the PDF; a pass that exercises them is not a minutes-long pass, and this module does
not pretend otherwise.

Identical text, not similar text
--------------------------------
The cache is built with the **same** `pdfplumber` call the live reader makes
(`page.extract_text()`, no arguments). `pypdf` is 2.5x faster and was rejected for this:
it emits page numbers, trailing spaces and broken words ("r esults") where pdfplumber
does not, so switching would silently change every reading in the file. A faster
extractor is a re-validation project, not an optimisation.

Staleness
---------
Each cache file records the source PDF's SHA-256, its byte length and its page count. A
read checks the byte length (cheap, every call) and the page count; a mismatch makes the
cache MISS rather than serve text from a different document, and the caller falls back to
the PDF. The SHA-256 is what `verify.py`-style auditing compares against
`data/verified_rhp_manifest.csv`.

    python build_text_cache.py --workers 3        # build (resumable)
    python -c "import extract.textcache as T; print(T.stats())"
"""
from __future__ import annotations

import gc
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "rhp_text_cache"
SCHEMA = 1
CHUNK = 50          # pages per open; see build_one

# One document at a time, by the same rule as the extractor itself: this laptop has ~8 GB
# and a previous batch reached 3.4 GB by holding more than one. The memo exists so that
# the eight readers that each ask for a slice of the SAME document do not un-gzip it eight
# times; it holds exactly one entry.
_memo: dict[str, dict] = {}


def cache_path(path) -> Path:
    return CACHE / (Path(path).stem + ".json.gz")


def sha_of(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def build_one(path, company: str | None = None, url: str | None = None,
              force: bool = False) -> dict:
    """Extract every page of one PDF, plus its TOC and offset, and write the cache file.

    Returns the record. Idempotent: an existing, valid cache file is returned untouched
    unless `force`, so the build is resumable after a kill at any moment (H9).
    """
    import pdfplumber
    from . import base as B

    path = Path(path)
    cp = cache_path(path)
    if not force:
        have = _read(cp, path)
        if have is not None:
            return have

    size = path.stat().st_size
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
    # **The file is re-opened every CHUNK pages.** `flush_cache()` drops a page's own
    # character objects but not the shared object graph pdfplumber builds as it walks the
    # page tree, and on these documents that graph grows without bound: a worker reading
    # one prospectus straight through reached **1.95 GB** resident, the machine began
    # compressing memory, and throughput collapsed to roughly one document per 25
    # minutes against four minutes for the same document alone. Reopening costs ~0.8 s
    # and is the only thing that actually releases the graph.
    for lo in range(0, n, CHUNK):
        with pdfplumber.open(path) as pdf:
            for i in range(lo, min(lo + CHUNK, n)):
                try:
                    pages.append(pdf.pages[i].extract_text() or "")
                except Exception:                              # noqa: BLE001
                    # One unreadable page must not lose the other 581. An empty string is
                    # exactly what the live reader would have seen, so nothing changes.
                    pages.append("")
                finally:
                    try:
                        pdf.pages[i].flush_cache()
                    except Exception:                          # noqa: BLE001
                        pass
        gc.collect()

    first10 = {i: pages[i] for i in range(min(10, n))}
    probe = {i: pages[i] for i in B.OFFSET_PROBES if i < n}
    rec = {"schema": SCHEMA, "stem": path.stem, "path": str(path),
           "company": company, "doc_url": url,
           "sha256": sha_of(path), "bytes": size, "n_pages": n,
           "toc": B.parse_toc(path, n, texts=first10),
           "offset": B.measure_offset(path, n, texts=probe),
           "extractor": "pdfplumber.extract_text()",
           "pages": pages}
    CACHE.mkdir(parents=True, exist_ok=True)
    # Atomic: a kill mid-write must not leave a half-written cache that reads as valid.
    tmp = cp.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(rec, fh)
    os.replace(tmp, cp)
    return rec


def _read(cp: Path, pdf_path) -> dict | None:
    """The cache record if it is valid FOR THIS FILE, else None."""
    if not cp.exists():
        return None
    try:
        with gzip.open(cp, "rt", encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception:                                          # noqa: BLE001
        return None
    if rec.get("schema") != SCHEMA:
        return None
    if len(rec.get("pages") or []) != rec.get("n_pages"):
        return None
    p = Path(pdf_path)
    if p.exists() and rec.get("bytes") != p.stat().st_size:
        # The PDF at this path is not the one that was cached. Serving its text would be
        # the fabrication rule 1 forbids, so this is a MISS.
        return None
    return rec


def get(path) -> dict | None:
    """The cached record for `path`, or None. Memoised for one document."""
    p = Path(path)
    hit = _memo.get(p.stem)
    if hit is not None and hit.get("path") == str(p):
        return hit
    rec = _read(cache_path(p), p)
    if rec is not None:
        _memo.clear()
        _memo[p.stem] = rec
    return rec


def pages_at(path, indices) -> dict[int, str] | None:
    """`{index: text}` for the requested indices from the cache, or None on a miss."""
    rec = get(path)
    if rec is None:
        return None
    pg, n = rec["pages"], rec["n_pages"]
    return {int(i): pg[int(i)] for i in sorted({int(i) for i in indices})
            if 0 <= int(i) < n}


def stats() -> dict:
    files = sorted(CACHE.glob("*.json.gz")) if CACHE.exists() else []
    return {"documents": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "dir": str(CACHE)}

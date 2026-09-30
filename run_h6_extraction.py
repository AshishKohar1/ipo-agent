"""
run_h6_extraction.py — PLAN.md Stage 15a: run the H6 extractors and measure coverage.

One document at a time. SHA-256 verified before a single page is read (hard rule 4). Page
text is extracted once per document and reused by every field group, which is both faster
and lower-peak than Stage 8's per-range reopening: a 476-page document's text is ~0.5 MB.

Coverage is measured **on the H6 fields only** (decision H6) — the headline financials that
H5 moved to the aggregator are not counted, and `extract/basis.py` and
`extract/financials.py` are not run here.

Two coverage numbers are reported, deliberately:

  strict    ok / (fields x documents)                  — counts nothing in my favour
  usable    (ok + ambiguous) / (fields x documents)     — a value with a caveat is still
                                                          checkable evidence
  adjusted  ok / (applicable fields x documents)        — excludes fields that are
                                                          structurally N/A for a document,
                                                          e.g. objects of the offer on a
                                                          pure offer for sale

The H6 target of >=60% is judged on `usable`, and `strict` is printed beside it so the gap
is visible rather than hidden. A field that cannot reach 60% across vintages is named in
the report rather than rescued by loosening a rule.

    python run_h6_extraction.py                 # read the PDFs
    python run_h6_extraction.py --cache DIR     # read cached page text (development)
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import gc
import hashlib
import json
import sys
import time
import zlib
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract import base as B           # noqa: E402
from extract import h6                  # noqa: E402

TARGET = 0.60


def page_text_all(path: Path) -> list[str]:
    """Every page's text, one open, per-page cache flushed. Memory stays flat."""
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages):
            try:
                out.append(pg.extract_text() or "")
            except Exception:
                out.append("")
            try:
                pg.flush_cache()
                pg.get_textmap.cache_clear()
            except Exception:
                pass
            if i % 100 == 99:
                gc.collect()
    return out


def cached_text(cache: Path, sha: str, doc_type: str) -> list[str] | None:
    p = cache / f"{sha[:16]}_{doc_type}.json.z"
    if not p.exists():
        return None
    return json.loads(zlib.decompress(p.read_bytes()).decode("utf-8"))["pages"]


def main(cache: Path | None = None) -> pd.DataFrame:
    man = pd.read_csv(ROOT / "data" / "verified_rhp_manifest.csv")
    rows, log = [], []
    for r in man.itertuples():
        p = ROOT / r.local_file
        if not p.exists():
            log.append({"company": r.company, "doc_type": r.doc_type, "status": "missing_file"})
            print(f"  MISSING {r.local_file}")
            continue
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if sha != r.sha256:
            log.append({"company": r.company, "doc_type": r.doc_type, "status": "sha256_mismatch"})
            print(f"  SKIP {p.name}: SHA-256 mismatch — refusing to extract (hard rule 4)")
            continue

        t0 = time.time()
        pages = (cached_text(cache, sha, r.doc_type) if cache else None)
        src = "cache" if pages else "pdf"
        if pages is None:
            pages = page_text_all(p)
        toc = B.parse_toc(p, r.pages) if not cache else {}
        off = B.measure_offset(p, r.pages) if not cache else _offset_from_text(pages)
        doc = B.Doc(p, r.company, r.doc_type, sha, r.url, r.pages, off, toc)

        vals = h6.extract(doc, pages)
        rows += [v.as_row() for v in vals]
        core = [v for v in vals if v.variable in h6.FIELDS]
        ok = sum(v.status == "ok" for v in core)
        amb = sum(v.status == "ambiguous" for v in core)
        na = sum(v.status == "not_applicable" for v in core)
        nf = sum(v.status == "not_found" for v in core)
        log.append({"company": r.company, "doc_type": r.doc_type, "n_fields": len(core),
                    "ok": ok, "ambiguous": amb, "not_applicable": na, "not_found": nf,
                    "offset": off, "source": src, "secs": round(time.time() - t0, 1)})
        print(f"  {r.company[:28]:30s} [{r.doc_type:10s}] offset={off:+d} "
              f"{ok:2d} ok  {amb:2d} ambiguous  {na} n/a  {nf:2d} not_found   "
              f"({time.time() - t0:.0f}s, {src})")
        del pages
        gc.collect()

    obs = pd.DataFrame(rows)
    (ROOT / "reports").mkdir(exist_ok=True)
    obs.to_csv(ROOT / "reports" / "h6_observations.csv", index=False, encoding="utf-8")
    pd.DataFrame(log).to_csv(ROOT / "reports" / "h6_extraction_log.csv", index=False,
                             encoding="utf-8")
    report_coverage(obs)
    return obs


def _offset_from_text(pages: list[str]) -> int:
    """offset = pdf_index - printed_page, from page footers (modal). Cache mode only."""
    from collections import Counter
    import re
    votes = []
    for i in (10, 25, 50, 80, 120, 200):
        if i >= len(pages):
            continue
        lines = [l.strip() for l in (pages[i] or "").splitlines() if l.strip()]
        for ln in (lines[-1:] + lines[-2:-1]):
            if re.fullmatch(r"(\d{1,4})", ln):
                votes.append(i - int(ln))
                break
    return Counter(votes).most_common(1)[0][0] if votes else 0


def report_coverage(obs: pd.DataFrame) -> dict:
    core = obs[obs["variable"].isin(h6.FIELDS)].copy()
    ndocs = core.groupby(["company", "doc_type"]).ngroups
    print("\n" + "=" * 100)
    print(f"H6 FIELD COVERAGE — {len(h6.FIELDS)} fields x {ndocs} documents = "
          f"{len(h6.FIELDS) * ndocs} cells")
    print("=" * 100)

    # crosstab, NOT pivot_table: pivot_table drops rows whose `values` column is NaN, and
    # every not_found row has value=None — so it silently under-counts the misses.
    per_field = (pd.crosstab(core["variable"], core["status"])
                 .reindex(index=h6.FIELDS, fill_value=0)
                 .reindex(columns=["ok", "ambiguous", "not_applicable", "not_found",
                                   "unreadable"], fill_value=0))
    per_field["usable"] = per_field["ok"] + per_field["ambiguous"]
    per_field["applicable"] = ndocs - per_field["not_applicable"]
    per_field["usable_pct"] = (per_field["usable"] / per_field["applicable"] * 100).round(1)
    per_field = per_field.sort_values("usable_pct", ascending=False)

    print(f"\n{'field':42s} {'ok':>3s} {'amb':>4s} {'n/a':>4s} {'miss':>5s} {'usable%':>8s}")
    for f, r in per_field.iterrows():
        mark = "  " if r["usable_pct"] >= TARGET * 100 else " <"
        print(f"{f:42s} {int(r['ok']):3d} {int(r['ambiguous']):4d} "
              f"{int(r['not_applicable']):4d} {int(r['not_found']):5d} "
              f"{r['usable_pct']:7.1f}%{mark}")

    tot = len(core)
    ok = int((core["status"] == "ok").sum())
    amb = int((core["status"] == "ambiguous").sum())
    na = int((core["status"] == "not_applicable").sum())
    summary = {
        "n_fields": len(h6.FIELDS), "n_docs": int(ndocs), "cells": tot,
        "ok": ok, "ambiguous": amb, "not_applicable": na,
        "not_found": int((core["status"] == "not_found").sum()),
        "strict_pct": round(ok / tot * 100, 1),
        "usable_pct": round((ok + amb) / tot * 100, 1),
        "adjusted_pct": round(ok / max(1, tot - na) * 100, 1),
        "usable_adjusted_pct": round((ok + amb) / max(1, tot - na) * 100, 1),
        "target_pct": TARGET * 100,
    }
    print(f"\n  strict   (ok only)            {summary['strict_pct']:5.1f}%")
    print(f"  usable   (ok + ambiguous)     {summary['usable_pct']:5.1f}%   <- judged against "
          f"the {TARGET:.0%} H6 target")
    print(f"  adjusted (excl. structural n/a) {summary['usable_adjusted_pct']:5.1f}%")
    print(f"  {'PASS' if summary['usable_pct'] >= TARGET * 100 else 'BELOW TARGET'}")

    below = [f for f, r in per_field.iterrows() if r["usable_pct"] < TARGET * 100]
    if below:
        print(f"\n  {len(below)} field(s) below {TARGET:.0%} across vintages, named rather "
              f"than rescued by loosening a rule:")
        for f in below:
            print(f"    - {f} ({per_field.loc[f, 'usable_pct']:.0f}%)")
    summary["fields_below_target"] = below

    per_field.to_csv(ROOT / "reports" / "h6_coverage_by_field.csv", encoding="utf-8")
    (ROOT / "reports" / "h6_coverage.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print("\nwritten: reports/h6_observations.csv, h6_coverage_by_field.csv, h6_coverage.json")
    return summary


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    main(Path(a.cache) if a.cache else None)

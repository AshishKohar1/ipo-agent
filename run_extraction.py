"""
run_extraction.py — PLAN.md Stage 8 orchestration.

Processes the manifest one document at a time, verifying each SHA-256 before use (hard
rule 4) and locating sections from the table of contents with a measured printed-page
offset. Each extractor receives only its own page range; the PDF is opened and closed per
range, so memory stays flat (rule 14 — a previous laptop session exhausted 8 GB).

Outputs:
  reports/rhp_observations.csv  every value with full provenance
  reports/rhp_extraction_log.csv one row per document per extractor

    python run_extraction.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import gc
import hashlib
import sys
import time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract import base as B                      # noqa: E402
from extract import objects, basis, financials, capital, litigation, rpt   # noqa: E402

EXTRACTORS = [objects, basis, financials, capital, litigation]   # rpt needs revenue, run after


def main():
    man = pd.read_csv(ROOT / "data" / "verified_rhp_manifest.csv")
    rows, log = [], []
    for r in man.itertuples():
        p = ROOT / r.local_file
        if not p.exists():
            log.append({"company": r.company, "doc_type": r.doc_type,
                        "status": "missing_file"})
            continue
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if sha != r.sha256:
            print(f"  SKIP {p.name}: SHA-256 mismatch — refusing to extract (hard rule 4)")
            log.append({"company": r.company, "doc_type": r.doc_type,
                        "status": "sha256_mismatch"})
            continue

        t0 = time.time()
        toc = B.parse_toc(p, r.pages)
        off = B.measure_offset(p, r.pages)
        doc = B.Doc(p, r.company, r.doc_type, sha, r.url, r.pages, off, toc)
        print(f"\n{r.company[:30]} [{r.doc_type}] pages={r.pages} offset={off:+d} toc={len(toc)}")

        rev_cr = None
        for mod in EXTRACTORS:
            try:
                vals = mod.extract(doc)
            except Exception as e:
                vals = []
                log.append({"company": r.company, "doc_type": r.doc_type,
                            "extractor": mod.NAME, "status": f"error: {type(e).__name__}: {e}"})
                print(f"   {mod.NAME:12s} ERROR {type(e).__name__}: {e}")
            else:
                ok = sum(v.status == "ok" for v in vals)
                amb = sum(v.status == "ambiguous" for v in vals)
                print(f"   {mod.NAME:12s} {ok:2d} ok, {amb} ambiguous, "
                      f"{sum(v.status == 'not_found' for v in vals)} not_found")
                log.append({"company": r.company, "doc_type": r.doc_type,
                            "extractor": mod.NAME, "status": "ran", "n_ok": ok,
                            "n_ambiguous": amb,
                            "n_not_found": sum(v.status == "not_found" for v in vals)})
                rows += [v.as_row() for v in vals]
                if mod is financials:
                    rc = next((v.value_crore for v in vals
                               if v.variable == "revenue_cr" and v.value_crore), None)
                    rev_cr = rc
            gc.collect()

        try:
            vals = rpt.extract(doc, revenue_cr=rev_cr)
            rows += [v.as_row() for v in vals]
            ok = sum(v.status == "ok" for v in vals)
            print(f"   {rpt.NAME:12s} {ok:2d} ok, "
                  f"{sum(v.status == 'not_found' for v in vals)} not_found")
            log.append({"company": r.company, "doc_type": r.doc_type, "extractor": rpt.NAME,
                        "status": "ran", "n_ok": ok})
        except Exception as e:
            print(f"   {rpt.NAME:12s} ERROR {type(e).__name__}: {e}")
            log.append({"company": r.company, "doc_type": r.doc_type, "extractor": rpt.NAME,
                        "status": f"error: {e}"})
        gc.collect()
        print(f"   ({time.time() - t0:.0f}s)")

    obs = pd.DataFrame(rows)
    obs.to_csv(ROOT / "reports" / "rhp_observations.csv", index=False, encoding="utf-8")
    pd.DataFrame(log).to_csv(ROOT / "reports" / "rhp_extraction_log.csv", index=False,
                             encoding="utf-8")
    print(f"\nobservations: {len(obs)} rows -> reports/rhp_observations.csv")
    if len(obs):
        print(obs.groupby("status").size().to_string())
    return obs


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

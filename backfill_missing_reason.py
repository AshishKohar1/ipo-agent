"""
backfill_missing_reason.py — decision H10, applied to rows already on disk.

Two jobs:

1. **Fill the column for existing observations.** The night batch was already running when
   H10 was taken, so its process holds the older `extract/base.py` and its rows carry no
   `missing_reason`. Every refusal note already encodes the reason in words, so
   `classify_missing_reason()` derives the column without re-reading a single PDF.

2. **Emit the rows that were never written at all.** A company whose document could not be
   resolved or failed verification produced *no* observation rows, so its fields are invisible
   rather than missing — and that is precisely what makes a field's final coverage
   uninterpretable. One row per H6 field is written for each such company with
   `missing_reason = document_unavailable`, so the denominator is the whole queue rather
   than only the companies that got as far as an extractor.

Idempotent: safe to run repeatedly while the batch is still going.

    python backfill_missing_reason.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract.base import classify_missing_reason, EXTRACTOR_VERSION   # noqa: E402
from extract import h6                                               # noqa: E402

FILES = [ROOT / "reports" / "h6_observations.csv",
         ROOT / "reports" / "h6_batch_observations.csv"]
PROGRESS = ROOT / "data" / "rhp_progress.csv"
NO_DOC = ("source_unresolved", "not_a_prospectus", "sha256_mismatch", "missing_file",
          "fetch_failed", "failed")


def fill(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    o = pd.read_csv(path, keep_default_na=False)
    if "missing_reason" not in o:
        o["missing_reason"] = ""
    before = int((o["missing_reason"].astype(str).str.len() > 0).sum())
    need = (o["missing_reason"].astype(str).str.len() == 0) & \
           (~o["status"].isin(["ok", "ambiguous"]))
    o.loc[need, "missing_reason"] = [
        classify_missing_reason(n, s) for n, s in
        zip(o.loc[need, "note"], o.loc[need, "status"])]
    # a value that WAS extracted has nothing missing
    o.loc[o["status"].isin(["ok", "ambiguous"]), "missing_reason"] = ""
    o.to_csv(path, index=False, encoding="utf-8")
    return before, int((o["missing_reason"].astype(str).str.len() > 0).sum())


def document_unavailable_rows() -> pd.DataFrame:
    """One row per H6 field for every company that never reached an extractor."""
    if not PROGRESS.exists():
        return pd.DataFrame()
    p = pd.read_csv(PROGRESS, keep_default_na=False)
    bad = p[p["status"].isin(NO_DOC)]
    if not len(bad):
        return pd.DataFrame()
    rows = []
    for r in bad.itertuples():
        for f in h6.FIELDS:
            rows.append({
                "company": r.company, "doc_type": getattr(r, "doc_type", "") or "NONE",
                "variable": f, "value": None, "original_unit": None, "value_crore": None,
                "page": None, "pdf_page_index": None, "source_text": None,
                "doc_url": getattr(r, "url", "") or None,
                "sha256": getattr(r, "sha256", "") or None,
                "extractor": "h6", "extractor_version": EXTRACTOR_VERSION,
                "status": "not_found", "missing_reason": "document_unavailable",
                "note": f"no document reached an extractor for this company "
                        f"(batch status '{r.status}': {str(getattr(r, 'note', ''))[:150]}). "
                        "Written so the field's coverage denominator is the whole queue, "
                        "not only the companies a document was obtained for.",
            })
    return pd.DataFrame(rows)


def main():
    for f in FILES:
        b, a = fill(f)
        if a:
            print(f"{f.name}: missing_reason set on {a} rows (was {b})")
        elif f.exists():
            print(f"{f.name}: nothing to fill")

    dl = document_unavailable_rows()
    if len(dl):
        target = ROOT / "reports" / "h6_document_unavailable.csv"
        dl.to_csv(target, index=False, encoding="utf-8")
        print(f"{target.name}: {len(dl)} rows for "
              f"{dl['company'].nunique()} companies with no usable document "
              f"({len(h6.FIELDS)} fields each)")

    # a combined view, so coverage can be read off one file
    parts = [pd.read_csv(f, keep_default_na=False) for f in FILES if f.exists()]
    if len(dl):
        parts.append(dl)
    if parts:
        allo = pd.concat(parts, ignore_index=True)
        allo = allo[allo["variable"].isin(h6.FIELDS)]
        out = ROOT / "reports" / "h6_coverage_with_reason.csv"
        tab = (pd.crosstab(allo["variable"], allo["missing_reason"].replace("", "EXTRACTED"))
               .reindex(index=h6.FIELDS, fill_value=0))
        for c in ("EXTRACTED", *sorted(set(allo["missing_reason"]) - {""})):
            if c not in tab:
                tab[c] = 0
        tab["total"] = tab.sum(axis=1)
        tab["extracted_pct"] = (tab["EXTRACTED"] / tab["total"] * 100).round(1)
        tab = tab.sort_values("extracted_pct", ascending=False)
        tab.to_csv(out, encoding="utf-8")
        print(f"\n{out.name} — coverage with the H10 reason for every gap "
              f"({len(allo)} rows, {allo['company'].nunique()} companies):\n")
        cols = [c for c in ["EXTRACTED", "not_present_on_page", "present_but_unparsed",
                            "section_not_found", "document_unavailable"] if c in tab]
        print(f"{'field':42s} " + " ".join(f"{c[:11]:>12s}" for c in cols) + "   extracted%")
        for f, r in tab.iterrows():
            print(f"{f:42s} " + " ".join(f"{int(r[c]):12d}" for c in cols)
                  + f"   {r['extracted_pct']:7.1f}%")
    return


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

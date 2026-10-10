"""
build_documents_needed.py — Task 1: the manual-sourcing list.

Every company in the Stage 15b queue whose document never reached an extractor, so the user
can source those RHPs by hand. A company here contributes **30 empty H6 fields** to the
dataset, which is why they matter out of proportion to their number: they do not lower a
field's coverage a little, they are invisible unless `missing_reason` records them (H10).

Three failure classes, kept separate because they need different action:

  `source_unresolved`   SEBI's archive has no document matching the company name and the
                        filing window. Usually a name mismatch — the user can find it from
                        the company's own site or the exchange filing.
  `not_a_prospectus`    A document WAS found and downloaded, but `_verify_is_prospectus()`
                        rejected it: wrong company on the cover, missing prospectus marker,
                        or under 100 pages. The URL is recorded, so the user can check
                        whether the verifier was right or over-strict.
  `fetch_error`         SEBI refused the connection. **Not a missing document** — these are
                        retryable and are flagged as such, because asking the user to source
                        a PDF by hand that a re-run would fetch wastes their time.

    python build_documents_needed.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "DOCUMENTS_NEEDED.csv"

COLS = ["company", "isin", "issue_year", "url_attempted", "failure_reason",
         "failure_class", "retryable", "queries_tried", "note", "sebi_search_hint"]


def classify(status: str, note: str) -> tuple[str, bool]:
    n = (note or "")
    if "ConnectionError" in n or "Max retries" in n or "Timeout" in n or "timed out" in n:
        return "fetch_error", True
    if status == "not_a_prospectus":
        return "not_a_prospectus", False
    return "source_unresolved", False


def main() -> pd.DataFrame:
    p = pd.read_csv(ROOT / "data" / "rhp_progress.csv", keep_default_na=False, na_values=[""])
    bad = p[~p["status"].isin(["done"])].copy()
    if not len(bad):
        print("no failures — nothing to source by hand")
        return pd.DataFrame()

    # The batch retried source_unresolved companies before the resumability fix landed, so
    # the progress file can hold the same company twice. Keep the LAST attempt.
    bad = bad.drop_duplicates(subset=["company"], keep="last")

    m = pd.read_csv(ROOT / "data" / "master_with_symbols.csv")
    m_isin = dict(zip(m["company"], m["isin"]))
    # listing_date is missing on rows the first run wrote, so the year is filled from the
    # master. An issue year is the first thing needed to find a filing by hand.
    m["ld"] = pd.to_datetime(m["listing_date"], errors="coerce")
    m_year = {c: (None if pd.isna(d) else int(d.year))
              for c, d in zip(m["company"], m["ld"])}
    m_year_isin = {i: (None if pd.isna(d) else int(d.year))
                   for i, d in zip(m["isin"], m["ld"])}

    # Third fallback: the completed Chittorgarh harvest, matched on a normalised name. The
    # master's listing_date is NaN for 13 of these companies, and an issue year is the first
    # thing needed to find a filing by hand, so it is worth a second lookup rather than
    # handing over a list with "????" in it.
    def norm(s):
        s = re.sub(r"(?i)(limited|ltd|private|pvt|india|the)", "", str(s))
        return re.sub(r"[^a-z0-9]", "", s.lower())

    cg_year = {}
    cg_path = ROOT / "data" / "chittorgarh_backfill.csv"
    if cg_path.exists():
        cg = pd.read_csv(cg_path, keep_default_na=False, na_values=[""])
        cg["ld"] = pd.to_datetime(cg["listed_on"], errors="coerce", format="mixed")
        for c, d in zip(cg["company"], cg["ld"]):
            k = norm(c)
            if k and not pd.isna(d) and k not in cg_year:
                cg_year[k] = int(d.year)

    rows = []
    for r in bad.itertuples():
        note = str(getattr(r, "note", "") or "")
        cls, retry = classify(r.status, note)
        yr = pd.to_datetime(getattr(r, "listing_date", None), errors="coerce")
        q = re.search(r"queries \[(.*?)\]", note)
        rows.append({
            "company": r.company,
            "isin": getattr(r, "isin", None) or m_isin.get(r.company),
            "issue_year": (int(yr.year) if not pd.isna(yr)
                           else m_year.get(r.company)
                           or m_year_isin.get(getattr(r, "isin", None))
                           or cg_year.get(norm(r.company))
                           or next((v for k, v in cg_year.items()
                                    if k and norm(r.company)[:12]
                                    and k.startswith(norm(r.company)[:12])), None)),
            "url_attempted": getattr(r, "url", None) or "(none — resolver found no URL)",
            "failure_reason": note[:300] or r.status,
            "failure_class": cls,
            "retryable": retry,
            "queries_tried": q.group(1) if q else "",
            "note": ("SEBI refused the connection — a re-run will probably fetch this. "
                     "Do NOT source by hand yet." if retry else
                     "A document was found but failed verification — check the URL before "
                     "sourcing; the verifier may have been right." if cls == "not_a_prospectus"
                     else "No match in SEBI's archive for this name and filing window."),
            "sebi_search_hint": ("https://www.sebi.gov.in/filings/public-issues "
                                 f"— search '{str(r.company).split()[0]}'"),
        })

    out = pd.DataFrame([{c: r.get(c) for c in COLS} for r in rows], columns=COLS)
    out = out.sort_values(["failure_class", "issue_year", "company"],
                          na_position="last").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")

    hand = out[~out["retryable"]]
    print(f"{len(out)} companies never reached an extractor "
          f"= {len(out) * 30} empty H6 field-cells")
    print(f"  {len(hand)} genuinely need manual sourcing")
    print(f"  {int(out['retryable'].sum())} are RETRYABLE (SEBI refused the connection) — "
          f"a re-run should fetch these, do not source them by hand")
    print()
    print(out["failure_class"].value_counts().to_string())
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

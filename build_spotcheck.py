"""
build_spotcheck.py — PLAN.md Stage 8 step 7: the hand-verification sheet.

Selects extracted values across all five companies, at least three per company, weighted
towards fields where the unit (lakh / million / crore) decides the answer. Every row
carries the page number and the exact source line so the user can open the SEBI or BSE SME
document and check it without trusting the pipeline.

Only `ok` and `ambiguous` values are eligible — a `not_found` has nothing to verify.
`ambiguous` rows are included deliberately and labelled, because those are the ones most
worth a human eye.

    python build_spotcheck.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent

# field -> (friendly label, is the unit decisive?)
PRIORITY = {
    "issue_size_cr":        ("Issue size", True),
    "has_fresh_issue":      ("Fresh issue present", False),
    "has_ofs":              ("Offer for sale present", False),
    "revenue_cr":           ("Revenue from operations", True),
    "total_income_cr":      ("Total income", True),
    "pat_cr":               ("Profit after tax", True),
    "pbt_cr":               ("Profit before tax", True),
    "net_worth_cr":         ("Net worth / total equity", True),
    "borrowings_cr":        ("Total borrowings", True),
    "ocf_cr":               ("Operating cash flow", True),
    "pe_at_issue":          ("P/E at the offer price", False),
    "peer_1_pe":            ("Peer multiple (peer 1 P/E)", False),
    "peer_2_pe":            ("Peer multiple (peer 2 P/E)", False),
    "peer_count":           ("Listed peers in the table", False),
    "eps_basic":            ("Basic EPS, latest FY", False),
    "eps_weighted_avg":     ("Basic EPS, weighted average", False),
    "ronw_pct":             ("Return on net worth", False),
    "nav_per_share":        ("NAV per equity share", False),
    "rpt_pct_revenue":      ("Related-party txns % of revenue", False),
    "uses_of_proceeds_n":   ("Stated uses of proceeds", False),
    "pre_ipo_allotment_count": ("Pre-IPO allotment rows", False),
}
TARGET_ROWS, MIN_PER_COMPANY = 20, 3


def main():
    o = pd.read_csv(ROOT / "reports" / "rhp_observations.csv")
    e = o[o["status"].isin(["ok", "ambiguous"])].copy()
    e = e[e["variable"].isin(PRIORITY)]
    e["label"] = e["variable"].map(lambda v: PRIORITY[v][0])
    e["unit_matters"] = e["variable"].map(lambda v: PRIORITY[v][1])
    # prefer the final prospectus over the RHP (RHP amounts carry [·] placeholders)
    e["doc_rank"] = (e["doc_type"] != "PROSPECTUS").astype(int)
    e = e.sort_values(["company", "doc_rank", "unit_matters", "variable"],
                      ascending=[True, True, False, True])
    e = e.drop_duplicates(["company", "variable"])

    picked = []
    for comp, grp in e.groupby("company"):
        picked.append(grp.head(max(MIN_PER_COMPANY, 4)))
    sel = pd.concat(picked)
    if len(sel) < TARGET_ROWS:                     # top up with the most unit-sensitive rest
        rest = e.drop(sel.index).sort_values("unit_matters", ascending=False)
        sel = pd.concat([sel, rest.head(TARGET_ROWS - len(sel))])
    sel = sel.sort_values(["company", "unit_matters"], ascending=[True, False]).reset_index(drop=True)

    sheet = pd.DataFrame({
        "#": range(1, len(sel) + 1),
        "Company": sel["company"],
        "Field": sel["label"],
        "Extracted value + unit": [
            (f"{v:,.2f} {u}" if isinstance(v, float) and u not in (None, "bool", "count")
             else ("yes" if u == "bool" and v == 1 else "no" if u == "bool" else
                   f"{v:,.0f} {u}" if u == "count" else f"{v}"))
            for v, u in zip(sel["value"], sel["original_unit"])],
        "Rs crore": [f"{c:,.2f}" if pd.notna(c) else "n/a" for c in sel["value_crore"]],
        "Page": sel["page"].astype("Int64"),
        "Exact source text line": sel["source_text"],
        "Document": sel["doc_type"],
        "Flag": ["CHECK (ambiguous)" if s == "ambiguous" else "" for s in sel["status"]],
        "Document link": sel["doc_url"],
    })
    sheet.to_csv(ROOT / "reports" / "SPOTCHECK.csv", index=False, encoding="utf-8")
    try:
        sheet.to_excel(ROOT / "reports" / "SPOTCHECK.xlsx", index=False)
        xl = "reports/SPOTCHECK.xlsx"
    except Exception as ex:
        xl = f"(xlsx failed: {ex})"
    print(f"rows {len(sheet)} | companies {sheet['Company'].nunique()} | "
          f"unit-sensitive {int(sel['unit_matters'].sum())}")
    print(f"written: reports/SPOTCHECK.csv and {xl}")
    print(sheet["Company"].value_counts().to_string())
    return sheet


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

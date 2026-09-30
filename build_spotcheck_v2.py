"""
build_spotcheck_v2.py — the Gate C2 hand-verification sheet.

Drawn **only from H6 fields** (decision H6) — the headline financials that H5 moved to the
aggregator are not eligible, which is what makes this sheet different from
`reports/SPOTCHECK.csv`. Source: `reports/h6_observations.csv`, the validated run over the
eight documents in `data/verified_rhp_manifest.csv`.

Selection: at least 4 rows per company, spread across the H6 groups rather than clustered on
whichever group extracts best, and weighted towards the rows where getting it wrong would
matter most — a governance flag that drives a veto, a percentage whose year alignment could
be off, an amount whose unit decides a 100x error.

`ambiguous` rows are included deliberately and labelled. Those are the ones most worth a
human eye, and hiding them would make the sheet look better than the pipeline is.

    python build_spotcheck_v2.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent

# field -> (label, group, why this row is worth checking)
LABELS = {
    "rpt_pct_revenue":        ("Related-party txns, % of revenue", "related party", "veto red flag 3 at >20%; year alignment"),
    "rpt_amount_cr":          ("Related-party value", "related party", "unit decides the magnitude"),
    "litigation_criminal_count": ("Criminal proceedings, count", "litigation", "veto red flag 6"),
    "litigation_criminal_promoters_directors": ("Criminal cases naming promoters/directors", "litigation", "veto red flag 6"),
    "litigation_tax_count":   ("Tax matters, count", "litigation", "MSCI tax transparency"),
    "litigation_statutory_count": ("Statutory/regulatory actions, count", "litigation", "MSCI business ethics"),
    "litigation_aggregate_amount_cr": ("Litigation amount involved", "litigation", "unit decides the magnitude"),
    "customer_concentration_top10_pct": ("Top-10 customer concentration", "concentration", "veto red flag 4 at >40%; year order differs by document"),
    "customer_concentration_top5_pct": ("Top-5 customer concentration", "concentration", "year order"),
    "geographic_concentration_flag": ("Geographic concentration disclosed", "concentration", "flag, not a measured share"),
    "licence_dependence_flag": ("Licence / approval dependence", "concentration", "veto red flag 4"),
    "promoter_experience_years": ("Promoter experience", "governance", "attribution: promoter vs any director"),
    "board_size_n":           ("Board size", "governance", "word-numbers and composition sums"),
    "independent_directors_n": ("Independent directors", "governance", "MSCI board"),
    "board_independence_ratio": ("Board independence ratio", "governance", "derived from both counts"),
    "kmp_remuneration_cr":    ("Director / KMP remuneration", "governance", "one person or the total?"),
    "auditor_qualification_flag": ("Auditor qualification", "governance", "veto red flag 2; POLARITY"),
    "auditor_emphasis_flag":  ("Emphasis of matter", "governance", "POLARITY; absence read as a real 0"),
    "pre_ipo_placement_flag": ("Pre-IPO placement", "ownership", "veto red flag 5"),
    "pre_ipo_placement_amount_cr": ("Pre-IPO placement amount", "ownership", "unit"),
    "promoter_holding_pre_pct": ("Promoter holding, pre-offer", "ownership", "promoters vs promoter GROUP"),
    "promoter_holding_post_pct": ("Promoter holding, post-offer", "ownership", "holding vs lock-in requirement"),
    "promoter_lockin_months": ("Promoter lock-in", "ownership", "which lock-in of several"),
    "esop_exists_flag":       ("ESOP scheme exists", "ownership", "POLARITY"),
    "dual_class_flag":        ("Dual-class / differential voting", "ownership", "absence read as a real 0"),
    "contingent_liabilities_cr": ("Contingent liabilities", "balance sheet", "unit; total vs summed items"),
    "uses_of_proceeds_n":     ("Stated uses of proceeds", "objects", "n/a on a pure offer for sale"),
    "gcp_pct_proceeds":       ("GCP as % of proceeds", "objects", "derived from a summed total"),
    "anchor_portion_shares":  ("Anchor portion, shares", "anchor", "reserved, not the book allotted"),
    "anchor_mf_reserved_pct": ("Mutual-fund share of anchor portion", "anchor", "the SEBI minimum, not actual demand"),
}
# rows whose correctness matters most, tried first for each company
PRIORITY_GROUPS = ["governance", "ownership", "related party", "litigation",
                   "concentration", "balance sheet", "objects", "anchor"]
PER_COMPANY, TARGET = 4, 20


def main():
    o = pd.read_csv(ROOT / "reports" / "h6_observations.csv")
    e = o[o["status"].isin(["ok", "ambiguous"]) & o["value"].notna()].copy()
    e = e[e["variable"].isin(LABELS)]
    # A row with no page and no quoted line cannot be spot-checked, and the whole purpose of
    # this sheet is checkability. That excludes the "absence read as a real 0" flags
    # (dual-class voting, emphasis of matter on documents where the phrase never occurs):
    # they are legitimate values, but there is no line to open the PDF at. The first draft
    # of this sheet was half filled with them, which made it unusable.
    e = e[e["page"].notna() & e["source_text"].notna()]
    e["label"] = e["variable"].map(lambda v: LABELS[v][0])
    e["group"] = e["variable"].map(lambda v: LABELS[v][1])
    e["why"] = e["variable"].map(lambda v: LABELS[v][2])
    e["grp_rank"] = e["group"].map(lambda g: PRIORITY_GROUPS.index(g))
    # the final prospectus beats the RHP: an RHP states amounts as [·] placeholders
    e["doc_rank"] = (~e["doc_type"].str.upper().str.startswith("PROS")).astype(int)
    e = e.sort_values(["company", "doc_rank", "grp_rank", "variable"])
    e = e.drop_duplicates(["company", "variable"])

    picked = []
    for comp, grp in e.groupby("company"):
        # one row per group first, so a company is not represented by four governance flags
        # one per group first, so a company is not represented by four flags from one group
        first = grp.drop_duplicates("group").head(PER_COMPANY)
        if len(first) < PER_COMPANY:
            first = pd.concat([first, grp.drop(first.index).head(PER_COMPANY - len(first))])
        # prefer an ambiguous row over a fourth safe one — those are the rows most worth a
        # human eye, and a sheet that hides them flatters the pipeline
        amb = grp[(grp["status"] == "ambiguous") & ~grp.index.isin(first.index)]
        if len(amb) and (first["status"] == "ambiguous").sum() == 0:
            first = pd.concat([first.head(PER_COMPANY - 1), amb.head(1)])
        picked.append(first)
    sel = pd.concat(picked)
    if len(sel) < TARGET:
        rest = e.drop(sel.index).sort_values(["grp_rank", "company"])
        sel = pd.concat([sel, rest.head(TARGET - len(sel))])
    sel = sel.sort_values(["company", "grp_rank"]).reset_index(drop=True)

    def show(v, u):
        if u == "bool":
            return "yes" if v == 1 else "no"
        if u in ("count", "shares"):
            return f"{v:,.0f}"
        if u == "%":
            return f"{v:.2f}%"
        if u == "years":
            return f"{v:.0f} years"
        if u == "months":
            return f"{v:.0f} months"
        if u == "ratio":
            return f"{v:.3f}"
        if u == "completeness":
            return f"{v:.2f}"
        return f"{v:,.2f} {u}" if isinstance(u, str) else f"{v:,.2f}"

    sheet = pd.DataFrame({
        "#": range(1, len(sel) + 1),
        "Company": sel["company"],
        "Field": sel["label"],
        "Extracted value": [show(v, u) for v, u in zip(sel["value"], sel["original_unit"])],
        "Rs crore": [f"{c:,.2f}" if pd.notna(c) else "" for c in sel["value_crore"]],
        "Page": sel["page"].astype("Int64"),
        "Exact source text line": sel["source_text"],
        "Document URL": sel["doc_url"],
        "Doc": sel["doc_type"],
        "Flag": ["CHECK (ambiguous)" if s == "ambiguous" else "" for s in sel["status"]],
        "Why this row": sel["why"],
    })
    sheet.to_csv(ROOT / "reports" / "SPOTCHECK_V2.csv", index=False, encoding="utf-8")
    try:
        sheet.to_excel(ROOT / "reports" / "SPOTCHECK_V2.xlsx", index=False)
        xl = "reports/SPOTCHECK_V2.xlsx"
    except Exception as ex:
        xl = f"(xlsx failed: {ex})"
    print(f"rows {len(sheet)} | companies {sheet['Company'].nunique()} | "
          f"ambiguous {(sel['status'] == 'ambiguous').sum()} | "
          f"groups {sel['group'].nunique()}")
    print(f"written: reports/SPOTCHECK_V2.csv and {xl}")
    print(sheet["Company"].value_counts().to_string())
    return sheet


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

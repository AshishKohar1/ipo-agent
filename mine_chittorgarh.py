"""
mine_chittorgarh.py — Priority 2d: every Model H field the completed harvest already holds.

2,861 companies were fetched in a previous session and are sitting on disk. Zero further
requests, so this is the cheapest coverage available anywhere in the project — and it reaches
back to 2010, which the RHP batch (485 queued, working backwards from 2025) will not do for
months.

What the harvest carries beyond promoter holding and anchors:

  financials       total income, PAT, net worth, reserves, borrowings, EBITDA, assets
  valuation        EPS pre/post, P/E pre/post, market cap at offer, RoE, RoCE, D/E, RoNW
  issue structure  issue size, fresh issue, OFS, price band, face value, lot size
  demand           final QIB / NII / Retail / Total subscription
  objects          number of stated uses, GCP present, GCP % of proceeds
  dates            issue window, listing date

**Derived ratios are computed only where both inputs exist**, never imputed. Each is a ratio
of two same-unit figures, so the unit ambiguity that dogs RHP extraction cannot arise.

**Everything here is single-source** (Chittorgarh) and tagged so. Where the master dataset
holds the same quantity it is reconciled under rule 2 and both values kept.

    python mine_chittorgarh.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "chittorgarh_backfill.csv"
OUT = ROOT / "data" / "model_h_from_aggregator.csv"
RECON = ROOT / "reports" / "aggregator_reconciliation.csv"
TOL = 0.05

DIRECT = ["issue_size_cr", "fresh_issue_cr", "ofs_cr", "face_value", "lot_size",
          "total_income_cr", "pat_cr", "net_worth_cr", "reserves_cr", "borrowings_cr",
          "ebitda_cr", "assets_cr", "eps_pre", "eps_post", "pe_pre", "pe_post",
          "market_cap_at_offer_cr", "roe_pct", "roce_pct", "debt_equity", "ronw_pct",
          "promoter_pre_pct", "promoter_post_pct", "total_subscription_x", "qib_x",
          "nii_x", "retail_x", "uses_of_proceeds_n", "has_gcp", "gcp_pct_proceeds",
          "anchor_portion_cr", "anchor_shares", "anchor_pct_of_issue"]


def main() -> dict:
    c = pd.read_csv(SRC, keep_default_na=False, na_values=[""])
    print(f"{len(c)} harvested companies on disk — zero requests needed")
    for col in DIRECT:
        if col in c:
            c[col] = pd.to_numeric(c[col], errors="coerce")
    c["listed"] = pd.to_datetime(c["listed_on"], errors="coerce", format="mixed")
    c["listing_year"] = c["listed"].dt.year

    f = pd.DataFrame({"company": c["company"], "ipo_id": c["ipo_id"],
                      "listing_date": c["listed"], "listing_year": c["listing_year"]})
    for col in DIRECT:
        if col in c:
            f[col] = c[col]

    def ratio(num, den, lo=None, hi=None):
        """num/den where both exist; never imputed, and clipped only to reject nonsense."""
        a, b = c.get(num), c.get(den)
        if a is None or b is None:
            return pd.Series(np.nan, index=c.index)
        with np.errstate(divide="ignore", invalid="ignore"):
            r = a / b.where((b.notna()) & (b != 0))
        if lo is not None:
            r = r.where((r >= lo) & (r <= hi))
        return r

    # ---- derived ratios: both inputs same-unit, so no unit ambiguity can arise
    f["pat_margin_pct"] = ratio("pat_cr", "total_income_cr", -10, 10) * 100
    f["debt_to_networth"] = ratio("borrowings_cr", "net_worth_cr", -50, 50)
    f["ebitda_margin_pct"] = ratio("ebitda_cr", "total_income_cr", -10, 10) * 100
    f["asset_turnover"] = ratio("total_income_cr", "assets_cr", 0, 50)
    f["issue_to_networth"] = ratio("issue_size_cr", "net_worth_cr", 0, 200)
    f["mcap_to_income"] = ratio("market_cap_at_offer_cr", "total_income_cr", 0, 500)
    f["ofs_share_pct"] = ratio("ofs_cr", "issue_size_cr", 0, 1.5) * 100
    f["fresh_share_pct"] = ratio("fresh_issue_cr", "issue_size_cr", 0, 1.5) * 100
    f["promoter_dilution_pp"] = c.get("promoter_pre_pct") - c.get("promoter_post_pct")
    f["eps_dilution_pct"] = (ratio("eps_post", "eps_pre", -10, 10) - 1) * 100
    # veto red flag 7: OFS over 50% of the issue
    f["ofs_over_50pct"] = (f["ofs_share_pct"] > 50).astype(float).where(
        f["ofs_share_pct"].notna())
    f["anchor_book_existed"] = np.where(
        c.get("anchor_portion_cr").notna() | c.get("anchor_shares").notna(), 1.0,
        np.where(c["listing_year"] >= 2022, 0.0, np.nan))
    f["source"] = "chittorgarh"
    f["single_source_unverified"] = True

    OUT.parent.mkdir(parents=True, exist_ok=True)
    f.to_csv(OUT, index=False, encoding="utf-8")

    # ---- rule 2 against the master, on the quantities both hold
    m = pd.read_csv(ROOT / "data" / "master_with_symbols.csv")

    def norm(s):
        s = re.sub(r"(?i)\b(limited|ltd|private|pvt|india|the|ipo)\b", "", str(s))
        return re.sub(r"[^a-z0-9]", "", s.lower())

    m["k"] = m["company"].map(norm)
    f["k"] = f["company"].map(norm)
    j = f.merge(m[["k", "company", "Issue_Size(crores)", "Total"]], on="k",
                how="inner", suffixes=("_cg", "_m"))
    # A column named "Issue_Size(crores)" cannot be read with getattr on an itertuples
    # row -- pandas mangles it -- which is why the first run reconciled nothing at all.
    # Renaming first and indexing by label is both correct and legible.
    j = j.rename(columns={"Issue_Size(crores)": "master_issue_size_cr",
                          "Total": "master_total_x"})
    rows = []
    for cg_col, m_col, label in (("issue_size_cr", "master_issue_size_cr", "issue_size_cr"),
                                 ("total_subscription_x", "master_total_x",
                                  "total_subscription_x")):
        if cg_col not in j or m_col not in j:
            continue
        sub = j[[("company_m" if "company_m" in j else "company"), cg_col, m_col]].dropna()
        for _, r in sub.iterrows():
            a_v, b_v = float(r[cg_col]), float(r[m_col])
            hi = max(abs(a_v), abs(b_v)) or 1.0
            d = abs(a_v - b_v) / hi
            rows.append({"company": r.iloc[0], "field": label, "chittorgarh": a_v,
                         "master": b_v, "rel_diff_pct": round(d * 100, 3),
                         "verdict": "PASS" if d <= TOL else "MISMATCH -> flag both",
                         "note": "both values kept; neither is trusted on a mismatch "
                                 "(rule 2)"})
    rec = pd.DataFrame(rows)
    if len(rec):
        rec.to_csv(RECON, index=False, encoding="utf-8")

    # ---- coverage and variance, together (the Task 5 discipline)
    print(f"\n{'field':26s} {'n':>6s} {'cov%':>6s} {'distinct':>8s} {'major%':>7s}")
    report = []
    for col in [c for c in f.columns if c not in
                ("company", "ipo_id", "listing_date", "source", "k",
                 "single_source_unverified")]:
        v = pd.to_numeric(f[col], errors="coerce").dropna()
        cov = len(v) / len(f) * 100
        maj = (v.value_counts().iloc[0] / len(v) * 100) if len(v) else None
        report.append({"field": col, "n": len(v), "coverage_pct": round(cov, 1),
                       "distinct": int(v.nunique()),
                       "majority_share_pct": None if maj is None else round(maj, 1)})
        if cov >= 20:
            print(f"{col:26s} {len(v):6d} {cov:5.1f}% {v.nunique():8d} "
                  f"{'' if maj is None else f'{maj:6.1f}%'}")
    pd.DataFrame(report).to_csv(ROOT / "reports" / "aggregator_coverage.csv", index=False,
                                encoding="utf-8")
    if len(rec):
        print(f"\nrule 2 vs the master: {rec['verdict'].value_counts().to_dict()}")
    print(f"\nwritten: {OUT.relative_to(ROOT)}, reports/aggregator_coverage.csv")
    return {"companies": int(len(f)), "fields": len(report),
            "reconciled": None if not len(rec) else rec["verdict"].value_counts().to_dict()}


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    print(json.dumps(main(), indent=2, default=str))

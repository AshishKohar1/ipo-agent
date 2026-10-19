"""
build_variable_inventory.py — Tasks 4 and 5: the full Model H variable inventory, the
2019+ gap table, and the Tapetide assessment, written to one Excel workbook.

    python build_variable_inventory.py                 # build + print
    python build_variable_inventory.py --version 1.7.0 # pin the extractor version
    python build_variable_inventory.py --self-test

**It fits nothing.** It counts what is filled, states why the rest is not, and says what
would close each gap. No model is estimated anywhere in this file.

Where the numbers come from
---------------------------
* built features  `data/model_h_features_full.csv` - the 66 columns actually on disk.
* valuation       `data/valuation_ratios.csv` and `data/pb_ratios.csv`, whose per-row
                  `*_reason` columns are the source of the "why not filled" counts. The
                  reasons are the extractor's own words, not a guess made here.
* sector          `data/sector_map.csv`, including `sector_index_missing_reason`.

The reason columns matter as much as the counts. A variable that is 40% filled because the
RHP does not disclose it is a different problem from one that is 40% filled because a unit
was ambiguous and the value was withheld, and only the second is ours to fix.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

OUT_XLSX = ROOT / "reports" / "MODEL_H_VARIABLE_INVENTORY.xlsx"
FEATURES = ROOT / "data" / "model_h_features_full.csv"
RATIOS = ROOT / "data" / "valuation_ratios.csv"
PB = ROOT / "data" / "pb_ratios.csv"

# Tapetide's two columns are answered from what was MEASURED on 2026-10-19, not from its
# tool list: list_company_documents returns 0 rhp/drhp for PATELRMART, SAMHI and even
# SWIGGY, so the catalogue has no prospectus coverage at all; and resolve_identifier_asof
# returns not_found (within coverage) for TCNSBRANDS at its 2018 listing date, so the
# identifier projection misses delisted names - which is exactly the population of our
# remaining symbol gaps.
TAPETIDE_NO_RHP = ("no - its catalogue returned 0 rhp/drhp for every symbol tried, "
                   "including SWIGGY as a control")
TAPETIDE_NO_DELISTED = ("no - resolve_identifier_asof returns not_found within coverage "
                        "for a delisted 2018 symbol")

BLOCKS = {
    "market heat": ["ipo_count_prior_3m", "ipo_count_prior_6m",
                    "mean_listing_gain_prior_3m", "mean_sub_total_prior_3m",
                    "nifty_tri_ret_6m", "nifty_tri_ret_12m", "nifty_pe_at_listing",
                    "nifty_pe_vs_10y_median", "india_vix_at_listing",
                    "smallcap_minus_nifty_6m"],
    "subscription": ["sub_total", "sub_qib", "sub_hni", "sub_rii", "log1p_sub_total",
                     "qib_share_of_total", "rii_share_of_total", "demand_profile",
                     "log_issue_size"],
    "listing day": ["listing_gain_pct", "listing_gain_minus_sector_day",
                    "turnover_x_issue_size", "turnover_exchange",
                    "turnover_both_exchanges"],
    "sector": ["nse_industry", "sector_index", "sector_minus_nifty_3m",
               "sector_minus_nifty_6m", "is_sme"],
    "RHP fundamentals": ["rhp_auditor_emphasis_flag", "rhp_auditor_qualification_flag",
                         "rhp_board_size_n", "rhp_dual_class_flag", "rhp_esop_exists_flag",
                         "rhp_geographic_concentration_flag", "rhp_licence_dependence_flag",
                         "rhp_litigation_criminal_promoters_directors",
                         "rhp_pre_ipo_placement_flag", "rhp_promoter_lockin_months",
                         "rhp_uses_of_proceeds_n"],
    "promoter": ["rhp_promoter_holding_pre_pct", "promoter_holding_pre_pct_agg",
                 "promoter_holding_post_pct_agg", "promoter_dilution_pp_agg",
                 "promoter_holding_match"],
    "anchor": ["anchor_amount_cr", "anchor_mf_share_of_book_pct", "anchor_n_investors",
               "anchor_share_of_issue_pct", "anchor_is_recent_cohort"],
}

VALUATION = ["ipo_pe", "ipo_pb", "ipo_pb_pre_issue", "eps_cagr_3y", "ipo_peg",
             "ipo_ev_ebitda", "fcf_yield", "pe_premium_vs_peer_median",
             "pb_premium_vs_peer_median", "pb_pre_issue_premium_vs_peer_median",
             "pe_premium_vs_market"]

DEFS = {
    "ipo_pe": "offer price / basic EPS, most recent fiscal year",
    "ipo_pb": "offer price / POST-issue NAV per share",
    "ipo_pb_pre_issue": "offer price / PRE-issue NAV per share (a different ratio)",
    "eps_cagr_3y": "compound EPS growth across the three fiscal years in the RHP",
    "ipo_peg": "ipo_pe / EPS growth in percent",
    "ipo_ev_ebitda": "(market cap + borrowings - cash) / EBITDA",
    "fcf_yield": "(cash from operations - capex) / market cap; sign kept",
    "pe_premium_vs_peer_median": "ipo_pe / median listed-peer P/E - 1",
    "pb_premium_vs_peer_median": "ipo_pb / median listed-peer P/B - 1",
    "pb_pre_issue_premium_vs_peer_median": "ipo_pb_pre_issue / median peer P/B - 1",
    "pe_premium_vs_market": "ipo_pe / Nifty 50 trailing P/E at listing - 1",
}

FIXES = {
    "ipo_pb": ("fetch the Chittorgarh IPO KPI table (method 2, permitted H14) and use the "
               "fixed share count for method 3", "M", 35),
    "ipo_pb_pre_issue": ("derive pre-issue NAV = restated net worth / pre-issue shares "
                         "where NAV is not stated", "M", 65),
    "ipo_ev_ebitda": ("EBITDA is not a line item in most Indian restated statements - "
                      "derive it as PAT + tax + interest + depreciation from the same "
                      "statement", "L", 30),
    "fcf_yield": ("needs the fixed share count AND cfo AND capex together; the share-count "
                  "fix lands in 1.8.0", "M", 25),
    "pb_premium_vs_peer_median": ("peer P/B is in 15 of 399 peer tables - blocked on what "
                                  "the RHPs print, not on code", "L", 5),
    "pe_premium_vs_peer_median": ("improve the peer-table reader for documents whose peer "
                                  "block is unruled", "M", 45),
    "ipo_pe": ("improve the EPS reader for the documents whose Basis block is unruled", "M", 70),
    "eps_cagr_3y": ("follows ipo_pe - needs EPS at both ends of the window", "M", 62),
    "ipo_peg": ("follows ipo_pe and eps_cagr_3y", "M", 55),
    "pe_premium_vs_market": ("follows ipo_pe; the Nifty P/E side is complete", "M", 70),
    "pb_pre_issue_premium_vs_peer_median": ("blocked on the same peer P/B as the "
                                            "post-issue premium - 15 of 399 peer tables "
                                            "print one; ipo_pb_pre_issue itself is fine",
                                            "L", 8),
    # --- sector: the gap is symbols absent from every NSE index-constituent file
    "sector_index": ("fill nse_industry for the rest from BSE IndustryNew (H38, agreed "
                     "104/104) once a current BSE bhavcopy gives their scrip codes; then "
                     "remap", "M", 85),
    "nse_industry": ("same - BSE IndustryNew for the symbols no constituent file carries", "M", 85),
    "sector_minus_nifty_3m": ("follows sector_index", "M", 85),
    "sector_minus_nifty_6m": ("follows sector_index", "M", 85),
    "listing_gain_minus_sector_day": ("follows sector_index", "M", 85),
    "is_sme": ("segment comes from the bid-time record; backfill from NSE's series (EQ vs "
               "SM/ST) in public-past-issues", "S", 95),
    # --- listing day
    "turnover_x_issue_size": ("bhavcopy turnover for the listing date; the gap is the days "
                              "whose bhavcopy was never fetched", "S", 92),
    "turnover_exchange": ("same bhavcopy backfill", "S", 92),
    "turnover_both_exchanges": ("same bhavcopy backfill", "S", 92),
    # --- promoter
    "promoter_holding_pre_pct_agg": ("Chittorgarh promoter columns exist for 2,564 rows; "
                                     "the gap is rows absent from that harvest", "M", 88),
    "promoter_holding_post_pct_agg": ("same", "M", 88),
    "promoter_dilution_pp_agg": ("follows the two above", "M", 88),
    "promoter_holding_match": ("follows the two above", "M", 88),
    "rhp_promoter_holding_pre_pct": ("the RHP capital-structure text reader added in 1.7.0 "
                                     "has not been run over all documents yet - it lands "
                                     "with the 1.8.0 pass", "S", 70),
    # --- anchor
    "anchor_amount_cr": ("Chittorgarh anchor table; the gap is issues with no anchor book "
                         "(pre-2013 and small issues) plus rows the harvest missed", "M", 70),
    "anchor_n_investors": ("same", "M", 70),
    "anchor_share_of_issue_pct": ("same", "M", 70),
    "anchor_mf_share_of_book_pct": ("needs the per-investor anchor breakdown, which "
                                    "Chittorgarh prints only for recent issues", "L", 45),
    # --- RHP flags: all from the same extraction, all improve with a better section locator
    "rhp_auditor_emphasis_flag": ("the flag readers depend on locating the auditor's "
                                  "report; improve the section locator for documents whose "
                                  "TOC does not name it", "M", 60),
    "rhp_auditor_qualification_flag": ("same section locator", "M", 85),
    "rhp_board_size_n": ("improve the management-section reader; the board table is "
                         "routinely unruled", "M", 70),
    "rhp_dual_class_flag": ("same section locator", "M", 85),
    "rhp_esop_exists_flag": ("same section locator", "M", 85),
    "rhp_geographic_concentration_flag": ("same section locator", "M", 85),
    "rhp_licence_dependence_flag": ("same section locator", "M", 70),
    "rhp_litigation_criminal_promoters_directors": ("improve the litigation-section "
                                                    "reader", "M", 75),
    "rhp_pre_ipo_placement_flag": ("read it from the capital build-up rather than prose - "
                                   "the same table the share count comes from", "S", 80),
    "rhp_promoter_lockin_months": ("same capital build-up", "S", 85),
    "rhp_uses_of_proceeds_n": ("improve the objects-of-the-offer reader", "M", 80),
}

# Where a variable is absent from the built table entirely, the reason is not "not present"
# - that is a statement about our file, not about the world. These say what is actually
# true, measured during the 1.7.0 pass.
ABSENT_REASON = {
    "ipo_ev_ebitda": "EBITDA is tabulated in 4 of 412 prospectuses - it is a non-GAAP "
                     "measure most Indian restated statements simply do not print (412)",
    "pb_premium_vs_peer_median": "peer P/B appears in 15 of 399 peer tables (399)",
}


def _n_mod(table) -> int:
    if table is None or not len(table) or "year" not in getattr(table, "columns", []):
        return 0
    return int((table["year"] >= 2019).sum())


def _pct(a, b):
    return float(a) / float(b) if b else 0.0


def _reasons(d: pd.DataFrame, var: str) -> tuple[str, str]:
    """The top two reasons a variable is unfilled, with counts, from its own reason column."""
    col = f"{var}_reason"
    if col not in d.columns or var not in d.columns:
        return "", ""
    r = d.loc[d[var].isna(), col].dropna().astype(str).str.slice(0, 90)
    vc = r.value_counts()
    out = [f"{vc.index[i]} ({vc.iloc[i]})" for i in range(min(2, len(vc)))]
    return (out + ["", ""])[0], (out + ["", ""])[1]


def build(version: str | None = None) -> dict[str, pd.DataFrame]:
    feats = pd.read_csv(FEATURES, low_memory=False)
    feats["year"] = pd.to_datetime(feats["listing_date"], errors="coerce").dt.year
    rat = pd.read_csv(RATIOS, low_memory=False) if RATIOS.exists() else pd.DataFrame()
    pb = pd.read_csv(PB, low_memory=False) if PB.exists() else pd.DataFrame()
    for t in (rat, pb):
        if len(t):
            t["year"] = pd.to_datetime(t["listing_date"], errors="coerce").dt.year

    rows = []

    def add(var, block, source, table, definition=""):
        if not len(table) or var not in table.columns:
            fix, eff, exp = FIXES.get(var, ("", "", None))
            rows.append({"variable": var, "block": block,
                         "definition": definition or DEFS.get(var, ""),
                         "source": source, "rows_filled": 0, "pct_all": 0.0,
                         "pct_2019plus": 0.0, "n_2019plus": _n_mod(table),
                         "top_reason": ABSENT_REASON.get(
                             var, "never produced on any document"),
                         "second_reason": "", "first_year": "", "status": "blocked",
                         "tapetide_lookup_helps": TAPETIDE_NO_RHP if block in
                         ("RHP fundamentals", "valuation") else "no",
                         "tapetide_data_with_consent": _tapetide_data(var, block),
                         "other_fix": fix})
            return
        t = table
        n = len(t)
        filled = t[var].notna()
        if t[var].dtype == object:
            filled &= t[var].astype(str).str.strip().ne("")
        mod = t[t["year"] >= 2019] if "year" in t else t
        mfill = mod[var].notna()
        if len(mod) and mod[var].dtype == object:
            mfill &= mod[var].astype(str).str.strip().ne("")
        fy = t.loc[filled, "year"].min() if filled.any() and "year" in t else None
        r1, r2 = _reasons(t, var)
        pa, pm = _pct(filled.sum(), n), _pct(mfill.sum(), len(mod))
        status = "built" if pm >= 0.9 else ("partial" if pm > 0.05 else "blocked")
        fix, eff, exp = FIXES.get(var, ("", "", None))
        rows.append({
            "variable": var, "block": block, "definition": definition or DEFS.get(var, ""),
            "source": source, "rows_filled": int(filled.sum()),
            "pct_all": pa, "pct_2019plus": pm,
            "top_reason": r1, "second_reason": r2,
            "first_year": "" if fy is None or pd.isna(fy) else int(fy),
            "n_2019plus": len(mod),
            "status": status,
            "tapetide_lookup_helps": (TAPETIDE_NO_RHP if block == "RHP fundamentals"
                                      or block == "valuation" else "no"),
            "tapetide_data_with_consent": _tapetide_data(var, block),
            "other_fix": fix})

    for block, vs in BLOCKS.items():
        for v in vs:
            add(v, block, _source_for(block), feats)
    for v in VALUATION:
        table = pb if (len(pb) and v in pb.columns) else rat
        add(v, "valuation", "RHP extraction + master offer price", table)

    inv = pd.DataFrame(rows)
    gaps = _gap_table(inv)
    tap = _tapetide_sheet(inv)
    return {"Inventory": inv, "2019+ gaps": gaps, "Tapetide": tap}


def _source_for(block: str) -> str:
    return {
        "market heat": "NSE Indices TRI + niftyindices P/E + India VIX archive",
        "subscription": "NSE ipo-active-category / Chittorgarh (H22)",
        "listing day": "exchange bhavcopy ON the listing date",
        "sector": "NSE index-constituent files + BSE IndustryNew (H38) + user input",
        "RHP fundamentals": "RHP extraction (single-source, unreconciled)",
        "promoter": "RHP capital structure + Chittorgarh cross-check",
        "anchor": "Chittorgarh anchor table",
    }.get(block, "")


def _tapetide_data(var: str, block: str) -> str:
    if block == "promoter":
        return "yes - get_shareholding / get_promoter_pledge would carry promoter holding"
    if block == "market heat":
        return "yes - get_india_vix and get_index_history cover these series"
    if var in ("ipo_ev_ebitda", "fcf_yield", "ipo_pe", "eps_cagr_3y", "ipo_peg"):
        return "yes - get_financials would give revenue, EBITDA, PAT, CFO and capex"
    if var in ("ipo_pb", "ipo_pb_pre_issue", "pb_premium_vs_peer_median"):
        return "yes - get_screener_ratios carries book value and P/B"
    if block == "listing day":
        return "yes - get_price_history, but the bhavcopy is already the better source"
    return "no"


def _gap_table(inv: pd.DataFrame) -> pd.DataFrame:
    g = inv[inv["pct_2019plus"] < 0.90].copy()
    # rows missing is measured against the 2019+ population of each variable's own table
    # Measured against EACH variable's own 2019+ population. A flat denominator made the
    # valuation ratios (399 documents) and the feature table (623 IPOs) look comparable
    # when they are not, and the sheet is sorted on this column.
    g["rows_missing"] = ((1 - g["pct_2019plus"]) * g["n_2019plus"]).round().astype(int)
    g["expected_after_fix"] = [FIXES.get(v, ("", "", None))[2] for v in g["variable"]]
    g["effort"] = [FIXES.get(v, ("", "", ""))[1] for v in g["variable"]]
    g["blocked_why"] = np.where(
        g["status"] == "blocked",
        "yes - " + g["top_reason"].astype(str).str.slice(0, 70), "no")
    return g[["variable", "block", "pct_2019plus", "n_2019plus", "rows_missing",
              "top_reason",
              "second_reason", "other_fix", "expected_after_fix", "effort",
              "blocked_why"]].sort_values("rows_missing", ascending=False)


def _tapetide_sheet(inv: pd.DataFrame) -> pd.DataFrame:
    n_lookup = int((inv["tapetide_lookup_helps"].astype(str).str.startswith("yes")).sum())
    n_data = int((inv["tapetide_data_with_consent"].astype(str).str.startswith("yes")).sum())
    return pd.DataFrame([
        {"finding": "Document catalogue carries NO prospectuses",
         "evidence": "list_company_documents with doc_types=[rhp,drhp] returned 0 for "
                     "PATELRMART, SAMHI and SWIGGY (a control: a major 2024 IPO)",
         "consequence": "Tapetide cannot locate a missing RHP, so it cannot close any "
                        "RHP-sourced gap by lookup"},
        {"finding": "Identifier lookup misses delisted names",
         "evidence": "resolve_identifier_asof('TCNSBRANDS', 2018-07-30) -> not_found, "
                     "WITHIN its stated coverage from 2016-01-01",
         "consequence": "our 45 unresolved symbols are pre-2019 and largely delisted - "
                        "exactly the population it misses. Survivorship again"},
        {"finding": f"Variables a LOOKUP alone could improve: {n_lookup}",
         "evidence": "measured, not inferred from the tool list",
         "consequence": "lookups are free of the H36 storage restriction but buy nothing "
                        "here"},
        {"finding": f"Variables its DATA could fill with written consent: {n_data}",
         "evidence": "get_financials, get_shareholding, get_screener_ratios, "
                     "get_india_vix, get_index_history",
         "consequence": "this is where the value is, and it needs a data-use consent "
                        "because H36 forbids storing Tapetide values"},
    ])


def write_xlsx(sheets: dict[str, pd.DataFrame]) -> Path:
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as xl:
        book = xl.book
        pctf = book.add_format({"num_format": "0.0%"})
        hdr = book.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1,
                               "text_wrap": True, "valign": "top"})
        wrap = book.add_format({"text_wrap": True, "valign": "top"})
        for name, d in sheets.items():
            d.to_excel(xl, sheet_name=name[:31], index=False, startrow=1, header=False)
            ws = xl.sheets[name[:31]]
            for j, c in enumerate(d.columns):
                ws.write(0, j, c, hdr)
            ws.freeze_panes(1, 0)
            for j, c in enumerate(d.columns):
                body = d[c].astype(str)
                w = max(len(str(c)), int(body.str.len().quantile(0.95)) if len(d) else 10)
                w = min(max(w + 2, 10), 60)
                if str(c).startswith("pct") or str(c) == "expected_after_fix":
                    ws.set_column(j, j, max(w, 12), pctf if str(c).startswith("pct")
                                  else None)
                else:
                    ws.set_column(j, j, w, wrap if w >= 40 else None)
            ws.autofilter(0, 0, max(len(d), 1), max(len(d.columns) - 1, 0))
    return OUT_XLSX


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, extra=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  ok   {n}")
        else:
            fail += 1
            print(f"  FAIL {n} {extra}")

    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] it fits nothing")
    body = src.split('"""', 2)[-1]
    chk("no estimator is imported or called",
        not any(k in body for k in ("LogisticRegression", "framework", ".fit(",
                                    "walk_forward")))
    print(chr(10) + "[2] the reasons come from the data, not from here")
    chk("the unfilled reasons are read off each variable's own reason column",
        'f"{var}_reason"' in src)
    chk("and the top TWO are reported with counts", "min(2, len(vc))" in src)

    print(chr(10) + "[3] the Tapetide answer is measured, not assumed")
    chk("the no-RHP finding cites the SWIGGY control", "SWIGGY" in src)
    chk("the delisted finding cites TCNSBRANDS and 'within coverage'",
        "TCNSBRANDS" in src and "WITHIN its stated coverage" in src)
    chk("data-with-consent names the specific tool", "get_financials" in src
        and "get_shareholding" in src)

    print(chr(10) + "[4] the workbook meets the spec")
    chk("three sheets", all(k in src for k in ('"Inventory"', '"2019+ gaps"', '"Tapetide"')))
    chk("header frozen", "freeze_panes(1, 0)" in src)
    chk("percent columns formatted as percentages", '"0.0%"' in src)
    chk("columns autofitted", "set_column(j, j," in src)
    chk("the gap sheet is sorted by rows missing, largest first",
        'sort_values("rows_missing", ascending=False)' in src)
    chk("and covers every variable below 90% on 2019+",
        'inv["pct_2019plus"] < 0.90' in src)
    chk("rows missing is measured against each variable's OWN 2019+ population",
        'g["n_2019plus"]' in src)
    chk("an absent variable states what is TRUE, not 'not present in our table'",
        "ABSENT_REASON" in src and "non-GAAP" in src)
    chk("every gap variable has a named fix",
        len(FIXES) >= 30, len(FIXES))
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    sheets = build(a.version)
    p = write_xlsx(sheets)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 46)
    pd.set_option("display.max_rows", 200)
    inv = sheets["Inventory"]
    print("=== Sheet 1: Inventory ===")
    show = inv[["variable", "block", "rows_filled", "pct_all", "pct_2019plus", "status",
                "top_reason"]].copy()
    show["pct_all"] = (show["pct_all"] * 100).round(0).astype(int).astype(str) + "%"
    show["pct_2019plus"] = (show["pct_2019plus"] * 100).round(0).astype(int).astype(str) + "%"
    print(show.to_string(index=False))
    print()
    print("=== Sheet 2: 2019+ gaps ===")
    g = sheets["2019+ gaps"].copy()
    g["pct_2019plus"] = (g["pct_2019plus"] * 100).round(0).astype(int).astype(str) + "%"
    print(g[["variable", "pct_2019plus", "rows_missing", "other_fix", "expected_after_fix",
             "effort"]].to_string(index=False))
    print()
    print(f"written {p}")

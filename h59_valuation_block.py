"""
h59_valuation_block.py - the H59 valuation block: primary, second source, rule 2, ratios.

Task 1 of the 6 November brief. H5 makes the aggregator primary for headline financials.
This module adds the second source per value, applies hard rule 2 (<=5% reconciled; >5%
NULL with both values logged; one source only -> `single_source_unverified`, H26), and
derives the ratios with withholding (H45/H54: a ratio whose inputs are not trustworthy is
withheld with a reason, never approximated).

Sources, in precedence order:

1. **Chittorgarh** (primary, H5) - `data/chittorgarh_mainboard_fy.csv`, the full financial
   year established under H59 as amended.
2. **Tickertape** (H58, the one permitted second source) - `data/tickertape_annuals.csv`,
   matched on the SAME fiscal year end. Six aggregate fields only, no per-share figure.
3. **The RHP** - `data/rhp_valuation_values.csv`, matched on the same fiscal year.

Chittorgarh and IPOMatrix share a parent and are NOT independent (hard rule 2), so a
Chittorgarh value alone is single-source.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TOL_PCT = 5.0                      # hard rule 2

PRIMARY = "chittorgarh"


def _num(v):
    """A float, or None. pandas stores a missing value as NaN, and float('nan') is TRUTHY -
    `v or default` therefore returns NaN. Every absence check here goes through pd.isna."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def reconcile_value(primary, seconds: dict) -> dict:
    """Hard rule 2 on one value.

    Every PAIR of sources is compared, and the maximum relative difference decides - so a
    value with one agreeing and one disagreeing second source is withheld, rather than
    reconciled against whichever source happens to agree.
    """
    p = _num(primary)
    vals = {k: _num(v) for k, v in seconds.items()}
    vals = {k: v for k, v in vals.items() if v is not None}
    allv = dict(vals)
    if p is not None:
        allv[PRIMARY] = p
    out = {"value": None, "status": None, "primary_value": p,
           "second_source": None, "second_value": None,
           "max_rel_diff_pct": None, "n_sources": len(allv), "all_values": allv}
    if vals:
        # The named second source is the first available in precedence order.
        for k in ("tickertape", "rhp"):
            if k in vals:
                out["second_source"], out["second_value"] = k, vals[k]
                break
        else:
            k = sorted(vals)[0]
            out["second_source"], out["second_value"] = k, vals[k]
    if p is None:
        out["status"] = "no_primary"
        return out
    if not vals:
        out["value"], out["status"] = p, "single_source_unverified"
        return out
    items = list(allv.values())
    worst = 0.0
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            den = max(abs(a), abs(b))
            if den == 0:
                continue                      # 0 vs 0 is agreement, not a zero division
            worst = max(worst, 100.0 * abs(a - b) / den)
    out["max_rel_diff_pct"] = round(worst, 4)
    if worst <= TOL_PCT:
        out["value"], out["status"] = p, "reconciled"
    else:
        out["value"], out["status"] = None, "withheld_disagreement"
    return out

# RHP variable -> our field. `value_crore` is used where the reader converted a unit;
# a ratio or per-share figure has no crore conversion and is taken as stated.
RHP_AMOUNT = {"pat_fy1": "pat_cr", "revenue_fy1": "total_income_cr",
              "borrowings_fy1": "borrowings_cr", "cash_fy1": "cash_cr",
              "ebitda_fy1": "ebitda_cr"}
RHP_AS_STATED = {"ronw_fy1": "ronw_pct", "eps_basic_fy1": "eps_pre",
                 "nav_fy1": "nav_fy1", "nav_pre_issue": "nav_pre_issue",
                 "nav_post_issue": "nav_post_issue"}


def rhp_fiscal_year(note) -> int | None:
    """The fiscal year out of a reader note, or None.

    The reader's notes are not always sane - `AAVAS Financiers Ltd` carries
    "fiscal 2031, column 2", which cannot be a reported year for a 2018 filing. A year
    outside 1990-2026 is therefore refused rather than matched on, so a mis-parsed year
    cannot silently align a value to the wrong period.
    """
    if note is None or (isinstance(note, float) and pd.isna(note)):
        return None
    m = re.search(r"fiscal\s*(\d{4})", str(note), re.I) or re.search(r"\b(\d{4})\b", str(note))
    if not m:
        return None
    y = int(m.group(1))
    return y if 1990 <= y <= 2026 else None


def fy_label_year(label) -> int | None:
    """'31 Mar 2024' -> 2024. The Indian FY is named by the year it ENDS in, which is the
    year printed in the label, so no arithmetic is needed - and none is done."""
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    m = re.search(r"\b(19|20)(\d{2})\b", str(label))
    return int(m.group(0)) if m else None


def tickertape_for(tt: pd.DataFrame, ipo_id: int, end_date: str) -> dict:
    """Tickertape's six fields for exactly this id and this fiscal year end, else {}."""
    if not len(tt) or end_date is None or pd.isna(end_date):
        return {}
    g = tt[(tt["ipo_id"] == ipo_id) & (tt["end_date"].astype(str) == str(end_date)[:10])]
    if not len(g):
        return {}
    r = g.iloc[0]
    out = {}
    for c in ("total_income_cr", "pat_cr", "ebitda_cr", "net_worth_cr", "borrowings_cr",
              "cash_cr"):
        v = _num(r.get(c))
        if v is not None:
            out[c] = v
    return out


def rhp_for(rhp: pd.DataFrame, company: str, fy_year: int | None) -> dict:
    """The RHP's own values for this company's fiscal year `fy_year`, else {}."""
    if not len(rhp) or fy_year is None:
        return {}
    g = rhp[(rhp["company"] == company) & (rhp["status"] == "ok")]
    out = {}
    for r in g.itertuples(index=False):
        if rhp_fiscal_year(r.note) != fy_year:
            continue
        if r.variable in RHP_AMOUNT:
            v = _num(r.value_crore)
            if v is not None:
                out[RHP_AMOUNT[r.variable]] = v
        elif r.variable in RHP_AS_STATED:
            v = _num(r.value)
            if v is not None:
                out[RHP_AS_STATED[r.variable]] = v
    return out


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

    print("[1] rule 2: <=5% reconciled, >5% NULL with BOTH logged, one source flagged")
    r = reconcile_value(100.0, {"tickertape": 102.0})
    chk("within 5% -> the primary value, reconciled",
        r["value"] == 100.0 and r["status"] == "reconciled", str(r))
    chk("the second source and the gap are recorded",
        r["second_source"] == "tickertape" and r["second_value"] == 102.0
        and abs(r["max_rel_diff_pct"] - 1.9608) < 0.001, str(r))
    r = reconcile_value(100.0, {"tickertape": 120.0})
    chk("over 5% -> value NULL",
        r["value"] is None and r["status"] == "withheld_disagreement", str(r))
    chk("over 5% -> BOTH values still logged (rule 2)",
        r["primary_value"] == 100.0 and r["second_value"] == 120.0, str(r))
    r = reconcile_value(100.0, {})
    chk("no second source -> kept and flagged single_source_unverified (H26)",
        r["value"] == 100.0 and r["status"] == "single_source_unverified", str(r))
    chk("single source records no second value",
        r["second_source"] is None and r["second_value"] is None, str(r))
    r = reconcile_value(None, {"tickertape": 120.0})
    chk("no primary -> no value; a second source never becomes the primary (H5)",
        r["value"] is None and r["status"] == "no_primary", str(r))
    chk("the second value is still logged when the primary is missing",
        r["second_value"] == 120.0, str(r))

    print("[2] MAX PAIRWISE difference decides, not the best-agreeing pair")
    r = reconcile_value(100.0, {"tickertape": 101.0, "rhp": 130.0})
    chk("one agreeing and one disagreeing source -> withheld",
        r["value"] is None and r["status"] == "withheld_disagreement", str(r))
    chk("the worst of ALL pairs is reported (here 100 vs 130, not 101 vs 130)",
        abs(r["max_rel_diff_pct"] - 100.0 * (130.0 - 100.0) / 130.0) < 0.001,
        str(r["max_rel_diff_pct"]))
    # A second-vs-second pair can be the worst one, with the primary between them.
    r2 = reconcile_value(115.0, {"tickertape": 101.0, "rhp": 130.0})
    chk("a second-vs-second pair can be the worst, and still withholds",
        r2["status"] == "withheld_disagreement"
        and abs(r2["max_rel_diff_pct"] - 100.0 * (130.0 - 101.0) / 130.0) < 0.001,
        str(r2["max_rel_diff_pct"]))
    chk("every source is named in the log",
        "tickertape" in r["all_values"] and "rhp" in r["all_values"]
        and r["all_values"]["chittorgarh"] == 100.0, str(r["all_values"]))
    r = reconcile_value(100.0, {"tickertape": 102.0, "rhp": 103.0})
    chk("all three within 5% of each other -> reconciled on two sources",
        r["status"] == "reconciled" and r["n_sources"] == 3, str(r))

    print("[3] zero, sign and None are handled, not crashed through")
    chk("0 vs 0 is agreement, not a division by zero",
        reconcile_value(0.0, {"tickertape": 0.0})["status"] == "reconciled")
    chk("0 vs non-zero is a 100% disagreement",
        reconcile_value(0.0, {"tickertape": 5.0})["status"] == "withheld_disagreement")
    chk("a loss reconciles against the same loss",
        reconcile_value(-16.5, {"tickertape": -16.4})["status"] == "reconciled")
    chk("a sign flip is never reconciled",
        reconcile_value(-16.5, {"tickertape": 16.5})["status"] == "withheld_disagreement")
    chk("a None second source is ignored, not counted",
        reconcile_value(10.0, {"tickertape": None})["status"] == "single_source_unverified")
    chk("NaN is treated as absent (the pandas trap)",
        reconcile_value(10.0, {"tickertape": float("nan")})["status"]
        == "single_source_unverified")

    print("[4] a second source counts only for the SAME fiscal year")
    chk("the RHP's note gives the fiscal year", rhp_fiscal_year("fiscal 2024, column 7") == 2024)
    chk("a year outside 1990-2026 is NOT a fiscal year (the 'fiscal 2031' defect)",
        rhp_fiscal_year("fiscal 2031, column 2") is None)
    chk("no year in the note -> None", rhp_fiscal_year("column 2") is None)
    chk("an empty note -> None", rhp_fiscal_year(None) is None)
    chk("a 31 March FY is named by its END year", fy_label_year("31 Mar 2024") == 2024)
    chk("a 31 December FY is named by its own year", fy_label_year("31 Dec 2015") == 2015)
    chk("an unparseable label -> None", fy_label_year("not a date") is None)

    tt = pd.DataFrame([
        {"ipo_id": 1, "end_date": "2024-03-31", "reporting": "consolidated",
         "total_income_cr": 2470.0, "pat_cr": 78.9, "net_worth_cr": 422.0,
         "borrowings_cr": 300.0, "cash_cr": 25.0, "ebitda_cr": 150.0},
        {"ipo_id": 1, "end_date": "2023-03-31", "reporting": "consolidated",
         "total_income_cr": 2422.0, "pat_cr": 59.9, "net_worth_cr": 282.0,
         "borrowings_cr": 280.0, "cash_cr": 10.0, "ebitda_cr": 140.0},
    ])
    chk("the matching year is taken", tickertape_for(tt, 1, "2024-03-31")["pat_cr"] == 78.9)
    chk("a NON-matching year is NOT used as a second source",
        tickertape_for(tt, 1, "2022-03-31") == {}, str(tickertape_for(tt, 1, "2022-03-31")))
    chk("an id Tickertape never resolved yields nothing",
        tickertape_for(tt, 99, "2024-03-31") == {})

    rhp = pd.DataFrame([
        {"company": "Bansal Wire Industries", "variable": "pat_fy1", "status": "ok",
         "value": 788.0, "value_crore": 78.8, "note": "fiscal 2024, column 2"},
        {"company": "Bansal Wire Industries", "variable": "ronw_fy1", "status": "ok",
         "value": 18.66, "value_crore": None, "note": "fiscal 2024"},
        {"company": "Bansal Wire Industries", "variable": "cash_fy1", "status": "ok",
         "value": 50.0, "value_crore": 5.0, "note": "fiscal 2023, column 3"},
        {"company": "Bansal Wire Industries", "variable": "borrowings_fy1",
         "status": "not_found", "value": None, "value_crore": None, "note": ""},
    ])
    got = rhp_for(rhp, "Bansal Wire Industries", 2024)
    chk("a crore-converted amount is taken in crore, never the raw number",
        got["pat_cr"] == 78.8, str(got))
    chk("a ratio with no unit is taken as stated", got["ronw_pct"] == 18.66, str(got))
    chk("a value from ANOTHER fiscal year is not used", "cash_cr" not in got, str(got))
    chk("a status that is not 'ok' is not used", "borrowings_cr" not in got, str(got))
    chk("a company the RHP set does not hold yields nothing",
        rhp_for(rhp, "Nobody Ltd", 2024) == {})


    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(self_test())

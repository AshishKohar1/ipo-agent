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

# name -> (numerator, denominator, scale, denominator must be > 0)
# `scale` 100 makes a percentage. A denominator that may legitimately be negative - total
# income never is, net worth and EBITDA can be - is marked must_be_positive, because a
# ratio over a negative denominator is not a small number, it is a meaningless one.
RATIOS = {
    "roe_pct":                        ("pat_cr", "net_worth_cr", 100.0, True),
    "pat_margin_pct_on_total_income": ("pat_cr", "total_income_cr", 100.0, True),
    "ebitda_margin_pct":              ("ebitda_cr", "total_income_cr", 100.0, True),
    "debt_equity":                    ("borrowings_cr", "net_worth_cr", 1.0, True),
    "issue_size_over_net_worth":      ("issue_size_cr", "net_worth_cr", 1.0, True),
    "mcap_over_total_income":         ("market_cap_at_offer_cr", "total_income_cr", 1.0, True),
}


def derive_ratios(v: dict) -> dict:
    """Every ratio, each either a value or a withholding with the reason named.

    H45/H54: a ratio whose inputs are not trustworthy is withheld, never approximated and
    never silently zeroed. A missing input names itself in the reason, so a reader can see
    WHICH input was absent without re-running anything.
    """
    out = {}
    for name, (num, den, scale, positive) in RATIOS.items():
        out[name] = _ratio(v, num, den, scale, positive)
    # EV/EBITDA: enterprise value needs cash, and cash is NEVER assumed to be zero.
    missing = [k for k in ("market_cap_at_offer_cr", "borrowings_cr", "cash_cr",
                           "ebitda_cr") if _num(v.get(k)) is None]
    if missing:
        out["ev_ebitda"] = {"value": None, "status": "withheld_missing_input",
                            "reason": "missing " + ", ".join(missing)}
    else:
        eb = _num(v["ebitda_cr"])
        if eb <= 0:
            out["ev_ebitda"] = {"value": None,
                                "status": "withheld_non_positive_denominator",
                                "reason": f"ebitda_cr = {eb}"}
        else:
            ev = (_num(v["market_cap_at_offer_cr"]) + _num(v["borrowings_cr"])
                  - _num(v["cash_cr"]))
            out["ev_ebitda"] = {"value": ev / eb, "status": "derived",
                                "reason": "mcap + borrowings - cash, over EBITDA"}
    return out


def _ratio(v: dict, num: str, den: str, scale: float, positive: bool) -> dict:
    a, b = _num(v.get(num)), _num(v.get(den))
    missing = [k for k, x in ((num, a), (den, b)) if x is None]
    if missing:
        return {"value": None, "status": "withheld_missing_input",
                "reason": "missing " + ", ".join(missing)}
    if b == 0 or (positive and b < 0):
        return {"value": None, "status": "withheld_non_positive_denominator",
                "reason": f"{den} = {b}"}
    return {"value": scale * a / b, "status": "derived",
            "reason": f"{num} / {den}" + (" x100" if scale != 1.0 else "")}


def cross_check(derived, stated) -> dict:
    """A derived ratio against the source's own stated one. Rule 2, same 5% tolerance."""
    d, t = _num(derived), _num(stated)
    out = {"value": d, "derived": d, "stated": t, "rel_diff_pct": None, "status": None}
    if d is None:
        out["status"] = "no_derived_value"
        return out
    if t is None:
        out["status"] = "derived_no_stated_check"
        return out
    den = max(abs(d), abs(t))
    rel = 0.0 if den == 0 else 100.0 * abs(d - t) / den
    out["rel_diff_pct"] = round(rel, 4)
    if rel <= TOL_PCT:
        out["status"] = "reconciled"
    else:
        out["value"], out["status"] = None, "withheld_disagreement"
    return out

# The six aggregates the aggregator publishes and a second source can check.
AGGREGATES = ("total_income_cr", "pat_cr", "net_worth_cr", "borrowings_cr", "ebitda_cr")
# Issue-level figures, from the aggregator's own page.
# `roe_pct` and `debt_equity` are NOT here: the aggregator's stated figures for those two
# are the CROSS-CHECK against our derived ones, and emitting both under one name collided.
ISSUE_FIELDS = ("issue_size_cr", "market_cap_at_offer_cr", "pe_pre", "pe_post",
                "ronw_pct", "roce_pct")
OUT_COLS = ["ipo_id", "company", "listing_year", "fy_period", "variable", "value",
            "status", "primary_value", "second_source", "second_value",
            "max_rel_diff_pct", "n_sources", "reason", "all_values"]


def _year(v) -> int | None:
    y = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(y) else int(y.year)


def build(fy: pd.DataFrame, issue: pd.DataFrame, tt: pd.DataFrame, rhp: pd.DataFrame,
          h45: pd.DataFrame) -> pd.DataFrame:
    """The whole block, long: one row per (ipo_id, variable), every row with a status."""
    iss = issue.set_index("ipo_id") if "ipo_id" in issue.columns else issue
    h45i = h45.set_index("company") if "company" in h45.columns else h45
    rows = []
    for r in fy.itertuples(index=False):
        ipo_id, company = int(r.ipo_id), r.company
        fy_year = fy_label_year(getattr(r, "fy_period", None))
        second_tt = tickertape_for(tt, ipo_id, getattr(r, "fy_period_parsed", None))
        second_rhp = rhp_for(rhp, company, fy_year)
        i = iss.loc[ipo_id] if ipo_id in iss.index else {}
        h = h45i.loc[company] if (len(h45i) and company in h45i.index) else {}
        if isinstance(h, pd.DataFrame):
            h = h.iloc[0]
        base = {"ipo_id": ipo_id, "company": company,
                "listing_year": _year(_get(i, "listed_on")),
                "fy_period": getattr(r, "fy_period", None)}

        kept = {}            # only values good enough to build a ratio on
        for f in AGGREGATES:
            res = reconcile_value(_num(getattr(r, f, None)),
                                  {"tickertape": second_tt.get(f),
                                   "rhp": second_rhp.get(f)})
            rows.append({**base, "variable": f, **_flat(res)})
            if res["status"] in ("reconciled", "single_source_unverified"):
                kept[f] = res["value"]

        # Cash is not on the aggregator's page at all. It comes from a second source, is
        # labelled as such, and is NEVER assumed to be zero (that is what blocks EV/EBITDA).
        cash = reconcile_value(None, {"tickertape": second_tt.get("cash_cr"),
                                      "rhp": second_rhp.get("cash_cr")})
        cash_v = cash["second_value"]
        rows.append({**base, "variable": "cash_cr",
                     **_flat({**cash, "value": cash_v,
                              "status": ("second_source_only" if cash_v is not None
                                         else "no_primary")})})
        if cash_v is not None:
            kept["cash_cr"] = cash_v

        for f in ISSUE_FIELDS:
            v = _num(_get(i, f))
            seconds = {}
            if f in ("pe_pre", "pe_post"):
                seconds["rhp"] = _num(_get(h, "ipo_pe"))        # offer price / RHP EPS
            if f == "ronw_pct":
                seconds["rhp"] = second_rhp.get("ronw_pct")
            res = reconcile_value(v, seconds)
            rows.append({**base, "variable": f, **_flat(res)})
            if res["status"] in ("reconciled", "single_source_unverified"):
                kept[f] = res["value"]

        # P/B: the aggregator does not publish it. The H54 routes are the primary, and the
        # route's own precedence and withholding already applied there.
        for name, col in (("pb_pre_issue", "ipo_pb_pre_issue"), ("pb_post_issue", "ipo_pb")):
            res = reconcile_value(_num(_get(h, col)), {})
            res["status"] = ("h54_route" if res["value"] is not None
                             else "withheld_by_h54_route")
            rows.append({**base, "variable": name, **_flat(res)})

        # Derived ratios, each cross-checked against the aggregator's stated figure.
        der = derive_ratios(kept)
        stated = {"roe_pct": _num(_get(i, "roe_pct")),
                  "debt_equity": _num(_get(i, "debt_equity"))}
        for name, d in der.items():
            cc = cross_check(d["value"], stated.get(name))
            status = d["status"] if d["value"] is None else cc["status"]
            rows.append({**base, "variable": name, "value": cc["value"],
                         "status": status, "primary_value": d["value"],
                         "second_source": ("chittorgarh_stated"
                                           if stated.get(name) is not None else None),
                         "second_value": cc["stated"],
                         "max_rel_diff_pct": cc["rel_diff_pct"],
                         "n_sources": 2 if stated.get(name) is not None else 1,
                         "reason": d["reason"], "all_values": None})
    return pd.DataFrame(rows).reindex(columns=OUT_COLS)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return obj[key]
    except Exception:
        return None


def _flat(res: dict) -> dict:
    return {"value": res.get("value"), "status": res.get("status"),
            "primary_value": res.get("primary_value"),
            "second_source": res.get("second_source"),
            "second_value": res.get("second_value"),
            "max_rel_diff_pct": res.get("max_rel_diff_pct"),
            "n_sources": res.get("n_sources"),
            "reason": res.get("reason"),
            "all_values": (str(res.get("all_values")) if res.get("all_values") else None)}


def coverage(b: pd.DataFrame) -> pd.DataFrame:
    """| variable | primary n | reconciled n | single-source n | withheld n | 2019+ % |"""
    out = []
    recent = b[b["listing_year"].fillna(0) >= 2019]
    for v, g in b.groupby("variable", sort=True):
        gr = recent[recent["variable"] == v]
        out.append({
            "variable": v,
            "primary_n": int(g["primary_value"].notna().sum()),
            "reconciled_n": int((g["status"] == "reconciled").sum()),
            "single_source_n": int((g["status"] == "single_source_unverified").sum()),
            "withheld_n": int(g["status"].astype(str).str.startswith("withheld").sum()),
            "coverage_2019_plus_pct": (round(100.0 * gr["value"].notna().sum() / len(gr), 1)
                                       if len(gr) else 0.0)})
    return pd.DataFrame(out)


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


    print("[5] ratios are derived WITH WITHHOLDING (H45/H54), never approximated")
    base = {"net_worth_cr": 400.0, "pat_cr": 80.0, "total_income_cr": 2000.0,
            "ebitda_cr": 200.0, "borrowings_cr": 300.0, "cash_cr": 50.0,
            "market_cap_at_offer_cr": 3200.0, "issue_size_cr": 745.0}
    d = derive_ratios(base)
    chk("PAT margin is on TOTAL INCOME and says so in its name",
        abs(d["pat_margin_pct_on_total_income"]["value"] - 4.0) < 1e-9,
        str(d["pat_margin_pct_on_total_income"]))
    chk("EBITDA margin on total income", abs(d["ebitda_margin_pct"]["value"] - 10.0) < 1e-9)
    chk("ROE uses net worth", abs(d["roe_pct"]["value"] - 20.0) < 1e-9)
    chk("debt/equity", abs(d["debt_equity"]["value"] - 0.75) < 1e-9)
    chk("issue size / net worth", abs(d["issue_size_over_net_worth"]["value"] - 745.0 / 400.0) < 1e-9)
    chk("market cap / total income", abs(d["mcap_over_total_income"]["value"] - 1.6) < 1e-9)
    chk("EV/EBITDA uses mcap + debt - CASH",
        abs(d["ev_ebitda"]["value"] - (3200.0 + 300.0 - 50.0) / 200.0) < 1e-9,
        str(d["ev_ebitda"]))

    print("[6] a missing input WITHHOLDS the ratio and names what was missing")
    nocash = dict(base); nocash.pop("cash_cr")
    d2 = derive_ratios(nocash)
    chk("no cash -> EV/EBITDA withheld, cash NEVER assumed to be zero",
        d2["ev_ebitda"]["value"] is None
        and d2["ev_ebitda"]["status"] == "withheld_missing_input"
        and "cash_cr" in d2["ev_ebitda"]["reason"], str(d2["ev_ebitda"]))
    chk("the ratios that do not need cash are unaffected",
        d2["roe_pct"]["value"] == 20.0 and d2["debt_equity"]["value"] == 0.75)
    d3 = derive_ratios({"pat_cr": 80.0, "total_income_cr": 2000.0})
    chk("no net worth -> ROE withheld, not zero",
        d3["roe_pct"]["value"] is None and "net_worth_cr" in d3["roe_pct"]["reason"],
        str(d3["roe_pct"]))

    print("[7] a non-positive denominator withholds rather than returning a number")
    d4 = derive_ratios({**base, "net_worth_cr": -120.0})
    chk("negative net worth -> ROE withheld as meaningless",
        d4["roe_pct"]["value"] is None
        and d4["roe_pct"]["status"] == "withheld_non_positive_denominator",
        str(d4["roe_pct"]))
    chk("negative net worth -> debt/equity withheld too",
        d4["debt_equity"]["value"] is None, str(d4["debt_equity"]))
    d5 = derive_ratios({**base, "ebitda_cr": -30.0})
    chk("negative EBITDA -> EV/EBITDA withheld",
        d5["ev_ebitda"]["value"] is None
        and d5["ev_ebitda"]["status"] == "withheld_non_positive_denominator",
        str(d5["ev_ebitda"]))
    chk("a LOSS does not withhold the PAT margin - it is a real negative margin",
        abs(derive_ratios({**base, "pat_cr": -40.0})
            ["pat_margin_pct_on_total_income"]["value"] + 2.0) < 1e-9)

    print("[8] a derived ratio is cross-checked against the source's stated one")
    chk("within 5% of the stated figure -> reconciled",
        cross_check(20.0, 20.5)["status"] == "reconciled", str(cross_check(20.0, 20.5)))
    chk("over 5% -> NULL with both logged (rule 2)",
        cross_check(20.0, 30.0)["value"] is None
        and cross_check(20.0, 30.0)["stated"] == 30.0
        and cross_check(20.0, 30.0)["status"] == "withheld_disagreement",
        str(cross_check(20.0, 30.0)))
    chk("nothing stated -> the derived value stands, flagged",
        cross_check(20.0, None)["value"] == 20.0
        and cross_check(20.0, None)["status"] == "derived_no_stated_check")
    chk("nothing derived -> no value, whatever is stated",
        cross_check(None, 30.0)["value"] is None, str(cross_check(None, 30.0)))


    print("[9] the assembled block: one row per (ipo_id, variable), status always set")
    fy = pd.DataFrame([{"ipo_id": 1, "company": "Bansal Wire Industries",
                        "fy_period": "31 Mar 2024", "fy_period_parsed": "2024-03-31",
                        "total_income_cr": 2470.89, "pat_cr": 78.8, "net_worth_cr": 422.37,
                        "borrowings_cr": 300.0, "ebitda_cr": 150.0}])
    issue = pd.DataFrame([{"ipo_id": 1, "issue_size_cr": 745.0,
                           "market_cap_at_offer_cr": 3200.0, "pe_pre": 40.0,
                           "pe_post": 40.6, "ronw_pct": 18.66, "roe_pct": 18.0,
                           "roce_pct": 20.0, "debt_equity": 0.71,
                           "listed_on": "2024-07-10"}])
    tt = pd.DataFrame([{"ipo_id": 1, "end_date": "2024-03-31", "total_income_cr": 2470.0,
                        "pat_cr": 78.9, "net_worth_cr": 422.0, "borrowings_cr": 900.0,
                        "cash_cr": 25.0, "ebitda_cr": None}])
    rhp = pd.DataFrame([{"company": "Bansal Wire Industries", "variable": "ronw_fy1",
                         "status": "ok", "value": 18.6, "value_crore": None,
                         "note": "fiscal 2024"}])
    h45 = pd.DataFrame([{"company": "Bansal Wire Industries", "ipo_pe": 41.0,
                         "ipo_pb_pre_issue": 7.4, "ipo_pb": None}])
    b = build(fy, issue, tt, rhp, h45)
    g = b.set_index("variable")
    chk("every row carries a status", b["status"].notna().all())
    chk("an agreeing aggregate is reconciled on Tickertape",
        g.loc["pat_cr", "status"] == "reconciled"
        and g.loc["pat_cr", "second_source"] == "tickertape", str(dict(g.loc["pat_cr"])))
    chk("a disagreeing aggregate is NULL with both values kept",
        pd.isna(g.loc["borrowings_cr", "value"])
        and g.loc["borrowings_cr", "status"] == "withheld_disagreement"
        and g.loc["borrowings_cr", "primary_value"] == 300.0
        and g.loc["borrowings_cr", "second_value"] == 900.0,
        str(dict(g.loc["borrowings_cr"])))
    chk("an aggregate with no second source is single_source_unverified",
        g.loc["ebitda_cr", "status"] == "single_source_unverified",
        str(dict(g.loc["ebitda_cr"])))
    chk("cash comes from the second source and is labelled as such",
        g.loc["cash_cr", "status"] in ("second_source_only", "no_primary"),
        str(dict(g.loc["cash_cr"])))
    chk("a withheld input withholds the ratio built on it",
        pd.isna(g.loc["debt_equity", "value"])
        and "borrowings_cr" in str(g.loc["debt_equity", "reason"]),
        str(dict(g.loc["debt_equity"])))
    chk("a ratio whose inputs survived is derived and cross-checked",
        abs(g.loc["roe_pct", "value"] - 100.0 * 78.8 / 422.37) < 1e-9
        and g.loc["roe_pct", "status"] == "reconciled", str(dict(g.loc["roe_pct"])))
    chk("the RHP seconds a ratio Tickertape cannot: RoNW",
        g.loc["ronw_pct", "status"] == "reconciled"
        and g.loc["ronw_pct", "second_source"] == "rhp", str(dict(g.loc["ronw_pct"])))
    chk("P/E is the aggregator's against the RHP's, not against itself",
        g.loc["pe_post", "status"] == "reconciled"
        and g.loc["pe_post", "second_value"] == 41.0, str(dict(g.loc["pe_post"])))
    chk("P/B pre-issue comes from the H54 route when the aggregator has none",
        g.loc["pb_pre_issue", "primary_value"] == 7.4, str(dict(g.loc["pb_pre_issue"])))
    chk("the listing year travels with every row, for the 2019+ cut",
        (b["listing_year"] == 2024).all(), str(b["listing_year"].unique()))

    print("[10] the coverage table counts what the brief asks for")
    cov = coverage(b)
    chk("one row per variable", len(cov) == b["variable"].nunique())
    chk("the columns are the ones specified",
        list(cov.columns) == ["variable", "primary_n", "reconciled_n", "single_source_n",
                              "withheld_n", "coverage_2019_plus_pct"], str(list(cov.columns)))
    row = cov.set_index("variable").loc["borrowings_cr"]
    chk("a withheld value counts as withheld and NOT as coverage",
        row["withheld_n"] == 1 and row["coverage_2019_plus_pct"] == 0.0, str(dict(row)))
    row = cov.set_index("variable").loc["pat_cr"]
    chk("a reconciled value counts once, in reconciled and in coverage",
        row["reconciled_n"] == 1 and row["coverage_2019_plus_pct"] == 100.0, str(dict(row)))


    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(self_test())

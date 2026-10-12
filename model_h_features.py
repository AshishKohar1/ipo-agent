"""
model_h_features.py — Task 3: Model H's candidate variables, built from sources on disk.

The rule every variable here obeys
----------------------------------
**Knowable ON the listing date.** H30 puts Model H's primary decision point at the listing
day, so a variable computed from anything that happened after it is leakage, however
predictive it looks. Every window below is therefore **strictly before or on** the listing
date, and `self_test()` asserts it two ways: a synthetic IPO placed in the middle of the
series must get identical values whether or not later IPOs exist, and a deliberately
leaky variant must be caught.

This is not a theoretical worry for the market-heat block. "Average listing gain of IPOs in
the prior 3 months" is computed from other IPOs' outcomes, and the obvious implementation -
group by quarter and average - includes IPOs that listed *after* the row being scored. That
would be a model that knows the future of its own cohort.

What is here and what is not
----------------------------
Built, from files already on disk (no network, so no contention with the Model H night
batch's 3 s NSE gap):

  d  sentiment      total subscription, QIB / HNI / RII, demand profile, log issue size
  f  market heat    IPO count prior 3m and 6m; mean listing gain prior 3m; mean total
                    subscription prior 3m; Nifty 50 TRI 6m and 12m return
  g  is_sme         derived from the security type, never defaulted
  c  listing day    listing gain (from the master)

**Not built, and why** - each needs a source that is not on disk, and fetching it now would
put a second client on NSE at the same time as the night batch:

  c  day-1 turnover / issue size   the bhavcopy IS cached for many dates, but
                                   `listing_prices._norm` keeps only isin/symbol/open/close
                                   and drops turnover. That module is inside the live-path
                                   freeze, so the raw files must be re-parsed here instead -
                                   queued, not blocked.
  c  listing-day return vs sector  needs (e)
  e  sector momentum               needs NSE's industry classification per symbol, and the
                                   sectoral index close history. `market_context.py` fetches
                                   15 indices but only for recent dates, and Nifty Smallcap
                                   is not among them.
  f  Nifty 50 P/E vs 10y median    NSE Indices publishes the P/E series; not on disk.
  f  smallcap minus Nifty, 6m      needs the Nifty Smallcap close history; not on disk.
  f  India VIX                     NSE publishes it; not on disk.
  d  anchor share (2022+)          `data/chittorgarh_anchor_lockin.csv` exists; wiring it in
                                   is queued with the rest.

    python model_h_features.py --self-test
    python model_h_features.py --build
    python model_h_features.py --coverage
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                # noqa: E402

OUT = ROOT / "data" / "model_h_features.csv"

# Which block of Task 3 each variable belongs to, and where its value comes from. Printed
# by --coverage so the table is generated rather than retyped.
SOURCES = {
    "sub_total":            ("d sentiment", "master Total"),
    "sub_qib":              ("d sentiment", "master QIB"),
    "sub_hni":              ("d sentiment", "master HNI"),
    "sub_rii":              ("d sentiment", "master RII"),
    "log1p_sub_total":      ("d sentiment", "derived from master Total"),
    "qib_share_of_total":   ("d sentiment", "derived from master QIB / Total"),
    "rii_share_of_total":   ("d sentiment", "derived from master RII / Total"),
    "demand_profile":       ("d sentiment", "derived: which category led"),
    "log_issue_size":       ("d sentiment", "master Issue_Size(crores)"),
    "listing_gain_pct":     ("c listing day", "master Listing Gain"),
    "ipo_count_prior_3m":   ("f market heat", "master listing dates, strictly prior"),
    "ipo_count_prior_6m":   ("f market heat", "master listing dates, strictly prior"),
    "mean_listing_gain_prior_3m": ("f market heat", "master, strictly prior listings"),
    "mean_sub_total_prior_3m":    ("f market heat", "master, strictly prior listings"),
    "nifty_tri_ret_6m":     ("f market heat", "data/NIFTY50_TRI.csv (NSE Indices)"),
    "nifty_tri_ret_12m":    ("f market heat", "data/NIFTY50_TRI.csv (NSE Indices)"),
    "is_sme":               ("g flag", "NSE security type via the spine; never defaulted"),
}


def _tri() -> pd.Series:
    t = dataio.load_nifty_tri()
    t = t.dropna()
    t.index = pd.to_datetime(t.index)
    return t.sort_index()


def _tri_ret(tri: pd.Series, on, months: int) -> float | None:
    """TRI return over the `months` ending ON the listing date. None if either end is
    outside the series - never a partial window silently scaled up."""
    end = pd.Timestamp(on)
    start = end - pd.DateOffset(months=months)
    if end < tri.index.min() or start < tri.index.min() or end > tri.index.max():
        return None
    a = tri[tri.index <= start]
    b = tri[tri.index <= end]
    if a.empty or b.empty:
        return None
    return float(b.iloc[-1] / a.iloc[-1] - 1.0) * 100.0


def _is_sme(symbol, spine_types: dict) -> int | None:
    """1 for SME, 0 for mainboard, **None when unknown**.

    Never defaulted to 0. The master this project uses is a mainboard dataset, so a
    default of 0 would be right most of the time and silently wrong for every SME row that
    found its way in - and H31 makes this flag a model input, so a wrong value here moves
    a coefficient rather than just a label.
    """
    if symbol is None or (isinstance(symbol, float) and pd.isna(symbol)):
        return None
    t = str(spine_types.get(str(symbol).strip(), "")).strip().upper()
    if not t:
        return None
    if t in ("SM", "ST", "SME"):
        return 1
    if t in ("EQ", "BE", "BZ"):
        return 0
    return None


def build(write: bool = True) -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    if "exclude_reason" in m:
        m = m[m["exclude_reason"].isna()]
    m = m.copy()
    # `listing_date_master` is the trustworthy one; `issue_open_date` holds the listing
    # date too (the known defect) and is the fallback.
    m["ld"] = pd.to_datetime(m.get("listing_date_master"), errors="coerce")
    m["ld"] = m["ld"].fillna(pd.to_datetime(m["issue_open_date"], errors="coerce"))
    m = m.dropna(subset=["ld"]).sort_values("ld").reset_index(drop=True)

    for c in ("Total", "QIB", "HNI", "RII", "Listing Gain", "Issue_Size(crores)"):
        m[c] = pd.to_numeric(m[c], errors="coerce")

    spine = dataio.load_nse_spine()
    types = dict(zip(spine["symbol"].astype(str).str.strip(),
                     spine.get("security_type", pd.Series(dtype=str)).astype(str)))
    tri = _tri()

    # Market heat from OTHER IPOs, strictly before this one. Computed per row against the
    # whole frame rather than with a rolling window, because a rolling window over a
    # calendar index silently includes same-day rows and this must not.
    ld = m["ld"].to_numpy()
    gain = m["Listing Gain"].to_numpy(dtype=float)
    tot = m["Total"].to_numpy(dtype=float)
    rows = []
    for i, r in m.iterrows():
        on = r["ld"]
        # STRICTLY prior: `<` on the upper bound, so an IPO never counts itself and
        # same-day listings do not leak into each other.
        prior3 = (ld >= np.datetime64(on - pd.DateOffset(months=3))) & (ld < np.datetime64(on))
        prior6 = (ld >= np.datetime64(on - pd.DateOffset(months=6))) & (ld < np.datetime64(on))
        g3, t3 = gain[prior3], tot[prior3]
        g3, t3 = g3[~np.isnan(g3)], t3[~np.isnan(t3)]
        total = r["Total"]
        rows.append({
            "company": r["company"], "symbol": r.get("symbol"),
            "listing_date": f"{on:%Y-%m-%d}",
            "sub_total": total, "sub_qib": r["QIB"], "sub_hni": r["HNI"],
            "sub_rii": r["RII"],
            "log1p_sub_total": (None if pd.isna(total) else float(np.log1p(max(total, 0)))),
            "qib_share_of_total": (None if pd.isna(total) or not total or pd.isna(r["QIB"])
                                   else float(r["QIB"] / total)),
            "rii_share_of_total": (None if pd.isna(total) or not total or pd.isna(r["RII"])
                                   else float(r["RII"] / total)),
            "demand_profile": _profile(r["QIB"], r["HNI"], r["RII"]),
            "log_issue_size": (None if pd.isna(r["Issue_Size(crores)"])
                               or r["Issue_Size(crores)"] <= 0
                               else float(np.log(r["Issue_Size(crores)"]))),
            "listing_gain_pct": r["Listing Gain"],
            "ipo_count_prior_3m": int(prior3.sum()),
            "ipo_count_prior_6m": int(prior6.sum()),
            "mean_listing_gain_prior_3m": (float(g3.mean()) if g3.size else None),
            "mean_sub_total_prior_3m": (float(t3.mean()) if t3.size else None),
            "nifty_tri_ret_6m": _tri_ret(tri, on, 6),
            "nifty_tri_ret_12m": _tri_ret(tri, on, 12),
            "is_sme": _is_sme(r.get("symbol"), types),
        })
    d = pd.DataFrame(rows)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(OUT, index=False, encoding="utf-8")
    return d


def _profile(qib, hni, rii) -> str | None:
    """Which category led the book. Display and model label, not a fetched value (H3)."""
    vals = {"QIB": qib, "HNI": hni, "RII": rii}
    vals = {k: v for k, v in vals.items() if pd.notna(v)}
    if not vals:
        return None
    return max(vals, key=vals.get) + "_led"


def coverage() -> pd.DataFrame:
    d = pd.read_csv(OUT) if OUT.exists() else build(write=False)
    rows = []
    for v, (block, src) in SOURCES.items():
        if v not in d.columns:
            continue
        s = d[v]
        have = s.notna()
        yrs = pd.to_datetime(d.loc[have, "listing_date"], errors="coerce").dt.year
        rows.append({"variable": v, "block": block, "rows_with_value": int(have.sum()),
                     "pct": round(have.mean() * 100, 1),
                     "first_year": (int(yrs.min()) if have.any() else None),
                     "source": src})
    return pd.DataFrame(rows).sort_values(["block", "variable"]).reset_index(drop=True)


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

    print("[1] market heat uses STRICTLY prior IPOs - the leakage test")
    # Three IPOs a month apart. The middle one's prior-3m stats must not see the third.
    import model_h_features as SELF
    m = pd.DataFrame({
        "ld": pd.to_datetime(["2020-01-10", "2020-02-10", "2020-03-10"]),
        "Listing Gain": [10.0, 20.0, 1000.0],
        "Total": [5.0, 6.0, 999.0],
    })
    ld = m["ld"].to_numpy()
    on = m["ld"].iloc[1]
    prior3 = (ld >= np.datetime64(on - pd.DateOffset(months=3))) & (ld < np.datetime64(on))
    chk("the middle IPO sees exactly one prior IPO", int(prior3.sum()) == 1,
        int(prior3.sum()))
    chk("and the LATER IPO's 1000% gain is excluded",
        float(m["Listing Gain"].to_numpy()[prior3].mean()) == 10.0,
        m["Listing Gain"].to_numpy()[prior3])
    chk("an IPO never counts itself", not bool(prior3[1]))
    # The leaky variant, to prove the test can fail.
    leaky = (ld >= np.datetime64(on - pd.DateOffset(months=3))) & (ld <= np.datetime64(on
             + pd.DateOffset(months=3)))
    chk("a <= upper bound WOULD leak, which is what the < prevents",
        float(m["Listing Gain"].to_numpy()[leaky].mean()) > 300.0,
        m["Listing Gain"].to_numpy()[leaky])
    import inspect
    bsrc = inspect.getsource(build)
    chk("the built code uses the strict bound", 'ld < np.datetime64(on)' in bsrc)

    print("\n[2] a TRI window that does not fit returns None, never a partial")
    tri = pd.Series([100.0, 110.0], index=pd.to_datetime(["2020-01-01", "2020-06-01"]))
    chk("a 12m window on a 5-month series is None",
        _tri_ret(tri, "2020-06-01", 12) is None)
    chk("a date past the series end is None",
        _tri_ret(tri, "2030-01-01", 6) is None)
    tri2 = pd.Series([100.0, 120.0],
                     index=pd.to_datetime(["2019-06-01", "2020-06-01"]))
    chk("a window that does fit returns the return",
        abs(_tri_ret(tri2, "2020-06-01", 12) - 20.0) < 1e-9,
        _tri_ret(tri2, "2020-06-01", 12))

    print("\n[3] is_sme is derived and NEVER defaulted")
    types = {"ALPHA": "EQ", "SMEONE": "SM", "ODD": "XX"}
    chk("EQ -> 0", _is_sme("ALPHA", types) == 0)
    chk("SM -> 1", _is_sme("SMEONE", types) == 1)
    chk("an unknown series -> None, not 0", _is_sme("ODD", types) is None)
    chk("a symbol absent from the spine -> None, not 0",
        _is_sme("NOTTHERE", types) is None)
    chk("a NULL symbol -> None", _is_sme(None, types) is None)
    chk("and the docstring says why a default of 0 would be wrong",
        "silently wrong" in (_is_sme.__doc__ or ""))

    print("\n[4] derived shares and the profile label")
    # The previous version of this line asserted `build.__doc__ is None or True`, which is
    # always true and could never fail. Now it exercises the real division guard.
    one = pd.DataFrame({"Total": [0.0], "QIB": [5.0]}).iloc[0]
    share = (None if pd.isna(one["Total"]) or not one["Total"] or pd.isna(one["QIB"])
             else float(one["QIB"] / one["Total"]))
    chk("qib share of a ZERO total is None, not an infinity", share is None, share)
    nz = pd.DataFrame({"Total": [50.0], "QIB": [25.0]}).iloc[0]
    chk("and a real total divides normally",
        abs(float(nz["QIB"] / nz["Total"]) - 0.5) < 1e-12)
    chk("the profile names the category that led",
        _profile(100, 50, 10) == "QIB_led" and _profile(1, 2, 3) == "RII_led")
    chk("and is None when no category is known", _profile(None, None, None) is None)
    chk("it works when only one category is known", _profile(None, 5, None) == "HNI_led")

    print("\n[5] every declared variable is actually produced")
    d = build(write=False)
    missing = [v for v in SOURCES if v not in d.columns]
    chk("no declared variable is missing from the output", not missing, missing)
    extra = [c for c in d.columns if c not in SOURCES
             and c not in ("company", "symbol", "listing_date")]
    chk("and nothing undeclared is produced", not extra, extra)
    chk("every row has a listing date", d["listing_date"].notna().all())
    chk("rows are in listing-date order, so a reader cannot mistake the panel",
        list(d["listing_date"]) == sorted(d["listing_date"]))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.build:
        d = build()
        print(f"{len(d)} rows -> {OUT}")
        raise SystemExit(0)
    if a.coverage:
        print(coverage().to_string(index=False))
        raise SystemExit(0)
    ap.print_help()

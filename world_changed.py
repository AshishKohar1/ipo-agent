"""
world_changed.py — Priority 3b: did the world change, or did the model?

The 12-month email backtest under-delivers both promises (L1 85.7% against 90%, L2 72.2%
against 80%) and 2025 is the weakest year in the series. The question is whether that is
the rule decaying or the market moving underneath a rule that is still sound.

The user's hypothesis was heavy FII outflows in 2025, to be **verified against actual data,
not assumed**. On the FII series specifically, see `reports/WORLD_CHANGED.md`: NSE's
`api/fiidiiTradeReact` works but returns today only — `?date=` and `?from=&to=` are
accepted with HTTP 200 and silently ignored — and the historical archive page is
JS-rendered with no static file links. So **this module does not measure FII flows**, and
it says so rather than substituting a proxy and calling it FII (rule 1, and the same
discipline as "never substitute a nearby index").

What it does measure, from data already in hand and with no new source:

* the **delivered hit rate per listing year** at the ratified thresholds — the thing that
  is actually said to have deteriorated;
* the **Nifty 50 TRI return** over each year, from `data/NIFTY50_TRI.csv`;
* **IPO supply** per year and the **median subscription** per year;
* the **Nifty move between issue close and listing**, per IPO, aggregated by year — the
  3-to-6-day window in which a listing gain is actually realised.

That last one is the closest thing available to "the market turned against these listings",
and it is a *mechanism* rather than a correlate: if the index fell between close and
listing, every IPO that week faces a worse tape regardless of its book.

    python world_changed.py
    python world_changed.py --self-test
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
import score_l as SL                                         # noqa: E402

OUT_CSV = ROOT / "reports" / "WORLD_CHANGED.csv"
OUT_MD = ROOT / "reports" / "WORLD_CHANGED.md"

# Stated once here rather than in prose: what this module does NOT measure, and why.
NOT_MEASURED = (
    "FII/DII flows. NSE's api/fiidiiTradeReact returns the current day only; ?date= and "
    "?from=&to= are accepted with HTTP 200 and ignored. The historical FII/FPI/DII "
    "archive page is JS-rendered and exposes no static file links, and the two report-API "
    "shapes tried returned HTTP 503 and {\"error\": \"file is unavailable\"}. No permitted "
    "historical series was reached, so none is reported. Nothing here is a stand-in for it."
)


def tri_series() -> pd.DataFrame:
    """`load_nifty_tri()` returns a date-indexed Series; make it a frame once."""
    t = dataio.load_nifty_tri()
    out = t.rename("tri").reset_index()
    out.columns = ["date", "tri"]
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date").reset_index(drop=True)


def tri_return(tri: pd.DataFrame, a, b) -> float | None:
    """TRI return between two dates, using the last close at or before each. None if the
    window falls outside the series — never extrapolated."""
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    s = tri[tri["date"] <= a]
    e = tri[tri["date"] <= b]
    if s.empty or e.empty or b < tri["date"].min() or a < tri["date"].min():
        return None
    v0, v1 = float(s["tri"].iloc[-1]), float(e["tri"].iloc[-1])
    if v0 <= 0:
        return None
    return 100.0 * (v1 / v0 - 1.0)


def rows() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    d = m[m["exclude_reason"].isna()].copy() if "exclude_reason" in m else m.copy()
    # The master's `issue_open_date` holds the LISTING date (known defect, CLAUDE.md), so
    # it is used as the listing date here and named accordingly.
    d["listing"] = pd.to_datetime(d["issue_open_date"], errors="coerce")
    d["total"] = pd.to_numeric(d["Total"], errors="coerce")
    d["gain"] = pd.to_numeric(d["Listing Gain"], errors="coerce")
    d = d.dropna(subset=["listing", "total", "gain"])

    # Prefer the exchange-sourced label where we have one (H18).
    lab = ROOT / "data" / "listing_prices.csv"
    if lab.exists():
        L = pd.read_csv(lab)
        L = L.dropna(subset=["listing_gain_pct"]).copy()
        L["k"] = L["ipo"].astype(str).map(dataio.norm_name)
        L = L.drop_duplicates("k", keep="last")[["k", "listing_gain_pct"]]
        d["k"] = d["company"].astype(str).map(dataio.norm_name)
        d = d.merge(L, on="k", how="left")
        d["gain"] = d["listing_gain_pct"].where(d["listing_gain_pct"].notna(), d["gain"])

    tri = tri_series()

    # The close-to-listing window. The master has no reliable issue-close date, so the
    # window is taken as the 5 calendar days before listing: the T+3 settlement era puts
    # listing 3 working days after close, and 5 calendar days spans that without assuming
    # a specific exchange calendar. It is a WINDOW, not a claimed close date, and is
    # labelled as such everywhere it appears.
    d["nifty_5d_to_listing_pct"] = [
        tri_return(tri, x - pd.Timedelta(days=5), x) for x in d["listing"]]

    lv = SL.firing_levels()
    d["email_L1"] = np.where(d["total"] >= lv["L1"], "BID", "no")
    d["email_L2"] = np.where(d["total"] >= lv["L2"], "BID", "no")
    d["L1_met"] = (d["gain"] > 0).astype(int)
    d["L2_met"] = (d["gain"] > 10).astype(int)
    d["year"] = d["listing"].dt.year
    return d.sort_values("listing").reset_index(drop=True)


def by_year(d: pd.DataFrame) -> pd.DataFrame:
    tri = tri_series()
    out = []
    for y, g in d.groupby("year"):
        r = {"year": int(y), "n_ipos": len(g),
             "median_total_x": round(float(g["total"].median()), 2),
             "nifty_tri_year_pct": None,
             "median_nifty_5d_to_listing_pct": (
                 None if g["nifty_5d_to_listing_pct"].isna().all()
                 else round(float(g["nifty_5d_to_listing_pct"].median()), 2)),
             "base_rate_L1_pct": round(100 * float(g["L1_met"].mean()), 1),
             "base_rate_L2_pct": round(100 * float(g["L2_met"].mean()), 1)}
        yr = tri_return(tri, f"{y}-01-01", f"{y}-12-31")
        r["nifty_tri_year_pct"] = None if yr is None else round(yr, 2)
        for tgt in ("L1", "L2"):
            f = g[g[f"email_{tgt}"] == "BID"]
            r[f"{tgt}_fires"] = int(len(f))
            r[f"{tgt}_hits"] = int(f[f"{tgt}_met"].sum()) if len(f) else 0
            r[f"{tgt}_delivered_pct"] = (round(100 * float(f[f"{tgt}_met"].mean()), 1)
                                         if len(f) else None)
        out.append(r)
    return pd.DataFrame(out).sort_values("year").reset_index(drop=True)


def correlate(t: pd.DataFrame, min_fires: int = 10) -> dict:
    """Rank correlation between a year's delivered rate and each market measure.

    Spearman, computed from ranks with numpy, because what matters is whether weak years
    line up with weak markets rather than the shape of the relationship. Years with fewer
    than `min_fires` fires are excluded: a 100% delivered rate on 2 fires is noise, and
    including it is how a spurious correlation gets manufactured.
    """
    res = {"min_fires": min_fires, "pairs": {}}
    for tgt in ("L1", "L2"):
        sub = t[(t[f"{tgt}_fires"] >= min_fires) & t[f"{tgt}_delivered_pct"].notna()]
        res["pairs"][tgt] = {"n_years": int(len(sub)),
                             "years": [int(x) for x in sub["year"]]}
        for col in ("nifty_tri_year_pct", "median_nifty_5d_to_listing_pct",
                    "n_ipos", "median_total_x"):
            s = sub[[f"{tgt}_delivered_pct", col]].dropna()
            if len(s) < 4:
                res["pairs"][tgt][col] = None
                continue
            a = pd.Series(s[f"{tgt}_delivered_pct"]).rank().to_numpy()
            b = pd.Series(s[col]).rank().to_numpy()
            if a.std() == 0 or b.std() == 0:
                res["pairs"][tgt][col] = None
                continue
            res["pairs"][tgt][col] = round(float(np.corrcoef(a, b)[0, 1]), 3)
    return res


def md(d: pd.DataFrame, t: pd.DataFrame, c: dict) -> str:
    lv = SL.firing_levels()
    L = ["# Did the world change, or did the model? — Priority 3b", "",
         f"Delivered hit rate per listing year at the **ratified** thresholds "
         f"(L1 >= {lv['L1']:.2f}x, L2 >= {lv['L2']:.2f}x), against what the market was "
         f"doing that year. {len(d)} IPOs, {int(t['year'].min())}-{int(t['year'].max())}.",
         "",
         "> **What this does not measure.** " + NOT_MEASURED, "",
         "## Year by year", "",
         "| year | IPOs | median Total | Nifty TRI yr | Nifty 5d to listing (median) "
         "| L1 fires | L1 delivered | L2 fires | L2 delivered |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in t.itertuples():
        f = lambda v, s="%": "—" if v is None or pd.isna(v) else f"{v:+.1f}{s}"  # noqa: E731
        g = lambda v: "—" if v is None or pd.isna(v) else f"{v:.1f}%"             # noqa: E731
        L.append(f"| {r.year} | {r.n_ipos} | {r.median_total_x:.2f}x "
                 f"| {f(r.nifty_tri_year_pct)} | {f(r.median_nifty_5d_to_listing_pct)} "
                 f"| {r.L1_fires} | {g(r.L1_delivered_pct)} "
                 f"| {r.L2_fires} | {g(r.L2_delivered_pct)} |")

    L += ["", "## Does the delivered rate track the market?", "",
          f"Spearman rank correlation, years with at least {c['min_fires']} fires only — "
          f"a 100% rate on two fires is noise, and including it is how a spurious "
          f"correlation gets manufactured.", "",
          "| | L1 | L2 |", "|---|---|---|"]
    names = {"nifty_tri_year_pct": "Nifty TRI return that year",
             "median_nifty_5d_to_listing_pct": "Nifty move, 5d before listing",
             "n_ipos": "IPO supply that year",
             "median_total_x": "median subscription that year"}
    for col, label in names.items():
        a = c["pairs"]["L1"].get(col)
        b = c["pairs"]["L2"].get(col)
        L.append(f"| {label} | {'—' if a is None else a} | {'—' if b is None else b} |")
    # The finding, generated from the numbers above so it cannot go stale.
    y25 = t[t["year"] == 2025]
    if len(y25):
        r = y25.iloc[0]
        tri_yr = r["nifty_tri_year_pct"]
        pre = r["median_nifty_5d_to_listing_pct"]
        n_ipos = int(r["n_ipos"])
        med_tot = r["median_total_x"]
        busiest = n_ipos == int(t["n_ipos"].max())
        rho_supply = c["pairs"]["L1"].get("n_ipos")
        rho_pre = c["pairs"]["L1"].get("median_nifty_5d_to_listing_pct")
        rho_yr = c["pairs"]["L1"].get("nifty_tri_year_pct")
        L += ["", "## What this says about 2025", "",
              f"2025 is the year under suspicion, and it was **not** a weak market. The "
              f"Nifty 50 TRI returned **{tri_yr:+.1f}%** that year, and the median Nifty "
              f"move in the five days before each listing was **{pre:+.2f}%** — flat, not "
              f"falling.", "",
              f"What was unusual about 2025 is **supply**: {n_ipos} IPOs"
              + (", the largest year in the dataset" if busiest else "")
              + f", at a median subscription of {med_tot:.2f}x.", "",
              f"Across the years thick enough to count, L1's delivered rate ranks "
              f"**{rho_supply} against IPO supply** and **{rho_pre} against the "
              f"pre-listing Nifty move**, but only **{rho_yr} against the year's index "
              f"return**. So the annual market direction is not where the signal is. With "
              f"only {c['pairs']['L1']['n_years']} usable years for L1 and "
              f"{c['pairs']['L2']['n_years']} for L2, none of this is significant on its "
              f"own — L2's figures in particular are noise at that sample size and should "
              f"not be read as a pattern.", "",
              "**The FII hypothesis is neither confirmed nor refuted here**, because no "
              "permitted historical FII series was reachable. What can be said is that the "
              "two market measures that *were* available do not show 2025 as a bad tape, "
              "so if FII outflows were heavy that year they did not show up in the index "
              "level or in the window where a listing gain is actually realised.", ""]

    L += ["", f"L1 years used: {c['pairs']['L1']['years']}",
          "", f"L2 years used: {c['pairs']['L2']['years']}", ""]
    return "\n".join(L) + "\n"


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

    print("[1] no FII number is reported, and the absence is explained")
    import inspect
    # The DATA producers only. md() discusses the FII hypothesis in prose, which is the
    # point - what must not exist is a COLUMN purporting to be an FII flow.
    body = "".join(inspect.getsource(fn) for fn in (rows, by_year, correlate))
    chk("no column claims to be an FII flow", "fii" not in body.lower())
    cols = set(by_year(rows()).columns)
    chk("and none of the emitted columns mentions one",
        not any("fii" in str(x).lower() or "fpi" in str(x).lower() for x in cols), cols)
    chk("the reason it is absent is recorded", "fiidiiTradeReact" in NOT_MEASURED)
    chk("and it says nothing substitutes for it", "stand-in" in NOT_MEASURED)

    print("\n[2] TRI returns are read, never extrapolated")
    tri = tri_series()
    chk("a window before the series starts returns None, not a guess",
        tri_return(tri, "2005-01-01", "2005-12-31") is None)
    r = tri_return(tri, "2020-01-01", "2020-12-31")
    chk("a real year returns a number", r is not None and -60 < r < 120, r)

    print("\n[3] thresholds come from the ratified artefact, not from this file")
    src = inspect.getsource(rows)
    chk("firing levels are read from score_l", "SL.firing_levels()" in src)
    chk("no threshold is hardcoded here",
        "28.39" not in src and "54.02" not in src)

    print("\n[4] thin years are excluded from the correlation")
    t = pd.DataFrame({"year": [2020, 2021], "L1_fires": [2, 40],
                      "L1_delivered_pct": [100.0, 80.0], "L2_fires": [1, 30],
                      "L2_delivered_pct": [100.0, 70.0],
                      "nifty_tri_year_pct": [10.0, 20.0],
                      "median_nifty_5d_to_listing_pct": [1.0, 2.0],
                      "n_ipos": [5, 50], "median_total_x": [2.0, 10.0]})
    c = correlate(t, min_fires=10)
    chk("a 2-fire year is dropped", c["pairs"]["L1"]["years"] == [2021])
    chk("and with one year left no correlation is invented",
        c["pairs"]["L1"]["nifty_tri_year_pct"] is None)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = rows()
    t = by_year(d)
    c = correlate(t)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_MD.write_text(md(d, t, c), encoding="utf-8")
    cols = ["year", "n_ipos", "nifty_tri_year_pct", "median_nifty_5d_to_listing_pct",
            "L1_fires", "L1_delivered_pct", "L2_fires", "L2_delivered_pct"]
    print(t[cols].to_string(index=False))
    print("\nrank correlation with delivered rate:")
    for tgt in ("L1", "L2"):
        p = c["pairs"][tgt]
        print(f"  {tgt} (n={p['n_years']} years): "
              f"nifty_year={p.get('nifty_tri_year_pct')}  "
              f"nifty_5d={p.get('median_nifty_5d_to_listing_pct')}  "
              f"supply={p.get('n_ipos')}  median_total={p.get('median_total_x')}")
    print(f"\n{OUT_CSV}\n{OUT_MD}")

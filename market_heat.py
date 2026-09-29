"""
market_heat.py — "market IPO heat" per IPO (PLAN.md Stage 2).

    heat = mean listing gain of mainboard IPOs that LISTED in the 30 days before this
           IPO's bidding opened.

Leakage discipline. The cutoff is when *this* IPO's bidding opened, and only IPOs that had
already listed strictly before that moment contribute. Their listing gains were public on
their own listing day, so the feature is knowable before the bid deadline (global rule 7).

Cutoff, in order of preference:
  1. the recovered true issue-open date (`issue_dates_recovered.csv`, 2021+ only)
  2. otherwise listing date − 10 days (the plan's fallback; Indian IPOs list ~6-8 working
     days after bidding opens, so this is conservative rather than optimistic)

Window widening, per the plan:
  30 days → fewer than 2 IPOs → 60 days → still fewer than 2 → long-run median, flagged.

The long-run median is the **expanding** median of every mainboard listing gain that was
already public before the cutoff — not the full-sample median, which would leak the future
into the earliest rows. Rows with no prior listing at all (the very first IPOs in the
dataset) get NaN and are flagged `no_prior_data`.

    python market_heat.py        # writes market_heat.csv + prints coverage
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import dataio

ROOT = Path(__file__).resolve().parent
NARROW_DAYS, WIDE_DAYS, MIN_IPOS = 30, 60, 2
OPEN_TO_LIST_FALLBACK_DAYS = 10


def _true_open_dates() -> pd.Series:
    """company -> recovered true issue-open date (only rows that actually have one)."""
    p = ROOT / "issue_dates_recovered.csv"
    if not p.exists():
        return pd.Series(dtype="datetime64[ns]")
    d = pd.read_csv(p, parse_dates=["issue_open_date_true"])
    d = d[d["issue_open_date_true"].notna()]
    return d.drop_duplicates("company").set_index("company")["issue_open_date_true"]


def build(master: pd.DataFrame | None = None) -> pd.DataFrame:
    m = (dataio.load_master_with_symbols() if master is None else master).copy()
    m["listing_date_m"] = m["listing_date_master"]
    m["listing_gain"] = pd.to_numeric(m["Listing Gain"], errors="coerce")

    opens = _true_open_dates()
    m["open_true"] = m["company"].map(opens)
    m["cutoff"] = m["open_true"].fillna(
        m["listing_date_m"] - pd.Timedelta(days=OPEN_TO_LIST_FALLBACK_DAYS))
    m["cutoff_source"] = np.where(m["open_true"].notna(), "recovered_open_date",
                                  f"listing_date_minus_{OPEN_TO_LIST_FALLBACK_DAYS}d")

    # contributors: excluded rows (FPO/REIT/IDR/bad date) never count as market activity,
    # and a contributor needs a listing date and a listing gain to contribute anything.
    src = m[m["exclude_reason"].isna() & m["listing_date_m"].notna()
            & m["listing_gain"].notna()][["listing_date_m", "listing_gain"]]
    src = src.sort_values("listing_date_m").reset_index(drop=True)
    ld = src["listing_date_m"].to_numpy()
    lg = src["listing_gain"].to_numpy()
    cum = np.concatenate([[0.0], np.cumsum(lg)])

    rows = []
    for i, r in m.iterrows():
        cut = r["cutoff"]
        if pd.isna(cut):
            rows.append({"heat": np.nan, "n_window": 0, "window_days": None,
                         "heat_flag": "no_cutoff"})
            continue
        hi = int(np.searchsorted(ld, np.datetime64(cut), side="left"))   # listed strictly before
        heat, n, wd, flag = np.nan, 0, None, ""
        for days in (NARROW_DAYS, WIDE_DAYS):
            lo = int(np.searchsorted(ld, np.datetime64(cut - pd.Timedelta(days=days)), side="left"))
            n = hi - lo
            if n >= MIN_IPOS:
                heat = (cum[hi] - cum[lo]) / n
                wd, flag = days, "" if days == NARROW_DAYS else f"widened_to_{days}d"
                break
        if not np.isfinite(heat):
            if hi >= 1:
                heat = float(np.median(lg[:hi]))      # expanding, leak-free
                n, wd, flag = hi, None, "long_run_median"
            else:
                heat, n, wd, flag = np.nan, 0, None, "no_prior_data"
        rows.append({"heat": heat, "n_window": int(n), "window_days": wd, "heat_flag": flag})

    # keep the master's index: company names are NOT unique (Power Grid and Engineers
    # India each have two FPO rows), so callers must join on the index, not on name.
    out = pd.concat([m[["company", "symbol", "listing_date_m", "cutoff", "cutoff_source",
                        "exclude_reason"]],
                     pd.DataFrame(rows, index=m.index)], axis=1)
    return out.rename(columns={"listing_date_m": "listing_date"})


def main():
    h = build()
    h.to_csv(ROOT / "market_heat.csv", index=False, encoding="utf-8")
    ok = h["heat"].notna()
    print(f"rows {len(h)} | heat present {ok.sum()} | missing {(~ok).sum()}")
    print("\ncutoff source:")
    print(h["cutoff_source"].value_counts().to_string())
    print("\nflags:")
    print(h["heat_flag"].replace("", "30d_window").value_counts().to_string())
    print("\nheat distribution (unflagged rows):")
    print(h.loc[ok, "heat"].describe().round(2).to_string())
    print("\nrows without heat:")
    print(h[~ok][["company", "listing_date", "heat_flag"]].to_string(index=False))
    print("\nwritten: market_heat.csv")


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

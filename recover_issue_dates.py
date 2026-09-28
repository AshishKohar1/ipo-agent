"""
recover_issue_dates.py — recover the TRUE issue-open date for each master row.

The master's 'issue_open_date' column holds the listing date (see CLAUDE.md). This
script joins each row to the NSE spine (ISSUE START DATE) and the IPOMatrix trackers
(Opening Date) on completed company name + listing date within ±30 days, and writes
issue_dates_recovered.csv. It never modifies master_with_symbols.csv.

Reconciliation (the NSE spine and IPOMatrix are independent sources):
  both sources, same date   -> confidence high,   source nse_spine+tracker
  one source only           -> confidence medium, source nse_spine | tracker
  sources disagree          -> NULL, confidence rejected, both dates in the flags file
  no match                  -> NULL, confidence none
Rows whose recovered open date is after the listing date, or more than 45 days before
it, are written to issue_dates_FLAGS.csv (the date is kept in the main file, flagged).

    python recover_issue_dates.py
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import dataio

WINDOW = pd.Timedelta(days=30)
SIM = 0.85
MAX_GAP_DAYS = 45


def best(name, listing, cands):
    w = cands[((cands["listing_date"] - listing).abs() <= WINDOW) |
              ((cands["issue_open_date"] - listing).abs() <= WINDOW)]
    scored = sorted(((dataio.prefix_sim(name, c), i) for i, c in w["company"].items()),
                    reverse=True)
    scored = [s for s in scored if s[0] >= SIM]
    if not scored:
        return None
    top = [i for s, i in scored if s == scored[0][0]]
    opens = {cands.at[i, "issue_open_date"] for i in top}
    names = {dataio.norm_name(cands.at[i, "company"]) for i in top}
    if len(names) > 1 or len(opens) > 1:      # ambiguous candidate -> no match
        return "ambiguous"
    return cands.loc[top[0]]


def main():
    m = pd.read_csv("master_with_symbols.csv", parse_dates=["issue_open_date", "listing_date"])
    spine = dataio.load_nse_spine()
    spine = spine[spine["security_type"].isin(["EQ", "SME", "BE", "IV", "RR"])]
    trk = dataio.load_trackers()

    out, flags = [], []
    for _, r in m.iterrows():
        # the master's date column IS the listing date; prefer a recovered listing_date
        L = r["listing_date"] if pd.notna(r["listing_date"]) else r["issue_open_date"]
        s, t = best(r["company"], L, spine), best(r["company"], L, trk)
        vals = {}
        if isinstance(s, pd.Series) and pd.notna(s["issue_open_date"]):
            vals["nse_spine"] = s["issue_open_date"].normalize()
        if isinstance(t, pd.Series) and pd.notna(t["issue_open_date"]):
            vals["tracker"] = t["issue_open_date"].normalize()

        if not vals:
            d, src, conf = None, "ambiguous" if "ambiguous" in (s, t) else "unresolved", "none"
        elif len(set(vals.values())) > 1:
            d, src, conf = None, "conflict", "rejected"
            flags.append({"company": r["company"], "listing_date": L.date(),
                          "flag": "sources disagree",
                          **{k: v.date() for k, v in vals.items()}})
        else:
            d = next(iter(vals.values()))
            src = "+".join(sorted(vals))
            conf = "high" if len(vals) == 2 else "medium"
            gap = (L - d).days
            if gap < 0 or gap > MAX_GAP_DAYS:
                flags.append({"company": r["company"], "listing_date": L.date(),
                              "flag": "open after listing" if gap < 0
                              else f"open {gap}d before listing",
                              **{k: v.date() for k, v in vals.items()}})
        out.append({"company": r["company"], "symbol": r["symbol"],
                    "listing_date": L.date(),
                    "issue_open_date_true": None if d is None else d.date(),
                    "source": src, "confidence": conf})

    o = pd.DataFrame(out)
    o.to_csv("issue_dates_recovered.csv", index=False)
    pd.DataFrame(flags).to_csv("issue_dates_FLAGS.csv", index=False)

    o["year"] = pd.to_datetime(o["listing_date"]).dt.year
    by = o.groupby("year").agg(rows=("company", "size"),
                               recovered=("issue_open_date_true", lambda x: x.notna().sum()))
    by["rate_%"] = (by["recovered"] / by["rows"] * 100).round(1)
    print(by.to_string())
    print(f"\nTOTAL recovered {o['issue_open_date_true'].notna().sum()}/{len(o)}")
    print(o["confidence"].value_counts().to_string())
    print(f"flags: {len(flags)} -> issue_dates_FLAGS.csv")
    ok = o.dropna(subset=["issue_open_date_true"])
    gap = (pd.to_datetime(ok["listing_date"]) - pd.to_datetime(ok["issue_open_date_true"])).dt.days
    print("open->listing gap (days):", gap.describe()[["min", "50%", "max"]].to_dict())


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    main()

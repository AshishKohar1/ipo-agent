"""
backtest_email.py — Priority 2: backtest the EMAIL, not the model.

The model has been measured plenty. This measures the thing the user actually reads: for
every IPO that closed in the last 12 months, what the daily email **would have said**, and
what then happened.

Two deliberate choices:

**The labels come from the exchanges, not from the master.** `data/listing_prices.csv` holds
as-reported listing prices reconciled from NSE's and BSE's own bhavcopies (H18), so the
"what actually happened" column is independent of the `Listing Gain` column the thresholds
were derived against. Where a row has no exchange label the master's figure is used and the
row says so, because dropping it would quietly bias the summary toward the companies the
exchanges still carry.

**The verdict comes from the live code path.** `score_l.predict_live()` is called, not a
reimplementation of the rule, so a divergence between this backtest and the email is
impossible by construction.

One honest limitation, stated in the output: the email scores the **~15:00** subscription
figure, and what is on record historically is the **final** figure. Final subscription is
higher, so this backtest is **optimistic about how often the email would have fired** — it
is a test of the decision rule, not of the 3pm-versus-close gap, which only the paired
15:00/17:30 capture can measure.

    python backtest_email.py
    python backtest_email.py --months 24
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
sys.path.insert(0, str(ROOT / "models"))
import dataio                                               # noqa: E402
import score_l as SL                                        # noqa: E402

OUT_CSV = ROOT / "reports" / "EMAIL_BACKTEST_12M.csv"
OUT_MD = ROOT / "reports" / "EMAIL_BACKTEST_12M.md"
LABELS = ROOT / "data" / "listing_prices.csv"

COLS = ["date", "company", "total_subscription_x", "offer_price",
        "email_L1", "email_L2", "listing_gain_pct", "label_source", "label_reconciled",
        "L1_target_met", "L2_target_met", "L1_verdict_right", "L2_verdict_right",
        "outcome"]


def rows(months: int) -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    d = m[m["exclude_reason"].isna()].copy() if "exclude_reason" in m else m.copy()
    # The master's `issue_open_date` holds the LISTING date (known defect, CLAUDE.md).
    d["date"] = pd.to_datetime(d["issue_open_date"], errors="coerce")
    d["total"] = pd.to_numeric(d["Total"], errors="coerce")
    d["master_gain"] = pd.to_numeric(d["Listing Gain"], errors="coerce")
    d["offer"] = pd.to_numeric(d["Offer Price"], errors="coerce")
    d = d.dropna(subset=["date", "total"])
    cut = d["date"].max() - pd.DateOffset(months=months)
    d = d[d["date"] > cut]

    # Exchange-sourced labels (H18) take precedence over the master's.
    lab = pd.DataFrame()
    if LABELS.exists():
        lab = pd.read_csv(LABELS)
        lab["k"] = lab["ipo"].astype(str).map(dataio.norm_name)
        lab = lab[["k", "listing_gain_pct", "reconciled"]].dropna(subset=["listing_gain_pct"])
        lab = lab.drop_duplicates(subset="k", keep="last")
    d["k"] = d["company"].astype(str).map(dataio.norm_name)
    d = d.merge(lab, on="k", how="left") if len(lab) else d.assign(
        listing_gain_pct=np.nan, reconciled=None)

    d["gain"] = d["listing_gain_pct"].where(d["listing_gain_pct"].notna(), d["master_gain"])
    d["label_source"] = np.where(d["listing_gain_pct"].notna(),
                                 "exchange bhavcopy (H18)", "master Listing Gain")
    return d.dropna(subset=["gain"]).sort_values("date").reset_index(drop=True)


def backtest(months: int = 12) -> tuple[pd.DataFrame, dict]:
    d = rows(months)
    out = []
    for r in d.itertuples():
        # The LIVE code path, not a reimplementation.
        res = SL.predict_live(float(r.total))
        l1, l2 = res["L1"]["verdict"], res["L2"]["verdict"]
        g = float(r.gain)
        l1_met, l2_met = g > 0.0, g > 10.0
        out.append({
            "date": str(r.date.date()), "company": r.company,
            "total_subscription_x": round(float(r.total), 2),
            "offer_price": None if pd.isna(r.offer) else float(r.offer),
            "email_L1": l1, "email_L2": l2,
            "listing_gain_pct": round(g, 2),
            "label_source": r.label_source,
            "label_reconciled": getattr(r, "reconciled", None),
            "L1_target_met": int(l1_met), "L2_target_met": int(l2_met),
            "L1_verdict_right": int((l1 == "BID") == l1_met),
            "L2_verdict_right": int((l2 == "BID") == l2_met),
            "outcome": ("BID and it worked" if l1 == "BID" and l1_met else
                        "BID and it fell" if l1 == "BID" else
                        "said no and it soared" if l2_met else
                        "said no and it was right" if not l1_met else
                        "said no, small gain missed"),
        })
    t = pd.DataFrame(out, columns=COLS)

    s = {"months": months, "n_ipos": len(t),
         "date_range": [t["date"].min(), t["date"].max()] if len(t) else None,
         "levels": SL.firing_levels(),
         "label_mix": t["label_source"].value_counts().to_dict() if len(t) else {}}
    for tgt in ("L1", "L2"):
        fired = t[t[f"email_{tgt}"] == "BID"]
        met = t[f"{tgt}_target_met"]
        s[tgt] = {
            "promise": SL.required()[tgt],
            "bids": int(len(fired)),
            "bid_hits": int(fired[f"{tgt}_target_met"].sum()) if len(fired) else 0,
            "bid_hit_rate": (float(fired[f"{tgt}_target_met"].mean())
                             if len(fired) else None),
            "no_bids": int(len(t) - len(fired)),
            "missed_winners": int((~(t[f"email_{tgt}"] == "BID") & (met == 1)).sum()),
            "base_rate": float(met.mean()) if len(t) else None,
            "accuracy": float(t[f"{tgt}_verdict_right"].mean()) if len(t) else None,
        }
    return t, s


def md(t: pd.DataFrame, s: dict) -> str:
    lv = s["levels"]
    L = [f"# Email backtest — last {s['months']} months", "",
         f"What the daily email **would have said** for every IPO that closed between "
         f"{s['date_range'][0]} and {s['date_range'][1]}, and what then happened.", "",
         f"Rule under test (H17, ratified): **L1 bids at Total ≥ {lv['L1']:.2f}x, "
         f"L2 at ≥ {lv['L2']:.2f}x.** Verdicts come from the live `score_l.predict_live()`, "
         f"not a reimplementation.", "",
         f"`{s['n_ipos']}` IPOs. Labels: "
         + ", ".join(f"{v} from {k}" for k, v in s["label_mix"].items()) + ".", "",
         "> **This is optimistic about how often the email would have fired.** The email "
         "scores the ~15:00 figure; what is on record historically is the FINAL figure, "
         "which is higher. So treat the bid COUNT as an upper bound. The hit rate among "
         "those bids is the honest number, because it conditions on the same rows either "
         "way.", ""]

    L += ["## Summary", "",
          "| | L1 (gain > 0%) | L2 (gain > 10%) |", "|---|---|---|"]
    a, b = s["L1"], s["L2"]
    hr_a = "—" if a["bid_hit_rate"] is None else f"{a['bid_hit_rate']:.1%}"
    hr_b = "—" if b["bid_hit_rate"] is None else f"{b['bid_hit_rate']:.1%}"
    L += [f"| Promise | {a['promise']:.0%} | {b['promise']:.0%} |",
          f"| Fires above | {lv['L1']:.2f}x | {lv['L2']:.2f}x |",
          f"| **BIDs** | **{a['bids']}** | **{b['bids']}** |",
          f"| of which hit | {a['bid_hits']} | {b['bid_hits']} |",
          f"| **hit rate among BIDs** | **{hr_a}** | **{hr_b}** |",
          f"| said no | {a['no_bids']} | {b['no_bids']} |",
          f"| winners it said no to | {a['missed_winners']} | {b['missed_winners']} |",
          f"| base rate (all IPOs) | {a['base_rate']:.1%} | {b['base_rate']:.1%} |",
          f"| verdict accuracy | {a['accuracy']:.1%} | {b['accuracy']:.1%} |", ""]

    for tgt, label in (("L1", "L1 — any listing gain"), ("L2", "L2 — gain above 10%")):
        fired = t[t[f"email_{tgt}"] == "BID"]
        bad = fired[fired[f"{tgt}_target_met"] == 0].nsmallest(8, "listing_gain_pct")
        miss = t[(t[f"email_{tgt}"] != "BID") & (t[f"{tgt}_target_met"] == 1)] \
            .nlargest(8, "listing_gain_pct")
        L += [f"## {label}", "",
              "### Backed and it fell", ""]
        if bad.empty:
            L += ["None.", ""]
        else:
            L += ["| date | company | Total | gain |", "|---|---|---|---|"]
            L += [f"| {r.date} | {r.company} | {r.total_subscription_x:.2f}x "
                  f"| **{r.listing_gain_pct:+.1f}%** |" for r in bad.itertuples()]
            L += [""]
        L += ["### Said no and it soared", ""]
        if miss.empty:
            L += ["None.", ""]
        else:
            L += ["| date | company | Total | gain |", "|---|---|---|---|"]
            L += [f"| {r.date} | {r.company} | {r.total_subscription_x:.2f}x "
                  f"| **{r.listing_gain_pct:+.1f}%** |" for r in miss.itertuples()]
            L += [""]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    t, s = backtest(a.months)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_MD.write_text(md(t, s), encoding="utf-8")
    lv = s["levels"]
    print(f"{s['n_ipos']} IPOs, {s['date_range'][0]} to {s['date_range'][1]}")
    print(f"rule: L1 >= {lv['L1']:.2f}x, L2 >= {lv['L2']:.2f}x\n")
    for tgt in ("L1", "L2"):
        d = s[tgt]
        hr = "—" if d["bid_hit_rate"] is None else f"{d['bid_hit_rate']:.1%}"
        print(f"  {tgt}: {d['bids']:3d} BIDs, {d['bid_hits']:3d} hit  -> {hr:>7s} "
              f"(promise {d['promise']:.0%})   said no to {d['missed_winners']} winners   "
              f"base rate {d['base_rate']:.1%}")
    print(f"\nlabels: {s['label_mix']}")
    print(f"\n{OUT_CSV}\n{OUT_MD}")

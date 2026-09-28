"""
models/model_l.py — Model L: P(listing gain), on models/framework.py.

Four fitted models (segments are never pooled — CLAUDE.md rule 6):
  model_l1_mainboard   listing_gain > 0    master dataset, Total + QIB/HNI/RII split + size
  model_l2_mainboard   listing_gain > 10
  model_l1_sme         listing_gain > 0    IPOMatrix trackers 2025-26, Total + size only
  model_l2_sme         listing_gain > 10

DECISION TIME: these use FINAL subscription, knowable only at bid close (the D3 model
of Part B.2). They are not valid for a bid decision on day 1-2 of the issue.

    python models/model_l.py            # fit all four, write cards
    from models.model_l import predict_live
    predict_live("mainboard", {"Total": 45, "QIB": 80, "HNI": 60, "RII": 12, "Issue_Size": 800})
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import framework as F
import dataio

MB_FEATURES = ["log1p_total", "log1p_qib", "log1p_hni", "log1p_rii", "log_issue_size"]
SME_FEATURES = ["log1p_total", "log_issue_size"]
THRESHOLDS = {"L1": {"L1": 0.90}, "L2": {"L2": 0.80}}
CUTS = {"L1": 0.0, "L2": 10.0}


# ----------------------------------------------------------------------
# loaders (dataio only) and feature builders
# ----------------------------------------------------------------------
def load_mainboard() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    m["listing_date"] = m["listing_date_master"]
    m["listing_gain"] = pd.to_numeric(m["Listing Gain"], errors="coerce")
    for k, c in CUTS.items():
        m[k] = (m["listing_gain"] > c).astype(float).where(m["listing_gain"].notna())
    return m


def load_sme() -> pd.DataFrame:
    t = dataio.load_trackers()
    t = t[t["category"] == "SME"].copy()
    t = t.rename(columns={"subscription_x": "Total", "issue_size_cr": "Issue_Size",
                          "listing_gain_pct": "listing_gain"})
    for k, c in CUTS.items():
        t[k] = (t["listing_gain"] > c).astype(float).where(t["listing_gain"].notna())
    t["exclude_reason"] = None
    return t


def _num(df, *names):
    for n in names:
        if n in df:
            return pd.to_numeric(df[n], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def mb_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["log1p_total"] = np.log1p(_num(df, "Total", "total"))
    out["log1p_qib"] = np.log1p(_num(df, "QIB", "qib"))
    out["log1p_hni"] = np.log1p(_num(df, "HNI", "hni", "NII"))
    out["log1p_rii"] = np.log1p(_num(df, "RII", "rii"))
    size = _num(df, "Issue_Size", "Issue_Size(crores)", "issue_size_cr")
    out["log_issue_size"] = np.log(size.where(size > 0))
    return out


def sme_features(df: pd.DataFrame) -> pd.DataFrame:
    return mb_features(df)[SME_FEATURES]


# ----------------------------------------------------------------------
# specs
# ----------------------------------------------------------------------
MB_NOTES = [
    "Uses FINAL subscription (QIB/HNI/RII/Total). Knowable only at bid close — this is the D3 "
    "model. Not valid for bidding on day 1-2.",
    "Mainboard status is verified against the NSE spine / trackers only from Sep 2021; earlier "
    "rows are assumed mainboard (no SME row was found in the master where it could be checked).",
    "`Listing Gain` comes from the master dataset; whether it's listing open or close is not "
    "documented in the source. The SME model uses listing-day CLOSE — the two are not comparable.",
    "`class_weight='balanced'` pushes probabilities towards 0.5; thresholds are verified on "
    "out-of-fold hit rates, not read off the probability scale.",
    "Survivorship does not affect Model L: the target is realised on listing day for every IPO.",
    "**Severe collinearity.** VIF: Total 83, HNI 20, QIB 20, RII 8 (spec limit 5). Total is a "
    "blend of the three categories, so the negative QIB/HNI/RII coefficients are conditional on "
    "Total and must NOT be read as 'more QIB demand is bad'. Walk-forward, the split adds little: "
    "L1 mean AUC 0.765 with it vs 0.760 on Total + size alone; L2 0.865 vs 0.871 (unweighted). "
    "Consider Total + size, or the categories without Total.",
    "Half-life is chosen by the UNWEIGHTED mean of per-year AUCs, so the 2026 fold (n=20) counts "
    "as much as 2025 (n=102). For L1 this decides the choice: pooled out-of-fold AUC would pick 2y.",
]
SME_NOTES = [
    "**Thin history.** Only two calendar years (2025-26, 402 SME IPOs) exist in the trackers. "
    "Walk-forward by year can test ONE year (2026, trained on 2025 only) — a single fold, so the "
    "AUC has no year-to-year spread to judge stability by.",
    "**Recency weighting is nearly meaningless here.** With all training rows 1-2 years old, "
    "half-lives of 2-8 years give almost flat weights, so the half-life 'selection' mostly "
    "reflects noise. Treat the chosen half-life as uninformative.",
    "Features are Total subscription and issue size only (the trackers have no category split).",
    "Target is listing-day CLOSE vs issue price (tracker). Mainboard uses the master's "
    "`Listing Gain`, which may be an opening price.",
    "IPOMatrix (tracker) and Chittorgarh share a parent; the SME target and features are "
    "single-source, not reconciled.",
    "Uses FINAL subscription — D3 decision time only.",
]


def spec(target: str, segment: str) -> F.ModelSpec:
    mb = segment == "mainboard"
    return F.ModelSpec(
        name=f"model_{target.lower()}_{segment}",
        title=f"Model {target} — {segment} (listing gain > {CUTS[target]:g}%)",
        load=load_mainboard if mb else load_sme,
        make_features=mb_features if mb else sme_features,
        features=MB_FEATURES if mb else SME_FEATURES,
        target=target,
        target_desc=f"1 if listing gain > {CUTS[target]:g}% else 0",
        realised_days=0,
        thresholds=THRESHOLDS[target],
        notes=MB_NOTES if mb else SME_NOTES,
    )


def predict_live(segment: str, features: dict) -> dict:
    """Raw inputs -> both L1 and L2 verdicts for the segment."""
    fx = mb_features if segment == "mainboard" else sme_features
    return {t: F.predict_live(f"model_{t.lower()}_{segment}", features, fx) for t in ("L1", "L2")}


def main():
    results = {}
    for segment in ("mainboard", "sme"):
        for target in ("L1", "L2"):
            r = F.run(spec(target, segment))
            results[(target, segment)] = r
            print(f"{r['spec'].name:22s} n={len(r['df'])} half-life={r['best']} "
                  f"mean AUC={r['per_best']['auc'].mean():.3f} years={r['years']} "
                  f"thresholds={r['final_thr']} -> {r['card'].name}")
    return results


if __name__ == "__main__":
    main()

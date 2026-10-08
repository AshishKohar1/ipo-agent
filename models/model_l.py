"""
models/model_l.py — Model L: `L_final_3pm`, P(listing gain), on models/framework.py.

**There is one Model L** (decision H1). `L_day1`, `L_day2` and the final-day forecaster are
cancelled, because no permitted source publishes day-wise subscription history — Chittorgarh
shows it live and deletes it at close (0 of 50 pre-2026 pages carried it), and every
aggregator that keeps it is blocked by robots.txt or terms. No day-wise code path exists in
this module or anywhere else in the repo; there is nothing dormant to fall back to.

Two fitted models per segment, never pooled (CLAUDE.md rule 6):

  model_l_v1.0_l1   listing gain >  0%   required hit rate 90%
  model_l_v1.0_l2   listing gain > 10%   required hit rate 80%
  model_l_v1.0_l1_sme / _l2_sme          SME shadow mode only

**Features: Set A, frozen** (A1, H2) — `log1p(Total subscription)` + `log(issue size)`.
Nine literature-sourced candidates were tested and all nine rejected; `stage16_model_l.py`
reproduces that test on the current dataset and records where it disagrees. Do not add a
feature here without a gate decision.

**Decision time.** The input is final-day subscription, which is knowable at ~3pm on the
closing day, before the 4:00 PM broker cutoff. Per C3 the model is trained on *final*
subscription, so it is **approximated, not measured**, at 3pm and overestimates the 3pm
position. It is rebuilt once ~40 IPOs of genuine 3pm snapshots accumulate (B4).

**Output discipline (G2).** `predict_live` returns the verdict and the threshold met. It
does **not** return the probability as a literal chance: isotonic overclaims in the top tail
(claims ~98.5%, delivers 94.0% on L1). The raw probability is available only under
`diagnostics`, for logging.

    python stage16_model_l.py           # fit, validate, freeze -> Gate B
    from models.model_l import predict_live
    predict_live(total=45.0, issue_size_cr=800.0, qib=80.0, rii=12.0)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import framework as F
import dataio

MODEL_ID = "model_l_v1.0"
DECISION_POINT = "L_final_3pm"
SET_A = ["log1p_total", "log_issue_size"]      # the standing challenger (A2-style), not the champion
# Decision H11: issue size is DROPPED. Its standardised coefficient is positive at every
# finite half-life and negative only unweighted -- it never stabilises, so its direction was
# set by the recency knob rather than by the data. log1p(Total) alone scores HIGHER on L1
# (0.8112 vs 0.8081), identically on L2, passes the C5 gates at every half-life including
# `none` where Set A fails L2's Wilson bound, and leaves no knob to tune.
FEATURES = ["log1p_total"]
HALF_LIFE = None                       # H11: no recency weighting; AUC is monotone in it
REQUIRED = {"L1": 0.90, "L2": 0.80}    # promised hit rates, not thresholds
CUTS = {"L1": 0.0, "L2": 10.0}


# ----------------------------------------------------------------------
# loaders (dataio only — CLAUDE.md data-loading contract)
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


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """The production feature, plus the challenger's. Only `FEATURES` reaches the model.

    `log_issue_size` is still computed so the Set A challenger can be fitted from the same
    frame in monthly retraining, and `retail_skew` so the demand-profile label can be
    derived -- neither is a model input (H11, H3).
    """
    out = pd.DataFrame(index=df.index)
    out["log1p_total"] = np.log1p(_num(df, "Total", "total"))
    size = _num(df, "Issue_Size(crores)", "Issue_Size", "issue_size_cr")
    out["log_issue_size"] = np.log(size.where(size > 0))
    return out


def retail_skew(df: pd.DataFrame) -> pd.Series:
    """H3: log1p(RII) - log1p(QIB). Displayed as a demand-profile label, never modelled."""
    return np.log1p(_num(df, "RII", "rii")) - np.log1p(_num(df, "QIB", "qib"))


# ----------------------------------------------------------------------
# H3 — demand profile: DISPLAY ONLY
# ----------------------------------------------------------------------
# Cut-points are fitted on training rows only (H3). They are stored in the model bundle so
# the live path never re-derives them from data that includes the row being scored.
PROFILE_LABELS = ("institution-led", "balanced", "balanced", "retail-skewed")


def fit_profile_cutpoints(train: pd.DataFrame) -> list[float]:
    s = retail_skew(train).dropna()
    return [float(x) for x in np.quantile(s, [0.25, 0.50, 0.75])]


def demand_profile(qib: float | None, rii: float | None,
                   cutpoints: list[float] | None) -> str:
    """`institution-led` | `balanced` | `retail-skewed`, or `unknown` when a leg is missing.

    Never influences a verdict — it is a label for the reader's own judgement (H3).
    """
    if qib is None or rii is None or cutpoints is None:
        return "unknown"
    if not np.isfinite(qib) or not np.isfinite(rii):
        return "unknown"
    v = float(np.log1p(rii) - np.log1p(qib))
    i = int(np.searchsorted(np.asarray(cutpoints, float), v, side="right"))
    return PROFILE_LABELS[min(i, 3)]


# ----------------------------------------------------------------------
# specs
# ----------------------------------------------------------------------
NOTES = [
    "**One model only (H1).** `L_day1`, `L_day2` and the final-day forecaster are cancelled: "
    "no permitted source publishes day-wise subscription history. Their code paths do not "
    "exist — there is nothing dormant to fall back to.",
    "**Trained on 5pm final subscription, fed 3pm figures live — so it UNDERSTATES, and "
    "that makes it conservative (C3).** No historical 3pm snapshot exists, so the model is "
    "fitted on final-day subscription and then scored on the position at ~15:00. "
    "Institutional bids concentrate in the final hours (observed: Adroit Industries QIB "
    "1.82x on day 2 against 195x at close), so a 3pm figure is systematically LOWER than "
    "the figure the model was trained on. The probability it returns is therefore too low, "
    "not too high: **the model will miss good IPOs rather than recommend bad ones.** A "
    "near-threshold `no` should be read as uncertain, not as a negative verdict. "
    "**The size of this bias is unmeasured** until the 15:00/19:30 paired capture "
    "accumulates data (`data/subscription_snapshots.csv`); it cannot be estimated from any "
    "existing source.",
    "**Feature set is `log1p(Total)` alone (H11), superseding Set A.** Issue size was "
    "dropped: its coefficient is positive at every finite half-life and negative only "
    "unweighted, so its direction came from the recency knob rather than the data. Dropping "
    "it RAISED L1 pooled AUC (0.8112 vs 0.8081), left L2 unchanged (0.8808 vs 0.8809), and "
    "fixed the one configuration where Set A failed L2's Wilson gate. Set A is retained as a "
    "standing challenger on the A2 champion/challenger rule, never promoted by hand.",
    "**The evidence for several rejected candidates is WEAKER than PLAN.md states.** "
    "Re-tested on the current dataset: the log transform improves pooled AUC by "
    "**0.07pp, not the 1.2pp** recorded in Amendment 02, so it is justified on "
    "distributional grounds and not by AUC; and `plus_hni` is **marginally better** "
    "(+0.26pp L1, +0.15pp L2), not worse as recorded. Market heat helps L1 (+0.53pp) and "
    "hurts L2 (-0.54pp), so the Set C challenger should be tracked per target. The feature "
    "choice still stands — every gap is under 0.6pp, inside this dataset's noise band — but "
    "the published figures should not be quoted as measured here.",
    "**`retail_skew` is displayed, never modelled (H3).** Adding it moves pooled AUC by less "
    "than the noise band and it is already embedded in Total.",
    "**Isotonic calibration (G1), and it overclaims (G2).** Among rows it places above the "
    "requirement it claims a mean 98.5% and delivers 94.0% (L1), and claims 99.2% and "
    "delivers 87.5% (L2). Reports must print the verdict and the threshold met, never the "
    "probability as a literal chance.",
    "**No recency weighting (H11).** Pooled AUC rises monotonically as the half-life "
    "lengthens (L1 0.8051 at 2y to 0.8112 unweighted), so `none` is both the best setting "
    "and the end of the sequence. Every training row counts equally and there is no knob a "
    "reader could question. Effective sample size equals the row count.",
    "`class_weight='balanced'` pushes probabilities towards 0.5; thresholds are validated on "
    "out-of-fold hit rates, not read off the probability scale.",
    "Survivorship does not affect Model L: the target is realised on listing day for every IPO.",
    "`Listing Gain` comes from the master dataset; whether it is the listing open or close is "
    "not documented in the source. The SME shadow model uses listing-day CLOSE — the two are "
    "not comparable.",
]
SME_NOTES = NOTES + [
    "**Thin history.** Two calendar years only (2025-26), so walk-forward tests ONE year and "
    "the AUC has no year-to-year spread to judge stability by. SME runs in SHADOW MODE: it is "
    "logged to `sme_shadow_log.csv` and must not drive a bid.",
    "**Recency weighting is nearly meaningless here** — every training row is 1-2 years old, "
    "so the selected half-life mostly reflects noise.",
    "IPOMatrix (tracker) and Chittorgarh share a parent, so the SME target and features are "
    "single-source and not reconciled (rule 2).",
]


def spec(target: str, segment: str = "mainboard") -> F.ModelSpec:
    mb = segment == "mainboard"
    return F.ModelSpec(
        name=f"{MODEL_ID}_{target.lower()}" + ("" if mb else "_sme"),
        title=f"{DECISION_POINT} {target} — {segment} (listing gain > {CUTS[target]:g}%)",
        load=load_mainboard if mb else load_sme,
        make_features=make_features, features=FEATURES, target=target,
        target_desc=f"1 if listing gain > {CUTS[target]:g}% else 0",
        realised_days=0, required_hit_rate={target: REQUIRED[target]},
        notes=NOTES if mb else SME_NOTES,
    )


# ----------------------------------------------------------------------
# live scoring
# ----------------------------------------------------------------------
def _score_one(name: str, total: float, issue_size_cr: float) -> dict:
    import joblib
    b = joblib.load(F.MODELS_DIR / f"{name}.joblib")
    X = make_features(pd.DataFrame([{"Total": total, "Issue_Size": issue_size_cr}]))[b["features"]]
    if X.isna().any(axis=None):
        missing = ", ".join(X.columns[X.isna().iloc[0]])
        return {"model": name, "verdict": f"NO CALL — missing input: {missing}"}
    p = float(b["pipeline"].predict_proba(X.to_numpy())[0, 1])
    cal = b.get("calibrator_object")
    p_cal = float(cal.predict(np.array([p]))[0]) if cal is not None else None
    req = b.get("required_hit_rate")
    fired = p_cal is not None and req is not None and p_cal >= req
    return {"model": name, "bundle": b.get("model_id", name),
            "verdict": "BID" if fired else "no",
            # G2: the THRESHOLD MET, never the probability as a literal chance.
            "threshold_met": (f"validated hit rate >= {req:.0%}" if fired else
                              f"below the {req:.0%} threshold" if req else "no threshold"),
            "half_life": b.get("half_life"),
            "diagnostics": {"raw_p": round(p, 4),
                            "calibrated_p": None if p_cal is None else round(p_cal, 4),
                            "raw_equivalent_threshold": b.get("raw_equivalent_threshold"),
                            "note": "for predictions_log.csv only — never shown as a chance (G2)"}}


def predict_live(total: float, issue_size_cr: float, qib: float | None = None,
                 rii: float | None = None, segment: str = "mainboard") -> dict:
    """Final-day subscription + issue size -> L1 and L2 verdicts, plus the demand profile.

    Per G2 the return carries the verdict and the threshold met. The probability is under
    `diagnostics` for logging and must not be presented to the user as a chance.
    """
    import joblib
    sfx = "" if segment == "mainboard" else "_sme"
    out = {"model_id": MODEL_ID, "decision_point": DECISION_POINT, "segment": segment,
           "inputs": {"total": total, "issue_size_cr": issue_size_cr, "qib": qib, "rii": rii}}
    cuts = None
    for t in ("L1", "L2"):
        name = f"{MODEL_ID}_{t.lower()}{sfx}"
        out[t] = _score_one(name, total, issue_size_cr)
        if cuts is None:
            try:
                cuts = joblib.load(F.MODELS_DIR / f"{name}.joblib").get("profile_cutpoints")
            except Exception:
                cuts = None
    out["demand_profile"] = demand_profile(qib, rii, cuts)
    out["demand_profile_note"] = "display only — not a model input and never a verdict (H3)"
    if segment != "mainboard":
        out["shadow_mode"] = "SME runs in shadow mode; logged, never a bid decision"
    return out


def format_live_line(name: str, r: dict, closing: str = "closing today") -> str:
    """The live-report block fixed by decision D2, with G2's output discipline."""
    L = [f"{name} — {closing}, bid by 4:00 PM",
         f"  {DECISION_POINT}  L1: {r['L1']['verdict']:<4s} ({r['L1']['threshold_met']})",
         f"  {' ' * len(DECISION_POINT)}  L2: {r['L2']['verdict']:<4s} ({r['L2']['threshold_met']})",
         f"  Subscription: Total {r['inputs']['total']}x | QIB {r['inputs']['qib']}x | "
         f"Retail {r['inputs']['rii']}x   [15:00]",
         f"  Demand profile: {r['demand_profile']}   [NOT IN MODEL — context only]",
         "  Veto flags: (requires RHP data)",
         "  GMP: ____%   [NOT IN MODEL — your judgement only]"]
    return "\n".join(L)


if __name__ == "__main__":
    print(__doc__)
    print("Fitting is done by stage16_model_l.py, which also re-tests H2's nine candidates.")

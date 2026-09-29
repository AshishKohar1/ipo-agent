"""
models/framework.py — shared model framework for every model in this project.

A model is a ModelSpec: how to load its rows (via dataio only), how to turn raw inputs
into features, which binary target to fit, and how long the target takes to be realised.
The framework does everything else identically for every model:

  * drops rows with an exclude_reason (fpo, reit_invit, idr, bad_listing_date, ...)
  * recency weighting   w = 0.5 ** (age_years / half_life), age = listing date -> today,
                        reported with effective n = (Σw)² / Σw²
  * walk-forward validation: for each test year T (the last N years with enough data),
                        train on rows listed before T whose target was REALISED before
                        Jan 1 of T (target-window embargo), test on rows listed in T.
                        Out-of-fold probabilities only. Weights apply to training rows
                        only; test rows are scored unweighted.
  * half-life selection over {2, 3, 5, 8, none} by mean walk-forward AUC
  * outputs: AUC per test year + mean, calibration by probability decile (winner vs
             unweighted), threshold table, standardised coefficients, HC-robust Logit
             summary, final fit + joblib bundle, predict_live(), model card.

Weights are normalised to mean 1 within each training set. Without that, the absolute
scale of the weights (which depends on "today") would silently change the strength of
the L2 penalty; relative weights between rows are unaffected.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import numpy as np
import pandas as pd
import joblib

# scikit-learn is NOT used: this machine's Windows Application Control policy blocks its
# compiled DLLs (_cd_fast). The estimator below reproduces sklearn's
# LogisticRegression(penalty='l2', C, class_weight='balanced') objective exactly —
#   minimise  C * Σ_i s_i * c_{y_i} * logloss_i  +  ½ ||β||²   (intercept unpenalised)
#   c_k = n / (2 * n_k)   from UNWEIGHTED class counts, as sklearn does —
# solved by Newton's method, on standardised features.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODELS_DIR = Path(__file__).resolve().parent
HALF_LIVES: tuple = (2, 3, 5, 8, None)          # None = no weighting
THRESHOLD_GRID = tuple(np.round(np.arange(0.50, 0.96, 0.05), 2))


@dataclass
class ModelSpec:
    name: str                                    # file stem: models/<name>.joblib, <name>_CARD.md
    title: str
    load: Callable[[], pd.DataFrame]             # raw rows; must include 'listing_date'
    make_features: Callable[[pd.DataFrame], pd.DataFrame]   # raw -> feature columns
    features: list[str]
    target: str                                  # binary 0/1 column produced by load()
    target_desc: str
    realised_days: int = 0                       # 0 for L (listing day); 365 / 1095 for H
    required_hit_rate: dict = field(default_factory=dict)  # {label: promised hit rate},
    # e.g. {'L1': 0.90}. The THRESHOLD is derived from it by threshold_section5().
    n_test_years: int = 5
    min_test_n: int = 20                         # test year needs this many rows ...
    min_test_class: int = 3                      # ... and this many of each class
    min_train_n: int = 50
    C: float = 1.0                               # L2 strength (sklearn default)
    notes: list[str] = field(default_factory=list)   # known limitations for the card


# ----------------------------------------------------------------------
# data
# ----------------------------------------------------------------------
def prepare(spec: ModelSpec, asof: pd.Timestamp | None = None) -> pd.DataFrame:
    """Load, drop excluded rows, build features, keep rows whose target is realised."""
    asof = asof or pd.Timestamp.today().normalize()
    raw = spec.load()
    n0 = len(raw)
    if "exclude_reason" in raw:
        raw = raw[raw["exclude_reason"].isna()]
    df = spec.make_features(raw.copy())
    df["listing_date"] = pd.to_datetime(raw["listing_date"])
    df[spec.target] = raw[spec.target]
    df = df.dropna(subset=spec.features + [spec.target, "listing_date"])
    df = df[df["listing_date"] + pd.Timedelta(days=spec.realised_days) <= asof]
    df[spec.target] = df[spec.target].astype(int)
    df.attrs["n_loaded"], df.attrs["n_excluded"] = n0, n0 - len(raw)
    return df.sort_values("listing_date").reset_index(drop=True)


def recency_weights(dates: pd.Series, half_life, asof=None) -> np.ndarray:
    if half_life is None:
        return np.ones(len(dates))
    asof = asof or pd.Timestamp.today().normalize()
    age = (asof - pd.to_datetime(dates)).dt.days.to_numpy() / 365.25
    return 0.5 ** (age / half_life)


def effective_n(w) -> float:
    w = np.asarray(w, float)
    return float(w.sum() ** 2 / (w ** 2).sum())


class BalancedLogit:
    """Standardise -> L2 logistic regression with balanced class weights."""

    def __init__(self, C: float = 1.0, balanced: bool = True):
        self.C, self.balanced = C, balanced

    def fit(self, X, y, sample_weight=None, tol=1e-10, max_iter=100):
        X = np.asarray(X, float); y = np.asarray(y, float)
        n, k = X.shape
        self.mean_ = X.mean(0); self.scale_ = X.std(0); self.scale_[self.scale_ == 0] = 1
        Z = np.column_stack([np.ones(n), (X - self.mean_) / self.scale_])
        s = np.ones(n) if sample_weight is None else np.asarray(sample_weight, float)
        if self.balanced:
            n1 = y.sum(); n0 = n - n1
            s = s * np.where(y == 1, n / (2 * n1), n / (2 * n0))
        a = self.C * s
        pen = np.eye(k + 1); pen[0, 0] = 0                # intercept unpenalised
        b = np.zeros(k + 1)
        for _ in range(max_iter):
            p = 1 / (1 + np.exp(-Z @ b))
            g = Z.T @ (a * (p - y)) + pen @ b
            H = (Z * (a * p * (1 - p))[:, None]).T @ Z + pen
            step = np.linalg.solve(H, g)
            b -= step
            if np.abs(step).max() < tol:
                break
        self.intercept_, self.coef_ = b[0], b[1:]           # coef_ on standardised scale
        return self

    def predict_proba(self, X):
        Z = (np.asarray(X, float) - self.mean_) / self.scale_
        p = 1 / (1 + np.exp(-(self.intercept_ + Z @ self.coef_)))
        return np.column_stack([1 - p, p])


def roc_auc_score(y, p) -> float:
    """Mann-Whitney AUC with average ranks for ties (same as sklearn's)."""
    y = np.asarray(y); r = pd.Series(np.asarray(p, float)).rank(method="average").to_numpy()
    n1 = (y == 1).sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _fit(X, y, w, C):
    return BalancedLogit(C=C).fit(X, y, sample_weight=w / w.mean())


# ----------------------------------------------------------------------
# walk-forward
# ----------------------------------------------------------------------
def test_years(df: pd.DataFrame, spec: ModelSpec) -> list[int]:
    """Most recent spec.n_test_years years with enough test rows, both classes, and
    enough embargo-eligible training rows."""
    ok = []
    for T in sorted(df["listing_date"].dt.year.unique(), reverse=True):
        te = df[df["listing_date"].dt.year == T]
        tr = _train_rows(df, spec, T)
        if (len(te) >= spec.min_test_n and te[spec.target].sum() >= spec.min_test_class
                and (len(te) - te[spec.target].sum()) >= spec.min_test_class
                and len(tr) >= spec.min_train_n and tr[spec.target].nunique() == 2):
            ok.append(int(T))
        if len(ok) == spec.n_test_years:
            break
    return sorted(ok)


def _train_rows(df, spec, T):
    start = pd.Timestamp(year=T, month=1, day=1)
    realised = df["listing_date"] + pd.Timedelta(days=spec.realised_days)
    return df[(df["listing_date"] < start) & (realised < start)]      # embargo


def walk_forward(df: pd.DataFrame, spec: ModelSpec, half_life, years=None):
    """Returns (oof DataFrame[listing_date, year, y, p], per-year DataFrame)."""
    years = years or test_years(df, spec)
    oof, per = [], []
    for T in years:
        tr = _train_rows(df, spec, T)
        te = df[df["listing_date"].dt.year == T]
        w = recency_weights(tr["listing_date"], half_life)
        m = _fit(tr[spec.features].to_numpy(), tr[spec.target].to_numpy(), w, spec.C)
        p = m.predict_proba(te[spec.features].to_numpy())[:, 1]        # unweighted scoring
        oof.append(pd.DataFrame({"listing_date": te["listing_date"].to_numpy(), "year": T,
                                 "y": te[spec.target].to_numpy(), "p": p}))
        per.append({"test_year": T, "n_train": len(tr), "eff_n_train": effective_n(w),
                    "n_test": len(te), "test_pos_rate": te[spec.target].mean(),
                    "auc": roc_auc_score(te[spec.target], p)})
    return pd.concat(oof, ignore_index=True), pd.DataFrame(per)


def select_half_life(df, spec, select_by: str = "pooled_oof_auc"):
    """Half-life chosen by POOLED out-of-fold AUC (PLAN.md section 5): concatenate every
    fold's out-of-fold predictions and score once. The mean of per-year AUCs is also
    reported, but must not drive the choice — it lets a 20-row test year count as much as
    a 100-row one."""
    years = test_years(df, spec)
    rows, runs = [], {}
    for hl in HALF_LIVES:
        oof, per = walk_forward(df, spec, hl, years)
        runs[hl] = (oof, per)
        pooled = roc_auc_score(oof["y"], oof["p"])
        rows.append({"half_life": "none" if hl is None else hl,
                     "pooled_oof_auc": pooled, "pooled_gini": 2 * pooled - 1,
                     "mean_auc": per["auc"].mean(),
                     **{f"auc_{int(r.test_year)}": r.auc for r in per.itertuples()}})
    tab = pd.DataFrame(rows)
    best = HALF_LIVES[int(tab[select_by].to_numpy().argmax())]
    return best, tab, runs, years


# ----------------------------------------------------------------------
# reporting tables
# ----------------------------------------------------------------------
def calibration(oof: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    edges = np.linspace(0, 1, bins + 1)
    b = pd.cut(oof["p"], edges, include_lowest=True)
    t = oof.groupby(b, observed=False).agg(n=("y", "size"), mean_pred=("p", "mean"),
                                           actual=("y", "mean")).reset_index()
    t["gap"] = t["actual"] - t["mean_pred"]
    t["p_bin"] = t["p"].astype(str)
    return t[["p_bin", "n", "mean_pred", "actual", "gap"]]


def wilson_lower(k, n, z=1.96):
    if n == 0:
        return np.nan
    ph = k / n
    return (ph + z*z/(2*n) - z*np.sqrt(ph*(1-ph)/n + z*z/(4*n*n))) / (1 + z*z/n)


def threshold_table(oof: pd.DataFrame, grid=THRESHOLD_GRID) -> pd.DataFrame:
    rows = []
    for t in grid:
        f = oof[oof["p"] >= t]
        k = int(f["y"].sum()); n = len(f)
        rows.append({"threshold": t, "n_fire": n, "fire_pct": n / len(oof) * 100,
                     "hits": k, "hit_rate": k / n if n else np.nan,
                     "hit_rate_lo95": wilson_lower(k, n)})
    return pd.DataFrame(rows)


def vif(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Variance inflation factor per feature, by OLS of each feature on the others
    (numpy lstsq — no statsmodels dependency). VIF > 5 means the coefficient on that
    feature is not separately interpretable."""
    X = df[features].astype(float)
    rows = []
    for c in features:
        other = X.drop(columns=c)
        A = np.column_stack([np.ones(len(other)), other.to_numpy()])
        beta, *_ = np.linalg.lstsq(A, X[c].to_numpy(), rcond=None)
        resid = X[c].to_numpy() - A @ beta
        ss_tot = ((X[c] - X[c].mean()) ** 2).sum()
        r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else 0.0
        rows.append({"feature": c, "vif": np.inf if r2 >= 1 else 1 / (1 - r2)})
    return pd.DataFrame(rows)


def threshold_section5(oof: pd.DataFrame, required: float, min_fire: int = 20,
                       slack: float = 0.05, grid=None) -> dict:
    """PLAN.md section 5 threshold rule, applied to out-of-fold predictions.

    The chosen threshold is the LOWEST probability t (so it fires as often as possible)
    that satisfies all three:
      1. out-of-sample hit rate among rows with p >= t  >=  `required`
      2. Wilson 95% lower bound of that hit rate        >=  `required - slack`
      3. number of firing rows                          >=  `min_fire`

    `required` is the promised hit rate (0.90 for L1, 0.80 for L2) — NOT the threshold.
    Returns the chosen threshold and the evidence, or chosen=None if nothing qualifies.
    """
    grid = np.round(np.arange(0.05, 1.00, 0.01), 2) if grid is None else grid
    rows = []
    for t in grid:
        f = oof[oof["p"] >= t]
        n = len(f); k = int(f["y"].sum())
        hr = k / n if n else np.nan
        lo = wilson_lower(k, n) if n else np.nan
        rows.append({"threshold": float(t), "n_fire": n, "fire_pct": n / len(oof) * 100,
                     "hits": k, "hit_rate": hr, "hit_rate_lo95": lo,
                     "meets_hit_rate": bool(n and hr >= required),
                     "meets_wilson": bool(n and lo >= required - slack),
                     "meets_min_fire": n >= min_fire})
    tab = pd.DataFrame(rows)
    ok = tab[tab["meets_hit_rate"] & tab["meets_wilson"] & tab["meets_min_fire"]]
    chosen = float(ok["threshold"].min()) if len(ok) else None
    row = ok.loc[ok["threshold"].idxmin()].to_dict() if len(ok) else None
    # why it failed, for the report: the binding constraint at the best near-miss
    near = None
    if chosen is None:
        cand = tab[tab["meets_min_fire"]]
        if len(cand):
            near = cand.loc[cand["hit_rate"].idxmax()].to_dict()
    return {"required": required, "min_fire": min_fire, "slack": slack,
            "chosen": chosen, "at_chosen": row, "best_near_miss": near, "table": tab}


def verify_thresholds(thr: pd.DataFrame, claims: dict, min_fire: int = 10) -> list[dict]:
    """claims = {label: t}. The stated promise of 'fire at >= t' is an out-of-fold hit
    rate of at least t. A claim passes if, at threshold t, the hit rate is >= t on at
    least min_fire fires. If it fails, report the LOWEST threshold (most fires) whose
    hit rate delivers the stated rate t on >= min_fire fires — or None if nothing does.
    A failing threshold is never kept."""
    out = []
    for label, t in claims.items():
        r = thr.loc[np.isclose(thr["threshold"], t)].iloc[0]
        ok = bool(r["n_fire"] >= min_fire and r["hit_rate"] >= t)
        deliver = thr[(thr["n_fire"] >= min_fire) & (thr["hit_rate"] >= t)]
        out.append({"label": label, "claimed": t, "n_fire": int(r["n_fire"]),
                    "hit_rate": r["hit_rate"], "hit_rate_lo95": r["hit_rate_lo95"],
                    "passes": ok,
                    "lowest_passing": None if deliver.empty else float(deliver["threshold"].min())})
    return out


def hc_logit(df, spec):
    """Unweighted Logit on standardised features with robust (sandwich) SEs.
    Imported from statsmodels.discrete directly: statsmodels.api pulls in a tsa DLL
    that this machine's Application Control policy blocks."""
    from statsmodels.discrete.discrete_model import Logit
    from statsmodels.tools.tools import add_constant
    X = df[spec.features]
    Xs = (X - X.mean()) / X.std(ddof=0)
    return Logit(df[spec.target].to_numpy(), add_constant(Xs)).fit(disp=0, cov_type="HC3")


# ----------------------------------------------------------------------
# final fit, persistence, live prediction
# ----------------------------------------------------------------------
def fit_final(df, spec, half_life):
    w = recency_weights(df["listing_date"], half_life)
    pipe = _fit(df[spec.features].to_numpy(), df[spec.target].to_numpy(), w, spec.C)
    coefs = pd.Series(pipe.coef_, index=spec.features, name="std_coef")
    return pipe, coefs, w


def save_bundle(spec, pipe, half_life, thresholds_final, extra=None):
    bundle = {"name": spec.name, "features": spec.features, "pipeline": pipe,
              "half_life": half_life, "thresholds": thresholds_final,
              "target": spec.target, "target_desc": spec.target_desc,
              "trained_at": str(pd.Timestamp.now()), **(extra or {})}
    path = MODELS_DIR / f"{spec.name}.joblib"
    joblib.dump(bundle, path)
    return path


def predict_live(name: str, features_dict: dict, make_features: Callable) -> dict:
    """features_dict holds RAW inputs (e.g. Total=12.5, QIB=30, ...). The model's own
    make_features() transforms them exactly as in training."""
    b = joblib.load(MODELS_DIR / f"{name}.joblib")
    X = make_features(pd.DataFrame([features_dict]))[b["features"]]
    if X.isna().any(axis=None):
        return {"model": name, "probability": None,
                "verdict": "NO CALL — missing input: " + ", ".join(X.columns[X.isna().iloc[0]])}
    p = float(b["pipeline"].predict_proba(X.to_numpy())[0, 1])
    fired = [lab for lab, t in b["thresholds"].items() if t is not None and p >= t]
    verdict = ("FIRE: " + ", ".join(fired)) if fired else "NO FIRE"
    return {"model": name, "probability": round(p, 4), "verdict": verdict,
            "thresholds": b["thresholds"]}


# ----------------------------------------------------------------------
# orchestration + model card
# ----------------------------------------------------------------------
def _md(df: pd.DataFrame, fmt="{:.3f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else fmt.format(v))
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "---|" * len(d.columns)
    return "\n".join([head, sep] + ["| " + " | ".join(map(str, r)) + " |" for r in d.values])


def run(spec: ModelSpec, write_card: bool = True) -> dict:
    df = prepare(spec)
    best, hl_tab, runs, years = select_half_life(df, spec)
    oof_best, per_best = runs[best]
    oof_base, per_base = runs[None]
    cal_best, cal_base = calibration(oof_best), calibration(oof_base)
    thr = threshold_table(oof_best)
    # PLAN.md section 5: lowest threshold meeting the promised hit rate, a Wilson 95%
    # lower bound within 5pp of it, and >= 20 fires. Derived, never assumed.
    s5 = {lab: threshold_section5(oof_best, req)
          for lab, req in (spec.required_hit_rate or {}).items()}
    pipe, coefs, w = fit_final(df, spec, best)
    try:
        hc = hc_logit(df, spec); hc_txt = hc.summary().as_text()
    except Exception as e:                       # never let a stats nicety kill the run
        hc, hc_txt = None, f"HC Logit failed: {e}"
    final_thr = {lab: r["chosen"] for lab, r in s5.items()}
    pooled = roc_auc_score(oof_best["y"], oof_best["p"])
    path = save_bundle(spec, pipe, best, final_thr,
                       {"validation_pooled_auc": float(pooled),
                        "validation_mean_auc": float(per_best["auc"].mean()),
                        "required_hit_rate": dict(spec.required_hit_rate or {})})
    res = dict(spec=spec, df=df, best=best, hl_tab=hl_tab, years=years, per_best=per_best,
               per_base=per_base, oof=oof_best, cal_best=cal_best, cal_base=cal_base,
               thr=thr, s5=s5, coefs=coefs, w=w, hc=hc, hc_txt=hc_txt,
               final_thr=final_thr, bundle=path,
               vif=vif(df, spec.features), pooled_auc=pooled)
    if write_card:
        res["card"] = write_model_card(res)
    return res


def write_model_card(r: dict) -> Path:
    s, df = r["spec"], r["df"]
    hl = "none (unweighted)" if r["best"] is None else f"{r['best']} years"
    pos = df[s.target].mean()
    cal = r["cal_best"].merge(r["cal_base"], on="p_bin", suffixes=("_winner", "_unweighted"))
    cal = cal[(cal["n_winner"] > 0) | (cal["n_unweighted"] > 0)]
    lines = [
        f"# {s.title} — model card", "",
        f"_Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} by `models/framework.py`. Bundle: `models/{s.name}.joblib`._", "",
        "## Target", f"`{s.target}`: {s.target_desc}. Realised {s.realised_days} days after listing.", "",
        "## Training data",
        f"- Rows loaded {df.attrs.get('n_loaded')} → excluded by `exclude_reason` {df.attrs.get('n_excluded')} "
        f"→ usable (features + target present, target realised) **{len(df)}**",
        f"- Period: {df['listing_date'].min():%Y-%m-%d} to {df['listing_date'].max():%Y-%m-%d}",
        f"- Positive rate: {pos*100:.1f}%",
        f"- Final fit: n = {len(df)}, effective n = {effective_n(r['w']):.1f} (half-life {hl})", "",
        "## Features", "", _md(pd.DataFrame({"feature": s.features,
                                              "std_coef (final fit)": r["coefs"].to_numpy()})), "",
        "## Recency half-life selection (walk-forward, mean AUC)", "",
        _md(r["hl_tab"]), "", f"**Chosen: {hl}.**", "",
        "## Walk-forward validation (chosen half-life)",
        f"Test years {r['years']}. Train on rows listed before Jan 1 of the test year whose target "
        f"was realised before it (embargo {s.realised_days}d). Out-of-fold probabilities; weights on "
        "training rows only.", "",
        _md(r["per_best"]), "",
        f"**Mean AUC {r['per_best']['auc'].mean():.3f}** (unweighted baseline {r['per_base']['auc'].mean():.3f}). "
        f"Pooled out-of-fold AUC {roc_auc_score(r['oof']['y'], r['oof']['p']):.3f}.", "",
        "## Calibration by probability decile: winner vs unweighted", "",
        "`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled "
        "towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from "
        "the table below, not from the raw probability.", "",
        _md(cal), "",
        "## Threshold table (out-of-fold, chosen half-life)", "", _md(r["thr"]), "",
    ]
    if r["s5"]:
        lines += ["## Threshold derivation (PLAN.md section 5)",
                  "The threshold is the **lowest** probability whose out-of-fold hit rate meets the "
                  "promised rate, whose Wilson 95% lower bound is within 5pp of it, and which fires "
                  "on at least 20 IPOs. If nothing qualifies, no threshold is published.", ""]
        for lab, s in r["s5"].items():
            if s["chosen"] is None:
                nm = s["best_near_miss"]
                lines.append(f"- **{lab} (needs {s['required']:.0%})**: no threshold qualifies. "
                             + ("no threshold fires on 20+ IPOs" if nm is None else
                                f"best with 20+ fires: hit rate {nm['hit_rate']*100:.1f}% "
                                f"(lower bound {nm['hit_rate_lo95']*100:.1f}%) at t={nm['threshold']:.2f}"))
            else:
                at = s["at_chosen"]
                lines.append(f"- **{lab} (needs {s['required']:.0%})**: threshold **{s['chosen']:.2f}** "
                             f"-> fires {at['n_fire']} ({at['fire_pct']:.1f}%), hit rate "
                             f"{at['hit_rate']*100:.1f}%, Wilson lower bound {at['hit_rate_lo95']*100:.1f}%")
        lines += ["", f"Thresholds saved in the bundle: `{r['final_thr']}`", ""]
    lines += ["## Collinearity (VIF)", "", _md(r["vif"]), ""]
    lines += ["## Coefficient significance (unweighted Logit, standardised features, robust SEs)",
              "statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic "
              "robust sandwich, not the HC3 leverage correction.", "", "```", r["hc_txt"], "```", "",
              "## Known limitations"] + [f"- {n}" for n in s.notes] + [""]
    p = MODELS_DIR / f"{s.name}_CARD.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p

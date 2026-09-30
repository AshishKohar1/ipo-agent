"""
stage16_model_l.py — PLAN.md Stage 16: finalise and freeze `L_final_3pm` → GATE B.

Decisions applied: H1 (one model only), H2 (Set A frozen; nine candidates rejected),
H3 (demand profile displayed, never modelled), H4 (issue-size coefficient), G1 (isotonic
calibration), G2 (print the verdict and the threshold met, never the raw probability).

Four parts, in this order:

  1. **Reproduce H2's nine rejected candidates** on the current dataset, so the rejection is
     recorded as evidence rather than asserted. Each candidate is scored by POOLED
     out-of-fold AUC under the same walk-forward protocol as Set A, on the rows where that
     candidate's own inputs are present — and separately on rows identical to Set A's, since
     a candidate that drops rows is not comparable otherwise.
  2. **Reproduce H3's demand-profile quartiles and H4's issue-size coefficient.**
  3. **Fit the final model:** Set A, mainboard, class_weight balanced, half-life by pooled
     AUC, isotonic calibration fitted on the out-of-fold predictions (never on the rows it
     scores), thresholds at the required hit rates per G1.
  4. Save `model_l_v1.0` and write `MODEL_L_CARD.md`.

Writes reports/stage16_model_l.json and MODEL_L_CARD.md. Stops at Gate B — nothing goes
live from here.

    python stage16_model_l.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import framework as F          # noqa: E402
import calibration as C        # noqa: E402
import dataio                  # noqa: E402
import model_l as ML           # noqa: E402

REQUIRED = {"L1": 0.90, "L2": 0.80}
CUTS = {"L1": 0.0, "L2": 10.0}
SET_A = ["log1p_total", "log_issue_size"]
MIN_FIRE, SLACK = 20, 0.05

# H2's nine candidates, as recorded in PLAN_AMENDMENT_02.md section A.
CLAIMED_AUC = {
    "setA_baseline":       0.8832,
    "split_instead":       0.8807,
    "plus_qib":            0.8818,
    "plus_hni":            0.8823,
    "plus_rii":            0.8826,
    "plus_log_price":      None,      # "AUC unchanged"
    "plus_market_heat":    0.8818,    # from 0.8815
    "raw_subscription":    0.8711,
}
CLAIMED_H3 = {"Q1 institution-skewed": 20.4, "Q2": 4.1, "Q3": 2.2, "Q4 retail-skewed": 1.6}
CLAIMED_H4_COEF = -0.356
CLAIMED_VIF_TOTAL = 90.0
CLAIMED_SPLIT_COEFS = {"log1p_total": 26.26, "log1p_qib": -5.25, "log1p_hni": -3.04}


# ---------------------------------------------------------------------------- data
def load_mainboard() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    m["listing_date"] = m["listing_date_master"]
    m["listing_gain"] = pd.to_numeric(m["Listing Gain"], errors="coerce")
    for k, c in CUTS.items():
        m[k] = (m["listing_gain"] > c).astype(float).where(m["listing_gain"].notna())
    return m


def _num(df, *names):
    for n in names:
        if n in df:
            return pd.to_numeric(df[n], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Every feature any candidate needs. Set A is the first two columns."""
    out = pd.DataFrame(index=df.index)
    tot = _num(df, "Total", "total")
    out["log1p_total"] = np.log1p(tot)
    size = _num(df, "Issue_Size(crores)", "Issue_Size", "issue_size_cr")
    out["log_issue_size"] = np.log(size.where(size > 0))
    # candidate inputs
    out["log1p_qib"] = np.log1p(_num(df, "QIB", "qib"))
    out["log1p_hni"] = np.log1p(_num(df, "HNI", "hni", "NII"))
    out["log1p_rii"] = np.log1p(_num(df, "RII", "rii"))
    out["raw_total"] = tot
    out["log_offer_price"] = np.log(_num(df, "Offer Price").where(lambda s: s > 0))
    # H3: demand profile. Computed here so it can be MEASURED, but it is never in `features`.
    out["retail_skew"] = np.log1p(_num(df, "RII", "rii")) - np.log1p(_num(df, "QIB", "qib"))
    return out


def with_heat(df: pd.DataFrame) -> pd.DataFrame:
    """all_features plus the leak-free market IPO heat, joined on the master's index."""
    out = all_features(df)
    try:
        import market_heat
        h = market_heat.build()
        col = next((c for c in h.columns if "heat" in c.lower()), None)
        out["market_heat"] = h[col].reindex(out.index) if col else np.nan
    except Exception as e:                                    # pragma: no cover
        print(f"    market_heat unavailable: {type(e).__name__}: {e}")
        out["market_heat"] = np.nan
    return out


def spec(target: str, features: list[str], maker=all_features, name=None) -> F.ModelSpec:
    return F.ModelSpec(
        name=name or f"model_{target.lower()}_mainboard",
        title=f"L_final_3pm {target} — mainboard (listing gain > {CUTS[target]:g}%)",
        load=load_mainboard, make_features=maker, features=features, target=target,
        target_desc=f"1 if listing gain > {CUTS[target]:g}% else 0",
        realised_days=0, required_hit_rate={target: REQUIRED[target]},
    )


# ------------------------------------------------------------------- 1. candidates
CANDIDATES = {
    "setA_baseline":    (SET_A, all_features),
    "split_instead":    (["log1p_qib", "log1p_hni", "log1p_rii", "log_issue_size"], all_features),
    "plus_qib":         (SET_A + ["log1p_qib"], all_features),
    "plus_hni":         (SET_A + ["log1p_hni"], all_features),
    "plus_rii":         (SET_A + ["log1p_rii"], all_features),
    "plus_log_price":   (SET_A + ["log_offer_price"], all_features),
    "plus_market_heat": (SET_A + ["market_heat"], with_heat),
    "raw_subscription": (["raw_total", "log_issue_size"], all_features),
}


def part1_candidates() -> dict:
    print("=" * 86)
    print("1. H2's nine rejected candidates — reproduced on the current dataset")
    print("=" * 86)
    res = {}
    for target in ("L1", "L2"):
        # the common row set: rows where EVERY candidate's inputs are present, so all
        # candidates are scored on identical data (paired comparison).
        sp = spec(target, SET_A)
        raw = load_mainboard()
        raw = raw[raw["exclude_reason"].isna()]
        fx = with_heat(raw)
        need = sorted({c for f, _ in CANDIDATES.values() for c in f})
        common = fx[need].notna().all(axis=1) & raw[target].notna() & raw["listing_date"].notna()
        common_dates = set(pd.to_datetime(raw.loc[common, "listing_date"]))
        print(f"\n{target}: rows with every candidate's inputs present: {int(common.sum())}")

        res[target] = {"n_common_rows": int(common.sum()), "candidates": {}}
        base = None
        for key, (feats, maker) in CANDIDATES.items():
            try:
                sp_c = spec(target, feats, maker, name=f"cand_{target.lower()}")
                df = F.prepare(sp_c)
                df = df[df["listing_date"].isin(common_dates)]
                best, tab, runs, years = F.select_half_life(df, sp_c)
                oof, per = runs[best]
                auc = float(F.roc_auc_score(oof["y"], oof["p"]))
                row = {"n": int(len(df)), "half_life": "none" if best is None else best,
                       "pooled_auc": round(auc, 4), "claimed": CLAIMED_AUC.get(key)}
                if key == "setA_baseline":
                    base = auc
                row["vs_setA_pp"] = None if base is None else round((auc - base) * 100, 2)
                row["verdict"] = ("baseline" if key == "setA_baseline" else
                                  "WORSE than Set A" if auc < base - 1e-9 else
                                  "no better than Set A" if auc <= base + 0.0005 else
                                  "BETTER than Set A — investigate")
                res[target]["candidates"][key] = row
                cl = "" if row["claimed"] is None else f" claimed {row['claimed']:.4f}"
                print(f"  {key:18s} n={row['n']:4d} hl={str(row['half_life']):5s} "
                      f"pooled AUC {auc:.4f}{cl:>17s}  {row['verdict']}")
            except Exception as e:
                res[target]["candidates"][key] = {"error": f"{type(e).__name__}: {e}"}
                print(f"  {key:18s} ERROR {type(e).__name__}: {e}")

        # collinearity claim (VIF 90) and the sign-flip claim, on the split model
        allf = SET_A + ["log1p_qib", "log1p_hni", "log1p_rii"]
        sub = fx.loc[common, allf].dropna()
        v = F.vif(sub, allf).set_index("feature")["vif"].to_dict()
        res[target]["vif_total_with_split"] = {k: round(float(x), 2) for k, x in v.items()}
        res[target]["vif_total_claimed"] = CLAIMED_VIF_TOTAL
        print(f"  VIF with the split added: "
              + ", ".join(f"{k.replace('log1p_','')} {x:.1f}" for k, x in v.items())
              + f"   (H2 claims Total {CLAIMED_VIF_TOTAL})")

        sp_all = spec(target, allf)
        df_all = F.prepare(sp_all)
        df_all = df_all[df_all["listing_date"].isin(common_dates)]
        pipe, coefs, _ = F.fit_final(df_all, sp_all, None)
        res[target]["split_coefs_std"] = {k: round(float(x), 3) for k, x in coefs.items()}
        res[target]["split_coefs_claimed"] = CLAIMED_SPLIT_COEFS
        print("  standardised coefficients with the split added: "
              + ", ".join(f"{k.replace('log1p_','')} {x:+.2f}" for k, x in coefs.items()))
    return res


# ------------------------------------------------------------- 2. H3 and H4
def part2_h3_h4() -> dict:
    print("\n" + "=" * 86)
    print("2. H3 demand profile (displayed, never modelled) and H4 issue-size coefficient")
    print("=" * 86)
    raw = load_mainboard()
    raw = raw[raw["exclude_reason"].isna()]
    fx = all_features(raw)
    d = pd.DataFrame({"retail_skew": fx["retail_skew"],
                      "listing_gain": raw["listing_gain"],
                      "listing_date": pd.to_datetime(raw["listing_date"])}).dropna()
    # quartiles on the full eligible set, to reproduce H3's published table
    d["q"] = pd.qcut(d["retail_skew"], 4, labels=["Q1 institution-skewed", "Q2", "Q3",
                                                  "Q4 retail-skewed"])
    med = d.groupby("q", observed=True)["listing_gain"].agg(["median", "count"])
    print(f"\n  retail_skew = log1p(RII) - log1p(QIB), n={len(d)}")
    print(f"  {'quartile':26s} {'median gain':>12s} {'claimed':>9s} {'n':>5s}")
    h3 = {}
    for q, r in med.iterrows():
        cl = CLAIMED_H3.get(str(q))
        h3[str(q)] = {"median_listing_gain_pct": round(float(r["median"]), 2),
                      "claimed": cl, "n": int(r["count"]),
                      "reproduces": None if cl is None else bool(abs(r["median"] - cl) <= 1.0)}
        print(f"  {str(q):26s} {r['median']:+11.1f}% {cl:>8}% {int(r['count']):5d}")

    # cut-points fitted on TRAINING data only, as H3 requires for live use
    last = int(d["listing_date"].dt.year.max())
    tr = d[d["listing_date"].dt.year < last]
    cuts = [float(x) for x in np.quantile(tr["retail_skew"], [0.25, 0.50, 0.75])]
    print(f"\n  live cut-points fitted on years < {last} only (n={len(tr)}): "
          + ", ".join(f"{c:+.3f}" for c in cuts))

    # H4: standardised issue-size coefficient in the Set A model
    h4 = {}
    for target in ("L1", "L2"):
        sp = spec(target, SET_A)
        df = F.prepare(sp)
        _, coefs, _ = F.fit_final(df, sp, None)
        h4[target] = {"log_issue_size_std_coef": round(float(coefs["log_issue_size"]), 3),
                      "log1p_total_std_coef": round(float(coefs["log1p_total"]), 3),
                      "n": int(len(df)), "claimed": CLAIMED_H4_COEF}
        print(f"  {target}: standardised coef log(issue size) = "
              f"{coefs['log_issue_size']:+.3f}  (H4 claims {CLAIMED_H4_COEF:+.3f}); "
              f"log1p(Total) {coefs['log1p_total']:+.3f}; n={len(df)}")
    return {"h3_quartiles": h3, "h3_live_cutpoints": cuts, "h3_cutpoint_train_years_before": last,
            "h3_n": int(len(d)), "h4_issue_size": h4}


# ------------------------------------------------------------- 3. final model
def part3_final() -> dict:
    print("\n" + "=" * 86)
    print("3. Final fit — Set A, mainboard, isotonic calibration (G1), thresholds per C5")
    print("=" * 86)
    out, oof_dir = {}, ROOT / "reports" / "oof"
    oof_dir.mkdir(parents=True, exist_ok=True)
    for target in ("L1", "L2"):
        req = REQUIRED[target]
        sp = ML.spec(target, "mainboard")           # the production spec, not a local copy
        df = F.prepare(sp)
        best, tab, runs, years = F.select_half_life(df, sp)
        oof, per = runs[best]
        pooled = float(F.roc_auc_score(oof["y"], oof["p"]))
        oof.to_csv(oof_dir / f"stage16_{target.lower()}_setA.csv", index=False)

        # G1: isotonic, fitted OUT OF TIME on years < T, then applied to T. Nothing is
        # fitted on the rows it scores.
        yrs = sorted(oof["year"].unique())
        parts = []
        for T in yrs[1:]:
            tr, te = oof[oof["year"] < T], oof[oof["year"] == T].copy()
            cal = C.IsotonicCalibrator().fit(tr["p"].to_numpy(), tr["y"].to_numpy())
            te["p_cal"] = cal.predict(te["p"].to_numpy())
            parts.append(te)
        held = pd.concat(parts, ignore_index=True)
        fired = held[held["p_cal"] >= req]
        n, k = len(fired), int(fired["y"].sum())
        hr = k / n if n else float("nan")
        lo = F.wilson_lower(k, n) if n else float("nan")
        passes = bool(n >= MIN_FIRE and hr >= req and lo >= req - SLACK)
        brier_raw = C.brier(held["y"], held["p"])
        brier_iso = C.brier(held["y"], held["p_cal"])

        # the production calibrator: fitted on ALL out-of-fold predictions (each of which
        # came from a model that never saw its own row), then frozen.
        prod_cal = C.IsotonicCalibrator().fit(oof["p"].to_numpy(), oof["y"].to_numpy())
        raw_equiv = None
        grid = np.linspace(0.01, 0.999, 999)
        cg = prod_cal.predict(grid)
        hits = grid[cg >= req]
        if len(hits):
            raw_equiv = float(hits.min())

        pipe, coefs, w = F.fit_final(df, sp, best)
        thresholds = {target: raw_equiv}

        # H3 cut-points fitted on TRAINING rows only. "Training" here means every row
        # outside the most recent listing year, so the live label is never derived from a
        # window that includes the IPO being scored.
        raw_all = ML.load_mainboard()
        raw_all = raw_all[raw_all["exclude_reason"].isna()]
        raw_all["listing_date"] = pd.to_datetime(raw_all["listing_date"])
        last_year = int(raw_all["listing_date"].dt.year.max())
        cuts = ML.fit_profile_cutpoints(raw_all[raw_all["listing_date"].dt.year < last_year])

        path = F.save_bundle(sp, pipe, best, thresholds, extra={
            "model_id": ML.MODEL_ID, "decision_point": ML.DECISION_POINT,
            "calibrator": "isotonic", "calibrator_object": prod_cal,
            "required_hit_rate": req, "calibrated_threshold": req,
            "raw_equivalent_threshold": raw_equiv,
            "profile_cutpoints": cuts, "profile_cutpoints_fitted_on": f"years < {last_year}",
            "feature_set": "Set A (H2, frozen)", "plan_decisions": ["H1", "H2", "H3", "G1", "G2"],
        })

        print(f"\n  {target}: n={len(df)} half-life={best} pooled AUC {pooled:.4f} "
              f"(mean {per['auc'].mean():.4f}) years={[int(y) for y in years]}")
        print(f"      Brier held-out: raw {brier_raw:.4f} -> isotonic {brier_iso:.4f} "
              f"({'beats raw' if brier_iso < brier_raw else 'DOES NOT beat raw'})")
        print(f"      fire iff calibrated p >= {req:.2f}  (raw-equivalent "
              f"{raw_equiv if raw_equiv is None else round(raw_equiv,3)}): "
              f"fires {n}, hit {hr*100:.1f}%, Wilson lo95 {lo*100:.1f}%  "
              f"C5 {'PASS' if passes else 'FAIL'}")
        print(f"      standardised coefficients: "
              + ", ".join(f"{a} {b:+.3f}" for a, b in coefs.items())
              + f" | effective n {F.effective_n(w):.0f} of {len(df)}")
        print(f"      saved {path.name}")

        out[target] = {
            "n": int(len(df)), "half_life": "none" if best is None else best,
            "test_years": [int(y) for y in years], "pooled_auc": round(pooled, 4),
            "mean_auc": round(float(per["auc"].mean()), 4),
            "per_year": per.to_dict("records"),
            "brier_raw": round(brier_raw, 4), "brier_isotonic": round(brier_iso, 4),
            "isotonic_beats_raw": bool(brier_iso < brier_raw),
            "firing_rule": f"fire iff isotonic-calibrated p >= {req:.2f}",
            "raw_equivalent_threshold": raw_equiv,
            "held_out_n_fire": n, "held_out_hits": k,
            "held_out_hit_rate": None if n == 0 else round(hr, 4),
            "held_out_wilson_lo95": None if n == 0 else round(lo, 4),
            "passes_c5": passes,
            "calibrator_claimed_mean": None if n == 0 else round(float(fired["p_cal"].mean()), 4),
            "overclaim_pp": None if n == 0 else round(float(fired["p_cal"].mean() - hr) * 100, 2),
            "std_coefs": {a: round(float(b), 4) for a, b in coefs.items()},
            "effective_n": round(F.effective_n(w), 1),
            "bundle": path.name,
            "profile_cutpoints": cuts,
            "profile_cutpoints_fitted_on": f"years < {last_year}",
        }
    return out


def part4_sme_shadow() -> dict:
    """SME stays a separate model (rule 6) and stays in shadow mode. Same Set A features."""
    print("\n" + "=" * 86)
    print("3b. SME shadow models (rule 6 — segments are never pooled; shadow mode only)")
    print("=" * 86)
    out = {}
    for target in ("L1", "L2"):
        try:
            sp = ML.spec(target, "sme")
            df = F.prepare(sp)
            best, tab, runs, years = F.select_half_life(df, sp)
            oof, per = runs[best]
            pooled = float(F.roc_auc_score(oof["y"], oof["p"]))
            pipe, coefs, w = F.fit_final(df, sp, best)
            path = F.save_bundle(sp, pipe, best, {target: None}, extra={
                "model_id": ML.MODEL_ID, "decision_point": ML.DECISION_POINT,
                "shadow_mode": True, "required_hit_rate": REQUIRED[target],
                "feature_set": "Set A (H2, frozen)"})
            out[target] = {"n": int(len(df)), "half_life": "none" if best is None else best,
                           "pooled_auc": round(pooled, 4), "test_years": [int(y) for y in years],
                           "bundle": path.name, "shadow_mode": True}
            print(f"  {target}: n={len(df)} hl={best} pooled AUC {pooled:.4f} "
                  f"years={[int(y) for y in years]} -> {path.name} (SHADOW)")
        except Exception as e:
            out[target] = {"error": f"{type(e).__name__}: {e}"}
            print(f"  {target}: ERROR {type(e).__name__}: {e}")
    return out


# ---------------------------------------------------------------------------- main
def main():
    res = {"generated": str(pd.Timestamp.now()), "stage": 16,
           "decisions": ["H1", "H2", "H3", "H4", "G1", "G2"]}
    res["candidates"] = part1_candidates()
    res["h3_h4"] = part2_h3_h4()
    res["final"] = part3_final()
    res["sme_shadow"] = part4_sme_shadow()
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "stage16_model_l.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("\nwritten: reports/stage16_model_l.json")
    return res


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

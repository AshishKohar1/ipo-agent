"""
stage2_feature_comparison.py — PLAN.md Stage 2: Model L feature comparison -> Gate A.

Mainboard, both targets (L1 = listing gain > 0, L2 = listing gain > 10%), four sets:

    A  log1p(Total) + log(issue size)
    B  log1p(QIB) + log1p(HNI) + log1p(RII) + log(issue size)
    C  Set A + market IPO heat
    D  Set B + market IPO heat

All four are fitted on an IDENTICAL row set (rows where every candidate feature exists),
so the comparison is not confounded by differing samples. That costs 4 rows: the first
IPOs of Jan 2010, which have no prior listing to compute market heat from.

Per set and target: pooled out-of-fold AUC and Gini, per-year AUC, chosen half-life
(selected on POOLED AUC per section 5), VIF per feature, coefficient signs, HC-robust
significance, and the section-5 threshold derivation for L1 (90%) and L2 (80%).

    python stage2_feature_comparison.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import framework as F          # noqa: E402
import dataio                  # noqa: E402
import market_heat             # noqa: E402
from model_l import CUTS, mb_features   # noqa: E402

SETS = {
    "A": ["log1p_total", "log_issue_size"],
    "B": ["log1p_qib", "log1p_hni", "log1p_rii", "log_issue_size"],
    "C": ["log1p_total", "log_issue_size", "market_heat"],
    "D": ["log1p_qib", "log1p_hni", "log1p_rii", "log_issue_size", "market_heat"],
}
ALL_FEATURES = sorted({f for v in SETS.values() for f in v})
REQUIRED = {"L1": 0.90, "L2": 0.80}
SUBSCRIPTION = ("log1p_total", "log1p_qib", "log1p_hni", "log1p_rii")


def load_mainboard_with_heat() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    m["listing_date"] = m["listing_date_master"]
    m["listing_gain"] = pd.to_numeric(m["Listing Gain"], errors="coerce")
    for k, c in CUTS.items():
        m[k] = (m["listing_gain"] > c).astype(float).where(m["listing_gain"].notna())
    # join on the index: company names are not unique in the master
    h = market_heat.build(m)[["heat", "heat_flag", "cutoff_source"]]
    return m.join(h)


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    out = mb_features(df)
    out["market_heat"] = pd.to_numeric(df.get("heat"), errors="coerce")
    return out


def spec_for(set_name: str, target: str, common_index: pd.Index | None) -> F.ModelSpec:
    """common_index: restrict to these master row labels so every set sees the same rows."""
    def load():
        m = load_mainboard_with_heat()
        if common_index is not None:
            m = m.loc[m.index.intersection(common_index)]
        return m
    return F.ModelSpec(
        name=f"stage2_{target.lower()}_set{set_name}",
        title=f"Stage 2 — Model {target}, Set {set_name}",
        load=load, make_features=make_features, features=SETS[set_name],
        target=target, target_desc=f"1 if listing gain > {CUTS[target]:g}%",
        realised_days=0, required_hit_rate={target: REQUIRED[target]},
    )


def common_rows() -> pd.Index:
    """Master row labels usable by every set: unflagged, target present, all features present."""
    m = load_mainboard_with_heat()
    feats = make_features(m)
    ok = m["exclude_reason"].isna() & m["listing_date"].notna() & feats[ALL_FEATURES].notna().all(axis=1)
    ok &= m[["L1", "L2"]].notna().all(axis=1)
    return m.index[ok]


def evaluate(set_name: str, target: str, idx: pd.Index) -> dict:
    spec = spec_for(set_name, target, idx)
    df = F.prepare(spec)
    best, hl_tab, runs, years = F.select_half_life(df, spec)       # pooled AUC
    oof, per = runs[best]
    pooled = F.roc_auc_score(oof["y"], oof["p"])
    pipe, coefs, w = F.fit_final(df, spec, best)
    v = F.vif(df, spec.features)
    try:
        hc = F.hc_logit(df, spec)
        hc_tab = pd.DataFrame({"feature": ["const"] + spec.features,
                               "coef": hc.params, "se": hc.bse, "z": hc.tvalues,
                               "p": hc.pvalues}).reset_index(drop=True)
        hc_txt = hc.summary().as_text()
    except Exception as e:
        hc_tab, hc_txt = pd.DataFrame(), f"HC Logit failed: {e}"
    subs = [f for f in spec.features if f in SUBSCRIPTION]
    signs = {f: float(coefs[f]) for f in spec.features}
    sign_ok = all(signs[f] > 0 for f in subs)
    s5 = F.threshold_section5(oof, REQUIRED[target])
    return {"set": set_name, "target": target, "n": len(df),
            "pos_rate": float(df[spec.target].mean()),
            "half_life": ("none" if best is None else best),
            "eff_n": F.effective_n(w),
            "pooled_auc": float(pooled), "pooled_gini": float(2 * pooled - 1),
            "mean_auc": float(per["auc"].mean()),
            "per_year": {int(r.test_year): float(r.auc) for r in per.itertuples()},
            "years": years, "hl_tab": hl_tab, "per": per, "oof": oof,
            "vif": v, "max_vif": float(v["vif"].max()),
            "coefs": signs, "subscription_coefs": {f: signs[f] for f in subs},
            "sign_ok": bool(sign_ok), "hc_tab": hc_tab, "hc_txt": hc_txt, "s5": s5}


def main():
    idx = common_rows()
    print(f"common row set usable by every feature set: {len(idx)} mainboard IPOs")
    m = load_mainboard_with_heat()
    dropped = m[m["exclude_reason"].isna() & m["listing_date"].notna()
                & m[["L1", "L2"]].notna().all(axis=1)].index.difference(idx)
    if len(dropped):
        print("dropped for comparability (no market heat):")
        print(m.loc[dropped, ["company", "listing_date", "heat_flag"]].to_string(index=False))

    results = {}
    for target in ("L1", "L2"):
        for s in SETS:
            r = evaluate(s, target, idx)
            results[(s, target)] = r
            print(f"  {target} Set {s}: n={r['n']} hl={r['half_life']:>4} "
                  f"pooled AUC={r['pooled_auc']:.4f} Gini={r['pooled_gini']:.3f} "
                  f"maxVIF={r['max_vif']:.1f} signs_ok={r['sign_ok']} "
                  f"thr={r['s5']['chosen']}")

    # machine-readable summary
    flat = [{k: v for k, v in r.items()
             if k not in ("hl_tab", "per", "oof", "vif", "hc_tab", "hc_txt", "s5")}
            | {"threshold": r["s5"]["chosen"],
               "thr_n_fire": (r["s5"]["at_chosen"] or {}).get("n_fire"),
               "thr_hit_rate": (r["s5"]["at_chosen"] or {}).get("hit_rate"),
               "thr_lo95": (r["s5"]["at_chosen"] or {}).get("hit_rate_lo95")}
            for r in results.values()]
    pd.DataFrame(flat).to_csv(ROOT / "reports" / "stage2_results.csv", index=False)
    (ROOT / "reports" / "stage2_results.json").write_text(
        json.dumps(flat, indent=2, default=str), encoding="utf-8")
    print("\nwritten: reports/stage2_results.csv, reports/stage2_results.json")
    return results


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

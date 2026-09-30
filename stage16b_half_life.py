"""
stage16b_half_life.py — Gate B, Task 2: settle the issue-size sign. Decision H11.

The problem: the standardised `log(issue size)` coefficient is **−0.137 unweighted** and
**+0.314 at the 2-year half-life** selected by pooled AUC. A variable whose direction is set
by a tuning knob rather than by the data cannot be defended in a model card.

The test, for half-lives {2, 3, 5, 8, none}:
  * pooled out-of-fold AUC under the standard walk-forward protocol
  * the standardised `log_issue_size` coefficient and its sign, from the final fit
  * the L1 and L2 thresholds with their out-of-time hit rates

**Adoption rule (as instructed):** take the **shortest** half-life at which the issue-size
sign stops flipping and **matches the unweighted sign**, provided its pooled AUC is within
1 percentage point of the best. If no half-life achieves that, say so and recommend dropping
issue size entirely — subscription carries almost all the signal regardless.

"Stops flipping" is read literally: the sign at that half-life must equal the unweighted
sign **and** stay that way at every longer half-life. A half-life that happens to agree
while its neighbours disagree has not stopped flipping; it has crossed zero.

A control column reports Set A minus issue size — `log1p(Total)` alone — so the
recommendation to drop it can be judged on evidence rather than asserted.

Writes reports/stage16b_half_life.json.

    python stage16b_half_life.py
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
import framework as F        # noqa: E402
import calibration as C      # noqa: E402
import model_l as ML         # noqa: E402

HALF_LIVES = [2, 3, 5, 8, None]
REQUIRED = {"L1": 0.90, "L2": 0.80}
MIN_FIRE, SLACK = 20, 0.05
TOTAL_ONLY = ["log1p_total"]


def thresholds_out_of_time(oof: pd.DataFrame, req: float) -> dict:
    """G1's rule, measured honestly: the calibrator is fitted on years < T and applied to T,
    so nothing is fitted on the rows it scores."""
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
    # the raw-probability equivalent of the calibrated cut, for a portable scoring formula
    prod = C.IsotonicCalibrator().fit(oof["p"].to_numpy(), oof["y"].to_numpy())
    grid = np.linspace(0.01, 0.999, 999)
    hits = grid[prod.predict(grid) >= req]
    return {"n_fire": n, "hits": k,
            "hit_rate": None if n == 0 else round(hr, 4),
            "wilson_lo95": None if n == 0 else round(lo, 4),
            "raw_equivalent_threshold": float(hits.min()) if len(hits) else None,
            "passes_c5": bool(n >= MIN_FIRE and hr >= req and lo >= req - SLACK),
            "brier_raw": round(C.brier(held["y"], held["p"]), 4),
            "brier_isotonic": round(C.brier(held["y"], held["p_cal"]), 4)}


def sweep(features: list[str], label: str) -> dict:
    out = {"label": label, "features": features, "by_half_life": {}}
    for target in ("L1", "L2"):
        sp = ML.spec(target, "mainboard")
        sp.features = features
        df = F.prepare(sp)
        years = F.test_years(df, sp)
        out["n"] = int(len(df))
        out["test_years"] = [int(y) for y in years]
        for hl in HALF_LIVES:
            key = "none" if hl is None else str(hl)
            oof, per = F.walk_forward(df, sp, hl, years)
            pooled = float(F.roc_auc_score(oof["y"], oof["p"]))
            _, coefs, w = F.fit_final(df, sp, hl)
            row = out["by_half_life"].setdefault(key, {})
            row[target] = {
                "pooled_auc": round(pooled, 4),
                "mean_auc": round(float(per["auc"].mean()), 4),
                "effective_n": round(F.effective_n(w), 1),
                "std_coefs": {a: round(float(b), 4) for a, b in coefs.items()},
                **thresholds_out_of_time(oof, REQUIRED[target]),
            }
    return out


def main():
    print("=" * 100)
    print("Gate B Task 2 — does the issue-size sign survive the choice of half-life?")
    print("=" * 100)

    seta = sweep(ML.SET_A, "Set A (log1p_total + log_issue_size)")
    control = sweep(TOTAL_ONLY, "control: log1p_total ONLY (issue size dropped)")

    # the unweighted sign is the reference: it is the one the data gives with no knob set
    ref = {t: np.sign(seta["by_half_life"]["none"][t]["std_coefs"]["log_issue_size"])
           for t in ("L1", "L2")}
    print(f"\nReference (half-life = none, no recency knob): "
          f"L1 {seta['by_half_life']['none']['L1']['std_coefs']['log_issue_size']:+.3f}, "
          f"L2 {seta['by_half_life']['none']['L2']['std_coefs']['log_issue_size']:+.3f}"
          f"  -> reference sign {'negative' if ref['L1'] < 0 else 'positive'} (L1), "
          f"{'negative' if ref['L2'] < 0 else 'positive'} (L2)")

    print(f"\n{'half-life':>10s} | {'L1 AUC':>7s} {'coef':>8s} {'sign':>5s} "
          f"{'fires':>6s} {'hit':>7s} {'C5':>5s} | "
          f"{'L2 AUC':>7s} {'coef':>8s} {'sign':>5s} {'fires':>6s} {'hit':>7s} {'C5':>5s}")
    print("-" * 100)
    rows = []
    for key in [("none" if h is None else str(h)) for h in HALF_LIVES]:
        a, b = seta["by_half_life"][key]["L1"], seta["by_half_life"][key]["L2"]
        ca, cb = a["std_coefs"]["log_issue_size"], b["std_coefs"]["log_issue_size"]
        rows.append({"half_life": key, "L1": a, "L2": b})
        print(f"{key:>10s} | {a['pooled_auc']:7.4f} {ca:+8.3f} "
              f"{'neg' if ca < 0 else 'pos':>5s} {a['n_fire']:6d} "
              f"{(a['hit_rate'] or 0) * 100:6.1f}% "
              f"{'PASS' if a['passes_c5'] else 'FAIL':>5s} | "
              f"{b['pooled_auc']:7.4f} {cb:+8.3f} {'neg' if cb < 0 else 'pos':>5s} "
              f"{b['n_fire']:6d} {(b['hit_rate'] or 0) * 100:6.1f}% "
              f"{'PASS' if b['passes_c5'] else 'FAIL':>5s}")

    print(f"\n{'half-life':>10s} | control (log1p_total only): "
          f"{'L1 AUC':>7s} {'L1 fires/hit':>16s} | {'L2 AUC':>7s} {'L2 fires/hit':>16s}")
    for key in [("none" if h is None else str(h)) for h in HALF_LIVES]:
        a, b = control["by_half_life"][key]["L1"], control["by_half_life"][key]["L2"]
        print(f"{key:>10s} |                             "
              f"{a['pooled_auc']:7.4f} {a['n_fire']:6d} / "
              f"{(a['hit_rate'] or 0) * 100:5.1f}%     | {b['pooled_auc']:7.4f} "
              f"{b['n_fire']:6d} / {(b['hit_rate'] or 0) * 100:5.1f}%")

    # ---------------------------------------------------------------- the adoption rule
    best = {t: max(r["L1" if t == "L1" else "L2"]["pooled_auc"] for r in rows)
            for t in ("L1", "L2")}
    order = [("none" if h is None else str(h)) for h in HALF_LIVES]
    shortest_first = [k for k in ("2", "3", "5", "8", "none")]

    def sign_at(key, t):
        return np.sign(seta["by_half_life"][key][t]["std_coefs"]["log_issue_size"])

    chosen, why = None, []
    for k in shortest_first:
        idx = shortest_first.index(k)
        longer = shortest_first[idx:]                # itself and every LONGER half-life
        # "stops flipping" -- it must match the reference sign here AND stay so afterwards
        stable = all(sign_at(j, t) == ref[t] for j in longer for t in ("L1", "L2"))
        within = all(best[t] - seta["by_half_life"][k][t]["pooled_auc"] <= 0.01
                     for t in ("L1", "L2"))
        gap = {t: round((best[t] - seta["by_half_life"][k][t]["pooled_auc"]) * 100, 2)
               for t in ("L1", "L2")}
        why.append({"half_life": k, "sign_matches_and_stable": bool(stable),
                    "auc_within_1pp": bool(within), "auc_gap_pp": gap,
                    "L1_sign": "neg" if sign_at(k, "L1") < 0 else "pos",
                    "L2_sign": "neg" if sign_at(k, "L2") < 0 else "pos"})
        if stable and within and chosen is None:
            chosen = k

    print("\n" + "=" * 100)
    print("ADOPTION RULE — shortest half-life whose issue-size sign matches the unweighted")
    print("sign and stays matched at every longer half-life, with pooled AUC within 1pp of best")
    print("=" * 100)
    for w in why:
        print(f"  half-life {w['half_life']:>4s}: sign L1 {w['L1_sign']} / L2 {w['L2_sign']} "
              f"-> stable {str(w['sign_matches_and_stable']):5s} | "
              f"AUC gap L1 {w['auc_gap_pp']['L1']:+.2f}pp L2 {w['auc_gap_pp']['L2']:+.2f}pp "
              f"-> within 1pp {str(w['auc_within_1pp']):5s}")

    if chosen:
        verdict = (f"ADOPT half-life {chosen}. Its issue-size coefficient matches the "
                   f"unweighted sign and does not flip at any longer half-life, and its "
                   f"pooled AUC is within 1pp of the best on both targets.")
        drop = False
    else:
        # is the control actually as good? that is the evidence for dropping issue size
        cgap = {t: round((best[t] - max(control["by_half_life"][k][t]["pooled_auc"]
                                        for k in order)) * 100, 2) for t in ("L1", "L2")}
        verdict = (f"NO half-life satisfies the rule. The issue-size sign is set by the "
                   f"recency knob, not by the data, so the variable cannot be defended. "
                   f"RECOMMEND DROPPING issue size: log1p(Total) alone costs "
                   f"{cgap['L1']:+.2f}pp on L1 and {cgap['L2']:+.2f}pp on L2 against the "
                   f"best Set A figure.")
        drop = True
    print(f"\n{verdict}")

    res = {"generated": str(pd.Timestamp.now()), "decision": "H11",
           "reference_sign_unweighted": {t: ("neg" if ref[t] < 0 else "pos") for t in ref},
           "set_a": seta, "control_total_only": control,
           "best_pooled_auc": {t: round(best[t], 4) for t in best},
           "rule_evaluation": why, "chosen_half_life": chosen,
           "recommend_dropping_issue_size": drop, "verdict": verdict}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "stage16b_half_life.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("\nwritten: reports/stage16b_half_life.json")
    return res


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

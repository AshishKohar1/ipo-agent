"""
stage3_calibration.py — PLAN.md Stage 3: calibration curve and final thresholds.

Input: Set A's walk-forward out-of-fold predictions from Stage 2 (Gate A decision A1),
`reports/oof/stage2_l1_setA.csv` and `stage2_l2_setA.csv`.

Method:
  1. Out-of-time calibration. For each test year T, fit the calibrator on out-of-fold
     predictions from years BEFORE T and apply it to year T. The first year has no prior
     data, so it cannot be scored — held-out years are the second onward.
  2. Compare raw vs Platt vs isotonic on those held-out years: Brier score and a decile
     reliability table.
  3. Derive each target's threshold two ways, BOTH out of time so they are comparable:
       (a) bucket rule  — decision C5, but with the threshold chosen on years < T only.
                          Choosing it on the rows it is then scored on inflates the result,
                          because the threshold is picked *because* it satisfies the
                          constraint there.
       (b) calibrated   — fire when the calibrated probability reaches the required hit
                          rate. The calibrator saw only earlier years, so nothing is tuned
                          on the rows being scored.
  4. Adopt the calibrated method only if its held-out Brier beats raw **and** its threshold
     still passes the C5 hit-rate, Wilson and 20-fire checks on held-out data. Otherwise
     keep the bucket method.

Writes reports/stage3_calibration.json.

    python stage3_calibration.py
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

REQUIRED = {"L1": 0.90, "L2": 0.80}
MIN_FIRE, SLACK = 20, 0.05
GRID = np.round(np.arange(0.05, 1.00, 0.01), 2)


def out_of_time(oof: pd.DataFrame, cal_cls):
    """Fit on years < T, predict year T. Returns the held-out frame with calibrated p."""
    years = sorted(oof["year"].unique())
    parts = []
    for T in years[1:]:                       # the first year has no history to fit on
        tr = oof[oof["year"] < T]
        te = oof[oof["year"] == T].copy()
        cal = cal_cls().fit(tr["p"].to_numpy(), tr["y"].to_numpy())
        te["p_cal"] = cal.predict(te["p"].to_numpy())
        te["fitted_on_years"] = ";".join(str(y) for y in sorted(tr["year"].unique()))
        parts.append(te)
    return pd.concat(parts, ignore_index=True)


def bucket_rule_out_of_time(oof: pd.DataFrame, required: float) -> dict:
    """(a) The C5 bucket rule applied honestly: threshold chosen on years < T, then applied
    to year T. min_fire is relaxed to 10 when picking on the short early history; the >=20
    gate still applies to the pooled result."""
    years = sorted(oof["year"].unique())
    fired, picks = [], {}
    for T in years[1:]:
        tr = oof[oof["year"] < T]
        te = oof[oof["year"] == T]
        s5 = F.threshold_section5(tr[["y", "p"]], required, min_fire=10, slack=SLACK, grid=GRID)
        picks[int(T)] = s5["chosen"]
        if s5["chosen"] is not None:
            fired.append(te[te["p"] >= s5["chosen"]])
    f = pd.concat(fired) if fired else pd.DataFrame(columns=["y"])
    n = len(f); k = int(f["y"].sum()) if n else 0
    hr = k / n if n else float("nan")
    lo = F.wilson_lower(k, n) if n else float("nan")
    return {"thresholds_by_year": picks, "n_fire": n, "hits": k, "hit_rate": hr,
            "hit_rate_lo95": lo,
            "passes_c5": bool(n >= MIN_FIRE and hr >= required and lo >= required - SLACK)}


def calibrated_rule_out_of_time(held: pd.DataFrame, required: float) -> dict:
    """(b) Fire when the CALIBRATED probability reaches the required hit rate — the literal
    reading of the plan."""
    f = held[held["p_cal"] >= required]
    n = len(f); k = int(f["y"].sum()) if n else 0
    hr = k / n if n else float("nan")
    lo = F.wilson_lower(k, n) if n else float("nan")
    return {"rule": f"fire iff calibrated p >= {required:.2f}",
            "raw_equivalent_threshold": float(f["p"].min()) if n else None,
            "n_fire": n, "hits": k, "hit_rate": hr, "hit_rate_lo95": lo,
            "calibrator_claimed_mean": float(f["p_cal"].mean()) if n else None,
            "overclaim_pp": (float(f["p_cal"].mean() - hr) * 100) if n else None,
            "passes_c5": bool(n >= MIN_FIRE and hr >= required and lo >= required - SLACK)}


def main():
    out = {"generated": str(pd.Timestamp.now()), "targets": {}}
    for target in ("L1", "L2"):
        req = REQUIRED[target]
        oof = pd.read_csv(ROOT / "reports" / "oof" / f"stage2_{target.lower()}_setA.csv")
        years = [int(y) for y in sorted(oof["year"].unique())]
        print(f"\n{'='*78}\n{target}: required hit rate {req:.0%} | oof rows {len(oof)} | years {years}")

        res = {"n_oof": len(oof), "years": years, "required": req, "methods": {}}
        held = {}
        for cls in C.CALIBRATORS:
            h = out_of_time(oof, cls)
            held[cls.name] = h
            b = C.brier(h["y"], h["p_cal"])
            res["methods"][cls.name] = {"held_out_n": len(h), "brier": b,
                                        "held_out_years": [int(y) for y in sorted(h["year"].unique())]}
            print(f"  {cls.name:9s} held-out n={len(h)} Brier={b:.4f}")

        raw_b = res["methods"]["raw"]["brier"]
        for name in ("platt", "isotonic"):
            res["methods"][name]["beats_raw"] = bool(res["methods"][name]["brier"] < raw_b)

        # (a) bucket rule, chosen out-of-time so it is comparable with (b)
        bk = bucket_rule_out_of_time(oof, req)
        res["bucket_rule"] = bk
        print(f"  (a) bucket   out-of-time: fires {bk['n_fire']:3d} hit {bk['hit_rate']*100:5.1f}% "
              f"lo95 {bk['hit_rate_lo95']*100:5.1f}%  C5 {'PASS' if bk['passes_c5'] else 'FAIL'}"
              f"  thresholds/yr={bk['thresholds_by_year']}")

        # (b) calibrated rule, per calibrator
        res["calibrated_rule"] = {}
        for name in ("platt", "isotonic"):
            r = calibrated_rule_out_of_time(held[name], req)
            res["calibrated_rule"][name] = r
            print(f"  (b) {name:9s} out-of-time: fires {r['n_fire']:3d} hit {r['hit_rate']*100:5.1f}% "
                  f"lo95 {r['hit_rate_lo95']*100:5.1f}%  C5 {'PASS' if r['passes_c5'] else 'FAIL'}"
                  f"  (claims {r['calibrator_claimed_mean']*100:.1f}%, overclaims "
                  f"{r['overclaim_pp']:+.1f}pp)")

        # 4. adoption
        best, adopt, why = None, False, []
        for name in ("isotonic", "platt"):
            m, cr = res["methods"][name], res["calibrated_rule"][name]
            if not m["beats_raw"]:
                why.append(f"{name}: Brier {m['brier']:.4f} does not beat raw {raw_b:.4f}")
            elif not cr["passes_c5"]:
                why.append(f"{name}: Brier improves but its threshold fails the C5 audit "
                           f"(hit {cr['hit_rate']*100:.1f}%, lo95 {cr['hit_rate_lo95']*100:.1f}%)")
            else:
                best, adopt = name, True
                why.append(f"{name}: Brier {m['brier']:.4f} beats raw {raw_b:.4f} AND the C5 "
                           f"audit passes (fires {cr['n_fire']}, hit {cr['hit_rate']*100:.1f}%, "
                           f"lo95 {cr['hit_rate_lo95']*100:.1f}%)")
                break
        if adopt:
            why.append(f"bucket rule for comparison: fires {bk['n_fire']}, hit "
                       f"{bk['hit_rate']*100:.1f}%, C5 {'PASS' if bk['passes_c5'] else 'FAIL'}")
        res["adopted"] = {
            "method": f"calibrated_{best}" if adopt else "bucket_rule_on_raw",
            "calibrated": adopt,
            "firing_rule": (res["calibrated_rule"][best]["rule"] if adopt
                            else f"fire iff raw p >= per-year threshold {bk['thresholds_by_year']}"),
            "raw_equivalent_threshold": (res["calibrated_rule"][best]["raw_equivalent_threshold"]
                                         if adopt else None),
            "reasoning": why}
        print(f"  ADOPTED: {res['adopted']['method']} -> {res['adopted']['firing_rule']}")
        for w in why:
            print(f"     - {w}")

        res["reliability"] = {n: C.reliability(held[n]["y"], held[n]["p_cal"]).to_dict("records")
                              for n in held}
        out["targets"][target] = res

    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "stage3_calibration.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nwritten: reports/stage3_calibration.json")
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

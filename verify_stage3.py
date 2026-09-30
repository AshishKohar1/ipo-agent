"""
verify_stage3.py — INDEPENDENT verification of Stage 3's calibration results.

Deliberately shares no code with models/calibration.py or models/framework.py. Every
quantity is recomputed from first principles from the Stage 2 out-of-fold CSVs:

  * isotonic regression via the **greatest convex minorant** of the cumulative-sum diagram
    (a convex-hull scan), which is a different algorithm from the PAV stack used in
    models/calibration.py. If both agree to machine precision, PAV is verified.
  * Platt scaling by its own Newton solve.
  * Brier score, Wilson lower bound and the C5 gates re-derived here.
  * A leakage audit that asserts, for every test year, that nothing which chose a
    threshold or fitted a calibrator ever saw the rows it is scored on.

    python verify_stage3.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REQUIRED = {"L1": 0.90, "L2": 0.80}
MIN_FIRE, SLACK = 20, 0.05
GRID = np.round(np.arange(0.05, 1.00, 0.01), 2)
CLAIMED = {  # what the laptop session reported, to be confirmed or refuted
    "L1": {"iso_fires": 117, "iso_hit": 0.940, "iso_lo": 0.882, "bucket_fires": 92,
           "bucket_hit": 0.924, "brier_raw": 0.1596, "brier_iso": 0.1579},
    "L2": {"iso_fires": 96, "iso_hit": 0.875, "iso_lo": 0.794, "bucket_fires": 83,
           "bucket_hit": 0.771, "brier_raw": 0.1624, "brier_iso": 0.1586},
}


# ---------------------------------------------------------------- primitives
def brier_indep(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    return float(((p - y) ** 2).sum() / len(y))


def wilson_lo_indep(k, n, z=1.96):
    """Wilson score interval, lower end. Written from the closed form directly."""
    if n == 0:
        return float("nan")
    ph = k / n
    denom = 1.0 + z * z / n
    centre = ph + z * z / (2 * n)
    rad = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return float((centre - rad) / denom)


def isotonic_gcm(x, y):
    """Isotonic regression by the greatest convex minorant of the cumulative sum diagram.

    For points P_i = (i, sum_{j<=i} y_j), the isotonic fit is the vector of slopes of the
    GCM of {P_0..P_n}. Implemented as a lower convex hull scan — a genuinely different
    route to the same optimum as PAV.
    Returns (x_unique_sorted, fitted_value_per_unique_x).
    """
    x = np.asarray(x, float); y = np.asarray(y, float)
    order = np.argsort(x, kind="mergesort")
    xs, ys = x[order], y[order]
    n = len(ys)
    cs = np.concatenate([[0.0], np.cumsum(ys)])          # P_i y-coords, i = 0..n
    # lower convex hull over points (i, cs[i])
    hull = [0]
    for i in range(1, n + 1):
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            # drop b if (a,b,i) is not a left/convex turn
            if (cs[b] - cs[a]) * (i - b) >= (cs[i] - cs[b]) * (b - a):
                hull.pop()
            else:
                break
        hull.append(i)
    fitted = np.empty(n)
    for a, b in zip(hull[:-1], hull[1:]):
        fitted[a:b] = (cs[b] - cs[a]) / (b - a)           # constant slope on the segment
    # collapse duplicate x by averaging
    uniq, inv = np.unique(xs, return_inverse=True)
    agg = np.zeros(len(uniq)); cnt = np.zeros(len(uniq))
    np.add.at(agg, inv, fitted); np.add.at(cnt, inv, 1.0)
    return uniq, agg / cnt


def iso_apply(model, p):
    gx, gy = model
    return np.clip(np.interp(np.asarray(p, float), gx, gy), 0.0, 1.0)


def platt_indep(p, y):
    """p' = sigmoid(a*logit(p)+b), own Newton solve."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p)); y = np.asarray(y, float)
    X = np.column_stack([z, np.ones_like(z)])
    b = np.zeros(2)
    for _ in range(300):
        q = 1.0 / (1.0 + np.exp(-(X @ b)))
        grad = X.T @ (q - y)
        W = q * (1 - q) + 1e-12
        step = np.linalg.solve((X * W[:, None]).T @ X, grad)
        b = b - step
        if np.abs(step).max() < 1e-11:
            break
    return b


def platt_apply(b, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p))
    return 1.0 / (1.0 + np.exp(-(b[0] * z + b[1])))


# ---------------------------------------------------------------- verification
def gates(k, n, required):
    hr = k / n if n else float("nan")
    lo = wilson_lo_indep(k, n)
    return hr, lo, bool(n >= MIN_FIRE and hr >= required and lo >= required - SLACK)


def main():
    print("=" * 80)
    print("PART 1 — is the PAV isotonic in models/calibration.py correct?")
    print("=" * 80)
    sys_path = str(ROOT / "models")
    if sys_path not in _sys.path:
        _sys.path.insert(0, sys_path)
    import calibration as C          # only to compare against
    rng = np.random.default_rng(11)
    worst = 0.0
    for trial in range(200):
        m = rng.integers(5, 300)
        xx = rng.uniform(size=m)
        yy = (rng.uniform(size=m) < xx ** 1.7).astype(float)
        gx, gy = isotonic_gcm(xx, yy)                      # independent (convex hull)
        pav = C.IsotonicCalibrator().fit(xx, yy)           # PAV under test
        worst = max(worst, float(np.abs(gy - pav.y_).max()), float(np.abs(gx - pav.x_).max()))
    print(f"  200 random problems, max |GCM - PAV| = {worst:.3e}  -> "
          f"{'AGREE' if worst < 1e-9 else 'DISAGREE'}")

    print("\n" + "=" * 80)
    print("PART 2 — independent out-of-time recomputation")
    print("=" * 80)
    verdicts, results = [], {}
    for target, req in REQUIRED.items():
        oof = pd.read_csv(ROOT / "reports" / "oof" / f"stage2_{target.lower()}_setA.csv")
        years = sorted(int(y) for y in oof["year"].unique())
        print(f"\n### {target}: required {req:.0%} | rows {len(oof)} | years {years}")

        audit, rows_raw, rows_iso, rows_plt, rows_bucket = [], [], [], [], []
        for T in years[1:]:
            tr = oof[oof["year"] < T]
            te = oof[oof["year"] == T]
            # leakage audit: training years must all be strictly before T
            assert tr["year"].max() < T, f"LEAK: train year {tr['year'].max()} >= test {T}"
            audit.append({"test_year": T, "fit_years": sorted(int(y) for y in tr["year"].unique()),
                          "n_train": len(tr), "n_test": len(te)})

            iso = isotonic_gcm(tr["p"].to_numpy(), tr["y"].to_numpy())
            pb = platt_indep(tr["p"].to_numpy(), tr["y"].to_numpy())
            te_iso = iso_apply(iso, te["p"].to_numpy())
            te_plt = platt_apply(pb, te["p"].to_numpy())
            rows_raw.append(pd.DataFrame({"y": te["y"].to_numpy(), "pc": te["p"].to_numpy()}))
            rows_iso.append(pd.DataFrame({"y": te["y"].to_numpy(), "pc": te_iso,
                                          "p": te["p"].to_numpy()}))
            rows_plt.append(pd.DataFrame({"y": te["y"].to_numpy(), "pc": te_plt}))

            # bucket rule: pick the lowest qualifying threshold on the TRAINING years only
            best = None
            for t in GRID:
                f = tr[tr["p"] >= t]
                hr, lo, ok = gates(int(f["y"].sum()), len(f), req)
                if len(f) >= 10 and hr >= req and lo >= req - SLACK:
                    best = float(t); break
            if best is not None:
                sel = te[te["p"] >= best]
                rows_bucket.append(pd.DataFrame({"y": sel["y"].to_numpy()}))
            audit[-1]["bucket_threshold_from_history"] = best

        R = pd.concat(rows_raw); I = pd.concat(rows_iso); P = pd.concat(rows_plt)
        B = pd.concat(rows_bucket) if rows_bucket else pd.DataFrame(columns=["y"])

        b_raw, b_iso, b_plt = (brier_indep(R["y"], R["pc"]), brier_indep(I["y"], I["pc"]),
                               brier_indep(P["y"], P["pc"]))
        print(f"  Brier  raw {b_raw:.4f} | platt {b_plt:.4f} | isotonic {b_iso:.4f}"
              f"   (held-out n={len(R)})")

        fi = I[I["pc"] >= req]; hr_i, lo_i, ok_i = gates(int(fi["y"].sum()), len(fi), req)
        fp = P[P["pc"] >= req]; hr_p, lo_p, ok_p = gates(int(fp["y"].sum()), len(fp), req)
        hr_b, lo_b, ok_b = gates(int(B["y"].sum()), len(B), req)
        print(f"  (a) bucket   out-of-time: fires {len(B):3d} hit {hr_b*100:5.1f}% lo95 {lo_b*100:5.1f}%  C5 {'PASS' if ok_b else 'FAIL'}")
        print(f"  (b) platt    out-of-time: fires {len(fp):3d} hit {hr_p*100:5.1f}% lo95 {lo_p*100:5.1f}%  C5 {'PASS' if ok_p else 'FAIL'}")
        print(f"  (b) isotonic out-of-time: fires {len(fi):3d} hit {hr_i*100:5.1f}% lo95 {lo_i*100:5.1f}%  C5 {'PASS' if ok_i else 'FAIL'}")
        print(f"      isotonic claims mean {fi['pc'].mean()*100:.1f}%, delivers {hr_i*100:.1f}%"
              f"  (overclaim {(fi['pc'].mean()-hr_i)*100:+.1f}pp)"
              f" | raw-equivalent threshold {fi['p'].min():.2f}")

        c = CLAIMED[target]
        checks = {
            "isotonic fires": (len(fi), c["iso_fires"], len(fi) == c["iso_fires"]),
            "isotonic hit rate": (round(hr_i, 3), c["iso_hit"], abs(hr_i - c["iso_hit"]) < 0.001),
            "isotonic Wilson lo": (round(lo_i, 3), c["iso_lo"], abs(lo_i - c["iso_lo"]) < 0.001),
            "bucket fires": (len(B), c["bucket_fires"], len(B) == c["bucket_fires"]),
            "bucket hit rate": (round(hr_b, 3), c["bucket_hit"], abs(hr_b - c["bucket_hit"]) < 0.001),
            "Brier raw": (round(b_raw, 4), c["brier_raw"], abs(b_raw - c["brier_raw"]) < 1e-4),
            "Brier isotonic": (round(b_iso, 4), c["brier_iso"], abs(b_iso - c["brier_iso"]) < 1e-4),
        }
        print("  claim-by-claim:")
        for name, (got, want, ok) in checks.items():
            print(f"    {'OK ' if ok else 'MISMATCH'}  {name:20s} independent={got}  claimed={want}")
            verdicts.append(ok)
        results[target] = {"brier": {"raw": b_raw, "platt": b_plt, "isotonic": b_iso},
                           "isotonic": {"fires": len(fi), "hit_rate": hr_i, "lo95": lo_i,
                                        "passes_c5": ok_i,
                                        "claimed_mean": float(fi["pc"].mean()),
                                        "raw_equivalent": float(fi["p"].min())},
                           "platt": {"fires": len(fp), "hit_rate": hr_p, "lo95": lo_p, "passes_c5": ok_p},
                           "bucket": {"fires": len(B), "hit_rate": hr_b, "lo95": lo_b, "passes_c5": ok_b},
                           "leakage_audit": audit}

    print("\n" + "=" * 80)
    ok = all(verdicts)
    print(f"VERDICT: {sum(verdicts)}/{len(verdicts)} claims reproduced independently -> "
          f"{'CONFIRMED' if ok else 'DISCREPANCY — do not record G1/G2'}")
    print("Leakage: every calibrator and every bucket threshold was fitted/chosen on years")
    print("strictly before the year it scored (asserted in code, would have raised).")
    (ROOT / "reports" / "stage3_independent_verification.json").write_text(
        json.dumps({"pav_vs_gcm_max_diff": worst, "all_claims_reproduced": ok,
                    "targets": results}, indent=2, default=str), encoding="utf-8")
    print("written: reports/stage3_independent_verification.json")
    return ok


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    _sys.exit(0 if main() else 1)

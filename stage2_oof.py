"""
stage2_oof.py — write walk-forward out-of-fold predictions for every Stage 2 candidate.

One (set, target) at a time, released between runs: this laptop has ~8 GB RAM and running
all eight evaluations in a single process exhausted it. Each combination is computed at the
half-life that pooled AUC selected for it (recorded in reports/stage2_results.csv), so the
saved predictions are the ones the comparison is based on.

Output: reports/oof/stage2_<target>_set<S>.csv  (listing_date, year, y, p)
These are also Stage 3's input — calibration is fitted on out-of-fold predictions only.

    python stage2_oof.py
"""
from __future__ import annotations
import gc
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import framework as F                      # noqa: E402
import stage2_feature_comparison as S2     # noqa: E402

OUT = ROOT / "reports" / "oof"
HALF_LIFE = 2          # selected by pooled AUC for all 8 combinations (see Stage 2 report)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = S2.common_rows()
    meta = []
    for target in ("L1", "L2"):
        for s in S2.SETS:
            spec = S2.spec_for(s, target, idx)
            df = F.prepare(spec)
            oof, per = F.walk_forward(df, spec, HALF_LIFE)
            pooled = F.roc_auc_score(oof["y"], oof["p"])
            p = OUT / f"stage2_{target.lower()}_set{s}.csv"
            oof.to_csv(p, index=False, encoding="utf-8")
            meta.append({"set": s, "target": target, "half_life": HALF_LIFE,
                         "n_train_rows": len(df), "n_oof": len(oof),
                         "pooled_auc": pooled, "pooled_gini": 2 * pooled - 1,
                         "mean_per_year_auc": per["auc"].mean(),
                         "years": ";".join(str(y) for y in per["test_year"]),
                         "file": p.name})
            print(f"  {target} Set {s}: n_oof={len(oof)} pooled AUC={pooled:.4f} -> {p.name}")
            del spec, df, oof, per
            gc.collect()
    pd.DataFrame(meta).to_csv(ROOT / "reports" / "stage2_oof_index.csv", index=False)
    print("written: reports/oof/*.csv and reports/stage2_oof_index.csv")


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

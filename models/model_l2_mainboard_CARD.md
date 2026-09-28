# Model L2 — mainboard (listing gain > 10%) — model card

_Generated 2026-09-28 11:08 by `models/framework.py`. Bundle: `models/model_l2_mainboard.joblib`._

## Target
`L2`: 1 if listing gain > 10% else 0. Realised 0 days after listing.

## Training data
- Rows loaded 652 → excluded by `exclude_reason` 29 → usable (features + target present, target realised) **620**
- Period: 2010-01-04 to 2026-05-08
- Positive rate: 43.5%
- Final fit: n = 620, effective n = 323.4 (half-life 2 years)

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 2.420 |
| log1p_qib | 0.238 |
| log1p_hni | -0.817 |
| log1p_rii | -0.043 |
| log_issue_size | 0.187 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2022 | auc_2023 | auc_2024 | auc_2025 | auc_2026 |
|---|---|---|---|---|---|---|---|
| 2 | 0.878 | 0.880 | 0.908 | 0.865 | 0.889 | 0.866 | 0.863 |
| 3 | 0.877 | 0.879 | 0.908 | 0.865 | 0.887 | 0.862 | 0.863 |
| 5 | 0.875 | 0.877 | 0.905 | 0.866 | 0.885 | 0.856 | 0.863 |
| 8 | 0.870 | 0.874 | 0.908 | 0.866 | 0.882 | 0.850 | 0.843 |
| none | 0.865 | 0.869 | 0.917 | 0.870 | 0.876 | 0.840 | 0.824 |

**Chosen: 2 years.**

## Walk-forward validation (chosen half-life)
Test years [2022, 2023, 2024, 2025, 2026]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 0d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2022 | 322 | 145.421 | 38 | 0.342 | 0.908 |
| 2023 | 360 | 166.294 | 58 | 0.586 | 0.865 |
| 2024 | 418 | 195.403 | 80 | 0.613 | 0.889 |
| 2025 | 498 | 245.264 | 102 | 0.402 | 0.866 |
| 2026 | 600 | 310.508 | 20 | 0.150 | 0.863 |

**Mean AUC 0.878** (unweighted baseline 0.865). Pooled out-of-fold AUC 0.880.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (-0.001, 0.1] | 50 | 0.066 | 0.040 | -0.026 | 51 | 0.070 | 0.039 | -0.031 |
| (0.1, 0.2] | 39 | 0.140 | 0.077 | -0.063 | 39 | 0.138 | 0.051 | -0.087 |
| (0.2, 0.3] | 13 | 0.257 | 0.385 | 0.127 | 10 | 0.262 | 0.400 | 0.138 |
| (0.3, 0.4] | 13 | 0.358 | 0.308 | -0.050 | 13 | 0.356 | 0.385 | 0.028 |
| (0.4, 0.5] | 10 | 0.458 | 0.400 | -0.058 | 12 | 0.455 | 0.500 | 0.045 |
| (0.5, 0.6] | 12 | 0.548 | 0.417 | -0.132 | 10 | 0.548 | 0.600 | 0.052 |
| (0.6, 0.7] | 15 | 0.648 | 0.467 | -0.181 | 17 | 0.642 | 0.412 | -0.230 |
| (0.7, 0.8] | 23 | 0.754 | 0.522 | -0.232 | 23 | 0.754 | 0.478 | -0.275 |
| (0.8, 0.9] | 44 | 0.864 | 0.591 | -0.273 | 45 | 0.861 | 0.622 | -0.239 |
| (0.9, 1.0] | 79 | 0.944 | 0.911 | -0.033 | 78 | 0.949 | 0.885 | -0.065 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 173 | 58.054 | 122 | 0.705 | 0.633 |
| 0.550 | 169 | 56.711 | 120 | 0.710 | 0.638 |
| 0.600 | 161 | 54.027 | 117 | 0.727 | 0.653 |
| 0.650 | 153 | 51.342 | 113 | 0.739 | 0.664 |
| 0.700 | 146 | 48.993 | 110 | 0.753 | 0.678 |
| 0.750 | 135 | 45.302 | 104 | 0.770 | 0.693 |
| 0.800 | 123 | 41.275 | 98 | 0.797 | 0.717 |
| 0.850 | 107 | 35.906 | 90 | 0.841 | 0.760 |
| 0.900 | 79 | 26.510 | 72 | 0.911 | 0.828 |
| 0.950 | 36 | 12.081 | 36 | 1.000 | 0.904 |

## Threshold verification
'Fire at ≥t' promises an out-of-fold hit rate of at least t. It passes if the hit rate among IPOs firing at t is ≥ t on at least 10 fires. A failing threshold is replaced by the lowest threshold that does deliver t (most fires) — never kept.

- **L2 ≥80%**: fires 123, hit rate 79.7% (95% lower bound 71.7%) → **FAIL** → use ≥85%

Thresholds saved in the bundle: `{'L2': 0.85}`

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  620
Model:                          Logit   Df Residuals:                      614
Method:                           MLE   Df Model:                            5
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                  0.4081
Time:                        11:08:06   Log-Likelihood:                -251.30
converged:                       True   LL-Null:                       -424.58
Covariance Type:                  HC3   LLR p-value:                 9.633e-73
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const             -0.4713      0.117     -4.027      0.000      -0.701      -0.242
log1p_total        5.0497      1.016      4.970      0.000       3.058       7.041
log1p_qib         -1.3314      0.480     -2.773      0.006      -2.272      -0.390
log1p_hni         -1.1291      0.463     -2.441      0.015      -2.036      -0.223
log1p_rii         -0.8860      0.312     -2.841      0.004      -1.497      -0.275
log_issue_size    -0.1572      0.158     -0.992      0.321      -0.468       0.153
==================================================================================
```

## Known limitations
- Uses FINAL subscription (QIB/HNI/RII/Total). Knowable only at bid close — this is the D3 model. Not valid for bidding on day 1-2.
- Mainboard status is verified against the NSE spine / trackers only from Sep 2021; earlier rows are assumed mainboard (no SME row was found in the master where it could be checked).
- `Listing Gain` comes from the master dataset; whether it's listing open or close is not documented in the source. The SME model uses listing-day CLOSE — the two are not comparable.
- `class_weight='balanced'` pushes probabilities towards 0.5; thresholds are verified on out-of-fold hit rates, not read off the probability scale.
- Survivorship does not affect Model L: the target is realised on listing day for every IPO.
- **Severe collinearity.** VIF: Total 83, HNI 20, QIB 20, RII 8 (spec limit 5). Total is a blend of the three categories, so the negative QIB/HNI/RII coefficients are conditional on Total and must NOT be read as 'more QIB demand is bad'. Walk-forward, the split adds little: L1 mean AUC 0.765 with it vs 0.760 on Total + size alone; L2 0.865 vs 0.871 (unweighted). Consider Total + size, or the categories without Total.
- Half-life is chosen by the UNWEIGHTED mean of per-year AUCs, so the 2026 fold (n=20) counts as much as 2025 (n=102). For L1 this decides the choice: pooled out-of-fold AUC would pick 2y.

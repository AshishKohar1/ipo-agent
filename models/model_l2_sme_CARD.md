# Model L2 — sme (listing gain > 10%) — model card

_Generated 2026-09-28 11:08 by `models/framework.py`. Bundle: `models/model_l2_sme.joblib`._

## Target
`L2`: 1 if listing gain > 10% else 0. Realised 0 days after listing.

## Training data
- Rows loaded 402 → excluded by `exclude_reason` 0 → usable (features + target present, target realised) **402**
- Period: 2025-01-08 to 2026-09-17
- Positive rate: 36.3%
- Final fit: n = 402, effective n = 391.4 (half-life 2 years)

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 1.333 |
| log_issue_size | 0.107 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2026 |
|---|---|---|---|
| 2 | 0.824 | 0.824 | 0.824 |
| 3 | 0.824 | 0.824 | 0.824 |
| 5 | 0.824 | 0.824 | 0.824 |
| 8 | 0.824 | 0.824 | 0.824 |
| none | 0.824 | 0.824 | 0.824 |

**Chosen: 2 years.**

## Walk-forward validation (chosen half-life)
Test years [2026]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 0d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2026 | 266 | 263.649 | 136 | 0.368 | 0.824 |

**Mean AUC 0.824** (unweighted baseline 0.824). Pooled out-of-fold AUC 0.824.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (0.1, 0.2] | 18 | 0.189 | 0.167 | -0.022 | 28 | 0.186 | 0.179 | -0.008 |
| (0.2, 0.3] | 46 | 0.233 | 0.109 | -0.124 | 37 | 0.234 | 0.081 | -0.153 |
| (0.3, 0.4] | 14 | 0.347 | 0.214 | -0.133 | 14 | 0.343 | 0.214 | -0.129 |
| (0.4, 0.5] | 8 | 0.453 | 0.250 | -0.203 | 8 | 0.455 | 0.250 | -0.205 |
| (0.5, 0.6] | 5 | 0.554 | 0.600 | 0.046 | 4 | 0.554 | 0.750 | 0.196 |
| (0.6, 0.7] | 3 | 0.655 | 0.667 | 0.012 | 4 | 0.657 | 0.750 | 0.093 |
| (0.7, 0.8] | 8 | 0.750 | 0.750 | 0.000 | 10 | 0.764 | 0.600 | -0.164 |
| (0.8, 0.9] | 28 | 0.846 | 0.714 | -0.132 | 26 | 0.848 | 0.769 | -0.079 |
| (0.9, 1.0] | 6 | 0.913 | 1.000 | 0.087 | 5 | 0.912 | 1.000 | 0.088 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 50 | 36.765 | 37 | 0.740 | 0.604 |
| 0.550 | 48 | 35.294 | 36 | 0.750 | 0.612 |
| 0.600 | 45 | 33.088 | 34 | 0.756 | 0.613 |
| 0.650 | 44 | 32.353 | 33 | 0.750 | 0.606 |
| 0.700 | 42 | 30.882 | 32 | 0.762 | 0.615 |
| 0.750 | 39 | 28.676 | 30 | 0.769 | 0.617 |
| 0.800 | 34 | 25.000 | 26 | 0.765 | 0.600 |
| 0.850 | 19 | 13.971 | 17 | 0.895 | 0.686 |
| 0.900 | 6 | 4.412 | 6 | 1.000 | 0.610 |
| 0.950 | 0 | 0.000 | 0 |  |  |

## Threshold verification
'Fire at ≥t' promises an out-of-fold hit rate of at least t. It passes if the hit rate among IPOs firing at t is ≥ t on at least 10 fires. A failing threshold is replaced by the lowest threshold that does deliver t (most fires) — never kept.

- **L2 ≥80%**: fires 34, hit rate 76.5% (95% lower bound 60.0%) → **FAIL** → use ≥85%

Thresholds saved in the bundle: `{'L2': 0.85}`

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  402
Model:                          Logit   Df Residuals:                      399
Method:                           MLE   Df Model:                            2
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                  0.2665
Time:                        11:08:07   Log-Likelihood:                -193.21
converged:                       True   LL-Null:                       -263.40
Covariance Type:                  HC3   LLR p-value:                 3.293e-31
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const             -0.7169      0.131     -5.457      0.000      -0.974      -0.459
log1p_total        1.3734      0.128     10.754      0.000       1.123       1.624
log_issue_size     0.1418      0.125      1.136      0.256      -0.103       0.387
==================================================================================
```

## Known limitations
- **Thin history.** Only two calendar years (2025-26, 402 SME IPOs) exist in the trackers. Walk-forward by year can test ONE year (2026, trained on 2025 only) — a single fold, so the AUC has no year-to-year spread to judge stability by.
- **Recency weighting is nearly meaningless here.** With all training rows 1-2 years old, half-lives of 2-8 years give almost flat weights, so the half-life 'selection' mostly reflects noise. Treat the chosen half-life as uninformative.
- Features are Total subscription and issue size only (the trackers have no category split).
- Target is listing-day CLOSE vs issue price (tracker). Mainboard uses the master's `Listing Gain`, which may be an opening price.
- IPOMatrix (tracker) and Chittorgarh share a parent; the SME target and features are single-source, not reconciled.
- Uses FINAL subscription — D3 decision time only.

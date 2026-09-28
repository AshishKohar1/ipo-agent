# Model L1 — sme (listing gain > 0%) — model card

_Generated 2026-09-28 11:08 by `models/framework.py`. Bundle: `models/model_l1_sme.joblib`._

## Target
`L1`: 1 if listing gain > 0% else 0. Realised 0 days after listing.

## Training data
- Rows loaded 402 → excluded by `exclude_reason` 0 → usable (features + target present, target realised) **402**
- Period: 2025-01-08 to 2026-09-17
- Positive rate: 62.2%
- Final fit: n = 402, effective n = 391.4 (half-life 2 years)

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 1.132 |
| log_issue_size | 0.120 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2026 |
|---|---|---|---|
| 2 | 0.796 | 0.796 | 0.796 |
| 3 | 0.795 | 0.795 | 0.795 |
| 5 | 0.795 | 0.795 | 0.795 |
| 8 | 0.795 | 0.795 | 0.795 |
| none | 0.795 | 0.795 | 0.795 |

**Chosen: 2 years.**

## Walk-forward validation (chosen half-life)
Test years [2026]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 0d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2026 | 266 | 263.649 | 136 | 0.603 | 0.796 |

**Mean AUC 0.796** (unweighted baseline 0.795). Pooled out-of-fold AUC 0.796.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (0.2, 0.3] | 6 | 0.296 | 0.333 | 0.038 | 6 | 0.294 | 0.333 | 0.040 |
| (0.3, 0.4] | 59 | 0.332 | 0.356 | 0.024 | 59 | 0.330 | 0.356 | 0.026 |
| (0.4, 0.5] | 13 | 0.437 | 0.769 | 0.332 | 14 | 0.438 | 0.786 | 0.348 |
| (0.5, 0.6] | 10 | 0.542 | 0.500 | -0.042 | 9 | 0.541 | 0.444 | -0.097 |
| (0.6, 0.7] | 5 | 0.631 | 0.800 | 0.169 | 5 | 0.625 | 0.800 | 0.175 |
| (0.7, 0.8] | 21 | 0.763 | 0.857 | 0.094 | 22 | 0.759 | 0.864 | 0.104 |
| (0.8, 0.9] | 22 | 0.841 | 1.000 | 0.159 | 21 | 0.838 | 1.000 | 0.162 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 58 | 42.647 | 49 | 0.845 | 0.731 |
| 0.550 | 52 | 38.235 | 47 | 0.904 | 0.794 |
| 0.600 | 48 | 35.294 | 44 | 0.917 | 0.804 |
| 0.650 | 44 | 32.353 | 41 | 0.932 | 0.818 |
| 0.700 | 43 | 31.618 | 40 | 0.930 | 0.814 |
| 0.750 | 36 | 26.471 | 35 | 0.972 | 0.858 |
| 0.800 | 22 | 16.176 | 22 | 1.000 | 0.851 |
| 0.850 | 6 | 4.412 | 6 | 1.000 | 0.610 |
| 0.900 | 0 | 0.000 | 0 |  |  |
| 0.950 | 0 | 0.000 | 0 |  |  |

## Threshold verification
'Fire at ≥t' promises an out-of-fold hit rate of at least t. It passes if the hit rate among IPOs firing at t is ≥ t on at least 10 fires. A failing threshold is replaced by the lowest threshold that does deliver t (most fires) — never kept.

- **L1 ≥90%**: fires 0, hit rate n/a (95% lower bound nan%) → **FAIL** → use ≥55%

Thresholds saved in the bundle: `{'L1': 0.55}`

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  402
Model:                          Logit   Df Residuals:                      399
Method:                           MLE   Df Model:                            2
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                  0.1479
Time:                        11:08:06   Log-Likelihood:                -227.16
converged:                       True   LL-Null:                       -266.58
Covariance Type:                  HC3   LLR p-value:                 7.629e-18
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const              0.6796      0.120      5.656      0.000       0.444       0.915
log1p_total        1.0865      0.132      8.258      0.000       0.829       1.344
log_issue_size     0.0872      0.124      0.704      0.481      -0.156       0.330
==================================================================================
```

## Known limitations
- **Thin history.** Only two calendar years (2025-26, 402 SME IPOs) exist in the trackers. Walk-forward by year can test ONE year (2026, trained on 2025 only) — a single fold, so the AUC has no year-to-year spread to judge stability by.
- **Recency weighting is nearly meaningless here.** With all training rows 1-2 years old, half-lives of 2-8 years give almost flat weights, so the half-life 'selection' mostly reflects noise. Treat the chosen half-life as uninformative.
- Features are Total subscription and issue size only (the trackers have no category split).
- Target is listing-day CLOSE vs issue price (tracker). Mainboard uses the master's `Listing Gain`, which may be an opening price.
- IPOMatrix (tracker) and Chittorgarh share a parent; the SME target and features are single-source, not reconciled.
- Uses FINAL subscription — D3 decision time only.

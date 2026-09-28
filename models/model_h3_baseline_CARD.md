# Model H3 (3y) — baseline — model card

_Generated 2026-09-28 11:21 by `models/framework.py`. Bundle: `models/model_h3_baseline.joblib`._

## Target
`H3_label`: 1 if excess_3y_pp (IPO return − Nifty 50 TRI return, listing close → +1095d) > 0. Realised 1095 days after listing.

## Training data
- Rows loaded 331 → excluded by `exclude_reason` 0 → usable (features + target present, target realised) **330**
- Period: 2010-01-04 to 2023-09-22
- Positive rate: 36.1%
- Final fit: n = 330, effective n = 330.0 (half-life none (unweighted))

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 0.169 |
| log1p_qib | 0.470 |
| log1p_hni | -0.136 |
| log1p_rii | -0.150 |
| log_issue_size | -0.066 |
| listing_gain | -0.202 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2017 | auc_2018 | auc_2021 | auc_2022 | auc_2023 |
|---|---|---|---|---|---|---|---|
| 2 | 0.507 | 0.498 | 0.476 | 0.546 | 0.537 | 0.438 | 0.539 |
| 3 | 0.524 | 0.511 | 0.476 | 0.546 | 0.564 | 0.443 | 0.589 |
| 5 | 0.544 | 0.529 | 0.476 | 0.565 | 0.577 | 0.458 | 0.644 |
| 8 | 0.557 | 0.542 | 0.476 | 0.574 | 0.586 | 0.478 | 0.672 |
| none | 0.562 | 0.556 | 0.462 | 0.583 | 0.591 | 0.487 | 0.689 |

**Chosen: none (unweighted).**

## Walk-forward validation (chosen half-life)
Test years [2017, 2018, 2021, 2022, 2023]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 1095d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2017 | 76 | 76.000 | 34 | 0.235 | 0.462 |
| 2018 | 81 | 81.000 | 21 | 0.429 | 0.583 |
| 2021 | 154 | 154.000 | 61 | 0.426 | 0.591 |
| 2022 | 175 | 175.000 | 38 | 0.395 | 0.487 |
| 2023 | 190 | 190.000 | 27 | 0.444 | 0.689 |

**Mean AUC 0.562** (unweighted baseline 0.562). Pooled out-of-fold AUC 0.556.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (-0.001, 0.1] | 4 | 0.063 | 0.000 | -0.063 | 4 | 0.063 | 0.000 | -0.063 |
| (0.1, 0.2] | 5 | 0.165 | 0.600 | 0.435 | 5 | 0.165 | 0.600 | 0.435 |
| (0.2, 0.3] | 17 | 0.262 | 0.353 | 0.091 | 17 | 0.262 | 0.353 | 0.091 |
| (0.3, 0.4] | 35 | 0.349 | 0.314 | -0.034 | 35 | 0.349 | 0.314 | -0.034 |
| (0.4, 0.5] | 52 | 0.454 | 0.423 | -0.031 | 52 | 0.454 | 0.423 | -0.031 |
| (0.5, 0.6] | 29 | 0.556 | 0.379 | -0.176 | 29 | 0.556 | 0.379 | -0.176 |
| (0.6, 0.7] | 35 | 0.648 | 0.400 | -0.248 | 35 | 0.648 | 0.400 | -0.248 |
| (0.7, 0.8] | 3 | 0.720 | 0.667 | -0.054 | 3 | 0.720 | 0.667 | -0.054 |
| (0.8, 0.9] | 1 | 0.800 | 1.000 | 0.200 | 1 | 0.800 | 1.000 | 0.200 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 68 | 37.569 | 28 | 0.412 | 0.303 |
| 0.550 | 54 | 29.834 | 24 | 0.444 | 0.320 |
| 0.600 | 39 | 21.547 | 17 | 0.436 | 0.293 |
| 0.650 | 19 | 10.497 | 7 | 0.368 | 0.191 |
| 0.700 | 4 | 2.210 | 3 | 0.750 | 0.301 |
| 0.750 | 1 | 0.552 | 1 | 1.000 | 0.207 |
| 0.800 | 1 | 0.552 | 1 | 1.000 | 0.207 |
| 0.850 | 0 | 0.000 | 0 |  |  |
| 0.900 | 0 | 0.000 | 0 |  |  |
| 0.950 | 0 | 0.000 | 0 |  |  |

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  330
Model:                          Logit   Df Residuals:                      323
Method:                           MLE   Df Model:                            6
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                 0.02341
Time:                        11:21:56   Log-Likelihood:                -210.69
converged:                       True   LL-Null:                       -215.74
Covariance Type:                  HC3   LLR p-value:                    0.1205
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const             -0.5923      0.117     -5.060      0.000      -0.822      -0.363
log1p_total        0.2452      1.058      0.232      0.817      -1.829       2.319
log1p_qib          0.4729      0.514      0.921      0.357      -0.534       1.480
log1p_hni         -0.1889      0.508     -0.372      0.710      -1.184       0.806
log1p_rii         -0.1717      0.296     -0.580      0.562      -0.752       0.408
log_issue_size    -0.0855      0.143     -0.596      0.551      -0.367       0.196
listing_gain      -0.2073      0.171     -1.210      0.226      -0.543       0.129
==================================================================================
```

## Known limitations
- **Decision time: listing-day close** (baseline includes listing gain).
- Benchmark: official Nifty 50 TRI. Six rows exceed +500pp excess (MAZDOCK, NBCC, KAYNES, IRFC, ANANDRATHI, ANGELONE). They're genuine and don't affect the binary label.
- **Survivorship.** 58 seasoned, unflagged IPOs have no 3y target. Observed base rate overstates by ~4pp.
- **3-year embargo.** Test year T trains only on IPOs listed before T-3. Every fold trains on data at least 3 years stale, and early folds are small.
- RHP blocks are placeholders (all NaN) until the RHP batch + reconcile.py run.

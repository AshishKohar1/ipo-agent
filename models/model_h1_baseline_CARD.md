# Model H1 (1y) — baseline — model card

_Generated 2026-09-28 11:21 by `models/framework.py`. Bundle: `models/model_h1_baseline.joblib`._

## Target
`H_label`: 1 if excess_1y_pp (IPO return − Nifty 50 TRI return, listing close → +365d) > 0. Realised 365 days after listing.

## Training data
- Rows loaded 491 → excluded by `exclude_reason` 0 → usable (features + target present, target realised) **490**
- Period: 2010-01-04 to 2025-09-23
- Positive rate: 40.4%
- Final fit: n = 490, effective n = 436.2 (half-life 8 years)

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 0.842 |
| log1p_qib | 0.045 |
| log1p_hni | -0.614 |
| log1p_rii | -0.445 |
| log_issue_size | -0.279 |
| listing_gain | 0.052 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2021 | auc_2022 | auc_2023 | auc_2024 | auc_2025 |
|---|---|---|---|---|---|---|---|
| 2 | 0.516 | 0.560 | 0.450 | 0.673 | 0.426 | 0.552 | 0.482 |
| 3 | 0.517 | 0.556 | 0.454 | 0.679 | 0.427 | 0.560 | 0.467 |
| 5 | 0.521 | 0.548 | 0.454 | 0.673 | 0.437 | 0.560 | 0.483 |
| 8 | 0.525 | 0.545 | 0.461 | 0.670 | 0.447 | 0.552 | 0.494 |
| none | 0.524 | 0.529 | 0.474 | 0.673 | 0.418 | 0.539 | 0.515 |

**Chosen: 8 years.**

## Walk-forward validation (chosen half-life)
Test years [2021, 2022, 2023, 2024, 2025]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 365d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2021 | 190 | 177.097 | 61 | 0.328 | 0.461 |
| 2022 | 204 | 188.242 | 38 | 0.632 | 0.670 |
| 2023 | 265 | 239.582 | 56 | 0.464 | 0.447 |
| 2024 | 303 | 272.448 | 79 | 0.329 | 0.552 |
| 2025 | 359 | 320.576 | 52 | 0.365 | 0.494 |

**Mean AUC 0.525** (unweighted baseline 0.524). Pooled out-of-fold AUC 0.545.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (0.1, 0.2] | 2 | 0.156 | 1.000 | 0.844 | 1 | 0.194 | 1.000 | 0.806 |
| (0.2, 0.3] | 10 | 0.265 | 0.200 | -0.065 | 9 | 0.258 | 0.333 | 0.075 |
| (0.3, 0.4] | 28 | 0.369 | 0.321 | -0.048 | 30 | 0.367 | 0.367 | -0.000 |
| (0.4, 0.5] | 91 | 0.460 | 0.440 | -0.020 | 142 | 0.461 | 0.408 | -0.053 |
| (0.5, 0.6] | 141 | 0.538 | 0.383 | -0.155 | 99 | 0.531 | 0.404 | -0.127 |
| (0.6, 0.7] | 14 | 0.630 | 0.571 | -0.059 | 4 | 0.639 | 0.500 | -0.139 |
| (0.7, 0.8] | 0 |  |  |  | 1 | 0.740 | 0.000 | -0.740 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 155 | 54.196 | 62 | 0.400 | 0.326 |
| 0.550 | 59 | 20.629 | 26 | 0.441 | 0.322 |
| 0.600 | 14 | 4.895 | 8 | 0.571 | 0.326 |
| 0.650 | 2 | 0.699 | 1 | 0.500 | 0.095 |
| 0.700 | 0 | 0.000 | 0 |  |  |
| 0.750 | 0 | 0.000 | 0 |  |  |
| 0.800 | 0 | 0.000 | 0 |  |  |
| 0.850 | 0 | 0.000 | 0 |  |  |
| 0.900 | 0 | 0.000 | 0 |  |  |
| 0.950 | 0 | 0.000 | 0 |  |  |

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  490
Model:                          Logit   Df Residuals:                      483
Method:                           MLE   Df Model:                            6
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                0.008981
Time:                        11:21:56   Log-Likelihood:                -327.60
converged:                       True   LL-Null:                       -330.57
Covariance Type:                  HC3   LLR p-value:                    0.4302
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const             -0.3934      0.093     -4.247      0.000      -0.575      -0.212
log1p_total        0.7764      0.887      0.875      0.382      -0.963       2.516
log1p_qib          0.0264      0.429      0.062      0.951      -0.814       0.867
log1p_hni         -0.4877      0.437     -1.116      0.264      -1.344       0.369
log1p_rii         -0.4253      0.250     -1.700      0.089      -0.916       0.065
log_issue_size    -0.2171      0.120     -1.804      0.071      -0.453       0.019
listing_gain       0.0523      0.121      0.432      0.666      -0.185       0.289
==================================================================================
```

## Known limitations
- **Decision time: listing-day close.** The baseline uses listing gain, so it can't be used before bidding. It answers 'hold from the listing close?', which is where the target starts.
- Benchmark: official Nifty 50 TRI (NSE Indices). IPO prices are dividend-adjusted (Yahoo auto_adjust), so both legs are total return.
- **Survivorship.** 63 seasoned, unflagged IPOs have no target (60 never resolved to a symbol, 3 with no price series). They are mostly wiped-out 2010-11 small caps (median current gain −96%). The observed base rate overstates by ~3pp. `target_MISSES.csv` must be read alongside.
- Baseline features share Model L's collinearity (VIF Total 83). Coefficients on QIB/HNI/RII are conditional on Total.
- Embargo: a training row counts for test year T only if listing + 365d < Jan 1 of T, so the most recent training rows are 1-2 years older than the test year.
- RHP blocks are placeholders (all NaN) until the RHP batch + reconcile.py run.

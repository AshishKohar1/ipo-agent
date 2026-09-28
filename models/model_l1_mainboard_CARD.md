# Model L1 — mainboard (listing gain > 0%) — model card

_Generated 2026-09-28 11:08 by `models/framework.py`. Bundle: `models/model_l1_mainboard.joblib`._

## Target
`L1`: 1 if listing gain > 0% else 0. Realised 0 days after listing.

## Training data
- Rows loaded 652 → excluded by `exclude_reason` 29 → usable (features + target present, target realised) **620**
- Period: 2010-01-04 to 2026-05-08
- Positive rate: 68.4%
- Final fit: n = 620, effective n = 620.0 (half-life none (unweighted))

## Features

| feature | std_coef (final fit) |
|---|---|
| log1p_total | 2.423 |
| log1p_qib | -0.178 |
| log1p_hni | -0.348 |
| log1p_rii | -0.545 |
| log_issue_size | -0.278 |

## Recency half-life selection (walk-forward, mean AUC)

| half_life | mean_auc | pooled_oof_auc | auc_2022 | auc_2023 | auc_2024 | auc_2025 | auc_2026 |
|---|---|---|---|---|---|---|---|
| 2 | 0.724 | 0.810 | 0.712 | 0.799 | 0.840 | 0.841 | 0.427 |
| 3 | 0.731 | 0.807 | 0.708 | 0.803 | 0.833 | 0.831 | 0.479 |
| 5 | 0.746 | 0.804 | 0.705 | 0.804 | 0.825 | 0.824 | 0.573 |
| 8 | 0.748 | 0.802 | 0.702 | 0.804 | 0.824 | 0.816 | 0.594 |
| none | 0.765 | 0.799 | 0.699 | 0.804 | 0.818 | 0.804 | 0.698 |

**Chosen: none (unweighted).**

## Walk-forward validation (chosen half-life)
Test years [2022, 2023, 2024, 2025, 2026]. Train on rows listed before Jan 1 of the test year whose target was realised before it (embargo 0d). Out-of-fold probabilities; weights on training rows only.

| test_year | n_train | eff_n_train | n_test | test_pos_rate | auc |
|---|---|---|---|---|---|
| 2022 | 322 | 322.000 | 38 | 0.684 | 0.699 |
| 2023 | 360 | 360.000 | 58 | 0.793 | 0.804 |
| 2024 | 418 | 418.000 | 80 | 0.762 | 0.818 |
| 2025 | 498 | 498.000 | 102 | 0.696 | 0.804 |
| 2026 | 600 | 600.000 | 20 | 0.400 | 0.698 |

**Mean AUC 0.765** (unweighted baseline 0.765). Pooled out-of-fold AUC 0.799.

## Calibration by probability decile: winner vs unweighted

`class_weight='balanced'` re-weights the classes to 50/50, so probabilities are pulled towards 0.5 and are **not** calibrated to the true base rate. Read thresholds from the table below, not from the raw probability.

| p_bin | n_winner | mean_pred_winner | actual_winner | gap_winner | n_unweighted | mean_pred_unweighted | actual_unweighted | gap_unweighted |
|---|---|---|---|---|---|---|---|---|
| (-0.001, 0.1] | 3 | 0.061 | 0.667 | 0.606 | 3 | 0.061 | 0.667 | 0.606 |
| (0.1, 0.2] | 35 | 0.159 | 0.457 | 0.298 | 35 | 0.159 | 0.457 | 0.298 |
| (0.2, 0.3] | 33 | 0.236 | 0.394 | 0.158 | 33 | 0.236 | 0.394 | 0.158 |
| (0.3, 0.4] | 19 | 0.337 | 0.368 | 0.031 | 19 | 0.337 | 0.368 | 0.031 |
| (0.4, 0.5] | 14 | 0.451 | 0.571 | 0.121 | 14 | 0.451 | 0.571 | 0.121 |
| (0.5, 0.6] | 16 | 0.549 | 0.750 | 0.201 | 16 | 0.549 | 0.750 | 0.201 |
| (0.6, 0.7] | 14 | 0.658 | 0.786 | 0.128 | 14 | 0.658 | 0.786 | 0.128 |
| (0.7, 0.8] | 27 | 0.758 | 0.593 | -0.166 | 27 | 0.758 | 0.593 | -0.166 |
| (0.8, 0.9] | 49 | 0.861 | 0.837 | -0.024 | 49 | 0.861 | 0.837 | -0.024 |
| (0.9, 1.0] | 88 | 0.942 | 0.977 | 0.035 | 88 | 0.942 | 0.977 | 0.035 |

## Threshold table (out-of-fold, chosen half-life)

| threshold | n_fire | fire_pct | hits | hit_rate | hit_rate_lo95 |
|---|---|---|---|---|---|
| 0.500 | 194 | 65.101 | 166 | 0.856 | 0.799 |
| 0.550 | 186 | 62.416 | 160 | 0.860 | 0.803 |
| 0.600 | 178 | 59.732 | 154 | 0.865 | 0.807 |
| 0.650 | 171 | 57.383 | 148 | 0.865 | 0.806 |
| 0.700 | 164 | 55.034 | 143 | 0.872 | 0.812 |
| 0.750 | 154 | 51.678 | 137 | 0.890 | 0.830 |
| 0.800 | 137 | 45.973 | 127 | 0.927 | 0.871 |
| 0.850 | 121 | 40.604 | 115 | 0.950 | 0.896 |
| 0.900 | 88 | 29.530 | 86 | 0.977 | 0.921 |
| 0.950 | 35 | 11.745 | 35 | 1.000 | 0.901 |

## Threshold verification
'Fire at ≥t' promises an out-of-fold hit rate of at least t. It passes if the hit rate among IPOs firing at t is ≥ t on at least 10 fires. A failing threshold is replaced by the lowest threshold that does deliver t (most fires) — never kept.

- **L1 ≥90%**: fires 88, hit rate 97.7% (95% lower bound 92.1%) → **PASS**

Thresholds saved in the bundle: `{'L1': 0.9}`

## Coefficient significance (unweighted Logit, standardised features, robust SEs)
statsmodels' discrete Logit gives identical SEs for HC0/HC1/HC3 — it applies a generic robust sandwich, not the HC3 leverage correction.

```
                           Logit Regression Results                           
==============================================================================
Dep. Variable:                      y   No. Observations:                  620
Model:                          Logit   Df Residuals:                      614
Method:                           MLE   Df Model:                            5
Date:                Mon, 28 Sep 2026   Pseudo R-squ.:                  0.2586
Time:                        11:08:06   Log-Likelihood:                -286.81
converged:                       True   LL-Null:                       -386.83
Covariance Type:                  HC3   LLR p-value:                 2.800e-41
==================================================================================
                     coef    std err          z      P>|z|      [0.025      0.975]
----------------------------------------------------------------------------------
const              1.1669      0.114     10.271      0.000       0.944       1.390
log1p_total        4.5733      1.092      4.187      0.000       2.433       6.714
log1p_qib         -1.1530      0.539     -2.141      0.032      -2.209      -0.097
log1p_hni         -1.1405      0.465     -2.454      0.014      -2.051      -0.230
log1p_rii         -1.1442      0.353     -3.243      0.001      -1.836      -0.453
log_issue_size    -0.3174      0.140     -2.262      0.024      -0.593      -0.042
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

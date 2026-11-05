# H35 — Model H-market, the pre-registered run (2026-11-05)

Specified 13 Oct 2026 (H35); the two open choices settled 5 Nov 2026 (H56) **before** this module existed. **Option B is binding; option A is a diagnostic and cannot change the verdict.** Tercile cut-offs come from the training fold. Scheme C expanding, Y-2 embargo, equal weights, no fitted coefficients.

## excess_1y

491 IPOs with a corrected 1y target, 198 beat the Nifty 50 TRI (40.3%).

### Option B (BINDING)

Scored 427 of 427 test rows; coolest 90, hottest 232.

| tercile | n | beat_pct | mean_excess | median_excess |
|---|---|---|---|---|
| COOLEST | 90 | 51.11 | 16.82 | 1.28 |
| MID | 105 | 50.48 | 12.84 | 0.45 |
| HOTTEST | 232 | 36.64 | 2.1 | -14.26 |

| test_year | n_cool | n_hot | gap_pp | sign |
|---|---|---|---|---|
| 2012 | 8 | 1 | -75.0 | - |
| 2013 | 3 | 0 |  |  |
| 2014 | 2 | 2 | 0.0 | 0 |
| 2015 | 17 | 0 |  |  |
| 2016 | 15 | 0 |  |  |
| 2017 | 2 | 15 | -20.0 | - |
| 2018 | 8 | 8 | 50.0 | + |
| 2019 | 12 | 2 | 75.0 | + |
| 2020 | 1 | 8 | -62.5 | - |
| 2021 | 0 | 59 |  |  |
| 2022 | 4 | 3 | -16.67 | - |
| 2023 | 7 | 38 | -7.14 | - |
| 2024 | 0 | 69 |  |  |
| 2025 | 11 | 27 | 3.03 | + |

### Option A (diagnostic only)

Scored 268 of 427 test rows; coolest 49, hottest 148.

| tercile | n | beat_pct | mean_excess | median_excess |
|---|---|---|---|---|
| COOLEST | 49 | 53.06 | 18.78 | 8.35 |
| MID | 71 | 49.3 | 6.92 | -0.96 |
| HOTTEST | 148 | 36.49 | 2.75 | -13.13 |

| test_year | n_cool | n_hot | gap_pp | sign |
|---|---|---|---|---|
| 2012 | 2 | 0 |  |  |
| 2014 | 0 | 1 |  |  |
| 2015 | 6 | 0 |  |  |
| 2016 | 12 | 0 |  |  |
| 2017 | 1 | 4 | -25.0 | - |
| 2018 | 4 | 5 | 35.0 | + |
| 2019 | 7 | 2 | 71.43 | + |
| 2020 | 1 | 6 | -66.67 | - |
| 2021 | 0 | 44 |  |  |
| 2022 | 1 | 2 | -50.0 | - |
| 2023 | 6 | 25 | -14.67 | - |
| 2024 | 0 | 44 |  |  |
| 2025 | 9 | 15 | -6.67 | - |

### Criteria

| criterion | required | achieved (B, binding) | achieved (A, diagnostic) | pass/fail (B) |
|---|---|---|---|---|
| coolest beats hottest by >= 10pp (pooled) | >= 10.0pp | 14.47 | 16.57 | **PASS** |
| the gap's sign holds in >= 75% of test years | >= 75% | 33% | 29% | **FAIL** |
| one-sided two-proportion test on the pooled gap | p < 0.05 | 0.00883 | 0.02029 | **PASS** |

**Verdict on excess_1y: FAIL** (option B; all three criteria must hold).

## excess_3y  (secondary)

331 IPOs with a corrected 3y target, 119 beat the Nifty 50 TRI (36.0%).

### Option B (BINDING)

Scored 267 of 267 test rows; coolest 79, hottest 107.

| tercile | n | beat_pct | mean_excess | median_excess |
|---|---|---|---|---|
| COOLEST | 79 | 44.3 | 32.56 | -25.7 |
| MID | 81 | 41.98 | 28.01 | -27.38 |
| HOTTEST | 107 | 39.25 | 12.68 | -25.69 |

| test_year | n_cool | n_hot | gap_pp | sign |
|---|---|---|---|---|
| 2012 | 8 | 1 | 50.0 | + |
| 2013 | 3 | 0 |  |  |
| 2014 | 2 | 2 | -50.0 | - |
| 2015 | 17 | 0 |  |  |
| 2016 | 15 | 0 |  |  |
| 2017 | 2 | 15 | -20.0 | - |
| 2018 | 8 | 8 | 50.0 | + |
| 2019 | 12 | 2 | 75.0 | + |
| 2020 | 1 | 8 | -75.0 | - |
| 2021 | 0 | 59 |  |  |
| 2022 | 4 | 3 | 50.0 | + |
| 2023 | 7 | 9 | -38.1 | - |

### Option A (diagnostic only)

Scored 158 of 267 test rows; coolest 40, hottest 67.

| tercile | n | beat_pct | mean_excess | median_excess |
|---|---|---|---|---|
| COOLEST | 40 | 50.0 | 43.46 | -0.33 |
| MID | 51 | 35.29 | 14.35 | -30.6 |
| HOTTEST | 67 | 41.79 | 13.23 | -25.59 |

| test_year | n_cool | n_hot | gap_pp | sign |
|---|---|---|---|---|
| 2012 | 2 | 0 |  |  |
| 2014 | 0 | 1 |  |  |
| 2015 | 6 | 0 |  |  |
| 2016 | 12 | 0 |  |  |
| 2017 | 1 | 4 | -50.0 | - |
| 2018 | 4 | 5 | 35.0 | + |
| 2019 | 7 | 2 | 71.43 | + |
| 2020 | 1 | 6 | -83.33 | - |
| 2021 | 0 | 44 |  |  |
| 2022 | 1 | 2 | 0.0 | 0 |
| 2023 | 6 | 3 | -50.0 | - |

### Criteria

| criterion | required | achieved (B, binding) | achieved (A, diagnostic) | pass/fail (B) |
|---|---|---|---|---|
| coolest beats hottest by >= 10pp (pooled) | >= 10.0pp | 5.05 | 8.21 | **FAIL** |
| the gap's sign holds in >= 75% of test years | >= 75% | 50% | 33% | **FAIL** |
| one-sided two-proportion test on the pooled gap | p < 0.05 | 0.24466 | 0.20439 | **FAIL** |

**Verdict on excess_3y: FAIL** (option B; all three criteria must hold).


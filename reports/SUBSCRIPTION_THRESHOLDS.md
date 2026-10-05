# Firing thresholds in subscription terms

Derived by `derive_subscription_thresholds.py` on 2026-10-05. **No model, no calibrator** — a monotone threshold on Total subscription, scored against the realised listing gain.

## L1 — listing gain > 0%, promise 90%

620 mainboard IPOs, 2010-01-04 to 2026-05-08. Base rate 68.4%.

| Measurement | Threshold | Fires | Hits | Delivered | Wilson 95% LB |
|---|---|---|---|---|---|
| **In-sample** (derived and measured on all data) | **16.86x** | 284 | 256 | **90.1%** | 86.1% |
| **Walk-forward** (derived on prior years, measured on the next) | per year | 300 | 259 | **86.3%** | 82.0% |

**The flattery is +3.8 percentage points.** The in-sample figure is an upper bound; the walk-forward figure is the expectation.

### Per test year (threshold derived on prior years only)

| Year | Threshold | IPOs | Fires | Hits | Delivered |
|---|---|---|---|---|---|
| 2015 | 5.43x | 19 | 7 | 6 | 86% |
| 2016 | 5.43x | 27 | 17 | 13 | 76% |
| 2017 | 11.63x | 36 | 16 | 16 | 100% |
| 2018 | 8.59x | 24 | 8 | 7 | 88% |
| 2019 | 8.59x | 16 | 7 | 7 | 100% |
| 2020 | 5.43x | 14 | 10 | 9 | 90% |
| 2021 | 5.43x | 63 | 44 | 38 | 86% |
| 2022 | 5.43x | 38 | 15 | 13 | 87% |
| 2023 | 6.14x | 58 | 47 | 40 | 85% |
| 2024 | 8.59x | 80 | 61 | 52 | 85% |
| 2025 | 11.63x | 102 | 65 | 57 | 88% |
| 2026 | 11.88x | 20 | 3 | 1 | 33% |

### Calibrating the gap away

Deriving at an internal target of **95%** makes the pooled walk-forward delivery **90.2%** on 214 fires — at or above the 90% promise.

**Shipped threshold: Total >= 28.39x** (derived on all data at that internal target; fires on 242 of 620 IPOs, 39.0%).

### What it costs in opportunities

| Year | IPOs | Fires | Hits | Delivered |
|---|---|---|---|---|
| 2010 | 67 | 15 | 15 | 100% |
| 2011 | 37 | 1 | 1 | 100% |
| 2012 | 11 | 2 | 2 | 100% |
| 2013 | 3 | 0 | 0 | — |
| 2014 | 5 | 3 | 3 | 100% |
| 2015 | 19 | 5 | 4 | 80% |
| 2016 | 27 | 10 | 10 | 100% |
| 2017 | 36 | 16 | 16 | 100% |
| 2018 | 24 | 4 | 4 | 100% |
| 2019 | 16 | 6 | 6 | 100% |
| 2020 | 14 | 8 | 8 | 100% |
| 2021 | 63 | 32 | 31 | 97% |
| 2022 | 38 | 8 | 8 | 100% |
| 2023 | 58 | 32 | 31 | 97% |
| 2024 | 80 | 45 | 42 | 93% |
| 2025 | 102 | 52 | 48 | 92% |
| 2026 | 20 | 3 | 1 | 33% |

## L2 — listing gain > 10%, promise 80%

620 mainboard IPOs, 2010-01-04 to 2026-05-08. Base rate 43.5%.

| Measurement | Threshold | Fires | Hits | Delivered | Wilson 95% LB |
|---|---|---|---|---|---|
| **In-sample** (derived and measured on all data) | **26.66x** | 248 | 200 | **80.6%** | 75.3% |
| **Walk-forward** (derived on prior years, measured on the next) | per year | 244 | 185 | **75.8%** | 70.1% |

**The flattery is +4.8 percentage points.** The in-sample figure is an upper bound; the walk-forward figure is the expectation.

### Per test year (threshold derived on prior years only)

| Year | Threshold | IPOs | Fires | Hits | Delivered |
|---|---|---|---|---|---|
| 2015 | 31.11x | 19 | 5 | 4 | 80% |
| 2016 | 31.11x | 27 | 9 | 7 | 78% |
| 2017 | 43.84x | 36 | 14 | 12 | 86% |
| 2018 | 26.51x | 24 | 4 | 3 | 75% |
| 2019 | 29.55x | 16 | 6 | 6 | 100% |
| 2020 | 24.47x | 14 | 9 | 8 | 89% |
| 2021 | 19.29x | 63 | 37 | 30 | 81% |
| 2022 | 18.03x | 38 | 10 | 8 | 80% |
| 2023 | 18.03x | 58 | 36 | 29 | 81% |
| 2024 | 17.41x | 80 | 51 | 41 | 80% |
| 2025 | 17.20x | 102 | 60 | 36 | 60% |
| 2026 | 26.51x | 20 | 3 | 1 | 33% |

### Calibrating the gap away

Deriving at an internal target of **87%** makes the pooled walk-forward delivery **80.8%** on 156 fires — at or above the 80% promise.

**Shipped threshold: Total >= 54.02x** (derived on all data at that internal target; fires on 167 of 620 IPOs, 26.9%).

### What it costs in opportunities

| Year | IPOs | Fires | Hits | Delivered |
|---|---|---|---|---|
| 2010 | 67 | 4 | 4 | 100% |
| 2011 | 37 | 0 | 0 | — |
| 2012 | 11 | 1 | 1 | 100% |
| 2013 | 3 | 0 | 0 | — |
| 2014 | 5 | 2 | 2 | 100% |
| 2015 | 19 | 1 | 1 | 100% |
| 2016 | 27 | 7 | 6 | 86% |
| 2017 | 36 | 11 | 9 | 82% |
| 2018 | 24 | 4 | 3 | 75% |
| 2019 | 16 | 4 | 4 | 100% |
| 2020 | 14 | 7 | 7 | 100% |
| 2021 | 63 | 23 | 21 | 91% |
| 2022 | 38 | 3 | 3 | 100% |
| 2023 | 58 | 21 | 20 | 95% |
| 2024 | 80 | 37 | 34 | 92% |
| 2025 | 102 | 41 | 31 | 76% |
| 2026 | 20 | 1 | 1 | 100% |

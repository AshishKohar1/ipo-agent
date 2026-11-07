# H60 result — the combined Model H fit. **FAIL.** (2026-11-09)

Run exactly as pre-registered in `reports/H60_PREREGISTRATION.md`, which was written and
committed on 2026-11-08 **before** `run_h60.py` existed, and approved by the user before
the fit ran. Thirteen variables, H30's method, H29's bar — none of them changed after the
number was seen.

## The verdict

| criterion (H29, unchanged) | required | achieved | pass/fail |
|---|---|---|---|
| picks in the top-20% band | >= 50 | **87** | **PASS** |
| hit rate vs Nifty 50 TRI, first year | >= 54% | **44.83%** | **FAIL** |
| Wilson 95% lower bound above the base rate | > 42.76% | **34.82%** | **FAIL** |

**H29: FAIL.** Pooled out-of-sample AUC **0.5239** on
435 scored IPOs; 39 of 87 band picks beat the index.

The band did not merely miss the 54% bar — at 44.83% it came in **below the 42.76% base
rate plus nothing**, i.e. essentially at chance, and its Wilson lower bound (34.82%) sits
**8 points below** the base rate rather than above it. Two of the three conditions fail,
and the one that passes is only the sample-size condition.

## Per test year

| year | n_train | n_train_outcomes | n_vars_fitted | n_test | auc | band_picks | band_hits | band_hit_rate | base_rate | note |
|---|---|---|---|---|---|---|---|---|---|---|
| 2010 | 0 |  |  | 45 |  |  |  |  |  | too little history to train |
| 2011 | 0 |  |  | 18 |  |  |  |  |  | too little history to train |
| 2012 | 45 | 6.0 | 1.0 | 8 | 0.5 | 2.0 | 1.0 | 0.5 | 0.25 |  |
| 2013 | 63 | 12.0 | 1.0 | 3 |  | 1.0 | 1.0 | 1.0 | 1.0 |  |
| 2014 | 71 | 14.0 | 1.0 | 5 | 0.5 | 1.0 | 1.0 | 1.0 | 0.8 |  |
| 2015 | 74 | 17.0 | 1.0 | 17 | 0.4583 | 3.0 | 2.0 | 0.6667 | 0.5294 |  |
| 2016 | 79 | 21.0 | 2.0 | 25 | 0.4351 | 5.0 | 3.0 | 0.6 | 0.56 |  |
| 2017 | 96 | 30.0 | 3.0 | 34 | 0.5625 | 7.0 | 2.0 | 0.2857 | 0.2353 |  |
| 2018 | 121 | 44.0 | 4.0 | 22 | 0.442 | 4.0 | 1.0 | 0.25 | 0.3636 |  |
| 2019 | 155 | 52.0 | 5.0 | 16 | 0.6417 | 3.0 | 3.0 | 1.0 | 0.625 |  |
| 2020 | 177 | 60.0 | 6.0 | 14 | 0.55 | 3.0 | 2.0 | 0.6667 | 0.7143 |  |
| 2021 | 193 | 70.0 | 7.0 | 63 | 0.5299 | 13.0 | 5.0 | 0.3846 | 0.3492 |  |
| 2022 | 207 | 80.0 | 8.0 | 38 | 0.4866 | 8.0 | 4.0 | 0.5 | 0.6316 |  |
| 2023 | 270 | 102.0 | 10.0 | 57 | 0.4249 | 11.0 | 4.0 | 0.3636 | 0.4561 |  |
| 2024 | 308 | 126.0 | 12.0 | 80 | 0.4363 | 16.0 | 3.0 | 0.1875 | 0.325 |  |
| 2025 | 365 | 152.0 | 13.0 | 53 | 0.5174 | 11.0 | 7.0 | 0.6364 | 0.3774 |  |

The variable cap is H30's own: one variable per ten beat-Nifty outcomes in the training
fold. Only the 2025 fold fitted all thirteen; 2012-2015 fitted one. That is the existing
rule, stated in the pre-registration, and it was not relaxed to help the fit.

**A correction to my own first reading of this table.** I initially wrote that eight of the
measurable test years came in below their own base rate. That is wrong, and the opposite way
round: **8 of the 14 measurable years are ABOVE** their base rate, 5 below and 1 equal.

| band hit rate vs that year's base rate | years |
|---|---|
| above | 2012, 2014, 2015, 2016, 2017, 2019, 2021, 2025 |
| below | 2018, 2020, 2022, 2023, 2024 |
| equal | 2013 |

So the per-year picture is mixed-to-favourable while the **pooled** band fails. That is not
a contradiction, and it is worth stating precisely because it is the same structural fact
H35 ran into. The pooled band is the top 20% of probabilities **across all years at once**,
and the model's probabilities are not comparable between years with different base rates —
so the pooled band is not one pick from each year. Where the 87 pooled picks actually came
from:

| year | pooled picks | hits | hit rate |
|---|---|---|---|
| 2016 | 5 | 2 | 0.400 |
| 2017 | 5 | 2 | 0.400 |
| 2018 | 3 | 1 | 0.333 |
| 2020 | 2 | 2 | 1.000 |
| 2021 | 19 | 9 | 0.474 |
| 2022 | 18 | 11 | 0.611 |
| 2023 | 6 | 2 | 0.333 |
| 2024 | 3 | 1 | 0.333 |
| 2025 | 26 | 9 | 0.346 |

Three years — 2021, 2022 and 2025 — supply **63 of the 87 picks**, and 2025 alone supplies
26 at a 34.6% hit rate. The model scores hot vintages high, and hot vintages are where the
beat-the-index rate is lowest. That is H35's finding reappearing inside the per-IPO fit,
which is consistent with four of the seven firm variables on the pre-registered list being
market-heat variables — a point the pre-registration recorded in advance.

H29 is the pooled bar, fixed before any of this was known, and it is the bar that was
applied. The per-year table above does not change the verdict and was not used to.

## What this closes

Under decision 4 of the 6 November brief: **Model H is closed as display-only.**

All three claims ever made for Model H have now been measured against bars set in advance,
and all three failed:

| claim | bar | result |
|---|---|---|
| **H29** per-IPO scorecard | top 20%, >=50 picks, >=54%, Wilson lo > base | **FAIL** — AUC 0.5338; 83 picks, 53.01%, Wilson 42.38% vs base 43.13% |
| **H35** cohort / market heat | gap >=10pp, sign in >=75% of test years, p<0.05 | **FAIL** — 14.47pp PASS, sign 33% FAIL, p=0.00883 PASS |
| **H60** combined firm + valuation | H29, unchanged | **FAIL** — 87 picks PASS, 44.83% FAIL, Wilson 34.82% vs base 42.76% FAIL |

The combined fit was the best remaining case: the widest variable set the stability
analysis admitted, on the longest window, with the aggregator reconciled against a second
source for the first time. It scored 0.5239.

No further fit is authorised, and no threshold, email or decision path changes as a result
of this run. Model L is untouched — it is a different signal, and the correlation between
listing gain and long-run CAGR is 0.218.

## What was NOT done after seeing the result

No bar was adjusted, no variable was added or dropped, no window was re-chosen, no band
was re-cut, and the fit was not re-run with a different seed or scheme. The pre-registration
is in git history at commit `b4eb78e`, before `run_h60.py` was written.

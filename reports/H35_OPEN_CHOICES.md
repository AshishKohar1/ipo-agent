# H35 — two choices the pre-registered spec does not settle (2026-11-02)

H35 was written on 13 Oct 2026 **before** any result, and that is its whole value. Running
it requires two decisions the spec is silent on, and both change the answer. Per the brief,
nothing has been run.

## The spec, for reference

Six stable heat variables, **and only these**: `ipo_count_prior_3m`, `ipo_count_prior_6m`,
`mean_listing_gain_prior_3m`, `nifty_tri_ret_12m`, `listing_gain_minus_sector_day`,
`turnover_x_issue_size`. Each standardised **inside the training fold only**, signed so
higher = hotter, averaged with **equal weights**. Walk-forward **scheme C (expanding) with
the Y-2 embargo** — which `model_h_stability.windows(years, "C", embargo=True)` already
implements, so that part needs no decision.

Pass requires all three: coolest third beats the TRI **≥10pp more often** than the hottest
third, pooled; the gap's sign holds in **≥75% of test years**; a one-sided two-proportion
test gives **p < 0.05**.

## Choice 1 — missing values

Coverage on the 491 rows that have a corrected 1y target:

| variable | non-null | coverage |
|---|---|---|
| `ipo_count_prior_3m` | 491 | 100.0% |
| `ipo_count_prior_6m` | 491 | 100.0% |
| `nifty_tri_ret_12m` | 491 | 100.0% |
| `mean_listing_gain_prior_3m` | 485 | 98.8% |
| `turnover_x_issue_size` | 481 | 98.0% |
| **`listing_gain_minus_sector_day`** | **288** | **58.7%** |

| | rows |
|---|---|
| all six present | **284 of 491** |
| at least five present | 479 |
| the other five, all present | 475 |

The spec says "averaged with equal weights" and never says what an average of six things is
when one is absent. It matters twice over, because the gap is **not spread evenly across
time** — complete-case rows by listing year:

| 2010 | 2011 | 2012 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | 3 | 2 | 1 | 6 | 15 | 14 | 9 | 9 | 10 | 46 | 29 | 39 | 53 | 35 |

2013 disappears entirely and 2012 and 2014 fall to 2 and 1 rows. Criterion 2 is a count of
**test years** whose sign agrees, so a scheme that empties the early years can fail — or
pass — on three-row years. That is the opposite of a robustness check.

### Options

| | option | effect | cost |
|---|---|---|---|
| **A** | **Complete cases only** — drop any row missing any of the six | 284 rows, honest to "average of six" | loses 42% of the sample and most of 2012-2015; criterion 2 then rests on years with 1-6 rows |
| **B** | **Average the variables that are present** (mean of available z-scores) | 491 rows, all test years intact | the score is a 6-variable average for some rows and a 5-variable one for others, so the terciles are not one quantity |
| **C** | **Impute the missing z as 0** (the training fold's own mean) | 491 rows, score always a 6-term average | treats "unknown heat" as "average heat", which drags 42% of rows toward the middle tercile and weakens the contrast the test is looking for |
| **D** | **Drop `listing_gain_minus_sector_day`, run on five** | 475 rows, all years, one quantity throughout | changes the pre-registered variable set — the one thing H35 exists to prevent |

**My recommendation: B, with A reported beside it.** B keeps every test year, so criterion 2
measures what it was written to measure, and the only distortion is that some scores average
five terms instead of six — all six are measures of the same thing and are positively
correlated by construction, which is precisely the argument H35 already makes for equal
weights. Running A as well costs nothing and shows whether the answer depends on the choice.
If A and B disagree, that disagreement is the finding and neither should be reported alone.

**D is defensible but is a spec change**, and should be recorded as an amendment to H35
rather than slipped in as a missing-value policy.

## Choice 2 — where the tercile cuts come from

The spec fixes standardisation as in-fold. It does not say where the **coolest/hottest third**
boundaries are cut, and the options are not equivalent:

| | option | note |
|---|---|---|
| **i** | Cut on the **training fold's** score distribution | consistent with "inside the training fold only"; a test year that is hot throughout can land entirely in one tercile — which is arguably the correct behaviour, since the claim is about market heat |
| **ii** | Cut **within each test year** | forces a third into each band every year, so the bands measure relative heat *within* a year and the cross-year claim is lost |
| **iii** | Cut on **all pooled test rows** | uses test-period information to define the bands — leakage, and it is the one option the walk-forward exists to prevent |

**My recommendation: i.** It is the only one consistent with the spec's own in-fold rule, and
iii leaks. ii answers a different question from the one H35 asks.

## What is not in doubt

Scheme C with the Y-2 embargo, equal weights, no fitted coefficients, the three pass
criteria, and the display-only LOW/MID/HIGH output if it passes. Those are all specified and
will not be touched.

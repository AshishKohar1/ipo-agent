# H59 Task 1 - the valuation block: primary, second source, rule 2, ratios (2026-11-08)

Mainboard only (H33), 482 IPOs. Primary is the aggregator (H5); the second source is
Tickertape where it holds the SAME fiscal year (H58), then the RHP, then for P/B the H54
routes. Chittorgarh and IPOMatrix share a parent and are not independent, so a Chittorgarh
value alone is single-source (hard rule 2, H26).

## The read

| item | value |
|---|---|
| mainboard IPOs | 482 |
| resolved on Tickertape (exact normalised name, H28) | **455** |
| Tickertape pages read | 455, HTTP 200, **0 errors** |
| Tickertape annual rows | 3,589 (median 8 years per company) |
| gap between requests | 3.2 s; robots.txt re-read at the start of the run |
| block rows | 10,122 = 482 IPOs x 21 variables |

## Coverage (the table the brief asks for)

| variable | primary n | reconciled n | single-source n | withheld n | coverage 2019+ |
|---|---|---|---|---|---|
| `borrowings_cr` | 425 | 148 | 133 | 144 | 50.3% |
| `cash_cr` | 0 | 0 | 0 | 0 | 94.5% |
| `debt_equity` | 242 | 0 | 0 | 240 | 39.7% |
| `ebitda_cr` | 226 | 100 | 43 | 83 | 31.8% |
| `ebitda_margin_pct` | 138 | 0 | 0 | 344 | 30.3% |
| `ev_ebitda` | 31 | 0 | 0 | 451 | 8.8% |
| `issue_size_cr` | 482 | 0 | 482 | 0 | 100.0% |
| `issue_size_over_net_worth` | 390 | 0 | 0 | 92 | 77.6% |
| `market_cap_at_offer_cr` | 336 | 0 | 336 | 0 | 77.3% |
| `mcap_over_total_income` | 315 | 0 | 0 | 167 | 71.2% |
| `net_worth_cr` | 475 | 259 | 134 | 82 | 78.5% |
| `pat_cr` | 481 | 285 | 124 | 72 | 84.8% |
| `pat_margin_pct_on_total_income` | 381 | 0 | 0 | 101 | 78.8% |
| `pb_post_issue` | 19 | 0 | 0 | 463 | 2.4% |
| `pb_pre_issue` | 147 | 0 | 0 | 335 | 35.2% |
| `pe_post` | 198 | 16 | 104 | 78 | 36.1% |
| `pe_pre` | 250 | 78 | 128 | 44 | 62.1% |
| `roce_pct` | 213 | 0 | 213 | 0 | 59.1% |
| `roe_pct` | 356 | 57 | 0 | 219 | 45.2% |
| `ronw_pct` | 326 | 125 | 149 | 52 | 62.1% |
| `total_income_cr` | 480 | 304 | 131 | 45 | 91.5% |

## Every status, per variable

| variable | derived_no_stated_check | h54_route | no_primary | reconciled | second_source_only | single_source_unverified | withheld_by_h54_route | withheld_disagreement | withheld_missing_input | withheld_non_positive_denominator |
|---|---|---|---|---|---|---|---|---|---|---|
| `borrowings_cr` | 0 | 0 | 57 | 148 | 0 | 133 | 0 | 144 | 0 | 0 |
| `cash_cr` | 0 | 0 | 128 | 0 | 354 | 0 | 0 | 0 | 0 | 0 |
| `debt_equity` | 242 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 239 | 1 |
| `ebitda_cr` | 0 | 0 | 256 | 100 | 0 | 43 | 0 | 83 | 0 | 0 |
| `ebitda_margin_pct` | 138 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 344 | 0 |
| `ev_ebitda` | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 451 | 0 |
| `issue_size_cr` | 0 | 0 | 0 | 0 | 0 | 482 | 0 | 0 | 0 | 0 |
| `issue_size_over_net_worth` | 390 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 89 | 3 |
| `market_cap_at_offer_cr` | 0 | 0 | 146 | 0 | 0 | 336 | 0 | 0 | 0 | 0 |
| `mcap_over_total_income` | 315 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 167 | 0 |
| `net_worth_cr` | 0 | 0 | 7 | 259 | 0 | 134 | 0 | 82 | 0 | 0 |
| `pat_cr` | 0 | 0 | 1 | 285 | 0 | 124 | 0 | 72 | 0 | 0 |
| `pat_margin_pct_on_total_income` | 381 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 101 | 0 |
| `pb_post_issue` | 0 | 19 | 0 | 0 | 0 | 0 | 463 | 0 | 0 | 0 |
| `pb_pre_issue` | 0 | 147 | 0 | 0 | 0 | 0 | 335 | 0 | 0 | 0 |
| `pe_post` | 0 | 0 | 284 | 16 | 0 | 104 | 0 | 78 | 0 | 0 |
| `pe_pre` | 0 | 0 | 232 | 78 | 0 | 128 | 0 | 44 | 0 | 0 |
| `roce_pct` | 0 | 0 | 269 | 0 | 0 | 213 | 0 | 0 | 0 | 0 |
| `roe_pct` | 206 | 0 | 0 | 57 | 0 | 0 | 0 | 93 | 124 | 2 |
| `ronw_pct` | 0 | 0 | 156 | 125 | 0 | 149 | 0 | 52 | 0 | 0 |
| `total_income_cr` | 0 | 0 | 2 | 304 | 0 | 131 | 0 | 45 | 0 | 0 |

## What the disagreements actually are — 693 values NULLed under rule 2

| variable | second source | n withheld | median gap | 75th | max |
|---|---|---|---|---|---|
| `borrowings_cr` | tickertape | 144 | 28.9% | 75.6% | 100.0% |
| `roe_pct` | chittorgarh stated | 93 | 16.0% | 27.9% | 198.9% |
| `ebitda_cr` | tickertape | 83 | 16.1% | 39.9% | 178.7% |
| `net_worth_cr` | tickertape | 82 | 15.7% | 31.5% | 164.0% |
| `pe_post` | rhp | 78 | 21.5% | 28.9% | 99.3% |
| `pat_cr` | tickertape 67, rhp 5 | 72 | 29.3% | 81.9% | 186.7% |
| `ronw_pct` | rhp | 52 | 88.0% | 106.6% | 200.0% |
| `total_income_cr` | tickertape 44, rhp 1 | 45 | 10.3% | 33.1% | 97.8% |
| `pe_pre` | rhp | 44 | 18.2% | 36.1% | 120.1% |

**These are not rounding gaps.** The median is 10–29% on the aggregates, so the two sources
are reporting different quantities, and rule 2 is doing exactly what it exists for. Two
causes measured, not guessed:

**1. Reporting basis is NOT the main cause.** Tickertape states `consolidated` or
`standalone` per year. Disagreement rate by basis, over the 1,718 aggregate values
Tickertape could check:

| Tickertape basis | values | disagreed |
|---|---|---|
| consolidated | 1,297 | **26.3%** |
| standalone | 414 | **18.6%** |
| earnings-consolidated | 6 | 33.3% |

Consolidated figures disagree *more*, not less, so the basis explains part of the spread
but is not the driver. The likelier driver is that the aggregator's figures are the
**RHP-era restated** numbers for the year before the issue, while Tickertape carries the
company's **as-reported** history for the same year end. That is a hypothesis, not a
measurement, and it is stated as such.

**2. The RHP `ronw_fy1` reader is defective, and that is why RoNW's gaps are the worst.**
Across the 362 companies with an RHP RoNW:

| symptom | n |
|---|---|
| value is exactly `3.00` | **86** |
| value is negative | 28 |
| value above 100 | 2 |

A quarter of the readings sitting on exactly 3.00 is not a distribution of returns on net
worth; it is a column index or a footnote marker captured as the value. And of the 289
RoNW rows the RHP seconded, **11 are exact sign flips** of the aggregator's figure (Ortel
+243.70 vs −243.70; Coffee Day +32.62 vs −32.62) and **25 carry the 3.00 artefact** —
together **23 of the 52 withholdings**.

So RoNW's withholdings are caused mainly by the second source, not by the primary.
Nothing was repaired here: the values stay NULL with both figures logged, which is rule 2
as written. The reader itself is a Task 5 item ("fix the top failure reasons per reader
without lowering precision"), and this is the measurement that says where to start.

## Where the block is thin, and why

| variable | coverage 2019+ | the reason, stated |
|---|---|---|
| `ev_ebitda` | **8.8%** | needs EBITDA **and** cash. Cash is on no aggregator page; it exists for 354 IPOs from a second source only, and EBITDA for 226. Cash is never assumed to be zero, so the ratio is withheld 451 times |
| `pb_post_issue` | **2.4%** | the H54 route needs a post-issue NAV per share, which 463 of 482 filings do not yield. Withheld by the route, not recomputed here |
| `ebitda_margin_pct` | 30.3% | EBITDA appears only on the newer aggregator pages (226 of 482) |
| `ebitda_cr` | 31.8% | as above |
| `pb_pre_issue` | 35.2% | H54's pre-issue route fires for 147 |
| `pe_post` | 36.1% | the aggregator states a post-issue P/E for 198; 78 of those disagree with offer-price-over-RHP-EPS by more than 5% |
| `debt_equity` | 39.7% | derived for 242; the aggregator states its own D/E almost nowhere, so 242 are `derived_no_stated_check` and 239 lack an input |

`cash_cr` shows **0 primary** by construction: the aggregator does not publish it at all, so
every one of its 354 values is `second_source_only` and labelled as such.

`issue_size_cr`, `market_cap_at_offer_cr` and `roce_pct` are `single_source_unverified` for
every row: no permitted second source publishes them for the pre-issue year. They are kept
and flagged, per H26, and must never be described as reconciled.

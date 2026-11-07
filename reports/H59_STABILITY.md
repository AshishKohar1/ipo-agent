# H59 valuation variables - Model H stability (2026-11-08)

Task 2 of the 6 November brief. **Analysis only.** No variable set is chosen here, no window is chosen and no model is fitted. Every rule, window, IV floor and label is `model_h_stability`'s own, imported rather than reimplemented.

- 498 mainboard IPOs with a corrected 1y target
- 19 valuation variables admissible under Model H's own floors (>= 30 non-null, >= 2 distinct values)
- a value the rule-2 reconciliation withheld is NULL here, never its pre-withholding figure

Below those floors, so never measured: `ev_ebitda`, `pb_post_issue`

## Scheme A

| variable | coverage 2019+ | verdict | IV | sign | median AUC |
|---|---|---|---|---|---|
| `ebitda_cr` | 22.7% | STABLE | 0.4047 | -1 | 0.5626 |
| `debt_equity` | 31.8% | STABLE | 0.3688 | -1 | 0.5235 |
| `ebitda_margin_pct` | 21.8% | STABLE | 0.3016 | -1 | 0.5747 |
| `net_worth_cr` | 63.6% | STABLE | 0.2583 | -1 | 0.5416 |
| `issue_size_over_net_worth` | 62.6% | STABLE | 0.2032 | -1 | 0.5417 |
| `issue_size_cr` | 81.9% | STABLE | 0.1988 | -1 | 0.4875 |
| `market_cap_at_offer_cr` | 58.9% | STABLE | 0.1355 | 1 | 0.5278 |
| `mcap_over_total_income` | 54.2% | STABLE | 0.1313 | 1 | 0.5000 |
| `cash_cr` | 76.6% | STABLE | 0.1231 | -1 | 0.4591 |
| `roce_pct` | 45.5% | STABLE | 0.0933 | -1 | 0.5000 |
| `borrowings_cr` | 41.1% | CURRENT | 0.1885 | -1 | 0.5625 |
| `roe_pct` | 38.6% | CURRENT | 0.1679 | 1 | 0.5223 |
| `pat_margin_pct_on_total_income` | 63.9% | NOISE | 0.2758 | 1 | 0.4902 |
| `total_income_cr` | 74.8% | NOISE | 0.2611 | 1 | 0.4167 |
| `pat_cr` | 68.8% | NOISE | 0.2529 | -1 | 0.4841 |
| `ronw_pct` | 43.6% | NOISE | 0.1179 | 1 | 0.5000 |
| `pb_pre_issue` | 36.1% | NOISE | 0.0975 | -1 | 0.5000 |
| `pe_post` | 18.4% | NOISE | 0.0000 | -1 | 0.5000 |
| `pe_pre` | 43.0% | NOISE | 0.0000 | -1 | 0.5000 |

## Scheme B

| variable | coverage 2019+ | verdict | IV | sign | median AUC |
|---|---|---|---|---|---|
| `debt_equity` | 31.8% | STABLE | 0.4093 | -1 | 0.5167 |
| `ebitda_margin_pct` | 21.8% | STABLE | 0.3090 | -1 | 0.5500 |
| `net_worth_cr` | 63.6% | STABLE | 0.3025 | -1 | 0.4758 |
| `ebitda_cr` | 22.7% | STABLE | 0.3015 | -1 | 0.6071 |
| `issue_size_over_net_worth` | 62.6% | STABLE | 0.2600 | -1 | 0.5353 |
| `borrowings_cr` | 41.1% | STABLE | 0.2366 | -1 | 0.5434 |
| `issue_size_cr` | 81.9% | STABLE | 0.2152 | -1 | 0.4722 |
| `market_cap_at_offer_cr` | 58.9% | STABLE | 0.1449 | 1 | 0.5136 |
| `cash_cr` | 76.6% | STABLE | 0.1252 | -1 | 0.4732 |
| `roce_pct` | 45.5% | STABLE | 0.0583 | -1 | 0.5000 |
| `pat_cr` | 68.8% | CURRENT | 0.3576 | 1 | 0.4857 |
| `pat_margin_pct_on_total_income` | 63.9% | CURRENT | 0.3145 | 1 | 0.5433 |
| `roe_pct` | 38.6% | CURRENT | 0.1494 | 1 | 0.5167 |
| `mcap_over_total_income` | 54.2% | CURRENT | 0.1037 | 1 | 0.4878 |
| `total_income_cr` | 74.8% | NOISE | 0.2898 | 1 | 0.4167 |
| `pb_pre_issue` | 36.1% | NOISE | 0.1383 | -1 | 0.4970 |
| `ronw_pct` | 43.6% | NOISE | 0.0701 | 1 | 0.5000 |
| `pe_post` | 18.4% | NOISE | 0.0000 | -1 | 0.5000 |
| `pe_pre` | 43.0% | NOISE | 0.0000 | -1 | 0.5000 |

## Scheme C

| variable | coverage 2019+ | verdict | IV | sign | median AUC |
|---|---|---|---|---|---|
| `ebitda_cr` | 22.7% | STABLE | 0.3914 | -1 | 0.5348 |
| `issue_size_over_net_worth` | 62.6% | STABLE | 0.3311 | -1 | 0.5149 |
| `pat_margin_pct_on_total_income` | 63.9% | STABLE | 0.3049 | -1 | 0.5068 |
| `ebitda_margin_pct` | 21.8% | STABLE | 0.3000 | -1 | 0.5665 |
| `total_income_cr` | 74.8% | STABLE | 0.2914 | 1 | 0.4583 |
| `debt_equity` | 31.8% | STABLE | 0.2394 | -1 | 0.4739 |
| `mcap_over_total_income` | 54.2% | STABLE | 0.1895 | 1 | 0.5000 |
| `roce_pct` | 45.5% | STABLE | 0.1042 | -1 | 0.5000 |
| `cash_cr` | 76.6% | STABLE | 0.0725 | -1 | 0.5139 |
| `ronw_pct` | 43.6% | STABLE | 0.0703 | 1 | 0.5000 |
| `net_worth_cr` | 63.6% | CURRENT | 0.3004 | -1 | 0.4833 |
| `pat_cr` | 68.8% | CURRENT | 0.2667 | 1 | 0.5015 |
| `roe_pct` | 38.6% | CURRENT | 0.2074 | 1 | 0.4833 |
| `issue_size_cr` | 81.9% | NOISE | 0.3033 | -1 | 0.5390 |
| `borrowings_cr` | 41.1% | NOISE | 0.1781 | 1 | 0.4762 |
| `market_cap_at_offer_cr` | 58.9% | NOISE | 0.1255 | 1 | 0.5327 |
| `pb_pre_issue` | 36.1% | NOISE | 0.0887 | -1 | 0.5000 |
| `pe_post` | 18.4% | NOISE | 0.0000 | -1 | 0.5000 |
| `pe_pre` | 43.0% | NOISE | 0.0000 | -1 | 0.5000 |

## Scheme C with the Y-2 embargo

| variable | coverage 2019+ | verdict | IV | sign | median AUC |
|---|---|---|---|---|---|
| `ebitda_cr` | 22.7% | STABLE | 0.4051 | -1 | 0.5346 |
| `issue_size_over_net_worth` | 62.6% | STABLE | 0.3606 | -1 | 0.5079 |
| `pat_margin_pct_on_total_income` | 63.9% | STABLE | 0.3348 | -1 | 0.4946 |
| `issue_size_cr` | 81.9% | STABLE | 0.3208 | -1 | 0.5001 |
| `total_income_cr` | 74.8% | STABLE | 0.3035 | 1 | 0.5233 |
| `ebitda_margin_pct` | 21.8% | STABLE | 0.3030 | -1 | 0.5824 |
| `debt_equity` | 31.8% | STABLE | 0.2667 | -1 | 0.4794 |
| `mcap_over_total_income` | 54.2% | STABLE | 0.2328 | 1 | 0.4939 |
| `borrowings_cr` | 41.1% | STABLE | 0.1893 | 1 | 0.4717 |
| `roce_pct` | 45.5% | STABLE | 0.1118 | -1 | 0.5000 |
| `cash_cr` | 76.6% | STABLE | 0.0816 | -1 | 0.4995 |
| `ronw_pct` | 43.6% | STABLE | 0.0793 | 1 | 0.4895 |
| `pat_cr` | 68.8% | CURRENT | 0.2727 | 1 | 0.5187 |
| `roe_pct` | 38.6% | CURRENT | 0.2425 | 1 | 0.4838 |
| `net_worth_cr` | 63.6% | NOISE | 0.3761 | -1 | 0.4917 |
| `market_cap_at_offer_cr` | 58.9% | NOISE | 0.1395 | 1 | 0.5000 |
| `pb_pre_issue` | 36.1% | NOISE | 0.1032 | -1 | 0.5083 |
| `pe_post` | 18.4% | NOISE | 0.0000 | 1 | 0.5000 |
| `pe_pre` | 43.0% | NOISE | 0.0000 | -1 | 0.5000 |


## Two readings a reader must not take from the table above

**1. A STABLE label is not a claim that the variable predicts.** STABLE means the sign
agreed in at least 75% of windows and the in-fold IV cleared 0.02 in at least 60% of them.
The median **out-of-sample** AUC of the twelve STABLE valuation variables runs 0.47 to 0.58,
and six of them sit within 0.01 of 0.50. The label is a consistency label, exactly as
`model_h_stability` defines it, and nothing here changes that definition.

For comparison, Model H's own firm variables in `reports/MODEL_H_STABILITY.md` read the
same way — `ipo_count_prior_6m` STABLE at IV 0.3077 and AUC **0.5000**,
`ipo_count_prior_3m` STABLE at IV 0.2823 and AUC **0.5000**, `nifty_tri_ret_12m` STABLE at
IV 0.2363 and AUC **0.5000**. So the valuation block is neither better nor worse than the
firm block on this measure. Both are consistent and both are close to a coin flip.

**2. The IV is NOT an artefact of missingness — this was measured, not assumed.** The
obvious worry about a block with 22–88% missing values is that the WoE bins are really
reading "did we have this number", which is a fact about our data collection rather than
about the company. It was tested directly: the IV of the **missingness indicator alone**,
for every admissible variable:

| variable | % missing | IV of missingness ALONE | corr(missing, listing year) |
|---|---|---|---|
| `pat_margin_pct_on_total_income` | 40.2 | **0.0543** | −0.123 |
| `ebitda_cr` | 79.7 | **0.0501** | −0.063 |
| `ebitda_margin_pct` | 80.3 | **0.0439** | −0.056 |
| `pat_cr` | 35.3 | 0.0377 | −0.152 |
| `total_income_cr` | 31.1 | 0.0248 | −0.196 |
| `issue_size_cr` | 22.7 | 0.0144 | −0.241 |
| `pe_post` | 88.2 | 0.0139 | −0.346 |
| `pb_pre_issue` | 71.1 | 0.0095 | −0.222 |
| `ronw_pct` | 62.4 | 0.0057 | −0.188 |
| `net_worth_cr` | 37.6 | 0.0034 | −0.081 |
| `pe_pre` | 72.3 | 0.0029 | −0.536 |
| `issue_size_over_net_worth` | 38.2 | 0.0019 | −0.073 |
| `roce_pct` | 68.3 | 0.0015 | −0.456 |
| `mcap_over_total_income` | 53.6 | 0.0004 | −0.239 |
| `roe_pct` | 57.0 | 0.0002 | +0.110 |
| `debt_equity` | 62.0 | 0.0002 | +0.149 |
| `borrowings_cr` | 55.6 | 0.0002 | +0.062 |
| `cash_cr` | 42.6 | 0.0000 | −0.568 |
| `market_cap_at_offer_cr` | 50.4 | 0.0000 | −0.291 |

The highest is **0.0543**, against reported in-fold IVs of 0.08–0.41. So the missingness
hypothesis is refused by the measurement: the IV comes from the values. What the IV does
not come with is out-of-sample discrimination — in-fold IV of 0.3 against a test-year AUC
of 0.50 is overfitted bins, not a transferable edge.

`cash_cr` is worth one line on its own: its missingness correlates −0.568 with listing year
(newer filings are the ones a second source covers), yet its missingness IV is **0.0000**.
Strong vintage structure in the availability, no information in it about the outcome.

## What is NOT done here

No variable set is chosen, no window is chosen, no model is fitted. `ev_ebitda` (8.8%
coverage) and `pb_post_issue` (2.4%) never reached the analysis: they fall below
`model_h_stability.candidates()`'s own floors of 30 non-null values and 2 distinct values,
and those floors were not relaxed.

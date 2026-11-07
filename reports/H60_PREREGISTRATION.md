# H60 — the combined Model H fit, pre-registered BEFORE any fit (2026-11-08)

Task 3 of the 6 November brief. **Nothing is fitted in this document.** It fixes the
variables, the method, the windows and the bar in advance, so that the result cannot be
chosen after seeing it — the same discipline H29 and H35 were run under, both of which
failed against bars set this way.

This is the **one** combined fit decision 4 of the 6 November brief allows. If it fails
H29 as written, Model H is closed as display-only.

## 1. The bar — H29, unchanged, quoted

The top-20% band of the fitted score must satisfy **all three**:

| criterion | required |
|---|---|
| picks in the band | **>= 50** |
| hit rate (beat Nifty 50 TRI over the first year) | **>= 54%** |
| Wilson 95% lower bound on that hit rate | **strictly above the base rate** |

The base rate is computed on the same scored population, not on a different one. Nothing
in this document relaxes, re-scales or reinterprets any of those three numbers.

## 2. Method — H30, unchanged

- **WoE bins, IV selection, numpy logistic regression.** No scikit-learn (rule 10).
- Bins are fitted **inside the training fold only**; the test year is transformed with the
  training fold's bin edges and WoE values, never its own.
- **Scheme C walk-forward, expanding, with the Y-2 embargo** — the year immediately before
  the test year is dropped, because its 12-month outcomes close inside the test year.
- A missing value is its **own WoE bin**. It is never imputed and never zero-filled.
- One variable per 10 beat-Nifty outcomes in the training fold (`MIN_TRAIN_OUTCOMES`), so
  an early fold may fit fewer variables than the list below. That is the existing rule.

## 3. The variable list — firm + valuation STABLE only, at most 13

**Eligibility, fixed now:** a variable is eligible only if it is labelled **STABLE** under
**scheme C with the Y-2 embargo** — the same scheme the fit uses. 16 firm variables and 12
valuation variables qualify, which is 28, so a pre-registered cut is needed to reach 13.

**The cut, in this order:**

1. **Drop exact transform duplicates.** `sub_total` and `log1p_sub_total` carry identical
   IV (0.2137) and identical AUC (0.5042) because they are the same variable; the logged
   form is kept, matching Model L's frozen Set A. This drops 1.
2. **Drop anything that is not knowable before the outcome window opens.**
   `listing_gain_pct` is the listing-day return, which is knowable at listing, so it stays;
   nothing in the list is post-listing beyond that.
3. **Rank by median in-fold IV under scheme C with the embargo, and take the top 13**,
   with at least 4 valuation variables so the combined fit is genuinely combined and not
   the firm model with decoration.

Applying that to the measured numbers gives this list, fixed now:

| # | variable | block | median IV | median AUC | sign |
|---|---|---|---|---|---|
| 1 | `nifty_pe_vs_10y_median` | firm | 0.4718 | 0.4863 | −1 |
| 2 | `ipo_count_prior_3m` | firm | 0.4371 | 0.5389 | −1 |
| 3 | `val_ebitda_cr` | valuation | 0.4051 | 0.5346 | −1 |
| 4 | `val_issue_size_over_net_worth` | valuation | 0.3606 | 0.5079 | −1 |
| 5 | `val_pat_margin_pct_on_total_income` | valuation | 0.3348 | 0.4946 | −1 |
| 6 | `val_issue_size_cr` | valuation | 0.3208 | 0.5001 | −1 |
| 7 | `nifty_tri_ret_12m` | firm | 0.3177 | 0.5506 | −1 |
| 8 | `ipo_count_prior_6m` | firm | 0.3103 | 0.5000 | −1 |
| 9 | `promoter_dilution_pp_agg` | firm | 0.3055 | 0.5574 | −1 |
| 10 | `val_total_income_cr` | valuation | 0.3035 | 0.5233 | +1 |
| 11 | `val_ebitda_margin_pct` | valuation | 0.3030 | 0.5824 | −1 |
| 12 | `sub_hni` | firm | 0.2907 | 0.5152 | +1 |
| 13 | `promoter_holding_pre_pct_agg` | firm | 0.2814 | 0.5194 | −1 |

**7 firm, 6 valuation.** `log_issue_size` (firm) and `val_issue_size_cr` (valuation) are
the same underlying quantity on two scales; `log_issue_size` ranks 15th and does not make
the 13, so no duplicate enters. `val_market_cap_at_offer_cr` is NOISE and is not eligible.

Note what this list contains: four of the seven firm variables
(`nifty_pe_vs_10y_median`, `ipo_count_prior_3m`, `nifty_tri_ret_12m`, `ipo_count_prior_6m`)
are **market-heat** variables, which is the signal H35 just failed on.

## 4. What the measurements already say about the likely outcome

Stated before the fit, so it cannot be claimed afterwards as foresight:

- The median out-of-sample AUC of **every** variable on the list is between **0.4863 and
  0.5824**; eight of the thirteen are within 0.03 of 0.50.
- The two narrower claims on this same target both failed against bars set in advance:
  **H29 per-IPO** (AUC 0.5338; 83 picks, 53.01% hit, Wilson lower bound 42.38% against a
  base rate of 43.13%) and **H35 cohort** (criterion 2: the sign held in 3 of 9 measurable
  test years against a required 75%).
- The valuation block's in-fold IV is real and not an artefact of missingness — that was
  measured, with the missingness indicator's own IV at most 0.0543 — but it comes with no
  out-of-sample discrimination.

So the honest prior is that this fit **fails** H29. It is still worth running once, because
H29 is a pre-set bar and a combined fit has not been measured against it; what would not be
legitimate is running it and then adjusting the bar.

## 5. What happens to the result

- **Pass** (all three criteria): report it and stop. No wiring, no email change, no
  threshold change in the same step.
- **Fail**: Model H is closed as **display-only** under decision 4 of the 6 November brief,
  and that closure is recorded as the H60 result.

Either way: the variables, method, windows and bar above are not changed after the number
is seen.

## 6. Awaiting approval

Per the brief, **the fit has not been run.** This document and the variable list go to the
user first.

# Model H — combined-fit readiness (Task 7, 2026-11-02)

**No fit was run.** This is the variable list H30's criteria would admit, with coverage
measured on the 2019+ rows that have a corrected 1y target.

**Caveat on timing:** this reflects Tasks 2-4. **Task 5 (transcribing the 13 untouched
check-set RHPs) is not done**, so the RHP-sourced rows can still move: a reader that earns
a verdict changes `rhp_*` coverage, and nothing else in the table.

Base: **315** rows listed 2019 or later with a 1y target, of which **135** beat the Nifty 50
TRI. At 10 wins per variable that allows **13** variables, against H30's ceiling of ~20 — so
the binding constraint is wins, not the ceiling.

| variable | block | coverage 2019+ | stable? | in fit? |
|---|---|---|---|---|
| `ipo_count_prior_3m` | market heat | 100.0% | STABLE (all 4) | **yes** |
| `ipo_count_prior_6m` | market heat | 100.0% | STABLE (all 4) | **yes** |
| `nifty_tri_ret_12m` | market heat | 100.0% | STABLE (all 4) | **yes** |
| `mean_listing_gain_prior_3m` | market heat | 99.4% | STABLE (all 4) | **yes** |
| `turnover_x_issue_size` | listing / size | 99.7% | STABLE (all 4) | **yes** |
| `rhp_uses_of_proceeds_n` | RHP (single-source) | 72.1% | STABLE (all 4) | maybe |
| `log1p_sub_total` | demand | 100.0% | STABLE in 3/4 | maybe |
| `sub_total` | demand | 100.0% | STABLE in 3/4 | maybe |
| `log_issue_size` | listing / size | 100.0% | STABLE in 3/4 | maybe |
| `mean_sub_total_prior_3m` | market heat | 99.4% | STABLE in 3/4 | maybe |
| `sector_minus_nifty_6m` | listing / size | 70.8% | STABLE in 3/4 | maybe |
| `sub_qib` | demand | 100.0% | STABLE in 2/4 | maybe |
| `india_vix_at_listing` | market heat | 100.0% | CURRENT | no |
| `listing_gain_pct` | listing / size | 100.0% | CURRENT | no |
| `listing_gain_minus_sector_day` | listing / size | 70.8% | CURRENT | no |
| `qib_share_of_total` | demand | 100.0% | CURRENT | no |
| `sub_hni` | demand | 100.0% | CURRENT | no |
| `nifty_pe_at_listing` | market heat | 100.0% | CURRENT | no |
| `smallcap_minus_nifty_6m` | market heat | 100.0% | CURRENT | no |
| `promoter_holding_pre_pct_agg` | ownership | 79.7% | CURRENT | no |
| `promoter_holding_post_pct_agg` | ownership | 79.0% | CURRENT | no |
| `promoter_dilution_pp_agg` | ownership | 79.0% | CURRENT | no |
| `sector_minus_nifty_3m` | listing / size | 70.8% | CURRENT | no |
| `rhp_promoter_lockin_months` | RHP (single-source) | 90.5% | CURRENT | no |
| `anchor_amount_cr` | demand | 54.6% | CURRENT | no |
| `anchor_n_investors` | demand | 54.6% | CURRENT | no |
| `anchor_share_of_issue_pct` | demand | 54.6% | CURRENT | no |
| `rhp_esop_exists_flag` | RHP (single-source) | 88.9% | NOISE | no |
| `rhp_promoter_holding_pre_pct` | RHP (single-source) | 63.8% | NOISE | no |
| `rhp_pre_ipo_placement_flag` | RHP (single-source) | 58.7% | NOISE | no |
| `rhp_board_size_n` | RHP (single-source) | 56.8% | NOISE | no |
| `nifty_tri_ret_6m` | market heat | 100.0% | NOISE | no |
| `nifty_pe_vs_10y_median` | market heat | 100.0% | NOISE | no |
| `rii_share_of_total` | demand | 100.0% | NOISE | no |
| `sub_rii` | demand | 100.0% | NOISE | no |
| `rhp_auditor_qualification_flag` | RHP (single-source) | 90.2% | NO SPREAD | no |
| `anchor_mf_share_of_book_pct` | demand | 34.0% | NO SPREAD | no |

`in fit?` is mechanical: **yes** = STABLE in all four schemes and ≥80% coverage;
**maybe** = STABLE somewhere and ≥60% coverage; **no** otherwise.

## Is the condition met?

**Yes, with room.** 5 variables qualify outright and 12 reach "maybe", against a budget of
13 wins-per-variable and a ceiling of ~20. The arithmetic is not the constraint.

Three things the table shows that the arithmetic does not:

1. **Four of the five firm variables are market heat, and the fifth is turnover.** The
   combined fit's signal is concentrated in exactly the variables H35 already isolates — so
   a combined per-IPO fit and the H35 market statement are close to the same claim wearing
   different clothes. H29 failed at AUC 0.5338; adding `turnover_x_issue_size` and four heat
   measures is unlikely to change that, and this table is the reason to expect it.
2. **Not one RHP-sourced variable is firm.** `rhp_uses_of_proceeds_n` is the only STABLE one
   and it sits at 72.1%. Every other `rhp_*` variable is NOISE, CURRENT or NO SPREAD. The
   RHP extraction programme has not yet produced a variable Model H can use, which is worth
   saying plainly before more extraction effort is committed.
3. **The anchor block is unusable at 54.6% coverage** and all three of its variables are
   CURRENT, not STABLE.

**Next step is the user's, per the brief: the combined fit is the next run's job, after
review.** Nothing was fitted.

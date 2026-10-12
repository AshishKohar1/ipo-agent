# Model H — variable stability (2026-10-13)

Analysis only. **No variable set is chosen here, no window is chosen, and no model is fitted.** H29 is unchanged.

- 497 mainboard IPOs with a corrected 1y target, 2010-2025
- base rate 39.8% beat the Nifty 50 TRI over their first year
- 31 candidate variables, each measured **one at a time** (one variable per 10 beat-Nifty outcomes)
- IV floor 0.02; a test year with fewer than 10 rows is flagged and its AUC is not trusted

## Labels

- **STABLE** — same direction in >= 75% of windows AND IV >= 0.02 in >= 60%
- **CURRENT** — sign and IV hold in the last 4 windows only
- **NOISE** — direction flips in more than a quarter of windows, or IV is below the floor in most
- **WEAK** — neither; the counts are given so the reader can judge
- **NOT MEASURED** — no window had enough outcomes

## Scheme A — rolling 5-year

| variable | label | windows | same_sign | dirs_measured | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|---|
| ipo_count_prior_6m | STABLE | 14 | 13 | 14 | 14 | 0.3077 | 0.5 | -1.0 |
| ipo_count_prior_3m | STABLE | 14 | 14 | 14 | 14 | 0.2823 | 0.5 | -1.0 |
| log1p_sub_total | STABLE | 14 | 12 | 14 | 14 | 0.2566 | 0.5395 | -1.0 |
| sub_total | STABLE | 14 | 12 | 14 | 14 | 0.2566 | 0.5395 | -1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 13 | 14 | 14 | 0.2427 | 0.5779 | -1.0 |
| nifty_tri_ret_12m | STABLE | 14 | 13 | 14 | 14 | 0.2363 | 0.5 | -1.0 |
| sub_qib | STABLE | 14 | 11 | 14 | 13 | 0.2266 | 0.4152 | -1.0 |
| mean_sub_total_prior_3m | STABLE | 14 | 12 | 14 | 14 | 0.2265 | 0.5104 | -1.0 |
| log_issue_size | STABLE | 14 | 13 | 14 | 13 | 0.1985 | 0.4838 | -1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 13 | 0.1835 | 0.5347 | -1.0 |
| sector_minus_nifty_6m | STABLE | 14 | 11 | 14 | 14 | 0.1536 | 0.5 | -1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 13 | 14 | 12 | 0.0824 | 0.5 | 1.0 |
| smallcap_minus_nifty_6m | CURRENT | 14 | 9 | 14 | 14 | 0.3052 | 0.5149 | -1.0 |
| sub_hni | CURRENT | 14 | 8 | 14 | 14 | 0.1883 | 0.5089 | 1.0 |
| qib_share_of_total | CURRENT | 14 | 7 | 14 | 14 | 0.1439 | 0.4792 | 1.0 |
| anchor_amount_cr | CURRENT | 14 | 5 | 8 | 9 | 0.1112 | 0.5342 | 1.0 |
| anchor_n_investors | CURRENT | 14 | 6 | 8 | 9 | 0.0755 | 0.5 | -1.0 |
| rhp_promoter_lockin_months | CURRENT | 14 | 9 | 14 | 12 | 0.043 | 0.4821 | 1.0 |
| promoter_holding_post_pct_agg | NOISE | 14 | 7 | 14 | 14 | 0.2463 | 0.5064 | 1.0 |
| listing_gain_pct | NOISE | 14 | 9 | 14 | 14 | 0.2137 | 0.557 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 7 | 14 | 14 | 0.1672 | 0.5062 | 1.0 |
| sub_rii | NOISE | 14 | 8 | 14 | 13 | 0.1626 | 0.5 | -1.0 |
| nifty_tri_ret_6m | NOISE | 14 | 7 | 14 | 14 | 0.1583 | 0.5078 | 1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 5 | 10 | 10 | 0.1301 | 0.5 | 1.0 |
| rii_share_of_total | NOISE | 14 | 8 | 14 | 14 | 0.1247 | 0.5174 | -1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 9 | 14 | 14 | 0.0973 | 0.4514 | -1.0 |
| anchor_share_of_issue_pct | NOISE | 14 | 5 | 8 | 9 | 0.097 | 0.5385 | -1.0 |
| rhp_pre_ipo_placement_flag | NOISE | 14 | 4 | 5 | 11 | 0.0558 | 0.5031 | -1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 9 | 14 | 8 | 0.0232 | 0.4822 | 1.0 |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 0 | 8 | 0.0288 | 0.5 |  |
| rhp_auditor_qualification_flag | NO SPREAD | 14 | 0 | 0 | 6 | 0.0175 | 0.4938 |  |

Why each label:

- `ipo_count_prior_6m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_3m` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `log1p_sub_total` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `sub_total` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `nifty_tri_ret_12m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `sub_qib` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `mean_sub_total_prior_3m` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `log_issue_size` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `sector_minus_nifty_6m` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 12/14 (>= 60%)
- `smallcap_minus_nifty_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 9/14 and 14/14 overall
- `sub_hni` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 8/14 and 14/14 overall
- `qib_share_of_total` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 7/14 and 14/14 overall
- `anchor_amount_cr` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 5/8 and 9/14 overall
- `anchor_n_investors` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 6/8 and 9/14 overall
- `rhp_promoter_lockin_months` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 9/14 and 12/14 overall
- `promoter_holding_post_pct_agg` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `listing_gain_pct` **NOISE** — sign agrees in only 9/14 measurable windows and IV >= 0.02 in 14/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `sub_rii` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 13/14
- `nifty_tri_ret_6m` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 5/10 measurable windows and IV >= 0.02 in 10/14
- `rii_share_of_total` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 9/14 measurable windows and IV >= 0.02 in 14/14
- `anchor_share_of_issue_pct` **NOISE** — sign agrees in 5/8 measurable windows, direction measurable in only 8/14, IV >= 0.02 in 9/14
- `rhp_pre_ipo_placement_flag` **NOISE** — sign agrees in 4/5 measurable windows, direction measurable in only 5/14, IV >= 0.02 in 11/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 9/14 measurable windows and IV >= 0.02 in 8/14
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window
- `rhp_auditor_qualification_flag` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## Scheme B — rolling 4-year

| variable | label | windows | same_sign | dirs_measured | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|---|
| nifty_tri_ret_12m | STABLE | 14 | 13 | 14 | 14 | 0.3118 | 0.5375 | -1.0 |
| ipo_count_prior_3m | STABLE | 14 | 14 | 14 | 14 | 0.2892 | 0.523 | -1.0 |
| log1p_sub_total | STABLE | 14 | 13 | 14 | 13 | 0.2863 | 0.4777 | -1.0 |
| sub_total | STABLE | 14 | 13 | 14 | 13 | 0.2863 | 0.4777 | -1.0 |
| ipo_count_prior_6m | STABLE | 14 | 12 | 14 | 14 | 0.2597 | 0.5 | -1.0 |
| mean_sub_total_prior_3m | STABLE | 14 | 11 | 14 | 14 | 0.2386 | 0.5139 | -1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 13 | 14 | 14 | 0.2013 | 0.5417 | -1.0 |
| log_issue_size | STABLE | 14 | 14 | 14 | 14 | 0.1666 | 0.5216 | -1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 13 | 0.1651 | 0.5227 | -1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 13 | 14 | 12 | 0.1386 | 0.5 | 1.0 |
| sub_rii | STABLE | 14 | 11 | 14 | 12 | 0.1289 | 0.4752 | -1.0 |
| smallcap_minus_nifty_6m | CURRENT | 14 | 10 | 14 | 14 | 0.2374 | 0.497 | -1.0 |
| listing_gain_pct | CURRENT | 14 | 8 | 14 | 14 | 0.2137 | 0.5833 | 1.0 |
| anchor_amount_cr | CURRENT | 14 | 5 | 8 | 8 | 0.0925 | 0.5385 | 1.0 |
| anchor_share_of_issue_pct | CURRENT | 14 | 4 | 8 | 8 | 0.0898 | 0.5378 | 1.0 |
| anchor_n_investors | CURRENT | 14 | 6 | 8 | 8 | 0.0829 | 0.5 | -1.0 |
| rhp_promoter_lockin_months | CURRENT | 14 | 10 | 14 | 12 | 0.0548 | 0.4906 | 1.0 |
| promoter_holding_post_pct_agg | NOISE | 14 | 8 | 14 | 14 | 0.2452 | 0.5 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 7 | 14 | 14 | 0.2073 | 0.4859 | 1.0 |
| qib_share_of_total | NOISE | 14 | 7 | 14 | 14 | 0.2052 | 0.4625 | 1.0 |
| sub_hni | NOISE | 14 | 7 | 14 | 13 | 0.1816 | 0.5 | 1.0 |
| sector_minus_nifty_6m | NOISE | 14 | 10 | 14 | 13 | 0.1784 | 0.5268 | -1.0 |
| sub_qib | NOISE | 14 | 9 | 14 | 13 | 0.1745 | 0.443 | -1.0 |
| nifty_tri_ret_6m | NOISE | 14 | 7 | 14 | 14 | 0.1555 | 0.5208 | 1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 6 | 10 | 10 | 0.1503 | 0.5 | 1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 8 | 14 | 14 | 0.1355 | 0.5055 | -1.0 |
| rii_share_of_total | NOISE | 14 | 7 | 14 | 14 | 0.1112 | 0.5294 | 1.0 |
| rhp_auditor_qualification_flag | NOISE | 14 | 2 | 2 | 9 | 0.0601 | 0.4833 | -1.0 |
| rhp_pre_ipo_placement_flag | NOISE | 14 | 3 | 3 | 10 | 0.0394 | 0.5031 | -1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 8 | 14 | 8 | 0.0238 | 0.4665 | -1.0 |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 0 | 7 | 0.0228 | 0.5 |  |

Why each label:

- `nifty_tri_ret_12m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_3m` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `log1p_sub_total` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `sub_total` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `ipo_count_prior_6m` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `mean_sub_total_prior_3m` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `log_issue_size` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 12/14 (>= 60%)
- `sub_rii` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 12/14 (>= 60%)
- `smallcap_minus_nifty_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 10/14 and 14/14 overall
- `listing_gain_pct` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 8/14 and 14/14 overall
- `anchor_amount_cr` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 5/8 and 8/14 overall
- `anchor_share_of_issue_pct` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 4/8 and 8/14 overall
- `anchor_n_investors` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 6/8 and 8/14 overall
- `rhp_promoter_lockin_months` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 10/14 and 12/14 overall
- `promoter_holding_post_pct_agg` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `qib_share_of_total` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `sub_hni` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 13/14
- `sector_minus_nifty_6m` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 13/14
- `sub_qib` **NOISE** — sign agrees in only 9/14 measurable windows and IV >= 0.02 in 13/14
- `nifty_tri_ret_6m` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 6/10 measurable windows and IV >= 0.02 in 10/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `rii_share_of_total` **NOISE** — sign agrees in only 7/14 measurable windows and IV >= 0.02 in 14/14
- `rhp_auditor_qualification_flag` **NOISE** — sign agrees in 2/2 measurable windows, direction measurable in only 2/14, IV >= 0.02 in 9/14
- `rhp_pre_ipo_placement_flag` **NOISE** — sign agrees in 3/3 measurable windows, direction measurable in only 3/14, IV >= 0.02 in 10/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 8/14
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## Scheme C — expanding

| variable | label | windows | same_sign | dirs_measured | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|---|
| ipo_count_prior_3m | STABLE | 14 | 14 | 14 | 14 | 0.4246 | 0.5219 | -1.0 |
| nifty_tri_ret_12m | STABLE | 14 | 14 | 14 | 14 | 0.3175 | 0.5 | -1.0 |
| ipo_count_prior_6m | STABLE | 14 | 13 | 14 | 14 | 0.3087 | 0.5 | -1.0 |
| promoter_holding_post_pct_agg | STABLE | 14 | 11 | 14 | 14 | 0.2663 | 0.5 | -1.0 |
| sub_hni | STABLE | 14 | 13 | 14 | 13 | 0.2595 | 0.5164 | 1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 11 | 14 | 14 | 0.1847 | 0.5487 | -1.0 |
| listing_gain_pct | STABLE | 14 | 12 | 14 | 14 | 0.1807 | 0.5617 | 1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 14 | 14 | 14 | 0.1714 | 0.5 | 1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 14 | 0.1589 | 0.5182 | -1.0 |
| nifty_tri_ret_6m | STABLE | 14 | 11 | 14 | 14 | 0.1244 | 0.4955 | -1.0 |
| rhp_pre_ipo_placement_flag | STABLE | 14 | 9 | 9 | 12 | 0.0682 | 0.5 | -1.0 |
| anchor_n_investors | CURRENT | 14 | 6 | 8 | 9 | 0.0408 | 0.5 | -1.0 |
| rhp_promoter_lockin_months | WEAK | 14 | 11 | 14 | 7 | 0.0153 | 0.4969 | 1.0 |
| smallcap_minus_nifty_6m | NOISE | 14 | 8 | 14 | 14 | 0.2496 | 0.4732 | -1.0 |
| log1p_sub_total | NOISE | 14 | 10 | 14 | 12 | 0.2064 | 0.4778 | -1.0 |
| sub_total | NOISE | 14 | 10 | 14 | 12 | 0.2064 | 0.4778 | -1.0 |
| sector_minus_nifty_6m | NOISE | 14 | 10 | 14 | 13 | 0.1217 | 0.5347 | -1.0 |
| sub_qib | NOISE | 14 | 8 | 14 | 14 | 0.121 | 0.4567 | -1.0 |
| mean_sub_total_prior_3m | NOISE | 14 | 8 | 14 | 14 | 0.1169 | 0.4777 | -1.0 |
| qib_share_of_total | NOISE | 14 | 8 | 14 | 11 | 0.0989 | 0.4706 | 1.0 |
| log_issue_size | NOISE | 14 | 10 | 14 | 14 | 0.094 | 0.5549 | -1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 8 | 14 | 14 | 0.0604 | 0.5 | -1.0 |
| sub_rii | NOISE | 14 | 9 | 14 | 11 | 0.0544 | 0.4422 | -1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 6 | 10 | 9 | 0.0459 | 0.4866 | 1.0 |
| rii_share_of_total | NOISE | 14 | 10 | 14 | 13 | 0.0451 | 0.518 | -1.0 |
| anchor_share_of_issue_pct | NOISE | 14 | 7 | 8 | 9 | 0.0412 | 0.5 | -1.0 |
| anchor_amount_cr | NOISE | 14 | 5 | 8 | 7 | 0.0316 | 0.5 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 8 | 14 | 10 | 0.0234 | 0.4675 | -1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 10 | 14 | 6 | 0.0161 | 0.4911 | 1.0 |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 0 | 5 | 0.0049 | 0.5 |  |
| rhp_auditor_qualification_flag | NO SPREAD | 14 | 0 | 0 | 2 | 0.0016 | 0.4833 |  |

Why each label:

- `ipo_count_prior_3m` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `nifty_tri_ret_12m` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_6m` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `promoter_holding_post_pct_agg` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `sub_hni` **STABLE** — sign agrees in 13/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 13/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_pct` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 14/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `nifty_tri_ret_6m` **STABLE** — sign agrees in 11/14 measurable windows (>= 75%), direction measurable in 14/14, and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_pre_ipo_placement_flag` **STABLE** — sign agrees in 9/9 measurable windows (>= 75%), direction measurable in 9/14, and IV >= 0.02 in 12/14 (>= 60%)
- `anchor_n_investors` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 6/8 and 9/14 overall
- `rhp_promoter_lockin_months` **WEAK** — sign agrees in 11/14 and IV >= 0.02 in 7/14 - neither stable nor clearly noise
- `smallcap_minus_nifty_6m` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `log1p_sub_total` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 12/14
- `sub_total` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 12/14
- `sector_minus_nifty_6m` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 13/14
- `sub_qib` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `mean_sub_total_prior_3m` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `qib_share_of_total` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 11/14
- `log_issue_size` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 14/14
- `sub_rii` **NOISE** — sign agrees in only 9/14 measurable windows and IV >= 0.02 in 11/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 6/10 measurable windows and IV >= 0.02 in 9/14
- `rii_share_of_total` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 13/14
- `anchor_share_of_issue_pct` **NOISE** — sign agrees in 7/8 measurable windows, direction measurable in only 8/14, IV >= 0.02 in 9/14
- `anchor_amount_cr` **NOISE** — sign agrees in 5/8 measurable windows, direction measurable in only 8/14, IV >= 0.02 in 7/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 8/14 measurable windows and IV >= 0.02 in 10/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 10/14 measurable windows and IV >= 0.02 in 6/14
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window
- `rhp_auditor_qualification_flag` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## The embargo

Scheme A trains on the year immediately before the test year, whose 12-month outcomes close **inside** it. Below is scheme A recomputed with that year dropped. Where the two disagree, this one is the honest number.

| variable | label | windows | same_sign | dirs_measured | iv_ok | median_iv | median_auc |
|---|---|---|---|---|---|---|---|
| ipo_count_prior_6m | STABLE | 13 | 12 | 13 | 13 | 0.3107 | 0.5 |
| ipo_count_prior_3m | STABLE | 13 | 13 | 13 | 13 | 0.3032 | 0.5 |
| log1p_sub_total | STABLE | 13 | 11 | 13 | 13 | 0.2996 | 0.5537 |
| sub_total | STABLE | 13 | 11 | 13 | 13 | 0.2996 | 0.5537 |
| nifty_tri_ret_12m | STABLE | 13 | 12 | 13 | 13 | 0.2599 | 0.5507 |
| mean_sub_total_prior_3m | STABLE | 13 | 11 | 13 | 13 | 0.2518 | 0.4795 |
| mean_listing_gain_prior_3m | STABLE | 13 | 12 | 13 | 13 | 0.2514 | 0.4789 |
| sub_qib | STABLE | 13 | 10 | 13 | 13 | 0.2418 | 0.4863 |
| log_issue_size | STABLE | 13 | 12 | 13 | 13 | 0.2135 | 0.5147 |
| listing_gain_minus_sector_day | STABLE | 13 | 11 | 13 | 13 | 0.1847 | 0.5361 |
| sector_minus_nifty_6m | STABLE | 13 | 10 | 13 | 13 | 0.1638 | 0.4993 |
| rhp_uses_of_proceeds_n | STABLE | 13 | 13 | 13 | 12 | 0.0892 | 0.5083 |
| smallcap_minus_nifty_6m | CURRENT | 13 | 8 | 13 | 13 | 0.3388 | 0.4988 |
| promoter_holding_post_pct_agg | CURRENT | 13 | 7 | 13 | 13 | 0.2532 | 0.4978 |
| sub_hni | CURRENT | 13 | 8 | 13 | 13 | 0.1939 | 0.5087 |
| anchor_amount_cr | CURRENT | 13 | 4 | 7 | 8 | 0.1084 | 0.5 |
| sector_minus_nifty_3m | CURRENT | 13 | 9 | 13 | 13 | 0.1006 | 0.5 |
| qib_share_of_total | CURRENT | 13 | 7 | 13 | 13 | 0.0979 | 0.4748 |
| anchor_n_investors | CURRENT | 13 | 5 | 7 | 8 | 0.0697 | 0.5 |
| listing_gain_pct | NOISE | 13 | 9 | 13 | 13 | 0.2318 | 0.556 |
| rhp_board_size_n | NOISE | 13 | 7 | 13 | 13 | 0.1693 | 0.4901 |
| sub_rii | NOISE | 13 | 7 | 13 | 13 | 0.1666 | 0.4966 |
| nifty_tri_ret_6m | NOISE | 13 | 7 | 13 | 13 | 0.1663 | 0.5621 |
| rhp_promoter_holding_pre_pct | NOISE | 13 | 5 | 9 | 9 | 0.142 | 0.534 |
| rii_share_of_total | NOISE | 13 | 7 | 13 | 13 | 0.1415 | 0.4707 |
| anchor_share_of_issue_pct | NOISE | 13 | 5 | 7 | 8 | 0.1287 | 0.5 |
| rhp_pre_ipo_placement_flag | NOISE | 13 | 4 | 5 | 11 | 0.0586 | 0.5 |
| rhp_promoter_lockin_months | NOISE | 13 | 8 | 13 | 11 | 0.0537 | 0.4731 |
| rhp_esop_exists_flag | NOISE | 13 | 8 | 13 | 8 | 0.024 | 0.4712 |
| anchor_mf_share_of_book_pct | NO SPREAD | 13 | 0 | 0 | 7 | 0.0249 | 0.5 |
| rhp_auditor_qualification_flag | NO SPREAD | 13 | 0 | 0 | 6 | 0.019 | 0.4885 |

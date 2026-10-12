# Model H — variable stability (2026-10-13)

Analysis only. **No variable set is chosen here, no window is chosen, and no model is fitted.** H29 is unchanged.

- 473 mainboard IPOs with a corrected 1y target, 2010-2025
- base rate 40.6% beat the Nifty 50 TRI over their first year
- 31 candidate variables, each measured **one at a time** (one variable per 10 beat-Nifty outcomes)
- IV floor 0.02; a test year with fewer than 10 rows is flagged and its AUC is not trusted

## Labels

- **STABLE** — same direction in >= 75% of windows AND IV >= 0.02 in >= 60%
- **CURRENT** — sign and IV hold in the last 4 windows only
- **NOISE** — direction flips in more than a quarter of windows, or IV is below the floor in most
- **WEAK** — neither; the counts are given so the reader can judge
- **NOT MEASURED** — no window had enough outcomes

## Scheme A — rolling 5-year

| variable | label | windows | same_sign | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|
| ipo_count_prior_3m | STABLE | 14 | 12 | 14 | 0.3615 | 0.5 | -1.0 |
| ipo_count_prior_6m | STABLE | 14 | 11 | 14 | 0.2659 | 0.5 | -1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 13 | 14 | 0.2288 | 0.5089 | -1.0 |
| nifty_tri_ret_12m | STABLE | 14 | 13 | 14 | 0.2222 | 0.5 | -1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 0.2108 | 0.5363 | -1.0 |
| mean_sub_total_prior_3m | STABLE | 14 | 11 | 14 | 0.1935 | 0.4692 | -1.0 |
| log1p_sub_total | STABLE | 14 | 11 | 14 | 0.1624 | 0.4775 | -1.0 |
| log_issue_size | STABLE | 14 | 14 | 13 | 0.1616 | 0.53 | -1.0 |
| sector_minus_nifty_6m | STABLE | 14 | 11 | 14 | 0.1557 | 0.4836 | -1.0 |
| sub_total | STABLE | 14 | 11 | 14 | 0.1507 | 0.4775 | -1.0 |
| anchor_share_of_issue_pct | STABLE | 14 | 6 | 9 | 0.0895 | 0.5 | -1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 13 | 13 | 0.0839 | 0.5 | 1.0 |
| anchor_n_investors | STABLE | 14 | 6 | 9 | 0.0736 | 0.5 | -1.0 |
| rhp_pre_ipo_placement_flag | STABLE | 14 | 5 | 11 | 0.0563 | 0.5 | -1.0 |
| smallcap_minus_nifty_6m | CURRENT | 14 | 9 | 14 | 0.2956 | 0.5149 | -1.0 |
| qib_share_of_total | CURRENT | 14 | 7 | 13 | 0.1654 | 0.4722 | 1.0 |
| anchor_amount_cr | CURRENT | 14 | 5 | 9 | 0.104 | 0.5 | 1.0 |
| sub_rii | NOISE | 14 | 9 | 13 | 0.2686 | 0.4724 | -1.0 |
| promoter_holding_post_pct_agg | NOISE | 14 | 7 | 14 | 0.2535 | 0.4462 | 1.0 |
| listing_gain_pct | NOISE | 14 | 10 | 14 | 0.2029 | 0.5702 | 1.0 |
| sub_hni | NOISE | 14 | 7 | 13 | 0.1995 | 0.5073 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 7 | 14 | 0.172 | 0.6057 | 1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 5 | 10 | 0.1553 | 0.5 | 1.0 |
| sub_qib | NOISE | 14 | 10 | 14 | 0.1547 | 0.4509 | -1.0 |
| rii_share_of_total | NOISE | 14 | 8 | 13 | 0.1436 | 0.4782 | -1.0 |
| nifty_tri_ret_6m | NOISE | 14 | 8 | 14 | 0.1409 | 0.51 | 1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 7 | 13 | 0.1058 | 0.439 | 1.0 |
| rhp_promoter_lockin_months | NOISE | 14 | 9 | 10 | 0.0381 | 0.4861 | 1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 9 | 9 | 0.0289 | 0.4732 | 1.0 |
| rhp_auditor_qualification_flag | NO SPREAD | 14 | 0 | 9 | 0.0434 | 0.5089 |  |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 8 | 0.0304 | 0.5 |  |

Why each label:

- `ipo_count_prior_3m` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_6m` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `nifty_tri_ret_12m` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `mean_sub_total_prior_3m` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `log1p_sub_total` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `log_issue_size` **STABLE** — sign agrees in 14/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `sector_minus_nifty_6m` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `sub_total` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `anchor_share_of_issue_pct` **STABLE** — sign agrees in 6/8 windows (>= 75%) and IV >= 0.02 in 9/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `anchor_n_investors` **STABLE** — sign agrees in 6/8 windows (>= 75%) and IV >= 0.02 in 9/14 (>= 60%)
- `rhp_pre_ipo_placement_flag` **STABLE** — sign agrees in 5/5 windows (>= 75%) and IV >= 0.02 in 11/14 (>= 60%)
- `smallcap_minus_nifty_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 9/14 and 14/14 overall
- `qib_share_of_total` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 7/14 and 13/14 overall
- `anchor_amount_cr` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 5/8 and 9/14 overall
- `sub_rii` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 13/14
- `promoter_holding_post_pct_agg` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 14/14
- `listing_gain_pct` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `sub_hni` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 13/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 14/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 5/10 windows and IV >= 0.02 in 10/14
- `sub_qib` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `rii_share_of_total` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 13/14
- `nifty_tri_ret_6m` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 13/14
- `rhp_promoter_lockin_months` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 10/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 9/14
- `rhp_auditor_qualification_flag` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## Scheme B — rolling 4-year

| variable | label | windows | same_sign | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|
| nifty_tri_ret_12m | STABLE | 14 | 14 | 14 | 0.3117 | 0.5395 | -1.0 |
| ipo_count_prior_3m | STABLE | 14 | 12 | 14 | 0.2809 | 0.5 | -1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 0.2349 | 0.5 | -1.0 |
| sub_rii | STABLE | 14 | 11 | 13 | 0.1911 | 0.4643 | -1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 12 | 14 | 0.1906 | 0.5 | -1.0 |
| log_issue_size | STABLE | 14 | 14 | 13 | 0.1546 | 0.5278 | -1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 13 | 13 | 0.1471 | 0.5 | 1.0 |
| log1p_sub_total | STABLE | 14 | 12 | 14 | 0.1408 | 0.4788 | -1.0 |
| sub_total | STABLE | 14 | 12 | 14 | 0.1408 | 0.4788 | -1.0 |
| rhp_auditor_qualification_flag | STABLE | 14 | 2 | 10 | 0.0776 | 0.5102 | -1.0 |
| smallcap_minus_nifty_6m | CURRENT | 14 | 9 | 14 | 0.2582 | 0.5 | -1.0 |
| ipo_count_prior_6m | CURRENT | 14 | 10 | 14 | 0.247 | 0.5 | -1.0 |
| anchor_share_of_issue_pct | CURRENT | 14 | 4 | 8 | 0.0801 | 0.506 | 1.0 |
| anchor_n_investors | CURRENT | 14 | 6 | 8 | 0.0799 | 0.5 | -1.0 |
| anchor_amount_cr | CURRENT | 14 | 5 | 8 | 0.0783 | 0.5 | 1.0 |
| sub_hni | NOISE | 14 | 8 | 13 | 0.278 | 0.5 | -1.0 |
| listing_gain_pct | NOISE | 14 | 10 | 14 | 0.2394 | 0.596 | 1.0 |
| promoter_holding_post_pct_agg | NOISE | 14 | 8 | 14 | 0.2367 | 0.4712 | 1.0 |
| mean_sub_total_prior_3m | NOISE | 14 | 10 | 14 | 0.2287 | 0.541 | -1.0 |
| qib_share_of_total | NOISE | 14 | 7 | 14 | 0.2185 | 0.4538 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 7 | 14 | 0.2185 | 0.5282 | 1.0 |
| sub_qib | NOISE | 14 | 10 | 14 | 0.2145 | 0.4659 | -1.0 |
| sector_minus_nifty_6m | NOISE | 14 | 10 | 14 | 0.1909 | 0.5 | -1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 6 | 10 | 0.1784 | 0.4856 | 1.0 |
| nifty_tri_ret_6m | NOISE | 14 | 9 | 14 | 0.1375 | 0.5456 | -1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 8 | 14 | 0.1272 | 0.4758 | -1.0 |
| rii_share_of_total | NOISE | 14 | 9 | 14 | 0.1149 | 0.5457 | -1.0 |
| rhp_promoter_lockin_months | NOISE | 14 | 9 | 11 | 0.045 | 0.5024 | 1.0 |
| rhp_pre_ipo_placement_flag | NOISE | 14 | 2 | 10 | 0.0425 | 0.5 | -1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 8 | 8 | 0.0404 | 0.4808 | -1.0 |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 7 | 0.0236 | 0.5 |  |

Why each label:

- `nifty_tri_ret_12m` **STABLE** — sign agrees in 14/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_3m` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `sub_rii` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `log_issue_size` **STABLE** — sign agrees in 14/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `log1p_sub_total` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `sub_total` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_auditor_qualification_flag` **STABLE** — sign agrees in 2/2 windows (>= 75%) and IV >= 0.02 in 10/14 (>= 60%)
- `smallcap_minus_nifty_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 9/14 and 14/14 overall
- `ipo_count_prior_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 10/14 and 14/14 overall
- `anchor_share_of_issue_pct` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 4/8 and 8/14 overall
- `anchor_n_investors` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 6/8 and 8/14 overall
- `anchor_amount_cr` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 5/8 and 8/14 overall
- `sub_hni` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 13/14
- `listing_gain_pct` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `promoter_holding_post_pct_agg` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 14/14
- `mean_sub_total_prior_3m` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `qib_share_of_total` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 14/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 14/14
- `sub_qib` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_6m` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 6/10 windows and IV >= 0.02 in 10/14
- `nifty_tri_ret_6m` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 14/14
- `rii_share_of_total` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 14/14
- `rhp_promoter_lockin_months` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 11/14
- `rhp_pre_ipo_placement_flag` **NOISE** — sign agrees in only 2/3 windows and IV >= 0.02 in 10/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 8/14
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## Scheme C — expanding

| variable | label | windows | same_sign | iv_ok | median_iv | median_auc | direction |
|---|---|---|---|---|---|---|---|
| ipo_count_prior_3m | STABLE | 14 | 12 | 14 | 0.4165 | 0.5462 | -1.0 |
| sub_hni | STABLE | 14 | 13 | 12 | 0.2398 | 0.5119 | 1.0 |
| promoter_holding_post_pct_agg | STABLE | 14 | 11 | 14 | 0.2314 | 0.44 | -1.0 |
| nifty_tri_ret_12m | STABLE | 14 | 14 | 14 | 0.2291 | 0.4878 | -1.0 |
| ipo_count_prior_6m | STABLE | 14 | 11 | 14 | 0.224 | 0.5006 | -1.0 |
| listing_gain_pct | STABLE | 14 | 13 | 14 | 0.2058 | 0.5506 | 1.0 |
| listing_gain_minus_sector_day | STABLE | 14 | 12 | 14 | 0.1594 | 0.5 | -1.0 |
| log1p_sub_total | STABLE | 14 | 11 | 14 | 0.1576 | 0.4808 | -1.0 |
| sub_total | STABLE | 14 | 11 | 14 | 0.1447 | 0.4808 | -1.0 |
| rhp_uses_of_proceeds_n | STABLE | 14 | 14 | 13 | 0.1445 | 0.5 | 1.0 |
| mean_listing_gain_prior_3m | STABLE | 14 | 11 | 14 | 0.1132 | 0.494 | -1.0 |
| log_issue_size | STABLE | 14 | 13 | 14 | 0.0965 | 0.5236 | -1.0 |
| rhp_pre_ipo_placement_flag | STABLE | 14 | 9 | 11 | 0.0645 | 0.5 | -1.0 |
| anchor_share_of_issue_pct | STABLE | 14 | 7 | 9 | 0.0427 | 0.5 | -1.0 |
| anchor_n_investors | STABLE | 14 | 6 | 9 | 0.0413 | 0.5 | -1.0 |
| smallcap_minus_nifty_6m | CURRENT | 14 | 9 | 14 | 0.1945 | 0.4306 | -1.0 |
| rii_share_of_total | CURRENT | 14 | 10 | 14 | 0.0395 | 0.4927 | -1.0 |
| sub_qib | NOISE | 14 | 7 | 14 | 0.1115 | 0.5033 | 1.0 |
| mean_sub_total_prior_3m | NOISE | 14 | 10 | 14 | 0.1053 | 0.4827 | -1.0 |
| nifty_tri_ret_6m | NOISE | 14 | 8 | 14 | 0.0978 | 0.4478 | -1.0 |
| sector_minus_nifty_6m | NOISE | 14 | 10 | 11 | 0.092 | 0.5056 | -1.0 |
| qib_share_of_total | NOISE | 14 | 9 | 11 | 0.0842 | 0.4169 | -1.0 |
| sub_rii | NOISE | 14 | 7 | 13 | 0.0819 | 0.51 | 1.0 |
| rhp_promoter_holding_pre_pct | NOISE | 14 | 6 | 9 | 0.0655 | 0.5 | 1.0 |
| sector_minus_nifty_3m | NOISE | 14 | 7 | 12 | 0.0537 | 0.4769 | 1.0 |
| anchor_amount_cr | NOISE | 14 | 5 | 8 | 0.0393 | 0.5 | 1.0 |
| rhp_board_size_n | NOISE | 14 | 8 | 11 | 0.0324 | 0.4654 | -1.0 |
| rhp_promoter_lockin_months | NOISE | 14 | 11 | 3 | 0.0118 | 0.5024 | 1.0 |
| rhp_esop_exists_flag | NOISE | 14 | 10 | 5 | 0.0083 | 0.4551 | 1.0 |
| rhp_auditor_qualification_flag | NO SPREAD | 14 | 0 | 5 | 0.012 | 0.5102 |  |
| anchor_mf_share_of_book_pct | NO SPREAD | 14 | 0 | 6 | 0.0086 | 0.5 |  |

Why each label:

- `ipo_count_prior_3m` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `sub_hni` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 12/14 (>= 60%)
- `promoter_holding_post_pct_agg` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `nifty_tri_ret_12m` **STABLE** — sign agrees in 14/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `ipo_count_prior_6m` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_pct` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `listing_gain_minus_sector_day` **STABLE** — sign agrees in 12/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `log1p_sub_total` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `sub_total` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_uses_of_proceeds_n` **STABLE** — sign agrees in 14/14 windows (>= 75%) and IV >= 0.02 in 13/14 (>= 60%)
- `mean_listing_gain_prior_3m` **STABLE** — sign agrees in 11/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `log_issue_size` **STABLE** — sign agrees in 13/14 windows (>= 75%) and IV >= 0.02 in 14/14 (>= 60%)
- `rhp_pre_ipo_placement_flag` **STABLE** — sign agrees in 9/9 windows (>= 75%) and IV >= 0.02 in 11/14 (>= 60%)
- `anchor_share_of_issue_pct` **STABLE** — sign agrees in 7/8 windows (>= 75%) and IV >= 0.02 in 9/14 (>= 60%)
- `anchor_n_investors` **STABLE** — sign agrees in 6/8 windows (>= 75%) and IV >= 0.02 in 9/14 (>= 60%)
- `smallcap_minus_nifty_6m` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 9/14 and 14/14 overall
- `rii_share_of_total` **CURRENT** — sign agrees and IV >= 0.02 in all of the last 4 windows, but only 10/14 and 14/14 overall
- `sub_qib` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 14/14
- `mean_sub_total_prior_3m` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 14/14
- `nifty_tri_ret_6m` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 14/14
- `sector_minus_nifty_6m` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 11/14
- `qib_share_of_total` **NOISE** — sign agrees in only 9/14 windows and IV >= 0.02 in 11/14
- `sub_rii` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 13/14
- `rhp_promoter_holding_pre_pct` **NOISE** — sign agrees in only 6/10 windows and IV >= 0.02 in 9/14
- `sector_minus_nifty_3m` **NOISE** — sign agrees in only 7/14 windows and IV >= 0.02 in 12/14
- `anchor_amount_cr` **NOISE** — sign agrees in only 5/8 windows and IV >= 0.02 in 8/14
- `rhp_board_size_n` **NOISE** — sign agrees in only 8/14 windows and IV >= 0.02 in 11/14
- `rhp_promoter_lockin_months` **NOISE** — sign agrees in only 11/14 windows and IV >= 0.02 in 3/14
- `rhp_esop_exists_flag` **NOISE** — sign agrees in only 10/14 windows and IV >= 0.02 in 5/14
- `rhp_auditor_qualification_flag` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window
- `anchor_mf_share_of_book_pct` **NO SPREAD** — the quantile bins collapse to one, so there is no direction to measure - near-constant in every window

## The embargo

Scheme A trains on the year immediately before the test year, whose 12-month outcomes close **inside** it. Below is scheme A recomputed with that year dropped. Where the two disagree, this one is the honest number.

| variable | label | windows | same_sign | iv_ok | median_iv | median_auc |
|---|---|---|---|---|---|---|
| ipo_count_prior_3m | STABLE | 13 | 11 | 13 | 0.4091 | 0.4971 |
| ipo_count_prior_6m | STABLE | 13 | 10 | 13 | 0.2892 | 0.5151 |
| mean_listing_gain_prior_3m | STABLE | 13 | 12 | 13 | 0.2348 | 0.453 |
| nifty_tri_ret_12m | STABLE | 13 | 12 | 13 | 0.2296 | 0.5251 |
| mean_sub_total_prior_3m | STABLE | 13 | 10 | 13 | 0.2276 | 0.4654 |
| listing_gain_pct | STABLE | 13 | 10 | 13 | 0.2246 | 0.5638 |
| listing_gain_minus_sector_day | STABLE | 13 | 11 | 13 | 0.213 | 0.5342 |
| log_issue_size | STABLE | 13 | 13 | 13 | 0.1851 | 0.5064 |
| log1p_sub_total | STABLE | 13 | 10 | 13 | 0.1694 | 0.5524 |
| sub_qib | STABLE | 13 | 10 | 13 | 0.1631 | 0.5052 |
| sector_minus_nifty_6m | STABLE | 13 | 10 | 13 | 0.1608 | 0.5243 |
| sub_total | STABLE | 13 | 10 | 13 | 0.1555 | 0.5524 |
| anchor_share_of_issue_pct | STABLE | 13 | 6 | 8 | 0.1222 | 0.5 |
| rhp_uses_of_proceeds_n | STABLE | 13 | 13 | 13 | 0.0905 | 0.5093 |
| rhp_pre_ipo_placement_flag | STABLE | 13 | 5 | 11 | 0.0597 | 0.4962 |
| smallcap_minus_nifty_6m | CURRENT | 13 | 8 | 13 | 0.3286 | 0.5 |
| promoter_holding_post_pct_agg | CURRENT | 13 | 7 | 13 | 0.2546 | 0.4929 |
| sub_hni | CURRENT | 13 | 7 | 13 | 0.2126 | 0.4886 |
| qib_share_of_total | CURRENT | 13 | 7 | 12 | 0.1159 | 0.4749 |
| anchor_amount_cr | CURRENT | 13 | 4 | 8 | 0.1014 | 0.5 |
| anchor_n_investors | CURRENT | 13 | 5 | 8 | 0.0713 | 0.5 |
| sub_rii | NOISE | 13 | 8 | 13 | 0.2756 | 0.5104 |
| rhp_board_size_n | NOISE | 13 | 7 | 13 | 0.1853 | 0.4992 |
| rhp_promoter_holding_pre_pct | NOISE | 13 | 5 | 9 | 0.1584 | 0.5347 |
| rii_share_of_total | NOISE | 13 | 7 | 12 | 0.147 | 0.4955 |
| nifty_tri_ret_6m | NOISE | 13 | 7 | 13 | 0.1456 | 0.4715 |
| sector_minus_nifty_3m | NOISE | 13 | 7 | 12 | 0.1086 | 0.4812 |
| rhp_promoter_lockin_months | NOISE | 13 | 8 | 9 | 0.0466 | 0.4815 |
| rhp_esop_exists_flag | NOISE | 13 | 8 | 9 | 0.0339 | 0.465 |
| rhp_auditor_qualification_flag | NO SPREAD | 13 | 0 | 9 | 0.0634 | 0.5205 |
| anchor_mf_share_of_book_pct | NO SPREAD | 13 | 0 | 7 | 0.0254 | 0.5 |

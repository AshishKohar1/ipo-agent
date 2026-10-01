# Coverage and variance, side by side — Task 5

8520 field-cells across 280 companies. Coverage is never reported alone: a field that reaches 95% while being 97% one value has gained nothing, so both numbers appear in every row and the verdict uses the pair.

| Field | Coverage | Distinct | Majority share | Verdict |
|---|---|---|---|---|
| `dual_class_flag` | 88.0% | 2 | 92.8% | **collect-only** |
| `litigation_criminal_count` | 43.7% | 12 | 83.9% | **collect-only** |
| `customer_concentration_top10_pct` | 33.8% | 83 | 7.3% | **collect-only** |
| `independent_directors_n` | 33.5% | 6 | 38.9% | **collect-only** |
| `gcp_pct_proceeds` | 33.5% | 52 | 9.5% | **collect-only** |
| `kmp_remuneration_cr` | 30.6% | 47 | 32.2% | **collect-only** |
| `rpt_pct_revenue` | 23.9% | 63 | 2.9% | **collect-only** |
| `board_independence_ratio` | 21.1% | 16 | 58.3% | **collect-only** |
| `rpt_amount_cr` | 20.1% | 56 | 3.5% | **collect-only** |
| `litigation_statutory_count` | 17.3% | 10 | 75.5% | **collect-only** |
| `customer_concentration_top5_pct` | 14.1% | 39 | 5.0% | **collect-only** |
| `litigation_tax_count` | 13.7% | 9 | 53.8% | **collect-only** |
| `anchor_portion_shares` | 11.3% | 30 | 6.2% | **collect-only** |
| `promoter_holding_post_pct` | 10.9% | 6 | 77.4% | **collect-only** |
| `anchor_mf_reserved_pct` | 87.0% | 1 | 100.0% | **drop** |
| `geographic_concentration_flag` | 80.6% | 1 | 100.0% | **drop** |
| `licence_dependence_flag` | 58.8% | 1 | 100.0% | **drop** |
| `pre_ipo_placement_amount_cr` | 6.0% | 15 | 11.8% | **drop** |
| `promoter_experience_years` | 3.9% | 10 | 18.2% | **drop** |
| `litigation_aggregate_amount_cr` | 2.5% | 7 | 14.3% | **drop** |
| `auditor_emphasis_flag` | 88.0% | 2 | 51.6% | **scorecard** |
| `litigation_criminal_promoters_directors` | 86.3% | 31 | 81.6% | **scorecard** |
| `promoter_lockin_months` | 84.9% | 4 | 51.0% | **scorecard** |
| `auditor_qualification_flag` | 81.7% | 2 | 87.5% | **scorecard** |
| `esop_exists_flag` | 78.2% | 2 | 62.6% | **scorecard** |
| `pre_ipo_placement_flag` | 68.0% | 2 | 72.0% | **scorecard** |
| `uses_of_proceeds_n` | 64.4% | 8 | 24.6% | **scorecard** |
| `board_size_n` | 63.7% | 13 | 33.1% | **scorecard** |
| `promoter_holding_pre_pct` | 57.4% | 140 | 8.6% | **scorecard** |
| `contingent_liabilities_cr` | 51.1% | 143 | 1.4% | **scorecard** |

## Why a gap exists, per field (decision H10)

| Field | not_present | unparsed | section_missing | no_document | unit_undet |
|---|---|---|---|---|---|
| `dual_class_flag` | 0 | 0 | 0 | 34 | 0 |
| `litigation_criminal_count` | 126 | 0 | 0 | 34 | 0 |
| `customer_concentration_top10_pct` | 154 | 0 | 0 | 34 | 0 |
| `independent_directors_n` | 155 | 0 | 0 | 34 | 0 |
| `gcp_pct_proceeds` | 155 | 0 | 0 | 34 | 0 |
| `kmp_remuneration_cr` | 163 | 0 | 0 | 34 | 0 |
| `rpt_pct_revenue` | 182 | 0 | 0 | 34 | 0 |
| `board_independence_ratio` | 2 | 188 | 0 | 34 | 0 |
| `rpt_amount_cr` | 193 | 0 | 0 | 34 | 0 |
| `litigation_statutory_count` | 201 | 0 | 0 | 34 | 0 |
| `customer_concentration_top5_pct` | 210 | 0 | 0 | 34 | 0 |
| `litigation_tax_count` | 211 | 0 | 0 | 34 | 0 |
| `anchor_portion_shares` | 218 | 0 | 0 | 34 | 0 |
| `promoter_holding_post_pct` | 219 | 0 | 0 | 34 | 0 |
| `anchor_mf_reserved_pct` | 3 | 0 | 0 | 34 | 0 |
| `geographic_concentration_flag` | 21 | 0 | 0 | 34 | 0 |
| `licence_dependence_flag` | 83 | 0 | 0 | 34 | 0 |
| `pre_ipo_placement_amount_cr` | 233 | 0 | 0 | 34 | 0 |
| `promoter_experience_years` | 213 | 0 | 26 | 34 | 0 |
| `litigation_aggregate_amount_cr` | 146 | 97 | 0 | 34 | 0 |
| `auditor_emphasis_flag` | 0 | 0 | 0 | 34 | 0 |
| `litigation_criminal_promoters_directors` | 5 | 0 | 0 | 34 | 0 |
| `promoter_lockin_months` | 9 | 0 | 0 | 34 | 0 |
| `auditor_qualification_flag` | 18 | 0 | 0 | 34 | 0 |
| `esop_exists_flag` | 28 | 0 | 0 | 34 | 0 |
| `pre_ipo_placement_flag` | 57 | 0 | 0 | 34 | 0 |
| `uses_of_proceeds_n` | 67 | 0 | 0 | 34 | 0 |
| `board_size_n` | 0 | 69 | 0 | 34 | 0 |
| `promoter_holding_pre_pct` | 87 | 0 | 0 | 34 | 0 |
| `contingent_liabilities_cr` | 0 | 105 | 0 | 34 | 0 |

## Recommendation

### Good enough for the scorecard (10)

- **`auditor_emphasis_flag`** — 88% coverage, 2 distinct values, majority share 52%
- **`litigation_criminal_promoters_directors`** — 86% coverage, 31 distinct values, majority share 82%
- **`promoter_lockin_months`** — 85% coverage, 4 distinct values, majority share 51%
- **`auditor_qualification_flag`** — 82% coverage, 2 distinct values, majority share 88%
- **`esop_exists_flag`** — 78% coverage, 2 distinct values, majority share 63%
- **`pre_ipo_placement_flag`** — 68% coverage, 2 distinct values, majority share 72%
- **`uses_of_proceeds_n`** — 64% coverage, 8 distinct values, majority share 25%
- **`board_size_n`** — 64% coverage, 13 distinct values, majority share 33%
- **`promoter_holding_pre_pct`** — 57% coverage, 140 distinct values, majority share 9%
- **`contingent_liabilities_cr`** — 51% coverage, 143 distinct values, majority share 1%

### Collect-only — keep, do not weight yet (14)

- **`dual_class_flag`** — 93% of extracted values are the same — coverage 88% is real but the field barely discriminates
- **`litigation_criminal_count`** — 44% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`customer_concentration_top10_pct`** — 34% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`independent_directors_n`** — 33% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`gcp_pct_proceeds`** — 33% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`kmp_remuneration_cr`** — 31% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`rpt_pct_revenue`** — 24% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`board_independence_ratio`** — 21% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`rpt_amount_cr`** — 20% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`litigation_statutory_count`** — 17% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`customer_concentration_top5_pct`** — 14% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`litigation_tax_count`** — 14% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`anchor_portion_shares`** — 11% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves
- **`promoter_holding_post_pct`** — 11% coverage is below the 50% floor; variance is fine, so it becomes useful if coverage improves

### Drop (6)

- **`anchor_mf_reserved_pct`** — every one of the 247 extracted values is identical (33.33) — it cannot separate any two companies, whatever its coverage
- **`geographic_concentration_flag`** — every one of the 229 extracted values is identical (1.0) — it cannot separate any two companies, whatever its coverage
- **`licence_dependence_flag`** — every one of the 167 extracted values is identical (1.0) — it cannot separate any two companies, whatever its coverage
- **`pre_ipo_placement_amount_cr`** — 6% coverage; too sparse to impute and too sparse to weight
- **`promoter_experience_years`** — 4% coverage; too sparse to impute and too sparse to weight
- **`litigation_aggregate_amount_cr`** — 2% coverage; too sparse to impute and too sparse to weight


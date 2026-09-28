# Morning report: overnight run of 28 Sep 2026

**Status:** all three jobs completed. It was one clean launch: the run started at 01:58 and ended at 02:17 with exit code 0. There were no restarts, no crashes and no HTTP 429s. `check_env.py` passed 9/9 before launch.

**Before training, read this:** the run itself is mechanically clean. But **Job 1c has a query bug that dropped 117 live listings.** These include DMart, HDFC Life, SBI Life, HAL and Polycab, and they skew towards winners. So the 41.1% base rate below is **not final**. See §6 and §9.

---

## 1. Final symbol recovery

**450 / 652 (69.0%)**, up from 260 (39.9%).

| Stage | Symbols recovered | Running total |
|---|---|---|
| Pre-existing | — | 260 |
| 1a: complete names (68/69 truncated names completed) | (enables 1b) | 260 |
| 1b: join to trackers + NSE spine | **59** (0 source conflicts) | 319 |
| 1c: Yahoo search, 333 residual | **131** (39%) | **450** |

| Year | Rows | Pre-existing | 1b | 1c | Unresolved | Resolved % |
|---|---|---|---|---|---|---|
| 2010 | 74 | 0 | 0 | 36 | 38 | 48.6 |
| 2011 | 39 | 0 | 0 | 12 | 27 | 30.8 |
| 2012 | 11 | 0 | 0 | 5 | 6 | 45.5 |
| 2013 | 4 | 0 | 0 | 3 | 1 | 75.0 |
| 2014 | 6 | 0 | 0 | 4 | 2 | 66.7 |
| 2015 | 20 | 0 | 0 | 8 | 12 | 40.0 |
| 2016 | 27 | 0 | 0 | 6 | 21 | 22.2 |
| 2017 | 38 | 0 | 0 | 3 | 35 | **7.9** |
| 2018 | 24 | 0 | 0 | 6 | 18 | 25.0 |
| 2019 | 17 | 0 | 0 | 3 | 14 | 17.6 |
| 2020 | 16 | 0 | 0 | 1 | 15 | **6.2** |
| 2021 | 65 | 21 | 2 | 39 | 3 | 95.4 |
| 2022 | 39 | 31 | 3 | 1 | 4 | 89.7 |
| 2023 | 60 | 46 | 10 | 0 | 4 | 93.3 |
| 2024 | 82 | 74 | 3 | 4 | 1 | 98.8 |
| 2025 | 107 | 75 | 31 | 0 | 1 | 99.1 |
| 2026 | 23 | 13 | 10 | 0 | 0 | 100.0 |
| **All** | **652** | **260** | **59** | **131** | **202** | **69.0** |

Rows in this table are bucketed by the master's date column, which is really the listing date.

**The low 2016–2020 rates are a bug, not delistings.** Yahoo's search endpoint returns *nothing* when the query contains "Ltd" or a bracketed alias. For example, "Avenue Supermarts Ltd (DMart)" returns nothing, while "Avenue Supermarts" returns DMART.NS. I didn't patch Job 1 overnight, per your rules. I ran a read-only diagnostic instead (`diag_cleanquery.py`) that strips Ltd/Limited/brackets and requires the first trading day to fall within ±10 days of the listing date. It found candidates for **117 of the 202** unresolved rows, with no duplicates and no clashes with existing symbols. They are listed in `symbols_CANDIDATES_cleanquery.csv` and **have not been merged**. If they're merged, coverage would be about **567 / 652 (87%)**.

## 2. Job 2: holding target

**370 rows built. 7 missed.** `holding_target.csv` has 370 rows, matching the log.

| Listing-date path | Rows |
|---|---|
| known: real listing date in master (pre-existing, or recovered in 1b) | 240 |
| derived: first trading day in the yfinance series | 130 |
| dropped: no price series | 5 |
| dropped: series unusable (first bar too far from the listing date) | 2 |
| **Candidates** | **377** |

All 130 derived listing dates fall within **0–3 days** of the master's date column, which is the listing date. That's strong evidence that the Yahoo-found symbols are the right companies: a namesake stock would almost never start trading on the IPO's listing day.

## 3. Headline: H_label base rate

**41.1% of IPOs beat the Nifty over year one (n = 370).** Before quoting it, read §6: the direction and size of its bias are set out there.

## 4. Distribution of `excess_1y_pp`

| mean | median | p10 | p25 | p75 | p90 | min | max |
|---|---|---|---|---|---|---|---|
| +4.4 | **−10.4** | −55.1 | −35.4 | +27.6 | +82.9 | −88.6 | +436.8 |

The distribution is strongly right-skewed. The typical IPO lags the Nifty by about 10pp, but a few big winners pull the mean positive. Mean IPO 1-year return is +11.3% (median −2.8%), against a mean Nifty return of +6.9%.

## 5. Base rate by segment and by listing year

**Segment.** The master has no segment column. I matched rows to the NSE spine and trackers, which only cover Sep 2021 onwards. No master row matched an SME listing, so the master looks mainboard-only, which fits CLAUDE.md's figure of 624 mainboard IPOs.

| Segment | n | Base rate | Median excess |
|---|---|---|---|
| Mainboard (verified) | 233 | 41.2% | −9.6 |
| Not verified (no spine/tracker match, mostly pre-Sep-2021) | 130 | 38.5% | −12.8 |
| REIT / InvIT | 7 | 85.7% | +15.1 |

| Listing year | n | Base rate | Median excess (pp) | Median Nifty 1y (%) |
|---|---|---|---|---|
| 2010 | 36 | 19.4% | −25.5 | −10.0 |
| 2011 | 12 | 33.3% | −41.3 | 1.0 |
| 2012 | 5 | 40.0% | −9.3 | 9.4 |
| 2013 | 3 | 100% | +90.3 | 17.8 |
| 2014 | 4 | 100% | +28.1 | −2.5 |
| 2015 | 8 | 62.5% | +8.9 | 1.4 |
| 2016 | 6 | 33.3% | −14.6 | 17.1 |
| 2017 | 2 | 50.0% | −18.2 | 11.5 |
| 2018 | 6 | 16.7% | −37.3 | 4.2 |
| 2019 | 3 | 100% | +55.3 | −23.7 |
| 2020 | 1 | 0% | −47.3 | 45.0 |
| 2021 | 62 | 35.5% | −21.5 | 6.4 |
| 2022 | 35 | 65.7% | +13.2 | 11.9 |
| 2023 | 54 | 51.9% | +0.9 | 25.9 |
| 2024 | 79 | 34.2% | −11.2 | 4.2 |
| 2025 | 54 | 37.0% | −10.6 | −2.5 |

The years 2012–2020 have n ≤ 8 each, which is too thin to read anything into. Their small counts come from the §1 search bug.

## 6. Miss analysis and survivorship

579 master rows are old enough for a target (listed at least 370 days ago). Of those, **370 were built and 209 were not**:

| Why it's missing | Rows | What these rows are |
|---|---|---|
| Never got a symbol, but the clean-query diagnostic recovers one | ~117 | **Live listings**: DMart, HDFC Life, SBI Life, HAL, Polycab, CAMS, Bharat Dynamics and others. Median master "Current Gains" is **+49.7%**, against +13.6% for the built set. |
| Never got a symbol, and still unrecoverable | ~85 | **True survivorship.** Mostly 2010–11 small caps. Median current gain is **−64%**, and 55% are down more than 50%. |
| Job 2 miss: no price series (`target_MISSES.csv`) | 5 | ARISINFRA, CAPINVIT, SGLTL, SAH, IDEAFPO (which is an FPO, not an IPO) |
| Job 2 miss: first bar too far from the listing date | 2 | IGIL (first bar 10 days after the known listing date), IRBINVIT (36 days after) |

**How far survivorship overstates the base rate.** If the 117 search misses were merged and beat the Nifty at the observed rate:
- all 92 true dropouts (85 + 7) failing gives **34.6%**;
- the dropouts beating the Nifty at half the observed rate gives **37.8%**.

So **survivorship alone overstates the base rate by about 3–6.5pp**. The worst case is 41.1% → 26.3%, but only if every unbuilt row failed, and that's clearly false because the 117 are live and mostly winners.

Separately, the 117 search misses probably make the base rate *too low*, because they're better performers. The two biases partly cancel, but by an unknown amount. **Don't quote 41.1% as final until the 117 are merged and Job 2 is re-run.**

## 7. Restarts, errors and anomalies

| Time | Event |
|---|---|
| 01:58:36 | Launch #1 (`supervisor_log.txt`) |
| 01:58–02:09 | Job 1. 1b: 0 source conflicts. 1c: 333 queries, no 429s, no exceptions |
| 02:09:52 | Job 2 started: 377 candidates |
| 02:13:19 | Job 2 done: 370 built / 7 missed |
| 02:17:26 | Job 3 done: 444 of 450 symbols; `price_history.csv` has no duplicates or NaNs |
| 02:17:26 | ALL JOBS COMPLETE, exit 0. **0 restarts, 0 crashes, 0 rate-limits, 0 stalls** |

**Validation (all passed):**
- `holding_target.csv` has 370 rows and `target_MISSES.csv` has 7, both matching the log. No duplicate symbols.
- No `|excess_1y_pp|` above 500pp. The largest is ONELIFECAP at +436.8pp (see anomalies below).
- `H_label == (excess_1y_pp > 0)` on 370 of 370 rows. No row has exactly 0 excess.
- 10 random rows: `ipo_ret_1y_pct` recomputed from `listing_close` and `price_t365` matches within 2e-14 pp. I also checked all 370 rows (max difference 6e-14), plus the identity excess = IPO return − Nifty return.
- No non-positive prices and no NaNs.

**Anomalies:**
1. **PROTEAN has a wrong target.** The master's `listing_date` for it was already wrong before tonight (2025-02-06; the real listing date is 2023-11-13). Job 2 took it as "known", so the target covers the wrong year: excess −66.2pp, H = 0. **Exclude it or fix it before training.** It's the only row where a known listing date differs from the master's date column.
2. **Adjusted prices.** Job 2 uses `auto_adjust=True`. That's correct for splits and bonuses, but it makes the IPO leg a *total* return (dividends included) while `^NSEI` is a *price* index. That gives the IPO leg roughly a +1–1.5pp/yr edge. It's a small bias, but a systematic one towards H = 1.
3. **Listing-day close is used as the base, not the listing price.** For some 2010–11 small caps the gap is big: BEDMUTHA's listing-day close was +57% above its open, and TEXMOPIPES +37%. That's by design, but worth knowing.
4. **ONELIFECAP**: +447% IPO return in year one. The prices check out, but it's a 2011 operator-era stock. Consider winsorising.
5. **WAAREEINDO** (Indosolar): 1:100 reverse split in 2022. Yahoo adjusts it consistently, so the return is valid.
6. **Non-IPO rows in the master:** IDEAFPO (Vodafone Idea FPO), Yes Bank 2020 (an FPO, still unresolved), and 13 REITs/InvITs.

## 8. Issue-open-date recovery

`issue_dates_recovered.csv` has one row per master row (652), with columns company, symbol, listing_date, issue_open_date_true, source, confidence. **313 of 652 were recovered (48.0%).** `master_with_symbols.csv` was not modified.

| Year | Rows | Recovered | Rate |
|---|---|---|---|
| 2010–2020 | 276 | 0 | **0%**: no source covers these years |
| 2021 | 65 | 23 | 35.4% (the NSE spine starts 17 Sep 2021) |
| 2022 | 39 | 34 | 87.2% |
| 2023 | 59 | 53 | 89.8% |
| 2024 | 82 | 76 | 92.7% |
| 2025 | 108 | 104 | 96.3% |
| 2026 | 23 | 23 | 100% |

These year counts differ slightly from §1 for 2023 and 2025. This table buckets by `listing_date`, and PROTEAN's is wrong.

**Confidence:**
- **high** (NSE spine and tracker agree exactly): 120
- **medium** (one source only; spine 189, tracker 4): 193
- **rejected** (sources disagree): 0
- **none**: 339

The gap from open to listing is typically 6–8 days (median 8).

**Flags** (`issue_dates_FLAGS.csv`): one row. PROTEAN shows an open date 458 days before the listing date, and the cause is the wrong listing date from anomaly 1. No recovered open date falls after its listing date.

Pre-2021 open dates need another source, such as BSE's archive or the RHP cover pages.

## 9. What to look at before training

1. **Merge the 117 clean-query symbols, then re-run Job 2** (about 4 minutes). This is the biggest open issue, because the current H sample under-represents 2016–2020 and probably under-states the base rate. Review `symbols_CANDIDATES_cleanquery.csv` first. The proper fix is a two-line change to Job 1c's query cleaning, which I left for you to approve.
2. **Fix or exclude PROTEAN.**
3. **Decide the scope for REITs/InvITs and FPOs.** They're different instruments; 7 REIT/InvIT rows are in the H target with an 85.7% base rate, and IDEAFPO / Yes Bank 2020 are follow-on offers. The same rule should apply to Model L.
4. **Nifty benchmark:** switch to Nifty 50 TRI, or use unadjusted-for-dividends IPO prices, so both legs are measured the same way.
5. **The master date column is the listing date.** Any D0–D3 leakage cut-off for Model L must use `issue_open_date_true`, which exists for only 48% of rows and none before 2021.
6. **Sample size for H:** 370 rows now, perhaps about 480 after step 1. By the 10–15 rows-per-feature rule, H supports roughly 30–40 features at most. Fewer is better given the skew.
7. **Winsorise `excess_1y_pp`** if any continuous version is used. The label itself is fine.
8. `run_overnight.py` Job 1 is resumable, but a re-run will start 1c from scratch for any rows whose name changes. Merging the 117 through a reviewed script is safer than re-running Job 1.

## Files produced

| File | What it is |
|---|---|
| `master_with_symbols.csv` | Updated by Job 1: 450 symbols, plus new `company_as_listed`, `*_source` columns, and ISINs and listing dates from 1b |
| `holding_target.csv` | 370 rows |
| `target_MISSES.csv` | 7 rows |
| `price_history.csv` | Job 3 output, 444 rows |
| `job1b_CONFLICTS.csv` | Empty: no source conflicts |
| `issue_dates_recovered.csv`, `issue_dates_FLAGS.csv`, `issue_dates_summary.txt` | Issue-open-date recovery, from `recover_issue_dates.py` |
| `symbols_CANDIDATES_cleanquery.csv` | Diagnostic only, not merged; from `diag_cleanquery.py` |
| `run_log.txt`, `supervisor_log.txt`, `report_stats.txt` | Logs and statistics |

Not touched: `fetch_rhp.py` and all RHP work, as instructed.

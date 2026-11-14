# IPO Agent — final handover (14 November 2026)

Written for someone starting cold. Model L is live and working. Model H is scrapped (H63).

---

## A. Data and information locations

| item | location | committed or local-only | source | refresh method | terms status |
|---|---|---|---|---|---|
| The master dataset | `data/master_with_symbols.csv` | committed | a bought/compiled IPO list, symbols recovered by us | `recover_symbols.py`, `clean_master.py` | ours to use |
| Subscription history | `data/master_with_symbols.csv` (`Total`, `QIB`, `HNI`, `RII`) | committed | the master; live figures from NSE/BSE/Chittorgarh | `nse_subscription.py`, `chittorgarh_live.py` | **H47/H51** for NSE; **B2** for Chittorgarh (>= 3 s) |
| Chittorgarh harvest | `data/chittorgarh_backfill.csv`, `data/chittorgarh_anchor_lockin.csv`, `data/chittorgarh_id_probe.csv` | committed | chittorgarh.com, one request per IPO id | `chittorgarh_backfill.py` | **B2**: personal use, >= 3.2 s, robots re-read every run |
| Chittorgarh full-year tables | `data/chittorgarh_mainboard_periods.csv`, `data/chittorgarh_mainboard_fy.csv`, `data/chittorgarh_period_financials.csv` | committed | same pages, every period column | `chittorgarh_periods.py` | **B2** |
| Chittorgarh HTML cache | `_local/cg_html_cache/` (154 MB, 482 files) | **local-only, gitignored** | the fetched pages themselves | re-fetch with `chittorgarh_periods.py` | **B2** |
| The valuation block (H59) | `data/h59_valuation_block.csv`, `data/h59_valuation_coverage.csv` | committed | aggregator primary, Tickertape + RHP second sources | `h59_valuation_block.py` | **H58**: Tickertape personal, non-commercial, >= 3 s, no S&P field |
| Tickertape annuals | `data/tickertape_annuals.csv`, `data/tickertape_match.csv` | committed | tickertape.in stock pages | `tickertape_second_source.py` | **H58** |
| Tickertape page cache | `_local/tickertape/` (480 MB) | **local-only** | the fetched pages | re-fetch as above | **H58** |
| RHP PDFs | `_local/rhp_fetched/` (3.6 GB), `_local/rhp_manual/` (118 MB), `_local/rhp_replacement/` (23 MB) | **local-only, gitignored** | SEBI (mainboard), BSE SME | `restore_rhp_pdfs.py` from `data/verified_rhp_manifest.csv` (URL + SHA-256 per file) | public filings |
| RHP manifest and types | `data/verified_rhp_manifest.csv`, `data/rhp_doc_type.csv`, `data/rhp_replacements.csv`, `data/rhp_sources.csv` | committed | our own fetch records | `build_rhp_manifest.py` | — |
| RHP text cache | `data/rhp_text_cache/` (198 MB, 445 docs) | **local-only, gitignored** | the PDFs | `build_text_cache.py` | — |
| RHP table cache | `_local/rhp_table_cache/` (296 MB) | **local-only** | the PDFs | `build_table_cache.py` | — |
| RHP page index | `data/rhp_page_index.csv` (6,166 rows) | committed | the text cache | `build_page_index.py` | — |
| RHP extracted values | `data/rhp_valuation_values.csv`, `data/rhp_master_values.csv`, `data/manual_rhp_values.csv` | committed | the PDFs via the readers | `rhp_master_pass.py`, `run_extraction.py` | — |
| Derived ratios | `data/valuation_ratios.csv`, `data/valuation_ratios_h45.csv` | committed | the above | `derive_ratios.py`, `derive_pb.py`, `derive_post_issue.py` | — |
| Quarantine | `_local/rhp_quarantine/` (currently empty) | **local-only** | documents that failed hard rule 4 or rule 3 | — | — |
| Check set (ground truth) | `reports/rhp_check_set.csv` (281 rows, 20 companies), `reports/rhp_check_set_docs.csv` | committed | **hand-read** from numbered pages | transcribe more by hand | — |
| Reader gate | `reports/READER_GATE.csv`, `reports/READER_GATE_SUMMARY.csv`, `reports/READER_GATE.md` | committed | scoring the readers against the check set | `rhp_reader_gate.py` | — |
| Nifty 50 TRI | `data/NIFTY50_TRI.csv` | committed | niftyindices.com | `fetch_nifty_tri.py` | **H47/H51** |
| Index / P-E / VIX history | `data/nifty_pe_history.csv`, `data/india_vix.csv`, `data/sector_index_*.csv` | committed | NSE / NSE Indices | the fetchers in `market_context.py`, `market_heat.py` | **H47/H51** |
| Sector map | `data/sector_map.csv` | committed | NSE industry files, BSE as a second source | `bse_sector_fill.py`, `correct_manual_sectors.py` | **H47/H51** |
| Corporate actions | `data/corporate_actions.csv` | committed | NSE | `post_listing_filings.py` | **H47/H51** |
| Symbol and name changes | `data/nse_symbol_changes.csv`, `data/nse_name_changes.csv`, `data/company_aliases.csv` | committed | NSE | `company_aliases.py`, `recover_symbols.py` | **H47/H51** |
| Equity list, holidays | `data/nse_equity_list.csv`, `data/nse_holidays.csv` | committed | NSE | `nse_holidays.py` | **H47/H51** |
| Listing prices, day-1 turnover | `data/listing_prices.csv`, `data/day1_turnover.csv` | committed | NSE/BSE bhavcopies | `listing_prices.py`, `model_h_turnover.py` | **H47/H51** |
| Bhavcopy caches | `data/bhavcopy_cache/`, `data/bhavcopy_raw_cache/` | **local-only, gitignored** | the exchanges | re-fetch; **no bulk re-fetch without a reason** | **H47/H51** |
| Adjusted IPO returns vs TRI | `data/holding_target.csv`, `data/holding_target_3y.csv`, `data/holding_target_corrected.csv` | committed | our own computation | `model_h_targets.py` | **this is DATA**, not a Model H artefact (H63) |
| Live decision log | `data/predictions_log.csv` (18 predictions, 14 outcomes) | committed | the live runs | append-only; **never hand-edit** | — |
| Sent markers | `data/sent_markers.csv`, `data/live_markers.csv` | committed | the live runs | `sent_markers.py`, `live_markers.py` | — |
| Model L card | `data/model_l_v1.1*.json`, `reports/MODEL_L_CARD.md` | committed | the fit | `retrain_l.py`, `write_model_l_card.py` | — |
| Decisions and plan | `DECISIONS.md` (H1–H63), `PROGRESS.md`, `PLAN.md`, `PLAN_AMENDMENT_01/02.md`, `CLAUDE.md` | committed | — | — | — |
| Source map | `SOURCE_MAP.md` | committed | — | — | — |
| Reports | `reports/` (98 files) | committed | — | — | — |

### The local-only caches, and backing them up

**Nothing under `_local/`, `data/rhp_text_cache/` or `data/bhavcopy_cache/` is in git.** That
is deliberate — together they are about **5 GB**. All of it is re-fetchable, and
`data/verified_rhp_manifest.csv` carries a URL and a SHA-256 for every PDF, so a rebuilt
cache can be proved identical to this one.

**Recommendation: copy them to an external disk now.** Re-fetching 445 RHPs from SEBI at
3 s a request is roughly an hour of unattended work, and the 482 Chittorgarh pages another
26 minutes; the risk is not the time but that a source changes or blocks in the meantime.
A disk died once in this project already (2 November) and everything local was lost.

```bash
rsync -a --progress ~/Projects/ipo-agent/_local/ /Volumes/<DISK>/ipo-agent-local/
rsync -a --progress ~/Projects/ipo-agent/data/rhp_text_cache/ /Volumes/<DISK>/ipo-agent-text-cache/
```

---

## B. Access and infrastructure

**Names only below. No secret value appears in this file, and none should ever be written
into this repository — it is public.**

| item | detail | what breaks if it expires or is lost |
|---|---|---|
| GitHub repo | `AshishKohar1/ipo-agent`, **public** by the user's decision (H51) | — |
| Branch | `main`, the only branch (F1) | — |
| Tags | `model-h-final` (the full Model H state), `pre-housekeep`, `stage-NN-done` | the recoverability of deleted work |
| SSH key | named **"MacBook Air"** on the GitHub account | `git push` stops working; re-add a key in GitHub → Settings → SSH keys |
| Git identity | `AshishKohar1 <ashishkohar@yahoo.com>` | commit attribution only |
| Workflow | `.github/workflows/live-model-l.yml` ("Model L live") | the whole live pipeline |
| Workflow | `.github/workflows/retry-infra-failure.yml` | the automatic retry after an infrastructure failure |
| Secret name | `GMAIL_ADDRESS` | the email cannot authenticate; no report is sent |
| Secret name | `GMAIL_APP_PASSWORD` | same — **this is the one that expires in practice** |
| Secret name | `EMAIL_TO` | the report is composed and then has nowhere to go |

### The cron jobs

GitHub's own scheduler ran **5 to 9 hours late**, which is useless for a 15:00 deadline, so
the schedule is driven from **cron-job.org**, which calls the workflow by API.

| job | cron (UTC) | IST | body / mode |
|---|---|---|---|
| email attempt 1 | `45 8 * * 1-5` | 14:15 | `mode=email` |
| email attempt 2 | `0 9 * * 1-5` | 14:30 | `mode=email` |
| email attempt 3 | `15 9 * * 1-5` | 14:45 | `mode=email` |
| email attempt 4 | `30 9 * * 1-5` | 15:00 | `mode=email` |
| day-end capture | `0 14 * * 1-5` | 19:30 | `mode=final` |
| weekly audit | `0 5 * * 6` | 10:30 Sat | `mode=audit` |

Four attempts because a single call can fail; `sent_markers.py` makes the send idempotent,
so the second to fourth attempts do nothing once one has gone out.

**The cron-job.org token** is a GitHub **fine-grained personal access token** scoped to
**Actions: write, this repository only**. Rotate it at GitHub → Settings → Developer
settings → Personal access tokens → Fine-grained tokens, then paste the new value into each
cron-job.org job's request header. If it expires, every job returns 401 and **no email is
sent at all, silently** — the workflow is simply never triggered.

**The Gmail app password** is rotated at Google Account → Security → 2-Step Verification →
App passwords: delete the old entry, create a new one, and update the `GMAIL_APP_PASSWORD`
repository secret. It is a 16-character value; it is not the account password.

---

## C. Model L — the live model

| item | value |
|---|---|
| What it decides | whether to **bid** on a mainboard IPO, from subscription at 15:00 on the final day |
| Model | `model_l_v1.1`, the only Model L (H1); numpy logistic regression, no scikit-learn (rule 10) |
| Features | **Set A, frozen**: `log1p(Total)` + `log(issue size)` (A1, H2). Nine literature candidates were tested and all nine rejected |
| The rule (H17) | **L1 bids at Total >= 28.39x** (target: listing gain > 0), **L2 at >= 54.02x** (target: > 10%) |
| What is printed | the verdict and the threshold met, **never a probability as a literal chance** (G2) |
| Walk-forward AUC | L1 **0.8084**, L2 **0.8809** (pooled) |
| Email timing | four attempts, 14:15–15:00 IST; the 15:00 one is the last before the 16:00 cutoff |
| Send window | enforced in `send_daily_email.send_window()`; outside it the run exits without sending |
| Data sources | NSE primary for the IPO list and subscription, failing over to BSE then Chittorgarh (`failover.py`). Every fetch is logged with its URL in `data/live_fetch_log.csv` |
| The tripwire | `tripwire.py` — refuses to send a verdict when the model's inputs or the thresholds are not what the card says |
| Retrain | `python retrain_l.py` monthly, then `python retrain_review.py --email` to see the proposed change. **The thresholds do not move until you accept them**; the review is a proposal, not an application |

### The live record so far

| IPO | L1 | L2 | Total | listing gain % | L1 right? | L2 right? |
|---|---|---|---|---|---|---|
| HD Fire Protect | **BID** | **BID** | 85.12x | +23.62 | yes | yes |
| Tonbo Imaging India | **BID** | **BID** | 80.78x | +65.86 | yes | yes |
| BLS Polymers | **BID** | **BID** | 171.83x | +64.03 | yes | yes |
| Bombay Coated and Special Steels | **BID** | no | 35.47x | +11.60 | yes | — |
| Fusion CX | no | no | 3.39x | +5.54 | — | — |
| Bonfiglioli Transmissions | no | no | 15.25x | 0.00 | — | — |
| Sahajanand Medical Technologies | no | no | 5.01x | +7.44 | — | — |
| Zetwerk Manufacturing | no | no | 1.74x | +5.38 | — | — |
| Paras Healthcare | no | no | 1.16x | +3.90 | — | — |
| Jio Platforms | no | no | 11.17x | +21.36 | — | — |
| EAAA India Alternatives | no | no | 2.01x | +0.56 | — | — |
| SFC Environmental Technologies | no | no | 2.42x | +7.45 | — | — |
| M. K. Sons Fine Jewels | no | no | 3.68x | +5.74 | — | — |

| measure | promise | live |
|---|---|---|
| L1 hit rate | 90% | **4 of 4 = 100%** |
| L2 hit rate | 80% | **3 of 3 = 100%** |

**Read that honestly. Four bids is not evidence of a 100% hit rate.** And the other side of
the ledger matters: of the 9 no-bids with an outcome, **8 listed above zero**. In this
window almost everything went up, so the thresholds' selectivity cost more than it saved —
the model bid on 4 of 13 and was right each time, while a buy-everything rule would have
been right 12 times out of 13. One good quarter for IPOs is not a test of a model built to
avoid the bad ones.

---

## D. Model H — scrapped

| item | detail |
|---|---|
| Goal | how much of an allotment to **keep**: `excess_1y = IPO return (listing close → +365d) − Nifty 50 TRI over the same window`, label 1 if > 0. Secondary `excess_3y` |
| Design (H30) | WoE bins fitted in the training fold only, IV selection, numpy logistic regression, scheme C expanding walk-forward with a Y-2 embargo, a missing value as its own bin, one variable per 10 outcomes |
| Why a separate model | the correlation between listing gain and long-run CAGR is **0.218**. The two share almost no signal and were never merged |

| claim | bar, fixed in advance | result |
|---|---|---|
| **H29** per-IPO scorecard | top 20% band: >= 50 picks, >= 54% hit, Wilson 95% lower bound > base rate | **FAIL** — AUC 0.5338; 83 picks, 53.01%, Wilson 42.38% vs base 43.13% |
| **H35** cohort / market heat | gap >= 10pp, sign holds in >= 75% of test years, p < 0.05 | **FAIL** — 14.47pp PASS, sign **33%** FAIL, p = 0.00883 PASS |
| **H60** combined firm + valuation | H29, unchanged | **FAIL** — 87 picks PASS, **44.83%** vs 54% FAIL, Wilson **34.82%** vs base 42.76% FAIL; pooled AUC 0.5239 |

**Why it was scrapped.** Three independent attempts, each measured against a bar written
down before the run, all failed. H60 was the best remaining case — the widest variable set
the stability analysis admitted, the longest window, and the first time the aggregator was
reconciled against a second source — and it scored 0.5239 against a coin flip's 0.5. The
pooled band's hit rate came in **below** the base rate.

One finding worth keeping: the model scores **hot vintages** highest, and hot vintages beat
the index least. 2021, 2022 and 2025 supplied 63 of H60's 87 pooled picks. That is H35's
cohort result reappearing inside the per-IPO fit, and it is why adding more firm variables
did not help.

Everything is recoverable at tag **`model-h-final`**.

---

## E. Challenges log

The most important section. Marked honestly.

| # | challenge | impact | overcome? | how | lesson |
|---|---|---|---|---|---|
| 1 | GitHub's scheduler fired **5–9 hours late** | a 15:00 IST deadline cannot be met; the whole purpose of the system fails | **yes** | moved the trigger to **cron-job.org** calling the workflow by API, four attempts 14:15–15:00, idempotent via `sent_markers.py` | a free scheduler's "cron" is best-effort. If a deadline matters, do not trust it |
| 2 | **joblib / scikit-learn banned** | the fitted model could not be loaded or refitted on the laptop | **yes** | a validated numpy logistic regression and a portable JSON model card; rule 10 | the original cause (Windows Application Control blocking DLLs) is gone, but the rule stayed because the model was fitted and frozen without it |
| 3 | **NSE terms and blocks** | the primary data source prohibits automated collection, and returns 403 | **partly** | **H47/H51**: the user accepts the risk for personal use; one attempt per host per run, no header rotation, no retry loop, no proxy, and a 403 fails over to BSE or Chittorgarh and says so in the report | a block is a decision by the other side. Working around it is where a project becomes something else |
| 4 | **BSE bhavcopy empty for 154 dates** | the failover is not a complete substitute | **partly** | those dates are recorded as missing, never interpolated | a failover's coverage must be measured, not assumed |
| 5 | **Windows → Mac path bug** | `work_list()` returned zero documents; `rhp_reader_gate.score()` returned an empty frame and `summarise()` died on `KeyError: 'field'` | **yes** | `repo_paths.repo_file()` in one place, replacing eight hand-rolled joins | a CSV holding paths is a portability bug waiting for a new machine |
| 6 | **Disk loss** (2 November) | every local cache gone: PDFs, text cache, bhavcopies, venv | **yes** | restored from `data/verified_rhp_manifest.csv` by URL + SHA-256; proved faithful two ways — the rebuilt cache reproduced a prior report **byte-identically**, and all **124 of 124** hand-quoted ground-truth lines were present | the manifest, not the cache, is the asset. Keep the thing that lets you rebuild |
| 7 | **DRHPs passed the prospectus guard** (H57) | a draft read as a final document corrupts every value from it | **yes** | a position-based **title-line** test, then self-reference. 445 documents: 428 RHP, 17 prospectus, **0 DRHP, 0 UNCLEAR** | my first version tested for the phrase *anywhere* in the first four pages and flagged 37 of 430 — 35 of them genuine RHPs, because an RHP cover back-references its own draft. Position mattered, presence did not |
| 8 | **SEBI files the DRAFT under "RHP"** | the resolver asked for an RHP and got a DRHP, byte-identical SHA | **yes** | fall back to the PROSPECTUS slot; three documents replaced, DRHPs quarantined | the slot a document comes out of is not what the document is |
| 9 | **Stale gate report** (H53) | a report on disk read exactly like a finished run and I nearly reported its numbers as current | **yes** | extraction library versions recorded in the cache, `textcache.lib_drift()` reports a mismatch, reports written only after every stage completes | a partial run that leaves yesterday's output in place is worse than a crash |
| 10 | **P/B regression** (H54) | the fallback referenced two variables absent from the values file, so it could never fire — and it was an H5 violation besides | **yes** | `pre_issue_nav()` / `post_issue_nav_routes()` with an explicit `POST_PREFERENCE`, every pair reconciled at 5% | a fallback that is never exercised is not a fallback. Test the path, not the intention |
| 11 | **Stub periods in Chittorgarh** | 279 of 482 mainboard rows had no full financial year, because `parse()` kept only the latest column | **yes** | `parse_periods()` reads every period column; the full year comes from another column of the same page or stays NULL. **146 → 482 of 482** now carry a full year. Nothing annualised | the data was already on the page we had fetched. Look before you fetch again |
| 12 | **A non-March fiscal year** | three December-year-end companies were classified as stubs | **yes** | H59 amendment: a non-March month-end counts when the page shows two of it twelve months apart and no 31 March column — exactly three companies across 482 | and the first implementation picked the **stub quarter** for Hexaware because it iterated a set; the longest consecutive annual run now decides |
| 13 | **Readers' column and year proof** (H50) and **H55 minimum sample** | three readers "passed" at 100% on 1, 1 and 5 correct values — 100% of one is a coin landing heads | **yes** | H55: precision >= 95% **and** >= 10 correct, else `INSUFFICIENT`. After transcribing 13 more RHPs, `shares_outstanding_pre_issue` passes at **100% on 12** | a precision figure without a denominator is not a measurement |
| 14 | **Share-count guard errors, and the LIC exception** | counts far too small (a historical allotment row) and far too large (the aggregate rupee capital read as a share count) | **partly** | `derive_pb.share_count_plausible` is two-sided; it flags 5 of 387 — four genuine errors and **LIC, where the guard is wrong**, because its ceiling assumes a minimum public offer LIC was relaxed from at ~3.5% | a one-sided guard reported 133 of 153 as plausible when 121 was the truth. And a guard needs its own exceptions documented |
| 15 | **15:00 vs final subscription** | the figures at 15:00 understate final demand, so a near-threshold NO is uncertain | **not overcome — stated** | the email says so every day (H23). **No permitted source publishes day-wise subscription history**, so the day-wise models and the final-day forecaster were cancelled (H1) | some uncertainty cannot be modelled away. Print it instead of hiding it |
| 16 | **H16 reversal** | a decision was taken and then had to be undone | **yes** | reversed in `DECISIONS.md` with the reason, not deleted | a decisions log is only useful if the wrong ones stay visible |
| 17 | **H18 / H28 renumbering** | two different decisions were both called H18, so citations became ambiguous | **yes** | the 2026-10-03 name-similarity decision was renumbered **H28**; H18 now means only the browser-header relaxation | numbering is an interface. Reusing a number breaks every reference to it |
| 18 | **Survivorship bias** | delisted and suspended companies vanish from the price source and are disproportionately failures, so any base rate computed after dropping them is optimistic | **not overcome — stated** | `data/target_MISSES.csv` must be read alongside any result | this one cannot be fixed with better code. It is a property of the available data |
| 19 | **Single-source variables** | RPT %, litigation quantum, customer concentration, promoter experience, uses-of-proceeds count and auditor qualification exist only in the RHP and cannot be reconciled | **not overcome — flagged** | kept, flagged `single_source_unverified` (H26), never described as reconciled | rule 2 cannot be satisfied by wishing. Label it and move on |
| 20 | **Second sources are licence-limited** (H58) | eight candidate sites audited, **one** permits | **partly** | Tickertape only, on terms; Screener.in and Trendlyne forbid it in their own words; the paid data MCPs were not authorised (the user's decision) | the ceiling on rule 2 here is legal, not technical. Trendlyne's robots.txt welcomes `ClaudeBot` while its terms forbid exactly this project — **both gates must pass** |
| 21 | **The readers' recall** | four of five readers withhold on 9–13 of 15–17 check-set documents; 29 of 39 withholdings share one cause, that no P&L column reproduces a stated EPS on the pre-issue share count | **not overcome** | a widening via the NAV anchor was implemented, measured at precision **66.7% → 42.9%**, and **reverted**: many RHPs strike their NAV on the stub balance sheet, so the anchor matches the stub column correctly and returns the wrong quantity | the fix that improves recall and destroys precision is not a fix. Measure before you keep it |
| 22 | **L1/L2 under-delivery against the promise** | 4 bids and 3 bids is far too small a sample to claim the 90%/80% hit rates, and 8 of 9 no-bids also listed up | **not overcome — open** | the live record is printed in full in section C, both sides of it | precision on four picks is not a hit rate. The honest statement is "not yet measurable" |

---

## F. How to resume on a new Mac

```bash
xcode-select --install
```

```bash
git clone git@github.com:AshishKohar1/ipo-agent.git ~/Projects/ipo-agent
```

```bash
cd ~/Projects/ipo-agent && python3.14 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
python check_env.py
```

`check_env.py` must print **15/15 checks passed** before anything else is run. It checks the
data-loading contract, the pinned packages and the network.

Then rebuild the local caches, **in this order** — each step depends on the one before:

```bash
python restore_rhp_pdfs.py
```

```bash
python build_text_cache.py
```

```bash
python build_table_cache.py
```

```bash
python build_page_index.py
```

`restore_rhp_pdfs.py` re-fetches every PDF from the URL in
`data/verified_rhp_manifest.csv` and verifies its SHA-256; a mismatch quarantines the file
rather than using it. Allow about an hour — SEBI is called no more often than every 3 s.

If you copied `_local/` and `data/rhp_text_cache/` to an external disk, restore those
instead and skip the three cache builds.

The live pipeline needs nothing local: it runs on GitHub Actions from the committed data.

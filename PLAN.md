# IPO Analyst Agent — Master Plan

This file is the single source of instructions for building the IPO Analyst Agent.
In Stage 0 it is committed to the repository as `PLAN.md`. Every session reads it.

---

## 1. Objective

Build, validate and run two models for Indian IPOs, both of which improve as new IPOs list.

- **Model L (listing gains) — decides whether to bid.**
  L1 = P(listing gain > 0). L2 = P(listing gain > 10%).
  Runs before bidding closes. When final-day subscription isn't known yet, it uses a
  conservative forecast of it.
- **Model H (hold after listing) — decides how much of an allotment to keep.**
  Runs after an IPO lists. Predicts P(IPO beats the Nifty 50 Total Return Index over the
  365 days from listing close) and recommends what % of the allotment to hold.

The user bids only for listing gains. With no model edge, the default after listing is
**sell** — historically only ~37–40% of IPOs beat the index over a year.

**Done means:** both models validated out-of-sample by walk-forward testing, running live,
logging every prediction before its outcome is known, and retraining as new IPOs list.

---

## 2. Current state (verify in Stages 0–1; do not assume)

- Master dataset: 652 mainboard IPOs, 2010 to May 2026, with QIB/HNI/RII/Total subscription
  and listing gain. **Its `Date` column is the listing date, not the issue-open date.** True
  open dates for 2021+ are in `issue_dates_recovered.csv`.
- `master_with_symbols.csv`: 578 of 652 with symbols. `exclude_reason` flags 29 rows
  (13 FPO, 14 REIT/InvIT, 1 depository receipt, PROTEAN bad listing date).
- Official Nifty 50 TRI from NSE Indices, 2009 to Sep 2026.
- Holding targets vs TRI: `excess_1y` 491 rows (40.3% beat index); `excess_3y` 331 rows (36.0%).
- `models/framework.py`: numpy logistic regression (validated against statsmodels Logit to
  3e-10), walk-forward validation, target-window embargo, recency weighting, calibration
  and threshold tables. `models/model_l.py`, `models/model_h.py`, model cards.
- Model L walk-forward: L1 AUC 0.765, ≥90% threshold → 97.7% hit rate. L2 AUC 0.878,
  ≥80% → 79.7% (fails), ≥85% passes. Total vs QIB/HNI/RII collinearity (VIF 83) unresolved.
- Model H baseline (subscription + size + listing gain only): pooled walk-forward AUC
  0.525 (1y), 0.562 (3y).
- `fetch_rhp.py` resolvers: SEBI (open), BSE SME (open), NSE (behind a disclaimer —
  disabled), BSE mainboard (not implemented). 5 of 5 verification companies passed:
  Hyundai, Jupiter, CapitalNumbers (SME, matched on net offer), Syngene, TD Power
  (2011, prospectus fallback). 8 PDFs in `rhp_pdfs/`.
- Windows Application Control on the laptop blocks scikit-learn and parts of statsmodels.

---

## 3. Stage protocol — MANDATORY

Sessions can end without warning (memory, token or time limits). This protocol makes sure
no completed work is ever lost.

**At the start of every session**
1. `git fetch`, check out branch `work` (create it from `main` if missing), `git pull`.
2. Read `CLAUDE.md`, `PLAN.md`, `PROGRESS.md`, `DECISIONS.md`.
3. Choose the lowest-numbered stage that is not `DONE` and whose dependencies are met
   (section 6). If a stage is `IN_PROGRESS`, resume it from its last sub-checkpoint —
   do not restart it.

**Starting a stage**
4. Set its status to `IN_PROGRESS` with an IST timestamp in `PROGRESS.md`. Commit and push.

**During a stage**
5. Save intermediate results to files after every meaningful unit of work.
6. Commit and push at least every ~20 minutes of work, and always before any step expected
   to run longer than ~10 minutes.
7. Any loop over many items (IPOs, companies, pages) must be idempotent: record per-item
   status in a progress CSV and skip completed items on resume.

**Ending a stage**
8. Run the stage's acceptance checks.
9. Write `reports/STAGE_NN_REPORT.md` (format in section 8).
10. Set status to `DONE`, or `FAILED` with the reason. Commit and push.
11. You may start the next stage in the same session **only after** this commit is pushed.

**Gates**
12. At a gate, write the gate report, set status `AWAITING_USER`, commit, push. Do not start
    any stage that depends on that gate. Continue with other unblocked stages if any exist.
13. The user answers in the form `Gate X decision: …`. Record it verbatim in
    `DECISIONS.md` with the date, then continue.

**Safety**
14. Never end a turn with uncommitted work. If you may be close to a limit, stop at the next
    commit point rather than starting new work.
15. If a stage fails its acceptance checks twice, mark it `FAILED`, document why, and move
    only to stages that don't depend on it.
16. At the end of every session, update the 5-line summary at the top of `PROGRESS.md`:
    finished, in progress, open gates, next stage, anything blocked.

Stage 0 runs only on the user's laptop. Stages 1+ run in Claude Code on the web (preferred)
or on the laptop. The `work` branch on GitHub is the source of truth; on the laptop always
`git pull` before running anything.

---

## 4. Global rules

1. **Never fabricate a value.** A failed or missing value is written as NULL with a logged
   reason. A wrong value corrupts every ratio and weight derived from it.
2. **Reconcile every value.** Compare across independent sources. If the max pairwise
   relative difference exceeds 5%, write NULL and log both values and the reason.
   - Independent means derived from a **different original filing**. Aggregator copies of
     the RHP (Chittorgarh, IPOMatrix) only check our extraction, not the RHP itself.
     Chittorgarh and IPOMatrix share a parent — they count as one source.
   - RHP financials are restated; annual reports are as-reported. Log legitimate
     differences with reason `restatement_basis`.
3. **Single-source variables** (e.g. RPT %, litigation, customer concentration) are kept
   but flagged `single_source_unverified`, and never described as reconciled.
4. **Read `data/` only through `dataio.py`.** No hardcoded filenames, sheet names, header
   rows or exact column spellings. Report match rates on every join.
5. **Sources and access.** RHPs only from SEBI (mainboard) and BSE SME.
   `NSE_DOWNLOADS_ALLOWED` stays `False`. Respect robots.txt and site terms. Never bypass a
   disclaimer, login, CAPTCHA or click-through. If a site blocks automated access, stop
   using it and report. At least 3 s between SEBI requests, 1 s elsewhere.
6. **Every PDF must pass `_verify_is_prospectus()`** before use.
7. **No leakage.** Timestamp every feature by when it becomes knowable. Model L uses only
   information available before the bid deadline, or forecasts of it. Walk-forward
   validation with target-window embargo.
8. **SME and mainboard are modelled separately.** SME Model L runs in shadow mode:
   outputs labelled `PROVISIONAL — not for bid decisions`, logged, never used for verdicts.
9. Rows with an `exclude_reason` are excluded from every model.
10. **Estimator:** use the validated numpy logistic regression. Do not add scikit-learn.
11. **`predictions_log.csv` is append-only.** Never edit or delete past rows.
12. **Agreed decisions (section 5) are fixed.** If evidence contradicts one, report it at the
    next gate. Never change one silently.
13. All times in IST. No secrets, tokens or passwords in the repository.
14. Process PDFs one at a time, by page range, and close them promptly — cloud sessions
    have memory limits.

---

## 5. Agreed decisions

### Model L
- Targets: L1 = listing gain > 0; L2 = listing gain > 10%.
- Required hit rates: **L1 90%, L2 80%.** Threshold = the lowest probability threshold whose
  out-of-sample hit rate meets the requirement **and** whose Wilson 95% lower bound is at
  least the requirement minus 5pp **and** which fires on at least 20 IPOs.
- Walk-forward: for each test year T, train on IPOs listed before T. Use the last 5 test
  years with enough data. Select using **pooled** AUC (concatenate all out-of-fold
  predictions), not the mean of per-year AUCs.
- Recency weight = 0.5^(age_years / half_life), half-life ∈ {2, 3, 5, 8 years, none},
  chosen by pooled AUC. Always report effective sample size (Σw)² / Σw².
- Class weights balanced.
- Feature set: decided at Gate A.
- Day naming: `day_1`, …, `day_before_final`, `final_day` — never "day 3".
- Final-day forecaster outputs P10 / P50 / P90. **Model L is fed P10** (conservative).
- GMP is tested as an input; included in production only if it improves held-out results.
- Decision-point models D0–D3 are superseded by the forecaster approach.
- Retraining monthly; champion/challenger; PSI drift monitoring.
- Every IPO is ingested after listing — mainboard and SME, bid or not.

### Model H
- Post-listing model. Primary target `excess_1y` vs Nifty 50 TRI (label = excess > 0).
  Secondary `excess_3y`.
- Method: credit scorecard (WoE binning, IV selection, logistic on WoE, points).
- Must beat baseline pooled walk-forward AUC: 0.525 (1y), 0.562 (3y).
- Embargo: a training row is eligible only if listing date + 365 days (or + 1095) falls
  before the test year begins.
- Learns with a one-year lag.
- News is a veto gate, not a model feature.
- Hold sizing: default sell; enabled only after Gate E.

### Red-flag veto (applies to both models)
Three or more flags → verdict `VETO`, shown alongside the model's own verdict. Initial flags
(thresholds may be revised at a gate, never silently):
1. Revenue or PAT declined in the most recent year
2. Auditor qualification or adverse opinion
3. Related-party transactions > 20% of revenue
4. Top-10 customers > 40% of revenue, or dependence on a single licence/approval
5. Pre-IPO allotment within 12 months at > 30% below the issue price
6. Criminal or regulatory proceedings naming a promoter or director
7. OFS > 50% of the issue with no stated reason for the exit
8. Negative operating cash flow in 2 of the last 3 years

### RHP handling
- RHP only; if SEBI has no RHP, use the final prospectus and label it. **No DRHPs.**
- In the cloud: download → verify → extract → keep values, page numbers, source text line,
  SHA-256 and URL → **discard the PDF**. Any PDF can be re-fetched from SEBI and verified
  against its SHA-256.
- On the laptop: stop cleanly if free disk space drops below 2 GB.
- Normalise money to ₹ crore; always keep the original unit.

### Out of scope
Portfolio or trading agent for seasoned stocks; accepting NSE's disclaimer; DRHP downloads;
running Model H before bidding.

---

## 6. Dependencies

| Stage | Title | Depends on | Ends in |
|---|---|---|---|
| 0 | Repository setup (laptop) | — | — |
| 1 | Cloud environment check | 0 + user's cloud setup | — |
| 2 | Model L feature comparison | 1 | **Gate A** |
| 3 | Calibration curve + final thresholds | Gate A | — |
| 4 | Day-wise subscription + GMP history | 1 | — |
| 5 | Final-day forecaster + GMP test | Gate A, 4 | — |
| 6 | Productionize Model L | 3, 5 | **Gate B** |
| 7 | Go live (Model L) | Gate B | — |
| 8 | RHP extraction build + spot-check | 1 | **Gate C** |
| 9 | RHP batch pilot (10 companies) | Gate C | **Gate D** |
| 10 | RHP full batch (chunked) | Gate D | — |
| 11 | Model H scorecard | 10 | — |
| 12 | Hold-sizing backtest | 11 | **Gate E** |
| 13 | Integration + wrap-up | 7, Gate E | — |

When the next stage in order is blocked, move to the next unblocked one.

---

## 7. Stages

### Stage 0 — Repository setup  [LAPTOP ONLY]
Runs in Claude Code on the user's Windows laptop in `C:\Projects\ipo-agent`.
**Only Stage 0 runs in this session. Stop after it.**

1. Run `check_env.py`; record the result. Check `git --version`. If git is missing, stop
   and ask the user to install Git for Windows.
2. Write `data/verified_rhp_manifest.csv`: for every PDF in `rhp_pdfs/`, record company,
   document type, SEBI/BSE URL, SHA-256, page count, verification date.
3. Create `requirements.txt` pinned to the currently working versions of: pandas, numpy,
   requests, yfinance, pdfplumber, openpyxl, statsmodels, beautifulsoup4, lxml.
4. Create `.gitignore` excluding: `*.pdf`, `rhp_pdfs/`, `_backup_*/`, `__pycache__/`,
   `*.pyc`, `.venv/`, `.env`.
5. Make the code OS-independent: `pathlib` everywhere, UTF-8 file I/O, no Windows-only
   paths or shell commands. Fix anything found and list it in the report.
6. Copy this file to `PLAN.md`. Create:
   - `PROGRESS.md` — 5-line summary block, then a table of all stages with status and
     timestamps (Stage 0 `IN_PROGRESS`, the rest `NOT_STARTED`)
   - `DECISIONS.md` — empty decision log
   - `reports/`
7. Update `CLAUDE.md` — merge, don't overwrite: add a "Session start" section pointing to
   PLAN.md section 3; refresh "Current state" to match section 2; state that the `work`
   branch is the source of truth.
8. Warn if any single file exceeds 50 MB.
9. `git init`, commit everything, add the remote URL the user provides, push `main`, create
   branch `work` from `main`, push `work`. Git may open a browser for GitHub sign-in —
   tell the user to complete it.
10. Write `reports/STAGE_00_REPORT.md`, set Stage 0 `DONE`, commit and push to `work`.
11. Final message to the user, in plain English: what was pushed, and the cloud setup steps
    (connect GitHub at claude.ai/code; create an environment with network access **Full**
    and setup script `pip install -r requirements.txt`; select this repository).

**Acceptance:** repo on GitHub with all code and data except PDFs; `work` branch exists;
manifest has one row per PDF; `PROGRESS.md` shows Stage 0 `DONE`.

### Stage 1 — Cloud environment check
1. Confirm the session is on Linux and `requirements.txt` installed cleanly.
2. Run `check_env.py`. Make its Windows-specific checks OS-aware; don't delete them.
3. Test reachability with one light request each: www.sebi.gov.in, www.niftyindices.com,
   www.nseindia.com, www.bseindia.com, www.bsesme.com, query2.finance.yahoo.com,
   www.chittorgarh.com, www.ipoji.com, www.investorgain.com, www.screener.in, www.rbi.org.in.
   If any required domain is blocked, set Stage 1 `FAILED`, tell the user exactly which
   domains are blocked, and stop.
4. Integrity: master 652 rows; 29 `exclude_reason` flags; `excess_1y` 491 rows;
   `excess_3y` 331 rows; TRI series present and gap-free; numpy estimator regression test
   passes.
5. Re-fetch Syngene's RHP from SEBI; confirm its SHA-256 matches the manifest; delete it.

**Acceptance:** all checks pass.

### Stage 2 — Model L feature comparison → GATE A
Mainboard, both targets (L1, L2). Four candidate sets:

| Set | Features |
|---|---|
| A | log1p(Total) + log(issue size) |
| B | log1p(QIB) + log1p(HNI) + log1p(RII) + log(issue size) |
| C | Set A + market IPO heat |
| D | Set B + market IPO heat |

**Market IPO heat** = mean listing gain of mainboard IPOs that listed in the 30 days before
this IPO's bidding opened. Use the true open date where recovered; otherwise cutoff =
listing date − 10 days. If fewer than 2 IPOs fall in the window, widen to 60 days; if still
fewer than 2, use the long-run median and record a flag.

For each set report: pooled AUC and Gini; per-year AUC; chosen half-life; VIF for every
feature; coefficient signs (every subscription coefficient must be positive); HC3
significance; threshold tables for L1 (90%) and L2 (80%) under the section-5 rule.

**Gate A report** must include: a side-by-side table; a recommendation; and this note —
choosing Set B or D means the forecaster must predict three final-day categories, and QIB
is the hardest because institutions often bid mostly on the final day. The user has said he
leans towards the category split; show the evidence plainly either way.

### Stage 3 — Calibration curve + final thresholds  (after Gate A)
1. Walk-forward out-of-fold probabilities for the chosen set.
2. Fit two calibrators in numpy: isotonic (pool-adjacent-violators) and Platt. Validate
   out-of-time: for each test year T, fit on out-of-fold predictions from years before T,
   apply to year T.
3. Compare raw vs Platt vs isotonic on held-out years: Brier score and a decile
   reliability table.
4. Derive L1/L2 thresholds two ways: (a) the bucket rule in section 5; (b) the lowest
   threshold where calibrated probability ≥ the required hit rate.
5. Adopt the calibrated method only if its held-out Brier score beats raw **and** its
   threshold still passes the section-5 hit-rate, Wilson and 20-fire checks on held-out
   data. Otherwise keep the bucket method. Record the outcome in `DECISIONS.md`.

**Acceptance:** final L1 and L2 thresholds recorded with evidence.

### Stage 4 — Day-wise subscription and GMP history  [large — chunked]
Scope: every mainboard IPO whose bidding opened on or after 1 Oct 2023; SME for the same
period stored separately.

For each IPO and each bidding day, record end-of-day Total, QIB, HNI (NII) and RII
subscription, plus GMP in ₹ and as % of the price-band cap. Label days `day_1` …
`day_before_final`, `final_day`.

- Subscription sources: Chittorgarh and IPO Ji; reconcile under rule 2.
- GMP sources: InvestorGain and IPO Watch. GMP is unregulated and sites often copy each
  other, so agreement does not prove accuracy — tag GMP `sentiment_grade`.
- Respect rule 5. If a source forbids automated access, stop using it and report.
- Progress in `data/daywise_progress.csv`; commit every 10 IPOs.

**Output:** `data/daywise_subscription.csv` in long format — ipo, isin, date, day_label,
category, value, source_a, source_b, status.

**Acceptance:** coverage by month; reconciliation counts; final-day Total matches the master
Total within 5% for at least 95% of overlapping IPOs, with every mismatch logged.

### Stage 5 — Final-day forecaster + GMP test  (after Gate A and Stage 4)
1. Predict log(final-day subscription) from log(day_before_final), log(day_1), category mix
   at day_before_final, log issue size and number of bidding days. Recency-weighted.
   P10 / P50 / P90 from residual quantiles. If Gate A chose categories, forecast QIB, HNI
   and RII separately as well as Total.
2. Also support a forecast from `day_1` alone, with wider bands.
3. Validate walk-forward by quarter. Report P10–P90 coverage (target ~80%) and median
   absolute log error.
4. Integration test on history: L probability using (a) actual final subscription,
   (b) forecast P10, (c) forecast P50. Report how often the verdict changes, and how often
   P10 produces a bid where actual final would not.
5. **GMP test:** corr(GMP %, final subscription); whether GMP improves the forecaster;
   whether GMP and a `gmp_sub_divergence` feature (z(GMP) − z(subscription)) add to Model L
   beyond subscription — pooled walk-forward AUC on the 3-year subset. Recommend include
   or exclude; the decision is taken at Gate B.

**Acceptance:** P10–P90 coverage between 70% and 90%; GMP findings documented.

### Stage 6 — Productionize Model L → GATE B
1. Final fit with the chosen features, half-life and thresholds. Save `model_l_v1.0`, plus
   its coefficients as JSON so the scoring formula is portable.
2. `predict_live(inputs, subscription_as_of)` with `subscription_as_of` ∈ {`final`,
   `day_before_final`, `day_1`}. For anything but `final`, use forecaster P10 and label the
   output `Forecast-based (P10) — conservative`.
3. SME Model L in shadow mode; log to `sme_shadow_log.csv`.
4. `predictions_log.csv` (append-only): IST timestamp, IPO, ISIN, segment, model version,
   inputs, subscription_as_of, probabilities, thresholds, verdict, veto flags.
5. `ingest_outcomes.py`: finds every IPO listed since its last run — mainboard and SME, bid
   or not — gets the listing price from two sources, reconciles, appends to the dataset,
   and scores the matching prediction-log rows.
6. `retrain_l.py` (monthly): challenger vs champion on the latest 12 months out-of-sample.
   Promote only if the challenger's pooled AUC ≥ champion's and calibration is not worse;
   otherwise keep the champion and write an alert. PSI per input vs training distribution —
   alert above 0.25. Record every version in `models/registry.csv`.
7. `run_live_l.py`:
   a. Get the IPO calendar (open and close dates) from two sources.
   b. For IPOs whose final day is today or tomorrow, fetch current subscription (and GMP if
      approved) from two sources and reconcile.
   c. Score; apply the red-flag veto where RHP data exists.
   d. Write `reports/live/YYYY-MM-DD.md`: per IPO — name, segment, closing date,
      subscription as-of, forecast band, L1/L2 probabilities, verdict, veto status, and the
      line "Decide before your broker's IPO cutoff on <date>".
   e. Append to `predictions_log.csv`.
8. Write `MODEL_L_CARD.md` v1.0.
9. Dry run on currently open IPOs, or the most recent week if none are open.

**Gate B report:** dry-run output, model card summary, GMP recommendation. Stop.

### Stage 7 — Go live  (after Gate B)
Create Remote Routines via `/schedule` if available in the session; otherwise write exact
setup steps in `LIVE_SETUP.md` for the user:
- Daily 19:00 IST — `run_live_l.py` (day_before_final forecasts)
- Daily 14:00 IST — `run_live_l.py` (final-day update, early enough for broker cutoffs)
- Weekly, Monday 08:00 IST — `ingest_outcomes.py` + weekly digest
- Monthly, 1st, 08:00 IST — `retrain_l.py`

Routines count against the account's daily run allowance — schedule nothing beyond this.

**Acceptance:** the first scheduled run succeeds and writes a report.

### Stage 8 — RHP extraction build + spot-check → GATE C
1. Re-fetch the documents in the manifest; verify each SHA-256; delete them at the end.
2. Locate sections from the table of contents, with a regex fallback on section headers.
   Process page ranges only.
3. Build extractors in `extract/`:
   - `objects` — issue size, fresh vs OFS, uses of proceeds (count), GCP %
   - `capital` — promoter holding pre/post, pre-IPO allotments (price and date), lock-ins
   - `financials` — restated, 3 years: revenue, EBITDA, PAT, net worth, debt, operating and
     free cash flow, receivable/inventory/payable days, contingent liabilities
   - `basis` — EPS, RoNW, NAV, P/E, P/B, and the full **peer table** with peer multiples
   - `rpt` — related-party transactions as % of revenue
   - `litigation` — counts and ₹ amount of the top 5 cases, by category, against company,
     promoters and directors
   - `risk` — customer and geographic concentration, licence dependence
   - `management` — promoter experience, board composition and independence, KMP pay
4. **Governance** — capture raw flags and metrics under MSCI's six key issues: Ownership &
   Control, Board, Pay, Accounting, Business Ethics, Tax Transparency. Don't hand-weight
   them — the scorecard learns weights. Flag auditor qualification prominently.
5. Every value carries: value, original unit, value in ₹ crore, page number, the exact source
   text line, document URL, SHA-256, extractor version.
6. Reconcile under rule 2 against NSE/BSE issue notices (size, price, split), the master
   dataset, the first shareholding pattern filed after listing (promoter %), Screener or the
   first post-listing annual report (financials), and recomputed ratios.
7. **Spot-check sheet:** about 20 values across all 5 companies, at least 3 per company.
   Cover issue size, fresh/OFS, revenue, PAT, net worth, P/E, promoter %, RPT %, litigation
   count, a peer multiple — and at least 5 values where the unit (lakh, million, crore)
   matters. Columns:
   `# | Company | Field | Extracted value + unit | ₹ crore | Page | Exact source text line | SEBI PDF link`
   Save as `reports/SPOTCHECK.xlsx` and `reports/SPOTCHECK.csv`, and **show the full table
   in the session message** — the user checks it on a phone.

**Gate C:** stop. The user replies with the row numbers that are wrong. Record them, fix the
extractors, re-run, and report field-level accuracy.

### Stage 9 — RHP batch pilot → GATE D
Ten mainboard companies from the Model H queue: at least 3 from 2010–2014, 3 from
2015–2019, 3 from 2020–2025. Per company: resolve → download → verify → extract →
reconcile → write → discard the PDF.

Measure: minutes per company, peak memory, verified rate, RHP vs prospectus fallback,
not found (by year), completeness per field, reconciliation outcomes. Extrapolate total time
for the full queue and recommend a chunk size.

**Gate D report.** Stop.

### Stage 10 — RHP full batch  [large — chunked]
- Queue: every mainboard IPO with an `excess_1y` label, excluding flagged rows and anything
  already processed.
- Chunk size as approved at Gate D. Commit every 5 companies. Per-company status in
  `data/rhp_progress.csv`.
- Retry transient errors (timeouts, 5xx) up to 3 times with backoff. After two identical
  non-transient failures on one company, mark it failed with the reason and move on. If 5
  consecutive companies fail, stop the chunk and report — the site has probably changed.
- End report: processed, verified, fallback, not found by year, failures by reason, field
  completeness, reconciliation outcomes.

### Stage 11 — Model H scorecard
**Targets:** `excess_1y` (primary), `excess_3y` (secondary), both vs Nifty 50 TRI.

**Candidate variables**
- Valuation: P/E, P/B, EV/EBITDA, P/S — each ÷ peer median; industry P/E; market cap ÷
  revenue.
- Quality/moat: RoCE 3-yr average; RoCE − cost of capital (91-day T-bill from RBI + 6%);
  gross-margin standard deviation; revenue and PAT 3-yr CAGR; OCF ÷ PAT; years of positive
  free cash flow.
- Balance sheet: D/E, interest cover, working-capital days, contingent liabilities ÷ net worth.
- Governance: the six MSCI key-issue metrics and flags from Stage 8.
- Ownership: post-issue promoter %, change in promoter holding, fresh issue %, pre-IPO
  allotment price ÷ issue price, mutual-fund share of the anchor book.
- Business risk: top-10 customer %, geographic concentration, promoter experience, company
  age, litigation ÷ net worth.
- Competition: peer multiples, industry growth, market share where stated.
- **Sentiment:** an Indian Baker–Wurgler-style composite — first principal component (numpy
  SVD on standardised inputs) of IPO count (trailing 30 days), market IPO heat, NSE market
  turnover, India VIX and the advance–decline ratio, each measured as of the listing date
  from official sources. Drop and document any component that can't be sourced officially.
  Report variance explained. Also test separately: own listing gain, Nifty TRI 30-day return.

**Method — credit scorecard.** Fit binning and WoE **inside each walk-forward training fold
only**.
1. Fine-class, then coarse-class each numeric variable into 3–6 bins, each holding at least
   5% of rows. Missing values get their own bin.
2. WoE = ln(%good / %bad), good = beat TRI. Enforce monotonic WoE where the economics are
   clear: higher valuation premium ↓, higher RoCE ↑, higher D/E ↓, higher RPT ↓, more
   litigation ↓, governance flags ↓. Elsewhere let the data decide, and report it.
3. IV per variable. Drop IV < 0.02. Flag IV > 0.5 as possible leakage and investigate.
4. Drop one of any pair of WoE variables with |correlation| > 0.7, keeping the higher IV.
5. Logistic on WoE, class weights balanced, recency half-life selection, walk-forward with
   embargo.
6. Scale to points: 600 at odds 1:1, PDO 20.
7. Calibrate using the method adopted in Stage 3.

**Outputs:** IV table; bin tables with WoE; the points scorecard; pooled walk-forward AUC,
Gini and KS for 1y and 3y against the baseline; calibration table; PSI; `MODEL_H_CARD.md`.

**Acceptance:** report whether H beats the baseline (0.525 1y) — honestly, either way.

### Stage 12 — Hold-sizing backtest → GATE E
For every IPO H scored out-of-sample, simulate from listing close:
- **Always sell** — proceeds go into the Nifty 50 TRI (baseline)
- **Always hold** 12 months
- **Probability bands**, starting at <45% → 0%, 45–55% → 25%, 55–65% → 50%, 65–75% → 75%,
  >75% → 100%; re-tune cut-points on training folds only
- **Half-Kelly**: f = 0.5 × (p − (1−p)/b), clipped to 0–100%, where b = average gain of
  winners ÷ average loss of losers, measured on training folds within the same score band

Round partial holds to whole shares. Measure total return, volatility, maximum drawdown and
return per unit of risk — **after tax and costs**. Get current Indian equity short- and
long-term capital gains rates and exemptions from an official source (Income Tax Department
or the Finance Act) and cite it. State assumptions for brokerage, STT and exchange charges.

**Enable sizing only if** H's pooled walk-forward AUC ≥ 0.60 **and** the chosen rule beats
always-sell after tax. Otherwise H stays information-only.

**Gate E report** with a recommendation. Stop.

### Stage 13 — Integration and wrap-up  (after Stage 7 and Gate E)
1. `run_h_after_listing.py`: for each newly listed IPO, bid or not, extract its RHP, score
   Model H with RHP and listing-day data, output the hold % if sizing is enabled, and append
   to `predictions_log.csv`.
2. Add the red-flag veto section to the live Model L report for open IPOs whose RHP has been
   extracted.
3. Model H retraining quarterly (one-year label lag), champion/challenger as for L.
4. Final model cards, `CLAUDE.md`, `README.md`, and `reports/STAGE_13_REPORT.md`: what's
   live, every schedule, and how to operate it.

---

## 8. Report format

Every `reports/STAGE_NN_REPORT.md`:
- **Status:** DONE / FAILED / AWAITING_USER
- **What was done** — at most 5 lines
- **Key numbers** — a table
- **Deviations from plan** and why
- **Open issues**
- **For gates:** the exact decision needed, the options, and a recommendation

End every session with a short plain-English message to the user: what finished, what's in
progress, and anything waiting on them.

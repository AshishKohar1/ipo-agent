# IPO Analyst Agent — Master Plan

This file is the single source of instructions for building the IPO Analyst Agent.
In Stage 0 it is committed to the repository as `PLAN.md`. Every session reads it.

**Amended 2026-09-30 by `PLAN_AMENDMENT_01.md`** (kept in the repo as the audit trail).
The amendment's decisions A1–A3, B1–B5, C1–C5, D1–D2, E1–E2, F1–F2 are merged into the
sections below and logged in `DECISIONS.md`. Where this file and the amendment ever
disagree, the amendment wins and this file should be corrected.

---

## 1. Objective

Build, validate and run two models for Indian IPOs, both of which improve as new IPOs list.

- **Model L (listing gains) — decides whether to bid.**
  L1 = P(listing gain > 0). L2 = P(listing gain > 10%).
  Runs before bidding closes. **Three separate decision-point models** (`L_day1`,
  `L_day2`, `L_final_3pm`), each trained only on what is knowable at that moment —
  no forecaster (decisions C1, C2).
- **Model H (hold after listing) — decides how much of an allotment to keep.**
  Runs after an IPO lists. Predicts P(IPO beats the Nifty 50 Total Return Index over the
  365 days from listing close) and recommends what % of the allotment to hold.

The user bids only for listing gains. With no model edge, the default after listing is
**sell** — historically only ~37–40% of IPOs beat the index over a year.

**Done means:** both models validated out-of-sample by walk-forward testing, running live,
logging every prediction before its outcome is known, and retraining as new IPOs list.

---

## 2. Current state (verify; do not assume)

Updated 2026-09-30. Live stage status is in `PROGRESS.md`; that file wins on status.

- Master dataset: 652 mainboard IPOs, 2010 to May 2026, with QIB/HNI/RII/Total subscription
  and listing gain. **Its `Date` column is the listing date, not the issue-open date.** True
  open dates for 2021+ are in `issue_dates_recovered.csv` (313 of 652 recovered).
- `master_with_symbols.csv`: 578 of 652 with symbols. `exclude_reason` flags 29 rows
  (13 FPO, 14 REIT/InvIT, 1 depository receipt, PROTEAN bad listing date). Excluded rows
  are dropped from every model.
- Official Nifty 50 TRI from NSE Indices, 2009 to Sep 2026, `data/NIFTY50_TRI.csv`.
- Holding targets vs TRI: `excess_1y` 491 rows (40.3% beat index); `excess_3y` 331 rows (36.0%).
- `models/framework.py`: numpy logistic regression (validated against statsmodels Logit to
  3e-10), walk-forward validation, target-window embargo, recency weighting, `vif()`,
  `threshold_section5()`, calibration and threshold tables, model cards.
- **Stage 2 closed (Gate A).** Model L uses **Set A** = `log1p(Total)` + `log(issue size)`
  for both targets (decision A1). Walk-forward on 616 mainboard rows, test years 2022–2026,
  half-life 2 years chosen on pooled AUC: **L1 pooled AUC 0.8084** (Gini 0.617),
  **L2 pooled AUC 0.8809** (Gini 0.762). Set C is the standing challenger (A2); Sets B and D
  are rejected (A3). A paired bootstrap showed Set A reliably beats Set B on both targets and
  every other difference sits inside sampling noise.
- Out-of-fold predictions for all Stage 2 candidates are saved in `reports/oof/` — these are
  Stage 3's input.
- `market_heat.py`: leak-free market IPO heat (only IPOs that **listed** before this IPO's
  bidding opened; 30d → 60d → expanding median). Used by the Set C challenger.
- **Stage 4 sources settled (B1, B2).** IPO Ji, InvestorGain, ipoindex.in and iporupee.com
  are all off-limits. Chittorgarh is permitted for personal use at ≥3s per request.
  GMP is dropped as a model feature (B5) and is display-only (D1, D2).
- `fetch_rhp.py` resolvers: SEBI (open), BSE SME (open), NSE (behind a disclaimer —
  `NSE_DOWNLOADS_ALLOWED` stays False), BSE mainboard (not implemented). 5 of 5 verification
  companies passed: Hyundai, Jupiter, CapitalNumbers (SME, matched on net offer), Syngene,
  TD Power (2011, prospectus fallback). 8 PDFs in `_local/rhp_fetched/`, listed with URL + SHA-256 in
  `data/verified_rhp_manifest.csv`.
- `check_env.py` 13/13 and `stage1_env_check.py` pass on the laptop; all 11 required domains
  reachable. **The Linux/cloud `pip install` path is still unverified** — the first cloud
  session must re-run both.
- Windows Application Control on the laptop blocks scikit-learn and parts of statsmodels.
  Use the numpy estimator; import `Logit` from `statsmodels.discrete.discrete_model`, never
  `statsmodels.api`.

## 3. Stage protocol — MANDATORY

Sessions can end without warning (memory, token or time limits). This protocol makes sure
no completed work is ever lost.

**At the start of every session**
1. `git fetch`, then `git pull` on **`main`** (decision F1: single branch, no `work`).
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
or on the laptop. **`main` on GitHub is the source of truth** (decision F1) — there is a
single branch; completed stages are marked with a tag (`git tag stage-NN-done`), not a
branch. On the laptop always `git pull` before running anything.

**Git on this laptop:** chain commands separately, not with `&&` (decision F2) — it fails
in the older PowerShell here.

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
   **Blocked sources (decision B1) — never fetch, and never send a browser User-Agent to
   work around them:** IPO Ji (robots.txt names ClaudeBot and anthropic-ai), InvestorGain
   (`ai-train=no`), ipoindex.in (Terms of Use §10), iporupee.com (T&C). If any source's
   robots.txt or terms change to prohibit access, stop using it and report.
   **Chittorgarh is permitted for personal use (B2)** — robots.txt allows it and its
   disclaimer restricts public and commercial use, not private analysis. **≥3 s between
   requests, and re-read its robots.txt at the start of every run, aborting if it changed.**
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
  Implemented in `framework.threshold_section5()`. Applied to `L_final_3pm`, the only
  Model L (decision H1); decision C5's "separately per decision-point model" is moot now
  that there is one model. **Calibrated with isotonic regression before thresholding**
  (decision G1); the report prints the verdict and the threshold met, never the raw
  probability as a literal chance (decision G2).
- Walk-forward: for each test year T, train on IPOs listed before T. Use the last 5 test
  years with enough data. Select using **pooled** AUC (concatenate all out-of-fold
  predictions), not the mean of per-year AUCs.
- Recency weight = 0.5^(age_years / half_life), half-life ∈ {2, 3, 5, 8 years, none},
  chosen by pooled AUC. Always report effective sample size (Σw)² / Σw².
- Class weights balanced.
- **Feature set: Set A, FROZEN** — `log1p(Total subscription)` + `log(issue size)`, for
  both L1 and L2 (decision A1, Gate A closed 2026-09-30; frozen by decision H2).
  Nine literature-sourced candidates were tested out-of-sample on 624 mainboard IPOs and
  **all nine were rejected** — the table is in `PLAN_AMENDMENT_02.md` section A. Total
  subscription already aggregates every category's view expressed in money; re-adding the
  components is double-counting and drives Total's VIF to 90.0, which is the source of
  Dave (2022)'s negative coefficients (reproduced here: Total +26.26, QIB −5.25, HNI −3.04).
  Do not re-test these nine without new evidence.
- **Issue size coefficient (decision H4).** On 624 mainboard IPOs 2010–2026, controlling for
  subscription, the standardised coefficient is **−0.356** — slightly negative, consistent
  with Bansal & Khanna (2012) and Huang (2025). An earlier note claiming it had "flipped
  sign" came from a 588-row SME-heavy 2025–26 sample and did not generalise. Small either way.
- **Set C** (Set A + market IPO heat) is a **standing challenger** in monthly retraining.
  It is statistically tied with Set A; promote it only via the champion/challenger rule,
  never by hand (decision A2).
- **Sets B and D (the QIB/HNI/RII split) are rejected** (decision A3). The category figures
  are still **displayed** in every live report for the user's own judgement — they are not
  model inputs.
- Day naming: `day_1`, …, `day_before_final`, `final_day` — never "day 3".
- **One model only: `L_final_3pm`** (decision H1, supersedes C1). `L_day1`, `L_day2` and
  the final-day forecaster are **cancelled and their code paths deleted**, not left dormant.
  No permitted source publishes day-wise subscription history: Chittorgarh shows it live and
  deletes it once an IPO closes (measured in Stage 4A — 0 of 50 pre-2026 pages carry it);
  IPO Ji blocks Anthropic crawlers by name; InvestorGain, ipoindex.in and iporupee.com
  prohibit scraping. Stage 4B is cancelled for the same reason.
  Never feed day-N subscription into this model: the bias is large and one-directional
  (observed: Adroit Industries QIB 1.82x on day 2 → 195x on the final day).
- **No forecaster** (decision C2, reaffirmed by H1).
- **`L_final_3pm` is approximated until real 3pm data exists** (decision C3). No historical
  3pm snapshots exist, so it is trained on final-day subscription and the model card must
  label it **approximated, not measured**, stating plainly that final-day figures
  overestimate the 3pm position. It is rebuilt once ~40 IPOs of genuine 3pm data accumulate
  from the 19:00 snapshot job (B4).
- **Demand profile is displayed, never modelled** (decision H3).
  `retail_skew = log1p(RII) − log1p(QIB)`. Measured on 624 IPOs, median listing gain by
  quartile: most institution-skewed **+20.4%**, Q2 +4.1%, Q3 +2.2%, most retail-skewed
  **+1.6%**. Real signal, but adding it changes nothing (AUC 0.8832 → 0.8811) because it is
  already embedded in Total. It appears in the live report as
  `Demand profile: institution-led | balanced | retail-skewed`, with quartile cut-points
  fitted **on training data only**, and may never enter the model or override a verdict.
- **Uncertainty is reported, not hidden** (decision C4). Report each model's AUC and firing
  rate side by side, so the value of waiting a day is visible rather than assumed.
- **GMP is not a model feature** (decisions B5, D1): no permitted historical source exists.
  It is display-only — see "GMP" below.
- Retraining monthly; champion/challenger; PSI drift monitoring.
- Every IPO is ingested after listing — mainboard and SME, bid or not.

### GMP — display only
- GMP is **not** a model feature and **not** an automated fetch (D1). It appears in the live
  report as a field the user fills in manually, clearly marked as outside the model.
- Every live report logs the GMP value the user supplies (or blank) in
  `predictions_log.csv`, so its incremental value over subscription can be measured
  retrospectively after ~12 months (D2). Until then **no GMP-based rule may influence a
  verdict.**
- Required live-report format:

```
Orient Cables — closing today, bid by 4:00 PM
  L_final_3pm  L1: 94%  -> BID        (threshold 90%)
               L2: 71%  -> no         (threshold 85%)
  Subscription: Total 8.77x | QIB 3.1x | HNI 14.2x | Retail 6.4x   [15:00]
  Veto flags: none
  GMP: ____%   [NOT IN MODEL — your judgement only]
```

### Live schedule — Model L
The broker cutoff is **4:00 PM** (Paytm Money, user-confirmed — decision E1).

| Job | Time IST | Action |
|---|---|---|
| Score | **15:00** daily | Fetch subscription for IPOs closing today, score `L_final_3pm`, write report |
| Notify | **15:30** daily | Deliver the report — 30 minutes before cutoff |
| Snapshot | **19:00** daily | Record day-wise subscription (NSE + BSE) for every open IPO |
| Ingest | **Mon & Thu 08:00** | Add newly listed IPOs to the dataset, score past predictions |
| Retrain | 1st of month, 08:00 | Champion/challenger |

The 30-minute gap between scoring and notifying is deliberate: a slow fetch must not push
the reminder past the cutoff. If the 15:00 job fails, retry immediately and still notify by
15:30, marking the report `PARTIAL — verify subscription manually`.

**Model L goes live without any forecaster** — it is not a prerequisite (decision E2).

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

**Decision H5 — aggregator-first for headline financials.** Stop extracting from the RHP
anything an aggregator already publishes. Issue size, fresh/OFS split, offer price band, P/E
and P/B at offer, EPS, RoNW, NAV, revenue, PAT, net worth and total borrowings come from the
aggregator and the master dataset, with the RHP as the **verifying second source where
found**. This satisfies rule 2 properly, because the two are genuinely independent
derivations.

**Decision H6 — RHP extraction covers only what nothing else publishes.** These are Model
H's actual differentiators and exist only in the prospectus. Coverage is measured on **these**
fields, not on the headline financials; target **≥60%**:

- Related-party transactions as % of revenue
- Litigation: counts and ₹ quantum of the top 5, by category, against company, promoters,
  directors
- Customer concentration (top-10 %), geographic concentration, licence dependence
- Promoter experience (years), board size and independence ratio, KMP remuneration
- Auditor qualification / emphasis of matter
- Pre-IPO placement price and date; promoter holding pre and post issue; lock-in schedule
- Contingent liabilities as % of net worth
- Number of stated uses of proceeds; GCP as % of proceeds
- Anchor investor list, allocation, mutual-fund share, lock-in expiry dates
- MSCI six-key-issue governance capture: Ownership & Control, Board, Pay, Accounting,
  Business Ethics, Tax Transparency

**Decision H7 — provenance and refusal rules are non-negotiable.** Every extracted value
carries page number, exact source text line, document URL, SHA-256 and extractor version.
Where the unit is not present on the page, the ₹-crore conversion is **withheld**, not
assumed. A doubtful value is deleted, never shipped.

**Decision H8 — never ingest AI-generated summary tables as data.** A comparison table
produced by a general web-search assistant was reviewed and rejected: Jupiter Life Line and
Syngene shared an identical net worth (₹844.90 cr) and operating income (₹871.60 cr) across
a 2023 hospital chain and a 2015 CRO; Syngene was listed as "100% OFS" while also claiming
capital-expenditure use of proceeds; TD Power's net worth equalled its issue size; six
values were marked approximate; no value carried a page citation. Such tables may prompt a
human cross-check, never serve as a source. Related: the ipotrack.in article "Using IPO
Subscription Data to Predict Listing Day Performance" is **fabricated** (Nykaa stated as
23× / +9.4% / 2022 against an actual 81.78× / +77.87% / 2021; "Jio Financial Services IPO"
never existed — it was a demerger). It is blacklisted; treat unattributed AI-written SEO
content as hostile to the dataset.

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

Revised by amendment 01 section H. Live status is in `PROGRESS.md`.

| Stage | Title | Depends on | Ends in |
|---|---|---|---|
| 0 | Repository setup (laptop) | — | — |
| 1 | Environment check | 0 | — |
| 2 | Model L feature comparison | 1 | **Gate A** ✅ closed 2026-09-30 |
| 4A | Chittorgarh 20-IPO coverage sample | 1 | **Gate F** |
| 4B | ~~Day-wise subscription backfill~~ | — | **CANCELLED (H1)** |
| 3 | Calibration curve + final thresholds | Gate A ✅ | — ✅ closed 2026-09-30 |
| 5 | ~~Three decision-point models~~ | — | **CANCELLED (H1)** |
| 6 | Productionize Model L | 3 | **Gate B** |
| 7 | Go live (Model L) | Gate B | — |
| 8 | RHP extraction build + spot-check | 1 | **Gate C** |
| 9 | RHP batch pilot (10 companies) | Gate C | **Gate D** |
| 10 | RHP full batch (chunked) | Gate D | — |
| 11 | Model H scorecard | 10 | — |
| 12 | Hold-sizing backtest | 11 | **Gate E** |
| 13 | Integration + wrap-up | 7, Gate E | — |
| 14 | Apply Amendment 02 to PLAN/DECISIONS/CLAUDE | — | — |
| 15 | RHP extractor rebuild + night batch  **[NIGHT]** | 14 | **Gate C2** |
| 16 | Finalise and freeze `L_final_3pm` | 3, 14 | **Gate B** |
| 17 | Aggregator-first financial backfill  **[NIGHT]** | 14 | — |
| 18 | Anchor / lock-in backfill from Chittorgarh  **[NIGHT]** | 14 | — |
| 19 | Productionise + go live | Gate B | — |

**Night-batch policy (decision H9).** Any task expected to exceed ~30 minutes runs as an
unattended night batch: chunked, checkpointed per item, committed at least every 10 items,
resumable, and safe to kill at any moment. Night batches are scheduled **immediately after**
the model-logic changes in each session, so they use the idle hours.

When the next stage in order is blocked, move to the next unblocked one. **Stage 8 depends
only on Stage 1 and needs no decision from the user — it is the fallback whenever a gate
blocks everything else.**

## 7. Stages

### Stage 0 — Repository setup  [LAPTOP ONLY]
Runs in Claude Code on the user's Windows laptop in `C:\Projects\ipo-agent`.
**Only Stage 0 runs in this session. Stop after it.**

1. Run `check_env.py`; record the result. Check `git --version`. If git is missing, stop
   and ask the user to install Git for Windows.
2. Write `data/verified_rhp_manifest.csv`: for every PDF in `_local/rhp_fetched/`, record company,
   document type, SEBI/BSE URL, SHA-256, page count, verification date.
3. Create `requirements.txt` pinned to the currently working versions of: pandas, numpy,
   requests, yfinance, pdfplumber, openpyxl, statsmodels, beautifulsoup4, lxml.
4. Create `.gitignore` excluding: `*.pdf`, `_local/rhp_fetched/`, `_backup_*/`, `__pycache__/`,
   `*.pyc`, `.venv/`, `.env`.
5. Make the code OS-independent: `pathlib` everywhere, UTF-8 file I/O, no Windows-only
   paths or shell commands. Fix anything found and list it in the report.
6. Copy this file to `PLAN.md`. Create:
   - `PROGRESS.md` — 5-line summary block, then a table of all stages with status and
     timestamps (Stage 0 `IN_PROGRESS`, the rest `NOT_STARTED`)
   - `DECISIONS.md` — empty decision log
   - `reports/`
7. Update `CLAUDE.md` — merge, don't overwrite: add a "Session start" section pointing to
   PLAN.md section 3; refresh "Current state" to match section 2; state that **`main`**
   is the source of truth.
8. Warn if any single file exceeds 50 MB.
9. `git init`, commit everything, add the remote URL the user provides, push `main`. Git may
   open a browser for GitHub sign-in — tell the user to complete it.
   (Historical note: Stage 0 originally also created a `work` branch. Decision F1 of
   2026-09-30 retired it — there is one branch, `main`.)
10. Write `reports/STAGE_00_REPORT.md`, set Stage 0 `DONE`, commit and push to `main`.
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

### Stage 2 — Model L feature comparison → GATE A  ✅ CLOSED 2026-09-30

Four candidate sets were compared on mainboard IPOs for both targets, on an identical
616-row sample, walk-forward over test years 2022–2026, half-life chosen on pooled AUC.

| Set | Features | L1 pooled AUC | L2 pooled AUC | max VIF |
|---|---|---|---|---|
| **A** (chosen) | log1p(Total) + log(size) | 0.8084 | **0.8809** | 1.0 |
| B | log1p(QIB/HNI/RII) + log(size) | 0.7980 | 0.8721 | 5.3 |
| C (challenger) | A + market IPO heat | **0.8137** | 0.8755 | 1.1 |
| D | B + market IPO heat | 0.8098 | 0.8718 | 5.3 |

A paired bootstrap (3,000 resamples, identical rows) found **one reliable difference: Set A
beats Set B on both targets.** Every other gap, including whether market heat helps, sits
inside sampling noise. Half-life 2 years won for all eight combinations. Every subscription
coefficient was positive. The "VIF 83" problem was an artefact of mixing Total *with* the
categories — no candidate set does that.

**Gate A decision (A1–A3):** Set A for both L1 and L2; Set C retained as a standing
challenger for monthly retraining only; Sets B and D rejected, though the category figures
are still displayed in live reports. Full evidence: `reports/STAGE_02_REPORT.md`.
Out-of-fold predictions for all candidates: `reports/oof/`.

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

### Stage 4A — Chittorgarh coverage sample → GATE F

Before fetching anything in bulk (decision B3). Chittorgarh's own note says that for past
IPOs it publishes "final bidding detail as of the last day", so day-wise depth for older
years is unverified and may thin out.

1. **Read `chittorgarh.com/robots.txt` first and abort if it no longer permits access** (B2).
2. Sample **20 mainboard IPOs** from `master_with_symbols.csv` spread across 2010, 2013,
   2016, 2019, 2022 and 2025.
3. For each, record: is the **"Day-wise Subscription Details"** table present, how many
   bidding days it carries, which categories it has, and whether anchor allocation and
   lock-in dates are present.
4. **≥3 seconds between requests.**

**Acceptance:** a coverage table by year. **Then stop at Gate F** — no bulk fetch until the
user has seen the coverage.

### Stage 4B — Day-wise subscription backfill  ❌ CANCELLED 2026-10-01 (decision H1)

**Reason: there is no permitted source for day-wise subscription history.** Stage 4A
established that Chittorgarh publishes the day-wise table only while an IPO is open and
removes it at close — 0 of 50 pre-2026 pages carried it, and the 2026 anchor's own table
disappeared between two consecutive days. Every other aggregator that keeps it is blocked
(IPO Ji names Anthropic crawlers; InvestorGain, ipoindex.in and iporupee.com prohibit
scraping). A backfill would spend hours retrieving nothing.

**Kept from this stage:** forward collection (B4) — the 19:00 job snapshots live
subscription from the NSE and BSE official APIs for every open IPO, building a two-source,
fully permitted history going forward. Every night of delay loses one IPO permanently.
Anchor allocation and lock-in dates *are* archived on Chittorgarh and are backfilled by
**Stage 18** instead.

### Stage 5 — Three decision-point models  ❌ CANCELLED 2026-10-01 (decision H1)

**Reason: two of the three models have no training data and never will** — see Stage 4B.
`L_day1` and `L_day2` are cancelled together with the final-day forecaster, and their code
paths are **deleted, not left dormant**. The surviving model, `L_final_3pm`, is finalised by
**Stage 16**.

### Stage 6 — Productionize Model L → GATE B
1. Final fit with the chosen features, half-life and thresholds. Save `model_l_v1.0`, plus
   its coefficients as JSON so the scoring formula is portable.
2. `predict_live(total_subscription, issue_size_cr, qib=None, rii=None)` → `L_final_3pm`
   only (H1). It returns the L1 and L2 **verdicts** against their calibrated thresholds and
   the demand-profile label (H3), and per decision G2 prints the verdict and the threshold
   met — **never the raw probability as a literal chance**. There is no
   `subscription_as_of` dispatch and no forecaster.
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
   b. For IPOs whose final day is today or tomorrow, fetch current subscription from the
      NSE and BSE official APIs and reconcile. **GMP is never fetched** (D1) — the report
      carries a blank `GMP: ____%` field marked `[NOT IN MODEL — your judgement only]`, and
      whatever the user supplies is logged for later evaluation (D2).
   c. Score; apply the red-flag veto where RHP data exists.
   d. Write `reports/live/YYYY-MM-DD.md` in the format fixed by decision D2: per IPO —
      name, closing date and **"bid by 4:00 PM"**, the model used, L1/L2 probabilities with
      each model's own threshold and verdict, the displayed QIB/HNI/Retail/Total figures
      with their as-of time (A3), veto flags, and the blank GMP field.
   e. Append to `predictions_log.csv`.
8. Write `MODEL_L_CARD.md` v1.0.
9. Dry run on currently open IPOs, or the most recent week if none are open.

**Gate B report:** dry-run output and the `L_final_3pm` model card — AUC, calibrated
threshold, firing rate and hit rate for L1 and L2. No GMP recommendation — GMP is
display-only (B5, D1). Stop.

### Stage 7 — Go live  (after Gate B)

Create Remote Routines via `/schedule` if available in the session; otherwise write exact
setup steps in `LIVE_SETUP.md` for the user. Schedule fixed by decision E1 — the broker
cutoff is **4:00 PM** (Paytm Money):

| Job | Time IST | Action |
|---|---|---|
| Score | **15:00** daily | Fetch subscription for IPOs closing today, score `L_final_3pm`, write the report |
| Notify | **15:30** daily | Deliver the report — 30 minutes before the 4:00 PM cutoff |
| Snapshot | **19:00** daily | Record day-wise subscription (NSE + BSE) for every open IPO (B4) |
| Ingest | **Mon & Thu 08:00** | Add newly listed IPOs to the dataset, score past predictions |
| Retrain | 1st of month, 08:00 | Champion/challenger, including the Set C challenger (A2) |

The 30-minute gap between scoring and notifying is deliberate: a slow fetch must not push
the reminder past the cutoff. If the 15:00 job fails, retry immediately and still notify by
15:30, marking the report `PARTIAL — verify subscription manually`.

Routines count against the account's daily run allowance — schedule nothing beyond this.

**Acceptance:** the first scheduled run succeeds and writes a report.

### Stage 8 — RHP extraction build + spot-check → GATE C  ⚠️ SUPERSEDED by Stage 15

Stage 8 ran on 2026-09-30 and reached **24% coverage on the headline financial fields**
(`reports/STAGE_08_REPORT.md`). Gate C was **not** closed. Decisions H5 and H6 re-scope the
work: the headline financials move to the aggregator, and RHP extraction refocuses on the
H6 field list. Stage 15 replaces steps 3–7 below; the framework, provenance model and
section-location machinery built here are kept.

The original text follows for the record.

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

### Stage 14 — Apply Amendment 02  ✅
Merge `PLAN_AMENDMENT_02.md` into this file in place, record H1–H9 in `DECISIONS.md`, update
`CLAUDE.md`'s current-state table and stage list, and mark Stages 4B and 5 CANCELLED in
`PROGRESS.md` with the reason. Commit and push.

### Stage 15 — RHP extractor rebuild + night batch  [NIGHT] → GATE C2

**15a — rebuild the extractors (H5, H6).**
1. Remove the headline financial fields from RHP extraction; they now come from the
   aggregator with the RHP as verifier (H5).
2. Refocus the extractors on the **H6 field list**.
3. Fix the two failures found in Stage 8: **case-sensitive and layout-variant table
   detection**, and **unit detection** (lakh / lac / lacs / million / mn / crore / cr).
4. Keep every H7 safeguard: page number, exact source text line, document URL, SHA-256,
   extractor version, unit withheld rather than assumed, doubtful values deleted not shipped.
5. Iterate against the 8 PDFs in `data/verified_rhp_manifest.csv` until **H6-field coverage
   reaches ≥60%**. Report coverage per field and per document. If a field cannot reach 60%
   across vintages, **say so plainly rather than loosening the rules.**

**15b — night batch.** Queue every mainboard IPO in `master_with_symbols.csv` with an
`excess_1y` label and no `exclude_reason`. Per company: resolve from SEBI (BSE SME for SME)
→ download → verify SHA-256 and `_verify_is_prospectus()` → extract H6 fields → reconcile →
write to the database → **discard the PDF**.

Batch rules: ≥3 s between SEBI requests; per-company status in `data/rhp_progress.csv`;
commit every 5 companies; fully resumable; retry transient errors up to 3 times with
backoff; after two identical non-transient failures on one company mark it failed and move
on; **if 5 consecutive companies fail, stop the batch and report** — the site has probably
changed. Check free disk space before starting and **stop cleanly below 2 GB**.

**Gate C2 deliverable:** a fresh ~20-row spot-check drawn **only from H6 fields**, at least
3 per company, columns
`# | Company | Field | Extracted value | Page | Exact source text line | Document URL`.
Save as `reports/SPOTCHECK_V2.xlsx` and `.csv` and print it in full in the session message —
the user reviews on a phone. Then stop.

### Stage 16 — Finalise and freeze `L_final_3pm` → GATE B  (H1, H2, H3)
1. Retrain on **Set A only**, mainboard, 624 rows, excluding flagged rows. Logistic,
   class_weight balanced, walk-forward validation, **isotonic calibration** (G1), recency
   half-life by **pooled** AUC.
2. **Delete** the `L_day1`, `L_day2` and forecaster code paths entirely — not dormant.
3. Add the demand-profile display (H3): compute `retail_skew`, fit quartile cut-points **on
   training data only**, expose it as a report label. It must not enter the model or alter
   any verdict.
4. `predict_live` takes final-day subscription and issue size and returns the L1 and L2
   verdicts against their calibrated thresholds plus the demand-profile label, printing the
   verdict and the threshold met, never the raw probability as a literal chance (G2).
5. **Verify the nine rejected candidates of H2 reproduce on the current dataset**, so the
   rejection is recorded as evidence rather than assertion. Report any that disagree.
6. Refit on all eligible data, save `model_l_v1.0`, write `MODEL_L_CARD.md`.

**Gate B:** stop for approval before anything goes live.

### Stage 17 — Aggregator-first financial backfill  [NIGHT]  (H5)
Runs only after Stage 15b is running or complete, so the two do not contend for the same
sites. Re-read `chittorgarh.com/robots.txt` first and **abort if it no longer permits
access** (B2); ≥3 s between requests; resumable; commit every 10 companies.

Collect the H5 headline fields per company, reconcile against the master dataset under rule
2 (5% tolerance, **both** values logged on mismatch), and flag anything single-sourced.
**Acceptance:** coverage by year and reconciliation outcomes.

### Stage 18 — Anchor / lock-in backfill from Chittorgarh  [NIGHT]
Anchor investor names, allocations and lock-in expiry dates are archived on Chittorgarh IPO
pages (~41% overall, ~60% for 2020 onward) and feed Model H's empty ownership block. Same
rate limits and resumability as Stage 17. **Acceptance:** coverage by year.

### Stage 19 — Productionise + go live
Stages 6 and 7 as written above, with the single-model `predict_live` of H1.
**Model H's scorecard does not start until extraction is trusted.**

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

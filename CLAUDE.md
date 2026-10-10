# IPO Analyst Agent — project context

Read this before doing anything in this repo.

## Session start — do this first, every session

1. Follow the stage protocol in **`PLAN.md` section 3** exactly: `git fetch`, then
   `git pull` on **`main`**. There is a single branch (decision F1) — no `work`.
2. Read `CLAUDE.md`, `PLAN.md`, `PROGRESS.md`, `DECISIONS.md`.
3. Pick the lowest-numbered stage that is not `DONE` and whose dependencies are met
   (`PLAN.md` section 6). Resume an `IN_PROGRESS` stage from its last checkpoint.

**`main` on GitHub (github.com/AshishKohar1/ipo-agent) is the source of truth** — one
branch only (decision F1). Completed stages are marked with a tag (`stage-NN-done`), not a
branch. On the laptop, always `git pull` before running anything. Never end a turn with
uncommitted work. Chain git commands separately, not with `&&` (decision F2).

`PLAN.md` is the single source of instructions; where this file and `PLAN.md` disagree,
`PLAN.md` wins. `PLAN.md` was amended on 2026-09-30 and again on **2026-10-01** — see
`PLAN_AMENDMENT_01.md`, `PLAN_AMENDMENT_02.md` and `DECISIONS.md`.

**Night-batch policy (H9):** any task expected to exceed ~30 minutes runs as an unattended
night batch — chunked, checkpointed per item, committed at least every 10 items, resumable,
and safe to kill at any moment. Start it as early in the session as possible.

## What this project is

A two-model system for Indian IPOs, plus the data pipeline that feeds it.

- **Model L** — P(listing gain), decides whether to bid. Targets: L1 `listing_gain > 0`
  (required hit rate 90%) and L2 `listing_gain > 10` (80%). **Features: Set A** =
  `log1p(Total)` + `log(issue size)` — **frozen** (A1, H2); nine literature candidates were
  tested and all nine rejected, so do not re-test them without new evidence. Pooled
  walk-forward AUC: **L1 0.8084, L2 0.8809**. **One model only: `L_final_3pm`** (H1) —
  `L_day1`, `L_day2` and the forecaster are cancelled and their code paths deleted, because
  no permitted source publishes day-wise subscription history. Thresholds come from isotonic
  calibration (G1), and reports print **the verdict and the threshold met, never the raw
  probability as a literal chance** (G2). `retail_skew` is a **displayed** demand-profile
  label, never a feature (H3). (The earlier "AUC 0.883" came from random K-fold; the
  0.765/0.878 pair came from the mean of per-year AUCs. Both are superseded by pooled AUC.)
- **Model H** — post-listing, decides how much of an allotment to keep. Target
  `excess_1y = IPO_return(listing close→+365d) − Nifty 50 TRI return(same window)`,
  label 1 if > 0; secondary `excess_3y`. Baseline walk-forward AUC 0.525 (1y), 0.562 (3y).

The two models share almost no signal: correlation between listing gain and long-run
CAGR is 0.218. Never merge them.

## Hard rules

1. **Never fabricate a value.** If a source fails, write NULL and log it. A missing value
   costs one row; a wrong value corrupts every derived ratio and every fitted weight, and
   will not be found by inspection.
2. **Reconcile everything.** Each variable on each row is compared across independent
   sources. Max pairwise relative difference > 5% → NULL. See `reconcile.py`.
   Chittorgarh and IPOMatrix share a parent — they are NOT two independent sources.
3. **No manual downloads, and some sources are off-limits.** RHPs come from SEBI
   (mainboard) and BSE SME only; if SEBI has no RHP, use the final prospectus and label it.
   No DRHPs. `NSE_DOWNLOADS_ALLOWED` stays `False` — never accept a disclaimer or
   click-through. Never ask the user to fetch a document.
   **Never fetch from IPO Ji, InvestorGain, ipoindex.in or iporupee.com** (decision B1).
   **Rule 5 was relaxed by the user on 2026-10-05 (H18):** realistic browser headers MAY be
   sent to **official** sources — NSE, BSE, NSE Indices, SEBI — because the earlier ban on
   browser User-Agents was stricter than intended and was the only thing blocking us. Still
   forbidden: bypassing a login, CAPTCHA, paywall or click-through agreement; ignoring an
   explicit robots.txt disallow that applies to our client; and the B1 sources above.
   **Chittorgarh is permitted for personal use** at ≥3 s per request, re-reading its
   robots.txt at the start of every run (B2). (PLAN.md rule 5.)
4. **Verify every PDF before use.** `_verify_is_prospectus()` checks prospectus marker,
   company name on the cover, and ≥100 pages. A wrong URL must produce a logged failure,
   never a silent bad row.
5. **Leakage discipline.** Model L must only use data knowable before the bid deadline.
   Final subscription is NOT knowable before the final day, so Model L is fed the
   final-day forecaster's P10 (PLAN.md section 5). The earlier D0–D3 per-decision-point
   models are superseded.
6. **Separate models for SME and mainboard.** Their coefficients differ in sign on market
   hotness and band width. Pooling is wrong.
7. **Aggregator-first for headline financials (H5).** Do not extract from the RHP anything
   an aggregator already publishes — issue size, fresh/OFS, price band, P/E, P/B, EPS, RoNW,
   NAV, revenue, PAT, net worth, borrowings. Those come from the aggregator and the master,
   with the RHP as the verifying second source. RHP extraction covers only the **H6** list:
   what nothing else publishes.
8. **Never ingest an AI-generated summary table as data (H8).** One was reviewed and
   rejected — two unrelated companies with identical net worth, a "100% OFS" issue also
   claiming capex use of proceeds, six values marked approximate, no page citations. Use
   such tables to prompt a human check, never as a source. `ipotrack.in`'s subscription
   article is **fabricated** and blacklisted.

## Data loading contract

- Every read of a file under `data/` goes through `dataio.py`. No other module opens
  `data/` directly, and no module or doc hardcodes a `data/` filename.
- `dataio` finds files by glob pattern (`PATTERNS`). Zero matches, or several where one
  is expected, raises an error. It never silently picks one.
- Loaders only rename columns and parse dates. They never fill or estimate values.
- `python check_env.py` checks this contract, the packages and the network. It must
  pass before any overnight run.

## Current state (updated 2026-10-01 after PLAN Amendment 02)

`PROGRESS.md` is authoritative for stage status; this table is the orientation summary.

| Item | Status |
|---|---|
| Master dataset | 652 mainboard IPOs, 2010 – May 2026, in `data/` via `dataio.load_master()`. **Its `Date` column is the listing date, not the issue-open date.** True open dates for 2021+ in `data/issue_dates_recovered.csv` (313 of 652) |
| `data/master_with_symbols.csv` | 578 of 652 with symbols; `exclude_reason` flags 29 rows, dropped from every model |
| Benchmark | Official Nifty 50 TRI (NSE Indices), 2009 – Sep 2026, `data/NIFTY50_TRI.csv` |
| Holding targets vs TRI | `excess_1y` 491 rows (40.3% beat); `excess_3y` 331 rows (36.0%) |
| Framework | `models/framework.py` — numpy logistic regression, walk-forward + embargo, recency weighting, `vif()`, `threshold_section5()`, calibration, model cards |
| **Stage 0** | ✅ DONE — repo on GitHub, acceptance verified against the remote |
| **Stage 1** | ✅ DONE on the laptop — `check_env.py` 13/13, `stage1_env_check.py` all pass, 11/11 domains. **Linux/cloud `pip install` still unverified** |
| **Stage 2 / Gate A** | ✅ CLOSED 2026-09-30 — **Set A** for both targets (A1); Set C standing challenger (A2); Sets B/D rejected but categories still displayed (A3) |
| **Stage 3** | ✅ DONE — isotonic calibration adopted (G1, G2), independently verified 14/14 by `verify_stage3.py`. Fire iff calibrated p ≥ 0.90 (L1) / ≥ 0.80 (L2) |
| **Stage 4A / Gate F2** | ✅ CLOSED 2026-10-01 by H1. The ID walk solved company→Chittorgarh-id, but the day-wise table is **transient**: 0 of 50 pre-2026 pages carry it |
| **Stage 4B** | ❌ **CANCELLED** (H1) — no permitted source for day-wise history |
| **Stage 5** | ❌ **CANCELLED** (H1) — `L_day1`/`L_day2`/forecaster have no training data |
| **Stage 14** | ✅ DONE — Amendment 02 applied |
| **Stage 15** | RHP extractor rebuild on the H6 fields + night batch → **Gate C2**, target ≥60% coverage |
| **Stage 16** | Finalise and freeze `L_final_3pm` → **Gate B** |
| **Stage 17 / 18** | Night backfills: aggregator headline financials (H5); anchor and lock-in from Chittorgarh |
| **Stage 19** | Productionise + go live (absorbs Stages 6 and 7) |
| Model H | `models/model_h.py` baseline only: AUC 0.525 (1y), 0.562 (3y). RHP blocks are placeholders |
| RHP fetcher | SEBI + BSE SME resolvers, 5/5 verified; `data/verified_rhp_manifest.csv` has all 8 PDFs with URL + SHA-256 |
| RHP extraction | Stage 8 reached 24% on the headline financials and did **not** close Gate C; superseded by Stage 15, which measures coverage on the H6 fields instead. Framework (`extract/`), provenance model and TOC-driven section location with **measured** page offsets are kept |
| GMP | **not a model feature and never fetched** (B5, D1). Display-only field in live reports, logged for later evaluation (D2) |
| Live schedule | **Three** GitHub Actions jobs and nothing else: 15:00 IST weekday bid email, 19:30 IST weekday day-end capture, Saturday 10:30 capture audit. Two app routines survive: `ipo-retrain-monthly`, `ipo-ingest-outcomes`. The 15:00 leg refuses to send outside 14:00-16:00 IST and is **never** caught up — broker cutoff 4:00 PM (E1). See `LIVE_SETUP.md` |

**Environment:** Windows Application Control on the laptop blocks scikit-learn's and
statsmodels.tsa's DLLs. Use the validated numpy logistic regression (never add
scikit-learn); import `Logit` from `statsmodels.discrete.discrete_model`, never
`statsmodels.api`. The laptop has ~8 GB RAM — process large jobs one item at a time.

## Run order

```bash
pip install -r requirements.txt   # Python >= 3.12
python check_env.py               # must pass first
python run_overnight.py           # symbols -> 1y/3y targets -> price history (resumable)
python models/model_l.py          # L_final_3pm fit + card (the only Model L)
python models/model_h.py          # Model H baseline + cards
```
What to build next is decided by `PLAN.md` sections 6–7 and `PROGRESS.md`, not by this file.

## Known data defect — master date column

`issue_open_date` in `data/master_with_symbols.csv` (the master's `Date` column) holds the
**listing date**, not the issue-open date. It matched the listing date in all 316 clean
NSE-spine matches and all 129 tracker matches (2021–2026), and the open date in none.
Pre-2021 rows have no second source to check against. The existing `listing_date` column
was a copy of the same value. Job 1 matching accounts for this. Do not use the column as
an issue-open date for leakage cut-offs (D0–D3) until it has been renamed and re-sourced.

## Known biases to state in any output

- **Survivorship.** Delisted/suspended companies vanish from yfinance and are
  disproportionately failures. Any base rate computed after dropping them is optimistic.
  `data/target_MISSES.csv` must be read alongside the results.
- **Single-source variables.** RPT %, litigation quantum, customer concentration,
  promoter experience, uses-of-proceeds count and auditor qualification exist only in the
  RHP. They cannot be reconciled. They are kept but flagged `single_source_unverified` and
  must never be described as reconciled.

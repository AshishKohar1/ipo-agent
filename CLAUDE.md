# IPO Analyst Agent — project context

Read this before doing anything in this repo.

## Session start — do this first, every session

1. Follow the stage protocol in **`PLAN.md` section 3** exactly: `git fetch`, check out
   branch `work` (create it from `main` if missing), `git pull`.
2. Read `CLAUDE.md`, `PLAN.md`, `PROGRESS.md`, `DECISIONS.md`.
3. Pick the lowest-numbered stage that is not `DONE` and whose dependencies are met
   (`PLAN.md` section 6). Resume an `IN_PROGRESS` stage from its last checkpoint.

**The `work` branch on GitHub (github.com/AshishKohar1/ipo-agent) is the source of truth.**
On the laptop, always `git pull` on `work` before running anything. Never end a turn with
uncommitted work. `PLAN.md` is the single source of instructions; where this file and
`PLAN.md` disagree, `PLAN.md` wins.

## What this project is

A two-model system for Indian IPOs, plus the data pipeline that feeds it.

- **Model L** — P(listing gain), decides whether to bid. Targets: L1 `listing_gain > 0`
  (required hit rate 90%) and L2 `listing_gain > 10` (80%). Walk-forward AUC: L1 0.765,
  L2 0.878. (The earlier "AUC 0.883" came from random K-fold and is superseded.)
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
3. **No manual downloads.** RHPs come from SEBI (mainboard) and BSE SME only; if SEBI has
   no RHP, use the final prospectus and label it. No DRHPs. `NSE_DOWNLOADS_ALLOWED` stays
   `False` — never accept a disclaimer or click-through. Never ask the user to fetch a
   document. (PLAN.md rule 5.)
4. **Verify every PDF before use.** `_verify_is_prospectus()` checks prospectus marker,
   company name on the cover, and ≥100 pages. A wrong URL must produce a logged failure,
   never a silent bad row.
5. **Leakage discipline.** Model L must only use data knowable before the bid deadline.
   Final subscription is NOT knowable before the final day, so Model L is fed the
   final-day forecaster's P10 (PLAN.md section 5). The earlier D0–D3 per-decision-point
   models are superseded.
6. **Separate models for SME and mainboard.** Their coefficients differ in sign on market
   hotness and band width. Pooling is wrong.

## Data loading contract

- Every read of a file under `data/` goes through `dataio.py`. No other module opens
  `data/` directly, and no module or doc hardcodes a `data/` filename.
- `dataio` finds files by glob pattern (`PATTERNS`). Zero matches, or several where one
  is expected, raises an error. It never silently picks one.
- Loaders only rename columns and parse dates. They never fill or estimate values.
- `python check_env.py` checks this contract, the packages and the network. It must
  pass before any overnight run.

## Current state (Stage 0, 2026-09-28 — mirrors PLAN.md section 2; verify, don't assume)

| Item | Status |
|---|---|
| Master dataset | 652 mainboard IPOs, 2010 – May 2026, QIB/HNI/RII/Total + listing gain, in `data/` via `dataio.load_master()`. **Its `Date` column is the listing date, not the issue-open date.** True open dates for 2021+ are in `issue_dates_recovered.csv` |
| `master_with_symbols.csv` | 578 of 652 with symbols. `exclude_reason` flags 29 rows (13 FPO, 14 REIT/InvIT, 1 depository receipt, PROTEAN bad listing date). Every model excludes them |
| Benchmark | Official Nifty 50 TRI (NSE Indices), 2009 – Sep 2026, `data/NIFTY50_TRI.csv` |
| Holding targets vs TRI | `excess_1y` 491 rows (40.3% beat) in `holding_target.csv`; `excess_3y` 331 rows (36.0%) in `holding_target_3y.csv` |
| Model framework | `models/framework.py`: numpy logistic regression (validated vs statsmodels Logit to 3e-10), walk-forward, target-window embargo, recency weighting, calibration + threshold tables |
| Model L | `models/model_l.py`. Walk-forward L1 AUC 0.765, ≥90% → 97.7% hit. L2 AUC 0.878, ≥80% → 79.7% (fails), ≥85% passes. Total vs QIB/HNI/RII collinearity (VIF 83) unresolved → Gate A |
| Model H | `models/model_h.py` baseline only (subscription + size + listing gain): AUC 0.525 (1y), 0.562 (3y) |
| RHP fetcher | `fetch_rhp.py`: SEBI (open), BSE SME (open), NSE (disclaimer — disabled), BSE mainboard (not implemented). 5/5 verification companies passed. `data/verified_rhp_manifest.csv` lists every verified PDF with URL + SHA-256 |
| RHP extraction | not written (Stage 8) |
| Stage status | see `PROGRESS.md` |

**Environment:** Windows Application Control on the laptop blocks scikit-learn's and
statsmodels.tsa's DLLs. Use the validated numpy logistic regression (never add
scikit-learn); import Logit from `statsmodels.discrete.discrete_model`, never
`statsmodels.api`.

## Run order

```bash
pip install -r requirements.txt   # Python >= 3.12
python check_env.py               # must pass first
python run_overnight.py           # symbols -> 1y/3y targets -> price history (resumable)
python models/model_l.py          # Model L fits + cards
python models/model_h.py          # Model H baseline + cards
```
What to build next is decided by `PLAN.md` sections 6–7 and `PROGRESS.md`, not by this file.

## Known data defect — master date column

`issue_open_date` in `master_with_symbols.csv` (the master's `Date` column) holds the
**listing date**, not the issue-open date. It matched the listing date in all 316 clean
NSE-spine matches and all 129 tracker matches (2021–2026), and the open date in none.
Pre-2021 rows have no second source to check against. The existing `listing_date` column
was a copy of the same value. Job 1 matching accounts for this. Do not use the column as
an issue-open date for leakage cut-offs (D0–D3) until it has been renamed and re-sourced.

## Known biases to state in any output

- **Survivorship.** Delisted/suspended companies vanish from yfinance and are
  disproportionately failures. Any base rate computed after dropping them is optimistic.
  `target_MISSES.csv` must be read alongside the results.
- **Single-source variables.** RPT %, litigation quantum, customer concentration,
  promoter experience, uses-of-proceeds count and auditor qualification exist only in the
  RHP. They cannot be reconciled. They are kept but flagged `single_source_unverified` and
  must never be described as reconciled.

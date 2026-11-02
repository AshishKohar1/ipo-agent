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
   **Rule 5 was relaxed by the user on 2026-10-05 (H18 — the ONLY meaning of H18; the
   2026-10-03 name-similarity decision was renumbered H28 on 2026-10-10):** realistic
   browser headers MAY be
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
8. **NSE and niftyindices are used under H47 (ratified 2026-10-23), as amended by H51
   (2026-11-02).** Their terms prohibit automated collection and storage without written
   consent; the user accepts that risk for personal, non-commercial use.
   **H51: the repository is PUBLIC by the user's decision, and H47's "stays private"
   condition (rules 1 and 2) is waived.** Raw NSE/niftyindices rows are therefore
   published — retroactively, across all history, and permanently. `DECISIONS.md` H51
   lists every `data/` file that carries them. Do not change the repository's visibility,
   and do not treat the aggregate-only wording of H47 rule 1 as still binding.
   **What still binds every run: a 403 or a refused connection is never worked around.**
   One attempt per host per run; on a block the pipeline fails over to BSE or Chittorgarh
   and reports `NSE blocked — failed over to X`. No header rotation, no retry loop, no
   proxy. H47 rules 3, 4, 5 and 6 stand in full.
9. **Never ingest an AI-generated summary table as data (H8).** One was reviewed and
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

## Current state

**`PROGRESS.md` is authoritative for stage status, gates and what to do next.** The
orientation table that used to sit here was last true on 2026-10-01 and went stale within
days; it is deliberately not reproduced, because a stale summary of a fifty-decision
project is worse than no summary. Read, in this order: `PROGRESS.md` (its Summary block),
`DECISIONS.md` from **H17 to H57**, and the commit messages from `379a51f` to `c11e45c` —
the last human work before the laptop died. Everything after `c11e45c` is automated live
runs.

Three things that table asserted which a reader must not inherit:

| the old table said | what is true |
|---|---|
| Gate B AWAITING_USER on `model_l_v1.0` | **H17 supersedes it.** Model L is live on `model_l_v1.1`: L1 bids at Total >= 28.39x, L2 at >= 54.02x, and no probability enters the decision path |
| Gate C2 AWAITING_USER on RHP coverage | **superseded by H44/H45 and the check set.** The field list is frozen, a reader is graded before it runs, and the check set is the measurement |
| Model H "baseline only" | still unfit, but the shape is settled: H29 failed by under 1pp, **H35 is the fallback and is not yet run** (two spec choices open — `reports/H35_OPEN_CHOICES.md`), H48-H50 are done, **all five readers are INSUFFICIENT under H55** (none has 10 correct values), check set 7/20 |

**Environment (macOS, from 2026-11-02).** The Windows laptop's disk died. GitHub `main` is
authoritative and this Mac is the development machine: macOS 26.6 on arm64, Python 3.14.10
in `.venv` (`python3.14 -m venv .venv`), every `requirements.txt` pin installing as a
prebuilt wheel. `check_env.py` passes **15/15** here.

- **Rule 10 still holds: never add scikit-learn.** Use the validated numpy logistic
  regression. The *reason* has changed — it was Windows Application Control blocking the
  DLLs, and now it is simply that the models were fitted and frozen without it — but the
  rule has not.
- `statsmodels.api` imports fine on macOS. Keep importing `Logit` from
  `statsmodels.discrete.discrete_model` anyway: `check_env.py` asserts that path.
- The "~8 GB RAM, one item at a time" constraint was the laptop's. Keep the H9 night-batch
  discipline regardless — it is about resumability, not memory.
- **Two caches, both gitignored.** `data/rhp_text_cache/` holds every page's text for 444
  documents (198 MB); `_local/rhp_table_cache/` holds every table on every page, parsed
  with `{vertical_strategy: text, horizontal_strategy: text}` and keyed by SHA-256
  (~300 MB). Adding a variable means writing a reader against these, not opening a PDF.
  Both record the extraction library versions; `textcache.lib_drift()` reports a mismatch.
- **Rule 3 is enforced at the title line** (H57). `data/rhp_doc_type.csv` classifies all
  444 documents; the two DRHPs in the corpus are excluded from every reader run and fit.
- Gitignored, and **lost with the disk**: `_local/`, `data/rhp_text_cache/`,
  `data/bhavcopy_cache/`, `data/bhavcopy_raw_cache/`, `_local/check_set_dump/`, `.venv`.
  Everything else is re-fetchable, and `data/verified_rhp_manifest.csv` carries a URL plus
  SHA-256 for every PDF.
- **There is no `.env`, and none is to be created.** No module reads one; the Gmail
  credentials live only in GitHub Secrets.

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

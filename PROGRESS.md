# Progress

**Working branch: `work`** (on GitHub at github.com/AshishKohar1/ipo-agent). This is the
source of truth. Every session: `git fetch`, check out `work`, `git pull`.

## Summary (updated at the end of every session)
- **Finished:** Stage 0 (closed against `origin/main`); Stage 1 (laptop); Stage 2 (Sets A-D x L1/L2, pooled AUC + section-5 thresholds + paired bootstrap)
- **In progress:** Stage 4 next (day-wise subscription + GMP), the only unblocked stage while Gate A is open
- **Open gates:** **GATE A** - which feature set Model L uses. Recommendation: Set A for both targets (Set C for L1 optional). See reports/STAGE_02_REPORT.md
- **Next stage:** Stage 3 and Stage 5 are BLOCKED on Gate A. Stage 4 and Stage 8 do not depend on it
- **Blocked:** Stage 3, 5 (Gate A). Caveat: Stage 1's Linux/`pip install` half is unverified - the first cloud session must re-run check_env.py and stage1_env_check.py

## Stages

| Stage | Title | Depends on | Status | Started (IST) | Finished (IST) | Notes |
|---|---|---|---|---|---|---|
| 0 | Repository setup (laptop) | — | DONE | 2026-09-28 23:01 | 2026-09-29 | acceptance verified against `origin/main`; `work` branch created and pushed — see reports/STAGE_00_CLOSURE.md |
| 1 | Cloud environment check | 0 + cloud setup | DONE | 2026-09-29 21:55 | 2026-09-29 22:10 | ran on the LAPTOP: check_env 13/13, 11/11 domains, integrity + estimator + SHA round-trip all pass. Linux/`pip install` half UNVERIFIED - first cloud session must re-run check_env.py and stage1_env_check.py |
| 2 | Model L feature comparison | 1 | AWAITING_USER | 2026-09-29 22:10 | 2026-09-29 22:40 | Gate A open - see reports/STAGE_02_REPORT.md. Sets A-D x L1/L2 on 616 identical rows |
| 3 | Calibration curve + final thresholds | Gate A | NOT_STARTED | | | |
| 4 | Day-wise subscription + GMP history | 1 | NOT_STARTED | | | |
| 5 | Final-day forecaster + GMP test | Gate A, 4 | NOT_STARTED | | | |
| 6 | Productionize Model L | 3, 5 | NOT_STARTED | | | ends in Gate B |
| 7 | Go live (Model L) | Gate B | NOT_STARTED | | | |
| 8 | RHP extraction build + spot-check | 1 | NOT_STARTED | | | ends in Gate C |
| 9 | RHP batch pilot (10 companies) | Gate C | NOT_STARTED | | | ends in Gate D |
| 10 | RHP full batch (chunked) | Gate D | NOT_STARTED | | | |
| 11 | Model H scorecard | 10 | NOT_STARTED | | | |
| 12 | Hold-sizing backtest | 11 | NOT_STARTED | | | ends in Gate E |
| 13 | Integration + wrap-up | 7, Gate E | NOT_STARTED | | | |

## Gates

| Gate | After stage | Status | Decision (verbatim in DECISIONS.md) |
|---|---|---|---|
| A | 2 | **AWAITING_USER** (opened 2026-09-29) | |
| B | 6 | — | |
| C | 8 | — | |
| D | 9 | — | |
| E | 12 | — | |

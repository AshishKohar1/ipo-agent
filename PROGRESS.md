# Progress

**Working branch: `work`** (on GitHub at github.com/AshishKohar1/ipo-agent). This is the
source of truth. Every session: `git fetch`, check out `work`, `git pull`.

## Summary (updated at the end of every session)
- **Finished:** Stage 0 (closed against `origin/main`); Stage 1 (laptop: check_env 13/13, 11/11 domains, integrity + estimator + Syngene SHA round-trip)
- **In progress:** Stage 2, Model L feature comparison (Sets A-D, both targets) -> Gate A
- **Open gates:** none yet; Gate A opens when Stage 2 finishes
- **Next stage:** Stage 2 -> Gate A (user decision), then Stage 4 is unblocked in parallel
- **Blocked:** nothing. Caveat: Stage 1's Linux/`pip install` half is unverified - the first cloud session must re-run check_env.py and stage1_env_check.py before working there

## Stages

| Stage | Title | Depends on | Status | Started (IST) | Finished (IST) | Notes |
|---|---|---|---|---|---|---|
| 0 | Repository setup (laptop) | — | DONE | 2026-09-28 23:01 | 2026-09-29 | acceptance verified against `origin/main`; `work` branch created and pushed — see reports/STAGE_00_CLOSURE.md |
| 1 | Cloud environment check | 0 + cloud setup | DONE | 2026-09-29 21:55 | 2026-09-29 22:10 | ran on the LAPTOP: check_env 13/13, 11/11 domains, integrity + estimator + SHA round-trip all pass. Linux/`pip install` half UNVERIFIED - first cloud session must re-run check_env.py and stage1_env_check.py |
| 2 | Model L feature comparison | 1 | IN_PROGRESS | 2026-09-29 22:10 | | ends in Gate A |
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
| A | 2 | — | |
| B | 6 | — | |
| C | 8 | — | |
| D | 9 | — | |
| E | 12 | — | |

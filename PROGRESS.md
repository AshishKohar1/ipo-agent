# Progress

**Working branch: `work`** (on GitHub at github.com/AshishKohar1/ipo-agent). This is the
source of truth. Every session: `git fetch`, check out `work`, `git pull`.

## Summary (updated at the end of every session)
- **Finished:** Stage 0 (verified against `origin/main`, closed 2026-09-29 — see reports/STAGE_00_CLOSURE.md)
- **In progress:** Stage 1, environment check — running on the laptop, not the cloud
- **Open gates:** none
- **Next stage:** Stage 1, then Stage 2 (Model L feature comparison → Gate A)
- **Blocked:** nothing

## Stages

| Stage | Title | Depends on | Status | Started (IST) | Finished (IST) | Notes |
|---|---|---|---|---|---|---|
| 0 | Repository setup (laptop) | — | DONE | 2026-09-28 23:01 | 2026-09-29 | acceptance verified against `origin/main`; `work` branch created and pushed — see reports/STAGE_00_CLOSURE.md |
| 1 | Cloud environment check | 0 + cloud setup | NOT_STARTED | | | |
| 2 | Model L feature comparison | 1 | NOT_STARTED | | | ends in Gate A |
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

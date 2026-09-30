# Progress

**Working branch: `main`** (github.com/AshishKohar1/ipo-agent) — a single branch, no `work`
(decision F1). Completed stages are marked with a tag, `stage-NN-done`. Every session:
`git fetch`, then `git pull` on `main`. Chain git commands separately, not with `&&` (F2).

Stage numbering follows `PLAN.md` as amended by `PLAN_AMENDMENT_01.md` (2026-09-30).

## Summary (updated at the end of every session)
- **Finished:** Stage 0, Stage 1 (laptop), Stage 2 → **Gate A closed** (Set A), Stage 3 → **isotonic calibration adopted**, thresholds fixed
- **In progress:** none. Stage 8 (RHP extraction → Gate C) is next and needs no decision
- **Open gates:** **Gate F** (opened 2026-09-30) — how to resolve company->id; no bulk fetch until decided
- **Next stage:** Stage 3 (calibration + final thresholds), then Stage 8 (RHP extraction), which needs no decision
- **Blocked:** Stage 4B (Gate F); Stage 5 (needs 3 + 4B). Caveat: Stage 1's Linux/`pip install` half is unverified — the first cloud session must re-run `check_env.py` and `stage1_env_check.py`

## Stages

| Stage | Title | Depends on | Status | Started (IST) | Finished (IST) | Notes |
|---|---|---|---|---|---|---|
| 0 | Repository setup (laptop) | — | DONE | 2026-09-28 23:01 | 2026-09-29 | acceptance verified against the remote — `reports/STAGE_00_CLOSURE.md`. Tag `stage-00-done` |
| 1 | Environment check | 0 | DONE | 2026-09-29 21:55 | 2026-09-29 22:10 | laptop: `check_env.py` 13/13, `stage1_env_check.py` all pass, 11/11 domains. **Linux/`pip install` half UNVERIFIED.** Tag `stage-01-done` |
| 2 | Model L feature comparison | 1 | DONE | 2026-09-29 22:10 | 2026-09-30 | **Gate A closed by decision A1: Set A for both L1 and L2.** Sets A–D × L1/L2 on 616 identical rows; pooled AUC L1 0.8084 / L2 0.8809. `reports/STAGE_02_REPORT.md`. Tag `stage-02-done` |
| 3 | Calibration curve + final thresholds | Gate A ✅ | DONE | 2026-09-30 | 2026-09-30 | **Isotonic adopted for both targets:** fire iff calibrated p >= 0.90 (L1) / 0.80 (L2). Out-of-time: L1 fires 117 @ 94.0% hit (lo95 88.2%), L2 fires 96 @ 87.5% (lo95 79.4%). The C5 bucket rule, measured out-of-time, FAILS L2 (77.1%). `reports/STAGE_03_REPORT.md` |
| 4A | Chittorgarh 20-IPO coverage sample | 1 | AWAITING_USER | 2026-09-30 | 2026-09-30 | **Gate F open.** robots.txt unchanged; day-wise table confirmed rich on a closed IPO, but 0 of 20 sample IPOs testable - company->id needs a bulk id walk or a JS index. See reports/STAGE_04A_REPORT.md |
| 4B | Day-wise subscription backfill (chunked) | Gate F | NOT_STARTED | | | day-1/day-2 flagged `single_source_unverified`; forward NSE+BSE snapshots per B4 |
| 5 | Three decision-point models (`L_day1`, `L_day2`, `L_final_3pm`) | 3, 4B | NOT_STARTED | | | **no forecaster** (C1, C2); `L_final_3pm` approximated until ~40 real 3pm samples (C3) |
| 6 | Productionize Model L | 3, 5 | NOT_STARTED | | | ends in Gate B |
| 7 | Go live (Model L) | Gate B | NOT_STARTED | | | schedule per E1; broker cutoff 4:00 PM |
| 8 | RHP extraction build + spot-check | 1 | NOT_STARTED | | | ends in Gate C. **Needs no user decision — the fallback when gates block everything else** |
| 9 | RHP batch pilot (10 companies) | Gate C | NOT_STARTED | | | ends in Gate D |
| 10 | RHP full batch (chunked) | Gate D | NOT_STARTED | | | |
| 11 | Model H scorecard | 10 | NOT_STARTED | | | |
| 12 | Hold-sizing backtest | 11 | NOT_STARTED | | | ends in Gate E |
| 13 | Integration + wrap-up | 7, Gate E | NOT_STARTED | | | |

## Gates

| Gate | After stage | Status | Decision (verbatim in DECISIONS.md) |
|---|---|---|---|
| A | 2 | ✅ **CLOSED** 2026-09-30 | A1: Model L uses **Set A** for both L1 and L2 (`log1p(Total)` + `log(issue size)`). A2: Set C retained as a standing challenger, promoted only by champion/challenger. A3: Sets B and D rejected; category figures still displayed in live reports |
| F | 4A | **AWAITING_USER** (opened 2026-09-30) | How to resolve company->Chittorgarh id: sample id-walk first (recommended), full id walk, browser-rendered year index, or forward-only |
| B | 6 | — | |
| C | 8 | — | |
| D | 9 | — | |
| E | 12 | — | |

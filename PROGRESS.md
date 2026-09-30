# Progress

**Working branch: `main`** (github.com/AshishKohar1/ipo-agent) — a single branch, no `work`
(decision F1). Completed stages are marked with a tag, `stage-NN-done`. Every session:
`git fetch`, then `git pull` on `main`. Chain git commands separately, not with `&&` (F2).

Stage numbering follows `PLAN.md` as amended by `PLAN_AMENDMENT_01.md` (2026-09-30) and
`PLAN_AMENDMENT_02.md` (2026-10-01).

## Summary (updated at the end of every session)
- **Finished:** Stage 0, Stage 1 (laptop), Stage 2 → **Gate A closed** (Set A), Stage 3 → **isotonic calibration adopted** and independently verified, Stage 4A → Gate F2, Stage 14 (Amendment 02 applied)
- **In progress:** Stage 15 (RHP extractor rebuild + night batch) → **Gate C2**; Stage 16 (`L_final_3pm`) → **Gate B**; Stages 17 and 18 night backfills
- **Open gates:** **Gate B** and **Gate C2** when their stages report. Gate F2 is **closed by decision H1**
- **Cancelled:** Stage 4B and Stage 5 — no permitted source for day-wise subscription history (H1)
- **Caveat:** Stage 1's Linux/`pip install` half is still unverified — every session so far has run on the Windows laptop, so the first genuine cloud session must re-run `check_env.py` and `stage1_env_check.py`

## Stages

| Stage | Title | Depends on | Status | Started (IST) | Finished (IST) | Notes |
|---|---|---|---|---|---|---|
| 0 | Repository setup (laptop) | — | DONE | 2026-09-28 23:01 | 2026-09-29 | acceptance verified against the remote — `reports/STAGE_00_CLOSURE.md`. Tag `stage-00-done` |
| 1 | Environment check | 0 | DONE | 2026-09-29 21:55 | 2026-09-29 22:10 | laptop: `check_env.py` 13/13, `stage1_env_check.py` all pass, 11/11 domains. **Linux/`pip install` half UNVERIFIED.** Tag `stage-01-done` |
| 2 | Model L feature comparison | 1 | DONE | 2026-09-29 22:10 | 2026-09-30 | **Gate A closed by decision A1: Set A for both L1 and L2.** Sets A–D × L1/L2 on 616 identical rows; pooled AUC L1 0.8084 / L2 0.8809. `reports/STAGE_02_REPORT.md`. Tag `stage-02-done` |
| 3 | Calibration curve + final thresholds | Gate A ✅ | DONE (independently verified) | 2026-09-30 | 2026-09-30 | **Isotonic adopted for both targets (G1, G2); 14/14 claims reproduced by verify_stage3.py:** fire iff calibrated p >= 0.90 (L1) / 0.80 (L2). Out-of-time: L1 fires 117 @ 94.0% hit (lo95 88.2%), L2 fires 96 @ 87.5% (lo95 79.4%). The C5 bucket rule, measured out-of-time, FAILS L2 (77.1%). `reports/STAGE_03_REPORT.md` |
| 4A | Chittorgarh coverage sample + capped ID walk | 1 | DONE | 2026-09-30 | 2026-09-30 | **Gate F2 open.** 71/200 requests, 0 errors. ID walk solves company->id, but day-wise data is TRANSIENT (Adroit's table vanished within a day, replaced at allotment); 0 of 50 pre-2026 ids carry it. Anchor/lock-in IS archived (41%). See reports/STAGE_04A_COVERAGE.md |
| 4B | ~~Day-wise subscription backfill~~ | — | **❌ CANCELLED 2026-10-01 (H1)** | | 2026-10-01 | **Reason: no permitted source for day-wise subscription history.** Chittorgarh publishes the table only while an IPO is open and removes it at close (0 of 50 pre-2026 pages carried it; the 2026 anchor's own table vanished between two consecutive days); every aggregator that keeps it is blocked by robots.txt or terms. A backfill would retrieve nothing. Forward collection (B4) survives and moves to Stage 19 |
| 5 | ~~Three decision-point models~~ | — | **❌ CANCELLED 2026-10-01 (H1)** | | 2026-10-01 | **Reason: two of the three models have no training data and never will** (see 4B). `L_day1`, `L_day2` and the forecaster are cancelled and their code paths **deleted, not left dormant**. The surviving `L_final_3pm` is finalised by Stage 16 |
| 6 | Productionize Model L | 3 | SUPERSEDED by Stage 19 | | | ends in Gate B |
| 7 | Go live (Model L) | Gate B | NOT_STARTED | | | schedule per E1; broker cutoff 4:00 PM |
| 8 | RHP extraction build + spot-check | 1 | **PARTIAL → SUPERSEDED by Stage 15** | 2026-09-30 | | Gate C NOT closed: 58/246 fields ok (24%) — but measured on the headline financials that H5 now removes from scope, so it is not comparable to Stage 15's ≥60% H6 target. Framework, provenance model and section location are kept. reports/STAGE_08_REPORT.md |
| 9 | RHP batch pilot (10 companies) | Gate C | NOT_STARTED | | | ends in Gate D |
| 10 | RHP full batch (chunked) | Gate D | NOT_STARTED | | | |
| 11 | Model H scorecard | 10 | NOT_STARTED | | | |
| 12 | Hold-sizing backtest | 11 | NOT_STARTED | | | ends in Gate E |
| 13 | Integration + wrap-up | 7, Gate E | NOT_STARTED | | | |
| 14 | Apply Amendment 02 to PLAN/DECISIONS/CLAUDE | — | DONE | 2026-10-01 | 2026-10-01 | H1–H9 recorded in `DECISIONS.md`; PLAN sections replaced in place; 4B and 5 cancelled |
| 15 | RHP extractor rebuild + night batch **[NIGHT]** | 14 | IN_PROGRESS | 2026-10-01 | | ends in **Gate C2** — H6-field coverage ≥60%, then the full batch, then `reports/SPOTCHECK_V2.*` |
| 16 | Finalise and freeze `L_final_3pm` | 3, 14 | NOT_STARTED | | | ends in **Gate B**; deletes the L_day1/L_day2/forecaster code paths |
| 17 | Aggregator-first financial backfill **[NIGHT]** | 14 | NOT_STARTED | | | H5 headline fields, reconciled under rule 2 |
| 18 | Anchor / lock-in backfill **[NIGHT]** | 14 | NOT_STARTED | | | feeds Model H's empty ownership block |
| 19 | Productionise + go live | Gate B | NOT_STARTED | | | absorbs Stages 6 and 7 with the single-model `predict_live` |

## Gates

| Gate | After stage | Status | Decision (verbatim in DECISIONS.md) |
|---|---|---|---|
| A | 2 | ✅ **CLOSED** 2026-09-30 | A1: Model L uses **Set A** for both L1 and L2 (`log1p(Total)` + `log(issue size)`). A2: Set C retained as a standing challenger, promoted only by champion/challenger. A3: Sets B and D rejected; category figures still displayed in live reports |
| F | 4A | CLOSED 2026-09-30 | User approved a capped 200-request ID walk |
| F2 | 4A ID walk | ✅ **CLOSED** 2026-10-01 by **H1** | Cancel Stage 4B's backfill, cancel `L_day1`/`L_day2` and the forecaster, keep B4 forward collection, and backfill anchor/lock-in instead (now Stage 18) |
| B | 6 | — | |
| C | 8 | SUPERSEDED by Gate C2 | Spot-check delivered (20 rows, 5 companies) but coverage was 24% on the headline financials. H5/H6 re-scope the work rather than re-run it |
| C2 | 15 | — | H6-field coverage ≥60% on the 8 manifest documents, the night batch's outcome, and `reports/SPOTCHECK_V2.csv`/`.xlsx` |
| D | 9 | — | |
| E | 12 | — | |

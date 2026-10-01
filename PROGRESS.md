# Progress

**Working branch: `main`** (github.com/AshishKohar1/ipo-agent) — a single branch, no `work`
(decision F1). Completed stages are marked with a tag, `stage-NN-done`. Every session:
`git fetch`, then `git pull` on `main`. Chain git commands separately, not with `&&` (F2).

Stage numbering follows `PLAN.md` as amended by `PLAN_AMENDMENT_01.md` (2026-09-30) and
`PLAN_AMENDMENT_02.md` (2026-10-01).

## Summary (updated at the end of every session)
- **Finished:** Stage 0, Stage 1 (laptop), Stage 2 → **Gate A closed** (Set A), Stage 3 → **isotonic calibration adopted** and independently verified, Stage 4A → Gate F2, Stage 14 (Amendment 02 applied)
- **In progress:** Stage 15b night batch (485 companies, resumable) and Stages 17+18 Chittorgarh sweep (2,861 ids) — both running; the sweep was restarted 05:24 after dying on a malformed cell
- **Gate C2:** ✅ **CLOSED 2026-10-01** — keep every field; `missing_reason` added (H10)
- **Gate B:** **AWAITING RATIFICATION.** Model L v1.0 is built, frozen and productionised, but **H11 supersedes A1 and H2's frozen Set A** — that is the one item needing your word. Gate F2 closed by H1
- **Morning report:** `reports/NIGHT_RUN_REPORT.md`
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
| 15a | H6 extractor rebuild | 14 | DONE | 2026-10-01 | 2026-10-01 | 30 H6 fields x 8 docs: **48.8% strict, 59.6% usable, 63.0% adjusted** (target 60%). Flat-text + cross-page scanning and full unit detection fixed both Stage 8 failures. **Ten wrong values caught and deleted**, each documented in `extract/h6.py`. 6 fields named as unreachable across vintages |
| 15b | RHP night batch **[NIGHT]** | 15a | **IN_PROGRESS** (running) | 2026-10-01 01:05 | | 485 companies, ~140 s each, ~19 h, resumable. `data/rhp_progress.csv` + `reports/h6_batch_observations.csv`, commit every 5. Ends in **Gate C2** |
| 16 | Finalise and freeze `L_final_3pm` | 3, 14 | DONE | 2026-10-01 | 2026-10-01 | **Gate B open.** L1 pooled AUC 0.8081 fires 117 @ 94.0%; L2 0.8809 fires 96 @ 87.5%; both PASS C5. `MODEL_L_CARD.md`. **2 of H2's 9 rejections do not reproduce**; H4's issue-size sign is half-life dependent and production is POSITIVE |
| 17+18 | Chittorgarh backfill **[NIGHT]** | 14 | **IN_PROGRESS** (running) | 2026-10-01 01:26 | | One request per company serves BOTH stages: `/ipo/x/{id}/` carries the H5 financials and the anchor/lock-in block. ids 250-3110, >=3.2 s apart, robots.txt re-verified. Also yields an independent 2nd source for promoter holding |
| 19 | Productionise + go live | Gate B | **DONE (awaiting Gate B ratification)** | 2026-10-01 | 2026-10-01 | `model_l_v1.0` on H11 (log1p(Total) alone, no recency weighting); coefficients exported as portable JSON and VERIFIED to reproduce every verdict standalone. `predictions_log.py` (append-only), `ingest_outcomes.py`, `run_live_l.py` (dual 15:00/17:30 capture), `retrain_l.py`, `LIVE_SETUP.md`. **5 schedules created.** BLOCKER: NSE/BSE official APIs refuse this host — jobs log honestly and invent nothing |
| 16b | Settle the issue-size sign | 16 | DONE | 2026-10-01 | 2026-10-01 | **H11**: no half-life defends the sign, so issue size is DROPPED. log1p(Total) alone is +0.31pp better on L1, identical on L2, and passes C5 where Set A failed. `reports/stage16b_half_life.json` |

## Gates

| Gate | After stage | Status | Decision (verbatim in DECISIONS.md) |
|---|---|---|---|
| A | 2 | ✅ **CLOSED** 2026-09-30 | A1: Model L uses **Set A** for both L1 and L2 (`log1p(Total)` + `log(issue size)`). A2: Set C retained as a standing challenger, promoted only by champion/challenger. A3: Sets B and D rejected; category figures still displayed in live reports |
| F | 4A | CLOSED 2026-09-30 | User approved a capped 200-request ID walk |
| F2 | 4A ID walk | ✅ **CLOSED** 2026-10-01 by **H1** | Cancel Stage 4B's backfill, cancel `L_day1`/`L_day2` and the forecaster, keep B4 forward collection, and backfill anchor/lock-in instead (now Stage 18) |
| B | 6 | — | |
| C | 8 | SUPERSEDED by Gate C2 | Spot-check delivered (20 rows, 5 companies) but coverage was 24% on the headline financials. H5/H6 re-scope the work rather than re-run it |
| C2 | 15 | **AWAITING_USER** (opened 2026-10-01) | Coverage 59.6% usable / 63.0% adjusted vs a 60% target; 20-row spot-check from H6 fields only in `reports/SPOTCHECK_V2.csv`/`.xlsx`. Recommend approving the field set, but decide first whether the 11 fields at or below 50% are worth keeping as sparse columns |
| B | 16 | **AWAITING_USER** (opened 2026-10-01) | `model_l_v1.0` frozen; both targets pass every C5 gate out-of-time. Decide on the POSITIVE issue-size coefficient the 2-year half-life produces, and on amending Amendment 02 section A where two of nine rejections did not reproduce |
| D | 9 | — | |
| E | 12 | — | |

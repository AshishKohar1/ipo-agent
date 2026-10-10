# Progress

**Working branch: `main`** (github.com/AshishKohar1/ipo-agent) — a single branch, no `work`
(decision F1). Completed stages are marked with a tag, `stage-NN-done`. Every session:
`git fetch`, then `git pull` on `main`. Chain git commands separately, not with `&&` (F2).

Stage numbering follows `PLAN.md` as amended by `PLAN_AMENDMENT_01.md` (2026-09-30) and
`PLAN_AMENDMENT_02.md` (2026-10-01).

## Summary (updated at the end of every session)
- **Finished:** Stages 0-3, 4A, 14, 15a/15b, 16, 16b, 17+18, 19, 20-23, 25, 26, 27, 28, **29-34 (2026-10-08)** and **35-40 (2026-10-09)**, **41-46 (2026-10-10)**
- **In progress:** nothing. Working tree clean
- **Model L is go-live ready** on H17 (ratified): L1 bids at Total >= 28.39x, L2 at >= 54.02x, no probability in the decision path. Three Actions jobs and nothing else: 15:00 IST email, 19:30 IST day-end capture, Saturday 10:30 audit
- **Model H: NOT started and much further out.** Baseline only, AUC 0.525 (1y) / 0.562 (3y), RHP blocks still placeholders, and 37 prospectuses still missing. Scorecard parked per instruction
- **Open for the user:** the 12-month email backtest under-delivers both promises (L1 85.7% vs 90%, L2 72.2% vs 80%). Tripwire armed at 1 of 2 on both; **no action by design**. **H24 (2026-10-10)** now also requires half a window's firing rows to be new before it counts - consecutive 12-month windows share 11 of 12 months, and rolling the current window forward a month leaves 0 of 45 L1 fires new
- **Needs a date in the diary:** the HDFIRE intraday test, **13-15 October**. Confirmed from NSE's calendar as mainboard (series EQ). The poller is built and wired; it decides whether H22 is confirmed
- **Needs YOU:** jobs 1 and 2 (email + dead-man) are set up. Still to add: **job 3, the 19:30 day-end capture at 14:00 UTC**, and **jobs 4-6, the HDFIRE polls** (`LIVE_SETUP.md` section 1b). GitHub's scheduler was **5h31m to 9h06m late on nine consecutive runs**, so the external trigger is what actually makes the 15:00 email land
- **Gate C2:** AWAITING_USER since 2026-10-01
- **Caveat:** Stage 1's Linux/`pip install` half is still unverified on a real cloud session

## FIRST STEP OF THE NEXT SESSION (written 2026-10-10 ~15:30 IST)

**13-15 October is the HDFIRE window and it is the only thing in this project with a
deadline.** HD Fire Protect (`HDFIRE`, series EQ, mainboard) bids 13-15 Oct; Ravita
Engineering (`RAVITA`, SME) is the control. Nothing can be re-run afterwards - the
subscription table is removed at allotment. So:

1. Confirm the three cron-job.org poll jobs exist (`LIVE_SETUP.md` 1b, jobs 4-6). If they
   do not, dispatch the polls by hand:
   `gh workflow run live-model-l.yml -f mode=poll`
2. On 15 October, confirm the 15:00 email went out for HDFIRE through the NSE-primary path
   (`data/sent_markers.csv` gains a `decision` row; the report names the source).
3. After 15 October, write the Task 9 report: update frequency, NSE vs Chittorgarh per
   poll, 15:00-to-final growth, and whether H22 should be confirmed or stay provisional.

### Then: did the 9 Oct handover check close? Yes

All nine of 9 October's scheduled runs fired, all green, **all of them late**: 5h16m to
7h03m. Every one of the four email attempts arrived after 16:00 IST, so the send-window
guard refused all four - correctly, and green, because nothing was owed that day. The
day-end leg due 19:30 IST started 00:46 IST on 10 October and stamped itself 2026-10-10.
That is fixed (trading date now comes from the cron slot the run was due for), and the
delay table in `LIVE_SETUP.md` 1b now carries all 21 measured runs.

### Known red that is not a bug

`capture_audit --audit --days 7` reports two real historical gaps: the **15:00 email on
2026-10-08** and the **day-end on 2026-10-07**. Both happened, both are correctly
recorded, and neither can be invented after the fact - the markers are append-only. The
Saturday audit will go red until they age out of its 7-day window (after 2026-10-15). Do
not backfill a marker to make it green.

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
| 15b | RHP night batch **[NIGHT]** | 15a | **DONE** | 2026-10-01 01:05 | 2026-10-03 | **486 settled: 418 done (86%), 57 source_unresolved, 11 not_a_prospectus.** Throttle-aware after tripping SEBI's breaker: 5 s gap, backoff 10/30/90/270/600 s, and a throttle does not advance the failure breaker. All 5 retryable companies succeeded on retry, confirming they were connection refusals. Ends in **Gate C2** |
| 16 | Finalise and freeze `L_final_3pm` | 3, 14 | DONE | 2026-10-01 | 2026-10-01 | **Gate B open.** L1 pooled AUC 0.8081 fires 117 @ 94.0%; L2 0.8809 fires 96 @ 87.5%; both PASS C5. `MODEL_L_CARD.md`. **2 of H2's 9 rejections do not reproduce**; H4's issue-size sign is half-life dependent and production is POSITIVE |
| 17+18 | Chittorgarh backfill **[NIGHT]** | 14 | **DONE** | 2026-10-01 01:26 | 2026-10-02 | One request per company serves BOTH stages: `/ipo/x/{id}/` carries the H5 financials and the lock-in block. **CORRECTED 2026-10-08:** what was collected is the pre-issue **lock-in** table, NOT the anchor allocation book - `data/chittorgarh_anchor_lockin.csv` has zero names containing 'mutual fund' across 3,127 rows and 674 IPOs. The anchor book is a different block on the same page and is still uncollected, which is why Priority 4's anchor-quality candidate could not be tested. ids 250-3110, >=3.2 s apart, robots.txt re-verified. Also yields an independent 2nd source for promoter holding |
| 19 | Productionise + go live | Gate B | **DONE (awaiting Gate B ratification)** | 2026-10-01 | 2026-10-01 | `model_l_v1.0` on H11 (log1p(Total) alone, no recency weighting); coefficients exported as portable JSON and VERIFIED to reproduce every verdict standalone. `predictions_log.py` (append-only), `ingest_outcomes.py`, `run_live_l.py` (dual 15:00/17:30 capture), `retrain_l.py`, `LIVE_SETUP.md`. **5 schedules created.** BLOCKER: NSE/BSE official APIs refuse this host — jobs log honestly and invent nothing |
| 20 | Fix the live pipeline | 19 | **DONE** | 2026-10-03 | 2026-10-03 | Every scheduled run 1–3 Oct died in ~35 s on `ModuleNotFoundError: joblib`. A clean-venv audit of every module the jobs touch found joblib the ONLY missing package. New `score_l.py` scores from the portable JSON on stdlib alone, so the live path imports in a venv with **no joblib at all**. ONE pipeline now (`send_daily_email.py` for both legs); `run_live_l.py` retired to `reports/live/exchange_probe/`. Subject fixed to `IPO decision - `, `EMAIL_TO` added, marker bug fixed (H17), `subscription_snapshots.csv` written by both legs, runner pinned `ubuntu-24.04`, actions upgraded off Node 20 |
| 21 | Historical-name aliases | 20 | **DONE** | 2026-10-03 | 2026-10-03 | **H18.** `data/company_aliases.csv`, 23 document/user-evidenced aliases; 8 of 28 hand-sourced companies had a genuine rename. Two systematic sources tried and REJECTED with the evidence recorded (aggregator name matching produced *different companies*; unanchored "formerly known as" produced BRLMs, registrars and an address). Wired into `fetch_rhp.py`, current name first. Live probe: `reports/alias_resolution_probe.csv` |
| 22 | Manual RHPs **[NIGHT]** | 20 | **DONE** | 2026-10-03 | 2026-10-06 | 28 hand-supplied documents through the same pipeline — SHA-256, `_verify_is_prospectus()`, full provenance, no exceptions. **No network requests.** Branches on `doc_type`: 4 fields that need the issue priced are `not_in_drhp` for DRHP rows. **28/28 settled, 27 done**, 1,008 values. Samhi Hotels reprocessed with the re-supplied file (570 pages, marker on page 1) after the first was a 1-page scan. Coverage **RHP 58.4% / DRHP 57.6%** — within 1pp only BECAUSE 4 pre-pricing fields are `not_in_drhp` (11 occurrences) rather than counted as failures |
| 23 | Market context | 20 | **DONE** | 2026-10-03 | 2026-10-06 | **Unblocked by H18.** robots.txt now HTTP 200 with `Allow: /`; endpoint PROBED (`/BackPage/getHistoricaldatatabletoString`). **All 15 indices capture.** Nifty Healthcare needed `NIFTY HEALTHCARE`, not `NIFTY HEALTHCARE INDEX` — Pharma was NOT substituted. Guards: the response's INDEX_NAME is checked against what was asked, and the TRI endpoint is explicitly not used (a TRI value is not a close) |
| 24 | Outcome ingest repair | 20 | **PARTIAL** | 2026-10-03 | | 5a `symbols.py` resolves by ISIN first, then names+aliases, falling back to `NSE_EQUITY_L.csv` (ISIN on all 2,601 rows, runs to 2026-09-25): **56 of 170 post-cutoff listings now resolve, up from 0**; the other 114 are SME and need an SME equity list. 5b rule 6 violation fixed — segment comes from the bid-time record, never defaulted to mainboard. **5c UNSOLVED: still no listing-price source.** Chittorgarh's per-IPO page has a verified "Listing Day Trading Information" table (Final Issue Price / Open / Low / High / Last Trade) — recommended, needs a ~500-page sweep and the user's acceptance of single-source |
| 25 | Thresholds on subscription | 16 | **DONE (awaiting ratification)** | 2026-10-05 | 2026-10-05 | **H17, superseding H16 — which had the direction backwards.** Derived with no model/standardiser/calibrator: a monotone threshold on Total subscription vs the realised gain. In-sample flatters by **+3.8pp (L1) / +4.8pp (L2)**; walk-forward is the expectation. **1b REFUTED** — L1 delivers 86.3%, not 90%, at its naive threshold. Calibrated: **L1 fires above 28.39x, L2 above 54.02x**, which roughly DOUBLES the bids (L2 74→166 fires) because the shipped model fired on only 11.9% at 98.6% delivery. `reports/SUBSCRIPTION_THRESHOLDS.md` |
| 26 | Listing-price labels **[NIGHT]** | 24 | **DONE** | 2026-10-06 | 2026-10-07 | **H18 unblocked NSE, BSE and NSE Indices** — the browser-UA ban was the only barrier; NSE's robots.txt says `Allow: /` and always did. As-reported gate PASSES on 3 sources (Syngene 295.0, not 147.50; gain 18.0% = the master's figure). Bhavcopy is the instrument: unadjusted, one request per DATE, and NSE+BSE are independent so **rule 2 applies to the label**. First pass: **282 reconciled / 230 single-source / 76 no-source**, 87% within 2pp of the master. Final: **526 of 623 labelled (84.4%)** - 338 two-source, 206 single-source, **1 prefix-only**. Match provenance (isin/code/symbol/symbol_prefix/ambiguous_prefix) added as a deterministic substitute for the plausibility inference H8 forbids. BSE matched by ISIN on ZERO rows (its old format carries no ISIN column); NSE on 461 |
| 27 | Listing-day capture (standing rule) | 26 | **DONE** | 2026-10-06 | 2026-10-06 | **A listing price is captured ON the listing date, never later** — a later read is silently restated for splits/bonuses (Syngene 295→147.50, +18%→−41%). Refuses a future date; refuses a past one without `--catch-up`, which reads that date's ARCHIVED bhavcopy. Also scores predictions (2e) by APPENDING an outcome row. Wired into the 17:30 job |
| 28 | Documents still missing | 21 | **DONE** | 2026-10-06 | 2026-10-06 | `reports/DOCUMENTS_STILL_MISSING.csv` — **37, down from 68**. Decisive: **not a naming problem.** All 37 listed 2010–2020, 23 before 2013, NONE has an alias. SEBI's archive does not reach back. NSE offer docs have no click-through but 403/503 APIs; BSE SME is open but SME-only |
| 29 | Dead-code sweep + go-live wiring | 20 | **DONE** | 2026-10-08 | 2026-10-08 | **H20, H21.** `first_day_marker` removed entirely (False on **621 of 623** rows - both exchanges populate previous close on a listing day, so the premise was wrong) along with the `prev` plumbing that existed only to feed it. An assertion ending `... or True` that **could not fail** was found and fixed the same way. AST scan of all 15 live-path modules: no dead imports; 2 unread variables removed. No executable `L_day1`/`L_day2`/forecaster path survives - the 4 remaining mentions are comments recording H1 |
| 30 | Schedule, send window, catch-up, retry, audit | 29 | **DONE** | 2026-10-08 | 2026-10-08 | Day-end 17:30 -> **19:30 IST** (index closes publish after settlement). **Not one 15:00 email had ever been sent at 15:00** - markers read 16:53, 21:49, 22:11, 00:06, 00:39, all outside the window, and nothing checked the clock. `send_window()` now refuses outside 14:00-16:00 and exits non-zero; **never caught up**. New `capture_audit.py` (12/12): a gap is `attempts()==0`, not an empty capture. New `retry-infra-failure.yml` re-runs only when NO step executed, bounded at 3. Saturday audit cron. `LIVE_SETUP.md` rewritten |
| 31 | NSE Basket 1 access test | 30 | **DONE** | 2026-10-08 | 2026-10-08 | **NSE is fully open under H18.** `ipo-active-category` reproduces the master's Total to 2dp on **14 of 14**; `ipo-detail` is an intermediate cut running 9-57% LOWER and would wreck the decision. But 14 exact matches is evidence of a **shared origin, not independence** - recorded as NOT a rule-2 reconciliation. BSE has no working subscription endpoint. `public-past-issues` carries real `ipoStartDate` for **1,474** issues - a direct fix for the master's date defect. Intraday behaviour UNTESTABLE until a mainboard IPO is open: **HDFIRE, 13-15 Oct** |
| 32 | Under-delivery tripwire | 30 | **DONE** | 2026-10-08 | 2026-10-08 | **H19.** `tripwire.py` (16/16), wired into the monthly retrain. Two consecutive under-delivering 12-month windows re-derives; one does not. Thin windows recorded but never counted; same-month re-runs revise rather than increment; a corrupt state file RAISES rather than silently resetting to zero. **Armed: L1 and L2 both at 1 of 2** |
| 33 | Did the world change? | 32 | **DONE** | 2026-10-08 | 2026-10-08 | FII hypothesis **not verified and not proxied** - `api/fiidiiTradeReact` returns today only (`?date=` accepted and ignored), the archive page is JS-rendered. What is measurable says 2025 was **not** a bad tape: TRI **+11.4%**, median pre-listing 5d move **+0.05%**. The delivered rate ranks **-0.767 against IPO supply** but only **+0.206 against the index**. 7 usable years for L1, 5 for L2 - not significant alone, and said so |
| 34 | Three candidate features | 16 | **DONE** | 2026-10-08 | 2026-10-08 | **All three rejected.** Free float tested two ways: `offer_pct_of_cap` gives the largest AUC gain anywhere (+0.0290 L1) and still does not convert to delivery; `non_promoter_post_pct` makes AUC **worse**. Nifty close-to-listing is a **leakage violation as a feature** (unknowable at the 15:00 bid) - reported as a diagnostic, and its +0.0063/+0.0001 is the set's most interesting negative: the listing gain is issue-specific, not a market ride. Anchor quality **could not be tested** (see Stage 18). Materiality floor added: a delta below one hit (~1pp at 100 fires) is noise |
| 35 | Cron in UTC + one trading date per run | 30 | **DONE** | 2026-10-08 | 2026-10-09 | **H20 extended.** Timezone hypothesis REJECTED - `git log` shows the cron was correct UTC from the first commit. The real cause is a **5h31m-9h06m GitHub scheduler delay**, nine for nine. Crons rewritten in UTC with IST comments; four email attempts 14:15-15:00 IST; mode selection is an exhaustive `case` that EXITS 1 on an unrecognised trigger. The 2026-10-08 mislabelling was a **midnight crossing**, not a UTC bug: run #11 started 23:59:30 IST and each step re-asked the clock, so it requested tomorrow's index closes and logged 15 NULLs. New `trading_day.py` (11/11) fixes the date once in IST per run |
| 36 | Idempotent send + dead-man | 35 | **DONE** | 2026-10-09 | 2026-10-09 | **Task 4.** `sent_markers.py` (12/12), keyed by IPO AND date. First attempt inside the window that succeeds sends; the rest exit GREEN. A refusal is RED only if a decision was owed and undelivered. Past 15:30 IST an undelivered decision emails `IPO decision - NOT SENT`. The notice writes a `not_sent_notice` marker that `already_sent()` deliberately does NOT count - otherwise the silence would become permanent. **Verified live: run #16 green, refused for being too EARLY, nothing owed, no email** |
| 37 | Email content (H23) + test send | 36 | **DONE** | 2026-10-09 | 2026-10-09 | **Task 5.** Body order: name + closing date, 15:00 figures with exact fetch time and source, then L1/L2 as BID / NO BID each with "threshold 28.39x met/NOT met", then the H23 caveat, GMP blank, Nifty footer. Figures print BEFORE verdicts - a reader who sees the verdict first has nothing to check it against. "NO BID" is display-only; `score_l` still returns `no` because the log and the backtest key on it. **Test email SENT: run #14, subject `IPO decision - TEST`, no marker written** |
| 38 | Record both figures | 37 | **DONE** | 2026-10-09 | 2026-10-09 | **Task 6.** `sub_*_1500` on the prediction row, written at send and only when the capture point really is 1500. Finals go to `data/final_subscription.csv` keyed to `prediction_id`, appended, never by rewriting the prediction (rule 10) - overwriting `total_x` would destroy the only record of what the decision was taken on. Carries `would_L1/L2_fire_on_final` and `verdict_would_have_changed`, so the 3pm understatement becomes a counted quantity |
| 39 | Ingest rewired (Task 7) | 38 | **DONE** | 2026-10-09 | 2026-10-09 | Pricing **deleted** (6,402 chars): all 15 rows it ever wrote were NULL/no_source, and it priced up to 3 days late, which the Stage 27 rule forbids. Harvest kept. Backfill went 0/15 -> **6/15** after the first attempt diagnosed the real fault: isin AND symbol were NULL on every row, so both bhavcopies were downloading fine and being searched for an unnamed company. Fixed with NSE `public-past-issues`, requiring name AND date to agree. 2 segment labels corrected to `sme` from NSE's own `securityType` (rule 6) |
| 40 | Source order (H22) + HDFIRE poller | 39 | **DONE (H22 PROVISIONAL)** | 2026-10-09 | 2026-10-09 | **Tasks 8/9.** `nse_subscription.py` (30/30): NSE `ipo-active-category` primary, Chittorgarh fallback, `ipo-detail` NEVER (it is an intermediate cut running 9-57% low). Single-origin - the flag stays, because 14 exact matches is a shared origin not independence. Safe before the test via a freshness gate: Total > 0, `updateTime` on the trading date, symbol matches. `hdfire_poll.py` (18/18); **HDFIRE confirmed from NSE: series EQ = mainboard, 13-15 Oct**, with RAVITA (SME) as a control |
| 16b | Settle the issue-size sign | 16 | DONE | 2026-10-01 | 2026-10-01 | **H11**: no half-life defends the sign, so issue size is DROPPED. log1p(Total) alone is +0.31pp better on L1, identical on L2, and passes C5 where Set A failed. `reports/stage16b_half_life.json` |

### Stages 41-46 (2026-10-10)

| Stage | Title | Status | Notes |
|---|---|---|---|
| 41 | Trading date from the cron DUE time | DONE | `trading_day.py` resolves the UTC cron string to the last slot at or before now and converts it to an IST date. The 9 Oct day-end leg, due 19:30 IST, started 00:46 IST on 10 Oct and stamped itself 2026-10-10. 26/26 self-tests, including the simulated 01:30-next-day run |
| 42 | Day-end capture idempotent on its trading date | DONE | `send_daily_email.day_end_captured()`. Tests the 15 index closes, not the snapshot marker - a day with no IPO open captures 15 closes and 0 snapshots, so the marker alone would say "nothing captured". Verified green by dispatch #38042425621 |
| 43 | Concurrency group + push retry | DONE | `group: model-l-live`, `cancel-in-progress: false` (queue, never cancel). The commit step retries a rejected push five times with backoff and exits 1 if all five fail - an unpushed capture on a throwaway runner is a lost capture. "pushed on attempt 1" in the dispatch log |
| 44 | The 15:35 dead-man, asserted | DONE | `main()` driven end to end with the clock, market view, markers and SMTP substituted. Six paths. **Finding: at 15:35 the window is still OPEN, so a run with no marker sends the real VERDICT** - the notice fires only if that send fails, or past 16:00 |
| 45 | H24, the tripwire overlap rule | DONE | A window counts only if half its resolved firing rows are new since the last **counted** window. Gate on incrementing, never on resetting. State re-evaluated: both targets stay at 1 of 2, now with 49 / 36 firing-row identities stored. 33/33 |
| 46 | Recover the lost index closes | DONE | 7 **and** 8 October, 15 of 15 each, from niftyindices.com with per-index source and fetch time. The 15 NULL rows run #11 wrote stay on the record (rule 10) |

**Dispatch-option gap closed in passing:** `dry-run`, `probe` and `rehearse` were
`workflow_dispatch` options with **no branch** in the workflow's `case`, so choosing one
ran nothing and exited 0 - a green run that did no work. `rehearse` removed, the other two
wired, and an unmatched mode now exits 1.

**Known gap, recorded not fixed:** the email subject is the prefix plus a summary of the
day (`IPO decision - 1 open, 1 closes today`), not the prefix plus the issue name that
Task 5 asked for. Now asserted in the self-test so it is visible rather than assumed.

### Root housekeeping (2026-10-10)

The repository root went from **110 entries to 79**: 22 loose data files to 0, and 305 MB
of local-only bulk out of sight. `git tag pre-housekeep` is the state before it.

| Moved to | What | Why |
|---|---|---|
| `data/` | the 10 primary datasets — `master_with_symbols.csv`, `holding_target.csv` / `_3y`, `issue_dates_recovered.csv`, `predictions_log.csv`, `price_history.csv`, `market_heat.csv`, `target_MISSES*.csv`, `rhp_verify.json` | never scratch; they were simply in the wrong folder. 20 modules updated, plus the live workflow's git-add list |
| `data/rhp_sources.csv` | was `manual_rhp/SOURCES.csv` | the one tracked file inside a now-ignored folder, and it is provenance |
| `reports/intermediate/` | `first_bar_scan.csv`, `symbols_CANDIDATES_cleanquery.csv`, `merge_REJECTIONS.csv`, `job1b_CONFLICTS.csv`, `issue_dates_FLAGS.csv` | written as bare `to_csv("name.csv")` by scripts that chdir to the root first, so they landed in the root **by design**. Now named from `__file__` |
| `reports/` | `run_log.txt` → `run_overnight.log`; the two 28 Sep session write-ups, dated | they are reports |
| `docs/` | `IPO-Factor-Research-v1.md`, `IPO-Model-Build-Spec-v2.md` | the original input specs |
| `_local/` (gitignored) | `rhp_manual` 279 MB, `rhp_fetched` 26 MB, `backup_pre_fixes`, `backup_session2` | kept, as asked, but in one place. Every PDF is re-fetchable via `data/verified_rhp_manifest.csv` |

**Deleted** — six files mentioned nowhere in any code (`issue_dates_summary.txt`,
`report_stats.txt`, `task1_baserate.txt`, `task3_targets.txt`, `symbols_TO_RESOLVE.csv`,
`supervisor_log.txt`), `EMAIL_SETUP.md` (folded into `LIVE_SETUP.md` §6), and two
superseded scripts (`build_spotcheck.py`, `build_documents_needed.py`). All were tracked,
so `pre-housekeep` still holds them.

**Two defects it turned up, both fixed:**

1. `check_env.py`'s data/ contract check had been **failing** — 12/13 — on four files,
   none of which violated anything: it matched any `.xlsx` anywhere
   (`reports/SPOTCHECK.xlsx`) and any string starting `data/` (a `git add` pathspec). It
   now matches a *read* of a hardcoded `data/` path, and a second check runs the pattern
   against 3 real violations and 4 benign shapes so it cannot quietly stop working.
   **14/14.** CLAUDE.md requires this script to pass before any overnight run, so a gate
   that could not pass was worse than no gate.
2. `EMAIL_SETUP.md` printed the email subject as `IPO decision — ` with an **em dash**.
   The subject is a byte-exact hyphen with a self-test asserting it, so the document would
   have sent anyone building a filter to the wrong string.

**Not merged, and why:** `build_spotcheck` vs `_v2` and `build_documents_needed` vs
`_still_missing` look like duplicate pairs but are supersessions — collapsing them would
have lost the distinction rather than removed a duplicate. `stage2_oof` imports
`stage2_feature_comparison`: a driver and its library, not two copies. The ~30 remaining
`stage*.py` / `build_*.py` / `verify_*.py` scripts are the reproducible evidence behind
claims in PLAN, DECISIONS and the stage reports; `write_model_l_card.py` and
`stage16_model_l.py` are the only generators of `MODEL_L_CARD.md` and its input. Deleting
any of those would trade a tidy root for an unreproducible decision log.

Verified: 366 self-test assertions across 12 modules, `check_env` 14/14, and dispatch
`38044701907` green on the runner with all 11 pre-flight self-tests passing and
`data/predictions_log.csv` staging correctly.

## Gates

| Gate | After stage | Status | Decision (verbatim in DECISIONS.md) |
|---|---|---|---|
| A | 2 | ✅ **CLOSED** 2026-09-30 | A1: Model L uses **Set A** for both L1 and L2 (`log1p(Total)` + `log(issue size)`). A2: Set C retained as a standing challenger, promoted only by champion/challenger. A3: Sets B and D rejected; category figures still displayed in live reports |
| F | 4A | CLOSED 2026-09-30 | User approved a capped 200-request ID walk |
| F2 | 4A ID walk | ✅ **CLOSED** 2026-10-01 by **H1** | Cancel Stage 4B's backfill, cancel `L_day1`/`L_day2` and the forecaster, keep B4 forward collection, and backfill anchor/lock-in instead (now Stage 18) |
| B | 6 | — | |
| C | 8 | SUPERSEDED by Gate C2 | Spot-check delivered (20 rows, 5 companies) but coverage was 24% on the headline financials. H5/H6 re-scope the work rather than re-run it |
| C2 | 15 | **AWAITING_USER** (opened 2026-10-01) | Coverage 59.6% usable / 63.0% adjusted vs a 60% target; 20-row spot-check from H6 fields only in `reports/SPOTCHECK_V2.csv`/`.xlsx`. Recommend approving the field set, but decide first whether the 11 fields at or below 50% are worth keeping as sparse columns |
| B | 16 | **AWAITING_USER** (opened 2026-10-01) | `model_l_v1.0` frozen; both targets pass every C5 gate out-of-time. Decide on the POSITIVE issue-size coefficient the 2-year half-life produces, and on amending Amendment 02 section A where two of nine rejections did not reproduce. **SUPERSEDED 2026-10-05 by H17**: H16 had the direction backwards. Deriving on subscription instead of through a calibrated probability gives L1 ≥ 28.39x and L2 ≥ 54.02x, which roughly DOUBLES the bids. L1's 90% is also refuted (86.3% at its naive threshold). Ratify H17. |
| D | 9 | — | |
| E | 12 | — | |

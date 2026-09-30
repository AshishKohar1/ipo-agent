# PLAN Amendment 01 — decisions of 2026-09-30

Supersedes the named sections of `PLAN.md`. Merge into `PLAN.md`, record each numbered
decision in `DECISIONS.md` with this date, then continue under the stage protocol.

---

## A. Gate A — RESOLVED

**Decision A1.** Model L uses **Set A** for both L1 and L2: `log1p(Total subscription)` +
`log(issue size)`.

**Decision A2.** **Set C** (Set A + market IPO heat) is retained as a **standing
challenger** in monthly retraining. It is statistically tied with Set A; promote it only
if it wins on the champion/challenger rule, never by hand.

**Decision A3.** Set B and Set D (the QIB/HNI/RII split) are **rejected**. The paired
bootstrap showed Set B is reliably beaten on both targets. The three category figures are
still **displayed** in every live report for the user's own judgement — they are just not
model inputs.

Supersedes: PLAN.md §7 Stage 2 (now closed) and any feature list implying the split.

---

## B. Stage 4 — RESOLVED. Sources and scope.

**Decision B1 — blocked sources.** Do not fetch from: **IPO Ji** (robots.txt names
ClaudeBot and anthropic-ai), **InvestorGain** (`ai-train=no`), **ipoindex.in** (Terms of
Use §10 prohibits automated scraping), **iporupee.com** (T&C prohibits scraping). Never
send a browser User-Agent to work around any of these. If a source's robots.txt or terms
change to prohibit access, stop using it and report.

**Decision B2 — Chittorgarh is permitted for personal use.** robots.txt allows it; its
disclaimer restricts *public and commercial* use, not private analysis. Verified: every
IPO page carries a **"Day-wise Subscription Details"** table with QIB / NII / bNII / sNII
/ Retail / Total per bidding day, plus anchor investor names, allocations and lock-in
dates. Rate limit: **minimum 3 seconds** between requests. Re-read robots.txt at the start
of every run and abort if it has changed.

**Decision B3 — sample before bulk.** Before fetching all 652, test **20 IPOs** spread
across 2010, 2013, 2016, 2019, 2022 and 2025. Report per year whether the day-wise table
is present, and how many bidding days it carries. Chittorgarh's own note says that for
past IPOs it publishes "final bidding detail as of the last day" — day-wise coverage for
older years is unverified and may thin out. **Report the coverage table and stop for a
decision before bulk fetching.**

**Decision B4 — forward collection.** Independently of the backfill, record an evening
snapshot of live subscription from the **NSE and BSE official APIs** for every open IPO,
every day. This builds a fully two-source, fully permitted history going forward.

**Decision B5 — GMP is dropped as a model feature.** No permitted historical source
exists. See section D.

---

## C. Model L — three decision-point models

**Decision C1.** Train and validate three separate models per target, each on the data
actually available at that moment. Never feed day-N subscription into a model trained on
final figures — the bias is large and one-directional (observed: Adroit Industries QIB
1.82x on day 2 → 195x on the final day).

| Model | Trained on | Role |
|---|---|---|
| `L_day1` | Day-1 subscription | Informational — "bid today?" |
| `L_day2` | Day-before-final subscription | Informational — "bid tomorrow?" |
| `L_final_3pm` | Final-day ~3pm subscription | **Production bidding model** |

**Decision C2 — no forecaster.** The chained design (forecast final subscription → feed
into Model L) is dropped. Direct day-N models make one prediction instead of two and avoid
compounding error. Stage 5 is re-scoped accordingly.

**Decision C3 — `L_final_3pm` approximation, and its honest limitation.** No 3pm
historical snapshots exist. Until forward collection accumulates, approximate it and
**label it clearly in the model card as approximated, not measured**. Rebuild it properly
once ~40 IPOs of real 3pm data exist. If the approximation cannot be made defensible,
report that and fall back to the final-subscription model with a stated warning that it
overestimates at 3pm.

**Decision C4 — uncertainty is reported, not hidden.** Day-2 demand genuinely may or may
not continue. That is what the model measures: if day-2 is weakly informative, `L_day2`
will show a low AUC and rarely fire at its threshold. Report each model's AUC and firing
rate side by side so the value of waiting is visible rather than assumed.

**Decision C5 — thresholds.** Unchanged rule: L1 requires a 90% hit rate, L2 requires 80%;
pick the lowest threshold meeting the requirement whose Wilson 95% lower bound is at least
(requirement − 5pp) and which fires on at least 20 IPOs. Apply it separately to each of
the three models — they will land on different thresholds.

Supersedes: PLAN.md §5 "Final-day forecaster outputs P10/P50/P90" and "Model L is fed P10";
§7 Stage 5; §6 dependency rows for Stages 5–7.

---

## D. GMP — display only

**Decision D1.** GMP is **not** a model feature and **not** an automated fetch. It appears
in the live report as a field the user fills in manually from a browser, clearly marked as
outside the model.

**Decision D2.** Every live report logs the GMP value the user supplies (or blank) in
`predictions_log.csv`, so that after ~12 months its incremental value over subscription
can be measured retrospectively. Until then, no GMP-based rule may influence a verdict.

Required format in the live report:

```
Orient Cables — closing today, bid by 4:00 PM
  L_final_3pm  L1: 94%  -> BID        (threshold 90%)
               L2: 71%  -> no         (threshold 85%)
  Subscription: Total 8.77x | QIB 3.1x | HNI 14.2x | Retail 6.4x   [15:00]
  Veto flags: none
  GMP: ____%   [NOT IN MODEL — your judgement only]
```

---

## E. Live schedule — Model L

**Decision E1.** Paytm Money's IPO cutoff is **4:00 PM** (user-confirmed).

| Job | Time IST | Action |
|---|---|---|
| Score | **15:00** daily | Fetch subscription for IPOs closing today, score `L_final_3pm`, write report |
| Notify | **15:30** daily | Deliver the report — 30 minutes before cutoff |
| Snapshot | **19:00** daily | Record day-wise subscription (NSE + BSE) for every open IPO |
| Ingest | **Mon & Thu 08:00** | Add newly listed IPOs to the dataset, score past predictions |
| Retrain | 1st of month, 08:00 | Champion/challenger |

The 30-minute gap between scoring and notifying is deliberate: a slow fetch must not push
the reminder past the cutoff. If the 15:00 job fails, retry immediately and still notify by
15:30, marking the report `PARTIAL — verify subscription manually`.

**Decision E2.** Model L goes live **without** any forecaster. It is not a prerequisite.

---

## F. Repository

**Decision F1.** The user merged `work` into `main`. Simplify to a **single branch**:
use `main` as the working branch; delete `work` locally and remotely if it still exists.
Tag completed stages (`git tag stage-NN-done`) instead of branching. Update `PLAN.md` §3
and `CLAUDE.md` to refer to `main` throughout.

**Decision F2.** `reports/STAGE_04_REPORT.md` and the matching `PROGRESS.md` update are on
the laptop, uncommitted. Commit and push them **before** starting any new work. Use
separate commands, not `&&` — it fails in older PowerShell.

---

## G. New stage 4B — day-wise subscription backfill

Replaces PLAN.md §7 Stage 4.

**Scope:** every mainboard IPO in `master_with_symbols.csv` without an `exclude_reason`.
SME stored separately.

**Method:** for each IPO, resolve its Chittorgarh subscription page, extract the day-wise
table (all categories, all days), plus anchor allocation and lock-in dates where present.

**Capture per row:** ipo, isin, date, day_index, day_label (`day_1` … `day_before_final`,
`final_day`), category, subscription_x, source, fetched_at.

**Reconciliation:** the `final_day` Total must match the master dataset's Total within 5%.
Mismatches → NULL with both values logged. Day-1 and day-2 values have no second source and
are flagged `single_source_unverified` — they may be used for `L_day1` and `L_day2`, and
those model cards must state it.

**Politeness and resumability:** ≥3s between requests, per-IPO status in
`data/daywise_progress.csv`, commit every 10 IPOs, resumable.

**Acceptance:** coverage table by year; final-day reconciliation rate ≥95% on overlapping
IPOs; every mismatch logged.

---

## H. Revised dependencies

| Stage | Title | Depends on | Ends in |
|---|---|---|---|
| 4A | Chittorgarh 20-IPO coverage sample | 1 | **Gate F** |
| 4B | Day-wise backfill (chunked) | Gate F | — |
| 3 | Calibration curve + thresholds | Gate A ✅ | — |
| 5 | Three decision-point models | 3, 4B | — |
| 6 | Productionize Model L | 3, 5 | **Gate B** |
| 7 | Go live | Gate B | — |
| 8 | RHP extraction + spot-check | 1 | **Gate C** |
| 9–13 | Unchanged | | |

Stage 8 depends only on Stage 1 and needs no decision from the user — it is the fallback
whenever a gate blocks everything else.

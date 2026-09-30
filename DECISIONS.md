# Decision log

Gate decisions are recorded here verbatim, with the date (IST), when the user answers in the
form `Gate X decision: …`. Decisions taken inside a stage (e.g. Stage 3's calibration
choice) are recorded here too. Past entries are never edited.

## 2026-09-30 — PLAN Amendment 01

Source: `PLAN_AMENDMENT_01.md`, kept in the repo as the audit trail. Merged into `PLAN.md`
the same day. Decisions are quoted verbatim.

| Date (IST) | Gate / stage | Decision (verbatim) | Recorded by |
|---|---|---|---|
| 2026-09-30 | Gate A / Stage 2 | **A1.** Model L uses **Set A** for both L1 and L2: `log1p(Total subscription)` + `log(issue size)`. | Claude (from PLAN_AMENDMENT_01.md) |
| 2026-09-30 | Gate A / Stage 2 | **A2.** **Set C** (Set A + market IPO heat) is retained as a **standing challenger** in monthly retraining. It is statistically tied with Set A; promote it only if it wins on the champion/challenger rule, never by hand. | Claude |
| 2026-09-30 | Gate A / Stage 2 | **A3.** Set B and Set D (the QIB/HNI/RII split) are **rejected**. The paired bootstrap showed Set B is reliably beaten on both targets. The three category figures are still **displayed** in every live report for the user's own judgement — they are just not model inputs. | Claude |
| 2026-09-30 | Stage 4 / rule 5 | **B1 — blocked sources.** Do not fetch from: **IPO Ji** (robots.txt names ClaudeBot and anthropic-ai), **InvestorGain** (`ai-train=no`), **ipoindex.in** (Terms of Use §10 prohibits automated scraping), **iporupee.com** (T&C prohibits scraping). Never send a browser User-Agent to work around any of these. If a source's robots.txt or terms change to prohibit access, stop using it and report. | Claude |
| 2026-09-30 | Stage 4 | **B2 — Chittorgarh is permitted for personal use.** robots.txt allows it; its disclaimer restricts *public and commercial* use, not private analysis. Verified: every IPO page carries a **"Day-wise Subscription Details"** table with QIB / NII / bNII / sNII / Retail / Total per bidding day, plus anchor investor names, allocations and lock-in dates. Rate limit: **minimum 3 seconds** between requests. Re-read robots.txt at the start of every run and abort if it has changed. | Claude |
| 2026-09-30 | Stage 4A | **B3 — sample before bulk.** Before fetching all 652, test **20 IPOs** spread across 2010, 2013, 2016, 2019, 2022 and 2025. Report per year whether the day-wise table is present, and how many bidding days it carries. … **Report the coverage table and stop for a decision before bulk fetching.** | Claude |
| 2026-09-30 | Stage 4B | **B4 — forward collection.** Independently of the backfill, record an evening snapshot of live subscription from the **NSE and BSE official APIs** for every open IPO, every day. This builds a fully two-source, fully permitted history going forward. | Claude |
| 2026-09-30 | Stage 4 / 5 | **B5 — GMP is dropped as a model feature.** No permitted historical source exists. See section D. | Claude |
| 2026-09-30 | Stage 5 | **C1.** Train and validate three separate models per target, each on the data actually available at that moment. Never feed day-N subscription into a model trained on final figures — the bias is large and one-directional (observed: Adroit Industries QIB 1.82x on day 2 → 195x on the final day). `L_day1` / `L_day2` informational; `L_final_3pm` is the production bidding model. | Claude |
| 2026-09-30 | Stage 5 | **C2 — no forecaster.** The chained design (forecast final subscription → feed into Model L) is dropped. Direct day-N models make one prediction instead of two and avoid compounding error. Stage 5 is re-scoped accordingly. | Claude |
| 2026-09-30 | Stage 5 | **C3 — `L_final_3pm` approximation, and its honest limitation.** No 3pm historical snapshots exist. Until forward collection accumulates, approximate it and **label it clearly in the model card as approximated, not measured**. Rebuild it properly once ~40 IPOs of real 3pm data exist. If the approximation cannot be made defensible, report that and fall back to the final-subscription model with a stated warning that it overestimates at 3pm. | Claude |
| 2026-09-30 | Stage 5 | **C4 — uncertainty is reported, not hidden.** Day-2 demand genuinely may or may not continue. That is what the model measures: if day-2 is weakly informative, `L_day2` will show a low AUC and rarely fire at its threshold. Report each model's AUC and firing rate side by side so the value of waiting is visible rather than assumed. | Claude |
| 2026-09-30 | Stage 3 / 5 | **C5 — thresholds.** Unchanged rule: L1 requires a 90% hit rate, L2 requires 80%; pick the lowest threshold meeting the requirement whose Wilson 95% lower bound is at least (requirement − 5pp) and which fires on at least 20 IPOs. Apply it separately to each of the three models — they will land on different thresholds. | Claude |
| 2026-09-30 | Stage 6 / 7 | **D1.** GMP is **not** a model feature and **not** an automated fetch. It appears in the live report as a field the user fills in manually from a browser, clearly marked as outside the model. | Claude |
| 2026-09-30 | Stage 6 / 7 | **D2.** Every live report logs the GMP value the user supplies (or blank) in `predictions_log.csv`, so that after ~12 months its incremental value over subscription can be measured retrospectively. Until then, no GMP-based rule may influence a verdict. | Claude |
| 2026-09-30 | Stage 7 | **E1.** Paytm Money's IPO cutoff is **4:00 PM** (user-confirmed). Score 15:00, notify 15:30, snapshot 19:00, ingest Mon & Thu 08:00, retrain 1st of month 08:00. The 30-minute gap between scoring and notifying is deliberate. | Claude |
| 2026-09-30 | Stage 7 | **E2.** Model L goes live **without** any forecaster. It is not a prerequisite. | Claude |
| 2026-09-30 | Repository | **F1.** The user merged `work` into `main`. Simplify to a **single branch**: use `main` as the working branch; delete `work` locally and remotely if it still exists. Tag completed stages (`git tag stage-NN-done`) instead of branching. Update `PLAN.md` §3 and `CLAUDE.md` to refer to `main` throughout. | Claude |
| 2026-09-30 | Repository | **F2.** `reports/STAGE_04_REPORT.md` and the matching `PROGRESS.md` update are on the laptop, uncommitted. Commit and push them **before** starting any new work. Use separate commands, not `&&` — it fails in older PowerShell. | Claude |

### Notes on execution

- **F2 done first**, before any other work: committed as `eadae0c` and pushed.
- **A1 closes Gate A.** `PROGRESS.md` and `reports/STAGE_02_REPORT.md` updated to record it.
- **B1 confirms and extends** what Stage 4 had already found independently (`reports/STAGE_04_REPORT.md`): IPO Ji and InvestorGain were already excluded on the same grounds. The amendment adds ipoindex.in and iporupee.com.
- **B2 resolves the Stage 4 blocker** that Stage 4's report raised. Note the report's separate finding still stands: Chittorgarh is a *single* source, and IPOMatrix shares its parent, so day-1/day-2 values cannot be reconciled — which is exactly why B4 adds forward two-source collection and 4B flags those values `single_source_unverified`.
- **C1's premise is confirmed by our own data.** Stage 2's models were trained on *final* subscription, so they must not be applied to day-1 or day-2 figures; the three-model design in C1 is what makes a pre-bid call legitimate.

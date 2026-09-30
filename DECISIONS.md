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

## 2026-09-30 — Stage 3 outcome (recorded per PLAN.md Stage 3 step 5)

| Date (IST) | Gate / stage | Decision | Recorded by |
|---|---|---|---|
| 2026-09-30 | Stage 3 | **Isotonic calibration is adopted for both L1 and L2.** Firing rule: fire iff the calibrated probability reaches the required hit rate — `p_cal ≥ 0.90` for L1 (≈ raw 0.75) and `p_cal ≥ 0.80` for L2 (≈ raw 0.74). Both conditions of step 5 are met: held-out Brier beats raw (L1 0.1579 vs 0.1596; L2 0.1586 vs 0.1624) **and** the threshold passes the C5 hit-rate, Wilson and 20-fire gates out-of-time (L1 fires 117, 94.0% hit, lower bound 88.2%; L2 fires 96, 87.5% hit, lower bound 79.4%). | Claude |
| 2026-09-30 | Stage 3 | **The C5 bucket rule is NOT used for the final thresholds.** Measured honestly out-of-time it fails L2's promise (fires 83, 77.1% hit against the 80% requirement) and only scrapes L1 (92.4%, lower bound 85.1% against an 85.0% floor). Its apparent earlier pass (83.7%) came from selecting the threshold on the same rows it was scored on. The C5 *gates* remain in force — they are what disqualified the alternatives. | Claude |
| 2026-09-30 | Stage 3 | **Platt rejected despite winning L2's Brier** (0.1557 vs isotonic 0.1586): its L2 threshold fails the C5 Wilson gate (74.2% against the 75% floor). Brier is not the decision criterion; the C5 gates are. | Claude |
| 2026-09-30 | Stage 3 | **Live output must not present the calibrated probability as a literal chance.** Isotonic overclaims in the top tail: it claims a mean 98.5% and delivers 94.0% (L1), claims 99.2% and delivers 87.5% (L2). Reports show the verdict and the validated hit rate for the firing band. | Claude |

## 2026-09-30 — Stage 3 confirmed by independent verification (G1, G2)

Recorded after `verify_stage3.py` reproduced every Stage 3 figure from first principles,
sharing no code with `models/calibration.py` or `models/framework.py`: isotonic re-derived
via the greatest convex minorant of the cumulative-sum diagram (a convex-hull scan, not the
PAV stack) agreed to 0.000e+00 on 200 random problems, and 14/14 reported claims reproduced.
A leakage assertion confirms every calibrator and every bucket threshold was fitted or
chosen on years strictly before the year it scored.

| Date (IST) | Gate / stage | Decision | Recorded by |
|---|---|---|---|
| 2026-09-30 | Stage 3 | **G1. Isotonic calibration is adopted for L1 and L2 threshold selection, replacing the C5 bucket rule.** C5's hit-rate, Wilson-bound and 20-fire requirements remain in force as **acceptance checks**; only the selection method changes. Firing rule: fire iff calibrated p ≥ 0.90 (L1, raw-equivalent 0.75) and ≥ 0.80 (L2, raw-equivalent 0.74). Evidence, out-of-time on 260 held-out rows: isotonic L1 fires 117 at 94.0% (Wilson 88.2%), L2 fires 96 at 87.5% (Wilson 79.4%) — both PASS; the bucket rule fires 92 at 92.4% for L1 (PASS, but only 0.1pp above the Wilson floor) and **83 at 77.1% for L2, FAILING the 80% requirement**. Isotonic also beats raw on Brier for both targets (0.1579 vs 0.1596; 0.1586 vs 0.1624). | Claude |
| 2026-09-30 | Stage 3 | **G2. Isotonic overclaims in the top tail** — among rows it places above the requirement it claims a mean 98.5% and delivers 94.0% (L1), and claims 99.2% and delivers 87.5% (L2), an overclaim of +4.5pp and +11.7pp. **Live reports must print the verdict and the threshold met, never the raw probability as a literal chance.** This limitation is to be carried into `MODEL_L_CARD.md`. | Claude |
| 2026-09-30 | Stage 3 | **Platt rejected** despite winning L2's Brier (0.1557 vs isotonic 0.1586): its L2 threshold fails the C5 Wilson gate (74.2% against the 75% floor). Brier is not the decision criterion; the C5 gates are. | Claude |

### Notes on execution

- **F2 done first**, before any other work: committed as `eadae0c` and pushed.
- **A1 closes Gate A.** `PROGRESS.md` and `reports/STAGE_02_REPORT.md` updated to record it.
- **B1 confirms and extends** what Stage 4 had already found independently (`reports/STAGE_04_REPORT.md`): IPO Ji and InvestorGain were already excluded on the same grounds. The amendment adds ipoindex.in and iporupee.com.
- **B2 resolves the Stage 4 blocker** that Stage 4's report raised. Note the report's separate finding still stands: Chittorgarh is a *single* source, and IPOMatrix shares its parent, so day-1/day-2 values cannot be reconciled — which is exactly why B4 adds forward two-source collection and 4B flags those values `single_source_unverified`.
- **C1's premise is confirmed by our own data.** Stage 2's models were trained on *final* subscription, so they must not be applied to day-1 or day-2 figures; the three-model design in C1 is what makes a pre-bid call legitimate.

## 2026-10-01 — PLAN Amendment 02

Source: `PLAN_AMENDMENT_02.md`, kept in the repo as the audit trail. Merged into `PLAN.md`
the same day, superseded sections replaced in place. Decisions are quoted verbatim.

**H1 also closes Gate F2** (opened 2026-09-30 by the Stage 4A ID walk): the user's answer is
to cancel the day-wise backfill outright.

| Date (IST) | Gate / stage | Decision (verbatim) | Recorded by |
|---|---|---|---|
| 2026-10-01 | Stage 5 / Gate F2 | **H1 — one model only.** Build and maintain **`L_final_3pm`**. `L_day1`, `L_day2` and the final-day forecaster are **cancelled**: no permitted source publishes day-wise subscription history (Chittorgarh shows it live and deletes it once an IPO closes; IPO Ji blocks Anthropic crawlers by name; InvestorGain, ipoindex.in and iporupee.com prohibit scraping in robots.txt or terms). Stage 4B's backfill is cancelled for the same reason. | Claude (from PLAN_AMENDMENT_02.md) |
| 2026-10-01 | Stage 2 / Gate A | **H2 — feature set frozen at Set A.** `log1p(Total subscription)` + `log(issue size)`. Nine literature-sourced candidates were tested out-of-sample on 624 mainboard IPOs (2010–2026) and **all were rejected** (table in `PLAN_AMENDMENT_02.md` §A). Rationale: Total subscription already aggregates every investor category's fundamental, sentiment and valuation view expressed in money. Re-adding the components is double-counting, and Total's VIF reaches **90.0** when combined with them — which is the source of Dave (2022)'s nonsensical negative coefficients (reproduced on our data: Total +26.26, QIB −5.25, HNI −3.04). | Claude |
| 2026-10-01 | Stage 6 / live report | **H3 — demand profile is displayed, never modelled.** `retail_skew = log1p(RII) − log1p(QIB)`. Measured on 624 IPOs, median listing gain by quartile: most institution-skewed **+20.4%**, Q2 +4.1%, Q3 +2.2%, most retail-skewed **+1.6%**. Real signal, but adding it to the model changes nothing (AUC 0.8832 → 0.8811) because it is already embedded in Total. It therefore appears in the live report as `Demand profile: institution-led \| balanced \| retail-skewed` (quartile cut-points fitted on training data only) and **never** as a feature or a verdict override. | Claude |
| 2026-10-01 | Stage 2 | **H4 — correction to the record.** An earlier note claimed issue size had "flipped sign" versus the literature. On 624 mainboard IPOs 2010–2026, controlling for subscription, the standardised coefficient is **−0.356** — slightly negative, consistent with Bansal & Khanna (2012) and Huang (2025). The earlier claim came from a 588-row SME-heavy 2025–26 sample and did not generalise. The effect is small either way. | Claude |
| 2026-10-01 | Stage 8 / 15 | **H5 — aggregator-first for headline financials.** Stop extracting from the RHP anything an aggregator already publishes. Those fields come from the aggregator and the master dataset, with the RHP as the **verifying second source where found**. This satisfies rule 2 properly, because the two are genuinely independent derivations. Aggregator-first fields: issue size, fresh/OFS split, offer price band, P/E and P/B at offer, EPS, RoNW, NAV, revenue, PAT, net worth, total borrowings. | Claude |
| 2026-10-01 | Stage 8 / 15 | **H6 — RHP extraction refocuses on what nothing else publishes.** RPT % of revenue; litigation counts and ₹ quantum of the top 5 by category against company, promoters, directors; customer concentration (top-10 %), geographic concentration, licence dependence; promoter experience (years), board size and independence ratio, KMP remuneration; auditor qualification / emphasis of matter; pre-IPO placement price and date, promoter holding pre and post issue, lock-in schedule; contingent liabilities as % of net worth; number of stated uses of proceeds and GCP as % of proceeds; anchor investor list, allocation, mutual-fund share, lock-in expiry dates; MSCI six-key-issue governance capture (Ownership & Control, Board, Pay, Accounting, Business Ethics, Tax Transparency). **Coverage is measured on these fields, not on the headline financials. Target ≥60%.** | Claude |
| 2026-10-01 | Stage 15 | **H7 — provenance and refusal rules are unchanged and non-negotiable.** Every extracted value carries page number, exact source text line, document URL, SHA-256 and extractor version. Where the unit is not present on the page, the ₹-crore conversion is **withheld**, not assumed. A doubtful value is deleted, never shipped. | Claude |
| 2026-10-01 | Global rule | **H8 — never ingest AI-generated summary tables as data.** A comparison table produced by a general web-search assistant was reviewed and rejected: Jupiter Life Line and Syngene shared identical Net Worth (₹844.90 Cr) and Operating Income (₹871.60 Cr) across a 2023 hospital chain and a 2015 CRO; Syngene was listed as "100% OFS" while simultaneously claiming capital-expenditure use of proceeds; TD Power's net worth equalled its issue size; six values were marked approximate; no value carried a page citation. Such tables may be used as a prompt for human cross-checking, never as a source. Related: the ipotrack.in article "Using IPO Subscription Data to Predict Listing Day Performance" is fabricated (Nykaa stated as 23× / +9.4% / 2022 against actual 81.78× / +77.87% / 2021; "Jio Financial Services IPO" never existed — it was a demerger). Blacklist it and treat unattributed AI-written SEO content as hostile to the dataset. | Claude |
| 2026-10-01 | Stage protocol | **H9 — night-batch policy.** Any task expected to exceed ~30 minutes runs as an unattended night batch: chunked, checkpointed per item, committed at least every 10 items, resumable, and safe to kill at any moment. Night batches are scheduled **immediately after** model-logic changes in each session so they use the idle hours. | Claude |

### Notes on execution

- Amendment 02 **supersedes C1, C4 and C5's multi-model clauses** and **closes Gate F2**.
  C2 (no forecaster) and C3 (`L_final_3pm` labelled *approximated, not measured*) survive
  unchanged and now apply to the single model.
- **Stage 8's Gate C is not closed and is not re-opened as it stood.** H5/H6 re-scope the
  work into Stage 15, which ends at a new **Gate C2** measured on the H6 field list. Stage
  8's 24% figure was measured on the headline financials that H5 now removes from scope, so
  it is not comparable to the ≥60% H6 target.
- **B4 forward collection becomes the only source of day-wise data.** Every evening of delay
  loses one IPO permanently; it is scheduled in Stage 19, not Stage 4B.

## 2026-10-01 — Gate C2 closed, and H10

| Date (IST) | Gate / stage | Decision (verbatim) | Recorded by |
|---|---|---|---|
| 2026-10-01 | **Gate C2** / Stage 15 | **Keep every field. No pruning now; the priority is an exhaustive dataset, and we'll decide what to drop once coverage is visible.** | User |
| 2026-10-01 | Stage 15 | **H10 — every extracted field carries a `missing_reason`**, recording one of `not_present_on_page`, `present_but_unparsed`, `section_not_found`, `document_unavailable`. "Without this, a field sitting at 45% at the end is uninterpretable." | User |

### H10 as implemented

- `missing_reason` is a column on `extract/base.Value`, set **explicitly at each refusal
  site** in `extract/h6.py` — the distinction that matters is "the document does not
  disclose this" against "the disclosure is on the page and I could not read it", which is
  the difference between a dataset gap and an extractor gap, and only the call site knows
  which it is.
- `classify_missing_reason()` derives it from the refusal note as a fallback. The night
  batch was already running when H10 was taken and its process holds the older module, so
  `backfill_missing_reason.py` fills the column for rows already on disk without re-reading
  a single PDF.
- **A company whose document never reached an extractor produced no rows at all**, which is
  worse than a missing value: the field is invisible rather than missing. The backfill emits
  one row per H6 field for each such company with `document_unavailable`, so a field's
  denominator is the whole queue and not just the companies a document was obtained for.
- **Honest limit of the classification:** `not_present_on_page` is the *residual* category —
  the default when neither a section-location failure nor a partial-parse marker is present
  in the note. The other three are positively identified. So `not_present_on_page` should be
  read as "not positively attributable to anything else", not as a verified absence.

### First reading, on 96 companies (3,030 field-cells) — `reports/h6_coverage_with_reason.csv`

The reason column changes the picture. Coverage on the real batch is far below the
8-document sample, but the gap is overwhelmingly **disclosure, not extraction**:

| Gap type | cells | What it means |
|---|---|---|
| `not_present_on_page` | 1,313 | the section was read; the field is not positively attributable elsewhere |
| `present_but_unparsed` | 166 | **a genuine extractor gap** — concentrated in 4 fields |
| `section_not_found` | 7 | promoter section heading not located |
| `document_unavailable` | 270 | 9 companies (30 fields each) never reached an extractor |

Only four fields carry a material `present_but_unparsed` count, and those are the only ones
where more extractor work would pay: `board_independence_ratio` (69),
`contingent_liabilities_cr` (41), `litigation_aggregate_amount_cr` (33), `board_size_n` (23).
Every other low field is low because the documents do not print the number.

## 2026-10-01 — H11: the issue-size sign, settled

**Instruction (Gate B, Task 2):** "Test half-lives of 2, 3, 5, 8 years and none… Adopt the
shortest half-life at which the issue-size sign stops flipping and matches the unweighted
sign, provided its pooled AUC is within 1 percentage point of the best. If no half-life
achieves this, say so and recommend dropping issue size entirely."

### Evidence — Set A (`log1p_total` + `log_issue_size`), 620 mainboard rows, test years 2022–2026

| Half-life | L1 pooled AUC | issue-size coef | sign | L1 fires | L1 hit | L1 C5 | L2 pooled AUC | issue-size coef | sign | L2 fires | L2 hit | L2 C5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **2 y** | 0.8081 | **+0.314** | pos | 117 | 94.0% | PASS | 0.8809 | **+0.409** | pos | 96 | 87.5% | PASS |
| **3 y** | 0.8062 | +0.232 | pos | 114 | 94.7% | PASS | 0.8792 | +0.313 | pos | 96 | 85.4% | PASS |
| **5 y** | 0.8009 | +0.112 | pos | 112 | 94.6% | PASS | 0.8773 | +0.191 | pos | 92 | 85.9% | PASS |
| **8 y** | 0.7988 | +0.021 | pos | 113 | 93.8% | PASS | 0.8762 | +0.102 | pos | 91 | 85.7% | PASS |
| **none** | 0.7963 | **−0.137** | **neg** | 114 | 93.9% | PASS | 0.8737 | **−0.058** | **neg** | 92 | 83.7% | **FAIL** |

### Control — `log1p_total` ALONE (issue size dropped)

| Half-life | L1 pooled AUC | L1 fires | L1 hit | L1 Wilson | L1 C5 | L2 pooled AUC | L2 fires | L2 hit | L2 Wilson | L2 C5 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 y | 0.8051 | 119 | 95.0% | 89.4% | PASS | 0.8797 | 96 | 85.4% | 77.0% | PASS |
| 3 y | 0.8066 | 117 | 95.7% | 90.4% | PASS | 0.8796 | 95 | 85.3% | 76.8% | PASS |
| 5 y | 0.8075 | 119 | 94.1% | 88.3% | PASS | 0.8801 | 94 | 85.1% | 76.5% | PASS |
| 8 y | 0.8093 | 117 | 94.9% | 89.3% | PASS | 0.8803 | 94 | 85.1% | 76.5% | PASS |
| **none** | **0.8112** | 117 | 94.9% | 89.3% | **PASS** | **0.8808** | 94 | 85.1% | 76.5% | **PASS** |

### H11 — the decision

**No half-life satisfies the adoption rule.** The issue-size coefficient is **positive at
every finite half-life** (+0.314, +0.232, +0.112, +0.021 as the half-life lengthens) and
**negative only unweighted** (−0.137). It does not stabilise anywhere — it crosses zero
between 8 years and none. The only configuration matching the unweighted sign is
half-life `none`, whose L1 pooled AUC is **1.18pp** below the best, outside the 1pp
tolerance — and whose **L2 fails the C5 Wilson gate** (83.7% hit, lower bound 74.8% against
the 75% floor).

**H11: issue size is DROPPED. Model L becomes `log1p(Total subscription)` alone, with no
recency weighting (half-life `none`).**

The control makes this more than a tie-break — dropping issue size is *better* on every
axis that matters:

1. **Higher AUC.** L1 0.8112 against Set A's best 0.8081 (**+0.31pp**); L2 0.8808 against
   0.8809 (−0.01pp, i.e. identical).
2. **It fixes the failure.** Set A at half-life `none` fails L2's Wilson gate. The
   total-only model **passes C5 at every half-life**, including `none`.
3. **Nothing left to tune.** The AUC rises monotonically as the half-life lengthens
   (0.8051 → 0.8112 on L1), so `none` is both the best and the end of the sequence. There is
   no knob whose setting a reader could question, which was the whole objection.
4. **Better calibration.** Held-out Brier 0.1549 (L1) and 0.1604 (L2), against Set A's
   0.1579 and 0.1586 — better on L1, marginally worse on L2.

**H11 supersedes A1 and H2's "Set A, frozen".** Set A is retained as a **standing
challenger** in monthly retraining, on the same champion/challenger rule as Set C (A2) —
promoted only if it wins, never by hand. **This is the one item at Gate B that changes a
decision the user has twice frozen, so it is flagged for ratification rather than treated as
settled.**

Evidence: `reports/stage16b_half_life.json`, produced by `stage16b_half_life.py`.

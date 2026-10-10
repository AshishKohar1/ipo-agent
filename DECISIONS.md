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

## 2026-10-02 — H12 and H13 (user ratifications)

| Date (IST) | Gate / stage | Decision (verbatim) | Recorded by |
|---|---|---|---|
| 2026-10-02 | **Gate B** / Stage 16 | **H12 — I ratify H11. Model L is a one-variable model: `log1p(Total subscription)`. Issue size is dropped.** | User |
| 2026-10-02 | **Gate C2** / Stage 15 | **H13 — Gate C2 closed: keep all 30 H6 fields, prune only once full coverage is visible.** | User |

### H12 — the user's supporting evidence, recorded verbatim

The raw correlation between log issue size and listing gain is **negative in every era**:

| Era | Correlation |
|---|---|
| 2010–17 | −0.045 |
| 2018–21 | −0.227 |
| 2022–23 | −0.081 |
| 2024–26 | −0.069 |

"The positive coefficient was an artefact of the 2-year half-life placing **72.5% of weight
on 2024–2026**, where four large IPOs (Bajaj Housing +114%, Tata Technologies +140%, Premier
Energies +120%, LG Electronics +50%) dominated."

This is a better diagnosis than the one H11 recorded. H11 established only that the sign was
*unstable* across half-lives and therefore indefensible; it did not identify the mechanism.
The user's era-by-era correlations show the relationship is **consistently negative in the
raw data**, and the recency weighting did not reveal a genuine regime change — it concentrated
weight onto a handful of large, exceptionally successful recent issues. The direction of
the full-sample coefficient (−0.137 L1, −0.058 L2) was right all along; the 2-year fit was
measuring four companies.

**Consequence for the model card.** `MODEL_L_CARD.md` says the sign "was set by the recency
knob rather than by the data". That is true but understates it: the correct statement is that
the data says negative in every era and the knob manufactured a positive. The card is
updated accordingly.

**H12 closes Gate B.** `model_l_v1.0` as built and productionised in Stage 19 is the ratified
model: `log1p(Total)` alone, no recency weighting, isotonic calibration, thresholds at the
required hit rates. Set A remains a standing challenger under A2's champion/challenger rule
and is reported, never promoted by hand (`retrain_l.py`).

### H13 — what it changes

Nothing is pruned. `missing_reason` (H10) is what makes a low field interpretable, and a
field is only a candidate for removal once the **full** queue has been attempted. The
scorecard excludes a field by reading `low_variance` / coverage, not by the field being
absent from the dataset.

## 2026-10-02 — H14: the live subscription source

**robots.txt re-read before recording this** (2026-10-02, HTTP 200). Chittorgarh **still
permits** access: `User-agent: *` → `Allow: /`, with only `/ipo/ipo_discussions.asp`
disallowed. The file now names fifteen crawlers and blocks each with `Disallow: /` —
AmazonAdBot, Adsbot-Google, CCBot, GPTBot, OAI-SearchBot, omgili, omgilibot, MAZBot,
ChatGPT-User, Baiduspider, DataForSeoBot, AhrefsBot, PetalBot — and **no Claude, Anthropic,
`ai-train` or `noai` token appears anywhere in it**. We are not any of the named agents and
are not crawling: a handful of specific pages per weekday at ≥3 s. Decision B2's permission
stands. **The direction of travel is worth watching**, and `robots_ok()` already aborts the
run if a Claude or Anthropic token ever appears.

| Date (IST) | Gate / stage | Decision (verbatim) | Recorded by |
|---|---|---|---|
| 2026-10-02 | Stage 19 / live | **H14 — Chittorgarh is the live subscription source for Model L v1.0, accepted as single-source and therefore outside rule 2's two-source standard.** Every reading is tagged `single_source_unverified` in `predictions_log.csv`, and every email carries "Subscription from a single source — verify on your broker app before bidding." If NSE or BSE later grant access they become the primary pair and Chittorgarh the corroborator. | User |

### Why this was needed

NSE times out on every path for our User-Agent and BSE returns 403 even on its own
`robots.txt`. Both are recorded in `reports/exchange_permission_check.json`. Chittorgarh is
the only permitted source that publishes subscription **during** bidding.

### What single-source costs, stated plainly

Rule 2 exists because a wrong Total corrupts the only input Model L has (H12). With one
source there is nothing to reconcile against, so **a Chittorgarh error becomes a wrong
verdict with no check able to catch it.** That is the risk the user has accepted, and it is
why the caveat is mandatory on every email rather than a footnote. The mitigation is
behavioural, not technical: the user verifies on the broker app before bidding.

### Verified working, 2026-10-02

`/ipo/` is the IPO dashboard and carries the calendar with an `O` (open) / `P` (past) badge
and the issue dates. `/ipo_subscription/x/{id}/` carries live category-wise subscription
while an IPO is open. Both read successfully:

| IPO | id | Window | QIB | NII | Retail | **Total** |
|---|---|---|---|---|---|---|
| Nityas Gems & Jewellery | 2974 | 30 Sep – 05 Oct | 0.38x | 0.27x | 1.32x | **0.69x** |
| Vishal Nirmiti | 2665 | 30 Sep – 05 Oct | 1.00x | 0.84x | 0.49x | **0.60x** |

Both close **Monday 5 October**, so the first scheduled run is also the first real test.

## 2026-10-03 — H15 to H18

Taken while fixing the live pipeline, which had failed silently for three days. H15 and H17
are mine to take — they implement rules already decided. **H16 and H18 need the user's
ratification**, because each changes a promise the system makes.

### H15 — the live path carries no modelling dependency

Every scheduled run from 1–3 Oct died in ~35 s with `ModuleNotFoundError: No module named
'joblib'` at `models/framework.py:32`. `send_daily_email.py` imported `model_l`, which
imports `framework`, which imports `joblib`; joblib reaches the laptop only as a
scikit-learn dependency, and scikit-learn is banned (rule 10), so `requirements.txt` never
listed it and the cloud never got it. A *modelling* dependency was breaking *mail delivery*.

**Decision.** Live scoring reads the portable coefficient JSON through `score_l.py`, which
imports only `json`, `math` and `bisect`. No joblib, framework, dataio, numpy or pandas.
The live path is verified to import in a venv containing **no joblib at all**, so this class
of failure cannot reach the email again. joblib is also now listed explicitly in
`requirements.txt` for the fitting path.

The JSON is the artefact of record for live scoring; the joblib bundle remains the artefact
of record for fitting. `score_l.self_test()` checks they produce identical verdicts wherever
the bundle can be loaded, and the two forms of the threshold rule were measured to fire
within 0.4% of the same Total subscription.

A clean-environment audit of every module the scheduled jobs touch found **joblib was the
only missing package**. It also surfaced a pre-existing break: `model_h` imported
`mb_features`, renamed `make_features` when the `L_day1`/`L_day2` paths were deleted under
H1.

### H16 — L2's threshold under-delivers, and not because the window is thin (NEEDS RATIFICATION)

The 2026-10 retrain reported L2 delivering **76.0% (19/25) against an 80% promise**. 25
fires is thin, so the window was widened to see whether the shortfall persists as the fire
count grows.

| Out-of-sample window | Fires | Hits | Delivered | Wilson 95% LB | Meets 80%? |
|---|---|---|---|---|---|
| 12 months | 25 | 19 | **76.0%** | 56.6% | no |
| 18 months | 38 | 32 | 84.2% | 69.6% | yes |
| 24 months | 54 | 48 | 88.9% | 77.8% | yes |
| **36 months** | **125** | **97** | **77.6%** | 69.5% | **no** |
| **48 months** | **138** | **106** | **76.8%** | 69.1% | **no** |
| **60 months** | **160** | **125** | **78.1%** | 71.1% | **no** |

It is **not** a small-sample artefact: at 125–160 fires the delivered rate sits at
76.8–78.1%. The 18- and 24-month windows are the exceptions, and the 24-month figure
(88.9%) is the 2024–25 hot market — the same window that produced H11's false positive sign
on issue size.

L1 is the control and clears its promise in every window — 92.3% / 92.9% / 95.2% / 91.0% at
39–145 fires. So this is specific to L2's threshold, not general degradation and not the
window.

The derivation itself said so. Stage 16 chose L2's threshold on a delivered 85.1% over 94
fires with a **Wilson 95% lower bound of 76.5%**, passing C5 only because the rule allows
5pp of slack. 76–78% is that lower bound materialising. The central estimate was the
optimistic read all along.

**Recommendation: re-derive L2's threshold on current data at Gate B.** Re-deriving by the
C5 rule on the last 36 months gives 0.84 (0.82 at 48 months), which delivers **92.2% on 64
fires** — but at the cost of roughly **half the bids**. Those figures come from models
refitted on each window's training half, so the threshold numbers are not transplantable to
the production bundle; the re-derivation must be done on the production fit.

Until it is, **L2's stated 80% is not currently supported by the data.** L1's 90% is.

### H17 — a failed run no longer locks out its own retry

`mark_ran()` wrote an idempotency marker even when the run captured zero rows, and
`already_ran()` only checked that the key existed. A failure therefore recorded itself as a
success and blocked every retry for that slot. Three slots were stuck:
`2026-10-01|1730`, `2026-10-02|1730`, `2026-10-02|1500`.

**Decision.** A marker counts as "ran" only if `n_snapshots > 0`. Zero-row markers are kept
as the audit trail of failed attempts but do not lock. The three stuck slots were cleared by
the logic change rather than by deleting rows. Idempotency suppresses duplicate *work*,
never duplicate *attempts at work that has not happened*.

### H18 — name similarity cannot identify a company rename (NEEDS RATIFICATION)

Our master carries current names; SEBI filings carry the name at filing time, so a renamed
company resolves to nothing and reports `source_unresolved` — which reads as SEBI not having
the document rather than as us asking the wrong question. `manual_rhp/SOURCES.csv` shows
**8 of 28 hand-sourced companies had a genuine rename**, not the 4 the user spotted.

Two systematic sources were tried and **rejected**, and both are documented in
`company_aliases.py` so they are not retried as if new:

* **Aggregator name matching.** Free and looked systematic — the 2,861-row Chittorgarh
  harvest, zero requests. It produced 98 candidates that are mostly *different companies*:
  Godrej Properties to Godrej Agrovet, Power Grid Corporation to Powerica, Jaypee Infratech
  to Rahee Infratech, ARSS Infrastructure to JSW Infrastructure. Renamed companies need not
  have similar names (Eternal/Zomato scores far below any usable band) while unrelated
  Indian companies routinely share a word. Feeding these to the resolver would fetch
  **another company's filing**. Making the aggregator usable needs a name-independent key,
  and `mine_chittorgarh.py` joined on normalised *name*, so by construction it can offer no
  rename evidence.

* **"Formerly known as" on RHP covers.** Right idea, wrong anchor. A cover page also names
  the lead managers, the registrar and the selling shareholders, each with its own
  "formerly". Unanchored it produced Alivus to IDFC Securities (the BRLM), Alivus to Karvy
  Fintech (the registrar), M & B Engineering to "Link Intime India Private 12th Floor" (an
  *address*), Urban Company to SAIF Partners (a shareholder). Anchored to require the
  issuer's own name immediately before "formerly", it is reliable, and it contributed one
  new verified alias: Sri Lotus Developers & Realty, formerly AKP Holdings, read off its own
  cover.

**Decision.** `data/company_aliases.csv` holds only aliases with document or user evidence —
23 of them. Every entry records what the evidence is and how it was obtained.
`fetch_rhp.py` resolves against the current name **first**, then aliases, so a company that
already resolved resolves identically.

**ISIN, not name, is the key that should have been used.** It is the only identifier immune
to renaming. `symbols.py` now tries ISIN first everywhere.

One entry is `our_data_error`, not `rename`: the company is and always was Udayshivakumar
**Infra**, so this is our master carrying a wrong name. An `our_data_error` should be fixed
at source; a `rename` must be kept forever. **The master still needs that fix.**

### Verifier: one narrow widening, stated exactly

The two outstanding `not_a_prospectus` cases are settled, because the PDFs were in hand:

* **Manoj Vaibhav Gems** — 416 pages, but pages 1–2 are **scanned images with zero
  extractable text**, page 3 is blank and page 4 is the table of contents, so the marker
  first appears on page 5. A fixed 4-page window rejected a genuine RHP because its cover
  was scanned. The window is now the first 4 pages **that contain text**, searched within
  the first 12. What the test needs is four pages of readable front matter; counting image
  pages against that budget measures the scanner, not the document.
* **Samhi Hotels** — **one page, zero text.** Genuinely not a prospectus. The verifier was
  right, and still rejects it after the widening. The document needs re-sourcing.

The company-name test and the ≥100-page test are untouched. Patel Retail's 1-page addendum
and SEBI's own "Corigendum to RHP" for Ideaforge also still fail.

### Not a decision, but it must be recorded: an existing rule-3 violation

`fetch_nifty_tri.py` sends a **spoofed Chrome User-Agent** to niftyindices.com. That
predates the current rules and contradicts project rule 3 ("never send a browser
User-Agent"). It is how `data/NIFTY50_TRI.csv` was obtained and is why that host appears
reachable. With our honest User-Agent, `www.niftyindices.com` **read-times-out on every
path including `/robots.txt`** — retried at 40 s and twice at 75 s, on both the apex and
`www` hosts — so its permission cannot be established at all. `market_context.py` does not
copy the spoof: it logs NULL with `permission_unverifiable`. The existing TRI file on disk
is kept and used; no new spoofed request is made. **Whether to keep or remove that
User-Agent is the user's call.**

## 2026-10-05 — H17: thresholds derived on subscription, superseding H16

**H16 was right that L2's promise was not being met, and wrong about the direction of the
fix.** It recommended raising the probability cut-off and halving the bids. The data says
the opposite: fire **more than twice as often**. H16 is superseded and should not be
implemented.

Derived by `derive_subscription_thresholds.py`. **No model, no standardiser, no isotonic
calibrator** — a monotone threshold on observed Total subscription, scored against the
realised listing gain, on the same 620 mainboard IPOs and the same exclusions the model
uses (2010-01-04 to 2026-05-08).

### 1a / 1b — in-sample against out-of-sample

| Target | Method | Threshold | Fires | Hits | Delivered | Wilson 95% LB |
|---|---|---|---|---|---|---|
| **L1** (gain > 0%, promise 90%) | in-sample | 16.86x | 284 | 256 | **90.1%** | 86.1% |
| | walk-forward | per year | 300 | 259 | **86.3%** | 82.0% |
| **L2** (gain > 10%, promise 80%) | in-sample | 26.66x | 248 | 200 | **80.6%** | 75.3% |
| | walk-forward | per year | 244 | 185 | **75.8%** | 70.1% |

**The flattery is +3.8pp on L1 and +4.8pp on L2.** In-sample, the rule picks the point that
looks best on the rows it is looking at, so its hit rate is an upper bound. The
walk-forward figure — threshold derived on prior years only, then measured on the next year,
fires and hits **pooled** across years rather than averaging per-year rates — is the
expectation.

**Trust the walk-forward number.** It is the only one that answers "what will this deliver
on an IPO I have not seen", which is the only question a bid decision asks.

**1b is refuted, not confirmed.** L1 does **not** hold at 90%: at its own naively derived
threshold it delivers **86.3%**, the same disease as L2 and only 1pp milder. It looked safe
in H16 because H16 measured the *model's probability cut*, which happens to sit at a much
higher subscription level — a different quantity, not a healthier one.

### The per-year table is where the mechanism shows

L2's naively derived threshold **drifts downward**, 31.11x (2015) to 17.20x (2025), dragged
by the hot 2021–24 market. Then it breaks:

| Year | Derived on prior years | IPOs | Fires | Hits | Delivered |
|---|---|---|---|---|---|
| 2021 | 19.29x | 63 | 37 | 30 | 81% |
| 2023 | 18.03x | 58 | 36 | 29 | 81% |
| 2024 | 17.41x | 80 | 51 | 41 | 80% |
| **2025** | **17.20x** | **102** | **60** | **36** | **60%** |
| 2026 | 26.51x | 20 | 3 | 1 | 33% |

2025 is the largest year in the dataset and accounts for most of the shortfall on its own.
This is the same pathology H12 identified in the 2-year half-life: recent hot years dominate
and mislead. A threshold that re-derives itself downward every year is not learning, it is
chasing.

### Calibrating the gap away

If the walk-forward rate falls short, the fix is to derive at a **stricter internal target**
so realised out-of-sample delivery lands on the promise. The internal target is a knob; the
promise is what the method delivers on unseen data.

| Target | Internal target | Pooled walk-forward delivery | Fires |
|---|---|---|---|
| L1 | **95%** | **90.2%** | 214 |
| L2 | **87%** | **80.8%** | 156 |

### 1c — the answer, in the units the email prints

> **L1 fires above Total ≥ 28.39x. L2 fires above Total ≥ 54.02x.**

Derived on all data at the calibrated internal targets above. These are subscription levels
the user can read straight off a broker screen — no probability is involved in the decision
any more.

### H16 reversed: the shipped model was grossly over-conservative

On the same 620 IPOs:

| Target | Rule | Total ≥ | Fires | Delivered | Wilson LB | Share of IPOs |
|---|---|---|---|---|---|---|
| L1 | production model (probability cut) | 64.86x | 135 | 99.3% | 95.9% | 21.8% |
| L1 | **H17, derived on subscription** | **28.39x** | **242** | 95.0% | 91.5% | **39.0%** |
| L2 | production model (probability cut) | 98.53x | 74 | 98.6% | 92.7% | 11.9% |
| L2 | **H17, derived on subscription** | **54.02x** | **166** | 88.0% | 82.1% | **26.8%** |

The shipped L2 threshold fired on **11.9%** of IPOs and delivered **98.6%** against an
**80%** promise. It was not under-delivering — it was leaving most of the opportunity on the
table, and H16 would have made that worse.

**Both failures are the same root cause: routing the decision through a calibrated
probability.** H16's shortfall came from `retrain_l.evaluate()`, which refits the
*calibrator* on each window's training half; the refit calibrator places `p_cal >= 0.80` far
lower on the subscription scale, which is why that window fired on 49% of its test rows
rather than 11.9%. So H16 measured the refit procedure and the 98.53x figure describes the
shipped bundle — two different thresholds, one under-delivering and one over-conservative.
Deriving directly on subscription removes the intermediary and both problems with it.

### 1d — what the honesty costs in opportunities

It costs nothing. It buys them.

* **L1**: 242 fires over 17 years, **~14.2 a year**, up from 135 (~7.9 a year).
* **L2**: 166 fires over 17 years, **~9.8 a year**, up from 74 (~4.4 a year).

L2 at 54.02x, by year: 2021 91% (23 fires), 2023 95% (21), 2024 92% (37), **2025 76% (41)**,
2022 and 2026 100% on 3 and 1. 2025 still misses 80%, but at 76% rather than the 60% the
naive threshold delivered.

L1 at 28.39x clears 90% in every year except 2015 (80% on 5 fires) and 2026 (33% on 3 fires,
a part-year to May).

### 1e / 1f — status

**H17 supersedes H16 and awaits ratification.** Nothing in the live path has been changed to
use these thresholds yet: the email still scores through `score_l.py` and the production
bundle.

Until ratification, every L2 **BID** in the email carries, verbatim:

> `L2's 80% promise is under review - measured delivery is 77%. Treat L2 as indicative only.`

L1 carries no such warning, **despite 1b being refuted**, because that is what was asked for
and because L1's firing band on the shipped bundle delivers 99.3% — so a live L1 BID today
is conservative, not optimistic. The refutation matters for the *new* L1 threshold, not for
what is currently shipped.

## 2026-10-05 — H18: rule 5 relaxed, and what it unblocked

**The user's decision, recorded verbatim in intent.** The earlier instruction "fetch only
from official sites" had been implemented as "never send a browser User-Agent", which was
stricter than intended. Realistic browser headers may now be sent **to official sources** —
NSE, BSE, NSE Indices, SEBI. The purpose is unchanged: correct numbers from official
channels, and keep trying.

**Still forbidden, unchanged:** bypassing a login, CAPTCHA, paywall or click-through
agreement; ignoring an explicit `robots.txt` disallow that applies to our client; and
reaching any source whose terms prohibit scraping — `ipoindex.in`, `iporupee.com`, IPO Ji
and InvestorGain remain off-limits (B1).

### What was actually blocking us: a User-Agent filter, not a policy

Every one of these was previously recorded as refusing this host. Re-read today with
realistic headers:

| Host | Before | With headers (H18) |
|---|---|---|
| `www.nseindia.com/robots.txt` | connection reset / timeout | **HTTP 200.** `User-agent: *` → `Allow: /`, only `/market-data-test` disallowed |
| `www.bseindia.com/robots.txt` | **403** | HTTP 200 — serves the SPA homepage, i.e. no robots.txt exists, so nothing is disallowed |
| `www.niftyindices.com/robots.txt` | read timeout on every path | **HTTP 200.** `Allow: /` with four specific disallows, **none** of them the historical-data endpoint |

So NSE positively permits us and always did; the WAF was filtering on the User-Agent
string. BSE publishes no robots.txt at all. niftyindices permits the path we need.

### Endpoints, probed rather than assumed

| Source | Endpoint | Result |
|---|---|---|
| BSE live | `api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w` | **HTTP 200**, live JSON (SYNGENE 357.50) |
| **BSE bhavcopy, old format** | `/download/BhavCopy/Equity/EQ<DDMMYY>_CSV.ZIP` | **HTTP 200.** 3,161 scrips for 11-Aug-2015 |
| **BSE bhavcopy, new format** | `/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_<YYYYMMDD>_F_0000.CSV` | **HTTP 200**, 863 KB, and it carries **ISIN** |
| **NSE bhavcopy** | `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_<YYYYMMDD>_F_0000.csv.zip` | **HTTP 200** |
| NSE JSON APIs | `www.nseindia.com/api/quote-equity`, `/api/historical/cm/equity` | **403 / 503** — still WAF-blocked even with headers |

**Bhavcopy is the right instrument, and better than anything previously considered.** It is
the exchanges' own end-of-day file, unadjusted, one file per trading date covering every
scrip — so a listing date is one request, not one request per company. And **NSE bhavcopy
plus BSE bhavcopy are two genuinely independent official sources, so rule 2 applies
properly.** No `single_source_unverified` compromise is needed for the label after all.

### The as-reported gate (2c), run before collecting anything

Syngene International: offer **₹250**, 1:1 bonus in 2017, as-reported list price **₹295**.
yfinance returns **₹147.50** — exactly 295/2 — which is why it is banned. The test: ~295
means as-reported and usable; ~147.50 means it carries the same adjustment disease and must
be rejected outright.

**Chittorgarh** `/ipo/x/481/`, "Listing Day Trading Information":

| Price Details | BSE | NSE |
|---|---|---|
| Final Issue Price | ₹250.00 | ₹250.00 |
| **Open** | **₹295.00** | **₹295.00** |
| Low | ₹295.00 | ₹295.00 |
| High | ₹318.20 | ₹318.50 |
| Last Trade | ₹310.40 | ₹310.55 |

**PASSES.** ₹295.00, not ₹147.50. As-reported, unadjusted.

**BSE bhavcopy** for 11-Aug-2015, SC_CODE 539268:

```
OPEN 295.0  HIGH 318.2  LOW 295.0  CLOSE 310.4  LAST 310.4  PREVCLOSE 0.0
```

**Also passes, and agrees with Chittorgarh to the paisa.** The implied listing gain is
**18.0%**, which is exactly the figure the master already carries — three independent
confirmations of the same number.

One incidental find worth keeping: **`PREVCLOSE = 0.0` marks a scrip's first trading day**
in BSE bhavcopy. That is a source-side listing-day marker, which is more reliable than
matching our own calendar.

### Consequences

* Chittorgarh's listing-day table is **cleared for use**, but is now the *corroborator*
  rather than the primary, because the two exchanges' bhavcopies are independent of each
  other and of it.
* `NSE_DOWNLOADS_ALLOWED` no longer needs to gate bhavcopy: there is no click-through on
  these files. The flag's original purpose — never accept a disclaimer or click-through —
  is untouched and still binding.
* Priority 4c (index closes) is unblocked: `market_context.py` can reach niftyindices.
* `fetch_nifty_tri.py`'s browser User-Agent is, under H18, no longer a violation. The
  existing `NIFTY50_TRI.csv` stays and is **not** to be re-derived.

## 2026-10-06 — H17 RATIFIED and SHIPPED. H16 is void.

The user ratified H17 on 2026-10-06. Model L's decision is now a plain subscription
threshold. **There is no calibrated probability anywhere in the decision path.**

> **L1 fires above Total ≥ 28.39x** (90% promise)
> **L2 fires above Total ≥ 54.02x** (80% promise)

### The standing definition, in the user's words

> **the threshold at which 90% (L1) / 80% (L2) of IPOs the model has never seen met the
> target. Walk-forward, never in-sample.**

This is now the definition of a threshold in this project. The in-sample figure flatters by
**3.8pp on L1 and 4.8pp on L2**, and that gap produced *both* earlier failures:

* **H16's apparent shortfall** — `retrain_l.evaluate()` refits the calibrator on each
  window, which places `p_cal >= 0.80` far lower on the subscription scale, so that window
  fired on 49% of its test rows and under-delivered.
* **The shipped bundle's over-conservatism** — its fixed probability cut sat at Total
  ≥ 98.53x, firing on 11.9% of IPOs and delivering 98.6% against an 80% promise.

One cause, two opposite symptoms. Removing the intermediary removes both.

### What shipped (1b)

| | Before | After |
|---|---|---|
| Decision input | calibrated probability `p_cal` | **Total subscription** |
| L1 fires at | Total ≥ 64.86x (implied) | **Total ≥ 28.39x** (stated) |
| L2 fires at | Total ≥ 98.53x (implied) | **Total ≥ 54.02x** (stated) |
| Expected L2 bids | ~4.4 a year | **~9.8 a year** |
| Artefact of record | `model_l_v1.0_*_coefficients.json` | `models/model_l_v1.1_thresholds.json` |

* `models/model_l_v1.1_thresholds.json` is emitted by
  `derive_subscription_thresholds.py` and carries its own provenance: the ratification, the
  walk-forward definition, what it supersedes, the delivered out-of-sample rate, the fire
  count and the in-sample flattery. **`score_l.py` reads it; no threshold is hardcoded
  anywhere**, for the same reason no report hardcodes a promise.
* `score_one()` is one comparison: `tot >= cut`. Asserted in the self-test that it contains
  no `p_cal`, `p_raw`, `isotonic` or `_interp`, and that where H17 and the old probability
  rule disagree **H17 wins**.
* The probability is still *computed*, under `diagnostics`, labelled
  `NOT in the decision path (H17)`, because a diverging probability is an early warning
  that the threshold needs re-deriving. Its coefficient path is pinned to **v1.0** on
  purpose: the drift series is only comparable over time if it keeps coming from the same
  fit, so bumping it with `MODEL_ID` would silently change what is being measured.
* **The L2 under-review caveat is deleted.** It warned that L2's 80% promise rested on a
  cut-off whose measured delivery was 77%; H17 replaced that cut-off with a threshold
  derived to deliver 80.8% out of sample. The caveat now described a rule that no longer
  exists, and a stale warning is worse than none — it teaches the reader to discount a
  verdict that is sound.
* The email prints both firing levels on every send, including quiet days, and each verdict
  line carries its own level. That is the practical gain over a probability: **the reader
  can check the number against their own broker screen.**

### The drift guard (1c)

The monthly retrain re-derives both thresholds by the same walk-forward method as data
grows. **A re-derivation that moves a threshold by more than 25% in either direction is not
applied** — it is flagged in the retrain report for the user's review.

The reason is on the record. The naively derived L2 threshold drifted **31.11x (2015) to
17.20x (2025)**, chasing the hot 2021–24 market, and 2025 — the largest year in the dataset,
102 IPOs — then delivered **60% on 60 fires**. A threshold that tracks recent conditions
that closely is not learning, it is chasing, and the size of the move is the symptom that
tells the two apart.

`drift_check()` in `derive_subscription_thresholds.py`; `DRIFT_LIMIT = 0.25`.

---

## 2026-10-08 — H19 to H21

### A numbering collision, recorded before anything is added to it

`H17` and `H18` were each used twice in this file, for unrelated decisions:

| ID | First use (2026-10-03) | Second use (2026-10-05/06) |
|---|---|---|
| H17 | a failed run no longer locks out its own retry | thresholds derived on subscription, superseding H16 |
| H18 | name similarity cannot identify a company rename | rule 5 relaxed: realistic headers to official sources |

Both second uses are the ones referred to everywhere else in the project — in code
comments, report prose and the live email footer — so **they keep the numbers**, and the
2026-10-03 pair is cited by date rather than by ID from here on. Nothing is renumbered,
because renumbering would invalidate a ratified rule's identifier in a shipped artefact
(`models/model_l_v1.1_thresholds.json` records `ratified: "H17"`). Today's decisions start
at **H19** so the collision does not grow.

---

### H19 — the under-delivery tripwire: two windows, not one

The 12-month email backtest under-delivers both promises: **L1 85.7% against 90%, L2 72.2%
against 80%** (`reports/EMAIL_BACKTEST_12M.md`). The user's decision is to **change
nothing now** and to fix the trigger in advance:

> **If the next monthly retrain also shows the trailing 12 months under-delivering on the
> same target, re-derive that threshold. Two consecutive under-delivering windows is the
> trigger; one is not.**

Deciding this before seeing the next window is the whole point. The alternative — looking
at one weak window and adjusting — is exactly the mechanism that produced the two failures
already on the record:

* the naive L2 threshold drifted **31.11x (2015) → 17.20x (2025)** by chasing the hot
  2021–24 market, and 2025 then delivered **60% on 60 fires**;
* H16 read a single refitted window as a live shortfall and had the direction backwards.

A threshold that moves on one window is not learning, it is tracking noise. And the
under-delivery is not a contradiction of H17: H17's promise is the **pooled walk-forward**
rate across every test year, and its own per-year table already showed 2025 at 76%. One
weak year inside a pooled promise is the expected shape of the thing, not a breach of it.

**What makes the second window independent enough to act on:** it adds roughly a month of
genuinely unseen IPOs and re-derives on data the first window did not include. Two
consecutive windows failing the same target is evidence about the rule; one is evidence
about the year.

The 25% drift guard still sits on top. A re-derivation triggered by this tripwire that
*also* moves a threshold by more than 25% is still held for review rather than applied —
the tripwire licenses re-deriving, not applying unexamined.

Implemented in `retrain_l.py`; the consecutive count is persisted so the retrain can tell
a first failure from a second.

---

### H20 — the 15:00 email has a send window, and is never caught up

**The defect.** Not one 15:00 email had ever been sent at 15:00. The `ran_at` column of
`data/live_run_markers.csv` records every 15:00 leg to date:

| date | stamped at | past the 16:00 cutoff? |
|---|---|---|
| 2026-10-02 | 21:49 | yes |
| 2026-10-03 | 16:53 | yes |
| 2026-10-05 | 00:39 | — too early, see below |
| 2026-10-06 | 00:06 | — too early |
| 2026-10-07 | 22:11 | yes |

Nothing in the leg checked the clock. GitHub queues a delayed job, or a manual run lands at
any hour, and the email went out regardless.

**The rule.** `send_window()` in `send_daily_email.py` refuses to send outside
**14:00–16:00 IST**, on both sides and for two different reasons:

* **At or after 16:00** — the broker cutoff (E1). A bid signal then is not late
  information, it is *wrong* information: it invites a bid that can no longer be placed.
* **Before 14:00** — the model is `L_final_3pm` (H1), fitted on the final-day
  late-afternoon subscription figure. A morning figure is a **different distribution**, not
  an early look at the same one, so scoring it would be a leakage-discipline breach in the
  opposite direction from the usual one.

The report is still written in both cases, so the day keeps a record of what the verdict
would have been. Then the run **exits non-zero**: a refused send must make the run red,
because silence that looks like success is the failure mode this whole priority exists to
remove.

**There is no flag that re-sends a missed email**, and the self-test asserts there is none.
`--dry-run` composes and prints; nothing sends.

---

### H21 — a guard that lies is worse than no guard

`first_day_marker` is **removed entirely** — from `listing_prices.py`, from `OUT_COLS` and
from `data/listing_prices.csv`.

It claimed to identify a scrip's first trading day from the source side rather than from
our own calendar, on the premise that `PREVCLOSE == 0`. Measured against the finished
backfill it read **False on 621 of 623 rows**, including rows that are demonstrably
correct, because both exchanges populate the previous-close field on a listing day — BSE
with the issue price, NSE with the discovery price. The premise was simply wrong.

The user's reasoning, which is now the standing rule for guards in this project:

> A guard that lies is worse than no guard.

A check that is False on 99.7% of correct rows does not fail safe. It teaches the reader to
ignore it, and an ignored check is indistinguishable from an absent one right up to the
moment it would have mattered. Listing dates come from the master and are asserted by
`capture_listing_day()` instead.

The `prev` column existed only to feed it, so it is gone from the normalised bhavcopy
schema too. `listing_prices.py` self-test section [9] asserts the guard stays removed, with
the needle assembled at runtime — three earlier self-tests in this project passed only
because they found their own assertion string in the file they were checking.

The same sweep found a worse instance of the same class: the assertion that the L2
under-review caveat had been deleted ended in `... or True`, which I had added to stop it
matching its own text. **It could not fail.** Fixed the same way.

---

## 2026-10-08 (later) — H22 and H23

### H22 — source order for subscription: NSE primary, Chittorgarh fallback (PROVISIONAL)

> **NSE `api/ipo-active-category` is primary (the origin); Chittorgarh is fallback;
> subscription is single-origin, rule 2 is not achievable — the flag stays. Never use
> `ipo-detail`.**

**Why NSE is the origin and not a second opinion.** `ipo-active-category` reproduced the
master's recorded `Total` to two decimal places on **14 of 14** mainboard IPOs. Fourteen
exact matches is not what two independent measurements look like; it is what a figure and
a copy of that figure look like. NSE publishes it and Chittorgarh republishes it. Reading
the original removes a transcription step and a third party's uptime from the live path —
and that is the entire gain. It buys **no** independence.

So **every subscription row keeps `single_source_unverified`**. Rule 2 needs two
measurements and there is still only one, for the same reason `CLAUDE.md` says Chittorgarh
and IPOMatrix are not two sources. BSE, probed the same day, has no working subscription
endpoint at all — three candidate paths returned the same 1,814-byte ASP.NET error page —
so the independence problem is not solved by adding NSE and is not solvable today.

**`ipo-detail` is forbidden, and this is the trap worth naming.** It is the more obvious
endpoint, it has the richer-looking payload, and its `bidDetails` block is an
**intermediate cut, not the close**: measured against the same 14 IPOs it runs **9% to 57%
lower** than the final figure. Building on it would understate subscription by tens of
percent and push every verdict toward `no`. `nse_subscription.py`'s self-test asserts no
code path constructs an `ipo-detail` URL.

**Why this ships as provisional, and what makes it safe anyway.** It is **not yet known**
whether `ipo-active-category` updates during the bidding day or only publishes once at
19:00. Every closed issue shows a single 19:00 `updateTime`, which is consistent with
either and proves neither. Task 9's HDFIRE test (13–15 Oct) settles it.

Promoting NSE unconditionally before that would risk scoring the 15:00 decision on a zero
or on yesterday's figure. So a payload is used **only if it passes a freshness gate**:

| check | why |
|---|---|
| `Total` present and **> 0** | a forthcoming issue answers `0.00`; that is "nothing published", not "no demand" |
| `updateTime` parses **and is the trading date** | an undated or stale figure could be any day's. `"Updated as on null"` must never be read as *now* |
| the symbol in the payload **is the symbol asked for** | the Priority 2 probe silently returned a *different company's* subscription for the guessed symbol `PARAMOUNT` |

A gate failure is a normal outcome, not an error: it means NSE has published nothing usable
yet, and the Chittorgarh figure stands. **Which source was used is recorded on every row**
(`sub["source"]`, `sub["nse_note"]`), because a silent switch between two sources is how a
divergence stops being detectable.

Symbols come from NSE's own `api/all-upcoming-issues`, never from guessing at a name:
`market_view()` rows carry a company name and a Chittorgarh id and no symbol at all. Two
candidate matches return nothing rather than the first one.

---

### H23 — the live verdict uses the 15:00 figure, and that is accepted

> **The live verdict uses the 15:00 IST subscription figure. It understates final
> subscription; this makes verdicts conservative and is accepted. No threshold
> adjustment.**

**Task 10 — what the thresholds were actually derived on: the FINAL figure.** Traced, with
lines, rather than assumed:

| step | file:line | what it does |
|---|---|---|
| 1 | [derive_subscription_thresholds.py:86](derive_subscription_thresholds.py:86) | `"total": np.expm1(df["log1p_total"])` — the threshold grid is built from this |
| 2 | [models/model_l.py:97](models/model_l.py:97) | `out["log1p_total"] = np.log1p(_num(df, "Total", "total"))` |
| 3 | [models/model_l.py:62](models/model_l.py:62) | `load_mainboard()` → `dataio.load_master_with_symbols()` |
| 4 | the master's `Total` column | the subscription recorded **after the issue closed** |

And this is now **confirmed against the exchange rather than inferred**: the master's
`Total` for SRTL is `43.66`, and NSE's `ipo-active-category` returns `43.66` with
`updateTime` `25-Feb-2026 19:00:00` — the published final update. The same held on all 14
IPOs checked. **So `28.39x` and `54.02x` are thresholds on FINAL subscription, applied live
to the ~15:00 reading.**

**The direction of the error, and why it is accepted.** Institutional bids concentrate in
the closing hours, so the 15:00 figure is **lower** than the figure the thresholds were
derived on. A threshold crossed at 15:00 is therefore crossed by more at the close. The
error is one-sided: the email **misses qualifying IPOs rather than recommending bad ones**.
A near-threshold `NO BID` is uncertain, not negative.

**No adjustment, and the reason is not laziness.** Shifting the thresholds down to
compensate would require knowing the size of the 15:00-to-final gap, and that quantity has
never been measured — no permitted source publishes day-wise subscription history, which is
what cancelled Stage 4B. Guessing a correction would replace a known, one-sided,
conservative bias with an unknown two-sided one.

It is now being measured instead. Task 6 writes `data/final_subscription.csv` on every
day-end capture: the 15:00 figure, the final figure, `growth_x`, and
`would_L1_fire_on_final` / `would_L2_fire_on_final` under the same ratified thresholds. The
3pm understatement stops being a caveat and becomes a counted quantity. When there is
enough of it, this decision can be revisited on evidence.

The email states the caveat on every closing issue: *"Figures as of HH:MM IST — final
subscription is usually higher (H23)."*

---

## H24 — a trailing-12-month window only counts toward the tripwire if half its firing rows are new (2026-10-10)

**Decided before the 1 November retrain, deliberately, while the count stands at 1 of 2
on both targets and nobody knows what November will say.**

### The problem

H19 says two consecutive under-delivering trailing-12-month windows re-derive the
threshold. But two consecutive such windows **share eleven of their twelve months**. If
October under-delivers, November is reading almost the same rows. The second reading is
near-automatic: one bad year arms the tripwire in October and fires it in November without
a single new outcome having to disappoint. That is not two pieces of evidence, it is one
piece of evidence counted twice — the same error as deriving a threshold from a single
window, wearing a different hat.

Measured on the current data, rolling the window forward by one month leaves **0 of 45 L1
firing rows new and 0 of 34 L2 firing rows new**. The overlap is not a theoretical worry.

### The rule

On top of H19, unchanged in every other respect:

> A window counts toward the tripwire only if **at least half of its resolved firing rows
> are new since the last counted window.**

* "Resolved firing rows" is exactly the set the delivered hit rate was computed on: the
  IPOs the email would have said BID to, whose listing gain is known. Their identity is
  stored on the observation (`fire_keys`), so the overlap is **measured, not assumed**.
* Overlap is measured against the **last counted** window, not the previous window. This
  matters: it means the count advances the first time half the firing rows have turned
  over, rather than never. With a 12-month window and a monthly retrain that is roughly
  six retrains, which is the pace at which the evidence actually renews.
* The gate applies to **incrementing** the count, never to resetting it. A window that
  delivers disarms the tripwire whether or not its rows are new. H24 exists to stop a
  near-automatic second strike, not to make the tripwire harder to switch off — gating the
  reset too would make the rule *more* trigger-happy than H19, in the one direction H19
  was careful about.
* A window whose firing rows were **not recorded** is recorded and not counted, with the
  reason. The exception is the first counted window, which has nothing to overlap with.
  H24 cannot be checked against rows that were never stored, and counting an unverifiable
  window is the thing H24 exists to stop.
* Unchanged from H19: the trigger is still two; a thin window (fewer than 20 bids) is
  still recorded and not counted; firing still authorises **re-deriving** the threshold and
  **not** applying the result, with the 25% drift guard still on top.

### What this does to the current state

Nothing. The October 2026 window is the first counted window on both targets, so it has no
predecessor to overlap with and still counts. `L1` and `L2` both stand at **1 of 2**, and
`data/tripwire_state.json` now also carries the 49 L1 and 36 L2 firing-row identities that
the next window will be measured against.

### The consequence, stated plainly

H24 makes the tripwire slower by design. A second strike now needs half the firing rows to
have turned over, which on a 12-month window is of the order of six monthly retrains
rather than one. That is the intended trade: the tripwire fires on renewed evidence or not
at all. If a genuine regime change arrives, it will show up as a delivered rate that keeps
falling across windows that *do* count — and in the meantime every window, counted or not,
is still recorded with its numbers, so nothing is hidden while the count waits.

Implemented in `tripwire.py` (`_recount`, `MIN_NEW_SHARE = 0.5`) and
`backtest_email.backtest()` (which now returns `fire_keys`). 33 self-test assertions.

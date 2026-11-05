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

> **Renumbered `H27` on 2026-10-10.** `H17` now means only the subscription
> thresholds (2026-10-06). See *Numbering resolved* at the end of this file.

`mark_ran()` wrote an idempotency marker even when the run captured zero rows, and
`already_ran()` only checked that the key existed. A failure therefore recorded itself as a
success and blocked every retry for that slot. Three slots were stuck:
`2026-10-01|1730`, `2026-10-02|1730`, `2026-10-02|1500`.

**Decision.** A marker counts as "ran" only if `n_snapshots > 0`. Zero-row markers are kept
as the audit trail of failed attempts but do not lock. The three stuck slots were cleared by
the logic change rather than by deleting rows. Idempotency suppresses duplicate *work*,
never duplicate *attempts at work that has not happened*.

### H18 → RENUMBERED H28 — name similarity cannot identify a company rename

> **Renumbered `H28` on 2026-10-10.** `H18` now means only the rule 5 relaxation
> (2026-10-05). See *Numbering resolved* at the end of this file.

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

---

## Numbering resolved: one rule, one number (2026-10-10)

The 2026-10-08 entry above *recorded* the `H17`/`H18` collision and left the superseded
pair "cited by date". That is not an identifier — you cannot grep a date, and a reader who
finds `### H17` twice in this file has no way to tell which one a comment meant. So the
superseded pair is given numbers of its own, at the end, where nothing points yet:

| Was | Meaning | Now | Why this direction |
|---|---|---|---|
| `H17` (2026-10-03) | a failed run no longer locks out its own retry | **`H27`** | the 2026-10-06 H17 is recorded inside a shipped artefact — `models/model_l_v1.1_thresholds.json` carries `ratified: "H17"` — and renumbering that would invalidate a ratified identifier in a file already written |
| `H18` (2026-10-03) | name similarity cannot identify a company rename | **`H28`** | the 2026-10-05 H18 is cited in code comments, report prose and the live email footer; it is the one everything means |

So from today: **`H17` means only the subscription thresholds** (2026-10-06, superseding
H16) and **`H18` means only the rule 5 relaxation** (2026-10-05). `H27` and `H28` are the
2026-10-03 pair. The original headings below are left in place with a pointer rather than
rewritten, because this file is the decision log and editing an entry's identity after the
fact is the thing it exists to prevent.

### The `rule 10` clash

`rule 10` was being cited for two different rules. PLAN.md section 4 is unambiguous and
nothing there changes:

* **rule 10** — the estimator. Use the validated numpy logistic regression; do not add
  scikit-learn.
* **rule 11** — `data/predictions_log.csv` is append-only. Never edit or delete past rows.

Four live-path files cite `rule 10` where they mean `rule 11`. They are **not edited
today**: the live-path freeze runs to 15 October and a comment is not worth a diff in
`send_daily_email.py` the week HDFIRE goes live. They are queued in PROGRESS.md under
"Queued for after 15 Oct".

---

## 2026-10-10 — H25 and H26 (ratified by the user)

### H25 — Model H proceeds without the 37 missing RHPs, and "missing" is its own band

37 of the prospectuses Model H's RHP feature blocks were specified against are not on
disk, and several are not reachable from SEBI or BSE SME at all. Model H waits for them no
longer.

**Missing is treated as its own band**, not as zero, not as the mean, and not as a dropped
row. That distinction is the whole decision:

* **imputing** a value invents evidence, which rule 1 forbids outright;
* **dropping** the row throws away a real IPO with a real outcome, and does it
  non-randomly — the companies whose documents are hardest to find are not a random
  sample, so dropping them biases every coefficient toward the well-documented;
* **a band** says what is true. "We do not know this company's related-party percentage"
  is a fact about the company's documentation, it is measurable, and the model is allowed
  to find that it predicts something. If it does, that is a finding about disclosure, not
  a defect.

Revisited **only** if Task 6a recovers documents. A recovered document moves its rows out
of the missing band; nothing else does.

### H26 — single-source relaxation for sanctioned third-party access

Rule 2 requires two independent sources. Rule 3 keeps a single-source value but flags it
`single_source_unverified`. Neither anticipated a field that **no official source carries at
all** — where the choice is not "one source or two" but "one source or nothing".

**Where no official source carries a field, a third-party source with sanctioned access —
its own API or token, used within its terms — may be the sole source.** Such values are
flagged **`single_source_third_party`**, a new flag kept distinct from
`single_source_unverified`: the existing flag means "one source, and we could not check
it"; the new one means "one source, by sanctioned access, because there is no other". A
reader must be able to tell those apart, because they justify different amounts of trust.

**Official sources always take precedence where they exist.** This is a fallback, never a
shortcut — if NSE publishes the field, NSE is the source, and a third party that disagrees
is a reconciliation failure, not an alternative.

**Provenance is mandatory and non-negotiable.** Every such value records:

| Field | Why |
|---|---|
| source | which provider |
| endpoint or tool | which call, by name |
| request parameters | so the call can be repeated exactly |
| retrieval timestamp (IST) | rule 13; and because a third party may restate |
| **SHA-256 of the raw response** | the response is the evidence. Without its hash there is nothing to re-verify against, and a restated value later is indistinguishable from a transcription error now |

Any value missing any of the five is not admissible. This is H7's standard applied to a
new source class, not a weaker one.

**H18's prohibitions are unchanged and are not relaxed by this.** Still forbidden: bypassing
a login, CAPTCHA, paywall or click-through; ignoring a robots.txt disallow that applies to
our client; and any source whose terms prohibit scraping or reuse. The B1 blacklist stands.
"Sanctioned access" means the provider issued us the means of access and permits the use —
a token is not a licence to ignore the terms it came with, and the terms are read **before**
the first call, not after.

### What H26 does not do

It does not make a third-party figure equal to an exchange figure, and it does not let one
into the Model L decision path. Model L's only input is subscription, which NSE and
Chittorgarh both carry, so H26 has nothing to add there. Its scope is Model H's post-listing
fields — corporate actions, dividends, identifier history — where the official record is
incomplete and the alternative to a flagged third-party value is a permanently empty column.

---

## 2026-10-12 — H29 to H31, and an addendum to H25 (all ratified by the user)

### H29 — Model H's stop rule, fixed before the measurement

Adopted exactly as proposed in PROGRESS.md on 2026-10-10 and moved here on ratification.

> Model H's top band earns the right to issue a hold/exit instruction only if, in a
> **walk-forward backtest on IPOs the model has never seen, pooled across test years**, the
> **top-20% score band ("Hold")**:
>
> 1. fires on **at least 50 picks**, and
> 2. hits **at least 54%** against the Nifty 50 TRI over year one, and
> 3. has a **Wilson 95% lower bound above the base rate**.
>
> All three, or Model H is **display-only**: its score appears in the email and never a
> hold/exit instruction.

**Why 50 and not Model L's 20.** Model L fires on 20 because its edge is large — pooled
walk-forward AUC 0.8084. Model H's baseline is **0.525**, and 0.5 is a coin. At 20 picks the
band would have to hit **65%**, a +24.7pp gap, before the lower bound cleared a 40.3% base
rate; an AUC-0.525 model producing 24.7pp is not a plausible outcome, it is what 20 lucky
picks look like. 50 is the first count whose required rate (54%) that model could actually
produce.

**The cost, stated rather than buried.** At 50 picks a band whose true rate is 55% is
certified only **61%** of the time. The rule will fail a real-but-modest edge two times in
five. That is the price of not certifying noise. If Model H is still being evaluated when
100 picks are available, 100 is the number to move to — detection rises to 87%.

**Pooled, never per-year.** The yearly base rate runs from **14.3% (2010) to 71.4% (2020)**.
A band judged on one test year could clear or fail any threshold for reasons unconnected to
the model, which is the mistake H24 exists to stop in the tripwire and H2 avoids by pooling
AUC rather than averaging per-year AUCs.

**Top-20% is the band, and it was chosen before fitting.** Over 2021–2025 (286 rows) the
bands hold 85 picks (top 30%), **57 (top 20%)** and 28 (top 10%). Top-10% cannot satisfy
condition 1 at all, so it is not an available choice later — fixing the band now is what
stops the cut being picked after seeing which one passes.

### H30 — Model H's design

| Element | Decision |
|---|---|
| Target | excess return vs **Nifty 50 TRI**, listing-day close to +12 months, **corrected method**: raw bhavcopy prices × official split/bonus factors + dividends in the window |
| Primary decision point | **listing day** |
| Quarterly re-scoring | **phase 2**, designed but not built (see PROGRESS.md) |
| Method | **credit scorecard** — WoE binning, IV selection, logistic |
| Estimator | **numpy only** (rule 10 — never scikit-learn) |
| Recency weighting | **none.** Market conditions enter as explicit market-heat variables instead |
| Validation | **walk-forward expanding window by calendar year.** Never in-sample |
| Output | score band → **% of allotment to hold**, bands and percentages derived from the backtest |
| Reporting | **both pre-tax and post-tax**; the user decides |
| Benchmark | **Nifty 50 TRI only** |
| Sector | **NSE's own industry classification** |
| Data | free and permitted sources only (H18, H26) |
| Exit timing | **out of scope** — a separate tool handles it |
| Drift guard | as Model L: any coefficient moving **>25% or flipping sign** between refits is held for review |

Two of these are worth saying out loud because they are the opposite of the obvious choice.

**No recency weighting, deliberately.** Model L uses it (half-life chosen by pooled AUC).
Model H does not, because recency weighting and market-heat variables are two answers to the
same question and using both makes neither interpretable: a coefficient on "hot market" is
not readable if recent hot years are also weighted up. Model H's whole claim is that market
conditions are *measurable*, so they are measured.

**A scorecard rather than a better classifier.** With AUC 0.525 the limit is the signal, not
the estimator — a stronger learner would fit noise more confidently. WoE binning gives
monotone, inspectable bins and an IV number per variable, so a variable earns its place for
a reason that can be read off a table. That matters more here than a decimal of AUC.

### H31 — one pooled Model H for SME and mainboard, with a flag

Rule 6 requires separate SME and mainboard models. **This is an exception, for Model H
only:** one pooled model with an **`is_sme` flag (0/1)**, every other variable captured
identically wherever available.

**Why the exception is defensible here and not in Model L.** Rule 6 exists because SME and
mainboard Model L coefficients differ in *sign* on market hotness and band width — a
measured fact about bid-time behaviour. Model H is a different target at a different horizon,
and there is no equivalent measurement for it; what there is instead is a sample-size problem
that a split would make fatal. A pooled model with a flag can be *tested* for whether the
segments behave differently; two models fitted on too few rows each cannot.

**Model L is unchanged. SME is still never scored for bids.**

**And the flag does not earn SME advice.** SME hold advice is given only if the picks that
are SME **pass H29 on their own** — ≥50 SME picks, ≥54%, Wilson lower bound above the base
rate. Below that: display-only for SME, whatever the pooled model achieves. A pooled model
that works because of its mainboard rows must not be allowed to speak for SME.

### H25 addendum — the 37 IPOs without RHPs are a held-out test set

H25 made "missing" its own band. This makes those 37 rows do work: they are **held out** and
scored on the **non-RHP variables plus the "missing" band only**, to check that the band
behaves as the fitted model predicts it will.

That is the test H25 otherwise lacked. A band is only honest if it predicts something, and
the way to find out is to score rows that *are* in that band and compare the predicted beat
rate against the realised one. If the band's realised rate is far from its predicted rate,
"missing" is not a usable band and H25 has to be revisited — which is the condition H25
already names.

---

### H32 — a narrow freeze exception for the HDFIRE email fix (2026-10-13)

**Approved by the user on 13 Oct 2026**, inside the 12 Oct 18:00 → 15 Oct 20:00 IST
live-path freeze, and limited to Phase 1 Tasks 1.1–1.3. Nothing else in `.live-path` moves
until the freeze lifts; the four queued `rule 10` → `rule 11` comment fixes stay queued.

**Why an exception was the right call rather than waiting.** The freeze existed to protect
the first live test. The 12 Oct emails proved the thing being protected was already broken:
two identical emails said "UPCOMING: Nothing scheduled to open" while NSE's calendar
carried HD Fire Protect bidding 13–15 Oct. Freezing a working system protects it; freezing
a silent one guarantees the test produces nothing. The exception is the narrower risk.

**Files changed under this exception**

| File | Why |
|---|---|
| `chittorgarh_live.py` | the two parser defects (badge removed from the page; same-month window) |
| `ipo_calendar.py` *(new)* | NSE-primary IPO list, Chittorgarh fallback and union |
| `send_daily_email.py` | consume the new list; `DATA CHECK FAILED` subject; honest footer; one summary email per date |
| `.github/workflows/live-model-l.yml` | gate the new module in the pre-flight |
| `.live-path` | add the new module to the frozen manifest |

**What was NOT changed, though it was tempting.** `nse_subscription.enrich_market_view`
still covers mainboard issues **closing today** only, so an issue that is open but not
closing shows a Chittorgarh figure even though NSE is the source of record under H22.
Widening H22's scope is a behaviour change nobody asked for, three days into a live test,
on a path that had just been found broken. It is queued, not done.

**The standing rule this produced.** A required element of a third-party page must never be
mandatory in a parser. Chittorgarh dropped a status badge and the row regex went from
matching every IPO to matching none, reporting "0 dated rows" with no error, on the one
page the entire live path depended on. Where a source can go silent, there are two sources
or there is an alarm. There are now both.

---

### H33 — Model H excludes SME for now; H31 stays recorded but inactive (2026-10-13)

**Ratified by the user on 13 Oct 2026.** Model H is a **mainboard** model. SME issues are
out of its scope until an SME dataset exists.

**H31 is not withdrawn — it is dormant.** H31 permits one pooled Model H across SME and
mainboard with an `is_sme` flag, as an exception to rule 6. That exception cannot be
exercised, because the master contains **0 SME rows**: 309 mainboard and 314 whose series is
unknown, and `is_sme` therefore has zero variance. A flag that is constant is not a
control; the pooled model H31 describes has never been fitted and cannot be.

So H31 remains the standing design for the day an SME dataset arrives, and its condition is
unchanged: **SME hold advice must pass H29 on SME picks alone before it is given.** Until
then Model H says nothing about SME issues at all — which is a stronger statement than a
model with an untested flag, and an honest one.

**What this does not change.** Model L's separate-SME treatment is untouched: SME issues
still appear in the live email, still get `SME, not scored`, and still carry the
shadow-mode caveat (H3/E2). The question Phase 2 Task 2.2 asks is not "which Model H
variables do SME rows have" but "can SME rows be obtained at all".

---

### H34 — Model H's stock-level pass mark is unchanged (2026-10-13)

**H29 stands exactly as written.** Nothing measured since — the corrected targets growing from
473 to 497 rows, three new source blocks, 37 candidate variables instead of 31 — changes the
bar or the way it is applied.

This is recorded as its own decision because the measured result was a **0.99pp miss** on
hit rate and a 0.75pp miss on the Wilson lower bound. A miss that small is exactly the
situation in which a threshold gets revisited, and the point of fixing it beforehand is that
it does not. Re-stating it here, before any combined model is fitted, means the next run
cannot be read as having been scored against a bar chosen with the result already in view.

**Model H remains display-only at the stock level until H29 passes on its own terms.**

---

### H35 — the fallback: "Model H-market", a market-heat statement rather than a per-IPO one

**Specified by the user on 13 Oct 2026, before the combined model is fitted.** This is a
second, weaker question asked of the same data: not *which IPO* will beat the index, but
*whether the market conditions at listing* say anything about how often IPOs of that vintage
did.

**Why it is worth asking separately.** Six of the seven variables that are STABLE across
every window scheme and both embargoed runs point the same way — a crowded IPO calendar, a
hot recent cohort, a strong index, a big listing pop against the sector, heavy first-day
churn all precede *worse* relative returns. The stock-level model cannot turn that into a
per-IPO ranking better than AUC 0.50. A tercile statement about the market is a much coarser
claim and may survive where the fine one does not.

**The score.** The six **stable heat variables**, and only these:

| Variable |
|---|
| `ipo_count_prior_3m` |
| `ipo_count_prior_6m` |
| `mean_listing_gain_prior_3m` |
| `nifty_tri_ret_12m` |
| `listing_gain_minus_sector_day` |
| `turnover_x_issue_size` |

Each **standardised** (mean and standard deviation computed **inside the training fold
only**), signed so that higher means hotter, then averaged with **equal weights**. No
fitted coefficients: equal weights are the point, because six correlated measures of one
thing cannot support six estimated weights on ~500 rows, and fitting them would be the
quiet way of reintroducing the stock-level model that already failed.

**The pass mark.** Walk-forward, **scheme C (expanding) with the `Y-2` embargo**. All three
must hold:

1. Pooled across test years, IPOs listed in the **coolest third** beat the Nifty 50 TRI at
   least **10 percentage points more often** than those in the **hottest third**.
2. The sign of that gap is the same in **at least 75% of test years**.
3. A **one-sided two-proportion test** on the pooled coolest-versus-hottest difference gives
   **p < 0.05**.

**What it may output if it passes.** A market-heat band — **LOW / MID / HIGH** — with that
tercile's historical beat rate against the index. Nothing else.

**What it may never output.** A per-IPO hold instruction, a percentage of an allotment, or
anything that reads as advice about a specific issue. H34 governs that, and H34 is a fail.
A tercile beat rate is a statement about a cohort; attaching it to one IPO would be exactly
the inference the stock-level AUC says cannot be made.

---

### H36 — Tapetide may be used for lookups only, and nothing of theirs is stored (2026-10-13)

**Their terms** (tapetide.com/terms) permit automated access **only** through their MCP or
API — no scraping — and forbid reproducing, distributing or making derivative works of their
data without written consent.

So Tapetide is used as a **pointer service and nothing else**:

| Permitted | Forbidden |
|---|---|
| Asking for a historical symbol or ISIN for the 45 unresolved rows | Storing any Tapetide **value** - a financial, a ratio, a price |
| Asking where an IPO document for the 37 missing RHPs can be found | Treating a Tapetide answer as a fact without official confirmation |
| Recording the note "located via Tapetide lookup" beside an official fact | Scraping their site; cloning their repo; putting their token in a GitHub secret |

**Every answer is a hypothesis until an official source confirms it.** A symbol is accepted
only if it appears in the **bhavcopy for that listing date** — the same gate every recovered
symbol passed in Phase 2.1. A document is accepted only if it is fetched from **SEBI, BSE,
NSE or another official host** and passes `_verify_is_prospectus()`. What gets stored is the
official fact with its official provenance; the Tapetide note records only *how it was
found*, which is a fact about our process and not their data.

A derivative work of their data is what storing their values would create. A symbol
confirmed in an NSE bhavcopy is NSE's fact, found faster.

**Budget: 50 calls per day**, counted and reported. The token lives only in the local
environment as `TAPETIDE_TOKEN` and is never written to the repository (CLAUDE.md: no
secrets in the repository).

---

### H37 — train and test on ALL years; pre-2019 gaps are not chased (2026-10-13)

**Decided by the user on 13 Oct 2026, before any model run.**

**Every year stays in.** Model H trains and tests on the whole 2010–2025 span, walk-forward,
**scheme C (expanding) with the `Y-2` embargo** — unchanged from H30 and H35. No year is
dropped, no era is excluded, and the sample is not trimmed to the years whose data happens
to be better.

**Pre-2019 data gaps are low priority.** They are not chased and nothing waits for them.
Where a value is absent it takes the **missing band (H25)** — its own bin, never zero, never
the mean, never a dropped row. That is what makes keeping the early years costless: a 2011
IPO with no RHP fundamentals contributes its market-heat variables and sits in the missing
band for the rest, rather than being excluded for what it lacks.

The gaps are real and measured, so the shape of them is on the record rather than implied:

| Source | Pre-2019 | 2019+ |
|---|---|---|
| Prospectus on SEBI | 60–67% of 2010–13 IPOs | 86–100% of 2019–25 |
| India VIX | **none** — NSE Indices serves the series from 2018 only | full |
| NSE industry (sector map) | sparse; index-constituent files cover current members | better |

**Reporting, not a decision rule.** Alongside the pooled result, the pooled figures for
**test years 2021–2025** are printed. That is a second view of the same fitted model, not a
second model and not a second pass mark: H34 (= H29) is still judged on the pooled result
across all test years, and H35's three conditions are still judged on all of them.

Why that distinction is worth stating: a recent-years figure will usually look better,
because coverage is better and the sample is denser. If the pass mark were read off it, the
model would effectively be judged on the subset where it has the most data — which is the
same error as choosing a threshold after seeing the result. The 2021–2025 block is there to
show whether the pooled number is being held down by the thin early years, and that is all
it may be used for.

### H38 — BSE's `IndustryNew` is accepted as a second source for the NSE sector (2026-10-15)

**This reverses the 13 Oct rejection of BSE, and the rejection was my error.**

That test compared BSE's `Sector` field against NSE's `Industry`, got 11 of 22, and
concluded BSE's scheme sat at a different rung of the ladder. The conclusion about `Sector`
was right; using it as the test was wrong. BSE serves four levels and **`IndustryNew`** is
the sector level — the same rung as the `Industry` column in NSE's index-constituent files.
The 13 Oct report listed `IndustryNew` in its own table and never tested it.

Re-measured on the 2019+ population the user asked for: 104 symbols that listed in 2019 or
later, whose NSE `Industry` is already on disk, and for which a scrip code exists in the
cached bhavcopies. All 104 fetches returned 200.

| BSE field | agrees with NSE `Industry` | agreement |
|---|---|---|
| **`IndustryNew`** | **104 of 104** | **100%** |
| `Sector` | 53 of 104 | 51% |
| `IGroup` | 9 of 104 | 9% |
| `ISubGroup` | 0 of 104 | 0% |

Before punctuation is normalised it reads 103 of 104: NSE prints "Media Entertainment &
Publication" and BSE "Media, Entertainment & Publication". One comma.

**So `IndustryNew` is a drop-in and is used to fill `nse_industry`.** The user's condition
was "if identical, fill with provenance and shrink the file; if not, stop and tell me", and
identical is what it is.

**The constraints on the fill, which are what make this safe rather than convenient:**

1. **Only `IndustryNew` is read.** `bse_sector_fill.py` asserts that `Sector`, `IGroup` and
   `ISubGroup` are never read as the industry. Filling from `Sector` would write "Consumer
   Discretionary" where `SECTOR_TO_INDEX` expects "Consumer Durables" — half the rows
   silently **wrong** rather than missing, which is exactly what hard rule 1 exists to stop.
2. **An NSE reading is never overwritten.** An official NSE constituent file outranks a
   second source that merely agrees with it 104 times out of 104. BSE only fills blanks.
3. **No request is made to discover a scrip code.** Codes come from the bhavcopies already
   cached in `data/`. A symbol with no cached code stays in the manual file for the user.
4. **Provenance per H26 on every filled row** — endpoint, scrip code, fetch time — and
   `source` reads `bseindia ComHeadernew IndustryNew`, so a filled row is never
   indistinguishable from an NSE-sourced one.
5. **3 s between requests** (rule 9), and `--validate` re-measures the agreement at any
   time rather than trusting this one measurement for ever.

**This is a second source, not a reconciliation.** Where NSE already states the industry,
BSE is not consulted; where it does not, there is nothing to reconcile against. So the
filled rows are single-source and must not be described as reconciled under hard rule 2.
They are not a *forced* mapping either — no crosswalk of ours is involved, which is the
thing H18's "never force a mapping" forbids. The vocabulary arrives already in NSE's words.

**Still blocked, and not worked around:** NSE's own four-level classification per symbol
from `api/quote-equity` returns HTTP 403 on all 258 symbols tried. The comparison above can
therefore only be made at the one rung NSE publishes in its constituent files — and that is
the rung `IndustryNew` matches.

### H39 — the predictions_log header was repaired; the DATA was not edited (2026-10-16)

**Approved by the user on 16 Oct 2026. This is a header correction, and the distinction
from a data edit is the whole point.**

**What was wrong.** `COLS` gained four columns — `sub_total_1500`, `sub_qib_1500`,
`sub_hni_1500`, `sub_rii_1500` — and `data/predictions_log.csv` was never migrated. The
file carried a **32-column header above a 36-column row** (HD Fire Protect, 14:47 IST on
15 Oct). Nothing complained, and that is the serious part: `to_csv(mode="a")` writes no
header when the file already exists, so every later append would have been wider than the
names above it, indefinitely. `pandas.read_csv` takes the first line as the names, so the
HD Fire row's last four values sat under no name at all — a silent misalignment in the
only record of what the live model actually decided.

**Why rewriting the header is legitimate here, and would not always be.** The four new
columns are appended at the **END** of `COLS`. So every existing 32-field row is still
correctly aligned under the first 32 names and simply reads the four new ones as blank.
No value changes meaning, and no row moves. `repair_header()` **refuses outright** if the
names on disk are not a PREFIX of `COLS`, because then the columns were reordered or
renamed and rewriting the header would silently relabel real data — in that case the rows
need migrating, not the header.

**Proof, not assertion.** Every data row's bytes were hashed before and after, and the
function reverts the file if any hash moves:

| | before | after |
|---|---|---|
| header columns | 32 | 36 |
| data rows | 6 | 6 |
| body SHA-256 | `3ff8ed35…a737f25b` | `3ff8ed35…a737f25b` |
| all six row hashes | — | identical |
| line endings | CRLF | CRLF |

The HD Fire row now reads its 15:00 split correctly — total 85.1185, QIB 120.398,
HNI 120.158, RII 25.535 — and the five older rows read the four new columns as blank.

**The guard, so this cannot happen again.** `check_header()` raises `SchemaMismatch` when
the file header and `COLS` disagree. It runs on **every append** and **every read**
(`_append`, `load`), and as a **pre-flight check** in `check_env.py`, which must pass
before any overnight or live run. The append direction is the dangerous one, so it is
checked there first. A schema change now cannot ship without migrating the header: the
pre-flight gate fails, and so does the next read.

Verified after the repair: `PL.load()` 6 rows x 36 columns, `PL.verify_append_only()` 6
predictions 0 outcomes 0 duplicates 0 orphans, `listing_prices._pending_predictions()`
returns its 1 pending row, `ingest_outcomes` reads through `load()` and `scored()`.
`check_env.py` 15/15.

### H40 — H22 is CONFIRMED: NSE first for the live figure, Chittorgarh as fallback (2026-10-16)

The HDFIRE intraday test (Task 9) set the rule in advance: confirm H22 if NSE's
`updateTime` advances within a bidding day, otherwise reduce NSE to an archival role. It
advances three to five times a day. Every other measure agrees.

| test | NSE `ipo-active-category` | Chittorgarh dashboard |
|---|---|---|
| `updateTime` advances intraday | yes, about every 2 hours | publishes no timestamp |
| polls returning a Total | **25 of 25** | 15 of 25 |
| carried the issue on closing day | yes | **no — 0 of 8** |
| lagged the other source | no | yes, at every comparable poll |
| category detail | QIB, NII + both sub-buckets, Retail, Employees, Total | Total + three categories |

**The caveat matters more than the verdict.** H22 was already the written policy and it was
not being honoured — not because NSE failed, but because our own client could not read its
payload. `run_live_l.nse_subscription` looked for `data`, `subscriptionTimes`,
`noOfshareBid` and `noOfSharesOffered`; NSE serves `dataList`, `noOfTotalMeant`,
`noOfSharesBid` and `noOfShareOffered`. It returned "no category rows" on every call, the
live leg fell back to Chittorgarh, and the row was logged `single_source_unverified (H14)`.
So **every prediction this system has made used the fallback source**, while the report
said the primary was NSE.

What it cost on HDFIRE: the 15:00 email decided on 85.12x from Chittorgarh when NSE's
14:57 publication already said **99.26x**. Both thresholds were cleared more than twice
over, so the verdict was right and nothing was lost. On a borderline IPO this is precisely
the failure that would have cost a qualifying bid.

Fixed on 16 Oct: categories are selected by `srNo`, a stable key, which also removes a
second latent bug — NSE serves the combined NII (`srNo 2`) and both sub-buckets (2.1 above
Rs 10 lakh, 2.2 Rs 2–10 lakh), all three containing "Non Institutional", and the old branch
assigned on every match so the LAST won: `hni_x` was the Rs 2–10 lakh bucket (137.28 on
HDFIRE) rather than the combined NII (203.21). The sub-buckets are now carried separately
for the DISPLAYED profile only, never as features (H3).

H22 is confirmed, and as of 16 Oct 2026 it is being honoured for the first time. The next
live run is the first that will log `nse_official` as the source.

### H41 — both Claude routines are replaced, and the user deletes them, not me (2026-10-16)

The two surviving app routines now have GitHub Actions equivalents (6a, 6b):

| routine | replacement |
|---|---|
| `ipo-ingest-outcomes` | a step inside `mode=final`, the 19:30 day-end leg |
| `ipo-retrain-monthly` | `mode=retrain`, driven by cron-job.org job 7 (`25 2 1 * *` UTC) |

**Nothing is deleted yet and I delete nothing.** The user's conditions, recorded so the
decision is not re-litigated later:

1. the ingest has run inside the day-end capture on **three consecutive weekdays** with no
   error, and
2. **one `retrain` run matches** the routine's last output.

The checklist lives in `PROGRESS.md` with the rows to tick. Until both are met the routine
and the workflow run in parallel; both legs are idempotent — the ingest on symbol plus
listing date, the retrain on the calendar month — so the overlap duplicates nothing and
sends nothing twice.

**Why parallel running is the right shape here rather than a cutover.** The ingest is the
only job that notices an IPO the user never bid on, so a silent failure costs training rows
that cannot be recovered later from any source. Running both until the replacement has
three clean days in a row makes that failure visible while the old path is still catching
what it would have missed.

**The engines stay.** `ingest_outcomes.py` and `retrain_l.py` are what the workflow calls.
Deleting the ROUTINES does not touch them, and that distinction is worth stating because
"decommission the retrain" could easily be read as deleting `retrain_l.py`, which would
remove the champion/challenger comparison, the PSI monitor, the 25% drift guard and the H19
tripwire in one go.

First evidence on the record: dispatch run `38824059003` (16 Oct 2026) produced
`IPO decision - RETRAIN 2026-10: no flags` with all eleven checks passing — L1 90.2% on 214
fires against a 90% promise, L2 80.8% on 156 against 80%, both H19 counts at 1 of 2,
threshold drift 0.0%, champion kept on both targets, 113 IPOs in the trailing 12 months,
and the predictions_log header at 36 of 36.

### H42 — two prospectuses accepted from non-official hosts, by name (2026-10-19)

**Approved by the user on 19 Oct 2026, for two specific documents, after seeing that
neither is on SEBI.** Hard rule 3 — RHPs come from SEBI for mainboard and BSE SME only —
is otherwise unchanged.

| company | host | source flag |
|---|---|---|
| Allied Blenders and Distillers Limited | `cms.abdindia.com` (the issuer's own CMS) | `issuer_site` |
| Sri Lotus Developers & Realty Ltd | `drive.google.com` (user-supplied link) | `user_supplied_drive_link` |

**The allow-list is keyed on the COMPANY, not the host**, so a different issuer's website
and a different Drive link are still refused. Every other condition applies in full: the
document must pass `_verify_is_prospectus()` — prospectus marker, company name on the
cover, at least 100 pages — and its URL, host, fetch time and SHA-256 are recorded, with
the source flag ensuring it is never indistinguishable from a regulator's copy.

No login is involved. A Drive *viewer* link is rewritten to its direct-download form; a
restricted file returns an HTML sign-in page, fails the `%PDF` check and is rejected, which
is the correct outcome rather than something to work around.

Allied Blenders verified at **675 pages**, so the issuer's copy is a genuine prospectus.

---

### H43 — P/B: two variables, three routes, and a share count that cannot be trusted whole

**ipo_pb_pre_issue and ipo_pb are different variables and are never interchanged.** The
pre-issue variant reaches **163 of 399 (41%)**; post-issue reaches 26 (7%).

**What the pre-issue NAV is.** `nav_pre_issue` — the explicit "NAV before the offer" line —
is extracted on **0 of 399** documents, so it cannot be the input. `nav_fy1`, the most
recent fiscal year's NAV per share, is on 166 and IS pre-issue book value per share: it is
struck before the offer by construction. Every row names its input in
`ipo_pb_pre_issue_input`.

**The three routes for post-issue, in the user's order, with the method on every row:**

| method | status | rows |
|---|---|---|
| 1 `rhp_stated_post_issue_nav` | built | 7 |
| 2 `chittorgarh_kpi` | **NOT fetched** — the 2,861-row harvest carries 50 fields and none is a P/BV or NAV, so this needs a fresh fetch of the KPI pages rather than a read of what we hold. Queued, and every row it would fill says so | 0 |
| 3 `derived_post_issue_nav` | built | 22 |

Method 1 outranks method 3; where both exist they are cross-checked and a disagreement over
5% withholds the row and logs both (hard rule 1). Method 3 **ignores issue expenses**, which
overstates post-issue book value and therefore understates the ratio — stated on every row
it produces.

**The finding that matters more than the coverage.** Hand-validating three IPOs caught a
wrong value no coverage table would have shown: Anupam Rasayan's post-issue share count
reads **220,000**, which gave a book value of Rs 72,023 per share and a P/B of **0.0077**.

So a guard now sits at the derive layer, and it is arithmetic rather than a heuristic:
selling a slice of a company for Rs N crore implies the company is worth at least Rs N
crore, so `shares x offer price >= issue size` must hold. **20 of the 153 extracted share
counts fail it**, some by three orders of magnitude; the 133 that pass sit between 2.0x and
425x the issue size, median 4.4x, so the test separates cleanly at 1.0.

| | count |
|---|---|
| share counts testable against offer price and issue size | 153 |
| **implausible — market cap below the money raised** | **20** |
| plausible | 133 |

The guard withholds the derived value and writes the reason and the multiple onto the row.
**The extractor still produces those 20 bad counts**, and that is recorded here as a defect
for the next extraction pass rather than hidden: re-running the extractor is a four-hour
job, and withholding at the derive layer is what protects the ratios today. `fcf_yield` and
`ipo_ev_ebitda` use the same share count and need the same guard.

**The peer premiums are blocked on data, not code.** `peer_1_pb` is extracted on 15 of 399
documents, because most RHP peer tables quote P/E, EPS, RoNW and NAV but not P/B.

Never from Tapetide (H36), asserted on the module body.

### H44 — the RHP field list is FROZEN, and a reader is graded before it runs (2026-10-21)

**The list.** These are the only fields read from a prospectus. Offer price, issue size and
the fresh/OFS split are **not** on it: they come from the master and Chittorgarh, per H5.

| block | fields |
|---|---|
| Basis for Issue Price | basic EPS and diluted EPS, 3 fiscal years + the weighted average; RoNW, 3 FY + weighted; NAV per share, latest FY, plus post-issue if stated; the peer table — name, face value, revenue, EPS, P/E, RoNW, NAV, P/B |
| Restated financials, last 3 **full** fiscal years, no stub periods | revenue from operations; PAT; tax expense; finance costs; depreciation & amortisation; EBITDA as stated, if given; net worth; total borrowings; cash & cash equivalents; cash from operations; capex (purchase of PPE) |
| Capital structure | pre-issue shares; post-issue paid-up shares; promoter % pre-offer and post-offer |

Frozen means: a field not on this list is not extracted, and a field on it is not dropped
for being hard. Two of them — **net worth** and **pre-issue shares** — have never been
extracted at all (0 values in `data/rhp_valuation_values.csv` at any version), which is
why four of the H45 formulas cannot produce a single row today. That is a reader gap, not
a formula problem, and naming it is the point of freezing the list.

**The gate.** `reports/rhp_check_set.csv` holds the hand-read truth for 20 prospectuses
from 2019 onward — every field, with its page and the quoted line. A reader runs over all
450 documents only after it reaches **95% precision** on the check-set rows for its own
fields, and precision and recall are printed per field.

The 20 are chosen by `build_check_set.py` from listing year crossed with NSE industry and
**nothing else** — never by whether the current readers succeed on a document. Grading a
reader on documents it already parses is how a 24%-coverage extractor came to be reported
as working (Stage 8). The selection is deterministic, so the same 20 come back on any
machine: 7 listing years, 18 industries.

### H45 — the derived valuation ratios, with their formulas (2026-10-21)

Every ratio is computed **at the final offer price**, and every one is withheld — NULL with
a reason — rather than approximated when an input is missing. Hard rule 1 applies to a
derived value exactly as it does to a read one.

| # | variable | formula | NULL when |
|---|---|---|---|
| a | `ipo_pe` | offer price / diluted EPS, latest full FY | EPS <= 0 |
| a | `ipo_pe_weighted` | offer price / weighted diluted EPS | weighted EPS <= 0 |
| b | `ipo_pb` | offer price / post-issue NAV per share (H43 methods 1-3) | no method yields a NAV |
| b | `ipo_pb_pre_issue` | offer price / pre-issue NAV per share — stated if given, else **net worth / pre-issue shares**, flagged `derived_pre_issue_nav` | NAV <= 0, or either input missing |
| c | `pe_premium_vs_peers` | `ipo_pe` / harmonic mean of peer P/Es - 1 | fewer than 2 usable peers |
| c | `pe_premium_vs_peer_median` | `ipo_pe` / median peer P/E - 1 | fewer than 2 usable peers |
| d | `pat_cagr` | (PAT latest FY / PAT earliest of the 3 FY)^(1/2) - 1 | either PAT <= 0 |
| d | `ipo_peg` | `ipo_pe` / (`pat_cagr` x 100) | `pat_cagr` <= 0 |
| e | `ebitda_fy1` | stated if the RHP gives it, else PAT + tax expense + finance costs + D&A, same FY and same unit, flagged `derived_ebitda` | **any** component missing |
| f | `pre_money_mcap` | pre-issue shares x offer price | pre-issue shares missing |
| f | `net_debt` | total borrowings - cash & equivalents, latest FY | either missing |
| f | `ipo_ev_ebitda` | (`pre_money_mcap` + `net_debt`) / EBITDA | EBITDA <= 0 |
| f | `fcf_yield` | (cash from operations - capex) / `pre_money_mcap` | either cash-flow input missing |

**Three choices worth stating, because each one could reasonably have gone the other way.**

*The pre-money basis (f).* Enterprise value and free-cash-flow yield are taken against
**pre-issue** shares, not post-issue. A fresh issue adds cash to the balance sheet that the
historical EBITDA and cash flow did not produce; pricing the post-issue share count against
pre-issue cash flow double-counts the raise. It also sidesteps the post-issue share count,
which is the least trustworthy number in the file — 130 values at 1.8.1, of which the
two-sided guard rejects a share.

*A harmonic mean for peer P/Es (c).* An arithmetic mean of ratios lets one 180x peer drag
the basket; the harmonic mean is the ratio of the sums, which is what "what is this
industry worth" means. The median is reported beside it so a reader can see when the two
disagree. A market-cap-weighted basket is **not possible** from this data and will not be
faked: RHP peer tables publish name, face value, revenue, EPS, P/E, RoNW, NAV and
sometimes P/B, and **never market capitalisation or net profit**, so there are no weights.

*Two growth years, not three (d).* Three fiscal years contain two year-on-year changes, so
the exponent is 1/2. Writing 1/3 — a common error — understates every CAGR in the file.

**Not built, and why.** A RoNW/Gordon-growth implied valuation needs an assumed cost of
equity and an assumed payout ratio. Neither is in the prospectus, so both would be
invented, and rule 1 does not have an exception for a plausible assumption. Note also that
the derived EBITDA **includes other income**, because PAT does; that is stated on every row
it produces rather than silently corrected.

### H46 — peer-basket momentum is dropped; sector-index momentum is the only one (2026-10-21)

`peer_basket_minus_nifty_3m` and `_6m` are cancelled before the price half was written.
The name reader is the ceiling, not the mapping: of 967 peer-name rows, 285 matched NSE's
equity list exactly, 510 were junk the reader had glued together from table headers and
period labels, and only **66 of 296 IPOs** reached the two mapped peers the variable needs.
A momentum number computed from two survivors of a noisy reader is a different variable on
every row.

`data/peer_symbols_mapped.csv` is kept for later. `data/manual_inputs/peer_symbols.csv` is
**withdrawn from the user's to-do list** — it was 156 rows of this project's own extraction
noise, and asking a human to resolve strings a reader invented is the wrong repair. It now
sits at `data/peer_symbols_unmatched.csv`, outside `manual_inputs/`, which is by definition
the folder of files the user is asked to fill.

Sector momentum stays, and this is what raising its coverage was worth:

| variable | 2019+ before | 2019+ after |
|---|---|---|
| `nse_industry` | 186 (47.3%) | **350 (89.1%)** |
| `sector_index` | 107 (27.2%) | **249 (63.4%)** |
| `sector_minus_nifty_3m` / `_6m` | 107 (27.2%) | **249 (63.4%)** |
| `listing_gain_minus_sector_day` | 106 (27.0%) | **247 (62.8%)** |

Three of those rows came from a comma. NSE spells the same sector two ways across its own
files — `Oil Gas & Consumable Fuels` and `Oil, Gas & Consumable Fuels`, likewise Media —
and the lookup used `.strip().lower()`, so one spelling mapped and the other fell through
to "no index exists". The key is now punctuation-insensitive, and nothing else about it is
loosened: two sectors differing by a word still differ (H28).

The remaining 2019+ gap is 104 rows with an industry and no index, and NSE genuinely
publishes no index for them. Re-checked against NSE's own catalogue (`api/equity-master`,
122 indices) on 21 Oct: nothing exists for Capital Goods (56 rows), Consumer Services (37),
Telecommunication (3), Utilities (3) or Textiles (2). The nearest candidates — NIFTY INDIA
MANUFACTURING, NIFTY CAPITAL MARKETS, NIFTY INDIA CONSUMPTION, NIFTY MIDSMALL IT & TELECOM
— are different baskets, and a wrong benchmark produces a momentum number that looks
exactly like a right one. Not forced.

### H47 — NSE's terms of use prohibit automated collection (2026-10-22; **RATIFIED 2026-10-23**, see the end of this file)

Rule 5 says "respect robots.txt **and site terms**", and B1's standing instruction is: if a
source's terms prohibit access, stop using it and report. The terms were read today for the
first time, at the URLs the user supplied. **This is the report.**

#### What NSE's terms say, quoted

`https://www.nseindia.com/static/nse-terms-of-use`, fetched 2026-10-22, payload SHA-256
`7da31c2d52ee…`:

> "User is granted a non-exclusive, non-transferable, limited right to access the Website /
> Mobile Application and avail the services provided by NSE through the Website / Mobile
> Application. **User is prohibited to conduct any systematic or automated data collection
> activities (including scraping, data mining, data extraction and data harvesting) on or in
> relation to our Website / Mobile Application.**"

And separately:

> "User agrees that any information or content or data on the Website / Mobile Application
> shall not be copied, modified, reverse engineer, reproduced, uploaded, transmitted, posted,
> **stored (either in hardcopy or in an electronic retrieval system)**, adapted, altered,
> translated, disseminated, distributed, displayed, performed, broadcasted, published,
> hyperlinked, sold, marketed, licensed, rented, leased or distributed in any form, without…"

`https://www.nseindia.com/static/website-policies` (SHA-256 `a8b5bb54bbd8…`) adds:

> "no portion of the information on this website may be reproduced on or transmitted to or
> stored in any other website or in other form of electronic retrieval system"

#### Why this matters here, stated plainly

Every NSE call this project makes is automated. `data/listing_prices.csv`,
`data/NIFTY50_TRI.csv`, the bhavcopy cache, `data/sector_map.csv`,
`data/nse_trading_holidays.csv` and `data/issue_dates_recovered.csv` all store NSE-sourced
values in an electronic retrieval system. On the plain words above, **this project is doing
what NSE's terms prohibit** — and by the project's own H18 clause ("still forbidden: …
reaching any source whose terms prohibit scraping"), NSE falls into the same category as
`ipoindex.in`, which is on the B1 blacklist for a Terms-of-Use clause.

The machine-readable permission says the opposite. `www.nseindia.com/robots.txt`, re-fetched
today, is `User-agent: *` → `Allow: /` with only `/market-data-test` disallowed. So NSE's
robots.txt invites the crawl its terms forbid. Both were read; neither is being ignored in
favour of the other, and the conflict is the finding.

#### What is NOT in dispute

* **BSE does not prohibit this.** Its footer Disclaimer and Website Policies, read today
  through the rendered page (they are buttons, not links — no URL to cite), contain no
  mention of scraping, crawling, automated access, data mining or robots. The only
  restriction is copyright: "Any reproduction, redistribution or transmission, for
  consideration or otherwise, of any such information contained on the Website is strictly
  prohibited", and "No part of the information on this Website … may be reproduced or
  transmitted in any form by any means, without the express written consent of BSE." That
  bars **redistribution**, which this project does not do. BSE is clear.
* **SEBI** publishes `robots.txt` with an empty `Disallow:` (allow all) plus four static
  asset paths. No automated-access clause was found.
* Nothing here concerns bypassing a login, CAPTCHA or paywall. NSE's data is served openly.

#### The decision is the user's, and these are the options

| | Option | What it costs |
|---|---|---|
| A | **Carry on.** Personal, non-commercial, no redistribution, a handful of requests a day, ≥3 s apart — treat the clause as aimed at commercial harvesting | The clause says "any", not "any commercial". This is a judgement that the words do not support on their face |
| B | **Stop at NSE. Rebuild on BSE.** BSE serves bhavcopies, an IPO demand schedule and industry classification, and permits it | Loses `api/public-past-issues`, `ipo-active-category`, the holiday master, NSE Indices TRI and the index constituent files. The TRI is Model H's benchmark and has no BSE equivalent. Weeks of work, and some of it unreplaceable |
| C | **Ask NSE for written permission** for personal research use, and pause new NSE collection until they answer | Slow, may get no reply, but it is the only route that makes A safe in writing |
| D | **Narrow it.** Keep the live subscription read (Chittorgarh already covers it) and stop storing NSE-derived values, deriving what is possible from BSE | Half-measure; the stored history is the asset |

**Recommendation: C, with A continuing meanwhile only if the user says so.** This is the
user's personal project on their own account and their call to make, not mine. What I will
not do is keep collecting while describing the position as settled.

**Until the user decides, this session made no further NSE requests after the finding.** The
calls already made today — the holiday calendar, HD Fire's issue record, the 137 issue-open
dates — were made before the terms were read and are recorded with full provenance.

---

## 2026-10-23 — H47 RATIFIED, and a correction to what I reported about H18

### H47 — NSE and niftyindices terms: the user accepts the risk and continues

**Supersedes the AWAITING_USER entry recorded on 2026-10-22.** The user's decision, verbatim
in substance:

> NSE and niftyindices.com terms prohibit automated collection and storage without written
> consent. The user accepts the risk of being blocked and continues for personal,
> non-commercial use:
>
> 1. The repository stays private. Raw NSE/niftyindices data is never published, shared or
>    redistributed; only aggregate results and conclusions may be shared.
> 2. Claude Code commits data only to the private repo — never to a public location, gist,
>    artifact or share link.
> 3. Requests stay minimal: existing schedule, rule-5 gaps, cached data reused, no bulk
>    re-downloads.
> 4. For each data item the source giving the most/best data is primary; BSE or Chittorgarh
>    replaces NSE only where equal or better, and is added wherever it brings data NSE lacks.
> 5. Every NSE/niftyindices fetch has an automatic failover to BSE/Chittorgarh. A block
>    (403/connection refusal) is never worked around — the pipeline fails over and reports it.
> 6. Pending: the user is applying via NSE's form; if consent is granted, record it here.

**What this binds me to, stated as operational rules rather than sentiment:**

| # | Rule | Enforced by |
|---|---|---|
| 1 | Never publish raw NSE or niftyindices data | No artifact, gist, paste or share link may carry a row of it. Aggregates and conclusions only |
| 2 | Commit only to this private repository | `git remote -v` is the only destination |
| 3 | No bulk re-download | Caches are reused: `data/bhavcopy_cache/`, `data/rhp_text_cache/`, the stored holiday calendar. A re-fetch needs a reason |
| 4 | Best source wins per item | Section "Source map" below. NSE is not the default — it is the default *where it is better* |
| 5 | **A 403 is an answer, never an obstacle** | Failover to BSE/Chittorgarh, and the run says `NSE blocked — failed over to X`. No retry loop, no header rotation, no proxy, no backing off and trying again later to see if the block lifted |
| 6 | Consent pending | `reports/NSE_FORM_DRAFT.md` is drafted for the user to complete and submit. Nothing is submitted by me |

Rule 5 deserves the emphasis. The line between "failing over because we were blocked" and
"working around a block" is the whole of this decision's integrity, and it is drawn at
**one** attempt: if NSE answers 403 or refuses the connection, that host is done for that
run. Changing a header, waiting and retrying, or routing differently would each be a
circumvention, and H18's prohibitions still stand in full.

**What has NOT changed.** The B1 blacklist (IPO Ji, InvestorGain, ipoindex.in,
iporupee.com). Bypassing a login, CAPTCHA, paywall or click-through. Ignoring a robots.txt
disallow. H36's Tapetide terms. BSE remains clear: its Disclaimer and Website Policies carry
no automated-access clause at all, only a copyright bar on reproduction and redistribution,
which rule 1 above already honours.

### A correction: H18 was not ambiguous, and I said it was

On 2026-10-22 I reported that "the label H18 is carrying two decisions" and offered to split
it. **That was wrong.** The collision was found and resolved on **2026-10-10**, in the
*Numbering resolved* section of this file, and in the opposite direction to the one I
described: the 2026-10-03 "name similarity cannot identify a company rename" decision was
renumbered **H28**, and **H18 means only the rule 5 relaxation** (2026-10-05). `CLAUDE.md`
line 61 attributes the header relaxation to H18, which is correct and needs no change.

So the user's instruction — "give the header-relaxation decision its own number" — is
**declined on the evidence**, because carrying it out would break what the 2026-10-10 entry
deliberately protected: H18 is cited by that meaning in code comments (`listing_prices.py`,
`market_context.py`, `model_h_sources.py`, `ingest_outcomes.py`, `backtest_email.py`), in
`PROGRESS.md` stage rows 21/23/26/31, and in the live email footer. Renumbering it now would
invalidate live citations to fix a problem that does not exist.

The one real defect was navigational: `### H18 — name similarity cannot identify a company
rename` still began with the string `### H18`, so a grep for the heading found the
superseded entry first. The heading now reads `### H18 → RENUMBERED H28`, with its body and
its pointer untouched. That is a signpost, not an edit to a decision's identity — which is
the thing this file exists to prevent.

### H48 — the three post-issue figures are CALCULATED, not read (2026-10-23)

Hand-reading the check set established what a coverage table had been hiding: a Red Herring
Prospectus **cannot** state the post-issue share count, the post-issue NAV per share or the
promoter post-Offer percentage. All three depend on a price that is not fixed until the book
closes, so the document prints `[●]`. Polycab prints it for every one. That is not a reader
failure, and it explains `shares_outstanding_post_issue` reaching only 130 of 450 documents
and `ipo_pb` sitting at 0% for 2019+.

So they are calculated, from numbers the RHP does state and the price the market later fixed:

| variable | formula |
|---|---|
| `post_issue_shares` | pre-issue shares (RHP) + fresh issue amount (RHP) ÷ final offer price (master). A fresh issue stated as a SHARE COUNT is added directly and no division happens. **An offer for sale does not change the total** — it transfers existing shares |
| `post_issue_nav` | (pre-issue net worth + fresh issue amount) ÷ `post_issue_shares` |
| `promoter_post_pct` | (promoter pre-issue shares − promoter OFS shares) ÷ `post_issue_shares` |

All flagged `derived_from_rhp`. The share count passes the same two-sided plausibility guard
`derive_pb` uses, and a failure there withholds everything downstream of it.

**Where the RHP prints `[●]` for the fresh issue amount too**, it is recovered as
`issue size (master) − OFS shares (RHP) × final offer price`. Every term is a stated number.
This was graded against a case where the RHP *does* state the amount before being trusted
anywhere else: Craftsman Automation, issue size ₹823.70 cr less 4,521,450 shares at ₹1,490 =
**₹150.00 cr**, against the **₹1,500.00 million** printed on p71 of its own RHP — agreement to
**0.003%**, which is the master's own rounding of the issue size to two decimals.

**Two things are disclosed on every row rather than smoothed away.** Issue expenses are
ignored, which overstates post-issue book value and therefore understates P/B. And where the
promoter OFS participation is unknown, the calculation assumes none and **says so**, because
that assumption overstates the holding.

**Hand-validated on three check-set RHPs:**

| | Polycab | Craftsman Automation | Global Health (Medanta) |
|---|---|---|---|
| pre-issue shares, page | 141,205,838 (p102) | 20,121,600 (p71) | 253,303,930 (p125) |
| fresh issue | ₹4,000 million, stated (p102) | ₹1,500.00 million, stated (p71) | **`[●]`** — derived ₹500.00 cr |
| OFS shares | 17,582,000 (p102) | 4,521,450 (p71) | 50,761,000 (p125) |
| final offer price | ₹538 | ₹1,490 | ₹336 |
| **post-issue shares** | **148,640,782** | **21,128,338** | **268,184,894** |
| **post-issue NAV** | **₹184.96** | not computed — net worth not yet transcribed | not computed — same |
| **promoter post %** | **63.00%**, from 66.32% pre | not computed | not computed |

Polycab's figures carry their own cross-check: the implied post-issue P/B is 538 ÷ 184.96 =
**2.91×**, the NAV rises from the stated pre-issue ₹166.39 as a raise requires, and the
promoter holding falls from the stated 66.32% as dilution requires. Craftsman and Medanta are
validated on the share count only; their net worth is not yet hand-read, and a figure is not
reported until it is.

`derive_post_issue.py`, 33 self-tests.

---

### H49 — net worth is not "share capital + other equity", and a promoter's OFS is not the offer's OFS (2026-10-25)

Found while hand-validating H48 across seven transcribed check-set RHPs. Three separate
corrections, each with the document that forced it.

**1. The net-worth cross-foot is not safe on its own.** H44 defines net worth as
`equity share capital + other equity`. Craftsman Automation's balance sheet prints its own
total-equity sub-total of **₹7,716.11 million** at 31 December 2020, and its stated NAV of
₹355.93 on 20,121,600 shares implies **₹7,161.88 million** — 7.7% lower, past rule 2's
tolerance. The document settles it itself: its stated RoNW of **7.07%** on a restated
profit of ₹506.60 million requires about ₹7,165 million. The balance-sheet sub-total would
give 6.57%. So the RHP's net worth is the lower figure, and the cross-foot is wrong here.

Two other documents in the set print an explicit definition that explains the mechanism:

| RHP | its own definition of net worth |
|---|---|
| Prince Pipes (p110) | equity share capital + reserves and surplus, per section 2(57) — the cross-foot IS valid |
| Vishwaraj Sugar (p110-111) | share capital + securities premium + general reserve + surplus, **excluding preference capital and revaluation reserve** |

**Rule for the reader:** take a stated `Total Equity`/`Net worth` line where one exists,
cross-foot it against share capital + other equity, **and** cross-check it against the
stated NAV and RoNW. On a disagreement above 5%, prefer the figure the stated NAV and RoNW
agree on, and if they do not agree with each other, withhold.

**2. The share count behind a stated NAV is the PERIOD-END count, not the RHP-date count.**

| RHP | net worth ÷ stated NAV | pre-issue count on the capital page | gap |
|---|---|---|---|
| Medanta | 253,225,000 | 253,303,930 | +0.03% |
| CAMS | 48,785,000 | 48,786,800 | exact |
| Prince Pipes | 91,617,988 | 95,980,816 | **−4.5%** |
| Likhitha | 14,625,000 | 14,625,000 | exact |

Shares issued between the balance-sheet date and the RHP make the gap, so the cross-check
must report the gap rather than fail on a fixed threshold. A hard ±1% test would have
rejected Prince Pipes' correct reading.

**3. A promoter's offer-for-sale is not the offer's offer-for-sale.** Polycab's post-issue
promoter percentage was recorded on 23 October as **63.00%**. That is wrong. It is what
`promoter_post_pct` returns when no promoter OFS count is supplied — and the function's own
reason string warns that it overstates the holding. Polycab's p89 breaks the 17,582,000
offered shares down by shareholder, and only four of the nine sellers are Promoters as p2
defines them (IFC is the Investor Selling Shareholder; two Jaisinghanis are Promoter
**Group**; two more are Individual Selling Shareholders). The Promoters' own portion is
**8,312,844**, and the correct figure is **57.41%**.

**4. A third route to a stated post-issue figure.** H48 named two exceptions: a pure OFS,
and a fresh issue stated as a share count. CAMS adds a third for the promoter percentage —
its promoter sells 6,108,400 shares **privately under share-purchase agreements before the
bid opens**, not in the offer, so the RHP states its post-Offer holding (15,115,600, 30.98%)
without needing a price.

**5. One correction of my own.** The CAMS pre- and post-issue share counts recorded on
23 October as 25,486,027 were the **securities premium account**. The words "Before and
after the Offer" appear twice on that page under different headings, and I matched the
phrase without reading the section. The true figure, 48,786,800, is on the same page and
cross-foots to both the stated promoter percentage and the stated NAV, which 25,486,027
cannot do. Corrected in `reports/rhp_check_set.csv`, with the securities premium now
recorded in its own right so the misread cannot recur silently.

**Also fixed:** `derive_post_issue.derive` produced no post-issue NAV at all when the fresh
issue was stated as a share count, because the NAV needs rupees. It now multiplies the
share count by the final offer price, and says that it did.

Evidence: `h48_validate.py` (29 self-tests), `reports/H48_VALIDATION.md`,
`reports/H48_VALIDATION.csv`. H48 stands; this narrows it.

---

### H50 — the RHP readers: the column is proved, not parsed; three of five are parked (2026-10-25)

Task 3 built the five readers and a gate. The gate is a floor on **precision** — the share
of values a reader produces that are right — because a reader that withholds is useless but
a reader that is confidently wrong corrupts every ratio built on it and will not be found
by inspection. Recall is reported but does not gate.

**The architecture, and why it is this and not simpler.**

| Step | What it does | Why not the obvious thing |
|---|---|---|
| 1 | Find the restated pages by **content** | `extract.base.locate` reads the TOC and puts Route Mobile's financials at PDF pages 2-28, which is the auditor's report in the front matter. Its restated balance sheet is 300 pages later |
| 2 | Name the target period: the **latest full fiscal year**, from the weighted rows of the Basis tables | "The latest column" is not an answer when the latest column is a nine-month stub. A nine-month figure in an annual ratio is a different quantity, not a small error |
| 3 | Pin the profit-and-loss column on `profit / shares = that year's stated EPS` | Borrowing the balance sheet's column index is what made the readers wrong |
| 4 | Net worth from `profit / that year's stated RoNW`, matched to a balance-sheet column | A great many RHPs print a NAV only for the stub period, so the fiscal year has nothing to anchor on |

**The column is never parsed from the header.** A restated table's header is split over two
printed lines in whatever order the typesetter chose, and getting it wrong files a correct
value against the wrong year. So the column is pinned by the document's own arithmetic, and
where no column can be proved the reader **withholds**.

**The score on the hand-read check set:**

| field | produced | correct | precision | recall | verdict |
|---|---|---|---|---|---|
| `shares_outstanding_pre_issue` | 3 | 3 | **100%** | 75% | clears the floor |
| `net_worth` | 1 | 1 | **100%** | 33% | clears the floor on **one** value |
| `tax_expense` | 0 | 0 | — | 0% | **parked** |
| `finance_costs` | 1 | 0 | **0%** | 0% | **parked** |
| `depreciation_amortisation` | 1 | 0 | **0%** | 0% | **parked** |

**Clearing a floor on one value is not a measurement, and is not treated as one.** Only the
share-count reader was run over the corpus, and only because it has an *independent* guard
that needs no hand reading: a pre-issue count times the offer price must imply a market
capitalisation of roughly 1x to 25x the money raised, because an issue is a slice of a
company. That turns the corpus into a few hundred checks instead of an extrapolation from
three.

**Why the three are parked, named precisely.** One cause dominates, and it is the PDF
extractor splitting long figures. Polycab's page prints
`Finance costs - - - - 9 36.80 - - - - 659.49`, where `9 36.80` is 936.80; the reader
returned **36.80**. The repair exists — a row with too many tokens is merged back to the
column count the page's clean rows agree on — but it needs a reliable column count, and on
a page where most rows are split the modal count is itself wrong. Three further causes,
each seen on real documents:

| cause | example |
|---|---|
| the `Profit for the year` row has many spellings | `Profit After Tax`, `Restated profit for the year`, `Profit/(loss) for the year` |
| margin tables interleave percentage columns | `Profit for the period 269.34 8.62% 691.02 7.14%` |
| segment tables carry the same row labels | the Polycab line above is a segment table, not the P&L |

The fix is a page-level column reconstruction — repair every row of the page to one
consensus count, reject pages whose rows cannot be reconciled — rather than four more
patches to a row-at-a-time parser. That is the next piece of work and it is not started.

**pdfplumber's text-strategy tables were measured first and are not used.** On three
check-set RHPs they split cells arbitrarily — `['Equity Share c', 'apital']`, and a number
broken across two cells as `'1,'` and `'108.52'` — at 2-3 seconds per page against
effectively zero for a cached text line.

**Consequence for the rest of Task 3:** the H45 ratios are not re-derived, the variable
inventory is not refreshed and the stability analysis is not re-run. All three consume the
readers' output, and with three of five parked they would change nothing that is not noise.
Stated rather than performed.

Evidence: `rhp_pages.py` (20 self-tests), `rhp_readers.py` (63), `rhp_reader_gate.py` (17),
`run_share_count.py` (9), `reports/READER_GATE.md`, `reports/SHARE_COUNT_450.md`.

### H51 — the repository is PUBLIC, and H47's private-repo condition is waived (2026-11-02)

**The user's decision, recorded as given:** the repository at
github.com/AshishKohar1/ipo-agent is public by their decision of 2 November 2026. H47's
condition that "the repository stays private" is **waived by the user**. Visibility is not
to be changed by me.

**This is a waiver, not a reinterpretation.** H47 rule 1 reads "Raw NSE/niftyindices data
is never published, shared or redistributed; only aggregate results and conclusions may be
shared", and rule 2 "commits data only to the private repo — never to a public location".
A public repository publishes every tracked file to anyone, so rules 1 and 2 as written are
now contradicted in fact, not merely relaxed. The user accepts that. What follows is the
exposure, on the record, so that no future reader of this file has to reconstruct it.

**Three properties of the exposure that are easy to get wrong:**

1. **It is retroactive and permanent.** All 383 commits are public, not just the current
   tree. The `pre-housekeep` tag holds files later moved or deleted. Returning the
   repository to private later does **not** un-publish anything already cloned, forked,
   cached by GitHub, or indexed.
2. **It is not limited to the files below.** `data/live_fetch_log.csv` records the exact
   NSE/niftyindices URL and timestamp of every request this project has ever made, and the
   `.github/workflows/live-model-l.yml` run logs quote report bodies into the step summary.
3. **The aggregate-only carve-out in H47 rule 1 no longer carves anything out**, because
   the raw rows are published alongside the aggregates.

#### Files under `data/` holding raw NSE or niftyindices data

Raw means the rows are substantially as the host served them: a fetched series, list or
table, not a figure derived through this project's modelling.

| file | rows | host | what it holds |
|---|---|---|---|
| `NIFTY50_TRI.csv` | 4,395 | niftyindices.com | Nifty 50 Total Return Index daily series, 2009–2026 (`getTotalReturnIndexString`) |
| `index_history.csv` | 83,698 | nsearchives.nseindia.com + niftyindices.com | daily closes for the broad and sector index set |
| `nifty_pe_history.csv` | 13,824 | niftyindices.com | Nifty P/E and P/B history (`getpepbHistoricaldataDBtoString`) |
| `nse_index_catalogue.csv` | 122 | niftyindices.com | the index catalogue |
| `india_vix_history.csv` | 2,167 | nseindia.com | India VIX daily series |
| `market_context.csv` | 376 | niftyindices.com | the 15 index closes captured by the 19:30 leg |
| `NSE_EQUITY_L.csv` | 2,601 | nsearchives.nseindia.com | `EQUITY_L.csv`, NSE's listed-equity master |
| `nse_trading_holidays.csv` | 20 | nseindia.com | trading holidays, current year |
| `nse_holiday_master.json` | 34 KB | nseindia.com | the holiday API response, all segments |
| `nse_name_changes.csv` | 2,328 | nsearchives.nseindia.com | `namechange.csv` |
| `nse_symbol_changes.csv` | 1,066 | nsearchives.nseindia.com | `symbolchange.csv` |
| `sector_map.csv` | 919 | nseindia.com | per-symbol sector from `api/quote-equity` |
| `sector_map_quotes.csv` | 258 | nseindia.com | the quote rows those sectors were read from |
| `listing_prices.csv` | 631 | nsearchives.nseindia.com (+ BSE) | listing-day bhavcopy prices |
| `listing_prices_progress.csv` | — | as above | the capture's own progress ledger |
| `day1_turnover.csv` | 506 | nsearchives.nseindia.com | day-1 turnover, read from the bhavcopy |
| `new_listings.csv` | 42 | nseindia.com | `api/public-past-issues`, the outcome harvest |
| `issue_dates_recovered.csv` | 737 | nseindia.com | true issue-open dates recovered from NSE |
| `corporate_actions.csv` | 1,505 | nseindia.com | splits and bonuses behind the H-target price adjustment |
| `corporate_actions_progress.json` | 160 KB | nseindia.com | the per-symbol response ledger for the above |
| `subscription_snapshots.csv` | 77 | nseindia.com + chittorgarh.com | the 15:00 subscription snapshots |
| `final_subscription.csv` | 1 | nseindia.com + chittorgarh.com | final subscription at close |
| `daywise_subscription.csv` | 3 | nseindia.com | the day-wise rows that exist at all (H1) |
| `hdfire_poll.csv` | 100 | nseindia.com + chittorgarh.com | the 13–15 Oct intraday poll |
| `predictions_log.csv` | 26 | carries NSE figures | each logged decision, with the subscription it was made on |
| `IPO-PastIssue-17-09-2021-to-17-09-2026.xlsx` | — | nseindia.com | the NSE past-issues export used as the spine |
| `live_fetch_log.csv` | — | metadata, not rows | every request's exact URL and timestamp |

**Not on this list, and why:** `price_history.csv` and the `holding_target*` files are
yfinance-derived or modelling output, not NSE rows; `chittorgarh_*`, `rhp_*`,
`manual_rhp_*` and `verified_rhp_manifest.csv` come from Chittorgarh, SEBI and BSE, which
H47 does not govern (BSE's policies bar reproduction and redistribution, which a public
repository arguably does engage — recorded here as a known question, not a decision);
`master_with_symbols.csv`, the tracker workbooks and `Initial Public Offering (Updated).xlsx`
are the master and IPOMatrix aggregator data.

#### What is NOT waived

H47 rules 3, 4, 5 and 6 stand unchanged and in full. In particular **rule 5 — a 403 or a
refused connection is one answer per host per run, never an obstacle to work around.** Also
unchanged: the B1 blacklist, the bar on bypassing a login, CAPTCHA, paywall or
click-through, the robots.txt rule, and H36 on Tapetide.

**My recommendation, on the record and overruled:** I advised keeping the repository
private, because publication is the one condition of H47 that cannot be undone once done.
The user considered it and decided otherwise. This entry exists so the decision is
auditable, not to re-litigate it.

### H52 — SEBI has no RHP for the four DRHP rows, so all four are excluded (2026-11-02)

**The user's instruction, on finding four `DRHP` rows in `data/rhp_sources.csv`:** rule 3
stands, no DRHPs; for each one, resolve the RHP from SEBI; if there is no RHP, use the final
prospectus and label it; verify with `_verify_is_prospectus()` and record URL + SHA-256; and
if none exists on SEBI, exclude it and say so.

**It is the last branch, for all four.** `resolve_sebi` was re-run on 2026-11-02 for
`doc_type="RHP"` and then `doc_type="PROSPECTUS"`:

| company | listed | RHP on SEBI | final prospectus on SEBI | verdict |
|---|---|---|---|---|
| Allied Blenders and Distillers Limited | 2024-07-02 | not found | not found | **EXCLUDED** |
| Northern Arc Capital Limited | 2024-09-24 | not found | not found | **EXCLUDED** |
| Amanta Healthcare Ltd. | 2025-09-09 | not found | not found | **EXCLUDED** |
| Sri Lotus Developers and Realty Limited | 2025-08-06 | not found | not found | **EXCLUDED** |

**Why four identical "not found" results are believable rather than a broken resolver.**
Four identical negatives are exactly what a silently broken resolver produces, so the
resolver was tested against a control first: three companies whose SEBI RHP is already
recorded in `data/rhp_progress.csv`.

| control | result |
|---|---|
| Euro Pratik Sales Ltd. | FOUND, and the URL matches the recorded one |
| Dev Accelerator Ltd. | FOUND, and the URL matches the recorded one |
| Shringar House of Mangalsutra Ltd. | FOUND, and the URL matches the recorded one |

The resolver works. And the result is not new: all four already sit in
`data/rhp_progress.csv` at **`status = source_unresolved`** with the note
`SEBI: no RHP matching name+date for queries [...]`. The 2026-11-02 run reproduces the
pipeline's own earlier verdict rather than discovering anything. That is also why
`rhp_sources.csv` carried a DRHP for them in the first place: a human went and found the
draft by hand because SEBI had no RHP.

**What was NOT done, deliberately.** The fetch log `data/rhp_valuation_fetch.csv` holds a
URL and a verified SHA-256 for each of the four, and three of those are SEBI
`attachdocs` paths — so a document could have been fetched for all four in one pass. It was
not, because those are the DRHPs: filed seven months before listing in each case, far
outside the 90-day window `fetch_rhp.DATE_WINDOW` allows an RHP. Fetching them would have
satisfied the letter of "restore the documents" while breaking rule 3. Note that
`_verify_is_prospectus()` would have **passed** all three: a draft red herring prospectus
carries a prospectus marker, the company name and well over 100 pages. The guard cannot
tell a DRHP from an RHP and was never meant to — which is the reason the document type has
to be established at resolution, not at verification.

**Recorded in the data, not just here.** `data/rhp_sources.csv` gains `h52_status` and
`h52_note`; the four rows read `EXCLUDED_NO_RHP_ON_SEBI`, so the file no longer looks like
it lists four fetchable documents. The 24 non-DRHP rows are untouched.

**Consequence for the text cache, stated as arithmetic and not as a match.** The old build
was **454 documents / 217,836 pages**, which is what `data/rhp_valuation_fetch.csv` records
and what `build_text_cache.py`'s own cost estimate quotes. The three provenance lists name
**446** distinct documents once the four DRHPs are dropped, of which **445** were restored —
`Samhi Hotels Limited` is the one failure, rejected because the PDF has no extractable text
at all. So the rebuild starts from 445 of the old 454, and **the 446 figure in the original
brief was 418 + 28 counting the DRHPs**. None of these numbers is 446-as-rebuilt, and the
gate must be reproduced on the check set, which contains none of the four.

## H53 — the committed READER_GATE.md was stale by one development step, and the rebuilt text cache is faithful

**Date:** 2026-11-02. **Context:** the macOS rebuild (Task 4). The brief required the
rebuilt cache to reproduce `reports/READER_GATE.md` exactly, and it did not.

### What the rebuild produced

| field | truth rows | produced | correct | precision | gate | baseline said |
|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 4 | 1 | 0 | 0.0% | **FAIL** | FAIL (2 truth rows) |
| `finance_costs` | 5 | 2 | 1 | 50.0% | **FAIL** | FAIL (3 truth rows) |
| `net_worth` | 4 | 1 | 1 | 100.0% | PASS | PASS (3 truth rows) |
| `shares_outstanding_pre_issue` | 6 | 5 | 5 | 100.0% | PASS | PASS (4 truth rows) |
| `tax_expense` | 2 | 1 | 1 | 100.0% | PASS | **FAIL, `nan%`** (2 truth rows) |

### The cache is not the problem — proven twice

**1. The gate at the parent commit reproduces the parent commit's report byte-for-byte.**
Running `rhp_reader_gate.py` with `6434b2c`'s reader and truth set, over the cache built
on macOS on 2026-11-02, gives:

| file | committed at 6434b2c | rebuilt-cache run |
|---|---|---|
| `READER_GATE.md` | `d179db3f8197bca29b1540e1224b9f324f01abc8` | `d179db3f8197bca29b1540e1224b9f324f01abc8` |
| `READER_GATE.csv` | `4fb70704838031f2dcdc67bcf180733a7893f81b` | `4fb70704838031f2dcdc67bcf180733a7893f81b` |

Identical. A cache whose text had drifted could not do this: the report quotes the
extracted lines verbatim, down to the broken digits in `9 36.80`.

**2. Every hand-read line is in the rebuilt cache.** All 124 `status = value` rows of
`reports/rhp_check_set.csv` carry a printed page and a quoted line, transcribed by hand
from the document. Each one is present in the rebuilt cache at that page:

| document | hand-quoted lines | found in the rebuilt cache |
|---|---|---|
| Computer Age Management Services Ltd | 15 | 15 |
| Craftsman Automation Limited | 15 | 15 |
| Global Health Limited | 18 | 18 |
| Likhitha Infrastructure Ltd | 11 | 11 |
| Polycab India Ltd | 47 | 47 |
| Prince Pipes and Fittings Ltd | 13 | 13 |
| Vishwaraj Sugar Industries Ltd | 5 | 5 |
| **TOTAL** | **124** | **124** |

A literal substring test scores this 96.8%, not 100%. The eight shortfalls are all in the
transcription, not the cache: the human wrote `Rs` for `₹` and `[*]` for `[●]`, joined
several printed lines with ` / `, and silently closed line wraps — the document prints
`Not` and `Applicable` on separate lines, and `at a` / `price of` likewise. Every figure
is there. The comparator was wrong, not the text.

### What was actually stale

`READER_GATE.md` as committed at `c11e45c` equals **`c11e45c`'s reader run against
`6434b2c`'s truth set** — byte for byte, in every row and every withheld reason, with one
exception. `c11e45c` added 36 truth rows (Craftsman Automation and Global Health, the
"two more documents transcribed" of its own commit message) and rewrote `rhp_readers.py`
by 554 lines, but the report committed beside them was generated before the truth rows
were appended. Hence 14 truth rows in the report against 21 in the file: the missing 7 are
exactly Craftsman's 3 and Global Health's 4 gradeable fields.

The one remaining cell is Polycab India's `tax_expense`. The committed report withholds it
with `row not present on the page`; the same reader on the same cache now returns 2,055.96
as `ok (derived)`, which is the truth value, from `Profit before tax 5,764.10` less
`Profit for the year 3,708.14`. That is the PBT-less-PAT fallback this very commit was
named for ("Task 3: tax from PBT less PAT"). So the report predates the fallback as well:
it was generated mid-commit, after the reader stopped accepting the `Total tax expense
763.86` line that `6434b2c` read, and before the fallback that replaced it worked.

### Decision

1. **`reports/READER_GATE.md` and `.csv` are regenerated and the new ones are
   authoritative.** They are the first run of the committed reader against the committed
   truth set. The baseline is not a target to reproduce; it is an artefact of a report
   written before the inputs it was committed with.
2. **`tax_expense` now passes the gate at 100% precision** on one produced value, and
   `net_worth` passes on one. Both are thin: a 95% precision floor measured on a single
   value is a coin, not a gate. Three of five readers pass, two fail, and the binding
   number is still the one in H50 — recall is low because the readers withhold.
3. **A report is regenerated in the same step as the code or truth it scores, or not
   committed.** This one cost a full diagnosis to tell staleness from corruption, and the
   only reason it could be told apart was that the cache happened to be faithful.
4. **The text cache records the extractor's name but not its version** (`"extractor":
   "pdfplumber.extract_text()"`), and `requirements.txt` pins `pdfplumber==0.11.10` but
   not `pdfminer.six`, which does the extraction and is installed here at `20260107`.
   Drift was disproven this time by evidence, not by the pin. Recorded as a known gap:
   the cache cannot tell you what built it. Not changed in this session — the brief
   forbids changing pins silently.

### H53, appended 2026-11-02 — the extraction stack is pinned, and the cache records what built it

H53 §4 recorded that the cache could not say what produced it. Closed:

| library | role | was | now |
|---|---|---|---|
| `pdfplumber` | wrapper; page objects | `==0.11.10` | `==0.11.10` |
| `pdfminer.six` | **does the text extraction** | **unpinned** | `==20260107` |
| `pillow` | image decode; decides if a page is readable | unpinned | `==13.0.0` |
| `pypdfium2` | page rendering | unpinned | `==5.14.0` |
| `cryptography` | encrypted PDFs | unpinned | `==50.0.2` |

Every cache record now carries `lib_versions` for those five, and
`extract.textcache.lib_drift()` reports any cached document built with a different stack.
The 444 existing records were **backfilled**, not re-measured, and each says so in
`lib_versions_source`: all 444 were built in this venv on 2026-11-02 with `pip list`
unchanged, so the field is an assertion with a stated basis rather than a measurement.

`lib_drift()` **reports; it does not invalidate.** H53 proved a rebuild can be
byte-identical across a `pdfminer.six` change, so a version bump makes the cache
*unverified*, not wrong. Silently discarding 444 documents and 214k pages on a patch bump
would cost more than it protects. Six tests in `build_text_cache.py` cover this, including
one that fails if any cached document's stack differs from the installed one — verified to
fail by substituting `pdfminer.six 20250506`, which flagged 5 of the first 5 records.

### H57 — rule 3 was not enforced: `_verify_is_prospectus()` could not tell a DRHP from an RHP

**Date:** 2026-11-02. H52 predicted this in writing — "the guard cannot tell a DRHP from an
RHP and was never meant to" — and it turned out not to be hypothetical.

The marker test was `re.search(r"RED HERRING PROSPECTUS|PROSPECTUS", head)`, which matches
the phrase **inside** `DRAFT RED HERRING PROSPECTUS`. So for as long as the guard has
existed, a draft passed it.

**Found in the corpus:**

| company | pages | title line | where |
|---|---|---|---|
| Mahindra Logistics Ltd | 562 | `DRAFT RED HERRING PROSPECTUS \| Dated August 3, 2017 \| (This Draft Red Herring Prospectus will be updated upon filing with the RoC)` | already cached |
| Nippon Life India Asset Management Ltd | 466 | `DRAFT RED HERRING PROSPECTUS \| Dated August 18, 2017 \| (This Draft Red Herring Prospectus will be updated upon filing with the RoC)` | already cached |
| Supriya Lifescience Limited | — | `DRAFT RED HERRING PROSPECTUS` | **refused at the gate** on its first live run |

Supriya is not lost: its `rhp_sources` copy is a genuine 377-page RHP and is kept. Only
the fetch-log duplicate was a draft.

**The test is the TITLE LINE, by position, not a substring.** An RHP's own cover routinely
back-references the draft it was filed as — Computer Age Management Services' does. The
numbers decided the design:

| rule | documents flagged of 444 | genuine DRHPs among them |
|---|---|---|
| phrase anywhere in the first 4 pages with text | 37 | 2 |
| phrase anywhere in the first 6 lines | 3 | 2 |
| **whichever of DRAFT/RHP appears FIRST in the head** | **2** | **2** |

The first rule would have discarded 35 real RHPs, two of them in the check set. Rejecting
a genuine RHP is the expensive error, so position wins.

`UNCLEAR` is **not** a rejection: a scanned cover pushes the first text page to the table
of contents (Manoj Vaibhav Gems, Rossari Biotech), and those are still settled by the
marker and 100-page tests.

**Decisions**

1. `_title_kind()` is added to `fetch_rhp.py` and `_verify_is_prospectus()` refuses a DRHP.
   Eight tests in `restore_rhp_pdfs.py`, every fixture a real cover.
2. `data/rhp_doc_type.csv` records the classification for all 444 cached documents:
   **421 RHP, 14 PROSPECTUS, 7 UNCLEAR, 2 DRHP**, with `allowed_under_rule_3`.
   The 14 final prospectuses are permitted — rule 3 allows one where SEBI has no RHP,
   labelled, and they are now labelled.
3. **The two cached DRHPs are excluded from every reader run and every fit.** They are
   left on disk and in the cache, flagged, rather than deleted: deleting them would hide
   that they were ever admitted, and both are 2017 listings outside the 2019+ set.
4. Any later corpus addition is classified before use. A document whose type cannot be
   established is `UNCLEAR` and is not silently promoted to RHP.

### H54 — H43's P/B routes are restored into `derive_ratios.py`, and why 24 became 20

**Date:** 2026-11-02. **Context:** `data/valuation_ratios_h45.csv` carried
`ipo_pb_pre_issue` for **0 of 433** rows and `ipo_pb` for 7, against H43's 163 and 24.

### What was actually broken

Confirmed before changing anything. H45 rewrote the module and the new pre-issue route read:

1. `nav_pre_issue` — extracted `ok` for **0 of 450** companies. Every RHP prints `[*]`,
   because post- and pre-issue NAV depend on a price the book has not fixed (H48).
2. else `net_worth_fy1 / shares_outstanding_pre_issue` — **neither variable exists in
   `rhp_valuation_values.csv`.** Not empty: absent from the schema. The fallback could
   never fire, so the route was dead on both legs.

`nav_fy1`, which H43 used and which has an `ok` number for **203** companies, was dropped.
`git log -S'nav_fy1'` shows it only ever existed in `derive_pb.py` (commit `314a23c`,
2026-10-19) — H45's module never had it. Looking for net worth in the RHP was also an **H5
violation**: H5 says net worth comes from the aggregator and the master, which is exactly
where H43 got it (Chittorgarh).

### Restored precedence

**Pre-issue NAV:** stated `nav_pre_issue` → `nav_fy1` (flagged `nav_fy1_as_pre_issue`,
carrying H43's justification: the latest fiscal year's NAV per share **is** pre-issue book
value, struck before the offer by construction) → net worth ÷ pre-issue shares (flagged
`derived_pre_issue_nav`).

**Post-issue NAV:** RHP-stated → H48-derived share count → H43 method 3 on the RHP's stated
post-issue count. The last two differ only in where the share count comes from, which is
why they are worth cross-checking. Order is a declared constant `POST_PREFERENCE`, after
the first version of `reconcile_routes` picked `sorted(routes)[0]` — alphabetical, so
`h43_method3_rhp_shares` beat `rhp_stated_post_issue_nav`, the opposite of the precedence.

**Cross-check:** every available PAIR, not just the chosen one against the next. Over 5%
the ratio is NULL and all routes are logged. H43's two-sided share-count guard and H48's
share derivation are **imported, not copied** — a second copy would drift.

### Result

| ratio | H43 (`pb_ratios.csv`) | H45 before | after |
|---|---|---|---|
| `ipo_pb_pre_issue` | 163 | **0** | **183** |
| `ipo_pb` | 24 | 7 | **20** |

| method | rows |
|---|---|
| `nav_fy1_as_pre_issue` | 183 |
| `h43_method3_rhp_shares` | 14 |
| `rhp_stated_post_issue_nav` | 6 |
| `withheld_disagreement` | 1 |
| `none` (post-issue) | 412 |

Every one of H43's 163 pre-issue documents is still priced, plus 20 more.

### Why `ipo_pb` is 20 and not 24 — and why that is correct

H43's 24 included four documents whose post-issue share count came from **extractor
1.7.0**: Cochin Shipyard (135,936,000), Krystal Integrated (11,524,394), Salasar Techno
(13,277,300), Varun Beverages (284,622,187). Extractor **1.8.0 and 1.8.1 return
`not_found`** for three of them and **824,000** for Cochin Shipyard — which H43's own
two-sided guard rejects as *"IMPLAUSIBLE share count, TOO SMALL"*. `derive_ratios._wide()`
floors at 1.8.0 precisely to keep values the current readers refuse out of the ratios.

So these four are not lost coverage; they are H43 resting on numbers the extractor has
since withdrawn. The regression test asserts `ipo_pb_pre_issue >= 163` and full document
coverage against H43, and `ipo_pb >= 20` with this reason recorded beside it — **not**
`>= 24`, which would demand resurrecting refused values.

### The cross-check earned its place on the first run

**PNC Infratech Ltd**: the RHP's stated post-issue NAV gives P/B **2.00**, the derived
route gives **219.89** — a 99.1% disagreement. Withheld under rule 2, both logged. A
P/B of 220 is not a valuation, it is a unit error, and precedence alone would have
published the stated 2.00 without ever noticing the contradiction. `PSP Projects Ltd` is
the opposite case: two routes within 1.2%, stated chosen, agreement recorded.

`withheld_disagreement` is kept as its own method value rather than collapsed into `none`:
a document contradicting itself is a different fact from a document being quiet.

21 tests, every route exercised by a real case.

### H55 — a reader needs 10 correct values as well as 95% precision; below that the verdict is INSUFFICIENT

**Date:** 2026-11-02. **Context:** after H53 regenerated `READER_GATE.md`, three of the
five readers "passed" the 95% precision floor — on **1, 1 and 5** correct values. 100% of
one value is a coin landing heads.

**The rule.** A reader runs on all documents only if precision ≥ 95% **and** correct
values ≥ **10**. Otherwise the verdict is **INSUFFICIENT**, which is neither a pass nor a
reader defect: it says the check set has not yet earned an opinion. The minimum is tested
**before** precision, so the verdict names the real problem — calling an unmeasured reader
FAIL would blame it for the check set, and calling it PASS is what this decision exists to
stop. Only **correct** values count; withheld rows do not, however many there are.

**Effect — every verdict changes:**

| field | truth rows | produced | correct | precision | before H55 | after H55 |
|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 4 | 1 | 0 | 0.0% | FAIL | **INSUFFICIENT** |
| `finance_costs` | 5 | 2 | 1 | 50.0% | FAIL | **INSUFFICIENT** |
| `net_worth` | 4 | 1 | 1 | 100.0% | PASS | **INSUFFICIENT** |
| `shares_outstanding_pre_issue` | 6 | 5 | 5 | 100.0% | PASS | **INSUFFICIENT** |
| `tax_expense` | 2 | 1 | 1 | 100.0% | PASS | **INSUFFICIENT** |

**Not one of the five readers has been measured.** That is the honest state, and it was
hidden behind three PASS marks resting on seven values between them.

**The fix for INSUFFICIENT is transcription, not reader work.** 13 of the 20 check-set
documents have no ground truth at all; 124 truth rows cover 7 documents. Grading a reader
harder cannot manufacture the values to grade it on. `rhp_reader_gate.py` exits non-zero
unless every reader PASSES — INSUFFICIENT is not a pass, so no reader runs on 442
documents on the strength of a single value.

Ten tests, including the 9-vs-10 boundary, the 19-correct-1-wrong case that is exactly
95.0%, and a check that withheld rows cannot pad the minimum.

### H56 — the two choices H35's spec left open, decided by the user BEFORE the run

**Date:** 2026-11-05. Recorded **before** `run_h35.py` existed, so neither choice can
have been picked to suit a result. `reports/H35_OPEN_CHOICES.md` set out the options.

**Choice 1 — missing values: OPTION B is binding.** Average the z-scores that are present,
all six signed hotter = higher. `listing_gain_minus_sector_day` is extracted for 288 of the
491 rows with a corrected 1y target (58.7%); complete cases are 284 of 491, and the gap is
concentrated in 2012-2015, where criterion 2 counts *test years*. B keeps every test year,
so criterion 2 measures what it was written to measure.

**Option A (complete cases) is a DIAGNOSTIC ONLY and cannot change the verdict.** It is
reported beside B. If A and B disagree, that disagreement is a finding about robustness; it
does not overturn B. This asymmetry is fixed here, in advance, for the same reason H35
itself was: a tie-break chosen after seeing two numbers is not a tie-break.

**Choice 2 — tercile cut-offs: the training fold only.** Consistent with H35's own in-fold
standardisation rule. Cutting on pooled test rows would use test-period information to
define the bands, which is the leakage the walk-forward exists to prevent; cutting within
each test year forces a third into each band every year and answers a different question.

**Unchanged and not open to interpretation:** the six variables, equal weights, no fitted
coefficients, scheme C (expanding) with the Y-2 embargo, and the three pass criteria.

#### H56, result — H35 FAILS on both targets. Nothing is wired.

Run 2026-11-05 by `run_h35.py` (38 self-tests, written test-first). Full tables in
`reports/H35_RESULT.md`.

**excess_1y, option B (binding).** 491 IPOs, 198 beat the TRI (40.3%). 427 test rows
scored, coolest 90, hottest 232.

| tercile | n | % beat Nifty | mean excess_1y | median |
|---|---|---|---|---|
| COOLEST | 90 | **51.11** | 16.82 | 1.28 |
| MID | 105 | 50.48 | 12.84 | 0.45 |
| HOTTEST | 232 | **36.64** | 2.10 | -14.26 |

| criterion | required | achieved (B, binding) | achieved (A, diagnostic) | |
|---|---|---|---|---|
| coolest − hottest, pooled | ≥ 10pp | **14.47pp** | 16.57pp | **PASS** |
| sign holds across test years | ≥ 75% | **33%** | 29% | **FAIL** |
| one-sided two-proportion test | p < 0.05 | **0.00883** | 0.02029 | **PASS** |

**excess_3y (secondary), option B:** coolest 44.30%, hottest 39.25%; gap 5.05pp, sign
agreement 50%, p 0.24466 — **all three fail**.

**Verdict: FAIL on excess_1y and on excess_3y. No market-heat line is added to any
report, and nothing is wired.** H34 was a fail, H29 was a fail by under 1pp, and H35 is a
fail. Option A agrees with option B on every criterion, so the H56 choice did not decide
the outcome.

### What failed, and why it is the interesting part

The pooled contrast is **large and significant**: coolest third beats the index 51.1% of
the time against 36.6% for the hottest, p = 0.0088. Criterion 1 and criterion 3 both pass
comfortably. **Criterion 2 kills it: only 3 of 9 measurable test years agree in sign.**

That is criterion 2 working exactly as intended. The pooled gap is mostly a
**between-year** effect — hot vintages as a whole did worse — and almost not a
within-year one. Year by year the sign flips: 2018 +50pp, 2019 +75pp, but 2012 −75pp,
2020 −62.5pp, 2017 −20pp, 2023 −7pp.

**A structural note, recorded because it constrains any future attempt and not as an
argument against this verdict.** Under H56's in-fold tercile cuts, a uniformly hot year
lands wholly in HOTTEST: 2021 scored 0 coolest against 59 hottest, 2024 0 against 69, and
2013/2015/2016 had no hottest rows at all. Five of fourteen test years therefore
contribute nothing to criterion 2, and the pooled arms are built largely from different
years. So criterion 1 (pooled) and criterion 2 (within-year) are close to measuring
opposite things under these cuts, and a design that satisfies both would need per-year
cuts — which H56 rejected, for the good reason that per-year cuts answer a different
question. H35 as written cannot pass on a cross-year effect alone. That is a fact about
the test, decided in advance, and the verdict stands.

**What this closes.** Both the per-IPO claim (H29, AUC 0.5338) and the coarser cohort
claim (H35) have now been measured against bars set in advance, and both failed. Model H
remains **display-only** and there is no market-heat statement to display either.

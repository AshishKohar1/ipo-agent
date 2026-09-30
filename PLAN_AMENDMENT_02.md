# PLAN Amendment 02 — decisions of 2026-10-01

Supersedes the named sections of `PLAN.md`. Merge in place, record each decision in
`DECISIONS.md` dated today, then continue under the stage protocol.

---

## A. Model L — final scope

**Decision H1 — one model only.** Build and maintain **`L_final_3pm`**. `L_day1`, `L_day2`
and the final-day forecaster are **cancelled**: no permitted source publishes day-wise
subscription history (Chittorgarh shows it live and deletes it once an IPO closes; IPO Ji
blocks Anthropic crawlers by name; InvestorGain, ipoindex.in and iporupee.com prohibit
scraping in robots.txt or terms). Stage 4B's backfill is cancelled for the same reason.

**Decision H2 — feature set frozen at Set A.** `log1p(Total subscription)` + `log(issue
size)`. Nine literature-sourced candidates were tested out-of-sample on 624 mainboard
IPOs (2010–2026) and **all were rejected**:

| Candidate | Source | Result |
|---|---|---|
| QIB / HNI / RII split instead of Total | Dave 2022; ipotrack | AUC 0.8807 vs 0.8832 — worse |
| QIB added to Total | Dave 2022 | 0.8818 — worse |
| HNI added to Total | Dave 2022 | 0.8823 — worse |
| RII added to Total | Dave 2022 | 0.8826 — worse |
| log(offer price) | Navyatha 2022; Joshi 2026 | corr +0.010; AUC unchanged |
| Market IPO heat | Huang 2025; Lowry 2002 | corr +0.184; AUC 0.8815→0.8818, inside noise |
| Raw (untransformed) subscription | — | 0.8711 — worse; log confirmed |
| Sensex/Nifty on listing day | Dave 2022 | Not significant in source (p=0.404); post-bid, unusable |
| Lot size, employee subscription | Dave 2022 | Not significant in source (p=0.719, p=0.552) |

Rationale to record: Total subscription already aggregates every investor category's
fundamental, sentiment and valuation view expressed in money. Re-adding the components is
double-counting, and Total's VIF reaches **90.0** when combined with them — which is the
source of Dave (2022)'s nonsensical negative coefficients (reproduced on our data: Total
+26.26, QIB −5.25, HNI −3.04).

**Decision H3 — demand profile is displayed, never modelled.**
`retail_skew = log1p(RII) − log1p(QIB)`. Measured on 624 IPOs:

| Quartile | Median listing gain |
|---|---|
| Most institution-skewed | **+20.4%** |
| Q2 | +4.1% |
| Q3 | +2.2% |
| Most retail-skewed | **+1.6%** |

Real signal, but adding it to the model changes nothing (AUC 0.8832 → 0.8811) because it
is already embedded in Total. It therefore appears in the live report as
`Demand profile: institution-led | balanced | retail-skewed` (quartile cut-points fitted on
training data only) and **never** as a feature or a verdict override.

**Decision H4 — correction to the record.** An earlier note claimed issue size had
"flipped sign" versus the literature. On 624 mainboard IPOs 2010–2026, controlling for
subscription, the standardised coefficient is **−0.356** — slightly negative, consistent
with Bansal & Khanna (2012) and Huang (2025). The earlier claim came from a 588-row
SME-heavy 2025–26 sample and did not generalise. The effect is small either way.

---

## B. RHP extraction — restructured

**Decision H5 — aggregator-first for headline financials.** Stop extracting from the RHP
anything an aggregator already publishes. Those fields come from the aggregator and the
master dataset, with the RHP as the **verifying second source where found**. This satisfies
rule 2 properly, because the two are genuinely independent derivations.

Aggregator-first fields: issue size, fresh/OFS split, offer price band, P/E and P/B at
offer, EPS, RoNW, NAV, revenue, PAT, net worth, total borrowings.

**Decision H6 — RHP extraction refocuses on what nothing else publishes.** These are
Model H's actual differentiators and exist only in the prospectus:

- Related-party transactions as % of revenue
- Litigation: counts and ₹ quantum of the top 5, by category, against company, promoters,
  directors
- Customer concentration (top-10 %), geographic concentration, licence dependence
- Promoter experience (years), board size and independence ratio, KMP remuneration
- Auditor qualification / emphasis of matter
- Pre-IPO placement price and date; promoter holding pre and post issue; lock-in schedule
- Contingent liabilities as % of net worth
- Number of stated uses of proceeds; GCP as % of proceeds
- Anchor investor list, allocation, mutual-fund share, lock-in expiry dates
- MSCI six-key-issue governance capture: Ownership & Control, Board, Pay, Accounting,
  Business Ethics, Tax Transparency

Coverage is measured **on these fields**, not on the headline financials. Target ≥60%.

**Decision H7 — provenance and refusal rules are unchanged and non-negotiable.** Every
extracted value carries page number, exact source text line, document URL, SHA-256 and
extractor version. Where the unit is not present on the page, the ₹-crore conversion is
**withheld**, not assumed. A doubtful value is deleted, never shipped.

**Decision H8 — never ingest AI-generated summary tables as data.** A comparison table
produced by a general web-search assistant was reviewed and rejected: Jupiter Life Line and
Syngene shared identical Net Worth (₹844.90 Cr) and Operating Income (₹871.60 Cr) across a
2023 hospital chain and a 2015 CRO; Syngene was listed as "100% OFS" while simultaneously
claiming capital-expenditure use of proceeds; TD Power's net worth equalled its issue size;
six values were marked approximate; no value carried a page citation. Such tables may be
used as a prompt for human cross-checking, never as a source.

Related: the ipotrack.in article "Using IPO Subscription Data to Predict Listing Day
Performance" is fabricated (Nykaa stated as 23× / +9.4% / 2022 against actual 81.78× /
+77.87% / 2021; "Jio Financial Services IPO" never existed — it was a demerger). Blacklist
it and treat unattributed AI-written SEO content as hostile to the dataset.

---

## C. Night-batch policy

**Decision H9.** Any task expected to exceed ~30 minutes runs as an unattended night batch:
chunked, checkpointed per item, committed at least every 10 items, resumable, and safe to
kill at any moment. Night batches are scheduled **immediately after** model-logic changes
in each session so they use the idle hours.

---

## D. Revised stage list

| Stage | Title | Type | Ends in |
|---|---|---|---|
| 14 | Apply Amendment 02 to PLAN/DECISIONS/CLAUDE | quick | — |
| 15 | **RHP extractor rebuild + night batch** | **NIGHT** | **Gate C2** |
| 16 | Finalise and freeze `L_final_3pm` | quick | **Gate B** |
| 17 | Aggregator-first financial backfill | **NIGHT** | — |
| 18 | Anchor / lock-in backfill from Chittorgarh | **NIGHT** | — |
| 19 | Productionise + go live | quick | — |
| 11–13 | Model H scorecard, hold sizing, integration | later | Gate E |

Cancelled: Stage 4B (day-wise backfill), Stage 5 (three decision-point models).

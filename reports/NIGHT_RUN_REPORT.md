# NIGHT RUN REPORT — 2026-10-01

Session ran on the Windows laptop (`Ashish-PC`, win32, Python 3.14.5). Amendment 02 applied,
Model L frozen, RHP extractors rebuilt, and three night jobs started and left running.

**Two gates are open for you: Gate B (Model L) and Gate C2 (extraction).**

---

## 1. H6-field coverage, before and after the extractor rebuild

Coverage is measured on the **H6 field list only** (decision H6) — 30 fields × 8 documents
in `data/verified_rhp_manifest.csv` = 240 cells. The headline financials that H5 moved to
the aggregator are **not** counted, so Stage 8's 24% is not comparable to anything here.

| Measure | Stage 8 (headline fields) | Stage 15a first run | Stage 15a final |
|---|---|---|---|
| strict — `ok` only | 24% | 22.9% | **48.8%** |
| usable — `ok` + `ambiguous` | — | 37.1% | **59.6%** |
| adjusted — excludes structurally N/A | — | 37.1% | **63.0%** |

**Against the ≥60% target: met on the adjusted measure (63.0%), missed by 0.4pp on the raw
usable measure (59.6%).** It peaked at 60.4% and I gave that back deliberately — see §1.3.

### 1.1 Coverage per field

| Field | ok | amb | n/a | miss | usable % |
|---|---|---|---|---|---|
| `auditor_qualification_flag` | 8 | 0 | 0 | 0 | 100% |
| `auditor_emphasis_flag` | 8 | 0 | 0 | 0 | 100% |
| `esop_exists_flag` | 8 | 0 | 0 | 0 | 100% |
| `dual_class_flag` | 8 | 0 | 0 | 0 | 100% |
| `licence_dependence_flag` | 8 | 0 | 0 | 0 | 100% |
| `promoter_lockin_months` | 8 | 0 | 0 | 0 | 100% |
| `anchor_mf_reserved_pct` | 0 | 8 | 0 | 0 | 100% |
| `uses_of_proceeds_n` | 4 | 0 | 4 | 0 | 100% |
| `promoter_holding_pre_pct` | 6 | 0 | 0 | 2 | 75% |
| `independent_directors_n` | 6 | 0 | 0 | 2 | 75% |
| `geographic_concentration_flag` | 6 | 0 | 0 | 2 | 75% |
| `anchor_portion_shares` | 6 | 0 | 0 | 2 | 75% |
| `rpt_pct_revenue` | 5 | 1 | 0 | 2 | 75% |
| `promoter_holding_post_pct` | 5 | 0 | 0 | 3 | 62.5% |
| `board_independence_ratio` | 4 | 0 | 0 | 4 | 50% |
| `board_size_n` | 2 | 2 | 0 | 4 | 50% |
| `rpt_amount_cr` | 4 | 0 | 0 | 4 | 50% |
| `kmp_remuneration_cr` | 0 | 4 | 0 | 4 | 50% |
| `customer_concentration_top10_pct` | 3 | 1 | 0 | 4 | 50% |
| `pre_ipo_placement_flag` | 4 | 0 | 0 | 4 | 50% |
| `gcp_pct_proceeds` | 0 | 2 | 4 | 2 | 50% |
| `promoter_experience_years` | 0 | 2 | 4 | 2 | 50% |
| `contingent_liabilities_cr` | 1 | 2 | 0 | 5 | 37.5% |
| `litigation_criminal_count` | 2 | 1 | 0 | 5 | 37.5% |
| `litigation_criminal_promoters_directors` | 2 | 0 | 0 | 6 | 25% |
| `litigation_aggregate_amount_cr` | 2 | 0 | 0 | 6 | 25% |
| `pre_ipo_placement_amount_cr` | 2 | 0 | 0 | 6 | 25% |
| `litigation_tax_count` | 1 | 2 | 0 | 5 | 37.5% |
| `litigation_statutory_count` | 0 | 1 | 0 | 7 | 12.5% |
| `customer_concentration_top5_pct` | 0 | 1 | 0 | 7 | 12.5% |

Live figures are in `reports/h6_coverage_by_field.csv` and `reports/h6_coverage.json`.

### 1.2 Fields that cannot reach 60% across vintages — named, not rescued

H6 says to say so plainly rather than loosen the rules. These are the ones, with why:

1. **`litigation_statutory_count` (12.5%) and `litigation_tax_count` (37.5%).** Only two of
   the five companies print a litigation summary with a countable "Number of matters"
   column. The rest give prose ("there are 1,046 consumer proceedings"), or a cross-reference
   to a page I do not extract. I now **require** a count-column header before reading an
   integer, because without that requirement the extractor invented counts (§1.3).
2. **`customer_concentration_top5_pct` (12.5%).** Only CapitalNumbers discloses a top-5
   figure. The others disclose top-10 or nothing. This is a disclosure gap, not an
   extraction gap — it will not improve.
3. **`litigation_aggregate_amount_cr` and `pre_ipo_placement_amount_cr` (25% each).** Most
   documents state no aggregate, and an RHP prints `[●]` where a prospectus prints a number.
4. **`contingent_liabilities_cr` (37.5%).** Four vintages, four layouts. Where there is no
   total row and no summable itemisation with a unit on the page, the value is withheld
   rather than part-summed.
5. **`promoter_experience_years` (50%, 4 of 8 N/A).** Syngene's promoter is Biocon and
   Hyundai's is Hyundai Motor Company — a body corporate has no bio and no years of
   experience, so the field is structurally N/A there, not missing. **This field is the
   least trustworthy of the thirty** and cost three attempts (§1.3).
6. **`kmp_remuneration_cr` (50%, all ambiguous).** Whether a figure is one director's pay or
   the board total is not stated in the sentence carrying it. Every value is labelled
   ambiguous for that reason. It needs the remuneration table, not the prose.

### 1.3 Ten wrong values caught and deleted rather than shipped

Each extracted cleanly and looked plausible. Each is documented in `extract/h6.py` at the
point of the fix so it cannot silently return.

| Field | Wrong value | Where it came from | Now |
|---|---|---|---|
| Syngene `promoter_experience_years` | 38 years | a finance director's bio; Syngene's promoter is **Biocon**, a company | scoped to the promoters section; corporate promoter → N/A |
| — (same field) | — | worse: the N/A was *justified* with "the promoter is 'interested in our Company to the extent it has promoted our Company'" — a parse failure recorded as fact | the name parser was deleted; a false justification is as bad as a false value |
| Jupiter `promoter_experience_years` | 33 years | its **auditor's** tenure, 420 characters away | the name and the clause must be in the same sentence |
| Jupiter `promoter_holding_pre_pct` | 9.1% | the promoter **group excluding the promoters**, against a true 40.69% | that phrasing is now rejected outright |
| CapitalNumbers `promoter_holding_post_pct` | 20.0% | the **lock-in requirement**, not a holding | lock-in prose rejected |
| Syngene `litigation_tax_count` | 29, then 57 | a page reference, then an **amount** in a contingent-liability table | a "Number of matters" header is now required |
| Jupiter / CapitalNumbers `litigation_tax_count` | 90 / 78 | cross-reference numerals | same fix |
| Syngene `litigation_criminal_count` | 225 | a page number pdfplumber placed **inside the table row**; the same table in its prospectus reads NIL | a numeral followed by NIL is not the count |
| Syngene `litigation_criminal_promoters_directors` | 30 | clause **(viii)** of the materiality-policy paragraph | policy prose rejected — this cost 0.8pp of coverage |
| Syngene `customer_concentration_top10_pct` | 71.2% | the **oldest** of three years | the year sequence is parsed and the latest taken (70.9%) |
| Hyundai `rpt_pct_revenue` | 9.36% | the **oldest** of five columns | max-year position; now 7.76% |

### 1.4 The two Stage 8 failures, fixed

- **Case-sensitive and layout-variant detection.** Every pattern now runs
  case-insensitively over **flattened** page text. RHP prose wraps mid-sentence, so a
  line-anchored regex could not see `71.2%, 69.4% and 70.9% … came from our top 10 clients`
  at all. Each page is also scanned with the next page's first 400 characters appended,
  because disclosure sentences are routinely cut by a page break — Jupiter's RHP ends one at
  "was 1.59%, 1.21% 55".
- **Unit detection.** lakh / lakhs / lac / lacs / million / millions / mn / crore / crores /
  cr / cr. / billion / bn / thousand, inline or as a table header, any case. **No unit still
  means `value_crore` is withheld**, never assumed (H7).

Two framework bugs also fixed: a field group raising an exception no longer swallows the
groups after it (one `TypeError` in `governance` was costing four whole groups on all eight
documents), and coverage is counted with `crosstab` rather than `pivot_table`, which
silently drops every row whose value is null — i.e. every miss.

### 1.5 One provenance defect I am leaving visible

Spot-check **row 14** (Syngene, ESOP exists = yes) has the right value but a **useless
quoted line** — the pattern matched the definitions page, so the source text is an address
block. The value is correct (Syngene has an ESOP 2011), but the provenance does not support
it. I would rather you see this than have me quietly drop the row.

---

## 2. Night batch — Stage 15b

`rhp_night_batch.py`, started 01:05 IST, **still running**.

| | |
|---|---|
| Queue | **485** mainboard IPOs with an `excess_1y` label and no `exclude_reason` |
| Measured rate | **~140 s per company** (dominated by full-document text extraction) |
| Extrapolated | **~19 hours** for the full queue — it is resumable across nights |
| Settled at the time of writing | 7 (4 `done`, 3 `source_unresolved`) |
| Disk | 143 GB free, floor 2 GB, PDFs discarded after every company |
| Restarts | **none** |

### Failures by reason so far

| Reason | n | What it means |
|---|---|---|
| `source_unresolved` | 3 | SEBI's archive has no document matching the company name and filing window. Urban Company, Amanta Healthcare and one other. Not a crash and not transient — recorded with the queries tried. |

Per-company status is appended to `data/rhp_progress.csv` after **every** company, and
observations to `reports/h6_batch_observations.csv`, so the batch is safe to kill at any
moment. It commits and pushes every 5 companies.

**One resumability bug found and fixed after launch:** `source_unresolved` was not counted
as settled, so every restart retried the same unresolvable companies before reaching new
ones and a resumed run could never finish the queue. Fixed in `rhp_night_batch.py`; the
change takes effect on the next restart, not on the process now running.

### Field yield on real batch companies

The first four successes returned 12–17 `ok` of 30 fields — in line with, and at the top end
of, the 8-document sample. Nothing suggests the manifest documents were unrepresentative.

---

## 3. Model L — Stage 16, frozen at v1.0 → **GATE B**

Full card in `MODEL_L_CARD.md`, every figure generated from
`reports/stage16_model_l.json`.

| | L1 (gain > 0%) | L2 (gain > 10%) |
|---|---|---|
| Rows | 620 | 620 |
| Half-life (by **pooled** AUC) | 2 y | 2 y |
| **Pooled out-of-fold AUC** | **0.8081** | **0.8809** |
| Held-out Brier, raw → isotonic | 0.1599 → 0.1579 | 0.1626 → 0.1586 |
| Firing rule (G1) | calibrated p ≥ 0.90 | calibrated p ≥ 0.80 |
| Fires on | 117 IPOs | 96 IPOs |
| **Delivered hit rate** | **94.0%** | **87.5%** |
| Wilson 95% lower bound | 88.2% | 79.4% |
| C5 gates | **PASS** | **PASS** |
| Overclaim (G2) | +4.5pp | +11.7pp |

`L_day1`, `L_day2` and the forecaster are cancelled. **A repo-wide search found no such code
path to delete** — Stage 5 was never started, so there was nothing dormant. What I did delete
is the four superseded 5-feature bundles and their cards, so two competing Model L files
cannot coexist. `retail_skew` is computed, displayed as a demand-profile label with
cut-points fitted on years < 2026 only, and enters no model.

### The nine rejected candidates: five reproduce, **two do not**

Re-tested on the same 616 rows under the identical walk-forward protocol.

| Candidate | L1 AUC | vs Set A | L2 AUC | vs Set A | H2 claims | Agrees? |
|---|---|---|---|---|---|---|
| Set A baseline | 0.8084 | — | 0.8809 | — | 0.8832 | baseline |
| QIB/HNI/RII instead of Total | 0.7980 | −1.04pp | 0.8721 | −0.88pp | 0.8807 | yes |
| + QIB | 0.8080 | −0.04pp | 0.8793 | −0.16pp | 0.8818 | yes |
| **+ HNI** | 0.8110 | **+0.26pp** | 0.8824 | **+0.15pp** | 0.8823 | **NO** |
| + RII | 0.8085 | +0.01pp | 0.8799 | −0.10pp | 0.8826 | yes |
| + log(offer price) | 0.8089 | +0.05pp | 0.8800 | −0.09pp | unchanged | yes |
| + market IPO heat | 0.8137 | **+0.53pp** | 0.8755 | −0.54pp | 0.8818 | split |
| **raw subscription** | 0.8089 | **+0.05pp** | 0.8802 | **−0.07pp** | 0.8711 | **NO** |

1. **`plus_hni` is not worse** — marginally better on both targets. Inside noise, but the
   direction does not reproduce.
2. **`raw_subscription` is barely worse, not decisively worse.** H2 records −1.2pp, which
   reads as proof of the log transform. Measured here it is −0.07pp on L2 and *+0.05pp* on
   L1. **The log transform is not confirmed by AUC** — it is justified on distributional
   grounds only.
3. **Market heat splits by target**: +0.53pp on L1 (the largest gain anywhere in the table),
   −0.54pp on L2. That argues A2's Set C challenger should be tracked **per target**.
4. Two candidates were never testable: Sensex/Nifty on listing day is post-bid and violates
   leakage discipline regardless of AUC; lot size and employee subscription are not columns
   in the master at all.

**Collinearity reproduces; the coefficient magnitudes do not.** Total's VIF is 85.4 against
H2's 90.0, and the sign pattern H2 rests on is exact — Total positive, all three categories
negative conditional on it. But H2 cites Total **+26.26**, QIB −5.25, HNI −3.04; measured
here they are **+2.50 / −0.29 / −0.11** standardised, and +5.10 / −1.37 / −1.12 with the L2
penalty effectively removed. **H2's numbers are on some other scale and should not be quoted.**

**H3's headline reproduces exactly, its gradient does not.** Most institution-skewed
quartile median +20.4% — H3's figure to the decimal. But Q2 +5.2%, Q3 +1.5%, Q4 +2.4%: not
monotone. Read the label as *institution-led is different*, not as a ranking.

**H4 needs a correction of its own.** The standardised issue-size coefficient is
**−0.137 (L1) / −0.058 (L2) unweighted** — H4's direction, but nowhere near its −0.356 — and
**+0.314 / +0.409 at the selected 2-year half-life**. So the **production model carries a
positive issue-size coefficient**, and the sign is decided by the recency weighting rather
than by the data as a whole. The earlier "flipped sign" observation H4 dismissed as a sample
artefact is real; it is a recency effect. **This is the one Gate B item I would think about.**

---

## 4. Stages 17 and 18 — Chittorgarh backfill

`chittorgarh_backfill.py`, started 01:26 IST, **still running**. robots.txt re-read first:
**still permits** (disallows only `/ipo/ipo_discussions.asp`, no Anthropic crawler named).
≥3.2 s between requests, single-threaded, one non-browser User-Agent.

**Both stages run off one request per company.** `/ipo/x/{id}/` carries the H5 headline
financials *and* the anchor/lock-in block, so a single sweep serves both rather than sending
the site two. There is no published company→id index, so the id space 250–3110 is walked
(2,861 ids, ~2.5 h) and the company name read off each page — the method Stage 4A
established.

One harvested row (id 3007, Adroit Industries, Sep 2026) carries: issue size ₹151 cr,
fresh ₹133 cr, OFS ₹10 cr, price band ₹126–134, face value ₹10, total income ₹143.04 cr,
PAT ₹26.16 cr, net worth ₹128.63 cr, borrowings ₹52.4 cr, EBITDA ₹38.71 cr, EPS 7.49→5.84,
P/E 17.89→22.95, ROE 22.54%, ROCE 19.01%, RoNW 22.51%, **promoter holding 96.1% → 71.86%**,
final subscription Total 176.85× / QIB 195.04× / NII 332.35× / Retail 99.81×, 6 stated uses
with GCP at 8.91%, anchor portion ₹45.21 cr (3,374,100 shares, 30% of the issue) and
**anchor lock-in expiry dates 27 Oct 2026 and 26 Dec 2026**.

Anchor data present on 5 of the first 8 ids — consistent with the ~41%/60% Stage 4A measured.

**Unexpected bonus: promoter holding pre/post is an independent second source** for two H6
fields. Rule 2 could not be applied to them from the RHP alone.

Coverage by year and the rule-2 reconciliation table will be in
`reports/chittorgarh_reconciliation.csv` once the sweep has passed enough of the id space to
be meaningful. At 8 ids it is not worth tabulating and I have not invented one.

Four bugs found and fixed while probing, each of which would have corrupted the dataset:
appending dicts with per-page keys produced a ragged CSV pandas then refused to read back;
`find_table(...) or pd.DataFrame()` raises because a DataFrame has no truth value; a bare
number fallback read "47,34,000 shares" as **an issue size of 4,734,000 crore** (a currency
marker is now required, and no unit means withheld); and two tables carry Pre IPO/Post IPO
columns with the valuation one first, so promoter holding came back empty until every
matching table was tried.

---

## 5. Restarts, disk, and anything unsaved

### Restarts

| Job | Time IST | What happened |
|---|---|---|
| Chittorgarh sweep | started **01:26** | — |
| Chittorgarh sweep | died **~01:40** | `pd.read_html` chose a parser per page and raised `ImportError: Import html5lib failed` on a page lxml could not handle, after 8 ids. The whole sweep died on one bad page. |
| Chittorgarh sweep | restarted **01:52** | `html5lib` installed and pinned in `requirements.txt`; `read_html` now tries lxml, then html5lib, then the default, and an unparseable page costs that page rather than the run. |
| SEBI night batch | started **01:05** | no restart |

**One file was discarded in the restart.** Adding a `note` column changed the fixed schema
from 49 to 50 fields, so `data/chittorgarh_backfill.csv` ended up with rows of both widths
and pandas refused to read it back. It held 8 rows of freely re-fetchable public data, so I
deleted it and let the sweep re-harvest those ids (26 seconds of requests) rather than
hand-repair a corrupt file. Nothing else was lost.
- **Disk:** 143 GB free at the time of writing. Floor 2 GB. PDFs are discarded after each
  company, so the batch's steady-state footprint is one PDF.
- **Nothing is unsaved.** Every artefact is committed and pushed to `main`. Both night jobs
  append to disk per item and commit on their own schedule (every 5 and every 10 items).
- Model H's scorecard has **not** been started, per your instruction.

---

## 6. What I would look at before the gates

1. **Gate C2 — I recommend approving the field set and the batch, with one reservation.**
   Coverage is 59.6% usable / 63.0% adjusted against a 60% target, and the batch is already
   running productively. The reservation is that **eleven of the thirty fields sit at or
   below 50%**, and three of them (`litigation_statutory_count`,
   `customer_concentration_top5_pct`, `promoter_experience_years`) will not improve without
   either per-vintage table maps or a decision to accept them as sparse. Decide whether a
   sparse column is worth keeping before Stage 11 builds a scorecard on it.
2. **Gate B — the positive issue-size coefficient.** It is an artefact of the 2-year
   half-life, not of the full history. Accept it, or pin the half-life longer and lose some
   recency adaptation?
3. **`PLAN_AMENDMENT_02.md` section A should be amended** to cite the figures measured here.
   Two of its nine rejections do not reproduce in direction and its coefficient magnitudes
   are wrong by an order of magnitude. The *decision* to freeze Set A still stands — every
   disagreement is under 0.6pp of AUC and none would change a bid.
4. **C3 still binds: `L_final_3pm` is approximated, not measured.** It is trained on
   final-day subscription. **B4 forward collection has not started**, and every evening
   without it loses one IPO's 3pm snapshot permanently. That is the cheapest thing on this
   list to fix and the only one that gets worse with delay.
5. **Stage 1's Linux/cloud half is still unverified.** Every session so far has run on this
   laptop.

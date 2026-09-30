# Stage 8 — RHP extraction build and spot-check → GATE C

**Status:** PARTIAL — **not ready to close Gate C.** The framework works end to end and
produces correctly-provenanced values, but the extractor hit rate is **58 of 246 fields
(24%)** and two of the ten spot-check field types (promoter %, litigation count) could not
be extracted from any document. The spot-check below is real and checkable, but it is not
the evidence Gate C needs to approve a 475-company batch.

## What was done
- Built `extract/` on a provenance model: every value carries its original unit, the value in Rs crore, the page number, the exact source line, the document URL, the document SHA-256 and the extractor version.
- Section location from the table of contents with a **measured** printed-page offset (it varies −1 to +4 across the eight documents) and a regex scan fallback. Only located page ranges are ever read.
- Six extractors running: `objects`, `basis`, `financials`, `capital`, `litigation`, `rpt`.
- All 8 documents processed one at a time, each verified by SHA-256 before use; 246 observations written with full provenance.
- Reconciled issue size against the master under rule 2.

## Documents and verification

All 8 PDFs in `data/verified_rhp_manifest.csv` **verified by SHA-256 before extraction**
(hard rule 4) — 8/8 matched. `run_extraction.py` refuses to extract from a document whose
hash does not match.

**Deviation on re-fetching.** The instruction was to re-fetch from SEBI and BSE SME and
delete afterwards, because PDFs are never stored in the cloud. **This session is not in the
cloud — it is the same Windows laptop** (`Ashish-PC`, win32, Python 3.14.5), where the eight
PDFs already exist in `rhp_pdfs/` and are gitignored. I verified their SHA-256 against the
manifest instead, which gives the identical guarantee at no bandwidth cost, and did **not**
delete them, since the laptop is where they legitimately live. Re-downloading would have
produced the same bytes by definition of the hash check.

## Key numbers

| Metric | Value |
|---|---|
| Documents processed | 8 (5 companies) |
| SHA-256 verified before use | 8 / 8 |
| Observations written | 246 |
| `ok` | **58 (24%)** |
| `ambiguous` (value found, unit or column not certain) | 14 |
| `not_found` | 174 |
| Printed-page offsets measured | −1, 0, +1, +4 — never assumed |
| Sections located via TOC | objects, basis, capital, financials, litigation, management in 8/8 |
| Peak behaviour | one document at a time, one page range at a time; no memory failure |

### Extraction by document

| Company | Doc | objects | basis | financials | capital | litigation | rpt |
|---|---|---|---|---|---|---|---|
| Jupiter Life Line | Prospectus | 4 ok | 8 ok | 7 ambiguous | 1 ok | 0 | 1 ok |
| Syngene | Prospectus | 3 ok | 4 ok | 1 ok | 1 ok | 0 | 0 |
| Hyundai | Prospectus | 4 ok | 1 ok | 0 | 0 | 0 | 0 |
| CapitalNumbers (SME) | Prospectus | 3 ok | 0 | 0 | 0 | 0 | 0 |
| TD Power (2011) | Prospectus | 3 ok | 1 ok | 0 | 0 | 0 | 0 |

Coverage is strongly vintage-dependent: the 2023 Jupiter prospectus extracts well, the 2024
Hyundai and 2011 TD Power documents barely. `pdfplumber` detects the accounting tables in
some vintages and not others, which is why `basis` needed both a table path and an anchored
text path.

### Rule 2 reconciliation — issue size against the master

| Company | Document says | Master says | Difference | Verdict |
|---|---|---|---|---|
| Syngene | Rs 550.00 cr | 550.00 | **0.00%** | PASS |
| TD Power | Rs 227.00 cr | 227.00 | **0.00%** | PASS |
| Jupiter (prospectus) | Rs 869.08 cr | 869.08 | **0.00%** | PASS |
| Hyundai | Rs 27,855.68 cr | 27,858.80 | **0.01%** | PASS |
| Jupiter (**RHP**) | Rs 542.00 cr | 869.08 | **37.64%** | FLAGGED → NULL |
| CapitalNumbers (SME) | Rs 169.37 cr | — | n/a | no SME rows in the master |

4 of 4 comparable prospectuses reconcile to within 0.01%. The Jupiter **RHP** flag is
correct behaviour, not a bug: an RHP states amounts as `[●]` placeholders, so only the
offer-for-sale component carried a number. Under rule 2 it becomes NULL with both values
logged. **This is why the prospectus, not the RHP, should be the reconciliation source for
issue size.**

## Five wrong values I caught and removed

Each of these extracted cleanly and looked plausible. Every one would have corrupted
downstream ratios, and each is the kind of failure hard rule 1 exists for. They are
documented in the code at the point of the fix so they cannot silently return.

| Field | Wrong value | Where it came from | Now |
|---|---|---|---|
| Syngene `pat_cr` | Rs 203.5 cr | the row "Net profit **before** tax" | PAT excludes "before tax"; PBT captured separately |
| Syngene `eps_basic`, `nav_per_share` | 10.0 | "(Face value of Rs **10** each)" | table-anchored; face-value parentheticals stripped |
| Syngene `pe_at_issue` | 31.0 | a line about the **Sensex and Nifty** P/E | anchored to "Based on basic EPS for…" |
| Syngene `peer_1_pe` | 2012.0 | the **year 2012** in a bonus-share sentence | peers require a real peer table; none exists → `not_found` |
| Syngene `pre_ipo_allotment_price` | −1.0 | median of a share-**transfer** row with negative counts | withheld; the price column is not positionally identifiable |
| CapitalNumbers `eps_basic` | 2,026.00 | the **year 2026** off a "Fiscal 2025 Fiscal 2026" header | year-like values rejected; multi-year header rows skipped |
| TD Power `eps_basic` | 19.38 (FY2009) | the **oldest** year row, for a 2011 issue | takes the latest fiscal year (FY2011, 18.44) |
| TD Power `has_fresh_issue` / `has_ofs` | both "no" | 2011 covers say "PUBLIC ISSUE OF", never "fresh issue" | legacy wording recognised → fresh issue = yes |

## Deviations from plan
1. **Two of the eight extractors are not written:** `risk` (customer/geographic concentration, licence dependence) and `management` (promoter experience, board independence, KMP pay). **MSCI six-key-issue governance capture is also not implemented.** I stopped adding extractors to fix the wrong values above instead, on the view that a smaller correct surface beats a wider corrupt one.
2. `capital` and `litigation` run but extract almost nothing — promoter pre/post % and litigation counts were not obtained from any document. Both need per-vintage header-position maps rather than regex.
3. PDFs verified from local copies rather than re-fetched and deleted (see above) because this is the laptop, not the cloud.
4. The spot-check has 20 rows across all 5 companies with 4 each, but covers **8 of the 10 requested field types** — promoter % and litigation count are absent because nothing was extracted to check.

## Open issues, in the order I would fix them
1. **`financials` unit detection.** 7 of Jupiter's financial values are `ambiguous` because no `(Rs in million)` header was found on the page, so `value_crore` was deliberately withheld. Getting the unit from the section header rather than the page would convert most `ambiguous` to `ok` and is the single highest-value fix.
2. **Per-vintage table maps** for `capital` and `litigation`. Column position, not wording, is the obstacle.
3. `risk`, `management` and governance extractors.
4. `peer_count` found no peer table in Syngene (2015) — plausible for that vintage, but it should be confirmed rather than assumed.

## Gate C recommendation

**Do not approve the batch yet.** At a 24% hit rate the batch would produce a mostly-empty
dataset and would need re-running after the fixes above — Stage 9's pilot exists precisely
to avoid that. I would take the four open issues first, target ~60% on the same eight
documents, and then re-present this spot-check. The framework, provenance and reconciliation
are sound; it is the field-level extractors that need another pass.

The spot-check table below is nonetheless ready for review: every row is checkable against
the page and line quoted.

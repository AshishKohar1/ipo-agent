# Task 5 — RHP pipeline: page index, master pass, transcription, H55 gate (2026-11-09)

## 1. The page index — `data/rhp_page_index.csv`

`rhp_pages`' content finders swept over all 445 cached documents. 6,166 rows: the best
five candidate pages per kind, each with its score and the basis the page states. Nothing
is extracted here — the index says WHERE to look, so a reader never rescans a 500-page
document.

| kind | documents with a hit | median page |
|---|---|---|
| `profit_loss` | 444 | 85.5 |
| `balance_sheet` | 439 | 81 |
| `capital` | 435 | 85 |
| `nav` | 377 | 201 |

A weakness worth recording: the index's rank-1 `profit_loss` page for Bansal Wire is PDF
page 322, a CSR note whose table scores as well as a statement. The real restated P&L is
rank 2, page 89. Rank 1 is a candidate, not an answer, which is why the index keeps five.

## 2. The 13 untouched check-set RHPs — transcribed

142 rows added; the check set is now **281 rows over 20 companies**. Every value carries
its unit, basis, page and the quoted line. Column-to-period mapping was read off each
page's own header; where a row wrapped or a header was unreadable the field was **skipped**
rather than guessed — Godavari's tax (only an MD&A percentage table, not the restated
statement), ACME's tax, Antony's depreciation.

Cross-checks that fell out of the transcription itself:

| check | result |
|---|---|
| Borana: share capital + other equity | equals the printed `Total Equity [A]` in every column |
| Cello FY2023: 975.00 + 2,389.50 | equals the printed *Total equity attributable to owners* 3,364.50 |
| IRM FY2023: 302.60 + 3,161.63 | equals the printed *attributable to equity holders* 3,464.23 |
| Bansal: 127,454,390 x Rs 5 | 637,271,950 = share capital 637.27 million |
| GNG x Rs 2, IRM x Rs 10, Godavari x Rs 10, Antony x Rs 5 | each reproduces the printed share capital |

Where a company has non-controlling interests the transcribed net worth is **share capital
plus other equity**, which is the convention the existing Polycab rows use and which three
of these documents print under their own name. It is NOT the printed `Total equity`, and
they differ: Bansal by 387.70 million, CarTrade by 1,206.45, Route Mobile by about 23.

## 3. The H55 gate, re-run

| field | truth rows | produced | correct | precision | verdict |
|---|---|---|---|---|---|
| `shares_outstanding_pre_issue` | 13 | 12 | **12** | **100.0%** | **PASS** |
| `tax_expense` | 12 | 3 | 3 | 100.0% | INSUFFICIENT |
| `finance_costs` | 17 | 4 | 3 | 75.0% | INSUFFICIENT |
| `net_worth` | 16 | 3 | 2 | 66.7% | INSUFFICIENT |
| `depreciation_amortisation` | 15 | 2 | 1 | 50.0% | INSUFFICIENT |

**The first reader ever to clear H55.** The other four are no longer precision-bound; they
are **recall**-bound. The dominant withholding reason, 29 of 39: *"no profit-and-loss column
reproduces a stated EPS within 3.0% on the pre-issue share count"*.

## 4. A fix implemented, measured, and REVERTED

`read_document` returns early for all four money fields when no stated EPS can pin the
profit-and-loss column — which also withholds **net worth**, a field that needs only the
balance sheet and the anchor *net worth / shares = the stated NAV*. Bansal states a FY2024
NAV of 33.14 and 127,454,390 shares; the product is 4,223.9 million against a hand-read
4,223.70. Letting the net-worth block run anyway:

| | before | after |
|---|---|---|
| produced | 3 | 7 |
| correct | 2 | 3 |
| **precision** | **66.7%** | **42.9%** |

Right: Bansal 4,223.70, IRM 3,464.23. Wrong: Delhivery 59,798.47, ACME 25,912.98,
Godavari 2,602.45, Route Mobile 2,681.94.

It is not a tolerance problem. All six state exactly **one** NAV for the target period and
every gap is under 0.11%. It is definitional: many RHPs strike their NAV on the **latest
balance sheet**, which is the stub period, so the anchor matches the stub column correctly
and returns a quantity the gate is not asking for. `target_period`'s own `how` does not
separate the cases either — Bansal (right) and ACME (wrong) both report *"dated NAV rows
whose month is the modal fiscal-year end (March)"*.

The brief said not to lower precision, so the route stays refused. The measurement is
recorded in `rhp_readers`' own self-test so it is not rediscovered.

## 5. The master pass — `data/rhp_master_values.csv`

445 documents, 2,225 rows. Values are written **only** for readers that passed the gate;
every other field is NULL with `status = reader_not_gated`, carrying no page, column, unit
or line either.

| field | ok | withheld by reader | reader_not_gated |
|---|---|---|---|
| `pre_issue_shares` | **387** | 58 | 0 |
| `net_worth` | 0 | 0 | 445 |
| `tax_expense` | 0 | 0 | 445 |
| `finance_costs` | 0 | 0 | 445 |
| `depreciation_amortisation` | 0 | 0 | 445 |

All 58 withholdings share one reason: *no ISSUED, SUBSCRIBED ... BEFORE THE OFFER line with
an Equity Shares count*.

### A caveat the gate cannot give you

100% precision on 12 check-set values is not 100% on 387. Running `derive_pb`'s own
two-sided plausibility guard over the sweep — reused, not reinvented — flags **5 of 387**:

| company | value | why |
|---|---|---|
| Apollo Micro Systems | 20,000 | too small: Rs 0.6 cr market cap against a Rs 156.0 cr issue |
| JSW Infrastructure | 24,750 | too small: Rs 0.3 cr against a Rs 2,800.0 cr issue |
| EMS Limited | 1,600,000 | too small: Rs 33.8 cr against a Rs 321.2 cr issue |
| Rossari Biotech | 10,500,000 | too small: Rs 446.2 cr against a Rs 496.2 cr issue |
| Life Insurance Corporation of India | 6,324,997,701 | flagged too large — **a false positive** |

The first four are a historical allotment row read as the pre-issue total. **LIC is the
guard being wrong, not the reader**: 6,324,997,701 is LIC's actual pre-issue count, and the
ceiling assumes SEBI's minimum public offer, from which LIC was relaxed at roughly 3.5%.

369 of 387 are plausible, 13 have no offer price or issue size to test against.

This **flags and does not withhold**: the check set cannot measure the flag, and silently
changing 387 values is not something a measurement supports. It is recorded so that no one
reads the PASS as a guarantee over the whole corpus.

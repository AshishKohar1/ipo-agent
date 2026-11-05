# H59 step 1 continued - the full-year harvest for the valuation block (2026-11-06)

Task 4.1(a) of the 5 November brief. A stub period is marked and NEVER annualised; the
full-year figure is taken from another column of the SAME page, or the value stays NULL
with the reason recorded.

## What was fetched

| item | value |
|---|---|
| mainboard ids (H33) | 482 |
| ids harvested this run | 482 |
| HTTP errors | 0 |
| parse failures | 0 |
| period rows (long table) | 1779 |
| gap between requests | 3.2 s (B2) |
| robots.txt | re-read at the start of the run: PERMITTED; `User-agent:*` disallows only `/ipo/ipo_discussions.asp` |
| HTML cache | `_local/cg_html_cache/` 482 files, 154 MB, gitignored - a re-parse costs no request |

## Periods per page

| period_kind | long rows |
|---|---|
| FULL_FY | 1441 |
| STUB | 338 |

## The collapse to one full-year row per IPO

| | before (latest column only) | after (all columns) |
|---|---|---|
| IPOs with a FULL_FY value | **146** | **479** |
| IPOs on a stub with no full year | 279 | **3** |
| IPOs with no financial table at all | 57 | **0** |

| latest_period_kind | n |
|---|---|
| STUB | 314 |
| FULL_FY | 168 |

| fy_source | n |
|---|---|
| `same_page_column_N` | 479 |
| `no_full_fy_on_page` | 3 |

## Coverage of the full-year values

| field | full-year values | of IPOs | coverage % | prior full year also present |
|---|---|---|---|---|
| `assets_cr` | 479 | 482 | 99.4 | 473 |
| `total_income_cr` | 477 | 482 | 99.0 | 471 |
| `pat_cr` | 478 | 482 | 99.2 | 473 |
| `net_worth_cr` | 472 | 482 | 97.9 | 466 |
| `reserves_cr` | 429 | 482 | 89.0 | 427 |
| `borrowings_cr` | 424 | 482 | 88.0 | 421 |
| `revenue_cr` | 0 | 482 | 0.0 | 0 |
| `ebitda_cr` | 225 | 482 | 46.7 | 223 |

`revenue_cr` is 0% because Chittorgarh's table has no 'Revenue' row at all - it carries
**Total Income**, which is already read. The field is not missing data; the label does
not exist on the source. `ebitda_cr` appears only on the newer pages.

## Reconciliation against the previous harvest (rule 2 applied to our own data)

Column 1 of the new read is the same period `parse()` kept. Compared value by value against
`data/chittorgarh_mainboard_periods.csv`:

| field | both present | exact match | within 5% | over 5% | only in the old read | only in the new read |
|---|---|---|---|---|---|---|
| `net_worth_cr` | 412 | 411 | 411 | **0** | 0 | 57 |
| `pat_cr` | 424 | 424 | 424 | **0** | 0 | 57 |
| `total_income_cr` | 423 | 423 | 423 | **0** | 0 | 57 |
| `assets_cr` | 424 | 424 | 424 | **0** | 0 | 57 |
| `borrowings_cr` | 370 | 358 | 358 | **0** | 0 | 55 |
| `reserves_cr` | 364 | 358 | 358 | **0** | 0 | 57 |
| `ebitda_cr` | 213 | 213 | 213 | **0** | 0 | 10 |

Not one value moved by more than 5%, and 2,611 of them are byte-identical. The rows counted
as neither "exact" nor "over 5%" are rows where both reads hold 0.0, so the relative
difference is undefined, not a disagreement. `fin_period` is identical on **425 of 482**;
the 57 that differ are the 57 that previously had no period at all.

### The 57 that were MISSING - stated honestly

All 57 are 2010-2013 IPOs. Today their pages carry a full `Period Ended` table, and
`parse()` - unchanged - reads it correctly from the cached HTML. The 1 October 2026 sweep
recorded nothing for them.

**The cause cannot be established retrospectively**, because the 1 October HTML was not
kept. Either the site has since filled in those pages, or that sweep received a page
variant without the table. What is NOT the explanation: a parser change. `parse()` itself
was not touched, and it reads these pages correctly today. From this run on the HTML is
cached, so the read is reproducible without a request.

## Unit and scale check, by hand, on 10 random rows

Each page carries its own unit line, `Amount in &#8377; Crore` (₹ crore). Parsed values
compared against the page's own table text for `Net Worth`, `Profit After Tax`,
`Total Income` and `Assets`:

| company | id | FY column | unit line on page | values matched |
|---|---|---|---|---|
| Interarch Building Products | 1811 | 31 Mar 2024 | ₹ Crore | 4/4 |
| Aditya Infotech | 2036 | 31 Mar 2025 | ₹ Crore | 4/4 |
| Crizac | 2096 | 31 Mar 2025 | ₹ Crore | 4/4 |
| Inventurus Knowledge Solutions | 1926 | 31 Mar 2024 | ₹ Crore | 4/4 |
| Alkem Laboratories | 512 | 31 Mar 2015 | ₹ Crore | 4/4 |
| Vijaya Diagnostic Centre | 1145 | 31 Mar 2021 | ₹ Crore | 4/4 |
| Rubicon Research | 2254 | 31 Mar 2025 | ₹ Crore | 4/4 |
| WeWork India Management | 2014 | 31 Mar 2025 | ₹ Crore | 4/4 |
| Ramky Infrastructure | 265 | 31 Mar 2010 | ₹ Crore | 4/4 |
| Quess Corp | 552 | 31 Mar 2016 | ₹ Crore | 4/4 |

**40 of 40 values match the page's own table text.** No scaling of any kind is applied.

## OPEN CHOICE - three December-year-end companies, awaiting the user

The period rule in force (Task 4.1, step 1) is: **31 March is a full Indian financial year;
any other month-end is a stub.** It was applied as written. Three IPOs fall foul of it, and
they are the only three left with no full year:

| company | id | period columns on the page |
|---|---|---|
| Varun Beverages | 598 | 30 Jun 2016, **31 Dec 2015, 31 Dec 2014, 31 Dec 2013** |
| International Gemmological Institute (India) | 1930 | 30 Sep 2024, **31 Dec 2023, 31 Dec 2022, 31 Dec 2021** |
| Hexaware Technologies | 1985 | 30 Sep 2024, **31 Dec 2023**, 30 Sep 2023, **31 Dec 2022, 31 Dec 2021** |

These companies close their books on **31 December**. Their 31 Dec columns are genuine
twelve-month years, not stubs - three consecutive ones each, which is measurable evidence
rather than an assumption. The rule as written classifies them as stubs, so their values
are NULL with `fy_source = no_full_fy_on_page`.

**That is how they stand right now: NULL, nothing annualised, nothing guessed.** The
literal wording of the brief is satisfied. But the full year those three rows need IS on
the page, under a different month-end.

The choice is the user's, because it is a change to a rule, not a bug:

- **Option 1 (in force now).** Keep 31 March as the only full year. The three stay NULL.
  Cost: three mainboard IPOs are unusable for the valuation block, two of them large
  (Varun Beverages, Hexaware).
- **Option 2.** A month-end other than 31 March counts as a full year **only when the page
  shows at least two of it, twelve months apart, and shows no 31 March column at all.**
  Measured against all 482 ids, that test selects **exactly these three** and nothing else.
  The twelve other ids with a repeated non-March month-end all also carry 31 March columns,
  so they are untouched. Still nothing annualised; the label changes, not a number.

Nothing was changed pending that answer.

# BSE as a sector source — usable after all, at the right rung (2026-10-15)

**Verdict: `IndustryNew` IS NSE's `Industry`.** 104 of 104 on 2019+ listings. Filled.

This supersedes the 13 Oct version of this file, which rejected BSE. That conclusion was
wrong, and the error was mine: the test compared BSE's **`Sector`** field against NSE's
`Industry`. `Sector` is BSE's eleven-bucket macro scheme; `IndustryNew` is the sector
level — the same rung as the `Industry` column in NSE's index-constituent files. The old
report's own table listed `IndustryNew` and the test never used it.

## What BSE serves

`api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode=<code>&seriesid=`
returns HTTP 200 JSON to ordinary browser headers (H18). Four levels:

| BSE field | Example (HDFC Bank, 500180) | Rung |
|---|---|---|
| `IndustryNew` | Financial Services | **sector — NSE's `Industry`** |
| `Sector` | Financial Services | macro (11 buckets) |
| `IGroup` | Banks | industry |
| `ISubGroup` | Private Sector Bank | basic industry |

`bseindia.com/robots.txt` returns the site's HTML shell rather than a robots file, so there
is no directive to respect — and none to ignore.

## The test, restricted to 2019+ as instructed

104 symbols that listed in 2019 or later and for which NSE's own `Industry` is already on
disk from the index-constituent files, and for which a BSE scrip code exists in the cached
bhavcopies. 104 of 104 fetches returned 200. Each BSE level against NSE's `Industry`:

| BSE field | agrees | differs | agreement |
|---|---|---|---|
| **`IndustryNew`** | **104** | **0** | **100%** |
| `Sector` | 53 | 51 | 51% |
| `IGroup` | 9 | 95 | 9% |
| `ISubGroup` | 0 | 104 | 0% |

Years covered: 2019, 2020, 2021, 2022, 2023, 2024.

Before punctuation is normalised `IndustryNew` reads 103 of 104. The single difference is
a comma:

| Symbol | NSE `Industry` | BSE `IndustryNew` |
|---|---|---|
| NAZARA | Media Entertainment & Publication | Media**,** Entertainment & Publication |

Same sector, one character. The comparison strips punctuation and keeps the ampersand, so
`Metals & Mining` still differs from `Metals Mining` only in a way that cannot change a
classification, while `Consumer Durables` and `Consumer Discretionary` still differ.

The vocabulary is NSE's, which is what matters: `SECTOR_TO_INDEX` keys on NSE's sector
names, and all 15 distinct `IndustryNew` values returned are in that vocabulary.

## Why the other three rungs are still unusable

`Sector` would write "Consumer Discretionary" where `SECTOR_TO_INDEX` expects "Consumer
Durables" — half the rows silently **wrong**, not missing, which is the failure hard rule 1
exists to prevent. `IGroup` and `ISubGroup` are finer than NSE's sector level ("Aerospace &
Defence" against "Capital Goods"), so neither is a drop-in either. Only `IndustryNew` is
read; `bse_sector_fill.py` asserts that the other three are never read as the industry.

## How the fill is constrained

* Scrip codes come from the **cached** BSE bhavcopies in `data/bhavcopy_cache/`. No request
  is made to discover one, and a symbol with no cached code stays in the manual file.
* An NSE reading is never overwritten. An official NSE constituent file outranks a second
  source that merely agrees with it 104 times out of 104.
* Every filled row carries the endpoint, the scrip code, and the fetch time (H26).
* 3 s between requests (rule 9); `--validate` re-measures the agreement at any time.

## What is still not available

NSE's own four-level classification, per symbol, from `api/quote-equity`. That returns
**HTTP 403 on all 258** symbols tried (`data/sector_map_quotes.csv`), and remains blocked.
So the comparison above can only be made at one rung — the one NSE publishes in its
constituent files — and that is the rung `IndustryNew` matches.

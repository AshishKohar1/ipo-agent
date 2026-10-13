# BSE as a sector source — tested and NOT usable as a drop-in (2026-10-13)

**Verdict: the classifications are not the same, so nothing was filled.** Per the
instruction, this stops here and reports.

## What BSE serves

`api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode=<code>&seriesid=`
returns HTTP 200 JSON to ordinary browser headers (H18). It does carry **four** levels:

| BSE field | Example (HDFC Bank, 500180) |
|---|---|
| `IndustryNew` | Financial Services |
| `Sector` | Financial Services |
| `IGroup` | Banks |
| `ISubGroup` | Private Sector Bank |

`bseindia.com/robots.txt` returns the site's HTML shell rather than a robots file, so there
is no directive to respect — and none to ignore.

## The test

22 symbols for which NSE's own classification is already on disk (from the index-constituent
files) and a BSE scrip code exists. BSE's `Sector` against NSE's `Industry`:

**11 agree, 11 differ.** The disagreements are not noise — they are a different level of
abstraction:

| Symbol | NSE industry | BSE Sector | BSE IGroup |
|---|---|---|---|
| WAKEFIT | Consumer Durables | **Consumer Discretionary** | Consumer Durables |
| AEQUS | Capital Goods | **Industrials** | Aerospace & Defence |
| SUDEEPPHRM | Chemicals | **Commodities** | Chemicals & Petrochemicals |
| TENNIND | Automobile and Auto Components | **Consumer Discretionary** | Auto Components |
| JAINREC | Metals & Mining | **Commodities** | Diversified Metals |
| MEESHO | Consumer Services | **Consumer Discretionary** | Retailing |

The eleven that agree do so only because a handful of names happen to exist at both levels —
Financial Services, Healthcare, Information Technology, Services.

## Why this cannot be filled in

`BSE.Sector` is a **macro** scheme of roughly eleven GICS-like buckets. NSE's `Industry`
column in the index files is the **sector** level, which is finer. They are two different
rungs of the ladder, not two spellings of one.

`BSE.IGroup` is closer to NSE's vocabulary but is **finer again**: "Aerospace & Defence"
against NSE's "Capital Goods", "Auto Components" against "Automobile and Auto Components".
So it is not a drop-in either.

Filling `nse_industry` from `BSE.Sector` would write "Consumer Discretionary" where
`SECTOR_TO_INDEX` expects "Consumer Durables", and the sector-index mapping keys on NSE's
vocabulary. **Half the rows would be silently wrong** — not missing, wrong, which is the
failure hard rule 1 exists to prevent.

## What would make it work, and why it was not done

A hand-built crosswalk from BSE's eleven macro buckets (or its IGroups) to NSE's sector
names. That is buildable, but it would be **our** mapping rather than an official one, and
the standing instruction is never to force a mapping. It is offered, not assumed.

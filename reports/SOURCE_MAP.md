# Source map and failover

Written 2026-10-23 under H47. Every row's verdict is backed by a request made today or by a
decision already recorded. Where a host answered 403 it was tried **once** and not worked
around (H47 rule 5).

## 1. Per data item

| Data item | NSE / niftyindices | BSE | Chittorgarh | Which gives more | Primary | Failover |
|---|---|---|---|---|---|---|
| **Live subscription** | `api/ipo-active-category`, category-wise, intraday | `api.bseindia.com/.../GetIPODemandSchedule` — **403, with and without Referer** | `/ipo_subscription/x/{id}/` while an issue is open | NSE: it is the origin; Chittorgarh republishes it | **NSE** (H22/H40) | **Chittorgarh** (B2/H14). BSE is unavailable |
| **IPO calendar** | `api/ipo-current-issue`, `api/all-upcoming-issues` — carries the **symbol and series**, which nothing else does | `/markets/PublicIssues/IPOIssues` (HTML) | `/ipo/` dashboard, with SME | NSE for symbol/series; Chittorgarh for SME breadth | **NSE**, unioned with Chittorgarh | Chittorgarh |
| **Past issues, issue price, issue dates** | `api/public-past-issues` — 1,474+ issues back to 2016 with `ipoStartDate`, `issuePrice`, `listingDate` | public-issue pages, no bulk feed | id-walk, one page per issue | **NSE, decisively.** 137 issue-open dates came from it today that nothing else carries | **NSE** | Chittorgarh id-walk (slow, ≥3 s) |
| **Listing-day prices** | bhavcopy, one file per date | bhavcopy, one file per date — **restored today** | — | Equal. They are independent, which is what rule 2 needs | **Both**, reconciled | either alone, flagged single-source |
| **Trading holidays** | `api/holiday-master?type=trading`, CM segment | a Trading Holidays page (HTML) | — | NSE: machine-readable, segment-specific | **NSE** | BSE page (not implemented; calendar is cached and a year lasts a year) |
| **Index closes (15 indices)** | niftyindices `getHistoricaldatatabletoString` | `api.bseindia.com` — **403** | — | NSE Indices only | **niftyindices** | **none available** |
| **Nifty 50 TRI** | niftyindices `getTotalReturnIndexString` | **no total-return index exists in BSE's public archive** — 0 of 151 | — | NSE Indices only | **niftyindices** | **none available** |
| **Sector indices** | 16 NSE sectoral indices mapped; 5 sectors have none | 151-index archive **including Capital Goods, Industrials, Services, Telecommunication, Utilities** | — | BSE covers four of NSE's five gaps — but see §3 | **NSE** where it has one | **blocked**: BSE's index data is behind `api.bseindia.com` |
| **Index P/E and P/B history** | niftyindices `getpepbHistoricaldataDBtoString` | `api.bseindia.com` — **403** | — | NSE Indices only | **niftyindices** | **none available** |

## 2. What was tested today, and what it showed

| Test | Result |
|---|---|
| BSE `GetIPODemandSchedule`, 3 recent closed IPOs (Om Power 544750, OnEMI 544754, Powerica 544744) | **HTTP 403 on all three**, with and without the `Referer` the code sends. `curl` independently confirms 403. Agreement against the stored figures **could not be measured**: BSE returned no data to compare |
| BSE subscription as failover or primary | **Neither. Unusable.** Consistent with the 8 Oct finding recorded in PROGRESS stage 31 |
| BSE bhavcopy | **Broken since 2024-07-02 and now fixed** — see below |
| BSE total-return index | **Does not exist publicly.** BSE's own historical-data archive lists 151 indices and **not one** is a TRI or total-return series |
| `api.bseindia.com`, any path | 403, including `/robots.txt`. The host is closed to this client |

**The BSE bhavcopy defect, because it is the largest thing found today.** Every BSE
bhavcopy from **2024-07-02 to 2026-10-22 — 154 dates** — was cached as 77 bytes of empty
gzip. Three causes, compounding:

1. BSE restructured its site and says so on the page: *"Website URLs have been updated."*
   The old `.aspx` Referer still resolves by redirect, and BSE's edge answers a download
   carrying it with the Angular shell — HTTP 200, 14,287 bytes of HTML.
2. `_norm` filtered the unified file's `SctySrs` column against **NSE's** series (`EQ`,
   `BE`). BSE writes its **group** there: `A`, `B`, `T`, `M`, `MT`, `X`, `XT`, `Z` for
   equity, `F` and `G` for debt and government securities. Every row of a BSE file was
   discarded. The unified file name hides that the column's vocabulary is still
   exchange-specific.
3. A zero-row parse was **cached and served**, which made the failure sticky and silent.

Consequence: **every listing since July 2024 was labelled single-source**, and rule 2's
two-source standard was unmet with nothing saying so. Now fixed and verified — 21 Oct
4,552 rows, 22 Oct 4,480. HD Fire Protect: BSE 334.40 / 307.20 against NSE 335.00 /
306.75, 0.18% apart, reconciling to `nse+bse`, gain **23.5055%**.

**Still owed:** the 154 dates' listing labels remain single-source from capture time. A
re-label is a night batch (H9), not a live-path job.

## 3. Sector indices: the honest position

BSE publishes sectoral indices that would fill four of NSE's five gaps — **Capital Goods**
(56 of our 2019+ rows), **Services**, **Telecommunication** (3), **Utilities** (3).
Consumer Services (37) has no clean BSE counterpart either; BSE's nearest is *Consumer
Discretionary*, a different basket.

**But the data is not reachable.** BSE's historical index values are served by
`api.bseindia.com`, which returns 403 to this client on every path tried, and the archive
page itself is an Angular front end over that same host. Under H47 rule 5 that is a block
and it is not worked around.

So the correlation table Task 3 asks for — NSE vs BSE daily, 3-month and 6-month returns,
2019–2026 — **cannot be computed**. Not because the method is unclear but because one side
of every pair is unobtainable. Nothing is mapped to a BSE index on that basis: a sector
mapped to an index whose history we cannot read is a column of NULLs with extra steps.

`sector_minus_nifty_3m/6m` and `listing_gain_minus_sector_day` therefore stand where
yesterday's work left them — 2019+ coverage **63.4%**, unchanged, with the remaining 104
rows being sectors for which NSE publishes no index and BSE's is out of reach.

**If BSE access is ever granted** (a data-request form, or the API host opening), the work
is small and the method is already fixed: correlate daily returns 2019–2026, keep NSE
unless the correlation is below 0.9 or BSE's history is longer, and record the source on
every mapped row.

## 4. niftyindices is a single point of failure, and nothing can replace it

Added 2026-10-25 (Task 4). Recorded here because it is a structural risk, not a bug: three
of Model H's inputs come from **one host with no second source anywhere**.

| Data item | Only source | Fallback | What a block costs |
|---|---|---|---|
| **Nifty 50 Total Return Index** | niftyindices `getTotalReturnIndexString` | **none** | Model H's target `excess_1y` / `excess_3y` cannot be computed for any window reaching past the stored end date |
| **Index closes (15 indices)** | niftyindices `getHistoricaldatatabletoString` | **none** | `market_heat`, sector-relative features |
| **Index P/E and P/B history** | niftyindices `getpepbHistoricaldataDBtoString` | **none** | the market-valuation features in the H45 ratio set |

**Why there is no fallback, rather than one we have not built.** BSE's public historical
archive lists 151 indices and **not one is a total-return series**. A price index is not a
substitute: the entire purpose of the benchmark is that it includes dividends, so swapping
in a price index would understate the benchmark and inflate every excess return in the
training set. That is a fabricated improvement, which rule 1 forbids more firmly than it
forbids a gap. `api.bseindia.com` also answers 403 on every path, so even BSE's price
indices are out of reach.

So the design is: **no substitute, and a loud failure.**

| Behaviour | Where | Proof |
|---|---|---|
| A 403 is one attempt and final — no retry, no header change | `fetch_nifty_tri.fetch` raises `failover.Blocked` on 401/403/429 **before** parsing the body | self-test [1]: the host is asked exactly once |
| Nothing is written on a block | `fetch_nifty_tri.refresh` returns before the writer is called | self-test [1]: "NOTHING was written" |
| The run prints `NIFTYINDICES BLOCKED - Model H target not refreshed` | `BLOCKED_SUMMARY`, and `model_h_targets.BENCH_BLOCKED` with the same wording | self-tests assert the exact string in both modules |
| The target goes **NULL**, never computed against a stale index | `_bench_at` returns None past the series end, so `excess` and the label stay None | pre-existing behaviour, now counted as `no_benchmark` and named in the summary instead of folded into `no_price` |
| Staleness is visible even when nothing is blocked | `bench_status()` prints every run, good news or bad | self-test: a series 58 days old is not ok |
| **The 15:00 Model L email is unaffected** | `send_daily_email` reaches no index at all | self-test [4]: the module's source contains no reference to the TRI or its file |

**A 403 was being retried until today.** `fetch_nifty_tri` wrapped the request in
`for attempt in range(3)` and caught every exception. A 403 returns HTML, so `json.loads`
raised a parse error and the loop asked twice more — three requests at a host that had
already refused. The same defect existed in `listing_prices.Fetcher.get`, which treated
403 and 429 as retryable alongside the 5xx codes. Both are fixed; 5xx stays retryable,
because a gateway error is a fault and not a refusal.

**Live status at the time of writing:** the stored TRI ends **2026-09-25**, 30 days before
today. Nothing is blocked — it simply has not been refreshed since. Under the rule above
that means any Model H target window ending after 2026-09-25 is NULL rather than wrong,
and `build_corrected` now says so on every run.

# Re-label of the BSE-blind window

Window **2024-07-02 to 2026-10-22**. Every BSE bhavcopy downloaded in it was cached
as 77 bytes of empty gzip, so `_norm` discarded every row and every listing was
labelled single-source with nothing in the output saying why. The code was fixed on
2026-10-23; this is the re-label of the data.

## 1. Fetch phase

| | |
|---|---|
| BSE dates re-fetched | **129 of 129** |
| Blocked | **none** |
| Missing (no file served) | **none** |
| Rows per file | 4,000-4,700, against 0 before |
| Forward-capture dates also fetched | 9 (2026-09-28 to 2026-10-12) |

## 2. Buckets after the re-label

| bucket | count | before |
|---|---|---|
| reconciled_2_sources | **178** | 0 |
| single_source_unverified | **1** | 178 |
| no_source | **1** | 2 |
| **total rows** | **180** | 180 |

**>5% disagreement forced to NULL (rule 2): 1**

| IPO | listing date | NSE open | BSE open | gap | old gain | new gain |
|---|---|---|---|---|---|---|
| Vishal Mega Mart Limited | 2024-12-18 | 104.00 | 110.00 | 5.5% | 33.3333 | **NULL** |

### Still not two-source, and why

| IPO | listing date | status | reason |
|---|---|---|---|
| Denta Water & Infrastructure Limited | 2025-01-29 | no_source | NSE: file present but scrip not matched (none); BSE: file present but scrip not matched (none) |
| National Securities Depository Ltd (NSDL) | 2025-08-06 | single_source_unverified | NSE: file present but scrip not matched (none) |

Both are genuine absences, not fetch failures: each date's file is on disk with thousands of rows, and the scrip is not in it under the symbol or ISIN the master carries. Neither was invented a price.

## 3. Impact: only the listings where something moved

| IPO | listing date | old gain | new gain | L1 old/new | L2 old/new | Model H start old/new |
|---|---|---|---|---|---|---|
| ** Vishal Mega Mart Limited ** | 2024-12-18 | 33.3333 | NULL | hit/- | hit/- | 111.93/111.94 |
| ** National Securities Depository Ltd (NSDL) ** | 2025-08-06 | NULL | 10.0000 | -/hit | -/miss | NULL/936.00 |
| ** GK Energy Ltd ** | 2025-09-26 | 11.7647 | 9.8039 | hit/hit | hit/miss | 167.74/167.75 |
| ** Shree Tirupati Balajee Agro Trading Company Limited ** | 2024-09-12 | 8.4337 | 10.1807 | hit/hit | miss/hit | 94.50/96.02 |
| ** Garuda Construction and Engineering Limited ** | 2024-10-15 | 10.5263 | 9.5789 | hit/hit | hit/miss | 106.36/106.59 |
| ** Rajputana Stainless Ltd. ** | 2026-03-19 | 0.0000 | 0.7992 | miss/hit | miss/miss | 113.03/112.97 |
| ** Trualt Bioenergy Ltd. ** | 2025-10-03 | 9.9597 | 10.4234 | hit/hit | miss/hit | 530.95/530.90 |
| ** Dev Accelerator Ltd. ** | 2025-09-17 | 0.0000 | 0.2459 | miss/hit | miss/miss | 64.05/64.20 |
| ** M & B Engineering Ltd ** | 2025-08-06 | 0.0000 | 0.1299 | miss/hit | miss/miss | 408.65/408.90 |
| ** Vidya Wires Ltd ** | 2025-12-10 | 0.0000 | 0.1250 | miss/hit | miss/miss | 53.17/53.16 |
| ** Kalpataru Limited ** | 2025-07-01 | 0.0000 | 0.0121 | miss/hit | miss/miss | 432.95/433.38 |
| Brainbees Solutions Limited | 2024-08-13 | 40.0000 | 37.2043 | hit/hit | hit/hit | 679.10/678.67 |
| Gala Precision Engineering Limited | 2024-09-09 | 36.3138 | 39.0454 | hit/hit | hit/hit | 757.15/772.10 |
| Prostarm Info Systems Limited | 2025-06-03 | 14.2857 | 16.6667 | hit/hit | hit/hit | 126.00/126.12 |
| Unicommerce eSolutions Limited | 2024-08-13 | 117.5926 | 115.2778 | hit/hit | hit/hit | 210.08/210.06 |
| KRN Heat Exchanger and Refrigeration Limited | 2024-10-03 | 118.1818 | 115.9091 | hit/hit | hit/hit | 478.79/478.62 |
| Manba Finance Limited | 2024-09-30 | 20.8333 | 22.9167 | hit/hit | hit/hit | 152.25/154.85 |
| Unimech Aerospace and Manufacturing Limited | 2024-12-31 | 85.9873 | 87.9618 | hit/hit | hit/hit | 1376.25/1374.72 |
| Saraswati Saree Depot Limited | 2024-08-20 | 21.2500 | 23.1250 | hit/hit | hit/hit | 203.70/206.82 |
| Waaree Energies Limited | 2024-10-28 | 66.3340 | 67.9973 | hit/hit | hit/hit | 2338.90/2337.85 |
| Inventurus Knowledge Solutions Limited | 2024-12-19 | 42.9646 | 41.3093 | hit/hit | hit/hit | 1960.85/1960.55 |
| Diffusion Engineers Limited | 2024-10-04 | 15.1786 | 13.5417 | hit/hit | hit/hit | 203.17/200.26 |
| Laxmi Dental Limited | 2025-01-20 | 26.6355 | 25.0000 | hit/hit | hit/hit | 550.55/550.60 |
| Glottis Ltd | 2025-10-07 | -34.8837 | -33.3333 | miss/miss | miss/miss | 83.70/83.78 |
| Standard Glass Lining Technology Limited | 2025-01-13 | 22.8571 | 24.2857 | hit/hit | hit/hit | 163.28/163.31 |
| Highway Infrastructure Ltd. | 2025-08-12 | 64.2857 | 65.7143 | hit/hit | hit/hit | 120.75/121.80 |
| Om Power Transmission Ltd. | 2026-04-17 | 6.2857 | 4.8857 | hit/hit | miss/miss | 193.38/191.76 |
| ACME Solar Holdings Limited | 2024-11-13 | -13.1488 | -11.7647 | miss/miss | miss/miss | 253.15/253.32 |
| Sanstar Limited | 2024-07-26 | 14.7368 | 13.3684 | hit/hit | hit/hit | 115.07/115.08 |
| Ajax Engineering Limited | 2025-02-17 | -8.4261 | -7.0747 | miss/miss | miss/miss | 595.40/595.50 |
| Fractal Analytics Ltd. | 2026-02-16 | -2.6667 | -1.3333 | miss/miss | miss/miss | 847.15/847.27 |
| Gem Aromatics Ltd | 2025-08-26 | 2.4923 | 1.2462 | hit/hit | miss/miss | 319.05/319.07 |
| Amir Chand Jagdish Kumar (Exports) Ltd. | 2026-04-02 | -5.6604 | -6.8396 | miss/miss | miss/miss | 180.00/177.75 |
| Powerica Ltd | 2026-04-02 | -7.3418 | -6.2025 | miss/miss | miss/miss | 390.00/390.00 |
| GNG Electronics Limited | 2025-07-30 | 49.7890 | 48.7342 | hit/hit | hit/hit | 333.39/333.44 |
| Capillary Technologies India Ltd. | 2025-11-21 | -0.8839 | -1.9151 | miss/miss | miss/miss | 606.50/606.70 |
| Swiggy Limited | 2024-11-13 | 7.6923 | 6.6667 | hit/hit | miss/miss | 456.00/455.98 |
| Hexaware Technologies Limited | 2025-02-19 | 5.2966 | 4.2726 | hit/hit | miss/miss | 762.55/763.20 |
| BMW Ventures Ltd | 2025-10-01 | -21.2121 | -20.2020 | miss/miss | miss/miss | 74.10/75.05 |
| Billionbrains Garage Ventures Ltd. | 2025-11-12 | 12.0000 | 13.0000 | hit/hit | hit/hit | 131.33/131.13 |

153 of 180 rows moved; the 40 largest are shown (**bold** = a hit label changed). Rows in **bold** number 11.

### Label flips in full

| target | flips | detail |
|---|---|---|
| L1 (gain > 0) | **7** | Vishal Mega Mart Limited hit->-; Kalpataru Limited miss->hit; M & B Engineering Ltd miss->hit; National Securities Deposito -->hit; Dev Accelerator Ltd. miss->hit; Vidya Wires Ltd miss->hit; Rajputana Stainless Ltd. miss->hit |
| L2 (gain > 10) | **6** | Shree Tirupati Balajee Agro  miss->hit; Garuda Construction and Engi hit->miss; Vishal Mega Mart Limited hit->-; National Securities Deposito -->miss; GK Energy Ltd hit->miss; Trualt Bioenergy Ltd. miss->hit |

### Base rates on the window

| target | before | after | n before | n after |
|---|---|---|---|---|
| L1 `gain > 0` | 67.98% | **70.79%** | 178 | 178 |
| L2 `gain > 10` | 44.94% | **44.38%** | 178 | 178 |

### Verdict

**No Model L hit rate changed, because not one of these 180 listings was ever scored by a live prediction.** `data/predictions_log.csv` holds 11 predictions and 9 outcome rows, and every one of them is from 2026-10-21 or later - after this window closes. So there is nothing to correct and no correction row is appended; appending one would be inventing a correction to a score that was never made.

The seven L1 flips are all marginal and all in the same direction, and the reason is worth stating because it is a measurement artefact rather than new information: five of them had an old gain of **exactly 0.0000**, meaning NSE's open equalled the offer price to the paisa. Averaging in BSE's open moves them a few hundredths of a percent above the offer price, which crosses `gain > 0`. A label that turns on the fourth decimal place is a label worth distrusting in either direction; it is recorded here rather than treated as a discovery.

Vishal Mega Mart is the one substantive change. It opened at **104.00 on NSE and 110.00 on BSE** - 5.5% apart, past rule 2's tolerance - so its listing price is now NULL and both its hit labels are undefined. It had been counted as an L1 and L2 hit on NSE's number alone. That is the whole purpose of a two-source rule: one of those two numbers is a worse answer than no number.

## 4. Model H targets

**Model H does not use the reconciled listing close, and that matters for reading the
table above.** `_raw_price` walks `("nse", "bse")` and returns the FIRST exchange that
carries the scrip, so Model H's start and end prices are single-source by construction and
NSE wins whenever it has the row. The `Model H start old/new` column above is the
reconciled close from `listing_prices.csv`, which moved on **173 of 180** rows (every move
under 2%) — but that is not the number Model H reads.

So the re-label changes Model H in exactly one place: a row where **NSE had no price and
BSE now does**.

| | |
|---|---|
| Window target rows (1y) | 109 |
| Affected, 1y | **1** |
| Affected, 3y | **0** — the window is too recent for a 3-year horizon to have closed |
| Largest change | **0.136 pp** |

| symbol | listing | end | start | end px | source | IPO ret | bench | excess | label |
|---|---|---|---|---|---|---|---|---|---|
| NSDL | 2025-08-06 | 2026-08-06 | 936.00 | 820.80 | `bse/bse`, matched on ISIN | −12.3077% | +1.4403% | **−13.748 pp** | 0 |

Its stored excess was −13.612 pp, so the corrected figure moves it by −0.136 pp and the
label stays 0. Appended, not edited.

**A separate finding, not repaired here:** Model H's prices being single-source by
construction means rule 2's two-source standard has never applied to them. Now that BSE is
reachable again, reconciling them is possible. That is a modelling change to a frozen
path, so it is recorded rather than made.

**The benchmark is 30 days stale** and said so loudly on every one of these runs:
`NIFTYINDICES BLOCKED - Model H target not refreshed - Nifty 50 TRI ends 2026-09-25`.
Eight of the nine pending rows stayed NULL for want of a price, not a benchmark.

## 5. Forward-captured listings (`data/new_listings.csv`)

The 34 forward captures inside the window were re-run through the existing `ingest_outcomes --backfill-prices` path once the 9 missing BSE dates were fetched.

| status | before | after |
|---|---|---|
| reconciled_2_sources | 0 | **10** |
| single_source_unverified | 6 | 12 |
| no_source | 9 | 12 |
| pending_dayend_capture | 19 | 0 |

**A labelling defect was found and fixed in that path.** When a bhavcopy row was found but the row had no OFFER price, it printed `NOT FOUND`, discarded the two captured prices, and still wrote `reconciled_2_sources`. A label claiming two-source agreement about a value that is not stored is worse than no label. It now stores the prices, leaves only the gain NULL, and distinguishes `NO OFFER PRICE` from `NOT IN BHAVCOPY`.

**Owed:** 23 of those rows still have no offer price, which is what `rescore_unpriced` is for. It appends outcome rows to `predictions_log.csv`, which is append-only, so it is left for an explicit run rather than done in passing.

## 6. Tripwires, so this cannot repeat silently

| | guard | test |
|---|---|---|
| a | A zero-row or HTML answer is **never cached**, and a zero-row file already in the cache is re-fetched rather than served | `relabel_window` [3], `listing_prices` self-test |
| b | `audit_bhavcopy_rows()` flags any cached bhavcopy under **1,000 rows**. Every trading day lists thousands of scrips, so a thin file is a failed download and not a quiet market. It reads the cache, so the Saturday audit spends no requests | `relabel_window` [4]: a 1-row file and an empty file are both flagged, a 1,500-row file is not |
| c | Every single-source row carries a **reason in words** - which exchange is missing, and whether the file was absent or the scrip simply was not in it | `relabel_window` [5] |
| extra | A 403/401/429 is one attempt and final, in `listing_prices.Fetcher.get` and `fetch_nifty_tri.fetch`. Both were retrying blocks until today | `relabel_window` [2], `fetch_nifty_tri` [1] |


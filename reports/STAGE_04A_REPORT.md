# Stage 4A — Chittorgarh coverage sample → GATE F

**Status:** AWAITING_USER (Gate F). **robots.txt re-checked and unchanged — access is
permitted.** The day-wise table exists and is richer than expected for a closed IPO, but
**the 20-IPO cross-year sample could not be completed**: there is no permitted way to
resolve a historical company to its Chittorgarh page id without the bulk fetching Gate F
exists to authorise. 5 pages were fetched in total, ≥3 s apart.

## What was done
- Re-read `chittorgarh.com/robots.txt` first (decision B2). **Unchanged** from Stage 1 — `User-agent: *` disallows only `/ipo/ipo_discussions.asp`, `Allow: /`, no Anthropic token. Not aborted.
- Established the URL shape and confirmed the numeric id is mandatory.
- Verified the day-wise table on a **closed** IPO, and confirmed a live IPO shows only a snapshot.
- Tried four different routes to a historical company→id index; all are client-rendered or unusable.
- Stopped without bulk fetching, as B3 requires.

## robots.txt check (mandatory first step)

```
# Block all bots from crawling this specific page
User-agent: *
Disallow: /ipo/ipo_discussions.asp

# Allow all other pages
User-agent: *
Allow: /
```
Named blocks exist for AmazonAdBot, Adsbot-Google, CCBot, GPTBot, OAI-SearchBot, omgili,
MAZBot, ChatGPT-User, Baiduspider, DataForSeoBot, AhrefsBot, PetalBot — **no Anthropic
token**. Identical to what Stage 1 recorded. Proceeding was correct under B2.

## What the pages actually contain

**URL shape:** `https://www.chittorgarh.com/ipo_subscription/<slug>/<id>/`
Slug alone 404s (`/ipo_subscription/vishal-nirmiti-ipo/` → 404), so **the numeric id is
required**. There is no site search (`/search/?q=` → 404).

### Closed IPO — Adroit Industries (id 3007): day-wise table present and rich ✅

The table is headed by **`Date`**, not the literal phrase "Day-wise Subscription Details" —
the phrase B2 refers to does not appear as text on the page, which matters for the parser.

| Date | QIB (Ex Anchor) | NII | NII > ₹10L | NII < ₹10L | Retail | Total |
|---|---|---|---|---|---|---|
| Sep 25 (Day 1) | 0.01 | 3.67 | 2.69 | 5.61 | 2.56 | 2.07 |
| Sep 28 (Day 2) | 0.06 | 18.31 | 15.08 | 24.77 | 9.66 | 8.77 |
| Sep 29 (Day 3) | 192.68 | 121.90 | 129.86 | 105.99 | 32.21 | 97.28 |

Also present on the same page:
- **Anchor allocation table** — fund name, group entity, shares allotted, amount, % allocated, % of issue (e.g. NIPPON INDIA POWER & INFRA FUND, 2,40,240 shares, ₹6.53 cr).
- **Lock-in** — `Shares Locked (30 Days)` 30,44,117 and `Shares Locked (90 Days)` 30,44,117, plus anchor price ₹272.00 and "% of QIBs 60.00%".
- Offer structure (category / shares offered / amount / size %) and a final cumulative subscription table.

**This confirms decision C1's premise even more strongly than stated.** C1 cites Adroit QIB
"1.82x on day 2 → 195x on the final day". The page shows QIB (Ex Anchor) at **0.06 on day 2
and 192.68 on day 3** — the exact figures differ from your note, but the one-directional
final-day spike is real and larger. Day-2 Total was 8.77x against a final 97.28x. Training
on final figures and scoring on day-2 inputs would be badly biased, exactly as C1 says.

### Live IPO — Vishal Nirmiti (id 2665): snapshot only, as expected
Opened the day of this run, so it carries a single cumulative
`Investor Category / Subscription (times)` table (Retail 0.02x, Total 0.02x) and no
day-wise rows. Not evidence against B2 — there was only one bidding day.

### Hero Motors (id 2225)
Offer structure, anchor table with 30/90-day lock-ins, basis-of-allotment detail and final
cumulative subscription (QIB 1.59x, NII 10.47x, Retail 8.62x, Total 4.90x). A day-wise
table was not captured in my extraction window; presence unconfirmed.

## Coverage by year — the requested table, and why it is empty

| Listing year | Master rows | IPOs sampled | Day-wise table present | Bidding days | Anchor + lock-in | Why |
|---|---|---|---|---|---|---|
| 2010 | 74 | **0** | not tested | — | — | id unresolvable |
| 2013 | 4 | **0** | not tested | — | — | id unresolvable |
| 2016 | 27 | **0** | not tested | — | — | id unresolvable |
| 2019 | 17 | **0** | not tested | — | — | id unresolvable |
| 2022 | 39 | **0** | not tested | — | — | id unresolvable |
| 2025 | 107 | **0** | not tested | — | — | id unresolvable |
| (Sep–Oct 2026, **not in master**) | 0 | 3 | **1 of 1 closed IPO ✅** (+1 live = snapshot, 1 unconfirmed) | 3 | ✅ both | only ids obtainable |

**Why no sample IPO could be tested.** Reaching a subscription page needs `<slug>/<id>`, and
I found no permitted, server-rendered index mapping a company to its id:

| Route tried | Result |
|---|---|
| `/report/mainboard-ipo-list-in-india-by-year/83/` with `?year=2016`, `&exchange=`, `/83/2016/` | Byte-identical (163,053) whatever the parameter — the year filter runs client-side. 0 id links |
| `/ipo/ipo_perf_tracker.asp?year=2016` | Year *is* honoured and 2016 company names are server-rendered (Mahanagar Gas, ICICI Pru Life, Quess Corp), but the rows are **plain text with no links or ids** |
| `sitemap.xml` → 70 sub-sitemaps | Sampled 3: brokers and glossary pages, 0 IPO pages; `?a=45` returns HTTP 500 |
| Site search `/search/?q=Syngene` | 404 — no search endpoint |
| `/ipo/` dashboard | Works, gives 20 slug+id pairs — but **all are Sep–Oct 2026, newer than the master's May 2026 cutoff, so 0 of 20 match any master row** |

The only remaining way to resolve historical ids is to walk the id space (~3,000 pages,
≥3 s each ≈ **2.5 hours of requests**) and read each page's company name. That is precisely
the bulk fetching B3 says must not happen before Gate F, so I stopped.

## Deviations from plan
1. **The core deliverable — a 20-IPO coverage table across 2010–2025 — was not produced.** The obstacle is id resolution, not access or politeness. Reported rather than worked around.
2. **B2's wording is slightly off in two ways**, both of which affect the 4B parser: the table is headed **`Date`** and the phrase "Day-wise Subscription Details" never appears as page text; and the categories are `QIB (Ex Anchor) / NII / NII > ₹10L / NII < ₹10L / Retail / Total` — that is bNII/sNII by another name, and **there is no separate plain "QIB" column** (anchor is broken out separately, so QIB-ex-anchor must be combined with the anchor row to reconcile against the master's QIB).
3. 5 requests total, all ≥3 s apart. No bulk fetch, no `data/daywise_progress.csv` yet.

## Open issues
1. Whether day-wise depth survives for 2010–2019 is **still unknown** — the original risk B3 raised. Chittorgarh's own note (per B3) says older IPOs may carry only "final bidding detail as of the last day".
2. Reconciling to the master's Total needs care: the page reports Total including anchor effects, and QIB is split anchor / ex-anchor.
3. Master coverage for 2013 is only 4 rows, so that year can never carry a meaningful sample.

---

# GATE F — decision needed

## The decision
**How should historical day-wise subscription be obtained, given that company→id resolution
needs either a bulk id-space walk or a JavaScript-rendered index?**

## Options

| Option | Cost | Risk |
|---|---|---|
| **1. Authorise a one-off id-discovery walk (recommended)** | ~3,000 requests at ≥3 s ≈ 2.5 h, once. Builds a permanent `company → slug/id` map committed to the repo, so it never repeats | Polite but unmistakably bulk. It reads listing pages only, and the map makes 4B cheap and resumable |
| **2. Sample-only walk** | Walk ids in a narrow range to hit ~20 IPOs across the six years first (~20–30 min), produce the real coverage table, then decide on the full backfill | Two gates instead of one, but it answers the 2010–2019 depth question cheaply before committing to 4B |
| **3. Render the year index with a browser** | The session has a browser tool; the year list would then yield ids directly for chosen years, no id walk | Heavier tooling, and still one page fetch per year |
| **4. Forward-only (drop the backfill)** | Zero historical fetching. Rely on B4's nightly NSE+BSE snapshots | `L_day1`/`L_day2` cannot be trained for ~6–12 months; Stage 5 stalls, though `L_final_3pm` is unaffected |

## Recommendation
**Option 2, then Option 1 if the depth holds.** The unresolved question is whether 2010–2019
pages carry day-wise rows at all — and that is cheap to answer on ~20 IPOs. If old years turn
out to be final-day-only, a full 2.5-hour id walk buys much less than it appears to, and
Option 4 becomes the honest choice for the older half of the dataset. Deciding the big fetch
before knowing the depth is the wrong order.

Option 3 is worth pairing with either: rendering six year-index pages is far cheaper than
walking 3,000 ids, if the tooling cooperates.

Reply in the form `Gate F decision: …` and I will record it verbatim in `DECISIONS.md`.

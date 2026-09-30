# Stage 4A — Chittorgarh ID-walk coverage → GATE F2

**Status:** AWAITING_USER (Gate F2). **Recommendation: do not run Stage 4B's day-wise
backfill — the data does not exist historically.** The walk found something more decisive
than a coverage gradient: Chittorgarh's day-wise subscription table is **transient**, not
archived. It is published during the bidding window and replaced by allotment data once the
basis of allotment appears.

71 requests used of the 200 authorised, all ≥3.2 s apart, single-threaded, one fixed
User-Agent, no retries. Stopped early because the pattern was unambiguous.

## Mandatory pre-flight: robots.txt

Re-read before anything was fetched. **Unchanged and permissive** — not aborted.

```
User-agent: *
Disallow: /ipo/ipo_discussions.asp
User-agent: *
Allow: /
```
No `ClaudeBot` or `anthropic-ai` token; nothing disallows `/ipo_subscription/`.
(sha256 of the file, first 16: `41eb2243d51c5fba`.)

## Two findings that changed the method

**1. The id alone is enough to identify a company — this solves the original Gate F blocker.**
`/ipo_subscription/<anything>/<id>/` returns 200 and renders the company name, IPO year,
anchor table and lock-ins. The slug is not validated. So a company→id map *can* be built by
walking ids, which is exactly what Stage 4A could not do before.

**2. But a wrong slug silently omits the day-wise table**, so the walk cannot measure
day-wise coverage. I caught this by validating the parser against the known-good id 3007
(Adroit Industries) rather than trusting the sweep: with slug `x` the day-wise table was
absent, and my first sweep result of "1 of 61" was therefore an artefact of my own method,
not a property of the site.

**3. Re-testing with the correct slug revealed the real finding: the table is gone from
Adroit's page entirely.** Yesterday `/ipo_subscription/adroit-industries-ipo/3007/` carried
`Date | QIB (Ex Anchor) | NII | NII>₹10L | NII<₹10L | Retail | Total` with Days 1–3 and a
final QIB of 192.68. Today the same URL has 8 tables, **no `Date` header among its 24 `<th>`
cells, no "(Day N)" labels, and no 192.68** — replaced by an allotment-style
`Category × QIB/NII/Retail/Total` table. Adroit closed 29 Sep; allotment has since been
published.

## Coverage by year

61 ids resolved (HTTP 200 on every one — no 4xx, no 5xx, no rate-limiting), spread across
2005–2026 by sampling ids 50…3050 in steps of 50. **The id space is not chronological** —
id 2900 → 2006, id 3050 → 2005, id 2950 → 2026 — so a sequential walk would not have
sampled years, and the spread sampling was necessary.

| Era | ids probed | day-wise table | anchor allocation | lock-in dates |
|---|---|---|---|---|
| 2005–09 | 6 | 0 | 0 (0%) | 0 |
| 2010–14 | 5 | 0 | 2 (40%) | 2 |
| 2015–19 | 11 | 0 | 1 (9%) | 1 |
| 2020–24 | 19 | 0 | 10 (53%) | 10 |
| 2025–26 | 20 | **1** | 12 (60%) | 12 |
| **Total** | **61** | **1** | **25 (41%)** | **25** |

**Earliest year carrying a populated day-wise table: 2026 — and only for an IPO still inside
its bidding/pre-allotment window.** The single hit is **A-One Steels (id 2000)**, closed
28 Sep, 3 bidding days, categories `Date | QIB (Ex Anchor) | NII | NII (>₹10L) | NII (<₹10L)
| Retail | EMP | Total`. Adroit closed one day *later* yet has already lost its table, so the
trigger is allotment publication, not age.

## Estimated IPOs available for L_day1 / L_day2 training

| Source | IPOs with day-wise data |
|---|---|
| Chittorgarh historical backfill | **0** |
| Chittorgarh, live window only | ~1–3 at any moment |
| Forward collection (decision B4) | 0 today, accumulating |

**`L_day1` and `L_day2` cannot be trained from any historical source.** Decision C1's
requirement — train each decision-point model only on data knowable at that moment — can
only be met going forward. At roughly 100 mainboard IPOs a year, C3's ~40-IPO bar is about
**5 months** away; a usable 20-IPO pilot is about 2–3 months. `L_final_3pm` is unaffected in
principle, but note it faces the same problem: no historical 3 pm snapshots exist either
(already acknowledged in C3).

## Recommendation

**1. Do not run Stage 4B's day-wise backfill.** It would spend hours to retrieve data that
is not there. This is not an id-resolution problem any more — ids are now solvable — it is
that Chittorgarh does not archive day-wise bidding detail, exactly as its own note (quoted in
decision B3) warned.

**2. Make decision B4 the primary route, and start it now.** Nightly official NSE + BSE
snapshots for every open IPO are the only way to build this history, and they satisfy rule 2
with two independent official sources. Every night of delay is a permanently lost IPO.

**3. Add a nightly Chittorgarh capture for currently-open IPOs only.** Permitted, ≥3 s, a
handful of requests a night. It is worth it because Chittorgarh's live table carries a finer
split than the exchanges publish — bNII/sNII and an EMP column — and it is the only place
that split is visible. It must be captured before allotment or it is gone.

**4. A backfill *is* worth running, but for anchor and lock-in data, not day-wise.** Those
**are** archived: 25 of 61 ids (41%) carry an anchor allocation table with fund names,
amounts and percentages, plus 30/90-day lock-in dates, rising to ~60% for 2020–26. That
feeds Model H's ownership block directly (`anchor_mf_share`, PLAN.md Part C.4 / Stage 11),
which is currently an unfilled placeholder. I would propose this as a separate, re-scoped
Stage 4C rather than smuggling it into 4B.

**How I would map the remaining companies to ids, within the same constraints.** The
dummy-slug walk already works and needs no page rendering: one request per id returns company
name and year. The full id space is ~3,050, so a complete map costs ~3,050 requests at ≥3 s
≈ **2.7 hours**, resumable, committing every 50 ids. It only becomes worth paying for if
recommendation 4 is approved — for day-wise purposes it buys nothing. A cheaper variant:
walk only ids whose neighbours indicate 2020+ IPOs, though because the id space is not
chronological that saves less than it appears to.

## Constraints observed
- robots.txt re-read first; unchanged; not aborted.
- **71 requests** of 200 (61 sweep + 3 pre-flight + 7 parser/slug validation), each ≥3.2 s apart.
- Stopped early, as instructed, once the mechanism was established.
- Single-threaded, one fixed User-Agent throughout, no retries, no parallelism.
- **Zero 4xx or 5xx responses and no sign of objection** — every one of the 61 ids returned 200.

## Open issues
1. The transience window is not precisely measured. A-One (closed 28 Sep) still had its table; Adroit (closed 29 Sep, allotment published) did not. The trigger looks like allotment publication, but that is an inference from two cases.
2. `data/chittorgarh_id_probe.csv` holds the 61-id map (company, year, anchor, lock-in). It is a useful by-product and is committed.
3. My first sweep's day-wise column is unreliable for the dummy-slug rows and must not be read as coverage; the report above uses only the correct-slug re-tests for that conclusion.

Reply `Gate F2 decision: …` and I will record it verbatim in `DECISIONS.md`.

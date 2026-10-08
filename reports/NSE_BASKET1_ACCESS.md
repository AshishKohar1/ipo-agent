# NSE Basket 1 access test — Priority 2

Probed **2026-10-08** from the laptop, under H18 headers (realistic browser headers to an
official host), ≥3 s between requests, `robots.txt` re-read first.

**Headline: NSE's primary-market data is fully reachable and machine-readable, and one
endpoint reproduces the master's subscription figure exactly on 14 of 14 IPOs. But it is
very probably the *origin* of the figure we already have rather than a second opinion on
it, so it does not by itself lift H14's single-source compromise. The test that would
settle that needs a live mainboard IPO, and the next one opens 13 October.**

---

## 2a. Is it reachable?

`robots.txt` first, every run:

```
User-agent: *
Allow: /
Disallow: /market-data-test
Sitemap: https://www.nseindia.com/sitemap.xml
```

Everything probed below sits outside `/market-data-test`, so it is explicitly permitted.
No login, CAPTCHA, paywall or click-through is involved at any point.

| URL | Result | Machine-readable? |
|---|---|---|
| `nseindia.com/market-data/all-upcoming-issues-ipo` | **HTTP 200**, 312 KB HTML | Server-rendered HTML, not an SPA shell — but the data is better taken from the JSON below |
| `api/all-upcoming-issues?category=ipo` | **HTTP 200**, JSON | **Yes** |
| `api/ipo-current-issue` | **HTTP 200**, JSON | **Yes** |
| `api/ipo-detail?symbol=X&series=EQ` | **HTTP 200**, JSON | **Yes** |
| `api/ipo-active-category?symbol=X&series=EQ` | **HTTP 200**, JSON | **Yes** |
| `api/ipo-bid-details?symbol=X&series=EQ` | **HTTP 200**, JSON | **Yes** |
| `api/public-past-issues` | **HTTP 200**, JSON, **1,474 rows** | **Yes** |
| `api/ipo-category?...` | HTTP 404 | — (guessed name, does not exist) |

This is a complete reversal of the position recorded on 2026-10-01, when every one of these
was logged as refusing this host. The diagnosis then was wrong: it was never a policy or a
robots restriction, it was a WAF filtering on User-Agent, which is the whole substance of
H18.

### What the fields are

`api/all-upcoming-issues?category=ipo` — the calendar:

```json
{"companyName": "HD Fire Protect Limited", "symbol": "HDFIRE", "series": "EQ",
 "status": "Forthcoming", "issueStartDate": "13-Oct-2026", "issueEndDate": "15-Oct-2026",
 "issuePrice": "Rs.258 to Rs.271", "priceBand": "Rs.258 to Rs.271",
 "issueSize": "26284500", "lotSize": "1200"}
```

`series` is worth calling out on its own: **`EQ` / `SME` / `DEBT` comes from the exchange**.
Rule 6 requires separate models for SME and mainboard, and segment is currently carried
from the bid-time record. This would make it an exchange-stated fact instead.

`api/ipo-active-category?symbol=X&series=EQ` — category-wise subscription, with an
`updateTime`:

```json
{"category": "Qualified Institutional Buyers(QIBs)", "noOfShareOffered": "1079840",
 "noOfSharesBid": "30289750", "noOfTotalMeant": "28.05022040302267"}
...
{"updateTime": "Updated as on 25-Feb-2026 19:00:00"}
```

`api/public-past-issues` — 1,474 historical issues carrying `ipoStartDate`, `ipoEndDate`,
`listingDate`, `issuePrice`, `priceRange`, `securityType` and `symbol`.

---

## The numbers, checked rather than assumed

14 most recent mainboard IPOs in the master, each with its recorded `Total`, against both
candidate endpoints:

| symbol | master Total | `ipo-detail` | `ipo-active-category` | detail vs active |
|---|---|---|---|---|
| KISSHT | 9.50 | 6.67 | **9.50** | −29.8% |
| OMPOWER | 3.33 | 2.37 | **3.33** | −28.6% |
| SAIPARENT | 1.05 | 0.63 | **1.05** | −39.6% |
| POWERICA | 1.45 | 0.63 | **1.45** | −56.3% |
| AMIRCHAND | 3.23 | 2.63 | **3.23** | −18.6% |
| CMPDI | 1.05 | 0.57 | **1.05** | −45.8% |
| GSPCROP | 1.61 | 1.46 | **1.61** | −9.0% |
| INNOVISION | 3.32 | 2.39 | **3.32** | −28.1% |
| RSL | 1.12 | 0.64 | **1.12** | −43.3% |
| SEDEMAC | 2.68 | 1.66 | **2.68** | −38.2% |
| OMNI | 1.14 | 0.50 | **1.14** | −56.3% |
| PNGSREVA | 1.23 | 0.53 | **1.23** | −56.9% |
| CLEANMAX | 0.94 | 0.81 | **0.94** | −13.9% |
| SRTL | 43.66 | 32.31 | **43.66** | −26.0% |

Raw output: `reports/NSE_BASKET1_PROBE.csv`.

**Two things follow, and the second is the one that matters.**

**1. `ipo-active-category` is the final figure; `ipo-detail` is not.** Active-category
matches the master to two decimal places on **14 of 14**. `ipo-detail`'s `bidDetails` block
is systematically *lower* — between 9% and 57% lower — because it is an intermediate cut,
not the close. Every active-category `updateTime` on a closed issue reads `19:00:00` on the
final bidding day, which is the published final update. **Anything built on this must read
`ipo-active-category`.** Using `ipo-detail`, which is the more obvious name and the one with
the richer-looking payload, would understate subscription by tens of percent and push every
verdict toward `no`.

**2. An exact match on 14 of 14 is evidence of a shared origin, not of independence.**
This is the finding to be careful about. Rule 2 needs two *independent* sources, and the
standing example in `CLAUDE.md` is that Chittorgarh and IPOMatrix are not two sources
because they share a parent. Agreement to two decimal places on fourteen consecutive issues
is not what two independent measurements look like; it is what a figure and a copy of that
figure look like. The likeliest reading is that **NSE publishes the number and Chittorgarh
republishes it**, so our live source and this new one are the mirror and the original.

That still buys something real — reading the original instead of a mirror removes a
transcription step and a third party's uptime from the path — but it is **not** a second
opinion, and it must not be recorded as a rule-2 reconciliation.

### Also worth knowing: it persists after listing

NITYAS and VNL both listed 2026-10-08 and still return full category-wise bid details;
SRTL (February) and KISSHT (May) still answer. This is the opposite of Chittorgarh, whose
table is removed at allotment (H1) — which is why Stage 4B had to be cancelled. **NSE
appears to archive what Chittorgarh discards.** That is a separate and possibly larger
prize than the second-source question, and it is what makes the forward-collection
compromise in H14 less permanent than it looked.

---

## 2b. What lifting H14's single-source compromise would actually take

Honest answer: **more than this probe establishes.** Four things, in order.

**1. Settle whether `ipo-active-category` updates intraday.** The live decision is made at
15:00, so what matters is not the 19:00 final but whether the same endpoint reports a
partial figure during the bidding window. Every closed issue shows only a 19:00
`updateTime`, which is consistent with either behaviour and proves neither. **This cannot be
tested today — no mainboard IPO is open.** The next one is **HDFIRE (HD Fire Protect),
EQ, 13–15 October**. The test is to poll `api/ipo-active-category?symbol=HDFIRE&series=EQ`
at 15:00 on each bidding day, record the `updateTime` and total, and compare with the 19:00
final. If it moves intraday, NSE can carry the live decision; if it only ever publishes at
19:00, it cannot, and it stays an archival and verification source.

**2. Find a genuinely independent second source, which BSE is not.** Probed the same day:

| BSE endpoint | Result |
|---|---|
| `api.bseindia.com/.../GetIPODemandSchedule` | HTTP 200 returning a 1,814-byte ASP.NET error page |
| `api.bseindia.com/.../DisplayIPO` | the same error page |
| `api.bseindia.com/.../IPODemandSchedule` | the same error page |
| `bseindia.com/robots.txt` | returns the homepage HTML — **BSE publishes no robots.txt** |

So there is **no working BSE subscription endpoint**, and the independence problem is not
solved by adding NSE. It would be solved by a source that measures rather than
republishes — in practice, BSE's own bid data if it ever becomes reachable, because a
mainboard IPO is bid on both platforms and the two books are genuinely different
measurements.

**3. Resolve symbols properly, which guessing does not.** Two checks against our own
Chittorgarh snapshots failed, and both failures are instructive:

* **RKFAL** — Chittorgarh 0.44×, NSE **0.00×**. Not a disagreement: R.K. Fashion
  Accessories is a **BSE SME** issue, so there were no NSE bids to count. NSE's book covers
  NSE-platform issues only.
* **PARAMOUNT** — the symbol resolves to a *different company*, whose `updateTime` is
  **30-Sep-2024**. A guessed ticker silently returned another issue's subscription.

Both argue for resolving through `api/all-upcoming-issues` and `api/public-past-issues`,
which return the symbol alongside the company name and dates, rather than constructing one.
The second failure is the dangerous kind: it returns a plausible number for the wrong
company, which is precisely the class of error match provenance was introduced to stop.

**4. Expect the WAF to reset under sustained load.** After roughly 40 requests in a session
the host began closing connections (`ConnectionResetError 10054`). It recovered after a
re-warm and a 15–90 s backoff. Any production use needs that backoff built in from the
start, exactly as `listing_prices.Fetcher` already does for the bhavcopies.

---

## Two incidental finds that are worth more than they look

**`api/public-past-issues` carries real issue-open dates for 1,474 issues.** The master's
`issue_open_date` column is a known defect: it holds the **listing** date, and true open
dates exist for only 313 of 652 rows (`CLAUDE.md`, "Known data defect"). This endpoint
returns `ipoStartDate`, `ipoEndDate` *and* `listingDate` as separate fields from the
exchange. That is a direct fix for the defect, across the whole history rather than 2021+,
and it would also give the leakage cut-offs a real date to work from.

**`api/fiidiiTradeReact` returns FII/DII flows** — relevant to Priority 3b — but **today
only**. Passing `?date=` or `?from=&to=` is accepted with HTTP 200 and ignored: the same
two rows for 08-Oct-2026 come back regardless. It is a live ticker, not a history endpoint,
so it cannot answer the 2025-versus-other-years question on its own.

---

## Recommendation

1. **Do not change the live 15:00 source yet.** Chittorgarh stays primary until the HDFIRE
   test shows whether NSE publishes intraday. Switching on an untested assumption about
   update frequency would risk scoring a stale or zero figure at 15:00.
2. **Run the HDFIRE test on 13–15 October.** It is three polls on three days and it decides
   the whole question.
3. **Add NSE as a verification and archival source now**, which needs no decision about the
   live path: it reconciles the historical record, it survives allotment, and it gives
   exchange-stated `series` and real issue-open dates.
4. **Do not record NSE plus Chittorgarh as a rule-2 reconciliation.** Fourteen exact matches
   say mirror, not independence. If NSE is adopted it should *replace* Chittorgarh as the
   source of record for mainboard subscription, with Chittorgarh demoted to corroborator —
   which is exactly what H14 said should happen if NSE ever answered.

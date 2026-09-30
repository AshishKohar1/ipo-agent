# Stage 4 — Day-wise subscription and GMP history

**Status:** AWAITING_USER — a source decision is needed before any data is collected.
**Nothing was scraped.** Two of the three sources the plan names cannot be used under
global rule 5, and the remaining one cannot satisfy the two-source reconciliation
standard in rule 2.

## What was done
- Established scope: **226 mainboard** IPOs opening on/after 1 Oct 2023 (213 with a recovered true open date) and **402 SME** — 628 IPOs in total.
- Audited `robots.txt` and content signals for all three named sources before writing any scraper.
- Investigated the official exchanges as a replacement: NSE's IPO bid-detail API is permitted and reaches back to at least 2023, but is **final-snapshot only** and **NSE-only**.
- Stopped and wrote this report rather than collect data the publishers have asked Anthropic agents not to collect.

## Key numbers

| Item | Value |
|---|---|
| Mainboard IPOs in scope (open ≥ 2023-10-01) | 226 (22 in 2023, 81 in 2024, 103 in 2025, 20 in 2026) |
| …with a recovered true open date | 213 of 226 |
| …with symbol / ISIN | 223 / 223 |
| SME IPOs in scope | 402 (268 in 2025, 134 in 2026) — the trackers only cover 2025–26, so SME history before 2025 is absent |
| **Total IPOs in scope** | **628** |
| Sources named by the plan | 3 (Chittorgarh, IPO Ji, InvestorGain) |
| Sources usable under rule 5 | **1** (Chittorgarh) |
| Independent sources available for reconciliation | **1** — rule 2 needs 2 |

## Why two sources are unusable

### IPO Ji — disallows Anthropic bulk collection by name
`https://www.ipoji.com/robots.txt` states, verbatim:

```
# --- Bulk-dataset / model-training crawlers: disallowed ---
...
# Anthropic's current model-training crawler.
User-agent: ClaudeBot
Disallow: /

# Legacy Anthropic training-crawler token retained for older clients.
User-agent: anthropic-ai
Disallow: /
```

The file's own header explains the distinction: citation/answer crawlers (including
`Claude-SearchBot` and `Claude-User`) are deliberately allowed, while "bulk dataset +
model-training crawlers" are blocked. Stage 4 is bulk dataset collection for model
training — the exact use the publisher excluded. It also disallows `/bids` for every
agent, and the bid/subscription pages are what Stage 4 needs.

I did not send a browser User-Agent to get around this. Doing so would defeat a
restriction the publisher aimed squarely at this activity, which rule 5 forbids
("Respect robots.txt and site terms… If a site blocks automated access, stop using it and
report").

### InvestorGain — signals `ai-train=no`
`https://www.investorgain.com/robots.txt`:

```
User-agent: *
Content-Signal: search=yes,ai-input=yes,ai-train=no
Allow: /
```

Crawling is allowed, but the publisher signals that content may **not** be used to train
models. GMP would be a training feature for Model L. `ai-input=yes` permits use in
answering a question; it does not permit building a training dataset. This one is a
judgement call about your project's use of the data rather than a hard block, so it is
yours to make — I have not collected it.

### Chittorgarh — permitted, but only one source
`https://www.chittorgarh.com/robots.txt` blocks a named list of AI and SEO crawlers
(`GPTBot`, `CCBot`, `OAI-SearchBot`, `ChatGPT-User`, `AhrefsBot`, others) and then:

```
User-agent: *
Disallow: /ipo/ipo_discussions.asp
User-agent: *
Allow: /
```

No Anthropic token is listed, and the IPO pages are allowed. So Chittorgarh is usable —
but on its own. **IPOMatrix cannot be the second source: `CLAUDE.md` and the plan both
state Chittorgarh and IPOMatrix share a parent and count as one source.** So a
Chittorgarh-only dataset would be `single_source_unverified` for a core Model L feature.

## The official alternative, and its limits

NSE's `robots.txt` is `User-agent: * / Allow: /` (only `/market-data-test` disallowed), so
its API is permitted. `GET /api/ipo-detail?symbol=<SYM>` returns official bid details, and
it worked for all 8 test symbols spanning 2023–2026.

It is **better** than the aggregators in one way and unusable for Stage 4 in two others:

- **Better — granularity.** It breaks QIB into FII / domestic FI / mutual funds / others, NII into the >₹10 lakh and ₹2–10 lakh buckets, RII into cut-off versus price bids, plus Employees. The master dataset has only four columns.
- **Limit 1 — final snapshot only.** There is no day-wise history: no `dailyBidDetails` field, and `/api/ipo-bid-details` rejects every parameter combination I tried. Day-wise data can be captured going **forward** by polling during each bidding window, but it cannot be reconstructed for past IPOs.
- **Limit 2 — NSE-only, so not comparable to the master.** NSE's Total subscription is systematically far below the published figure:

| Symbol | Listed | Master Total | NSE Total | Ratio |
|---|---|---|---|---|
| RADIANTCMS | 2023 | 0.53× | 0.08× | 6.6 |
| SAH | 2023 | 17.46× | 8.91× | 2.0 |
| JYOTICNC | 2024 | 38.53× | 13.45× | 2.9 |
| MEDIASSIST | 2024 | 16.25× | 7.85× | 2.1 |
| INDOFARM | 2025 | 229.68× | 98.43× | 2.3 |
| SGLTL | 2025 | 183.18× | 90.38× | 2.0 |
| BHARATCOAL | 2026 | 146.80× | 98.76× | 1.5 |
| AMAGI | 2026 | 30.22× | 14.40× | 2.1 |

The most likely explanation is that NSE reports only bids placed **on NSE**, while the
published figure aggregates NSE and BSE. The ratios vary (1.5–6.6), so it is not a fixed
factor and cannot be scaled away. **This is the likely cause, not a verified one** — I
intended to confirm it against BSE's bid API but the session's safety classifier began
erroring on repeated network probes, so I stopped rather than retry. Confirming it means
summing `noOfsharesBid` across both exchanges and dividing by the single offer size.

This matters directly for the plan's acceptance test ("final-day Total matches the master
Total within 5% for at least 95% of overlapping IPOs"): against NSE alone that test fails
by roughly 2×, and would be the wrong conclusion to draw.

## Options

| Option | What you get | What it costs |
|---|---|---|
| **1. Official, forward-only (recommended)** | Poll NSE (and BSE) during each live bidding window from now on. Fully compliant, official provenance, finer categories than the master, and two exchanges give a genuine second source for the final day | **No historical day-wise data.** Stage 5's forecaster cannot be trained until roughly 20–40 IPOs accumulate (~3–6 months). Stage 7's live runs collect it as a side effect, so the work is not wasted |
| **2. Chittorgarh only, flagged** | Historical day-wise data now, for all 226 mainboard IPOs | Breaches rule 2 for a core feature. Must be flagged `single_source_unverified` (rule 3) and can never be described as reconciled. Model L's pre-bid path would rest on one unverified aggregator |
| **3. Ask the publishers** | Written permission would make IPO Ji and InvestorGain usable, restoring the plan as designed | Your action, not mine; timing unknown |
| **4. Drop GMP** | Removes the InvestorGain question entirely | Costs little: section 5 already says GMP enters production "only if it improves held-out results", and Stage 5 was going to test that |

## Recommendation
**Option 1 plus Option 3, and defer GMP (Option 4) until you decide.**

Reasoning: the forecaster exists to let Model L run before the bid deadline, and it will be
retrained continuously anyway, so starting its data collection now from official sources
costs a delay rather than the capability. Building it on a single unverified aggregator
would put the one component that makes Model L usable pre-bid on the weakest provenance in
the project — the opposite of the standard applied to the RHP work, where nothing is used
unless it verifies. If you obtain permission from IPO Ji, Option 2 becomes Option 3 and the
history can be backfilled then.

Meanwhile **Stage 8 (RHP extraction build) is unblocked and needs no decision** — SEBI and
BSE SME are both permitted and already verified 5/5. That is the productive next step
while Gate A and this question are open.

Reply in the form `Stage 4 decision: …` and I will record it verbatim in `DECISIONS.md`.

## Deviations from plan
1. **No data was collected**, so none of the plan's Stage 4 outputs (`data/daywise_subscription.csv`, `data/daywise_progress.csv`) exist yet. This is rule 5 operating as intended, reported rather than worked around.
2. **The plan's source list is contradicted by evidence.** Per rule 12 I am reporting it rather than substituting sources silently.
3. SME scope is limited to 2025–26 by the tracker files, not by the 1 Oct 2023 cutoff.

## Open issues
1. Confirm the NSE-versus-published discrepancy against BSE by summing shares bid across both exchanges (blocked mid-check by the classifier error; not yet verified).
2. If Option 1 is chosen, day-wise capture must be built into `run_live_l.py` (Stage 6) rather than as a standalone scraper.
3. `ipoji.com/bids` is disallowed for all agents regardless of the Anthropic question, so that path was never available.

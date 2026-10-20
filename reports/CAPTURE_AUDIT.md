# Capture audit

Window: the last 7 days, NSE trading days only (weekends and NSE holidays both excluded; calendar in data/nse_trading_holidays.csv). Generated 2026-10-21 00:30 IST.

**Every trading day in the window produced a capture.**

A gap means the job left *no attempt at all* — an infrastructure failure. A job that ran and captured nothing is a quiet market, not a gap, and is not counted here. An NSE holiday is not a working day and never appears below.

| date | 15:00 attempts | day-end attempts |
|---|---|---|
| 2026-10-15 | 1 | 1 |
| 2026-10-16 | 1 | 1 |
| 2026-10-19 | 1 | 1 |

## What catch-up recovered

Nothing to recover.
## Not recoverable, by nature

* **final_subscription** — Chittorgarh removes the subscription table at allotment (H1), so a missed day's final figure does not exist anywhere we may fetch from. Not retryable.
* **bid_email** — A 15:00 bid signal is never re-sent. After the 16:00 broker cutoff it invites a bid that cannot be placed. The leg fails loudly instead.

# Capture audit

Window: the last 7 days, weekdays only. Generated 2026-10-16 00:45 IST.

**0 missed 15:00 leg(s), 1 missed day-end leg(s).**

A gap means the job left *no attempt at all* — an infrastructure failure. A job that ran and captured nothing is a quiet market, not a gap, and is not counted here.

| date | 15:00 attempts | day-end attempts |
|---|---|---|
| 2026-10-12 | 9 | **0 — MISSED** |
| 2026-10-13 | 1 | 1 |
| 2026-10-14 | 1 | 1 |
| 2026-10-15 | 1 | 1 |

## What catch-up recovered

Nothing to recover.
## Not recoverable, by nature

* **final_subscription** — Chittorgarh removes the subscription table at allotment (H1), so a missed day's final figure does not exist anywhere we may fetch from. Not retryable.
* **bid_email** — A 15:00 bid signal is never re-sent. After the 16:00 broker cutoff it invites a bid that cannot be placed. The leg fails loudly instead.

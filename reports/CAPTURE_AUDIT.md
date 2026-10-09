# Capture audit

Window: the last 4 days, weekdays only. Generated 2026-10-10 00:46 IST.

**1 missed 15:00 leg(s), 2 missed day-end leg(s).**

A gap means the job left *no attempt at all* — an infrastructure failure. A job that ran and captured nothing is a quiet market, not a gap, and is not counted here.

| date | 15:00 attempts | day-end attempts |
|---|---|---|
| 2026-10-07 | 1 | **0 — MISSED** |
| 2026-10-08 | **0 — MISSED** | 1 |
| 2026-10-09 | 5 | **0 — MISSED** |

## What catch-up recovered

### 2026-10-07

* listing prices — no live prediction is awaiting an outcome
* index closes — 15 closes, 0 NULL with a reason

### 2026-10-09

* listing prices — no live prediction is awaiting an outcome
* index closes — 15 closes, 0 NULL with a reason

## Not recoverable, by nature

* **final_subscription** — Chittorgarh removes the subscription table at allotment (H1), so a missed day's final figure does not exist anywhere we may fetch from. Not retryable.
* **bid_email** — A 15:00 bid signal is never re-sent. After the 16:00 broker cutoff it invites a bid that cannot be placed. The leg fails loudly instead.

The 15:00 leg was missed on 2026-10-08 and was **not** re-sent. That is the designed behaviour, not an outstanding task.

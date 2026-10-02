# Claude Code routines — audit and recommendations

2026-10-03. Five routines exist. **I have changed none of them** — the user deletes them at
claude.ai/code → Routines.

The headline: **three of the five call `run_live_l.py`, which Priority 1c retired.** They
are not merely duplicates of the GitHub Actions workflow — until today one of them was
actively destroying the good report. `ipo-score-1500` ran `run_live_l.py --score`, which
reads NSE and BSE (both refuse this host) and wrote to `reports/live/<date>.md`, the same
path the working Chittorgarh pipeline uses. That is what overwrote the 2 Oct report.

| # | Routine | Schedule (IST) | Runs | Duplicates Actions? | Recommendation |
|---|---|---|---|---|---|
| 1 | `ipo-score-1500` | 15:00 daily | `run_live_l.py --score` | **Yes** — Actions 09:30 UTC | **DELETE** |
| 2 | `ipo-notify-1530` | 15:30 daily | `run_live_l.py --notify` | No — but `--notify` no longer exists | **DELETE** |
| 3 | `ipo-final-capture-1730` | 17:30 daily | `run_live_l.py --final` | **Yes** — Actions 12:00 UTC | **DELETE** |
| 4 | `ipo-ingest-outcomes` | 08:00 Mon & Thu | `ingest_outcomes.py` | No | **KEEP, disabled** until Priority 5c is solved |
| 5 | `ipo-retrain-monthly` | 08:00, 1st of month | `retrain_l.py` | No | **KEEP** — the user's instinct is right |

---

## 1. `ipo-score-1500` — delete

Duplicates the Actions 15:00 job, which now does strictly more: Chittorgarh (which works)
rather than NSE/BSE (which do not), plus the email. The routine's own prompt still carries
the NSE/BSE reconciliation description, which is no longer what the 15:00 job does.

It is also the routine that caused the damage. After Priority 1c it can no longer overwrite
anything — `--score` is now an alias for `--probe` and writes to
`reports/live/exchange_probe/` — but there is no reason to keep running it daily.

## 2. `ipo-notify-1530` — delete

`run_live_l.py --notify` was removed with the schedule change. The email *is* the
notification now, and it is sent by the 15:00 Actions job, which lands well before the
16:00 broker cutoff. Keeping a second reminder at 15:30 would mean two emails a day.

## 3. `ipo-final-capture-1730` — delete

Duplicates the Actions 17:30 job. That job now also captures the day's index closes
(Priority 6), which the routine does not.

## 4. `ipo-ingest-outcomes` — keep, but disable it until it can work

**Actions cannot replace this one**, and it does something Actions cannot: the reconciliation
mismatches need reading, not just logging. A `MISMATCH -> NULL` between two official sources
is a judgement call about which source to trust.

But it cannot work yet, for two independent reasons (Priority 5):

* **No listing-price source.** NSE times out, BSE returns 403, yfinance is banned because it
  returns split-adjusted prices. No label has ever reached `predictions_log.csv`.
* **No segment source for historical rows.** Fixing the rule 6 violation means the segment
  must come from a bid-time record, and `predictions_log.csv` has no rows from before the
  live pipeline started. All 170 post-cutoff listings therefore come back
  `segment_undetermined` and are correctly not ingested.

Running it twice a week to report "nothing ingested" costs Claude usage for no information.
**Disable it, and re-enable once the Chittorgarh listing-day sweep (Priority 5c) is in
place.** Do not delete it — the prompt carries the yfinance warning and the
`single_source_REJECTED` discipline, which are worth preserving.

## 5. `ipo-retrain-monthly` — keep

The user's instinct is right, and this session is the evidence. The retrain *logged* "L2
delivered 76.0% against an 80% promise" on 2 Oct. A deterministic job would have logged it
again next month and the month after. What the number needed was someone to widen the
window and find that the shortfall persists at 125–160 fires while L1's does not — which is
H16, and which changes a promise the system makes to the user.

Twelve runs a year is negligible usage for the one job whose output is a judgement rather
than a file.

One change worth making to its prompt: it says to surface a hit-rate shortfall "with the
fires/hits count". It should also say **to widen the out-of-sample window when a shortfall
appears**, because a single thin window cannot distinguish a mis-set threshold from bad luck
— and that distinction is the whole value of the alert.

---

## The 21:48 runs on 2 Oct — what I can and cannot confirm

**Confirmed, and it is not what the question assumed.** The ~21:48 IST events on 2 Oct were
the **Claude Code routines**, run manually. `list_task_runs` gives their start times as
16:14:15Z, 16:15:15Z and 16:17:15Z — 21:44, 21:45 and 21:47 IST. Three routines whose crons
are 15:00, 15:30 and 17:30 IST cannot all fire inside a three-minute window, and none of
those times is any of their schedules. They were "Run now".

The same data shows the laptop-side scheduling is unreliable, which is the independent
argument for Actions: `ipo-score-1500` has only **two runs in total** — 1 Oct at 15:02 IST
(its cron, firing correctly) and 2 Oct at 21:47 IST (manual). **Its 2 Oct 15:01 cron never
fired at all**, because these routines only run while the desktop app is open.

**Not confirmed: whether the GitHub Actions *schedule* fired.** There is no `gh` CLI and no
API token in this environment, so I cannot read the Actions run list. What the dates say:

* The workflow first landed on `main` at **2026-10-01 21:50 IST (16:20 UTC)**.
* Scheduled opportunities since then were **2 Oct 09:30 UTC** and **2 Oct 12:00 UTC**. The
  1 Oct 12:00 UTC slot predates the file; 3 Oct is a Saturday and the cron is `1-5`.
* So **exactly two scheduled fires were due**, against three observed failures.

Three runs therefore cannot all have been scheduled — and if any of them appeared at
21:48 IST (16:18 UTC), that matches **neither** schedule and was a manual dispatch.

**To settle it in one look:** open the workflow's run list and read the trigger label on
each run — GitHub shows `schedule` or `workflow_dispatch` per run. All three failed with the
same joblib error regardless, so the distinction changes nothing about the fix; it only tells
you whether the cron is live. The next scheduled fire is **Monday 5 Oct 09:30 UTC = 15:00
IST**, which is also the first real test.

# LIVE_SETUP — Model L in production

Rewritten **2026-10-08**. Model `model_l_v1.1` / `L_final_3pm`, decision rule **H17,
ratified**. The previous version of this file described `model_l_v1.0`, a calibrated-probability
cut-off, five app routines and `run_live_l.py`. **None of that is how the system runs any
more**, which is why this is a rewrite rather than an edit.

The system scores, logs, reports and emails. **No order is ever placed.** The verdict is
advice you act on manually, before your broker's 4:00 PM cutoff.

---

## 1. The schedule — exactly three jobs, all on GitHub Actions

Everything runs from `.github/workflows/live-model-l.yml`. There are **no app routines and
no Task Scheduler tasks** for the live path any more; `ipo-score-1500`, `ipo-notify-1530`
and `ipo-final-capture-1730` were deleted on 2026-10-08 because all three called the retired
`run_live_l.py` and duplicated what Actions already does.

| When (IST) | Cron (UTC) | What runs | What it does |
|---|---|---|---|
| **15:00**, weekdays | `30 9 * * 1-5` | `send_daily_email.py` | Scores every mainboard IPO closing today, logs the predictions, appends the 1500 snapshot, writes `reports/live/<date>.md`, **sends the bid/no-bid email** |
| **19:30**, weekdays | `0 14 * * 1-5` | `capture_audit.py --catch-up`<br>`send_daily_email.py --final`<br>`listing_prices.py --capture-listing-day` | Recovers any missed day, then captures final subscription, the 15 index closes, and listing-day prices for anything that listed today |
| **10:30**, Saturdays | `0 5 * * 6` | `capture_audit.py --audit --days 7` | Checks every weekday that week left an attempt. **Fails the run if one did not** |

Plus `.github/workflows/retry-infra-failure.yml`, which is not scheduled — it fires when a
live run finishes and re-runs it if GitHub dropped it (section 4).

Two app routines remain, and they are the only two that should:

| Routine | When | Why it is still a routine |
|---|---|---|
| `ipo-retrain-monthly` | 1st, 08:00 | Its output is a **judgement**, not a file. It re-derives both thresholds walk-forward, holds any move beyond 25% for review, and reports drift. Worth having read rather than merely run |
| `ipo-ingest-outcomes` | Mon & Thu, 08:00 | It is the only job that **harvests IPOs you did not bid on** into `data/new_listings.csv`, which is how the training set grows. It is **not** redundant with the day-end capture — but see the warning in section 5 |

### Why 15:00 and not 15:30

GitHub's scheduler drifts 5–15 minutes under load. 15:00 absorbs that and still lands
45 minutes before the 16:00 cutoff (E1). 15:30 would not.

### Why 19:30 and not 17:30

NSE Indices publishes the day's index closes after its settlement run. At 17:30 the table
was incomplete, so index closes were being captured half-formed. 19:30 is after publication
and still the same evening.

---

## 2. The one rule that governs the email

**The 15:00 leg will not send outside 14:00–16:00 IST, and is never caught up.**

`send_window()` in `send_daily_email.py` refuses on both sides, for two different reasons:

* **At or after 16:00** — past the broker cutoff. A bid signal then is not late
  information, it is *wrong* information: it invites a bid that can no longer be placed.
  The leg writes its report, prints `REFUSING TO SEND`, and **exits non-zero** so the run
  goes red.
* **Before 14:00** — the model is `L_final_3pm`. It was fitted on the final-day
  late-afternoon subscription figure, and a morning figure is a different distribution, not
  an early look at the same one.

This is not theoretical. Every 15:00 marker on record before 2026-10-08 was stamped **after**
the cutoff — 16:53, 21:49, 22:11, 00:06, 00:39 — because GitHub queued a delayed job and
the leg sent anyway. The window is what closes that.

There is deliberately **no flag that re-sends a missed email.** `--dry-run` composes and
prints for inspection; nothing sends.

---

## 3. What the email says

`SUBJECT_PREFIX` is exactly `IPO decision - ` — plain ASCII hyphen, lowercase `d`, no em
dash. It is asserted byte-exact in the self-test, because mail filters match literally.

The decision is **one comparison** (H17, ratified 2026-10-06):

```
  L1 (any listing gain):  BID    90% promise  fires >= 28.39x
  L2 (gain above 10%):    no     80% promise  fires >= 54.02x
```

Each level is **the threshold at which that share of IPOs the model had never seen met the
target — walk-forward, never in-sample.** The thresholds live in
`models/model_l_v1.1_thresholds.json`; nothing hardcodes them.

**No probability appears anywhere in the decision.** The calibrated probability is still
computed into `predictions_log.csv` under `diagnostics`, labelled *not in the decision
path*, purely as a drift monitor — a probability that starts disagreeing with the threshold
is early warning that the threshold needs re-deriving. G2 still holds: the report prints the
verdict and the level met, never a number presented as your chance.

**GMP is never fetched** (D1). You fill it in; whatever you write is logged so its
incremental value over subscription can be measured later (D2). No GMP rule influences a
verdict.

---

## 4. When GitHub itself drops a run

On 2026-10-07 the day-end run was cancelled before a single step executed:

```
The job was not acquired by Runner of type hosted
Correlation ID d42e69c9-c697-45bc-90e6-cc8129f18f5c
```

Nothing inside that job could retry it, because the job never started. Three layers now
cover it:

1. **`retry-infra-failure.yml`** re-runs the failed jobs — but only when the run executed
   **no steps at all**, which is the infrastructure signature. A run that failed inside our
   own code is left red on purpose. Bounded at 3 attempts.
2. **`capture_audit.py --catch-up`** at the start of each day-end run recovers the
   recoverable part of the previous few days.
3. **The Saturday audit** fails the week if any weekday still has no attempt.

### What a missed day can and cannot recover

| | Recoverable? | Why |
|---|---|---|
| Listing-day prices | **Yes** | Both exchanges keep a per-date bhavcopy archive, read back exactly as reported |
| The 15 index closes | **Yes** | NSE Indices' endpoint is a historical endpoint; a past date is an ordinary query |
| Final subscription | **No, ever** | Chittorgarh publishes the table only while an IPO is open and replaces it at allotment (H1). The figure does not exist anywhere we may fetch from |
| The 15:00 bid email | **No, by design** | See section 2 |

`capture_audit.py` records the last two as permanent rather than leaving a hole that looks
like a fetch somebody could retry.

A gap is measured by `live_markers.attempts()`, **not** `already_ran()`. The distinction
matters: a job that ran and captured nothing is a quiet market, and counting that as a gap
would cry wolf every holiday-adjacent week.

---

## 5. Open items you should know about

**`ipo-ingest-outcomes` runs but has never produced a usable label.** All 15 rows in
`data/new_listings.csv` carry `listing_gain_pct = NULL` and `reconciled = no_source`. Its two
price sources are the NSE and BSE *historical-quote APIs*, and it also prices up to three
days after listing — which the Stage 27 standing rule exists to forbid, because a price read
later has been silently restated for any split or bonus since. It should be rewired to take
its prices from `listing_prices.py`'s bhavcopy path. Until then its harvest half works and
its pricing half does not.

**Subscription is single-source** (H14): Chittorgarh only. Rule 2 cannot be applied to it,
so every snapshot row is flagged `single_source_unverified` and the email says so. Priority 2
is testing whether NSE's Basket 1 primary-market data can become the second source.

**The 12-month email backtest under-delivers both promises** — L1 85.7% against 90%, L2
72.2% against 80%. A tripwire is recorded (H19) rather than an adjustment: two consecutive
under-delivering windows re-derive the threshold; one does not.

---

## 6. Secrets

Three repository secrets, set at **Settings → Secrets and variables → Actions**. They exist
nowhere else — not in a file, not in a routine, not in this document.

| Secret | Used for |
|---|---|
| `GMAIL_ADDRESS` | the sending account |
| `GMAIL_APP_PASSWORD` | a Gmail **app password**, not the account password |
| `EMAIL_TO` | the recipient; falls back to `GMAIL_ADDRESS` when unset |

**A missing secret fails the run.** It never silently skips the email, because a skipped
email looks identical to a quiet market, and silence must always mean something broke.

---

## 7. Your daily routine

1. **~15:00** — the email arrives. Verdicts are `BID` / `no`, each with the subscription
   level that fired it. You can check that number against your own broker screen, which is
   the practical gain over a probability.
2. Form your own view on GMP.
3. **Decide before 4:00 PM.** The standing caveat holds: a near-threshold `no` at 3pm is
   uncertain rather than negative, because the 3pm figure understates final demand. The size
   of that understatement is still being measured by the paired 15:00/19:30 captures.
4. **If no email arrives on a day an IPO was closing, the decision was not delivered** —
   and it will not arrive late. Check the Actions run; the report for the day still exists
   at `reports/live/<date>.md` and says what the verdict would have been.
5. **Saturday** — if the audit went red, a weekday lost a capture. The report is
   `reports/CAPTURE_AUDIT.md`.

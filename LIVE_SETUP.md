# LIVE_SETUP — Model L in production

Rewritten **2026-10-08**. Model `model_l_v1.1` / `L_final_3pm`, decision rule **H17,
ratified**. The previous version of this file described `model_l_v1.0`, a calibrated-probability
cut-off, five app routines and `run_live_l.py`. **None of that is how the system runs any
more**, which is why this is a rewrite rather than an edit.

The system scores, logs, reports and emails. **No order is ever placed.** The verdict is
advice you act on manually, before your broker's 4:00 PM cutoff.

---

## 1. The schedule — all on GitHub Actions, all cron in UTC

Everything runs from `.github/workflows/live-model-l.yml`. There are **no app routines and
no Task Scheduler tasks** for the live path any more; `ipo-score-1500`, `ipo-notify-1530`
and `ipo-final-capture-1730` were deleted on 2026-10-08 because all three called the retired
`run_live_l.py` and duplicated what Actions already does.

**All cron is UTC.** GitHub reads cron as UTC and nothing else; IST is UTC + 5:30.

| When (IST) | Cron (UTC) | What runs | What it does |
|---|---|---|---|
| **14:15** | `45 8 * * 1-5` | `send_daily_email.py` | Email attempt 1 |
| **14:30** | `0 9 * * 1-5` | `send_daily_email.py` | Email attempt 2 |
| **14:45** | `15 9 * * 1-5` | `send_daily_email.py` | Email attempt 3 |
| **15:00** | `30 9 * * 1-5` | `send_daily_email.py` | Email attempt 4. Scores every mainboard IPO closing today, logs the predictions, appends the 1500 snapshot, writes `reports/live/<date>.md`, **sends the bid/no-bid email** |
| **19:30** | `0 14 * * 1-5` | `capture_audit.py --catch-up`<br>`send_daily_email.py --final`<br>`listing_prices.py --capture-listing-day` | Day-end: recovers any missed day, then final subscription, the 15 index closes, and listing-day prices for anything that listed today |
| **10:30 Sat** | `0 5 * * 6` | `capture_audit.py --audit --days 7` | Checks every weekday that week left an attempt. **Fails the run if one did not** |
| **11:00 / 13:00 / 15:01 / 17:31** | `30 5` / `30 7` / `31 9` / `1 12`, Mon–Fri | `hdfire_poll.py` | Task 9 only, 13–15 Oct. Exits immediately on any other date |

Four email attempts, not one, because **the first that succeeds sends and the rest exit
green** on the sent marker (`data/sent_markers.csv`, keyed by IPO and date). All four sit
inside the 14:00–16:00 send window.

The `0 12 * * 1-5` cron — the retired 17:30 day-end leg — is **gone and deliberately not
reused**, even for a poll. A cron string that looks like the old schedule is a trap for
whoever reads this next.

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

## 1b. The external trigger — and why it is not optional

**GitHub's scheduler cannot be relied on here.** Measured from the Actions API across
every scheduled run between 2 and 8 October:

| run | mode | cron (UTC) | due (UTC) | actually started (UTC) | late by |
|---|---|---|---|---|---|
| 1 | email | `30 9` | 02 Oct 09:30 | 15:53 | **6h 23m** |
| 2 | final | `0 12` | 02 Oct 12:00 | 17:31 | **5h 31m** |
| 6 | email | `30 9` | 05 Oct 09:30 | 18:36 | **9h 06m** |
| 7 | final | `0 12` | 05 Oct 12:00 | 20:15 | **8h 15m** |
| 8 | email | `30 9` | 06 Oct 09:30 | 16:02 | **6h 32m** |
| 9 | final | `0 12` | 06 Oct 12:00 | 17:59 | **5h 59m** |
| 10 | email | `30 9` | 07 Oct 09:30 | 16:41 | **7h 11m** |
| 11 | final | `0 12` | 07 Oct 12:00 | 18:29 | **6h 29m** |
| 12 | email | `30 9` | 08 Oct 09:30 | 16:38 | **7h 08m** |
| 13 | poll | `30 5` | 09 Oct 05:30 | 12:03 | **6h 33m** |
| 14 | poll | `30 7` | 09 Oct 07:30 | 14:33 | **7h 03m** |
| 15 | email | `45 8` | 09 Oct 08:45 | 15:34 | **6h 49m** |
| 16 | email | `0 9` | 09 Oct 09:00 | 15:46 | **6h 46m** |
| 17 | email | `15 9` | 09 Oct 09:15 | 16:08 | **6h 53m** |
| 18 | email | `30 9` | 09 Oct 09:30 | 16:22 | **6h 52m** |
| 19 | poll | `31 9` | 09 Oct 09:31 | 16:26 | **6h 55m** |
| 20 | poll | `1 12` | 09 Oct 12:01 | 17:48 | **5h 47m** |
| 21 | final | `0 14` | 09 Oct 14:00 | 19:16 | **5h 16m** |

Twenty-one for twenty-one, between 5h16m and 9h06m late. Every single scheduled run on 9 October - all nine of them, including all four email attempts - arrived after the 16:00 IST broker cutoff had passed or was passing. The cron strings were correct UTC from the
first commit — `git log` on the workflow confirms it — so this is not a timezone error on
our side. It is GitHub deprioritising scheduled runs in a low-activity repository.

By contrast, both `workflow_dispatch` runs on 8 October started **within one second** of
being triggered. The API path is prompt; the cron path is not.

**So the four scheduled email crons are a backstop. The external trigger is the plan.**

### Setting up cron-job.org

1. **Create the token.** GitHub -> *Settings -> Developer settings -> Personal access
   tokens -> Fine-grained tokens -> Generate new token*.
   * **Repository access:** *Only select repositories* -> `AshishKohar1/ipo-agent`.
   * **Permissions:** *Repository permissions -> Actions -> **Read and write***. Nothing
     else - no `contents`, no account permissions.
   * **Expiry:** 90 days, with a calendar reminder to rotate it.

   **I have not created this token and cannot** - it is an account credential. Create it
   yourself and paste it only into cron-job.org's header field. One token serves all the
   jobs below.

2. **Check each job worked:** the run appears in Actions as `workflow_dispatch` within a
   second or two. A `401` means the token is wrong or expired; a `403` means it lacks
   *Actions: read and write*; a `404` usually means the token cannot see the repository; a
   `422` means the body's `mode` value is not one the workflow accepts.

### The jobs, as they now stand

All five jobs share the same URL, method, time zone, headers and token. Only the
**schedule** and the **body** differ.

| field | value (the same for every job) |
|---|---|
| URL | `https://api.github.com/repos/AshishKohar1/ipo-agent/actions/workflows/live-model-l.yml/dispatches` |
| Method | `POST` |
| Time zone | **UTC** — set it explicitly on every job; cron-job.org defaults to the browser's |
| Expect | **HTTP 204**, empty body. Not 200. |

Headers (*Advanced → Headers*), the same on every job:

```
Accept: application/vnd.github+json
Authorization: Bearer <your fine-grained token>
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

| # | title | cron (UTC) | IST | body |
|---|---|---|---|---|
| 1 | IPO email | `10,20,30 9 * * 1-5` | 14:40 / 14:50 / 15:00 | `{"ref":"main","inputs":{"mode":"email"}}` |
| 2 | IPO email dead-man | `5 10 * * 1-5` | 15:35 | `{"ref":"main","inputs":{"mode":"email"}}` |
| 3 | IPO day-end capture | `0 14 * * 1-5` | 19:30 | `{"ref":"main","inputs":{"mode":"final"}}` |
| 4 | HDFIRE poll AM | `30 5,7 13-15 10 *` | 11:00 / 13:00 | `{"ref":"main","inputs":{"mode":"poll"}}` |
| 5 | HDFIRE poll PM 1 | `31 9 13-15 10 *` | 15:01 | `{"ref":"main","inputs":{"mode":"poll"}}` |
| 6 | HDFIRE poll PM 2 | `1 12 13-15 10 *` | 17:31 | `{"ref":"main","inputs":{"mode":"poll"}}` |

**Jobs 1 and 2 are the ones already set up.** Job 3 is new and matters more than it looks
— see below. Jobs 4–6 are the HDFIRE test and can be deleted after 15 October.

#### Why the HDFIRE polls need three jobs and not one

The four poll times are 05:30, 07:30, 09:31 and 12:01 UTC. A cron expression multiplies
its minute list by its hour list, so `30,31,1 5,7,9,12 13-15 10 *` would not mean "those
four times" — it would mean twelve fires a day. 05:30 and 07:30 share minute `30`, so they
combine into one job; 09:31 and 12:01 share nothing with anything.

Two jobs is possible if you will accept two extra polls: `1,31 9,12 13-15 10 *` fires at
09:01, 09:31, 12:01 **and** 12:31 UTC. The poller records its real wall-clock time and the
NSE update stamp on every row, so extra polls are extra data rather than noise. Three
exact jobs is the cleaner answer; two is the cheaper one.

`13-15 10 *` restricts them to 13, 14 and 15 October. `hdfire_poll.py` also exits
immediately outside that window, so a job left running afterwards does nothing — but
delete them anyway once the test is reported.

#### Why the day-end job (3) is not optional either

The day-end leg does not just snapshot subscription. It fetches **the 15 index closes**,
captures **listing-day prices** for anything that listed that day, and runs the
**catch-up** that recovers a day lost to a fault. None of that is recoverable from a later
run except through the archive, and final subscription is not recoverable at all —
Chittorgarh removes the table at allotment.

The 9 October day-end leg is the demonstration. It was due at 14:00 UTC (19:30 IST).
GitHub started it at **19:16 UTC — 00:46 IST on 10 October**. It then took `date +%F` in
IST, stamped itself **2026-10-10**, and went looking for Saturday's index closes. Two
things have changed since:

* the trading date now comes from **the cron slot the run was due for**, not the clock it
  woke up on, so a 19:30 slot starting at 01:30 the next morning still does the previous
  day's work (`trading_day.py --due-date`);
* the day-end leg is **idempotent on that date** — if the 15 closes are already on record
  it prints `already captured` and exits green, so job 3 and the GitHub backstop cannot
  duplicate or overwrite each other, whichever arrives first.

#### Verifying the bodies against the workflow

The dispatch input is named **`mode`** and is a `choice`, so GitHub rejects any value not
in its list. The nine it accepts are:

`email`, `final`, `listing`, `audit`, `catch-up`, `test-email`, `poll`, `dry-run`, `probe`

The four values used above — `email`, `final`, `poll` — are all in that list. A typo gives
HTTP 422 with `Unexpected value for input 'mode'` rather than a wrong-mode run, so a
mistake here is loud.

Three options were listed and had **no branch** in the workflow's `case`: `dry-run`,
`probe` and `rehearse`. Dispatching one of those ran nothing and exited 0 — a green run
that did no work. `rehearse` has been removed, the other two now run something, and an
unmatched mode exits 1.

#### Why these times

* **09:10 / 09:20 / 09:30 UTC = 14:40 / 14:50 / 15:00 IST.** All three inside the
  14:00–16:00 send window, the last one a full hour before the broker cutoff. Three
  attempts rather than one because a single HTTP call can fail.
* **10:05 UTC = 15:35 IST.** The last chance. At 15:35 the window is **still open**, so if
  the earlier attempts failed this one sends the real verdict, not a notice — there are
  still 25 minutes to bid. Only if the 15:35 send *itself* fails does
  `IPO decision - NOT SENT` go out.
* **14:00 UTC = 19:30 IST.** After NSE Indices publishes the settlement closes. 17:30 was
  reading an incomplete table.

A second send is not a risk: `data/sent_markers.csv` is keyed by **IPO and date**, so the
first attempt that succeeds sends and every later one exits green having done nothing.

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
computed into `data/predictions_log.csv` under `diagnostics`, labelled *not in the decision
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

Use **repository** secrets, not environment secrets and not variables. A *variable* is
visible in logs; a secret is masked. The password is never written to a file in the repo.

### Creating the Gmail app password

Folded in from `EMAIL_SETUP.md` on 2026-10-10, which this replaces. An app password is a
16-character key that lets one program send mail as you, without your real password and
without disabling anything on the account. It can be revoked on its own.

1. The account needs **2-Step Verification** on first:
   <https://myaccount.google.com/signinoptions/two-step-verification>. App passwords do
   not appear as an option until it is enabled.
2. <https://myaccount.google.com/apppasswords> → **App name** `ipo-agent` → **Create**.
3. Google shows 16 characters in four blocks, e.g. `abcd efgh ijkl mnop`.
   **Copy it immediately — it is never shown again.** Spaces do not matter; the code
   strips them.
4. Paste it into `GMAIL_APP_PASSWORD` at
   <https://github.com/AshishKohar1/ipo-agent/settings/secrets/actions>.

If `/apppasswords` says the option is unavailable it is almost always because 2-Step is
off, or because the account is a Workspace account whose admin has disabled app passwords.

### When the email does not arrive

Dispatch the workflow by hand — Actions → *Model L live* → *Run workflow* → mode `email` —
and read the log. The failure is deliberately loud, and there are only a few:

| In the log | Cause | Fix |
|---|---|---|
| `missing repo secret(s): …` | a secret is absent or misnamed | re-check the exact names above |
| `535 … Username and Password not accepted` | wrong app password, or the real account password was used | regenerate the app password |
| `534 … Please log in with your web browser` | 2-Step is off, so it is not a real app password | enable 2-Step, regenerate |
| `Chittorgarh robots.txt no longer permits…` | **the source has withdrawn permission** | stop. This is not a bug to work around |
| `REFUSING TO SEND: … before 14:00` | the run landed outside the send window | expected on a dispatch; see section 2 |

To test without waiting for a closing IPO, use mode `test-email`: real SMTP, real
composition, subject `IPO decision - TEST`, and it writes no sent marker and logs no
prediction — a test is not a decision.

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

# LIVE_SETUP — Model L in production

Written 2026-10-01. Model `model_l_v1.0` / `L_final_3pm`, frozen at Gate B.

**Nothing here is live until you ratify Gate B.** The schedules below exist and will fire,
but they only score, log and report — no order is ever placed, and the verdict is advice you
act on manually before your broker's 4:00 PM cutoff.

---

## 1. The five schedules — created in this session

All five exist in this app's **Scheduled** sidebar section. The app fires them with a few
minutes' jitter, shown below as "actual".

| Job | Requested | Actual | Command | Purpose |
|---|---|---|---|---|
| `ipo-score-1500` | 15:00 daily | **15:01** | `python run_live_l.py --score` | Fetch NSE + BSE, reconcile, score, snapshot, write the report |
| `ipo-notify-1530` | 15:30 daily | **15:34** | `python run_live_l.py --notify` | Deliver the report — 26 min before the cutoff |
| `ipo-final-capture-1730` | 17:30 daily | **17:40** | `python run_live_l.py --final` | Re-capture the same IPOs after close |
| `ipo-ingest-outcomes` | Mon & Thu 08:00 | 08:00 | `python ingest_outcomes.py` | Add new listings, score past predictions |
| `ipo-retrain-monthly` | 1st, 08:00 | 08:00 | `python retrain_l.py` | Champion/challenger + PSI |

### ⚠️ Two things about these schedules you need to know

**1. They only run while this app is open.** If the app is closed when a job is due, it runs
on next launch — which for a 15:00 job against a 4:00 PM cutoff can mean it runs *after* the
decision was needed, or not that day at all. For a job whose entire value is being 26 minutes
early, that is a material weakness. **Use Windows Task Scheduler instead or as well** —
section 3 has the exact commands. Task Scheduler runs whether or not the app is open and can
wake the machine.

**2. The 15:30 notify drifted to 15:34.** That still leaves 26 minutes before the 4:00 PM
cutoff, so it is acceptable, but it is less margin than the 30 minutes decision E1 specified.
If you want the full 30 back, set the cron to `25 15 * * *` and it will land near 15:29.

---

## 2. What the 15:30 report contains

Per decisions D1, D2, G2 and H3 — all of it is in `reports/live/<date>.md`:

```
# IPO report — 2026-10-01 (scored 15:01 IST)

**Decide before your broker's 4:00 PM cutoff.**

> 3pm figures understate final demand — institutional bids concentrate in the last
> hours, and this model is trained on final-day subscription. A near-threshold "no"
> should be treated as UNCERTAIN, not as a negative verdict. The size of the gap is
> not yet measured; the 17:30 capture is accumulating the data that will measure it.

## <Company> — closing today

L_final_3pm  L1: BID   (validated hit rate >= 90%)
             L2: no    (below the 80% threshold)

- Subscription [1500]: Total 8.77x | QIB 3.1x | HNI 14.2x | Retail 6.4x
- Source: nse_official+bse_official — reconciliation `total_x=PASS;qib_x=PASS;...`
- Demand profile: institution-led   [NOT IN MODEL — context only, per H3]
- Veto flags: none (no RHP data for this issue)
- GMP: ____%   [NOT IN MODEL — your judgement only, per D1]
```

**Verdicts are the threshold met, never a probability (G2).** Isotonic overclaims in the top
tail — it claims ~98.5% and delivers 94.0% on L1 — so a number presented as "your chance"
would be wrong by several points. The raw and calibrated probabilities go to
`predictions_log.csv` under `diagnostics` for later calibration measurement, and nowhere else.

**GMP is never fetched** (D1). You fill it in. Whatever you write is logged so its
incremental value over subscription can be measured after ~12 months (D2). Until then no
GMP-based rule may influence a verdict.

---

## 3. Windows Task Scheduler — the reliable path

Run each line in an **elevated** PowerShell. Replace `IST_OFFSET` handling by setting the
machine's timezone to IST first (`tzutil /s "India Standard Time"`), because Task Scheduler
uses local time.

```powershell
$py = "C:\Users\HP\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$dir = "C:\Projects\ipo-agent"

schtasks /Create /TN "IPO\score-1500"  /SC DAILY /ST 15:00 /F /RL LIMITED `
  /TR "cmd /c cd /d $dir && set PYTHONIOENCODING=utf-8 && `"$py`" run_live_l.py --score"

schtasks /Create /TN "IPO\notify-1530" /SC DAILY /ST 15:30 /F /RL LIMITED `
  /TR "cmd /c cd /d $dir && set PYTHONIOENCODING=utf-8 && `"$py`" run_live_l.py --notify"

schtasks /Create /TN "IPO\final-1730"  /SC DAILY /ST 17:30 /F /RL LIMITED `
  /TR "cmd /c cd /d $dir && set PYTHONIOENCODING=utf-8 && `"$py`" run_live_l.py --final"

schtasks /Create /TN "IPO\ingest"      /SC WEEKLY /D MON,THU /ST 08:00 /F /RL LIMITED `
  /TR "cmd /c cd /d $dir && set PYTHONIOENCODING=utf-8 && `"$py`" ingest_outcomes.py"

schtasks /Create /TN "IPO\retrain"     /SC MONTHLY /D 1 /ST 08:00 /F /RL LIMITED `
  /TR "cmd /c cd /d $dir && set PYTHONIOENCODING=utf-8 && `"$py`" retrain_l.py"
```

Then, so a sleeping laptop still scores before the cutoff:

```powershell
schtasks /Change /TN "IPO\score-1500"  /ENABLE
powercfg /waketimers
```

In Task Scheduler's GUI, open each task → **Conditions** → tick *Wake the computer to run
this task*, and untick *Start the task only if the computer is on AC power* if you want it on
battery.

These tasks do **not** commit to git. Add a commit step yourself, or let the app-based
schedules (section 1) handle committing when the app happens to be open.

---

## 4. ⚠️ Open blocker: the official APIs are refusing this host

This is the one thing standing between the schedules and real output.

| Endpoint | Purpose | Result from this machine, 2026-10-01 |
|---|---|---|
| `nseindia.com/api/ipo-current-issue` | which IPOs are open | **connection reset** with our User-Agent; **HTTP 200** with a browser one |
| `nseindia.com/api/historical/cm/equity` | listing-day price | **HTTP 503** |
| `api.bseindia.com/.../GetIPODemandSchedule` | subscription, 2nd source | **HTTP 404** on the probed scrip |
| `api.bseindia.com/.../StockPriceCSVDownload` | listing-day price | **HTTP 403** |

**NSE's `robots.txt` says `Allow: /`** and disallows only `/market-data-test`, so these paths
are explicitly permitted. The block is infrastructure filtering keyed to the User-Agent
string, not a robots or terms restriction.

**I have not spoofed a browser User-Agent, and I will not without you saying so.** Project
rule 3 forbids sending a browser User-Agent to work around an access restriction, and
although robots.txt permits the path here, substituting a browser identity to defeat a block
is the exact pattern that rule exists to prevent. This is your call, and there are three
honest options:

1. **Ask NSE/BSE for API access** with a declared client identity. Slow, but it is the only
   option that makes the pipeline durable.
2. **Decide that a truthful non-browser User-Agent on a robots-permitted path is acceptable
   to present differently** — e.g. `Mozilla/5.0 (compatible; ipo-agent/1.0; +contact)`, which
   is a recognised convention for a bot that must satisfy a WAF while still identifying
   itself. Tell me explicitly and I will change one line.
3. **Fill the two captures manually** on the ~2–4 days a month an IPO actually closes. The
   snapshot file takes a hand-entered row and the pairing still works.

Until one is chosen, the jobs run, log honestly and write a report saying no subscription
could be fetched. **They will not invent a number.**

---

## 5. What is genuinely verified, and what is not

**Verified end to end:**
- Scoring, calibration, thresholds, demand-profile label, report contract, append-only log —
  rehearsed on the 5 most recently listed IPOs (`python run_live_l.py --rehearse`).
- The portable coefficients: scoring from `models/model_l_v1.0_l1_coefficients.json` alone,
  with no joblib and no repo imports, reproduced `predict_live`'s verdict on all 16 test
  cases by both the calibrated route and the raw-threshold route.
- The monthly retrain, dry-run: it independently reconfirms H11 (champion 0.8131 vs
  challenger Set A 0.7948 on L1 out-of-sample) and flags Set A's PSI at **1.322**.

**Not verified, and why:**
- **The two official fetches** — see section 4.
- **The 3pm understatement's size.** Unmeasurable until the paired captures accumulate. The
  model card states the direction (it understates, so it is conservative) and explicitly
  says the magnitude is unknown.
- **Symbol resolution for brand-new listings.** `ingest_outcomes.py` resolves symbols from
  `master_with_symbols.csv`, which does not yet contain an IPO that listed this week — so
  those rows report `no_symbol_resolved` rather than guessing. Refreshing
  `data/NSE_EQUITY_L.csv` fixes it.

---

## 6. Daily routine, once the blocker clears

1. **15:34** — read the report on your phone. Verdicts are BID / no, with the threshold met.
2. Form your own view on GMP and write it into the report's blank field, or reply with it.
3. **Decide before 4:00 PM.** Remember the standing caveat: a near-threshold `no` at 3pm is
   uncertain, not a negative — the model understates at that hour by an amount not yet known.
4. **17:40** — nothing to do. The final capture runs itself and builds the dataset that will
   eventually remove caveat 3.
5. **Mon & Thu** — outcomes get ingested and past predictions scored, so the model's claims
   stay auditable against what actually happened.

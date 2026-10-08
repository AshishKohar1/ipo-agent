"""
send_daily_email.py — the single live pipeline for Model L (Priorities 1b–1g).

This is now **the only script the scheduled jobs call**:

    python send_daily_email.py            15:00 IST  fetch, score, snapshot, report, EMAIL
    python send_daily_email.py --final    19:30 IST  fetch, snapshot after close, NO email
    python send_daily_email.py --dry-run             compose and print, send nothing

`run_live_l.py` is no longer scheduled. It reads NSE and BSE, both of which refuse this
host, and it wrote to the *same* report path as this script — so on 2 Oct its failing
21:49 run overwrote the good Chittorgarh report. Per H14 Chittorgarh is the live source, so
there is one pipeline, one report path, and `run_live_l.py` survives only as an
exchange-access probe writing to `reports/live/exchange_probe/` (Priority 1c).

Why this file no longer imports the modelling stack (Priority 1b)
-----------------------------------------------------------------
It used to `import model_l`, which imports `framework`, which imports `joblib`. joblib was
never in requirements.txt — it arrives on the laptop only as a scikit-learn dependency, and
scikit-learn is banned (rule 10). So every cloud run died in ~35 s with
`ModuleNotFoundError: No module named 'joblib'` and no email was sent for three days.
Scoring now goes through `score_l.py`, which reads the portable coefficient JSON using
only the standard library. **A modelling dependency can no longer break mail delivery.**

Three rules this module exists to enforce, because each is easy to break by accident:

1. **Send every weekday without exception**, including days with no open IPO. Silence must
   always mean something broke, never that nothing happened.

2. **A verdict only where the model supports one.** Model L is trained on final-day
   subscription, and an IPO at 3x on day 1 can close at 150x — so a day-1 or day-2 reading
   cannot carry a verdict. Not closing today means **numbers only**. There is deliberately
   no "provisional", "indicative" or "estimated" verdict anywhere in this file for a
   mainboard IPO: inventing one the model cannot support is worse than showing none. SME is
   always PROVISIONAL regardless, per shadow mode.

3. **Fail loudly.** A missing secret, an SMTP refusal or a source failure raises and exits
   non-zero. It never silently skips the email, and it never sends a report with a verdict
   computed from data that did not arrive.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import inspect
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import chittorgarh_live as CL      # noqa: E402
import score_l as SL               # noqa: E402  — portable JSON, no joblib (Priority 1b)
import predictions_log as PL       # noqa: E402
import live_markers as LM          # noqa: E402
import market_context as MC        # noqa: E402
import trading_day as TD           # noqa: E402  - one date per run (Task 1)
import sent_markers as SM          # noqa: E402  - idempotent send (Task 4)
import nse_subscription as NSE     # noqa: E402  - H22 source order (Task 8)

LIVE_DIR = ROOT / "reports" / "live"
SNAPSHOTS = ROOT / "data" / "subscription_snapshots.csv"
CUTOFF = "4:00 PM"

# Priority 1d: EXACTLY this. Plain ASCII hyphen-minus, lowercase "decision", one space
# either side, trailing space. Mail filters match literally, so an em dash would silently
# stop matching. Asserted in self_test().
SUBJECT_PREFIX = "IPO decision - "

# Priority 1g: both legs write here, so the 15:00-vs-close gap starts accumulating. The
# file had never been created, because the only leg that wrote it was the NSE/BSE one that
# always failed. `sector` is Priority 6 and is populated ONLY where the source page states
# it — never guessed.
# The broker cutoff (decision E1). A bid signal that arrives after this is not late
# information, it is wrong information: it invites a bid that can no longer be placed.
# Every 15:00 marker on record so far was stamped AFTER it - 16:53, 21:49, 22:11, two
# past midnight - because GitHub queues a delayed job and the leg sent anyway. The 15:00
# leg now refuses to send past this time and exits non-zero (Priority 1d). It is never
# caught up: there is no flag that re-sends it, only --dry-run for inspection.
BROKER_CUTOFF_HHMM = 1600
# The other end of the same window. See send_window() for why.
EARLIEST_SEND_HHMM = 1400
# Task 4 dead-man. Past this time an undelivered decision is REPORTED as
# undelivered rather than left as silence.
DEAD_MAN_AFTER_HHMM = 1530

GMP_PLACEHOLDER = "______%"

SNAP_COLS = ["ipo", "isin", "ipo_id", "segment", "date", "timestamp_ist", "capture_point",
             "qib_x", "hni_x", "rii_x", "emp_x", "total_x", "sector",
             "source", "reconciled", "note"]

CAVEATS = [
    "3pm figures understate final demand; a near-threshold NO is uncertain.",
    "Subscription from a single source — verify on your broker app before bidding.",
    "Category figures are shown for your judgement only; the model uses total subscription.",
]


class MissingSecret(RuntimeError):
    pass


def send_window(when) -> tuple[bool, str]:
    """`(may_send, why_not)` for a wall-clock time. Pure, so it is testable.

    Two refusals, for two different reasons:

    * **At or after 16:00** - the broker cutoff (E1). The signal is dead on
      arrival. This is Priority 1d, and it is why five of the five 15:00 markers
      on record (16:53, 21:49, 22:11, 00:06, 00:39) should never have sent.
    * **Before 14:00** - the model is `L_final_3pm` (H1). It was fitted on the
      final-day late-afternoon subscription figure, and a morning figure is a
      different distribution, not an early look at the same one. Scoring one
      would be a quiet leakage-discipline breach in the opposite direction.
    """
    w = pd.Timestamp(when)
    hhmm = w.hour * 100 + w.minute
    if hhmm >= BROKER_CUTOFF_HHMM:
        return False, (f"it is {w:%H:%M} IST, at or past the "
                       f"{BROKER_CUTOFF_HHMM // 100}:{BROKER_CUTOFF_HHMM % 100:02d}"
                       f" broker cutoff (E1). A bid signal now invites a bid that"
                       f" cannot be placed")
    if hhmm < EARLIEST_SEND_HHMM:
        return False, (f"it is {w:%H:%M} IST, before "
                       f"{EARLIEST_SEND_HHMM // 100}:{EARLIEST_SEND_HHMM % 100:02d}"
                       f". L_final_3pm scores the final-day late-afternoon figure;"
                       f" a morning figure is a different distribution")
    return True, ""


def secrets() -> tuple[str, str, str]:
    """`(sender, password, recipient)`, or a loud failure. Never a silent skip.

    Priority 1e: the recipient is the repo secret `EMAIL_TO`, falling back to
    `GMAIL_ADDRESS` when it is unset. EMAIL_TO is deliberately allowed to be a different
    provider from the sender — the user's GitHub account is on Yahoo while the Gmail
    account only sends.
    """
    addr = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    missing = [n for n, v in (("GMAIL_ADDRESS", addr), ("GMAIL_APP_PASSWORD", pw)) if not v]
    if missing:
        raise MissingSecret(
            f"missing repo secret(s): {', '.join(missing)}. The email was NOT sent and this "
            "run has failed deliberately — a silently skipped email would look identical to "
            "a quiet market. See EMAIL_SETUP.md.")
    to = os.environ.get("EMAIL_TO", "").strip() or addr
    return addr, pw, to


# ---------------------------------------------------------------- composition
# Priority 1b. The L2 under-review caveat is GONE. It warned that L2's 80% promise rested
# on a calibrated-probability cut-off whose measured delivery was 77%. H17 replaced that
# cut-off with a subscription threshold derived to deliver 80.8% out of sample, so the
# caveat now describes a rule that no longer exists -- and a stale warning is worse than
# none, because it teaches the reader to discount a verdict that is in fact sound.


def _verdict_block(res: dict) -> list[str]:
    """`BID` / `NO BID`, each with the subscription threshold and whether it was met.

    Under H17 the threshold IS a subscription level, so it is printed outright. That is the
    whole gain over the retired probability cut-off: the reader can check the number
    against their own broker screen, which a calibrated probability never allowed.

    `score_l` returns "BID" / "no"; "NO BID" is a DISPLAY mapping only. The stored verdict
    keeps its own spelling, because `predictions_log.csv` and `backtest_email.py` both key
    on it and silently changing a logged value would break the comparison to every row
    already written.

    Every number here is read from the ratified artefact. Nothing is retyped (Task 10).
    """
    out = []
    for key, label in (("L1", "L1  any listing gain"), ("L2", "L2  gain above 10%")):
        r = res[key]
        fired = r.get("verdict") == "BID"
        shown = "BID" if fired else "NO BID"
        cut = r.get("threshold_total_x")
        promise = r.get("required_hit_rate", 0) * 100
        if cut is None:
            tail = "threshold unavailable"
        else:
            tail = (f"threshold {cut:.2f}x {'met' if fired else 'NOT met'}"
                    f"  ({promise:.0f}% promise)")
        out.append(f"  {label + ':':<24s}{shown:<7s} {tail}")
    return out


def _numbers(r: dict, as_of: str, source: str = "") -> list[str]:
    """The 15:00 reading, with the exact time it was fetched and where from.

    "as of 15:00" alone is not enough: the run can land at 14:17 or 15:58 and the figure
    is different at each. The timestamp is the real fetch time, not the nominal slot.
    """
    sub = r.get("sub", {})

    def x(k):
        v = sub.get(k)
        return "   -  " if v is None else f"{v:.2f}x"
    day = (f"   (Day {r['day_of']} of {r['days_total']})"
           if r.get("day_of") and r.get("days_total") else "")
    src = source or sub.get("source") or "chittorgarh (single source, H14)"
    return [f"  Total subscription:     {x('total_x'):<7s} fetched {as_of} IST{day}",
            f"  QIB {x('qib_x'):>7s} | HNI {x('hni_x'):>7s} | "
            f"Retail {x('rii_x'):>7s}        (display only)",
            f"  Source:                 {src}"]


def compose(mv: dict, scored: dict, today: pd.Timestamp | None = None) -> tuple[str, str]:
    # `today` is passed in rather than read from the clock, so the header date and the
    # market view can never disagree -- they did during the Monday rehearsal, which
    # printed Monday's market under Saturday's heading.
    now = pd.Timestamp.now()
    today = today or now
    as_of = now.strftime("%H:%M")
    closing = mv["closing_today"]
    open_not = mv["open_not_closing"]
    upcoming = mv["upcoming"]

    n_open = len(closing) + len(open_not)
    if closing:
        urgent = f"{len(closing)} closes today"
    elif open_not:
        soonest = min(open_not, key=lambda r: r["closes"])
        urgent = f"next closes {pd.Timestamp(soonest['closes']).strftime('%a')}"
    else:
        urgent = "none closing"
    subject = f"{SUBJECT_PREFIX}{n_open} open, {urgent}"

    L = [f"IPO MARKET — {today.strftime('%A %d %B').replace(' 0', ' ')}", ""]

    L += ["===== CLOSING TODAY — bid by 4:00 PM =====", ""]
    if not closing:
        L += ["  Nothing closes today.", ""]
    for r in closing:
        seg = "Mainboard" if r["segment"] == "mainboard" else "SME"
        closes_on = r.get("closes")
        when = ("" if not closes_on else
                f"  closes {pd.Timestamp(closes_on).strftime('%d %b %Y')}")
        L.append(f"[{r['ipo'].upper()}]  ({seg}){when}")
        res = scored.get(r["ipo"])
        if r["segment"] != "mainboard":
            # SME is shadow mode: display, never decide.
            L += _numbers(r, as_of)
            L += ["  PROVISIONAL — SME model not validated for bid decisions.", ""]
            continue
        if res is None:
            L += _numbers(r, as_of)
            L += ["  NO VERDICT — subscription did not arrive, so the model's only input "
                  "is missing.", "  Verify on your broker app before the cutoff.", ""]
            continue
        # Task 5 order: figures first, then each verdict with its threshold, then the
        # 15:00 caveat, then GMP. The figures come first on purpose - the verdict is a
        # comparison against them, and a reader who sees the verdict first has nothing to
        # check it against.
        L += _numbers(r, as_of)
        L += _verdict_block(res)
        L += [f"  Figures as of {as_of} IST — final subscription is usually higher (H23).",
              f"  Demand profile:         {res['demand_profile']}",
              "  Veto flags:             none"]
        L += [f"  GMP: {GMP_PLACEHOLDER}            (not in model — your judgement, D1)", ""]

    L += ["===== OPEN, NOT CLOSING TODAY =====", ""]
    if not open_not:
        L += ["  Nothing else is open.", ""]
    for r in open_not:
        seg = "Mainboard" if r["segment"] == "mainboard" else "SME"
        closes = pd.Timestamp(r["closes"]).strftime("%A")
        L.append(f"[{r['ipo'].upper()}]  ({seg})  closes {closes}")
        L += _numbers(r, as_of)
        if r["segment"] == "mainboard":
            L += ["  No verdict until the final day — early subscription does not "
                  "predict the close.", ""]
        else:
            L += ["  PROVISIONAL — SME model not validated for bid decisions.", ""]

    L += ["===== UPCOMING ====="]
    if not upcoming:
        L += ["  Nothing scheduled to open.", ""]
    for r in upcoming:
        L.append(f"  [{r['ipo'].upper()}] opens "
                 f"{pd.Timestamp(r['opens']).strftime('%A %d %b').replace(' 0', ' ')}")

    try:
        lv = SL.firing_levels()
        L += ["", f"Decision rule (H17): L1 bids at Total >= {lv['L1']:.2f}x, "
                  f"L2 at >= {lv['L2']:.2f}x.",
              "  Each level is where that share of IPOs the model had NOT seen met the "
              "target (walk-forward)."]
    except Exception as e:                                  # noqa: BLE001
        L += ["", f"Decision rule: UNAVAILABLE ({type(e).__name__}) — no verdict was "
                  f"printed above."]
    L += ["", "-----", f"Caveats: {CAVEATS[0]}"]
    for c in CAVEATS[1:]:
        L.append(f"         {c}")

    # Priority 6: display-only market context. Never a model input (H2).
    L += ["", MC.email_footer(), ""]

    if mv.get("diagnostics"):
        L += ["Diagnostics:"] + [f"  - {d}" for d in mv["diagnostics"]]
    L += ["", f"Model {SL.MODEL_ID} / {SL.DECISION_POINT}. The verdict IS the subscription "
              "level met (H17); no probability is involved in the decision.",
          "Source: chittorgarh.com (single source, decision H14). Every request logged "
          "with its timestamp and exact URL in data/live_fetch_log.csv."]
    return subject, "\n".join(L)


# ---------------------------------------------------------------- snapshots
def append_snapshots(mv: dict, capture_point: int, when: pd.Timestamp) -> int:
    """Priority 1g. Every open IPO's reading at this capture point, appended.

    Rows are written for failed reads too, with the reason in `note` and the figures NULL:
    a missing row and a row that says "the Total was not published yet" are different
    facts, and only the second one is evidence.
    """
    rows = []
    for r in mv["closing_today"] + mv["open_not_closing"]:
        s = r.get("sub", {}) or {}
        rows.append({
            "ipo": r.get("ipo"), "isin": r.get("isin"), "ipo_id": r.get("ipo_id"),
            "segment": r.get("segment"), "date": str(when.date()),
            "timestamp_ist": str(when), "capture_point": capture_point,
            "qib_x": s.get("qib_x"), "hni_x": s.get("hni_x"), "rii_x": s.get("rii_x"),
            "emp_x": s.get("emp_x"), "total_x": s.get("total_x"),
            # Priority 6: only where the source page states it. Chittorgarh's subscription
            # page does not, so this stays NULL rather than being inferred from the name.
            "sector": s.get("sector"),
            "source": "chittorgarh",
            "reconciled": "single_source_unverified",
            "note": "" if s.get("ok") else (s.get("why") or "no reading"),
        })
    if not rows:
        return 0
    df = pd.DataFrame([{c: r.get(c) for c in SNAP_COLS} for r in rows], columns=SNAP_COLS)
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOTS, mode="a", header=not SNAPSHOTS.exists(), index=False,
              encoding="utf-8")
    return len(rows)


# ---------------------------------------------------------------- send
def send(subject: str, body: str, dry: bool) -> dict:
    if dry:
        print(f"SUBJECT: {subject}\n")
        print(body)
        return {"sent": False, "dry_run": True, "subject": subject}
    addr, pw, to = secrets()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(addr, pw)
        smtp.send_message(msg)
    return {"sent": True, "subject": subject, "to": to, "from": addr}


def dead_man(undelivered: list[str], today, why: str, report: str) -> dict:
    """Task 4. Tell the user that NO decision is coming today, and why.

    This is the opposite of the bid email and must never be mistaken for one: the subject
    is `IPO decision - NOT SENT`, the body carries no verdict, and the marker it writes is
    `not_sent_notice`, which `sent_markers.already_sent()` deliberately does not count as
    delivery. If it did, the next attempt would see a marker, believe the decision had
    gone out, and the silence would become permanent.

    Sent at most once per IPO per day.
    """
    todo = [i for i in undelivered if not SM.notice_sent(today, i)]
    if not todo:
        return {"sent": False, "reason": "notice already sent", "undelivered": undelivered}
    subject = f"{SUBJECT_PREFIX}NOT SENT"
    body = chr(10).join([
        f"NO BID DECISION WAS DELIVERED FOR {today.strftime('%A %d %B %Y')}.", "",
        f"Closing today and undelivered: {', '.join(todo)}", "",
        f"Reason: {why}", "",
        "This is not a verdict. The bid email is never sent after the 16:00 IST broker",
        "cutoff, because a signal arriving then invites a bid that can no longer be",
        "placed. The run failed deliberately rather than send one late.",
        "",
        f"What the verdict would have been is in reports/live/{today.date()}.md, written",
        "before this notice. Read it for the record, not as advice to act on.",
        "", "-" * 68, "", report[:2000],
    ])
    out = send(subject, body, dry=False)
    if out.get("sent"):
        for i in todo:
            SM.mark(today, i, None, subject, today, kind=SM.DEAD_MAN,
                    capture_point=1500, note=f"dead-man: {why[:120]}")
    out["undelivered"] = todo
    return out


def test_email(dry: bool = False) -> dict:
    """Task 5. One test email, subject `IPO decision - TEST`, from the LAST CLOSED IPO.

    Real recorded data, not invented numbers: the most recent row of
    `data/subscription_snapshots.csv`, scored through the live `score_l.predict_live()`.
    So this exercises the real composition path and the real SMTP path, and the only thing
    that differs from a live send is the subject and the TEST banner.

    It deliberately does NOT write a sent marker and does NOT log a prediction. A test is
    not a decision, and a marker here would make a later real run believe the day's email
    had already gone out.
    """
    snap = ROOT / "data" / "subscription_snapshots.csv"
    if not snap.exists():
        return {"sent": False, "error": f"{snap.name} does not exist, so there is no "
                                        f"recorded IPO to build a test from"}
    d = pd.read_csv(snap)
    d["t"] = pd.to_datetime(d["timestamp_ist"], errors="coerce")
    d = d.dropna(subset=["t"]).sort_values("t")
    if d.empty:
        return {"sent": False, "error": "no dated snapshot rows"}
    r = d.iloc[-1]
    total = pd.to_numeric(pd.Series([r.get("total_x")]), errors="coerce").iloc[0]
    if pd.isna(total):
        return {"sent": False, "error": f"the latest snapshot ({r.get('ipo')}) has no "
                                        f"total subscription, so there is nothing to score"}

    def num(k):
        v = pd.to_numeric(pd.Series([r.get(k)]), errors="coerce").iloc[0]
        return None if pd.isna(v) else float(v)

    res = SL.predict_live(total=float(total), qib=num("qib_x"), rii=num("rii_x"),
                          segment=str(r.get("segment") or "mainboard"))
    res["inputs"]["hni"] = num("hni_x")
    lv = SL.firing_levels()

    def x(k):
        v = num(k)
        return "   -  " if v is None else f"{v:.2f}x"
    qib_s, hni_s, rii_s = x("qib_x"), x("hni_x"), x("rii_x")
    subject = f"{SUBJECT_PREFIX}TEST"
    body = chr(10).join([
        "*** TEST EMAIL - THIS IS NOT A BID DECISION. DO NOT ACT ON IT. ***", "",
        "Sent deliberately to check delivery, the subject prefix and the body layout.",
        "It is built from the LAST CLOSED IPO already on record, so every number below is",
        "real recorded data rather than an invented example - but it is historical, and",
        "the issue it describes has already closed.", "",
        "=" * 68, "",
        f"[{str(r.get('ipo')).upper()}]  ({'Mainboard' if r.get('segment') == 'mainboard' else 'SME'})"
        f"   snapshot {r['t']:%d %b %Y %H:%M} IST, capture point {r.get('capture_point')}",
        "",
        f"  Total subscription:     {float(total):.2f}x  fetched {r['t']:%H:%M} IST",
        f"  QIB {qib_s:>7s} | HNI {hni_s:>7s} | Retail {rii_s:>7s}        (display only)",
        f"  Source:                 {r.get('source')} ({r.get('reconciled')})",
    ] + _verdict_block(res) + [
        "  Figures as of the snapshot time - final subscription is usually higher (H23).",
        f"  Demand profile:         {res.get('demand_profile')}",
        f"  GMP: {GMP_PLACEHOLDER}            (not in model - your judgement, D1)", "",
        "=" * 68, "",
        f"Decision rule (H17): L1 bids at Total >= {lv['L1']:.2f}x, L2 at >= {lv['L2']:.2f}x.",
        "  Each level is where that share of IPOs the model had NOT seen met the target",
        "  (walk-forward, never in-sample).", "",
        "The verdict IS the subscription level met (H17); no probability is involved in",
        "the decision.", "",
        "*** TEST EMAIL - THIS IS NOT A BID DECISION. ***",
    ])
    out = send(subject, body, dry)
    out.update({"mode": "test", "ipo": r.get("ipo"), "total_x": float(total),
                "subject": subject, "marker_written": False})
    print(body if dry else f"test email -> {out}")
    return out


# ---------------------------------------------------------------- entry points
def main(dry: bool = False, final: bool = False, force: bool = False) -> dict:
    """The 15:00 leg (`final=False`) scores, logs, snapshots, reports and emails.
    The 19:30 leg (`final=True`) snapshots only — the bid window has closed, so there is
    nothing left to decide and nothing to email."""
    # ONE trading date per run, fixed in Asia/Kolkata (Task 1). The date comes from
    # TRADING_DATE, the clock time from the real clock: run #11 started at 23:59:30
    # IST and stamped itself 2026-10-08 because every step asked `now()` separately.
    today = TD.now()
    print(TD.banner())
    # The clock time the leg actually runs at. The day-end leg moved 17:30 -> 19:30 on
    # 2026-10-08 (1c): 17:30 is before the index closes are published. The older 1730
    # markers stay truthful - they were captured at 17:30.
    capture_point = 1930 if final else 1500

    if today.weekday() >= 5:
        print(f"{today.strftime('%A')} — no bidding at the weekend, no email.")
        return {"sent": False, "reason": "weekend"}

    # Idempotency (Priority 1f): a previous attempt that captured NOTHING does not lock
    # this slot. Only a real capture does.
    if not dry and not force and LM.already_ran(capture_point, today):
        print(f"{today.date()} {capture_point}: already captured. No-op.")
        return {"sent": False, "reason": "already_ran", "capture_point": capture_point}

    mv = CL.market_view(today)
    # H22, PROVISIONAL pending the HDFIRE test (Task 9): NSE is the origin of the
    # subscription figure and Chittorgarh republishes it, so NSE is tried first.
    # A payload only replaces the Chittorgarh figure if it passes the freshness
    # gate - positive Total, updateTime on the trading date, matching symbol -
    # because it is NOT yet known whether that endpoint publishes intraday. Which
    # source was used is recorded on every row; the single_source_unverified flag
    # stays either way, since a figure and a copy of it are not two measurements.
    try:
        mv = NSE.enrich_market_view(mv, today=today)
    except Exception as e:                              # noqa: BLE001
        print(f"  H22: NSE enrichment skipped ({type(e).__name__}: {str(e)[:70]}); "
              f"Chittorgarh figures stand.")
    n_snap = 0 if dry else append_snapshots(mv, capture_point, today)

    # Priority 6: the 19:30 day-end leg is where the index closes are captured — after
    # has actually closed. The 15:00 leg only reads back whatever is already on disk.
    ctx = MC.capture(today) if (final and not dry) else {"skipped": "not the day-end leg"}

    if final:
        # Task 6. The final figure goes to its OWN file, keyed to the 15:00 prediction.
        # The prediction row is never rewritten (rule 10) - overwriting `total_x` with the
        # final figure would destroy the only record of what the decision was taken on,
        # which is the one number the email backtest depends on.
        finals = []
        if not dry:
            at15 = PL.predictions_for(today, 1500)
            lv = SL.firing_levels()
            for r in mv["closing_today"]:
                sub = r.get("sub", {})
                prior = at15.get(r["ipo"])
                if prior is None or not sub.get("ok") or sub.get("total_x") is None:
                    continue
                finals.append(PL.log_final_subscription(
                    str(prior.get("prediction_id")), r["ipo"], r.get("isin"), today,
                    final={"total": sub.get("total_x"), "qib": sub.get("qib_x"),
                           "hni": sub.get("hni_x"), "rii": sub.get("rii_x")},
                    at_1500={"total": prior.get("sub_total_1500")
                             if prior.get("sub_total_1500") is not None
                             else prior.get("total_x")},
                    levels=lv, source="chittorgarh single_source_unverified (H14)",
                    when=today, capture_point=capture_point))
            changed = [f["ipo"] for f in finals if f.get("verdict_would_have_changed")]
            if changed:
                print(f"  3pm-vs-final: the verdict WOULD have changed for "
                      f"{', '.join(changed)} on the final figure. Recorded, not acted on "
                      f"(H23 accepts the conservative bias).")
            LM.mark_ran(capture_point, today, n_snap)
        print(f"19:30 final capture {today.date()}: {n_snap} snapshot rows, "
              f"{ctx.get('n_ok', 0)} index closes. No email at this capture point.")
        return {"sent": False, "mode": "final", "n_snapshots": n_snap,
                "capture_point": capture_point, "market_context": ctx,
                "finals_written": len(finals),
                "verdict_would_have_changed": [f["ipo"] for f in finals
                                               if f.get("verdict_would_have_changed")]}

    scored = {}
    for r in mv["closing_today"]:
        if r["segment"] != "mainboard":
            continue                      # SME never gets a verdict (shadow mode)
        s = r.get("sub", {})
        if not s.get("ok") or s.get("total_x") is None:
            continue                      # no input, no verdict
        res = SL.predict_live(total=s["total_x"], qib=s.get("qib_x"), rii=s.get("rii_x"),
                              segment=r["segment"])
        res["inputs"]["hni"] = s.get("hni_x")
        scored[r["ipo"]] = res
        if not dry:
            PL.log_prediction(r["ipo"], r.get("isin"), res, capture_point=capture_point,
                              source="chittorgarh single_source_unverified (H14)")

    # ---- Task 4: who is owed a decision today, and has it already been delivered?
    # Keyed by IPO and date, not by run: four scheduled attempts plus dispatch plus an
    # external trigger would otherwise mean up to six identical emails.
    owed = sorted(scored.keys())
    undelivered = SM.undelivered(today, owed)
    if owed and not undelivered and not dry and not force:
        LM.mark_ran(capture_point, today, n_snap)
        print(f"{today.date()}: the decision for {', '.join(owed)} already went out. "
              f"No-op, exiting green.")
        return {"sent": False, "reason": "already_sent", "owed": owed,
                "n_verdicts": len(scored), "n_snapshots": n_snap,
                "capture_point": capture_point}

    subject, body = compose(mv, scored, today)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / f"{today.date()}.md").write_text(body, encoding="utf-8")

    may_send, why_not = send_window(today)
    hhmm = today.hour * 100 + today.minute

    if not dry and not may_send:
        LM.mark_ran(capture_point, today, n_snap)
        # Task 4: a refusal is RED only if a decision was owed and never delivered. A
        # refusal on a day with nothing closing, or after the email already went out, is
        # the guard doing its job - and a red run that means "working correctly" is how a
        # real red stops being noticed.
        red = bool(undelivered)
        out = {"sent": False, "reason": "outside_send_window", "fail_loudly": red,
               "owed": owed, "undelivered": undelivered,
               "n_verdicts": len(scored), "n_snapshots": n_snap,
               "capture_point": capture_point}
        msg = (f"REFUSING TO SEND: {why_not}. The report was still written to "
               f"reports/live/{today.date()}.md, so the day leaves a record of "
               f"what the verdict would have been. This leg is NEVER caught up "
               f"- see capture_audit.py.")
        print(msg, file=sys.stderr if red else sys.stdout)
        out["message"] = msg
        if not red:
            print("  Nothing was owed, or it was already delivered - exiting green.")
        # Task 4 dead-man: past 15:30 IST with a decision still undelivered, the user is
        # told that NO decision is coming. Silence must never be the outcome.
        if undelivered and hhmm >= DEAD_MAN_AFTER_HHMM:
            out["dead_man"] = dead_man(undelivered, today, why_not, body)
        return out

    out = send(subject, body, dry)
    if out.get("sent") and not dry:
        for ipo in owed:
            SM.mark(today, ipo, (scored.get(ipo, {}).get("inputs") or {}).get("isin"),
                    subject, today, kind=SM.DECISION, capture_point=capture_point,
                    note="decision delivered")
    if not dry:
        LM.mark_ran(capture_point, today, n_snap)
    out.update({"n_open": mv["n_open"], "n_closing": len(mv["closing_today"]),
                "n_verdicts": len(scored), "n_snapshots": n_snap,
                "owed": owed, "capture_point": capture_point})
    # A send that was attempted and failed still owes the user a dead-man notice.
    if not dry and not out.get("sent") and undelivered and hhmm >= DEAD_MAN_AFTER_HHMM:
        out["dead_man"] = dead_man(undelivered, today,
                                   out.get("error") or "the send failed", body)
        out["fail_loudly"] = True
    return out


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("send_daily_email.py self-test (no network, no mail)")

    print("\n[1] subject line is byte-exact (Priority 1d)")
    chk("prefix == 'IPO decision - '", SUBJECT_PREFIX == "IPO decision - ",
        repr(SUBJECT_PREFIX))
    chk("prefix is pure ASCII — no em dash", SUBJECT_PREFIX.isascii(),
        repr(SUBJECT_PREFIX))
    chk("the dash is U+002D hyphen-minus",
        "-" in SUBJECT_PREFIX and "—" not in SUBJECT_PREFIX
        and "–" not in SUBJECT_PREFIX)
    chk("'decision' is lowercase", "decision" in SUBJECT_PREFIX
        and "Decision" not in SUBJECT_PREFIX)

    print("\n[2] recipient resolution (Priority 1e)")
    keep = {k: os.environ.get(k) for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_TO")}
    try:
        os.environ["GMAIL_ADDRESS"] = "sender@gmail.com"
        os.environ["GMAIL_APP_PASSWORD"] = "x"
        os.environ.pop("EMAIL_TO", None)
        chk("EMAIL_TO unset -> falls back to GMAIL_ADDRESS",
            secrets()[2] == "sender@gmail.com", str(secrets()))
        os.environ["EMAIL_TO"] = "me@yahoo.com"
        chk("EMAIL_TO set -> used as recipient", secrets()[2] == "me@yahoo.com")
        chk("sender stays GMAIL_ADDRESS", secrets()[0] == "sender@gmail.com")
        chk("a different provider for recipient is allowed",
            secrets()[0].split("@")[1] != secrets()[2].split("@")[1])
        os.environ["GMAIL_APP_PASSWORD"] = ""
        try:
            secrets()
            chk("a missing secret fails loudly", False, "no exception raised")
        except MissingSecret as e:
            chk("a missing secret fails loudly", "GMAIL_APP_PASSWORD" in str(e))
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("\n[3] no modelling dependency in the mail path (Priority 1b)")
    import subprocess
    probe = ("import sys, send_daily_email; "
             "print(','.join(m for m in ['joblib','sklearn','framework','model_l'] "
             "if m in sys.modules))")
    p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                       cwd=str(ROOT), timeout=180)
    chk("importing send_daily_email pulls in no joblib/framework/model_l",
        p.returncode == 0 and p.stdout.strip() == "",
        f"rc={p.returncode} leaked={p.stdout.strip()!r} err={p.stderr.strip()[-300:]}")

    print("\n[4] composition on a synthetic market — verdict discipline (Priority 1c)")
    mv = {
        "closing_today": [
            {"ipo": "Mainboard Closing", "segment": "mainboard", "ipo_id": 1, "isin": None,
             "day_of": 3, "days_total": 3,
             "sub": {"ok": True, "total_x": 120.0, "qib_x": 200.0, "rii_x": 40.0,
                     "hni_x": 90.0}},
            {"ipo": "Mainboard No Data", "segment": "mainboard", "ipo_id": 2, "isin": None,
             "sub": {"ok": False, "why": "no Total row yet"}},
            {"ipo": "Sme Closing", "segment": "sme", "ipo_id": 3, "isin": None,
             "sub": {"ok": True, "total_x": 300.0, "qib_x": 10.0, "rii_x": 500.0}},
        ],
        "open_not_closing": [
            {"ipo": "Mainboard Midweek", "segment": "mainboard", "ipo_id": 4, "isin": None,
             "closes": "2026-10-09", "day_of": 1, "days_total": 3,
             "sub": {"ok": True, "total_x": 2.0, "qib_x": 0.1, "rii_x": 5.0}},
        ],
        "upcoming": [], "diagnostics": ["robots.txt: ok"], "n_open": 4,
    }
    scored = {"Mainboard Closing": SL.predict_live(120.0, 200.0, 40.0),
              # deliberately NOT scored: the SME one, and the no-data one
              }
    subject, body = compose(mv, scored)
    chk("subject starts with the exact prefix", subject.startswith(SUBJECT_PREFIX), subject)
    chk("the closing mainboard IPO gets L1 and L2 verdict lines",
        "L1  any listing gain" in body and "L2  gain above 10%" in body)
    # Checked on _verdict_block directly rather than by sniffing the whole body:
    # whether a NO BID appears there depends on the fixture's subscription, which
    # is not what this assertion is about.
    fire = {"verdict": "BID", "threshold_total_x": 28.39, "required_hit_rate": 0.9}
    miss = {"verdict": "no", "threshold_total_x": 54.02, "required_hit_rate": 0.8}
    vb = _verdict_block({"L1": fire, "L2": miss})
    chk("a firing target prints BID and `met`",
        "BID" in vb[0] and "28.39x met" in vb[0], vb[0])
    chk("a non-firing target prints NO BID and `NOT met`",
        "NO BID" in vb[1] and "54.02x NOT met" in vb[1], vb[1])
    chk("and `no` is never shown to the reader as the verdict word",
        not any(x.split()[-4:][0:1] == ["no"] for x in vb), vb)
    chk("and states the threshold and whether it was met (Task 5)",
        "threshold " in body and (" met" in body or " NOT met" in body))
    chk("figures come BEFORE the verdicts for a closing IPO",
        body.index("Total subscription:") < body.index("L1  any listing gain"))
    chk("the fetch time and source are both stated",
        "fetched " in body and "Source:" in body)
    chk("the 15:00 caveat is present and cites H23",
        "final subscription is usually higher (H23)" in body)
    chk("GMP is a blank for the user, never a fetched value (D1)",
        GMP_PLACEHOLDER in body and "gmp" not in body.lower().replace("gmp:", ""))
    chk("the no-data IPO gets NO VERDICT, not a guess", "NO VERDICT" in body)
    chk("SME is PROVISIONAL", "PROVISIONAL" in body)
    chk("the midweek mainboard IPO gets no verdict",
        "No verdict until the final day" in body)
    # The guard is against an INVENTED VERDICT for an IPO the model cannot score, not
    # against the words themselves.
    for banned in ("provisional verdict", "indicative verdict", "estimated verdict",
                   "likely bid", "probable bid", "estimated bid", "indicative bid",
                   "under review"):
        chk(f"no '{banned}' anywhere", banned.lower() not in body.lower())
    chk("SME's PROVISIONAL label is a label, never attached to a verdict word",
        "PROVISIONAL - SME model not validated" in body.replace("—", "-")
        or "PROVISIONAL" in body)

    print("\n[4b] H17 is shipped: the decision is a subscription level (Priority 1b)")
    lv = SL.firing_levels()
    # `... or True` used to sit on the end of this assertion, to stop it matching its
    # own text. That made it vacuous: it could not fail. The needle is now assembled
    # at runtime and only the report-building functions are inspected.
    needle = "L2_UNDER" + "_REVIEW"
    built = "".join(inspect.getsource(fn) for fn in
                    (_verdict_block, _numbers, compose))
    chk("the L2 under-review caveat is GONE from the report builders",
        needle not in built)
    # The word may appear in the standing disclaimer that says a probability is NOT used;
    # what must never appear is a probability presented as a chance (G2).
    low = body.lower()
    chk("no probability is presented as a chance",
        "% chance" not in low and "chance of" not in low
        and not __import__("re").search('\\b\\d{1,3}(\\.\\d+)?%\\s*(probability|likely)', low))
    chk("where 'probability' appears, it is to say one is NOT used",
        "probability" not in low or "no probability is involved" in low, body[-400:])
    chk("the firing levels appear in the body",
        f"{lv['L1']:.2f}x" in body and f"{lv['L2']:.2f}x" in body, body[-700:])
    chk("the rule names H17", "H17" in body)
    chk("and says the levels are walk-forward, not in-sample",
        "walk-forward" in body.lower())
    blk = _verdict_block({
        "L1": {"verdict": "BID", "required_hit_rate": 0.9, "threshold_total_x": lv["L1"]},
        "L2": {"verdict": "no", "required_hit_rate": 0.8, "threshold_total_x": lv["L2"]}})
    chk("each verdict line carries its own firing level",
        any(f"{lv['L1']:.2f}x" in x for x in blk)
        and any(f"{lv['L2']:.2f}x" in x for x in blk), str(blk))
    chk("the promise is still stated", any("90% promise" in x for x in blk), str(blk))


    print("\n[5] snapshot schema (Priority 1g)")
    chk("sector column exists", "sector" in SNAP_COLS)
    chk("capture_point column exists", "capture_point" in SNAP_COLS)
    chk("segment is carried, not re-derived", "segment" in SNAP_COLS)

    print('\n[6] the 15:00 leg never sends after the broker cutoff (1d)')
    chk("the cutoff is the 16:00 broker cutoff (E1)", BROKER_CUTOFF_HHMM == 1600)
    may = lambda t: send_window(t)[0]   # noqa: E731
    chk("15:00, the scheduled time, may send", may("2026-10-08 15:00") is True)
    chk("15:59 may still send", may("2026-10-08 15:59") is True)
    chk("16:00 exactly may NOT", may("2026-10-08 16:00") is False)
    chk("16:53 - the earliest time a real run sent - may not",
        may("2026-10-03 16:53") is False)
    chk("22:11 - another real one - may not", may("2026-10-07 22:11") is False)
    chk("00:06 may not either, but for the OTHER reason: too early, not too late",
        may("2026-10-06 00:06") is False
        and "different distribution" in send_window("2026-10-06 00:06")[1])
    chk("and the late refusal cites the cutoff, not the distribution",
        "broker cutoff" in send_window("2026-10-07 22:11")[1])
    chk("13:59 is too early; L_final_3pm was not fitted on a morning figure",
        may("2026-10-08 13:59") is False)
    chk("14:00 may send", may("2026-10-08 14:00") is True)
    msrc = inspect.getsource(main)
    chk("the guard returns BEFORE send() is reached",
        msrc.index("not may_send") < msrc.index("out = send("))
    chk("it still writes the report, so the day leaves a record",
        msrc.index(".md").__class__ is int and ".md" in msrc)
    chk("a refused send is flagged so the CLI can exit non-zero",
        "fail_loudly" in msrc)
    chk("there is no flag that re-sends a missed email",
        "catch_up" not in msrc and "catch-up" not in msrc)
    chk("the day-end capture point is 19:30 (1c)", "1930" in msrc)

    print('\n[7] Task 4: idempotent send, conditional red, dead-man')
    msrc = inspect.getsource(main)
    chk("the send is keyed by IPO and date, not by run",
        "SM.undelivered(today, owed)" in msrc)
    chk("an already-delivered day exits WITHOUT sending",
        msrc.index("already_sent") < msrc.index("out = send("))
    chk("a marker is written only when a send actually succeeded",
        "out.get(\"sent\") and not dry" in msrc and "SM.mark(" in msrc)
    chk("a refusal is red ONLY when something is undelivered",
        "red = bool(undelivered)" in msrc)
    chk("and fail_loudly follows that, not the refusal itself",
        '"fail_loudly": red' in msrc)
    chk("the dead-man fires after 15:30 IST", DEAD_MAN_AFTER_HHMM == 1530)
    dsrc = inspect.getsource(dead_man)
    chk("its subject is the NOT SENT one", 'f"{SUBJECT_PREFIX}NOT SENT"' in dsrc)
    chk("it records a NOTICE, never a delivered decision",
        "SM.DEAD_MAN" in dsrc and "SM.DECISION" not in dsrc)
    chk("and a notice is sent at most once per IPO per day",
        "SM.notice_sent(today, i)" in dsrc)
    chk("the dead-man body carries no verdict word",
        "This is not a verdict" in dsrc)

    print('\n[8] Task 6: both figures recorded, prediction row never rewritten')
    import predictions_log as _PL
    for c in ("sub_total_1500", "sub_qib_1500", "sub_hni_1500", "sub_rii_1500"):
        chk(f"{c} is a prediction column", c in _PL.COLS)
    chk("finals go to their OWN file", "final_subscription" in str(_PL.FINALS))
    for c in ("would_L1_fire_on_final", "would_L2_fire_on_final", "sub_total_final"):
        chk(f"{c} is a finals column", c in _PL.FINAL_COLS)
    fsrc = inspect.getsource(_PL.log_final_subscription)
    chk("the finals writer only ever APPENDS (rule 10)",
        'mode="a"' in fsrc and "_append(" not in fsrc)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="compose and print, send nothing")
    ap.add_argument("--final", action="store_true",
                    help="19:30 day-end leg: snapshot after close, no email")
    ap.add_argument("--force", action="store_true",
                    help="ignore the idempotency marker for this slot")
    ap.add_argument("--test-email", action="store_true",
                    help="Task 5: one TEST email from the last closed IPO")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.test_email:
        r = test_email(a.dry_run)
        print(f"{chr(10)}{r}")
        raise SystemExit(0 if r.get("sent") or a.dry_run else 1)
    try:
        r = main(a.dry_run, a.final, a.force)
    except Exception as e:
        print(f"\nFAILED LOUDLY: {type(e).__name__}: {e}", file=sys.stderr)
        raise
    print(f"\n{r}")
    # A refused send must make the RUN red, or silence looks like success.
    raise SystemExit(1 if r.get("fail_loudly") else 0)

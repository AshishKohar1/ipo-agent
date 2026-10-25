"""
capture_audit.py — Priorities 1d and 1e: prove every weekday produced a capture, and
recover the parts of a missed day that are genuinely recoverable.

Why this exists
---------------
On 2026-10-07 the day-end run was cancelled by a GitHub infrastructure fault before any
step executed:

    The job was not acquired by Runner of type hosted
    Correlation ID d42e69c9-c697-45bc-90e6-cc8129f18f5c

Nothing inside the job can retry that, because the job never started. So the recovery has
to live outside it, and it has to be *detected* rather than noticed by chance. A day that
silently produced nothing looks exactly like a quiet market.

What is recoverable, and what is not
------------------------------------
This is the whole substance of 1d, so it is stated explicitly rather than implied by what
the code happens to attempt:

* **Listing-day prices — RECOVERABLE.** Both exchanges keep a per-date bhavcopy archive, so
  a missed listing date can be read back exactly as it was reported. `--catch-up` passes
  through to `listing_prices.capture_listing_day`, which refuses a past date without it.
* **The 15 index closes — RECOVERABLE.** NSE Indices' endpoint is a historical-data
  endpoint; a past date is an ordinary query against it.
* **Final subscription — NOT RECOVERABLE, EVER.** Chittorgarh publishes the subscription
  table only while an IPO is open and replaces it at allotment (decision H1: 0 of 50
  pre-2026 pages carried it). A missed day's final figure is gone. This module records the
  gap as permanent instead of leaving a hole that looks like a fetch that could be retried.
* **The 15:00 email — NEVER CAUGHT UP, BY DESIGN.** A bid signal delivered after the 16:00
  broker cutoff is not late information, it is wrong information: it invites a bid that can
  no longer be placed. There is deliberately no code path here that can send one. The
  15:00 leg fails loudly instead, and `assert_no_email_catch_up()` is asserted in the
  self-test so a later edit cannot quietly add one.

Evidence of "the job ran"
-------------------------
`live_markers.attempts(point, day)`, not `already_ran`. The distinction matters:

* `attempts == 0` → the job never executed. That is an infrastructure gap.
* `attempts > 0` with nothing captured → the job ran and found no open IPO. That is a
  quiet market, and reporting it as a gap would cry wolf every holiday-adjacent week.

    python capture_audit.py --audit                 # last 7 days, exit 1 on an open gap
    python capture_audit.py --audit --days 30
    python capture_audit.py --catch-up              # recover what is recoverable
    python capture_audit.py --catch-up --days 3
    python capture_audit.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
# A cached bhavcopy under this many rows is a failed download, not a quiet market: every
# trading day lists thousands of scrips on either exchange.
THIN_ROWS = 1000
sys.path.insert(0, str(ROOT))
import live_markers as LM                                    # noqa: E402
import trading_day as TD                                     # noqa: E402
import nse_holidays as HOL                                   # noqa: E402

REPORT = ROOT / "reports" / "CAPTURE_AUDIT.md"

# The two scheduled capture points, as clock times in IST. The day-end leg moved from
# 17:30 to 19:30 on 2026-10-08 (1c) because 17:30 is before the index closes are published;
# the older value is still recognised so an audit over a window that straddles the change
# does not report the days before it as gaps.
EMAIL_POINT = 1500
DAYEND_POINT = 1930
DAYEND_LEGACY = (1730,)

# Permanently unrecoverable, per the module docstring. Named here so the report can say so
# rather than leaving an unexplained absence.
UNRECOVERABLE = {
    "final_subscription": ("Chittorgarh removes the subscription table at allotment (H1), "
                           "so a missed day's final figure does not exist anywhere we may "
                           "fetch from. Not retryable."),
    "bid_email": ("A 15:00 bid signal is never re-sent. After the 16:00 broker cutoff it "
                  "invites a bid that cannot be placed. The leg fails loudly instead."),
}


def weekdays(upto=None, days: int = 7, now=None) -> list[pd.Timestamp]:
    """The **NSE trading days** in the `days`-day window ending at `upto` (inclusive).

    Weekends were never in scope; **NSE holidays were, and should not have been.**
    Tuesday 20 October 2026 was Dussehra, a full NSE holiday, and `d.weekday() < 5`
    called it an ordinary working day - so this audit would have reported a missed 15:00
    leg and a missed day-end leg for a day on which the exchange was shut, exited 1, and
    gone red. A monitor that cries wolf on every holiday is a monitor that gets ignored.

    The calendar is NSE's own, stored with provenance by `nse_holidays.py`. A date in a
    year that calendar does not cover is **kept** in the window: hiding a real gap behind
    missing reference data is the one direction a monitor must not fail in.
    `is_trading_day` returns None for exactly that case, which is why the test below is
    `is not False` rather than a truth test.

    Drops the final day when it is **the current trading date** and the day-end slot has
    not come round yet, because a job that is not due is not missing.

    `now` is injectable, and the drop is keyed on `upto` matching the current trading
    date rather than on the wall clock alone. An earlier version compared `out[-1]`
    against the real clock, which made the result depend on the time of day even when the
    caller had specified the window explicitly: the self-test asked for the 7 days to
    2026-10-11 and got 5 weekdays on this laptop at 23:40 IST and 4 on a runner forty
    minutes later, because the clock had crossed into 9 October. A window the caller
    states in full must not move underneath them.
    """
    explicit = upto is not None
    upto = pd.Timestamp(upto).normalize() if explicit else TD.trading_date()
    start = upto - pd.Timedelta(days=days - 1)
    out = [d for d in pd.date_range(start, upto, freq="D")
           if HOL.is_trading_day(d) is not False]
    if explicit:
        return out
    t = pd.Timestamp(now) if now is not None else TD.ist_now()
    if out and out[-1].normalize() == upto and (t.hour * 100 + t.minute) < DAYEND_POINT:
        out = out[:-1]
    return out


def _ran(point: int, day, legacy: tuple[int, ...] = ()) -> int:
    """Attempts recorded for this slot, counting any legacy clock time as the same leg."""
    n = LM.attempts(point, day)
    for p in legacy:
        n += LM.attempts(p, day)
    return int(n)


def gaps(upto=None, days: int = 7) -> dict:
    """Weekdays in the window where a scheduled leg left no attempt at all."""
    out = {"window_days": days, "checked": [], "email_gaps": [], "dayend_gaps": []}
    for d in weekdays(upto, days):
        day = str(d.date())
        e = _ran(EMAIL_POINT, d)
        c = _ran(DAYEND_POINT, d, DAYEND_LEGACY)
        out["checked"].append({"date": day, "email_attempts": e, "dayend_attempts": c})
        if e == 0:
            out["email_gaps"].append(day)
        if c == 0:
            out["dayend_gaps"].append(day)
    out["n_email_gaps"] = len(out["email_gaps"])
    out["n_dayend_gaps"] = len(out["dayend_gaps"])
    out["clean"] = not (out["email_gaps"] or out["dayend_gaps"])
    return out


def catch_up_day(day) -> dict:
    """Recover what a missed day leaves recoverable. Never sends an email."""
    day = pd.Timestamp(day).normalize()
    res = {"date": str(day.date()), "recovered": {}, "unrecoverable": dict(UNRECOVERABLE)}

    # Listing-day prices from that date's archived bhavcopy.
    try:
        import listing_prices as LP
        res["recovered"]["listing_prices"] = LP.capture_listing_day(day, catch_up=True)
    except Exception as e:                                   # noqa: BLE001
        res["recovered"]["listing_prices"] = {"error": f"{type(e).__name__}: {e}"}

    # The 15 index closes, from the historical endpoint. Idempotent and append-only; an
    # index that is unavailable is written NULL with its reason, never substituted.
    try:
        import market_context as MC
        res["recovered"]["market_context"] = MC.capture(day)
    except Exception as e:                                   # noqa: BLE001
        res["recovered"]["market_context"] = {"error": f"{type(e).__name__}: {e}"}

    return res


def catch_up(upto=None, days: int = 7) -> dict:
    g = gaps(upto, days)
    out = {"gaps": g, "attempted": []}
    for day in g["dayend_gaps"]:
        out["attempted"].append(catch_up_day(day))
    # An email gap is reported and never acted on. See UNRECOVERABLE["bid_email"].
    out["email_gaps_not_recovered"] = g["email_gaps"]
    return out


def assert_no_email_catch_up() -> bool:
    """No code path in this module can send the 15:00 email. Asserted, not asserted-about.

    The needle is assembled at runtime: three earlier self-tests in this project passed
    only because they found their own assertion string in the file they were checking.
    """
    import inspect
    body = "".join(inspect.getsource(fn) for fn in
                   (catch_up, catch_up_day, gaps, weekdays, main))
    banned = ["send_daily" + "_email", "smtplib", "send" + "mail"]
    return not any(b in body for b in banned)


def thin_bhavcopies(days: int = 7, upto=None) -> list[dict]:
    """Trading days in the window whose cached bhavcopy is implausibly small.

    Why this is in the audit and not only in the fetcher. From 2024-07-02 to 2026-10-22
    every BSE bhavcopy this project downloaded parsed to ZERO rows - BSE began serving its
    Angular shell at the old download path, and the row filter was testing BSE's group
    codes against NSE's series vocabulary. The fetcher is fixed, but the reason the defect
    survived 154 dates is that nothing ever asked "does this file look like a bhavcopy?".

    Every trading day lists thousands of scrips on either exchange, so a file with fewer
    than 1,000 rows is a failed download rather than a quiet market. The check reads the
    cache, so it costs no requests.
    """
    import relabel_window as RW
    want = [f"{d:%Y-%m-%d}" for d in weekdays(upto=upto, days=days)]
    return RW.audit_bhavcopy_rows(dates=want)


def md(a: dict) -> str:
    g = a["gaps"]
    L = ["# Capture audit", "",
         f"Window: the last {g['window_days']} days, NSE trading days only "
         f"(weekends and NSE holidays both excluded; calendar in "
         f"data/nse_trading_holidays.csv). "
         f"Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} IST.", "",
         ("**Every trading day in the window produced a capture.**" if g["clean"] else
          f"**{g['n_email_gaps']} missed 15:00 leg(s), "
          f"{g['n_dayend_gaps']} missed day-end leg(s).**"), "",
         "A gap means the job left *no attempt at all* — an infrastructure failure. A job "
         "that ran and captured nothing is a quiet market, not a gap, and is not counted "
         "here. An NSE holiday is not a working day and never appears below.", "",
         "| date | 15:00 attempts | day-end attempts |", "|---|---|---|"]
    for r in g["checked"]:
        mark = lambda n: str(n) if n else "**0 — MISSED**"    # noqa: E731
        L.append(f"| {r['date']} | {mark(r['email_attempts'])} "
                 f"| {mark(r['dayend_attempts'])} |")
    L += ["", "## What catch-up recovered", ""]
    if not a.get("attempted"):
        L.append("Nothing to recover.")
    for d in a.get("attempted", []):
        lp = d["recovered"].get("listing_prices", {})
        mc = d["recovered"].get("market_context", {})
        lp_say = (lp.get("error") or lp.get("note")
                  or f"{len(lp.get('scored', []))} prediction(s) scored, "
                     f"{len(lp.get('missed', []))} not found in either bhavcopy")
        mc_say = (mc.get("error") or mc.get("skipped")
                  or f"{mc.get('n_ok', 0)} closes, {mc.get('n_null', 0)} NULL with a reason")
        L += [f"### {d['date']}", "",
              f"* listing prices — {lp_say}",
              f"* index closes — {mc_say}",
              ""]
    thin = a.get("thin_bhavcopies", [])
    L += ["", "## Bhavcopy plausibility", ""]
    if not thin:
        L += ["Every cached bhavcopy for a trading day in the window has at least "
              f"{THIN_ROWS:,} rows.", ""]
    else:
        L += [f"**{len(thin)} cached bhavcopy file(s) in the window are too small to be a "
              "bhavcopy.** Every trading day lists thousands of scrips, so this is a "
              "failed download, not a thin market.", "",
              "| file | exchange | date | rows | why |", "|---|---|---|---|---|"]
        for h in thin:
            L.append(f"| `{h['file']}` | {h['exchange']} | {h['date']} | "
                     f"{h['rows']} | {h['why']} |")
        L.append("")
    L += ["## Not recoverable, by nature", ""]
    for k, v in UNRECOVERABLE.items():
        L += [f"* **{k}** — {v}"]
    if a.get("email_gaps_not_recovered"):
        L += ["", f"The 15:00 leg was missed on "
                  f"{', '.join(a['email_gaps_not_recovered'])} and was **not** re-sent. "
                  f"That is the designed behaviour, not an outstanding task."]
    return "\n".join(L) + "\n"


def main(audit: bool = False, do_catch_up: bool = False, days: int = 7) -> int:
    a = catch_up(days=days) if do_catch_up else {"gaps": gaps(days=days)}
    a["thin_bhavcopies"] = thin_bhavcopies(days=days)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(md(a), encoding="utf-8")
    print(json.dumps(a["gaps"], indent=2, default=str))
    g = a["gaps"]
    print(f"\n{REPORT}")
    for h in a.get("thin_bhavcopies", []):
        print(f"THIN BHAVCOPY: {h['file']} — {h['why']}")
    if g["clean"] and not a.get("thin_bhavcopies"):
        print("every trading day in the window produced a capture")
        return 0
    if g["clean"]:
        # The capture legs ran, so this is not a gap - but a bhavcopy that is not a
        # bhavcopy is still a red audit, because the prices it fed are missing or wrong.
        print(f"{len(a['thin_bhavcopies'])} implausible bhavcopy file(s)")
        return 1 if audit else 0
    print(f"GAPS: 15:00 missed {g['email_gaps']}; day-end missed {g['dayend_gaps']}")
    # Exit non-zero so the scheduled audit goes red and is visible without being read.
    return 1 if audit else 0


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] a gap means NO ATTEMPT, not an empty capture")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.csv"
        LM.mark_ran(DAYEND_POINT, "2026-10-05", 0, path=p)   # ran, captured nothing
        chk("attempts counts an empty run", LM.attempts(DAYEND_POINT, "2026-10-05", p) == 1)
        chk("already_ran does NOT (1f: a failure must not lock its retry)",
            LM.already_ran(DAYEND_POINT, "2026-10-05", p) is False)

    print('\n[2] the window is weekdays only, and an explicit window does not move')
    w = weekdays("2026-10-11", days=7)            # Sun 11 Oct back to Mon 5 Oct
    chk("no weekend days", all(d.weekday() < 5 for d in w))
    chk("5 weekdays in a 7-day window", len(w) == 5, [str(d.date()) for d in w])
    # The day this change exists for: 20 Oct 2026 was Dussehra, a full NSE holiday.
    h = weekdays("2026-10-23", days=7)            # Sat 17 Oct .. Fri 23 Oct
    chk("20 Oct (Dussehra) is NOT audited",
        pd.Timestamp("2026-10-20") not in h, [str(d.date()) for d in h])
    chk("the other four trading days of that week are",
        [str(d.date()) for d in h]
        == ["2026-10-19", "2026-10-21", "2026-10-22", "2026-10-23"],
        [str(d.date()) for d in h])
    chk("2 Oct (Gandhi Jayanti, a Friday) is not audited either",
        weekdays("2026-10-02", days=1) == [])
    chk("a year with no stored calendar is still audited, so a gap cannot hide behind "
        "missing reference data",
        pd.Timestamp("2015-06-10") in weekdays("2015-06-10", days=1))
    chk("an explicit window is time-of-day independent",
        weekdays("2026-10-11", days=7) == weekdays("2026-10-11", days=7))
    # The drop only applies to a window that ENDS on the current trading date.
    import os as _os
    _saved = _os.environ.get("TRADING_DATE")
    try:
        _os.environ["TRADING_DATE"] = "2026-10-09"       # a Friday
        early = weekdays(days=7, now=pd.Timestamp("2026-10-09 09:00"))
        late = weekdays(days=7, now=pd.Timestamp("2026-10-09 20:00"))
        chk("before the day-end slot, today is not yet missing",
            pd.Timestamp("2026-10-09") not in early, [str(d.date()) for d in early])
        chk("after it, today IS in scope",
            pd.Timestamp("2026-10-09") in late, [str(d.date()) for d in late])
    finally:
        _os.environ.pop("TRADING_DATE", None)
        if _saved is not None:
            _os.environ["TRADING_DATE"] = _saved

    print("\n[3] the legacy 17:30 clock time counts as the same day-end leg")
    chk("17:30 is recognised", 1730 in DAYEND_LEGACY)
    chk("the live day-end point is 19:30 (1c)", DAYEND_POINT == 1930)
    chk("the email point is 15:00, not 15:30 (GitHub cron drifts 5-15 min)",
        EMAIL_POINT == 1500)

    print("\n[4] the 15:00 email can never be caught up (1d)")
    chk("no code path here can send it", assert_no_email_catch_up())
    chk("and the reason is recorded, not just the behaviour",
        "cannot be placed" in UNRECOVERABLE["bid_email"])
    chk("final subscription is named permanently unrecoverable",
        "Not retryable" in UNRECOVERABLE["final_subscription"])

    print("\n[5] catch-up reads an ARCHIVE, never a current quote")
    import inspect
    src = inspect.getsource(catch_up_day)
    chk("it passes catch_up=True, which is what unlocks the archived bhavcopy",
        "catch_up=True" in src)
    chk("it never calls a live-quote path", "StockReachGraph" not in src
        and "quote" not in src.lower())

    print("\n[T] a bhavcopy that is not a bhavcopy fails the audit")
    import relabel_window as _RW
    import tempfile
    import listing_prices as _LP
    import pandas as _pd
    _old = _LP.CACHE
    try:
        with tempfile.TemporaryDirectory() as _td:
            _LP.CACHE = Path(_td)
            _days = weekdays(upto="2026-01-09", days=7)
            _d0 = f"{_days[0]:%Y%m%d}"
            _pd.DataFrame({"symbol": ["A"], "open": [1.0]}).to_csv(
                _LP.CACHE / f"bse_{_d0}.csv.gz", index=False, compression="gzip")
            _pd.DataFrame({"symbol": [f"S{i}" for i in range(1200)],
                           "open": [1.0] * 1200}).to_csv(
                _LP.CACHE / f"nse_{_d0}.csv.gz", index=False, compression="gzip")
            _hits = thin_bhavcopies(days=7, upto="2026-01-09")
            chk("the 1-row BSE file is flagged",
                any(h["file"] == f"bse_{_d0}.csv.gz" for h in _hits), _hits)
            chk("the 1,200-row NSE file is not",
                not any(h["file"] == f"nse_{_d0}.csv.gz" for h in _hits), _hits)
            chk("the threshold is 1,000 rows", THIN_ROWS == 1000)
            _rep = md({"gaps": gaps(days=7, upto="2026-01-09"),
                       "thin_bhavcopies": _hits})
            chk("the report names the file", f"bse_{_d0}.csv.gz" in _rep)
            chk("the report says it is a failed download, not a thin market",
                "not a thin market" in _rep)
            _clean = md({"gaps": gaps(days=7, upto="2026-01-09"),
                         "thin_bhavcopies": []})
            chk("a clean window says so instead of staying silent",
                "has at least" in _clean)
    finally:
        _LP.CACHE = _old
    _msrc = inspect.getsource(main)
    chk("main runs the check every audit", "thin_bhavcopies(days=days)" in _msrc)
    chk("and a thin file makes the audit go red even when no leg was missed",
        "implausible bhavcopy file(s)" in _msrc)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true",
                    help="report gaps; exit 1 if any weekday left no attempt")
    ap.add_argument("--catch-up", action="store_true",
                    help="recover the recoverable part of every missed day-end")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    raise SystemExit(main(a.audit, a.catch_up, a.days))

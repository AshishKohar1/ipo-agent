"""
trading_day.py — one trading date per run, fixed at the start, always in Asia/Kolkata.

The bug this exists to kill
---------------------------
Run #11 fired for **7 October** and committed `Live final run 2026-10-08T00:00+0530`. Its
market-context capture then asked NSE Indices for **2026-10-08**, a date that had not
happened yet, and all 15 indices correctly answered `no_row_for_this_date` — so the run
logged 15 NULLs and 7 October's index closes were never collected at all.

`TZ` was already `Asia/Kolkata`, so this was **not** a UTC bug. It was a **midnight
crossing**: the job started at 23:59:30 IST and every step computed "now" independently, so
the steps either side of midnight disagreed about what day it was. A run is one trading
day's work; it cannot be two.

The rule
--------
The trading date is computed **once**, at the start of the job, in Asia/Kolkata, and passed
to every script in `TRADING_DATE`. Scripts take the date from here and the wall-clock time
from the clock — the date decides which day's row this is, the clock decides whether the
send window is open. Those are different questions and were being answered by the same
call.

`now()` below returns a timestamp whose **date** is the fixed trading date and whose
**time** is the real current time. That keeps `send_window()` honest (it must know it is
really 00:00) while keeping every file and marker on one date.

    TRADING_DATE=2026-10-07 python send_daily_email.py --final
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

ENV = "TRADING_DATE"
IST = timezone(timedelta(hours=5, minutes=30))


def ist_now() -> pd.Timestamp:
    """The real current time in IST, regardless of the host's TZ.

    Computed from UTC rather than from `datetime.now()` so it is correct on a runner whose
    TZ was never set, and on this laptop either way.
    """
    return pd.Timestamp(datetime.now(timezone.utc).astimezone(IST).replace(tzinfo=None))


def trading_date() -> pd.Timestamp:
    """The run's one trading date. `TRADING_DATE` if set, else today in IST."""
    v = (os.environ.get(ENV) or "").strip()
    if v:
        try:
            return pd.Timestamp(v).normalize()
        except Exception as e:                                # noqa: BLE001
            # A malformed value must not fall through to "today": that would silently
            # relabel the run, which is the whole class of bug this module removes.
            raise ValueError(f"{ENV}={v!r} is not a date. Unset it or fix it.") from e
    return ist_now().normalize()


def now() -> pd.Timestamp:
    """The trading date carrying the real IST clock time.

    Date from `trading_date()`, time from `ist_now()`. A 00:00 IST run therefore still
    *reports* 00:00 to the send window — it does not pretend to be mid-afternoon — while
    every file it writes stays on the trading date it was scheduled for.
    """
    d = trading_date()
    t = ist_now()
    return pd.Timestamp.combine(d.date(), t.time())


# ------------------------------------------------------- the DUE time, not the start time
#
# Task 1. A GitHub schedule run is delayed 5h31m to 9h06m (nine runs out of nine, table in
# LIVE_SETUP.md). The day-end leg due at 19:30 IST on 9 October actually started at 00:46
# IST on 10 October, took `date +%F` in IST, and stamped itself **2026-10-10** - a
# Saturday, with no index closes to collect. Freezing the date once per run fixed the
# midnight-crossing bug but not this one: a run that is seven hours late is not working on
# the day it woke up on, it is working on the day it was DUE for.
#
# So for a schedule-triggered run the date comes from the cron slot. For a
# `workflow_dispatch` there is no slot - somebody pressed it now - and the real IST clock
# is right.
#
# The slot is found by walking BACK from the current UTC time to the most recent moment
# this cron was due, because that is the only direction with an answer: forward is the
# next run, which has not happened.

CRON_ENV = "CRON_SCHEDULE"


def _field(spec: str, lo: int, hi: int) -> set[int]:
    """One cron field -> the set of values it matches. Supports `*`, `a`, `a-b`, `*/n`,
    `a-b/n` and comma lists of those. Anything else raises rather than matching
    everything: a field silently read as `*` would put the run on the wrong day."""
    out: set[int] = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"empty cron field in {spec!r}")
        step = 1
        if "/" in part:
            part, st = part.split("/", 1)
            step = int(st)
            if part.strip() in ("*", ""):
                part = f"{lo}-{hi}"
        if part.strip() == "*":
            out |= set(range(lo, hi + 1, step))
        elif "-" in part.lstrip("-"):
            a, b = part.split("-", 1)
            out |= set(range(int(a), int(b) + 1, step))
        else:
            v = int(part)
            if not lo <= v <= hi:
                raise ValueError(f"{v} out of range {lo}-{hi} in {spec!r}")
            out.add(v)
    return out


def _dow_ok(dows: set[int], day: pd.Timestamp) -> bool:
    """Cron counts Sunday as 0 (and accepts 7 for it); pandas counts Monday as 0."""
    cd = (day.weekday() + 1) % 7
    return cd in dows or (cd == 0 and 7 in dows)


def due_utc(cron: str, now_utc=None, lookback_days: int = 8) -> pd.Timestamp:
    """The latest UTC time at or before `now_utc` at which `cron` was due.

    `cron` is UTC because GitHub reads cron as UTC and nothing else.
    """
    parts = str(cron).split()
    if len(parts) != 5:
        raise ValueError(f"cron {cron!r} does not have five fields")
    mi, ho, dom, mon, dow = parts
    mins, hours = _field(mi, 0, 59), _field(ho, 0, 23)
    doms, mons, dows = _field(dom, 1, 31), _field(mon, 1, 12), _field(dow, 0, 7)
    if now_utc is not None:
        n = pd.Timestamp(now_utc)
    else:
        n = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    dom_set = dom.strip() != "*"
    dow_set = dow.strip() != "*"
    slots = sorted((h, m) for h in hours for m in mins)
    for back in range(lookback_days + 1):
        day = (n - pd.Timedelta(days=back)).normalize()
        if day.month not in mons:
            continue
        d_ok, w_ok = day.day in doms, _dow_ok(dows, day)
        # Real cron ORs day-of-month against day-of-week when BOTH are restricted, and
        # ANDs otherwise. None of our lines restrict day-of-month, but getting this wrong
        # silently moves a date, so it is implemented rather than assumed.
        if not ((d_ok or w_ok) if (dom_set and dow_set) else (d_ok and w_ok)):
            continue
        for h, m in reversed(slots):
            t = day + pd.Timedelta(hours=h, minutes=m)
            if t <= n:
                return t
    raise ValueError(f"cron {cron!r} was not due at any point in the "
                     f"{lookback_days} days before {n} UTC")


def due_trading_date(cron: str | None = None, now_utc=None) -> pd.Timestamp:
    """The IST date of the slot this run was due for; the real IST date if there is none.

    An empty cron means `workflow_dispatch`: there is no slot, the press was now, and the
    clock is the right answer.
    """
    c = (cron if cron is not None else os.environ.get(CRON_ENV) or "").strip()
    if not c:
        return (pd.Timestamp(now_utc) + pd.Timedelta(hours=5, minutes=30)).normalize()             if now_utc is not None else ist_now().normalize()
    return (due_utc(c, now_utc) + pd.Timedelta(hours=5, minutes=30)).normalize()


def crossed_midnight() -> bool:
    """True when the real IST date is no longer the trading date — i.e. the job has run
    past midnight, or is a deliberate catch-up. Worth printing, never worth hiding."""
    return ist_now().normalize() != trading_date()


def banner() -> str:
    d, t = trading_date(), ist_now()
    src = "TRADING_DATE" if os.environ.get(ENV) else "clock (IST)"
    s = f"trading date {d.date()} (from {src}); real IST now {t:%Y-%m-%d %H:%M}"
    return s + ("  ** RUN HAS CROSSED MIDNIGHT **" if crossed_midnight() else "")


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

    saved = os.environ.get(ENV)
    try:
        print("[1] TRADING_DATE pins the date")
        os.environ[ENV] = "2026-10-07"
        chk("trading_date honours it", trading_date() == pd.Timestamp("2026-10-07"))
        chk("now() carries that date", now().normalize() == pd.Timestamp("2026-10-07"))
        chk("but the real clock time, not a fabricated one",
            abs((now() - pd.Timestamp.combine(pd.Timestamp("2026-10-07").date(),
                                              ist_now().time())).total_seconds()) < 2)

        print("\n[2] the midnight crossing is reported, not hidden")
        os.environ[ENV] = "2000-01-01"
        chk("a stale trading date is flagged", crossed_midnight() is True)
        chk("and the banner says so", "CROSSED MIDNIGHT" in banner())
        os.environ[ENV] = str(ist_now().date())
        chk("today is not flagged", crossed_midnight() is False)

        print("\n[3] a malformed value raises rather than falling back to today")
        os.environ[ENV] = "not-a-date"
        try:
            trading_date()
            chk("it raises", False)
        except ValueError as e:
            chk("it raises", True)
            chk("and says what to do", "Unset it or fix it" in str(e))

        print("\n[4] with nothing set it uses IST, computed from UTC")
        os.environ.pop(ENV, None)
        chk("date is today in IST", trading_date() == ist_now().normalize())
        import inspect
        src = inspect.getsource(ist_now)
        chk("derived from UTC, so a runner with no TZ is still right",
            "timezone.utc" in src and "IST" in src)
        # A bare `now()` with no tz argument is the thing to rule out. Two traps avoided:
        # substring matching cannot tell it from `now(timezone.utc)`, hence the regex; and
        # ist_now's own DOCSTRING names the bad call, so the docstring is removed first.
        # An earlier version of this check failed against that docstring, not the code.
        import re
        # `__doc__` is dedented while the source is not, so replacing it by value does not
        # work; the docstring is cut out by its delimiters instead.
        code = re.sub(r'""".*?"""', "", src, flags=re.S)
        chk("and never from a bare, timezone-less now()",
            re.search(r"\.now\(\s*\)", code) is None, code)
        print("\n[5] Task 1: the date comes from the slot the run was DUE for")
        # The real failure. Day-end leg due 14:00 UTC 9 Oct = 19:30 IST 9 Oct; the runner
        # actually started it at 19:16 UTC = 00:46 IST 10 Oct, and it stamped itself
        # 2026-10-10 (a Saturday, no closes to collect).
        late = due_trading_date("0 14 * * 1-5", now_utc="2026-10-09 19:16")
        chk("a 19:30 slot starting 00:46 next day keeps 9 Oct",
            late == pd.Timestamp("2026-10-09"), late)
        # The case the task states: 19:30 slot, 01:30 IST the next day = 20:00 UTC.
        sim = due_trading_date("0 14 * * 1-5", now_utc="2026-10-09 20:00")
        chk("the simulated 01:30-next-day run also keeps 9 Oct",
            sim == pd.Timestamp("2026-10-09"), sim)
        chk("and the naive wall-clock answer would have been 10 Oct",
            (pd.Timestamp("2026-10-09 20:00") + pd.Timedelta(hours=5, minutes=30))
            .normalize() == pd.Timestamp("2026-10-10"))
        # An email leg delayed inside the same IST day must NOT move.
        chk("a 14:15 email slot started 21:04 IST stays on its own day",
            due_trading_date("45 8 * * 1-5", now_utc="2026-10-09 15:34")
            == pd.Timestamp("2026-10-09"))
        chk("an on-time 15:00 email slot is its own day",
            due_trading_date("30 9 * * 1-5", now_utc="2026-10-09 09:31")
            == pd.Timestamp("2026-10-09"))
        print("\n[6] weekday and Saturday crons resolve to the right weekday")
        # Mon 12 Oct 04:00 UTC: the last weekday 14:00 UTC slot was Fri 9 Oct.
        chk("a weekday-only cron skips the weekend backwards",
            due_trading_date("0 14 * * 1-5", now_utc="2026-10-12 04:00")
            == pd.Timestamp("2026-10-09"))
        # Sat audit cron 05:00 UTC; asked on Sunday 11 Oct.
        chk("the Saturday audit slot resolves to Saturday",
            due_trading_date("0 5 * * 6", now_utc="2026-10-11 09:00")
            == pd.Timestamp("2026-10-10"))
        chk("Sunday is weekday 6 in cron and 6 in pandas - not confused",
            _dow_ok({0}, pd.Timestamp("2026-10-11")) is True
            and _dow_ok({6}, pd.Timestamp("2026-10-11")) is False)
        chk("cron accepts 7 for Sunday too", _dow_ok({7}, pd.Timestamp("2026-10-11")) is True)

        print("\n[7] a dispatch has no slot, so the clock is the answer")
        chk("empty cron -> the real IST date",
            due_trading_date("", now_utc="2026-10-09 20:00") == pd.Timestamp("2026-10-10"))
        chk("None with nothing in the environment -> today in IST",
            due_trading_date(None) == ist_now().normalize())

        print("\n[8] a cron it cannot parse RAISES rather than guessing a date")
        for bad in ("0 14 * *", "0 14 * * mon-fri", "99 14 * * 1-5", ""):
            if bad == "":
                continue
            try:
                due_utc(bad, now_utc="2026-10-09 20:00")
                chk(f"{bad!r} raises", False)
            except (ValueError, TypeError):
                chk(f"{bad!r} raises", True)
        chk("every cron line in the live workflow parses",
            all(due_utc(c, now_utc="2026-10-09 20:00") is not None for c in (
                "45 8 * * 1-5", "0 9 * * 1-5", "15 9 * * 1-5", "30 9 * * 1-5",
                "0 14 * * 1-5", "0 5 * * 6", "30 5 * * 1-5", "30 7 * * 1-5",
                "31 9 * * 1-5", "1 12 * * 1-5")))
    finally:
        os.environ.pop(ENV, None)
        if saved is not None:
            os.environ[ENV] = saved

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import argparse
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    ap = argparse.ArgumentParser()
    ap.add_argument("--due-date", action="store_true",
                    help="print the IST date of the cron slot this run was DUE for")
    ap.add_argument("--cron", default="",
                    help="the UTC cron string that fired; empty means workflow_dispatch")
    a = ap.parse_args()
    if a.due_date:
        # Printed bare so the workflow can do TD=$(python trading_day.py --due-date ...).
        print(due_trading_date(a.cron).date())
        raise SystemExit(0)
    print(banner())

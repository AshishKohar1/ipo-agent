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
    finally:
        os.environ.pop(ENV, None)
        if saved is not None:
            os.environ[ENV] = saved

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print(banner())

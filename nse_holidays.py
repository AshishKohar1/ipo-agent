"""
nse_holidays.py — NSE's own trading-holiday calendar, fetched and stored with provenance.

The defect this closes
----------------------
Nothing in this repository knew what a holiday was. `trading_day.py` handled weekends
(through the cron day-of-week field) and `capture_audit.py` built its window with
`d.weekday() < 5`. So **Tuesday 20 October 2026 — Dussehra, a full NSE holiday** — was an
ordinary weekday to both: the 19:30 day-end leg was expected to capture closes that do not
exist, and the Saturday audit would have counted the day as a gap and exited 1. A monitor
that cries wolf on every holiday is a monitor that gets ignored, which is worse than none.

The source
----------
`https://www.nseindia.com/api/holiday-master?type=trading`, NSE's own calendar, read for
the **CM** (capital market / equities) segment — the segment the day-end capture and the
listing-day bhavcopy belong to. The other eleven segments it serves (FO, CD, COM, ...) do
not always agree, and picking the wrong rung is the mistake already made once with BSE's
four classification levels (H38), so the segment is named explicitly and stored on every
row.

Provenance (rule 1 and rule 2): every row records the source URL, the fetch time in IST
and the SHA-256 of the exact payload it was parsed from. The raw payload is kept beside
it, so a later disagreement can be settled against the bytes NSE actually served.

Coverage is honest
------------------
The endpoint serves the **current calendar year only**. `is_trading_day` therefore returns
a THREE-valued answer for a date in a year the stored calendar does not cover — `None`,
not `True` — because a weekday in an uncovered year is a date we have no calendar for, not
a date we know to be trading. Callers decide what to do with `None`; none of them may
treat it as "trading" silently.

Muhurat: NSE marks a holiday that also carries a special session with a `*` on its
description (2026: Diwali Laxmi Pujan, Sunday 8 November). Those rows are stored with
`muhurat=True` and are still NOT normal trading days; a one-hour ceremonial session is
flagged for a human rather than decided here.

    python nse_holidays.py --fetch        # refresh from NSE
    python nse_holidays.py --list
    python nse_holidays.py --check 2026-10-20
    python nse_holidays.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import trading_day as TD                                       # noqa: E402

DATA = ROOT / "data"
STORE = DATA / "nse_trading_holidays.csv"
RAW = DATA / "nse_holiday_master.json"

URL = "https://www.nseindia.com/api/holiday-master?type=trading"
SEGMENT = "CM"                      # capital market / equities
# H18: realistic browser headers are permitted to official sources. NSE serves this
# endpoint only to a client that has first been given a cookie by the home page.
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"),
      "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}

COLS = ["date", "weekday", "description", "segment", "muhurat",
        "source_url", "fetched_at_ist", "payload_sha256"]


# ------------------------------------------------------------------ fetch
def fetch(write: bool = True) -> pd.DataFrame:
    """NSE's CM-segment trading holidays, with provenance. Never fabricates a row."""
    import requests
    s = requests.Session()
    s.headers.update(UA)
    try:
        s.get("https://www.nseindia.com/", timeout=20)
    except Exception:                                          # noqa: BLE001
        pass
    r = s.get(URL, timeout=30)
    r.raise_for_status()
    payload = r.content
    sha = hashlib.sha256(payload).hexdigest()
    j = json.loads(payload)
    if SEGMENT not in j:
        raise RuntimeError(f"NSE served segments {sorted(j)} with no {SEGMENT}")
    at = TD.ist_now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for e in j[SEGMENT]:
        d = pd.to_datetime(str(e.get("tradingDate")), format="%d-%b-%Y", errors="coerce")
        if pd.isna(d):
            continue
        desc = str(e.get("description") or "").strip()
        rows.append({"date": str(d.date()), "weekday": str(e.get("weekDay") or ""),
                     "description": desc, "segment": SEGMENT,
                     "muhurat": "*" in desc,
                     "source_url": URL, "fetched_at_ist": at, "payload_sha256": sha})
    d = pd.DataFrame(rows, columns=COLS).sort_values("date").reset_index(drop=True)
    if write and len(d):
        DATA.mkdir(exist_ok=True)
        RAW.write_bytes(payload)
        # A refresh must not drop a year the stored file already covers: the endpoint
        # serves the current year only, so the file is the union, newest fetch winning.
        if STORE.exists():
            old = pd.read_csv(STORE)
            d = (pd.concat([old, d], ignore_index=True)
                 .drop_duplicates(subset=["date", "segment"], keep="last")
                 .sort_values("date").reset_index(drop=True))
        d.to_csv(STORE, index=False, encoding="utf-8")
    return d


def load() -> pd.DataFrame:
    if not STORE.exists():
        return pd.DataFrame(columns=COLS)
    d = pd.read_csv(STORE)
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    return d[d["date"].notna()]


def covered_years() -> set[int]:
    """The years the stored calendar actually covers."""
    d = load()
    return set(d["date"].dt.year.unique().tolist()) if len(d) else set()


# ------------------------------------------------------------------ the questions asked
def is_holiday(day) -> bool | None:
    """True / False, or None when the stored calendar does not cover that year."""
    t = pd.Timestamp(day).normalize()
    d = load()
    if t.year not in covered_years():
        return None
    return bool((d["date"] == t).any())


def is_trading_day(day) -> bool | None:
    """False on a weekend; otherwise NSE's calendar. None = we have no calendar for it."""
    t = pd.Timestamp(day).normalize()
    if t.weekday() >= 5:
        return False
    h = is_holiday(t)
    return None if h is None else not h


def holiday_reason(day) -> str | None:
    t = pd.Timestamp(day).normalize()
    d = load()
    hit = d[d["date"] == t]
    return str(hit.iloc[0]["description"]) if len(hit) else None


def trading_days(start, end) -> list[pd.Timestamp]:
    """Trading days in [start, end]. A day we have no calendar for is EXCLUDED, because
    including it would assert a trading day on no evidence."""
    return [d for d in pd.date_range(pd.Timestamp(start).normalize(),
                                     pd.Timestamp(end).normalize(), freq="D")
            if is_trading_day(d) is True]


def next_trading_day(day, within: int = 10) -> pd.Timestamp | None:
    """The first trading day strictly after `day`, or None if the calendar runs out."""
    t = pd.Timestamp(day).normalize()
    for i in range(1, within + 1):
        c = t + pd.Timedelta(days=i)
        if is_trading_day(c) is True:
            return c
    return None


def prev_trading_day(day, within: int = 10) -> pd.Timestamp | None:
    t = pd.Timestamp(day).normalize()
    for i in range(1, within + 1):
        c = t - pd.Timedelta(days=i)
        if is_trading_day(c) is True:
            return c
    return None


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] the stored calendar exists and carries provenance on every row")
    d = load()
    chk("rows are stored", len(d) > 0, len(d))
    chk("every row names its source URL", len(d) and d["source_url"].notna().all())
    chk("every row records the fetch time", len(d) and d["fetched_at_ist"].notna().all())
    chk("every row records the payload SHA-256",
        len(d) and d["payload_sha256"].astype(str).str.len().eq(64).all())
    chk("the segment is NSE's CM rung, named not assumed",
        len(d) and set(d["segment"].unique()) == {"CM"})

    print("\n[2] 20 October 2026 - the day this module exists for")
    chk("is a holiday", is_holiday("2026-10-20") is True)
    chk("is NOT a trading day", is_trading_day("2026-10-20") is False)
    chk("and the reason is NSE's own words",
        (holiday_reason("2026-10-20") or "").lower().startswith("dussehra"),
        holiday_reason("2026-10-20"))
    chk("a plain weekday check would have called it a working day",
        pd.Timestamp("2026-10-20").weekday() < 5)

    print("\n[3] weekends, ordinary weekdays, and the next trading day")
    chk("Monday 19 Oct is a trading day", is_trading_day("2026-10-19") is True)
    chk("Wednesday 21 Oct is a trading day", is_trading_day("2026-10-21") is True)
    chk("Saturday 17 Oct is not", is_trading_day("2026-10-17") is False)
    chk("the trading day after 20 Oct is 21 Oct",
        next_trading_day("2026-10-20") == pd.Timestamp("2026-10-21"))
    chk("the trading day before 20 Oct is 19 Oct",
        prev_trading_day("2026-10-20") == pd.Timestamp("2026-10-19"))
    chk("a 2 Oct holiday that falls on a Friday is caught too",
        is_trading_day("2026-10-02") is False)
    chk("the week of 19 Oct has 4 trading days, not 5",
        len(trading_days("2026-10-19", "2026-10-23")) == 4,
        [str(x.date()) for x in trading_days("2026-10-19", "2026-10-23")])

    print("\n[4] a year with no calendar answers None, never True")
    chk("2015 is not covered", 2015 not in covered_years())
    chk("is_holiday says None", is_holiday("2015-06-10") is None)
    chk("is_trading_day says None for a weekday", is_trading_day("2015-06-10") is None)
    chk("but a weekend is still False without a calendar",
        is_trading_day("2015-06-13") is False)
    chk("trading_days excludes what it cannot vouch for",
        trading_days("2015-06-08", "2015-06-12") == [])
    src = inspect.getsource(is_trading_day)
    chk("the None is deliberate, not a fall-through", "None if h is None" in src)

    print("\n[5] Muhurat is flagged, not decided")
    m = d[d["muhurat"].astype(str).str.lower().isin(("true", "1"))]
    chk("the 2026 Muhurat row is marked", len(m) >= 1, len(m))
    chk("and it is still not a normal trading day",
        all(is_trading_day(x) is False for x in m["date"]))

    print("\n[6] a refresh is a UNION, so an earlier year is never dropped")
    chk("the store is merged, newest fetch winning",
        'drop_duplicates(subset=["date", "segment"], keep="last")' in inspect.getsource(fetch))
    chk("the raw payload is kept beside the parsed rows", RAW.exists())

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        d = fetch()
        print(d[["date", "weekday", "description", "muhurat"]].to_string(index=False))
        print(f"\n{len(d)} rows -> {STORE}")
    if a.check:
        print(f"{a.check}: trading_day={is_trading_day(a.check)} "
              f"holiday={is_holiday(a.check)} reason={holiday_reason(a.check)}")
    if a.list:
        print(load().to_string(index=False))
    if a.self_test:
        raise SystemExit(self_test())

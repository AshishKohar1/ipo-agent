"""
fetch_nifty_tri.py — Nifty 50 Total Return Index from the OFFICIAL source only:
NSE Indices Ltd, https://www.niftyindices.com (Historical Data > Total Return Index).

The site's own page calls POST /BackPage/getTotalReturnIndexString with at most one
year per request. This script pages through 2009-01-01 -> today in <=360-day chunks
and writes data/NIFTY50_TRI.csv (date, tri, ntr). Read it via dataio.load_nifty_tri().

    python fetch_nifty_tri.py
    python fetch_nifty_tri.py --self-test

Single point of failure, stated plainly
---------------------------------------
niftyindices is the ONLY source for this series. No total-return index for the
Indian market exists in BSE's public archive (0 of its 151 indices), and a price
index is not a substitute: the whole point of Model H's target is that it compares
an IPO against a benchmark INCLUDING dividends. So there is no failover here, and
pretending otherwise would be worse than having none.

What happens instead is that a block fails LOUDLY:

* no partial file is written, so the stored TRI is never silently truncated;
* `refresh()` returns `blocked=True` and the summary line
  `NIFTYINDICES BLOCKED - Model H target not refreshed`;
* `model_h_targets` then has no benchmark value past the stored end date, so
  `_bench_at` returns None and the excess target is NULL rather than computed
  against a stale index;
* the 15:00 Model L email is untouched. It uses subscription and issue size,
  reaches no index at all, and must not fail because a benchmark refresh did.

A block is one attempt and final for the run (H47 rule 5). This file used to retry
any failure three times, which included a 403 - the body came back as HTML,
`json.loads` raised, and the retry loop asked twice more.
"""
from __future__ import annotations
import json, time
from pathlib import Path
import pandas as pd
import requests
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from failover import Blocked, BLOCKED_STATUS                # noqa: E402

URL = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
BLOCKED_SUMMARY = "NIFTYINDICES BLOCKED - Model H target not refreshed"
PAGE = "https://www.niftyindices.com/reports/historical-data"
OUT = Path(__file__).resolve().parent / "data" / "NIFTY50_TRI.csv"


def fetch(start="2009-01-01", end=None) -> pd.DataFrame:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                    "Chrome/120 Safari/537.36",
                      "Accept": "application/json, text/javascript, */*; q=0.01",
                      "X-Requested-With": "XMLHttpRequest", "Origin": "https://www.niftyindices.com",
                      "Referer": PAGE})
    s.get(PAGE, timeout=30)                                   # session cookies
    a = pd.Timestamp(start); end = pd.Timestamp(end or pd.Timestamp.today().normalize())
    rows = []
    while a <= end:
        b = min(a + pd.Timedelta(days=360), end)
        cinfo = (f"{{'name':'NIFTY 50','startDate':'{a:%d-%b-%Y}','endDate':'{b:%d-%b-%Y}',"
                 f"'indexName':'NIFTY 50'}}")
        chunk = None
        for attempt in range(3):
            try:
                r = s.post(URL, data=json.dumps({"cinfo": cinfo}), timeout=60,
                           headers={"Content-Type": "application/json; charset=utf-8"})
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"TRI fetch failed for {a:%Y-%m-%d}..{b:%Y-%m-%d}: {e}")
                time.sleep(3)
                continue
            # Check the STATUS before the body. A 403 arrives as HTML, so the old code met
            # it at `json.loads`, raised a parse error, and retried twice more - three
            # requests at a host that had already refused us (H47 rule 5).
            if r.status_code in BLOCKED_STATUS:
                raise Blocked(f"HTTP {r.status_code} from niftyindices "
                              f"for {a:%Y-%m-%d}..{b:%Y-%m-%d}")
            try:
                chunk = json.loads(r.text)
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"TRI fetch failed for {a:%Y-%m-%d}..{b:%Y-%m-%d}: {e}")
                time.sleep(3)
        rows += chunk
        print(f"  {a:%Y-%m-%d} .. {b:%Y-%m-%d}: {len(chunk)} rows")
        a = b + pd.Timedelta(days=1)
        time.sleep(1.0)
    df = pd.DataFrame(rows)
    df = pd.DataFrame({"date": pd.to_datetime(df["Date"], format="%d %b %Y"),
                       "tri": pd.to_numeric(df["TotalReturnsIndex"], errors="coerce"),
                       "ntr": pd.to_numeric(df.get("NTR_Value"), errors="coerce")})
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def refresh(start="2009-01-01", end=None, writer=None) -> dict:
    """Refresh the stored TRI. Never raises on a block; reports it.

    `writer` replaces the disk write so the self-test can prove a simulated block wrote
    nothing at all.
    """
    res = {"ok": False, "blocked": False, "rows": 0, "summary": "", "stored_end": None}
    try:
        prev = pd.read_csv(OUT)
        res["stored_end"] = str(pd.to_datetime(prev["date"]).max().date())
    except Exception:                                       # noqa: BLE001
        pass
    try:
        df = fetch(start, end)
    except Blocked as e:
        # Nothing is written. A partially refreshed TRI is worse than a stale one: a stale
        # one is obvious from its end date, a truncated one is not.
        res["blocked"] = True
        res["summary"] = f"{BLOCKED_SUMMARY} ({e})"
        return res
    except Exception as e:                                  # noqa: BLE001
        res["summary"] = (f"niftyindices FAILED (not a block): {type(e).__name__}: {e}"
                          " - Model H target not refreshed")
        return res
    (writer or (lambda d: d.to_csv(OUT, index=False)))(df)
    res.update(ok=True, rows=len(df),
               summary=(f"Nifty 50 TRI refreshed: {len(df)} rows "
                        f"{df['date'].min():%Y-%m-%d} .. {df['date'].max():%Y-%m-%d}"))
    return res


class _FakeHeaders(dict):
    def update(self, *a, **k):
        pass


def _fake_requests(post_fn):
    """A stand-in for the `requests` module, so a 403 can be simulated without a request."""
    class S:
        def __init__(self):
            self.headers = _FakeHeaders()

        def get(self, *a, **k):
            return None

        def post(self, *a, **k):
            return post_fn()

    return type("R", (), {"Session": staticmethod(S)})


def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    real = fetch.__globals__["requests"]
    wrote = []

    print("[1] a simulated 403 is a BLOCK: reported, not retried, nothing written")
    calls = []

    def post_403():
        calls.append(1)
        return type("Resp", (), {"status_code": 403, "text": "<html>Forbidden</html>"})()

    fetch.__globals__["requests"] = _fake_requests(post_403)
    try:
        res = refresh("2026-01-01", "2026-02-01", writer=wrote.append)
    finally:
        fetch.__globals__["requests"] = real
    chk("blocked is reported", res["blocked"] is True, res)
    chk("ok is False", res["ok"] is False)
    chk("the summary is the exact line the run prints",
        res["summary"].startswith(BLOCKED_SUMMARY), res["summary"])
    chk("the summary names the status", "403" in res["summary"], res["summary"])
    chk("the host was asked exactly ONCE", len(calls) == 1, len(calls))
    chk("NOTHING was written", wrote == [], wrote)
    chk("the stored end date is reported, so staleness stays visible",
        res["stored_end"] is None or len(res["stored_end"]) == 10, res["stored_end"])

    print("\n[2] a fault is not called a block")

    def post_boom():
        raise TimeoutError("timed out")

    fetch.__globals__["requests"] = _fake_requests(post_boom)
    try:
        r2 = refresh("2026-01-01", "2026-02-01", writer=wrote.append)
    finally:
        fetch.__globals__["requests"] = real
    chk("a timeout is not blocked", r2["blocked"] is False, r2)
    chk("and still says the target was not refreshed",
        "not refreshed" in r2["summary"], r2["summary"])
    chk("and still wrote nothing", wrote == [])

    print("\n[3] the status is checked BEFORE the body is parsed")
    src = inspect.getsource(fetch)
    chk("BLOCKED_STATUS is tested before json.loads",
        src.index("BLOCKED_STATUS") < src.index("json.loads(r.text)"))
    chk("a block raises rather than continuing the retry loop", "raise Blocked(" in src)

    print("\n[4] the 15:00 Model L email does not depend on this series")
    import send_daily_email as SDE
    esrc = inspect.getsource(SDE)
    chk("send_daily_email never loads the TRI",
        "load_nifty_tri" not in esrc and "fetch_nifty_tri" not in esrc)
    chk("nor the stored file", "NIFTY50_TRI" not in esrc)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    if ap.parse_args().self_test:
        raise SystemExit(self_test())
    r = refresh()
    print(r["summary"])
    raise SystemExit(0 if r["ok"] else 1)


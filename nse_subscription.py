"""
nse_subscription.py — H22: NSE is the subscription source of record; Chittorgarh is fallback.

Why NSE is primary
------------------
`api/ipo-active-category` reproduced the master's recorded `Total` to two decimal places on
**14 of 14** mainboard IPOs (`reports/NSE_BASKET1_ACCESS.md`). NSE publishes the figure;
Chittorgarh republishes it. Reading the original removes a transcription step and a third
party's uptime from the live path.

**It does not make the figure reconciled.** Fourteen exact matches is evidence of a shared
origin, not of independence — a figure and a copy of it are not two measurements, which is
the same reason `CLAUDE.md` says Chittorgarh and IPOMatrix are not two sources. So
subscription stays **single-origin** and every row keeps its
`single_source_unverified` flag. Rule 2 is not achievable here and the flag must not be
dropped on the strength of this change.

**`api/ipo-detail` is never used.** Its `bidDetails` block is an intermediate cut, not the
close: measured against the same 14 IPOs it runs **9% to 57% lower** than the final figure.
It is the more obvious endpoint, with the richer-looking payload, and building on it would
understate subscription by tens of percent and push every verdict toward `no`. Asserted in
the self-test.

The freshness gate, and why it exists before Task 9 answers the question
------------------------------------------------------------------------
It is **not yet known** whether `ipo-active-category` updates during the bidding day or
only publishes once at 19:00. Every closed issue shows a single `updateTime` of 19:00 on
the final day, which is consistent with either behaviour and proves neither. The HDFIRE
test (13–15 Oct) settles it.

Until it does, promoting NSE to primary unconditionally would risk scoring the 15:00
decision on a zero or on yesterday's number. So a payload is used **only if it passes**:

* the Total is present and strictly positive;
* `updateTime` parses and is **today** (or is absent, which the gate treats as a fail);
* the symbol in the response is the symbol that was asked for.

A payload that fails the gate is not an error — it is NSE saying "nothing published yet",
and the caller falls back to Chittorgarh and records which source was used. That makes
H22 safe to ship provisionally rather than after the test.

    python nse_subscription.py --symbol HDFIRE --series EQ
    python nse_subscription.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import failover as FO                                           # noqa: E402
import trading_day as TD                                     # noqa: E402

HOME = "https://www.nseindia.com/"
REFERER = HOME + "market-data/all-upcoming-issues-ipo"
# The ONLY subscription endpoint this project may read. See the docstring.
ENDPOINT = HOME + "api/ipo-active-category"
# Named so the self-test can assert it is never requested.
FORBIDDEN_ENDPOINT = "api/ipo-detail"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9",
           "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"}
MIN_GAP_S = 3.0
TIMEOUT_S = 30
BACKOFF_S = (15, 45, 90)

# Category labels as NSE spells them, mapped to our four fields. Matched on a normalised
# prefix because the strings are long and have changed punctuation before now.
CATEGORIES = {
    "total": "total",
    "qualified institutional buyers": "qib",
    "non institutional investors": "hni",
    "retail individual investors": "rii",
}


def _norm(s) -> str:
    return re.sub(r"[^a-z ]", "", str(s).lower()).strip()


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return None if pd.isna(x) else x


def parse_update_time(s) -> pd.Timestamp | None:
    """`"Updated as on 25-Feb-2026 19:00:00"` -> a Timestamp, or None.

    None on anything that does not parse, including the literal `"Updated as on null"`
    that a forthcoming issue returns — which must not be read as "now".
    """
    t = str(s or "").replace("Updated as on", "").strip()
    if not t or t.lower() in ("null", "none", "-"):
        return None
    try:
        return pd.Timestamp(t)
    except Exception:                                        # noqa: BLE001
        return None


class Fetcher:
    """One warmed session, polite, with backoff. The WAF closes connections after roughly
    40 requests in a session, so the backoff is not optional."""

    def __init__(self):
        import requests
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self._warm = False
        self._last = 0.0

    def _gap(self):
        w = MIN_GAP_S - (time.time() - self._last)
        if w > 0:
            time.sleep(w)
        self._last = time.time()

    def warm(self) -> bool:
        """Landing page then the IPO page, which is what sets the cookies the API needs.

        `robots.txt` is re-read every run and must say `Allow: /` (rule 3 / B2). If it does
        not, nothing is fetched.
        """
        if self._warm:
            return True
        try:
            self._gap()
            r = self.s.get(HOME + "robots.txt", timeout=TIMEOUT_S)
            if r.status_code != 200 or "Allow: /" not in r.text:
                print(f"  NSE robots.txt did not confirm Allow: / (HTTP {r.status_code})")
                return False
            self._gap()
            self.s.get(HOME, timeout=TIMEOUT_S)
            self._gap()
            self.s.get(REFERER, timeout=TIMEOUT_S)
        except Exception as e:                               # noqa: BLE001
            print(f"  NSE warm-up failed: {type(e).__name__}: {str(e)[:80]}")
            return False
        self._warm = True
        return True

    def get_json(self, url: str):
        for i, wait in enumerate((0,) + BACKOFF_S):
            if wait:
                time.sleep(wait)
            try:
                self._gap()
                r = self.s.get(url, headers={"Referer": REFERER,
                                             "Accept": "application/json"},
                               timeout=TIMEOUT_S)
            except Exception as e:                           # noqa: BLE001
                if i == len(BACKOFF_S):
                    return None, f"{type(e).__name__}: {str(e)[:70]}"
                continue
            if "json" not in r.headers.get("Content-Type", ""):
                return None, f"HTTP {r.status_code} {r.headers.get('Content-Type', '')[:30]}"
            try:
                return r.json(), f"HTTP {r.status_code}"
            except Exception as e:                           # noqa: BLE001
                return None, f"bad json: {str(e)[:60]}"
        return None, "exhausted"


def parse(payload: dict) -> dict:
    """The four figures plus the payload's own update time. No gate applied here."""
    out = {"total": None, "qib": None, "hni": None, "rii": None,
           "update_time": parse_update_time((payload or {}).get("updateTime")),
           "raw_update_time": (payload or {}).get("updateTime"),
           "symbol_in_payload": (payload or {}).get("symbol")}
    for row in (payload or {}).get("dataList", []) or []:
        n = _norm(row.get("category"))
        # The first row of dataList is a HEADER row whose values are the column titles.
        # Taking it as data would set every figure to a sentence.
        if n == "category":
            continue
        for prefix, field in CATEGORIES.items():
            if n.startswith(prefix):
                out[field] = _num(row.get("noOfTotalMeant"))
                break
    return out


def gate(parsed: dict, symbol: str, today=None) -> tuple[bool, str]:
    """`(usable, why_not)`. See the docstring for why this exists before Task 9."""
    today = pd.Timestamp(today).normalize() if today is not None else TD.trading_date()
    t = parsed.get("total")
    if t is None or t <= 0:
        return False, f"Total is {t!r} - nothing published yet"
    u = parsed.get("update_time")
    if u is None:
        return False, (f"no usable updateTime ({parsed.get('raw_update_time')!r}); an "
                       f"undated figure could be any day's")
    if pd.Timestamp(u).normalize() != today:
        return False, (f"updateTime {u:%Y-%m-%d %H:%M} is not the trading date "
                       f"{today.date()} - this is a stale figure")
    got = parsed.get("symbol_in_payload")
    if got and str(got).strip().upper() != str(symbol).strip().upper():
        return False, f"payload is for {got!r}, not {symbol!r}"
    return True, ""


def fetch(symbol: str, series: str = "EQ", f: Fetcher | None = None,
          today=None) -> dict:
    """Live subscription for one symbol, gated. Never raises.

    Returns `{ok, total, qib, hni, rii, source, note, update_time}`. `ok=False` with a
    `note` is a normal outcome, not an error: it means NSE has published nothing usable
    yet and the caller should fall back.
    """
    res = {"ok": False, "total": None, "qib": None, "hni": None, "rii": None,
           "source": "nse_active_category", "symbol": symbol, "series": series,
           "note": "", "update_time": None}
    f = f or Fetcher()
    if not f.warm():
        res["note"] = "NSE warm-up or robots.txt check failed"
        return res
    url = f"{ENDPOINT}?symbol={symbol}&series={series}"
    payload, note = f.get_json(url)
    if payload is None:
        res["note"] = f"fetch failed: {note}"
        return res
    p = parse(payload)
    res.update({k: p.get(k) for k in ("total", "qib", "hni", "rii")})
    res["update_time"] = None if p.get("update_time") is None else str(p["update_time"])
    ok, why = gate(p, symbol, today)
    res["ok"] = ok
    res["note"] = "" if ok else why
    return res


def _status_in(note) -> int | None:
    """The HTTP status a failure note names, if it names one."""
    m = re.search(r"HTTP\s+(\d{3})", str(note or ""))
    return int(m.group(1)) if m else None


def enrich_market_view(mv: dict, f: Fetcher | None = None, today=None) -> dict:
    """H22, provisional: try NSE first for every MAINBOARD IPO closing today.

    On success the row's `sub` is replaced and `sub["source"]` says `nse_active_category`;
    on a gate failure or a fetch failure the Chittorgarh figure is left exactly as it was
    and the reason is recorded in `sub["nse_note"]`. **Which source was used is always on
    the row** — a silent switch between two sources is how a divergence stops being
    detectable.

    SME is skipped: NSE's book covers NSE-platform issues, and an SME issue on BSE SME
    returns 0.00, which the gate would reject anyway but at the cost of a request.
    """
    rows = [r for r in mv.get("closing_today", []) if r.get("segment") == "mainboard"]
    if not rows:
        return mv
    f = f or Fetcher()
    # market_view() rows carry a company NAME and a Chittorgarh id, never a symbol, so the
    # symbol comes from NSE's own calendar rather than from guessing at the name.
    cal = open_issues(f)
    for r in rows:
        sym = str(r.get("symbol") or "").strip()
        series = "EQ"
        if not sym:
            got = symbol_for(r.get("ipo"), cal)
            if not got:
                r.setdefault("sub", {})["nse_note"] = (
                    "NSE not used: no unique symbol for this name in "
                    "all-upcoming-issues")
                continue
            sym, series = got["symbol"], (got["series"] or "EQ")
            r["nse_symbol"] = sym
            r["nse_symbol_how"] = got["how"]
        got = fetch(sym, series, f, today)
        sub = r.setdefault("sub", {})
        if got["ok"]:
            sub.update({"ok": True, "total_x": got["total"], "qib_x": got["qib"],
                        "hni_x": got["hni"], "rii_x": got["rii"],
                        "source": "nse_active_category",
                        "reconciled": "single_source_unverified",
                        "nse_update_time": got["update_time"],
                        "nse_note": "NSE primary (H22)"})
        else:
            # H47 rule 5. A REFUSAL and a fault are different facts and are kept apart:
            # a 403, a 401, a 429 or a refused connection means NSE has answered, that
            # answer is final for this run, and the run must SAY the host blocked us.
            # A timeout or a parse failure is an ordinary fault. Neither is retried -
            # retrying a block is the circumvention H47 forbids.
            state = FO.classify(status=_status_in(got["note"]))
            sub["nse_note"] = f"NSE not used: {got['note']}"
            sub.setdefault("source", "chittorgarh")
            if state == "blocked":
                sub["nse_blocked"] = True
                have = sub.get("total_x") is not None
                mv.setdefault("failover_notes", []).append(
                    f"NSE blocked - failed over to Chittorgarh for {r.get('ipo')}"
                    if have else
                    f"NSE blocked and Chittorgarh has no figure for {r.get('ipo')}")
    return mv


def open_issues(f: Fetcher | None = None) -> list[dict]:
    """NSE's own calendar of open and forthcoming issues: name, symbol, series, dates.

    `api/all-upcoming-issues?category=ipo`. This is how a symbol is obtained for a live
    row: `chittorgarh_live.market_view()` returns a company NAME and a Chittorgarh id, and
    there is no symbol anywhere on it. Guessing one from the name is what silently returned
    a different company's subscription for `PARAMOUNT` during the Priority 2 probe.
    """
    f = f or Fetcher()
    if not f.warm():
        return []
    payload, note = f.get_json(HOME + "api/all-upcoming-issues?category=ipo")
    if not isinstance(payload, list):
        print(f"  all-upcoming-issues not usable: {note}")
        return []
    out = []
    for r in payload:
        out.append({"company": str(r.get("companyName") or ""),
                    "symbol": str(r.get("symbol") or "").strip(),
                    "series": str(r.get("series") or "").strip(),
                    "status": str(r.get("status") or "").strip(),
                    "opens": r.get("issueStartDate"), "closes": r.get("issueEndDate"),
                    "norm": _name_key(r.get("companyName"))})
    return out


def _name_key(x) -> str:
    """Lowercase alphanumerics, common suffixes stripped. Deterministic, no fuzziness."""
    t = "".join(ch for ch in str(x).lower() if ch.isalnum() or ch == " ")
    for suf in (" limited", " ltd", " private", " pvt"):
        while t.endswith(suf):
            t = t[: -len(suf)]
    return "".join(ch for ch in t if ch.isalnum())


def symbol_for(name: str, cal: list[dict]) -> dict:
    """`{symbol, series, how}` for a company name, or `{}`.

    An exact normalised-name match, or a UNIQUE prefix match. Never a best guess: two
    candidates return nothing, because returning the wrong company's subscription is worse
    than returning none.
    """
    n = _name_key(name)
    if len(n) < 5 or not cal:
        return {}
    exact = [c for c in cal if c["norm"] == n]
    if len(exact) == 1:
        return {"symbol": exact[0]["symbol"], "series": exact[0]["series"],
                "how": "name"}
    pref = [c for c in cal if c["norm"].startswith(n[:12]) or n.startswith(c["norm"][:12])]
    if len(pref) == 1:
        return {"symbol": pref[0]["symbol"], "series": pref[0]["series"],
                "how": "name_prefix"}
    return {}


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

    import inspect
    print("[1] ipo-detail is NEVER requested (H22)")
    body = "".join(inspect.getsource(x) for x in (Fetcher, fetch, parse, gate,
                                                  enrich_market_view))
    chk("no code path builds an ipo-detail URL", FORBIDDEN_ENDPOINT not in body)
    chk("the only endpoint is ipo-active-category",
        ENDPOINT.endswith("api/ipo-active-category"))
    chk("and the reason is recorded, with the measured size of the error",
        "9% to 57% lower" in (__doc__ or ""))

    print("\n[2] the header row of dataList is not read as data")
    payload = {"updateTime": "Updated as on 09-Oct-2026 15:00:00", "symbol": "ABC",
               "dataList": [
                   {"category": "Category", "noOfTotalMeant": "No. of times of total"},
                   {"category": "Qualified Institutional Buyers(QIBs)",
                    "noOfTotalMeant": "25.9"},
                   {"category": "Non Institutional Investors", "noOfTotalMeant": "4.2"},
                   {"category": "Retail Individual Investors(RIIs)",
                    "noOfTotalMeant": "6.1"},
                   {"category": "Total", "noOfTotalMeant": "11.75"}]}
    p = parse(payload)
    chk("total parses", p["total"] == 11.75, p)
    chk("qib parses", p["qib"] == 25.9, p)
    chk("hni parses from 'Non Institutional Investors'", p["hni"] == 4.2, p)
    chk("rii parses", p["rii"] == 6.1, p)
    chk("the header row set nothing to a sentence",
        all(isinstance(p[k], float) for k in ("total", "qib", "hni", "rii")))

    print("\n[3] the freshness gate")
    g, why = gate(p, "ABC", today="2026-10-09")
    chk("a same-day, positive, matching payload passes", g is True, why)
    g, why = gate(p, "ABC", today="2026-10-10")
    chk("a figure from another day is REFUSED, not used", g is False)
    chk("and the refusal says it is stale", "stale" in why, why)
    g, why = gate(p, "XYZ", today="2026-10-09")
    chk("a payload for a DIFFERENT symbol is refused", g is False)
    chk("and says which symbol it got", "ABC" in why, why)
    zero = dict(p, total=0.0)
    g, why = gate(zero, "ABC", today="2026-10-09")
    chk("Total 0.00 is refused - nothing published yet", g is False)
    undated = dict(p, update_time=None, raw_update_time="Updated as on null")
    g, why = gate(undated, "ABC", today="2026-10-09")
    chk("'Updated as on null' is refused, never read as now", g is False)
    chk("and says why an undated figure is unusable", "any day" in why, why)

    print("\n[4] updateTime parsing")
    chk("a real one parses",
        parse_update_time("Updated as on 25-Feb-2026 19:00:00")
        == pd.Timestamp("2026-02-25 19:00:00"))
    chk("'null' gives None", parse_update_time("Updated as on null") is None)
    chk("empty gives None", parse_update_time("") is None)
    chk("nonsense gives None", parse_update_time("whenever") is None)

    print("\n[5] single-origin: the flag is never dropped")
    src = inspect.getsource(enrich_market_view)
    chk("rows stay single_source_unverified on NSE too",
        '"single_source_unverified"' in src)
    chk("and which source was used is recorded on the row", "nse_note" in src)
    chk("SME is not queried against NSE's EQ book",
        'segment") == "mainboard"' in src)

    print("\n[6] a failure falls back rather than raising")
    bad = Fetcher.__init__ is not None
    # The docstring says "Never raises", so the docstring has to come out before the
    # body is searched for `raise` - otherwise the assertion matches its own subject.
    fsrc = re.sub(r'""".*?"""', "", inspect.getsource(fetch), flags=re.S)
    chk("fetch returns a dict with ok=False rather than raising",
        'res["ok"] = ok' in fsrc and "raise" not in fsrc, fsrc[-200:])
    chk("robots.txt is re-read every run (rule 3 / B2)",
        "robots.txt" in inspect.getsource(Fetcher.warm) and bad)

    print('\n[7] symbol resolution never guesses')
    cal = [{"company": "HD Fire Protect Limited", "symbol": "HDFIRE", "series": "EQ",
            "status": "Forthcoming", "opens": None, "closes": None,
            "norm": _name_key("HD Fire Protect Limited")},
           {"company": "Ravita Engineering Services Limited", "symbol": "RAVITA",
            "series": "SME", "status": "Forthcoming", "opens": None, "closes": None,
            "norm": _name_key("Ravita Engineering Services Limited")},
           {"company": "Ravita Holdings Limited", "symbol": "RAVHOLD",
            "series": "EQ", "status": "Forthcoming", "opens": None, "closes": None,
            "norm": _name_key("Ravita Holdings Limited")}]
    chk("an exact name resolves, and carries the series",
        symbol_for("HD Fire Protect", cal).get("symbol") == "HDFIRE"
        and symbol_for("HD Fire Protect Ltd", cal).get("series") == "EQ")
    chk("`Limited` and `Ltd` are the same company",
        _name_key("HD Fire Protect Limited") == _name_key("HD Fire Protect Ltd"))
    chk("TWO candidates return NOTHING rather than the first one",
        symbol_for("Ravita", cal) == {}, symbol_for("Ravita", cal))
    chk("an unknown name returns nothing", symbol_for("Nonesuch Industries", cal) == {})
    chk("a too-short name is refused outright", symbol_for("ABC", cal) == {})

    print("\n[FO] H47 rule 5: a simulated 403 fails over and says so")
    import nse_subscription as _M
    _saved_fetch, _saved_open, _saved_sym = _M.fetch, _M.open_issues, _M.symbol_for
    try:
        calls = []

        def _blocked(sym, series, f=None, today=None):
            calls.append(sym)
            return {"ok": False, "note": "HTTP 403", "total": None, "qib": None,
                    "hni": None, "rii": None, "update_time": None}

        _M.fetch = _blocked
        _M.open_issues = lambda f=None: []
        _M.symbol_for = lambda name, cal: {"symbol": "HDFIRE", "series": "EQ",
                                           "how": "test"}
        import copy as _cp
        # DEEP copies. dict(mv) is shallow, so the second case reused the first case's
        # `sub` dict and inherited its nse_blocked flag - the test failed on its own
        # fixture, not on the code.
        mv = {"closing_today": [{"ipo": "HD Fire Protect Limited",
                                 "segment": "mainboard",
                                 "sub": {"ok": True, "total_x": 85.12,
                                         "source": "chittorgarh"}}]}
        out = _M.enrich_market_view(_cp.deepcopy(mv), f=object())
        sub = out["closing_today"][0]["sub"]
        chk("NSE was called exactly ONCE - a block is never retried",
            len(calls) == 1, calls)
        chk("the row is marked blocked", sub.get("nse_blocked") is True)
        chk("the Chittorgarh figure SURVIVES untouched", sub["total_x"] == 85.12)
        chk("the source stays chittorgarh", sub["source"] == "chittorgarh")
        chk("the run reports the block and the failover",
            out["failover_notes"] == ["NSE blocked - failed over to Chittorgarh for "
                                      "HD Fire Protect Limited"],
            out.get("failover_notes"))

        calls.clear()

        def _timeout(sym, series, f=None, today=None):
            calls.append(sym)
            return {"ok": False, "note": "ReadTimeout after 30s", "total": None,
                    "qib": None, "hni": None, "rii": None, "update_time": None}

        _M.fetch = _timeout
        out2 = _M.enrich_market_view(_cp.deepcopy(mv), f=object())
        chk("a TIMEOUT is not reported as a block",
            "failover_notes" not in out2
            and out2["closing_today"][0]["sub"].get("nse_blocked") is None)
        chk("but it still falls back to Chittorgarh",
            out2["closing_today"][0]["sub"]["total_x"] == 85.12)
    finally:
        _M.fetch, _M.open_issues, _M.symbol_for = _saved_fetch, _saved_open, _saved_sym

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol")
    ap.add_argument("--series", default="EQ")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if not a.symbol:
        ap.error("--symbol is required")
    import json
    print(json.dumps(fetch(a.symbol, a.series), indent=2, default=str))

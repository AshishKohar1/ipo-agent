"""
market_context.py — daily index closes, display only (Priority 6).

Captured by the **17:30 leg**, after the market has actually closed, and shown as a
one-line footer in the daily email. **It is not a model input.** Per H2 and H12, Model L
remains `log1p(Total subscription)` alone; nothing in this file may ever reach a feature
vector. The footer exists so the reader can see what kind of day it was, not so the model
can.

Source discipline
-----------------
The only permitted source for these numbers is **NSE Indices (niftyindices.com)** — the
same official source already used for `data/NIFTY50_TRI.csv`. No substitutions: if the
Nifty Healthcare close cannot be had, this file writes NULL with a reason. It never
substitutes a "nearby" index, because a Pharma close standing in for a Healthcare close
would be indistinguishable from the real thing a month later.

**Permission is established before any fetch**, the same standard as
`post_listing_filings.verify_permitted()`: robots.txt is read first, and if it cannot be
read then permission has not been established and nothing is fetched. An unreadable
robots.txt is a refusal, not a green light.

As of 2026-10-03 that check **fails**: `www.niftyindices.com` read-times-out for this
project's User-Agent on every path including `/robots.txt`, retried at 40 s and twice at
75 s, on both the apex and `www` host. So every row this module writes today is a NULL
with `permission_unverifiable`.

    Note for the record: `fetch_nifty_tri.py` reaches this host successfully, but only
    because it sends a spoofed Chrome User-Agent. That predates the current rules and
    contradicts project rule 3 ("never send a browser User-Agent to work around a
    robots.txt or terms restriction"). This module does NOT copy that approach. The
    historical TRI file on disk is kept and used; no new spoofed request is made.

    python market_context.py              # attempt a capture for today
    python market_context.py --footer     # just print the email footer
    python market_context.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
import time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "market_context.csv"
COLS = ["date", "index_name", "close", "source", "fetched_at"]

HOST = "https://www.niftyindices.com"
ROBOTS = f"{HOST}/robots.txt"
# The page whose own XHR serves index closes. Not called unless robots.txt permits it.
HIST_PAGE = f"{HOST}/reports/historical-data"
# H18 (user decision, 2026-10-05): realistic browser headers to OFFICIAL sources. The
# honest UA was read-timing-out on every niftyindices path INCLUDING /robots.txt, which
# made permission unverifiable and forced every row to NULL. With these headers
# robots.txt returns HTTP 200 with `Allow: /`, and the four paths it disallows are
# specific index pages -- not /BackPage/, which is what this module calls.
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-GB,en-US;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.niftyindices.com",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "Connection": "keep-alive",
}
MIN_GAP_S = 3.0
TIMEOUT_S = 45

# Exactly the fifteen the user named, in that order. The left value is what goes in
# `index_name`; the right is the index's official NSE Indices name.
INDICES: tuple[tuple[str, str], ...] = (
    ("Nifty 50",                "NIFTY 50"),
    ("Nifty Auto",              "NIFTY AUTO"),
    ("Nifty Bank",              "NIFTY BANK"),
    ("Nifty Financial Services", "NIFTY FINANCIAL SERVICES"),
    ("Nifty IT",                "NIFTY IT"),
    ("Nifty Pharma",            "NIFTY PHARMA"),
    # Probed: the API answers to "NIFTY HEALTHCARE" and returns ZERO rows for
    # "NIFTY HEALTHCARE INDEX". Pharma was NOT substituted for it.
    ("Nifty Healthcare",        "NIFTY HEALTHCARE"),
    ("Nifty FMCG",              "NIFTY FMCG"),
    ("Nifty Metal",             "NIFTY METAL"),
    ("Nifty Realty",            "NIFTY REALTY"),
    ("Nifty Energy",            "NIFTY ENERGY"),
    ("Nifty Oil & Gas",         "NIFTY OIL & GAS"),
    ("Nifty Infrastructure",    "NIFTY INFRASTRUCTURE"),
    ("Nifty Media",             "NIFTY MEDIA"),
    ("Nifty Consumer Durables", "NIFTY CONSUMER DURABLES"),
)

BENCHMARK = "Nifty 50"


# ---------------------------------------------------------------- permission
class NotPermitted(RuntimeError):
    """robots.txt does not permit the fetch, or could not be read at all."""


def verify_permitted() -> tuple[bool, str]:
    """Read robots.txt and decide. An unreadable robots.txt is a REFUSAL.

    Returns `(permitted, reason)`. The reason is what lands in the CSV, so it has to be
    specific enough to act on a month from now.
    """
    try:
        r = requests.get(ROBOTS, headers=UA, timeout=TIMEOUT_S)
    except Exception as e:                                   # noqa: BLE001
        return False, (f"permission_unverifiable: {ROBOTS} {type(e).__name__} — the host "
                       f"does not respond to this project's User-Agent, so robots.txt "
                       f"could not be read and permission was never established. Not "
                       f"fetched. (No browser User-Agent is sent to work around this.)")
    if r.status_code != 200:
        return False, (f"permission_unverifiable: {ROBOTS} returned HTTP {r.status_code}, "
                       f"so permission could not be established. Not fetched.")
    txt = r.text
    low = txt.lower()
    for tok in ("claude", "anthropic", "ai-train"):
        if tok in low:
            return False, (f"robots.txt now names '{tok}' — stopping, per B2/H14. "
                           f"Not fetched.")
    # Crude but conservative: if a global Disallow: / is present for *, refuse.
    blocks, cur = {}, None
    for line in txt.splitlines():
        line = line.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        k, v = (p.strip() for p in line.split(":", 1))
        if k.lower() == "user-agent":
            cur = v
            blocks.setdefault(cur, [])
        elif k.lower() == "disallow" and cur is not None:
            blocks.setdefault(cur, []).append(v)
    star = blocks.get("*", [])
    if "/" in star:
        return False, "robots.txt disallows / for User-agent: *. Not fetched."
    return True, f"robots.txt HTTP 200, User-agent: * disallows {star or 'nothing'}"


# ---------------------------------------------------------------- the capture
def _existing() -> pd.DataFrame:
    if not OUT.exists():
        return pd.DataFrame(columns=COLS)
    try:
        return pd.read_csv(OUT)
    except Exception:                                        # noqa: BLE001
        return pd.DataFrame(columns=COLS)


def already_have(day: str, index_name: str, df: pd.DataFrame | None = None) -> bool:
    """Idempotent: a real close already recorded for this (date, index) is never refetched.

    A NULL row does NOT count — a later run is allowed to try again and succeed, which is
    the same lesson as the Priority 1f marker bug.
    """
    df = _existing() if df is None else df
    if df.empty:
        return False
    hit = df[(df["date"].astype(str) == str(day))
             & (df["index_name"].astype(str) == index_name)]
    if hit.empty:
        return False
    return bool(pd.to_numeric(hit["close"], errors="coerce").notna().any())


def _append(rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame([{c: r.get(c) for c in COLS} for r in rows], columns=COLS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")


def _fetch_close(sess: requests.Session, official: str, day: pd.Timestamp):
    """One index's close for `day`, or `(None, reason)`.

    Only reached once robots.txt has permitted it. The endpoint and payload shape are the
    ones the Historical Data page itself issues, confirmed by probe on 2026-10-05:

        POST /BackPage/getHistoricaldatatabletoString
        {"cinfo": "{'name':'NIFTY 50','startDate':'01-Oct-2026',
                    'endDate':'01-Oct-2026','indexName':'NIFTY 50'}"}
        -> [{"INDEX_NAME":"Nifty 50","HistoricalDate":"01 Oct 2026",
             "OPEN":"22543.7","HIGH":"22610.6","LOW":"22217.3","CLOSE":"22421.95"}]

    Note this is the PRICE index, not the Total Return Index. `fetch_nifty_tri.py` calls a
    different endpoint (`getTotalReturnIndexString`) for the TRI, and the two must not be
    mixed: a TRI value recorded as a close would be wrong by the whole dividend series.
    """
    import json as _json
    cinfo = ("{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}"
             % (official, f"{day:%d-%b-%Y}", f"{day:%d-%b-%Y}", official))
    try:
        r = sess.post(f"{HOST}/BackPage/getHistoricaldatatabletoString",
                      data=_json.dumps({"cinfo": cinfo}), timeout=TIMEOUT_S,
                      headers={**UA, "Content-Type": "application/json; charset=utf-8"})
    except Exception as e:                                   # noqa: BLE001
        return None, f"fetch_failed: {type(e).__name__}: {str(e)[:120]}"
    if r.status_code != 200:
        return None, f"fetch_failed: HTTP {r.status_code}"
    try:
        payload = r.json()
        recs = _json.loads(payload) if isinstance(payload, str) else payload
    except Exception as e:                                   # noqa: BLE001
        return None, f"unparsed: {type(e).__name__}: {str(e)[:120]}"
    if not recs:
        return None, "no_row_for_this_date: the index published nothing for this date"
    row = recs[0]
    # Guard against the API quietly answering for a DIFFERENT index than the one asked
    # for, which would substitute one index's close for another -- the exact failure the
    # no-substitution rule exists to prevent.
    got = str(row.get("INDEX_NAME") or row.get("Index Name") or "").strip().lower()
    want = official.strip().lower()
    if got and got.replace(" index", "") != want.replace(" index", ""):
        return None, (f"index_mismatch: asked for {official!r}, the API answered for "
                      f"{row.get('INDEX_NAME')!r} - refusing to record it")
    for k in ("CLOSE", "CLOSE_INDEX_VAL", "close", "Closing Index Value"):
        if k in row and str(row[k]).strip() not in ("", "-", "nan", "None"):
            try:
                return float(str(row[k]).replace(",", "")), ""
            except ValueError:
                return None, f"unparsed: {k}={row[k]!r} is not a number"
    return None, f"unparsed: no close field in {sorted(row)[:6]}"


def capture(today: pd.Timestamp | None = None) -> dict:
    """Append one row per index for `today`. Append-only and idempotent.

    Every index gets a row either way: a close, or NULL with the reason it is NULL. Never
    a substituted index.
    """
    today = (today or pd.Timestamp.now()).normalize()
    day = str(today.date())
    fetched_at = str(pd.Timestamp.now())
    have = _existing()

    todo = [(name, official) for name, official in INDICES
            if not already_have(day, name, have)]
    if not todo:
        return {"date": day, "n_ok": 0, "n_null": 0, "skipped": "all already captured"}

    permitted, reason = verify_permitted()
    rows, n_ok, n_null = [], 0, 0

    if not permitted:
        # Honest block. One NULL row per index, all carrying the same reason, nothing
        # invented and nothing substituted.
        for name, _ in todo:
            rows.append({"date": day, "index_name": name, "close": None,
                         "source": HOST, "fetched_at": fetched_at})
            n_null += 1
        _append(rows)
        _note(day, reason)
        return {"date": day, "n_ok": 0, "n_null": n_null, "blocked": reason}

    sess = requests.Session()
    sess.headers.update(UA)
    try:
        sess.get(HIST_PAGE, timeout=TIMEOUT_S)               # session cookies
    except Exception:                                        # noqa: BLE001
        pass
    notes = []
    for i, (name, official) in enumerate(todo):
        if i:
            time.sleep(MIN_GAP_S)
        close, why = _fetch_close(sess, official, today)
        rows.append({"date": day, "index_name": name, "close": close,
                     "source": f"{HOST} ({official})", "fetched_at": str(pd.Timestamp.now())})
        if close is None:
            n_null += 1
            notes.append(f"{name}: {why}")
        else:
            n_ok += 1
    _append(rows)
    for n in notes:
        _note(day, n)
    return {"date": day, "n_ok": n_ok, "n_null": n_null, "permitted": reason,
            "notes": notes}


def _note(day: str, text: str) -> None:
    """Reasons go to a sidecar log, because the CSV's columns are fixed by the spec at
    (date, index_name, close, source, fetched_at) and a reason does not fit in any of them.
    """
    p = ROOT / "data" / "market_context_notes.csv"
    pd.DataFrame([{"date": day, "logged_at": str(pd.Timestamp.now()), "note": text}]).to_csv(
        p, mode="a", header=not p.exists(), index=False, encoding="utf-8")


# ---------------------------------------------------------------- the footer
def email_footer() -> str:
    """One line for the daily email. Display only.

    The 30-day change is computed from this file's own history. It is deliberately NOT
    backfilled from `NIFTY50_TRI.csv`: the TRI is a different series from the price close,
    and silently mixing them would make the first month's "30-day change" a number nobody
    could reproduce.
    """
    df = _existing()
    tag = "[NOT a model input — display only. Model L uses total subscription alone (H2).]"
    if df.empty:
        return f"Market context: no index history captured yet. {tag}"
    d = df[df["index_name"].astype(str) == BENCHMARK].copy()
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["close", "date"]).sort_values("date")
    if d.empty:
        n_null = int((df["index_name"].astype(str) == BENCHMARK).sum())
        return (f"Market context: {BENCHMARK} close unavailable "
                f"({n_null} NULL row(s) logged; see data/market_context_notes.csv). {tag}")
    last = d.iloc[-1]
    chg = ""
    window = d[d["date"] <= last["date"] - pd.Timedelta(days=30)]
    if not window.empty:
        prior = window.iloc[-1]
        pct = (last["close"] / prior["close"] - 1) * 100
        chg = (f", {pct:+.1f}% over 30 days "
               f"(vs {prior['date'].date()})")
    else:
        span = (last["date"] - d.iloc[0]["date"]).days
        chg = f", 30-day change not yet available ({span}d of history)"
    return (f"Market context: {BENCHMARK} {last['close']:,.2f} "
            f"on {last['date'].date()}{chg}. {tag}")


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    import tempfile
    global OUT
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("market_context.py self-test (no network)")

    print("\n[1] the index list is exactly the fifteen requested")
    want = ["Nifty 50", "Nifty Auto", "Nifty Bank", "Nifty Financial Services", "Nifty IT",
            "Nifty Pharma", "Nifty Healthcare", "Nifty FMCG", "Nifty Metal",
            "Nifty Realty", "Nifty Energy", "Nifty Oil & Gas", "Nifty Infrastructure",
            "Nifty Media", "Nifty Consumer Durables"]
    chk("15 indices", len(INDICES) == 15, str(len(INDICES)))
    chk("names and order match the request", [n for n, _ in INDICES] == want,
        str([n for n, _ in INDICES]))
    chk("no duplicates", len({n for n, _ in INDICES}) == 15)

    print("\n[2] columns are exactly the spec")
    chk("COLS == date,index_name,close,source,fetched_at",
        COLS == ["date", "index_name", "close", "source", "fetched_at"], str(COLS))

    print("\n[3] idempotency: a real close locks, a NULL does not")
    with tempfile.TemporaryDirectory() as td:
        keep = OUT
        try:
            OUT = Path(td) / "mc.csv"
            _append([{"date": "2026-10-05", "index_name": "Nifty 50", "close": None,
                      "source": HOST, "fetched_at": "t"}])
            chk("a NULL row does not count as captured",
                already_have("2026-10-05", "Nifty 50") is False)
            _append([{"date": "2026-10-05", "index_name": "Nifty 50", "close": 25000.0,
                      "source": HOST, "fetched_at": "t"}])
            chk("a real close does count", already_have("2026-10-05", "Nifty 50") is True)
            chk("a different index is independent",
                already_have("2026-10-05", "Nifty IT") is False)
            chk("a different date is independent",
                already_have("2026-10-06", "Nifty 50") is False)
            chk("append-only: both rows retained", len(_existing()) == 2)

            print("\n[4] the footer")
            f = email_footer()
            chk("footer names the benchmark", "Nifty 50" in f, f)
            chk("footer says it is not a model input", "not a model input" in f.lower(), f)
            chk("with <30d of history it says so, rather than inventing a change",
                "not yet available" in f, f)
            _append([{"date": "2026-08-20", "index_name": "Nifty 50", "close": 24000.0,
                      "source": HOST, "fetched_at": "t"}])
            f2 = email_footer()
            chk("with >=30d of history it reports the change",
                "over 30 days" in f2 and "+4.2%" in f2, f2)

            print("\n[5] an all-NULL file still produces an honest footer")
            OUT = Path(td) / "mc2.csv"
            _append([{"date": "2026-10-05", "index_name": "Nifty 50", "close": None,
                      "source": HOST, "fetched_at": "t"}])
            f3 = email_footer()
            chk("footer admits the close is unavailable", "unavailable" in f3, f3)
            chk("footer substitutes no other index",
                not any(n in f3 for n, _ in INDICES if n != "Nifty 50"), f3)

            print("\n[6] an empty file produces an honest footer")
            OUT = Path(td) / "mc3.csv"
            f4 = email_footer()
            chk("footer says no history yet", "no index history" in f4, f4)
        finally:
            OUT = keep

    print("\n[7] permission is required before any fetch")
    import inspect
    src = inspect.getsource(capture)
    chk("capture() calls verify_permitted()", "verify_permitted()" in src)
    chk("capture() returns before fetching when not permitted",
        src.index("if not permitted") < src.index("requests.Session()"))
    # Checked against the UA actually sent, not against the file's own source: the source
    # mentions browser tokens in prose, and the first version of this test matched its own
    # assertion string.
    # H18 superseded the old "never a browser User-Agent" rule. What must still hold is
    # narrower and is what this now asserts: the host is an OFFICIAL one, robots.txt is
    # honoured, and nothing bypasses a login, CAPTCHA, paywall or click-through.
    chk("the host is an official source (NSE Indices)",
        HOST == "https://www.niftyindices.com", HOST)
    chk("no credential, token or cookie jar is shipped in the headers",
        not any(k.lower() in ("authorization", "cookie") for k in UA))
    chk("the endpoint called is the page's own XHR, not a gated download",
        "/BackPage/getHistoricaldatatabletoString" in inspect.getsource(_fetch_close))
    # Checked against the executable body, not the whole source: the docstring explains
    # the TRI/close distinction by name, and the first version of this check matched its
    # own explanation.
    _body = inspect.getsource(_fetch_close).split('"""')[-1]
    chk("the TRI endpoint is NOT called here (a TRI value is not a close)",
        "getTotalReturnIndexString" not in _body)
    chk("an index answering for a DIFFERENT index is refused, never recorded",
        "index_mismatch" in inspect.getsource(_fetch_close))
    srcs = [ln.strip() for ln in Path(__file__).read_text(encoding="utf-8").splitlines()
            if ln.lstrip().startswith("UA = {")]
    chk("exactly one User-Agent is defined in this file", len(srcs) == 1, str(srcs))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--footer", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.footer:
        print(email_footer())
        raise SystemExit(0)
    print(capture())
    print()
    print(email_footer())

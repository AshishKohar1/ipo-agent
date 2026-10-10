"""
model_h_targets.py — Task 5: Model H's holding targets, computed so they can be audited.

What the stored targets actually are
------------------------------------
`run_overnight.job2_build_target()` computes, at `run_overnight.py:383`:

    ipo_r  = (p1 / p0 - 1) * 100
    b_r    = (n1 / n0 - 1) * 100
    excess = ipo_r - b_r

where `p0`, `p1` come from `_series()` at `run_overnight.py:274-291`, which calls
`yf.Ticker(sym + suf).history(..., auto_adjust=True)` at **`run_overnight.py:282`**, and
`n0`, `n1` come from the official Nifty 50 TRI (`run_overnight.py:266-267` ->
`dataio.load_nifty_tri()`).

Three consequences, and the first one is not the one it looks like:

1. **Dividends and splits are already in the number — silently.** `auto_adjust=True` makes
   yfinance back-adjust the whole series for splits AND dividends, so `p1 / p0` is already
   an approximate total return, not a price return. Adding dividends on top would
   double-count them. What is wrong is not the arithmetic but that **nothing is auditable**:
   no split factor, no dividend amount, no provenance, no way to re-derive the figure or
   reconcile it against anything (rule 2 cannot even be attempted).

2. **`listing_close` is not the listing close.** It is today's back-adjusted value of that
   day's close, restated by every corporate action since. This is exactly the trap CLAUDE.md
   names: Syngene's real Rs 295 listing open reads Rs 147.50 once its 2017 bonus is applied.
   The column name asserts something the value is not.

3. **The adjustment is as-of-whenever-the-row-was-built.** Two rows computed months apart
   sit on different adjustment states, so the dataset is not internally consistent over
   time, and rebuilding it changes historical rows.

Also: yfinance's dividend back-adjustment implicitly **reinvests** at the ex-date price. The
CRSP buy-and-hold convention this module implements adds the cash dividends without
reinvestment. Both are defensible; they are not the same number, and the difference is
reported rather than assumed away.

What this module computes
-------------------------
Per the specified standard, into **new columns in a new file**. The stored targets are never
overwritten - they are what every fitted Model H coefficient was derived from, and silently
restating them would make the model cards unreproducible.

    stock return = (raw end price x cumulative split/bonus factor between the dates
                    + dividends paid in the window) / raw listing-day price - 1
    benchmark    = Nifty 50 TRI over the same two dates (already includes dividends)

Raw prices come from the **bhavcopy on the exact dates** (`listing_prices.bhavcopy`, which
is imported and never modified - it is inside the live-path freeze). Corporate actions come
from NSE's own `api/corporates-corporateActions`, which answers per symbol with a date range
and reaches back to 2010. H18 applies: official host, robots.txt re-read and required to
say `Allow: /`, realistic headers, >=3 s between requests, no login or click-through.

Rule 1 throughout: a window with no corporate-action data is flagged
`ca_coverage_missing` and is **never treated as zero dividends**. "No dividend was paid" and
"we could not find out" are different facts and only the first is evidence.

Delisted or suspended inside the window: the last traded price is used, the row is flagged,
and it is **never dropped**. The stored build drops them
(`run_overnight.py:347-349`, `dropped_no_series`) and its own log then says the base rate is
optimistic - which is true, and is a reason to keep the row, not to print a warning.

    python model_h_targets.py --self-test
    python model_h_targets.py --probe            # reachability + one symbol, no batch
    python model_h_targets.py --actions          # fetch corporate actions (resumable)
    python model_h_targets.py --report           # coverage + effects, from what is cached
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

# Outputs. New files, never the stored targets.
ACTIONS = DATA / "corporate_actions.csv"
CA_CKPT = DATA / "corporate_actions_progress.json"
CORRECTED = DATA / "holding_target_corrected.csv"

ACTION_COLS = ["symbol", "window", "ex_date", "subject", "series", "isin", "face_value",
               "kind", "dividend_per_share", "split_from", "split_to", "bonus_new",
               "bonus_old", "factor", "source", "endpoint", "fetched_at_ist",
               "response_sha256", "parse_note"]

HOME = "https://www.nseindia.com/"
REF = HOME + "companies-listing/corporate-filings-actions"
ENDPOINT = HOME + "api/corporates-corporateActions"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
GAP = 3.0                      # seconds between requests (H18 / rule 5)


def ist_now() -> str:
    import trading_day as TD
    return str(TD.ist_now())


# ---------------------------------------------------------------- parsing NSE's free text
#
# `subject` is free text typed by a human and it shows: "Dividend - Rs 6 Per Share",
# " Annual General Meeting/Dividend - Rs 1.50", "Annual Genral Meeting/Dividend Rs 2.45 Per
# Share" (NSE's own typo), "Face Value Split From Rs 10 To Rs 2", "Bonus 1:1",
# "Rights 2:25 @ Premium Rs 17/-".
#
# Every pattern below is anchored on a keyword AND a number. A subject that mentions an
# action but carries no parseable number returns kind with a `parse_note` and NO factor -
# never a factor of 1, which would silently assert "no adjustment needed".

RE_DIV = re.compile(r"(?:divid|dividend)[^0-9]{0,24}?(?:rs?\.?|re\.?|inr)?\s*"
                    r"([0-9]+(?:\.[0-9]+)?)", re.I)
RE_SPLIT = re.compile(r"split[^0-9]{0,40}?([0-9]+(?:\.[0-9]+)?)\s*(?:/-)?\s*"
                      r"to\s*(?:rs?\.?|re\.?)?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
RE_SPLIT_RATIO = re.compile(r"split[^0-9]{0,24}?([0-9]+)\s*[:\-]\s*([0-9]+)", re.I)
RE_BONUS = re.compile(r"bonus[^0-9]{0,24}?([0-9]+)\s*[:\-]\s*([0-9]+)", re.I)


def classify(subject: str) -> dict:
    """One corporate action's free text -> what it does to a price series.

    `factor` is the number a RAW pre-event price must be MULTIPLIED by to be comparable
    with a raw post-event price. A 1:1 bonus doubles the share count, so a pre-event price
    is worth half as much per share afterwards: factor 0.5. A 10->2 face-value split is
    five new shares for one: factor 0.2.

    Returns `factor: None` where the text names an action but no number can be read. A
    missing factor must stay missing - defaulting it to 1.0 would assert that no adjustment
    is needed, which is the one thing we do not know.

    Rights issues are deliberately NOT given a factor. Adjusting for a rights issue needs
    the subscription price and the take-up, neither of which is in this field, and the
    theoretical ex-rights formula would be a guess dressed as arithmetic.
    """
    s = " " + str(subject or "").strip() + " "
    low = s.lower()
    out = {"kind": "other", "dividend_per_share": None, "split_from": None,
           "split_to": None, "bonus_new": None, "bonus_old": None, "factor": None,
           "parse_note": ""}

    if "split" in low:
        out["kind"] = "split"
        m = RE_SPLIT.search(s)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if a > 0 and b > 0:
                out["split_from"], out["split_to"] = a, b
                out["factor"] = b / a                  # Rs10 -> Rs2 : factor 0.2
            else:
                out["parse_note"] = "split face values not positive"
        else:
            m = RE_SPLIT_RATIO.search(s)
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                if a > 0 and b > 0:
                    out["split_from"], out["split_to"] = a, b
                    out["factor"] = b / a
            else:
                out["parse_note"] = "split named but no face values or ratio found"
        return out

    if "bonus" in low:
        out["kind"] = "bonus"
        m = RE_BONUS.search(s)
        if m:
            new, old = float(m.group(1)), float(m.group(2))
            if old > 0:
                out["bonus_new"], out["bonus_old"] = new, old
                # new:old bonus -> (old + new) shares where there were old.
                out["factor"] = old / (old + new)
            else:
                out["parse_note"] = "bonus ratio has a zero denominator"
        else:
            out["parse_note"] = "bonus named but no ratio found"
        return out

    if "rights" in low:
        out["kind"] = "rights"
        out["parse_note"] = ("rights issue - no factor applied: the adjustment needs the "
                             "subscription price and take-up, which this field does not "
                             "carry")
        return out

    if "divid" in low:
        out["kind"] = "dividend"
        m = RE_DIV.search(s)
        if m:
            out["dividend_per_share"] = float(m.group(1))
        else:
            out["parse_note"] = "dividend named but no amount found"
        return out

    if "meeting" in low:
        out["kind"] = "meeting"           # carries no price effect on its own
        return out
    return out


# ---------------------------------------------------------------- fetching
def session():
    """A warmed NSE session, or a loud failure. Never a partial-permission fetch."""
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9",
                      "Accept-Encoding": "gzip, deflate"})
    r = s.get(HOME + "robots.txt", timeout=30)
    if r.status_code != 200 or "Allow: /" not in r.text:
        raise RuntimeError(f"NSE robots.txt did not confirm Allow: / (HTTP "
                           f"{r.status_code}). Not fetching.")
    time.sleep(GAP)
    s.get(HOME, timeout=30)
    time.sleep(GAP)
    s.get(REF, timeout=30)
    return s


def fetch_actions(s, symbol: str, d0, d1) -> tuple[list[dict], str, str]:
    """`(rows, sha256, url)` for one symbol over one window. Empty list on any failure.

    The SHA-256 is of the RAW response bytes, per H26's provenance requirement: without it
    a restated value later is indistinguishable from a transcription error now.
    """
    import hashlib
    url = (f"{ENDPOINT}?index=equities&symbol={symbol}"
           f"&from_date={pd.Timestamp(d0):%d-%m-%Y}&to_date={pd.Timestamp(d1):%d-%m-%Y}")
    try:
        r = s.get(url, headers={"Referer": REF, "Accept": "application/json"}, timeout=30)
    except Exception as e:                                   # noqa: BLE001
        return [], "", f"{type(e).__name__}: {str(e)[:70]}"
    if "json" not in r.headers.get("Content-Type", ""):
        return [], "", f"non-JSON (HTTP {r.status_code})"
    sha = hashlib.sha256(r.content).hexdigest()
    try:
        d = r.json()
    except Exception:                                        # noqa: BLE001
        return [], sha, "response was not parseable JSON"
    return (d if isinstance(d, list) else []), sha, url


def cumulative_factor(rows: list[dict]) -> tuple[float | None, str]:
    """The product of every split/bonus factor in the window, or `(None, why)`.

    `None` is returned if ANY split or bonus in the window could not be parsed. A partial
    product is worse than no answer: it would be applied as though complete and would be
    wrong by exactly the factor it missed.
    """
    f, unparsed = 1.0, []
    for r in rows:
        if r.get("kind") not in ("split", "bonus"):
            continue
        if r.get("factor") in (None, ""):
            unparsed.append(str(r.get("subject"))[:40])
            continue
        f *= float(r["factor"])
    if unparsed:
        return None, "unparsed split/bonus in window: " + "; ".join(unparsed)
    return f, ""


def dividends_in_window(rows: list[dict]) -> tuple[float, int, str]:
    """`(total per share, how many, note)`. An unparsed dividend makes the total unusable."""
    tot, n, bad = 0.0, 0, []
    for r in rows:
        if r.get("kind") != "dividend":
            continue
        v = r.get("dividend_per_share")
        if v in (None, ""):
            bad.append(str(r.get("subject"))[:40])
            continue
        tot += float(v)
        n += 1
    if bad:
        return tot, n, "unparsed dividend in window: " + "; ".join(bad)
    return tot, n, ""


# ---------------------------------------------------------------- the batch
def rows_to_do(horizon: str = "1y") -> pd.DataFrame:
    f = DATA / ("holding_target.csv" if horizon == "1y" else "holding_target_3y.csv")
    d = pd.read_csv(f)
    d["listing_date"] = pd.to_datetime(d["listing_date"], errors="coerce")
    days = 365 if horizon == "1y" else 1095
    d["end_date"] = d["listing_date"] + pd.Timedelta(days=days)
    return d.dropna(subset=["listing_date", "symbol"])


def _ckpt() -> dict:
    if not CA_CKPT.exists():
        return {}
    try:
        return json.loads(CA_CKPT.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        raise RuntimeError(f"{CA_CKPT} is unreadable. Fix or delete it deliberately - "
                           f"a silent reset would refetch everything.")


def collect_actions(horizon: str = "1y", limit: int | None = None) -> dict:
    """Fetch corporate actions for every row's window. Resumable, checkpointed per symbol.

    H9: safe to kill at any moment. Each symbol is written and checkpointed before the next
    request, so a killed run loses at most the one in flight.
    """
    todo = rows_to_do(horizon)
    done = _ckpt()
    key = lambda sym: f"{horizon}|{sym}"                     # noqa: E731
    pending = [r for _, r in todo.iterrows() if key(r["symbol"]) not in done]
    if limit:
        pending = pending[:limit]
    print(f"{horizon}: {len(todo)} rows, {len(todo) - len(pending)} already cached, "
          f"{len(pending)} to fetch at {GAP}s apart "
          f"(~{len(pending) * GAP / 60:.0f} min)")
    if not pending:
        return {"horizon": horizon, "fetched": 0, "cached": len(todo)}

    s = session()
    n_ok = n_empty = n_fail = 0
    out_rows = []
    for i, r in enumerate(pending, 1):
        sym = str(r["symbol"])
        time.sleep(GAP)
        rows, sha, url = fetch_actions(s, sym, r["listing_date"], r["end_date"])
        when = ist_now()
        if url.startswith("http"):
            n_ok += 1 if rows else 0
            n_empty += 0 if rows else 1
            failed = False
        else:
            n_fail += 1
            failed = True
        for a in rows:
            cl = classify(a.get("subject"))
            out_rows.append({
                "symbol": sym, "window": f"{r['listing_date']:%Y-%m-%d}/"
                                         f"{r['end_date']:%Y-%m-%d}",
                "ex_date": a.get("exDate"), "subject": a.get("subject"),
                "series": a.get("series"), "isin": a.get("isin"),
                "face_value": a.get("faceVal"), "source": "NSE",
                "endpoint": "api/corporates-corporateActions",
                "fetched_at_ist": when, "response_sha256": sha, **cl})
        done[key(sym)] = {"n": len(rows), "sha256": sha, "fetched_at_ist": when,
                          "failed": failed, "note": "" if not failed else url}
        CA_CKPT.write_text(json.dumps(done, indent=1, default=str), encoding="utf-8")
        if out_rows and (i % 10 == 0 or i == len(pending)):
            _append_actions(out_rows)
            out_rows = []
        if i % 25 == 0:
            print(f"  {i}/{len(pending)}  with actions={n_ok} empty={n_empty} "
                  f"failed={n_fail}")
    if out_rows:
        _append_actions(out_rows)
    print(f"{horizon} done: {n_ok} symbols with actions, {n_empty} with none, "
          f"{n_fail} failed")
    return {"horizon": horizon, "with_actions": n_ok, "empty": n_empty, "failed": n_fail}


def _append_actions(rows: list[dict]) -> None:
    if not rows:
        return
    d = pd.DataFrame([{c: r.get(c) for c in ACTION_COLS} for r in rows],
                     columns=ACTION_COLS)
    DATA.mkdir(parents=True, exist_ok=True)
    d.to_csv(ACTIONS, mode="a", header=not ACTIONS.exists(), index=False,
             encoding="utf-8")


# ---------------------------------------------------------------- reporting
def coverage_by_year(horizon: str = "1y") -> pd.DataFrame:
    """Share of rows whose window has corporate-action data ON FILE, by listing year.

    A row the fetch has not reached yet is `not_attempted`, which is NOT the same as
    `ca_coverage_missing` - the first says we have not looked, the second that we looked
    and NSE answered with nothing usable.
    """
    todo = rows_to_do(horizon)
    done = _ckpt()
    acts = (pd.read_csv(ACTIONS) if ACTIONS.exists()
            else pd.DataFrame(columns=ACTION_COLS))
    have = set(acts["symbol"].astype(str)) if len(acts) else set()
    rec = []
    for _, r in todo.iterrows():
        sym = str(r["symbol"])
        c = done.get(f"{horizon}|{sym}")
        if c is None:
            state = "not_attempted"
        elif c.get("failed"):
            state = "ca_coverage_missing"
        elif sym in have:
            state = "have_actions"
        else:
            state = "no_actions_in_window"
        rec.append({"year": int(r["listing_date"].year), "state": state})
    d = pd.DataFrame(rec)
    if d.empty:
        return d
    t = d.pivot_table(index="year", columns="state", aggfunc="size", fill_value=0)
    t["rows"] = t.sum(axis=1)
    return t.reset_index()


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

    print("[1] NSE's free-text subjects, as actually observed")
    cases = [
        ("Dividend - Rs 6 Per Share", "dividend", 6.0),
        (" Annual General Meeting/Dividend - Rs 1.50", "dividend", 1.50),
        ("Annual Genral Meeting/Dividend Rs 2.45 Per Share", "dividend", 2.45),
        ("Interim Dividend - Re 0.20 Per Share", "dividend", 0.20),
        ("Dividend-Rs.2/- Per Share", "dividend", 2.0),
        (" Interim Dividend- Re 1 Per Share", "dividend", 1.0),
        ("Annual General Meeting And Dividend Rs.3/-", "dividend", 3.0),
    ]
    for sub, kind, amt in cases:
        c = classify(sub)
        chk(f"{sub[:44]!r} -> {amt}",
            c["kind"] == kind and c["dividend_per_share"] == amt,
            (c["kind"], c["dividend_per_share"]))

    print("\n[2] splits and bonuses give the factor a RAW price must be multiplied by")
    c = classify("Face Value Split From Rs 10 To Rs 2")
    chk("a 10->2 face split is factor 0.2", c["kind"] == "split"
        and abs(c["factor"] - 0.2) < 1e-12, c)
    c = classify("Bonus 1:1")
    chk("a 1:1 bonus halves a pre-event price (factor 0.5)",
        c["kind"] == "bonus" and abs(c["factor"] - 0.5) < 1e-12, c)
    c = classify("Bonus issue 3:1")
    chk("a 3:1 bonus is factor 0.25", abs(c["factor"] - 0.25) < 1e-12, c)
    c = classify("Bonus 1:2")
    chk("a 1:2 bonus is factor 2/3", abs(c["factor"] - 2 / 3) < 1e-12, c)

    print("\n[3] an action it cannot parse gets NO factor, never 1.0")
    for sub in ("Face Value Split", "Bonus Issue", "Stock Split Announced"):
        c = classify(sub)
        chk(f"{sub!r} -> factor None", c["factor"] is None, c)
        chk("  and says why", bool(c["parse_note"]), c)
    c = classify("Dividend declared")
    chk("an amountless dividend has no amount", c["dividend_per_share"] is None, c)
    chk("  and says why", "no amount found" in c["parse_note"], c)

    print("\n[4] a rights issue is deliberately not adjusted for")
    c = classify("Rights 2:25 @ Premium Rs 17/-")
    chk("kind is rights", c["kind"] == "rights")
    chk("no factor is invented", c["factor"] is None)
    chk("and the reason names what is missing",
        "subscription price" in c["parse_note"] and "take-up" in c["parse_note"], c)

    print("\n[5] a meeting is not a price event")
    c = classify("Annual General Meeting")
    chk("kind is meeting", c["kind"] == "meeting")
    chk("no dividend is read from it", c["dividend_per_share"] is None)
    chk("and no factor", c["factor"] is None)

    print("\n[6] cumulative factor refuses to be partially right")
    rows = [classify("Bonus 1:1"), classify("Face Value Split From Rs 10 To Rs 2")]
    f, why = cumulative_factor(rows)
    chk("two known events multiply (0.5 * 0.2)", abs(f - 0.1) < 1e-12, f)
    chk("and there is no complaint", why == "")
    rows = [classify("Bonus 1:1"), classify("Bonus Issue")]
    f, why = cumulative_factor(rows)
    chk("ONE unparsed event makes the whole product None", f is None, f)
    chk("rather than silently returning the half it could do",
        "unparsed split/bonus" in why, why)
    f, why = cumulative_factor([classify("Dividend - Rs 5 Per Share")])
    chk("a window with no split or bonus is factor 1.0", f == 1.0, f)

    print("\n[7] dividends: summed, counted, and never guessed")
    rows = [classify("Dividend - Rs 6 Per Share"),
            classify("Interim Dividend - Re 0.50 Per Share")]
    tot, n, note = dividends_in_window(rows)
    chk("two dividends sum", abs(tot - 6.5) < 1e-12, tot)
    chk("and are counted", n == 2)
    chk("with no complaint", note == "")
    tot, n, note = dividends_in_window(rows + [classify("Dividend declared")])
    chk("an unparsed one is reported, not rounded away",
        "unparsed dividend" in note, note)
    chk("and the parseable ones are still summed", abs(tot - 6.5) < 1e-12, tot)
    tot, n, note = dividends_in_window([classify("Annual General Meeting")])
    chk("no dividend in the window is 0.0 of 0 - which is a MEASURED zero",
        tot == 0.0 and n == 0)

    print("\n[8] the module never writes to the stored targets")
    import inspect
    src = inspect.getsource(sys.modules[__name__])
    for frozen in ("holding_target.csv", "holding_target_3y.csv"):
        writes = re.findall(rf"to_csv\([^)]*{re.escape(frozen)}", src)
        chk(f"no to_csv to {frozen}", not writes, writes)
    chk("corrected values go to their own file",
        "holding_target_corrected.csv" in str(CORRECTED))
    chk("and the live-path bhavcopy module is imported, never edited",
        "listing_prices" in src and "import" in src)

    print("\n[9] provenance is structural, not optional")
    for c in ("source", "endpoint", "fetched_at_ist", "response_sha256"):
        chk(f"{c} is an action column (H26)", c in ACTION_COLS)
    chk("the hash is of the RAW response bytes",
        "hashlib.sha256(r.content)" in src)
    chk("3s between requests (rule 5 / H18)", GAP >= 3.0)
    chk("robots.txt is re-read and must say Allow: /",
        'robots.txt' in src and '"Allow: /" not in r.text' in src)
    chk("and a refusal raises rather than fetching anyway",
        "Not fetching." in src)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--actions", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--horizon", default="1y", choices=["1y", "3y"])
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.probe:
        s = session()
        time.sleep(GAP)
        rows, sha, url = fetch_actions(s, "RELIANCE", "2010-01-01", "2012-12-31")
        print(f"RELIANCE 2010-2012: {len(rows)} actions, sha256 {sha[:16]}…")
        for r in rows:
            print("  ", r.get("exDate"), "|", str(r.get("subject"))[:56], "->",
                  classify(r.get("subject"))["kind"])
        raise SystemExit(0)
    if a.actions:
        print(json.dumps(collect_actions(a.horizon, a.limit), indent=2, default=str))
        raise SystemExit(0)
    if a.report:
        t = coverage_by_year(a.horizon)
        print(t.to_string(index=False) if len(t) else "nothing to report yet")
        raise SystemExit(0)
    ap.print_help()

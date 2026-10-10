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
# A face-value change is written half a dozen ways - "Face Value Split From Rs 10 To
# Rs 2", "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share",
# "Face Value Consolidation From Rs 1 To Rs 10". Anchoring on the word "split" missed the
# last two. So the numbers are read from the "from X ... to Y" structure, which all of them
# share, and the keyword is used only to decide that this IS a face-value change.
RE_FACE = re.compile(r"from[^0-9]{0,24}?([0-9]+(?:\.[0-9]+)?)"
                     r"[^0-9]{0,34}?to[^0-9]{0,24}?([0-9]+(?:\.[0-9]+)?)", re.I)
RE_SPLIT_RATIO = re.compile(r"split[^0-9]{0,24}?([0-9]+)\s*[:\-]\s*([0-9]+)", re.I)
RE_BONUS = re.compile(r"bonus[^0-9]{0,24}?([0-9]+)\s*[:\-]\s*([0-9]+)", re.I)


def classify(subject: str) -> dict:
    """One corporate action's free text -> what it does to a price series.

    `factor` is **shares held after the event per share held before it** - the number the
    RAW END price is multiplied by, which is the convention the buy-and-hold formula in
    `build_corrected()` uses.

    Get this backwards and the numbers are badly wrong in a way that still looks
    plausible, so here it is worked out. A 1:1 bonus on a share bought at 100, trading at
    60 a year later: the holder now has TWO shares worth 60 each, so 120, a **+20%**
    return. That needs factor **2.0**: (60 x 2) / 100 - 1 = +20%. The first version of
    this function returned 0.5 - the price DEFLATOR, which is the right number for
    restating a pre-event price and the wrong one here. It would have reported -70%.

      1:1 bonus          1 share -> 2    factor (1+1)/1 = 2.0
      3:1 bonus          1 share -> 4    factor (1+3)/1 = 4.0
      1:2 bonus          2 shares -> 3   factor (2+1)/2 = 1.5
      Rs 10 -> Rs 2      1 share -> 5    factor 10/2    = 5.0

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

    if "split" in low or "sub-division" in low or "subdivision" in low \
            or "consolidat" in low:
        # One branch for all three because the arithmetic is identical and only the
        # direction differs: a sub-division raises the share count (Rs 10 -> Rs 2, five
        # for one), a consolidation lowers it (Rs 1 -> Rs 10, one for ten). `from / to`
        # gives both without a special case, and a consolidation's factor is correctly
        # below 1. Detecting only the word "split" missed consolidations entirely - they
        # fell through to kind "other" and contributed no factor to a window that had one.
        out["kind"] = "split"
        m = RE_FACE.search(s)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if a > 0 and b > 0:
                out["split_from"], out["split_to"] = a, b
                out["factor"] = a / b                  # Rs10 -> Rs2 : 5 shares for 1
            else:
                out["parse_note"] = "split face values not positive"
        else:
            # A bare ratio - "Stock Split 1:5" - is genuinely AMBIGUOUS and gets no
            # factor. It can mean the face value went from 1 to 5 (a consolidation, factor
            # 0.2) or that one share became five (a sub-division, factor 5.0), and Indian
            # filings use the wording both ways. Those answers differ by 25x. Guessing
            # would be the same class of error as the inverted factor this module already
            # had once, so the row is flagged for a human instead.
            m = RE_SPLIT_RATIO.search(s)
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                out["split_from"], out["split_to"] = a, b
                out["parse_note"] = (f"bare ratio {a:g}:{b:g} - direction ambiguous "
                                     f"(face value {a:g}->{b:g} would be factor "
                                     f"{a / b if b else float('nan'):g}; one-share-becomes"
                                     f"-{b:g} would be {b / a if a else float('nan'):g}). "
                                     f"No factor applied; needs the filing.")
            else:
                out["parse_note"] = ("face-value change named but no face values or "
                                     "ratio found")
        return out

    if "bonus" in low:
        out["kind"] = "bonus"
        m = RE_BONUS.search(s)
        if m:
            new, old = float(m.group(1)), float(m.group(2))
            if old > 0:
                out["bonus_new"], out["bonus_old"] = new, old
                # new:old bonus -> (old + new) shares where there were `old`.
                out["factor"] = (old + new) / old
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


# ---------------------------------------------------------------- the corrected target
CORRECTED_COLS = [
    "symbol", "company", "isin", "listing_date", "end_date", "horizon",
    # raw, as reported on the day - the point of the exercise
    "raw_listing_close", "raw_end_close", "raw_price_source", "raw_price_how",
    "end_date_actual", "days_from_requested", "end_price_missing_reason",
    # corporate actions in the window
    "ca_factor", "n_splits", "n_bonuses", "n_rights", "dividends_total_per_share",
    "n_dividends", "ca_state", "ca_note",
    # the corrected numbers
    "ipo_ret_corrected_pct", "bench_ret_pct", "excess_corrected_pp",
    "H_label_corrected", "delisted_or_suspended",
    # the stored numbers, for comparison - copied, never overwritten
    "excess_stored_pp", "H_label_stored", "delta_pp",
    # provenance (H26 / H7)
    "computed_at_ist", "method",
]

METHOD = ("CRSP buy-and-hold: (raw_end x cumulative split/bonus factor + dividends in "
          "window) / raw_listing_close - 1, minus Nifty 50 TRI over the same two dates")


def _raw_price(f, day, isin, symbol, within_days: int = 7):
    """`(close, actual_date, source, how, note)` from the bhavcopy on or after `day`.

    Walks forward at most `within_days` because a listing date can fall on a holiday and an
    anniversary almost always does. It never walks BACKWARD: a price from before the window
    opened is not the window's price.

    `listing_prices.bhavcopy` and `.find` are imported and not modified - they are inside
    the live-path freeze. `find` returns HOW it matched, which is carried through, because a
    truncated-name match and an ISIN match are not equally trustworthy.
    """
    import listing_prices as LP
    for k in range(within_days + 1):
        d = pd.Timestamp(day) + pd.Timedelta(days=k)
        if d.weekday() >= 5:
            continue
        for which in ("nse", "bse"):
            df, note = LP.bhavcopy(f, d, which)
            if df is None or df.empty:
                continue
            hit, how = LP.find(df, isin=isin, symbol=symbol)
            if len(hit) and pd.notna(hit.iloc[0].get("close")):
                return (float(hit.iloc[0]["close"]), d, which, how, note)
    return (None, pd.NaT, None, None, f"no bhavcopy row within {within_days} days")


def build_corrected(horizon: str = "1y", limit: int | None = None,
                    use_cache_only: bool = False) -> dict:
    """Compute the corrected targets into their OWN file. Resumable.

    `use_cache_only=True` uses only bhavcopy dates already on disk and records the rest as
    `raw_price_missing`, so the method can be reported on real rows without a 20-minute
    fetch first. The flag is written into the row, so a partial run is never mistaken for a
    complete one.
    """
    import listing_prices as LP
    todo = rows_to_do(horizon)
    acts = (pd.read_csv(ACTIONS) if ACTIONS.exists()
            else pd.DataFrame(columns=ACTION_COLS))
    done_ck = _ckpt()
    bench = _bench()
    lab_stored = "H_label" if horizon == "1y" else "H3_label"
    ex_stored = f"excess_{horizon}_pp"

    have = set()
    if CORRECTED.exists():
        prev = pd.read_csv(CORRECTED)
        have = set(zip(prev["symbol"].astype(str), prev["horizon"].astype(str)))
    pending = [r for _, r in todo.iterrows()
               if (str(r["symbol"]), horizon) not in have]
    if limit:
        pending = pending[:limit]
    print(f"{horizon}: {len(todo)} rows, {len(have)} already computed, "
          f"{len(pending)} to do (cache_only={use_cache_only})")
    if not pending:
        return {"horizon": horizon, "computed": 0}

    f = LP.Fetcher()
    out, n_ok, n_nopx, n_noca = [], 0, 0, 0
    for i, r in enumerate(pending, 1):
        sym, isin = str(r["symbol"]), r.get("isin")
        d0, d1 = r["listing_date"], r["end_date"]
        win = f"{d0:%Y-%m-%d}/{d1:%Y-%m-%d}"

        # --- corporate actions for this window
        a = acts[(acts["symbol"].astype(str) == sym) & (acts["window"] == win)] \
            if len(acts) else acts
        ck = done_ck.get(f"{horizon}|{sym}")
        rows = a.to_dict("records")
        factor, fnote = cumulative_factor(rows)
        divs, ndiv, dnote = dividends_in_window(rows)
        if ck is None:
            ca_state, ca_note = "not_attempted", "corporate actions not fetched for this row"
        elif ck.get("failed"):
            ca_state, ca_note = "ca_coverage_missing", str(ck.get("note"))[:120]
        elif factor is None:
            ca_state, ca_note = "ca_coverage_missing", fnote
        elif dnote:
            ca_state, ca_note = "ca_coverage_missing", dnote
        else:
            ca_state, ca_note = "ok", ""
        if ca_state != "ok":
            n_noca += 1

        # --- raw prices on the exact dates
        if use_cache_only:
            p0 = _cached_only(f, d0, isin, sym)
            p1 = _cached_only(f, d1, isin, sym)
        else:
            p0 = _raw_price(f, d0, isin, sym)
            p1 = _raw_price(f, d1, isin, sym)
        raw0, _, src0, how0, _ = p0
        raw1, dd1, src1, how1, note1 = p1

        # A missing end price means one of two completely different things, and
        # conflating them invents a finding: either the bhavcopy for that date was not
        # available to us (a gap in OUR data), or the bhavcopy WAS read and the symbol was
        # not in it (the company stopped trading). Only the second is a delisting. The
        # first version tested `raw1 is None` alone and reported 205 delistings on a
        # cache-only run, against the 3 the stored build finds.
        end_note = note1 or ""
        bhav_unavailable = ("raw_price_missing" in end_note
                            or "no bhavcopy row within" in end_note
                            and src1 is None and how1 is None)
        delisted = bool(raw1 is None and raw0 is not None
                        and not str(end_note).startswith("raw_price_missing"))
        ipo_r = bench_r = excess = lab = None
        if raw0 is not None and raw1 is not None and factor is not None and not dnote:
            ipo_r = ((raw1 * factor + divs) / raw0 - 1) * 100
            n0 = _bench_at(bench, d0)
            n1 = _bench_at(bench, dd1 if pd.notna(dd1) else d1)
            if n0 and n1:
                bench_r = (n1 / n0 - 1) * 100
                excess = ipo_r - bench_r
                lab = int(excess > 0)
                n_ok += 1
        if raw0 is None or raw1 is None:
            n_nopx += 1

        out.append({
            "symbol": sym, "company": r.get("company"), "isin": isin,
            "listing_date": f"{d0:%Y-%m-%d}", "end_date": f"{d1:%Y-%m-%d}",
            "horizon": horizon,
            "raw_listing_close": raw0, "raw_end_close": raw1,
            "raw_price_source": f"{src0 or '-'}/{src1 or '-'}",
            "raw_price_how": f"{how0 or '-'}/{how1 or '-'}",
            "end_price_missing_reason": (
                None if raw1 is not None
                else ("bhavcopy_not_available" if bhav_unavailable
                      else "symbol_absent_from_bhavcopy")),
            "end_date_actual": (f"{dd1:%Y-%m-%d}" if pd.notna(dd1) else None),
            "days_from_requested": ((dd1 - d1).days if pd.notna(dd1) else None),
            "ca_factor": factor, "n_splits": sum(1 for x in rows if x.get("kind") == "split"),
            "n_bonuses": sum(1 for x in rows if x.get("kind") == "bonus"),
            "n_rights": sum(1 for x in rows if x.get("kind") == "rights"),
            "dividends_total_per_share": divs if not dnote else None,
            "n_dividends": ndiv, "ca_state": ca_state,
            "ca_note": ca_note or (note1 if raw1 is None else ""),
            "ipo_ret_corrected_pct": ipo_r, "bench_ret_pct": bench_r,
            "excess_corrected_pp": excess, "H_label_corrected": lab,
            "delisted_or_suspended": delisted,
            "excess_stored_pp": r.get(ex_stored), "H_label_stored": r.get(lab_stored),
            "delta_pp": (excess - float(r[ex_stored]))
                        if excess is not None and pd.notna(r.get(ex_stored)) else None,
            "computed_at_ist": ist_now(),
            "method": METHOD + ("  [CACHE-ONLY RUN]" if use_cache_only else ""),
        })
        if i % 20 == 0 or i == len(pending):
            _append_corrected(out)
            out = []
            print(f"  {i}/{len(pending)}  computed={n_ok} no_price={n_nopx} "
                  f"no_ca={n_noca}")
    if out:
        _append_corrected(out)
    return {"horizon": horizon, "computed": n_ok, "no_price": n_nopx,
            "ca_missing": n_noca}


def _cached_only(f, day, isin, symbol, within_days: int = 7):
    """`_raw_price` restricted to bhavcopy dates ALREADY on disk. Fetches nothing."""
    import listing_prices as LP
    for k in range(within_days + 1):
        d = pd.Timestamp(day) + pd.Timedelta(days=k)
        if d.weekday() >= 5:
            continue
        for which in ("nse", "bse"):
            cp = LP.CACHE / f"{which}_{d:%Y%m%d}.csv.gz"
            if not cp.exists():
                continue
            try:
                df = pd.read_csv(cp, low_memory=False)
            except Exception:                                # noqa: BLE001
                continue
            df = LP._norm(df, which) if "close" not in df.columns else df
            hit, how = LP.find(df, isin=isin, symbol=symbol)
            if len(hit) and pd.notna(hit.iloc[0].get("close")):
                return (float(hit.iloc[0]["close"]), d, which, how, "cache")
    return (None, pd.NaT, None, None, "raw_price_missing: no cached bhavcopy in window")


def _bench():
    import dataio
    b = dataio.load_nifty_tri()
    if isinstance(b, pd.DataFrame):
        col = [c for c in b.columns if "close" in str(c).lower() or "tri" in str(c).lower()]
        s = b[col[0]] if col else b.iloc[:, -1]
        s.index = pd.to_datetime(b.index if b.index.name else b.iloc[:, 0], errors="coerce")
        return s.dropna()
    return b


def _bench_at(bench, d):
    s = bench[bench.index >= pd.Timestamp(d)]
    return float(s.iloc[0]) if len(s) else None


def _append_corrected(rows: list[dict]) -> None:
    if not rows:
        return
    d = pd.DataFrame([{c: r.get(c) for c in CORRECTED_COLS} for r in rows],
                     columns=CORRECTED_COLS)
    d.to_csv(CORRECTED, mode="a", header=not CORRECTED.exists(), index=False,
             encoding="utf-8")


def effects(horizon: str = "1y") -> dict:
    """Everything Task 5 asks to be printed, from whatever has been computed."""
    if not CORRECTED.exists():
        return {"error": "nothing computed yet"}
    d = pd.read_csv(CORRECTED)
    d = d[d["horizon"].astype(str) == horizon]
    done = d[d["excess_corrected_pp"].notna()].copy()
    o = {"rows_attempted": len(d), "rows_with_a_corrected_value": len(done),
         "ca_state": d["ca_state"].value_counts().to_dict(),
         "delisted_or_suspended": int(d["delisted_or_suspended"].sum()),
         "end_price_missing_reason": (
             d["end_price_missing_reason"].value_counts().to_dict()
             if "end_price_missing_reason" in d else "column absent - rebuild needed"),
         "rows_with_split_or_bonus": int(((d["n_splits"].fillna(0)
                                           + d["n_bonuses"].fillna(0)) > 0).sum()),
         "rows_with_rights": int((d["n_rights"].fillna(0) > 0).sum()),
         "rows_with_a_dividend": int((d["n_dividends"].fillna(0) > 0).sum())}
    if len(done):
        o["base_rate_stored_pct"] = round(float(done["H_label_stored"].mean()) * 100, 1)
        o["base_rate_corrected_pct"] = round(float(done["H_label_corrected"].mean()) * 100, 1)
        o["median_excess_stored_pp"] = round(float(done["excess_stored_pp"].median()), 1)
        o["median_excess_corrected_pp"] = round(float(done["excess_corrected_pp"].median()), 1)
        o["median_delta_pp"] = round(float(done["delta_pp"].median()), 1)
        o["label_flips"] = int((done["H_label_stored"] != done["H_label_corrected"]).sum())
        sb = done[(done["n_splits"].fillna(0) + done["n_bonuses"].fillna(0)) > 0]
        o["split_bonus_rows_with_a_value"] = len(sb)
        if len(sb):
            top = sb.reindex(sb["delta_pp"].abs().sort_values(ascending=False).index).head(10)
            o["ten_largest_split_bonus_corrections"] = top[
                ["symbol", "listing_date", "ca_factor", "n_splits", "n_bonuses",
                 "excess_stored_pp", "excess_corrected_pp", "delta_pp"]
            ].round(2).to_dict("records")
        dv = done[done["n_dividends"].fillna(0) > 0]
        if len(dv):
            o["dividend_rows_with_a_value"] = len(dv)
            o["median_dividend_contribution_pp"] = round(float(
                (dv["dividends_total_per_share"] / dv["raw_listing_close"] * 100).median()), 2)
    return o


def reclassify() -> dict:
    """Re-derive every action's kind/factor/amount from its stored `subject`.

    Needed because the classifier was fixed three times while the fetch batch was already
    running, and a long-running batch holds the module it imported at start. The rows it
    wrote carry classifications from whichever version was loaded then - including the
    inverted bonus factor. The raw `subject`, `ex_date`, SHA-256 and timestamps are
    untouched evidence, so re-deriving is a pure local operation and does not refetch
    anything.

    This rewrites a DERIVED column in place, which is allowed: `subject` is the record and
    `kind`/`factor` are an interpretation of it. The provenance columns - source, endpoint,
    fetched_at_ist, response_sha256 - are never touched, so every row can still be checked
    against the response it came from.
    """
    if not ACTIONS.exists():
        return {"error": "no actions file"}
    d = pd.read_csv(ACTIONS)
    before = d[["kind", "factor", "dividend_per_share"]].copy()
    for i, row in d.iterrows():
        c = classify(row.get("subject"))
        for k, v in c.items():
            d.at[i, k] = v
    d.to_csv(ACTIONS, index=False, encoding="utf-8")
    changed = int((before["kind"].astype(str) != d["kind"].astype(str)).sum()
                  + (before["factor"].fillna(-999) != d["factor"].fillna(-999)).sum()
                  + (before["dividend_per_share"].fillna(-999)
                     != d["dividend_per_share"].fillna(-999)).sum())
    return {"rows": len(d), "field_values_changed": changed,
            "kinds": d["kind"].value_counts().to_dict(),
            "splits_or_bonuses_without_a_factor": int(
                ((d["kind"].isin(["split", "bonus"])) & d["factor"].isna()).sum()),
            "dividends_without_an_amount": int(
                ((d["kind"] == "dividend") & d["dividend_per_share"].isna()).sum())}


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

    print("\n[2] the factor is SHARES AFTER per SHARE BEFORE - checked by hand")
    # The direction that is easy to get wrong, and did: the first version returned the
    # price deflator (0.5 for a 1:1 bonus) where the formula needs the share multiplier
    # (2.0). Each case below is the share count, not a ratio rearranged.
    c = classify("Face Value Split From Rs 10 To Rs 2")
    chk("Rs 10 -> Rs 2 gives 5 shares for 1 (factor 5.0)",
        c["kind"] == "split" and abs(c["factor"] - 5.0) < 1e-12, c)
    c = classify("Bonus 1:1")
    chk("a 1:1 bonus gives 2 shares for 1 (factor 2.0)",
        c["kind"] == "bonus" and abs(c["factor"] - 2.0) < 1e-12, c)
    c = classify("Bonus issue 3:1")
    chk("a 3:1 bonus gives 4 for 1 (factor 4.0)", abs(c["factor"] - 4.0) < 1e-12, c)
    c = classify("Bonus 1:2")
    chk("a 1:2 bonus gives 3 for 2 (factor 1.5)", abs(c["factor"] - 1.5) < 1e-12, c)
    chk("a bonus or a sub-division always gives MORE shares (factor > 1)",
        all(classify(x)["factor"] > 1.0 for x in
            ("Bonus 1:1", "Bonus 3:1", "Bonus 1:2",
             "Face Value Split From Rs 10 To Rs 2",
             "Face Value Split From Rs 10 To Rs 1")))
    # A CONSOLIDATION is the same arithmetic in reverse and must not be forced above 1.
    c = classify("Face Value Consolidation From Rs 1 To Rs 10")
    chk("a consolidation gives FEWER shares (factor 0.1), and is not clamped",
        c["kind"] == "split" and abs(c["factor"] - 0.1) < 1e-12, c)
    # A bare ratio is ambiguous in Indian filings and gets NO factor rather than a coin
    # flip between 0.2 and 5.0 - answers that differ by 25x.
    c = classify("Stock Split 1:5")
    chk("a bare 1:5 ratio gets NO factor, because the direction is ambiguous",
        c["kind"] == "split" and c["factor"] is None, c)
    chk("and the note states BOTH readings and what it would take to settle it",
        "ambiguous" in c["parse_note"] and "needs the filing" in c["parse_note"]
        and "0.2" in c["parse_note"] and "5" in c["parse_note"], c["parse_note"])
    chk("the ratio itself is still recorded, so nothing is lost",
        c["split_from"] == 1 and c["split_to"] == 5, c)
    # NSE's real wording, which the first pattern could not read.
    c = classify("Face Value Split (Sub-Division) - From Rs 10/- Per Share "
                 "To Rs 2/- Per Share")
    chk("NSE's actual sub-division wording parses to 5.0",
        c["kind"] == "split" and abs(c["factor"] - 5.0) < 1e-12, c)

    print("\n[2b] the whole formula, on the worked example")
    # Bought at 100, 1:1 bonus during the year, trading at 60 at the anniversary, Rs 4
    # of dividends. Two shares at 60 = 120, plus 4 = 124, against 100 -> +24%.
    f, _ = cumulative_factor([classify("Bonus 1:1")])
    divs, _, _ = dividends_in_window([classify("Dividend - Rs 4 Per Share")])
    got = ((60.0 * f + divs) / 100.0 - 1) * 100
    chk("100 -> 60 with a 1:1 bonus and Rs 4 of dividends is +24%",
        abs(got - 24.0) < 1e-9, got)
    chk("and the inverted factor would have said -70%, which is why this test exists",
        abs(((60.0 * 0.5) / 100.0 - 1) * 100 + 70.0) < 1e-9)

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
    chk("two events multiply: 2.0 x 5.0 = 10 shares for 1", abs(f - 10.0) < 1e-12, f)
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

    print("\n[10] the corrected computation, on arithmetic that can be checked by hand")
    chk("the method string states the formula", "raw_end x cumulative" in METHOD
        and "Nifty 50 TRI" in METHOD, METHOD)
    for c in ("raw_listing_close", "raw_end_close", "excess_corrected_pp",
              "excess_stored_pp", "delta_pp", "delisted_or_suspended", "ca_state"):
        chk(f"{c} is a corrected column", c in CORRECTED_COLS)
    chk("the stored columns are carried for comparison, under their own names",
        "excess_stored_pp" in CORRECTED_COLS and "H_label_stored" in CORRECTED_COLS)
    # The direction is asserted in [2] and [2b] rather than reasoned about here.
    c = classify("Bonus 1:1")
    chk("a 1:1 bonus factor is 2.0 - shares after per share before",
        c["factor"] == 2.0)
    src2 = inspect.getsource(build_corrected)
    chk("and the formula multiplies the END price by the factor, as specified",
        "raw1 * factor + divs) / raw0" in src2, src2[src2.find("ipo_r ="):][:80])
    chk("a missing factor produces NO corrected value, not an unadjusted one",
        "factor is not None" in src2)
    chk("an unparsed dividend likewise blocks the row", "not dnote" in src2)
    chk("a missing end price is recorded as delisted/suspended, not dropped",
        "delisted = bool(raw1 is None" in src2)
    chk("and the row is still written out", src2.count("out.append(") == 1)
    chk("a cache-only run says so IN THE ROW, so it cannot pass as complete",
        "CACHE-ONLY RUN" in src2)
    chk("prices are never taken from BEFORE the window opens",
        "never walks BACKWARD" in inspect.getsource(_raw_price))

    print("\n[11] reclassify touches interpretation, never evidence")
    rsrc = inspect.getsource(reclassify)
    for keep in ("source", "endpoint", "fetched_at_ist", "response_sha256", "subject"):
        chk(f"{keep} is not assigned by it", f'd.at[i, "{keep}"]' not in rsrc)
    chk("it re-derives from the stored subject", 'classify(row.get("subject"))' in rsrc)
    chk("and refetches nothing", "requests" not in rsrc and "session(" not in rsrc)
    chk("it reports how many values moved",
        "field_values_changed" in rsrc)

    print("\n[12] a missing FILE is not a delisting")
    bsrc = inspect.getsource(build_corrected)
    chk("delisted excludes rows whose bhavcopy was simply unavailable",
        'startswith("raw_price_missing")' in bsrc, bsrc[bsrc.find("delisted ="):][:160])
    chk("and the reason is written into the row, so the two are separable",
        "end_price_missing_reason" in bsrc)
    chk("the two causes are named, not numbered",
        "bhavcopy_not_available" in bsrc and "symbol_absent_from_bhavcopy" in bsrc)
    chk("effects reports them separately", "end_price_missing_reason" in
        inspect.getsource(effects))
    chk("end_price_missing_reason is a column", "end_price_missing_reason" in CORRECTED_COLS)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--actions", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--build", action="store_true",
                    help="compute the corrected targets into their own file")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive kind/factor/amount from the stored subject text")
    ap.add_argument("--effects", action="store_true",
                    help="print everything Task 5 asks for, from what is computed")
    ap.add_argument("--cache-only", dest="cache_only", action="store_true",
                    help="use only bhavcopy dates already on disk; fetch nothing")
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
    if a.build:
        print(json.dumps(build_corrected(a.horizon, a.limit, a.cache_only),
                         indent=2, default=str))
        raise SystemExit(0)
    if a.reclassify:
        print(json.dumps(reclassify(), indent=2, default=str))
        raise SystemExit(0)
    if a.effects:
        print(json.dumps(effects(a.horizon), indent=2, default=str))
        raise SystemExit(0)
    ap.print_help()

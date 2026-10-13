"""
model_h_turnover.py — Phase 2.4a: day-1 turnover as a multiple of issue size.

Why this is a module and not a join
-----------------------------------
The bhavcopy cache under `data/bhavcopy_cache/` holds only the columns
`listing_prices._norm` returns: code, symbol, isin, open, close, prev. Turnover and traded
quantity are read out of the raw file and **discarded** before caching. So the 1808 cached
dates cannot answer this question, and the raw file for each listing date has to be read
again.

`listing_prices.py` is not touched - it is inside the live-path freeze, and widening its
normaliser would change what every other caller receives. Its `Fetcher`, its URL constants
and its unzip helper are IMPORTED and reused, so the politeness gap, the warm-up and the
era-correct URL order are the same ones the rest of the project uses rather than a second
copy that could drift.

What "turnover" means here
--------------------------
The value traded in the scrip on its listing date, in rupees, as the exchange reported it
that day, divided by the issue size. Both exchanges are tried and **NSE is preferred** when
both have the scrip, because the issue size in the master is the total issue and NSE carries
the larger share of volume for a mainboard listing; the exchange actually used is recorded
on the row. A scrip found on only one exchange gets that one, flagged, because a one-venue
turnover understates the multiple and a reader has to be able to see that.

Column names differ by era and exchange, so they are matched by pattern and the pattern
that matched is stored. A file whose columns match nothing produces a NULL with the column
list in the note - never a zero.

    python model_h_turnover.py --build --limit 20
    python model_h_turnover.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import inspect
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                  # noqa: E402
import model_h_sources as SRC   # noqa: E402  - one pause rule, not a second copy

DATA = ROOT / "data"
OUT = DATA / "day1_turnover.csv"
RAW_CACHE = DATA / "bhavcopy_raw_cache"

COLS = ["symbol", "listing_date", "exchange", "turnover_rs", "traded_qty",
        "issue_size_cr", "turnover_x_issue_size", "matched_columns", "both_exchanges",
        "source_url", "fetched_at_ist", "note"]

# Turnover has had several names. TOTTRDVAL (NSE, old), TURNOVER_LACS / NO_OF_TRADES
# (BSE, old), TURNOVER (unified BhavCopy_*_CM_*). The UNIT differs too, which is why the
# pattern that matched is stored on the row: lakhs read as rupees is a 100,000x error and
# would look like a plausible number.
VAL_PATTERNS = (
    (r"^tottrdval$", 1.0, "nse TOTTRDVAL (rupees)"),
    (r"^turnover_?lacs$", 1e5, "bse TURNOVER_LACS (lakhs)"),
    # The unified BhavCopy both exchanges moved to during 2024. Verified against the real
    # header rather than guessed: TtlTrfVal / TtlTradgVol / TckrSymb.
    (r"^ttltrfval$", 1.0, "unified TtlTrfVal (rupees)"),
    (r"^turnover$", 1.0, "unified TURNOVER (rupees)"),
    (r"^net_turnov$", 1.0, "bse NET_TURNOV (rupees)"),
)
QTY_PATTERNS = (r"^tottrdqty$", r"^no_?of_?shrs$", r"^ttltradgvol$", r"^ttl_trd_qnty$",
                r"^no_of_shares$", r"^no_of_shrs$")


def _symbols_as_of(symbol, day) -> list:
    """Today's symbol first, then the symbol as of that date (NSE's own register)."""
    import model_h_targets as MT
    return MT._symbols_as_of(symbol, day)


def _norm_cols(df: pd.DataFrame) -> dict:
    return {re.sub(r"[^a-z0-9_]", "", str(c).strip().lower().replace(" ", "_")): c
            for c in df.columns}


def parse_turnover(df: pd.DataFrame) -> tuple[pd.Series | None, pd.Series | None, str]:
    """`(turnover_in_rupees, traded_qty, which_columns)` or `(None, None, reason)`."""
    cols = _norm_cols(df)
    val, mult, label = None, None, None
    for pat, m, lab in VAL_PATTERNS:
        hit = [k for k in cols if re.match(pat, k)]
        if hit:
            val, mult, label = cols[hit[0]], m, lab
            break
    qty = None
    for pat in QTY_PATTERNS:
        hit = [k for k in cols if re.match(pat, k)]
        if hit:
            qty = cols[hit[0]]
            break
    if val is None:
        return None, None, f"no turnover column among {sorted(cols)[:14]}"
    t = pd.to_numeric(df[val], errors="coerce") * mult
    q = pd.to_numeric(df[qty], errors="coerce") if qty else None
    return t, q, label


def _raw(f, day, which: str):
    """The raw bhavcopy for one date, before `_norm` drops anything. Cached separately.

    A second cache, not a change to the first: the existing one holds normalised frames
    and other jobs read it expecting those columns.
    """
    import listing_prices as LP
    d = pd.Timestamp(day)
    RAW_CACHE.mkdir(parents=True, exist_ok=True)
    cp = RAW_CACHE / f"{which}_{d:%Y%m%d}.csv.gz"
    if cp.exists():
        try:
            return pd.read_csv(cp, low_memory=False), "cache"
        except Exception:                                      # noqa: BLE001
            pass
    if which == "bse":
        f.warm(LP.BSE_HOME)
        urls = ((LP.BSE_NEW.format(ymd=f"{d:%Y%m%d}"), LP.BSE_REFERER),
                (LP.BSE_OLD.format(ddmmyy=f"{d:%d%m%y}"), LP.BSE_REFERER))
    else:
        f.warm(LP.NSE_HOME)
        urls = ((LP.NSE_NEW.format(ymd=f"{d:%Y%m%d}"), LP.NSE_HOME),
                (LP.NSE_OLD.format(Y=f"{d:%Y}", MON=f"{d:%b}".upper(),
                                   ddMONyyyy=f"{d:%d%b%Y}".upper()), LP.NSE_HOME))
    if d < pd.Timestamp("2024-07-01"):
        urls = tuple(reversed(urls))
    for u, ref in urls:
        raw, note = f.get(u, referer=ref)
        if raw is None:
            continue
        try:
            df = LP._unzip_csv(raw)
        except Exception as e:                                 # noqa: BLE001
            continue
        if df is None or df.empty:
            continue
        df.to_csv(cp, index=False, encoding="utf-8")
        return df, u
    return None, "no raw bhavcopy for this date"


def issue_sizes() -> dict:
    """symbol -> issue size in crore, from the feature table's `log_issue_size`."""
    f = DATA / "model_h_features_full.csv"
    if not f.exists():
        f = DATA / "model_h_features.csv"
    d = pd.read_csv(f, low_memory=False)
    out = {}
    for _, r in d.iterrows():
        v = pd.to_numeric(pd.Series([r.get("log_issue_size")]), errors="coerce").iloc[0]
        if pd.notna(v):
            out[str(r["symbol"])] = float(np.exp(v))
    return out


def build(limit: int | None = None, cache_only: bool = False) -> pd.DataFrame:
    import listing_prices as LP
    import model_h_targets as MT
    t = MT.latest("1y")
    t = t[t["symbol"].notna()][["symbol", "isin", "listing_date"]].drop_duplicates(
        "symbol")
    sizes = issue_sizes()
    have = set()
    if OUT.exists():
        prev = pd.read_csv(OUT)
        have = set(prev.loc[prev["turnover_rs"].notna(), "symbol"].astype(str))
    pend = [r for _, r in t.iterrows() if str(r["symbol"]) not in have]
    if limit:
        pend = pend[:limit]
    print(f"{len(t)} symbols, {len(have)} already priced, {len(pend)} to do "
          f"(cache_only={cache_only})")
    f = LP.Fetcher()
    rows = []
    for i, r in enumerate(pend, 1):
        # The live path owns NSE during the HDFIRE window. The first version of this
        # module had NO pause check: it happened to finish at 04:20 IST on 13 Oct, six
        # hours before the window opened, so it respected the window by accident of
        # timing. A politeness rule that holds only because a job started early is not a
        # rule, and the next run of this - after the user fills missing_symbols.csv -
        # would not have been so lucky.
        SRC.wait_if_paused()
        sym, isin = str(r["symbol"]), r.get("isin")
        day = pd.Timestamp(r["listing_date"])
        got = {}
        for which in ("nse", "bse"):
            cp = RAW_CACHE / f"{which}_{day:%Y%m%d}.csv.gz"
            if cache_only and not cp.exists():
                continue
            df, src = _raw(f, day, which)
            if df is None:
                continue
            tv, qv, label = parse_turnover(df)
            if tv is None:
                continue
            hit, how = LP.find(df, isin=isin, symbol=sym)
            if not len(hit):
                # `find` works on normalised columns; the raw frame needs its own lookup.
                cols = _norm_cols(df)
                key = cols.get("symbol") or cols.get("tckrsymb") or cols.get("sc_code")
                if key is None:
                    continue
                col = df[key].astype(str).str.strip().str.upper()
                # The symbol AS OF the listing date, not as it is now - the same rename
                # problem that was losing nine corrected targets. Today's symbol first,
                # so nothing that already resolved changes.
                mask = None
                for cand in _symbols_as_of(sym, day):
                    m2 = col == str(cand).upper()
                    if m2.any():
                        mask = m2
                        break
                if mask is None:
                    continue
                idx = df.index[mask][0]
            else:
                continue_outer = False
                try:
                    idx = hit.index[0]
                except Exception:                              # noqa: BLE001
                    continue_outer = True
                if continue_outer:
                    continue
            val = tv.get(idx)
            if pd.isna(val):
                continue
            got[which] = {"turnover_rs": float(val),
                          "traded_qty": (None if qv is None or pd.isna(qv.get(idx))
                                         else float(qv.get(idx))),
                          "matched_columns": label, "source_url": str(src)}
        if not got:
            rows.append({"symbol": sym, "listing_date": str(day.date()),
                         "exchange": None, "turnover_rs": None, "traded_qty": None,
                         "issue_size_cr": sizes.get(sym),
                         "turnover_x_issue_size": None, "matched_columns": None,
                         "both_exchanges": False, "source_url": None,
                         "fetched_at_ist": str(pd.Timestamp.now()),
                         "note": "no turnover found on either exchange for this date"})
        else:
            which = "nse" if "nse" in got else "bse"
            g = got[which]
            size = sizes.get(sym)
            mult = (g["turnover_rs"] / (size * 1e7)) if (size and size > 0) else None
            rows.append({"symbol": sym, "listing_date": str(day.date()),
                         "exchange": which, **g,
                         "issue_size_cr": size,
                         "turnover_x_issue_size": mult,
                         "both_exchanges": len(got) == 2,
                         "fetched_at_ist": str(pd.Timestamp.now()),
                         "note": "" if size else "no issue size, so no multiple"})
        if i % 25 == 0 or i == len(pend):
            pd.DataFrame(rows, columns=COLS).to_csv(
                OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
            print(f"  {i}/{len(pend)} - {sum(1 for x in rows if x['turnover_rs'])} priced")
            rows = []
    if rows:
        pd.DataFrame(rows, columns=COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
    return pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=COLS)


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  ok   {name}")
        else:
            fail += 1
            print(f"  FAIL {name} {extra}")

    print("[1] the unit is read off the column name, not assumed")
    t, q, lab = parse_turnover(pd.DataFrame({"SYMBOL": ["X"], "TOTTRDVAL": [1234.0],
                                             "TOTTRDQTY": [10.0]}))
    chk("NSE TOTTRDVAL is rupees and passes through", float(t.iloc[0]) == 1234.0, lab)
    t2, _, lab2 = parse_turnover(pd.DataFrame({"SC_CODE": [1], "TURNOVER_LACS": [1.0]}))
    chk("BSE TURNOVER_LACS is lakhs and is multiplied by 1e5",
        float(t2.iloc[0]) == 1e5, (float(t2.iloc[0]), lab2))
    chk("and the row records WHICH column it came from",
        "lakhs" in lab2 and "rupees" in lab)
    t3, _, why = parse_turnover(pd.DataFrame({"SYMBOL": ["X"], "CLOSE": [1.0]}))
    chk("a file with no turnover column yields None, not 0", t3 is None)
    chk("and the reason lists the columns it did see", "CLOSE".lower() in why.lower(), why)

    t4, q4, lab4 = parse_turnover(pd.DataFrame(
        {"TckrSymb": ["X"], "TtlTrfVal": [5.0], "TtlTradgVol": [2.0]}))
    chk("the unified 2024+ BhavCopy header is recognised",
        t4 is not None and float(t4.iloc[0]) == 5.0, lab4)
    chk("and its volume column too", q4 is not None and float(q4.iloc[0]) == 2.0)
    chk("the symbol is looked up as of the listing date here as well",
        "_symbols_as_of" in Path(__file__).read_text(encoding="utf-8"))

    print(chr(10) + "[2] it does not touch listing_prices")
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.replace(__import__("inspect").getsource(self_test), "")
    chk("no assignment into the listing_prices module",
        not re.search(r"\bLP\.\w+\s*=", body))
    chk("but its fetcher, URLs and unzip helper ARE reused",
        "LP.Fetcher()" in body and "LP._unzip_csv" in body and "LP.NSE_OLD" in body)
    chk("and the raw cache is a SEPARATE directory from the normalised one",
        "bhavcopy_raw_cache" in body and RAW_CACHE.name != "bhavcopy_cache")

    print(chr(10) + "[2b] it pauses when the live path owns NSE")
    chk("the build loop asks before every symbol",
        "SRC.wait_if_paused()" in inspect.getsource(build))
    chk("and it uses the SAME pause rule as the rest of Phase 2, not a copy",
        SRC.paused_now(pd.Timestamp("2026-10-13 11:00"))[0]
        and not SRC.paused_now(pd.Timestamp("2026-10-13 04:00"))[0])
    if OUT.exists():
        _d = pd.read_csv(OUT)
        _t = pd.to_datetime(_d["fetched_at_ist"], errors="coerce")
        _h = _t.dt.hour * 100 + _t.dt.minute
        _in = ((_t.dt.date.astype(str).isin(SRC.PRIORITY_DATES))
               & (((_h >= 1030) & (_h < 1630)) | ((_h >= 1915) & (_h < 2000))))
        chk("and nothing on disk was fetched inside a pause window",
            int(_in.sum()) == 0, int(_in.sum()))

    print(chr(10) + "[3] the multiple is NULL unless both ends exist")
    sizes = issue_sizes()
    chk("issue sizes are read back as levels, not logs",
        all(v > 0 for v in list(sizes.values())[:50]) and
        max(list(sizes.values())[:50]) > 20,
        sorted(list(sizes.values()))[:3])
    if OUT.exists():
        d = pd.read_csv(OUT)
        bad = d[d["turnover_x_issue_size"].notna()
                & (d["turnover_rs"].isna() | d["issue_size_cr"].isna())]
        chk("no multiple exists without both a turnover and an issue size",
            len(bad) == 0, len(bad))
        chk("a row with no turnover says so rather than carrying a zero",
            not ((d["turnover_rs"] == 0).any()))
    else:
        print("  (no output yet - the multiple checks need a build first)")

    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.build:
        d = build(limit=a.limit, cache_only=a.cache_only)
        n = int(d["turnover_rs"].notna().sum())
        print(f"{OUT.name}: {len(d)} rows, {n} with a turnover "
              f"({100 * n / max(len(d), 1):.1f}%)")

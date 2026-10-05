"""
listing_prices.py — as-reported listing-day prices from the exchanges' own bhavcopies
(Priority 2, under H18).

Why bhavcopy and not a quote API
--------------------------------
A bhavcopy is the exchange's own end-of-day file for **every scrip on one date**. That has
three properties nothing else here has:

1. **It is as-reported.** The figures are what traded that day, never retroactively
   restated for a later split or bonus. Verified before any collection: Syngene
   International (offer ₹250, 1:1 bonus in 2017) reads **OPEN 295.0** in BSE's bhavcopy for
   11-Aug-2015 — not the ₹147.50 that yfinance returns. The implied gain, 18.0%, is exactly
   the figure the master already carries.
2. **One request serves every IPO that listed that day**, so the job is sized by distinct
   listing dates rather than by companies.
3. **NSE's and BSE's bhavcopies are genuinely independent of each other**, so the label can
   be reconciled under rule 2 instead of carrying `single_source_unverified`.

`PREVCLOSE == 0` (BSE) and a zero/absent previous close (NSE) mark a scrip's **first
trading day**. That is a source-side listing marker and is checked rather than trusting our
own calendar.

Access (H18)
------------
Realistic browser headers to official hosts only, with a session warm-up (both exchanges
set cookies on the landing page and reject the file request without them), a minimum gap
between requests, and exponential backoff on throttling. `robots.txt` remains binding:
NSE's allows everything but `/market-data-test`, and BSE publishes none.

No login, CAPTCHA, paywall or click-through is involved — these are plain file downloads.

    python listing_prices.py --verify-as-reported     # the Syngene gate, re-runnable
    python listing_prices.py --date 2015-08-11        # one date, both exchanges
    python listing_prices.py --backfill               # night batch over all listing dates
    python listing_prices.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import io
import sys
import time
import zipfile
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                               # noqa: E402

CACHE = ROOT / "data" / "bhavcopy_cache"
OUT = ROOT / "data" / "listing_prices.csv"
PROGRESS = ROOT / "data" / "listing_prices_progress.csv"
LOG = ROOT / "reports" / "listing_prices.log"

MIN_GAP_S = 3.0
BACKOFF_S = (5, 15, 45, 120, 300)
TIMEOUT_S = 60
TOL = 0.05                      # rule 2: max pairwise relative difference

# H18: realistic browser headers, official hosts only.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

BSE_HOME = "https://www.bseindia.com/"
BSE_OLD = "https://www.bseindia.com/download/BhavCopy/Equity/EQ{ddmmyy}_CSV.ZIP"
BSE_NEW = ("https://www.bseindia.com/download/BhavCopy/Equity/"
           "BhavCopy_BSE_CM_0_0_0_{ymd}_F_0000.CSV")
BSE_REFERER = "https://www.bseindia.com/markets/MarketInfo/BhavCopy.aspx"
NSE_HOME = "https://www.nseindia.com/"
NSE_NEW = ("https://nsearchives.nseindia.com/content/cm/"
           "BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip")
NSE_OLD = ("https://nsearchives.nseindia.com/content/historical/EQUITIES/"
           "{Y}/{MON}/cm{ddMONyyyy}bhav.csv.zip")

OUT_COLS = ["ipo", "isin", "symbol", "bse_code", "listing_date", "offer_price",
            "nse_open", "nse_close", "bse_open", "bse_close",
            "listing_open", "listing_close", "listing_gain_pct",
            "sources", "reconciled", "first_day_marker", "note", "fetched_at"]

# The Syngene gate. Kept as a constant so the check is re-runnable and so the expected
# value is stated in one place rather than retyped in prose.
GATE = {"name": "SYNGENE", "isin": "INE398R01022", "bse_code": "539268",
        "date": "2015-08-11", "offer": 250.0,
        "as_reported_open": 295.0, "adjusted_trap": 147.50}


def log(m: str) -> None:
    print(m, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}  {m}\n")


# ---------------------------------------------------------------- fetching
class Fetcher:
    """One warmed session per host, polite, with backoff that distinguishes throttling
    from a genuine 404 (a 404 on a bhavcopy usually means a non-trading day)."""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self._warm = set()
        self._last = 0.0

    def _gap(self):
        w = MIN_GAP_S - (time.time() - self._last)
        if w > 0:
            time.sleep(w)
        self._last = time.time()

    def warm(self, home: str) -> None:
        if home in self._warm:
            return
        try:
            self._gap()
            self.s.get(home, timeout=TIMEOUT_S)
        except Exception as e:                              # noqa: BLE001
            log(f"  warm-up {home} failed: {type(e).__name__}: {str(e)[:70]}")
        self._warm.add(home)

    def get(self, url: str, referer: str | None = None) -> tuple[bytes | None, str]:
        h = dict(HEADERS)
        if referer:
            h["Referer"] = referer
        for i, wait in enumerate((0,) + BACKOFF_S):
            if wait:
                time.sleep(wait)
            try:
                self._gap()
                r = self.s.get(url, headers=h, timeout=TIMEOUT_S)
            except Exception as e:                          # noqa: BLE001
                if i == len(BACKOFF_S):
                    return None, f"{type(e).__name__}: {str(e)[:70]}"
                continue
            if r.status_code == 200:
                # Both exchanges answer 200 with their SPA homepage for a path that does
                # not exist, so a content check is required: HTML is not a bhavcopy.
                if r.content[:2] == b"PK" or b"," in r.content[:400]:
                    if b"<!DOCTYPE html" in r.content[:200] or b"<html" in r.content[:200]:
                        return None, "HTTP 200 but HTML — path does not exist"
                    return r.content, "ok"
                return None, f"HTTP 200 but {len(r.content)}B of non-tabular content"
            if r.status_code in (404,):
                return None, "HTTP 404 — most likely not a trading day"
            if r.status_code in (403, 429, 500, 502, 503, 504):
                if i == len(BACKOFF_S):
                    return None, f"HTTP {r.status_code} after {len(BACKOFF_S)} retries"
                continue
            return None, f"HTTP {r.status_code}"
        return None, "exhausted"


def _unzip_csv(raw: bytes) -> pd.DataFrame:
    if raw[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(raw))
        name = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
        return pd.read_csv(z.open(name), low_memory=False)
    return pd.read_csv(io.BytesIO(raw), low_memory=False)


def _norm(df: pd.DataFrame, which: str) -> pd.DataFrame:
    """Map either bhavcopy format onto one schema: isin, symbol, code, open, close, prev."""
    df.columns = [str(c).strip() for c in df.columns]
    c = set(df.columns)
    if {"SC_CODE", "OPEN", "CLOSE"} <= c:                   # BSE old
        out = pd.DataFrame({"code": df["SC_CODE"].astype(str).str.strip(),
                            "symbol": df.get("SC_NAME", pd.Series(dtype=str)).astype(str).str.strip(),
                            "isin": None,
                            "open": pd.to_numeric(df["OPEN"], errors="coerce"),
                            "close": pd.to_numeric(df["CLOSE"], errors="coerce"),
                            "prev": pd.to_numeric(df.get("PREVCLOSE"), errors="coerce")})
    elif {"OpnPric", "ClsPric"} <= c:                       # BSE/NSE new unified format
        out = pd.DataFrame({"code": df.get("FinInstrmId", pd.Series(dtype=str)).astype(str).str.strip(),
                            "symbol": df.get("TckrSymb", pd.Series(dtype=str)).astype(str).str.strip(),
                            "isin": df.get("ISIN", pd.Series(dtype=str)).astype(str).str.strip(),
                            "open": pd.to_numeric(df["OpnPric"], errors="coerce"),
                            "close": pd.to_numeric(df["ClsPric"], errors="coerce"),
                            "prev": pd.to_numeric(df.get("PrvsClsgPric"), errors="coerce")})
        if "SctySrs" in c:
            out = out[df["SctySrs"].astype(str).str.strip().isin(["EQ", "BE", "", "nan"])]
    elif {"SYMBOL", "OPEN", "CLOSE"} <= c:                  # NSE old
        out = pd.DataFrame({"code": None,
                            "symbol": df["SYMBOL"].astype(str).str.strip(),
                            "isin": df.get("ISIN", pd.Series(dtype=str)).astype(str).str.strip(),
                            "open": pd.to_numeric(df["OPEN"], errors="coerce"),
                            "close": pd.to_numeric(df["CLOSE"], errors="coerce"),
                            "prev": pd.to_numeric(df.get("PREVCLOSE"), errors="coerce")})
        if "SERIES" in c:
            out = out[df["SERIES"].astype(str).str.strip().isin(["EQ", "BE"])]
    else:
        raise ValueError(f"unrecognised {which} bhavcopy columns: {sorted(c)[:12]}")
    out["_src"] = which
    return out.reset_index(drop=True)


def bhavcopy(f: Fetcher, day, which: str, use_cache: bool = True):
    """One exchange's bhavcopy for one date, cached on disk. `(DataFrame|None, note)`."""
    d = pd.Timestamp(day)
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / f"{which}_{d:%Y%m%d}.parquet"
    if use_cache and cp.exists():
        try:
            return pd.read_parquet(cp), "cache"
        except Exception:                                   # noqa: BLE001
            pass
    if which == "bse":
        f.warm(BSE_HOME)
        urls = [(BSE_NEW.format(ymd=f"{d:%Y%m%d}"), BSE_REFERER),
                (BSE_OLD.format(ddmmyy=f"{d:%d%m%y}"), BSE_REFERER)]
    else:
        f.warm(NSE_HOME)
        urls = [(NSE_NEW.format(ymd=f"{d:%Y%m%d}"), NSE_HOME),
                (NSE_OLD.format(Y=f"{d:%Y}", MON=f"{d:%b}".upper(),
                                ddMONyyyy=f"{d:%d}{d:%b}".upper() + f"{d:%Y}"), NSE_HOME)]
    notes = []
    for u, ref in urls:
        raw, why = f.get(u, ref)
        if raw is None:
            notes.append(f"{u.rsplit('/', 1)[-1]}: {why}")
            continue
        try:
            df = _norm(_unzip_csv(raw), which)
        except Exception as e:                              # noqa: BLE001
            notes.append(f"{u.rsplit('/', 1)[-1]}: parse {type(e).__name__}: {e}")
            continue
        try:
            df.to_parquet(cp, index=False)
        except Exception:                                   # noqa: BLE001
            pass
        return df, "fetched"
    return None, "; ".join(notes)


# ---------------------------------------------------------------- matching
def find(df: pd.DataFrame, isin=None, symbol=None, code=None) -> pd.DataFrame:
    """ISIN first, then exchange code, then symbol. ISIN first because it is the only key
    immune to renaming (H18/H3 lesson) — a renamed company's symbol may have changed too.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    if isin and "isin" in df and str(isin).lower() != "nan":
        h = df[df["isin"].astype(str).str.upper() == str(isin).strip().upper()]
        if len(h):
            return h
    if code and "code" in df and str(code).lower() not in ("nan", "none", ""):
        c = str(code).strip().split(".")[0]
        h = df[df["code"].astype(str).str.strip().str.split(".").str[0] == c]
        if len(h):
            return h
    if symbol and "symbol" in df:
        sy = str(symbol).strip().upper()
        h = df[df["symbol"].astype(str).str.upper() == sy]
        if len(h):
            return h
        # BSE old-format names are truncated and padded ("SYNGENE", "AEGIS LOGIS"), so a
        # prefix match is the only way in. Unique match only — never the first of several.
        nm = dataio.norm_name(sy)
        if len(nm) >= 6:
            h = df[df["symbol"].astype(str).map(dataio.norm_name).str.startswith(nm[:7])]
            if len(h) == 1:
                return h
    return pd.DataFrame()


def reconcile(nse: dict, bse: dict, offer: float | None) -> dict:
    """Rule 2 on the listing price. Max pairwise relative difference > 5% -> NULL."""
    out = {"nse_open": nse.get("open"), "nse_close": nse.get("close"),
           "bse_open": bse.get("open"), "bse_close": bse.get("close")}
    srcs = [s for s, d in (("nse", nse), ("bse", bse)) if d.get("open") is not None]
    out["sources"] = "+".join(srcs)
    notes = []
    for leg in ("open", "close"):
        a, b = nse.get(leg), bse.get(leg)
        vals = [v for v in (a, b) if v is not None and pd.notna(v) and v > 0]
        if not vals:
            out[f"listing_{leg}"] = None
            continue
        if len(vals) == 2:
            diff = abs(vals[0] - vals[1]) / max(vals)
            if diff > TOL:
                out[f"listing_{leg}"] = None
                notes.append(f"{leg}: NSE {a:.2f} vs BSE {b:.2f} differ "
                             f"{diff*100:.1f}% -> NULL (rule 2)")
                continue
            out[f"listing_{leg}"] = round(sum(vals) / 2, 4)
        else:
            out[f"listing_{leg}"] = round(vals[0], 4)
    out["reconciled"] = ("reconciled_2_sources" if len(srcs) == 2
                         else "single_source_unverified" if len(srcs) == 1
                         else "no_source")
    lo = out.get("listing_open")
    out["listing_gain_pct"] = (round(100 * (lo / offer - 1), 4)
                               if lo and offer and offer > 0 else None)
    out["note"] = "; ".join(notes)
    return out


# ---------------------------------------------------------------- the gate (2c)
def verify_as_reported(f: Fetcher | None = None) -> dict:
    """Priority 2c. MUST pass before any collection. Returns a verdict dict."""
    f = f or Fetcher()
    res = {"gate": GATE, "checks": []}
    for which in ("bse", "nse"):
        df, note = bhavcopy(f, GATE["date"], which)
        h = find(df, isin=GATE["isin"], symbol=GATE["name"],
                 code=GATE["bse_code"] if which == "bse" else None)
        if not len(h):
            res["checks"].append({"source": which, "ok": None,
                                  "why": f"not found ({note})"})
            continue
        o = float(h["open"].iloc[0])
        as_rep = abs(o - GATE["as_reported_open"]) < 3.0
        adj = abs(o - GATE["adjusted_trap"]) < 3.0
        res["checks"].append({
            "source": which, "open": o,
            "ok": bool(as_rep), "looks_adjusted": bool(adj),
            "implied_gain_pct": round(100 * (o / GATE["offer"] - 1), 2),
            "first_day_marker": bool(pd.isna(h["prev"].iloc[0])
                                     or float(h["prev"].iloc[0] or 0) == 0.0)})
    good = [c for c in res["checks"] if c.get("ok")]
    bad = [c for c in res["checks"] if c.get("looks_adjusted")]
    res["verdict"] = ("REJECT — a source returned the split/bonus-adjusted price"
                      if bad else
                      "PASS — as-reported" if good else
                      "INCONCLUSIVE — Syngene not found in any bhavcopy")
    res["passed"] = bool(good and not bad)
    return res


# ---------------------------------------------------------------- backfill (2c)
def targets() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    d = m.copy()
    if "exclude_reason" in d:
        d = d[d["exclude_reason"].isna()]
    # KNOWN DATA DEFECT (CLAUDE.md): the master's `issue_open_date` column actually holds
    # the LISTING date, and `listing_date` is a partial copy of it -- 310 of 623 rows,
    # 2021 onward only, and identical to `issue_open_date` on every row where both exist.
    # So `issue_open_date` is the complete column and the one to use. Preferring
    # `listing_date` silently dropped 313 companies and the whole of 2010-2021 from the
    # first backfill run.
    ld = pd.to_datetime(d.get("issue_open_date"), errors="coerce")
    ld = ld.fillna(pd.to_datetime(d.get("listing_date"), errors="coerce"))
    d["ld"] = ld
    d = d.dropna(subset=["ld"])
    return d[["company", "isin", "symbol", "bse_code", "ld", "Offer Price"]].rename(
        columns={"company": "ipo", "ld": "listing_date", "Offer Price": "offer_price"})


def done_dates() -> set:
    if not PROGRESS.exists():
        return set()
    try:
        return set(pd.read_csv(PROGRESS)["date"].astype(str))
    except Exception:                                       # noqa: BLE001
        return set()


def backfill(limit: int | None = None) -> dict:
    t = targets()
    g = t.groupby(t["listing_date"].dt.strftime("%Y-%m-%d"))
    skip = done_dates()
    dates = [d for d in sorted(g.groups) if d not in skip]
    if limit:
        dates = dates[:limit]
    log(f"backfill: {len(t)} IPOs over {len(g.groups)} listing dates; "
        f"{len(skip)} dates already done, {len(dates)} to do")

    f = Fetcher()
    counts = {"reconciled_2_sources": 0, "single_source_unverified": 0, "no_source": 0}
    for i, day in enumerate(dates, 1):
        rows = g.get_group(day)
        nse_df, nnote = bhavcopy(f, day, "nse")
        bse_df, bnote = bhavcopy(f, day, "bse")
        got = []
        for r in rows.itertuples():
            n = find(nse_df, r.isin, r.symbol, None)
            b = find(bse_df, r.isin, r.symbol, r.bse_code)

            def one(h):
                if not len(h):
                    return {}
                return {"open": float(h["open"].iloc[0]) if pd.notna(h["open"].iloc[0]) else None,
                        "close": float(h["close"].iloc[0]) if pd.notna(h["close"].iloc[0]) else None,
                        "prev": h["prev"].iloc[0]}
            nd, bd = one(n), one(b)
            offer = pd.to_numeric(pd.Series([r.offer_price]), errors="coerce").iloc[0]
            rec = reconcile(nd, bd, None if pd.isna(offer) else float(offer))
            prev = [p for p in (nd.get("prev"), bd.get("prev")) if p is not None]
            rec.update({
                "ipo": r.ipo, "isin": r.isin, "symbol": r.symbol, "bse_code": r.bse_code,
                "listing_date": day,
                "offer_price": None if pd.isna(offer) else float(offer),
                "first_day_marker": bool(prev) and all(
                    pd.isna(p) or float(p or 0) == 0.0 for p in prev),
                "fetched_at": str(pd.Timestamp.now())})
            if rec["reconciled"] == "no_source":
                rec["note"] = "; ".join(x for x in (rec["note"],
                                                    f"nse: {nnote}", f"bse: {bnote}") if x)
            got.append(rec)
            counts[rec["reconciled"]] = counts.get(rec["reconciled"], 0) + 1
        if got:
            pd.DataFrame([{c: r.get(c) for c in OUT_COLS} for r in got],
                         columns=OUT_COLS).to_csv(
                OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
        pd.DataFrame([{"date": day, "n_ipos": len(rows),
                       "nse": nnote, "bse": bnote,
                       "ran_at": str(pd.Timestamp.now())}]).to_csv(
            PROGRESS, mode="a", header=not PROGRESS.exists(), index=False, encoding="utf-8")
        ok = sum(1 for r in got if r["reconciled"] != "no_source")
        log(f"  [{i:4d}/{len(dates)}] {day}  {len(rows)} IPO(s)  priced {ok}  "
            f"nse={nnote[:26]} bse={bnote[:26]}")
    log(f"backfill finished: {counts}")
    return counts


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    print("listing_prices.py self-test (no network)")

    print("\n[1] rule 2 on the listing price")
    r = reconcile({"open": 100.0, "close": 110.0}, {"open": 101.0, "close": 111.0}, 80.0)
    chk("two close sources average", abs(r["listing_open"] - 100.5) < 1e-9, str(r))
    chk("marked reconciled", r["reconciled"] == "reconciled_2_sources")
    chk("gain computed off the reconciled open",
        abs(r["listing_gain_pct"] - 25.625) < 1e-6, str(r["listing_gain_pct"]))
    r = reconcile({"open": 100.0}, {"open": 140.0}, 80.0)
    chk("a >5% disagreement becomes NULL", r["listing_open"] is None, str(r))
    chk("and the gain is NULL too", r["listing_gain_pct"] is None)
    chk("and the reason is recorded", "rule 2" in r["note"], r["note"])
    r = reconcile({"open": 100.0}, {}, 80.0)
    chk("one source is flagged single_source_unverified",
        r["reconciled"] == "single_source_unverified", str(r))
    r = reconcile({}, {}, 80.0)
    chk("no source yields no_source and no gain",
        r["reconciled"] == "no_source" and r["listing_gain_pct"] is None)
    chk("a zero offer price cannot produce a gain",
        reconcile({"open": 100.0}, {"open": 100.0}, 0.0)["listing_gain_pct"] is None)

    print("\n[2] the gate's expected values are the real ones")
    chk("Syngene offer is 250", GATE["offer"] == 250.0)
    chk("as-reported open is 295", GATE["as_reported_open"] == 295.0)
    chk("the adjusted trap is exactly half", abs(GATE["adjusted_trap"] * 2 - 295.0) < 0.01)
    chk("gate carries an ISIN so it matches without a name",
        GATE["isin"].startswith("INE"))

    print("\n[3] matching prefers ISIN, then code, then symbol")
    df = pd.DataFrame({"isin": ["INE398R01022", "INE999X01010"],
                       "symbol": ["WRONGNAME", "SYNGENE"],
                       "code": ["111111", "539268"],
                       "open": [295.0, 1.0], "close": [310.4, 2.0], "prev": [0.0, 5.0]})
    chk("ISIN wins over a matching symbol on another row",
        float(find(df, isin="INE398R01022", symbol="SYNGENE")["open"].iloc[0]) == 295.0)
    chk("code is used when ISIN is absent",
        float(find(df, isin=None, symbol=None, code="539268")["open"].iloc[0]) == 1.0)
    chk("symbol is the last resort",
        float(find(df, isin=None, symbol="SYNGENE")["open"].iloc[0]) == 1.0)
    chk("nothing matches -> empty, never a guess",
        find(df, isin="INE000000000", symbol="NOSUCHCO", code="9").empty)

    print("\n[4] an ambiguous prefix match is refused")
    df2 = pd.DataFrame({"isin": [None, None], "symbol": ["RELIANCE IND", "RELIANCE POW"],
                        "code": ["1", "2"], "open": [1.0, 2.0], "close": [1.0, 2.0],
                        "prev": [1.0, 1.0]})
    chk("two prefix candidates yield nothing", find(df2, symbol="RELIANCE").empty)

    print("\n[5] HTML served with HTTP 200 is not treated as data")
    import inspect
    src = inspect.getsource(Fetcher.get)
    chk("the fetcher checks content, not just the status code",
        "<!DOCTYPE html" in src and "HTML" in src)
    chk("404 is distinguished from throttling",
        "not a trading day" in src and "503" in src)

    print("\n[6] the target set covers the whole history, not just 2021+")
    try:
        t = targets()
        yrs = pd.to_datetime(t["listing_date"]).dt.year
        chk("targets() returns the full master", len(t) > 600, str(len(t)))
        chk("and reaches back to 2010", int(yrs.min()) <= 2010, str(yrs.min()))
        chk("and forward to 2026", int(yrs.max()) >= 2026, str(yrs.max()))
    except Exception as e:
        chk("targets() runs", False, f"{type(e).__name__}: {e}")

    print("\n[7] column mapping for all four bhavcopy formats")
    bse_old = pd.DataFrame({"SC_CODE": [1], "SC_NAME": ["X "], "OPEN": [1.0],
                            "CLOSE": [2.0], "PREVCLOSE": [0.0]})
    chk("BSE old maps", _norm(bse_old, "bse")["open"].iloc[0] == 1.0)
    new = pd.DataFrame({"OpnPric": [1.0], "ClsPric": [2.0], "PrvsClsgPric": [0.0],
                        "ISIN": ["INE1"], "TckrSymb": ["X"], "FinInstrmId": ["9"],
                        "SctySrs": ["EQ"]})
    chk("unified new format maps", _norm(new, "nse")["isin"].iloc[0] == "INE1")
    nse_old = pd.DataFrame({"SYMBOL": ["X"], "SERIES": ["EQ"], "OPEN": [1.0],
                            "CLOSE": [2.0], "PREVCLOSE": [0.0], "ISIN": ["INE1"]})
    chk("NSE old maps", _norm(nse_old, "nse")["open"].iloc[0] == 1.0)
    try:
        _norm(pd.DataFrame({"a": [1]}), "nse")
        chk("an unknown format raises rather than guessing", False)
    except ValueError:
        chk("an unknown format raises rather than guessing", True)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-as-reported", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.verify_as_reported:
        import json
        r = verify_as_reported()
        print(json.dumps(r, indent=2, default=str))
        print(f"\n{r['verdict']}")
        raise SystemExit(0 if r["passed"] else 1)
    if a.date:
        f = Fetcher()
        for w in ("nse", "bse"):
            df, note = bhavcopy(f, a.date, w)
            print(f"{w}: {note}  rows={0 if df is None else len(df)}")
        raise SystemExit(0)
    if a.backfill:
        g = verify_as_reported()
        print(f"gate: {g['verdict']}")
        if not g["passed"]:
            print("REFUSING to collect: the as-reported gate did not pass.", file=sys.stderr)
            raise SystemExit(1)
        print(backfill(a.limit))
    else:
        print(__doc__)

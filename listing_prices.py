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
            "nse_match_by", "bse_match_by",
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
    # CSV.gz, not parquet: parquet needs pyarrow, which is not in requirements.txt, and
    # the first version swallowed the resulting ImportError in a bare `except: pass`. The
    # cache was therefore EMPTY on every run and each re-run refetched all 519 dates from
    # the exchanges - slow, and a worse citizen than intended. A cache that silently does
    # not cache is worse than no cache, because nothing tells you.
    cp = CACHE / f"{which}_{d:%Y%m%d}.csv.gz"
    if use_cache and cp.exists():
        try:
            return pd.read_csv(cp, low_memory=False), "cache"
        except Exception as e:                              # noqa: BLE001
            log(f"  cache unreadable, refetching {cp.name}: {type(e).__name__}")
    # Try the format that era actually used FIRST. Both exchanges moved to the unified
    # BhavCopy_*_CM_* naming during 2024; before that BSE used EQ<ddmmyy>_CSV.ZIP and NSE
    # used cm<DDMMMYYYY>bhav.csv.zip. Probing the modern name first on a 2010 date wasted a
    # round trip plus the politeness gap on every one of ~450 historical dates - about half
    # the job's requests, and half its load on the exchanges, for nothing. The other order
    # is still tried as a fallback, so a wrong guess about the cutover costs only what the
    # old behaviour cost.
    modern = d >= pd.Timestamp("2024-07-01")
    if which == "bse":
        f.warm(BSE_HOME)
        new_u = (BSE_NEW.format(ymd=f"{d:%Y%m%d}"), BSE_REFERER)
        old_u = (BSE_OLD.format(ddmmyy=f"{d:%d%m%y}"), BSE_REFERER)
    else:
        f.warm(NSE_HOME)
        new_u = (NSE_NEW.format(ymd=f"{d:%Y%m%d}"), NSE_HOME)
        old_u = (NSE_OLD.format(Y=f"{d:%Y}", MON=f"{d:%b}".upper(),
                                ddMONyyyy=f"{d:%d}{d:%b}".upper() + f"{d:%Y}"), NSE_HOME)
    urls = [new_u, old_u] if modern else [old_u, new_u]
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
            df.to_csv(cp, index=False, compression="gzip", encoding="utf-8")
        except Exception as e:                              # noqa: BLE001
            # Reported, never swallowed: a broken cache must be visible.
            log(f"  WARNING could not cache {cp.name}: {type(e).__name__}: {e}")
        return df, "fetched"
    return None, "; ".join(notes)


# ---------------------------------------------------------------- matching
def find(df: pd.DataFrame, isin=None, symbol=None, code=None) -> tuple[pd.DataFrame, str]:
    """`(rows, how)` where `how` records WHICH key matched.

    ISIN first because it is the only key immune to renaming. The `how` value is kept and
    written to the output because the keys are not equally trustworthy, and the first run
    proved it: Dharan Infra EPC (offer Rs 180) matched a BSE row opening at Rs 14.20, a
    -92% "gain", because BSE's old-format bhavcopy pads and TRUNCATES scrip names
    ("AEGIS LOGIS") so a 7-character prefix can land on an unrelated company. A value whose
    only support is a truncated-name prefix match must be distinguishable from one keyed on
    an ISIN, or that row silently corrupts every threshold derived from it (hard rule 1).
    """
    if df is None or df.empty:
        return pd.DataFrame(), "none"
    if isin and "isin" in df and str(isin).lower() != "nan":
        h = df[df["isin"].astype(str).str.upper() == str(isin).strip().upper()]
        if len(h):
            return h, "isin"
    if code and "code" in df and str(code).lower() not in ("nan", "none", ""):
        c = str(code).strip().split(".")[0]
        h = df[df["code"].astype(str).str.strip().str.split(".").str[0] == c]
        if len(h):
            return h, "code"
    if symbol and "symbol" in df:
        sy = str(symbol).strip().upper()
        h = df[df["symbol"].astype(str).str.upper() == sy]
        if len(h):
            return h, "symbol"
        nm = dataio.norm_name(sy)
        if len(nm) >= 6:
            h = df[df["symbol"].astype(str).map(dataio.norm_name).str.startswith(nm[:7])]
            if len(h) == 1:
                return h, "symbol_prefix"
            if len(h) > 1:
                return pd.DataFrame(), "ambiguous_prefix"
    return pd.DataFrame(), "none"


def reconcile(nse: dict, bse: dict, offer: float | None) -> dict:
    """Rule 2 on the listing price. Max pairwise relative difference > 5% -> NULL."""
    out = {"nse_open": nse.get("open"), "nse_close": nse.get("close"),
           "bse_open": bse.get("open"), "bse_close": bse.get("close"),
           "nse_match_by": nse.get("match_by"), "bse_match_by": bse.get("match_by")}
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
    if len(srcs) == 2:
        out["reconciled"] = "reconciled_2_sources"
    elif len(srcs) == 1:
        # A lone source matched only by a truncated-name prefix is the weakest evidence
        # there is and gets its own status, so it can be excluded without excluding every
        # single-source row. This is match PROVENANCE, not a judgement about whether the
        # number looks plausible -- plausibility inference is forbidden (H8).
        how = (nse if nse.get("open") is not None else bse).get("match_by")
        out["reconciled"] = ("single_source_prefix_match_unverified"
                             if how == "symbol_prefix" else "single_source_unverified")
    else:
        out["reconciled"] = "no_source"
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
        h, how = find(df, isin=GATE["isin"], symbol=GATE["name"],
                      code=GATE["bse_code"] if which == "bse" else None)
        if not len(h):
            res["checks"].append({"source": which, "ok": None,
                                  "why": f"not found ({note})"})
            continue
        o = float(h["open"].iloc[0])
        as_rep = abs(o - GATE["as_reported_open"]) < 3.0
        adj = abs(o - GATE["adjusted_trap"]) < 3.0
        res["checks"].append({
            "source": which, "open": o, "matched_by": how,
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
            n, nhow = find(nse_df, r.isin, r.symbol, None)
            b, bhow = find(bse_df, r.isin, r.symbol, r.bse_code)

            def one(h, how):
                if not len(h):
                    return {"match_by": how}
                return {"open": float(h["open"].iloc[0]) if pd.notna(h["open"].iloc[0]) else None,
                        "close": float(h["close"].iloc[0]) if pd.notna(h["close"].iloc[0]) else None,
                        "prev": h["prev"].iloc[0], "match_by": how}
            nd, bd = one(n, nhow), one(b, bhow)
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


# ------------------------------------------------- forward capture (2d) + scoring (2e)
#
# STANDING RULE, decided by the user on 2026-10-05 and recorded with H18:
#
#   A newly listed IPO's price is captured ON ITS LISTING DATE. Never earlier, and never
#   later.
#
# Not a preference -- it is the difference between a correct label and a corrupted one. A
# price read weeks later has been retroactively restated for any split or bonus since, and
# the restatement is silent: Syngene's genuine Rs 295 open reads Rs 147.50 once its 2017
# bonus is applied, turning a +18% listing gain into -41%. A bhavcopy for the listing DATE
# is frozen at what traded that day and can never be restated, so capturing on the day is
# the only way the label stays true however long it is kept.
#
# `catch_up` exists for a missed day and is safe for exactly the same reason: it reads the
# ARCHIVED bhavcopy for that date, not a current quote.

def _pending_predictions() -> pd.DataFrame:
    """Prediction rows in predictions_log.csv with no outcome row yet."""
    import predictions_log as PL
    d = PL.load()
    if d.empty:
        return d
    pred = d[d["row_type"] == "prediction"].copy()
    done = set(d.loc[d["row_type"] == "outcome", "prediction_id"].astype(str))
    pred = pred[~pred["prediction_id"].astype(str).isin(done)]
    # Rehearsal rows were scored on historical data and are not live predictions.
    src = pred.get("subscription_source", pd.Series("", index=pred.index)).astype(str)
    return pred[~src.str.contains("REHEARSAL", case=False, na=False)]


def capture_listing_day(day=None, catch_up: bool = False) -> dict:
    """Capture the listing-day price for anything listing on `day`, and score (2e) any
    prediction it settles.

    Idempotent: an IPO already present in listing_prices.csv for that date is skipped, and
    an outcome row is only appended for a prediction that has none.
    """
    import predictions_log as PL
    day = pd.Timestamp(day or pd.Timestamp.now()).normalize()
    today = pd.Timestamp.now().normalize()
    if day > today:
        return {"date": str(day.date()), "error": "refusing to capture a future date"}
    if day < today and not catch_up:
        return {"date": str(day.date()),
                "error": ("refusing to capture a past date without catch_up=True. The "
                          "standing rule is capture ON the listing date; pass --catch-up "
                          "to read that date's ARCHIVED bhavcopy deliberately.")}

    pend = _pending_predictions()
    if pend.empty:
        return {"date": str(day.date()), "n_pending": 0,
                "note": "no live prediction is awaiting an outcome"}

    f = Fetcher()
    nse_df, nnote = bhavcopy(f, day, "nse")
    bse_df, bnote = bhavcopy(f, day, "bse")

    already = set()
    if OUT.exists():
        try:
            e = pd.read_csv(OUT)
            already = {(str(a), str(b)) for a, b in zip(e["ipo"], e["listing_date"])}
        except Exception:                                    # noqa: BLE001
            pass

    m = dataio.load_master_with_symbols()
    by_isin = {str(r.isin).upper(): r for r in m.itertuples() if pd.notna(r.isin)}

    out = {"date": str(day.date()), "n_pending": int(len(pend)), "scored": [], "missed": []}
    rows = []
    for r in pend.itertuples():
        isin = str(getattr(r, "isin", "") or "").upper()
        mr = by_isin.get(isin)
        symbol = getattr(mr, "symbol", None) if mr is not None else None
        code = getattr(mr, "bse_code", None) if mr is not None else None
        offer = pd.to_numeric(pd.Series([getattr(mr, "Offer Price", None)
                                         if mr is not None else None]),
                              errors="coerce").iloc[0]

        n, nhow = find(nse_df, isin or None, symbol, None)
        b, bhow = find(bse_df, isin or None, symbol, code)

        def one(h, how):
            if not len(h):
                return {"match_by": how}
            return {"open": float(h["open"].iloc[0]) if pd.notna(h["open"].iloc[0]) else None,
                    "close": float(h["close"].iloc[0]) if pd.notna(h["close"].iloc[0]) else None,
                    "prev": h["prev"].iloc[0], "match_by": how}
        nd, bd = one(n, nhow), one(b, bhow)
        if nd.get("open") is None and bd.get("open") is None:
            out["missed"].append({"ipo": r.ipo, "why": f"not in either bhavcopy for "
                                                       f"{day.date()} (nse: {nnote}, bse: {bnote})"})
            continue

        rec = reconcile(nd, bd, None if pd.isna(offer) else float(offer))
        rec.update({"ipo": r.ipo, "isin": isin or None, "symbol": symbol, "bse_code": code,
                    "listing_date": str(day.date()),
                    "offer_price": None if pd.isna(offer) else float(offer),
                    "first_day_marker": any(
                        pd.isna(x.get("prev")) or float(x.get("prev") or 0) == 0.0
                        for x in (nd, bd) if "prev" in x),
                    "fetched_at": str(pd.Timestamp.now())})
        if (str(rec["ipo"]), str(rec["listing_date"])) not in already:
            rows.append(rec)

        # 2e: the label settles the prediction. Append an OUTCOME row - the prediction row
        # is never edited (the log is append-only by design).
        PL.log_outcome(str(r.prediction_id), str(r.ipo), str(day.date()),
                       rec.get("listing_gain_pct"),
                       note=(f"listing-day capture on the listing date; "
                             f"sources={rec.get('sources')} {rec.get('reconciled')}"
                             + (f"; {rec['note']}" if rec.get("note") else "")))
        out["scored"].append({"ipo": r.ipo, "prediction_id": str(r.prediction_id),
                              "listing_gain_pct": rec.get("listing_gain_pct"),
                              "reconciled": rec.get("reconciled")})

    if rows:
        pd.DataFrame([{c: x.get(c) for c in OUT_COLS} for x in rows],
                     columns=OUT_COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
    log(f"listing-day capture {day.date()}: {len(out['scored'])} scored, "
        f"{len(out['missed'])} not yet listed")
    return out


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
        float(find(df, isin="INE398R01022", symbol="SYNGENE")[0]["open"].iloc[0]) == 295.0)
    chk("code is used when ISIN is absent",
        float(find(df, isin=None, symbol=None, code="539268")[0]["open"].iloc[0]) == 1.0)
    chk("symbol is the last resort",
        float(find(df, isin=None, symbol="SYNGENE")[0]["open"].iloc[0]) == 1.0)
    chk("nothing matches -> empty, never a guess",
        find(df, isin="INE000000000", symbol="NOSUCHCO", code="9")[0].empty)

    print("\n[4] an ambiguous prefix match is refused")
    df2 = pd.DataFrame({"isin": [None, None], "symbol": ["RELIANCE IND", "RELIANCE POW"],
                        "code": ["1", "2"], "open": [1.0, 2.0], "close": [1.0, 2.0],
                        "prev": [1.0, 1.0]})
    chk("two prefix candidates yield nothing", find(df2, symbol="RELIANCE")[0].empty)
    chk("and are reported as ambiguous_prefix, not silently dropped",
        find(df2, symbol="RELIANCE")[1] == "ambiguous_prefix")

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

    print("\n[7] the listing-day standing rule (2d)")
    fut = (pd.Timestamp.now() + pd.Timedelta(days=5)).normalize()
    r = capture_listing_day(fut)
    chk("a FUTURE date is refused", "error" in r and "future" in r["error"], str(r))
    past = (pd.Timestamp.now() - pd.Timedelta(days=5)).normalize()
    r = capture_listing_day(past)
    chk("a PAST date is refused without catch_up",
        "error" in r and "catch_up" in r["error"], str(r))
    chk("and the refusal explains WHY the rule exists",
        "error" in r and "ON the listing date" in r["error"], str(r))
    import inspect
    _src = inspect.getsource(capture_listing_day)
    chk("catch_up reads an ARCHIVED bhavcopy, never a current quote",
        "bhavcopy(f, day" in _src and "StockReachGraph" not in _src)
    chk("rehearsal rows are never treated as live predictions",
        "REHEARSAL" in inspect.getsource(_pending_predictions))
    chk("an outcome is APPENDED, never written over the prediction",
        "log_outcome" in _src and "log_prediction" not in _src)

    print("\n[8] column mapping for all four bhavcopy formats")
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
    ap.add_argument("--capture-listing-day", action="store_true",
                    help="2d: capture today's listing-day prices and score predictions")
    ap.add_argument("--catch-up", action="store_true",
                    help="allow --date with --capture-listing-day for a MISSED day")
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
    if a.capture_listing_day:
        import json
        print(json.dumps(capture_listing_day(a.date, a.catch_up), indent=2, default=str))
        raise SystemExit(0)
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

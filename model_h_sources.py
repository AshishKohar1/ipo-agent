"""
model_h_sources.py — Phase 2's network fetching, in one queue (rule 9).

Everything Model H needs from a network source and does not already have on disk. One
fetcher, one process, >= 3.2 s between requests to a host, resumable, and safe to kill at
any moment (H9). **The live path has priority on NSE**: on 13, 14 and 15 Oct 2026 this
pauses 10:30-16:30 and 19:15-20:00 IST rather than competing with the email, the HDFIRE
polls and the day-end capture for the same politeness budget.

Stages, strictly sequential:

  sectors   NSE's own industry classification per symbol, from its index-constituent
            files, which carry an `Industry` column (2.4b)
  indices   total-return level history for Nifty 50, the 15 captured sectoral indices and
            Nifty Smallcap 100, from niftyindices.com (unblocks 2.4c, 2.4d, 2.4f)

What is NOT here, and why
-------------------------
Three things in the Phase 2 brief have no route that is open to us, and they are left
undone rather than approximated:

* **Nifty 50 P/E history (2.4e).** `niftyindices.com/reports/pe-pb-div` returns a page with
  no API endpoint named in it, and `getpepbdiv`, `getpepbdivData`, `getPEPBDIV` and
  `getHistoricalPEPBDIV` all return the site's HTML shell rather than JSON. The TRI
  endpoint on the same host works, so this is the endpoint not existing under those names,
  not a blocked client.
* **India VIX history (2.4g).** `api/historical/vixhistory` and
  `api/historical/indicesHistory?indexType=INDIA VIX` both return **HTTP 503** for our
  client, with the referring page primed first. `api/allIndices` carries India VIX but only
  TODAY's value, which is no use for a listing date in 2017.
* **Per-symbol four-level industry** (macro / sector / industry / basic industry).
  `api/quote-equity?symbol=X` returns **403**, again with its own page primed. The
  constituent files give ONE level - the macro sector - so that is what the sector map
  carries, and it says so.

H18 is why none of these is pursued further: a 403 or a 503 to an honest User-Agent is the
site declining, and the next step from here would be making ourselves look like something
else. Official sources take precedence where they exist, and where they decline, the column
is NULL with a reason.

    python model_h_sources.py --stage sectors
    python model_h_sources.py --stage indices
    python model_h_sources.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                  # noqa: E402

DATA = ROOT / "data"
MANUAL = DATA / "manual_inputs"
SECTOR_MAP = DATA / "sector_map.csv"
MISSING_SECTORS = MANUAL / "missing_sectors.csv"
INDEX_HISTORY = DATA / "index_history.csv"
FETCH_LOG = DATA / "model_h_fetch_log.csv"

GAP_S = 3.2

# The live path owns NSE during the HDFIRE window. These are IST clock ranges on those
# three dates only; outside them this module runs whenever it is started.
PRIORITY_DATES = ("2026-10-13", "2026-10-14", "2026-10-15")
PAUSE_WINDOWS = ((1030, 1630), (1915, 2000))

NSE_INDEX_LISTS = (
    "ind_niftytotalmarket_list.csv",
    "ind_nifty500list.csv",
    "ind_niftymicrocap250_list.csv",
    "ind_niftysmallcap250list.csv",
    "ind_niftymidsmallcap400list.csv",
    "ind_niftylargemidcap250list.csv",
)
ARCHIVE = "https://nsearchives.nseindia.com/content/indices/"

# NSE's macro sector -> the sectoral index that actually tracks it, among the 15 the live
# capture already stores. A sector with no matching index is NOT forced into a neighbour:
# it maps to None with a reason, because a wrong benchmark produces a momentum number that
# looks exactly like a right one.
SECTOR_TO_INDEX = {
    "financial services": "NIFTY FINANCIAL SERVICES",
    "information technology": "NIFTY IT",
    "healthcare": "NIFTY HEALTHCARE",
    "automobile and auto components": "NIFTY AUTO",
    "fast moving consumer goods": "NIFTY FMCG",
    "metals & mining": "NIFTY METAL",
    "realty": "NIFTY REALTY",
    "oil gas & consumable fuels": "NIFTY OIL & GAS",
    "power": "NIFTY ENERGY",
    "media entertainment & publication": "NIFTY MEDIA",
    "consumer durables": "NIFTY CONSUMER DURABLES",
    "construction": "NIFTY INFRASTRUCTURE",
}
# Named explicitly so a reader can see these were considered and declined, rather than
# wonder whether they were forgotten.
NO_INDEX_REASON = {
    "capital goods": "no Nifty Capital Goods index among the 15 captured; "
                     "Infrastructure is a different basket",
    "chemicals": "no Nifty Chemicals index among the 15 captured",
    "telecommunication": "no Nifty Telecom index among the 15 captured",
    "services": "too broad to benchmark - spans finance, logistics and hospitality",
    "consumer services": "no Nifty Consumer Services index among the 15 captured",
    "textiles": "no Nifty Textiles index among the 15 captured",
    "construction materials": "cement sits in no captured index",
    "diversified": "a conglomerate has no single sector by definition",
    "forest materials": "no captured index covers paper and forest products",
}

NIFTY_PAGE = "https://www.niftyindices.com/reports/historical-data"
NIFTY_TRI_URL = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
NIFTY_HDR = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
             "Accept": "application/json, text/javascript, */*; q=0.01",
             "X-Requested-With": "XMLHttpRequest",
             "Origin": "https://www.niftyindices.com", "Referer": NIFTY_PAGE}

# Nifty 50 is the benchmark every relative number is taken against; Smallcap 100 is block
# 2.4f; the rest are the sectoral indices the live capture already stores, so a momentum
# number computed here and an index close captured live refer to the same series.
WANT_INDICES = ("NIFTY 50", "NIFTY SMALLCAP 100", "NIFTY AUTO", "NIFTY BANK",
                "NIFTY FINANCIAL SERVICES", "NIFTY IT", "NIFTY PHARMA",
                "NIFTY HEALTHCARE", "NIFTY FMCG", "NIFTY METAL", "NIFTY REALTY",
                "NIFTY ENERGY", "NIFTY OIL & GAS", "NIFTY INFRASTRUCTURE",
                "NIFTY MEDIA", "NIFTY CONSUMER DURABLES")


# ------------------------------------------------------------------ politeness
def paused_now(when: pd.Timestamp | None = None) -> tuple[bool, str]:
    """True while the live path owns the network."""
    now = when or pd.Timestamp.now()
    if str(now.date()) not in PRIORITY_DATES:
        return False, ""
    hhmm = now.hour * 100 + now.minute
    for a, b in PAUSE_WINDOWS:
        if a <= hhmm < b:
            return True, (f"{now:%H:%M} IST is inside the live-path priority window "
                          f"{a // 100:02d}:{a % 100:02d}-{b // 100:02d}:{b % 100:02d} "
                          f"on {now.date()}")
    return False, ""


def wait_if_paused(when=None) -> None:
    while True:
        p, why = paused_now(when)
        if not p:
            return
        print(f"  PAUSED: {why}. Sleeping 5 min; the live path has priority on NSE.")
        time.sleep(300)


def log_fetch(url: str, status, nbytes: int, note: str = "") -> None:
    row = pd.DataFrame([{"fetched_at_ist": str(pd.Timestamp.now()), "url": url,
                         "http_status": status, "bytes": nbytes,
                         "sha256": note if len(str(note)) == 64 else "",
                         "note": "" if len(str(note)) == 64 else note}])
    FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(FETCH_LOG, mode="a", header=not FETCH_LOG.exists(), index=False,
               encoding="utf-8")


class Queue:
    """One fetcher, one gap, shared across every stage in this process (rule 9)."""

    def __init__(self):
        self._last = 0.0

    def gap(self):
        g = GAP_S - (time.time() - self._last)
        if g > 0:
            time.sleep(g)
        self._last = time.time()


# ------------------------------------------------------------------ 2.4b sectors
def fetch_sectors(q: Queue) -> pd.DataFrame:
    """NSE's industry classification per symbol, from its own index-constituent files.

    Every row carries the file it came from, the fetch time and the SHA-256 of the exact
    bytes parsed (rule 2 / H26). A symbol present in several files keeps the FIRST reading
    and the others are compared: a disagreement is recorded, never averaged away.
    """
    import nse_subscription as NSE
    f = NSE.Fetcher()
    if not f.warm():
        raise RuntimeError("NSE warm-up/robots check failed; nothing fetched")
    rows, seen, clashes = [], {}, []
    for name in NSE_INDEX_LISTS:
        wait_if_paused()
        q.gap()
        url = ARCHIVE + name
        try:
            r = f.s.get(url, timeout=60, headers={"Referer": "https://www.nseindia.com/"})
        except Exception as e:                                  # noqa: BLE001
            log_fetch(url, "error", 0, f"{type(e).__name__}: {str(e)[:60]}")
            print(f"  {name:40s} FAILED {type(e).__name__}")
            continue
        sha = hashlib.sha256(r.content).hexdigest()
        log_fetch(url, r.status_code, len(r.content), sha)
        if r.status_code != 200:
            print(f"  {name:40s} HTTP {r.status_code}")
            continue
        try:
            d = pd.read_csv(io.StringIO(r.text))
        except Exception as e:                                  # noqa: BLE001
            print(f"  {name:40s} unparsable: {type(e).__name__}")
            continue
        cols = {c.strip().lower(): c for c in d.columns}
        if "symbol" not in cols or "industry" not in cols:
            print(f"  {name:40s} no Symbol/Industry columns: {list(d.columns)}")
            continue
        n_new = 0
        for _, x in d.iterrows():
            sym = str(x[cols["symbol"]]).strip().upper()
            ind = str(x[cols["industry"]]).strip()
            if not sym or sym == "NAN" or not ind or ind == "nan":
                continue
            if sym in seen:
                if seen[sym] != ind:
                    clashes.append({"symbol": sym, "first": seen[sym], "then": ind,
                                    "file": name})
                continue
            seen[sym] = ind
            n_new += 1
            rows.append({
                "symbol": sym,
                "company_nse": str(x[cols.get("company name", cols["symbol"])]).strip(),
                "isin": str(x[cols["isin code"]]).strip() if "isin code" in cols else None,
                "nse_industry": ind,
                "source": "nseindia index constituent file",
                "source_file": name, "source_url": url, "source_sha256": sha,
                "fetched_at_ist": str(pd.Timestamp.now()),
            })
        print(f"  {name:40s} {len(d):4d} rows, {n_new:4d} new symbols")
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no constituent file yielded a Symbol/Industry pair")
    out["sector_index"] = out["nse_industry"].map(
        lambda v: SECTOR_TO_INDEX.get(str(v).strip().lower()))
    out["sector_index_missing_reason"] = [
        "" if idx else NO_INDEX_REASON.get(str(v).strip().lower(),
                                           f"sector {v!r} is not in the mapping table")
        for v, idx in zip(out["nse_industry"], out["sector_index"])]
    out.to_csv(SECTOR_MAP, index=False, encoding="utf-8")
    if clashes:
        print(f"  {len(clashes)} symbols carried a different industry in a later file; "
              f"the first reading is kept and the clash is recorded")
        pd.DataFrame(clashes).to_csv(DATA / "sector_map_clashes.csv", index=False,
                                     encoding="utf-8")
    print(f"  wrote {SECTOR_MAP.name}: {len(out)} symbols, "
          f"{out['sector_index'].notna().sum()} mapped to one of the 15 indices")
    return out


def write_missing_sectors() -> int:
    """The IPOs whose symbol NSE no longer shows - delisted, renamed, or simply too small
    to be in any index. Written for the user to fill, never guessed at."""
    m = dataio.load_master_with_symbols()
    smap = pd.read_csv(SECTOR_MAP) if SECTOR_MAP.exists() else pd.DataFrame()
    have = set(smap["symbol"].astype(str).str.upper()) if len(smap) else set()
    tgt = pd.read_csv(DATA / "holding_target_corrected.csv")
    scored = set(tgt["symbol"].dropna().astype(str).str.upper())
    rows = []
    for _, r in m.iterrows():
        sym = str(r.get("symbol") or "").strip().upper()
        if not sym or sym in ("NAN", "NONE"):
            continue
        if sym not in scored:
            continue                       # no Model H target, so no sector needed
        if sym in have:
            continue
        rows.append({"company": r.get("company"), "symbol": sym,
                     "listing_date": str(pd.Timestamp(r.get("issue_open_date")).date())
                     if pd.notna(r.get("issue_open_date")) else "",
                     "nse_industry": "",
                     "notes": "not in any NSE index-constituent file; delisted, renamed, "
                              "or below index inclusion size"})
    MANUAL.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["company", "symbol", "listing_date", "nse_industry",
                                "notes"]).to_csv(MISSING_SECTORS, index=False,
                                                 encoding="utf-8")
    print(f"  wrote {MISSING_SECTORS.relative_to(ROOT)}: {len(rows)} rows for the user")
    return len(rows)


# ------------------------------------------------------------- 2.1 official renames
NAME_CHANGES = DATA / "nse_name_changes.csv"
SYMBOL_CHANGES = DATA / "nse_symbol_changes.csv"
RENAME_FILES = (("namechange.csv", NAME_CHANGES),
                ("symbolchange.csv", SYMBOL_CHANGES))
RENAME_ARCHIVE = "https://nsearchives.nseindia.com/content/equities/"


def fetch_renames(q: Queue) -> dict:
    """NSE's own change-of-name and change-of-symbol registers.

    This is what Task 2.1 asks for first: the exchange's record of old name -> new name
    with an effective date, rather than any judgement about which names look alike. Both
    files are open CSV on nsearchives and need no login (H18).

    They are stored verbatim with the SHA-256 of the exact bytes. Both carry mutual-fund
    scheme rows in the thousands as well as companies; nothing is filtered out at fetch
    time, because a filter applied before storage is a filter nobody can audit later.
    """
    import nse_subscription as NSE
    f = NSE.Fetcher()
    if not f.warm():
        raise RuntimeError("NSE warm-up/robots check failed; nothing fetched")
    out = {}
    for name, dest in RENAME_FILES:
        wait_if_paused()
        q.gap()
        url = RENAME_ARCHIVE + name
        try:
            r = f.s.get(url, timeout=60, headers={"Referer": "https://www.nseindia.com/"})
        except Exception as e:                                  # noqa: BLE001
            log_fetch(url, "error", 0, f"{type(e).__name__}: {str(e)[:60]}")
            print(f"  {name:24s} FAILED {type(e).__name__}")
            continue
        sha = hashlib.sha256(r.content).hexdigest()
        log_fetch(url, r.status_code, len(r.content), sha)
        if r.status_code != 200:
            print(f"  {name:24s} HTTP {r.status_code}")
            continue
        d = pd.read_csv(io.StringIO(r.text))
        d.columns = [c.strip() for c in d.columns]
        d["source_url"] = url
        d["source_sha256"] = sha
        d["fetched_at_ist"] = str(pd.Timestamp.now())
        d.to_csv(dest, index=False, encoding="utf-8")
        print(f"  {name:24s} {len(d):6d} rows -> {dest.name}")
        out[name] = d
    return out


# ------------------------------------------------------------------ index history
def fetch_indices(q: Queue, start="2009-01-01", end=None,
                  only: list[str] | None = None) -> pd.DataFrame:
    """Total-return level history for every index in WANT_INDICES, appended and resumable.

    Appended, not rewritten (rule 11): a kill mid-index leaves what it fetched, and a
    re-run skips any (index, date) already on disk.
    """
    import requests
    want = [i for i in (only or WANT_INDICES)]
    end = pd.Timestamp(end or pd.Timestamp.today().normalize())
    have = set()
    if INDEX_HISTORY.exists():
        prev = pd.read_csv(INDEX_HISTORY)
        have = set(zip(prev["index_name"].astype(str), prev["date"].astype(str)))
        print(f"  {len(prev)} rows already on disk across "
              f"{prev['index_name'].nunique()} indices")
    s = requests.Session()
    s.headers.update(NIFTY_HDR)
    wait_if_paused()
    q.gap()
    r = s.get(NIFTY_PAGE, timeout=40)
    log_fetch(NIFTY_PAGE, r.status_code, len(r.content), "session cookies")
    n_tot = 0
    for name in want:
        a, got = pd.Timestamp(start), 0
        while a <= end:
            b = min(a + pd.Timedelta(days=360), end)
            wait_if_paused()
            q.gap()
            cinfo = (f"{{'name':'{name}','startDate':'{a:%d-%b-%Y}',"
                     f"'endDate':'{b:%d-%b-%Y}','indexName':'{name}'}}")
            try:
                rr = s.post(NIFTY_TRI_URL, data=json.dumps({"cinfo": cinfo}), timeout=60,
                            headers={"Content-Type": "application/json; charset=utf-8"})
                chunk = json.loads(rr.text)
                log_fetch(NIFTY_TRI_URL, rr.status_code, len(rr.content),
                          f"{name} {a:%Y-%m-%d}..{b:%Y-%m-%d} rows={len(chunk)}")
            except Exception as e:                              # noqa: BLE001
                log_fetch(NIFTY_TRI_URL, "error", 0,
                          f"{name} {a:%Y-%m-%d}: {type(e).__name__}")
                print(f"    {name:26s} {a:%Y-%m-%d}: FAILED {type(e).__name__} "
                      f"- left as a gap, not filled")
                a = b + pd.Timedelta(days=1)
                continue
            rows = []
            for x in chunk:
                dt = pd.to_datetime(x.get("Date"), format="%d %b %Y", errors="coerce")
                lvl = pd.to_numeric(x.get("TotalReturnsIndex"), errors="coerce")
                if pd.isna(dt) or pd.isna(lvl):
                    continue
                key = (name, str(dt.date()))
                if key in have:
                    continue
                have.add(key)
                rows.append({"index_name": name, "date": str(dt.date()),
                             "tri": float(lvl),
                             "source": "niftyindices getTotalReturnIndexString",
                             "fetched_at_ist": str(pd.Timestamp.now())})
            if rows:
                pd.DataFrame(rows).to_csv(INDEX_HISTORY, mode="a",
                                          header=not INDEX_HISTORY.exists(),
                                          index=False, encoding="utf-8")
                got += len(rows)
            a = b + pd.Timedelta(days=1)
        n_tot += got
        print(f"  {name:28s} +{got} rows")
    print(f"  wrote {INDEX_HISTORY.name}: +{n_tot} new rows this run")
    return pd.read_csv(INDEX_HISTORY)


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

    print("[1] the live path owns NSE during the HDFIRE window")
    chk("13 Oct 11:00 IST is paused",
        paused_now(pd.Timestamp("2026-10-13 11:00"))[0])
    chk("13 Oct 16:29 is still paused",
        paused_now(pd.Timestamp("2026-10-13 16:29"))[0])
    chk("13 Oct 16:30 is free again",
        not paused_now(pd.Timestamp("2026-10-13 16:30"))[0])
    chk("13 Oct 02:00 is free",
        not paused_now(pd.Timestamp("2026-10-13 02:00"))[0])
    chk("13 Oct 19:30 is paused for the day-end capture",
        paused_now(pd.Timestamp("2026-10-13 19:30"))[0])
    chk("16 Oct 11:00 is free - the window is three dates, not a standing rule",
        not paused_now(pd.Timestamp("2026-10-16 11:00"))[0])
    chk("and the pause says WHY, so a stalled batch is explicable",
        "priority window" in paused_now(pd.Timestamp("2026-10-13 11:00"))[1])

    print("\n[2] the sector mapping never forces a benchmark")
    chk("a sector with a real index maps to it",
        SECTOR_TO_INDEX["information technology"] == "NIFTY IT")
    chk("capital goods maps to NOTHING",
        SECTOR_TO_INDEX.get("capital goods") is None)
    chk("and the reason is recorded rather than left blank",
        "Capital Goods" in NO_INDEX_REASON["capital goods"])
    chk("every mapped index is one of the 15 the live capture stores",
        all(v in WANT_INDICES for v in SECTOR_TO_INDEX.values()),
        [v for v in SECTOR_TO_INDEX.values() if v not in WANT_INDICES])
    chk("no sector is in both the mapping and the declined list",
        not (set(SECTOR_TO_INDEX) & set(NO_INDEX_REASON)))
    chk("Nifty 50 is fetched too, since every relative number needs it",
        "NIFTY 50" in WANT_INDICES)

    print("\n[3] the gap is shared, not per-call")
    q = Queue()
    t0 = time.time()
    q.gap()
    q.gap()
    chk("two consecutive requests are at least 3 s apart (rule 9)",
        time.time() - t0 >= GAP_S - 0.05, time.time() - t0)

    print(f"\n{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["sectors", "indices", "renames", "all"])
    ap.add_argument("--only", help="comma-separated index names, for --stage indices")
    ap.add_argument("--start", default="2009-01-01")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if not a.stage:
        ap.error("--stage is required")
    q = Queue()
    print(f"model_h_sources: start {pd.Timestamp.now()} IST")
    if a.stage in ("sectors", "all"):
        print("\n=== stage sectors (2.4b)")
        fetch_sectors(q)
        write_missing_sectors()
    if a.stage in ("renames", "all"):
        print(chr(10) + "=== stage renames (2.1)")
        fetch_renames(q)
    if a.stage in ("indices", "all"):
        print("\n=== stage indices (2.4c / 2.4d / 2.4f)")
        fetch_indices(q, start=a.start,
                      only=[x.strip() for x in a.only.split(",")] if a.only else None)
    print(f"\nmodel_h_sources: done {pd.Timestamp.now()} IST")

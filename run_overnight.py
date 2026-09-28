"""
run_overnight.py — unattended. Start it, close the laptop lid setting, go to sleep.

Does three jobs in order, each resumable:
  JOB 1  resolve missing symbols / ISINs / listing dates for the master dataset
           1a  complete truncated "..." names against the trackers   (offline)
           1b  join master <-> trackers <-> NSE spine on name + date  (offline)
           1c  Yahoo search for whatever is still missing             (network)
  JOB 2  build the holding target (excess_1y vs Nifty) for everything resolved
  JOB 3  pull full price history for post-listing diagnostics

Every job checkpoints after each record. Kill it and restart — it resumes.

    python run_overnight.py            # all jobs
    python run_overnight.py --job 2    # one job
"""
from __future__ import annotations
import argparse, json, time, sys
from collections import Counter
from pathlib import Path
import pandas as pd, numpy as np

import dataio

CKPT = Path(__file__).resolve().parent / "checkpoints"; CKPT.mkdir(exist_ok=True)
LOG  = Path(__file__).resolve().parent / "run_log.txt"
MASTER_CSV = "master_with_symbols.csv"

MATCH_DAYS = 7        # issue-open date window for name matching
MATCH_SIM  = 0.85     # dataio.prefix_sim threshold
SYMBOL_MATCH_DAYS = 10  # 1c: first trading day within this many days of listing date
MAX_FIRST_BAR_LAG = 30  # derived listing date must be within this many days of issue open


def log(msg: str) -> None:
    line = f"{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_ckpt(name: str) -> dict:
    p = CKPT / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_ckpt(name: str, d: dict) -> None:
    (CKPT / f"{name}.json").write_text(json.dumps(d), encoding="utf-8")


def read_master() -> pd.DataFrame:
    return pd.read_csv(MASTER_CSV, parse_dates=["issue_open_date", "listing_date"])


# ======================================================================
# JOB 1 — resolve missing symbols
# ======================================================================
def _best_match(name, date, cands: pd.DataFrame):
    """Unique best candidate within ±MATCH_DAYS and ≥MATCH_SIM, else (None, reason).
    A tie between two *different* companies is ambiguous and returns None.

    The window is tested against the candidate's issue-open AND listing date: the
    master's 'issue_open_date' column actually holds the listing date (in every clean
    cross-check against trackers + NSE spine, 2021-2026 — see CLAUDE.md)."""
    if pd.isna(date):
        return None, "no issue date"
    win = pd.Timedelta(days=MATCH_DAYS)
    w = cands[((cands["issue_open_date"] - date).abs() <= win) |
              ((cands["listing_date"] - date).abs() <= win)]
    scored = sorted(((dataio.prefix_sim(name, c), i) for i, c in w["company"].items()),
                    reverse=True)
    scored = [s for s in scored if s[0] >= MATCH_SIM]
    if not scored:
        return None, "no candidate"
    top = [i for s, i in scored if s == scored[0][0]]
    if len({dataio.norm_name(cands.at[i, "company"]) for i in top}) > 1:
        return None, "ambiguous: " + " | ".join(str(cands.at[i, "company"]) for i in top)
    return cands.loc[top[0]], f"sim={scored[0][0]:.2f}"


def _agree(vals: dict):
    """Reconcile a field across sources: all non-null values must agree, else NULL."""
    vals = {k: v for k, v in vals.items() if pd.notna(v) and str(v).strip() not in ("", "-")}
    if not vals:
        return None, None, False
    norm = {k: (v.normalize() if isinstance(v, pd.Timestamp) else str(v).strip().upper())
            for k, v in vals.items()}
    if len(set(norm.values())) > 1:
        return None, None, True
    k = next(iter(vals))
    return vals[k], "+".join(sorted(vals)), False


def job1_stage_a(master: pd.DataFrame, trackers: pd.DataFrame) -> pd.DataFrame:
    """Complete truncated '...' names from the trackers."""
    trunc = master["company"].map(dataio.is_truncated)
    log(f"  1a  truncated names: {trunc.sum()}")
    if "company_as_listed" not in master:
        master["company_as_listed"] = master["company"]
    fails = []
    done = 0
    for i in master.index[trunc]:
        m, why = _best_match(master.at[i, "company"], master.at[i, "issue_open_date"], trackers)
        if m is None:
            fails.append(f"{master.at[i, 'company']} ({why})")
            continue
        master.at[i, "company"] = str(m["company"]).strip()
        done += 1
    log(f"  1a  completed {done}/{trunc.sum()} truncated names")
    for f in fails:
        log(f"      unmatched: {f}")
    return master


def job1_stage_b(master: pd.DataFrame, trackers: pd.DataFrame,
                 spine: pd.DataFrame) -> pd.DataFrame:
    """Join master to trackers and NSE spine on name + issue date. Fill only empty
    fields; any disagreement between sources leaves the field NULL and is logged."""
    for c in ("symbol_source", "isin_source", "listing_date_source"):
        if c not in master:
            master[c] = None
    master.loc[master["symbol"].notna() & master["symbol_source"].isna(),
               "symbol_source"] = "master_prebuilt"
    master["isin"] = master["isin"].astype(object)
    master["bse_code"] = master["bse_code"].astype(object)

    got = Counter(); conflicts = []
    need = master["symbol"].isna() | master["isin"].isna() | master["listing_date"].isna()
    log(f"  1b  rows missing symbol/isin/listing_date: {need.sum()} "
        f"(symbol missing: {master['symbol'].isna().sum()})")

    for i in master.index[need]:
        name, date = master.at[i, "company"], master.at[i, "issue_open_date"]
        t, _ = _best_match(name, date, trackers)
        s, _ = _best_match(name, date, spine)
        if t is None and s is None:
            continue
        got["matched_any"] += 1
        fields = {
            "symbol":       {"tracker": None if t is None else t["symbol"],
                             "nse_spine": None if s is None else s["symbol"]},
            "isin":         {"tracker": None if t is None else t["isin"]},
            "listing_date": {"tracker": None if t is None else t["listing_date"],
                             "nse_spine": None if s is None else s["listing_date"]},
            "bse_code":     {"tracker": None if t is None else t["bse_code"]},
        }
        for f, vals in fields.items():
            if pd.notna(master.at[i, f]):
                continue
            v, src, clash = _agree(vals)
            if clash:
                conflicts.append({"company": name, "field": f,
                                  **{k: str(x) for k, x in vals.items()}})
                continue
            if v is None:
                continue
            if f == "bse_code":
                v = str(int(float(v)))
            master.at[i, f] = v
            if f in ("symbol", "isin", "listing_date"):
                master.at[i, f"{f}_source"] = src
            got[f] += 1

    pd.DataFrame(conflicts).to_csv("job1b_CONFLICTS.csv", index=False)
    log(f"  1b  matched {got['matched_any']} rows | recovered symbol={got['symbol']} "
        f"isin={got['isin']} listing_date={got['listing_date']} bse_code={got['bse_code']} "
        f"| source conflicts left NULL: {len(conflicts)} (job1b_CONFLICTS.csv)")
    return master


def job1_stage_c(master: pd.DataFrame) -> pd.DataFrame:
    """Yahoo search, only for rows still missing a symbol."""
    import yfinance as yf
    import requests

    todo = master[master["symbol"].isna()]
    done = load_ckpt("symbols")
    log(f"  1c  residual for Yahoo search: {len(todo)} | {len(done)} already in checkpoint")

    for i, r in todo.iterrows():
        # checkpoint key is the CLEANED query: rows cached as misses under the old
        # raw-name query (which Yahoo silently returned [] for) get retried
        cid = "q2:" + dataio.yahoo_query(r["company"])
        if cid in done:
            continue
        found = None
        try:
            q = requests.get("https://query2.finance.yahoo.com/v1/finance/search",
                             params={"q": cid[3:], "quotesCount": 8},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            for it in q.json().get("quotes", []):
                sym = it.get("symbol", "")
                if sym.endswith((".NS", ".BO")):
                    # VERIFY: first trading day must be within SYMBOL_MATCH_DAYS of the
                    # listing date (the master's date column IS the listing date), else
                    # it's a namesake, an FPO of an already-listed company, or a gap
                    h = yf.Ticker(sym).history(period="max", auto_adjust=True)
                    if len(h) == 0:
                        continue
                    first = h.index[0].tz_localize(None)
                    if abs((first - r["issue_open_date"]).days) <= SYMBOL_MATCH_DAYS:
                        found = sym.replace(".NS", "").replace(".BO", "")
                        break
        except Exception as e:
            log(f"    {cid[:40]}: {e}")

        done[cid] = found
        save_ckpt("symbols", done)
        if len(done) % 20 == 0:
            log(f"  1c  progress {len(done)}/{len(todo)}  "
                f"resolved={sum(1 for v in done.values() if v)}")
        time.sleep(0.8)

    key = master["company"].map(lambda c: "q2:" + dataio.yahoo_query(c))
    hit = master["symbol"].isna() & key.map(lambda k: bool(done.get(k)))
    master.loc[hit, "symbol"] = key[hit].map(done)
    master.loc[hit, "symbol_source"] = "yahoo_search"
    log(f"  1c  recovered {hit.sum()}/{len(todo)} via Yahoo search")
    return master


def job1_resolve_symbols():
    log("JOB 1 — resolving missing symbols (1a names -> 1b joins -> 1c Yahoo)")
    master = read_master()
    before = master["symbol"].notna().sum()
    trackers = dataio.load_trackers()
    spine = dataio.load_nse_spine()
    spine = spine[spine["security_type"].isin(["EQ", "SME", "BE", "IV", "RR"])]

    master = job1_stage_a(master, trackers)
    master = job1_stage_b(master, trackers, spine)
    master.to_csv(MASTER_CSV, index=False)          # offline stages are cheap; save now
    after_b = master["symbol"].notna().sum()

    master = job1_stage_c(master)
    master.to_csv(MASTER_CSV, index=False)
    n = master["symbol"].notna().sum()
    log(f"JOB 1 done — symbols {before} -> {after_b} (after 1a+1b) -> {n} (after 1c) "
        f"of {len(master)} rows")


# ======================================================================
# JOB 2 — holding targets (excess return vs benchmark over a horizon)
# ======================================================================
HORIZONS = {"1y": 365, "3y": 1095}
TARGET_FILES = {"1y": ("holding_target.csv", "target_MISSES.csv"),
                "3y": ("holding_target_3y.csv", "target_MISSES_3y.csv")}
LABEL_COL = {"1y": "H_label", "3y": "H3_label"}


def load_benchmark(name: str) -> pd.Series:
    """'nifty50_tri' — official NSE Indices Total Return Index (data/NIFTY50_TRI.csv,
    fetched by fetch_nifty_tri.py). 'nsei' — ^NSEI price index from Yahoo, which omits
    dividends (~1.3pp/yr bias in the IPO's favour, since IPO prices are dividend-adjusted)."""
    if name == "nifty50_tri":
        return dataio.load_nifty_tri()
    import yfinance as yf
    n = yf.Ticker("^NSEI").history(start="2009-01-01", auto_adjust=True)["Close"]
    n.index = n.index.tz_localize(None).normalize()
    return n


def _series(yf, sym, anchor, days_after, near_days):
    """Price series from .NS or .BO. Prefer the exchange whose first bar is within
    near_days of the anchor: a BSE-first IPO's .NS series can start years later."""
    fallback = None
    for suf in (".NS", ".BO"):
        try:
            h = yf.Ticker(sym + suf).history(start=anchor - pd.Timedelta(days=5),
                                             end=anchor + pd.Timedelta(days=days_after),
                                             auto_adjust=True)["Close"]
            h.index = h.index.tz_localize(None)
        except Exception:
            continue
        if len(h) > 20:
            if (h.index[0] - anchor).days <= near_days:
                return h
            if fallback is None:
                fallback = h
    return fallback


def job2_build_target(horizon: str = "1y", benchmark: str = "nifty50_tri"):
    """excess_<h> = IPO return (listing close -> listing + horizon) - benchmark return
    over the same two dates. Rows with an exclude_reason are skipped (not misses).

    Listing date, single source of truth:
      known    — real listing date in master (from master / trackers / NSE spine)
      derived  — first trading day of the yfinance series on or after the master date
      dropped  — no price series at all, or a series that can't give a listing date
                 honestly (bars before the date, or first bar long after it)."""
    import yfinance as yf
    days = HORIZONS[horizon]
    out_csv, miss_csv = TARGET_FILES[horizon]
    lab = LABEL_COL[horizon]
    log(f"JOB 2 — building holding target excess_{horizon} vs {benchmark}")

    bench = load_benchmark(benchmark)
    df = read_master()
    n_flag = int(df["exclude_reason"].notna().sum()) if "exclude_reason" in df else 0
    if "exclude_reason" in df:
        df = df[df["exclude_reason"].isna()]
    df = df[df["symbol"].notna()].copy()
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days + 5)
    cutoff = min(cutoff, bench.index.max() - pd.Timedelta(days=days))   # benchmark must reach T+h
    known = df["listing_date"].notna()
    df = df[(known & (df["listing_date"] <= cutoff)) |
            (~known & (df["issue_open_date"] <= cutoff))]
    log(f"  flagged rows skipped: {n_flag} | candidates: {len(df)} IPOs "
        f"({known.loc[df.index].sum()} known listing date, {(~known.loc[df.index]).sum()} to derive)")

    def at(series, d):
        s = series[series.index >= d]
        return (float(s.iloc[0]), s.index[0]) if len(s) else (np.nan, pd.NaT)

    ck = f"target_{horizon}_{benchmark}"
    done = load_ckpt(ck)
    rows, misses, paths = [], [], Counter()
    for i, r in df.iterrows():
        cid = str(r["symbol"])
        c = done.get(cid)
        if isinstance(c, dict) and "path" in c:          # cached result
            paths[c["path"]] += 1
            (rows.append(c["rec"]) if c["rec"] else misses.append(c["miss"]))
            continue

        rec, miss = None, None
        has_known = pd.notna(r["listing_date"])
        anchor = r["listing_date"] if has_known else r["issue_open_date"]
        extra = 0 if has_known else MAX_FIRST_BAR_LAG
        px = _series(yf, cid, anchor, days + extra + 20, near_days=extra + 7)

        def drop(path, reason):
            return path, {"symbol": cid, "company": r["company"], "reason": reason}

        if px is None:
            path, miss = drop("dropped_no_series",
                              "no price series — delisted/suspended/renamed")
        elif has_known:
            path, d0 = "known", r["listing_date"]
        else:
            d0 = px.index[0]
            if (px.index < r["issue_open_date"]).any():
                path, miss = drop("dropped_bad_series",
                                  "bars before listing date — symbol likely not this IPO")
            elif (d0 - r["issue_open_date"]).days > MAX_FIRST_BAR_LAG:
                path, miss = drop("dropped_bad_series",
                                  f"first bar {(d0 - r['issue_open_date']).days}d after "
                                  "master date — listing date not derivable")
            elif d0 > cutoff:
                path, miss = drop("dropped_not_seasoned", f"listed < {days + 5} days ago")
            else:
                path = "derived"

        if miss is None:
            d1 = d0 + pd.Timedelta(days=days)
            p0, dd0 = at(px, d0); p1, dd1 = at(px, d1)
            n0, _ = at(bench, dd0); n1, _ = at(bench, dd1)
            if any(pd.isna(x) for x in (p0, p1, n0, n1)):
                path, miss = drop("dropped_short_history",
                                  f"history too short to reach T+{days}")
            elif (dd0 - d0).days > 7:
                path, miss = drop("dropped_bad_series",
                                  f"first bar {(dd0 - d0).days}d after known listing date")
            else:
                ipo_r = (p1 / p0 - 1) * 100
                b_r = (n1 / n0 - 1) * 100
                rec = {"symbol": cid, "company": r["company"], "isin": r.get("isin"),
                       "listing_date": str(d0.date()), "listing_date_source": path,
                       "listing_close": p0, f"price_t{days}": p1,
                       f"ipo_ret_{horizon}_pct": ipo_r, f"bench_ret_{horizon}_pct": b_r,
                       f"excess_{horizon}_pp": ipo_r - b_r, lab: int(ipo_r - b_r > 0),
                       "benchmark": benchmark}

        paths[path] += 1
        (rows.append(rec) if rec else misses.append(miss))
        done[cid] = {"path": path, "rec": rec, "miss": miss}
        save_ckpt(ck, done)
        if len(done) % 25 == 0:
            log(f"  progress {len(done)}/{len(df)}  built={len(rows)}  missed={len(misses)}")
        time.sleep(0.3)

    out = pd.DataFrame(rows)
    out.to_csv(out_csv, index=False)
    pd.DataFrame(misses).to_csv(miss_csv, index=False)
    log(f"JOB 2 [{horizon}, {benchmark}] done — target built for {len(out)}, missed {len(misses)}")
    log("  listing-date paths: " + ", ".join(f"{k}={v}" for k, v in sorted(paths.items())))
    if len(out):
        log(f"  BASE RATE {lab}=1 (beat {benchmark} over {horizon}): {out[lab].mean()*100:.1f}%")
        log(f"  median excess_{horizon} = {out[f'excess_{horizon}_pp'].median():+.1f} pp")
        log(f"  *** {len(misses)} dropouts are disproportionately failures — base rate is OPTIMISTIC")
    return out


# ======================================================================
# JOB 3 — price history for diagnostics
# ======================================================================
def job3_price_history():
    import yfinance as yf
    log("JOB 3 — price history / drawdown / volatility")
    df = read_master()
    df = df[df["symbol"].notna()]
    done = load_ckpt("prices"); rows = []
    for i, r in df.iterrows():
        cid = str(r["symbol"])
        if cid in done:
            if done[cid]: rows.append(done[cid])
            continue
        # first bar on/after listing (or issue open, if listing date unknown) = listing day
        start = r["listing_date"] if pd.notna(r["listing_date"]) else r["issue_open_date"]
        rec = None
        for suf in (".NS", ".BO"):
            try:
                h = yf.Ticker(cid + suf).history(start=start, auto_adjust=True)["Close"]
                if len(h) > 20:
                    b = float(h.iloc[0])
                    rec = {"symbol": cid, "current_price": float(h.iloc[-1]),
                           "ret_todate_pct": (h.iloc[-1] / b - 1) * 100,
                           "max_drawdown_pct": float(((h / h.cummax()) - 1).min() * 100),
                           "ann_vol_pct": float(h.pct_change().std() * np.sqrt(252) * 100)}
                    break
            except Exception:
                pass
        done[cid] = rec; save_ckpt("prices", done)
        if rec: rows.append(rec)
        if len(done) % 25 == 0: log(f"  progress {len(done)}/{len(df)}")
        time.sleep(0.3)
    pd.DataFrame(rows).to_csv("price_history.csv", index=False)
    log(f"JOB 3 done — {len(rows)} symbols")


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, default=0)
    a = ap.parse_args()
    log("="*60); log("OVERNIGHT RUN START")
    try:
        if a.job in (0, 1): job1_resolve_symbols()
        if a.job in (0, 2):
            job2_build_target("1y")
            job2_build_target("3y")
        if a.job in (0, 3): job3_price_history()
        log("ALL JOBS COMPLETE")
    except KeyboardInterrupt:
        log("interrupted — checkpoints saved, rerun to resume")
    except Exception as e:
        log(f"FATAL: {e}")
        raise

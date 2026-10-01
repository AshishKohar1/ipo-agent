"""
ingest_outcomes.py — PLAN Stage 6 step 5. Runs Mon & Thu 08:00 IST.

Finds every IPO listed since the last run — mainboard and SME, bid or not — gets its listing
price from two sources, reconciles them under rule 2, appends the row to the dataset, and
scores the matching rows in `predictions_log.csv`.

**Two sources, always.** A listing gain from one source is not ingested, because the whole
target depends on it: `listing_gain` is what L1 and L2 are measured against, so a single bad
value corrupts the label and every threshold derived from it. Sources:

  1. the NSE official historical-quote API
  2. the BSE official historical API

**yfinance is NOT one of them, and must not be.** Its stored series for Indian tickers is
adjusted for later splits and bonuses, and `auto_adjust=False` does not undo it: Syngene's
2015 listing comes back at Rs 147.50 against a Rs 250 offer price, because of its 2017 1:1
bonus. Comparing an adjusted price to an unadjusted offer price produces a listing gain of
-38% where the true figure is positive, and the error grows with the age of the issue. It is
kept below only as a corroboration channel, clearly labelled, and never enters the gain.

(The existing `Listing Gain` column in the master dataset is unaffected — it does not come
from yfinance. Model H's `excess_1y` is also unaffected, because it is a ratio of two points
on the same adjusted series.)

Max pairwise relative difference above 5% → the row is written with `listing_gain = NULL`
and **both** values logged (rule 2). Nothing is estimated or filled.

Outcomes are appended as *separate* rows keyed to `prediction_id`; a prediction row is never
rewritten (`predictions_log.py`).

    python ingest_outcomes.py                 # since the last run
    python ingest_outcomes.py --since 2026-09-01
    python ingest_outcomes.py --dry-run
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import sys
import time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import predictions_log as PL        # noqa: E402

STATE = ROOT / "data" / "ingest_state.json"
NEW_LISTINGS = ROOT / "data" / "new_listings.csv"
TOL = 0.05                          # rule 2
MIN_GAP_S = 3.2

NEW_COLS = ["ipo", "isin", "symbol", "segment", "listing_date", "offer_price",
            "listing_open", "listing_close", "listing_gain_pct", "gain_source_a",
            "gain_source_b", "rel_diff_pct", "reconciled", "note", "ingested_at"]


def last_run() -> pd.Timestamp:
    if STATE.exists():
        try:
            return pd.Timestamp(json.loads(STATE.read_text())["last_run"])
        except Exception:
            pass
    return pd.Timestamp.today().normalize() - pd.Timedelta(days=7)


def save_state(when: pd.Timestamp, n: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_run": str(when), "ingested": n}, indent=2),
                     encoding="utf-8")


# ---------------------------------------------------------------- calendar
def newly_listed(since: pd.Timestamp) -> pd.DataFrame:
    """IPOs whose listing date falls after `since`, from the Chittorgarh harvest.

    The harvest already records `listed_on` per company and is refreshed by the night
    sweep, so no extra request is needed to find them. When the sweep has not run, this
    returns empty and says so rather than guessing at a calendar.
    """
    p = ROOT / "data" / "chittorgarh_backfill.csv"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_csv(p, keep_default_na=False, na_values=[""])
    d["listed"] = pd.to_datetime(d["listed_on"], errors="coerce", format="mixed")
    out = d[d["listed"].notna() & (d["listed"] > since)].copy()
    # The upper end of the price band is the offer price for a book-built issue. A brand-new
    # listing is not in the master yet, so without this the offer price is unknown and no
    # gain can be computed for exactly the IPOs this job exists to ingest.
    out["offer_price_cg"] = out["price_band"].astype(str).str.findall(
        r"([\d,]+(?:\.\d+)?)").apply(
        lambda xs: max(float(x.replace(",", "")) for x in xs) if xs else None)
    out = out[["company", "listed", "issue_size_cr", "price_band", "offer_price_cg",
               "total_subscription_x", "qib_x", "nii_x", "retail_x", "url"]]
    return out.rename(columns={"company": "ipo", "listed": "listing_date"})


# ---------------------------------------------------------------- prices, two sources
def price_yfinance(symbol: str, listing_date) -> dict:
    try:
        import yfinance as yf
        t = yf.Ticker(f"{symbol}.NS")
        # auto_adjust=False is NOT optional here. yfinance adjusts for later splits and
        # bonuses by default, so Syngene's 2015 listing comes back at Rs 152 against a Rs 250
        # offer price -- a listing gain of -39% where the real figure is positive, because of
        # its 2017 bonus. Every ingested label would have been wrong for any company that has
        # since split or issued a bonus, and the error grows with age.
        h = t.history(start=pd.Timestamp(listing_date) - pd.Timedelta(days=2),
                      end=pd.Timestamp(listing_date) + pd.Timedelta(days=5),
                      auto_adjust=False)
        if h is None or not len(h):
            return {"ok": False, "why": "no bars returned"}
        first = h.iloc[0]
        return {"ok": True, "open": float(first["Open"]), "close": float(first["Close"]),
                "bar_date": str(h.index[0].date()), "source": "yfinance_unadjusted"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def price_official(symbol: str, listing_date) -> dict:
    """NSE's official quote endpoint. NSE_DOWNLOADS_ALLOWED does not apply — this is the
    quote API, not a gated offer document."""
    try:
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": "ipo-agent/1.0 (personal research)",
                          "Accept": "application/json"})
        s.headers.update({"Referer": "https://www.nseindia.com/report-detail/eq_security",
                          "Accept-Language": "en-US,en;q=0.9"})
        s.get("https://www.nseindia.com/", timeout=20)
        time.sleep(1.0)
        s.get("https://www.nseindia.com/get-quotes/equity", params={"symbol": symbol},
              timeout=20)                    # second hop: the API needs this cookie
        time.sleep(1.0)
        r = s.get("https://www.nseindia.com/api/historical/cm/equity",
                  params={"symbol": symbol,
                          "from": (pd.Timestamp(listing_date)).strftime("%d-%m-%Y"),
                          "to": (pd.Timestamp(listing_date) +
                                 pd.Timedelta(days=5)).strftime("%d-%m-%Y")},
                  timeout=30)
        if r.status_code != 200:
            return {"ok": False, "why": f"HTTP {r.status_code}"}
        rows = (r.json() or {}).get("data") or []
        if not rows:
            return {"ok": False, "why": "no rows"}
        rows = sorted(rows, key=lambda x: x.get("CH_TIMESTAMP", ""))
        f = rows[0]
        return {"ok": True, "open": float(f["CH_OPENING_PRICE"]),
                "close": float(f["CH_CLOSING_PRICE"]),
                "bar_date": f.get("CH_TIMESTAMP"), "source": "nse_official"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def price_bse(bse_code: str | int | None, listing_date) -> dict:
    """BSE's official historical endpoint. Unadjusted, which is what a listing gain needs."""
    if not bse_code:
        return {"ok": False, "why": "no BSE code"}
    try:
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": "ipo-agent/1.0 (personal research)",
                          "Accept": "application/json",
                          "Referer": "https://www.bseindia.com/"})
        d = pd.Timestamp(listing_date)
        r = s.get("https://api.bseindia.com/BseIndiaAPI/api/StockPriceCSVDownload/w",
                  params={"pageType": "0", "scripcode": str(int(bse_code)),
                          "fromdate": d.strftime("%d/%m/%Y"),
                          "todate": (d + pd.Timedelta(days=5)).strftime("%d/%m/%Y")},
                  timeout=30)
        if r.status_code != 200 or not r.text.strip():
            return {"ok": False, "why": f"HTTP {r.status_code}"}
        import io as _io
        df = pd.read_csv(_io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        if not len(df):
            return {"ok": False, "why": "no rows"}
        f = df.iloc[0]
        return {"ok": True, "open": float(f.get("open price", f.get("open"))),
                "close": float(f.get("close price", f.get("close"))),
                "bar_date": str(f.get("date")), "source": "bse_official"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def reconcile_gain(offer: float | None, a: dict, b: dict) -> dict:
    """Listing gain from two independent sources, under rule 2."""
    if not offer or offer <= 0:
        return {"listing_gain_pct": None, "reconciled": "no_offer_price",
                "note": "offer price unknown, so no gain can be computed"}
    gains, srcs = [], []
    for r in (a, b):
        if r.get("ok"):
            gains.append((r["close"] - offer) / offer * 100.0)
            srcs.append(r["source"])
    if not gains:
        return {"listing_gain_pct": None, "reconciled": "no_source",
                "note": f"both sources failed: {a.get('why')} | {b.get('why')}"}
    if len(gains) == 1:
        return {"listing_gain_pct": None, "gain_source_a": gains[0],
                "reconciled": "single_source_REJECTED",
                "note": f"only {srcs[0]} returned a price. A single source is NOT ingested: "
                        "listing_gain is the label L1 and L2 are measured against, so one "
                        "bad value corrupts every threshold derived from it (rule 2)."}
    hi = max(abs(g) for g in gains) or 1.0
    diff = abs(gains[0] - gains[1]) / hi
    if diff > TOL:
        return {"listing_gain_pct": None, "gain_source_a": gains[0],
                "gain_source_b": gains[1], "rel_diff_pct": round(diff * 100, 3),
                "reconciled": "MISMATCH -> NULL",
                "note": f"{srcs[0]} {gains[0]:.2f}% vs {srcs[1]} {gains[1]:.2f}% differ by "
                        f"{diff*100:.1f}% (> 5%); both logged, value NULL (rule 2)"}
    return {"listing_gain_pct": round(sum(gains) / len(gains), 4),
            "gain_source_a": gains[0], "gain_source_b": gains[1],
            "rel_diff_pct": round(diff * 100, 3), "reconciled": "PASS",
            "note": f"{srcs[0]} and {srcs[1]} agree within {diff*100:.2f}%"}


# ---------------------------------------------------------------- main
def main(since: str | None = None, dry: bool = False) -> pd.DataFrame:
    start = pd.Timestamp(since) if since else last_run()
    now = pd.Timestamp.now()
    print(f"ingesting IPOs listed after {start.date()}")

    cand = newly_listed(start)
    print(f"  {len(cand)} newly listed found in the harvest")
    if not len(cand):
        print("  nothing to ingest. (If the Chittorgarh sweep has not run, this is why — "
              "no calendar is guessed at.)")
        if not dry:
            save_state(now, 0)
        return pd.DataFrame()

    sym = pd.read_csv(ROOT / "master_with_symbols.csv")
    sym["norm"] = sym["company"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    rows, last = [], 0.0
    for r in cand.itertuples():
        norm = str(r.ipo).lower()
        norm = "".join(ch for ch in norm if ch.isalnum())
        m = sym[sym["norm"].str.startswith(norm[:14])] if len(norm) >= 6 else sym.iloc[0:0]
        symbol = m["symbol"].iloc[0] if len(m) else None
        isin = m["isin"].iloc[0] if len(m) else None
        offer = pd.to_numeric(m["Offer Price"], errors="coerce").iloc[0] if len(m) else None
        offer_src = "master"
        if offer is None or pd.isna(offer):
            offer = getattr(r, "offer_price_cg", None)
            offer_src = "chittorgarh_price_band (SINGLE SOURCE - flag it)"

        bse_code = m["bse_code"].iloc[0] if len(m) and "bse_code" in m else None
        a = b = {"ok": False, "why": "no symbol resolved"}
        corroboration = {"ok": False}
        if symbol:
            gap = MIN_GAP_S - (time.time() - last)
            if gap > 0:
                time.sleep(gap)
            last = time.time()
            a = price_official(symbol, r.listing_date)
            b = price_bse(bse_code, r.listing_date)
            corroboration = price_yfinance(symbol, r.listing_date)
        rec = reconcile_gain(offer, a, b)
        row = {"ipo": r.ipo, "isin": isin, "symbol": symbol, "segment": "mainboard",
               "listing_date": str(pd.Timestamp(r.listing_date).date()),
               "offer_price": offer,
               "listing_open": a.get("open") if a.get("ok") else b.get("open"),
               "listing_close": a.get("close") if a.get("ok") else b.get("close"),
               "ingested_at": str(now), **rec}
        row["note"] = (f"{row.get('note','')} | offer price from {offer_src}"
                       + (f" | yfinance corroboration close "
                          f"{corroboration['close']:.2f} (ADJUSTED series - not used in the "
                          f"gain)" if corroboration.get("ok") else ""))
        rows.append(row)
        print(f"  {str(r.ipo)[:34]:36s} {str(symbol):12s} "
              f"gain={rec.get('listing_gain_pct')} {rec['reconciled']}")

    out = pd.DataFrame([{c: r.get(c) for c in NEW_COLS} for r in rows], columns=NEW_COLS)
    if dry:
        print("\n--dry-run: nothing written")
        return out
    out.to_csv(NEW_LISTINGS, mode="a", header=not NEW_LISTINGS.exists(), index=False,
               encoding="utf-8")

    # score any matching predictions
    log = PL.load()
    preds = log[log["row_type"] == "prediction"] if len(log) else log
    n_scored = 0
    for r in out.itertuples():
        if r.listing_gain_pct is None or pd.isna(r.listing_gain_pct):
            continue
        hit = preds[preds["ipo"].astype(str).str.lower() == str(r.ipo).lower()]
        for h in hit.itertuples():
            PL.log_outcome(h.prediction_id, r.ipo, r.listing_date, r.listing_gain_pct,
                           note=f"reconciled {r.reconciled}")
            n_scored += 1
    save_state(now, len(out))
    print(f"\nwritten {len(out)} rows to data/new_listings.csv; "
          f"{n_scored} prediction(s) scored in predictions_log.csv")
    print(out["reconciled"].value_counts().to_string())
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.since, a.dry_run)

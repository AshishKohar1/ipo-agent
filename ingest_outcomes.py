"""
ingest_outcomes.py — the HARVEST half. Runs Mon & Thu 08:00 IST.

Finds every IPO that has listed since the last run — mainboard and SME, bid on or not —
resolves its identity (symbol, ISIN, segment) and appends a row to `data/new_listings.csv`.
That is how the training set grows: it is the only job that notices an IPO the user never
bid on, and the retrain needs those rows as much as the ones with predictions attached.

**It no longer prices anything** (Task 7, 2026-10-08). Prices come from exactly one place:
`listing_prices.py` reading the exchange bhavcopy **for the listing date itself**, run by
the 19:30 day-end leg. Rows are written with the price columns NULL and
`reconciled = pending_dayend_capture`.

Why the pricing was removed rather than fixed in place
------------------------------------------------------
Every one of the 15 rows this job had ever written carried `listing_gain_pct = NULL` and
`reconciled = no_source`. Its two sources were the NSE and BSE historical-**quote** APIs,
which refuse this host, rather than the bhavcopy archive, which does not.

And it ran Mon & Thu, so it priced listings up to three days after they listed. **A price
read later has been silently restated for any split or bonus since** — Syngene's real
Rs 295 open reads Rs 147.50 once its 2017 bonus is applied, turning +18% into −41%. That
is precisely what the Stage 27 standing rule exists to forbid, so a job that prices days
late cannot be made correct by fixing its endpoints. yfinance was in here as a
"corroboration" channel and is the worst offender for exactly that restatement; it is gone
with the rest.

    python ingest_outcomes.py                 # harvest since the last run
    python ingest_outcomes.py --since 2026-09-01
    python ingest_outcomes.py --dry-run
    python ingest_outcomes.py --backfill-prices    # fill NULL rows from their OWN
                                                   # archived bhavcopy date
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
import symbols as SY       # noqa: E402
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


def harvest_coverage() -> pd.Timestamp | None:
    """The latest listing date the Chittorgarh harvest actually covers.

    The watermark may never advance past this. `newly_listed()` reads its calendar from the
    harvest, so a harvest that stops at date D has examined nothing after D -- and a run that
    finds no candidates because the night sweep has not refreshed has not established that
    nothing listed, only that it could not look. Advancing `last_run` to `now` in that case
    skips the unexamined window *permanently*: those listings are never candidates again, and
    `listing_gain` is the label L1 and L2 are measured against, so the loss is silent and
    uncorrectable by inspection. Clamping is also duplicate-safe, because `newly_listed()`
    filters on `listed > since` strictly, so rows dated exactly D stay excluded.
    """
    p = ROOT / "data" / "chittorgarh_backfill.csv"
    if not p.exists():
        return None
    try:
        d = pd.read_csv(p, usecols=["listed_on"], keep_default_na=False, na_values=[""])
        m = pd.to_datetime(d["listed_on"], errors="coerce", format="mixed").max()
        return None if pd.isna(m) else m
    except Exception:
        return None


def save_state(when: pd.Timestamp, n: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    cover = harvest_coverage()
    saved, note = when, None
    if cover is not None and cover < when:
        saved = cover
        note = (f"watermark held at the harvest's last covered listing date {cover.date()} "
                f"rather than advanced to {when.date()}: the harvest calendar is stale, so "
                f"{cover.date()}..{when.date()} was never examined and must stay open")
        print(f"  NOTE: {note}")
    rec = {"last_run": str(saved), "ingested": n, "run_at": str(when),
           "harvest_covers_to": None if cover is None else str(cover.date())}
    if note:
        rec["watermark_note"] = note
    STATE.write_text(json.dumps(rec, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- calendar
# The NSE series that are equity. EQ is mainboard, SME and ST are the SME platforms, and
# BE is the trade-for-trade settlement series a small listing often starts in. N0/N1/N2 are
# DEBT and are not IPOs for this project's purposes.
EQUITY_SERIES = {"EQ", "BE", "SM", "SME", "ST", "MT"}


def newly_listed_nse(since: pd.Timestamp, until=None,
                     past: pd.DataFrame | None = None) -> pd.DataFrame:
    """IPOs that LISTED in `(since, until]`, from **NSE's own past-issues record**.

    This replaces the Chittorgarh harvest as the source of what has listed (6a). That
    harvest is a night-sweep snapshot and it goes stale: it records `listed_on` only for
    companies the sweep happened to cover, so a listing it had not yet seen was invisible
    to the ingest no matter how long ago it happened. NSE's `public-past-issues` is the
    exchange's own list of issues and carries `listingDate` directly, so "what listed in
    this window" is answered by the authority rather than inferred from a cache.

    Rows whose `listingDate` NSE has not published yet (it serves "-") are skipped, not
    guessed: an issue that has closed but not listed has no listing date, and inventing
    one would put a price lookup on the wrong day.
    """
    past = nse_past_issues() if past is None else past
    if past is None or past.empty:
        return pd.DataFrame()
    since = pd.Timestamp(since).normalize()
    until = pd.Timestamp(until).normalize() if until is not None else None
    d = past.copy()
    d = d[d["nse_listing"].notna()]
    m = d["nse_listing"] > since
    if until is not None:
        m &= d["nse_listing"] <= until
    out = d[m].copy()
    if out.empty:
        return pd.DataFrame()
    # NSE's past-issues list is not only equity IPOs. It carries debt issues too, under
    # series N0/N1/N2 and repeated once per tranche - the 1-16 Oct window returned seven
    # rows for IIFL Finance's NCD alone. Ingesting those would put bond series into the
    # training set as if they were IPOs. So the equity series are allow-listed, and
    # everything dropped is COUNTED and reported by series rather than silently filtered.
    out["nse_type"] = out["nse_type"].astype(str).str.upper().str.strip()
    dropped = out[~out["nse_type"].isin(EQUITY_SERIES)]
    if len(dropped):
        by = dropped.groupby("nse_type")["nse_company"].nunique().to_dict()
        print("  dropped %d non-equity row(s) by series: %s"
              % (len(dropped), by))
    out = out[out["nse_type"].isin(EQUITY_SERIES)].copy()
    if out.empty:
        return pd.DataFrame()
    # One row per symbol per listing date. A tranche repeat is not a second listing.
    before = len(out)
    out = out.drop_duplicates(subset=["nse_symbol", "nse_listing"])
    if len(out) < before:
        print("  collapsed %d duplicate tranche row(s)" % (before - len(out)))
    out = out.rename(columns={"nse_company": "ipo", "nse_listing": "listing_date",
                              "nse_symbol": "symbol", "nse_type": "nse_type"})
    for c in ("issue_size_cr", "price_band", "offer_price_cg", "total_subscription_x",
              "qib_x", "nii_x", "retail_x", "url"):
        if c not in out.columns:
            out[c] = None
    keep = ["ipo", "listing_date", "symbol", "nse_type", "issue_size_cr", "price_band",
            "offer_price_cg", "total_subscription_x", "qib_x", "nii_x", "retail_x", "url"]
    return out[[c for c in keep if c in out.columns]].reset_index(drop=True)


def newly_listed(since: pd.Timestamp) -> pd.DataFrame:
    """IPOs whose listing date falls after `since`, from the Chittorgarh harvest.

    **Superseded by `newly_listed_nse` for the live ingest (6a).** Kept because the
    historical rows in `data/new_listings.csv` were harvested through it and the
    subscription columns it carries have no NSE equivalent, so it is still the only way to
    read those back. It is no longer the source of WHAT HAS LISTED.
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
# ---------------------------------------------------------------- pricing: REMOVED
# Task 7, 2026-10-08. `price_yfinance`, `price_official`, `price_bse` and `reconcile_gain`
# lived here and are deleted, not disabled.
#
# They never worked. Every one of the 15 rows this job has ever written carries
# `listing_gain_pct = NULL` and `reconciled = no_source`, because its two sources were the
# NSE and BSE historical-QUOTE APIs rather than the bhavcopy archive.
#
# Worse than not working: the job runs Mon & Thu, so it priced listings up to three days
# AFTER they listed. A price read later has been silently restated for any split or bonus
# since - Syngene's real Rs 295 open reads Rs 147.50 once its 2017 bonus is applied - which
# is exactly what the Stage 27 standing rule forbids. The yfinance channel was kept here as
# "corroboration"; it is the single worst offender for that restatement and is gone too.
#
# Prices now come from ONE place: `listing_prices.py`, reading the exchange bhavcopy for
# the listing date itself, run by the 19:30 day-end leg. This job keeps its harvest half -
# finding IPOs that listed, including ones never bid on, which is how the training set
# grows - and writes its rows with the price columns NULL and
# `reconciled = pending_dayend_capture`.
#
# `--backfill-prices` fills historical rows from each row's OWN archived bhavcopy, which is
# the as-reported figure for that date rather than a later restatement.


def _norm_name(x) -> str:
    """Lowercase alphanumerics only, with the usual suffixes stripped. Deterministic."""
    t = "".join(ch for ch in str(x).lower() if ch.isalnum() or ch == " ")
    for suf in (" limited", " ltd", " private", " pvt", " india", " indias"):
        if t.endswith(suf):
            t = t[: -len(suf)]
    return "".join(ch for ch in t if ch.isalnum())


def nse_past_issues() -> pd.DataFrame:
    """Company -> symbol -> listing date, from NSE's own past-issues endpoint.

    `api/public-past-issues` returns ~1,474 historical issues carrying `symbol`,
    `company`, `ipoStartDate`, `ipoEndDate`, `listingDate` and `securityType`. It is the
    lookup this harvest has always been missing: all 15 rows it had written carried `isin`
    and `symbol` NULL, so the first backfill attempt fetched both bhavcopies for every
    date successfully and then searched them for an unnamed company.

    Permitted under H18: official host, robots.txt re-read and required to say `Allow: /`,
    no login or click-through. Returns an EMPTY frame on any failure, never a partial
    guess.
    """
    import time as _t

    import requests

    home = "https://www.nseindia.com/"
    ref = home + "market-data/all-upcoming-issues-ipo"
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
    sess = requests.Session()
    sess.headers.update({"User-Agent": ua, "Accept-Language": "en-GB,en;q=0.9",
                         "Accept-Encoding": "gzip, deflate"})
    try:
        r = sess.get(home + "robots.txt", timeout=30)
        if r.status_code != 200 or "Allow: /" not in r.text:
            print("  NSE robots.txt did not confirm Allow: / "
                  "(HTTP %s) - not fetching" % r.status_code)
            return pd.DataFrame()
        _t.sleep(3)
        sess.get(home, timeout=30)
        _t.sleep(3)
        sess.get(ref, timeout=30)
        _t.sleep(3)
        r = sess.get(home + "api/public-past-issues",
                     headers={"Referer": ref, "Accept": "application/json"}, timeout=30)
        if "json" not in r.headers.get("Content-Type", ""):
            print("  public-past-issues returned %s (HTTP %s) - not usable"
                  % (r.headers.get("Content-Type"), r.status_code))
            return pd.DataFrame()
        rows = r.json()
    except Exception as e:                                   # noqa: BLE001
        print("  public-past-issues failed: %s: %s" % (type(e).__name__, str(e)[:90]))
        return pd.DataFrame()

    d = pd.DataFrame(rows)
    if "symbol" not in d:
        print("  public-past-issues had no symbol column")
        return pd.DataFrame()
    name = d["company"] if "company" in d else None
    alt = d["companyName"] if "companyName" in d else None
    if name is None and alt is None:
        print("  public-past-issues had no company column")
        return pd.DataFrame()
    if name is None:
        name = alt
    elif alt is not None:
        name = name.fillna(alt)
    out = pd.DataFrame({
        "nse_company": name.astype(str),
        "nse_symbol": d["symbol"].astype(str).str.strip(),
        "nse_listing": pd.to_datetime(d.get("listingDate"), errors="coerce",
                                      format="mixed"),
        "nse_type": (d["securityType"].astype(str) if "securityType" in d
                     else pd.Series([""] * len(d))),
    })
    out["norm"] = out["nse_company"].map(_norm_name)
    print("  NSE past issues: %d rows, %d distinct symbols"
          % (len(out), out["nse_symbol"].nunique()))
    return out


def resolve_from_nse(ipo: str, listing_date, past: pd.DataFrame) -> dict:
    """`{symbol, how, ...}` for one harvested row, or `{}`.

    TWO keys must agree, never one: the normalised company name AND the listing date
    (within a day, because the sources can differ by a calendar day on a late-evening
    listing notice). Name alone is exactly how the Priority 2 probe silently returned a
    different company's subscription for the guessed symbol `PARAMOUNT`.
    """
    if past is None or past.empty:
        return {}
    n = _norm_name(ipo)
    if len(n) < 5:
        return {}
    day = pd.Timestamp(listing_date).normalize()
    cand = past[past["norm"] == n]
    how = "name+date"
    if cand.empty:
        # A prefix match is allowed ONLY when it is unique, and the date must still agree.
        pref = past[past["norm"].str.startswith(n[:12])]
        if len(pref) != 1:
            return {}
        cand, how = pref, "name_prefix+date"
    cand = cand[(cand["nse_listing"] - day).abs() <= pd.Timedelta(days=1)]
    if len(cand) != 1:
        return {}
    r = cand.iloc[0]
    return {"symbol": r["nse_symbol"], "how": how, "nse_type": r["nse_type"],
            "nse_company": r["nse_company"]}


def backfill_prices(dry: bool = False) -> pd.DataFrame:
    """Task 7. Fill every NULL-gain row in `new_listings.csv` from its OWN listing date's
    archived bhavcopy.

    One request per distinct listing date, not per company: a bhavcopy covers every scrip
    that traded that day, so companies sharing a date share a fetch.

    The figure is the as-reported one for that date. That is the whole point of going back
    to the archive rather than asking for a current quote: the archive cannot have been
    restated, because it is a file published that evening and never rewritten.
    """
    import listing_prices as LP
    if not NEW_LISTINGS.exists():
        print(f"{NEW_LISTINGS} does not exist")
        return pd.DataFrame()
    d = pd.read_csv(NEW_LISTINGS)
    before = d.copy()
    # An all-NULL column reads back as float64, so assigning a symbol string into it
    # raises `Invalid value 'ARMEE' for dtype 'float64'`. Cast the text columns up front.
    for c in ("isin", "symbol", "reconciled", "note", "gain_source_a", "gain_source_b"):
        if c in d:
            d[c] = d[c].astype(object)
    todo = d[pd.to_numeric(d["listing_gain_pct"], errors="coerce").isna()].copy()
    print(f"{len(d)} rows in new_listings.csv; {len(todo)} with no gain")
    if todo.empty:
        return d

    # Resolve the identities FIRST. The bhavcopies were always being fetched;
    # what was missing was a symbol to look them up by.
    past = nse_past_issues()

    f = LP.Fetcher()
    cache: dict[str, tuple] = {}
    filled = 0
    resolved = 0
    for i, r in todo.iterrows():
        day = str(r["listing_date"])
        if day not in cache:
            cache[day] = (LP.bhavcopy(f, day, "nse"), LP.bhavcopy(f, day, "bse"))
        (ndf, nnote), (bdf, bnote) = cache[day]
        isin = str(r.get("isin") or "")
        isin = isin.upper() if isin and isin.lower() != "nan" else None
        symbol = str(r.get("symbol") or "")
        symbol = symbol.strip() if symbol and symbol.lower() != "nan" else None
        how_sym = "already on the row"
        if not symbol:
            got = resolve_from_nse(str(r["ipo"]), day, past)
            if got:
                symbol = got["symbol"]
                how_sym = ("NSE public-past-issues (%s, %s)"
                           % (got["how"], got["nse_type"]))
                d.loc[i, "symbol"] = symbol
                resolved += 1
            else:
                how_sym = "UNRESOLVED"
        # new_listings.csv has never carried a bse_code column, so there is no
        # BSE scrip code to match on. Stated rather than left as a silent None.
        code = None

        n, nhow = LP.find(ndf, isin, symbol, None)
        b, bhow = LP.find(bdf, isin, symbol, code)

        def one(h, how):
            if h is None or not len(h):
                return {"match_by": how}
            return {"open": float(h["open"].iloc[0]) if pd.notna(h["open"].iloc[0]) else None,
                    "close": float(h["close"].iloc[0]) if pd.notna(h["close"].iloc[0]) else None,
                    "match_by": how}

        nd, bd = one(n, nhow), one(b, bhow)
        offer = pd.to_numeric(pd.Series([r.get("offer_price")]), errors="coerce").iloc[0]
        rec = LP.reconcile(nd, bd, None if pd.isna(offer) else float(offer))
        if rec.get("listing_gain_pct") is None:
            d.loc[i, "reconciled"] = rec.get("reconciled") or "no_source"
            d.loc[i, "note"] = (f"{r.get('note','')} | backfill {day}: symbol "
                                f"{symbol or 'NONE'} via {how_sym}; "
                                f"nse {nnote}; bse {bnote}")[:600]
            print(f"  {str(r['ipo'])[:30]:32s} {day}  sym={str(symbol):12s} "
                  f"NOT FOUND  {how_sym[:36]}")
            continue
        d.loc[i, "listing_open"] = rec.get("listing_open")
        d.loc[i, "listing_close"] = rec.get("listing_close")
        d.loc[i, "listing_gain_pct"] = rec.get("listing_gain_pct")
        d.loc[i, "gain_source_a"] = nd.get("open")
        d.loc[i, "gain_source_b"] = bd.get("open")
        d.loc[i, "reconciled"] = rec.get("reconciled")
        d.loc[i, "note"] = (f"{r.get('note','')} | backfilled from the {day} archived "
                            f"bhavcopy (as-reported); symbol via {how_sym}; "
                            f"nse match {nhow}, bse match {bhow}")[:600]
        filled += 1
        print(f"  {str(r['ipo'])[:30]:32s} {day}  sym={str(symbol):12s} "
              f"open={rec.get('listing_open')} gain={rec.get('listing_gain_pct')}%  "
              f"{rec.get('reconciled')}")

    print(f"{chr(10)}resolved {resolved} missing symbol(s); "
          f"filled {filled} of {len(todo)}")
    if dry:
        print("--dry-run: nothing written")
        return d
    d.to_csv(NEW_LISTINGS, index=False, encoding="utf-8")
    cols = ["ipo", "listing_date", "offer_price", "listing_open", "listing_gain_pct",
            "reconciled"]
    rep = before[cols].merge(d[cols], on=["ipo", "listing_date"], suffixes=("_before", "_after"))
    rep.to_csv(ROOT / "reports" / "NEW_LISTINGS_BACKFILL.csv", index=False, encoding="utf-8")
    print(f"written {NEW_LISTINGS} and reports/NEW_LISTINGS_BACKFILL.csv")
    return d


def fix_segments_from_nse(dry: bool = False) -> pd.DataFrame:
    """Set `segment` from NSE's own `securityType`, for every row that resolves.

    Rule 6 keeps SME and mainboard in separate models, so a wrong segment label is not
    cosmetic - it pools two populations whose coefficients differ in sign. Every one of
    the 15 legacy harvest rows says `mainboard`, because the rows were written before the
    segment default was removed (Priority 5b), and at least two of them are SME.

    The label comes from the exchange's own field. Nothing is inferred from the company
    name, the offer size or the listing venue.
    """
    if not NEW_LISTINGS.exists():
        return pd.DataFrame()
    d = pd.read_csv(NEW_LISTINGS)
    for c in ("segment", "symbol", "note"):
        if c in d:
            d[c] = d[c].astype(object)
    past = nse_past_issues()
    if past.empty:
        print("  no NSE past-issues data; segments left exactly as they are")
        return d
    changed = []
    for i, r in d.iterrows():
        got = resolve_from_nse(str(r["ipo"]), r["listing_date"], past)
        if not got:
            continue
        t = str(got.get("nse_type") or "").strip().upper()
        if t in ("EQ", "BE"):
            seg = "mainboard"
        elif t in ("SME", "ST", "SM"):
            seg = "sme"
        else:
            continue                      # unknown code: leave it alone, never guess
        if str(r.get("segment") or "") != seg:
            changed.append((r["ipo"], r.get("segment"), seg, t))
            d.loc[i, "segment"] = seg
            d.loc[i, "note"] = (f"{r.get('note','')} | segment set to {seg} from NSE "
                                f"securityType={t}")[:900]
    for ipo, old, new, t in changed:
        print(f"  {str(ipo)[:30]:32s} segment {old} -> {new}  (NSE securityType {t})")
    print(f"{chr(10)}{len(changed)} segment label(s) corrected")
    if dry:
        print("--dry-run: nothing written")
        return d
    d.to_csv(NEW_LISTINGS, index=False, encoding="utf-8")
    return d


def main(since: str | None = None, dry: bool = False, until: str | None = None,
         source: str = "nse") -> pd.DataFrame:
    """Harvest IPOs that listed in the window and append them to new_listings.csv.

    `source="nse"` (the default, 6a) asks NSE's own past-issues record what listed.
    `source="chittorgarh"` is the old night-sweep path, kept only for reading history
    back - it goes stale and a listing the sweep had not covered was invisible to the
    ingest however long ago it happened.
    """
    start = pd.Timestamp(since) if since else last_run()
    now = pd.Timestamp.now()
    print(f"ingesting IPOs listed after {start.date()}"
          + (f" and up to {pd.Timestamp(until).date()}" if until else "")
          + f", source={source}")

    cand = (newly_listed_nse(start, until) if source == "nse"
            else newly_listed(start))
    print(f"  {len(cand)} newly listed found via {source}")
    # IDEMPOTENT: a symbol+listing-date already in new_listings.csv is not re-ingested.
    # The 19:30 leg runs every weekday over a window that deliberately overlaps, so
    # without this the same listing would be appended once per run.
    if len(cand) and NEW_LISTINGS.exists():
        try:
            have = pd.read_csv(NEW_LISTINGS, keep_default_na=False, na_values=[""])
            seen = set()
            for c in ("symbol", "ipo"):
                if c in have.columns and "listing_date" in have.columns:
                    seen |= {(str(a).strip().upper(), str(b)[:10])
                             for a, b in zip(have[c], have["listing_date"])}
            before = len(cand)
            key_sym = cand["symbol"] if "symbol" in cand.columns else cand["ipo"]
            cand = cand[[(str(a).strip().upper(), str(b)[:10]) not in seen
                         for a, b in zip(key_sym,
                                         pd.to_datetime(cand["listing_date"],
                                                        errors="coerce"))]]
            if len(cand) < before:
                print(f"  {before - len(cand)} already ingested, skipped (idempotent)")
        except Exception as e:                                 # noqa: BLE001
            print(f"  NOTE could not read {NEW_LISTINGS.name} for the idempotency "
                  f"check: {type(e).__name__}: {e}")
    if not len(cand):
        print("  nothing new to ingest.")
        if not dry:
            save_state(now, 0)
        return pd.DataFrame()

    # Priority 5a: resolution moved to symbols.py. The old code matched a 14-character
    # name prefix against master_with_symbols.csv, which stops at 2026-05-14 -- so every
    # 2026 listing failed before any price was fetched -- and which cannot match a company
    # that listed under a former name (Priority 3). symbols.py tries ISIN first, then
    # names including known aliases, and falls back to data/NSE_EQUITY_L.csv, which carries
    # an ISIN for every row and runs to 2026-09-25.
    sym = pd.read_csv(ROOT / "data" / "master_with_symbols.csv")
    sym["norm"] = sym["company"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    rows, last = [], 0.0
    for r in cand.itertuples():
        # When the harvest row already carries NSE's own symbol for the issue, USE IT.
        # `SY.resolve` searches master_with_symbols.csv and NSE_EQUITY_L.csv, which are
        # built from issues that have already settled - so for a listing from the last
        # fortnight it finds nothing, and all 15 of the 1-16 Oct listings came back
        # UNRESOLVED while the symbol sat in the row being passed in. The exchange's own
        # record of the issue outranks our two caches of it.
        from_harvest = str(getattr(r, "symbol", "") or "").strip()
        if from_harvest and from_harvest.lower() not in ("nan", "none"):
            res = {"symbol": from_harvest, "isin": getattr(r, "isin", None),
                   "source": "NSE public-past-issues (the harvest row itself)",
                   "note": "symbol taken from NSE's own record of the issue"}
        else:
            res = SY.resolve(str(r.ipo), getattr(r, "isin", None))
        symbol, isin = res["symbol"], res["isin"]
        if symbol is None:
            print(f"  {str(r.ipo)[:34]:36s} {'-':12s} UNRESOLVED - {res['note'][:90]}")
            continue

        norm = "".join(ch for ch in str(r.ipo).lower() if ch.isalnum())
        m = sym[sym["norm"].str.startswith(norm[:14])] if len(norm) >= 6 else sym.iloc[0:0]
        offer = pd.to_numeric(m["Offer Price"], errors="coerce").iloc[0] if len(m) else None
        offer_src = "master"
        if offer is None or pd.isna(offer):
            offer = getattr(r, "offer_price_cg", None)
            offer_src = "chittorgarh_price_band (SINGLE SOURCE - flag it)"

        # Priority 5b / rule 6: the segment comes from the bid-time record, never from a
        # default. A NULL segment means the row is logged and NOT used for training;
        # pooling an SME listing into mainboard would break rule 6 silently.
        seg = SY.segment_for(str(r.ipo), isin)

        bse_code = res.get("bse_code") or (
            m["bse_code"].iloc[0] if len(m) and "bse_code" in m else None)
        # Task 7: NO pricing here. The harvest records that the IPO listed and resolves
        # its identity; the price comes from the bhavcopy captured ON the listing date.
        row = {"ipo": r.ipo, "isin": isin, "symbol": symbol, "segment": seg["segment"],
               "listing_date": str(pd.Timestamp(r.listing_date).date()),
               "offer_price": offer,
               "listing_open": None, "listing_close": None, "listing_gain_pct": None,
               "gain_source_a": None, "gain_source_b": None, "rel_diff_pct": None,
               "reconciled": "pending_dayend_capture",
               "ingested_at": str(now)}
        row["note"] = (f"harvest only; price from the day-end bhavcopy capture on the "
                       f"listing date (Task 7) | symbol via {res['source']}"
                       f" | segment: {seg['source']}"
                       f" | bse_code {bse_code}"
                       f" | offer price from {offer_src}")
        rows.append(row)
        print(f"  {str(r.ipo)[:34]:36s} {str(symbol):12s} harvested "
              f"(price pending day-end capture)")

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
    ap.add_argument("--until", default=None)
    ap.add_argument("--source", default="nse", choices=["nse", "chittorgarh"],
                    help="where to ask WHAT HAS LISTED. 'nse' (default, 6a) reads NSE's "
                         "own public-past-issues; 'chittorgarh' is the stale night-sweep "
                         "path and is kept only for reading history back")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fix-segments", action="store_true",
                    help="rule 6: set segment from NSE securityType")
    ap.add_argument("--backfill-prices", action="store_true",
                    help="Task 7: fill NULL-gain rows from their own "
                         "archived bhavcopy date")
    a = ap.parse_args()
    if a.fix_segments:
        fix_segments_from_nse(a.dry_run)
    elif a.backfill_prices:
        backfill_prices(a.dry_run)
    else:
        main(a.since, a.dry_run, a.until, a.source)

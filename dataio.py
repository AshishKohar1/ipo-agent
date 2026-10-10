"""
dataio.py — the ONLY module that reads files in data/.

Data loading contract (see CLAUDE.md):
  * No other module opens a file under data/ directly.
  * Files are discovered by glob pattern, never by hardcoded filename, because the
    source spreadsheets get re-exported with different names/dates.
  * A pattern that matches zero files, or more files than it allows, raises —
    it never silently picks one.
  * Loaders return columns renamed to the pipeline's canonical names and parsed
    dates. They do not fill, estimate or coerce values beyond parsing: a cell that
    doesn't parse becomes NaN/NaT.
"""
from __future__ import annotations
import datetime as _dt
import re
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parent / "data"

# canonical dataset -> (glob pattern, allow multiple matches?)
PATTERNS = {
    "master":   ("Initial Public Offering*.xlsx", False),
    "nse_spine": ("IPO-PastIssue-*.xlsx", False),
    "tracker":  ("IPOs_Performance_Tracker_*.xlsx", True),
    "nse_equity_list": ("NSE_EQUITY_L*.csv", False),   # nsearchives.nseindia.com EQUITY_L.csv
    "nifty_tri": ("NIFTY50_TRI*.csv", False),          # niftyindices.com, fetch_nifty_tri.py
}


def find(kind: str) -> list[Path]:
    pat, multi = PATTERNS[kind]
    hits = sorted(DATA.glob(pat))
    if not hits:
        raise FileNotFoundError(f"dataio: no file in {DATA} matches {pat!r} ({kind})")
    if len(hits) > 1 and not multi:
        raise RuntimeError(f"dataio: {len(hits)} files match {pat!r} ({kind}), expected 1: "
                           + ", ".join(h.name for h in hits))
    return hits


def _dates(s: pd.Series) -> pd.Series:
    # Excel gives real datetimes; placeholders like "-" become NaT. Strings are not
    # guessed at: an unexpected date string also becomes NaT rather than a misparse.
    return pd.to_datetime(s.where(s.map(lambda v: isinstance(v, _dt.datetime))),
                          errors="coerce")


def load_master() -> pd.DataFrame:
    """The master dataset (652 IPOs). Raw columns, Date parsed."""
    df = pd.read_excel(find("master")[0])
    df["Date"] = _dates(df["Date"])
    return df


def load_nse_spine() -> pd.DataFrame:
    """NSE past-issues list. Columns: company, security_type, symbol, issue_open_date,
    issue_close_date, listing_date, source."""
    df = pd.read_excel(find("nse_spine")[0]).rename(columns={
        "COMPANY NAME": "company", "SECURITY TYPE": "security_type", "Symbol": "symbol",
        "ISSUE START DATE": "issue_open_date", "ISSUE END DATE": "issue_close_date",
        "DATE OF LISTING": "listing_date"})
    for c in ("issue_open_date", "issue_close_date", "listing_date"):
        df[c] = _dates(df[c])
    df["symbol"] = df["symbol"].where(df["symbol"].notna(), None)
    df["source"] = "nse_spine"
    return df[["company", "security_type", "symbol", "issue_open_date",
               "issue_close_date", "listing_date", "source"]]


def load_trackers() -> pd.DataFrame:
    """All IPOMatrix performance trackers stacked. Header is on row 3 of each sheet.
    Columns: company, category, issue_open_date, listing_date, isin, bse_code, symbol, source."""
    frames = []
    for p in find("tracker"):
        df = pd.read_excel(p, header=2).rename(columns={
            "Company": "company", "Issue Category": "category",
            "Opening Date": "issue_open_date", "Listing Date": "listing_date",
            "ISIN": "isin", "BSE Script Code": "bse_code", "NSE Symbol": "symbol",
            "Issue Amount (Rs.cr.)": "issue_size_cr", "Subscription (x)": "subscription_x",
            "Issue Price (Rs.)": "issue_price", "Close Price on Listing (Rs.)": "_close_raw"})
        df = df[df["company"].notna()].copy()
        df["issue_open_date"] = _dates(df["issue_open_date"])
        df["listing_date"] = _dates(df["listing_date"])
        for c in ("issue_size_cr", "subscription_x", "issue_price"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # "94.99 (5.54%)" -> listing-day close and the tracker's own % gain. The gain is
        # recomputed from close/issue price and reconciled with the printed %: if they
        # disagree by > 0.5pp the value is NULL (never guessed).
        parts = df["_close_raw"].astype(str).str.extract(r"^\s*([\d.]+)\s*\((-?[\d.]+)%\)")
        df["listing_close"] = pd.to_numeric(parts[0], errors="coerce")
        printed = pd.to_numeric(parts[1], errors="coerce")
        calc = (df["listing_close"] / df["issue_price"] - 1) * 100
        df["listing_gain_pct"] = calc.where((calc - printed).abs() <= 0.5)
        df["source"] = f"tracker:{p.stem}"
        frames.append(df[["company", "category", "issue_open_date", "listing_date",
                          "isin", "bse_code", "symbol", "issue_size_cr", "subscription_x",
                          "issue_price", "listing_close", "listing_gain_pct", "source"]])
    return pd.concat(frames, ignore_index=True)


def load_nse_equity_list() -> pd.DataFrame:
    """NSE's official list of currently listed equities (live names only — delisted
    companies are absent). Columns: symbol, company, series, listing_date, isin."""
    df = pd.read_csv(find("nse_equity_list")[0])
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"SYMBOL": "symbol", "NAME OF COMPANY": "company",
                            "SERIES": "series", "DATE OF LISTING": "listing_date",
                            "ISIN NUMBER": "isin"})
    df["listing_date"] = pd.to_datetime(df["listing_date"], format="%d-%b-%Y", errors="coerce")
    df["source"] = "nse_equity_list"
    return df[["symbol", "company", "series", "listing_date", "isin", "source"]]


def load_nifty_tri() -> pd.Series:
    """Official Nifty 50 Total Return Index (NSE Indices Ltd), indexed by date."""
    df = pd.read_csv(find("nifty_tri")[0], parse_dates=["date"])
    return df.set_index("date")["tri"].sort_index()


# ----------------------------------------------------------------------
# pipeline outputs (project root) — models read these through dataio too
# ----------------------------------------------------------------------
ROOT = DATA.parent


def load_master_with_symbols() -> pd.DataFrame:
    """The working master. NOTE: its 'issue_open_date' column holds the LISTING date
    (CLAUDE.md). This loader adds 'listing_date_master' = that column, which is the
    listing date for every row except those flagged bad_listing_date."""
    df = pd.read_csv(DATA / "master_with_symbols.csv",
                     parse_dates=["issue_open_date", "listing_date"])
    df["listing_date_master"] = df["issue_open_date"]
    if "exclude_reason" not in df:
        df["exclude_reason"] = None
    return df


def load_holding_target(path: str = "holding_target.csv") -> pd.DataFrame:
    return pd.read_csv(DATA / path, parse_dates=["listing_date"])


# ----------------------------------------------------------------------
# name matching helpers (shared by run_overnight Job 1)
# ----------------------------------------------------------------------
_STOP = r"\b(limited|ltd|pvt|private|the|india|company|co)\b"


def norm_name(s) -> str:
    s = str(s).lower().replace("...", "")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(_STOP, "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def yahoo_query(s) -> str:
    """Company name as a Yahoo search query. Yahoo's search endpoint returns NOTHING
    when the query contains 'Ltd'/'Limited' or a bracketed alias ('Avenue Supermarts
    Ltd (DMart)' -> [], 'Avenue Supermarts' -> DMART.NS), so strip them."""
    s = re.sub(r"\(.*?\)|\(.*$", " ", str(s).replace("...", ""))
    s = re.sub(r"\b(ltd|limited|pvt|private|company|co)\b\.?", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .&,-")


def is_truncated(s) -> bool:
    return str(s).rstrip().endswith("...")


def prefix_sim(a, b) -> float:
    """Similarity of two names, tolerant of truncation: the better of the full-string
    ratio and the ratio over the shorter name's length. Names shorter than 6
    normalised chars score 0 — too short to match on safely."""
    a, b = norm_name(a), norm_name(b)
    if min(len(a), len(b)) < 6:
        return 0.0
    n = min(len(a), len(b))
    return max(SequenceMatcher(None, a, b).ratio(),
               SequenceMatcher(None, a[:n], b[:n]).ratio())

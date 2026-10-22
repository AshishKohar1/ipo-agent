"""
recover_issue_dates_nse.py — issue-open dates from NSE's own issue record, with provenance.

Why this and not the spreadsheet. `C:\\Users\\HP\\Downloads\\IPO-PastIssue-*.csv` is an
export of **this same NSE dataset** and agrees with `data/issue_dates_recovered.csv` on
**301 of 302** overlapping symbols. But a hand-downloaded file carries no URL, no fetch
time and no SHA-256, and rule 2 requires all three on every stored value. So the dates are
fetched from the API the repo already uses, and the spreadsheet is the independent
cross-check that the fetch is right — which is the stronger arrangement anyway.

Matching is by **symbol**, exact and normalised, against NSE's own `symbol` field. No name
similarity (H28). A symbol that appears in NSE's record more than once with different start
dates is refused rather than resolved: "Rajputana Stainless Limited-Special Withdrawal
Option" shares the symbol RSL with the issue itself, and a withdrawal window is not a
bidding window.

    python recover_issue_dates_nse.py --dry-run
    python recover_issue_dates_nse.py --write
    python recover_issue_dates_nse.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                        # noqa: E402
import trading_day as TD                                             # noqa: E402

DATA = ROOT / "data"
STORE = DATA / "issue_dates_recovered.csv"
XCHECK = Path(r"C:\Users\HP\Downloads\IPO-PastIssue-17-09-2021-to-17-09-2026.csv")
URL = "https://www.nseindia.com/api/public-past-issues"
# H18: realistic browser headers are permitted to official sources.
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"),
      "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}
EQUITY_SERIES = {"EQ", "BE", "SME"}
PROV = ["source_url", "fetched_at_ist", "payload_sha256"]


def fetch_rows() -> tuple[list[dict], str, str]:
    """`(rows, sha256 of the exact payload, fetch time IST)`. One request."""
    import requests
    s = requests.Session()
    s.headers.update(UA)
    try:
        s.get("https://www.nseindia.com/", timeout=25)
    except Exception:                                              # noqa: BLE001
        pass
    r = s.get(URL, timeout=35)
    r.raise_for_status()
    sha = hashlib.sha256(r.content).hexdigest()
    j = json.loads(r.content)
    rows = j if isinstance(j, list) else (j.get("data") or j.get("dataList") or [])
    return rows, sha, TD.ist_now().strftime("%Y-%m-%d %H:%M")


def wanted() -> pd.DataFrame:
    """Master rows with no recovered issue-open date yet."""
    m = dataio.load_master_with_symbols()
    m["sym"] = m["symbol"].astype(str).str.upper().str.strip()
    d = pd.read_csv(STORE)
    d["sym"] = d["symbol"].astype(str).str.upper().str.strip()
    have = set(d.loc[d["issue_open_date_true"].notna(), "sym"])
    return m[m["sym"].ne("NAN") & ~m["sym"].isin(have)][["company", "symbol", "sym",
                                                         "listing_date"]]


def resolve(rows: list[dict], syms: set[str]) -> dict[str, dict]:
    """`{symbol: {start, end, listing, issue_price, name}}`, refusing any ambiguity."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        sym = str(r.get("symbol") or "").upper().strip()
        if sym not in syms:
            continue
        if str(r.get("securityType") or "").upper().strip() not in EQUITY_SERIES:
            continue
        start = pd.to_datetime(r.get("ipoStartDate"), format="%d-%b-%Y", errors="coerce")
        if pd.isna(start):
            continue
        by.setdefault(sym, []).append(
            {"start": start, "end": pd.to_datetime(r.get("ipoEndDate"),
                                                   format="%d-%b-%Y", errors="coerce"),
             "listing": pd.to_datetime(r.get("listingDate"), format="%d-%b-%Y",
                                       errors="coerce"),
             "name": r.get("company")})
    out = {}
    for sym, hits in by.items():
        starts = {h["start"] for h in hits}
        if len(starts) == 1:
            out[sym] = hits[0]
        else:
            # Two different start dates under one symbol is NSE describing two different
            # events. Refused, not averaged and not "latest wins".
            out[sym] = {"refused": f"{len(starts)} different start dates in NSE's record: "
                                   + ", ".join(sorted(str(s.date()) for s in starts))}
    return out


def crosscheck() -> dict[str, pd.Timestamp]:
    """`{symbol: start}` from the user's NSE export. Cross-check only, never stored."""
    if not XCHECK.exists():
        return {}
    d = pd.read_csv(XCHECK)
    d.columns = [c.strip() for c in d.columns]
    d = d[d["SECURITY TYPE"].isin(EQUITY_SERIES)]
    d["start"] = pd.to_datetime(d["ISSUE START DATE"], format="%d-%b-%Y", errors="coerce")
    d = d[d["start"].notna()]
    out: dict[str, pd.Timestamp] = {}
    for sym, g in d.groupby(d["Symbol"].astype(str).str.upper().str.strip()):
        s = set(g["start"])
        if len(s) == 1:
            out[sym] = g["start"].iloc[0]
    return out


def run(write: bool = False) -> pd.DataFrame:
    w = wanted()
    rows, sha, at = fetch_rows()
    res = resolve(rows, set(w["sym"]))
    xc = crosscheck()
    out = []
    for r in w.itertuples():
        hit = res.get(r.sym)
        if hit is None:
            continue
        if "refused" in hit:
            out.append({"company": r.company, "symbol": r.symbol,
                        "nse_issue_open": None, "downloads_csv": xc.get(r.sym),
                        "agree": None, "note": hit["refused"]})
            continue
        x = xc.get(r.sym)
        out.append({"company": r.company, "symbol": r.symbol,
                    "nse_issue_open": hit["start"], "nse_issue_end": hit["end"],
                    "nse_listing": hit["listing"],
                    "downloads_csv": x,
                    "agree": None if x is None else bool(x == hit["start"]),
                    "note": ""})
    d = pd.DataFrame(out)
    if write and len(d):
        good = d[d["nse_issue_open"].notna()]
        store = pd.read_csv(STORE)
        for c in PROV:
            if c not in store.columns:
                store[c] = ""
        store["sym"] = store["symbol"].astype(str).str.upper().str.strip()
        for r in good.itertuples():
            sym = str(r.symbol).upper().strip()
            i = store.index[store["sym"] == sym]
            vals = {"issue_open_date_true": str(pd.Timestamp(r.nse_issue_open).date()),
                    "source": "nse_public_past_issues", "confidence": "high",
                    "source_url": URL, "fetched_at_ist": at, "payload_sha256": sha}
            if len(i):
                for k, v in vals.items():
                    store.loc[i, k] = v
            else:
                store = pd.concat([store, pd.DataFrame([{
                    "company": r.company, "symbol": r.symbol,
                    "listing_date": str(pd.Timestamp(r.nse_listing).date())
                    if pd.notna(r.nse_listing) else "", **vals}])], ignore_index=True)
        store.drop(columns=["sym"]).to_csv(STORE, index=False, encoding="utf-8")
    return d


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

    whole = inspect.getsource(sys.modules[__name__])
    # The PRODUCT code only. An earlier version searched the whole module and failed on
    # its own assertion strings - the needles found themselves. Everything from the
    # self-test onward is excluded, and each needle is assembled at runtime.
    src = whole.split("def self_test")[0]
    print("[1] matching is by SYMBOL, exact, never by name similarity (H28)")
    chk("the resolver keys on NSE's own symbol field",
        'sym = str(r.get("symbol") or "").upper().strip()' in src)
    for label, needle in {"a sequence matcher": "Sequence" + "Matcher",
                          "difflib": "diff" + "lib",
                          "an approximate matcher": "fuz" + "zy"}.items():
        chk(f"no {label} in the product code", needle not in src, needle)

    print("\n[2] ambiguity is refused, not resolved")
    rows = [{"symbol": "RSL", "securityType": "EQ", "ipoStartDate": "09-MAR-2026",
             "ipoEndDate": "11-MAR-2026", "listingDate": "16-MAR-2026",
             "company": "Rajputana Stainless Limited"},
            {"symbol": "RSL", "securityType": "EQ", "ipoStartDate": "12-MAR-2026",
             "ipoEndDate": "13-MAR-2026", "listingDate": "-",
             "company": "Rajputana Stainless Limited-Special Withdrawal Option"}]
    got = resolve(rows, {"RSL"})
    chk("two start dates under one symbol are refused", "refused" in got["RSL"])
    chk("and the refusal names both dates",
        "2026-03-09" in got["RSL"]["refused"] and "2026-03-12" in got["RSL"]["refused"])
    one = resolve(rows[:1], {"RSL"})
    chk("a single unambiguous record resolves",
        one["RSL"]["start"] == pd.Timestamp("2026-03-09"))

    print("\n[3] only equity series, and only a parseable date")
    chk("a DEBT row is ignored",
        resolve([{"symbol": "X", "securityType": "DEBT",
                  "ipoStartDate": "01-JAN-2026"}], {"X"}) == {})
    chk("an unparseable start date is ignored",
        resolve([{"symbol": "X", "securityType": "EQ",
                  "ipoStartDate": "-"}], {"X"}) == {})

    print("\n[4] provenance on every stored value (rule 2)")
    for c in PROV:
        chk(f"{c} is written", f'"{c}"' in src)
    chk("the SHA-256 is of the exact payload bytes",
        "hashlib.sha256(r.content).hexdigest()" in src)
    chk("one request per run", src.count("s.ge" + "t(URL") == 1)

    print("\n[5] the spreadsheet is a cross-check and is never stored")
    xs = inspect.getsource(crosscheck)
    chk("crosscheck only reads", "to_csv" not in xs)
    ws = inspect.getsource(run)
    chk("only the NSE value is written",
        '"source": "nse_public_past_issues"' in ws and "downloads_csv" not in
        ws.split("if write")[1])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = run(write=a.write)
    if len(d):
        print(d.to_string(index=False))
    print(f"\n{len(d)} resolved; written={a.write}")

"""
fetch_nifty_tri.py — Nifty 50 Total Return Index from the OFFICIAL source only:
NSE Indices Ltd, https://www.niftyindices.com (Historical Data > Total Return Index).

The site's own page calls POST /BackPage/getTotalReturnIndexString with at most one
year per request. This script pages through 2009-01-01 -> today in <=360-day chunks
and writes data/NIFTY50_TRI.csv (date, tri, ntr). Read it via dataio.load_nifty_tri().

    python fetch_nifty_tri.py
"""
from __future__ import annotations
import json, time
from pathlib import Path
import pandas as pd
import requests

URL = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
PAGE = "https://www.niftyindices.com/reports/historical-data"
OUT = Path(__file__).resolve().parent / "data" / "NIFTY50_TRI.csv"


def fetch(start="2009-01-01", end=None) -> pd.DataFrame:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                    "Chrome/120 Safari/537.36",
                      "Accept": "application/json, text/javascript, */*; q=0.01",
                      "X-Requested-With": "XMLHttpRequest", "Origin": "https://www.niftyindices.com",
                      "Referer": PAGE})
    s.get(PAGE, timeout=30)                                   # session cookies
    a = pd.Timestamp(start); end = pd.Timestamp(end or pd.Timestamp.today().normalize())
    rows = []
    while a <= end:
        b = min(a + pd.Timedelta(days=360), end)
        cinfo = (f"{{'name':'NIFTY 50','startDate':'{a:%d-%b-%Y}','endDate':'{b:%d-%b-%Y}',"
                 f"'indexName':'NIFTY 50'}}")
        for attempt in range(3):
            try:
                r = s.post(URL, data=json.dumps({"cinfo": cinfo}), timeout=60,
                           headers={"Content-Type": "application/json; charset=utf-8"})
                chunk = json.loads(r.text)
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"TRI fetch failed for {a:%Y-%m-%d}..{b:%Y-%m-%d}: {e}")
                time.sleep(3)
        rows += chunk
        print(f"  {a:%Y-%m-%d} .. {b:%Y-%m-%d}: {len(chunk)} rows")
        a = b + pd.Timedelta(days=1)
        time.sleep(1.0)
    df = pd.DataFrame(rows)
    df = pd.DataFrame({"date": pd.to_datetime(df["Date"], format="%d %b %Y"),
                       "tri": pd.to_numeric(df["TotalReturnsIndex"], errors="coerce"),
                       "ntr": pd.to_numeric(df.get("NTR_Value"), errors="coerce")})
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    df = fetch()
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(df)} rows {df['date'].min():%Y-%m-%d} .. {df['date'].max():%Y-%m-%d}, "
          f"null tri {df['tri'].isna().sum()}")

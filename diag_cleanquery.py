"""DIAGNOSTIC ONLY — does not modify master_with_symbols.csv or any pipeline file.
Re-queries Yahoo for unresolved rows with a cleaned name (no Ltd/Limited/brackets) and
writes candidates to reports/intermediate/ for the user to review."""
import re, time, requests, pandas as pd, yfinance as yf
import os; from pathlib import Path; os.chdir(Path(__file__).resolve().parent)

# Housekeeping, 2026-10-10. These intermediates used to be written as bare
# `to_csv("name.csv")`. The script chdir's to the project root first, so they landed in
# the ROOT by design - which is how the root accumulated twenty-odd loose files. They go
# to reports/intermediate/ now, named from __file__ so the chdir is no longer load-bearing.
INTERMEDIATE = Path(__file__).resolve().parent / "reports" / "intermediate"
INTERMEDIATE.mkdir(parents=True, exist_ok=True)

def clean(n):
    n = re.sub(r"\(.*?\)", " ", str(n))
    n = re.sub(r"\b(ltd|limited|pvt|private|company|co)\b\.?", " ", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" .&")

m = pd.read_csv("master_with_symbols.csv", parse_dates=["issue_open_date"])
todo = m[m["symbol"].isna()]
out = []
for _, r in todo.iterrows():
    q = clean(r["company"]); cand = first = None; note = "no .NS/.BO quote"
    try:
        js = requests.get("https://query2.finance.yahoo.com/v1/finance/search",
                          params={"q": q, "quotesCount": 8},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
        for it in js.get("quotes", []):
            sym = it.get("symbol", "")
            if not sym.endswith((".NS", ".BO")):
                continue
            h = yf.Ticker(sym).history(period="max", auto_adjust=True)
            if len(h) == 0:
                note = f"{sym}: empty history"; continue
            f = h.index[0].tz_localize(None)
            gap = (f - r["issue_open_date"]).days
            if abs(gap) <= 10:
                cand, first, note = sym, f.date(), f"first bar {gap:+d}d vs master listing date"; break
            note = f"{sym}: first bar {gap:+d}d — rejected (namesake or history gap)"
    except Exception as e:
        note = f"error: {e}"
    out.append({"company": r["company"], "year": r["issue_open_date"].year, "query": q,
                "candidate": cand, "first_bar": first, "note": note})
    time.sleep(0.8)

o = pd.DataFrame(out)
o.to_csv(INTERMEDIATE / "symbols_CANDIDATES_cleanquery.csv", index=False)
print(f"candidates found: {o['candidate'].notna().sum()}/{len(o)}")
print(o.groupby("year")["candidate"].agg(lambda x: f"{x.notna().sum()}/{len(x)}").to_string())
print("duplicate candidates:", o["candidate"].dropna()[o["candidate"].dropna().duplicated()].tolist())
print("clash with existing master symbols:",
      sorted(set(o["candidate"].dropna().str.replace(r"\.(NS|BO)$", "", regex=True)) & set(m["symbol"].dropna())))

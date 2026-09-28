"""
check_env.py — preflight. Must pass before any overnight run.

    python check_env.py        # exit 0 = ready, exit 1 = something is wrong
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # ₹ on Windows consoles
import importlib, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
import os; os.chdir(ROOT); sys.path.insert(0, str(ROOT))
results: list[tuple[bool, str, str]] = []


def check(name):
    def wrap(fn):
        try:
            detail = fn() or ""
            results.append((True, name, detail))
        except Exception as e:
            results.append((False, name, f"{type(e).__name__}: {e}"))
        return fn
    return wrap


@check("python >= 3.10")
def _():
    assert sys.version_info >= (3, 10), sys.version
    return sys.version.split()[0]


@check("packages")
def _():
    out = []
    for m in ("pandas", "numpy", "yfinance", "requests", "pdfplumber", "openpyxl"):
        out.append(f"{m} {importlib.import_module(m).__version__}")
    return ", ".join(out)


@check("data/ contract: every dataset resolves to its file(s)")
def _():
    import dataio
    return "; ".join(f"{k}: {', '.join(p.name for p in dataio.find(k))}"
                     for k in dataio.PATTERNS)


@check("data/ contract: loaders parse")
def _():
    import dataio
    m, s, t = dataio.load_master(), dataio.load_nse_spine(), dataio.load_trackers()
    assert len(m) > 0 and len(s) > 0 and len(t) > 0
    assert s["issue_open_date"].notna().mean() > 0.9, "spine issue dates failed to parse"
    assert t["issue_open_date"].notna().mean() > 0.9, "tracker issue dates failed to parse"
    return f"master {len(m)}, spine {len(s)}, trackers {len(t)} rows"


@check("data/ contract: no module reads data/ directly or hardcodes a data/ filename")
def _():
    bad = []
    for p in ROOT.glob("*.py"):
        if p.name in ("dataio.py", "check_env.py"):
            continue
        src = p.read_text(encoding="utf-8")
        if re.search(r"""["']data[/\\]|\.xlsx""", src):
            bad.append(p.name)
    for p in (ROOT / "CLAUDE.md", ROOT / "README.md"):
        if re.search(r"data/[^`\s]*\.xlsx", p.read_text(encoding="utf-8")):
            bad.append(p.name)
    assert not bad, f"direct data/ reference in: {bad}"


@check("master_with_symbols.csv: schema + integrity")
def _():
    import pandas as pd
    df = pd.read_csv(ROOT / "master_with_symbols.csv",
                     parse_dates=["issue_open_date", "listing_date"])
    need = {"company", "symbol", "isin", "bse_code", "issue_open_date", "listing_date"}
    assert need <= set(df.columns), f"missing columns {need - set(df.columns)}"
    assert len(df) == 652, f"{len(df)} rows, expected 652"
    assert df["issue_open_date"].notna().all(), "rows without issue_open_date"
    dup = df["symbol"].dropna().duplicated().sum()
    return (f"{len(df)} rows, symbols {df['symbol'].notna().sum()}, "
            f"truncated names {df['company'].astype(str).str.endswith('...').sum()}, "
            f"duplicate symbols {dup}")


@check("fetch_rhp: batch gated on 5/5 verification; NSE disclaimer not auto-accepted")
def _():
    import json, fetch_rhp
    assert fetch_rhp.NSE_DOWNLOADS_ALLOWED is False, "NSE_DOWNLOADS_ALLOWED must stay False until the user decides"
    v = json.loads(fetch_rhp.VERIFY_FILE.read_text(encoding="utf-8")) if fetch_rhp.VERIFY_FILE.exists() else {}
    return f"resolver verification on file: {v.get('passed', 0)}/{v.get('of', 5)} passed"


@check("network: Yahoo search + Nifty history")
def _():
    import requests, yfinance as yf
    r = requests.get("https://query2.finance.yahoo.com/v1/finance/search",
                     params={"q": "Reliance Industries", "quotesCount": 3},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    n = yf.Ticker("^NSEI").history(period="5d")
    assert len(n) > 0, "no Nifty bars"
    return f"search HTTP {r.status_code}, Nifty last {n['Close'].iloc[-1]:,.0f}"


@check("working dir writable")
def _():
    p = ROOT / ".check_env_write_test"
    p.write_text("ok", encoding="utf-8"); p.unlink()


if __name__ == "__main__":
    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:{width}s}  {detail}")
    bad = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - bad}/{len(results)} checks passed")
    sys.exit(1 if bad else 0)

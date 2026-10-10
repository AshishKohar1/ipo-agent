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


@check("platform")
def _():
    import platform
    return (f"{sys.platform} / {platform.platform()} / {platform.machine()} / "
            f"python {platform.python_version()} ({platform.python_implementation()})")


@check("python >= 3.10 (code minimum)")
def _():
    assert sys.version_info >= (3, 10), sys.version
    return sys.version.split()[0]


@check("requirements.txt pins match what is installed")
def _():
    """OS-aware: the laptop pins are the reference, but an older interpreter (e.g. a cloud
    image on 3.11) legitimately cannot install numpy 2.5.1. Mismatches are reported per
    package with the reason, so a deviation is visible instead of silent."""
    from importlib.metadata import version, PackageNotFoundError
    req = ROOT / "requirements.txt"
    assert req.exists(), "requirements.txt missing"
    pins, notes = {}, []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, want = line.split("==", 1)
        pins[name.strip()] = want.strip()
    for name, want in pins.items():
        try:
            got = version(name)
        except PackageNotFoundError:
            notes.append(f"{name}: NOT INSTALLED (pinned {want})"); continue
        if got != want:
            notes.append(f"{name}: installed {got} != pinned {want}")
    needs = "3.12+" if "numpy" in pins and pins["numpy"] >= "2.5" else "3.10+"
    head = f"{len(pins)} pins, interpreter needs {needs}"
    if notes:
        return head + " | DEVIATIONS: " + "; ".join(notes)
    return head + " | all match"


@check("scikit-learn absent (PLAN.md rule 10) and no module imports it")
def _():
    import importlib.util
    installed = importlib.util.find_spec("sklearn") is not None
    importers = [p.name for p in list(ROOT.glob("*.py")) + list((ROOT / "models").glob("*.py"))
                 if re.search(r"^\s*(import|from)\s+sklearn", p.read_text(encoding="utf-8"), re.M)]
    assert not importers, f"modules import sklearn: {importers}"
    return ("no module imports sklearn" +
            ("; note: sklearn IS installed in this environment but unused"
             if installed else "; not installed"))


@check("statsmodels Logit import path (OS-aware: statsmodels.api may be blocked)")
def _():
    """On the laptop, Windows Application Control blocks statsmodels.tsa, which
    statsmodels.api imports. The framework therefore imports Logit from
    statsmodels.discrete.discrete_model. That path must work on every OS."""
    from statsmodels.discrete.discrete_model import Logit  # noqa: F401
    try:
        import statsmodels.api  # noqa: F401
        api = "statsmodels.api also importable"
    except Exception as e:
        api = f"statsmodels.api blocked ({type(e).__name__}) — expected on this laptop"
    return f"discrete.Logit OK; {api}"


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


@check("data/ contract: no module READS a data/ file by hardcoded name")
def _():
    # What this protects. `dataio` finds every source dataset by GLOB, so a renamed or
    # duplicated source file raises instead of being silently half-loaded. A module that
    # opens `data/<exact name>` itself bypasses that and goes quietly wrong the day the
    # file is renamed.
    #
    # Rewritten 2026-10-10. The old regex was `["']data[/\\]|\.xlsx` - ANY `.xlsx`
    # anywhere, and ANY string starting `data/`. It had been failing on four files, none
    # of which violated anything: `reports/SPOTCHECK.xlsx` (not under data/ at all) and
    # `git("add", "data/rhp_progress.csv")` (a git pathspec for committing output, not a
    # read). A check that reports violations that are not violations stops being read -
    # and CLAUDE.md requires this script to pass before any overnight run, so it has to be
    # able to pass.
    #
    # It now matches a READ of a hardcoded data/ path, which is the thing the contract is
    # about, plus any .xlsx named under data/ in a doc.
    READ = re.compile(
        r"""(read_csv|read_excel|read_json|read_parquet|open|load|Path)\s*\(\s*"""
        r"""[^)]*?["']data[/\\][^"']+["']""")
    bad = []
    for q in ROOT.glob("*.py"):
        if q.name in ("dataio.py", "check_env.py"):
            continue
        for m in READ.finditer(q.read_text(encoding="utf-8")):
            bad.append(f"{q.name}: {m.group(0)[:60]}")
    for q in (ROOT / "CLAUDE.md", ROOT / "README.md"):
        if re.search(r"data/[^`\s]*\.xlsx", q.read_text(encoding="utf-8")):
            bad.append(f"{q.name}: hardcodes a data/*.xlsx filename")
    assert not bad, "data/ read by hardcoded name: " + "; ".join(bad)


@check("data/ contract: the check above can still fail")
def _():
    # A guard that cannot fail is worse than no guard - it reports PASS forever. The
    # rewritten pattern is run against a line that genuinely violates the contract, and
    # against the four shapes that were false positives, and must separate them.
    READ = re.compile(
        r"""(read_csv|read_excel|read_json|read_parquet|open|load|Path)\s*\(\s*"""
        r"""[^)]*?["']data[/\\][^"']+["']""")
    must_catch = [
        'df = pd.read_csv("data/Initial Public Offering 2010.xlsx")',
        "m = pd.read_excel('data/IPO-PastIssue-01-01-2010.xlsx')",
        'open("data/NIFTY50_TRI.csv")',
    ]
    must_allow = [
        'sheet.to_excel(ROOT / "reports" / "SPOTCHECK.xlsx", index=False)',
        'git("add", "data/chittorgarh_backfill.csv", "data/anchor.csv")',
        'OUT = ROOT / "data" / "market_context.csv"',
        'print("writes data/new_listings.csv")',
    ]
    missed = [x for x in must_catch if not READ.search(x)]
    wrong = [x for x in must_allow if READ.search(x)]
    assert not missed, f"the check would NOT catch a real violation: {missed}"
    assert not wrong, f"the check still flags a non-violation: {wrong}"
    return f"catches {len(must_catch)}/{len(must_catch)} real, allows {len(must_allow)}/{len(must_allow)} benign"


@check("master_with_symbols.csv: schema + integrity")
def _():
    import pandas as pd
    df = pd.read_csv(ROOT / "data" / "master_with_symbols.csv",
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

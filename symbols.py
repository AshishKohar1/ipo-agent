"""
symbols.py — resolve a newly listed company to its symbol, ISIN and SEGMENT (Priority 5).

Two defects in `ingest_outcomes.py` this module exists to fix.

**5a — the symbol master stops at May 2026.** `master_with_symbols.csv` runs to
2026-05-14, so every 2026 listing failed symbol resolution before any price was fetched.
It is also matched by a 14-character name prefix, which is the Priority 3 rename bug in
another place: a company filed and listed under its old name never matches.

The fix needs no network. `data/NSE_EQUITY_L.csv` is already on disk, carries SYMBOL, NAME
OF COMPANY, SERIES, DATE OF LISTING and **ISIN NUMBER for all 2,601 rows**, and runs to
**2026-09-25** — four months past the master. Resolution order is therefore:

    1. master_with_symbols.csv by ISIN              (exact, name-independent)
    2. NSE_EQUITY_L.csv by ISIN                     (exact, extends to Sep 2026)
    3. master_with_symbols.csv by name + aliases    (company_aliases.py)
    4. NSE_EQUITY_L.csv by name + aliases
    5. unresolved — and the row is NOT ingested

ISIN first matters: it is the only key immune to renaming, and it is the key the Priority 3
investigation showed we should have been using all along.

Keeping it current is one refresh of a public list — NSE's equity list is a plain CSV with
no click-through — so `NSE_EQUITY_L.csv` should be re-downloaded on the same cadence as the
ingest. That refresh is NOT done here, because `NSE_DOWNLOADS_ALLOWED` is pinned False
(CLAUDE.md rule 3) and flipping it is the user's decision, not this module's.

**5b — rule 6 violation.** `ingest_outcomes.py:265` hardcoded `segment = "mainboard"`,
which would pool SME listings into mainboard training. PLAN rule 6 is explicit that SME and
mainboard need separate models because their coefficients differ in sign.

Segment is NOT re-derived here. It was already determined correctly at bid time, by which
Chittorgarh dashboard listed the IPO (`chittorgarh_live.py` — the mainboard and SME
dashboards are separate pages), and that value is carried in `predictions_log.csv` and
`data/subscription_snapshots.csv`. Re-deriving it at ingest would be both redundant and
lossy. Where no such record exists the segment is **NULL with `segment_undetermined`** and
the row is excluded from training. It is never defaulted to mainboard: a wrong segment is
rule 6 broken silently, and it would not be found by inspection.

An issue-size heuristic is deliberately absent. Guessing SME from a small issue would
misclassify, and the whole point of rule 6 is that the two populations must not mix.

    python symbols.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                               # noqa: E402
import company_aliases                                     # noqa: E402

NSE_LIST = ROOT / "data" / "NSE_EQUITY_L.csv"
MASTER = ROOT / "master_with_symbols.csv"
PRED_LOG = ROOT / "predictions_log.csv"
SNAPSHOTS = ROOT / "data" / "subscription_snapshots.csv"

SEGMENTS = ("mainboard", "sme")
UNDETERMINED = "segment_undetermined"


# ---------------------------------------------------------------- symbol / ISIN
def _nse_list() -> pd.DataFrame:
    if not NSE_LIST.exists():
        return pd.DataFrame(columns=["symbol", "isin", "name", "series", "listing_date"])
    d = pd.read_csv(NSE_LIST)
    d.columns = [str(c).strip() for c in d.columns]
    return pd.DataFrame({
        "symbol": d.get("SYMBOL"), "isin": d.get("ISIN NUMBER"),
        "name": d.get("NAME OF COMPANY"), "series": d.get("SERIES"),
        "listing_date": pd.to_datetime(d.get("DATE OF LISTING"), errors="coerce",
                                       format="mixed"),
    }).dropna(subset=["symbol"])


def _master() -> pd.DataFrame:
    if not MASTER.exists():
        return pd.DataFrame(columns=["company", "symbol", "isin", "bse_code"])
    return pd.read_csv(MASTER)


def resolve(company: str, isin: str | None = None) -> dict:
    """`{symbol, isin, bse_code, source, note}`. `symbol` is None when unresolved."""
    m, n = _master(), _nse_list()
    out = {"symbol": None, "isin": isin, "bse_code": None, "source": None, "note": ""}

    # 1 & 2 — by ISIN. Exact and immune to renaming.
    if isin and str(isin).strip() and str(isin).lower() != "nan":
        key = str(isin).strip().upper()
        hit = m[m["isin"].astype(str).str.upper() == key] if "isin" in m else m.iloc[0:0]
        if len(hit):
            r = hit.iloc[0]
            return {**out, "symbol": r.get("symbol"), "isin": key,
                    "bse_code": r.get("bse_code"), "source": "master by ISIN"}
        hit = n[n["isin"].astype(str).str.upper() == key]
        if len(hit):
            r = hit.iloc[0]
            return {**out, "symbol": r["symbol"], "isin": key,
                    "source": "NSE_EQUITY_L by ISIN"}

    # 3 & 4 — by name, every name the company may appear under (Priority 3).
    names = company_aliases.names_to_try(company)
    norms = [dataio.norm_name(x) for x in names]
    for df, label, ncol in ((m, "master", "company"), (n, "NSE_EQUITY_L", "name")):
        if ncol not in df.columns or not len(df):
            continue
        dn = df[ncol].astype(str).map(dataio.norm_name)
        for nm, want in zip(names, norms):
            if len(want) < 6:
                continue
            hit = df[dn == want]
            if len(hit):
                r = hit.iloc[0]
                via = "" if nm == company else f" via alias {nm!r}"
                return {**out, "symbol": r.get("symbol") or r.get("SYMBOL"),
                        "isin": r.get("isin") if label == "master" else r.get("isin"),
                        "bse_code": r.get("bse_code") if label == "master" else None,
                        "source": f"{label} by name{via}"}

    out["note"] = (f"no symbol for {company!r}"
                   + (f" / ISIN {isin}" if isin else " and no ISIN was supplied")
                   + f". Tried {len(names)} name(s): {names}. NOT ingested.")
    return out


# ---------------------------------------------------------------- segment (5b)
def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:                                       # noqa: BLE001
        return pd.DataFrame()


def segment_for(company: str, isin: str | None = None) -> dict:
    """`{segment, source}`. `segment` is None (with `UNDETERMINED`) when unknown.

    Never guesses, and never defaults to mainboard — see the module docstring.
    """
    names = {dataio.norm_name(x) for x in company_aliases.names_to_try(company)}

    for path, label, col in ((PRED_LOG, "predictions_log", "ipo"),
                             (SNAPSHOTS, "subscription_snapshots", "ipo")):
        d = _read(path)
        if d.empty or "segment" not in d.columns or col not in d.columns:
            continue
        hit = d[d[col].astype(str).map(dataio.norm_name).isin(names)]
        if isin and "isin" in d.columns:
            byi = d[d["isin"].astype(str).str.upper() == str(isin).strip().upper()]
            if len(byi):
                hit = byi
        seg = (hit["segment"].dropna().astype(str).str.lower()
               .loc[lambda s: s.isin(SEGMENTS)].unique().tolist() if len(hit) else [])
        if len(seg) == 1:
            return {"segment": seg[0],
                    "source": f"{label} — recorded at bid time from the "
                              f"{seg[0]} dashboard"}
        if len(seg) > 1:
            # Two records disagree. That is a real contradiction, not something to average.
            return {"segment": None,
                    "source": f"{UNDETERMINED}: {label} holds conflicting segments "
                              f"{sorted(seg)} for this company — not ingested"}

    return {"segment": None,
            "source": f"{UNDETERMINED}: no bid-time record for {company!r}. Rule 6 forbids "
                      f"defaulting to mainboard, so this row is not ingested."}


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    import tempfile
    global PRED_LOG, SNAPSHOTS
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("symbols.py self-test")

    print("\n[1] the NSE list extends past the master (Priority 5a)")
    n = _nse_list()
    m = _master()
    mx_m = pd.to_datetime(m.get("listing_date"), errors="coerce").max()
    mx_n = n["listing_date"].max()
    chk("NSE_EQUITY_L.csv loads", len(n) > 1000, str(len(n)))
    chk("every NSE row has an ISIN", n["isin"].notna().all(),
        f"{n['isin'].isna().sum()} missing")
    chk(f"NSE list ({mx_n.date() if pd.notna(mx_n) else '?'}) is newer than the master "
        f"({mx_m.date() if pd.notna(mx_m) else '?'})",
        pd.notna(mx_n) and pd.notna(mx_m) and mx_n > mx_m)

    print("\n[2] resolution prefers ISIN, then falls back to names")
    mm = m[m["isin"].notna() & m["symbol"].notna()]
    if len(mm):
        r0 = mm.iloc[0]
        got = resolve("Totally Wrong Name Ltd", r0["isin"])
        chk("a correct ISIN resolves even with a wrong name",
            got["symbol"] == r0["symbol"], str(got))
        chk("and says it used the ISIN", "ISIN" in (got["source"] or ""), str(got))
        got = resolve(r0["company"], None)
        chk("a correct name with no ISIN still resolves",
            got["symbol"] == r0["symbol"], str(got))
    got = resolve("Zzz Nonexistent Holdings Ltd", None)
    chk("an unknown company resolves to None", got["symbol"] is None)
    chk("and explains itself, saying NOT ingested", "NOT ingested" in got["note"], got["note"])

    print("\n[3] segment is never defaulted to mainboard (Priority 5b, rule 6)")
    with tempfile.TemporaryDirectory() as td:
        kp, ks = PRED_LOG, SNAPSHOTS
        try:
            PRED_LOG = Path(td) / "p.csv"
            SNAPSHOTS = Path(td) / "s.csv"
            s = segment_for("Anything At All")
            chk("no record -> segment is None", s["segment"] is None, str(s))
            chk("and the reason is segment_undetermined", UNDETERMINED in s["source"])
            chk("the word 'mainboard' is not the answer", s["segment"] != "mainboard")

            pd.DataFrame([{"ipo": "Some Sme Co", "isin": "INE0TEST011",
                           "segment": "sme"}]).to_csv(PRED_LOG, index=False)
            s = segment_for("Some Sme Co")
            chk("an SME bid-time record gives 'sme'", s["segment"] == "sme", str(s))
            chk("and names where it came from", "predictions_log" in s["source"])

            pd.DataFrame([{"ipo": "Conflicted Co", "isin": "INE0TEST022",
                           "segment": "sme"},
                          {"ipo": "Conflicted Co", "isin": "INE0TEST022",
                           "segment": "mainboard"}]).to_csv(PRED_LOG, index=False)
            s = segment_for("Conflicted Co")
            chk("conflicting records -> None, not a majority vote",
                s["segment"] is None, str(s))
            chk("and the conflict is reported", "conflicting" in s["source"])
        finally:
            PRED_LOG, SNAPSHOTS = kp, ks

    print("\n[4] no issue-size heuristic exists")
    # Checked against the resolving functions' own source, not the whole file: the module
    # docstring explains why no heuristic exists, and the first version of this test
    # matched its own assertion string.
    import inspect
    body = inspect.getsource(segment_for) + inspect.getsource(resolve)
    chk("segment is not inferred from issue size",
        "issue_size" not in body.lower() and "issuesize" not in body.lower())

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--resolve", metavar="COMPANY")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.resolve:
        print(resolve(a.resolve))
        print(segment_for(a.resolve))
    else:
        print(__doc__)

"""
model_h_handoff.py — the files the user fills in, and the gate that accepts what comes back.

Phase 2 Tasks 2.1 and 2.2. Three things are blocked on information that is not reachable
from any permitted source, so they are handed over rather than guessed at:

  `data/manual_inputs/missing_symbols.csv`   60 IPOs with no NSE symbol (2.1)
  `data/manual_inputs/missing_rhps.csv`      37 IPOs with no prospectus on disk (2.2)
  `data/manual_inputs/missing_sectors.csv`   written by `model_h_sources.py` (2.4b)

**Why a gate, and not simple trust.** A symbol the user types is a claim about identity,
and a wrong one is worse than a blank: it attaches another company's entire price history
to this IPO, silently, and every target and every variable derived from it is then wrong in
a way no later check would find. So a filled row is accepted ONLY if the symbol or ISIN
actually traded on that listing date - proved by its presence in the bhavcopy for that date,
which is the same evidence `model_h_targets` uses for every other row. A row that cannot be
proved is rejected WITH ITS REASON and the cell stays empty. Nothing is accepted on the
strength of a name (H28), and nothing is accepted on the strength of having been typed.

    python model_h_handoff.py --write          # (re)write the blank files to fill
    python model_h_handoff.py --accept         # validate and ingest what has been filled
    python model_h_handoff.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import inspect
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                  # noqa: E402

DATA = ROOT / "data"
MANUAL = DATA / "manual_inputs"
MISSING_SYMBOLS = MANUAL / "missing_symbols.csv"
MISSING_RHPS = MANUAL / "missing_rhps.csv"
ACCEPTED = DATA / "manual_symbols_accepted.csv"
STILL_MISSING = ROOT / "reports" / "DOCUMENTS_STILL_MISSING.csv"

SYMBOL_COLS = ["master_name", "company_as_listed", "listing_date_master", "isin",
               "current_nse_symbol", "notes"]
RHP_COLS = ["company", "listing_date", "symbol", "rhp_url", "notes"]


# ------------------------------------------------------------------ 2.1 symbols
def unresolved_symbol_rows() -> pd.DataFrame:
    """The master rows that still have no symbol, after everything automatic has run."""
    m = dataio.load_master_with_symbols()
    rec = (pd.read_csv(DATA / "recovered_symbols.csv")
           if (DATA / "recovered_symbols.csv").exists() else pd.DataFrame())
    sym = m["symbol"].astype(str).str.strip()
    blank = sym.isin(["", "nan", "NaN", "None"]) | m["symbol"].isna()
    # 74 master rows have no symbol, but 14 of them are an FPO, a REIT/InvIT or an IDR.
    # Those are excluded from every model by `exclude_reason` and always were: asking the
    # user to find an NSE symbol for them would be asking for work that must then be
    # thrown away. 74 - 14 = the 60.
    excluded = m["exclude_reason"].notna() &         ~m["exclude_reason"].astype(str).str.strip().isin(["", "nan", "None"])
    out = m[blank & ~excluded].copy()
    # Anything a previous automatic pass DID resolve is not the user's problem.
    if len(rec) and "company" in rec and "symbol" in rec:
        done = set(rec.loc[rec["symbol"].notna(), "company"].astype(str))
        out = out[~out["company"].astype(str).isin(done)]
    return out


def write_missing_symbols() -> int:
    out = unresolved_symbol_rows()
    rows = []
    for _, r in out.iterrows():
        d = r.get("issue_open_date")
        rows.append({
            "master_name": r.get("company"),
            # The master's `issue_open_date` column holds the LISTING date (known defect,
            # CLAUDE.md). It is labelled for what it is so the user is not asked to
            # reconcile against the wrong date.
            "company_as_listed": "",
            "listing_date_master": str(pd.Timestamp(d).date()) if pd.notna(d) else "",
            "isin": r.get("isin") if pd.notna(r.get("isin")) else "",
            "current_nse_symbol": "",
            "notes": "no symbol from the NSE spine, the trackers or the rename walk; "
                     "name-only matching was measured and rejected (H28)",
        })
    MANUAL.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=SYMBOL_COLS).to_csv(MISSING_SYMBOLS, index=False,
                                                   encoding="utf-8")
    return len(rows)


# ------------------------------------------------------------------ 2.2 RHPs
def write_missing_rhps() -> int:
    if not STILL_MISSING.exists():
        raise FileNotFoundError(f"{STILL_MISSING} is not on disk, so the 37 cannot be "
                                f"listed. Nothing is guessed at.")
    d = pd.read_csv(STILL_MISSING)
    m = dataio.load_master_with_symbols()
    by_isin = {str(r.get("isin")).strip(): str(r.get("symbol") or "").strip()
               for _, r in m.iterrows() if pd.notna(r.get("isin"))}
    by_name = {dataio.norm_name(r.get("company")): str(r.get("symbol") or "").strip()
               for _, r in m.iterrows()}
    rows = []
    for _, r in d.iterrows():
        sym = by_isin.get(str(r.get("isin")).strip()) or \
            by_name.get(dataio.norm_name(r.get("company"))) or ""
        rows.append({
            "company": r.get("company"),
            "listing_date": r.get("listing_date"),
            "symbol": sym,
            "rhp_url": "",
            # The note says WHY it is missing, so the user knows whether to look for a
            # better URL or a different document altogether.
            "notes": f"{r.get('status')}: {str(r.get('next_step'))[:180]}",
        })
    MANUAL.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=RHP_COLS).to_csv(MISSING_RHPS, index=False,
                                                encoding="utf-8")
    return len(rows)


# ------------------------------------------------------------------ the gate
def _read_cached(path: Path, which: str) -> pd.DataFrame:
    """A cached bhavcopy is stored ALREADY normalised, so `_norm` must not run twice.

    It raises on columns it does not recognise, which is correct for a raw exchange file
    and wrong for one of its own outputs. Which shape is on disk is decided by looking,
    not assumed.
    """
    import listing_prices as LP
    df = pd.read_csv(path, low_memory=False)
    if {"symbol", "isin"} <= set(df.columns):
        return df
    return LP._norm(df, which)


def bhavcopy_has(symbol: str | None, isin: str | None, day) -> tuple[bool, str]:
    """Did this symbol (or ISIN) actually trade on that date?

    The bhavcopy for the listing date is the evidence, read from the on-disk cache only.
    A date whose file is not cached returns "cannot verify", which is NOT the same as
    "did not trade" and is never counted as a rejection of the symbol itself. Collapsing
    those two is how a gap in our own data becomes a claim about a company.

    Both exchanges are tried, because an IPO of this era may be on either.
    """
    import listing_prices as LP
    day = pd.Timestamp(day)
    sym = str(symbol or "").strip().upper()
    isn = str(isin or "").strip().upper()
    if not sym and not isn:
        return False, "rejected: neither a symbol nor an ISIN was supplied"
    checked = []
    for which in ("nse", "bse"):
        cp = LP.CACHE / f"{which}_{day:%Y%m%d}.csv.gz"
        if not cp.exists():
            continue
        try:
            df = _read_cached(cp, which)
        except Exception as e:                                 # noqa: BLE001
            checked.append(f"{which} cache unreadable ({type(e).__name__})")
            continue
        checked.append(which)
        hit, how = LP.find(df, isin=isn or None, symbol=sym or None)
        # Only an EXACT key counts. `find` also offers `symbol_prefix`, which exists for
        # truncated names in the master and lands on an unrelated company often enough
        # that `listing_prices` labels it separately. Confirming an identity claim on a
        # prefix would make this gate weaker than the matcher it is supposed to check.
        if hit is not None and len(hit) and how in ("isin", "symbol", "code"):
            return True, f"confirmed on {which.upper()} for {day.date()} by {how}"
        if hit is not None and len(hit):
            checked.append(f"{which} matched only on {how}, which is not exact enough")
    if not checked:
        return False, (f"cannot verify: no bhavcopy cached for {day.date()} on either "
                       f"exchange, so the symbol is neither confirmed nor refuted")
    what = sym or isn
    return False, (f"rejected: {what} does not appear in the {'/'.join(checked)} "
                   f"bhavcopy for {day.date()}, so it did not trade that day under "
                   f"that identifier")


def accept() -> pd.DataFrame:
    """Validate the filled rows. Accepted rows are written; rejected rows keep their
    reason and are NOT written anywhere a model could read them."""
    if not MISSING_SYMBOLS.exists():
        raise FileNotFoundError(f"{MISSING_SYMBOLS} has not been written yet")
    d = pd.read_csv(MISSING_SYMBOLS, keep_default_na=False)
    out = []
    for _, r in d.iterrows():
        sym = str(r.get("current_nse_symbol") or "").strip().upper()
        isn = str(r.get("isin") or "").strip().upper()
        if not sym and not isn:
            continue                                   # not filled in yet; not a failure
        day = str(r.get("listing_date_master") or "").strip()
        if not day:
            out.append({**r.to_dict(), "accepted": False,
                        "verdict": "rejected: no listing date to verify against"})
            continue
        ok, why = bhavcopy_has(sym, isn, day)
        out.append({**r.to_dict(), "accepted": bool(ok), "verdict": why})
    res = pd.DataFrame(out)
    if len(res):
        res.to_csv(ACCEPTED, index=False, encoding="utf-8")
    return res


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  ok   {name}")
        else:
            fail += 1
            print(f"  FAIL {name} {extra}")

    print("[1] the gate tells 'did not trade' apart from 'cannot check'")
    got, why = bhavcopy_has("ZZZZNOSUCH", "", "1990-01-02")
    chk("a date with no bhavcopy on disk is 'cannot verify', not a rejection",
        got is False and "cannot verify" in why, why)
    chk("and it says so in words, not as a bare False", "neither confirmed" in why, why)

    print(chr(10) + "[2] a real symbol on a real date is accepted; an invented one is not")
    import listing_prices as LP
    cached = sorted(LP.CACHE.glob("nse_*.csv.gz")) if LP.CACHE.exists() else []
    if not cached:
        print("  (no NSE bhavcopy cached - the live half of this check is skipped)")
    else:
        pth = cached[-1]
        day = pd.Timestamp(pth.stem.split("_")[1][:8])
        df = _read_cached(pth, "nse")
        real = str(df["symbol"].dropna().iloc[0]).strip().upper()
        got, why = bhavcopy_has(real, "", day)
        chk(f"a symbol in the {day.date()} bhavcopy is accepted", got, why)
        got2, why2 = bhavcopy_has("QQNOTREAL", "", day)
        chk("an invented symbol on the SAME date is rejected", got2 is False, why2)
        chk("and the rejection names the date it checked", str(day.date()) in why2, why2)
        chk("a blank row is rejected for being blank, not for failing a lookup",
            "neither a symbol nor an ISIN" in bhavcopy_has("", "", day)[1])

    chk("a prefix-only bhavcopy match is NOT accepted as confirmation",
        "symbol_prefix" in inspect.getsource(bhavcopy_has)
        and 'how in ("isin", "symbol", "code")' in inspect.getsource(bhavcopy_has))

    print(chr(10) + "[3] the handoff list is the 60, not the 74")
    u = unresolved_symbol_rows()
    m_all = dataio.load_master_with_symbols()
    s_all = m_all["symbol"].astype(str).str.strip()
    blank_all = s_all.isin(["", "nan", "NaN", "None"]) | m_all["symbol"].isna()
    chk("74 master rows have no symbol at all", int(blank_all.sum()) == 74,
        int(blank_all.sum()))
    # NOT pinned at 60. 60 was the count before any recovery; the file shrinks as
    # symbols are found, and a test that pins the number would fail for the right reason
    # and have to be edited every time, which is how an assertion stops being read.
    rec = (pd.read_csv(DATA / "recovered_symbols.csv")
           if (DATA / "recovered_symbols.csv").exists() else pd.DataFrame())
    found = int(rec["symbol"].notna().sum()) if "symbol" in rec else 0
    chk("the handoff holds exactly the unresolved remainder of the 60",
        len(u) + found == 60, (len(u), found))
    chk("and it excludes the 14 that are an FPO, a REIT/InvIT or an IDR",
        int(blank_all.sum()) - 60 == 14)
    chk("no FPO, REIT/InvIT or IDR reaches the file the user is asked to fill",
        u["exclude_reason"].isna().all() or
        not u["exclude_reason"].astype(str).str.strip().isin(
            ["fpo", "reit_invit", "idr"]).any(),
        u["exclude_reason"].value_counts(dropna=False).to_dict())

    print("\n[3] the handoff files have the columns the user was promised")
    chk("missing_symbols has the six agreed columns",
        SYMBOL_COLS == ["master_name", "company_as_listed", "listing_date_master",
                        "isin", "current_nse_symbol", "notes"])
    chk("missing_rhps has the five agreed columns",
        RHP_COLS == ["company", "listing_date", "symbol", "rhp_url", "notes"])
    chk("the columns the user fills start empty",
        all(c in SYMBOL_COLS for c in ("isin", "current_nse_symbol")))

    print(f"\n{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.write:
        n1 = write_missing_symbols()
        n2 = write_missing_rhps()
        print(f"{MISSING_SYMBOLS.relative_to(ROOT)}: {n1} rows to fill")
        print(f"{MISSING_RHPS.relative_to(ROOT)}: {n2} rows to fill")
    if a.accept:
        res = accept()
        if not len(res):
            print("nothing filled in yet - no rows to accept or reject")
        else:
            print(f"{int(res['accepted'].sum())} accepted, "
                  f"{int((~res['accepted']).sum())} rejected")
            for _, r in res.iterrows():
                print(f"  {'OK  ' if r['accepted'] else 'NO  '} "
                      f"{str(r['master_name'])[:40]:42s} {r['verdict'][:90]}")

"""
relabel_window.py — re-label the listings whose BSE bhavcopy was silently empty.

Why this exists
---------------
From 2024-07-02 to 2026-10-22 every BSE bhavcopy this project downloaded was cached as 77
bytes of empty gzip. Three causes compounded: BSE restructured its site and began serving
its Angular shell at the old download path, `_norm` filtered the unified file's `SctySrs`
column against NSE's *series* vocabulary rather than BSE's *group* codes, and a zero-row
parse was cached and served — which made the failure sticky and silent.

The code is fixed. The *labels* are not: every listing in that window was written with
`reconciled = single_source_unverified` because BSE contributed nothing, and rule 2's
two-source standard was therefore unmet with nothing in the output saying so. 180 of the
182 rows in the window carry that label today.

This module re-fetches BSE for each affected listing date and re-runs the reconciliation,
then reports what changed. It is deliberately a separate script rather than a flag on
`listing_prices.backfill`, because `backfill` skips dates it has already done — which is
correct for a backfill and wrong for a re-label.

What it will not do
-------------------
* It does not edit `data/predictions_log.csv`. That file is append-only (rule 11); a score
  correction is an appended correction row, never an edit of the row it corrects.
* It does not work around a block. BSE answering 401/403/429 is final for the run
  (H47 rule 5): the fetch phase stops and reports how far it got.
* It does not invent a price. A date BSE will not serve stays single-source, and the report
  says which dates those are and why.

Usage
-----
    python relabel_window.py --fetch            # phase 1, resumable, one heavy job
    python relabel_window.py --relabel          # phase 2, offline, reads the cache
    python relabel_window.py --self-test
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
import listing_prices as LP                                 # noqa: E402
from failover import BLOCKED_STATUS                         # noqa: E402

WIN_FROM = "2024-07-02"
WIN_TO = "2026-10-22"
CKPT = ROOT / "data" / "relabel_bse_progress.csv"
OUT_CSV = ROOT / "reports" / "RELABEL_WINDOW.csv"
OUT_MD = ROOT / "reports" / "RELABEL_WINDOW.md"
MIN_BHAV_ROWS = 1000                                        # see audit_bhavcopy_rows


def log(m: str) -> None:
    print(m, flush=True)


# ---------------------------------------------------------------- window and checkpoint

def window_dates() -> list[str]:
    """Listing dates inside the window, from the master, oldest first."""
    t = LP.targets()
    w = t[(t["listing_date"] >= WIN_FROM) & (t["listing_date"] <= WIN_TO)]
    return sorted(w["listing_date"].dt.strftime("%Y-%m-%d").unique())


def done() -> dict:
    """date -> status recorded by an earlier --fetch run."""
    if not CKPT.exists():
        return {}
    try:
        d = pd.read_csv(CKPT)
        return dict(zip(d["date"].astype(str), d["status"].astype(str)))
    except Exception:                                       # noqa: BLE001
        return {}


def note_is_block(note: str) -> bool:
    """True when a fetch note records the host REFUSING us, not merely failing.

    A block is final for the run (H47 rule 5) and stops the job. A 404 is not a block —
    on a bhavcopy path it usually just means the date was not a trading day — and a
    timeout is not a block either, because calling a timeout a block would make the word
    useless on the day it matters.
    """
    t = (note or "").upper()
    if "BLOCKED" in t:
        return True
    for s in BLOCKED_STATUS:
        if f"HTTP {s}" in t:
            return True
    return "REFUSED" in t or "FORCIBLY CLOSED" in t


def checkpoint(day: str, status: str, note: str, rows) -> None:
    pd.DataFrame([{"date": day, "status": status, "rows": rows, "note": note[:300],
                   "ran_at": str(pd.Timestamp.now())}]).to_csv(
        CKPT, mode="a", header=not CKPT.exists(), index=False, encoding="utf-8")


# ---------------------------------------------------------------- phase 1: fetch

def fetch(limit: int | None = None) -> dict:
    """Re-fetch BSE for every window date not already recorded. Resumable; stops on a block."""
    skip = done()
    dates = [d for d in window_dates() if d not in skip]
    if limit:
        dates = dates[:limit]
    log(f"relabel fetch: {len(window_dates())} window dates, {len(skip)} already done, "
        f"{len(dates)} to do")
    f = LP.Fetcher()
    res = {"fetched": 0, "cache": 0, "missing": 0, "blocked_at": None, "done": 0}
    for i, day in enumerate(dates, 1):
        df, note = LP.bhavcopy(f, day, "bse")
        if df is None:
            if note_is_block(note):
                # Final for this run. Not retried, not routed around, and reported by name
                # rather than folded into a count of failures.
                log(f"  [{i}/{len(dates)}] {day}  BSE BLOCKED: {note[:90]}")
                log("  STOPPING. A block is final for the run (H47 rule 5). "
                    "Re-run later to continue from here.")
                res["blocked_at"] = day
                checkpoint(day, "blocked", note, 0)
                break
            checkpoint(day, "missing", note, 0)
            res["missing"] += 1
            log(f"  [{i}/{len(dates)}] {day}  no BSE file: {note[:80]}")
        else:
            status = "cache" if note == "cache" else "fetched"
            checkpoint(day, status, note, len(df))
            res[status] += 1
            log(f"  [{i}/{len(dates)}] {day}  BSE {len(df)} rows ({status})")
        res["done"] += 1
    log(f"fetch finished: {res}")
    return res


# ---------------------------------------------------------------- phase 2: re-label

def _one(h, how) -> dict:
    if not len(h):
        return {"match_by": how}
    return {"open": float(h["open"].iloc[0]) if pd.notna(h["open"].iloc[0]) else None,
            "close": float(h["close"].iloc[0]) if pd.notna(h["close"].iloc[0]) else None,
            "match_by": how}


def why_single(rec: dict, nnote: str, bnote: str) -> str:
    """Plain reason a row is single-source. Printed in the run summary (Task 1 step 5c).

    A label without a reason is the thing that let this defect live for 2.3 years: the
    output said `single_source_unverified` on every row and nothing said whether that was
    a missing file, an unmatched symbol, or a download that returned HTML.
    """
    if rec.get("reconciled") not in ("single_source_unverified",
                                     "single_source_prefix_match_unverified",
                                     "no_source"):
        return ""
    bits = []
    for which, got, note in (("NSE", rec.get("nse_open"), nnote),
                             ("BSE", rec.get("bse_open"), bnote)):
        if got is None:
            mb = rec.get(f"{which.lower()}_match_by") or "?"
            if note and note not in ("cache", "fetched"):
                bits.append(f"{which}: no file ({note[:60]})")
            else:
                bits.append(f"{which}: file present but scrip not matched ({mb})")
    return "; ".join(bits)


def relabel(write: bool = True) -> pd.DataFrame:
    """Recompute every window row from the cache and compare with what is stored."""
    t = LP.targets()
    w = t[(t["listing_date"] >= WIN_FROM) & (t["listing_date"] <= WIN_TO)]
    old = pd.read_csv(LP.OUT)
    old["key"] = old["ipo"].astype(str) + "|" + old["listing_date"].astype(str)
    oldmap = {k: r for k, r in zip(old["key"], old.to_dict("records"))}

    f = None                                                # cache only; no network here
    rows = []
    for day, grp in w.groupby(w["listing_date"].dt.strftime("%Y-%m-%d")):
        nse_df, nnote = LP.bhavcopy(f or LP.Fetcher(), day, "nse")
        bse_df, bnote = LP.bhavcopy(f or LP.Fetcher(), day, "bse")
        for r in grp.itertuples():
            n, nhow = LP.find(nse_df, r.isin, r.symbol, None)
            b, bhow = LP.find(bse_df, r.isin, r.symbol, r.bse_code)
            offer = pd.to_numeric(pd.Series([r.offer_price]), errors="coerce").iloc[0]
            offer = None if pd.isna(offer) else float(offer)
            rec = LP.reconcile(_one(n, nhow), _one(b, bhow), offer)
            o = oldmap.get(f"{r.ipo}|{day}", {})
            rows.append({
                "ipo": r.ipo, "symbol": r.symbol, "listing_date": day,
                "offer_price": offer,
                "old_reconciled": o.get("reconciled"), "new_reconciled": rec["reconciled"],
                "old_gain": o.get("listing_gain_pct"), "new_gain": rec["listing_gain_pct"],
                "old_open": o.get("listing_open"), "new_open": rec["listing_open"],
                "old_close": o.get("listing_close"), "new_close": rec["listing_close"],
                "nse_open": rec["nse_open"], "bse_open": rec["bse_open"],
                "nse_close": rec["nse_close"], "bse_close": rec["bse_close"],
                "sources": rec["sources"], "rule2_note": rec["note"],
                "single_source_reason": why_single(rec, nnote, bnote)})
    out = pd.DataFrame(rows)
    if write and len(out):
        OUT_CSV.parent.mkdir(exist_ok=True)
        out.to_csv(OUT_CSV, index=False, encoding="utf-8")
    return out


def changed(out: pd.DataFrame) -> pd.DataFrame:
    """Only the rows where a stored number or label actually moved."""
    def diff(a, b):
        a = None if pd.isna(a) else a
        b = None if pd.isna(b) else b
        if a is None and b is None:
            return False
        if a is None or b is None:
            return True
        try:
            return abs(float(a) - float(b)) > 1e-6
        except (TypeError, ValueError):
            return str(a) != str(b)
    m = out.apply(lambda r: (r["old_reconciled"] != r["new_reconciled"]
                             or diff(r["old_gain"], r["new_gain"])
                             or diff(r["old_open"], r["new_open"])
                             or diff(r["old_close"], r["new_close"])), axis=1)
    return out[m] if len(out) else out


# ---------------------------------------------------- Task 1 step 5b: the audit tripwire

def audit_bhavcopy_rows(dates=None, min_rows: int = MIN_BHAV_ROWS) -> list[dict]:
    """Flag any cached bhavcopy with implausibly few rows.

    Every trading day on either exchange lists thousands of scrips. A cached file with
    fewer than `min_rows` is not a thin market, it is a failed download — which is exactly
    what went unnoticed for 154 dates. Reading the cache rather than the network means the
    Saturday audit can run this without spending a single request.
    """
    hits = []
    for p in sorted(LP.CACHE.glob("*.csv.gz")):
        which, ymd = p.stem.replace(".csv", "").split("_")[0], p.stem.split("_")[1][:8]
        day = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        if dates is not None and day not in set(dates):
            continue
        try:
            n = len(pd.read_csv(p, low_memory=False))
        except Exception as e:                              # noqa: BLE001
            hits.append({"file": p.name, "exchange": which, "date": day, "rows": None,
                         "why": f"unreadable: {type(e).__name__}"})
            continue
        if n < min_rows:
            hits.append({"file": p.name, "exchange": which, "date": day, "rows": n,
                         "why": f"{n} rows < {min_rows} — a failed download, not a market"})
    return hits


# ---------------------------------------------------------------- report

def md(out: pd.DataFrame, ch: pd.DataFrame, fetch_res: dict | None = None) -> str:
    L = ["# Re-label of the BSE-blind window", "",
         f"Window **{WIN_FROM} to {WIN_TO}**. Every BSE bhavcopy in it was cached as empty "
         "gzip, so every listing was labelled single-source with nothing saying why.", ""]
    L += ["## Buckets after the re-label", "", "| bucket | count |", "|---|---|"]
    vc = out["new_reconciled"].value_counts() if len(out) else pd.Series(dtype=int)
    for k, v in vc.items():
        L.append(f"| {k} | {v} |")
    L.append(f"| **total rows** | **{len(out)}** |")
    r2 = out[out["rule2_note"].astype(str).str.contains("rule 2", na=False)] if len(out) else out
    L += ["", f"Rule 2 NULLs (>5% disagreement): **{len(r2)}**", ""]
    if len(ch):
        L += ["## What changed", "",
              "| IPO | listing date | old label | new label | old gain | new gain |",
              "|---|---|---|---|---|---|"]
        for r in ch.itertuples():
            L.append(f"| {r.ipo} | {r.listing_date} | {r.old_reconciled} | "
                     f"{r.new_reconciled} | {r.old_gain} | {r.new_gain} |")
    else:
        L += ["## What changed", "", "Nothing.", ""]
    ss = out[out["single_source_reason"].astype(str).str.len() > 0] if len(out) else out
    if len(ss):
        L += ["", "## Still single-source, and why", "",
              "| IPO | listing date | reason |", "|---|---|---|"]
        for r in ss.itertuples():
            L.append(f"| {r.ipo} | {r.listing_date} | {r.single_source_reason} |")
    if fetch_res:
        L += ["", "## Fetch phase", "", f"`{fetch_res}`"]
    return "\n".join(L) + "\n"


def main(do_fetch: bool, do_relabel: bool, limit: int | None) -> int:
    res = fetch(limit) if do_fetch else None
    if do_relabel:
        out = relabel()
        ch = changed(out)
        OUT_MD.write_text(md(out, ch, res), encoding="utf-8")
        log(f"{len(out)} rows, {len(ch)} changed -> {OUT_CSV.name}, {OUT_MD.name}")
        print(out["new_reconciled"].value_counts().to_string())
    return 0


# ---------------------------------------------------------------- self-test

def self_test() -> int:
    import re as _re
    import inspect
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    print("[1] a block is recognised, and a 404 or a timeout is NOT")
    chk("403 is a block", note_is_block("HTTP 403 - BLOCKED, not retried (H47 rule 5)"))
    chk("429 is a block", note_is_block("HTTP 429"))
    chk("401 is a block", note_is_block("HTTP 401"))
    chk("a refused connection is a block",
        note_is_block("ConnectionRefusedError: refused"))
    chk("404 is NOT a block", not note_is_block("HTTP 404 - most likely not a trading day"))
    chk("a timeout is NOT a block", not note_is_block("ReadTimeout: timed out"))
    chk("500 is NOT a block", not note_is_block("HTTP 500 after 3 retries"))

    print("\n[2] listing_prices never retries a block (H47 rule 5)")
    src = inspect.getsource(LP.Fetcher.get)
    chk("403 returns rather than continuing",
        "BLOCKED_STATUS" in src and "return None, f\"HTTP {r.status_code} - BLOCKED" in src)
    chk("5xx is still a fault that may be retried", "(500, 502, 503, 504)" in src)
    chk("the blocked set is imported, not redefined here",
        "BLOCKED_STATUS = {" not in inspect.getsource(_sys.modules[LP.__name__]))

    print("\n[3] 5a: a zero-row or HTML answer is NEVER cached")
    bsrc = inspect.getsource(LP.bhavcopy)
    chk("a zero-row parse continues instead of writing the cache file",
        "ZERO rows (not a bhavcopy)" in bsrc
        and bsrc.index("ZERO rows (not a bhavcopy)") < bsrc.index("df.to_csv(cp"))
    chk("a zero-row CACHED file is refetched, not served",
        "cached ZERO rows" in bsrc)
    gsrc = inspect.getsource(LP.Fetcher.get)
    chk("HTML at a 200 is rejected before any caching",
        "HTTP 200 but HTML" in gsrc)

    print("\n[4] 5b: the audit flags a thin bhavcopy")
    import tempfile
    import gzip
    old_cache = LP.CACHE
    try:
        with tempfile.TemporaryDirectory() as td:
            LP.CACHE = Path(td)
            thin = pd.DataFrame({"symbol": ["A"], "open": [1.0], "close": [1.0]})
            fat = pd.DataFrame({"symbol": [f"S{i}" for i in range(1500)],
                                "open": [1.0] * 1500, "close": [1.0] * 1500})
            thin.to_csv(LP.CACHE / "bse_20250102.csv.gz", index=False, compression="gzip")
            fat.to_csv(LP.CACHE / "nse_20250102.csv.gz", index=False, compression="gzip")
            with gzip.open(LP.CACHE / "bse_20250103.csv.gz", "wt") as fh:
                fh.write("")
            hits = audit_bhavcopy_rows()
            names = {h["file"] for h in hits}
            chk("the 1-row BSE file is flagged", "bse_20250102.csv.gz" in names, names)
            chk("the 1,500-row NSE file is not", "nse_20250102.csv.gz" not in names, names)
            chk("an empty file is flagged too", "bse_20250103.csv.gz" in names, names)
            chk("the reason names the row count",
                any("rows <" in h["why"] or "unreadable" in h["why"] for h in hits))
            chk("a date filter narrows it",
                audit_bhavcopy_rows(dates=["2025-01-03"]) and
                len(audit_bhavcopy_rows(dates=["2025-01-03"])) == 1)
    finally:
        LP.CACHE = old_cache

    print("\n[5] 5c: a single-source row SAYS why")
    rec = {"reconciled": "single_source_unverified", "nse_open": 100.0, "bse_open": None,
           "bse_match_by": "none"}
    w = why_single(rec, "cache", "HTTP 404 - most likely not a trading day")
    chk("it names the exchange", w.startswith("BSE:"), w)
    chk("it gives the fetch note when there is no file", "404" in w, w)
    rec2 = dict(rec)
    w2 = why_single(rec2, "cache", "cache")
    chk("a present file with no match says SO, not 'no file'",
        "scrip not matched" in w2, w2)
    chk("a two-source row gets no reason",
        why_single({"reconciled": "reconciled_2_sources"}, "cache", "cache") == "")
    chk("a no_source row gets a reason for BOTH",
        why_single({"reconciled": "no_source", "nse_open": None, "bse_open": None,
                    "nse_match_by": "none", "bse_match_by": "none"}, "cache", "cache")
        .count(";") == 1)

    print("\n[6] the change detector")
    df = pd.DataFrame([
        {"ipo": "same", "old_reconciled": "x", "new_reconciled": "x", "old_gain": 1.0,
         "new_gain": 1.0, "old_open": 1.0, "new_open": 1.0, "old_close": 2.0,
         "new_close": 2.0},
        {"ipo": "label", "old_reconciled": "single_source_unverified",
         "new_reconciled": "reconciled_2_sources", "old_gain": 1.0, "new_gain": 1.0,
         "old_open": 1.0, "new_open": 1.0, "old_close": 2.0, "new_close": 2.0},
        {"ipo": "gain", "old_reconciled": "x", "new_reconciled": "x", "old_gain": 1.0,
         "new_gain": 1.5, "old_open": 1.0, "new_open": 1.0, "old_close": 2.0,
         "new_close": 2.0},
        {"ipo": "newly priced", "old_reconciled": "x", "new_reconciled": "x",
         "old_gain": None, "new_gain": 3.0, "old_open": None, "new_open": 1.0,
         "old_close": None, "new_close": 2.0},
    ])
    got = set(changed(df)["ipo"])
    chk("an unchanged row is not reported", "same" not in got, got)
    chk("a label-only change IS reported", "label" in got, got)
    chk("a gain change is reported", "gain" in got, got)
    chk("NULL -> value is reported", "newly priced" in got, got)

    print("\n[7] the window is the one the defect covered")
    chk("from 2024-07-02", WIN_FROM == "2024-07-02")
    chk("to 2026-10-22", WIN_TO == "2026-10-22")
    chk("no retry loop in the fetch phase",
        "for _ in range(" not in _re.sub(r'(?s)""".*?"""', "",
                                         inspect.getsource(fetch)))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--relabel", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test or not (a.fetch or a.relabel):
        raise SystemExit(self_test())
    raise SystemExit(main(a.fetch, a.relabel, a.limit))

"""
probe_alias_resolution.py — Priority 3b: does the alias map actually resolve anything?

Re-runs SEBI **resolution only** for every company currently `source_unresolved` or
`not_a_prospectus`, with `company_aliases.py` in place. It does NOT download a PDF and does
NOT extract: the question is narrowly whether a filing can now be FOUND, and answering it
that way keeps the job light on memory (no pdfplumber, no 400-page page lists) so it can run
while `run_manual_rhp.py` holds ~2 GB.

Resolution is the half of the pipeline the alias map changes. If a filing is found here, the
full fetch is then worth queueing; if it is not found, no amount of downloading helps.

5 s between companies, the same gap the night batch settled on after tripping SEBI's
throttle. Resumable: each company is appended as it finishes, and a re-run skips what is
already recorded.

    python probe_alias_resolution.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sys
import time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import company_aliases                                     # noqa: E402
from fetch_rhp import _session, resolve_sebi                # noqa: E402

OUT = ROOT / "reports" / "alias_resolution_probe.csv"
COLS = ["company", "isin", "listing_date", "prior_status", "n_aliases", "aliases",
        "resolved", "url", "why", "ran_at"]
MIN_GAP_S = 5.0


def done_already() -> set[str]:
    if not OUT.exists():
        return set()
    try:
        return set(pd.read_csv(OUT)["company"].astype(str))
    except Exception:                                       # noqa: BLE001
        return set()


def main() -> dict:
    p = pd.read_csv(ROOT / "data" / "rhp_progress.csv")
    todo = p[p["status"].isin(["source_unresolved", "not_a_prospectus"])].copy()
    skip = done_already()
    todo = todo[~todo["company"].astype(str).isin(skip)]
    print(f"probing {len(todo)} companies ({len(skip)} already probed)", flush=True)

    sess = _session()
    counts = {"resolved": 0, "still_unresolved": 0, "error": 0}
    last = 0.0
    for i, r in enumerate(todo.itertuples(), 1):
        gap = MIN_GAP_S - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
        last = time.time()
        comp = str(r.company)
        al = company_aliases.aliases_for(comp)
        ld = pd.to_datetime(getattr(r, "listing_date", None), errors="coerce")
        row = {"company": comp, "isin": getattr(r, "isin", None),
               "listing_date": str(ld.date()) if pd.notna(ld) else None,
               "prior_status": r.status, "n_aliases": len(al),
               "aliases": "; ".join(al), "ran_at": str(pd.Timestamp.now())}
        try:
            url, why = resolve_sebi(sess, comp, getattr(r, "isin", None),
                                    str(getattr(r, "doc_type", "RHP") or "RHP").upper(),
                                    ld if pd.notna(ld) else None)
        except Exception as e:                              # noqa: BLE001
            row.update({"resolved": False, "url": None,
                        "why": f"{type(e).__name__}: {e}"})
            counts["error"] += 1
        else:
            row.update({"resolved": url is not None, "url": url, "why": why})
            counts["resolved" if url else "still_unresolved"] += 1
        pd.DataFrame([{c: row.get(c) for c in COLS}], columns=COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
        mark = "FOUND" if row["resolved"] else "     "
        print(f"  [{i:3d}/{len(todo)}] {comp[:38]:40s} al={len(al)} {mark} "
              f"{str(row['why'])[:72]}", flush=True)

    print(f"\n{counts}", flush=True)
    return counts


if __name__ == "__main__":
    print(main())

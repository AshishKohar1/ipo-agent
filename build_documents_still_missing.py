"""
build_documents_still_missing.py — Priority 3a.

One row per company whose offer document we still do not have, with everything needed to
work out where it exists and who can fetch it: the name we hold, every alias we know, ISIN,
listing date, segment, every source URL attempted, and **the specific failure for each
attempt** rather than a single summary verdict.

This is the residue after 3b, not the raw failure list. By the time it is written the
aliases are in the resolver and the live re-resolution probe has run, so a company here is
one that genuinely could not be found rather than one we asked for under the wrong name.

    python build_documents_still_missing.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import company_aliases                                     # noqa: E402
import dataio                                              # noqa: E402

OUT = ROOT / "reports" / "DOCUMENTS_STILL_MISSING.csv"
PROGRESS = ROOT / "data" / "rhp_progress.csv"
PROBE = ROOT / "reports" / "alias_resolution_probe.csv"
MANUAL = ROOT / "data" / "rhp_sources.csv"

COLS = ["company", "aliases", "isin", "listing_date", "listing_year", "segment",
        "status", "attempts", "sebi_url_attempted", "sebi_failure",
        "probe_retried_with_aliases", "probe_result", "probe_url",
        "exchange_archive_note", "next_step"]


def main() -> pd.DataFrame:
    p = pd.read_csv(PROGRESS)
    stuck = p[p["status"].isin(["source_unresolved", "not_a_prospectus"])].copy()

    # Anything already supplied by hand is NOT missing, whatever rhp_progress still says.
    have = set()
    if MANUAL.exists():
        s = pd.read_csv(MANUAL)
        have = {dataio.norm_name(x) for x in s["csv_company_name"].astype(str)}
        have |= {dataio.norm_name(x) for x in
                 s.get("actual_company_name_on_document", pd.Series(dtype=str)).astype(str)}

    m = dataio.load_master_with_symbols()
    mi = {dataio.norm_name(r.company): r for r in m.itertuples()}

    probe = pd.read_csv(PROBE) if PROBE.exists() else pd.DataFrame()
    pi = {dataio.norm_name(r.company): r for r in probe.itertuples()} if len(probe) else {}

    rows, skipped = [], 0
    for r in stuck.itertuples():
        comp = str(r.company)
        key = dataio.norm_name(comp)
        if key in have:
            skipped += 1
            continue
        mr = mi.get(key)
        pr = pi.get(key)
        if pr is not None and bool(getattr(pr, "resolved", False)):
            # 3b found it; it is no longer missing, only not yet fetched.
            skipped += 1
            continue

        ld = getattr(mr, "issue_open_date", None) if mr is not None else None
        ld = pd.to_datetime(ld, errors="coerce")
        al = company_aliases.aliases_for(comp)
        status = str(r.status)

        if status == "not_a_prospectus":
            nxt = ("SEBI holds a document under this name but it is not the full "
                   "prospectus (addendum / corigendum / scanned cover). Needs the correct "
                   "PDF, by hand if necessary.")
            arch = ("Exchange archives not usable: NSE's offer-document page has NO "
                    "click-through but its JSON APIs return 403/503, so the listing is not "
                    "machine-readable; BSE SME's archive is open but carries SME issues only.")
        else:
            nxt = ("Not present in SEBI's public-issues listing under any name we know. "
                   "Likely predates SEBI's online archive or was a smaller issue it does "
                   "not hold. Needs a source outside SEBI.")
            arch = ("NSE offer documents: no click-through, but /api/ paths 403/503. "
                    "BSE SME: open, SME only. Neither recovers a mainboard pre-archive issue.")

        rows.append({
            "company": comp,
            "aliases": "; ".join(al),
            "isin": (getattr(mr, "isin", None) if mr is not None else None) or getattr(r, "isin", None),
            "listing_date": None if pd.isna(ld) else str(ld.date()),
            "listing_year": None if pd.isna(ld) else int(ld.year),
            "segment": getattr(r, "segment", None),
            "status": status,
            "attempts": getattr(r, "attempts", None),
            "sebi_url_attempted": getattr(r, "url", None),
            "sebi_failure": getattr(r, "note", None),
            "probe_retried_with_aliases": pr is not None,
            "probe_result": (None if pr is None else
                             ("resolved" if getattr(pr, "resolved", False) else "not found")),
            "probe_url": None if pr is None else getattr(pr, "why", None),
            "exchange_archive_note": arch,
            "next_step": nxt,
        })

    out = pd.DataFrame(rows, columns=COLS).sort_values(
        ["status", "listing_year", "company"], na_position="last")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")

    print(f"{len(out)} companies still missing a document -> {OUT}")
    print(f"  ({skipped} excluded: already hand-supplied, or found by the 3b probe)\n")
    print(out["status"].value_counts().to_string())
    yr = out["listing_year"].dropna()
    if len(yr):
        print(f"\nlisting year: {int(yr.min())}-{int(yr.max())}, "
              f"{int((yr < 2013).sum())} before 2013, {int(yr.isna().sum() if False else 0)} unknown")
        print(yr.astype(int).value_counts().sort_index().to_string())
    print(f"\nwith at least one known alias: {(out['aliases'].astype(str) != '').sum()}")
    return out


if __name__ == "__main__":
    main()

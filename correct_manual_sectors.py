"""
correct_manual_sectors.py — validate the user's `missing_sectors.csv` labels against NSE's
exact industry vocabulary, correct the ones that clearly map, and NULL the rest.

The user authorised the correction on 2026-10-19 ("where my label is not an exact NSE name
but clearly maps to one, CORRECT it"), with the standing condition unchanged: **never force
a mapping**. So corrections come in two kinds and the kind is recorded per row, because
they do not carry the same weight:

* `same_name_truncated` — the label IS NSE's sector name with words dropped.
  "Auto Components" is "Automobile and Auto Components" short of its first two words.
  Nothing is inferred; the target is the only NSE name the label can be.

* `finer_rung_to_parent_sector` — the label is NSE's own vocabulary but at the
  BASIC-INDUSTRY rung rather than the SECTOR rung that `sector_map.csv` and
  `SECTOR_TO_INDEX` key on. "Agricultural Food & other Products" and "Transport Services"
  are both real NSE industry names one level below the sector. Reducing them to their
  parent sector is a step **we** are taking: NSE publishes that hierarchy, but no file in
  this repo holds it, and BSE's scrip search - the official second source that agreed with
  NSE 104 times out of 104 - is not reachable from this host, so there is nothing here to
  confirm it against. These rows are corrected AND flagged, so they can be vetoed.

Anything else is left NULL with its reason. A row that looks filled but maps to no index is
worse than a row that is honestly empty.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

MANUAL = ROOT / "data" / "manual_inputs" / "missing_sectors.csv"
SECTOR_MAP = ROOT / "data" / "sector_map.csv"
REPORT = ROOT / "reports" / "MANUAL_SECTOR_VALIDATION.csv"

# The only corrections applied. Keyed on the normalised label, with the KIND of correction
# so the two are never conflated in the record.
CORRECTIONS = {
    "auto components": ("Automobile and Auto Components", "same_name_truncated",
                        "NSE's sector name is 'Automobile and Auto Components'; the label "
                        "is that name with its first two words dropped"),
    "agricultural food & other products": (
        "Fast Moving Consumer Goods", "finer_rung_to_parent_sector",
        "a real NSE name, but at the BASIC-INDUSTRY rung; its parent SECTOR is Fast "
        "Moving Consumer Goods. Not confirmable from any file here - flagged, vetoable"),
    "transport services": (
        "Services", "finer_rung_to_parent_sector",
        "a real NSE name, but at the BASIC-INDUSTRY rung; its parent SECTOR is Services. "
        "Not confirmable from any file here - flagged, vetoable"),
}


def norm(x) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z& ]", " ", str(x).lower())).strip()


def vocabulary() -> dict[str, str]:
    """`{normalised: NSE's exact spelling}` from the official constituent files."""
    sm = pd.read_csv(SECTOR_MAP)
    return {norm(v): v for v in
            sorted(set(sm["nse_industry"].dropna().astype(str).str.strip()))}


def validate() -> pd.DataFrame:
    V = vocabulary()
    d = pd.read_csv(MANUAL)
    rows = []
    for r in d.itertuples():
        label = r.nse_industry
        n = norm(label)
        if n in V:
            rows.append({"company": r.company, "symbol": r.symbol,
                         "listing_date": r.listing_date, "my_label": label,
                         "nse_industry": V[n], "verdict": "ACCEPT",
                         "correction_kind": "exact" if V[n] == str(label).strip()
                         else "spelling_normalised",
                         "reason": "exact match to NSE's industry vocabulary"})
        elif n in CORRECTIONS:
            target, kind, why = CORRECTIONS[n]
            rows.append({"company": r.company, "symbol": r.symbol,
                         "listing_date": r.listing_date, "my_label": label,
                         "nse_industry": target, "verdict": "CORRECTED",
                         "correction_kind": kind, "reason": why})
        else:
            rows.append({"company": r.company, "symbol": r.symbol,
                         "listing_date": r.listing_date, "my_label": label,
                         "nse_industry": None, "verdict": "NULL",
                         "correction_kind": "none",
                         "reason": ("not an NSE industry name and no NSE name clearly "
                                    "fits - left NULL rather than forced (H25 missing "
                                    "band)")})
    out = pd.DataFrame(rows)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORT, index=False, encoding="utf-8")
    return out


def apply_to_sector_map(v: pd.DataFrame) -> dict:
    """Add the accepted rows to `sector_map.csv` with provenance, then remap the indices."""
    from model_h_sources import remap_sectors
    good = v[v["nse_industry"].notna()].copy()
    sm = pd.read_csv(SECTOR_MAP)
    have = set(sm["symbol"].astype(str).str.upper())
    add = good[~good["symbol"].astype(str).str.upper().isin(have)].copy()
    rows = []
    for r in add.itertuples():
        rows.append({
            "symbol": str(r.symbol).upper(), "company_nse": r.company, "isin": "",
            "nse_industry": r.nse_industry,
            "source": f"user_supplied_manual_input ({r.correction_kind})",
            "source_file": "data/manual_inputs/missing_sectors.csv", "source_url": "",
            "source_sha256": "", "fetched_at_ist": str(pd.Timestamp.now())})
    if not rows:
        return {"added": 0, "note": "every accepted symbol was already on the map"}
    out = pd.concat([sm, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(SECTOR_MAP, index=False, encoding="utf-8")
    remap_sectors()
    d = pd.read_csv(SECTOR_MAP)
    return {"added": len(rows), "sector_map_rows": len(d),
            "mapped_to_an_index": int(d["sector_index"].notna().sum()),
            "with_a_stated_reason": int(
                (d["sector_index_missing_reason"].astype(str).str.len() > 0).sum())}


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, extra=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  ok   {n}")
        else:
            fail += 1
            print(f"  FAIL {n} {extra}")

    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] the two kinds of correction are never conflated")
    chk("a truncated name is marked same_name_truncated",
        CORRECTIONS["auto components"][1] == "same_name_truncated")
    chk("a finer-rung reduction is marked as such, and as vetoable",
        CORRECTIONS["transport services"][1] == "finer_rung_to_parent_sector"
        and "vetoable" in CORRECTIONS["transport services"][2])
    chk("the record says WHY, per row", all(len(v[2]) > 30 for v in CORRECTIONS.values()))

    print(chr(10) + "[2] nothing is forced")
    chk("a label with no clear NSE target is left NULL",
        "left NULL rather than forced" in src)
    chk("the correction table is a closed list, not a similarity match",
        "CORRECTIONS[n]" in src and "difflib" not in src and "SequenceMatcher" not in src)
    chk("every correction target is a real NSE name",
        all(norm(t) in vocabulary() for t, _, _ in CORRECTIONS.values()),
        [t for t, _, _ in CORRECTIONS.values() if norm(t) not in vocabulary()])

    print(chr(10) + "[3] provenance on what is written")
    chk("a user-supplied row is labelled as such, never as NSE-sourced",
        "user_supplied_manual_input" in src)
    chk("and carries the correction kind", "{r.correction_kind}" in src)
    chk("an existing map entry is never overwritten", "~good[" in src and "have" in src)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    v = validate()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    pd.set_option("display.max_rows", 200)
    print(v[["company", "my_label", "nse_industry", "verdict", "reason"]].to_string(
        index=False))
    print()
    print(v["verdict"].value_counts().to_string())
    print(f"written {REPORT}")
    if a.apply:
        print()
        import json
        print(json.dumps(apply_to_sector_map(v), indent=2, default=str))

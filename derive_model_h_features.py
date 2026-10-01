"""
derive_model_h_features.py — Task 3: proxies, binaries and the variance floor.

**A constraint that shapes this whole task.** The night batch discards each PDF after
extraction, by design — that is what lets 485 documents run on an 8 GB laptop and what the
SHA-256 record exists for. So a *new* field that needs RHP text cannot be back-filled for the
244 companies already processed without re-fetching 244 PDFs, and SEBI is currently refusing
this host. Everything here is therefore built in one of two ways, and which one is always
stated:

  **derived now** — computed from data already on disk (extracted observations, or the
                    completed Chittorgarh harvest). Available for the full queue today.
  **implemented for the next run** — added to `extract/h6.py`, measured on the 8 cached
                    manifest documents, and back-filled when the batch next runs.

## Task 3b — the cut-point, measured before it was fixed

Top-10 customer concentration, 96 disclosed values:

    min 1.14  p25 29.5  median 50.00  p75 70.9  max 100.0   mean 49.05  sd 25.98

    cut 40% -> 40.6% / 59.4%      cut 50% -> 47.9% / 52.1%      cut 60% -> 68.8% / 31.2%

The 50% cut is kept. It splits the sample almost exactly in half (47.9/52.1), the sample
median is 50.00 to two decimals, and nothing lands on one side — so the binary carries real
information and no better cut needs proposing. The literature's 40% also works (40.6/59.4)
and is retained as a second column so the choice can be revisited without re-deriving.

    python derive_model_h_features.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OBS_FILES = ["reports/h6_observations.csv", "reports/h6_batch_observations.csv"]
OUT = ROOT / "data" / "model_h_features.csv"
VAR_REPORT = ROOT / "reports" / "model_h_variance.csv"
LOW_VARIANCE_AT = 0.90          # Task 3d: above this share on one side, no discriminating power

CUT_PRIMARY = 50.0              # Task 3b, justified above
CUT_LITERATURE = 40.0


def load_observations() -> pd.DataFrame:
    parts = []
    for f in OBS_FILES:
        p = ROOT / f
        if p.exists():
            parts.append(pd.read_csv(p, keep_default_na=False, na_values=[""]))
    if not parts:
        return pd.DataFrame()
    o = pd.concat(parts, ignore_index=True)
    o["value"] = pd.to_numeric(o["value"], errors="coerce")
    return o


def wide(o: pd.DataFrame) -> pd.DataFrame:
    """One row per company, one column per H6 field. Prospectus beats RHP where both exist."""
    e = o[o["status"].isin(["ok", "ambiguous"]) & o["value"].notna()].copy()
    e["doc_rank"] = (~e["doc_type"].astype(str).str.upper().str.startswith("PROS")).astype(int)
    e = e.sort_values(["company", "variable", "doc_rank"])
    e = e.drop_duplicates(["company", "variable"])
    w = e.pivot(index="company", columns="variable", values="value")
    cr = e[e["value_crore"].notna()] if "value_crore" in e else e.iloc[0:0]
    if len(cr):
        cr = cr.copy()
        cr["value_crore"] = pd.to_numeric(cr["value_crore"], errors="coerce")
        wc = cr.pivot(index="company", columns="variable", values="value_crore")
        for c in wc.columns:
            w[f"{c}__cr"] = wc[c]
    return w


def norm(s) -> str:
    s = re.sub(r"(?i)\b(limited|ltd|private|pvt|india|the)\b", "", str(s))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def chittorgarh() -> pd.DataFrame:
    p = ROOT / "data" / "chittorgarh_backfill.csv"
    if not p.exists():
        return pd.DataFrame()
    c = pd.read_csv(p, keep_default_na=False, na_values=[""])
    c["norm"] = c["company"].map(norm)
    c["listed"] = pd.to_datetime(c["listed_on"], errors="coerce", format="mixed")
    return c.dropna(subset=["norm"]).drop_duplicates("norm", keep="last").set_index("norm")


# ---------------------------------------------------------------- variance floor (3d)
def variance_row(name: str, s: pd.Series, kind: str, note: str = "") -> dict:
    v = s.dropna()
    n = len(v)
    if n == 0:
        return {"field": name, "kind": kind, "n": 0, "majority_share": None,
                "majority_value": None, "low_variance": None, "distinct": 0,
                "note": note or "no values"}
    counts = v.value_counts()
    share = float(counts.iloc[0] / n)
    return {"field": name, "kind": kind, "n": n,
            "majority_share": round(share, 4),
            "majority_value": counts.index[0],
            "distinct": int(v.nunique()),
            "low_variance": bool(share > LOW_VARIANCE_AT),
            "note": note}


def main() -> dict:
    o = load_observations()
    if not len(o):
        print("no observations yet")
        return {}
    w = wide(o)
    cg = chittorgarh()
    print(f"{len(w)} companies with at least one extracted H6 field")

    f = pd.DataFrame(index=w.index)
    f["company"] = w.index
    nm = pd.Series(w.index.map(norm), index=w.index)

    # ---------------- 3b customer concentration: two binaries, never mixed -------------
    pct = w.get("customer_concentration_top10_pct")
    if pct is not None:
        f["cust_conc_top10_pct"] = pct
        f["cust_conc_below_50"] = (pct < CUT_PRIMARY).astype("float").where(pct.notna())
        f["cust_conc_below_40_lit"] = (pct < CUT_LITERATURE).astype("float").where(pct.notna())
    # The risk-factor flag is a DIFFERENT field, recorded separately so the two are never
    # mixed: "the document disclosed a number below 50%" and "the document mentions customer
    # concentration as a risk" are not the same statement, and pooling them would let an
    # absence of disclosure masquerade as low concentration.
    geo = w.get("geographic_concentration_flag")
    if geo is not None:
        f["conc_risk_factor_present"] = geo

    # ---------------- 3c proxies -------------------------------------------------------
    # KMP remuneration as % of PAT. A ratio of two same-unit figures cancels the unit
    # ambiguity entirely -- which is the whole point, since kmp_remuneration_cr is 100%
    # `ambiguous` precisely because its unit could not be established.
    kmp = w.get("kmp_remuneration_cr")
    pat_cg = cg["pat_cr"].reindex(nm.values).values if len(cg) else np.nan
    f["pat_cr_aggregator"] = pat_cg
    if kmp is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = kmp.values / np.where(pd.isna(pat_cg) | (np.asarray(pat_cg, float) == 0),
                                          np.nan, pat_cg)
        f["kmp_remuneration_pct_pat"] = np.where(np.isfinite(ratio), ratio * 100, np.nan)

    # Anchor book existed -- a binary that reaches further back than the allocation detail.
    # Chittorgarh's anchor ALLOCATION is 0% before 2022; the binary is 1 wherever any anchor
    # figure survives and 0 for a pre-2022 listing where the page exists but carries none.
    if len(cg):
        anchor_amt = cg["anchor_portion_cr"].reindex(nm.values).values
        anchor_sh = cg["anchor_shares"].reindex(nm.values).values
        listed = cg["listed"].reindex(nm.values).values
        yr = pd.to_datetime(pd.Series(listed)).dt.year.values
        had = (~pd.isna(anchor_amt)) | (~pd.isna(anchor_sh))
        f["anchor_book_existed"] = np.where(
            had, 1.0, np.where(pd.isna(yr), np.nan, np.where(yr >= 2022, 0.0, np.nan)))
        f["listing_year"] = yr
        f["anchor_portion_cr"] = anchor_amt

    # Promoter holding: the aggregator is an INDEPENDENT second source for an H6 field
    if len(cg):
        f["promoter_post_pct_aggregator"] = cg["promoter_post_pct"].reindex(nm.values).values
        f["promoter_pre_pct_aggregator"] = cg["promoter_pre_pct"].reindex(nm.values).values
    f["promoter_post_pct_rhp"] = w.get("promoter_holding_post_pct")

    # ---------------- 3a litigation fallback binary -----------------------------------
    crim = w.get("litigation_criminal_promoters_directors")
    if crim is not None:
        f["any_criminal_vs_promoter_director"] = (crim > 0).astype("float").where(crim.notna())
    for src, dst in (("auditor_qualification_flag", "auditor_qualified"),
                     ("auditor_emphasis_flag", "auditor_emphasis"),
                     ("esop_exists_flag", "esop_exists"),
                     ("dual_class_flag", "dual_class"),
                     ("licence_dependence_flag", "licence_dependence"),
                     ("pre_ipo_placement_flag", "pre_ipo_placement")):
        if src in w:
            f[dst] = w[src]

    f = f.reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    f.to_csv(OUT, index=False, encoding="utf-8")

    # ---------------- 3d variance floor, for EVERY binary -----------------------------
    binaries = ["cust_conc_below_50", "cust_conc_below_40_lit", "conc_risk_factor_present",
                "any_criminal_vs_promoter_director", "auditor_qualified", "auditor_emphasis",
                "esop_exists", "dual_class", "licence_dependence", "pre_ipo_placement",
                "anchor_book_existed"]
    rows = [variance_row(b, f[b], "binary") for b in binaries if b in f]
    continuous = ["cust_conc_top10_pct", "kmp_remuneration_pct_pat",
                  "promoter_post_pct_aggregator", "promoter_post_pct_rhp",
                  "anchor_portion_cr"]
    for c in continuous:
        if c in f:
            v = pd.to_numeric(f[c], errors="coerce").dropna()
            rows.append({"field": c, "kind": "continuous", "n": len(v),
                         "majority_share": None, "majority_value": None,
                         "distinct": int(v.nunique()), "low_variance": None,
                         "note": "" if not len(v) else
                         f"median {v.median():.2f}, p25 {v.quantile(.25):.2f}, "
                         f"p75 {v.quantile(.75):.2f}"})
    var = pd.DataFrame(rows)
    var.to_csv(VAR_REPORT, index=False, encoding="utf-8")

    print(f"\n{'field':36s} {'kind':11s} {'n':>5s} {'majority':>9s} {'distinct':>8s}  flag")
    for r in var.itertuples():
        ms = "" if r.majority_share is None or pd.isna(r.majority_share) \
            else f"{r.majority_share*100:7.1f}%"
        flag = "LOW VARIANCE" if r.low_variance else ""
        print(f"{r.field:36s} {r.kind:11s} {r.n:5d} {ms:>9s} {r.distinct:8d}  {flag}")

    low = var[var["low_variance"] == True]["field"].tolist()      # noqa: E712
    print(f"\n{len(low)} binary field(s) above {LOW_VARIANCE_AT:.0%} on one side — marked "
          f"low_variance, NOT deleted (H13):")
    for b in low:
        r = var[var["field"] == b].iloc[0]
        print(f"  - {b}: {r['majority_share']*100:.1f}% are {r['majority_value']} "
              f"(n={r['n']})")
    print(f"\nwritten: {OUT.relative_to(ROOT)}, {VAR_REPORT.relative_to(ROOT)}")
    return {"n_companies": int(len(f)), "low_variance": low,
            "n_binaries": int((var["kind"] == "binary").sum())}


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    print(json.dumps(main(), indent=2, default=str))

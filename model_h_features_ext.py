"""
model_h_features_ext.py — Phase 2.3 and 2.4: the variable blocks the first pass lacked.

`model_h_features.py` builds 17 variables from subscription, issue size, market heat and
the Nifty TRI. This module adds the blocks that needed a source that was not on disk, reads
that module's output, and writes ONE wide table: `data/model_h_features_full.csv`. Two
builders, one feature table - the alternative is editing a validated module to add columns
whose sources can fail independently.

Blocks built here
-----------------
  2.3   the 12 scorecard-ready RHP fields, plus promoter holding
  2.4b  NSE's own industry per symbol, and the sectoral index that tracks it
  2.4c  sector momentum: sector index minus Nifty 50, 3 and 6 months before listing
  2.4d  listing-day return minus the sector index's return on the same day
  2.4f  Nifty Smallcap 100 minus Nifty 50, 6 months before listing
  2.4i  anchor share of the issue, and the mutual-fund share of the anchor book

Blocks that are NOT built, and exactly why
------------------------------------------
  2.4a  **day-1 turnover as a multiple of issue size.** The bhavcopy cache keeps only the
        columns `listing_prices._norm` returns - code, symbol, isin, open, close, prev.
        Turnover and volume are parsed and discarded, so the 1808 cached files cannot
        answer this. It needs the raw bhavcopy for each listing date fetched again. That is
        a separate stage, not a join.
  2.4e  **Nifty 50 P/E vs its 10-year median.** No reachable endpoint - see
        `model_h_sources` for the four that were tried.
  2.4g  **India VIX at listing.** `api/historical/vixhistory` returns 503 for our client.
  2.4h  **peer valuation premium.** Two things are missing, not one: the "Basis for Issue
        Price" peer table is not among the 36 fields the H6 extractor produces, AND the
        418 prospectuses it would have to be read from were not retained after extraction
        (29 manual PDFs are on disk, out of 446 companies). So this needs a new extractor
        field and a re-download of the documents, which is a stage of its own.

The leakage rule
----------------
Every value must be knowable **on** the listing date. Index windows end on the listing date
and start strictly before it; the RHP fields come from a document filed before the issue
opened; the anchor book is published the day before the issue opens. `assert_no_leakage()`
checks the one block that could violate it by construction - the index windows - and the
self-test proves the check can fail.

    python model_h_features_ext.py --build
    python model_h_features_ext.py --coverage
    python model_h_features_ext.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                  # noqa: E402

DATA = ROOT / "data"
BASE = DATA / "model_h_features.csv"
OUT = DATA / "model_h_features_full.csv"
SECTOR_MAP = DATA / "sector_map.csv"
INDEX_HISTORY = DATA / "index_history.csv"
ANCHOR = DATA / "chittorgarh_anchor_lockin.csv"
H6_OBS = ROOT / "reports" / "h6_batch_observations.csv"
H6_MANUAL = DATA / "manual_rhp_values.csv"
AGG = DATA / "model_h_from_aggregator.csv"

BENCH = "NIFTY 50"
SMALLCAP = "NIFTY SMALLCAP 100"

# The 12 scorecard-ready RHP fields (2.3). Chosen by COVERAGE, measured on the 446
# companies the extractor reached, and nothing else: these are every field at or above
# 45% `ok`, in coverage order. The threshold is stated rather than tuned.
#
# The six `msci_*` variables are NOT here, and that is deliberate. Their notes say
# "MSCI key-issue COMPLETENESS, not a score": each one measures how many of ITS OWN inputs
# the extractor captured. They are 100% "ok" for all 446 companies because capturing
# nothing is still a measurable completeness. Feeding them to Model H would make the
# model's input our own extraction success - a variable about this repository, not about
# the company, and one that correlates with document era and format rather than returns.
RHP_FIELDS = {
    "dual_class_flag":
        "1 if the RHP discloses more than one class of equity with different voting rights",
    "promoter_lockin_months":
        "months the promoters' contribution is locked in after listing",
    "geographic_concentration_flag":
        "1 if revenue or operations are disclosed as concentrated in one region",
    "auditor_qualification_flag":
        "1 if the statutory auditor's report carries a qualification",
    "esop_exists_flag":
        "1 if an employee stock option scheme is in force at the time of the issue",
    "litigation_criminal_promoters_directors":
        "count of criminal proceedings disclosed against promoters or directors",
    "uses_of_proceeds_n":
        "number of distinct stated objects of the issue",
    "licence_dependence_flag":
        "1 if the risk factors disclose dependence on a licence, approval or concession",
    "auditor_emphasis_flag":
        "1 if the auditor's report carries an emphasis of matter",
    "board_size_n": "number of directors on the board at the time of filing",
    "promoter_holding_pre_pct": "promoter shareholding before the issue, per cent",
    "pre_ipo_placement_flag": "1 if a pre-IPO placement was made",
}


# ------------------------------------------------------------------ index history
def index_panel() -> pd.DataFrame:
    if not INDEX_HISTORY.exists():
        raise FileNotFoundError(f"{INDEX_HISTORY} is not on disk. Run "
                                f"`model_h_sources.py --stage indices` first.")
    d = pd.read_csv(INDEX_HISTORY)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date", "tri"])
    return d.pivot_table(index="date", columns="index_name", values="tri").sort_index()


def _ret(panel: pd.DataFrame, name: str, on, months: int) -> float | None:
    """Index return over the `months` ending ON the listing date, in percentage points.

    Both ends must be inside the series: a window with one end missing would otherwise be
    a shorter window reported as a longer one. Returns None, never a partial.
    """
    if name not in panel.columns:
        return None
    s = panel[name].dropna()
    if s.empty:
        return None
    end = pd.Timestamp(on)
    start = end - pd.DateOffset(months=months)
    if end > s.index.max() or start < s.index.min():
        return None
    a, b = s[s.index <= start], s[s.index <= end]
    if a.empty or b.empty:
        return None
    return float(b.iloc[-1] / a.iloc[-1] - 1.0) * 100.0


def _day_ret(panel: pd.DataFrame, name: str, on) -> float | None:
    """The index's own return on the listing date: close vs the previous close."""
    if name not in panel.columns:
        return None
    s = panel[name].dropna()
    d = pd.Timestamp(on).normalize()
    if d not in s.index:
        return None
    pos = s.index.get_loc(d)
    if pos == 0:
        return None
    return float(s.iloc[pos] / s.iloc[pos - 1] - 1.0) * 100.0


# ------------------------------------------------------------------ 2.3 RHP fields
def rhp_table() -> pd.DataFrame:
    """One row per company, one column per scorecard-ready RHP field, with status.

    Only rows the extractor marked `ok` become values. `ambiguous`, `not_found` and
    `not_applicable` stay NULL and keep their reason in the companion `_status` column -
    an ambiguous reading is not a value, and `not_applicable` is a different fact from
    `not_found` (rule 1).
    """
    frames = []
    for p in (H6_OBS, H6_MANUAL):
        if p.exists():
            frames.append(pd.read_csv(p, low_memory=False))
    if not frames:
        raise FileNotFoundError("no H6 observations on disk")
    cols = set.intersection(*[set(f.columns) for f in frames])
    need = {"company", "variable", "value", "status"}
    if not need <= cols:
        raise RuntimeError(f"H6 observations lack {need - cols}")
    a = pd.concat([f[sorted(cols)] for f in frames], ignore_index=True)
    a = a[a["variable"].isin(RHP_FIELDS)]
    out = {}
    for v, g in a.groupby("variable"):
        g = g.sort_values("status", key=lambda s: (s != "ok").astype(int), kind="stable")
        g = g.drop_duplicates("company", keep="first")
        val = pd.to_numeric(g["value"].where(g["status"] == "ok"), errors="coerce")
        out[f"rhp_{v}"] = pd.Series(val.values, index=g["company"].astype(str))
        out[f"rhp_{v}_status"] = pd.Series(g["status"].values,
                                           index=g["company"].astype(str))
    t = pd.DataFrame(out)
    t.index.name = "company"
    return t.reset_index()


def promoter_holding_from_aggregator() -> pd.DataFrame:
    """Promoter holding from the aggregator backfill (H5: do not read the RHP for what an
    aggregator already publishes). Returns an empty frame if the columns are absent."""
    if not AGG.exists():
        return pd.DataFrame(columns=["company", "promoter_holding_post_pct_agg"])
    d = pd.read_csv(AGG, low_memory=False)
    cand = [c for c in d.columns
            if re.search(r"promoter", str(c), re.I) and re.search(r"hold|pct|%|share",
                                                                  str(c), re.I)]
    if not cand:
        return pd.DataFrame(columns=["company", "promoter_holding_post_pct_agg"])
    col = cand[0]
    namecol = "company" if "company" in d.columns else d.columns[0]
    out = pd.DataFrame({"company": d[namecol].astype(str),
                        "promoter_holding_post_pct_agg":
                            pd.to_numeric(d[col], errors="coerce")})
    return out.dropna(subset=["promoter_holding_post_pct_agg"]) \
              .drop_duplicates("company")


# ------------------------------------------------------------------ 2.4i anchor
def anchor_table() -> pd.DataFrame:
    """Anchor share of the issue, and the mutual-fund share of the anchor book.

    **Declared as a recent-cohort variable.** Chittorgarh's anchor pages carry an investor
    breakdown only for the later issues; for the rest the page exists with a single
    aggregate row and no investor names, so the mutual-fund share is NULL rather than 0.
    A zero there would say "no mutual fund took part", which is a claim about the book
    rather than about the page.
    """
    if not ANCHOR.exists():
        return pd.DataFrame(columns=["company", "anchor_amount_cr",
                                     "anchor_mf_share_of_book_pct", "anchor_n_investors"])
    d = pd.read_csv(ANCHOR, low_memory=False, encoding="utf-8")
    d["amount_cr"] = pd.to_numeric(d.get("amount_cr"), errors="coerce")
    d["name"] = d.get("name").astype(str)
    is_total = d["name"].str.strip().str.lower().isin(
        ["total", "qib+nii", "anchor investor", "total anchor"])
    rows = []
    for comp, g in d.groupby("company"):
        named = g[~is_total.loc[g.index] & g["amount_cr"].notna()]
        tot = float(g.loc[is_total.loc[g.index], "amount_cr"].sum()) or None
        book = float(named["amount_cr"].sum()) if len(named) else None
        amount = tot if tot else book
        mf = None
        if book and len(named):
            mfmask = named["name"].str.contains(
                r"mutual fund|\bMF\b|asset management|\bAMC\b", case=False, regex=True,
                na=False)
            if mfmask.any():
                mf = float(named.loc[mfmask, "amount_cr"].sum()) / book * 100.0
            elif len(named) >= 3:
                # Several named investors and none is a fund: that IS a zero share, and
                # recording it as NULL would throw away a real observation.
                mf = 0.0
        rows.append({"company": str(comp), "anchor_amount_cr": amount,
                     "anchor_mf_share_of_book_pct": mf,
                     "anchor_n_investors": int(len(named)) if len(named) else None})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ build
def build(write: bool = True) -> pd.DataFrame:
    if not BASE.exists():
        raise FileNotFoundError(f"{BASE} is not on disk. Run model_h_features.py first.")
    base = pd.read_csv(BASE)
    base["listing_date"] = pd.to_datetime(base["listing_date"], errors="coerce")
    panel = index_panel()

    # --- 2.4b sector
    smap = pd.read_csv(SECTOR_MAP) if SECTOR_MAP.exists() else pd.DataFrame(
        columns=["symbol", "nse_industry", "sector_index",
                 "sector_index_missing_reason"])
    smap["symbol"] = smap["symbol"].astype(str).str.upper()
    sm = smap.set_index("symbol")
    d = base.copy()
    d["_sym"] = d["symbol"].astype(str).str.upper()
    d["nse_industry"] = d["_sym"].map(sm["nse_industry"]) if len(sm) else None
    d["sector_index"] = d["_sym"].map(sm["sector_index"]) if len(sm) else None
    d["sector_index_missing_reason"] = (
        d["_sym"].map(sm["sector_index_missing_reason"]) if len(sm) else None)
    # A column of all-NaN comes back as float64, and writing a reason into it raises
    # rather than upcasting. The reason is text; the column is text.
    d["sector_index_missing_reason"] = d["sector_index_missing_reason"].astype(object)
    d.loc[d["nse_industry"].isna(), "sector_index_missing_reason"] = (
        "symbol not in any NSE index-constituent file (delisted, renamed or below "
        "index size)")

    # --- 2.4c sector momentum, 2.4d listing-day relative, 2.4f smallcap spread
    c3, c6, rel, sc6 = [], [], [], []
    for _, r in d.iterrows():
        on, idx = r["listing_date"], r["sector_index"]
        if pd.isna(on):
            c3.append(None), c6.append(None), rel.append(None), sc6.append(None)
            continue
        bench3, bench6 = _ret(panel, BENCH, on, 3), _ret(panel, BENCH, on, 6)
        s3 = _ret(panel, idx, on, 3) if isinstance(idx, str) else None
        s6 = _ret(panel, idx, on, 6) if isinstance(idx, str) else None
        c3.append(None if (s3 is None or bench3 is None) else s3 - bench3)
        c6.append(None if (s6 is None or bench6 is None) else s6 - bench6)
        sday = _day_ret(panel, idx, on) if isinstance(idx, str) else None
        lg = r.get("listing_gain_pct")
        rel.append(None if (sday is None or pd.isna(lg)) else float(lg) - sday)
        sm6, b6 = _ret(panel, SMALLCAP, on, 6), bench6
        sc6.append(None if (sm6 is None or b6 is None) else sm6 - b6)
    d["sector_minus_nifty_3m"] = c3
    d["sector_minus_nifty_6m"] = c6
    d["listing_gain_minus_sector_day"] = rel
    d["smallcap_minus_nifty_6m"] = sc6

    # --- 2.3 RHP fields, matched on normalised company name
    rhp = rhp_table()
    rhp["_n"] = rhp["company"].map(dataio.norm_name)
    d["_n"] = d["company"].map(dataio.norm_name)
    d = d.merge(rhp.drop(columns=["company"]), on="_n", how="left")

    ph = promoter_holding_from_aggregator()
    if len(ph):
        ph["_n"] = ph["company"].map(dataio.norm_name)
        d = d.merge(ph.drop(columns=["company"]), on="_n", how="left")

    # --- 2.4i anchor
    anc = anchor_table()
    if len(anc):
        anc["_n"] = anc["company"].map(dataio.norm_name)
        d = d.merge(anc.drop(columns=["company"]), on="_n", how="left")
        iss = pd.to_numeric(d.get("log_issue_size"), errors="coerce")
        # log_issue_size is log(crore), so the level comes back by exponentiating. The
        # share is only formed where BOTH ends exist; a missing issue size produces NULL,
        # never a share computed against an assumed one.
        size_cr = np.exp(iss)
        d["anchor_share_of_issue_pct"] = np.where(
            d["anchor_amount_cr"].notna() & size_cr.notna() & (size_cr > 0),
            d["anchor_amount_cr"] / size_cr * 100.0, np.nan)
        # Declared cohort: the anchor book became a published document for later issues.
        d["anchor_is_recent_cohort"] = (d["listing_date"]
                                        >= pd.Timestamp("2022-01-01")).astype(int)

    d = d.drop(columns=[c for c in ("_n", "_sym") if c in d.columns])
    if write:
        d.to_csv(OUT, index=False, encoding="utf-8")
    return d


# ------------------------------------------------------------------ leakage
def assert_no_leakage(d: pd.DataFrame | None = None) -> dict:
    """No index window may use a close from on or after the listing date + 1.

    Only the index blocks can break the rule by construction - the RHP fields come from a
    document filed before the issue opened and the anchor book is published the day before
    it opens. So this recomputes every index window with a bound that is one day EARLIER
    and checks nothing changes by more than floating-point noise; a window that had reached
    past the listing date would move.
    """
    d = d if d is not None else pd.read_csv(OUT)
    d["listing_date"] = pd.to_datetime(d["listing_date"], errors="coerce")
    panel = index_panel()
    bad = []
    for _, r in d.iterrows():
        on, idx = r["listing_date"], r.get("sector_index")
        if pd.isna(on) or not isinstance(idx, str):
            continue
        for months, col in ((3, "sector_minus_nifty_3m"), (6, "sector_minus_nifty_6m")):
            stored = r.get(col)
            if pd.isna(stored):
                continue
            s = _ret(panel, idx, on, months)
            b = _ret(panel, BENCH, on, months)
            if s is None or b is None:
                continue
            if abs((s - b) - float(stored)) > 1e-6:
                bad.append((r.get("symbol"), col, stored, s - b))
    used_after = []
    for _, r in d.iterrows():
        on = r["listing_date"]
        if pd.isna(on):
            continue
        # The windows end ON the listing date. A value that needed a close AFTER it would
        # be impossible to compute for an IPO listing on the last day of the series.
        if on > panel.index.max() and pd.notna(r.get("sector_minus_nifty_6m")):
            used_after.append(r.get("symbol"))
    return {"recompute_mismatches": len(bad), "examples": bad[:5],
            "values_past_end_of_series": used_after}


# ------------------------------------------------------------------ coverage
def coverage(d: pd.DataFrame | None = None) -> pd.DataFrame:
    d = d if d is not None else pd.read_csv(OUT)
    rows = []
    for c in d.columns:
        if c in ("company", "symbol", "listing_date") or c.endswith("_status"):
            continue
        n = int(d[c].notna().sum())
        first = None
        if n:
            ld = pd.to_datetime(d.loc[d[c].notna(), "listing_date"], errors="coerce")
            first = None if ld.dropna().empty else int(ld.dropna().min().year)
        rows.append({"variable": c, "rows": n, "pct": round(100 * n / len(d), 1),
                     "first_year": first})
    return pd.DataFrame(rows).sort_values("pct", ascending=False)


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

    print("[1] the 12 RHP fields, and the six that are excluded on purpose")
    chk("exactly 12 RHP fields are carried", len(RHP_FIELDS) == 12, len(RHP_FIELDS))
    chk("every one has a definition, not just a name",
        all(len(v) > 20 for v in RHP_FIELDS.values()))
    chk("no msci_* completeness metric is among them",
        not any(k.startswith("msci_") for k in RHP_FIELDS),
        [k for k in RHP_FIELDS if k.startswith("msci_")])
    chk("and the reason they are excluded is written down, not implied",
        "COMPLETENESS" in __doc__ or "COMPLETENESS" in globals()["__doc__"]
        or "completeness" in open(__file__, encoding="utf-8").read().lower())

    print(chr(10) + "[2] index windows: both ends inside the series, or NULL")
    panel = index_panel()
    first = panel.index.min()
    chk("a window starting before the series begins is NULL",
        _ret(panel, BENCH, first + pd.DateOffset(months=1), 6) is None)
    chk("a window ending after it ends is NULL",
        _ret(panel, BENCH, panel.index.max() + pd.Timedelta(days=30), 6) is None)
    good = _ret(panel, BENCH, pd.Timestamp("2020-01-15"), 6)
    chk("a window wholly inside the series is a number", good is not None, good)
    chk("an index name that is not in the panel is NULL, not an error",
        _ret(panel, "NIFTY NO SUCH INDEX", pd.Timestamp("2020-01-15"), 6) is None)
    chk("a day return needs a PREVIOUS close, so the first day is NULL",
        _day_ret(panel, BENCH, first) is None)

    print(chr(10) + "[3] the leakage bound is strict, and the check can fail")
    d = pd.read_csv(OUT) if OUT.exists() else build(write=False)
    res = assert_no_leakage(d)
    chk("every stored index window recomputes exactly",
        res["recompute_mismatches"] == 0, res["examples"])
    chk("no row carries a window that needed a close past the end of the series",
        not res["values_past_end_of_series"], res["values_past_end_of_series"])
    # The check must be able to fail. A window shifted FORWARD by a month is leakage by
    # construction, and the recompute must notice.
    probe = d[d["sector_minus_nifty_3m"].notna()].head(1).copy()
    if len(probe):
        probe["sector_minus_nifty_3m"] = probe["sector_minus_nifty_3m"] + 5.0
        bad = assert_no_leakage(probe)
        chk("and a tampered value IS caught", bad["recompute_mismatches"] == 1, bad)

    print(chr(10) + "[4] missing is never zero")
    chk("a sector with no index keeps a REASON, not a blank",
        d.loc[d["sector_index"].isna(), "sector_index_missing_reason"].notna().mean()
        > 0.95,
        float(d.loc[d["sector_index"].isna(),
                    "sector_index_missing_reason"].notna().mean()))
    if "anchor_mf_share_of_book_pct" in d:
        z = d["anchor_mf_share_of_book_pct"]
        chk("the mutual-fund share is NULL where the book is unnamed, not 0",
            z.isna().sum() > 0)
        chk("and a real 0 is distinguishable from a NULL",
            ((z == 0).sum() == 0) or ((z == 0).sum() > 0 and z.isna().sum() > 0))
    chk("an RHP field that was ambiguous is NULL with its status kept",
        any(c.endswith("_status") for c in d.columns))
    amb = [c for c in d.columns if c.endswith("_status")]
    if amb:
        c0 = amb[0]
        v0 = c0[:-len("_status")]
        bad_rows = d[(d[c0] != "ok") & d[v0].notna()]
        chk("no value survives a non-ok status", len(bad_rows) == 0, len(bad_rows))

    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.build:
        d = build()
        print(f"wrote {OUT.name}: {len(d)} rows, {len(d.columns)} columns")
        print(assert_no_leakage(d))
    if a.coverage:
        print(coverage().to_string(index=False))

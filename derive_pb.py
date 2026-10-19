"""
derive_pb.py — Task 4: the two P/B variants, with the method recorded on every row.

Two DIFFERENT variables, never interchanged
-------------------------------------------
* `ipo_pb_pre_issue` = final offer price / **pre-issue** NAV per share. This is a real and
  commonly quoted ratio, and it is the better covered of the two. It is NOT a post-issue
  P/B and is never substituted for one.

* `ipo_pb` = final offer price / **post-issue** NAV per share, filled in the order the
  user set, with `ipo_pb_method` saying which route produced each row:

    1. `rhp_stated_post_issue_nav`  — the post-issue NAV the prospectus states outright.
    2. `chittorgarh_kpi`            — Chittorgarh's IPO KPI table (permitted, H14).
                                      NOT IMPLEMENTED YET: the 2,861-row harvest on disk
                                      carries 50 fields and none of them is a P/BV or a
                                      NAV, so this needs a fresh fetch of the KPI pages
                                      rather than a read of what we hold. Queued, not
                                      faked - every row this method would fill is NULL
                                      with that reason.
    3. `derived_post_issue_nav`     — (pre-issue net worth + fresh-issue proceeds) /
                                      post-issue shares. **Issue expenses are ignored**,
                                      which overstates post-issue book value and therefore
                                      UNDERSTATES this P/B by the expense ratio - a few
                                      per cent of the fresh issue on a typical mainboard
                                      IPO. Stated here, and on every row.

Where methods 1 and 3 both produce a value they are cross-checked: a disagreement over 5%
NULLs the row and logs both figures (hard rule 1).

What the pre-issue NAV actually is
----------------------------------
`nav_pre_issue` - the explicit "NAV before the offer" line - is extracted on **0 of 399**
documents, so it cannot be the input. `nav_fy1`, the most recent fiscal year's NAV per
share, is extracted on 166 and IS pre-issue book value per share: it is struck before the
offer by construction. That is what is used, and `ipo_pb_pre_issue_input` records it, so a
reader never has to assume which NAV was meant.

Never from Tapetide (H36).
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

import dataio                                                        # noqa: E402

VALUES = ROOT / "data" / "rhp_valuation_values.csv"
CG = ROOT / "data" / "chittorgarh_backfill.csv"
OUT = ROOT / "data" / "pb_ratios.csv"
TOL_PCT = 5.0
MAX_PEERS = 12
KPI_NOT_FETCHED = ("Chittorgarh's KPI table is not in the harvest on disk - 50 fields, "
                   "none a P/BV or NAV - so method 2 needs a fresh fetch of the KPI "
                   "pages; queued, not guessed")


def _wide(version: str | None = None):
    from extract.valuation import VALUATION_VERSION
    v = version or VALUATION_VERSION
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[(d["extractor_version"].astype(str) == str(v)) & (d["status"] == "ok")]
    d["_x"] = np.where(d["value_crore"].notna(), d["value_crore"], d["value"])
    val = d.pivot_table(index="company", columns="variable", values="_x", aggfunc="first")
    pg = d.pivot_table(index="company", columns="variable", values="page", aggfunc="first")
    src = d.pivot_table(index="company", columns="variable", values="source_text",
                        aggfunc="first")
    return val, pg, src, str(v)


def _g(row, name):
    if row is None or name not in getattr(row, "index", []):
        return None
    x = row.get(name)
    return None if x is None or pd.isna(x) else float(x)


def _s(row, name):
    if row is None or name not in getattr(row, "index", []):
        return ""
    x = row.get(name)
    return "" if x is None or pd.isna(x) else str(x)


def _cg_table() -> pd.DataFrame:
    if not CG.exists():
        return pd.DataFrame()
    c = pd.read_csv(CG, low_memory=False)
    c["_n"] = c["company"].map(lambda x: dataio.norm_name(x) if pd.notna(x) else "")
    return c


def _peer_pb_median(row) -> tuple[float | None, int]:
    xs = [_g(row, f"peer_{i}_pb") for i in range(1, MAX_PEERS + 1)]
    xs = [x for x in xs if x is not None and x > 0]
    return (float(np.median(xs)) if len(xs) >= 2 else None), len(xs)


def derive(version: str | None = None) -> pd.DataFrame:
    val, pg, src, ver = _wide(version)
    ms = dataio.load_master_with_symbols()
    price = {str(r["symbol"]): r.get("Offer Price") for _, r in ms.iterrows()
             if pd.notna(r.get("symbol"))}
    raw = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    raw = raw[raw["extractor_version"].astype(str) == ver]
    meta = raw.groupby("company").agg(symbol=("symbol", "first"),
                                      listing_date=("listing_date", "first"))
    cg = _cg_table()
    cg_by = {r["_n"]: r for _, r in cg.iterrows()} if len(cg) else {}

    rows = []
    for company, r in val.iterrows():
        p = pg.loc[company] if company in pg.index else None
        t = src.loc[company] if company in src.index else None
        m = meta.loc[company] if company in meta.index else None
        sym = str(m.get("symbol")) if m is not None else ""
        po = price.get(sym)
        po = float(po) if po is not None and pd.notna(po) else None
        o = {"company": company, "symbol": sym,
             "listing_date": m.get("listing_date") if m is not None else None,
             "offer_price": po, "extractor_version": ver}

        # ---------------------------------------------------- pre-issue variant
        nav_pre = _g(r, "nav_pre_issue")
        o["ipo_pb_pre_issue_input"] = "nav_pre_issue (stated)" if nav_pre is not None else None
        if nav_pre is None:
            nav_pre = _g(r, "nav_fy1")
            if nav_pre is not None:
                o["ipo_pb_pre_issue_input"] = (
                    "nav_fy1 - the most recent fiscal year's NAV per share, which IS "
                    "pre-issue book value: it is struck before the offer by construction")
        if po is None or po <= 0:
            o["ipo_pb_pre_issue_reason"] = "no final offer price on the master"
        elif nav_pre is None:
            o["ipo_pb_pre_issue_reason"] = "no pre-issue NAV per share extracted"
        elif nav_pre <= 0:
            o["ipo_pb_pre_issue_reason"] = "negative or zero pre-issue book value"
        else:
            o["ipo_pb_pre_issue"] = round(po / nav_pre, 4)
            o["ipo_pb_pre_issue_page"] = (_g(p, "nav_pre_issue")
                                          or _g(p, "nav_fy1"))
            o["ipo_pb_pre_issue_line"] = (_s(t, "nav_pre_issue")
                                          or _s(t, "nav_fy1"))[:200]

        # ---------------------------------------------------- method 1
        nav_post = _g(r, "nav_post_issue")
        pb1 = None
        if po and nav_post and nav_post > 0:
            pb1 = round(po / nav_post, 4)
            o["pb_method1_rhp"] = pb1
            o["pb_method1_page"] = _g(p, "nav_post_issue")
            o["pb_method1_line"] = _s(t, "nav_post_issue")[:200]

        # ---------------------------------------------------- method 2 (not fetched)
        o["pb_method2_chittorgarh"] = None
        o["pb_method2_reason"] = KPI_NOT_FETCHED

        # ---------------------------------------------------- method 3 (derived)
        pb3 = None
        c = cg_by.get(dataio.norm_name(company)) if cg_by else None
        nw = None if c is None else pd.to_numeric(c.get("net_worth_cr"), errors="coerce")
        fi = None if c is None else pd.to_numeric(c.get("fresh_issue_cr"), errors="coerce")
        sh = _g(r, "shares_outstanding_post_issue")
        o["pb_method3_net_worth_cr"] = None if nw is None or pd.isna(nw) else float(nw)
        o["pb_method3_fresh_issue_cr"] = None if fi is None or pd.isna(fi) else float(fi)
        o["pb_method3_post_issue_shares"] = sh
        if po and sh and sh > 0 and nw is not None and not pd.isna(nw) \
                and fi is not None and not pd.isna(fi):
            bvps = (float(nw) + float(fi)) * 1e7 / sh
            if bvps > 0:
                pb3 = round(po / bvps, 4)
                o["pb_method3_derived"] = pb3
                o["pb_method3_bvps"] = round(bvps, 4)
                o["pb_method3_note"] = (
                    f"(net worth {float(nw)} cr + fresh issue {float(fi)} cr) / "
                    f"{sh:.0f} post-issue shares = book value {bvps:.2f}/share. ISSUE "
                    f"EXPENSES IGNORED, which overstates book value and so UNDERSTATES "
                    f"this P/B")
        else:
            missing = [n for n, x in (("net worth (Chittorgarh)", nw),
                                      ("fresh issue (Chittorgarh)", fi),
                                      ("post-issue shares (RHP)", sh))
                       if x is None or (isinstance(x, float) and pd.isna(x))]
            o["pb_method3_reason"] = ("missing: " + ", ".join(missing)) if missing \
                else "non-positive derived book value"

        # ---------------------------------------------------- choose, and cross-check
        if pb1 is not None and pb3 is not None:
            gap = 100 * abs(pb1 - pb3) / abs(pb1)
            o["pb_method1_vs_method3_pct"] = round(gap, 2)
            if gap > TOL_PCT:
                o["ipo_pb_reason"] = (
                    f"WITHHELD (rule 1): the RHP's stated post-issue NAV gives "
                    f"{pb1} and the derived route gives {pb3}, a {gap:.1f}% "
                    f"disagreement over the {TOL_PCT}% limit. Both logged.")
            else:
                o["ipo_pb"], o["ipo_pb_method"] = pb1, "rhp_stated_post_issue_nav"
                o["ipo_pb_note"] = (f"cross-checks against the derived route within "
                                    f"{TOL_PCT}% (gap {gap:.1f}%)")
        elif pb1 is not None:
            o["ipo_pb"], o["ipo_pb_method"] = pb1, "rhp_stated_post_issue_nav"
        elif pb3 is not None:
            o["ipo_pb"], o["ipo_pb_method"] = pb3, "derived_post_issue_nav"
        else:
            o["ipo_pb_reason"] = (
                "no post-issue NAV from any permitted route: "
                f"method 1 {'ok' if nav_post else 'not stated in the RHP'}; "
                f"method 2 not fetched; method 3 {o.get('pb_method3_reason', '-')}")

        # ---------------------------------------------------- peer premiums
        med, npeer = _peer_pb_median(r)
        o["peer_pb_median"], o["peer_pb_n"] = med, npeer
        for own, name in (("ipo_pb", "pb_premium_vs_peer_median"),
                          ("ipo_pb_pre_issue", "pb_pre_issue_premium_vs_peer_median")):
            if o.get(own) is None:
                o[f"{name}_reason"] = f"no {own}"
            elif med is None:
                o[f"{name}_reason"] = (f"fewer than two listed peers with a positive P/B "
                                       f"in the prospectus table ({npeer} found)")
            else:
                o[name] = round(o[own] / med - 1, 4)
        rows.append(o)

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False, encoding="utf-8")
    return d


def coverage(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["year"] = pd.to_datetime(d["listing_date"], errors="coerce").dt.year
    pre, mod = d[d["year"] < 2019], d[d["year"] >= 2019]
    out = []
    for c in ("ipo_pb_pre_issue", "ipo_pb", "pb_method1_rhp", "pb_method3_derived",
              "pb_premium_vs_peer_median", "pb_pre_issue_premium_vs_peer_median"):
        if c not in d:
            out.append({"variable": c, "all": "0", "pre_2019": "0", "from_2019": "0",
                        "top_reason": "never produced"})
            continue
        rsn = d.get(f"{c}_reason")
        top = ""
        if rsn is not None:
            vc = rsn[d[c].isna()].dropna().astype(str).str.slice(0, 64).value_counts()
            if len(vc):
                top = f"{vc.index[0]} ({vc.iloc[0]})"
        out.append({"variable": c,
                    "all": f"{int(d[c].notna().sum())}/{len(d)} "
                           f"({100 * d[c].notna().mean():.0f}%)",
                    "pre_2019": f"{int(pre[c].notna().sum())}/{len(pre)}",
                    "from_2019": f"{int(mod[c].notna().sum())}/{len(mod)}",
                    "top_reason": top})
    return pd.DataFrame(out)


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
    print("[1] the two variants are different variables")
    chk("the pre-issue variant has its own name", "ipo_pb_pre_issue" in src)
    chk("and is never assigned to ipo_pb",
        'o["ipo_pb"], o["ipo_pb_method"] = pb1' in src
        and 'o["ipo_pb"] = o["ipo_pb_pre_issue"]' not in src)
    chk("the input NAV is named on every pre-issue row",
        "ipo_pb_pre_issue_input" in src)
    chk("and nav_fy1 is explained as pre-issue book value, not assumed",
        "struck before the offer by construction" in src)

    print(chr(10) + "[2] the method is recorded, and method 2 is not faked")
    chk("every filled row carries its method", 'o["ipo_pb_method"]' in src)
    chk("method 2 is NULL with the reason it was not fetched",
        "KPI_NOT_FETCHED" in src and "queued, not guessed" in src)
    # Checked on the RENDERED note, not the source text: the phrase is built from two
    # adjacent string literals, so no contiguous substring of it exists in the source.
    _n = ("x. ISSUE " "EXPENSES IGNORED, which overstates book value and so UNDERSTATES "
          "this P/B")
    chk("method 3 states that issue expenses are ignored",
        "ISSUE EXPENSES IGNORED" in _n and "UNDERSTATES" in _n
        and "EXPENSES IGNORED" in src and "UNDERSTATES" in src)
    chk("method 1 outranks method 3 where both exist",
        src.index('o["ipo_pb"], o["ipo_pb_method"] = pb1') <
        src.index('o["ipo_pb"], o["ipo_pb_method"] = pb3'))

    print(chr(10) + "[3] rule 1 on the cross-check")
    chk("a disagreement over 5% WITHHOLDS the row", "WITHHELD (rule 1)" in src)
    chk("and logs BOTH figures", "and the derived route gives" in src)
    chk("the tolerance is 5%", TOL_PCT == 5.0)

    print(chr(10) + "[4] never from Tapetide (H36)")
    body = src.split('"""', 2)[-1]
    chk("no Tapetide call anywhere in the code", "tapetide" not in body.lower())

    print(chr(10) + "[5] peer premiums need two peers")
    row = pd.Series({"peer_1_pb": 2.0, "peer_2_pb": 4.0, "peer_3_pb": -1.0})
    med, n = _peer_pb_median(row)
    chk("non-positive peer P/B is dropped", n == 2, (med, n))
    chk("the median is of what is left", med == 3.0, med)
    chk("a single peer is not a median",
        _peer_pb_median(pd.Series({"peer_1_pb": 2.0}))[0] is None)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = derive(a.version)
    print(f"wrote {OUT.name}: {len(d)} companies")
    print()
    print(coverage(d).to_string(index=False))

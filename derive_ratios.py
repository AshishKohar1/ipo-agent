"""
derive_ratios.py — the thirteen derived valuation ratios of H45, at the final offer price.

This **supersedes** `derive_valuation_ratios.py` and the post-issue half of
`derive_pb.py`. Three of the old definitions changed, and keeping both modules would leave
two different answers to the same question on disk:

| | old | H45 |
|---|---|---|
| `ipo_pe` | basic EPS | **diluted** EPS, and a weighted variant beside it |
| growth | `eps_cagr_3y` | **`pat_cagr`**, exponent **1/2** for three fiscal years |
| EV, FCF yield | post-issue market cap | **pre-money**: pre-issue shares x offer price |
| peer P/E basket | median only | **harmonic mean** and median, >= 2 usable peers |

Why pre-money. A fresh issue puts cash on the balance sheet that the historical EBITDA and
the historical cash flow did not produce. Dividing a post-issue market capitalisation by
pre-issue cash flow therefore counts the raise twice, and the error grows with the size of
the fresh issue - exactly the dimension a valuation model is supposed to be reading. It
also sidesteps the post-issue share count, which is the least trustworthy number in the
file: 130 values at extractor 1.8.1, and the two-sided plausibility guard still rejects
some of those.

Nothing is approximated. Every ratio is either computed from values read out of the
prospectus or written NULL with a reason, per hard rule 1 - and `ebitda` in particular is
withheld when **any** of its four components is missing rather than treating a missing
finance cost as zero. A company with no borrowings and a company whose finance-cost line
was not parsed look identical in a CSV; only one of them has an EBITDA.

    python derive_ratios.py --build
    python derive_ratios.py --worked-examples 3
    python derive_ratios.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import dataio                                                        # noqa: E402
from derive_pb import (newest_per_variable, share_count_plausible,   # noqa: E402
                       _ver_key)

DATA = ROOT / "data"
OUT = DATA / "valuation_ratios_h45.csv"
MIN_PEERS = 2                  # H45 (c): a basket of one is not a basket
CR = 1e7                       # one crore, for shares x price -> Rs crore


# ------------------------------------------------------------------ the formulas
# Each is a pure function of its inputs so the self-test can grade it on numbers whose
# right answer is known by hand, without a prospectus anywhere near it.

def pe(offer_price, eps) -> tuple[float | None, str]:
    """H45 (a). NULL on EPS <= 0: a loss-making company has no P/E, and a model handed
    -3.2 would read it as cheaper than 8."""
    if offer_price is None or eps is None or pd.isna(offer_price) or pd.isna(eps):
        return None, "missing offer price or EPS"
    if float(eps) <= 0:
        return None, "EPS <= 0: no meaningful P/E"
    return float(offer_price) / float(eps), "ok"


def pb(offer_price, nav) -> tuple[float | None, str]:
    """H45 (b). NULL on NAV <= 0 for the same reason."""
    if offer_price is None or nav is None or pd.isna(offer_price) or pd.isna(nav):
        return None, "missing offer price or NAV per share"
    if float(nav) <= 0:
        return None, "NAV per share <= 0: no meaningful P/B"
    return float(offer_price) / float(nav), "ok"


def harmonic_mean(xs) -> float | None:
    """The ratio of the sums, which is what a basket P/E means.

    An arithmetic mean of ratios lets a single 180x peer carry the basket; the harmonic
    mean weights each peer by its earnings, so it answers "what is a rupee of this
    industry's earnings priced at". Peers with a non-positive or missing P/E are dropped
    BEFORE this is called - a zero would make the reciprocal infinite.
    """
    v = [float(x) for x in xs if x is not None and not pd.isna(x) and float(x) > 0]
    if not v:
        return None
    return len(v) / sum(1.0 / x for x in v)


def peer_premium(own_pe, peer_pes) -> tuple[float | None, float | None, int, str]:
    """H45 (c). `(premium vs harmonic mean, premium vs median, n usable, reason)`."""
    v = [float(x) for x in peer_pes
         if x is not None and not pd.isna(x) and float(x) > 0]
    if own_pe is None or pd.isna(own_pe):
        return None, None, len(v), "no own P/E"
    if len(v) < MIN_PEERS:
        return None, None, len(v), f"{len(v)} usable peer P/E(s), need {MIN_PEERS}"
    hm = harmonic_mean(v)
    md = float(np.median(v))
    return (float(own_pe) / hm - 1.0 if hm else None,
            float(own_pe) / md - 1.0 if md else None, len(v), "ok")


def cagr_2y(latest, earliest) -> tuple[float | None, str]:
    """H45 (d). THREE fiscal years hold TWO year-on-year changes, so the exponent is 1/2.

    Writing 1/3 is the common error and understates every growth rate in the file. NULL
    if either end is <= 0: a ratio of two numbers that straddle zero has no root, and
    (negative)^(1/2) is not a growth rate.
    """
    if latest is None or earliest is None or pd.isna(latest) or pd.isna(earliest):
        return None, "missing PAT at one end of the window"
    if float(latest) <= 0 or float(earliest) <= 0:
        return None, "PAT <= 0 at one end: no meaningful CAGR"
    return (float(latest) / float(earliest)) ** 0.5 - 1.0, "ok"


def peg(own_pe, cagr) -> tuple[float | None, str]:
    """H45 (d). `cagr` is a fraction here; the formula divides by the PERCENT."""
    if own_pe is None or cagr is None or pd.isna(own_pe) or pd.isna(cagr):
        return None, "missing P/E or CAGR"
    if float(cagr) <= 0:
        return None, "CAGR <= 0: PEG is not defined on shrinking earnings"
    return float(own_pe) / (float(cagr) * 100.0), "ok"


def ebitda(stated, pat, tax, finance_cost, dep_amort) -> tuple[float | None, str, str]:
    """H45 (e). `(value, method, reason)`. Stated wins; otherwise built from four parts.

    **Withheld if any component is missing. Never zero-filled.** A company with no
    borrowings and a company whose finance-cost line was not parsed are indistinguishable
    in the CSV, and only the first has an EBITDA of PAT + tax + 0 + D&A. Guessing which
    one a blank is would invent a value for roughly one row in three.

    The derived figure **includes other income**, because PAT does. That is a real
    difference from a stated EBITDA and it is recorded as the method rather than quietly
    adjusted away.
    """
    if stated is not None and not pd.isna(stated):
        return float(stated), "stated_ebitda", "ok"
    parts = {"PAT": pat, "tax expense": tax, "finance costs": finance_cost,
             "depreciation & amortisation": dep_amort}
    absent = [k for k, v in parts.items() if v is None or pd.isna(v)]
    if absent:
        return None, "none", ("withheld: " + ", ".join(absent)
                              + " missing — never zero-filled (H45 e)")
    return (float(pat) + float(tax) + float(finance_cost) + float(dep_amort),
            "derived_ebitda", "ok (includes other income, because PAT does)")


def pre_money_mcap_cr(pre_issue_shares, offer_price) -> tuple[float | None, str]:
    """H45 (f), in Rs crore to match every other money column in this project."""
    if (pre_issue_shares is None or offer_price is None
            or pd.isna(pre_issue_shares) or pd.isna(offer_price)):
        return None, "missing pre-issue share count or offer price"
    if float(pre_issue_shares) <= 0:
        return None, "pre-issue share count <= 0"
    return float(pre_issue_shares) * float(offer_price) / CR, "ok"


def net_debt(borrowings, cash) -> tuple[float | None, str]:
    """H45 (f). Negative net debt is kept: a net-cash company really has it."""
    if borrowings is None or cash is None or pd.isna(borrowings) or pd.isna(cash):
        miss = [n for n, v in (("total borrowings", borrowings),
                               ("cash & equivalents", cash))
                if v is None or pd.isna(v)]
        return None, "missing " + " and ".join(miss)
    return float(borrowings) - float(cash), "ok"


def ev_ebitda(mcap_cr, nd_cr, eb_cr) -> tuple[float | None, str]:
    """H45 (f). NULL on EBITDA <= 0 — a negative multiple is meaningless, not cheap."""
    if mcap_cr is None or nd_cr is None or eb_cr is None:
        return None, "missing pre-money market cap, net debt or EBITDA"
    if float(eb_cr) <= 0:
        return None, "EBITDA <= 0: no meaningful EV/EBITDA"
    return (float(mcap_cr) + float(nd_cr)) / float(eb_cr), "ok"


def fcf_yield(cfo_cr, capex_cr, mcap_cr) -> tuple[float | None, str]:
    """H45 (f). KEEPS its sign: a company burning cash has a negative FCF yield, and that
    is information rather than an artefact. Only a multiple is meaningless when negative.
    """
    if cfo_cr is None or capex_cr is None or mcap_cr is None:
        miss = [n for n, v in (("cash from operations", cfo_cr), ("capex", capex_cr),
                               ("pre-money market cap", mcap_cr)) if v is None]
        return None, "missing " + " and ".join(miss)
    if float(mcap_cr) <= 0:
        return None, "pre-money market cap <= 0"
    return (float(cfo_cr) - float(capex_cr)) / float(mcap_cr), "ok"


# ------------------------------------------------------------------ the build
def _wide():
    """`(values, pages, source lines, version string)`, newest extractor PER VARIABLE.

    The floor at 1.8.0 keeps the four superseded passes out: they hold values the current
    readers have since been fixed to REFUSE, and a plain "newest wins" would resurrect a
    1.7.0 share count that 1.8.1 declines to produce.
    """
    d = newest_per_variable(floor="1.8.0")
    if d.empty:
        raise RuntimeError("no extracted rows at or above extractor version 1.8.0")
    ver = "+".join(sorted(set(d["extractor_version"].astype(str)), key=_ver_key))
    d = d.copy()
    d["_x"] = np.where(d["value_crore"].notna(), d["value_crore"], d["value"])
    val = d.pivot_table(index="company", columns="variable", values="_x", aggfunc="first")
    pg = d.pivot_table(index="company", columns="variable", values="page", aggfunc="first")
    src = d.pivot_table(index="company", columns="variable", values="source_text",
                        aggfunc="first")
    return val, pg, src, ver


def _offer_prices() -> pd.DataFrame:
    m = dataio.load_master_with_symbols()
    m = m[["company", "symbol", "listing_date", "Offer Price", "Issue_Size(crores)"]]
    m.columns = ["company", "symbol", "listing_date", "offer_price", "issue_size_cr"]
    m["_n"] = m["company"].map(lambda c: dataio.norm_name(c) if pd.notna(c) else "")
    return m


def _get(row, name):
    v = row.get(name)
    return None if v is None or pd.isna(v) else float(v)


def build(write: bool = True) -> pd.DataFrame:
    val, pg, src, ver = _wide()
    m = _offer_prices()
    by_n = {r["_n"]: r for _, r in m.iterrows()}

    rows = []
    for company in val.index:
        v = val.loc[company]
        mr = by_n.get(dataio.norm_name(company))
        po = None if mr is None else _get(mr, "offer_price")
        issue_cr = None if mr is None else _get(mr, "issue_size_cr")
        o = {"company": company,
             "symbol": None if mr is None else mr.get("symbol"),
             "listing_date": None if mr is None else mr.get("listing_date"),
             "offer_price": po, "issue_size_cr": issue_cr,
             "extractor_version_used": ver}

        # --- (a) P/E on DILUTED EPS, and the weighted variant
        o["ipo_pe"], o["ipo_pe_reason"] = pe(po, _get(v, "eps_diluted_fy1"))
        o["ipo_pe_weighted"], o["ipo_pe_weighted_reason"] = pe(
            po, _get(v, "eps_diluted_weighted"))
        o["eps_diluted_fy1"] = _get(v, "eps_diluted_fy1")
        o["eps_diluted_fy1_page"] = pg.loc[company].get("eps_diluted_fy1")

        # --- (b) P/B. Post-issue follows H43; pre-issue is new here.
        nav_post = _get(v, "nav_post_issue")
        method = "rhp_stated_post_issue_nav" if nav_post is not None else "none"
        o["ipo_pb"], o["ipo_pb_reason"] = pb(po, nav_post)
        o["ipo_pb_method"] = method if o["ipo_pb"] is not None else "none"

        nav_pre = _get(v, "nav_pre_issue")
        pre_shares = _get(v, "shares_outstanding_pre_issue")
        nw = _get(v, "net_worth_fy1")
        pre_method = "rhp_stated_pre_issue_nav"
        if nav_pre is None and nw is not None and pre_shares is not None and pre_shares > 0:
            # Rs crore / shares -> Rs per share
            nav_pre = nw * CR / pre_shares
            pre_method = "derived_pre_issue_nav"
        elif nav_pre is None:
            pre_method = "none"
        o["ipo_pb_pre_issue"], o["ipo_pb_pre_issue_reason"] = pb(po, nav_pre)
        o["ipo_pb_pre_issue_method"] = (pre_method if o["ipo_pb_pre_issue"] is not None
                                        else "none")
        o["nav_pre_issue_used"] = nav_pre

        # --- (c) peer premiums
        peer_pes = [_get(v, f"peer_{i}_pe") for i in range(1, 13)]
        (o["pe_premium_vs_peers"], o["pe_premium_vs_peer_median"],
         o["n_usable_peer_pe"], o["pe_premium_reason"]) = peer_premium(o["ipo_pe"],
                                                                      peer_pes)

        # --- (d) PAT CAGR and PEG
        o["pat_cagr"], o["pat_cagr_reason"] = cagr_2y(_get(v, "pat_fy1"),
                                                      _get(v, "pat_fy3"))
        o["ipo_peg"], o["ipo_peg_reason"] = peg(o["ipo_pe"], o["pat_cagr"])

        # --- (e) EBITDA
        eb, eb_method, eb_reason = ebitda(_get(v, "ebitda_fy1"), _get(v, "pat_fy1"),
                                          _get(v, "tax_expense_fy1"),
                                          _get(v, "finance_costs_fy1"),
                                          _get(v, "dep_amort_fy1"))
        o["ebitda_cr"], o["ebitda_method"], o["ebitda_reason"] = eb, eb_method, eb_reason

        # --- (f) pre-money basis
        mc, mc_reason = pre_money_mcap_cr(pre_shares, po)
        if mc is not None and issue_cr is not None:
            okp, why = share_count_plausible(pre_shares, po, issue_cr)
            if not okp:
                mc, mc_reason = None, f"pre-issue share count implausible: {why}"
        o["pre_money_mcap_cr"], o["pre_money_mcap_reason"] = mc, mc_reason
        nd, nd_reason = net_debt(_get(v, "borrowings_fy1"), _get(v, "cash_fy1"))
        o["net_debt_cr"], o["net_debt_reason"] = nd, nd_reason
        o["ipo_ev_ebitda"], o["ipo_ev_ebitda_reason"] = ev_ebitda(mc, nd, eb)
        o["fcf_yield"], o["fcf_yield_reason"] = fcf_yield(_get(v, "cfo_fy1"),
                                                          _get(v, "capex_fy1"), mc)
        rows.append(o)

    d = pd.DataFrame(rows)
    if write:
        d.to_csv(OUT, index=False, encoding="utf-8")
    return d


RATIOS = ["ipo_pe", "ipo_pe_weighted", "ipo_pb", "ipo_pb_pre_issue",
          "pe_premium_vs_peers", "pe_premium_vs_peer_median", "pat_cagr", "ipo_peg",
          "ebitda_cr", "pre_money_mcap_cr", "net_debt_cr", "ipo_ev_ebitda", "fcf_yield"]


def coverage(d: pd.DataFrame | None = None) -> pd.DataFrame:
    d = build(write=False) if d is None else d
    e = d.copy()
    e["_ld"] = pd.to_datetime(e["listing_date"], errors="coerce")
    e19 = e[e["_ld"] >= "2019-01-01"]
    out = []
    for c in RATIOS:
        rc = c.replace("_cr", "") + "_reason"
        rc = rc if rc in d.columns else (c + "_reason")
        top = ""
        if rc in d.columns:
            bad = d.loc[d[c].isna(), rc].dropna().astype(str)
            if len(bad):
                top = bad.value_counts().index[0][:70]
        out.append({"ratio": c, "all": int(d[c].notna().sum()),
                    "all_pct": round(d[c].notna().mean() * 100, 1),
                    "2019+": int(e19[c].notna().sum()),
                    "2019+_pct": round(e19[c].notna().mean() * 100, 1)
                    if len(e19) else 0.0,
                    "top_reason_when_null": top})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    def close(a, b, tol=1e-9):
        return a is not None and abs(a - b) < tol

    print("[a] P/E, on numbers whose answer is known by hand")
    chk("271 / 13.55 = 20.0", close(pe(271.0, 13.55)[0], 20.0))
    chk("a loss gives NULL, not a negative multiple", pe(271.0, -2.0)[0] is None)
    chk("and the reason says so", "EPS <= 0" in pe(271.0, -2.0)[1])
    chk("zero EPS is NULL too", pe(271.0, 0.0)[0] is None)
    chk("a missing EPS is NULL", pe(271.0, None)[0] is None)

    print("\n[b] P/B, including the derived pre-issue route")
    chk("100 / 40 = 2.5", close(pb(100.0, 40.0)[0], 2.5))
    chk("a negative book value gives NULL", pb(100.0, -5.0)[0] is None)
    # net worth Rs 500 cr over 10,000,000 shares = Rs 500 per share
    chk("net worth / pre-issue shares is Rs per share",
        close(500.0 * CR / 1e7, 500.0))

    print("\n[c] the peer basket is a HARMONIC mean, and needs two peers")
    chk("harmonic mean of 10 and 30 is 15, not 20",
        close(harmonic_mean([10.0, 30.0]), 15.0))
    chk("one 180x peer cannot carry the basket the way a mean would",
        harmonic_mean([10.0, 10.0, 180.0]) < 20.0)
    chk("a non-positive peer P/E is dropped before the reciprocal",
        close(harmonic_mean([10.0, 30.0, -5.0, 0.0]), 15.0))
    prem = peer_premium(30.0, [10.0, 30.0])
    chk("premium vs harmonic mean: 30/15 - 1 = 1.0", close(prem[0], 1.0))
    chk("premium vs median: 30/20 - 1 = 0.5", close(prem[1], 0.5))
    chk("one usable peer is not a basket",
        peer_premium(30.0, [10.0, None, -3.0])[0] is None)
    chk("and the reason counts them",
        "need 2" in peer_premium(30.0, [10.0])[3])

    print("\n[d] three fiscal years are TWO growth years")
    # 100 -> 121 over two years is 10% a year, not 6.5%
    chk("100 -> 121 is 10.0% a year", close(cagr_2y(121.0, 100.0)[0], 0.10, 1e-12))
    chk("the exponent is 1/2, not 1/3",
        not close(cagr_2y(121.0, 100.0)[0], 121 / 100 ** (1 / 3) - 1, 1e-3))
    chk("a loss at either end gives NULL",
        cagr_2y(121.0, -10.0)[0] is None and cagr_2y(-1.0, 100.0)[0] is None)
    chk("PEG divides by the PERCENT: 20 / 10 = 2.0",
        close(peg(20.0, 0.10)[0], 2.0))
    chk("shrinking earnings give no PEG", peg(20.0, -0.05)[0] is None)

    print("\n[e] EBITDA is withheld, never zero-filled")
    chk("a stated figure wins",
        ebitda(123.0, 1, 2, 3, 4)[0] == 123.0
        and ebitda(123.0, 1, 2, 3, 4)[1] == "stated_ebitda")
    v, meth, why = ebitda(None, 100.0, 30.0, 20.0, 50.0)
    chk("otherwise PAT + tax + finance + D&A = 200", close(v, 200.0))
    chk("and the method says it was derived", meth == "derived_ebitda")
    chk("the row admits it includes other income", "other income" in why)
    for miss, label in (((None, 30.0, 20.0, 50.0), "PAT"),
                        ((100.0, None, 20.0, 50.0), "tax expense"),
                        ((100.0, 30.0, None, 50.0), "finance costs"),
                        ((100.0, 30.0, 20.0, None), "depreciation & amortisation")):
        got = ebitda(None, *miss)
        chk(f"a missing {label} withholds the whole figure", got[0] is None)
        chk(f"and names {label} as what is missing", label in got[2])
    chk("the withholding reason says it is never zero-filled",
        "never zero-filled" in ebitda(None, 100.0, None, 20.0, 50.0)[2])

    print("\n[f] the pre-money basis")
    # 10,000,000 shares at Rs 271 = Rs 271 crore
    chk("shares x price comes out in Rs crore",
        close(pre_money_mcap_cr(1e7, 271.0)[0], 271.0))
    chk("a missing pre-issue count gives NULL",
        pre_money_mcap_cr(None, 271.0)[0] is None)
    chk("net debt = borrowings - cash", close(net_debt(300.0, 120.0)[0], 180.0))
    chk("net CASH keeps its negative sign", close(net_debt(50.0, 120.0)[0], -70.0))
    chk("a missing borrowing line withholds net debt, it does not read as zero",
        net_debt(None, 120.0)[0] is None)
    chk("and names which line is missing",
        "total borrowings" in net_debt(None, 120.0)[1])
    chk("EV/EBITDA = (mcap + net debt) / EBITDA = (271 + 29) / 20 = 15.0",
        close(ev_ebitda(271.0, 29.0, 20.0)[0], 15.0))
    chk("negative EBITDA gives NULL, not a negative multiple",
        ev_ebitda(271.0, 29.0, -5.0)[0] is None)
    chk("FCF yield = (CFO - capex) / pre-money mcap = (40 - 15) / 250 = 10%",
        close(fcf_yield(40.0, 15.0, 250.0)[0], 0.10))
    chk("a cash-burning company KEEPS its negative yield - a yield is not a multiple",
        close(fcf_yield(-10.0, 15.0, 250.0)[0], -0.10))
    chk("a missing capex withholds the yield rather than assuming no capex",
        fcf_yield(40.0, None, 250.0)[0] is None)

    print("\n[g] what is deliberately not built")
    src = inspect.getsource(sys.modules[__name__])
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.strip().startswith("#"))
    # The labels avoid the words too, or each needle finds itself in the code it is
    # searching and the check passes for the wrong reason.
    for label, needle in {"a discounted-cash-flow model": "D" + "CF",
                          "an assumed required return": "cost_of_" + "equity",
                          "a perpetual-growth dividend model": "gor" + "don"}.items():
        chk(f"no {label} is computed", needle.lower() not in code.lower(), needle)

    print("\n[h] provenance and the version floor")
    chk("the newest version PER VARIABLE is used, with a floor",
        'newest_per_variable(floor="1.8.0")' in src)
    chk("the share-count guard is the SAME one the P/B module uses",
        "from derive_pb import" in src and "share_count_plausible" in src)
    chk("every row records which extractor versions it came from",
        '"extractor_version_used"' in src)
    chk("every ratio has a reason column beside it",
        all(f'"{c}_reason"' in src or f'{c}_reason' in src
            for c in ("ipo_pe", "ipo_pb", "pat_cagr", "fcf_yield")))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--worked-examples", type=int, default=0)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.build or a.coverage or a.worked_examples:
        d = build()
        print(f"wrote {OUT.name}: {len(d)} rows")
    if a.coverage:
        print(coverage(d).to_string(index=False))
    if a.worked_examples:
        e = d.copy()
        e["_ld"] = pd.to_datetime(e["listing_date"], errors="coerce")
        e = e[(e["_ld"] >= "2019-01-01") & e["ipo_pe"].notna()]
        for _, r in e.head(a.worked_examples).iterrows():
            print(f"\n=== {r['company']} ({str(r['listing_date'])[:10]}) "
                  f"offer Rs {r['offer_price']}")
            for c in RATIOS:
                rc = c + "_reason"
                print(f"  {c:28s} {r[c] if pd.notna(r[c]) else 'NULL':>14} "
                      f"  {r.get(rc, '')}")

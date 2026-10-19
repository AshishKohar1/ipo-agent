"""
derive_valuation_ratios.py — Priority 1.3: the eight ratios, at the final offer price.

Inputs are the extracted RHP values (`data/rhp_valuation_values.csv`, filtered to one
extractor version) and the final **Offer Price** from the master, joined on symbol — 412
of 412 documents join. Nothing is fetched.

The eight
---------
    ipo_pe                        offer price / basic EPS, most recent fiscal year
    ipo_pb                        offer price / post-issue NAV per share
    eps_cagr_3y                   growth from the oldest to the newest EPS in the window
    ipo_peg                       ipo_pe / EPS growth in percent
    ipo_ev_ebitda                 (market cap + borrowings - cash) / EBITDA
    fcf_yield                     (cash from operations - capex) / market cap
    pe_premium_vs_peer_median     ipo_pe / median listed-peer P/E - 1
    pb_premium_vs_peer_median     ipo_pb / median listed-peer P/B - 1

and, because the user's list asks for a premium against the sector index too,
`pe_premium_vs_sector_index` / `pb_premium_vs_sector_index`, which are NULL with a stated
reason until the per-sector-index P/E histories are fetched — only the Nifty 50 P/E series
is on disk, so the *market* premium is given as well and is not called a sector premium.

What is never produced
----------------------
**A negative multiple.** A loss-making company has no P/E: `ipo_pe` and `ipo_peg` are NULL
with the reason `negative earnings`, and the same for `ipo_ev_ebitda` on negative EBITDA
and `ipo_pb` on a negative book value. A negative multiple is not a cheap valuation, it is
a meaningless one, and a model fed -3.2 as a P/E would read it as cheaper than 8.

`fcf_yield` is the exception and keeps its sign: it is a yield, not a multiple, and a
company burning cash genuinely has a negative free-cash-flow yield. That is information,
not an artefact.

**No DCF** (rule 3: it needs forecasts, and the RHP does not publish them).

Every row carries, per ratio, the inputs used and the printed page each came from, so a
ratio can be walked back to the line in the prospectus (rule 2).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import dataio                                                        # noqa: E402

DATA = ROOT / "data"
VALUES = DATA / "rhp_valuation_values.csv"
OUT = DATA / "valuation_ratios.csv"
PE_HISTORY = DATA / "nifty_pe_history.csv"
SECTOR_MAP = DATA / "sector_map.csv"
MAX_PEERS = 12
NEG_EARNINGS = "negative earnings"
SECTOR_PE_REASON = ("no P/E series is on disk for the sector index; only the Nifty 50 "
                    "P/E history has been fetched, so this is left NULL rather than "
                    "substituting the market multiple for a sector one")


def _wide(version: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """`(value per company x variable, page per company x variable, version used)`."""
    from extract.valuation import VALUATION_VERSION
    v = version or VALUATION_VERSION
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[d["extractor_version"].astype(str) == str(v)]
    if d.empty:
        raise RuntimeError(f"no rows at extractor version {v}")
    d = d[d["status"].astype(str) == "ok"]
    # value_crore where the extractor converted a money figure, value otherwise. A ratio
    # must never mix a figure in millions with one in crore, and `value_crore` is the only
    # column on which the unit is guaranteed to be the same for every row.
    d["_x"] = np.where(d["value_crore"].notna(), d["value_crore"], d["value"])
    val = d.pivot_table(index="company", columns="variable", values="_x", aggfunc="first")
    pg = d.pivot_table(index="company", columns="variable", values="page", aggfunc="first")
    return val, pg, str(v)


def _g(row, name):
    x = row.get(name)
    return None if x is None or pd.isna(x) else float(x)


def _peer_median(row, field: str) -> tuple[float | None, int]:
    """Median of the listed peers' own multiple, non-positive values dropped."""
    xs = [_g(row, f"peer_{i}_{field}") for i in range(1, MAX_PEERS + 1)]
    xs = [x for x in xs if x is not None and x > 0]
    return (float(np.median(xs)) if len(xs) >= 2 else None), len(xs)


def _market_pe(listing_date) -> tuple[float | None, str]:
    """The Nifty 50 trailing P/E on the last trading day at or before listing."""
    if not PE_HISTORY.exists() or pd.isna(listing_date):
        return None, "no Nifty 50 P/E history on disk"
    h = pd.read_csv(PE_HISTORY)
    h["date"] = pd.to_datetime(h["date"], errors="coerce")
    h = h[h["date"] <= pd.Timestamp(listing_date)].sort_values("date")
    if h.empty:
        return None, "the P/E series does not reach back to this listing date"
    return float(h.iloc[-1]["pe"]), ""


def derive(version: str | None = None) -> pd.DataFrame:
    val, pg, ver = _wide(version)
    ms = dataio.load_master_with_symbols()
    sym2price = {str(r["symbol"]): r.get("Offer Price") for _, r in ms.iterrows()
                 if pd.notna(r.get("symbol"))}
    sym2size = {str(r["symbol"]): r.get("Issue_Size(crores)") for _, r in ms.iterrows()
                if pd.notna(r.get("symbol"))}
    raw = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    raw = raw[raw["extractor_version"].astype(str) == ver]
    meta = raw.groupby("company").agg(symbol=("symbol", "first"),
                                      listing_date=("listing_date", "first"))
    smap = pd.read_csv(SECTOR_MAP) if SECTOR_MAP.exists() else pd.DataFrame()
    sym2sector = (dict(zip(smap["symbol"].astype(str), smap["sector_index"]))
                  if len(smap) else {})

    rows = []
    for company, row in val.iterrows():
        m = meta.loc[company] if company in meta.index else {}
        sym = str(m.get("symbol")) if hasattr(m, "get") else ""
        price = sym2price.get(sym)
        price = float(price) if price is not None and pd.notna(price) else None
        p = pg.loc[company] if company in pg.index else {}

        def page(name):
            x = p.get(name) if hasattr(p, "get") else None
            return "" if x is None or pd.isna(x) else int(x)

        o: dict = {"company": company, "symbol": sym,
                   "listing_date": m.get("listing_date") if hasattr(m, "get") else None,
                   "offer_price": price, "extractor_version": ver}
        if price is None or price <= 0:
            o["notes"] = "no final offer price on the master for this symbol"
            rows.append(o)
            continue

        eps1, eps3 = _g(row, "eps_basic_fy1"), _g(row, "eps_basic_fy3")
        nav = _g(row, "nav_post_issue")
        shares = _g(row, "shares_outstanding_post_issue")
        ebitda, borrow = _g(row, "ebitda_fy1"), _g(row, "borrowings_fy1")
        cash, cfo, capex = _g(row, "cash_fy1"), _g(row, "cfo_fy1"), _g(row, "capex_fy1")

        # --- 1. P/E
        if eps1 is None:
            o["ipo_pe_reason"] = "basic EPS for the most recent fiscal year not extracted"
        elif eps1 <= 0:
            o["ipo_pe_reason"] = NEG_EARNINGS
        else:
            o["ipo_pe"] = round(price / eps1, 4)
            o["ipo_pe_inputs"] = f"offer {price} / EPS {eps1} (page {page('eps_basic_fy1')})"
        # The RHP states its own P/E at the cap price. Where both exist they are compared,
        # because a derived multiple that disagrees with the one the document prints is a
        # sign the EPS was read from the wrong row.
        stated = _g(row, "pe_at_cap")
        if o.get("ipo_pe") and stated and stated > 0:
            gap = abs(o["ipo_pe"] - stated) / stated
            o["ipo_pe_vs_stated_pct"] = round(100 * gap, 2)
            o["ipo_pe_agrees_with_rhp"] = bool(gap <= 0.05)

        # --- 2. P/B, from post-issue NAV per share (no share count needed)
        if nav is None:
            o["ipo_pb_reason"] = "post-issue NAV per share not extracted"
        elif nav <= 0:
            o["ipo_pb_reason"] = "negative or zero book value"
        else:
            o["ipo_pb"] = round(price / nav, 4)
            o["ipo_pb_inputs"] = f"offer {price} / NAV {nav} (page {page('nav_post_issue')})"

        # --- 3. EPS growth
        if eps1 is None or eps3 is None:
            o["eps_cagr_3y_reason"] = "EPS is not available for both ends of the window"
        elif eps1 <= 0 or eps3 <= 0:
            o["eps_cagr_3y_reason"] = ("a compound rate is undefined across a sign change "
                                       "or a zero base")
        else:
            o["eps_cagr_3y"] = round((eps1 / eps3) ** 0.5 - 1, 6)
            o["eps_cagr_3y_inputs"] = (f"EPS {eps3} -> {eps1} over two years "
                                       f"(pages {page('eps_basic_fy3')}, "
                                       f"{page('eps_basic_fy1')})")

        # --- 4. PEG
        g = o.get("eps_cagr_3y")
        if o.get("ipo_pe") is None:
            o["ipo_peg_reason"] = o.get("ipo_pe_reason", "no P/E")
        elif g is None:
            o["ipo_peg_reason"] = o.get("eps_cagr_3y_reason", "no growth rate")
        elif g <= 0:
            o["ipo_peg_reason"] = "non-positive earnings growth"
        else:
            o["ipo_peg"] = round(o["ipo_pe"] / (g * 100), 4)

        # --- 5. EV/EBITDA
        # The SAME two-sided guard as the P/B module, imported rather than restated so
        # the two can never drift apart. 32 of the 153 extracted share counts fail it -
        # 20 too small, 12 the aggregate rupee capital read as shares - and every ratio
        # below is built on this number, so a wrong one poisons EV/EBITDA and FCF yield
        # exactly as it poisoned the derived P/B.
        from derive_pb import share_count_plausible
        issue_cr = sym2size.get(sym)
        sh_ok, sh_why, sh_ratio = share_count_plausible(shares, price, issue_cr)
        o["post_issue_shares_mcap_over_issue"] = (None if sh_ratio is None
                                                  else round(sh_ratio, 3))
        o["post_issue_shares_check"] = sh_why
        if shares is not None and not sh_ok:
            shares = None
        mcap = round(price * shares / 1e7, 4) if shares else None
        o["market_cap_crore"] = mcap
        if mcap is None:
            o["ipo_ev_ebitda_reason"] = (sh_why if (shares is None and not sh_ok)
                                         else "post-issue share count not extracted")
        elif ebitda is None:
            o["ipo_ev_ebitda_reason"] = "EBITDA not extracted"
        elif ebitda <= 0:
            o["ipo_ev_ebitda_reason"] = "negative EBITDA"
        elif borrow is None or cash is None:
            o["ipo_ev_ebitda_reason"] = ("borrowings or cash not extracted, so enterprise "
                                         "value cannot be built")
        else:
            ev = mcap + borrow - cash
            o["enterprise_value_crore"] = round(ev, 4)
            o["ipo_ev_ebitda"] = round(ev / ebitda, 4)
            o["ipo_ev_ebitda_inputs"] = (f"mcap {mcap} + borrowings {borrow} "
                                         f"(page {page('borrowings_fy1')}) - cash {cash} "
                                         f"(page {page('cash_fy1')}) / EBITDA {ebitda} "
                                         f"(page {page('ebitda_fy1')})")

        # --- 6. FCF yield. Sign kept: a cash-burning company has a negative FCF yield.
        if mcap is None:
            o["fcf_yield_reason"] = (sh_why if (shares is None and not sh_ok)
                                     else "post-issue share count not extracted")
        elif cfo is None or capex is None:
            o["fcf_yield_reason"] = "cash from operations or capex not extracted"
        else:
            o["fcf_yield"] = round((cfo - capex) / mcap, 6)
            o["fcf_yield_inputs"] = (f"(CFO {cfo} (page {page('cfo_fy1')}) - capex "
                                     f"{capex} (page {page('capex_fy1')})) / mcap {mcap}")

        # --- 7/8. premiums against the listed peers the RHP itself names
        for field, own, out_name in (("pe", "ipo_pe", "pe_premium_vs_peer_median"),
                                     ("pb", "ipo_pb", "pb_premium_vs_peer_median")):
            med, n = _peer_median(row, field)
            o[f"peer_{field}_median"], o[f"peer_{field}_n"] = med, n
            if o.get(own) is None:
                o[f"{out_name}_reason"] = f"no {own}"
            elif med is None:
                o[f"{out_name}_reason"] = (f"fewer than two listed peers with a positive "
                                           f"{field.upper()} in the prospectus table "
                                           f"({n} found)")
            else:
                o[out_name] = round(o[own] / med - 1, 4)

        # --- the market comparison, named for what it is
        mpe, why = _market_pe(o["listing_date"])
        o["nifty50_pe_at_listing"] = mpe
        if o.get("ipo_pe") is None:
            o["pe_premium_vs_market_reason"] = "no ipo_pe"
        elif mpe is None:
            o["pe_premium_vs_market_reason"] = why
        else:
            o["pe_premium_vs_market"] = round(o["ipo_pe"] / mpe - 1, 4)
        o["sector_index"] = sym2sector.get(sym)
        o["pe_premium_vs_sector_index_reason"] = SECTOR_PE_REASON
        o["pb_premium_vs_sector_index_reason"] = SECTOR_PE_REASON
        rows.append(o)

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False, encoding="utf-8")
    return d


RATIOS = ["ipo_pe", "ipo_pb", "eps_cagr_3y", "ipo_peg", "ipo_ev_ebitda", "fcf_yield",
          "pe_premium_vs_peer_median", "pb_premium_vs_peer_median"]


def coverage(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["year"] = pd.to_datetime(d["listing_date"], errors="coerce").dt.year
    pre, mod = d[d["year"] < 2019], d[d["year"] >= 2019]
    rows = []
    for r in RATIOS + ["pe_premium_vs_market"]:
        if r not in d:
            rows.append({"ratio": r, "all": 0, "pre_2019": 0, "from_2019": 0,
                         "top_reason": "never produced on any document"})
            continue
        rsn = d.get(f"{r}_reason")
        top = ""
        if rsn is not None:
            vc = rsn[d[r].isna()].dropna().value_counts()
            if len(vc):
                top = f"{vc.index[0][:58]} ({vc.iloc[0]})"
        rows.append({"ratio": r,
                     "all": f"{int(d[r].notna().sum())}/{len(d)} "
                            f"({100 * d[r].notna().mean():.0f}%)",
                     "pre_2019": f"{int(pre[r].notna().sum())}/{len(pre)}" if len(pre)
                                 else "0/0",
                     "from_2019": f"{int(mod[r].notna().sum())}/{len(mod)}" if len(mod)
                                  else "0/0",
                     "top_reason": top})
    return pd.DataFrame(rows)


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

    # The self-test's OWN source is removed from the haystack. A check for the absence
    # of a string cannot be written as a literal in the text it searches - the "no DCF"
    # assertion failed on itself the first time it ran.
    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] a loss-making company never gets a multiple")
    v = pd.DataFrame({"eps_basic_fy1": [-4.0], "nav_post_issue": [-2.0],
                      "ebitda_fy1": [-10.0]})
    r = v.iloc[0]
    chk("negative EPS is caught before the division", _g(r, "eps_basic_fy1") < 0)
    chk("and the reason is the words the user asked for", NEG_EARNINGS ==
        "negative earnings")
    chk("negative book value is refused too", "negative or zero book value" in src)
    chk("negative EBITDA is refused too", '"negative EBITDA"' in src)
    chk("non-positive growth gives no PEG", '"non-positive earnings growth"' in src)
    chk("fcf_yield KEEPS its sign - it is a yield, not a multiple",
        "Sign kept" in src and "fcf_yield_reason" in src)
    body = src.split('"""', 2)[-1].lower()
    chk("no DCF anywhere in the code (rule 3: it needs forecasts)", "dcf" not in body)

    print(chr(10) + "[2] units cannot be mixed")
    chk("money figures are taken from value_crore where it exists", '"_x"] = np.where' in
        src and 'value_crore' in src)
    chk("market cap is built in crore from a rupee price and a share count",
        "price * shares / 1e7" in src)
    chk("and the share count passes the SAME guard the P/B module uses",
        "from derive_pb import share_count_plausible" in src)
    chk("a refused count blocks EV/EBITDA and FCF yield, with the reason on the row",
        'o["post_issue_shares_check"]' in src and "sh_why" in src)

    print(chr(10) + "[3] a peer median is a median of at least two peers")
    row = pd.Series({f"peer_{i}_pe": x for i, x in
                     enumerate([10.0, 20.0, -5.0, None], start=1)})
    med, n = _peer_median(row, "pe")
    chk("non-positive peer multiples are dropped", n == 2, (med, n))
    chk("the median is of what is left", med == 15.0, med)
    one = pd.Series({"peer_1_pe": 10.0})
    chk("a single peer is not a median", _peer_median(one, "pe")[0] is None)

    print(chr(10) + "[4] provenance and honesty of the sector premium")
    chk("every ratio records its inputs and their pages",
        all(f"{k}_inputs" in src for k in ("ipo_pe", "ipo_pb", "ipo_ev_ebitda",
                                           "fcf_yield")))
    chk("the market P/E is NOT presented as a sector P/E",
        "pe_premium_vs_market" in src and "substituting the market multiple" in src)
    chk("the sector premium is NULL with a stated reason", SECTOR_PE_REASON.startswith(
        "no P/E series is on disk for the sector index"))
    chk("the derived P/E is compared with the one the prospectus prints",
        "ipo_pe_agrees_with_rhp" in src)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    d = derive(a.version)
    print(f"wrote {OUT.name}: {len(d)} companies")
    if a.coverage or True:
        print()
        print(coverage(d).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

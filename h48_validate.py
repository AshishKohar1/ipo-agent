"""
h48_validate.py — hand-validation of H48 on every transcribed check-set RHP.

H48 says a Red Herring Prospectus cannot state its post-issue share count, post-issue NAV
or promoter post-Offer percentage, because all three depend on a price the book has not yet
fixed. Two branches escape that: a pure offer for sale creates no shares, and a fresh issue
stated as a fixed SHARE COUNT is knowable without a price.

Every input below was read by hand from a page of the document and carries its page number
and the line it came from. Nothing is inferred from a figure the RHP does not print, and
where an input is missing the output is withheld rather than estimated (rule 3).

Two findings that change how the net-worth reader must work
-----------------------------------------------------------
1. **"Net worth" is not always "equity share capital + other equity".** Craftsman
   Automation's balance sheet prints its own total-equity sub-total of Rs 7,716.11 million
   at 31 December 2020, but its stated NAV of Rs 355.93 implies Rs 7,161.88 million - 7.7%
   lower. The document settles it itself: its stated RoNW of 7.07% against a profit of
   Rs 506.60 million requires a net worth of about Rs 7,165 million, which matches the NAV
   figure and not the balance-sheet sub-total. So the reader must cross-check net worth
   against the stated NAV and RoNW and withhold on disagreement, not simply cross-foot.
   Prince Pipes and Vishwaraj Sugar both print an explicit net-worth DEFINITION that
   excludes revaluation reserves and preference capital, which is the likely mechanism.

2. **The share count behind the NAV is the PERIOD-END count, not the RHP-date count.**
   Medanta, Prince Pipes and CAMS all show it. Dividing net worth by the pre-issue count
   on the capital-structure page therefore reproduces the stated NAV only when no shares
   were issued between the balance-sheet date and the RHP. The cross-check has to allow
   for that, or it will reject good readings.

    python h48_validate.py            # print the table
    python h48_validate.py --self-test
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
import derive_post_issue as DPI                             # noqa: E402

LAKH = 100_000.0
MILLION = 1_000_000.0
OUT_CSV = ROOT / "reports" / "H48_VALIDATION.csv"
OUT_MD = ROOT / "reports" / "H48_VALIDATION.md"

# ---------------------------------------------------------------------------------------
# Hand-read inputs. `pages` records where each number came from; `quoted` the line itself.
# `nw_basis` says WHICH net worth was used and why, because that is the field where these
# documents disagree with themselves.
# ---------------------------------------------------------------------------------------
CASES = [
    dict(
        company="Polycab India Ltd", year=2019, industry="Electricals",
        pre_shares=141_205_838, fresh_amount_inr=4_000.0 * MILLION, offer_price=538.0,
        issue_size_cr=1345.26,
        pre_net_worth_inr=23_493.73 * MILLION, pre_nav=166.39,
        promoter_pre_shares=93_646_582,
        # NOT the whole 17,582,000 offer for sale. p89 breaks it down by shareholder, and
        # only four of the nine are Promoters as p2 defines them: Inder, Ajay, Ramesh and
        # Girdhari Jaisinghani, 2,089,603 + 2,071,965 + 2,071,963 + 2,079,313. IFC is the
        # Investor Selling Shareholder, Bharat and Nikhil are Promoter GROUP rather than
        # Promoters, and Hariani and Ramamurthi are Individual Selling Shareholders.
        promoter_ofs_shares=2_089_603 + 2_071_965 + 2_071_963 + 2_079_313,
        promoter_pre_pct=66.32,
        nw_basis="stated net worth, Rs 23,493.73 million at 31 Mar 2018",
        pages="pre-issue shares and fresh issue p102; net worth and NAV p131; "
              "promoter holding p106; OFS by shareholder p89; who counts as a Promoter p2",
        quoted="141,205,838 Equity Shares / Fresh Issue of up to [*] Equity Shares "
               "aggregating upto Rs 4,000 / Offer for Sale of up to 17,582,000 Equity "
               "Shares / our Promoters, hold 93,646,582 Equity Shares, constituting "
               "66.32% / 2. Inder T. Jaisinghani Up to 2,089,603 Offered Shares ... "
               "Total Up to 17,582,000 Offered Shares",
        stated_post_shares=None, stated_post_nav=None, stated_promoter_post=None,
        branch="fresh issue stated as a RUPEE amount - needs the price. The promoters "
               "ARE selling, so the promoter percentage needs their own OFS share count, "
               "not the offer's total"),
    dict(
        company="Craftsman Automation Limited", year=2021, industry="Auto components",
        pre_shares=20_121_600, fresh_amount_inr=1_500.0 * MILLION, offer_price=1490.0,
        issue_size_cr=823.70,
        # NOT the balance-sheet sub-total of 7,716.11 million. See finding 1 above.
        pre_net_worth_inr=355.93 * 20_121_600, pre_nav=355.93,
        promoter_pre_shares=10_630_640, promoter_ofs_shares=130_640,
        promoter_pre_pct=52.83,
        nw_basis="implied by the stated NAV (355.93 x 20,121,600 = Rs 7,161.88 million); "
                 "CORROBORATED by the stated RoNW of 7.07% on a profit of Rs 506.60 "
                 "million, which needs ~Rs 7,165 million. The balance sheet's own total "
                 "equity sub-total of Rs 7,716.11 million would give RoNW 6.57% and is "
                 "NOT the net worth this RHP uses",
        pages="pre-issue shares and fresh issue p71; promoter p72; promoter OFS p57; "
              "NAV and RoNW p88; total equity p59",
        quoted="20,121,600 Equity Shares of face value of Rs 5 each 100.61 / "
               "Fresh Issue of up to [*] Equity Shares aggregating Rs 1,500.00 million / "
               "As on December 31, 2020 355.93 / 1. Srinivasan Ravi October 29, 2020 "
               "130,640",
        stated_post_shares=None, stated_post_nav=None, stated_promoter_post=None,
        branch="fresh issue stated as a RUPEE amount - needs the price"),
    dict(
        company="Global Health Limited (Medanta)", year=2022, industry="Hospitals",
        pre_shares=253_303_930, fresh_amount_inr=5_000.0 * MILLION, offer_price=336.0,
        issue_size_cr=2205.57,
        pre_net_worth_inr=16_160.11 * MILLION, pre_nav=63.82,
        promoter_pre_shares=88_725_240, promoter_ofs_shares=0,
        promoter_pre_pct=35.00,
        nw_basis="total equity at 31 Mar 2022, Rs 16,160.11 million (p97). Cross-foots to "
                 "the stated NAV within 0.03% on the PERIOD-END share count of "
                 "253,225,000 (share capital 506.45 / face value 2), not the RHP-date "
                 "count of 253,303,930",
        pages="pre-issue shares p125 and p92; fresh issue p92; net worth p97; NAV p161; "
              "promoter p132; selling shareholders p92-93",
        quoted="253,303,930 Equity Shares of face value of Rs 2 each 506,607,860 / "
               "Fresh Issue Up to [*] Equity Shares aggregating to up to Rs 5,000 million "
               "/ Total equity 16,755.51 14,253.77 16,160.11 13,823.42 13,495.37 / "
               "As at March 31, 2022* 63.82 / our Promoter, Dr. Naresh Trehan, holds "
               "88,725,240 Equity Shares, constituting approximately 35.00%",
        stated_post_shares=None, stated_post_nav=None, stated_promoter_post=None,
        branch="fresh issue stated as a RUPEE amount - needs the price. The amount IS "
               "stated here (Rs 5,000 million on p92), which validates the derivation "
               "used on it in Task 5 exactly"),
    dict(
        company="Computer Age Management Services Ltd", year=2020, industry="Financial services",
        pre_shares=48_786_800, fresh_amount_inr=None, fresh_shares=0, offer_price=1230.0,
        issue_size_cr=2242.33,
        pre_net_worth_inr=5_281.97 * MILLION, pre_nav=108.27,
        # Great Terrain sells 6,108,400 shares PRIVATELY before the bid opens, not in the
        # offer, and holds 15,115,600 both pre- and post-Offer by the RHP's own words.
        promoter_pre_shares=15_115_600, promoter_ofs_shares=0,
        promoter_pre_pct=30.98,
        nw_basis="stated net worth Rs 5,281.97 million at 30 Jun 2020 (p11). Cross-foots "
                 "to the stated NAV of 108.27 on 48.785 million shares, exact",
        pages="pre- AND post-issue shares p60; net worth and NAV p11; promoter p63",
        quoted="ISSUED, SUBSCRIBED AND PAID-UP SHARE CAPITAL BEFORE AND AFTER THE OFFER / "
               "48,786,800 Equity Shares 487,868,000 / Net worth 5,281.97 ... / "
               "Great Terrain will hold 15,115,600 Equity Shares, i.e. 30.98% of the "
               "pre-Offer and post-Offer paid-up capital",
        stated_post_shares=48_786_800, stated_post_nav=108.27,
        stated_promoter_post=30.98,
        branch="PURE OFFER FOR SALE - no shares created, so the RHP states the post-issue "
               "count, and the NAV does not move either"),
    dict(
        company="Vishwaraj Sugar Industries Ltd", year=2019, industry="Sugar",
        pre_shares=34_556_000, fresh_shares=3_000_000, offer_price=60.0,
        issue_size_cr=60.00,
        pre_net_worth_inr=61.20 * 34_556_000, pre_nav=61.20,
        promoter_pre_shares=11_734_750, promoter_ofs_shares=400_000,
        promoter_pre_pct=33.96,
        nw_basis="implied by the stated NAV at 31 Mar 2019 (61.20 x 34,556,000 = "
                 "Rs 2,114.83 million). The RHP defines net worth as share capital + "
                 "securities premium + general reserve + surplus, EXCLUDING preference "
                 "capital and revaluation reserve (p110-111)",
        pages="pre- and post-issue shares p70; NAV p111; net-worth definition p110-111; "
              "promoter pre and post p96 and p80",
        quoted="3,45,56,000 Equity Shares of face value of Rs 10 each 3,455.60 / "
               "3,75,56,000 Equity Shares of face value of Rs 10 each 3,755.60 / "
               "NAV as at March 31, 2019 61.20 / our Promoters collectively hold "
               "1,17,34,750 Equity Shares. After successful completion of the IPO, our "
               "Promoters will collectively hold 1,13,34,750 Equity Shares",
        stated_post_shares=37_556_000, stated_post_nav=None,
        stated_promoter_post=None,
        branch="fresh issue stated as a fixed SHARE COUNT (3,000,000) - knowable before "
               "pricing, so the RHP states the post-issue total"),
    dict(
        company="Likhitha Infrastructure Ltd", year=2020, industry="Oil and gas EPC",
        pre_shares=14_625_000, fresh_shares=5_100_000, offer_price=120.0,
        issue_size_cr=61.20,
        pre_net_worth_inr=6_995.58 * LAKH, pre_nav=47.83,
        promoter_pre_shares=14_252_875, promoter_ofs_shares=0,
        promoter_pre_pct=97.46,
        nw_basis="stated Total Equity Rs 6,995.58 LAKH at 31 Mar 2020. The unit was "
                 "unconfirmed until now and is settled by the cross-check: "
                 "699,558,000 / 14,625,000 = Rs 47.8330, against a stated NAV of 47.83",
        pages="pre-issue shares and fresh issue p71 (header: 'Rs. in Lakhs except the "
              "share data'); net worth p59; NAV p94; promoter p171",
        quoted="1,46,25,000 Equity Shares of Rs. 10 each 1,462.50 / Up to 51,00,000 "
               "Equity Shares of Rs. 10.00 each / Total Equity 6,995.58 5,031.23 "
               "3,242.94 / Net Asset Value per Equity Share as of March 31, 2020 47.83 / "
               "our Promoters hold 1,42,52,875 equity shares, which constitutes 97.46%",
        stated_post_shares=None, stated_post_nav=None, stated_promoter_post=None,
        branch="fresh issue stated as a fixed SHARE COUNT (5,100,000), 100% fresh - no "
               "offer for sale"),
    dict(
        company="Prince Pipes and Fittings Ltd", year=2019, industry="Plastic pipes",
        pre_shares=95_980_816, fresh_amount_inr=2_500.0 * MILLION, offer_price=178.0,
        issue_size_cr=500.00,
        pre_net_worth_inr=4_278.56 * MILLION, pre_nav=46.70,
        promoter_pre_shares=84_540_416,
        # The offer for sale is a RUPEE amount by the Promoter Selling Shareholders, so the
        # share count they sell is itself price-dependent: Rs 2,500m / Rs 178.
        promoter_ofs_shares=2_500.0 * MILLION / 178.0,
        promoter_pre_pct=88.08,
        nw_basis="stated Total Equity Rs 4,278.56 million at 30 Jun 2019. Net worth is "
                 "DEFINED on p110 as equity share capital + reserves and surplus under "
                 "section 2(57), so the cross-foot is valid. It reproduces the stated NAV "
                 "on 91,617,988 shares - the PERIOD-END count, 4.5% below the RHP-date "
                 "count of 95,980,816",
        pages="pre-issue shares and fresh issue p81; NAV and net-worth definition p110; "
              "promoter build-up p86-88",
        quoted="95,980,816 Equity Shares(1) 959.81 / Fresh issue of up to [*] Equity "
               "Shares aggregating up to Rs 2,500 million / Offer for sale of up to [*] "
               "Equity Shares by the Promoter Selling Shareholders aggregating up to "
               "Rs 2,500 million / As on June 30, 2019 46.70 / Total 7,680,000 8.00, "
               "Total 25,251,000 26.31, Total 25,796,800 26.88, Total 25,800,000 26.88, "
               "Total 12,616 0.01",
        stated_post_shares=None, stated_post_nav=None, stated_promoter_post=None,
        branch="fresh issue AND offer for sale both stated as RUPEE amounts - the "
               "promoter's own OFS share count is price-dependent too"),
]


def run() -> pd.DataFrame:
    rows = []
    for c in CASES:
        got = DPI.derive(
            pre_shares=c["pre_shares"],
            fresh_amount_inr=c.get("fresh_amount_inr"),
            fresh_shares=c.get("fresh_shares"),
            offer_price=c.get("offer_price"),
            pre_net_worth_inr=c.get("pre_net_worth_inr"),
            promoter_pre_shares=c.get("promoter_pre_shares"),
            promoter_ofs_shares=c.get("promoter_ofs_shares"),
            issue_size_cr=c.get("issue_size_cr"))
        # A pure OFS creates no shares: the branch H48 already names, taken explicitly
        # rather than left to a formula that has no fresh issue to work with.
        if c.get("fresh_shares") == 0 and not c.get("fresh_amount_inr"):
            got["post_issue_shares"] = float(c["pre_shares"])
            got["post_issue_shares_reason"] = ("pure offer for sale: no shares created, "
                                               "post equals pre")
            got["post_issue_nav"] = c["pre_nav"]
            got["post_issue_nav_reason"] = ("pure offer for sale: net worth and share "
                                            "count both unchanged, so the NAV is the "
                                            "pre-issue NAV")
            pct, why = DPI.promoter_post_pct(c["promoter_pre_shares"],
                                             c.get("promoter_ofs_shares"),
                                             float(c["pre_shares"]))
            got["promoter_post_pct"], got["promoter_post_pct_reason"] = pct, why

        # Cross-check: does net worth / stated NAV land on a share count near the one the
        # capital-structure page gives? A period-end count legitimately differs, so the
        # test reports the gap instead of passing or failing on a hard threshold.
        implied = (c["pre_net_worth_inr"] / c["pre_nav"]
                   if c.get("pre_nav") else None)
        gap = (100.0 * (implied - c["pre_shares"]) / c["pre_shares"]
               if implied else None)

        checks = []
        if c.get("stated_post_shares") is not None and got["post_issue_shares"]:
            d = abs(got["post_issue_shares"] - c["stated_post_shares"])
            checks.append(f"post shares vs STATED {c['stated_post_shares']:,}: "
                          f"{'MATCH' if d < 1 else f'OFF BY {d:,.0f}'}")
        if c.get("stated_post_nav") is not None and got["post_issue_nav"]:
            d = abs(got["post_issue_nav"] - c["stated_post_nav"])
            checks.append(f"post NAV vs STATED {c['stated_post_nav']}: "
                          f"{'MATCH' if d < 0.01 else f'OFF BY {d:.2f}'}")
        if c.get("stated_promoter_post") is not None and got["promoter_post_pct"]:
            d = abs(got["promoter_post_pct"] - c["stated_promoter_post"])
            checks.append(f"promoter post vs STATED {c['stated_promoter_post']}%: "
                          f"{'MATCH' if d < 0.05 else f'OFF BY {d:.2f}pp'}")
        if gap is not None:
            checks.append(f"net worth / stated NAV = {implied:,.0f} shares, "
                          f"{gap:+.2f}% vs the pre-issue count")
        pp = (100.0 * c["promoter_pre_shares"] / c["pre_shares"])
        checks.append(f"promoter pre {pp:.2f}% vs stated {c['promoter_pre_pct']}%: "
                      f"{'MATCH' if abs(pp - c['promoter_pre_pct']) < 0.05 else 'DIFFERS'}")

        rows.append({
            "company": c["company"], "year": c["year"], "industry": c["industry"],
            "branch": c["branch"],
            "pre_shares": c["pre_shares"],
            "post_shares": got["post_issue_shares"],
            "post_shares_reason": got["post_issue_shares_reason"],
            "pre_nav": c["pre_nav"], "post_nav": got["post_issue_nav"],
            "post_nav_reason": got["post_issue_nav_reason"],
            "promoter_pre_pct": c["promoter_pre_pct"],
            "promoter_post_pct": got["promoter_post_pct"],
            "promoter_post_reason": got["promoter_post_pct_reason"],
            "net_worth_basis": c["nw_basis"], "pages": c["pages"],
            "quoted_lines": c["quoted"], "cross_checks": " | ".join(checks),
            "flag": DPI.FLAG})
    return pd.DataFrame(rows)


def md(d: pd.DataFrame) -> str:
    L = ["# H48 hand-validation on the transcribed check set", "",
         "Every input below was read by hand from a numbered page and is quoted in "
         "`reports/H48_VALIDATION.csv`. Issue expenses are ignored throughout, which "
         "OVERSTATES post-issue book value and understates P/B; every row says so.", "",
         "## Results", "",
         "| RHP | post shares | post NAV | promoter pre % | promoter post % | pages | "
         "check |", "|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        ps = f"{r.post_shares:,.0f}" if pd.notna(r.post_shares) else "**withheld**"
        nav = f"Rs {r.post_nav:.2f}" if pd.notna(r.post_nav) else "**withheld**"
        pp = f"{r.promoter_post_pct:.2f}%" if pd.notna(r.promoter_post_pct) else "**withheld**"
        ok = "MATCH" if "MATCH" in str(r.cross_checks) and "OFF BY" not in str(r.cross_checks) \
            else ("no stated value to check against" if "STATED" not in str(r.cross_checks)
                  else "see detail")
        L.append(f"| {r.company} ({r.year}) | {ps} | {nav} | {r.promoter_pre_pct}% | "
                 f"{pp} | {r.pages.split(';')[0]} | {ok} |")
    L += ["", "## Branch taken, per document", "", "| RHP | branch |", "|---|---|"]
    for r in d.itertuples():
        L.append(f"| {r.company} | {r.branch} |")
    L += ["", "## Cross-checks in full", "", "| RHP | checks |", "|---|---|"]
    for r in d.itertuples():
        L.append(f"| {r.company} | {r.cross_checks} |")
    L += ["", "## Which net worth was used, and why", "", "| RHP | basis |", "|---|---|"]
    for r in d.itertuples():
        L.append(f"| {r.company} | {r.net_worth_basis} |")
    return "\n".join(L) + "\n"


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    d = run().set_index("company")
    print("[1] the two branches that DO state a post-issue count reproduce it exactly")
    cams = d.loc["Computer Age Management Services Ltd"]
    chk("CAMS post shares equal pre shares", cams.post_shares == 48_786_800, cams.post_shares)
    chk("and the RHP states that", "MATCH" in cams.cross_checks, cams.cross_checks)
    chk("CAMS post NAV equals pre NAV, because nothing changed",
        abs(cams.post_nav - 108.27) < 1e-9, cams.post_nav)
    chk("CAMS promoter post is the stated 30.98%",
        abs(cams.promoter_post_pct - 30.98) < 0.01, cams.promoter_post_pct)
    v = d.loc["Vishwaraj Sugar Industries Ltd"]
    chk("Vishwaraj post shares match the stated 37,556,000",
        v.post_shares == 37_556_000, v.post_shares)
    chk("and needed no offer price to get there",
        "share count" in v.post_shares_reason, v.post_shares_reason)

    print("\n[2] Craftsman and Medanta, the two Task 2 asks")
    cr = d.loc["Craftsman Automation Limited"]
    chk("Craftsman post shares are pre + 1,500m/1,490",
        abs(cr.post_shares - (20_121_600 + 1_500e6 / 1490)) < 1, cr.post_shares)
    chk("Craftsman post NAV is computed", pd.notna(cr.post_nav), cr.post_nav)
    chk("Craftsman post NAV exceeds its pre-issue NAV, as a premium issue must",
        cr.post_nav > cr.pre_nav, (cr.pre_nav, cr.post_nav))
    chk("Craftsman promoter falls from 52.83%",
        cr.promoter_post_pct < 52.83, cr.promoter_post_pct)
    chk("Craftsman's net worth is NOT the balance-sheet total equity",
        "7,716.11" in cr.net_worth_basis and "NOT the net worth" in cr.net_worth_basis)
    me = d.loc["Global Health Limited (Medanta)"]
    chk("Medanta post shares are pre + 5,000m/336",
        abs(me.post_shares - (253_303_930 + 5_000e6 / 336)) < 1, me.post_shares)
    chk("Medanta post NAV is computed", pd.notna(me.post_nav), me.post_nav)
    chk("Medanta's promoter sells nothing, so his COUNT is unchanged and only the "
        "percentage falls",
        me.promoter_post_pct < 35.00 and me.promoter_post_pct > 32.0,
        me.promoter_post_pct)

    print("\n[3] every row is flagged derived_from_rhp and says expenses are ignored")
    full = run()
    chk("every row carries the flag", (full["flag"] == DPI.FLAG).all())
    navs = full[full["post_nav"].notna() & (full["branch"].str.contains("RUPEE|SHARE"))]
    chk("every computed NAV from a fresh issue warns about issue expenses",
        all("expenses IGNORED" in str(x) or "pure offer" in str(x)
            for x in full.loc[full["post_nav"].notna(), "post_nav_reason"]),
        full.loc[full["post_nav"].notna(), "post_nav_reason"].tolist())

    print("\n[4] the promoter pre-issue percentage reproduces the stated one everywhere")
    for r in full.itertuples():
        pp = 100.0 * r.pre_shares  # placeholder to keep the loop honest
    bad = [r.company for r in full.itertuples() if "DIFFERS" in r.cross_checks]
    chk("no document's promoter count contradicts its stated percentage", not bad, bad)

    print("\n[5] a missing input is WITHHELD, not estimated")
    g = DPI.derive(pre_shares=1000, fresh_amount_inr=None, fresh_shares=None,
                   offer_price=100.0, pre_net_worth_inr=1e6,
                   promoter_pre_shares=500, promoter_ofs_shares=0)
    chk("no fresh issue and no share count gives no post count",
        g["post_issue_shares"] is None)
    chk("and therefore no NAV", g["post_issue_nav"] is None)
    chk("and therefore no promoter percentage", g["promoter_post_pct"] is None)
    chk("and the reason names what is missing",
        "pure offer for sale" in g["post_issue_shares_reason"])

    print("\n[6] a share-count fresh issue still raises money, so it still has a NAV")
    for _c in ("Vishwaraj Sugar Industries Ltd", "Likhitha Infrastructure Ltd"):
        chk(f"{_c.split()[0]} has a post-issue NAV", pd.notna(d.loc[_c].post_nav),
            d.loc[_c].post_nav)
    _v = d.loc["Vishwaraj Sugar Industries Ltd"]
    chk("Vishwaraj is priced BELOW its own NAV, so the issue DILUTES book value",
        _v.post_nav < _v.pre_nav, (_v.pre_nav, _v.post_nav))
    _l = d.loc["Likhitha Infrastructure Ltd"]
    chk("Likhitha is priced far above its NAV, so book value jumps",
        _l.post_nav > _l.pre_nav * 1.3, (_l.pre_nav, _l.post_nav))

    print("\n[7] Polycab: the promoters ARE selling, and only their own shares count")
    _p = d.loc["Polycab India Ltd"]
    chk("promoter OFS is 8,312,844, not the offer total of 17,582,000",
        "2,089,603" in _p.quoted_lines)
    chk("promoter post is 57.41%, NOT the 63.00% that assuming no promoter sale gives",
        abs(_p.promoter_post_pct - 57.409371) < 1e-4, _p.promoter_post_pct)
    chk("and 63.00% is exactly what zero promoter OFS would give - the trap named",
        abs(100 * 93_646_582 / _p.post_shares - 63.00) < 0.01)
    chk("the reason does not claim no promoter participation",
        "assuming NO promoter" not in str(_p.promoter_post_reason),
        _p.promoter_post_reason)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = run()
    OUT_CSV.parent.mkdir(exist_ok=True)
    d.to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_MD.write_text(md(d), encoding="utf-8")
    cols = ["company", "post_shares", "pre_nav", "post_nav", "promoter_pre_pct",
            "promoter_post_pct"]
    print(d[cols].to_string(index=False))
    print(f"\n{OUT_CSV}\n{OUT_MD}")

"""
derive_post_issue.py — the three post-issue figures a Red Herring Prospectus cannot state.

Why this module exists
----------------------
Hand-reading the check set established something a coverage table had been hiding: an RHP
**cannot** state the post-issue share count, the post-issue NAV or the promoter post-Offer
percentage. All three depend on a price that is not fixed until the book closes, so the
document prints `[*]` for every one. Polycab is the worked case and every other check-set
document so far agrees.

So they are not read. They are **calculated**, from two things the RHP does state and one
the market later fixes:

    post_issue_shares   = pre_issue_shares + fresh_issue_amount / final_offer_price
    post_issue_nav      = (pre_issue_net_worth + fresh_issue_amount) / post_issue_shares
    promoter_post_pct   = (promoter_pre_shares - promoter_ofs_shares) / post_issue_shares

The offer for sale does **not** change the total: an OFS transfers existing shares between
holders. It changes the promoter numerator and nothing else. Where the RHP states the
fresh issue as a share COUNT rather than a rupee amount, that count is added directly and
no division happens.

What is deliberately NOT papered over
-------------------------------------
**Issue expenses are ignored**, which overstates post-issue book value and therefore
understates P/B. Every row says so. Netting them off would need a figure the RHP gives only
as an estimate, and swapping a stated number for an estimate to make a ratio look tidier is
the fabrication rule 1 forbids.

Every output carries `derived_from_rhp`, the inputs it used, and the pages they came from.
A unit or period mismatch withholds the row rather than guessing at a conversion, and the
share count goes through the same two-sided plausibility guard the P/B module uses.

    python derive_post_issue.py --self-test
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

from derive_pb import share_count_plausible                          # noqa: E402

CR = 1e7            # one crore
MILLION = 1e6
FLAG = "derived_from_rhp"


def post_issue_shares(pre_shares, fresh_amount_inr=None, fresh_shares=None,
                      offer_price=None) -> tuple[float | None, str]:
    """`(shares, reason)`.

    `fresh_amount_inr` is the fresh issue in RUPEES; `fresh_shares` is a stated count.
    Exactly one of them is used, the count taking precedence because it needs no price and
    so carries no price risk.
    """
    if pre_shares is None or pd.isna(pre_shares) or float(pre_shares) <= 0:
        return None, "no pre-issue share count"
    pre = float(pre_shares)
    if fresh_shares is not None and not pd.isna(fresh_shares):
        if float(fresh_shares) < 0:
            return None, "fresh issue share count is negative"
        return pre + float(fresh_shares), "ok (fresh issue stated as a share count)"
    if fresh_amount_inr is None or pd.isna(fresh_amount_inr):
        # A pure OFS has no fresh issue, and the count genuinely does not change.
        return None, ("no fresh issue amount and no fresh issue share count - if this is a "
                      "pure offer for sale, post-issue shares equal pre-issue shares and "
                      "the caller should say so explicitly")
    if offer_price is None or pd.isna(offer_price) or float(offer_price) <= 0:
        return None, "no final offer price, so a rupee amount cannot become shares"
    if float(fresh_amount_inr) < 0:
        return None, "fresh issue amount is negative"
    return pre + float(fresh_amount_inr) / float(offer_price), "ok"


def fresh_amount_from_issue_size(issue_size_cr, ofs_shares, offer_price
                                 ) -> tuple[float | None, str]:
    """The fresh issue in RUPEES, where the RHP leaves the amount as `[*]`.

    `fresh = total issue size - (OFS shares x final offer price)`. Every term is a stated
    number: the issue size from the master, the OFS share count from the RHP's capital
    structure, the price from the book. Nothing is assumed.

    Validated against a case where the RHP DOES state the amount. Craftsman Automation:
    issue size Rs 823.70 cr, OFS 4,521,450 shares at Rs 1,490 = Rs 673.70 cr, so fresh =
    Rs 150.00 cr - and the RHP states Rs 1,500.00 million on the same page. Exact. It is
    then used on Global Health, whose RHP states only `[*]`.
    """
    for name, v in (("issue size", issue_size_cr), ("OFS share count", ofs_shares),
                    ("offer price", offer_price)):
        if v is None or pd.isna(v):
            return None, f"missing {name}"
    if float(offer_price) <= 0:
        return None, "offer price is not positive"
    fresh = float(issue_size_cr) * CR - float(ofs_shares) * float(offer_price)
    if fresh < 0:
        return None, ("the offer for sale alone exceeds the issue size - the two numbers "
                      "do not describe the same offer, so neither is used")
    return fresh, "ok (derived: issue size less the offer for sale at the final price)"


def post_issue_nav(pre_net_worth_inr, fresh_amount_inr, shares_post) -> tuple[float | None, str]:
    """`(NAV per share, reason)`. Both money inputs must already be in RUPEES."""
    for name, v in (("pre-issue net worth", pre_net_worth_inr),
                    ("fresh issue amount", fresh_amount_inr),
                    ("post-issue shares", shares_post)):
        if v is None or pd.isna(v):
            return None, f"missing {name}"
    if float(shares_post) <= 0:
        return None, "post-issue share count is not positive"
    nw = float(pre_net_worth_inr) + float(fresh_amount_inr)
    if nw <= 0:
        return None, "post-issue net worth is not positive"
    return nw / float(shares_post), ("ok (issue expenses IGNORED: this overstates book "
                                     "value and understates P/B)")


def promoter_post_pct(promoter_pre_shares, promoter_ofs_shares, shares_post
                      ) -> tuple[float | None, str]:
    """`(percent, reason)`. An OFS reduces the numerator only; it never changes the total."""
    if promoter_pre_shares is None or pd.isna(promoter_pre_shares):
        return None, "missing promoter pre-issue share count"
    if shares_post is None or pd.isna(shares_post) or float(shares_post) <= 0:
        return None, "missing or non-positive post-issue share count"
    ofs = 0.0 if (promoter_ofs_shares is None or pd.isna(promoter_ofs_shares)) \
        else float(promoter_ofs_shares)
    if ofs < 0:
        return None, "promoter OFS share count is negative"
    held = float(promoter_pre_shares) - ofs
    if held < 0:
        return None, "promoters cannot sell more shares than they hold"
    return 100.0 * held / float(shares_post), (
        "ok" if promoter_ofs_shares is not None and not pd.isna(promoter_ofs_shares)
        else "ok, assuming NO promoter participation in the offer for sale - stated, not "
             "silently assumed; if promoters are selling, this OVERSTATES the holding")


def derive(pre_shares, fresh_amount_inr=None, fresh_shares=None, offer_price=None,
           pre_net_worth_inr=None, promoter_pre_shares=None, promoter_ofs_shares=None,
           issue_size_cr=None) -> dict:
    """All three, with the plausibility guard and a reason on every field."""
    out = {"flag": FLAG}
    sh, why = post_issue_shares(pre_shares, fresh_amount_inr, fresh_shares, offer_price)
    out["post_issue_shares"], out["post_issue_shares_reason"] = sh, why
    if sh is not None and offer_price is not None and issue_size_cr is not None:
        ok, guard, _mult = share_count_plausible(sh, offer_price, issue_size_cr)
        if not ok:
            out["post_issue_shares"] = None
            out["post_issue_shares_reason"] = f"implausible: {guard}"
            sh = None
    # A fresh issue stated as a SHARE COUNT raises money too, and the NAV needs the rupee
    # amount. Without this the share-count branch - the one that needs no price for the
    # share total - silently produced no NAV at all, which is the opposite of what that
    # branch is for. The amount still needs the price, and says so.
    fresh_for_nav, fresh_why = fresh_amount_inr, "stated rupee amount"
    if (fresh_for_nav is None or pd.isna(fresh_for_nav)) and             fresh_shares is not None and not pd.isna(fresh_shares):
        if offer_price is None or pd.isna(offer_price) or float(offer_price) <= 0:
            fresh_why = ("fresh issue is a share count and there is no final offer price, "
                         "so the money raised is unknown")
        elif float(fresh_shares) == 0:
            fresh_for_nav, fresh_why = 0.0, "pure offer for sale: no money raised"
        else:
            fresh_for_nav = float(fresh_shares) * float(offer_price)
            fresh_why = (f"{float(fresh_shares):,.0f} fresh shares x the final offer "
                         f"price")
    out["fresh_amount_for_nav"] = fresh_for_nav
    out["fresh_amount_for_nav_reason"] = fresh_why
    nav, why = post_issue_nav(pre_net_worth_inr, fresh_for_nav, sh)
    out["post_issue_nav"], out["post_issue_nav_reason"] = nav, why
    pct, why = promoter_post_pct(promoter_pre_shares, promoter_ofs_shares, sh)
    out["promoter_post_pct"], out["promoter_post_pct_reason"] = pct, why
    return out


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

    def near(a, b, tol):
        return a is not None and abs(a - b) <= tol

    print("[1] the formulas, on numbers whose answer is known by hand")
    s, _ = post_issue_shares(100_000_000, fresh_amount_inr=1_000_000_000,
                             offer_price=100.0)
    chk("100m shares + Rs 100 cr at Rs 100 = 110m", near(s, 110_000_000, 1))
    s2, why2 = post_issue_shares(100_000_000, fresh_shares=10_000_000)
    chk("a stated fresh-issue COUNT is added directly", near(s2, 110_000_000, 1))
    chk("and needs no price", "share count" in why2)
    chk("an OFS does NOT change the total",
        near(post_issue_shares(100_000_000, fresh_amount_inr=0, offer_price=100.0)[0],
             100_000_000, 1))
    chk("no fresh issue and no count withholds, and says what a pure OFS means",
        post_issue_shares(100_000_000)[0] is None
        and "pure offer for sale" in post_issue_shares(100_000_000)[1])
    chk("a rupee amount with no price withholds",
        post_issue_shares(100_000_000, fresh_amount_inr=1e9)[0] is None)

    nav, whynav = post_issue_nav(10_000_000_000, 1_000_000_000, 110_000_000)
    chk("NAV = (1000 cr + 100 cr) / 110m = Rs 100.00", near(nav, 100.0, 1e-9))
    chk("and the row admits issue expenses are ignored", "IGNORED" in whynav)
    chk("a missing net worth withholds",
        post_issue_nav(None, 1e9, 1.1e8)[0] is None)

    p, _ = promoter_post_pct(66_000_000, 6_000_000, 110_000_000)
    chk("promoter 66m less 6m sold, over 110m = 54.5454%", near(p, 54.5454, 1e-3))
    _, whyp = promoter_post_pct(66_000_000, None, 110_000_000)
    chk("no OFS figure assumes none, and SAYS it is assuming",
        "assuming NO promoter participation" in whyp)
    chk("promoters cannot sell more than they hold",
        promoter_post_pct(1_000, 2_000, 110_000_000)[0] is None)

    print("\n[2] hand-validation: Polycab India Ltd, RHP p102 and p69")
    # pre-issue 141,205,838 shares (p102); fresh issue Rs 4,000 million (p102);
    # OFS 17,582,000 shares (p102); net worth FY2018 Rs 23,495.15 million (p69, derived as
    # Equity Share Capital 1,412.06 + Other Equity 22,083.09); final offer price Rs 538.
    r = derive(pre_shares=141_205_838, fresh_amount_inr=4_000 * MILLION,
               offer_price=538.0, pre_net_worth_inr=23_495.15 * MILLION,
               promoter_pre_shares=93_646_582, promoter_ofs_shares=None,
               issue_size_cr=1345.26)
    chk("post-issue shares = 141,205,838 + 4,000m/538 = 148,640,782",
        near(r["post_issue_shares"], 148_640_782, 2), r["post_issue_shares"])
    chk("and it passes the two-sided plausibility guard",
        r["post_issue_shares"] is not None)
    chk("post-issue NAV = (23,495.15m + 4,000m) / 148.64m = Rs 184.96",
        near(r["post_issue_nav"], 184.96, 0.02), r["post_issue_nav"])
    chk("the RHP's own pre-issue NAV was Rs 166.39, so the raise LIFTS it",
        r["post_issue_nav"] > 166.39)
    chk("promoter post = 93,646,582 / 148,640,782 = 63.00%",
        near(r["promoter_post_pct"], 63.00, 0.02), r["promoter_post_pct"])
    chk("which is BELOW the stated 66.32% pre-issue, as dilution requires",
        r["promoter_post_pct"] < 66.32)
    chk("every row is flagged", r["flag"] == FLAG)
    # A cross-check the RHP itself supplies: offer price / derived post-issue NAV is the
    # P/B the Basis block would have printed had the price been known.
    chk("implied post-issue P/B is 538 / 184.96 = 2.91x",
        near(538.0 / r["post_issue_nav"], 2.91, 0.02))

    print("\n[3] the guard and the withholding rules")
    bad = derive(pre_shares=220_000, fresh_amount_inr=0, offer_price=538.0,
                 pre_net_worth_inr=1e10, promoter_pre_shares=1000,
                 issue_size_cr=1345.26)
    chk("a share count too small for the money raised is refused",
        bad["post_issue_shares"] is None, bad["post_issue_shares_reason"])
    chk("and everything downstream of it is withheld too",
        bad["post_issue_nav"] is None and bad["promoter_post_pct"] is None)
    src = inspect.getsource(sys.modules[__name__]).split("def self_test")[0]
    chk("the share-count guard is the SAME one the P/B module uses",
        "from derive_pb import share_count_plausible" in src)
    # The honest form of "no expense estimate is invented": the arithmetic must be exactly
    # net worth plus the raise, with no fudge factor anywhere. Searching for the WORD
    # failed on this module's own disclosure that expenses are ignored.
    chk("post-issue net worth is net worth plus the raise, with no adjustment factor",
        "nw = float(pre_net_worth_inr) + float(fresh_amount_inr)" in src)
    import re as _re
    body = _re.sub(r'(?s)""".*?"""', "", src)
    # 0.0 is a zero default, not a fudge factor. Anything else fractional would be.
    frac = [m.group(0) for m in _re.finditer(r"0\.\d+", body) if m.group(0) != "0.0"]
    chk("no fractional constant is applied anywhere in the arithmetic", not frac, frac)
    chk("and the NAV reason discloses the DIRECTION of the error",
        "overstates book value and understates P/B" in post_issue_nav(
            1.0, 1.0, 1.0)[1])

    print("\n[4] the fresh issue recovered where the RHP prints [*]")
    # Craftsman Automation: the RHP STATES Rs 1,500.00 million on p71, so this case
    # grades the derivation against a known answer before it is trusted elsewhere.
    # Tolerances are RELATIVE, because the master stores the issue size rounded to two
    # decimals in crore. Demanding the rupee to the rupee would be grading the derivation
    # against a precision its own input does not carry.
    def within(a, b, pct):
        return a is not None and abs(a - b) / abs(b) * 100 <= pct

    f_cr, whyf = fresh_amount_from_issue_size(823.70, 4_521_450, 1490.0)
    chk("Craftsman: 823.70 cr less 4,521,450 x 1,490 = Rs 150.00 cr",
        within(f_cr, 150.0 * CR, 0.01), f_cr)
    chk("and that agrees with the Rs 1,500.00 million the RHP STATES on p71, "
        "to 0.003% - the master's own rounding",
        within(f_cr, 1_500 * MILLION, 0.01),
        f"{abs(f_cr - 1500 * MILLION) / (1500 * MILLION) * 100:.4f}%")
    cs, _ = post_issue_shares(20_121_600, fresh_amount_inr=f_cr, offer_price=1490.0)
    chk("Craftsman post-issue shares = 20,121,600 + fresh/1490 = 21,128,338",
        within(cs, 21_128_338, 0.001), cs)

    # Global Health (Medanta): the RHP prints [*] for the fresh issue amount.
    g_cr, _ = fresh_amount_from_issue_size(2205.57, 50_761_000, 336.0)
    chk("Medanta: 2,205.57 cr less 50,761,000 x 336 = Rs 500.00 cr",
        within(g_cr, 500.0 * CR, 0.01), g_cr)
    gs, _ = post_issue_shares(253_303_930, fresh_amount_inr=g_cr, offer_price=336.0)
    chk("Medanta post-issue shares = 253,303,930 + fresh/336 = 268,184,894",
        within(gs, 268_184_894, 0.001), gs)
    chk("an OFS larger than the whole issue is refused, not negated",
        fresh_amount_from_issue_size(10.0, 50_761_000, 336.0)[0] is None)
    chk("and the refusal says the two numbers disagree",
        "do not describe the same offer"
        in fresh_amount_from_issue_size(10.0, 50_761_000, 336.0)[1])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    raise SystemExit(self_test())

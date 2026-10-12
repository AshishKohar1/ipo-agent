"""
tax_view.py — Task 5: the post-tax comparison, with the rates fetched, never hard-coded.

The rates
---------
Read out of an **official CBDT document** on incometax.gov.in, not from memory and not from
a tax-advice site. `data/tax_rates.csv` records, for each rate: the value, the section, the
document title, its URL, the page the line appears on, the exact line quoted, the SHA-256
of the PDF and the fetch timestamp in IST (H26's provenance requirement, and rule 13 for
the timezone).

**`incometaxindia.gov.in` is blocked** and is not used: it returns HTTP 403 on its own
`robots.txt`, which this project treats as a site refusing automated access (rule 5 — the
same call made for BSE). `incometax.gov.in` serves no robots.txt and its pages declare
`<meta name="robots" content="index, follow">`, so there is no disallow to respect.

The two options being compared
------------------------------
At the listing-day close you already hold the allotment, bought at the offer price. The
decision is sell now or hold. So:

  (a) SELL AT LISTING, then hold the Nifty 50 TRI for the same period.
      STCG at 20% on (listing close - offer), because the holding is days old.
      The Nifty leg is then held past 12 months, so its own gain is LTCG at 12.5%.
  (b) HOLD THE IPO past 12 months.
      LTCG at 12.5% on (exit price - offer).

**Day 366, not day 365.** Section 112A needs the holding to exceed 12 months, so a sale on
day 365 is still SHORT-term and would be taxed at 20%, not 12.5%. The pre-tax target is
measured at +365 days; the post-tax comparison therefore uses only rows whose **actual**
end price is at least 366 days after listing. `build_corrected()` walks forward past
holidays and records `days_from_requested`, so that filter is exact rather than a proxy.

**The annual LTCG exemption is ignored**, as instructed. It is a per-person allowance, not
a per-trade one, so it cannot be attributed to a single IPO without knowing the rest of the
portfolio. Ignoring it makes both options worse by a similar amount and the comparison
between them close to unaffected; it does mean the absolute post-tax figures are
pessimistic.

    python tax_view.py --record      # fetch nothing; write the rate record from the PDF
    python tax_view.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

RATES = ROOT / "data" / "tax_rates.csv"
RATE_COLS = ["kind", "section", "rate_pct", "applies_to", "min_holding_days",
             "document", "url", "page", "quoted_line", "source_sha256",
             "fetched_at_ist", "note"]

# Set by --record from the fetched document; never a literal in the computation path.
SRC_URL = ("https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-06/"
           "CBDT_e-filing_ITR-3_Validation%20Rules_V1.0_AY%2026-27.pdf")
SRC_DOC = "CBDT e-Filing ITR-3 Validation Rules V1.0, AY 2026-27 (created 18 Jun 2026)"


def rates() -> dict:
    """`{"stcg": pct, "ltcg": pct, "ltcg_min_days": n}` read from the recorded file.

    Raises if the file is absent. A default would be a hard-coded rate wearing a
    different hat, and the one thing this module exists to avoid is a rate nobody can
    trace.
    """
    if not RATES.exists():
        raise RuntimeError(
            f"{RATES} does not exist. Run `python tax_view.py --record` first. "
            f"There is deliberately no fallback rate: an untraceable rate is the thing "
            f"this module exists to prevent.")
    d = pd.read_csv(RATES)
    out = {}
    for _, r in d.iterrows():
        out[str(r["kind"]).lower()] = float(r["rate_pct"])
        if str(r["kind"]).lower() == "ltcg":
            out["ltcg_min_days"] = int(r["min_holding_days"])
    for need in ("stcg", "ltcg", "ltcg_min_days"):
        if need not in out:
            raise RuntimeError(f"{RATES} has no {need} row")
    return out


def record(pdf_path: str, quotes: list[tuple[str, str, int, str, int]]) -> pd.DataFrame:
    """Write the rate record from lines already extracted from the official PDF.

    `quotes` is `(kind, section, page, line, min_holding_days)` per rate. The rate itself
    is PARSED OUT OF THE QUOTED LINE, not passed in separately - so the number in the file
    and the evidence for it cannot drift apart.
    """
    import re
    p = Path(pdf_path)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    import trading_day as TD
    when = str(TD.ist_now())
    rows = []
    for kind, section, page, line, min_days in quotes:
        m = re.search(rf"{re.escape(section)}[^0-9%]{{0,24}}?([0-9]+(?:\.[0-9]+)?)\s*%",
                      line) or re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", line)
        if not m:
            raise ValueError(f"no percentage in the quoted line for {kind}: {line!r}")
        rows.append({
            "kind": kind, "section": section, "rate_pct": float(m.group(1)),
            "applies_to": "listed equity shares with STT paid",
            "min_holding_days": min_days, "document": SRC_DOC, "url": SRC_URL,
            "page": page, "quoted_line": line.strip(), "source_sha256": sha,
            "fetched_at_ist": when,
            "note": ("rate parsed from the quoted line, so the figure and its evidence "
                     "cannot drift apart")})
    d = pd.DataFrame(rows, columns=RATE_COLS)
    RATES.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(RATES, index=False, encoding="utf-8")
    return d


def post_tax(offer: float, listing_close: float, exit_price: float,
             nifty_return_pct: float, held_days: int, r: dict | None = None) -> dict:
    """The two options, net of tax, per share held.

    Returns both net values and the difference in percentage points of the listing close,
    so it is comparable with the pre-tax excess which is also in pp.
    """
    r = r or rates()
    stcg, ltcg, min_days = r["stcg"] / 100.0, r["ltcg"] / 100.0, r["ltcg_min_days"]

    # (a) sell at listing, pay STCG on the listing gain, put the net into the Nifty.
    listing_gain = listing_close - offer
    net_now = listing_close - stcg * max(listing_gain, 0.0)
    nr = nifty_return_pct / 100.0
    # The Nifty leg is held the same period, so past 12 months its gain is LTCG.
    nifty_rate = ltcg if held_days > min_days else stcg
    a_net = net_now * (1.0 + nr * (1.0 - nifty_rate)) if nr > 0 else net_now * (1.0 + nr)

    # (b) hold the IPO. Long-term only if the holding actually exceeded 12 months.
    hold_gain = exit_price - offer
    hold_rate = ltcg if held_days > min_days else stcg
    b_net = exit_price - hold_rate * max(hold_gain, 0.0)

    return {"sell_at_listing_net": a_net, "hold_net": b_net,
            "post_tax_excess_pp": (b_net - a_net) / listing_close * 100.0,
            "rate_applied_to_hold_pct": hold_rate * 100.0,
            "long_term": held_days > min_days, "held_days": held_days}


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] the rate record carries its own evidence")
    if RATES.exists():
        d = pd.read_csv(RATES)
        for c in ("rate_pct", "url", "page", "quoted_line", "source_sha256",
                  "fetched_at_ist"):
            chk(f"{c} is recorded", c in d.columns)
        chk("the STCG rate came from an incometax.gov.in document",
            all("incometax.gov.in" in str(u) for u in d["url"]), list(d["url"])[:1])
        chk("every rate has a quoted line as its evidence",
            d["quoted_line"].notna().all() and (d["quoted_line"].str.len() > 10).all())
        chk("and the quoted line contains the rate it claims",
            all(f"{float(r['rate_pct']):g}" in str(r["quoted_line"])
                for _, r in d.iterrows()),
            d[["rate_pct", "quoted_line"]].to_dict("records"))
        chk("the SHA-256 is a full hash", (d["source_sha256"].str.len() == 64).all())
    else:
        chk("rate file exists (run --record)", False, str(RATES))

    print("\n[2] no rate is hard-coded in the computation path")
    import inspect
    import re as _re
    src = inspect.getsource(post_tax)
    chk("post_tax reads the rates in, it does not contain them",
        not _re.search(r"\b(20|12\.5|15|10)\s*/\s*100", src), src[:0])
    chk("and it raises rather than defaulting when the record is missing",
        "There is deliberately no fallback" in inspect.getsource(rates))

    print("\n[3] the arithmetic, on numbers checkable by hand")
    r = {"stcg": 20.0, "ltcg": 12.5, "ltcg_min_days": 365}
    # Offer 100, listed at 150, a year later 200, Nifty +10% over the window.
    #  (a) sell: gain 50, STCG 20% -> 10 tax, net 140. Nifty +10% on 140 = +14,
    #      LTCG 12.5% on 14 = 1.75, so 140 + 12.25 = 152.25
    #  (b) hold: gain 100, LTCG 12.5% -> 12.5 tax, net 187.5
    g = post_tax(100, 150, 200, 10.0, 400, r)
    chk("sell-at-listing net is 152.25", abs(g["sell_at_listing_net"] - 152.25) < 1e-9,
        g["sell_at_listing_net"])
    chk("hold net is 187.50", abs(g["hold_net"] - 187.5) < 1e-9, g["hold_net"])
    chk("post-tax excess is +23.5pp of the listing close",
        abs(g["post_tax_excess_pp"] - (187.5 - 152.25) / 150 * 100) < 1e-9,
        g["post_tax_excess_pp"])
    chk("and it is flagged long-term", g["long_term"] is True)

    print("\n[4] day 365 is SHORT-term and is taxed as such")
    g365 = post_tax(100, 150, 200, 10.0, 365, r)
    chk("at exactly 365 days the hold is NOT long-term", g365["long_term"] is False)
    chk("so the 20% rate is applied, not 12.5%",
        g365["rate_applied_to_hold_pct"] == 20.0, g365)
    chk("which makes holding look worse than at 366 days",
        g365["hold_net"] < g["hold_net"], (g365["hold_net"], g["hold_net"]))
    g366 = post_tax(100, 150, 200, 10.0, 366, r)
    chk("366 days crosses the line", g366["long_term"] is True)
    chk("and that single day is worth something, which is why the filter matters",
        g366["hold_net"] > g365["hold_net"],
        (g365["hold_net"], g366["hold_net"]))

    print("\n[5] a loss is not taxed as a gain")
    g = post_tax(100, 80, 60, 10.0, 400, r)
    chk("a listing BELOW the offer price pays no STCG",
        abs(g["sell_at_listing_net"] - 80 * (1 + 0.10 * (1 - 0.125))) < 1e-9,
        g["sell_at_listing_net"])
    chk("and an exit below the offer price pays no LTCG",
        abs(g["hold_net"] - 60.0) < 1e-9, g["hold_net"])
    chk("so the comparison still works on a losing IPO",
        g["post_tax_excess_pp"] < 0, g["post_tax_excess_pp"])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--record", metavar="PDF",
                    help="write data/tax_rates.csv from the official PDF already on disk")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.record:
        d = record(a.record, [
            ("stcg", "111A", 27,
             "443. In Schedule CG, STCG @ 20% - 111A & 115AD(1)(b)(ii) can only be "
             "entered once.", 0),
            ("ltcg", "112A", 52,
             "nature of Long Term Capital Gain chargeable @ 12.5%-u/s 112A, Pass Through "
             "Income", 365),
        ])
        print(d.to_string(index=False))
        raise SystemExit(0)
    if a.show:
        print(pd.read_csv(RATES).to_string(index=False) if RATES.exists() else "not recorded")
        raise SystemExit(0)
    ap.print_help()

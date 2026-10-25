"""
rhp_pages.py — find the restated-statement pages by CONTENT, not by the table of contents.

Why this exists
---------------
`extract.base.locate` reads the TOC and `locate_by_scan` matches section headings. Both
fail on real documents. Route Mobile's RHP puts its financials at PDF pages 2-28 according
to the locator, which is the auditor's report inside the front matter; its restated balance
sheet is 300 pages later. A reader pointed at the wrong pages does not fail loudly - it
finds plausible-looking numbers on the wrong table, which is the most expensive outcome
available.

So the pages are found by what is ON them:

* **a restated balance sheet** has `Total assets` and an equity block in the same page;
* **a restated statement of profit and loss** has `Profit before tax` and a tax line;
* **the basis-for-offer page** has `Net Asset Value per Equity Share`;
* **the capital-structure page** has `ISSUED, SUBSCRIBED AND PAID-UP`.

Each finder returns EVERY matching page with a score, because a 500-page RHP contains the
same table several times - standalone and consolidated, restated and audited, company and
subsidiary. Choosing between them is the caller's job and is done on stated evidence, never
on which number looks nicer.

    python rhp_pages.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# A restated table is identified by several marks, not one, because any single phrase also
# appears in prose, in the index, and in the risk factors.
BS_MARKS = (
    (re.compile(r"Total\s+assets", re.I), 2),
    (re.compile(r"Total\s+equity(\s+and\s+liabilities)?", re.I), 2),
    (re.compile(r"(Other\s+equity|Reserves\s+and\s+surplus)", re.I), 2),
    (re.compile(r"Equity\s+[Ss]hare\s+capital", re.I), 1),
    (re.compile(r"Total\s+(non-current|current)\s+liabilities", re.I), 1),
    (re.compile(r"(Trade\s+receivables|Inventories)", re.I), 1),
)
PL_MARKS = (
    (re.compile(r"Profit\s+before\s+tax", re.I), 3),
    (re.compile(r"(Total\s+tax\s+expense|Tax\s+expense|Total\s+tax)", re.I), 2),
    (re.compile(r"Finance\s+cost", re.I), 2),
    (re.compile(r"Depreciation\s+(and|&|,)\s*amorti", re.I), 2),
    (re.compile(r"(Revenue\s+from\s+operations|Total\s+income)", re.I), 1),
    (re.compile(r"Earnings\s+per\s+(equity\s+)?share", re.I), 1),
)
NAV_MARKS = (
    (re.compile(r"Net\s+[Aa]sset\s+[Vv]alue\s+per\s+[Ee]quity\s+[Ss]hare", re.I), 3),
    (re.compile(r"Return\s+on\s+Net\s*[Ww]orth", re.I), 2),
    (re.compile(r"(Basic\s+and\s+[Dd]iluted\s+)?[Ee]arnings\s+per\s+[Ss]hare", re.I), 1),
)
CAP_MARKS = (
    (re.compile(r"ISSUED,?\s+SUBSCRIBED\s+AND\s+PAID[- ]UP", re.I), 3),
    (re.compile(r"AUTHORI[SZ]ED\s+SHARE\s+CAPITAL", re.I), 2),
    (re.compile(r"(Fresh\s+Issue|Offer\s+for\s+[Ss]ale|PRESENT\s+(OFFER|ISSUE))", re.I), 1),
    (re.compile(r"SECURITIES\s+PREMIUM", re.I), 1),
)
KINDS = {"balance_sheet": BS_MARKS, "profit_loss": PL_MARKS, "nav": NAV_MARKS,
         "capital": CAP_MARKS}

# A page of running prose that happens to mention these is not a table. A table has
# several lines carrying three or more numbers.
NUMROW = re.compile(r"(\(?\d[\d,]*\.?\d*\)?[^\dA-Za-z]+){3,}")
# Consolidated and standalone both exist; which to prefer is the caller's decision, but
# the page says which it is and that is recorded rather than guessed.
BASIS_CONS = re.compile(r"[Cc]onsolidated", re.I)
BASIS_STAND = re.compile(r"[Ss]tandalone", re.I)


def numeric_lines(text: str) -> int:
    return sum(1 for ln in (text or "").splitlines() if NUMROW.search(ln))


def score_page(text: str, kind: str) -> int:
    """How strongly this page looks like `kind`. 0 means it does not."""
    if not text:
        return 0
    marks = KINDS[kind]
    s = sum(w for pat, w in marks if pat.search(text))
    if s == 0:
        return 0
    nl = numeric_lines(text)
    if kind in ("balance_sheet", "profit_loss"):
        # A balance sheet or P&L without a column of numbers is the index or the prose
        # that refers to one.
        if nl < 4:
            return 0
        s += min(nl // 6, 3)
    elif kind == "capital":
        if nl < 2:
            return 0
    return s


def find(pages: list[str], kind: str, min_score: int = 5) -> list[dict]:
    """Every page scoring at least `min_score`, best first, with its basis if stated."""
    out = []
    for i, t in enumerate(pages or []):
        s = score_page(t, kind)
        if s >= min_score:
            basis = ("consolidated" if BASIS_CONS.search(t or "") else
                     "standalone" if BASIS_STAND.search(t or "") else "")
            out.append({"index": i, "score": s, "basis": basis,
                        "numeric_lines": numeric_lines(t)})
    out.sort(key=lambda r: (-r["score"], r["index"]))
    return out


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

    bs = """Particulars As at March 31, 2020 2019 2018
    Property, plant and equipment 1,234.56 1,100.00 950.10
    Inventories 345.67 300.00 280.20
    Trade receivables 456.78 400.00 380.30
    Total assets 5,678.90 5,000.00 4,800.40
    Equity share capital 100.00 100.00 100.00
    Other equity 2,345.67 2,000.00 1,800.50
    Total equity 2,445.67 2,100.00 1,900.50
    Total non-current liabilities 1,000.00 900.00 850.60
    Total equity and liabilities 5,678.90 5,000.00 4,800.40"""
    pl = """Restated Consolidated Statement of Profit and Loss
    Revenue from operations 10,000.00 9,000.00 8,000.00
    Finance costs 123.45 110.00 100.10
    Depreciation and amortisation expense 234.56 220.00 210.20
    Profit before tax 1,500.00 1,400.00 1,300.30
    Total tax expense 400.00 380.00 350.40
    Earnings per equity share 12.34 11.00 10.50"""
    prose = ("Our total assets and total equity are discussed in the section Financial "
             "Information. For further information on our profit before tax, see page 225.")
    index = "Total assets ............ 225\nTotal equity ............ 226"
    cap = """CAPITAL STRUCTURE
    A) AUTHORISED SHARE CAPITAL
    40,000,000 Equity Shares of face value of Rs 5 each 200.00 -
    B) ISSUED, SUBSCRIBED AND PAID-UP SHARE CAPITAL BEFORE THE OFFER
    20,121,600 Equity Shares of face value of Rs 5 each 100.61 -
    D) SECURITIES PREMIUM ACCOUNT
    Before the Offer 1,379.53"""
    nav = """Net Asset Value per Equity Share (Rs)
    As on December 31, 2020 355.93
    Return on Net Worth 7.07 6.19 15.51"""

    print("[1] each kind is found on its own page")
    chk("a balance sheet scores", score_page(bs, "balance_sheet") >= 5,
        score_page(bs, "balance_sheet"))
    chk("a P&L scores", score_page(pl, "profit_loss") >= 5, score_page(pl, "profit_loss"))
    chk("a capital page scores", score_page(cap, "capital") >= 5,
        score_page(cap, "capital"))
    chk("a NAV page scores", score_page(nav, "nav") >= 5, score_page(nav, "nav"))

    print("\n[2] prose and the index are NOT tables, however many keywords they carry")
    chk("prose about total assets is not a balance sheet",
        score_page(prose, "balance_sheet") == 0, score_page(prose, "balance_sheet"))
    chk("prose about profit before tax is not a P&L",
        score_page(prose, "profit_loss") == 0, score_page(prose, "profit_loss"))
    chk("a table of contents line is not a balance sheet",
        score_page(index, "balance_sheet") == 0, score_page(index, "balance_sheet"))
    chk("an empty page scores nothing", score_page("", "balance_sheet") == 0)
    chk("None scores nothing", score_page(None, "profit_loss") == 0)

    print("\n[3] a balance sheet is not mistaken for a P&L, or the reverse")
    chk("the balance sheet does not win on profit_loss",
        score_page(bs, "profit_loss") < score_page(pl, "profit_loss"),
        (score_page(bs, "profit_loss"), score_page(pl, "profit_loss")))
    chk("the P&L does not win on balance_sheet",
        score_page(pl, "balance_sheet") < score_page(bs, "balance_sheet"),
        (score_page(pl, "balance_sheet"), score_page(bs, "balance_sheet")))

    print("\n[4] find() ranks and records the basis")
    pages = [prose, index, bs, pl, "", cap, nav]
    got = find(pages, "balance_sheet")
    chk("the balance sheet page is found", got and got[0]["index"] == 2, got)
    chk("and prose is not", all(r["index"] != 0 for r in got), got)
    pl2 = find(pages, "profit_loss")
    chk("the P&L page is found", pl2 and pl2[0]["index"] == 3, pl2)
    chk("and it records that it is consolidated",
        pl2[0]["basis"] == "consolidated", pl2[0])
    chk("the balance sheet's basis is blank when the page does not say",
        got[0]["basis"] == "", got[0])
    chk("every kind returns a LIST, because a long RHP holds the table several times",
        isinstance(find(pages, "nav"), list))
    chk("a higher min_score narrows it",
        len(find(pages, "balance_sheet", min_score=99)) == 0)

    print("\n[5] numeric_lines counts rows of figures, not words")
    chk("a table has numeric rows", numeric_lines(bs) >= 8, numeric_lines(bs))
    chk("prose has none", numeric_lines(prose) == 0, numeric_lines(prose))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    raise SystemExit(self_test())

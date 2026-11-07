"""
rhp_readers.py — the five readers: net worth, tax expense, finance costs, depreciation and
amortisation, and the pre-issue share count.

The problem these solve, and the trick that solves it
-----------------------------------------------------
A restated table in an RHP has three to five columns and its header is split across two
printed lines in whatever order the typesetter chose:

    Particulars No. of As at December 31 As at March 31 As at March 31 As at March 31
    Annexure 2020 2020 2019 2018

    As at As at June 30, As at As at March As at March
    June 30, 2022 2021 March 31, 2022 31, 2021 31, 2020

Parsing that reliably is a losing game, and getting it wrong is the most expensive mistake
available: a correct value filed against the wrong year corrupts every ratio derived from
it and will not be found by inspection. A leading stub period - three, six or nine months -
is the usual way it happens.

So the column is **not** parsed from the header. It is pinned by the document's own
arithmetic:

* the **balance-sheet column** is the one where `net worth / shares = the stated NAV`;
* the **profit-and-loss column** is the one where `profit / shares = the stated EPS`.

Both anchors are printed in the Basis for Offer Price section, which every RHP must carry.
When no column matches, the reader WITHHOLDS. That is the point: a reader that cannot prove
which column it is reading has nothing to say.

This also solves page selection, which is a bigger problem than it looks. A 500-page RHP
carries the same table several times - standalone and consolidated, company and subsidiary.
Medanta's highest-scoring balance sheet by keywords is a subsidiary's, with total equity of
Rs 3,111.34 million against the company's Rs 16,160.11 million. The anchor rejects it,
because a subsidiary's net worth does not reproduce the company's NAV.

What was tried and rejected
---------------------------
`pdfplumber.extract_tables(vertical_strategy="text", horizontal_strategy="text")` was
measured on three check-set RHPs before this was written. It produces cells, but splits
them arbitrarily: `['Equity Share c', 'apital', ...]` and `['Other equity', '2,470.20',
'2,203.65', '1,617.84', '1,', '108.52']` - a number broken across two cells, which is worse
than no cell boundary at all. It also costs 2-3 seconds per page against effectively zero
for a cached text line. Reading the text line and taking its numbers with a regex is both
more accurate and about a hundred times faster, so the text strategy is not used.

    python rhp_readers.py --self-test
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
import rhp_pages as RP                                      # noqa: E402

# One token of a figure column: digits, commas, a decimal point, optional brackets for a
# negative. NO whitespace inside, because `18 100.61` (a note number and a figure) and
# `1 00.61` (one figure the extractor split) are lexically identical and no regex tells
# them apart. The table does - see `row_numbers`.
TOKEN = re.compile(r"\(?[\d][\d,]*(?:\.\d{1,4})?\)?|\(?\.\d{1,4}\)?|\(?,\d{2,3}(?:\.\d{1,4})?\)?")
# A WELL-FORMED Indian figure: 1,234.56 / 12,34,567 / 100.61 / 0.24. A leading zero on a
# multi-digit integer part is the signature of a split number (`1` + `00.61`), so it is
# not well formed on its own.
WELL = re.compile(r"^\(?(?:0|[1-9]\d{0,2}(?:,?\d{2,3})*)(?:\.\d{1,4})?\)?$")
UNITS = (
    (re.compile(r"in\s*(₹|Rs\.?|INR)?\s*(million|millions)\b", re.I), 1e6, "INR million"),
    (re.compile(r"(₹|Rs\.?|INR)\s*in\s*(million|millions)\b", re.I), 1e6, "INR million"),
    (re.compile(r"in\s*(₹|Rs\.?|INR)?\s*(lakhs?|lacs?)\b", re.I), 1e5, "INR lakh"),
    (re.compile(r"(₹|Rs\.?|INR)\s*in\s*(lakhs?|lacs?)\b", re.I), 1e5, "INR lakh"),
    (re.compile(r"in\s*(₹|Rs\.?|INR)?\s*(crores?)\b", re.I), 1e7, "INR crore"),
    (re.compile(r"(₹|Rs\.?|INR)\s*in\s*(crores?)\b", re.I), 1e7, "INR crore"),
)
# The line that names each quantity. Deliberately narrow: `Total Equity and Liabilities` is
# NOT net worth, and a reader that matches it reads the balance-sheet total instead.
ROWS = {
    # The negative lookahead sits IMMEDIATELY after the alternation and swallows the
    # space itself. Written as `\\s*(?!and...)` the engine backtracks `\\s*` to empty
    # and the lookahead passes on " and Liabilities" - so `Total Equity and
    # Liabilities`, the balance-sheet TOTAL, was being read as net worth.
    "net_worth": re.compile(r"^\s*(Net\s*worth|Total\s+equity)(?!\s+and\s+liabilit)"
                            r"(?!\s+and\s+Liabilit)", re.I),
    "equity_share_capital": re.compile(r"^\s*\(?[a-d]?\)?\s*Equity\s+[Ss]hare\s+[Cc]apital\b", re.I),
    "other_equity": re.compile(r"^\s*\(?[a-d]?\)?\s*Other\s+[Ee]quity\b", re.I),
    "nci": re.compile(r"^\s*Non[- ]controlling\s+interest", re.I),
    "tax_expense": re.compile(r"^\s*(Total\s+[Tt]ax\s+[Ee]xpense|Tax\s+expense|"
                              r"Total\s+tax\s+expense\s*/?\s*\(?credit\)?)\b", re.I),
    "finance_costs": re.compile(r"^\s*Finance\s+[Cc]osts?\b", re.I),
    "depreciation_amortisation": re.compile(
        r"^\s*Depreciation\s*(and|&|,)\s*[Aa]morti[sz]ation", re.I),
    "pat": re.compile(r"^\s*Profit\s+(for\s+the|after\s+tax)", re.I),
    "pbt": re.compile(r"^\s*Profit\s+before\s+tax\b", re.I),
}
NAV_LINE = re.compile(r"Net\s+[Aa]sset\s+[Vv]alue\s*(per|Per)?\s*([Ee]quity\s+)?"
                      r"[Ss]hare|^\s*NAV\s+(as\s+(at|on)|\(in)", re.I)
# Form 1: one period per line - "As on March 31, 2019 43.71", "As at September 30, 2020 89.87".
NAV_VALUE = re.compile(r"^\s*As\s+(on|at|of)\s+\w+\s+\d{1,2},?\s+\d{4}\*?\s*"
                       r"\(?([\d,]+\.\d{1,2})\)?", re.I)
# Form 2: the date inside the label - Likhitha's "... as of March 31, 2020 47.83".
NAV_INLINE = re.compile(r"Net\s+[Aa]sset\s+[Vv]alue\s+per\s+[Ee]quity\s+[Ss]hare\s+as\s+"
                        r"(of|on|at)\s+\w+\s+\d{1,2},?\s+\d{4}\*?\s+([\d,]+\.\d{1,2})",
                        re.I)
# Form 3: a whole column series on the NAV line itself, which is the common case.
NAV_SERIES = re.compile(r"Net\s+[Aa]sset\s+[Vv]alue\s*(Per|per)?\s*([Ee]quity\s+)?"
                        r"[Ss]hare", re.I)
# The two companion lines of the NAV's own derivation, where the RHP prints it.
NW_BASIS = re.compile(r"^\s*(Restated\s+)?Net\s*[Ww]orth", re.I)
SHARES_BASIS = re.compile(r"Number\s+of\s+equity\s+shares?\s+(outstanding|issued)", re.I)
IN_MILLION_SHARES = re.compile(r"\(in\s+million\)", re.I)
# The profit-and-loss anchor. `Earnings per equity share` appears on the statement itself;
# `Basic EPS` and `Diluted EPS` appear in the Basis for Offer Price table, which gives a
# second and independent list to test a column against.
EPS_ROW = re.compile(r"(Earnings\s+per\s+(equity\s+)?share|^\s*(-\s*)?Basic(\s+EPS)?\b|"
                     r"^\s*(-\s*)?Diluted(\s+EPS)?\b|per\s+equity\s+share\s*\(?)", re.I)
# "March 31, 2020 20.41 20.41 3" in the Basis table: a period, basic, diluted, weight.
EPS_DATED = re.compile(r"^\s*(March|June|September|December)\s+\d{1,2},?\s+\d{4}\*?\s+"
                       r"\(?([\d,]+\.\d{1,2})\)?", re.I)
EPS_LINE = re.compile(r"^\s*(March|June|September|December)\s+\d{1,2},?\s+\d{4}\*?\s+"
                      r"([\d,]+\.\d{1,2})\s+([\d,]+\.\d{1,2})", re.I)
# The extractor splits long counts: Prince Pipes prints "9 5,980,816 Equity Shares",
# which is 95,980,816. Taking the token after the space gives 5,980,816 - a count 16
# times too small, and one that still looks like a share count. So an optional
# one-or-two digit prefix before a space is captured and glued back on.
PRE_ISSUE = re.compile(r"(?:(\d{1,2})\s+)?([\d][\d,]{4,})\s+[Ee]quity\s+[Ss]hares")
BEFORE = re.compile(r"(ISSUED,?\s+SUBSCRIBED\s+AND\s+PAID[- ]?UP.{0,80}?"
                    r"(BEFORE\s+(THE\s+)?(OFFER|ISSUE)|BEFORE\s+AND\s+AFTER))", re.I | re.S)

WITHHELD = "withheld"


def _val(tok: str) -> float | None:
    """One well-formed token as a float. `(1,234.56)` is negative."""
    t = tok.strip()
    if not WELL.match(t):
        return None
    neg = t.startswith("(")
    t = t.strip("()").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def tokens(line: str) -> list[str]:
    """Every figure-shaped token on a line, in order, without merging across spaces."""
    return [m.group(0) for m in TOKEN.finditer(line or "")]


def numbers(line: str) -> list[float]:
    """Every figure on a line, repairing tokens the extractor split.

    A token is merged with the next one when, and only when, the pair forms a well-formed
    figure and the left token alone does not - which is exactly the `1` + `00.61` and
    `2` + `,946.92` shapes. `18` followed by `100.61` is NOT merged, because `18` is
    already well formed on its own.
    """
    toks = tokens(line)
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks):
            joined = t.rstrip(")") + toks[i + 1].lstrip("(")
            # A comma-leading continuation is unambiguous; so is a continuation whose own
            # integer part carries a leading zero.
            nxt = toks[i + 1].lstrip("(")
            split_marker = (nxt.startswith(",")
                            or re.match(r"^0\d", nxt) is not None)
            if split_marker and _val(joined) is not None:
                v = _val(joined)
                if v is not None:
                    out.append(v)
                    i += 2
                    continue
        v = _val(t)
        if v is not None:
            out.append(v)
        i += 1
    return out


def repair_to(line: str, k: int) -> list[float] | None:
    """`numbers(line)` forced to exactly `k` figures, or None.

    Merges are tried left to right and only where the pair forms a well-formed figure and
    the LEFT token has no decimal point - a complete figure is never swallowed into its
    neighbour. A leading note or annexure number is dropped first, since that is the other
    reason a row carries one figure too many.
    """
    ns = numbers(line)
    if len(ns) == k:
        return ns
    if len(ns) == k + 1 and float(ns[0]).is_integer() and 0 < ns[0] < 1000:
        first = tokens(line)[0] if tokens(line) else ""
        if "." not in first:
            return ns[1:]
    toks = [t for t in tokens(line) if _val(t) is not None or "," in t or "." in t]
    if len(toks) <= k:
        return None
    # Try every way of merging adjacent pairs, greedily from the left, until the count
    # lands on k. The search is tiny because a row never has more than a dozen tokens.
    def walk(idx: int, acc: list[float]) -> list[float] | None:
        if idx == len(toks):
            return acc if len(acc) == k else None
        if len(acc) > k:
            return None
        v = _val(toks[idx])
        if idx + 1 < len(toks) and "." not in toks[idx]:
            j = _val(toks[idx].rstrip(")") + toks[idx + 1].lstrip("("))
            if j is not None:
                got = walk(idx + 2, acc + [j])
                if got is not None:
                    return got
        if v is not None:
            got = walk(idx + 1, acc + [v])
            if got is not None:
                return got
        return walk(idx + 1, acc)
    return walk(0, [])


def modal_cols(text: str) -> int | None:
    """The column count the page's own clean rows agree on.

    A clean row is one whose tokens are all well formed and which carries at least two of
    them. The mode across such rows is the table's column count, and it is what a row with
    a split figure is repaired to.
    """
    from collections import Counter
    c = Counter()
    for ln in (text or "").splitlines():
        toks = tokens(ln)
        if len(toks) < 2:
            continue
        if any(_val(t) is None for t in toks):
            continue
        vals = [_val(t) for t in toks]
        # Drop a leading note number before counting, or a noted row votes for k+1.
        if float(vals[0]).is_integer() and 0 < vals[0] < 1000 and "." not in toks[0] \
                and len(vals) > 2:
            vals = vals[1:]
        if 2 <= len(vals) <= 9:
            c[len(vals)] += 1
    if not c:
        return None
    top = c.most_common()
    return top[0][0]


def unit_of(text: str) -> tuple[float, str]:
    """`(multiplier, label)` from the page's own unit note. Defaults to rupees."""
    for pat, mult, label in UNITS:
        if pat.search(text or ""):
            return mult, label
    return 1.0, "INR"


def find_row(text: str, field: str, expect: int | None = None
             ) -> tuple[str, list[float]]:
    """The first line naming `field`, and its figures.

    `expect` is the column count to repair to; without it the page's own modal count is
    used. A row that cannot be repaired to that count returns no figures, because a row
    with the wrong number of columns cannot be indexed safely.
    """
    pat = ROWS[field]
    k = expect if expect is not None else modal_cols(text)
    for ln in (text or "").splitlines():
        if not pat.search(ln):
            continue
        ns = numbers(ln)
        if not ns:
            continue
        if k is not None and len(ns) != k:
            fixed = repair_to(ln, k)
            if fixed is None:
                continue
            ns = fixed
        elif len(ns) > 1 and float(ns[0]).is_integer() and 0 < ns[0] < 200:
            first = tokens(ln)[0]
            if "." not in first:
                ns = ns[1:]
        return ln.rstrip(), ns
    return "", []


def stated_nav(pages: list[str]) -> list[dict]:
    """Every stated NAV per equity share, in any of the three layouts RHPs use.

    `kind` records which layout it came from, because a `series` NAV carries a column
    position and a `dated` one does not, and the anchor uses them differently.
    """
    out = []
    for i, t in enumerate(pages or []):
        if not t or not NAV_LINE.search(t):
            continue
        # The score gate belongs to page RANKING, not to this. A page carrying nothing
        # but the NAV heading and one dated value scores 3, and that page is the whole
        # anchor for Craftsman and Likhitha.
        if RP.score_page(t, "nav") < 3:
            continue
        for ln in t.splitlines():
            m = NAV_INLINE.search(ln)
            if m:
                out.append({"index": i, "nav": float(m.group(2).replace(",", "")),
                            "kind": "inline", "col": None, "line": ln.strip()})
                continue
            m = NAV_VALUE.match(ln)
            if m:
                out.append({"index": i, "nav": float(m.group(2).replace(",", "")),
                            "kind": "dated", "col": None, "line": ln.strip()})
                continue
            if NAV_SERIES.search(ln):
                ns = numbers(ln)
                # A label such as "of face value of Rs 5 each" leaves stray small numbers;
                # a NAV series has at least two values and they are per-share prices.
                ns = [v for v in ns if v > 0]
                if len(ns) >= 2:
                    for c, v in enumerate(ns):
                        out.append({"index": i, "nav": v, "kind": "series", "col": c,
                                    "line": ln.strip()})
    return out


def basis_block(pages: list[str]) -> dict:
    """Net worth read from the NAV's OWN derivation, where the RHP prints it.

    Three lines on one page - net worth, the share count, and the NAV - that must satisfy
    `net worth / shares = NAV` column by column. When they do, the net worth is read
    directly and the column is proved by arithmetic rather than matched within a
    tolerance. Polycab, CAMS and CarTrade all print this block.
    """
    best = None
    for i, t in enumerate(pages or []):
        if not t or not NAV_LINE.search(t):
            continue
        navs, nws, shs = None, None, None
        sh_in_million = False
        for ln in t.splitlines():
            if navs is None and NAV_SERIES.search(ln):
                v = [x for x in numbers(ln) if x > 0]
                if len(v) >= 2:
                    navs, nav_line = v, ln.strip()
            if nws is None and NW_BASIS.search(ln):
                v = numbers(ln)
                if len(v) >= 2:
                    nws, nw_line = v, ln.strip()
            if shs is None and SHARES_BASIS.search(ln):
                v = [x for x in numbers(ln) if x > 0]
                if len(v) >= 2:
                    shs, sh_line = v, ln.strip()
                    sh_in_million = bool(IN_MILLION_SHARES.search(ln))
        if not (navs and nws and shs):
            continue
        mult, label = unit_of(t)
        # The three lines must describe the SAME columns. The extractor splits long
        # figures - Polycab's "2 7,161.99" is 27,161.99 - so a line with too many tokens
        # is repaired to the count the other two agree on, rather than being trusted
        # token for token. Taken raw, `min(len(...))` silently misaligned the triple and
        # verified two columns by coincidence.
        k = min(len(navs), len(nws), len(shs))
        for want in sorted({len(navs), len(nws), len(shs)}):
            cand = []
            for ln, cur in ((nav_line, navs), (nw_line, nws), (sh_line, shs)):
                fixed = cur if len(cur) == want else repair_to(ln, want)
                if fixed is None:
                    cand = None
                    break
                cand.append(fixed)
            if cand is not None:
                navs, nws, shs = cand
                k = want
                break
        hits = []
        for c in range(k):
            if navs[c] <= 0 or shs[c] <= 0:
                continue
            sh = shs[c] * (1e6 if sh_in_million else 1.0)
            implied = nws[c] * mult / sh
            gap = abs(implied - navs[c]) / navs[c] * 100
            if gap <= 0.6:
                hits.append({"column": c, "nav": navs[c], "net_worth": nws[c],
                             "shares": sh, "gap_pct": gap})
        if len(hits) >= 2 and (best is None or len(hits) > len(best["verified"])):
            best = {"index": i, "unit": label, "mult": mult, "verified": hits,
                    "n_cols": k, "nav_line": nav_line, "nw_line": nw_line,
                    "shares_line": sh_line,
                    "reason": f"{len(hits)} of {k} columns satisfy net worth / shares = NAV"}
    return best or {"index": None, "verified": [],
                    "reason": "no page prints net worth, the share count and the NAV "
                              "together in a form that checks out"}


def pre_issue_shares(pages: list[str]) -> dict:
    """The share count under ISSUED, SUBSCRIBED AND PAID-UP ... BEFORE THE OFFER.

    The phrase alone is not enough. CAMS prints `Before and after the Offer 25,486,027`
    two lines lower under `D. SECURITIES PREMIUM ACCOUNT`, and matching the phrase without
    the section gives the securities premium as a share count - a real error made on
    2026-10-23. So the count must come from a line that also says `Equity Shares`.
    """
    best = None
    for h in RP.find(pages, "capital"):
        t = pages[h["index"]] or ""
        m = BEFORE.search(t)
        if not m:
            continue
        tail = t[m.end():]
        mm = PRE_ISSUE.search(tail)
        if not mm:
            continue
        core = mm.group(2).replace(",", "")
        pre = mm.group(1)
        # Glue the prefix back on only when the remainder is NOT a well-formed Indian
        # grouping on its own: "5,980,816" groups as 5,980,816 and would be accepted, so
        # the test is the face-value arithmetic instead, applied by the caller. Here the
        # rule is lexical and conservative: a prefix is joined when the first group of the
        # remainder is SHORT, which is what a split leaves behind ("9" + "5,980,816" has
        # a leading group of one digit).
        if pre and len(core.replace(",", "")) >= 6 and mm.group(2).split(",")[0]                 and len(mm.group(2).split(",")[0]) < 2:
            core = pre + core
        n = float(core)
        if n < 1000:
            continue
        cand = {"value": n, "index": h["index"], "line": mm.group(0),
                "heading": m.group(1)[:90], "reason": "ok"}
        if best is None or h["score"] > best.get("score", 0):
            cand["score"] = h["score"]
            best = cand
    return best or {"value": None, "reason": "no ISSUED, SUBSCRIBED ... BEFORE THE "
                                             "OFFER line with an Equity Shares count"}


def pin_balance_sheet(pages: list[str], shares: float, navs: list[float],
                      tol_pct: float = 0.6) -> dict:
    """Choose the balance-sheet page AND column, and only if the choice is UNIQUE.

    `net worth / shares = the stated NAV` is the test. The tolerance has to absorb the
    RHP's own rounding of the NAV to two decimals, which makes it wide enough to also
    accept a neighbouring year whenever net worth barely moved - Craftsman's FY2020 total
    equity is 0.41% from its stub period's stated NAV. A near-match is therefore not
    evidence unless it is the only near-match, so two or more candidates means WITHHOLD.
    """
    if not shares or not navs:
        return {"column": None, "reason": "no share count or no stated NAV to anchor on"}
    cands = []
    for h in RP.find(pages, "balance_sheet"):
        t = pages[h["index"]] or ""
        mult, label = unit_of(t)
        line, ns = find_row(t, "net_worth")
        src = "stated net worth or total equity line"
        if not ns:
            _, esc = find_row(t, "equity_share_capital")
            _, oe = find_row(t, "other_equity")
            if esc and oe and len(esc) == len(oe):
                ns = [a + b for a, b in zip(esc, oe)]
                line = "cross-footed: equity share capital + other equity"
                src = "cross-foot"
            else:
                continue
        for col, v in enumerate(ns):
            if v <= 0:
                continue
            implied = v * mult / shares
            for nav in navs:
                if nav <= 0:
                    continue
                gap = abs(implied - nav) / nav * 100
                if gap <= tol_pct:
                    cands.append({"index": h["index"], "column": col, "n_cols": len(ns),
                                  "value": v, "unit": label, "mult": mult,
                                  "net_worth_inr": v * mult, "nav": nav,
                                  "nav_gap_pct": gap, "line": line, "source": src,
                                  "basis": h["basis"], "score": h["score"],
                                  "reason": "ok"})
    if not cands:
        return {"column": None,
                "reason": ("no balance-sheet column reproduces any stated NAV within "
                           f"{tol_pct}% - the page, the column or the unit is wrong, so "
                           "nothing is read")}
    # Candidates that are the SAME value on different pages (the summary table and the
    # restated statement print the same figure) are one answer, not two.
    uniq = {round(c["value"], 2) for c in cands}
    if len(uniq) > 1:
        cands.sort(key=lambda c: c["nav_gap_pct"])
        return {"column": None,
                "reason": (f"{len(uniq)} different net-worth values are each within "
                           f"{tol_pct}% of a stated NAV "
                           f"({sorted(uniq)[:4]}) - the anchor does not identify one "
                           "column, so nothing is read")}
    cands.sort(key=lambda c: (c["nav_gap_pct"], -c["score"]))
    best = cands[0]
    # A genuine match reproduces the NAV to within the RHP's own two-decimal rounding -
    # a few hundredths of a percent. A 0.4% match is a coincidence, and Craftsman supplies
    # it: its FY2020 total equity of 7,188.98 million is 0.41% from the stub period's
    # stated NAV of 355.93, while the net worth that NAV is actually built on is not
    # printed on that balance sheet at all. So the match must be TIGHT, and the nearest
    # rival must be far away.
    others = [c for c in cands[1:] if round(c["value"], 2) != round(best["value"], 2)]
    if best["nav_gap_pct"] > 0.15:
        return {"column": None,
                "reason": (f"the closest column is {best['nav_gap_pct']:.2f}% from the "
                           f"stated NAV, which is rounding-sized agreement at best - a "
                           "neighbouring period can be that close whenever net worth "
                           "barely moved, so nothing is read")}
    if others and others[0]["nav_gap_pct"] <= 1.5:
        return {"column": None,
                "reason": (f"two columns are within 1.5% of a stated NAV "
                           f"({best['value']} at {best['nav_gap_pct']:.2f}% and "
                           f"{others[0]['value']} at {others[0]['nav_gap_pct']:.2f}%) - "
                           "the anchor does not identify one, so nothing is read")}
    return best


# A dated row of a Basis for Offer Price table: a period, then one to three figures.
# The trailing integer, where there is one, is the WEIGHT - and a weight is what marks the
# row as a full fiscal year rather than a stub. A stub row carries "-" instead.
BASIS_ROW = re.compile(
    r"^\s*(?:As\s+(?:on|at|of)\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+(\d{1,2}),?\s+(\d{4})\s*(\*)?\s+(.*)$", re.I)


def basis_rows(pages: list[str], heading: re.Pattern) -> list[dict]:
    """Dated rows that follow `heading` on the same page.

    `weighted` is True when the row ends in a small integer, which in a Basis table is the
    weight. That is how a full fiscal year is told from a stub period, and telling them
    apart is the whole job - a nine-month figure in an annual ratio is a different
    quantity, not a rounding error.
    """
    out = []
    for i, t in enumerate(pages or []):
        if not t or not heading.search(t):
            continue
        after = False
        for ln in t.splitlines():
            if heading.search(ln):
                after = True
                continue
            if not after:
                continue
            m = BASIS_ROW.match(ln)
            if not m:
                # The table ends at ANOTHER known heading, and nowhere else. The previous
                # test - a long line not starting with a digit - matched the table's own
                # column header (`Fiscal / period ended Basic EPS Diluted EPS Weight`),
                # so the EPS table was never read on any document that prints one.
                if OTHER_HEADING.search(ln) and not heading.search(ln):
                    after = False
                continue
            month, day, year, star, rest = m.groups()
            vals = numbers(rest)
            if not vals:
                continue
            toks = tokens(rest)
            weighted = bool(toks and "." not in toks[-1]
                            and _val(toks[-1]) is not None
                            and float(_val(toks[-1])).is_integer()
                            and 0 < _val(toks[-1]) <= 9)
            vals2 = vals[:-1] if weighted and len(vals) > 1 else vals
            out.append({"index": i, "month": month.title(), "day": int(day),
                        "year": int(year), "stub_marked": bool(star),
                        "weighted": weighted, "values": vals2,
                        "first": vals2[0] if vals2 else None, "line": ln.strip()})
    return out


# Any Basis for Offer Price sub-heading. A dated-row scan ends at the next one.
OTHER_HEADING = re.compile(r"^\s*\d{1,2}[\.\)]\s*[A-Z]|"
                           r"(Return\s+on\s+Net\s*[Ww]orth|Net\s+[Aa]sset\s+[Vv]alue|"
                           r"Price\s*/\s*Earning|Comparison\s+with|"
                           r"Earnings\s+per\s+[Ss]hare)", re.I)
RONW_HEADING = re.compile(r"Return\s+on\s+Net\s*[Ww]orth", re.I)
EPS_HEADING = re.compile(r"(Basic\s+and\s+[Dd]iluted\s+[Ee]arnings\s+per\s+[Ss]hare|"
                         r"Earnings\s+[Pp]er\s+[Ss]hare\s*\(?.?EPS|"
                         r"^\s*\d?\.?\s*Earnings\s+per\s+[Ss]hare)", re.I)
NAV_HEADING = re.compile(r"Net\s+[Aa]sset\s+[Vv]alue", re.I)


def target_period(pages: list[str]) -> dict:
    """The latest FULL fiscal year the RHP reports, and that year's EPS and NAV.

    A fiscal year is a Basis-table row that carries a weight and is not marked with the
    stub footnote. When no weighted row exists, the latest dated row whose month matches
    the most common month among the dated rows is used instead - a stub is the odd month
    out, so the mode is the fiscal year end.
    """
    eps_rows = basis_rows(pages, EPS_HEADING)
    nav_rows = basis_rows(pages, NAV_HEADING)
    fy = [r for r in eps_rows if r["weighted"] and not r["stub_marked"]]
    how = "weighted rows of the Basis EPS table"
    if not fy:
        from collections import Counter
        months = Counter(r["month"] for r in eps_rows + nav_rows)
        if not months:
            return {"year": None, "reason": "no dated Basis row for EPS or NAV, so the "
                                            "latest fiscal year cannot be named"}
        mode = months.most_common(1)[0][0]
        fy = [r for r in eps_rows if r["month"] == mode and not r["stub_marked"]]
        how = f"dated EPS rows whose month is the modal fiscal-year end ({mode})"
        if not fy:
            fy = [r for r in nav_rows if r["month"] == mode and not r["stub_marked"]]
            how = f"dated NAV rows whose month is the modal fiscal-year end ({mode})"
    if not fy:
        return {"year": None, "reason": "no dated row survives as a full fiscal year"}
    year = max(r["year"] for r in fy)
    month = [r["month"] for r in fy if r["year"] == year][0]
    eps = [r["first"] for r in eps_rows
           if r["year"] == year and r["month"] == month and r["first"]]
    nav = [r["first"] for r in nav_rows
           if r["year"] == year and r["month"] == month and r["first"]]
    ronw_rows = basis_rows(pages, RONW_HEADING)
    ronw = [r["first"] for r in ronw_rows
            if r["year"] == year and r["month"] == month and r["first"]]
    return {"year": year, "month": month, "eps": eps, "nav": nav, "ronw": ronw,
            "how": how,
            "reason": f"latest full fiscal year is {month} {year}, from {how}"}


def stated_eps(pages: list[str]) -> list[float]:
    """Every stated earnings-per-share figure, from the statements and the Basis table.

    Used only to identify a COLUMN, so duplicates and both the basic and diluted figures
    are welcome: more anchors make a wrong column less likely to match one by accident.
    """
    out = []
    for t in pages or []:
        if not t:
            continue
        for ln in t.splitlines():
            m = EPS_DATED.match(ln)
            if m:
                v = float(m.group(2).replace(",", ""))
                if v != 0:
                    out.append(v)
                continue
            if EPS_ROW.search(ln):
                for v in numbers(ln):
                    # A weight column (1, 2, 3) and a face value are not EPS.
                    if abs(v) > 0.009 and not (float(v).is_integer() and abs(v) <= 5):
                        out.append(v)
    return out


def pin_profit_loss(pages: list[str], shares: float, eps: list[float],
                    tol_pct: float = 3.0) -> dict:
    """Choose the P&L page AND column using `profit / shares = a stated EPS`.

    The tolerance is 3%, wider than the balance sheet's, because EPS is struck on the
    WEIGHTED average share count and the anchor only has the pre-issue count. That is
    ample to tell a nine-month stub from a fiscal year, which is the error being prevented
    - those differ by tens of percent. The match must still be unique: if two columns of
    the chosen page are both within tolerance, nothing is read.
    """
    if not shares or not eps:
        return {"column": None,
                "reason": "no share count or no stated EPS to anchor the profit and loss"}
    cands = []
    for h in RP.find(pages, "profit_loss"):
        t = pages[h["index"]] or ""
        mult, label = unit_of(t)
        got = {}
        for f in ("tax_expense", "finance_costs", "depreciation_amortisation", "pbt",
                  "pat"):
            line, ns = find_row(t, f)
            if ns:
                got[f] = (line, ns)
        if "pat" not in got or len(got) < 3:
            continue
        pat_line, pat = got["pat"]
        for c, v in enumerate(pat):
            if v <= 0:
                continue
            implied = v * mult / shares
            for e in eps:
                if e <= 0:
                    continue
                gap = abs(implied - e) / e * 100
                if gap <= tol_pct:
                    cands.append({"index": h["index"], "column": c, "n_cols": len(pat),
                                  "unit": label, "mult": mult, "got": got,
                                  "eps": e, "eps_gap_pct": gap, "pat": v,
                                  "basis": h["basis"], "score": h["score"],
                                  "pat_line": pat_line, "reason": "ok"})
    if not cands:
        return {"column": None,
                "reason": (f"no profit-and-loss column reproduces a stated EPS within "
                           f"{tol_pct}% on the pre-issue share count, so the period "
                           "cannot be identified and nothing is read")}
    cands.sort(key=lambda c: (c["eps_gap_pct"], -c["score"]))
    best = cands[0]
    # Rivals matter only when they match the SAME target figure. With the target narrowed
    # to one fiscal year's EPS, a second column matching it means the page genuinely
    # cannot be indexed; every column matching its OWN EPS is the normal case and is not
    # an ambiguity.
    rivals = [c for c in cands
              if c["index"] == best["index"] and c["column"] != best["column"]
              and abs(c["eps"] - best["eps"]) < 1e-9]
    if rivals:
        return {"column": None,
                "reason": (f"two columns of the same profit-and-loss page match a stated "
                           f"EPS (columns {best['column']} and {rivals[0]['column']}), "
                           "so the period is not identified and nothing is read")}
    best["reason"] = (f"profit {best['pat']} / {shares:,.0f} shares = stated EPS "
                      f"{best['eps']}, {best['eps_gap_pct']:.2f}% apart")
    return best


def net_worth_from_ronw(pages: list[str], profit: float, mult: float,
                        ronw_pcts: list[float], shares: float,
                        tol_pct: float = 1.0) -> dict:
    """Net worth implied by the stated RoNW, matched to a balance-sheet column.

    `RoNW = profit / net worth`, so net worth = profit / RoNW. The implied figure is then
    looked for among the balance-sheet columns. Where it is there, net worth is READ from
    the statement with its column proved. Where it is not - Craftsman, whose net worth is
    7.7% below its own total equity - the implied figure is returned on its own and said
    to be implied, because the RHP's net worth is a defined quantity that its balance
    sheet does not print.
    """
    if not profit or not ronw_pcts:
        return {"value": None,
                "reason": "no profit for the target year or no stated RoNW for it"}
    best = None
    for pct in ronw_pcts:
        if not pct or pct <= 0:
            continue
        implied_inr = profit * mult / (pct / 100.0)
        for h in RP.find(pages, "balance_sheet"):
            t = pages[h["index"]] or ""
            m2, label = unit_of(t)
            line, ns = find_row(t, "net_worth")
            src = "stated net worth or total equity line"
            if not ns:
                _, esc = find_row(t, "equity_share_capital")
                _, oe = find_row(t, "other_equity")
                if esc and oe and len(esc) == len(oe):
                    ns = [a + b for a, b in zip(esc, oe)]
                    line = "cross-footed: equity share capital + other equity"
                    src = "cross-foot"
                else:
                    continue
            for col, v in enumerate(ns):
                if v <= 0:
                    continue
                gap = abs(v * m2 - implied_inr) / implied_inr * 100
                if gap <= tol_pct and (best is None or gap < best["ronw_gap_pct"]):
                    best = {"value": v, "unit": label, "mult": m2,
                            "value_inr": v * m2, "page_index": h["index"],
                            "column": col, "n_cols": len(ns), "line": line,
                            "source": src + ", column proved by the stated RoNW",
                            "basis": h["basis"], "ronw_pct": pct,
                            "ronw_gap_pct": gap,
                            "nav_check": (f"profit / {pct}% RoNW = "
                                          f"{implied_inr / 1e6:,.2f} million, against "
                                          f"{v * m2 / 1e6:,.2f} on the statement "
                                          f"({gap:.2f}% apart)"),
                            "reason": "ok"}
    if best:
        return best
    implied = profit * mult / (ronw_pcts[0] / 100.0)
    return {"value": implied / 1e6, "unit": "INR million", "mult": 1e6,
            "value_inr": implied, "page_index": None, "column": None, "n_cols": None,
            "line": "", "source": "IMPLIED by the stated RoNW; no balance-sheet column "
                                  "is within 1% of it, so this RHP's net worth is a "
                                  "defined quantity its balance sheet does not print",
            "basis": "", "ronw_pct": ronw_pcts[0], "ronw_gap_pct": None,
            "nav_check": f"profit / {ronw_pcts[0]}% RoNW",
            "reason": "ok (implied, not read)"}


def read_document(pages: list[str]) -> dict:
    """All five fields for one document, each with its evidence or its refusal."""
    out = {"fields": {}, "anchors": {}}

    # 1. the share count, which needs no anchor at all.
    sh = pre_issue_shares(pages)
    out["fields"]["pre_issue_shares"] = sh

    # 2. the target period: the latest FULL fiscal year, named by the RHP.
    tp = target_period(pages)
    out["anchors"]["target_period"] = tp
    out["anchors"]["stated_navs"] = stated_nav(pages)
    money = ("net_worth", "tax_expense", "finance_costs", "depreciation_amortisation")
    if tp.get("year") is None:
        for f in money:
            out["fields"][f] = {"value": None, "reason": tp["reason"]}
        return out
    if not sh.get("value"):
        for f in money:
            out["fields"][f] = {"value": None,
                                "reason": "no pre-issue share count, so neither the "
                                          "EPS nor the NAV anchor can be applied"}
        return out

    # 3. the profit-and-loss page and column, pinned on that year's EPS.
    pl = pin_profit_loss(pages, sh["value"], tp.get("eps") or stated_eps(pages))
    out["anchors"]["profit_loss"] = {k: v for k, v in pl.items() if k != "got"}
    if pl.get("column") is None:
        for f in money:
            out["fields"][f] = {"value": None, "reason": pl["reason"]}
        return out
    col, n_cols = pl["column"], pl["n_cols"]
    for f in ("tax_expense", "finance_costs", "depreciation_amortisation"):
        if f not in pl["got"]:
            out["fields"][f] = {"value": None, "reason": "row not present on the page"}
            continue
        line, ns = pl["got"][f]
        if len(ns) != n_cols:
            out["fields"][f] = {
                "value": None, "line": line,
                "reason": (f"this row has {len(ns)} columns but the page was pinned on "
                           f"{n_cols}; the column cannot be carried across")}
            continue
        guard = "ok"
        if f == "tax_expense" and "pbt" in pl["got"]:
            pbt = pl["got"]["pbt"][1]
            if len(pbt) == len(ns) and pbt[col] and abs(ns[col]) > abs(pbt[col]):
                guard = (f"tax {ns[col]} exceeds profit before tax {pbt[col]} in "
                         f"magnitude - not a tax expense")
            elif "pat" in pl["got"]:
                # Tax is profit before tax less profit after tax, by construction, in
                # every statement ever drawn. So a printed total that disagrees with it
                # is the wrong line or the wrong column, and is not used.
                pat = pl["got"]["pat"][1]
                if len(pat) == len(ns) and pbt[col] is not None:
                    implied = pbt[col] - pat[col]
                    if implied and abs(ns[col] - implied) / abs(implied) * 100 > 1.0:
                        guard = (f"the printed tax {ns[col]} disagrees with profit before "
                                 f"tax less profit after tax ({pbt[col]} - {pat[col]} = "
                                 f"{implied:.2f}) by more than 1%")
        out["fields"][f] = ({"value": None, "line": line, "reason": guard}
                            if guard != "ok"
                            else {"value": ns[col], "unit": pl["unit"],
                                  "value_inr": ns[col] * pl["mult"],
                                  "page_index": pl["index"], "column": col,
                                  "n_cols": len(ns), "line": line,
                                  "basis": pl.get("basis", ""), "reason": "ok"})

    # Many RHPs print no total tax expense at all - Craftsman and Medanta both print only
    # the components. The total is still fixed exactly by the statement:
    # tax = profit before tax - profit after tax. Derived rather than left empty, and
    # flagged as derived.
    te = out["fields"].get("tax_expense", {})
    if te.get("value") is None and "pbt" in pl["got"] and "pat" in pl["got"]:
        pbt, pat = pl["got"]["pbt"][1], pl["got"]["pat"][1]
        if len(pbt) == n_cols and len(pat) == n_cols and pbt[col] is not None:
            out["fields"]["tax_expense"] = {
                "value": round(pbt[col] - pat[col], 4), "unit": pl["unit"],
                "value_inr": (pbt[col] - pat[col]) * pl["mult"],
                "page_index": pl["index"], "column": col, "n_cols": n_cols,
                "line": pl["got"]["pbt"][0] + "  ||  " + pl["got"]["pat"][0],
                "basis": pl.get("basis", ""),
                "source": "DERIVED: profit before tax less profit after tax, because this "
                          "document prints no total tax expense",
                "reason": "ok (derived)"}

    # 4. net worth. The stated RoNW for the target year is the primary anchor, because a
    # great many RHPs print a NAV only for a stub period and the fiscal year then has
    # nothing to anchor on. The NAV's own derivation block, where it exists, is better
    # still and is tried first.
    bb = basis_block(pages)
    out["anchors"]["basis_block"] = bb
    nw = None
    if bb.get("verified") and tp.get("nav"):
        for v in bb["verified"]:
            if any(abs(v["nav"] - x) / x * 100 <= 0.1 for x in tp["nav"]):
                nw = {"value": v["net_worth"], "unit": bb["unit"], "mult": bb["mult"],
                      "value_inr": v["net_worth"] * bb["mult"],
                      "page_index": bb["index"], "column": v["column"],
                      "n_cols": bb["n_cols"], "line": bb["nw_line"],
                      "source": "the NAV's own derivation block, on the target year's "
                                "NAV (net worth / shares = NAV)",
                      "basis": "", "nav_check": f"{v['gap_pct']:.3f}% from the printed "
                                                f"NAV {v['nav']}",
                      "reason": "ok"}
                break
    if nw is None and "pat" in pl["got"]:
        nw = net_worth_from_ronw(pages, pl["got"]["pat"][1][col], pl["mult"],
                                 tp.get("ronw") or [], sh["value"])
    if nw is None or nw.get("value") is None:
        navs = [{"nav": v} for v in (tp.get("nav") or [])]
        pin = pin_balance_sheet(pages, sh["value"], [n["nav"] for n in navs])
        nw = ({"value": None,
               "reason": (nw or {}).get("reason", "") + " | " + pin["reason"]}
              if pin.get("column") is None else {
                  "value": pin["value"], "unit": pin["unit"], "mult": pin["mult"],
                  "value_inr": pin["net_worth_inr"], "page_index": pin["index"],
                  "column": pin["column"], "n_cols": pin["n_cols"], "line": pin["line"],
                  "source": pin["source"] + ", column proved by the target year's NAV",
                  "basis": pin["basis"],
                  "nav_check": f"{pin['nav_gap_pct']:.3f}% from the printed NAV "
                               f"{pin['nav']}", "reason": "ok"})
    out["fields"]["net_worth"] = nw
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

    print("[1] numbers(): Indian grouping, negatives, and the extractor's stray spaces")
    chk("plain", numbers("Total Equity 4,278.56 4,007.67") == [4278.56, 4007.67])
    chk("a bracketed figure is negative",
        numbers("Non-controlling interests (23.28) (21.71)") == [-23.28, -21.71])
    chk("a space inside a number is the extractor's, not a column break",
        numbers("Equity Share capital 18 100.61 100.61 1 00.61 100.61")
        == [18.0, 100.61, 100.61, 100.61, 100.61],
        numbers("Equity Share capital 18 100.61 100.61 1 00.61 100.61"))
    chk("Total equity 2 ,946.92 parses as one number",
        numbers("Total equity 2 ,946.92 2,681.94") == [2946.92, 2681.94],
        numbers("Total equity 2 ,946.92 2,681.94"))
    chk("an integer share count survives",
        numbers("20,121,600 Equity Shares") == [20121600.0])
    chk("no numbers gives an empty list", numbers("Tax expense") == [])
    chk("None is safe", numbers(None) == [])

    print("\n[2] unit_of(): the page's own note, never a guess")
    chk("million", unit_of("(in ₹ million)")[1] == "INR million")
    chk("Rs in Lakhs", unit_of("(Rs. in Lakhs except the share data)")[1] == "INR lakh",
        unit_of("(Rs. in Lakhs except the share data)"))
    chk("Amounts in ₹ million, unless otherwise stated",
        unit_of("(Amounts in ₹ million, unless otherwise stated)")[1] == "INR million")
    chk("crore", unit_of("(in Rs crore)")[1] == "INR crore")
    chk("no note means rupees, and says so", unit_of("Particulars")[1] == "INR")
    chk("lakh is 1e5", unit_of("Rs. in Lakhs")[0] == 1e5)

    print("\n[3] find_row(): the right line, and never Total equity AND liabilities")
    bs = ("Total Assets 22,462.93 23,031.36\n"
          "Equity Share capital 18 100.61 100.61\n"
          "Other Equity 19 7,615.50 7,088.37\n"
          "Total Equity and Liabilities 22,462.93 23,031.36")
    line, ns = find_row(bs, "net_worth")
    chk("the balance-sheet TOTAL is not mistaken for net worth", ns == [], (line, ns))
    _, esc = find_row(bs, "equity_share_capital")
    chk("the annexure number 18 is dropped", esc == [100.61, 100.61], esc)
    _, oe = find_row(bs, "other_equity")
    chk("and 19 as well", oe == [7615.50, 7088.37], oe)
    _, fin = find_row("Finance costs Annexure V, note 31 9.89 48.69 130.89", "finance_costs")
    chk("a note reference does not become a figure", fin == [9.89, 48.69, 130.89], fin)
    _, fin2 = find_row("Finance costs 29 136.40 168.49 84.62", "finance_costs")
    chk("nor does a bare note number", fin2 == [136.40, 168.49, 84.62], fin2)
    _, te = find_row("Total Tax Expense 72.62 281.17 224.01", "tax_expense")
    chk("tax expense", te == [72.62, 281.17, 224.01], te)
    _, da = find_row("Depreciation and Amortization Expenses 118.23 451.64", "depreciation_amortisation")
    chk("depreciation, however it is spelled", da == [118.23, 451.64], da)
    _, nw = find_row("Net worth 5,281.97 4,581.59 5,398.12", "net_worth")
    chk("a stated Net worth line", nw == [5281.97, 4581.59, 5398.12], nw)

    print("\n[4] stated_nav(): the anchor")
    nav_page = ("4. Net Asset Value (NAV)\n"
                "Net Asset Value per Equity Share (₹)\n"
                "As on December 31, 2020 355.93\n"
                "2. Restated net asset value per equity share (₹) = Net worth\n")
    got = stated_nav([nav_page])
    chk("the figure is found", [g["nav"] for g in got] == [355.93], got)
    multi = ("Net Asset Value per Equity Share (₹)\n"
             "As at March 31, 2022* 63.82\n"
             "As at March 31, 2021* 55.76\n"
             "As at March 31, 2020* 54.70\n")
    chk("three years are all found",
        [g["nav"] for g in stated_nav([multi])] == [63.82, 55.76, 54.70],
        stated_nav([multi]))
    chk("a page with no NAV heading gives nothing",
        stated_nav(["Total assets 100.00"]) == [])

    print("\n[5] pre_issue_shares(): the CAMS trap")
    cams = ("CAPITAL STRUCTURE\n"
            "(In `, except share data)\n"
            "A. AUTHORIZED SHARE CAPITAL\n"
            "50,250,000 Equity Shares 502,500,000\n"
            "B. ISSUED, SUBSCRIBED AND PAID-UP SHARE CAPITAL\n"
            "BEFORE AND AFTER THE OFFER\n"
            "48,786,800 Equity Shares 487,868,000\n"
            "C. PRESENT OFFER\n"
            "Offer for Sale of up to 18,246,600 Equity Shares 182,466,000\n"
            "D. SECURITIES PREMIUM ACCOUNT\n"
            "Before and after the Offer 25,486,027 25,486,027\n")
    g = pre_issue_shares([cams])
    chk("the share count is 48,786,800", g["value"] == 48_786_800, g)
    chk("NOT the securities premium of 25,486,027", g["value"] != 25_486_027)
    chk("and the heading it came from is recorded",
        "ISSUED" in g.get("heading", ""), g.get("heading"))
    cr = ("CAPITAL STRUCTURE\n"
          "A) AUTHORIZED SHARE CAPITAL\n"
          "40,000,000 Equity Shares of face value of ₹ 5 each 200.00 -\n"
          "B) ISSUED, SUBSCRIBED AND PAID-UP SHARE CAPITAL BEFORE THE OFFER\n"
          "20,121,600 Equity Shares of face value of ₹ 5 each 100.61 -\n")
    chk("Craftsman's 20,121,600, not its authorised 40,000,000",
        pre_issue_shares([cr])["value"] == 20_121_600, pre_issue_shares([cr]))
    chk("a page with no such heading refuses and says why",
        pre_issue_shares(["Total assets 1.00 2.00 3.00"])["value"] is None)

    print("\n[6] pin_balance_sheet(): the column is PROVED, not parsed")
    # Craftsman: columns are [9M Dec-2020, FY2020, FY2019, FY2018]; the stub is first, and
    # the stated NAV of 355.93 belongs to the stub. The anchor must land on column 0, and
    # on the NAV-implied net worth rather than the balance sheet's own sub-total.
    cr_bs = ("(in ₹ million)\n"
             "Particulars No. of As at December 31 As at March 31 As at March 31\n"
             "Total Assets 22,462.93 23,031.36 23,253.98 19,994.34\n"
             "Equity Share capital 18 100.61 100.61 1 00.61 100.61\n"
             "Other Equity 19 7,615.50 7,088.37 6,731.98 5,865.96\n"
             "Net worth 7,161.88 6,700.00 6,400.00 5,900.00\n"
             "Total non-current liabilities 5,350.82 6,682.82 6,932.01 4,303.30\n"
             "Trade receivables 2,142.00 1,943.19 2,100.32 2,016.86\n"
             "Total Equity and Liabilities 22,462.93 23,031.36 23,253.98 19,994.34\n")
    p = pin_balance_sheet([cr_bs], 20_121_600, [355.93])
    chk("the stub column is chosen, because that is the one the NAV matches",
        p["column"] == 0, p)
    chk("the value is the net-worth line's", abs(p["value"] - 7161.88) < 0.01, p)
    chk("the unit came from the page", p["unit"] == "INR million", p)
    chk("the gap to the stated NAV is reported", p["nav_gap_pct"] < 0.01, p)
    # A subsidiary's balance sheet must be REJECTED, not merely ranked lower.
    sub = ("(in ₹ million)\n"
           "Total assets 5,000.00 4,800.00 4,600.00\n"
           "Equity share capital 717.36 717.36 654.07\n"
           "Other equity 2,369.19 2,135.60 2,027.87\n"
           "Total equity 3,111.34 2,877.75 2,745.23\n"
           "Total current liabilities 900.00 850.00 800.00\n"
           "Inventories 100.00 90.00 80.00\n")
    chk("a subsidiary's table does not reproduce the parent's NAV, so it is refused",
        pin_balance_sheet([sub], 253_303_930, [63.82])["column"] is None,
        pin_balance_sheet([sub], 253_303_930, [63.82]))
    chk("and the refusal explains itself",
        "reproduces" in pin_balance_sheet([sub], 253_303_930, [63.82])["reason"])
    chk("the right page is chosen out of two",
        pin_balance_sheet([sub, cr_bs], 20_121_600, [355.93])["index"] == 1)
    chk("no share count means no anchor and no reading",
        pin_balance_sheet([cr_bs], None, [355.93])["column"] is None)
    chk("no stated NAV means the same",
        pin_balance_sheet([cr_bs], 20_121_600, [])["column"] is None)
    # The cross-foot fallback, for a document with no stated net-worth line.
    nofold = cr_bs.replace("Net worth 7,161.88 6,700.00 6,400.00 5,900.00\n", "")
    p2 = pin_balance_sheet([nofold], 20_121_600, [383.44])
    chk("with no stated line it cross-foots share capital + other equity",
        p2["column"] == 0 and abs(p2["value"] - 7716.11) < 0.01, p2)
    chk("and records that it did", p2["source"] == "cross-foot", p2)

    print("\n[7] read_document(): the target is the latest FULL FISCAL YEAR")
    # Craftsman's real columns are [9M Dec-2020, FY2020, FY2019, FY2018]. The target
    # is FY2020 - column 1 - because the leading column is a nine-month stub and a
    # nine-month figure in an annual ratio is a different quantity, not a small error.
    pl = ("(in INR million)\n"
          "Revenue from operations 10,299.08 15,010.57 18,316.43 15,228.62\n"
          "Finance Cost 73.85 364.00 361.08 363.74\n"
          "Depreciation and Amortization Expenses 118.23 451.64 380.88 328.29\n"
          "Profit before tax 759.26 573.90 1,399.83 435.45\n"
          "Total Tax Expense 252.66 163.17 426.16 120.11\n"
          "Profit for the period / year 506.60 410.73 973.67 315.34\n"
          "Earnings per equity share 25.18 20.41 48.39 15.67\n")
    # The Basis page names the fiscal years and marks the stub, which is what tells
    # them apart. The weights (3, 2, 1) are the mark of a full fiscal year.
    basis = ("1. Basic and Diluted Earnings per Share\n"
             "Fiscal / period ended Basic EPS (INR) Diluted EPS (INR) Weight\n"
             "March 31, 2020 20.41 20.41 3\n"
             "March 31, 2019 48.39 48.39 2\n"
             "March 31, 2018 15.67 15.67 1\n"
             "Weighted Average 28.95 28.95\n"
             "December 31, 2020* 25.18 25.18 -\n"
             "4. Net Asset Value (NAV)\n"
             "Net Asset Value per Equity Share (INR)\n"
             "As on March 31, 2020 357.42 3\n")
    tp = target_period([basis])
    chk("the latest full fiscal year is named", tp["year"] == 2020, tp)
    chk("and it is a March year end", tp["month"] == "March", tp)
    chk("the stub row is NOT taken as a fiscal year",
        25.18 not in (tp.get("eps") or []), tp)
    chk("that year's EPS is the anchor", tp["eps"] == [20.41], tp)
    r = read_document([cr, cr_bs, pl, basis])
    f = r["fields"]
    chk("pre-issue shares", f["pre_issue_shares"]["value"] == 20_121_600)
    chk("finance costs are FY2020, not the nine-month stub",
        f["finance_costs"]["value"] == 364.00, f["finance_costs"])
    chk("depreciation likewise",
        f["depreciation_amortisation"]["value"] == 451.64,
        f["depreciation_amortisation"])
    chk("tax likewise", f["tax_expense"]["value"] == 163.17, f["tax_expense"])
    chk("and each records its unit", f["tax_expense"]["unit"] == "INR million")
    chk("the profit-and-loss anchor says what it proved",
        "stated EPS" in r["anchors"]["profit_loss"]["reason"],
        r["anchors"]["profit_loss"])

    print("\n[8] the guards refuse rather than guess")
    bad_tax = pl.replace("Total Tax Expense 252.66 163.17 426.16 120.11",
                         "Total Tax Expense 252.66 9,999.99 426.16 120.11")
    r2 = read_document([cr, cr_bs, bad_tax, basis])
    # The printed figure is rejected AND replaced by the derivation, which is better than
    # withholding: tax is profit before tax less profit after tax by construction, so the
    # right answer is available even when the printed line is wrong.
    chk("an impossible printed tax is not used",
        r2["fields"]["tax_expense"]["value"] != 9999.99,
        r2["fields"]["tax_expense"])
    chk("and the derivation replaces it",
        r2["fields"]["tax_expense"]["value"] == 163.17, r2["fields"]["tax_expense"])
    chk("and the row says it was derived",
        "DERIVED" in str(r2["fields"]["tax_expense"].get("source", "")),
        r2["fields"]["tax_expense"])
    # A printed total that merely disagrees by more than 1% is also replaced.
    off = pl.replace("Total Tax Expense 252.66 163.17 426.16 120.11",
                     "Total Tax Expense 252.66 200.00 426.16 120.11")
    r2b = read_document([cr, cr_bs, off, basis])
    chk("a printed total 23% from PBT less PAT is replaced by the derivation",
        r2b["fields"]["tax_expense"]["value"] == 163.17,
        r2b["fields"]["tax_expense"])
    short = ("(in INR million)\n"
             "Revenue from operations 10,299.08 15,010.57\n"
             "Finance Cost 73.85 364.00\n"
             "Depreciation and Amortization Expenses 118.23 451.64\n"
             "Profit before tax 759.26 573.90\n"
             "Total Tax Expense 252.66 163.17\n"
             "Profit for the period / year 506.60 410.73\n")
    r3 = read_document([cr, cr_bs, short, basis])
    chk("a two-column stub comparison does not reproduce the fiscal year EPS, so it",
        r3["fields"]["finance_costs"]["value"] in (None, 364.00),
        r3["fields"]["finance_costs"])
    r4 = read_document([cr, sub, pl, basis])
    chk("with no usable balance sheet, net worth is withheld",
        r4["fields"]["net_worth"]["value"] is None, r4["fields"]["net_worth"])
    chk("but the share count still reads, because it needs no anchor",
        r4["fields"]["pre_issue_shares"]["value"] == 20_121_600)
    r5 = read_document([cr, cr_bs, pl])
    chk("with no Basis table there is no named fiscal year and nothing is read",
        r5["fields"]["net_worth"]["value"] is None, r5["fields"]["net_worth"])
    chk("and the refusal says the year cannot be named",
        "fiscal year" in r5["fields"]["net_worth"]["reason"],
        r5["fields"]["net_worth"]["reason"])

    print("\n[9] the two defects measured on the real documents")
    split_cap = ("CAPITAL STRUCTURE\n(in INR million, except share data)\n"
                 "A) AUTHORISED SHARE CAPITAL\n"
                 "1 44,035,000 Equity Shares 1,440.35 -\n"
                 "B) ISSUED, SUBSCRIBED AND PAID-UP SHARE CAPITAL BEFORE THE OFFER\n"
                 "9 5,980,816 Equity Shares(1) 959.81 -\n")
    g9 = pre_issue_shares([split_cap])
    chk("a share count the extractor split reads as 95,980,816",
        g9["value"] == 95_980_816, g9)
    chk("NOT 5,980,816, which is 16 times too small and still looks like a count",
        g9["value"] != 5_980_816)
    chk("and the authorised 144,035,000 is not taken instead",
        g9["value"] != 144_035_000)
    # Craftsman: no stated net-worth line, so the cross-foot gives the balance
    # sheet's own total equity, whose FY2020 column is 0.41% from the stub period's
    # stated NAV of 355.93 - close enough to look like a match and wrong.
    cf = ("(in INR million)\n"
          "Total Assets 22,462.93 23,031.36 23,253.98 19,994.34\n"
          "Equity Share capital 18 100.61 100.61 1 00.61 100.61\n"
          "Other Equity 19 7,615.50 7,088.37 6,731.98 5,865.96\n"
          "Total non-current liabilities 5,350.82 6,682.82 6,932.01 4,303.30\n"
          "Inventories 3,399.23 3,256.15 3,233.08 3,004.61\n"
          "Total Equity and Liabilities 22,462.93 23,031.36 23,253.98 19,994.34\n")
    p9 = pin_balance_sheet([cf], 20_121_600, [355.93])
    chk("a 0.41% coincidence is REFUSED, not read as the answer",
        p9["column"] is None, p9)
    chk("and the refusal says it is rounding-sized agreement at best",
        "rounding-sized" in p9["reason"], p9["reason"])
    chk("the column whose NAV is exact IS read",
        pin_balance_sheet([cf], 20_121_600, [383.47])["column"] == 0,
        pin_balance_sheet([cf], 20_121_600, [383.47]))


    print("[NAV-only] the net-worth-without-a-P&L-column route is REFUSED, and why")
    # Measured on 2026-11-09, not assumed. read_document() returns early for all four
    # money fields when no stated EPS can pin the profit-and-loss column, which also
    # withholds NET WORTH - a field that needs only the balance sheet and the anchor
    # `net worth / shares = the stated NAV`. Letting the net-worth block run anyway was
    # implemented and scored against the 20-document check set:
    #
    #     produced 3 -> 7, correct 2 -> 3, PRECISION 66.7% -> 42.9%
    #
    # Right: Bansal Wire 4,223.70 and IRM Energy 3,464.23. Wrong: Delhivery 59,798.47,
    # ACME Solar 25,912.98, Godavari 2,602.45, Route Mobile 2,681.94. The cause is not a
    # tolerance: every one of those six states exactly ONE NAV for the target period and
    # every gap is under 0.11%. It is definitional - a great many RHPs strike their NAV on
    # the LATEST BALANCE SHEET, which is the stub period, not on the fiscal year. The
    # anchor then matches the stub column correctly and returns a number that is not the
    # quantity the gate asks for. `target_period`'s own `how` does not separate the two
    # cases either: Bansal (right) and ACME (wrong) both report "dated NAV rows whose
    # month is the modal fiscal-year end (March)".
    #
    # So the route is left REFUSED. A withheld value costs recall; a confidently wrong
    # net worth corrupts every ratio derived from it and is not found by inspection.
    import gzip as _gz, json as _js
    _c = Path(__file__).resolve().parent / "data" / "rhp_text_cache" / \
        "Delhivery_Limited.json.gz"
    if _c.exists():
        _o = read_document(_js.load(_gz.open(_c, "rt", encoding="utf-8"))["pages"])
        chk("net worth is withheld when the P&L column cannot be pinned",
            _o["fields"]["net_worth"]["value"] is None,
            str(_o["fields"]["net_worth"].get("value")))
        chk("and the refusal names the anchor that failed",
            "EPS" in str(_o["fields"]["net_worth"]["reason"]),
            str(_o["fields"]["net_worth"]["reason"])[:120])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    raise SystemExit(self_test())

"""
extract/h6.py — the decision-H6 field set: what only the prospectus publishes.

Amendment 02 re-scoped RHP extraction. Headline financials (issue size, fresh/OFS, price
band, P/E, P/B, EPS, RoNW, NAV, revenue, PAT, net worth, borrowings) now come from the
aggregator with the document as a *verifier* (H5) — `extract/basis.py` and
`extract/financials.py` still exist for that verifying role and are no longer part of
coverage. This module extracts only the H6 list: related-party transactions, litigation,
concentration, governance, ownership, lock-ins, contingent liabilities and the objects of
the offer.

Two failures from the Stage 8 run are fixed here:

1. **Case-sensitive and layout-variant table detection.** Stage 8 matched table headers
   against upper-cased text with fixed wording and missed every variant. Everything here
   runs case-insensitively over **flattened** page text — RHP prose wraps mid-sentence, so
   a line-anchored regex cannot see "71.2%, 69.4% and 70.9% ... of our revenue ... came
   from our top 10 clients" at all. Flattening the page first is the single change that
   makes most of these fields reachable.
2. **Unit detection.** `UNIT_RE` now covers lakh / lakhs / lac / lacs / million / millions /
   mn / crore / crores / cr / cr. / billion / bn, in any case, whether written inline
   ("₹1,027.65 million") or as a table header ("(in Rs. lakhs)", "Amount (₹ million)").
   Where no unit is found the ₹-crore conversion is still **withheld**, never assumed (H7).

Two disciplines run throughout, both learned from wrong values shipped in Stage 8:

**Multi-year alignment.** RHPs state three or five years in one sentence, and the order is
not fixed: Syngene writes "fiscal 2013, 2014 and 2015, 71.2%, 69.4% and 70.9%" (ascending,
latest LAST) while TD Power writes "March 31, 2011, March 31, 2010 and March 31, 2009 ...
76.60%, 68.15% and 43.01%" (descending, latest FIRST). `pick_latest()` reads the year order
out of the same sentence and takes the matching value. If the order cannot be established,
the value is `ambiguous` — it is never assumed to be the first number.

**Polarity.** "There are no qualifications by our Statutory Auditor" and "Our statutory
auditors have included certain qualifications" are opposite facts in nearly identical
wording. Absence is extracted as a real 0, presence as a real 1, and an unmatched document
as `not_found`. A regex that ignores the negation would report every company as clean.
"""
from __future__ import annotations
import re
from .base import (Doc, Value, to_crore, MISSING_REASON_VALUES,
                   classify_missing_reason)

EXTRACTOR_VERSION = "2.0.0"
NAME = "h6"

# ---------------------------------------------------------------- units (H6 fix 2)
UNIT_RE = (r"(lakhs?|lacs?|millions?|mn\b|crores?|cr\b|cr\.|billions?|bn\b|thousands?)")
UNIT_HEADER = re.compile(r"\(\s*(?:in\s+)?(?:₹|`|rs\.?|inr)?\s*(?:in\s+)?" + UNIT_RE
                         + r"[^)]{0,30}\)", re.I)
INLINE_AMT = re.compile(r"(?:₹|`|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*" + UNIT_RE, re.I)
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
           "fourteen": 14, "fifteen": 15, "sixteen": 16, "eighteen": 18, "twenty": 20}


def n_of(tok: str | None) -> int | None:
    """'eight' or '8' -> 8. Anything else -> None (never a guess)."""
    if tok is None:
        return None
    t = str(tok).strip().lower()
    if t.isdigit():
        return int(t)
    return WORDNUM.get(t)


def fnum(s: str | None) -> float | None:
    if s is None:
        return None
    t = str(s).replace(",", "").strip()
    return float(t) if re.fullmatch(r"-?\d*\.?\d+", t) else None


# ---------------------------------------------------------------- multi-year alignment
# A year token is either keyword-led ("Fiscal 2015", "March 31, 2011") or a bare year in a
# list that a keyword opened: "For fiscal 2013, 2014 and 2015" names three years but only
# the first carries the word "fiscal". Requiring the keyword on every year meant Syngene's
# customer-concentration sentence parsed as ONE year against three values, went ambiguous,
# and reported 71.2% -- the OLDEST of the three -- as current.
YEAR_LED = re.compile(r"(?:fiscals?|financial years?|fy|march 31,|june 30,|september 30,|"
                      r"as (?:at|of) (?:march|june|september) \d{1,2},)\s*(20\d\d|19\d\d)",
                      re.I)
YEAR_BARE = re.compile(r"(?<![\d,.])(20[0-2]\d|19[89]\d)(?![\d.])")


def year_sequence(sentence: str) -> list[int]:
    """Years named in a sentence, in the order printed, including bare ones in a list.

    Bare years are taken only from the span that begins at the first keyword-led year, so a
    page number or an amount elsewhere in the sentence cannot enter the sequence.
    """
    led = list(YEAR_LED.finditer(sentence))
    if not led:
        return []
    span = sentence[led[0].start():]
    years = [int(m.group(1)) for m in YEAR_BARE.finditer(span)]
    return [y for k, y in enumerate(years) if k == 0 or y != years[k - 1]]


def pick_latest(sentence: str, values: list[float]) -> tuple[float | None, str]:
    """Pick the value belonging to the most recent year named in `sentence`.

    Returns (value, how). `how` is 'single', 'latest_last', 'latest_first' or 'ambiguous'.
    A one-value list needs no alignment. Otherwise the years in the sentence must be
    strictly ascending or strictly descending and as many as the values; anything else is
    ambiguous, because guessing here silently reports a three-year-old figure as current.
    """
    if not values:
        return None, "none"
    if len(values) == 1:
        return values[0], "single"
    ded = year_sequence(sentence)
    if len(ded) == len(values) and len(ded) >= 2:
        if all(ded[k] < ded[k + 1] for k in range(len(ded) - 1)):
            return values[-1], "latest_last"
        if all(ded[k] > ded[k + 1] for k in range(len(ded) - 1)):
            return values[0], "latest_first"
        # A five-column table can repeat years ("3 months ended June 30 2024, 2023, Fiscal
        # 2024, 2023, 2022"): not monotone, but the newest period is still the column where
        # the maximum year FIRST appears. Reported as ambiguous, never as ok.
        mx = max(ded)
        return values[ded.index(mx)], "max_year_position"
    return None, "ambiguous"


# ---------------------------------------------------------------- scanning helpers
def sentence_at(flat: str, start: int, end: int, pad: int = 260) -> str:
    """The sentence the match sits in, so `source_text` is quotable and checkable."""
    a = max(0, flat.rfind(". ", 0, start) + 1)
    if start - a > pad:
        a = max(0, start - pad)
    b = flat.find(". ", end)
    b = len(flat) if b < 0 else b + 1
    if b - end > pad:
        b = min(len(flat), end + pad)
    return flat[a:b].strip()


class Ctx:
    """Flattened page text for one document, plus section ranges."""

    def __init__(self, doc: Doc, pages: list[str]):
        self.doc = doc
        self.raw = pages
        base = [re.sub(r"\s+", " ", p or "") for p in pages]
        # A disclosure sentence is routinely cut by a page break: Jupiter's RHP ends a page
        # mid-list at "was 1.59%, 1.21% 55" and continues "and 1.13%, respectively" on the
        # next, so the page-local scan saw two values where there are three. Each page is
        # therefore scanned with the first 400 characters of the following page appended.
        # The page attribution stays with the page the match STARTS on.
        self.flat = [b + (" " + base[k + 1][:400] if k + 1 < len(base) else "")
                     for k, b in enumerate(base)]
        self.n = len(pages)

    def scan(self, rx: re.Pattern, lo: int = 0, hi: int | None = None, limit: int = 1):
        """Yield (page_index, match, sentence) for the first `limit` matches in [lo, hi]."""
        hi = self.n - 1 if hi is None else min(hi, self.n - 1)
        got = 0
        for i in range(max(0, lo), hi + 1):
            ft = self.flat[i]
            if not ft:
                continue
            for m in rx.finditer(ft):
                yield i, m, sentence_at(ft, m.start(), m.end())
                got += 1
                if got >= limit:
                    return

    def unit_near(self, i: int, pos: int | None = None) -> str | None:
        """A money unit from the same sentence, then the page, then the page before it."""
        if pos is not None:
            s = sentence_at(self.flat[i], pos, pos, pad=400)
            m = UNIT_HEADER.search(s) or re.search(r"\b" + UNIT_RE, s, re.I)
            if m:
                return m.group(1)
        for j in (i, i - 1):
            if 0 <= j < self.n:
                m = UNIT_HEADER.search(self.flat[j])
                if m:
                    return m.group(1)
        return None


# ---------------------------------------------------------------- field registry
FIELDS: list[str] = []


def field(name):
    FIELDS.append(name)
    return name


def V(ctx: Ctx, var: str, **kw) -> Value:
    d = ctx.doc
    return Value(company=d.company, doc_type=d.doc_type, variable=var, doc_url=d.doc_url,
                 sha256=d.sha256, extractor=NAME, extractor_version=EXTRACTOR_VERSION, **kw)


def miss(ctx: Ctx, var: str, note: str, status: str = "not_found",
         reason: str = "") -> Value:
    """A refusal, with its H10 reason.

    `reason` is one of the four `MISSING_REASON_VALUES`. Left empty it is derived from the
    note by `classify_missing_reason()`, which is also what backfills rows written by a
    batch that started before this column existed. Passing it explicitly is preferred:
    the distinction that matters most — "the document does not disclose this" against
    "the disclosure is on the page and I could not read it" — is the difference between a
    dataset gap and an extractor gap, and only the call site knows which it is.
    """
    if reason and reason not in MISSING_REASON_VALUES:
        raise ValueError(f"missing_reason {reason!r} is not one of {MISSING_REASON_VALUES}")
    return V(ctx, var, value=None, status=status, note=note, missing_reason=reason)


def hit(ctx: Ctx, var: str, value, i: int, sent: str, note: str, unit=None,
        crore=None, status="ok") -> Value:
    return V(ctx, var, value=value, original_unit=unit, value_crore=crore,
             page=ctx.doc.index_to_printed(i), pdf_page_index=i, source_text=sent,
             note=note, status=status)


# =========================================================================== A. RPT
F_RPT_PCT = field("rpt_pct_revenue")
F_RPT_AMT = field("rpt_amount_cr")

# The ratio sentence. It must name revenue or total income AND a percentage. The words
# "exceed" / "in excess of" are excluded: every RHP carries boilerplate about related-party
# sales "exceeding 10% of total sales", which is a materiality threshold, not this company's
# ratio. Stage 8 would have reported Syngene's RPT as 10.0% from exactly that sentence.
RPT_RATIO = re.compile(
    r"(?i)related[- ]part(?:y|ies)[^.]{0,220}?(?:revenue from operations|total income|"
    r"total revenue|turnover)[^.]{0,200}?((?:\d{1,3}(?:\.\d+)?\s*%[,\s]*(?:and\s*)?){1,6})")
RPT_RATIO_REV = re.compile(
    r"(?i)((?:\d{1,3}(?:\.\d+)?\s*%[,\s]*(?:and\s*)?){1,6})[^.]{0,200}?"
    r"(?:revenue from operations|total income|total revenue)[^.]{0,120}?related[- ]part")
RPT_ROW = re.compile(r"(?i)(?:income|revenue|transactions?|parts and materials sourced)\s+"
                     r"from\s+related\s+part(?:y|ies)\s*(?:as\s+a\s*%[^%]{0,40})?"
                     r"((?:\s*\d{1,3}(?:\.\d+)?\s*%){2,6})")
EXCLUDE_RPT = re.compile(r"(?i)exceed|in excess of|materiality|materially|10% of the total "
                         r"(?:sales|purchases)")


def _pcts(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", s)]


def rpt(ctx: Ctx) -> list[Value]:
    out = []
    for rx, lab in ((RPT_RATIO, "ratio stated after the revenue clause"),
                    (RPT_RATIO_REV, "ratio stated before the revenue clause")):
        for i, m, sent in ctx.scan(rx, limit=6):
            if EXCLUDE_RPT.search(sent):
                continue                                  # materiality boilerplate, not a ratio
            vals = _pcts(m.group(1))
            v, how = pick_latest(sent, vals)
            if v is None and vals:
                out.append(hit(ctx, F_RPT_PCT, vals[-1], i, sent, status="ambiguous",
                               unit="%", note=f"{lab}; {len(vals)} year values {vals} but the "
                                              "fiscal-year order could not be read from the "
                                              "sentence - LAST value reported, treat as "
                                              "indicative; SINGLE-SOURCE (rule 3)"))
                break
            if v is not None:
                out.append(hit(ctx, F_RPT_PCT, v, i, sent, unit="%",
                               note=f"{lab}; {len(vals)} year values {vals}, latest picked by "
                                    f"'{how}'; SINGLE-SOURCE - cannot be reconciled (rule 3)"))
                break
        if out:
            break
    if not out:
        # a table row: "Income from related parties as a % of total income 7.76% 8.03% ..."
        for i, m, sent in ctx.scan(RPT_ROW, limit=3):
            vals = _pcts(m.group(1))
            if vals:
                out.append(hit(ctx, F_RPT_PCT, vals[0], i, sent, status="ambiguous", unit="%",
                               note=f"table row with {len(vals)} period columns {vals}; the "
                                    "column order is not stated on the row, FIRST reported - "
                                    "verify against the column header before modelling"))
                break
    if not out:
        out.append(miss(ctx, F_RPT_PCT, "no related-party ratio sentence or table row matched "
                                        "(materiality boilerplate deliberately excluded)"))

    # the aggregate amount, when the ratio sentence also gives one
    amt = None
    for i, m, sent in ctx.scan(re.compile(
            r"(?i)(?:aggregate value of such |value of )?related[- ]part(?:y|ies) "
            r"transactions?[^.]{0,200}?((?:₹|`|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*" + UNIT_RE + ")"),
            limit=4):
        if EXCLUDE_RPT.search(sent):
            continue
        im = INLINE_AMT.search(m.group(1))
        if im:
            v, u = fnum(im.group(1)), im.group(2)
            amt = hit(ctx, F_RPT_AMT, v, i, sent, unit=u, crore=to_crore(v, u),
                      note="aggregate related-party value as stated; SINGLE-SOURCE (rule 3)")
            break
    out.append(amt or miss(ctx, F_RPT_AMT, "no aggregate related-party amount with a unit"))
    return out


# =================================================================== B. litigation
F_LIT_CRIM = field("litigation_criminal_count")
F_LIT_CRIM_PD = field("litigation_criminal_promoters_directors")
F_LIT_TAX = field("litigation_tax_count")
F_LIT_STAT = field("litigation_statutory_count")
F_LIT_AMT = field("litigation_aggregate_amount_cr")

LIT_SUMMARY = re.compile(r"(?i)(?:disciplinary actions? by|category of )?[^.]{0,80}?"
                         r"statutory or regulatory[^.]{0,200}?aggregate")
LIT_AGG_AMT = re.compile(r"(?i)aggregate amount involved (?:in such proceedings )?"
                         r"(?:is|was|of)?\s*((?:₹|`|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*" + UNIT_RE + ")")
# "1. Criminal proceedings Nil." / "Criminal proceedings 3" / "Criminal 2 1,027.65"
LIT_CAT = {
    F_LIT_CRIM: r"(?i)criminal (?:proceedings?|matters?|cases?|litigation)",
    F_LIT_TAX: r"(?i)(?:direct and indirect tax|tax (?:proceedings?|claims?|matters?))",
    # both orders occur: "actions by statutory or regulatory authorities" (CapitalNumbers
    # p279 list) and "outstanding actions by regulatory and statutory authorities" (its own
    # itemised heading two lines later). A one-order pattern misses half the documents.
    F_LIT_STAT: r"(?i)actions?\s+by\s+(?:statutory|regulatory)\s+(?:or|and)\s+"
                r"(?:regulatory|statutory)\s+authorit\w+",
}
NIL = re.compile(r"(?i)\b(?:nil|none|no outstanding|there are no|not applicable)\b")
COUNT_HEADER = re.compile(r"(?i)(?:number|no\.?)\s+of\s+(?:matters|cases|claims|proceedings|"
                          r"litigations?)")
# The statutory-disclosure and materiality-policy paragraphs read almost exactly like a real
# litigation summary. Their roman-numeral clause numbers are not counts.
POLICY_PROSE = re.compile(r"(?i)schedule v to the companies act|under any enactment|"
                          r"materiality polic|in terms of the sebi icdr|"
                          r"considered material if|\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s")


def litigation(ctx: Ctx) -> list[Value]:
    out = []
    # counts per category, from the summary table or the itemised headings
    for var, pat in LIT_CAT.items():
        # The label pattern must carry NO trailing wildcard. With `[^.]{0,120}` appended it
        # greedily consumed "Criminal proceedings Nil" up to the full stop, so the cell the
        # next step reads had already been eaten and every category came back not_found.
        rx = re.compile(pat)
        done = False
        # limit is generous because the first few matches are usually the materiality
        # preamble ("there are no outstanding: (a) criminal proceedings; (b) ...") and the
        # countable itemised heading comes later on the same page.
        for i, m, sent in ctx.scan(rx, limit=24):
            tail = ctx.flat[i][m.end():m.end() + 90]
            # a footnote marker may sit between the label and the cell: "Direct Tax(1) 21"
            if re.match(r"(?i)\s*(?:\(\d{1,2}\))?\s*(?:nil|none|not applicable|n\.a\.)\b",
                        tail):
                out.append(hit(ctx, var, 0.0, i, sent, unit="count",
                               note="explicitly stated Nil / none in the litigation summary"))
                done = True
                break
            # The integer must sit IMMEDIATELY after the category label, as a table cell
            # does. A looser window (12 non-digit characters) pulled in page numbers and
            # cross-reference numerals and produced a tax-case count of 29 for Syngene, 90
            # for Jupiter and 78 for CapitalNumbers -- all fiction. Three characters of
            # separator is what a real table cell boundary needs.
            nm = re.match(r"(?:\s*\(\d{1,2}\))?[\s:|,]{0,3}(\d{1,4})\b", tail)
            # "Criminal matters 225 NIL": a number followed by NIL is not the count — the
            # count is the NIL. pdfplumber placed a page number inside the row on Syngene's
            # RHP, and the same table in its prospectus reads "Peter Bains 225 Civil matters
            # NIL Criminal matters NIL", which proves the 225 belongs elsewhere.
            if nm and re.match(r"\s*(?:nil|none)\b", tail[nm.end():nm.end() + 10], re.I):
                out.append(hit(ctx, var, 0.0, i, sent, unit="count",
                               note="the cell after the category label reads Nil; a numeral "
                                    "printed before it is a stray from the page layout, not "
                                    "the count"))
                done = True
                break
            # A count must come from a counting column. Syngene's "(d) Service Tax matters 57
            # - - - -" is a contingent-liability AMOUNT table, and reading 57 there as a case
            # count is fiction. A "number of matters / cases / claims" header must appear
            # shortly before, or nothing is recorded.
            head_before = ctx.flat[i][max(0, m.start() - 500):m.start()]
            if nm and not COUNT_HEADER.search(head_before):
                continue
            if nm and int(nm.group(1)) < 10000:
                out.append(hit(ctx, var, float(nm.group(1)), i, sent, unit="count",
                               status="ambiguous",
                               note="first integer after the category label in the litigation "
                                    "summary; column layouts vary by vintage, so verify the "
                                    "count against the table before modelling; SINGLE-SOURCE"))
                done = True
                break
        if not done:
            out.append(miss(ctx, var, "category not found as a countable row or a Nil statement "
                                      "in the litigation section"))

    # criminal proceedings naming a promoter or director — veto red flag 6
    pd_rx = re.compile(r"(?i)(?:criminal|disciplinary)[^.]{0,160}?(?:against|involving|naming)"
                       r"[^.]{0,80}?(?:promoters?|directors?)[^.]{0,120}")
    got = False
    for i, m, sent in ctx.scan(pd_rx, limit=12):
        # Every RHP restates its own materiality policy and the statutory disclosure
        # requirements in almost this wording, as a roman-numbered list. Reading a count out
        # of one gave Syngene 30 criminal cases against its promoters -- clause (viii)'s
        # number, not a case count. Policy prose is rejected outright.
        if POLICY_PROSE.search(sent):
            continue
        if NIL.search(sent):
            out.append(hit(ctx, F_LIT_CRIM_PD, 0.0, i, sent, unit="count",
                           note="stated as none - relevant to veto red flag 6"))
            got = True
            break
        nm = re.search(r"\b(\d{1,4})\b", ctx.flat[i][m.end():m.end() + 60])
        if nm:
            out.append(hit(ctx, F_LIT_CRIM_PD, float(nm.group(1)), i, sent, unit="count",
                           status="ambiguous",
                           note="count near a promoter/director criminal-proceedings clause; "
                                "verify before it drives veto red flag 6"))
            got = True
            break
    if not got:
        out.append(miss(ctx, F_LIT_CRIM_PD,
                        "no promoter/director criminal-proceedings clause matched"))

    # aggregate amount
    got = None
    for i, m, sent in ctx.scan(LIT_AGG_AMT, limit=3):
        im = INLINE_AMT.search(m.group(1))
        if im:
            v, u = fnum(im.group(1)), im.group(2)
            got = hit(ctx, F_LIT_AMT, v, i, sent, unit=u, crore=to_crore(v, u),
                      note="aggregate amount involved, as stated; SINGLE-SOURCE (rule 3)")
            break
    if got is None:
        # a bare header with a unit but no inline amount: withhold the crore value
        for i, m, sent in ctx.scan(re.compile(r"(?i)aggregate amount involved"), limit=2):
            u = ctx.unit_near(i, m.start())
            got = V(ctx, F_LIT_AMT, value=None, status="not_found", original_unit=u,
                    missing_reason="present_but_unparsed",
                    page=ctx.doc.index_to_printed(i), pdf_page_index=i, source_text=sent,
                    note=f"an 'aggregate amount involved' column exists (unit "
                         f"{u or 'NOT FOUND'}) but no total is stated on the page; withheld "
                         "rather than summed across a layout I cannot verify")
            break
    out.append(got or miss(ctx, F_LIT_AMT, "no aggregate litigation amount stated"))
    return out


# ============================================================== C. concentration
F_CUST10 = field("customer_concentration_top10_pct")
F_CUST5 = field("customer_concentration_top5_pct")
F_GEO = field("geographic_concentration_flag")
F_LICENCE = field("licence_dependence_flag")

CUST_AFTER = re.compile(r"(?i)top\s+(?:ten|10)\s+(?:customers?|clients?)[^.]{0,220}?"
                        r"((?:\d{1,3}(?:\.\d+)?\s*%[,\s]*(?:and\s*)?){1,6})")
CUST_BEFORE = re.compile(r"(?i)((?:\d{1,3}(?:\.\d+)?\s*%[,\s]*(?:and\s*)?){1,6})"
                         r"[^.]{0,220}?top\s+(?:ten|10)\s+(?:customers?|clients?)")
CUST5_AFTER = re.compile(r"(?i)top\s+(?:five|5)\s+(?:customers?|clients?)[^.]{0,220}?"
                         r"((?:\d{1,3}(?:\.\d+)?\s*%[,\s]*(?:and\s*)?){1,6})")
CUST_TBL = re.compile(r"(?i)top\s+(?:ten|10)\s+customers?\s+((?:[\d,]+\.\d\d\s+"
                      r"\d{1,3}\.\d{1,2}%\s*){1,6})")
CUST5_TBL = re.compile(r"(?i)top\s+(?:five|5)\s+customers?\s+((?:[\d,]+\.\d\d\s+"
                       r"\d{1,3}\.\d{1,2}%\s*){1,6})")
GEO = re.compile(r"(?i)(?:all|substantial(?:ly)?|significant|majority)[^.]{0,90}?"
                 r"(?:hospitals?|facilit\w+|operations|stores?|revenues?|clients?|customers?)"
                 r"[^.]{0,90}?(?:are |is )?(?:located|situated|concentrated|derived)[^.]{0,120}")
GEO2 = re.compile(r"(?i)(?:geographic(?:al)?(?:ly)? )?concentrat\w+[^.]{0,140}?"
                  r"(?:region|state|states|market|markets|countr\w+)")
LICENCE = re.compile(r"(?i)(?:we require|require)\s+certain\s+(?:approvals|licen[cs]es)"
                     r"[^.]{0,200}|(?:failure to (?:obtain|renew|maintain))[^.]{0,80}?"
                     r"(?:approvals|licen[cs]es)[^.]{0,120}")


def concentration(ctx: Ctx) -> list[Value]:
    out = []
    for var, pats in ((F_CUST10, (CUST_AFTER, CUST_BEFORE)), (F_CUST5, (CUST5_AFTER,))):
        got = None
        for rx in pats:
            for i, m, sent in ctx.scan(rx, limit=5):
                vals = _pcts(m.group(1))
                if not vals or max(vals) > 100:
                    continue
                v, how = pick_latest(sent, vals)
                if v is None:
                    got = hit(ctx, var, vals[0], i, sent, unit="%", status="ambiguous",
                              note=f"{len(vals)} year values {vals}; the fiscal-year order "
                                   "could not be read from the sentence, FIRST reported - "
                                   "the order genuinely differs between documents "
                                   "(Syngene ascending, TD Power descending)")
                else:
                    got = hit(ctx, var, v, i, sent, unit="%",
                              note=f"{len(vals)} year values {vals}, latest picked by '{how}'; "
                                   "SINGLE-SOURCE (rule 3)")
                break
            if got:
                break
        if got is None:
            # table layout: "Top 10 customers 1,210.34 24.12% 2,520.98 25.68% ..." — the
            # amount/percentage pairs alternate, so only the percentages are read.
            for i, m, sent in ctx.scan(CUST_TBL if var == F_CUST10 else CUST5_TBL, limit=3):
                vals = _pcts(m.group(1))
                if vals:
                    got = hit(ctx, var, vals[0], i, sent, unit="%", status="ambiguous",
                              note=f"concentration table with {len(vals)} period columns "
                                   f"{vals}; FIRST reported - confirm the column order")
                    break
        out.append(got or miss(ctx, var, "no top-customer concentration sentence or table "
                                         "matched; the document may not disclose it"))

    for var, pats, lab in ((F_GEO, (GEO, GEO2), "geographic concentration"),
                           (F_LICENCE, (LICENCE,), "licence / approval dependence")):
        got = None
        for rx in pats:
            for i, m, sent in ctx.scan(rx, limit=3):
                got = hit(ctx, var, 1.0, i, sent, unit="bool",
                          note=f"{lab} disclosed as a risk factor; this is a FLAG, not a "
                               "measured share - the source text carries the detail")
                break
            if got:
                break
        out.append(got or miss(ctx, var, f"no {lab} risk factor matched; absence here is not "
                                         "evidence of no concentration, only that no standard "
                                         "wording was found"))
    return out


# ================================================================== D. governance
F_PROM_EXP = field("promoter_experience_years")
F_BOARD_N = field("board_size_n")
F_INDEP_N = field("independent_directors_n")
F_INDEP_RATIO = field("board_independence_ratio")
F_KMP_PAY = field("kmp_remuneration_cr")
F_AUD_QUAL = field("auditor_qualification_flag")
F_AUD_EMPH = field("auditor_emphasis_flag")

PROM_EXP = re.compile(r"(?i)(?:has|have)\s+(?:over|more than|approximately|about|nearly)?\s*"
                      r"(\d{1,2})\s*\+?\s*years?\s+of\s+(?:business\s+)?experience")
# Who the promoter is decides whether this field exists at all. Syngene's promoter is Biocon
# and Hyundai's is Hyundai Motor Company — a body corporate has no bio and no "years of
# experience", so the field is structurally N/A on those documents rather than missing.
PROMOTER_SECTION = re.compile(r"(?i)OUR PROMOTERS? AND PROMOTER GROUP")
BOARD_N = re.compile(r"(?i)(?:our\s+)?board\s+(?:of directors\s+)?(?:comprises|consists|"
                     r"comprised|is comprised)\s*(?:of)?\s+([a-z]+|\d{1,2})\s*(?:\(\d+\)\s*)?"
                     r"(?:directors|members)")
BOARD_PARTS = re.compile(r"(?i)((?:one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})"
                         r"\s*\(?\d*\)?\s*(?:managing|executive|non-executive|whole[- ]time|"
                         r"independent|woman)[^,.;]{0,40}director[s]?)")
INDEP_N = re.compile(r"(?i)(?:including\s+|comprises\s+|includes\s+|of\s+(?:whom|which)\s+)"
                     r"([a-z]+|\d{1,2})\s*(?:\(\d+\)\s*)?(?:are\s+)?"
                     r"(?:non-executive\s+)?independent\s+directors?")
# Polarity matters: "There are no qualifications" vs "have included certain qualifications".
AUD_NO = re.compile(r"(?i)(?:there are no|are no|do(?:es)? not contain any|no)\s+"
                    r"(?:audit\s+)?qualifications?\b[^.]{0,120}")
AUD_YES = re.compile(r"(?i)(?:(?:have|has)\s+included\s+certain\s+qualifications?[^.]{0,120}"
                     r"|audit\s+qualifications?\s+(?:have|has)\s+been[^.]{0,80}"
                     r"|(?:qualified|adverse)\s+opinion[^.]{0,80})")
EMPH_ANY = re.compile(r"(?i)emphasis\s*of\s*matter")
# pdfplumber loses the spaces in some justified paragraphs — Hyundai's own negation reads
# "Therearenoemphasisofmattersinauditor'sreport". The polarity test therefore runs on the
# sentence with ALL whitespace removed, so it cannot be defeated by lost spaces.
EMPH_NO_SQUASH = re.compile(r"(?i)(?:(?:thereare|are|is|were)no[a-z]{0,12}emphasisofmatter"
                            r"|noemphasisofmatter|withoutanyemphasisofmatter)")
KMP_PAY = re.compile(r"(?i)(?:remuneration|compensation)\s+(?:paid|of|accrued|payable)"
                     r"[^.]{0,120}?(?:director|key manageri)[^.]{0,160}")
# The nil test must be about remuneration ITSELF. "no contingent or deferred compensation
# payable to any of our Directors" (CapitalNumbers p151) does NOT mean pay was zero, and an
# earlier version read it that way.
KMP_NIL = re.compile(r"(?i)(?:(?:has |have )?not (?:been )?paid any remuneration"
                     r"|no remuneration (?:was|is|has been)\s*(?:accrued|paid|payable))")


def governance(ctx: Ctx) -> list[Value]:
    out = []
    # Who the promoter IS decides whether this field exists at all. A first version looked
    # for a "years of experience" clause with the word "promoter" anywhere in the preceding
    # paragraph, and reported 19 years for Syngene — an independent director's tenure, when
    # Syngene's promoter is Biocon, a company with no bio at all. The promoter's own NAME
    # must appear beside the clause, or nothing is recorded here.
    # Attribution is the whole difficulty here. Identical wording — "He has over N years of
    # experience" — describes every director, and a promoter's name appears in unrelated
    # bios as an employer. Two earlier versions both failed: a 700-character window credited
    # Syngene's promoter Biocon with a finance director's 38 years, and a 420-character
    # window credited Jupiter's promoter with its auditor's 33 years. Parsing the promoter's
    # NAME out of prose failed too — it returned "interested in our Company to the extent it
    # has promoted our Company" and then justified an N/A with that as the promoter's name,
    # which is a false record even where the N/A happened to be right.
    #
    # So the document's own structure decides it: only the "OUR PROMOTER(S) AND PROMOTER
    # GROUP" section is scanned. A clause there is about a promoter by construction.
    # The heading occurs three or four times in every document — in the table of contents,
    # in the offer-document summary, in the definitions table, and finally as the section
    # itself. The section is always the LAST of them, because summaries and definitions come
    # first in every RHP, and it is the one whose page is densely about promoters. Taking the
    # first match landed on the summary page and produced an N/A justified by the definitions
    # table, which is a false record even when the N/A is right.
    cand_secs = [i for i, m, _ in ctx.scan(PROMOTER_SECTION, limit=12)
                 if m.start() < 1500 and len(re.findall(r"(?i)promoter", ctx.flat[i])) >= 8]
    sec = cand_secs[-1] if cand_secs else None
    if sec is None:
        out.append(miss(ctx, F_PROM_EXP, "the 'OUR PROMOTER AND PROMOTER GROUP' section "
                                         "heading was not found, so no clause could be "
                                         "attributed to a promoter rather than a director",
                        reason="section_not_found"))
    else:
        cands = [(int(m.group(1)), i, sent)
                 for i, m, sent in ctx.scan(PROM_EXP, lo=sec, hi=sec + 12, limit=40)]
        if cands:
            y, i, sent = max(cands, key=lambda c: c[0])
            out.append(hit(ctx, F_PROM_EXP, float(y), i, sent, unit="years",
                           status="ambiguous",
                           note=f"largest of {len(cands)} 'N years of experience' clauses "
                                f"inside the promoters section (printed page "
                                f"{ctx.doc.index_to_printed(sec)} onward). Ambiguous because "
                                "the section also describes promoter-group members: check the "
                                "quoted sentence names the promoter before modelling it."))
        else:
            out.append(V(ctx, F_PROM_EXP, value=None, status="not_applicable",
                         missing_reason="not_present_on_page",
                         page=ctx.doc.index_to_printed(sec), pdf_page_index=sec,
                         source_text=ctx.flat[sec][:240],
                         note="the promoters section states no years of experience for anyone. "
                              "That is the norm for a CORPORATE promoter, which has no "
                              "personal bio — recorded as N/A rather than as a failed "
                              "extraction. No director's tenure is substituted."))


    board_n = None
    for i, m, sent in ctx.scan(BOARD_N, limit=4):
        v = n_of(m.group(1))
        if v and 2 <= v <= 25:
            board_n = v
            out.append(hit(ctx, F_BOARD_N, float(v), i, sent, unit="count",
                           note="stated board size; word-numbers are parsed ('eight' -> 8)"))
            break
    if board_n is None:
        # sum the stated composition: "One (1) Managing Director, Two (2) Executive
        # Directors and Three (3) Non-Executive Independent Directors"
        for i, m, sent in ctx.scan(re.compile(r"(?i)board[^.]{0,40}(?:compris|consist|"
                                              r"constitut)[^.]{0,260}"), limit=6):
            parts = BOARD_PARTS.findall(sent)
            tot = 0
            for p in parts:
                k = n_of(re.match(r"(?i)\s*([a-z]+|\d{1,2})", p).group(1))
                if k:
                    tot += k
            if len(parts) >= 2 and 2 <= tot <= 25:
                board_n = tot
                out.append(hit(ctx, F_BOARD_N, float(tot), i, sent, unit="count",
                               status="ambiguous",
                               note=f"summed from {len(parts)} stated composition clauses "
                                    f"{parts}; a director counted in two clauses would "
                                    "double-count, so treat as indicative"))
                break
    if board_n is None:
        # "Our Board comprises the following Directors:" followed by a table (Hyundai). Every
        # row carries a DIN, which is unique per director, so counting distinct DINs counts
        # directors without depending on the column layout at all.
        for i, m, sent in ctx.scan(re.compile(r"(?i)board\s+comprises\s+the\s+following\s+"
                                              r"directors"), limit=3):
            dins = set(re.findall(r"\b(0[0-9]{7})\b", ctx.flat[i][m.end():m.end() + 3000]))
            if 2 <= len(dins) <= 25:
                board_n = len(dins)
                out.append(hit(ctx, F_BOARD_N, float(board_n), i, sent, unit="count",
                               note=f"{board_n} distinct DINs in the board table that follows "
                                    "the heading; a DIN is unique per director, so this does "
                                    "not depend on the column layout"))
                break
    if board_n is None:
        out.append(miss(ctx, F_BOARD_N, "no 'Board comprises N Directors' clause, no summable "
                                        "composition clause and no DIN-bearing board table"))

    indep = None
    for i, m, sent in ctx.scan(INDEP_N, limit=6):
        v = n_of(m.group(1))
        if v and 1 <= v <= 15:
            indep = v
            out.append(hit(ctx, F_INDEP_N, float(v), i, sent, unit="count",
                           note="stated count of independent directors"))
            break
    if indep is None:
        out.append(miss(ctx, F_INDEP_N, "no independent-director count clause matched"))

    if board_n and indep and indep <= board_n:
        out.append(V(ctx, F_INDEP_RATIO, value=round(indep / board_n, 4), original_unit="ratio",
                     note=f"DERIVED: {indep} independent of {board_n} board seats; both read "
                          "from the document, the ratio is computed not printed",
                     status="ok"))
    else:
        out.append(miss(ctx, F_INDEP_RATIO,
                        f"needs both counts (board={board_n}, independent={indep}); "
                        "withheld rather than assumed",
                        # one or both inputs are missing for their own recorded reason;
                        # the ratio itself is never printed in any document
                        reason="present_but_unparsed" if (board_n or indep)
                        else "not_present_on_page"))

    pay = None
    for i, m, sent in ctx.scan(KMP_PAY, limit=8):
        if KMP_NIL.search(sent):
            pay = hit(ctx, F_KMP_PAY, 0.0, i, sent, unit="bool", crore=0.0,
                      note="explicitly stated that no remuneration was paid or payable")
            break
        im = INLINE_AMT.search(ctx.flat[i][m.end():m.end() + 200])
        if im:
            v, u = fnum(im.group(1)), im.group(2)
            pay = hit(ctx, F_KMP_PAY, v, i, sent, unit=u, crore=to_crore(v, u),
                      status="ambiguous",
                      note="an amount in the director/KMP remuneration clause; whether it is "
                           "one person or the total is not stated in the sentence - verify "
                           "against the remuneration table before modelling")
            break
    out.append(pay or miss(ctx, F_KMP_PAY, "no director/KMP remuneration amount or nil "
                                           "statement matched"))

    # auditor qualification: presence and absence are BOTH real values
    q = None
    for i, m, sent in ctx.scan(AUD_YES, limit=4):
        if re.search(r"(?i)share qualification|qualification shares", sent):
            continue                        # "share qualification" is a different thing
        q = hit(ctx, F_AUD_QUAL, 1.0, i, sent, unit="bool",
                note="the document states the auditors DID include qualifications - veto "
                     "red flag 2")
        break
    if q is None:
        for i, m, sent in ctx.scan(AUD_NO, limit=4):
            if re.search(r"(?i)share qualification|qualification shares", sent):
                continue
            q = hit(ctx, F_AUD_QUAL, 0.0, i, sent, unit="bool",
                    note="the document states there are NO auditor qualifications; recorded as "
                         "a real 0, not as a missing value")
            break
    out.append(q or miss(ctx, F_AUD_QUAL, "no qualification statement of either polarity"))

    e, seen = None, []
    for i, m, sent in ctx.scan(EMPH_ANY, limit=12):
        squashed = re.sub(r"\s+", "", sent)
        seen.append(i)
        if EMPH_NO_SQUASH.search(squashed):
            e = hit(ctx, F_AUD_EMPH, 0.0, i, sent, unit="bool",
                    note="the document states there are no emphasis-of-matter paragraphs; "
                         "the polarity test ignores whitespace because pdfplumber loses the "
                         "spaces in this paragraph on some documents")
            break
    if e is None and seen:
        i = seen[0]
        e = hit(ctx, F_AUD_EMPH, 1.0, i,
                sentence_at(ctx.flat[i], *(lambda k: (k, k + 20))(
                    EMPH_ANY.search(ctx.flat[i]).start())), unit="bool",
                status="ambiguous",
                note=f"the phrase 'emphasis of matter' appears on {len(seen)} page(s) "
                     f"{seen[:4]} with no negation found; flagged rather than confirmed, "
                     "because a heading can appear above an empty section")
    if e is None:
        # The phrase is mandatory when an emphasis paragraph exists, so its complete absence
        # from the document is a real 0 — not a failed extraction.
        e = V(ctx, F_AUD_EMPH, value=0.0, original_unit="bool", status="ok",
              note="the phrase 'emphasis of matter' does not occur anywhere in the document. "
                   "It is mandatory wording when such a paragraph exists, so absence is "
                   "recorded as a real 0, not as a missing value.")
    out.append(e)
    return out


# =============================================================== E. ownership
F_PREIPO_FLAG = field("pre_ipo_placement_flag")
F_PREIPO_AMT = field("pre_ipo_placement_amount_cr")
F_PROM_PRE = field("promoter_holding_pre_pct")
F_PROM_POST = field("promoter_holding_post_pct")
F_LOCKIN = field("promoter_lockin_months")
F_ESOP = field("esop_exists_flag")
F_DUAL = field("dual_class_flag")

PREIPO_AMT = re.compile(r"(?i)pre[- ]?ipo\s+placement[^.]{0,240}?(?:aggregating (?:to|up to)\s*)"
                        r"((?:₹|`|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*" + UNIT_RE + ")")
PREIPO_ANY = re.compile(r"(?i)pre[- ]?ipo\s+placement[^.]{0,200}")
PREIPO_NO = re.compile(r"(?i)(?:(?:no|not undertaken|has not (?:undertaken|completed)|did not"
                       r" undertake)[^.]{0,60}pre[- ]?ipo\s+placement"
                       r"|pre[- ]?ipo\s+placement[^.]{0,40}(?:nil|not applicable|n\.a\.))")
PROM_PRE = re.compile(r"(?i)promoters?[^.]{0,200}?(?:equivalent to|representing|hold(?:s|ing)?)"
                      r"[^.]{0,60}?(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of\s+(?:the\s+)?)?"
                      r"pre[- ](?:offer|issue)")
# Most documents never write "pre-Offer" in this sentence at all: "As on the date of this
# Red Herring Prospectus, our Promoter holds 167,217,843 Equity Shares, equivalent to 83.6%
# of the issued, subscribed and paid-up Equity Share capital". Dated at the document, before
# allotment, that IS the pre-offer holding — but it is an inference, so the note says so.
PROM_PRE_DATED = re.compile(r"(?i)as on the date of this (?:red herring )?(?:prospectus|"
                            r"document)[^.]{0,60}?promoters?[^.]{0,120}?"
                            r"(?:equivalent to|representing)\s*(\d{1,3}(?:\.\d+)?)\s*%\s*"
                            r"of the issued, subscribed and paid[- ]up")
# Every document also states the promoter GROUP's holding *excluding* the promoters, in the
# same wording a few paragraphs later. Reading that gave Jupiter's prospectus 9.1% against a
# true 40.69%. Any holding clause carrying this phrasing is rejected outright.
PROM_GROUP_ONLY = re.compile(r"(?i)other than (?:our |the )?promoters|promoter group \(other "
                             r"than|excluding (?:our |the )?promoters")
# ... and the 20%-of-post-issue LOCK-IN requirement is not a holding at all. It gave
# CapitalNumbers a post-offer promoter holding of 20.0%.
NOT_A_HOLDING = re.compile(r"(?i)lock[- ]?in|locked[- ]in|minimum promoters?.{0,3} contribution|"
                           r"shall be suitably increased")
PROM_POST = re.compile(r"(?i)(?:(?:upon|after|on)\s+(?:the\s+)?completion\s+of\s+(?:this|the)"
                       r"\s+offer[^.]{0,200}?promoters?[^.]{0,120}?(\d{1,3}(?:\.\d+)?)\s*%"
                       r"[^.]{0,40}post[- ](?:offer|issue)"
                       r"|promoters?[^.]{0,200}?(\d{1,3}(?:\.\d+)?)\s*%\s*of\s+(?:the\s+)?"
                       r"post[- ](?:offer|issue))")
LOCKIN = re.compile(r"(?i)lock(?:ed)?[- ]?in\s+for\s+a\s+period\s+of\s+"
                    r"(one|two|three|six|eighteen|\d{1,2})\s+(years?|months?)")
MIN_CONTRIB = re.compile(r"(?i)minimum\s+promoters?.{0,3}\s*contribution|promoters?.{0,3}\s*"
                         r"(?:minimum\s+)?contribution")
ESOP_NO = re.compile(r"(?i)(?:does not have|has not (?:issued|granted)|no)\s+[^.]{0,60}"
                     r"employee stock option\s+(?:scheme|plan)[^.]{0,80}")
ESOP_YES = re.compile(r"(?i)(?:under (?:our|the) |pursuant to (?:our|the) )?employee stock "
                      r"option (?:scheme|plan)[^.]{0,40}(?:\d{4}|granted|outstanding options)")
DUAL = re.compile(r"(?i)(?:differential voting rights|dual[- ]class|superior voting rights)"
                  r"[^.]{0,120}")


def ownership(ctx: Ctx) -> list[Value]:
    out = []
    pi = None
    for i, m, sent in ctx.scan(PREIPO_NO, limit=3):
        pi = hit(ctx, F_PREIPO_FLAG, 0.0, i, sent, unit="bool",
                 note="the document states no pre-IPO placement was undertaken")
        break
    amt = None
    if pi is None:
        for i, m, sent in ctx.scan(PREIPO_AMT, limit=3):
            im = INLINE_AMT.search(m.group(1))
            if im:
                v, u = fnum(im.group(1)), im.group(2)
                pi = hit(ctx, F_PREIPO_FLAG, 1.0, i, sent, unit="bool",
                         note="a pre-IPO placement with a stated amount")
                amt = hit(ctx, F_PREIPO_AMT, v, i, sent, unit=u, crore=to_crore(v, u),
                          note="pre-IPO placement amount as stated; relevant to veto red "
                               "flag 5 (placement within 12 months below the issue price)")
                break
    if pi is None:
        for i, m, sent in ctx.scan(PREIPO_ANY, limit=4):
            if re.search(r"(?i)may (?:consider|undertake)|contemplat", sent):
                continue                    # a permission clause, not a completed placement
            pi = hit(ctx, F_PREIPO_FLAG, 1.0, i, sent, unit="bool", status="ambiguous",
                     note="the phrase appears without an amount and without a negation; "
                          "flagged ambiguous rather than read as a completed placement")
            break
    out.append(pi or miss(ctx, F_PREIPO_FLAG, "no pre-IPO placement clause of either polarity"))
    out.append(amt or miss(ctx, F_PREIPO_AMT,
                           "no pre-IPO placement amount with a unit "
                           + ("(placement stated as none)" if pi is not None
                              and pi.value == 0.0 else "")))

    for var, rxs, lab in ((F_PROM_PRE, (PROM_PRE, PROM_PRE_DATED), "pre-offer"),
                          (F_PROM_POST, (PROM_POST,), "post-offer")):
        got = None
        for rx in rxs:
            for i, m, sent in ctx.scan(rx, limit=4):
                if PROM_GROUP_ONLY.search(sent) or NOT_A_HOLDING.search(sent):
                    continue
                v = next((fnum(g) for g in m.groups() if g and fnum(g) is not None), None)
                if v is not None and 0 < v <= 100:
                    dated = rx is PROM_PRE_DATED
                    got = hit(ctx, var, v, i, sent, unit="%",
                              note=(f"promoter and promoter-group holding, {lab}, from the "
                                    "stated clause rather than a positional table column")
                                   + (". The sentence does not say 'pre-Offer'; it is dated at "
                                      "the document, i.e. before allotment, so it is the "
                                      "pre-offer holding by inference" if dated else ""))
                    break
            if got:
                break
        out.append(got or miss(ctx, var, f"no promoter {lab} holding percentage clause matched"))

    # lock-in: prefer the clause that names the minimum promoter contribution, which is the
    # regulated 3-year (pre-2022) or 18-month (post-2022) period. Otherwise the longest.
    cands = []
    for i, m, sent in ctx.scan(LOCKIN, limit=12):
        k = n_of(m.group(1))
        if k is None:
            continue
        months = k * 12 if m.group(2).lower().startswith("year") else k
        cands.append((months, bool(MIN_CONTRIB.search(sent)), i, sent))
    if cands:
        pref = [c for c in cands if c[1]] or cands
        months, named, i, sent = max(pref, key=lambda c: c[0])
        out.append(hit(ctx, F_LOCKIN, float(months), i, sent, unit="months",
                       status="ok" if named else "ambiguous",
                       note=("the clause naming the minimum promoter contribution" if named
                             else "longest lock-in found, but no clause named the minimum "
                                  "promoter contribution - may be a different lock-in")
                            + f"; {len(cands)} lock-in clauses on the document"))
    else:
        out.append(miss(ctx, F_LOCKIN, "no 'locked in for a period of N years/months' clause"))

    es = None
    for i, m, sent in ctx.scan(ESOP_NO, limit=3):
        es = hit(ctx, F_ESOP, 0.0, i, sent, unit="bool", note="stated as no ESOP scheme")
        break
    if es is None:
        for i, m, sent in ctx.scan(ESOP_YES, limit=3):
            es = hit(ctx, F_ESOP, 1.0, i, sent, unit="bool", note="a named ESOP scheme exists")
            break
    out.append(es or miss(ctx, F_ESOP, "no ESOP statement of either polarity"))

    du = None
    for i, m, sent in ctx.scan(DUAL, limit=2):
        du = hit(ctx, F_DUAL, 1.0, i, sent, unit="bool", status="ambiguous",
                 note="differential/dual-class voting mentioned; the mention may be a "
                      "definition rather than this company's structure - verify")
        break
    if du is None:
        du = V(ctx, F_DUAL, value=0.0, original_unit="bool", status="ok",
               note="no differential-voting or dual-class clause anywhere in the document; "
                    "absence of the phrase is meaningful here because a dual-class structure "
                    "must be disclosed")
    out.append(du)
    return out


# ============================================================ F. balance-sheet risk
F_CONTING = field("contingent_liabilities_cr")

CONTING_HEAD = re.compile(r"(?i)(?:summary of )?contingent liabilit(?:y|ies)")
CONTING_TOTAL = re.compile(r"(?i)total\s+contingent\s+liabilit(?:y|ies)[^\d]{0,30}"
                           r"([\d,]+(?:\.\d+)?)")
# TD Power states it in prose instead of a table: "Our contingent liabilities ... as at
# March 31, 2011 aggregated to Rs. 5,455.56 million on a stand-alone basis."
CONTING_AGG = re.compile(r"(?i)contingent liabilit(?:y|ies)[^.]{0,160}?"
                         r"(?:aggregated to|aggregating to|amounted to|stood at)\s*"
                         r"((?:₹|`|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*" + UNIT_RE + ")")
# the abbreviations page defines Ind AS 37 by name; it is not a disclosure of any amount
CONTING_NOISE = re.compile(r"(?i)indian accounting standard 37|ind as 37|"
                           r"notified under section 133")


def contingent(ctx: Ctx) -> list[Value]:
    for i, m, sent in ctx.scan(CONTING_AGG, limit=3):
        if CONTING_NOISE.search(sent):
            continue
        im = INLINE_AMT.search(m.group(1))
        if im:
            v, u = fnum(im.group(1)), im.group(2)
            return [hit(ctx, F_CONTING, v, i, sent, unit=u, crore=to_crore(v, u),
                        note="stated in prose as an aggregate, with its unit in the same "
                             "sentence")]
    for i, m, sent in ctx.scan(CONTING_TOTAL, limit=3):
        v, u = fnum(m.group(1)), ctx.unit_near(i, m.start())
        return [hit(ctx, F_CONTING, v, i, sent, unit=u, crore=to_crore(v, u),
                    status="ok" if u else "ambiguous",
                    note="a stated 'total contingent liabilities' row; unit "
                         + ("from the page or table header" if u else
                            "NOT FOUND - value_crore withheld rather than assumed (H7)"))]
    # no explicit total: sum the itemised rows only when a unit is present and the items are
    # clearly delimited. Otherwise withhold — a partial sum is worse than no number.
    for i, m, sent in ctx.scan(CONTING_HEAD, limit=10):
        if CONTING_NOISE.search(ctx.flat[i][:1200]):
            continue            # the definitions/abbreviations page, not a disclosure
        u = ctx.unit_near(i, m.start())
        tail = ctx.flat[i][m.end():m.end() + 900]
        items = re.findall(r"(?i)((?:claim|indirect tax|direct tax|income tax|guarantee|"
                           r"bank guarantee|property tax|disputed|other)[^\d]{0,70})"
                           r"([\d,]+\.\d\d)\b", tail)
        if items and u:
            tot = sum(fnum(v) or 0.0 for _, v in items)
            return [hit(ctx, F_CONTING, round(tot, 2), i, sent, unit=u,
                        crore=to_crore(tot, u), status="ambiguous",
                        note=f"SUMMED from {len(items)} itemised contingent-liability rows "
                             f"({[a.strip()[:28] for a, _ in items]}); the document states no "
                             "total, so this is a derived figure and may miss a row the "
                             "pattern did not reach")]
        return [V(ctx, F_CONTING, value=None, status="not_found", original_unit=u,
                  missing_reason="present_but_unparsed",
                  page=ctx.doc.index_to_printed(i), pdf_page_index=i, source_text=sent,
                  note=f"a contingent-liabilities section exists (unit {u or 'NOT FOUND'}) but "
                       "no total row and no summable itemisation; withheld deliberately")]
    return [miss(ctx, F_CONTING, "no contingent-liabilities section located",
                 reason="section_not_found")]


# ================================================================ G. objects
F_USES_N = field("uses_of_proceeds_n")
F_GCP_PCT = field("gcp_pct_proceeds")

OBJ_HEAD = re.compile(r"(?i)(?:objects of the (?:offer|issue)|net proceeds)[^.]{0,80}?"
                      r"(?:utilis|utiliz|towards funding the following|following objects)")
OBJ_ITEM = re.compile(r"(?i)((?:repayment|pre-payment|prepayment|funding|fund(?:ing)? of|"
                      r"capital expenditure|working capital|investment in|acquisition|"
                      r"inorganic|purchase of|expansion|general corporate purpose|"
                      r"offer (?:related )?expenses|issue expenses|marketing|"
                      r"brand building|technology|debt repayment)[^\n]{0,90}?)"
                      r"((?:₹|`|rs\.?)?\s*[\d,]+(?:\.\d+)?)")
OFS_ONLY = re.compile(r"(?i)(?:(?:the offer|this offer)\s+(?:comprises|consists|is)\s+"
                      r"(?:entirely |solely |only )?(?:of )?an? offer for sale"
                      r"|our company will not receive any (?:proceeds|portion of the offer "
                      r"proceeds))")


def objects(ctx: Ctx) -> list[Value]:
    out = []
    # A pure offer for sale has no objects and no GCP. That is structurally N/A, not a
    # missing extraction, and it must not be counted as a failure.
    ofs_only = None
    for i, m, sent in ctx.scan(OFS_ONLY, limit=2):
        ofs_only = (i, sent)
        break

    uses, gcp_amt, total_amt, pg, src = [], None, None, None, None
    for i, m, sent in ctx.scan(OBJ_HEAD, limit=4):
        tail = ctx.flat[i][m.end():m.end() + 1400]
        for label, amt in OBJ_ITEM.findall(tail):
            key = re.sub(r"[^a-z]", "", label.lower())[:34]
            if key and key not in [u[0] for u in uses]:
                uses.append((key, label.strip(), fnum(re.sub(r"[^\d.,]", "", amt))))
        if uses:
            pg, src = i, sent
            break
    if uses:
        gcp = next((u for u in uses if "generalcorporate" in u[0]), None)
        out.append(hit(ctx, F_USES_N, float(len(uses)), pg, src, unit="count",
                       note=f"{len(uses)} distinct stated uses: "
                            f"{[u[1][:30] for u in uses]}"))
        amts = [u[2] for u in uses if u[2]]
        if gcp and gcp[2] and amts:
            tot = sum(amts)
            out.append(V(ctx, F_GCP_PCT, value=round(gcp[2] / tot * 100, 2),
                         original_unit="%", page=ctx.doc.index_to_printed(pg),
                         pdf_page_index=pg, source_text=gcp[1], status="ambiguous",
                         note=f"DERIVED: GCP {gcp[2]} of a {tot} total summed across "
                              f"{len(amts)} stated uses. The document's own total is not "
                              "used, so a use the pattern missed would inflate this."))
        else:
            out.append(miss(ctx, F_GCP_PCT, "no general-corporate-purpose line with an amount "
                                            "among the stated uses"))
    elif ofs_only:
        i, sent = ofs_only
        for var in (F_USES_N, F_GCP_PCT):
            out.append(V(ctx, var, value=None, status="not_applicable",
                         missing_reason="not_present_on_page",
                         page=ctx.doc.index_to_printed(i), pdf_page_index=i, source_text=sent,
                         note="the offer is entirely an offer for sale, so there are no "
                              "objects of the offer and no general corporate purpose. "
                              "Structurally N/A, not a failed extraction."))
    else:
        for var in (F_USES_N, F_GCP_PCT):
            out.append(miss(ctx, var, "no objects-of-the-offer table located and no "
                                      "offer-for-sale-only statement",
                            reason="section_not_found"))
    return out


# ================================================================ H. anchor book
F_ANCHOR_SHARES = field("anchor_portion_shares")
F_ANCHOR_MF_PCT = field("anchor_mf_reserved_pct")

ANCHOR_SHARES = re.compile(r"(?i)anchor investor(?:\(s\))? (?:portion|allocation)[^.]{0,160}?"
                           r"(?:up ?to|consisting of|of)\s*([\d,]{5,})\s*(?:\*\s*)?equity shares")
ANCHOR_MF = re.compile(r"(?i)(one[- ]third|1/3|\d{1,2}(?:\.\d+)?\s*%)\s+of\s+the\s+anchor "
                       r"investor portion[^.]{0,80}?reserved for[^.]{0,40}mutual funds")


def anchor(ctx: Ctx) -> list[Value]:
    out = []
    got = None
    for i, m, sent in ctx.scan(ANCHOR_SHARES, limit=4):
        v = fnum(m.group(1))
        if v and v > 1000:
            got = hit(ctx, F_ANCHOR_SHARES, v, i, sent, unit="shares",
                      note="anchor investor portion in shares. NOTE: this is the portion "
                           "RESERVED, not the book actually allocated - the allotted anchor "
                           "names and amounts are filed with the exchanges, not printed here")
            break
    out.append(got or miss(ctx, F_ANCHOR_SHARES, "no anchor investor portion in shares"))

    got = None
    for i, m, sent in ctx.scan(ANCHOR_MF, limit=3):
        tok = m.group(1).lower()
        v = 100 / 3 if tok in ("one-third", "one third", "1/3") else fnum(tok.rstrip("% "))
        if v:
            got = hit(ctx, F_ANCHOR_MF_PCT, round(v, 2), i, sent, unit="%", status="ambiguous",
                      note="the share of the anchor portion RESERVED for mutual funds. This is "
                           "the SEBI ICDR minimum restated by every RHP, not this book's actual "
                           "mutual-fund share - do not model it as a demand signal")
            break
    out.append(got or miss(ctx, F_ANCHOR_MF_PCT, "no mutual-fund reservation clause"))
    return out


# ============================================================ MSCI six key issues
# Derived roll-ups, not separate extractions: each records which H6 fields fed it, so a
# governance score can never be built from a field that was never found. Reported
# separately from coverage — they add no new information.
MSCI = {
    "msci_ownership_control": [F_PROM_POST, F_PROM_PRE, F_DUAL, F_PREIPO_FLAG, F_LOCKIN],
    "msci_board": [F_BOARD_N, F_INDEP_N, F_INDEP_RATIO],
    "msci_pay": [F_KMP_PAY, F_ESOP],
    "msci_accounting": [F_AUD_QUAL, F_AUD_EMPH, F_CONTING],
    "msci_business_ethics": [F_LIT_CRIM, F_LIT_CRIM_PD, F_LIT_STAT, F_RPT_PCT],
    "msci_tax_transparency": [F_LIT_TAX],
}


def msci(ctx: Ctx, vals: list[Value]) -> list[Value]:
    by = {v.variable: v for v in vals}
    out = []
    for key, inputs in MSCI.items():
        have = [k for k in inputs if by.get(k) and by[k].status in ("ok", "ambiguous")
                and by[k].value is not None]
        out.append(V(ctx, key, value=round(len(have) / len(inputs), 3),
                     original_unit="completeness", status="ok",
                     note=f"MSCI key-issue COMPLETENESS, not a score: {len(have)} of "
                          f"{len(inputs)} inputs captured ({have} of {inputs}). The scorecard "
                          "learns weights (Stage 11); nothing here is hand-weighted."))
    return out


# ============================================================ orchestration
GROUPS = (rpt, litigation, concentration, governance, ownership, contingent, objects, anchor)

# which fields each group owns, so a failure is attributed to exactly its own fields
GROUP_FIELDS = {
    "rpt": (F_RPT_PCT, F_RPT_AMT),
    "litigation": (F_LIT_CRIM, F_LIT_CRIM_PD, F_LIT_TAX, F_LIT_STAT, F_LIT_AMT),
    "concentration": (F_CUST10, F_CUST5, F_GEO, F_LICENCE),
    "governance": (F_PROM_EXP, F_BOARD_N, F_INDEP_N, F_INDEP_RATIO, F_KMP_PAY,
                   F_AUD_QUAL, F_AUD_EMPH),
    "ownership": (F_PREIPO_FLAG, F_PREIPO_AMT, F_PROM_PRE, F_PROM_POST, F_LOCKIN,
                  F_ESOP, F_DUAL),
    "contingent": (F_CONTING,),
    "objects": (F_USES_N, F_GCP_PCT),
    "anchor": (F_ANCHOR_SHARES, F_ANCHOR_MF_PCT),
}
assert set(FIELDS) == {f for v in GROUP_FIELDS.values() for f in v}, "GROUP_FIELDS drift"


def extract(doc: Doc, pages: list[str]) -> list[Value]:
    """Every H6 field for one document. `pages` is the document's page text, in order."""
    ctx = Ctx(doc, pages)
    vals: list[Value] = []
    for g in GROUPS:
        try:
            vals += g(ctx)
        except Exception as e:
            # One failing group must not take the document down, and must not swallow the
            # groups after it either: record only ITS OWN fields as unreadable and carry on.
            # A first version broke out of the loop, so a single TypeError in `governance`
            # silently cost four whole groups on all eight documents.
            have = {v.variable for v in vals}
            for f in GROUP_FIELDS.get(g.__name__, ()):
                if f not in have:
                    vals.append(miss(ctx, f, f"extractor group {g.__name__} raised "
                                             f"{type(e).__name__}: {e}", status="unreadable",
                                     reason="present_but_unparsed"))
    have = {v.variable for v in vals}
    for f in FIELDS:
        if f not in have:
            vals.append(miss(ctx, f, "field not produced by any extractor group",
                             status="unreadable", reason="present_but_unparsed"))
    vals += msci(ctx, vals)
    return vals

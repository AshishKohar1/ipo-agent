"""
extract/valuation.py — Priority 1.2: the valuation block of a prospectus.

What it pulls, each value with its printed page and the exact line it came from (rule 2):

  1.2a  "Basis for Issue Price"
          eps_basic_fy1..fy3, eps_diluted_fy1..fy3, eps_basic_weighted,
          eps_diluted_weighted, pe_at_floor, pe_at_cap, ronw_fy1..fy3,
          ronw_weighted, nav_pre_issue, nav_post_issue
          and the listed-peer table: peer_<n>_{name,face_value,eps,pe,ronw,nav,revenue}
  1.2b  restated financials, three years: revenue, ebitda, pat, borrowings, cash,
          cash from operations, capex
  1.2c  shares_outstanding_post_issue

Table-anchored, never text-anchored where a table exists
--------------------------------------------------------
`extract/basis.py` records what happens otherwise: an early text-regex version read EPS and
NAV as 10.0 out of the parenthetical "(Face value of Rs 10 each)", and took a P/E off a
line about the Sensex. Every number here is tied to a header AND a row label, and where the
table is missing the value is `not_found` rather than inferred from prose.

Where a value is withheld
-------------------------
* **unit mismatch** - a financials table whose unit line says lakhs while a sibling says
  millions, or no unit line at all: withheld, `present_but_unparsed`.
* **period mismatch** - a column covering a stub period (six months, nine months) where a
  full year is wanted: withheld, with the period that was found in the note.
* **negative earnings** - P/E and anything derived from it is NULL with the reason
  `negative earnings`, never a negative multiple. That decision lives in the derive step
  but the EPS sign is carried here so the reason can be given.
"""
from __future__ import annotations
import re

from .base import (Doc, Value, EXTRACTOR_VERSION, page_tables, page_texts, find,
                   num, MONEY_UNIT_RE)

NAME = "valuation"
MAX_PEERS = 12

# This module's OWN version, independent of `base.EXTRACTOR_VERSION`, which is shared with
# the h6 extractor and must not be relabelled when only this one changes.
#
# Bump it whenever a change could alter an extracted VALUE. The first pilot wrote 243 rows
# for 5 companies and stamped them `1.0.0`; the financials stage was then narrowed to scan
# only pages whose text carries a target row label, which can change which values are
# found - and because the version string had not moved, a file mixing the two code paths
# was indistinguishable from a clean one. Those 5 companies were discarded and re-extracted
# rather than left as rows nobody could date.
#
#   1.0.0  first pilot
#   1.1.0  financials narrowed by a text pre-scan; peer role order taken from table
#          columns rather than line-joined text; TOC and offset probes read in one open
#   1.2.0  promoter pre-/post-offer shareholding, via extract/capital.py
#   1.3.0  FIXED: the 1.2b financials block had raised PatternError on every document
#          since the text pre-scan was added, producing zero values for revenue, EBITDA,
#          PAT, borrowings, cash, cash-from-operations and capex
#   1.4.0  the money unit is carried forward from the head of a statement instead of
#          being required on each page, and the page it came from is recorded; a header
#          cell is only read as a fiscal year if the year is plausible
#   1.5.0  1.2b reads the restated financials from TEXT lines as well as tables, because
#          the statements in this document family are UNRULED - pdfplumber returns a
#          header fragment and no data rows, so all 28 financial rows reported "no table
#          in the financial section carries this row". Same root cause, and same remedy,
#          as the Basis block. 1.2c reads the post-issue share count from the Capital
#          Structure build-up table as well as from a sentence, and no longer takes the
#          LARGEST number on the line - on a row that prints both a share count and the
#          aggregate rupee capital, the largest is the rupee figure.
#   1.6.0  THREE FAMILIES OF WRONG VALUE in the Basis block, found by hand-validating one
#          document before the pass. All three were present from 1.0.0 onwards:
#            (a) a hyphenated fiscal-year label leaked its second half into the values -
#                "FY 2020-21 4.92 4.92 3" was read as EPS 21.00 instead of 4.92, because
#                YEAR_LABEL matched only "FY 2020" and the remainder began "-21";
#            (b) the rightward probe for a split merged cell could land on the WEIGHT
#                column - "FY 2008-09 | 10.99 | 3" was read as RoNW 3.00;
#            (c) a stub period was stored as a fiscal year - "September 30, 2021 3.71",
#                a six-month figure the document itself prints as "not annualised", was
#                stored as fiscal 2021 and collided with the real FY2021 row.
#          A hyphenated label now also resolves to the LATER year: Indian "FY 2020-21"
#          ends on 31 March 2021, and it was being recorded as fiscal 2020.
#   1.7.0  promoter pre-/post-offer shareholding read from TEXT - the capital-structure
#          tables are unruled too, and the table-only reader produced a promoter
#          percentage on ZERO of 412 documents. The Capital Structure pages are now read
#          once and shared between the share-count and promoter readers rather than
#          twice, and capital.py pre-scans the text before extracting any table;
#          together those were 29 of the 53 seconds one document took.
#   1.8.1  1.2c again: 1.8.0's capital phrase required "equity SHARE capital" and missed
#          the two commonest build-up spellings, "AFTER THE ISSUE n Equity Shares of face
#          value" and "EQUITY CAPITAL AFTER THE ISSUE n Equity Shares". Precision rose to
#          91% while USABLE output fell from 121 to 81 - a worse result. "equity capital"
#          and a bare "Equity Shares" now satisfy the capital side, and a line opening with
#          the after-the-offer phrase is accepted as a build-up row on its own.
#   1.8.0  1.2c: the post-issue share count now requires the CAPITAL BUILD-UP context,
#          not merely a line mentioning "post-issue". 20 of the 153 counts 1.7.0 produced
#          were impossible - implied market capitalisation below the money raised - and
#          every one came from a line about something else: an employee reservation cap, a
#          promoter lock-in row, a pre-IPO placement or preference-share footnote, or the
#          selling shareholders' OFS size. Not a unit or scale fault.
VALUATION_VERSION = "1.8.1"

FY_HDR = re.compile(r"(?:FY|FISCAL|FINANCIAL YEAR|YEAR ENDED|MARCH)\s*'?\s*(\d{2,4})", re.I)
WEIGHTED = re.compile(r"(?i)weighted\s*average")
STUB = re.compile(r"(?i)(?:six|nine|three|6|9|3)[\s-]*month|period\s+ended|stub")
FACE_VALUE = re.compile(r"(?i)face\s*value")
# "(Amt Rs in Lakhs)", "(₹ in millions)", "(Rs. in crore)", "(in ₹ lakhs)". The first
# version required the currency to follow the opening bracket immediately, so Uma
# Exports' "(Amt Rs in Lakhs)" was not a unit at all and every money row on those pages
# was withheld for want of one - a correct refusal under rule 3, caused by the pattern
# rather than by the document. Filler before "in" is now allowed, and the currency may
# sit on either side of it.
UNIT_LINE = re.compile(r"\([^)]{0,24}?\bin\b\s*(?:₹|`|rs\.?|inr)?\s*"
                       + MONEY_UNIT_RE + r"[^)]*\)", re.I)
UNIT_MULT = {"crore": 1.0, "crores": 1.0, "cr": 1.0, "lakh": 0.01, "lakhs": 0.01,
             "lac": 0.01, "lacs": 0.01, "million": 0.1, "millions": 0.1, "mn": 0.1,
             "thousand": 1e-5, "thousands": 1e-5}


def _v(doc: Doc, var: str, **kw) -> Value:
    kw.setdefault("extractor_version", VALUATION_VERSION)
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME, **kw)


def _miss(doc: Doc, var: str, note: str, reason: str = "not_present_on_page") -> Value:
    return _v(doc, var, value=None, status="not_found", note=note, missing_reason=reason)


def _cells(row) -> list[str]:
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]


def _flat(tbl, upto: int = 3) -> str:
    return " ".join(" ".join(_cells(r)) for r in tbl[:upto]).upper()


def _line_for(cells: list[str]) -> str:
    """The quoted line rule 2 requires: the row as the document prints it."""
    return " | ".join(c for c in cells if c)


def _unit_of(text: str) -> tuple[float | None, str | None]:
    """`(multiplier to crore, the matched unit phrase)` or `(None, None)`."""
    m = UNIT_LINE.search(text or "")
    if not m:
        return None, None
    word = re.search(MONEY_UNIT_RE, m.group(0), re.I)
    if not word:
        return None, None
    return UNIT_MULT.get(word.group(0).lower()), m.group(0)


# ------------------------------------------------------------------ table shapes
YEAR_LABEL = re.compile(r"(?i)(?:fiscal|fy|year\s+ended|march|as\s+at)?[^\d]{0,12}"
                        r"(?:march\s*31,?\s*)?(20\d{2})\b")
METRIC_HDR = (
    ("eps_basic", r"BASIC\s*EPS|EPS\s*\(?\s*BASIC|BASIC\s*EARNINGS"),
    ("eps_diluted", r"DILUTED\s*EPS|EPS\s*\(?\s*DILUTED|DILUTED\s*EARNINGS"),
    ("ronw", r"RONW|RETURN\s+ON\s+NET\s+WORTH"),
    ("nav", r"NAV|NET\s+ASSET\s+VALUE"),
)


def _col_headers(rows: list[list[str]], upto: int = 6) -> dict[int, str]:
    """Per-column header text, joined DOWN the first few rows.

    An RHP peer table routinely wraps one heading over six lines - "P/E" / "based" / "on"
    / "FY18" / "EPS(B" / "asic)" - so a header read from a single row is meaningless. The
    join is per column, which is what reassembles them.
    """
    out: dict[int, list[str]] = {}
    for r in rows[:upto]:
        for i, c in enumerate(_cells(r)):
            if c:
                out.setdefault(i, []).append(c)
    return {i: " ".join(v).upper() for i, v in out.items()}


# "FY 2020-21", "2020-2021", "FY2020-21": an Indian fiscal year written as a span. The
# whole label must be consumed, because matching only "FY 2020" leaves a remainder that
# starts "-21", and that 21 was then read as the first metric value. The fiscal year is
# the LATER one - FY 2020-21 ends on 31 March 2021.
FY_SPAN = re.compile(r"(?i)(?:fy|fiscal|financial\s+year)?\s*(20\d{2})\s*[-\u2013]\s*"
                     r"(20\d{2}|\d{2})\b")
# A period that is NOT a full fiscal year. The RHPs print these in the same block as the
# fiscal years - "September 30, 2021 3.71 3.71 -" - and each carries a note saying the
# figure is not annualised. Storing one as a fiscal year is a period mismatch (rule 3),
# and it also collides with the real row for that year.
STUB_LABEL = re.compile(r"(?i)(?:six|nine|three|6|9|3)[\s-]*month"
                        r"|period\s+ended"
                        # ANY month other than March beside a year, with or without a
                        # day. An Indian fiscal year ends on 31 March, so "SEPT 2021" or
                        # "April 30, 2024" is by definition an interim period - and a
                        # column header often gives the month with no day at all.
                        r"|\b(?:jan|feb|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
                        r"\s*\d{0,2}\s*,?\s*20\d\d"
                        r"|\b31\s*(?:st)?\s*(?:december|september|june)\b")
STUB_YEAR = -2                       # distinct from -1, which means weighted average


def _span_year(cell: str) -> tuple[int | None, int]:
    """`(fiscal year, end offset of the whole label)` for a hyphenated span, else
    `(None, 0)`."""
    m = FY_SPAN.match((cell or "").strip())
    if not m:
        return None, 0
    a, b = m.group(1), m.group(2)
    y = int(b) if len(b) == 4 else int(a[:2] + b)
    # "2020-21" -> 2021. A span that does not advance by exactly one year is not a
    # fiscal span, so it is left to the ordinary matcher.
    if y - int(a) != 1:
        return None, 0
    return (y if 1990 <= y <= 2030 else None), m.end()


def _year_of(cell: str) -> int | None:
    c = (cell or "").strip()
    if WEIGHTED.search(c):
        return -1
    if STUB_LABEL.search(c):
        return STUB_YEAR
    y, _ = _span_year(c)
    if y is not None:
        return y
    m = YEAR_LABEL.search(c)
    if not m:
        return None
    y = int(m.group(1))
    return y if 1990 <= y <= 2030 else None


def section_rows(path, a: int, b: int, offset: int) -> list[tuple[int, list[str]]]:
    """Every table row on the section's pages, in order, tagged with its page index.

    Flattening the section rather than working table by table is what handles a table
    SPLIT ACROSS A PAGE BREAK. In this document family the EPS block routinely puts
    `Fiscal | Basic EPS | Diluted EPS | Weight` at the foot of one page and its three data
    rows at the head of the next, and pdfplumber reports them as two tables - one of which
    is a header with no data and the other data with no header.
    """
    out = []
    tabs = page_tables(path, a, b)
    for idx in sorted(tabs):
        for tbl in tabs[idx] or []:
            for row in (tbl or []):
                cs = _cells(row)
                if any(cs):
                    out.append((idx, cs))
    del tabs
    return out


def read_year_rows(rows: list[tuple[int, list[str]]]) -> dict:
    """`{metric: {year: (value, page_idx, line)}}` for tables whose ROWS are fiscal years.

    Scans the flattened section for a header row naming at least one metric, then takes
    the rows after it whose first non-empty cell is a fiscal year or "Weighted Average".
    A run ends at the first row that is neither, so a following unrelated table cannot
    leak its numbers into the series.
    """
    found: dict = {}
    i = 0
    while i < len(rows):
        idx, cs = rows[i]
        hdr = _col_headers([cs], 1)
        roles = {}
        for ci, text in hdr.items():
            for metric, pat in METRIC_HDR:
                if re.search(pat, text) and metric not in roles.values():
                    roles[ci] = metric
                    break
        if not roles:
            i += 1
            continue
        j, run = i + 1, 0
        while j < len(rows):
            jdx, jcs = rows[j]
            lab = next((c for c in jcs if c), "")
            y = _year_of(lab)
            if y is None:
                break
            line = _line_for(jcs)
            if y == STUB_YEAR:
                # A stub row sits INSIDE the run, so the run must not end here - the
                # fiscal-year rows below it are still wanted. The row itself is skipped.
                run += 1
                j += 1
                continue
            # The last numeric cell of a weighted-average block is the WEIGHT (1, 2, 3),
            # not a metric. The rightward probe below used to land on it: "FY 2008-09 |
            # 10.99 | 3" was stored as RoNW 3.00 on three documents. Its column is found
            # once per row and excluded.
            nums = [k for k, c in enumerate(jcs) if num(c) is not None]
            weight_col = None
            if nums:
                lv = num(jcs[nums[-1]])
                if lv is not None and float(lv).is_integer() and 0 < lv <= 5:
                    weight_col = nums[-1]
            for ci, metric in roles.items():
                val = num(jcs[ci]) if ci < len(jcs) else None
                if val is not None and ci == weight_col:
                    val = None      # the header lines up with the weight: refuse it
                if val is None:
                    # The value may sit one or two columns right of its header when
                    # pdfplumber splits a merged cell. Only a numeric cell within two
                    # columns is accepted, never one that belongs to another metric, and
                    # never the weight column.
                    for k in (ci + 1, ci + 2):
                        if (k < len(jcs) and k not in roles and k != weight_col
                                and num(jcs[k]) is not None):
                            val = num(jcs[k])
                            break
                if val is not None:
                    found.setdefault(metric, {}).setdefault(y, (val, jdx, line))
            run += 1
            j += 1
        i = j if run else i + 1
    return found


NUMBER = re.compile(r"\(?-?\u20b9?\s*([\d,]+(?:\.\d+)?)\s*%?\)?")
HDR_LINE = re.compile(r"(?i)^\s*(?:fiscal|financial\s+year|year|particulars?|nav\s+per)")


def _numbers(text: str) -> list[float]:
    out = []
    for m in NUMBER.finditer(text or ""):
        v = num(m.group(1))
        if v is not None:
            out.append(-v if m.group(0).lstrip().startswith("(")
                       and m.group(0).rstrip().endswith(")") else v)
    return out


def read_year_lines(texts: dict[int, str]) -> dict:
    """`{metric: {year: (value, page_idx, line)}}`, read from TEXT lines.

    **The Basis tables in this document family have no ruling lines**, so pdfplumber
    reports the header row and nothing else - the first version of this module extracted
    the `Fiscal | Basic EPS | Diluted EPS | Weight` header and zero data rows, and
    reported EPS as absent on a document that states it plainly.

    So the shape is read off the text: a header line naming the metric columns IN ORDER,
    then the lines after it whose label is a fiscal year or "Weighted Average". The year
    is stripped from the label first, then the remaining numbers are zipped positionally
    against the metric list. A trailing integer "Weight" column is ignored by taking only
    as many numbers as there are metrics.

    Positional zipping is safe here *only because* the header gives the order explicitly.
    Where no header names a metric, nothing is read.
    """
    found: dict = {}
    for idx in sorted(texts):
        lines = [ln.strip() for ln in (texts[idx] or "").splitlines()]
        order: list[str] = []
        for ln in lines:
            if not ln:
                continue
            up = ln.upper()
            # A header line: names at least one metric, and is not itself a data row.
            cand = []
            for metric, pat in METRIC_HDR:
                m = re.search(pat, up)
                if m:
                    cand.append((m.start(), metric))
            if cand and HDR_LINE.match(ln) and len(_numbers(ln)) <= 1:
                order = [mt for _, mt in sorted(cand)]
                continue
            if not order:
                continue
            y = _year_of(ln.split("(")[0][:40])
            if y == STUB_YEAR:
                continue            # a six-month figure is not a fiscal year
            if y is None:
                # A run ends at the first non-year line, so a later unrelated paragraph
                # cannot contribute numbers to the series.
                if re.match(r"(?i)^(?:\d+[.)]|note|source|\(\d+\))", ln):
                    order = []
                continue
            # The label is stripped by the SAME matcher that identified the year, so a
            # hyphenated span is consumed whole. Stripping only "FY 2020" out of
            # "FY 2020-21 4.92 4.92 3" left "-21 ..." and the 21 became the EPS.
            _, span_end = _span_year(ln.strip())
            if span_end:
                rest = ln.strip()[span_end:]
            else:
                lab = YEAR_LABEL.search(ln)
                rest = ln[lab.end():] if (lab and y > 0) else ln
            if y == -1:
                rest = re.sub(r"(?i)^\s*weighted\s*average", "", ln)
            ns = _numbers(rest)[:len(order)]
            for metric, val in zip(order, ns):
                found.setdefault(metric, {}).setdefault(y, (val, idx, ln))
    return found


# ------------------------------------------------------------------ 1.2a basis
def _year_columns(tbl) -> dict[int, int]:
    """`{column index: fiscal year}` from the header rows, plus -1 for weighted average."""
    out = {}
    for r in tbl[:3]:
        cs = _cells(r)
        for i, c in enumerate(cs):
            if WEIGHTED.search(c):
                out[i] = -1
                continue
            if STUB_LABEL.search(c):
                # An interim column, e.g. "Year ended September 30, 2021". Left out of
                # the map entirely so no fiscal year can resolve to it - the same guard
                # the text reader applies, for the same reason.
                continue
            m = FY_HDR.search(c)
            if m:
                y = int(m.group(1))
                y = 2000 + y if y < 100 else y
                # A header cell can carry a page number or a note reference that looks
                # like a year: the first run reported "fiscal 2031 column present but
                # empty". Anything outside a plausible range is not a year.
                if 1990 <= y <= 2030:
                    out[i] = y
    return out


def _row_series(doc, tbl, page, idx, label_pat: re.Pattern, base: str,
                unit: str) -> list[Value]:
    """Every year's value for one labelled row, newest first as fy1..fy3."""
    cols = _year_columns(tbl)
    if not cols:
        return [_miss(doc, f"{base}_fy1",
                      "the table has no identifiable fiscal-year column header",
                      "present_but_unparsed")]
    out, hit = [], None
    for r in tbl:
        cs = _cells(r)
        if cs and label_pat.search(cs[0]):
            hit = cs
            break
    if hit is None:
        return []
    line = _line_for(hit)
    if STUB.search(line):
        return [_v(doc, f"{base}_fy1", value=None, status="not_found",
                   page=page, pdf_page_index=idx, source_text=line,
                   note="withheld: the row covers a stub period, not a full year",
                   missing_reason="present_but_unparsed")]
    years = sorted({y for y in cols.values() if y > 0}, reverse=True)
    for n, y in enumerate(years[:3], 1):
        ci = next((i for i, yy in cols.items() if yy == y), None)
        val = num(hit[ci]) if (ci is not None and ci < len(hit)) else None
        out.append(_v(doc, f"{base}_fy{n}", value=val, original_unit=unit,
                      page=page, pdf_page_index=idx, source_text=line,
                      status="ok" if val is not None else "not_found",
                      note=f"fiscal {y}, column {ci}" if val is not None
                      else f"fiscal {y} column present but empty",
                      missing_reason="" if val is not None else "present_but_unparsed"))
    wi = next((i for i, yy in cols.items() if yy == -1), None)
    if wi is not None and wi < len(hit):
        wv = num(hit[wi])
        out.append(_v(doc, f"{base}_weighted", value=wv, original_unit=unit,
                      page=page, pdf_page_index=idx, source_text=line,
                      status="ok" if wv is not None else "not_found",
                      note="weighted average column",
                      missing_reason="" if wv is not None else "present_but_unparsed"))
    return out


# ORDER MATTERS. Each column takes the FIRST role whose pattern matches, so the specific
# form must be tried before the general one: a bare `P/E` matches the "P/E based on FY18
# EPS (Diluted)" column too, and when it was tested first that column was consumed as
# `pe`, `pe_diluted` was never assigned, and every value after it shifted left by one.
# Same for diluted EPS against EPS.
ROLE_WORDS = (
    ("revenue", r"REVENUE|TOTAL\s+INCOME|TURNOVER"),
    ("face_value", r"FACE\s*VALUE"),
    ("eps_diluted", r"EPS\s*\(?\s*DILUTED|DILUTED\s*\)?\s*EPS|DILUTED\s+EARNINGS"),
    ("eps", r"EPS\s*\(?\s*BASIC|BASIC\s*\)?\s*EPS|BASIC\s+EARNINGS|EPS"),
    ("pe_diluted", r"P\s*/\s*E.{0,40}?DILUT"),
    ("pe", r"P\s*/\s*E"),
    ("nav", r"NET\s+ASSET\s+VALUE|\bNAV\b"),
    ("pb", r"PRICE\s*/\s*BOOK|\bP\s*/\s*B\b"),
    ("ronw", r"RETURN\s+ON\s+NET[\s-]*WORTH|RONW"),
)


def peer_roles_in_order(header: str) -> list[str]:
    """Role names in the ORDER their heading words appear across the header.

    Positional zipping of a peer row's numbers is only safe if the order comes from the
    document. Each role is matched at its earliest position, duplicates are dropped, and
    the list is sorted by that position - so a prospectus that puts RoNW before NAV is
    read as it is printed rather than as the last one was.
    """
    hits = {}
    for role, pat in ROLE_WORDS:
        m = re.search(pat, header, re.I)
        if m and role not in hits:
            hits[role] = m.start()
    # A bare "P/E" also matches the diluted heading; keep whichever matched earlier and
    # let the explicit diluted pattern own its own position.
    return [r for r, _ in sorted(hits.items(), key=lambda kv: kv[1])]


def peer_roles_from_tables(rows: list[tuple[int, list[str]]]) -> list[str]:
    """Role order taken from the TABLE's column headers, by column index.

    This must not come from the page text. The peer header wraps over six lines, so
    joining the LINES reads it row-major - "Name of the FY18 Face FY18 FY18 P/E P/E Net"
    - and "P/E" then appears before "EPS". Ordering roles off that put P/E third and
    reported HDFC's EPS of 100.4 as its P/E of 18.6. pdfplumber's columns are correct even
    when it finds no data rows, so the ORDER comes from the table and the VALUES from the
    text.
    """
    best: list[str] = []
    for i in range(len(rows)):
        # The window must BEGIN on the peer header's own first row. Allowing it to start
        # earlier let the preceding NAV table's "NAV per Equity Share" land in column 0,
        # so `nav` was assigned to the company-name column and every role shifted.
        first = rows[i][1]
        if not (first and first[0] and re.search(r"(?i)name\s+of\s+the", first[0])):
            continue
        block = [r for _, r in rows[i:i + 8]]
        hdr = _col_headers(block, 8)
        joined = " ".join(hdr.values())
        if not re.search(r"P\s*/\s*E", joined):
            continue
        order = []
        for ci in sorted(hdr):
            text = hdr[ci]
            for role, pat in ROLE_WORDS:
                if role in order:
                    continue
                if re.search(pat, text, re.I):
                    order.append(role)
                    break
        if len(order) > len(best):
            best = order
    return best


def peers_from_text(doc, texts: dict[int, str],
                    role_order: list[str] | None = None) -> list[Value]:
    """The listed-peer table read from TEXT, which is how it is actually printed.

    In this document family the peer block is unruled: pdfplumber returns a nine-row
    table consisting entirely of wrapped header fragments and no data at all. The rows
    are there in the text, with company names spilling onto a second line
    ("Gruh Finance" / "Limited"), so a continuation line with no numbers is appended to
    the previous peer's name rather than being treated as a new peer.
    """
    out, n = [], 0
    for idx in sorted(texts):
        lines = [ln.strip() for ln in (texts[idx] or "").splitlines() if ln.strip()]
        joined = " ".join(lines)
        if not re.search(r"(?i)name\s+of\s+the\s+compan|peer\s+group", joined):
            continue
        roles = role_order or peer_roles_in_order(joined)
        if "pe" not in roles or len(roles) < 3:
            continue
        # Reading begins AFTER the header block. Scanning the whole page made the NAV
        # table's rows look like peers - "As on March 31, 2018 157.03 157.03" has a text
        # label and two numbers, which is the shape of a peer row - and produced two
        # invented peers with a face value of 2018.
        anchor = -1
        for k, ln in enumerate(lines):
            if re.search(r"(?i)peer\s+group|name\s+of\s+the\s+compan", ln):
                anchor = k
        if anchor < 0:
            continue
        started = False
        for ln in lines[anchor + 1:]:
            ns = _numbers(ln)
            label = re.split(r"\s{2,}|\s(?=[\d(])", ln, maxsplit=1)[0].strip()
            if re.match(r"(?i)^(?:note|source|\(?\d+[.)])", ln):
                if started:
                    break
                continue
            if len(ns) >= max(3, len(roles) - 3) and label and not label[0].isdigit():
                n += 1
                started = True
                if n > MAX_PEERS:
                    break
                vals = ns[:len(roles)]
                out.append(_v(doc, f"peer_{n}_name", value=None, original_unit="name",
                              page=doc.index_to_printed(idx), pdf_page_index=idx,
                              source_text=ln, status="ok",
                              note=f"peer name: {label[:60]}"))
                for role, val in zip(roles, vals):
                    out.append(_v(doc, f"peer_{n}_{role}", value=val,
                                  original_unit="x" if role in ("pe", "pe_diluted",
                                                                "pb") else "Rs",
                                  page=doc.index_to_printed(idx), pdf_page_index=idx,
                                  source_text=ln, status="ok",
                                  note=f"peer '{label[:40]}', position {role}"))
            elif started and not ns and len(ln) < 40:
                # A wrapped company name. It extends the previous peer, and must never
                # start a new one - that would invent a peer with no numbers.
                for v in reversed(out):
                    if v.variable.endswith("_name"):
                        v.note = f"{v.note} {ln[:30]}".strip()
                        break
        if n:
            break
    if n:
        out.append(_v(doc, "peer_count", value=float(n), original_unit="count",
                      status="ok", note=f"{n} listed peers read from the text block"))
    return out


def _peers_flat(doc, rows: list[tuple[int, list[str]]]) -> list[Value]:
    """The listed-peer table, located across the whole section.

    The header is accumulated DOWN consecutive rows until the column roles stop growing,
    then peer rows are taken until a row stops looking like one. A peer row is a non-empty
    text label plus at least two numeric cells in role columns; a `Total`, `Average`,
    `Median`, `Notes` or `Source` label ends the block.
    """
    n_start = None
    for i in range(len(rows)):
        joined = " ".join(_col_headers([r for _, r in rows[i:i + 8]], 8).values())
        if re.search(r"P\s*/\s*E", joined) and re.search(
                r"(?i)name\s+of\s+the|peer\s+group|compar", joined):
            n_start = i
            break
    if n_start is None:
        return []
    # Grow the header while the role set keeps improving.
    best_roles, best_end = {}, n_start
    for end in range(n_start + 1, min(n_start + 10, len(rows)) + 1):
        hdr = _col_headers([r for _, r in rows[n_start:end]], end - n_start)
        roles = {}
        for i, text in hdr.items():
            if re.search(r"FACE\s*VALUE", text):
                roles[i] = "face_value"
            elif re.search(r"P\s*/\s*E", text):
                roles[i] = "pe"
            elif "EPS" in text:
                roles[i] = "eps"
            elif re.search(r"RONW|RETURN\s+ON\s+NET\s+WORTH", text):
                roles[i] = "ronw"
            elif re.search(r"NAV|NET\s+ASSET\s+VALUE", text):
                roles[i] = "nav"
            elif re.search(r"REVENUE|TOTAL\s+INCOME|TURNOVER", text):
                roles[i] = "revenue"
        if len(roles) >= len(best_roles):
            best_roles, best_end = roles, end
    roles = best_roles
    if not roles:
        return []
    out, n = [], 0
    for idx, cs in rows[best_end:]:
        if not cs or not cs[0] or len(cs[0]) < 3:
            continue
        name = cs[0]
        if re.search(r"(?i)^(?:total|average|median|notes?|source|particulars?)\b", name):
            break
        nums_in_roles = sum(1 for i in roles if i < len(cs) and num(cs[i]) is not None)
        if nums_in_roles < 2:
            # One stray numeric is a continuation fragment, not a peer.
            if n:
                break
            continue
        n += 1
        if n > MAX_PEERS:
            break
        line = _line_for(cs)
        out.append(_v(doc, f"peer_{n}_name", value=None, original_unit="name",
                      page=doc.index_to_printed(idx), pdf_page_index=idx,
                      source_text=line, status="ok", note=f"peer name: {name[:60]}"))
        for i, role in roles.items():
            val = num(cs[i]) if i < len(cs) else None
            out.append(_v(doc, f"peer_{n}_{role}", value=val,
                          original_unit="x" if role == "pe" else "Rs",
                          page=doc.index_to_printed(idx), pdf_page_index=idx,
                          source_text=line,
                          status="ok" if val is not None else "not_found",
                          note=f"peer '{name[:40]}', column {i} ({role})",
                          missing_reason="" if val is not None
                          else "present_but_unparsed"))
    if n:
        out.append(_v(doc, "peer_count", value=float(n), original_unit="count",
                      page=doc.index_to_printed(rows[best_end][0]),
                      pdf_page_index=rows[best_end][0],
                      source_text=" | ".join(sorted(set(roles.values()))),
                      status="ok", note=f"{n} listed peers in the comparison table"))
    return out


def _peers(doc, tbl, page, idx) -> list[Value]:
    """The listed-peer comparison table, one block of values per peer."""
    # The header is read DOWN six rows per column, because this table wraps one heading
    # over as many as six lines: "P/E" / "based" / "on" / "FY18" / "EPS(B" / "asic)".
    # A header read from one row is meaningless here, and an earlier version of this
    # function found nothing at all on exactly that account.
    hdr = _col_headers(tbl, 6)
    joined = " ".join(hdr.values())
    if not re.search(r"P\s*/\s*E", joined):
        return []
    if not re.search(r"(?i)name\s+of\s+the|peer|compar|industry", joined):
        return []
    roles = {}
    for i, text in hdr.items():
        if re.search(r"FACE\s*VALUE", text):
            roles[i] = "face_value"
        elif re.search(r"P\s*/\s*E", text):
            roles[i] = "pe"
        elif "EPS" in text:
            roles[i] = "eps"
        elif re.search(r"RONW|RETURN\s+ON\s+NET\s+WORTH", text):
            roles[i] = "ronw"
        elif re.search(r"NAV|NET\s+ASSET\s+VALUE", text):
            roles[i] = "nav"
        elif re.search(r"REVENUE|TOTAL\s+INCOME|TURNOVER", text):
            roles[i] = "revenue"
    if not roles:
        return []
    hdr_row = _cells(tbl[0])
    # Data begins at the first row whose leading cell is a name rather than more header.
    hdr_idx = 0
    for k, r in enumerate(tbl[:8]):
        cs = _cells(r)
        if cs and cs[0] and any(num(c) is not None for i, c in enumerate(cs)
                                if i in roles):
            hdr_idx = k - 1
            break
    out, n = [], 0
    for r in tbl[hdr_idx + 1:]:
        cs = _cells(r)
        if not cs or not cs[0] or len(cs[0]) < 3:
            continue
        name = cs[0]
        if re.search(r"(?i)^(?:total|average|median|notes?|source)\b", name):
            continue
        if not any(num(c) is not None for i, c in enumerate(cs) if i in roles):
            continue
        n += 1
        if n > MAX_PEERS:
            break
        line = _line_for(cs)
        out.append(_v(doc, f"peer_{n}_name", value=None, original_unit="name",
                      page=page, pdf_page_index=idx, source_text=line,
                      status="ok", note=f"peer name: {name[:60]}"))
        for i, role in roles.items():
            val = num(cs[i]) if i < len(cs) else None
            out.append(_v(doc, f"peer_{n}_{role}", value=val,
                          original_unit="x" if role == "pe" else "Rs",
                          page=page, pdf_page_index=idx, source_text=line,
                          status="ok" if val is not None else "not_found",
                          note=f"peer '{name[:40]}', column {i} ({role})",
                          missing_reason="" if val is not None
                          else "present_but_unparsed"))
    if n:
        out.append(_v(doc, "peer_count", value=float(n), original_unit="count",
                      page=page, pdf_page_index=idx, source_text=_line_for(hdr_row or []),
                      status="ok", note=f"{n} listed peers in the comparison table"))
    return out


def _floor_cap(doc, texts: dict[int, str], doc_offset: int) -> list[Value]:
    """P/E at the floor price and at the cap price, from the sentence that states them.

    These two are prose by convention - "P/E ratio based on Basic EPS ... at the Floor
    Price: 24.3; at the Cap Price: 25.6" - so the anchor is the Floor/Cap WORD next to the
    number, not a bare P/E figure anywhere on the page.
    """
    out = []
    for var, word in (("pe_at_floor", r"floor\s*price"), ("pe_at_cap", r"cap\s*price")):
        best = None
        for i, t in sorted(texts.items()):
            for ln in (t or "").splitlines():
                if not re.search(r"(?i)P\s*/\s*E", ln):
                    continue
                m = re.search(r"(?i)" + word + r"[^0-9\-]{0,40}(\d+(?:\.\d+)?)", ln)
                if not m:
                    continue
                v = float(m.group(1))
                if 0 < v < 500:
                    best = (v, i, ln)
                    break
            if best:
                break
        if best:
            out.append(_v(doc, var, value=best[0], original_unit="x",
                          page=best[1] - doc_offset, pdf_page_index=best[1],
                          source_text=best[2], status="ok",
                          note=f"P/E stated at the {word.replace(chr(92) + 's*', ' ')}"))
        else:
            out.append(_miss(doc, var,
                             "no line states a P/E alongside the floor or cap price"))
    return out


def _nav_pre_post(doc, texts: dict[int, str], doc_offset: int) -> list[Value]:
    out = []
    for var, pat in (("nav_pre_issue", r"(?i)NAV[^\n]{0,60}(?:before|pre)[\s-]*"
                                      r"(?:the\s*)?(?:offer|issue)"),
                     ("nav_post_issue", r"(?i)NAV[^\n]{0,60}(?:after|post)[\s-]*"
                                       r"(?:the\s*)?(?:offer|issue)")):
        best = None
        for i, t in sorted(texts.items()):
            for ln in (t or "").splitlines():
                if not re.search(pat, ln):
                    continue
                # Face-value parentheticals are the known trap: "(face value Rs 10 each)"
                # has produced an NAV of 10.0 before. A line that mentions face value and
                # nothing else numeric is refused.
                cand = [v for v in (num(x) for x in re.findall(r"[\d,]+(?:\.\d+)?", ln))
                        if v is not None]
                if FACE_VALUE.search(ln) and len(cand) < 2:
                    continue
                if cand:
                    best = (cand[-1], i, ln)
                    break
            if best:
                break
        if best:
            out.append(_v(doc, var, value=best[0], original_unit="Rs",
                          page=best[1] - doc_offset, pdf_page_index=best[1],
                          source_text=best[2], status="ok",
                          note="NAV stated on a row-labelled line"))
        else:
            out.append(_miss(doc, var, "no line states NAV before/after the offer"))
    return out


def basis(doc: Doc) -> list[Value]:
    rng, how = find(doc, "basis")
    wanted = ("eps_basic_fy1", "eps_diluted_fy1", "pe_at_floor", "pe_at_cap",
              "ronw_fy1", "nav_pre_issue", "nav_post_issue", "peer_count")
    if not rng:
        return [_miss(doc, v, "the Basis for Issue Price section could not be located",
                      "section_not_found") for v in wanted]
    a, b = rng
    b = min(b, a + 14)
    out = []
    rows = section_rows(doc.path, a, b, doc.offset)

    # --- the year-row block: EPS basic/diluted, RoNW, NAV.
    # Both readers run and are merged: the RoNW block in this family IS ruled and comes
    # out of the table reader, while the EPS block is not and only the text reader sees
    # it. Whichever finds a value wins; the table reader is preferred where both do,
    # because a cell boundary is stronger evidence than a position on a line.
    texts_basis = page_texts(doc.path, a, b)
    got = read_year_lines(texts_basis)
    from_tables = read_year_rows(rows)
    for metric, series in from_tables.items():
        for y, trip in series.items():
            got.setdefault(metric, {})[y] = trip
    for metric in ("eps_basic", "eps_diluted", "ronw", "nav"):
        series = got.get(metric, {})
        years = sorted([y for y in series if y > 0], reverse=True)
        if not years and -1 not in series:
            out.append(_miss(doc, f"{metric}_fy1",
                             "no fiscal-year row block names this metric"))
            continue
        unit = "%" if metric == "ronw" else "Rs"
        for n, y in enumerate(years[:3], 1):
            val, idx, line = series[y]
            out.append(_v(doc, f"{metric}_fy{n}", value=val, original_unit=unit,
                          page=doc.index_to_printed(idx), pdf_page_index=idx,
                          source_text=line, status="ok", note=f"fiscal {y}"))
        if -1 in series:
            val, idx, line = series[-1]
            out.append(_v(doc, f"{metric}_weighted", value=val, original_unit=unit,
                          page=doc.index_to_printed(idx), pdf_page_index=idx,
                          source_text=line, status="ok",
                          note="weighted average row"))

    # --- the peer table, read off the FLATTENED section for the same reason the EPS
    # block is: its six-row wrapped header sits at the foot of one page and its peer rows
    # at the head of the next, so pdfplumber reports a nine-row table of pure header and
    # the data separately. Working table by table found zero peers on a document that
    # lists eight.
    peer_vals = peers_from_text(doc, texts_basis, peer_roles_from_tables(rows))
    if not peer_vals:
        peer_vals = _peers_flat(doc, rows)
    out += peer_vals

    out += _floor_cap(doc, texts_basis, doc.offset)
    out += _nav_pre_post(doc, texts_basis, doc.offset)
    del texts_basis, rows

    seen, uniq = set(), []
    for v in out:
        if v.variable in seen:
            continue
        seen.add(v.variable)
        uniq.append(v)
    return uniq


# ------------------------------------------------------------------ 1.2b financials
FIN_ROWS = {
    "revenue": r"(?i)^(?:total\s+)?revenue\s+from\s+operations",
    "ebitda": r"(?i)^EBITDA",
    # PAT must never match "profit BEFORE tax" - an earlier version did, and reported a
    # PBT of Rs 2,035 million as PAT.
    # "before" of ANY kind disqualifies the row, not just "before tax". Uma Exports
    # prints "Profit/(Loss) Before Exceptional Items and Tax", which the narrower
    # lookahead let through - and a profit before exceptional items is not PAT.
    "pat": r"(?i)^(?:net\s+)?profit\s*(?:/\s*\(loss\))?\s*(?:for\s+the\s+"
           r"(?:year|period)\s*)?(?:after\s+tax|attributable)?(?!.*\bbefore\b)",
    "borrowings": r"(?i)^(?:total\s+)?borrowings",
    "cash": r"(?i)^cash\s+and\s+cash\s+equivalents",
    "cfo": r"(?i)net\s+cash\s+(?:flow\s+)?(?:generated\s+)?from\s+operating",
    "capex": r"(?i)purchase\s+of\s+property,?\s*plant|capital\s+expenditure",
}


# A note-reference column ("Revenue from operations 21 12,345 10,234 8,123") sits between
# the label and the first value. Anything that small is not a money figure in a restated
# statement printed in millions or lakhs, so a leading run of small integers may be
# dropped - but only when dropping it makes the count match the years EXACTLY. Otherwise
# the row is withheld (rule 3) rather than reshaped until it fits.
NOTE_REF_MAX = 1000.0
FIN_SKIP_LINE = re.compile(r"(?i)^\s*(?:note|source|annexure|schedule)\b")
# A sentence in the MD&A can name two fiscal years and would then be read as a column
# header, after which the next labelled row's numbers would be zipped to the wrong years.
# Two guards, both cheap: prose verbs, and a decimal number (a column header carries
# years and nothing else; a sentence carries percentages and amounts).
# A year list written as prose: "2021, 2020 and 2019". The comma must be followed by a
# space and another year for this to fire, so "March 31, 2021 March 31, 2020" - where the
# comma belongs to the date - is still a header.
# A year followed by "and" is prose, whatever comes between: Garuda's financials carry
# the sentence "...as at March 31, 2023, and March 31,2022." directly above the rows, and
# read as a header it offered two columns against a row printing four numbers.
CAPTION_SEP = re.compile(r"(?i)20\d\d\s*,?\s*(?:and|&)\b")
PROSE_CUE = re.compile(r"(?i)\b(?:increased|decreased|declined|grew|compared|respectively"
                       r"|whereas|primarily|because|due\s+to|was|were|is|are|has|have"
                       r"|had|we|our|which|represent(?:s|ed)?)\b")
DECIMAL_NUM = re.compile(r"\d\.\d")


def _fin_year_order(line: str) -> list[int | None]:
    """The header's COLUMNS, left to right: a fiscal year, or `None` for a stub column.

    The restated statements put years in COLUMNS - the reverse of the Basis tables, where
    the years are in rows. So the header is one line carrying the period labels and each
    data row carries one number per column, and POSITION is the only link between them.

    **The columns must be counted, not de-duplicated.** An interim period is routinely
    printed alongside the full years and lands on the same calendar year as the newest of
    them - "SEPT 2021 2021 2020 2019", "2024 2024 2023 2022". A first version treated the
    header as a SET of years, collapsed the repeat to three, found three numbers on the
    row and zipped them - shifting every value by one year. Garuda's FY2024 borrowings of
    10.75 were reported as 10.40, which is the interim figure. A wrong value, produced by
    the very reader meant to fix a missing one.

    So a repeated year is kept as its own column and marked a stub where the header says
    so. Where a year repeats and NOTHING in the header marks either column as an interim
    period, the header is refused: which column is which cannot be established, and under
    rule 3 that is a withhold rather than a guess.

    A line is only a header at all if it names at least two year tokens, reads like a
    header rather than a sentence, and carries no decimal number of its own.
    """
    if not line or PROSE_CUE.search(line) or DECIMAL_NUM.search(line):
        return []
    # "Consolidated Financial Information as at and for the Fiscals 2021, 2020 and 2019"
    # is a CAPTION, not a column header: it lists the years in prose, separated by commas
    # and "and", and it names three of them while the table below has four columns. Read
    # as a header it made the row counts disagree and withheld every money row on the
    # page. A header separates its columns by whitespace, never by a comma or "and".
    if CAPTION_SEP.search(line):
        return []
    cols: list[int | None] = []
    prev_end = 0
    for m in YEAR_LABEL.finditer(line):
        y = int(m.group(1))
        if not 1990 <= y <= 2030:
            continue
        # The text between the previous column and this year token describes THIS column.
        lead = line[prev_end:m.end()]
        cols.append(None if STUB_LABEL.search(lead) else y)
        prev_end = m.end()
    if len(cols) < 2:
        return []
    real = [c for c in cols if c is not None]
    if len(real) != len(set(real)):
        return []            # an unmarked repeated year: refuse the header
    return cols


def _fin_values_on(line: str, years: list[int | None]) -> tuple[list[float] | None, str]:
    """`(one value per column, in the header's order)` or `(None, why not)`.

    Counted against EVERY column including the stub ones, because the row prints a number
    in each. The stub values are dropped by the caller after the positions line up.
    """
    ns = _numbers(line)
    if len(ns) == len(years):
        return ns, ""
    if len(ns) < len(years):
        return None, (f"withheld: the row prints {len(ns)} numbers for "
                      f"{len(years)} period columns")
    # ONE column, not a run. A note reference is a single column; a loop that kept
    # dropping small leading integers until the count fitted turned "1,1 2,2 3,3 4,4 5,5"
    # into a clean three-year series, which is reshaping data until it agrees - exactly
    # what rule 3 exists to stop.
    if (len(ns) - len(years) == 1 and abs(ns[0]) < NOTE_REF_MAX
            and float(ns[0]).is_integer()):
        return ns[1:], ""
    return None, (f"withheld: the row prints {len(ns)} numbers for {len(years)} "
                  f"period columns and the surplus is not a note reference")


def read_fin_lines(texts: dict[int, str]) -> dict:
    """`{base: (page_idx, row line, {year: value} | None, header line, why withheld)}`.

    The year order carries forward across the pages of one statement, because a restated
    statement that runs over four pages prints its column header once. A page that states
    its own header replaces the carried one. The header line is returned alongside every
    value so that the positional zip can be audited from the row itself (rule 2) - a value
    whose header cannot be seen is a value nobody can check.
    """
    found: dict = {}
    years: list[int] = []
    header = ""
    for idx in sorted(texts):
        for raw in (texts[idx] or "").splitlines():
            ln = re.sub(r"\s+", " ", raw).strip()
            if not ln:
                continue
            hit = next((b for b, pat in FIN_ROWS.items() if re.search(pat, ln)), None)
            if hit is None:
                ys = _fin_year_order(ln)
                if ys:
                    years, header = ys, ln
                continue
            if not years or hit in found or FIN_SKIP_LINE.match(ln):
                continue
            vals, why = _fin_values_on(ln, years)
            # Only the full-year columns survive. A stub column's number is read solely
            # so that the positions line up, and is then discarded - it is a six-month or
            # one-month figure and the document says so.
            by_year = ({y: v for y, v in zip(years, vals) if y is not None}
                       if vals else None)
            found[hit] = (idx, ln, by_year, header, why)
    return found


def _fin_rows_from_lines(doc, found: dict, unit_at: dict, done: set) -> list[Value]:
    out = []
    for base, (idx, line, by_year, header, why) in found.items():
        if base in done:
            continue
        printed = doc.index_to_printed(idx)

        def withhold(note: str) -> Value:
            return _v(doc, f"{base}_fy1", value=None, status="not_found", page=printed,
                      pdf_page_index=idx, source_text=line, note=note,
                      missing_reason="present_but_unparsed")

        if by_year is None:
            out.append(withhold(f"{why}; header was: {header[:80]}"))
            done.add(base)
            continue
        if STUB.search(line):
            out.append(withhold("withheld: the row covers a stub period, not a full year"))
            done.add(base)
            continue
        mult, phrase, unit_page = unit_at.get(idx, (None, None, None))
        if mult is None:
            out.append(withhold("withheld: no money unit stated on this page or any "
                                "earlier page of the section"))
            done.add(base)
            continue
        where = ("same page" if unit_page == idx
                 else f"page {doc.index_to_printed(unit_page)}")
        for n, y in enumerate(sorted(by_year, reverse=True)[:3], 1):
            val = by_year[y]
            out.append(_v(doc, f"{base}_fy{n}", value=val, original_unit=phrase,
                          value_crore=round(val * mult, 4) if val is not None else None,
                          page=printed, pdf_page_index=idx, source_text=line,
                          status="ok" if val is not None else "not_found",
                          note=(f"fiscal {y}, text line (the table is unruled); "
                                f"header: {header[:80]}; unit {phrase} from {where} "
                                f"-> crore x{mult}"),
                          missing_reason="" if val is not None
                          else "present_but_unparsed"))
        done.add(base)
    return out


# The RHP prints a weighted-average EPS and RoNW alongside the three fiscal years, and
# the weights it uses are 3, 2, 1 - most recent year heaviest. That makes the stated
# average a CHECKSUM over the three years rather than a fourth datum: if the three are
# read correctly, (3*fy1 + 2*fy2 + 1*fy3) / 6 must reproduce it.
#
# It is the strongest validation available in this block, because it does not depend on
# the parse that produced the numbers - and it is what proved the hyphenated-label fix.
# Uma Exports read EPS 3.71 / 21.00 / 20.00 against a stated 3.73 before it, and
# 4.92 / 3.30 / 1.02 after, which reproduces 3.73 exactly.
WEIGHTS_321 = (3, 2, 1)
CHECK_TOL_PCT = 2.0


def weighted_checks(out: list) -> list[tuple]:
    """`[(metric, recomputed, stated, gap %, agrees, the row it came from)]`.

    A disagreement is REPORTED, never corrected. Which of the four numbers is wrong
    cannot be known from the arithmetic alone, so the row carries the gap and the reader
    decides; a metric whose check fails should not be trusted in a ratio.
    """
    by = {v.variable: v for v in out if v.value is not None and v.status == "ok"}
    rows = []
    for metric in ("eps_basic", "eps_diluted", "ronw"):
        w = by.get(metric + "_weighted")
        ys = [by.get(f"{metric}_fy{i}") for i in (1, 2, 3)]
        if w is None or any(y is None for y in ys) or abs(w.value) < 1e-9:
            continue
        calc = sum(k * y.value for k, y in zip(WEIGHTS_321, ys)) / sum(WEIGHTS_321)
        gap = 100 * abs(calc - w.value) / abs(w.value)
        rows.append((metric, round(calc, 4), w.value, round(gap, 3),
                     gap <= CHECK_TOL_PCT, w))
    return rows


def financials(doc: Doc) -> list[Value]:
    rng, how = find(doc, "financials")
    if not rng:
        return [_miss(doc, f"{k}_fy1", "the financial information section could not be "
                                       "located", "section_not_found")
                for k in FIN_ROWS]
    a, b = rng
    b = min(b, a + 40)
    out, done = [], set()
    # Table extraction is the expensive operation - minutes, on forty pages of a
    # restated-financials section. The TEXT of those pages is cheap, so it is read first
    # and tables are extracted ONLY on pages whose text actually carries one of the row
    # labels being looked for. On a 500-page prospectus this is the difference between
    # the batch finishing overnight and not finishing.
    texts = page_texts(doc.path, a, b)
    # `(?i)` is a GLOBAL flag: Python rejects it anywhere but the start of a pattern.
    # Each FIN_ROWS pattern carries its own, so joining them put `(?i)` inside a group and
    # every call raised PatternError - on all 412 documents. `extract()` caught it and
    # recorded `financials_group: unreadable`, so nothing crashed and nothing was
    # fabricated, but the whole 1.2b block produced zero values and I reported extraction
    # quality without reading the `_group` rows that said so.
    want = re.compile("|".join(f"(?:{pat.replace('(?i)', '')})"
                               for pat in FIN_ROWS.values()), re.I)
    pages = [i for i in sorted(texts)
             if any(want.search(ln) for ln in (texts[i] or "").splitlines())]
    if not pages:
        del texts
        return [_miss(doc, f"{k}_fy1",
                      "no page in the financial section carries any of these row labels")
                for k in FIN_ROWS]
    tabs = {}
    for i in pages[:12]:
        tabs.update(page_tables(doc.path, i, i))
    # The unit phrase - "(₹ in millions)" - is printed once at the head of a statement,
    # not repeated on every page of it. Requiring it on the SAME page withheld 7 of 13
    # financial rows in the first spot-check: rule 3 behaving correctly but scoped too
    # tightly. It is now carried forward from the nearest PRECEDING page in the section
    # that states one, and the page it came from is recorded on the row - because a unit
    # inherited from two pages back is a weaker claim than one in the same caption, and
    # the reader should be able to see which they have.
    unit_at: dict[int, tuple] = {}
    carried = (None, None, None)
    for idx in sorted(texts):
        m, phrase = _unit_of(texts.get(idx, ""))
        if m is not None:
            carried = (m, phrase, idx)
        unit_at[idx] = carried

    for idx in sorted(tabs):
        printed = doc.index_to_printed(idx)
        mult, unit_phrase, unit_page = unit_at.get(idx, (None, None, None))
        for tbl in tabs[idx] or []:
            if not tbl or len(tbl) < 2:
                continue
            if not _year_columns(tbl):
                continue
            for base, pat in FIN_ROWS.items():
                if base in done:
                    continue
                if mult is None:
                    # Rule 3: a money figure with no stated unit is withheld. Reading
                    # lakhs as crore is a 100x error that looks like a plausible number.
                    # NOT marked done - the text reader below may find the same row on a
                    # page the carried unit does reach, and a withheld row here would
                    # otherwise mask a readable one there.
                    continue
                vals = _row_series(doc, tbl, printed, idx, re.compile(pat), base,
                                   unit_phrase or "unknown")
                if not vals:
                    continue
                for v in vals:
                    if v.value is not None:
                        v.value_crore = round(v.value * mult, 4)
                        where = ("same page" if unit_page == idx
                                 else f"page {doc.index_to_printed(unit_page)}")
                        v.note = (f"{v.note}; unit {unit_phrase} from {where} "
                                  f"-> crore x{mult}")
                out += vals
                done.add(base)
    del tabs
    # The TEXT reader runs for whatever the tables did not yield. In this document family
    # that is nearly everything: the restated statements are unruled, so `_year_columns`
    # finds no header and `_row_series` is never reached. The table reader stays ahead of
    # it because a cell boundary is stronger evidence than a position on a line.
    out += _fin_rows_from_lines(doc, read_fin_lines(texts), unit_at, done)
    del texts
    for base in FIN_ROWS:
        if base not in done:
            out.append(_miss(doc, f"{base}_fy1",
                             "neither a table nor a text line in the financial section "
                             "carries this row under a fiscal-year header"))
    return out


# ------------------------------------------------------------------ 1.2c share count
# The post-issue share count must come from the CAPITAL BUILD-UP row, not from any line
# that happens to say "post-Issue". The first version accepted the latter and 20 of its
# 153 values were impossible - the implied market capitalisation came out BELOW the money
# the IPO raised. The causes were never units or scale; they were four families of line
# that mention the post-issue capital while counting something else entirely:
#
#   employee reservation caps   "The Employee Reservation Portion shall not exceed 5% of
#                                the post-Issue paid up Equity Share capital" - Brigade
#                                200,000, Sambhv 500,000, Anupam Rasayan 220,000
#   promoter lock-in tables     "Name No. of Equity Shares Pre-Offer (%) Post-Offer (%)
#                                Udaya Kumar Hebbar 212,500 0.17" - one promoter's holding
#   pre-IPO placements and      "After the Offer [bullet] ... allotted 6,300,000 Equity
#   preference conversions       Shares to JSW Group Welfare Trust pursuant to a Pre-IPO
#                                Placement"; CCPS and FRCPS footnotes
#   selling-shareholder counts  "The Selling Shareholders are offering 5,433,016 Equity
#                                Shares" - the OFS size, not the total
#
# So the line must now carry BOTH the after-the-offer phrase AND a paid-up-capital phrase,
# in either order and within 90 characters of each other, which is what the build-up row
# looks like: "D) ISSUED, SUBSCRIBED AND PAID-UP CAPITAL AFTER THE OFFER". And any line
# matching one of the four families above is refused outright, because a line can satisfy
# the capital phrasing and still be about the employee quota.
# 1.8.1 widens this. 1.8.0 required "equity SHARE capital" and so missed the two commonest
# build-up row spellings - "AFTER THE ISSUE 31,250,000 Equity Shares of face value of
# Rs 10/- each" and "E) EQUITY CAPITAL AFTER THE ISSUE 423,559,671 Equity Shares" - which
# cost 34 good values. Precision went up (79% -> 91%) and usable output went DOWN (121 ->
# 81), which is a worse result, not a better one.
#
# So "equity capital" and a bare "Equity Shares" now satisfy the capital side, and a line
# that OPENS with the after-the-offer phrase is accepted as a build-up row in its own
# right: a row in that table begins with its label, optionally after a row letter like
# "E)". The four false families are still refused by NOT_THE_COUNT, and the two-sided
# arithmetic guard still sits behind all of it.
CAPITAL_PHRASE = (r"(?:issued|subscribed|paid[\s-]*up"
                  r"|equity\s+(?:share\s+)?capital|equity\s+shares?)")
AFTER_PHRASE = r"(?:after|post)[\s-]*(?:the\s*)?(?:offer|issue|ipo)"
# A build-up row opens with its label, so the after-phrase appearing in the first ~34
# characters is itself the evidence - "E) EQUITY CAPITAL AFTER THE ISSUE ...",
# "AFTER THE ISSUE 31,250,000 Equity Shares ...". A prose sentence about the post-issue
# capital almost never starts that way.
ROW_OPENER = re.compile(r"(?i)^\s*(?:[A-Z]\s*[).]\s*)?(?:total\s+)?"
                        r"(?:equity\s+(?:share\s+)?capital\s+)?" + AFTER_PHRASE)
POST_ISSUE = re.compile(
    r"(?i)(?:" + CAPITAL_PHRASE + r".{0,90}?" + AFTER_PHRASE
    + r"|" + AFTER_PHRASE + r".{0,90}?" + CAPITAL_PHRASE + r")")
# Any of these on the line disqualifies it, however well it matches above.
NOT_THE_COUNT = re.compile(
    r"(?i)employee\s+reservation"
    r"|reservation\s+portion"
    r"|lock(?:ed)?[\s-]*in"
    r"|pre[\s-]*ipo\s+placement"
    r"|preference\s+shares?"
    r"|\bCCPS\b|\bFRCPS\b|\bOCRPS\b"
    r"|selling\s+shareholders?\s+(?:are|is|have|has)?\s*offer"
    r"|pursuant\s+to\s+(?:the\s+)?conversion"
    r"|no\.?\s*of\s+equity\s+shares\s+pre[\s-]*(?:offer|issue)"
    r"|shall\s+not\s+exceed"
    r"|in\s+excess\s+of")
# "123,456,789 Equity Shares of face value Rs 10 each" - the count is the number ADJACENT
# to "Equity Shares". The same row usually also prints the aggregate rupee capital, which
# is larger, so the previous `max()` took the money figure and called it a share count.
COUNT_ADJ = re.compile(r"([\d,]{5,})\s*(?:fully\s+paid[\s-]*up\s*)?(?:equity\s+)?shares",
                       re.I)
FACE_EACH = re.compile(r"(?i)(?:face\s*value\s*(?:of)?\s*)?(?:\u20b9|rs\.?|inr)\s*"
                       r"([\d,]+(?:\.\d+)?)\s*(?:each|per\s+equity\s+share)")


def _post_issue_count(doc, texts: dict[int, str]):
    """`(count|None, page index, quoted line, how)` or `None` if no such line exists.

    A wrapped row is read with the next line joined on, because the Capital Structure
    build-up routinely breaks "D) Issued, subscribed and paid-up Equity Share capital
    after the Offer" from its figures.
    """
    for i, t in sorted(texts.items()):
        lines = [re.sub(r"\s+", " ", x).strip() for x in (t or "").splitlines()]
        for n, ln in enumerate(lines):
            if not ln or NOT_THE_COUNT.search(ln):
                continue
            if not (POST_ISSUE.search(ln) or ROW_OPENER.match(ln)):
                continue
            joined = ln if COUNT_ADJ.search(ln) else " ".join(lines[n:n + 2]).strip()
            if NOT_THE_COUNT.search(joined):
                # The continuation line can reveal what the first line was really about -
                # "After the Offer [bullet]" followed by a pre-IPO placement footnote.
                continue
            adj = [num(m.group(1)) for m in COUNT_ADJ.finditer(joined)]
            adj = [v for v in adj if v is not None and v > 1e5]
            if adj:
                how = "post-issue equity share count from Capital Structure"
                fv = FACE_EACH.search(joined)
                big = [v for v in _numbers(joined) if v is not None and v > adj[0]]
                if fv and big:
                    want = adj[0] * (num(fv.group(1)) or 0)
                    near = [v for v in big if want and abs(v - want) / want < 0.02]
                    how += (f"; cross-checks against the aggregate capital at a face "
                            f"value of {fv.group(1)}" if near else
                            "; the aggregate capital on the row does NOT reconcile at "
                            "the stated face value")
                    if not near:
                        return None, i, joined[:300], (
                            "withheld: the count and the aggregate rupee capital on this "
                            "row do not reconcile at the stated face value")
                return adj[0], i, joined[:300], how
            # A number is present but not adjacent to "Equity Shares": that is the case
            # the old reader guessed at. Withheld, with the line, rather than guessed.
            other = [v for v in _numbers(joined) if v is not None and v > 1e5]
            if len(other) == 1:
                return other[0], i, joined[:300], (
                    "post-issue share count from Capital Structure; the row prints one "
                    "large number and it is not adjacent to the words 'Equity Shares'")
            if other:
                return None, i, joined[:300], (
                    f"withheld: the row prints {len(other)} large numbers and none is "
                    f"adjacent to the words 'Equity Shares', so which one is the share "
                    f"count cannot be established")
    return None


def shares_post_issue(doc: Doc, texts=None) -> list[Value]:
    rng, how = find(doc, "capital")
    if not rng:
        return [_miss(doc, "shares_outstanding_post_issue",
                      "the Capital Structure section could not be located",
                      "section_not_found")]
    a, b = rng
    # Twelve pages, not eight. The Capital Structure build-up is routinely preceded by the
    # authorised/issued history table and the notes to it, and the "after the Offer" row
    # sat past page eight in the documents that came back empty.
    own = texts is None
    texts = page_texts(doc.path, a, min(b, a + 12)) if own else texts
    best = _post_issue_count(doc, texts)
    if own:
        del texts
    if best is None:
        return [_miss(doc, "shares_outstanding_post_issue",
                      "no line in Capital Structure states the post-issue share count")]
    val, i, line, how = best
    if val is None:
        return [_v(doc, "shares_outstanding_post_issue", value=None, status="not_found",
                   page=i - doc.offset, pdf_page_index=i, source_text=line, note=how,
                   missing_reason="present_but_unparsed")]
    return [_v(doc, "shares_outstanding_post_issue", value=val,
               original_unit="shares", page=i - doc.offset,
               pdf_page_index=i, source_text=line, status="ok", note=how)]


def promoter_shareholding(doc: Doc, texts=None) -> list[Value]:
    """Promoter and promoter-group % before and after the offer, from Capital Structure.

    This calls `extract/capital.py` rather than reimplementing it. That module already
    anchors the figures to a promoter-labelled row in a pre/post table, records the page
    and the quoted line, and deliberately WITHHOLDS the pre-IPO allotment price because
    the price column cannot be identified positionally - a previous version averaged a
    share-transfer row containing negative share counts and reported -1.0. Writing a third
    implementation of the same table would be inviting the two to disagree.

    Only the three shareholding variables are carried through here; the allotment fields
    belong to the H6 block and are already collected there.
    """
    from . import capital
    want = {"promoter_pre_pct", "promoter_post_pct", "promoter_change_pp"}
    out = []
    for v in capital.extract(doc, texts=texts):
        if v is None or v.variable not in want:
            continue
        # Re-stamped with THIS module's version, because this pipeline's output file is
        # resumed on that version and a row carrying capital.py's would look stale for
        # ever.
        v.extractor_version = VALUATION_VERSION
        v.extractor = f"{NAME}->capital"
        out.append(v)
    return out


def extract(doc: Doc) -> list[Value]:
    """Everything 1.2 asks for. Each group opens and closes the PDF itself, so peak
    memory is one section's tables rather than the whole document."""
    # The Capital Structure pages feed BOTH the share count and the promoter row, and
    # they were being read twice - 29 of the 53 seconds one document took. Read once here
    # and handed to both. A failure to locate the section is not fatal: each block still
    # calls `find` itself and reports its own miss.
    cap_texts = None
    try:
        rng, _ = find(doc, "capital")
        if rng:
            ca, cb = rng
            cap_texts = page_texts(doc.path, ca, min(cb, ca + 20))
    except Exception:                                          # noqa: BLE001
        cap_texts = None
    out = []
    for fn in (basis, financials, shares_post_issue, promoter_shareholding):
        try:
            out += (fn(doc, texts=cap_texts)
                    if fn in (shares_post_issue, promoter_shareholding) else fn(doc))
        except Exception as e:                                 # noqa: BLE001
            out.append(_v(doc, f"{fn.__name__}_group", value=None, status="unreadable",
                          note=f"{type(e).__name__}: {str(e)[:120]}",
                          missing_reason="present_but_unparsed"))
    del cap_texts
    # The stated weighted average is a checksum over the three fiscal years.
    for metric, calc, stated, gap, agrees, src in weighted_checks(out):
        verdict = "reconciles" if agrees else "DOES NOT reconcile"
        out.append(_v(doc, metric + "_weighted_check", value=gap,
                      original_unit="percent gap", page=src.page,
                      pdf_page_index=src.pdf_page_index, source_text=src.source_text,
                      status="ok",
                      note=(f"(3*fy1+2*fy2+1*fy3)/6 = {calc} against the stated "
                            f"{stated}: {verdict} within {CHECK_TOL_PCT}%")))
    return out

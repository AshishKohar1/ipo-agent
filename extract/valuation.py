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
VALUATION_VERSION = "1.2.0"

FY_HDR = re.compile(r"(?:FY|FISCAL|FINANCIAL YEAR|YEAR ENDED|MARCH)\s*'?\s*(\d{2,4})", re.I)
WEIGHTED = re.compile(r"(?i)weighted\s*average")
STUB = re.compile(r"(?i)(?:six|nine|three|6|9|3)[\s-]*month|period\s+ended|stub")
FACE_VALUE = re.compile(r"(?i)face\s*value")
UNIT_LINE = re.compile(r"\(\s*(?:₹|`|RS\.?|INR)?\s*in\s*" + MONEY_UNIT_RE + r"[^)]*\)", re.I)
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


def _year_of(cell: str) -> int | None:
    if WEIGHTED.search(cell or ""):
        return -1
    m = YEAR_LABEL.search(cell or "")
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
            for ci, metric in roles.items():
                val = num(jcs[ci]) if ci < len(jcs) else None
                if val is None:
                    # The value may sit one or two columns right of its header when
                    # pdfplumber splits a merged cell. Only a numeric cell within two
                    # columns is accepted, and never one that belongs to another metric.
                    for k in (ci + 1, ci + 2):
                        if k < len(jcs) and k not in roles and num(jcs[k]) is not None:
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
            if y is None:
                # A run ends at the first non-year line, so a later unrelated paragraph
                # cannot contribute numbers to the series.
                if re.match(r"(?i)^(?:\d+[.)]|note|source|\(\d+\))", ln):
                    order = []
                continue
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
            m = FY_HDR.search(c)
            if m:
                y = int(m.group(1))
                out[i] = 2000 + y if y < 100 else y
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
    "pat": r"(?i)^(?:net\s+)?profit\s*(?:/\s*\(loss\))?\s*(?:for\s+the\s+"
           r"(?:year|period)\s*)?(?:after\s+tax|attributable)?(?!.*before\s+tax)",
    "borrowings": r"(?i)^(?:total\s+)?borrowings",
    "cash": r"(?i)^cash\s+and\s+cash\s+equivalents",
    "cfo": r"(?i)net\s+cash\s+(?:flow\s+)?(?:generated\s+)?from\s+operating",
    "capex": r"(?i)purchase\s+of\s+property,?\s*plant|capital\s+expenditure",
}


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
    want = re.compile("|".join(f"(?:{pat})" for pat in FIN_ROWS.values()))
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
    for idx in sorted(tabs):
        printed = doc.index_to_printed(idx)
        mult, unit_phrase = _unit_of(texts.get(idx, ""))
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
                    out.append(_v(doc, f"{base}_fy1", value=None, status="not_found",
                                  page=printed, pdf_page_index=idx,
                                  note="withheld: the table states no money unit",
                                  missing_reason="present_but_unparsed"))
                    done.add(base)
                    continue
                vals = _row_series(doc, tbl, printed, idx, re.compile(pat), base,
                                   unit_phrase or "unknown")
                if not vals:
                    continue
                for v in vals:
                    if v.value is not None:
                        v.value_crore = round(v.value * mult, 4)
                        v.note = f"{v.note}; unit {unit_phrase} -> crore x{mult}"
                out += vals
                done.add(base)
    del tabs, texts
    for base in FIN_ROWS:
        if base not in done:
            out.append(_miss(doc, f"{base}_fy1",
                             "no table in the financial section carries this row"))
    return out


# ------------------------------------------------------------------ 1.2c share count
def shares_post_issue(doc: Doc) -> list[Value]:
    rng, how = find(doc, "capital")
    if not rng:
        return [_miss(doc, "shares_outstanding_post_issue",
                      "the Capital Structure section could not be located",
                      "section_not_found")]
    a, b = rng
    texts = page_texts(doc.path, a, min(b, a + 8))
    pat = re.compile(r"(?i)(?:equity shares? )?(?:outstanding )?(?:after|post)[\s-]*"
                     r"(?:the\s*)?(?:offer|issue)")
    best = None
    for i, t in sorted(texts.items()):
        for ln in (t or "").splitlines():
            if not pat.search(ln):
                continue
            cand = [v for v in (num(x) for x in re.findall(r"[\d,]{5,}", ln))
                    if v is not None and v > 1e5]
            if cand:
                best = (max(cand), i, ln)
                break
        if best:
            break
    del texts
    if not best:
        return [_miss(doc, "shares_outstanding_post_issue",
                      "no line in Capital Structure states the post-issue share count")]
    return [_v(doc, "shares_outstanding_post_issue", value=best[0],
               original_unit="shares", page=best[1] - doc.offset,
               pdf_page_index=best[1], source_text=best[2], status="ok",
               note="post-issue equity share count from Capital Structure")]


def promoter_shareholding(doc: Doc) -> list[Value]:
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
    for v in capital.extract(doc):
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
    out = []
    for fn in (basis, financials, shares_post_issue, promoter_shareholding):
        try:
            out += fn(doc)
        except Exception as e:                                 # noqa: BLE001
            out.append(_v(doc, f"{fn.__name__}_group", value=None, status="unreadable",
                          note=f"{type(e).__name__}: {str(e)[:120]}",
                          missing_reason="present_but_unparsed"))
    return out

"""
extract/financials.py — restated financials: revenue, EBITDA, PAT, net worth, borrowings,
operating cash flow, for up to three years.

Read from "SUMMARY OF FINANCIAL INFORMATION", which is a compact restated summary near the
front of every RHP. The full restated statements run to ~150 pages and are far harder to
parse reliably; the summary carries the same restated figures and states its own unit in a
header such as "(Rs in million)".

The unit is taken from the table or page header and normalised to Rs crore, with the
original unit always preserved (Stage 8 step 5). If no unit can be found on the page, the
value is recorded with `value_crore=None` rather than assuming crore — the wrong unit is a
100x error.
"""
from __future__ import annotations
import re
from .base import (Doc, Value, EXTRACTOR_VERSION, page_tables, page_texts, num, to_crore,
                   MONEY_UNIT_RE, find)

NAME = "financials"

ROWS = {
    "revenue_cr": r"(?i)^(?:total\s+)?revenue\s+from\s+operations",
    "total_income_cr": r"(?i)^total\s+income",
    # PAT must never match "profit BEFORE tax" — a first version did, and reported
    # Syngene's PBT of Rs 2,035 million as its PAT.
    "pat_cr": r"(?i)^(?:net\s+)?profit\s*(?:/\s*\(loss\))?\s*(?:for\s+the\s+(?:year|period)\s*)?"
              r"(?:after\s+tax|attributable)?(?!.*before\s+tax)",
    "pbt_cr": r"(?i)^(?:net\s+)?profit\s+before\s+tax",
    "ebitda_cr": r"(?i)^EBITDA",
    "net_worth_cr": r"(?i)^(?:net\s*worth|total\s+equity)",
    "borrowings_cr": r"(?i)^(?:total\s+)?borrowings",
    "ocf_cr": r"(?i)net\s+cash\s+(?:generated\s+)?from\s+operating\s+activities",
}
UNIT_IN = re.compile(r"\(\s*(?:₹|`|RS\.?|INR)?\s*in\s*" + MONEY_UNIT_RE + r"[^)]*\)", re.I)


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def _cells(row):
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]


def extract(doc: Doc) -> list[Value]:
    out: list[Value] = []
    rng, how = find(doc, "financials")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="financial summary section not located") for v in ROWS]
    a, b = rng
    lo, hi = a, min(b, a + 10)
    tabs = page_tables(doc.path, lo, hi)
    txts = page_texts(doc.path, lo, hi)
    found: dict[str, Value] = {}

    for i in sorted(tabs):
        page_unit = None
        um = UNIT_IN.search(txts.get(i, "") or "")
        if um:
            page_unit = um.group(1)
        for tbl in tabs[i]:
            if not tbl or len(tbl) < 2:
                continue
            tu = page_unit
            hm = UNIT_IN.search(" ".join(" ".join(_cells(r)) for r in tbl[:2]))
            if hm:
                tu = hm.group(1)
            for row in tbl:
                cs = _cells(row)
                if not cs or not cs[0]:
                    continue
                label = cs[0]
                vals = [num(c) for c in cs[1:]]
                vals = [v for v in vals if v is not None]
                if not vals:
                    continue
                for var, pat in ROWS.items():
                    if var in found or not re.search(pat, label):
                        continue
                    # the most recent year is normally the first numeric column
                    found[var] = _v(doc, var, value=vals[0], original_unit=tu,
                                    value_crore=to_crore(vals[0], tu),
                                    page=doc.index_to_printed(i), pdf_page_index=i,
                                    source_text=" | ".join(c for c in cs if c)[:280],
                                    status="ok" if tu else "ambiguous",
                                    note=(f"most recent column of {len(vals)}; unit "
                                          f"{'from table/page header' if tu else 'NOT FOUND - '
                                          'value_crore withheld rather than assumed'}; "
                                          f"section by {how}"))
    for v in ROWS:
        out.append(found.get(v) or _v(doc, v, value=None, status="not_found",
                                      note=f"row label not matched in the financial summary "
                                           f"(section located by {how})"))
    return out

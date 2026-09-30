"""
extract/rpt.py — related-party transactions as a percentage of revenue.

RPT is red flag 3 in the veto list (>20% of revenue) and a governance metric under MSCI's
Ownership & Control key issue. It exists only in the RHP, so it can never be reconciled
against a second source and must carry `single_source_unverified` downstream (global
rule 3, and CLAUDE.md's "known biases").

Two routes are tried, in order:
  1. a summary line stating RPT as a percentage of revenue directly
  2. the aggregate RPT amount, divided by revenue supplied by the caller

The RPT section is rarely a TOC entry — it sits inside the restated financial notes — so
location relies on the regex scan fallback.
"""
from __future__ import annotations
import re
from .base import (Doc, Value, EXTRACTOR_VERSION, page_texts, num, to_crore,
                   MONEY_UNIT_RE, find)

NAME = "rpt"
AS_PCT = re.compile(r"(?i)related[- ]party\s+transactions?[^.\n]{0,120}?"
                    r"(\d{1,3}(?:\.\d+)?)\s*%")
AGG = re.compile(r"(?i)(?:aggregate|total)\s+(?:value\s+of\s+)?related[- ]party\s+"
                 r"transactions?[^\d\n]{0,80}?([\d,]+(?:\.\d+)?)")
UNIT_IN = re.compile(r"\(\s*(?:₹|`|RS\.?|INR)?\s*in\s*" + MONEY_UNIT_RE + r"[^)]*\)", re.I)


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def extract(doc: Doc, revenue_cr: float | None = None) -> list[Value]:
    want = ["rpt_pct_revenue", "rpt_amount_cr"]
    rng, how = find(doc, "rpt")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="related-party section not located by TOC or scan") for v in want]
    a, b = rng
    txts = page_texts(doc.path, a, min(b, a + 8))
    found: dict[str, Value] = {}

    for i in sorted(txts):
        unit = None
        um = UNIT_IN.search(txts[i] or "")
        if um:
            unit = um.group(1)
        for ln in (txts[i] or "").splitlines():
            s = ln.strip()
            if "rpt_pct_revenue" not in found:
                m = AS_PCT.search(s)
                if m and re.search(r"(?i)revenue|turnover|income", s):
                    found["rpt_pct_revenue"] = _v(
                        doc, "rpt_pct_revenue", value=num(m.group(1)), original_unit="%",
                        page=doc.index_to_printed(i), pdf_page_index=i, source_text=s,
                        note=f"stated directly as a % of revenue; section by {how}; "
                             "SINGLE-SOURCE - cannot be reconciled (rule 3)")
            if "rpt_amount_cr" not in found:
                m = AGG.search(s)
                if m:
                    v = num(m.group(1))
                    found["rpt_amount_cr"] = _v(
                        doc, "rpt_amount_cr", value=v, original_unit=unit,
                        value_crore=to_crore(v, unit), page=doc.index_to_printed(i),
                        pdf_page_index=i, source_text=s,
                        status="ok" if unit else "ambiguous",
                        note=("aggregate RPT value; unit "
                              + ("from the page header" if unit else
                                 "NOT FOUND - value_crore withheld rather than assumed")
                              + "; SINGLE-SOURCE (rule 3)"))

    # derive the percentage if only the amount was found and revenue is known
    if "rpt_pct_revenue" not in found and revenue_cr and found.get("rpt_amount_cr"):
        amt = found["rpt_amount_cr"]
        if amt.value_crore:
            found["rpt_pct_revenue"] = _v(
                doc, "rpt_pct_revenue", value=round(amt.value_crore / revenue_cr * 100, 3),
                original_unit="%", page=amt.page, pdf_page_index=amt.pdf_page_index,
                source_text=amt.source_text, status="ambiguous",
                note=f"DERIVED: RPT {amt.value_crore:.2f} cr / revenue {revenue_cr:.2f} cr; "
                     "not a figure printed in the document")

    return [found.get(v) or _v(doc, v, value=None, status="not_found",
                               note=f"no RPT summary line matched (section by {how})")
            for v in want]

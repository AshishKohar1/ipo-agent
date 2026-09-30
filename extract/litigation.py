"""
extract/litigation.py — outstanding litigation: counts and amounts by category and party.

"OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS" opens with a summary table whose rows
are the parties (Company, Directors, Promoters, Subsidiaries) and whose columns are
categories (criminal, tax, statutory/regulatory, civil/other material), with a count and
an amount involved. That summary is what feeds the veto list (red flag 6, criminal or
regulatory proceedings naming a promoter or director) and Model H's business-risk block.

Counts are single-source by nature — no second source states them — so they are recorded
and must be flagged `single_source_unverified` downstream (global rule 3).
"""
from __future__ import annotations
import re
from .base import (Doc, Value, EXTRACTOR_VERSION, page_tables, page_texts, num, to_crore,
                   MONEY_UNIT_RE, find)

NAME = "litigation"
UNIT_IN = re.compile(r"\(\s*(?:₹|`|RS\.?|INR)?\s*in\s*" + MONEY_UNIT_RE + r"[^)]*\)", re.I)
PARTY = re.compile(r"(?i)^(company|directors?|promoters?|subsidiar|group compan|key manageri)")


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def _cells(row):
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]


def extract(doc: Doc) -> list[Value]:
    want = ["litigation_rows", "litigation_total_count", "litigation_amount_cr",
            "criminal_against_promoters_directors"]
    rng, how = find(doc, "litigation")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="litigation section not located") for v in want]
    a, b = rng
    lo, hi = a, min(b, a + 6)
    tabs = page_tables(doc.path, lo, hi)
    txts = page_texts(doc.path, lo, hi)
    found: dict[str, Value] = {}

    for i in sorted(tabs):
        unit = None
        um = UNIT_IN.search(txts.get(i, "") or "")
        if um:
            unit = um.group(1)
        for tbl in tabs[i]:
            if not tbl or len(tbl) < 3:
                continue
            head = " ".join(" ".join(_cells(r)) for r in tbl[:2]).upper()
            if not re.search(r"CRIMINAL|TAX|STATUTORY|AGGREGATE|DISCIPLINARY", head):
                continue
            hm = UNIT_IN.search(head)
            if hm:
                unit = hm.group(1)
            party_rows, total_count, total_amt, crim = [], 0.0, None, None
            for row in tbl:
                cs = _cells(row)
                if not cs or not cs[0] or not PARTY.search(cs[0]):
                    continue
                ns = [num(c) for c in cs[1:]]
                ns = [x for x in ns if x is not None]
                if not ns:
                    continue
                party_rows.append((cs[0], ns, " | ".join(c for c in cs if c)[:280]))
                # counts are the small integers; the amount is normally the last column
                total_count += sum(x for x in ns[:-1] if x == int(x) and x < 1000)
                if total_amt is None:
                    total_amt = ns[-1]
                if re.search(r"(?i)promoter|director", cs[0]) and crim is None:
                    crim = (ns[0], " | ".join(c for c in cs if c)[:280])
            if not party_rows:
                continue
            pr = doc.index_to_printed(i)
            found["litigation_rows"] = _v(
                doc, "litigation_rows", value=float(len(party_rows)), original_unit="count",
                page=pr, pdf_page_index=i, source_text=party_rows[0][2],
                note=f"party rows in the litigation summary; section by {how}")
            found["litigation_total_count"] = _v(
                doc, "litigation_total_count", value=total_count or None, original_unit="count",
                page=pr, pdf_page_index=i, source_text=party_rows[0][2], status="ambiguous",
                note="sum of small-integer cells across party rows, excluding the last "
                     "(amount) column; column layouts vary, so treat as indicative")
            found["litigation_amount_cr"] = _v(
                doc, "litigation_amount_cr", value=total_amt, original_unit=unit,
                value_crore=to_crore(total_amt, unit), page=pr, pdf_page_index=i,
                source_text=party_rows[0][2],
                status="ok" if unit else "ambiguous",
                note=("amount involved from the last numeric column; unit "
                      + ("from the table/page header" if unit
                         else "NOT FOUND - value_crore withheld rather than assumed")))
            if crim:
                found["criminal_against_promoters_directors"] = _v(
                    doc, "criminal_against_promoters_directors", value=crim[0],
                    original_unit="count", page=pr, pdf_page_index=i, source_text=crim[1],
                    note="first numeric column of the promoter/director row, normally the "
                         "criminal-proceedings count — relevant to veto red flag 6")
            break

    return [found.get(v) or _v(doc, v, value=None, status="not_found",
                               note=f"litigation summary table not matched (section by {how})")
            for v in want]

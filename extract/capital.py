"""
extract/capital.py — promoter shareholding pre- and post-offer, and pre-IPO allotments.

"CAPITAL STRUCTURE" carries a build-up of allotments and a shareholding table stating the
promoter and promoter-group percentage before and after the offer. Post-issue promoter
holding and the change across the offer feed Model H's ownership block (PLAN.md Part C.4).

Pre-IPO allotment price against the issue price is red flag 5 in the veto list, so the most
recent pre-IPO allotment price is captured where the allotment table gives one.
"""
from __future__ import annotations
import re
from .base import (Doc, Value, EXTRACTOR_VERSION, page_tables, page_texts, num,
                   find)

NAME = "capital"
PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def _cells(row):
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]



# The promoter row, read from TEXT. `page_tables` returns nothing usable here for the same
# reason it returned nothing in the valuation block: the shareholding tables in this
# document family are UNRULED, so pdfplumber reports a header fragment and no data rows.
# Measured over 412 documents, the table-only reader produced promoter_pre_pct on **zero**
# of them.
#
# A positional read of a text line is only safe under tight conditions, so all of these
# must hold or the row is withheld (hard rule 1 - a missing value costs one row, a wrong
# one corrupts every ratio built on it):
#
#   * the line's label names the promoter (or "Total" inside a promoter block);
#   * the page states both a pre- and a post-offer column, so the two percentages are
#     known to be the two sides of the offer rather than, say, two classes of share;
#   * after filtering to percentage-like values, there are EXACTLY two of them.
#
# The percentage filter is what makes the positional read work: a shareholding row prints
# share counts and percentages side by side ("Promoter and Promoter Group 1,23,45,678
# 100.00 98,76,543 73.50"), and only the percentages can be 0-100 with a decimal point.
PROMOTER_LABEL = re.compile(r"(?i)^\s*(?:total\s+)?(?:\(?[a-d]\)?\s*)?"
                            r"(?:promoter|promoters?\s+and\s+promoter\s+group)")
TOTAL_LABEL = re.compile(r"(?i)^\s*total\b")
PREPOST_CUE = re.compile(r"(?i)pre[\s-]*(?:offer|issue|ipo)")
POSTPRE_CUE = re.compile(r"(?i)post[\s-]*(?:offer|issue|ipo)")
PCT_LIKE = re.compile(r"(?<![\d,.])(\d{1,3}\.\d{1,2})\s*%?(?![\d,])")


def _pct_like(line: str) -> list[float]:
    """Percentage-like values on a line: 0-100 with a decimal point, in order."""
    out = []
    for m in PCT_LIKE.finditer(line or ""):
        v = num(m.group(1))
        if v is not None and 0.0 <= v <= 100.0:
            out.append(v)
    return out


def promoter_from_text(doc: Doc, a: int, b: int, how: str, texts=None) -> dict:
    """`{variable: Value}` for the three promoter variables, or `{}`.

    `texts` may be handed in by the caller. The Capital Structure pages were being read
    twice per document - once here and once by the share-count reader - which together
    accounted for 29 of the 53 seconds this document took.
    """
    own = texts is None
    texts = page_texts(doc.path, a, b) if own else texts
    try:
        for i in sorted(texts):
            t = texts[i] or ""
            if not (PREPOST_CUE.search(t) and POSTPRE_CUE.search(t)):
                continue
            in_promoter_block = False
            for raw in t.splitlines():
                ln = re.sub(r"\s+", " ", raw).strip()
                if not ln:
                    continue
                if PROMOTER_LABEL.match(ln):
                    in_promoter_block = True
                elif re.match(r"(?i)^\s*(?:public|non[\s-]*promoter|others?)\b", ln):
                    in_promoter_block = False
                # A bare "Total" counts only while inside a promoter block, never after
                # the public-shareholder rows have started.
                if not (PROMOTER_LABEL.match(ln)
                        or (in_promoter_block and TOTAL_LABEL.match(ln))):
                    continue
                pcts = _pct_like(ln)
                if len(pcts) != 2:
                    continue
                pre, post = pcts
                src = ln[:280]
                note_tail = ("" if pre >= post else
                             "; NOTE the post-offer figure is the HIGHER of the two, "
                             "which is unusual - check whether the promoter subscribed")
                return {
                    "promoter_pre_pct": _v(
                        doc, "promoter_pre_pct", value=pre, original_unit="%",
                        page=doc.index_to_printed(i), pdf_page_index=i, source_text=src,
                        note=(f"promoter row read from the text line (the table is "
                              f"unruled); the page states both a pre- and a post-offer "
                              f"column and the row carries exactly two percentage-like "
                              f"values; section by {how}{note_tail}")),
                    "promoter_post_pct": _v(
                        doc, "promoter_post_pct", value=post, original_unit="%",
                        page=doc.index_to_printed(i), pdf_page_index=i, source_text=src,
                        note="the second of the two percentages (post-offer)"),
                    "promoter_change_pp": _v(
                        doc, "promoter_change_pp", value=round(post - pre, 4),
                        original_unit="pp", page=doc.index_to_printed(i),
                        pdf_page_index=i, source_text=src,
                        note="post minus pre, in percentage points"),
                }
        return {}
    finally:
        if own:
            del texts


def extract(doc: Doc, texts=None) -> list[Value]:
    want = ["promoter_pre_pct", "promoter_post_pct", "promoter_change_pp",
            "pre_ipo_allotment_price", "pre_ipo_allotment_count"]
    rng, how = find(doc, "capital")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="capital structure section not located") for v in want]
    a, b = rng
    b20 = min(b, a + 20)
    # Table extraction is the expensive operation - twenty pages of it dominated this
    # module's cost - and it produced a promoter percentage on NONE of 412 documents,
    # because these tables carry no ruling lines. So the text is read first (cheaply) and
    # tables are extracted only on the pages whose text actually carries an allotment
    # build-up or a pre/post shareholding column. The same pre-scan the financials block
    # uses, for the same reason.
    if texts is None:
        texts = page_texts(doc.path, a, b20)
    want_tbl = re.compile(r"(?i)date\s+of\s+allotment|issue\s+price"
                          r"|pre[\s-]*(?:offer|issue)|post[\s-]*(?:offer|issue)")
    hot = [i for i in sorted(texts) if want_tbl.search(texts[i] or "")]
    tabs = {}
    for i in hot[:8]:
        tabs.update(page_tables(doc.path, i, i))
    found: dict[str, Value] = {}
    allots = []

    for i in sorted(tabs):
        pr = doc.index_to_printed(i)
        for tbl in tabs[i]:
            if not tbl or len(tbl) < 2:
                continue
            flat = " ".join(" ".join(_cells(r)) for r in tbl[:3]).upper()

            # --- shareholding: a row naming the promoter group with two percentages ---
            if "promoter_post_pct" not in found and re.search(
                    r"PRE[- ]?(?:OFFER|ISSUE)|POST[- ]?(?:OFFER|ISSUE)|% OF", flat):
                for row in tbl:
                    cs = _cells(row)
                    if not cs or not cs[0]:
                        continue
                    if not re.search(r"(?i)^(?:total\s+)?(?:for\s+)?promoter", cs[0]):
                        continue
                    pcts = [num(m.group(1)) for m in PCT.finditer(" ".join(cs[1:]))]
                    if len(pcts) >= 2:
                        pre, post = pcts[0], pcts[-1]
                        src = " | ".join(c for c in cs if c)[:280]
                        found["promoter_pre_pct"] = _v(
                            doc, "promoter_pre_pct", value=pre, original_unit="%", page=pr,
                            pdf_page_index=i, source_text=src,
                            note=f"first of {len(pcts)} percentages on the promoter row "
                                 f"(read as pre-offer); section by {how}")
                        found["promoter_post_pct"] = _v(
                            doc, "promoter_post_pct", value=post, original_unit="%", page=pr,
                            pdf_page_index=i, source_text=src,
                            note=f"last of {len(pcts)} percentages (read as post-offer)")
                        found["promoter_change_pp"] = _v(
                            doc, "promoter_change_pp", value=round(post - pre, 4),
                            original_unit="pp", page=pr, pdf_page_index=i, source_text=src,
                            note="post minus pre, in percentage points")
                        break

            # --- allotment build-up: rows with a date and an issue price -------------
            if re.search(r"DATE OF ALLOTMENT", flat) or re.search(r"ISSUE PRICE", flat):
                for row in tbl[1:]:
                    cs = _cells(row)
                    joined = " ".join(cs)
                    dm = re.search(r"(?i)((?:January|February|March|April|May|June|July|August|"
                                   r"September|October|November|December)\s+\d{1,2},\s*(\d{4}))",
                                   joined)
                    if not dm:
                        continue
                    prices = [num(c) for c in cs if num(c) is not None]
                    if prices:
                        allots.append((int(dm.group(2)), dm.group(1), prices, i,
                                       " | ".join(c for c in cs if c)[:280]))

    if allots:
        allots.sort(key=lambda r: r[0])
        latest = allots[-1]
        found["pre_ipo_allotment_count"] = _v(
            doc, "pre_ipo_allotment_count", value=float(len(allots)), original_unit="count",
            page=doc.index_to_printed(latest[3]), pdf_page_index=latest[3],
            source_text=latest[4], note="rows in the capital build-up carrying a date and a price")
        # No price is reported. A first version took the median of the row's numeric cells,
        # which returned -1.0 for Syngene by averaging a share-transfer row containing
        # negative share counts. The price column cannot be identified positionally across
        # documents, so this is left not_found rather than shipped as a plausible number
        # (hard rule 1). Identifying it needs a header-position map per document layout.
        found["pre_ipo_allotment_price"] = _v(
            doc, "pre_ipo_allotment_price", value=None, status="not_found",
            page=doc.index_to_printed(latest[3]), pdf_page_index=latest[3],
            source_text=latest[4],
            note=f"allotment rows found ({len(allots)}, most recent {latest[1]}) but the "
                 "price column is not positionally identifiable; withheld deliberately")

    # The table reader found nothing on any of 412 documents, because these tables carry
    # no ruling lines. The text reader runs for whatever it missed; the table reader keeps
    # precedence, because a cell boundary is stronger evidence than a position on a line.
    if "promoter_post_pct" not in found:
        found.update(promoter_from_text(doc, a, b20, how, texts=texts))
    return [found.get(v) or _v(doc, v, value=None, status="not_found",
                               note=f"not matched in the capital structure section "
                                    f"(located by {how})") for v in want]

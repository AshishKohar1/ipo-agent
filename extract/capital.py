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
from .base import Doc, Value, EXTRACTOR_VERSION, page_tables, num, find

NAME = "capital"
PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def _cells(row):
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]


def extract(doc: Doc) -> list[Value]:
    want = ["promoter_pre_pct", "promoter_post_pct", "promoter_change_pp",
            "pre_ipo_allotment_price", "pre_ipo_allotment_count"]
    rng, how = find(doc, "capital")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="capital structure section not located") for v in want]
    a, b = rng
    tabs = page_tables(doc.path, a, min(b, a + 20))
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

    return [found.get(v) or _v(doc, v, value=None, status="not_found",
                               note=f"not matched in the capital structure section "
                                    f"(located by {how})") for v in want]

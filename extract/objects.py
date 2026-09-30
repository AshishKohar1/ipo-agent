"""
extract/objects.py — issue size, fresh issue vs offer for sale, uses of proceeds, GCP %.

Sources, in order of reliability:
  1. the cover page, which states the offer in words and totals
  2. "OBJECTS OF THE OFFER", whose table lists each stated use and its amount

The cover is authoritative for the totals; the objects table is authoritative for the
breakdown. Both are captured with provenance so a disagreement is visible rather than
silently resolved.
"""
from __future__ import annotations
import re
from .base import (Doc, Value, EXTRACTOR_VERSION, page_texts, num, to_crore,
                   MONEY_UNIT_RE, find)

NAME = "objects"

# "AGGREGATING UP TO Rs 5,500 MILLION" / "AGGREGATING TO ₹ 8468.60 LAKHS"
AMT = re.compile(r"AGGREGATING\s+(?:UP\s*)?TO\s*(?:₹|`|RS\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*\**\s*"
                 + MONEY_UNIT_RE, re.I)
# a bare amount with a unit, used on covers where the table layout splits the currency sign
BARE = re.compile(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)\s*\**\s*" + MONEY_UNIT_RE, re.I)
FRESH = re.compile(r"FRESH\s+ISSUE", re.I)
OFS = re.compile(r"OFFER\s+FOR\s+SALE", re.I)
GCP = re.compile(r"GENERAL\s+CORPORATE\s+PURPOSE", re.I)
# pre-2012 covers: "PUBLIC ISSUE OF 9,000,000 EQUITY SHARES OF RS 10 EACH ..."
LEGACY_ISSUE = re.compile(r"(?:PUBLIC\s+ISSUE|ISSUE)\s+OF\s+(?:UP\s+TO\s+)?[\d,]{5,}\s+EQUITY\s+SHARES", re.I)


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def extract(doc: Doc) -> list[Value]:
    out: list[Value] = []

    # ---- cover: total issue size ------------------------------------------------
    cover = page_texts(doc.path, 0, 1)
    ctext = " ".join(cover.get(i, "") for i in sorted(cover))
    flat = re.sub(r"\s+", " ", ctext)
    cands = [(num(m.group(1)), m.group(2), m.group(0)) for m in AMT.finditer(flat)]
    if not cands:
        cands = [(num(m.group(1)), m.group(2), m.group(0)) for m in BARE.finditer(flat)]
    cands = [(v, u, s) for v, u, s in cands if v]
    if cands:
        best = max(cands, key=lambda c: to_crore(c[0], c[1]) or 0)
        out.append(_v(doc, "issue_size_cr", value=best[0], original_unit=best[1],
                      value_crore=to_crore(best[0], best[1]), page=1, pdf_page_index=0,
                      source_text=best[2],
                      note=f"largest of {len(cands)} cover amounts; totals exceed components"))
    else:
        out.append(_v(doc, "issue_size_cr", value=None, status="not_found",
                      page=1, pdf_page_index=0, note="no amount+unit on cover pages 1-2"))

    # fresh issue / OFS presence on the cover.
    # Pre-2012 covers do not use the phrase "fresh issue" at all — they read
    # "PUBLIC ISSUE OF n EQUITY SHARES ... AGGREGATING Rs X". A first version therefore
    # reported BOTH flags as 0 for TD Power (2011), which is simply false: that offer was
    # entirely a fresh issue. So when neither modern phrase appears, fall back to the older
    # wording, and when nothing matches at all report not_found rather than a confident 0.
    m_fresh, m_ofs = FRESH.search(flat), OFS.search(flat)
    m_legacy = LEGACY_ISSUE.search(flat)
    if m_fresh or m_ofs:
        for var, m in (("has_fresh_issue", m_fresh), ("has_ofs", m_ofs)):
            out.append(_v(doc, var, value=1.0 if m else 0.0, original_unit="bool",
                          page=1, pdf_page_index=0,
                          source_text=(flat[max(0, m.start() - 80):m.end() + 80] if m else
                                       "neither phrase on the cover; the other component was found"),
                          note="modern cover wording"))
    elif m_legacy:
        out.append(_v(doc, "has_fresh_issue", value=1.0, original_unit="bool", page=1,
                      pdf_page_index=0,
                      source_text=flat[max(0, m_legacy.start() - 40):m_legacy.end() + 120],
                      note="pre-2012 wording: 'public issue of ... equity shares' with no "
                           "offer-for-sale clause, i.e. a fresh issue"))
        out.append(_v(doc, "has_ofs", value=0.0, original_unit="bool", page=1,
                      pdf_page_index=0, source_text=None,
                      note="no offer-for-sale clause on a pre-2012 cover"))
    else:
        for var in ("has_fresh_issue", "has_ofs"):
            out.append(_v(doc, var, value=None, status="not_found", page=1, pdf_page_index=0,
                          note="neither modern nor legacy issue wording matched on the cover"))

    # ---- objects section: uses of proceeds --------------------------------------
    rng, how = find(doc, "objects")
    if not rng:
        out.append(_v(doc, "uses_of_proceeds_n", value=None, status="not_found",
                      note="objects section not located"))
        return out
    a, b = rng
    texts = page_texts(doc.path, a, min(b, a + 12))
    uses, gcp_amt, first_page = [], None, None
    for i in sorted(texts):
        for ln in (texts[i] or "").splitlines():
            s = ln.strip()
            if not s or len(s) < 12:
                continue
            # a stated use is a line naming a purpose next to an amount
            if re.search(r"(?i)(fund|repay|prepay|capital expenditure|working capital|"
                         r"investment in|acquisition|inorganic|general corporate|"
                         r"purchase|expansion|debt|loan|offer expenses)", s) and BARE.search(s):
                uses.append((i, s))
                first_page = first_page if first_page is not None else i
            if GCP.search(s) and BARE.search(s) and gcp_amt is None:
                m = BARE.search(s)
                gcp_amt = (num(m.group(1)), m.group(2), i, s)

    # de-duplicate by the purpose wording, since tables often wrap across lines
    seen, uniq = set(), []
    for i, s in uses:
        k = re.sub(r"[^a-z]", "", s.lower())[:38]
        if k not in seen:
            seen.add(k); uniq.append((i, s))
    out.append(_v(doc, "uses_of_proceeds_n", value=float(len(uniq)) if uniq else None,
                  original_unit="count", page=doc.index_to_printed(a), pdf_page_index=a,
                  status="ok" if uniq else "not_found",
                  source_text=(uniq[0][1] if uniq else None),
                  note=f"section located by {how}; {len(uniq)} distinct stated uses"))

    if gcp_amt:
        v, u, i, s = gcp_amt
        out.append(_v(doc, "gcp_amount_cr", value=v, original_unit=u,
                      value_crore=to_crore(v, u), page=doc.index_to_printed(i),
                      pdf_page_index=i, source_text=s))
    else:
        out.append(_v(doc, "gcp_amount_cr", value=None, status="not_found",
                      note="no general-corporate-purpose amount in the objects table"))
    return out

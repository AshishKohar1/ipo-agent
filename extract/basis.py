"""
extract/basis.py — "BASIS FOR THE OFFER PRICE": EPS, RoNW, NAV, P/E and the peer table.

Table-driven, not text-driven. A first text-regex version of this module produced
confidently wrong values: it read EPS and NAV as 10.0 from the parenthetical
"(Face value of Rs 10 each)", and took the P/E off a line about the Sensex and Nifty. Those
are exactly the silent corruptions hard rule 1 warns about, so every value here is now
anchored to a real table header and its row label. Where a table is absent the value is
`not_found` — never inferred from prose.

Each accounting ratio is reported for the most recent financial year in the table, with
the weighted average captured separately where the RHP gives one.
"""
from __future__ import annotations
import re
from .base import Doc, Value, EXTRACTOR_VERSION, page_tables, num, find

NAME = "basis"
FY = re.compile(r"(?:MARCH|SEPTEMBER|JUNE|DECEMBER)\s*\d{0,2},?\s*(\d{4})", re.I)


def _v(doc: Doc, var: str, **kw) -> Value:
    return Value(company=doc.company, doc_type=doc.doc_type, variable=var,
                 doc_url=doc.doc_url, sha256=doc.sha256, extractor=NAME,
                 extractor_version=EXTRACTOR_VERSION, **kw)


def _cells(row) -> list[str]:
    return [re.sub(r"\s+", " ", (c or "")).strip() for c in row]


def _nums(row) -> list[float]:
    return [v for v in (num(c) for c in _cells(row)) if v is not None]


def _header(tbl) -> str:
    """Flatten the first two rows — RHP headers routinely wrap onto a second line."""
    return " ".join(" ".join(_cells(r)) for r in tbl[:2]).upper()


def _latest_year_row(tbl):
    """The data row for the most recent financial year, and that year."""
    best = None
    for r in tbl:
        cs = _cells(r)
        m = FY.search(" ".join(cs))
        if m and _nums(r):
            y = int(m.group(1))
            if best is None or y > best[0]:
                best = (y, r)
    return best


def extract(doc: Doc) -> list[Value]:
    out: list[Value] = []
    want = ["eps_basic", "eps_weighted_avg", "ronw_pct", "nav_per_share", "pe_at_issue",
            "peer_count"]
    rng, how = find(doc, "basis")
    if not rng:
        return [_v(doc, v, value=None, status="not_found",
                   note="basis-for-offer-price section not located") for v in want]
    a, b = rng
    tabs = page_tables(doc.path, a, min(b, a + 14))
    found: dict[str, Value] = {}

    for i in sorted(tabs):
        for tbl in tabs[i]:
            if not tbl or len(tbl) < 2:
                continue
            h = _header(tbl)
            pr = doc.index_to_printed(i)

            # --- EPS table: header names Basic EPS -------------------------------
            if "BASIC EPS" in h and "eps_basic" not in found:
                lr = _latest_year_row(tbl)
                if lr:
                    y, row = lr
                    found["eps_basic"] = _v(doc, "eps_basic", value=_nums(row)[0],
                                            original_unit="Rs", page=pr, pdf_page_index=i,
                                            source_text=" | ".join(c for c in _cells(row) if c),
                                            note=f"basic EPS for FY ending {y}; table header "
                                                 f"'Basic EPS'; section by {how}")
                for row in tbl:
                    if re.search(r"(?i)weighted\s+average", " ".join(_cells(row))) and _nums(row):
                        found["eps_weighted_avg"] = _v(
                            doc, "eps_weighted_avg", value=_nums(row)[0], original_unit="Rs",
                            page=pr, pdf_page_index=i,
                            source_text=" | ".join(c for c in _cells(row) if c),
                            note="weighted-average basic EPS as printed")

            # --- RoNW table ------------------------------------------------------
            if "RONW" in h and "ronw_pct" not in found:
                lr = _latest_year_row(tbl)
                if lr:
                    y, row = lr
                    found["ronw_pct"] = _v(doc, "ronw_pct", value=_nums(row)[0],
                                           original_unit="%", page=pr, pdf_page_index=i,
                                           source_text=" | ".join(c for c in _cells(row) if c),
                                           note=f"RoNW for FY ending {y}")

            # --- P/E table: rows read "Based on basic EPS ..." -------------------
            if "P/E" in h and "pe_at_issue" not in found:
                for row in tbl:
                    txt = " ".join(_cells(row))
                    if re.search(r"(?i)based on basic", txt) and _nums(row):
                        ns = _nums(row)
                        # two columns = floor and cap price; the offer price is the cap
                        found["pe_at_issue"] = _v(
                            doc, "pe_at_issue", value=ns[-1], original_unit="x",
                            page=pr, pdf_page_index=i,
                            source_text=" | ".join(c for c in _cells(row) if c),
                            note=("P/E on basic EPS at the upper end of the price band "
                                  f"({'floor ' + str(ns[0]) + ', cap ' + str(ns[-1]) if len(ns) > 1 else 'single value'})"))
                        break

            # --- NAV table: a money-only header with 'As on <date>' rows ---------
            if "nav_per_share" not in found and re.search(r"(?i)net asset value|NAV", h + " " +
                                                          " ".join(" ".join(_cells(r)) for r in tbl[:4])):
                for row in tbl:
                    txt = " ".join(_cells(row))
                    if re.search(r"(?i)^as on|as at", txt.strip()) and _nums(row):
                        found["nav_per_share"] = _v(
                            doc, "nav_per_share", value=_nums(row)[0], original_unit="Rs",
                            page=pr, pdf_page_index=i,
                            source_text=" | ".join(c for c in _cells(row) if c),
                            note="NAV per equity share before the offer")
                        break

            # --- peer comparison table -------------------------------------------
            if "peer_count" not in found and "P/E" in h and re.search(
                    r"(?i)name of|company|peer", h):
                rows = []
                for row in tbl[2:]:
                    cs = _cells(row)
                    if cs and cs[0] and re.search(r"(?i)(ltd|limited|industries|pharma|labs|"
                                                  r"motors|bank|technologies|corp)", cs[0]):
                        rows.append(row)
                if rows:
                    found["peer_count"] = _v(doc, "peer_count", value=float(len(rows)),
                                             original_unit="count", page=pr, pdf_page_index=i,
                                             source_text=" | ".join(c for c in _cells(rows[0]) if c),
                                             note="rows in the listed-peer comparison table")
                    for k, row in enumerate(rows[:5], start=1):
                        ns = _nums(row)
                        found[f"peer_{k}_pe"] = _v(
                            doc, f"peer_{k}_pe", value=ns[-1] if ns else None,
                            original_unit="x", page=pr, pdf_page_index=i,
                            status="ok" if ns else "not_found",
                            source_text=" | ".join(c for c in _cells(row) if c),
                            note=f"peer '{_cells(row)[0][:40]}'; last numeric column — "
                                 "column order varies, verify before modelling")

    # ---- anchored text fallback -------------------------------------------------
    # Modern RHPs (e.g. Hyundai 2024) defeat pdfplumber's table detection in this section,
    # so the same values are read from text lines — but only ever from a line that carries
    # the exact anchoring phrase, never from a loose "P/E" mention.
    if any(k not in found for k in ("eps_basic", "ronw_pct", "nav_per_share", "pe_at_issue")):
        from .base import page_texts
        tx = page_texts(doc.path, a, min(b, a + 14))
        FV = re.compile(r"(?i)face\s+value")

        def scan(anchor: re.Pattern, var: str, unit: str, note: str, pick=-1):
            if var in found:
                return
            for i in sorted(tx):
                for ln in (tx[i] or "").splitlines():
                    s = ln.strip()
                    m = anchor.search(s)
                    if not m:
                        continue
                    tail = s[m.end():]
                    # drop any parenthetical face-value clause before reading numbers
                    tail = re.sub(r"\((?:[^()]*face\s+value[^()]*)\)", " ", tail, flags=re.I)
                    ns = [v for v in (num(x) for x in
                                      re.findall(r"(?<![\d.])(\d[\d,]*\.?\d*)", tail))
                          if v is not None]
                    if not ns or (FV.search(s) and var in ("eps_basic", "nav_per_share")
                                  and len(ns) == 1):
                        continue
                    found[var] = _v(doc, var, value=ns[pick], original_unit=unit,
                                    page=doc.index_to_printed(i), pdf_page_index=i,
                                    source_text=s, note=note + " (anchored text fallback)")
                    return

        scan(re.compile(r"(?i)based on basic EPS for (?:the )?(?:Financial Year|Fiscal|the year)[^\d]{0,20}"),
             "pe_at_issue", "x", "P/E on basic EPS at the offer price")
        # EPS from text rows "Fiscal 2011 19.38 1 19.46 1": take the row for the LATEST
        # fiscal year, and never accept a year-like number as an EPS. A first version
        # returned 2,026.00 for CapitalNumbers (the year 2026, off a "Fiscal 2025 Fiscal
        # 2026 Fiscal 2027" header row) and Fiscal 2009's EPS for TD Power's 2011 issue.
        if "eps_basic" not in found:
            cands = []
            for i in sorted(tx):
                for ln in (tx[i] or "").splitlines():
                    s = ln.strip()
                    m = re.match(r"(?i)^(?:Fiscal|Financial Year|FY)\s*(20\d\d)\b", s)
                    if not m:
                        continue
                    yr = int(m.group(1))
                    if len(re.findall(r"(?i)\b(?:Fiscal|Financial Year|FY)\s*20\d\d", s)) > 1:
                        continue                      # a multi-year header row, not data
                    ns = [v for v in (num(x) for x in
                                      re.findall(r"(?<![\d.])(\d[\d,]*\.?\d*)", s[m.end():]))
                          if v is not None and not (1990 <= v <= 2100)]
                    if ns:
                        cands.append((yr, ns[0], i, s))
            if cands:
                yr, val, i, s = max(cands, key=lambda c: c[0])
                found["eps_basic"] = _v(
                    doc, "eps_basic", value=val, original_unit="Rs",
                    page=doc.index_to_printed(i), pdf_page_index=i, source_text=s,
                    note=f"basic EPS for the latest fiscal year in the table (FY{yr}) of "
                         f"{len(cands)} year rows; year-like numbers rejected "
                         "(anchored text fallback)")
        # NAV: only from a row-like line that BEGINS with the label. A first version
        # matched a footnote starting "31, 2024; Net asset value per equity share based
        # on..." and returned 31.0 — the day of a date.
        scan(re.compile(r"(?i)^(?:As at |As on )?Net Asset Value Per Equity Share"
                        r"(?:\s*\(?(?:NAV)?\)?)?(?:\s*Amount\s*\(in\s*₹\))?\s*[:\-]?"),
             "nav_per_share", "Rs", "NAV per equity share, from a row-labelled line")

    for v in want:
        out.append(found.get(v) or _v(doc, v, value=None, status="not_found",
                                      note=f"no anchoring table or text anchor found "
                                           f"(section located by {how})"))
    out += [v for k, v in found.items() if k.startswith("peer_") and k != "peer_count"]
    return out

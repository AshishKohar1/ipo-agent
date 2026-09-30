"""
extract/base.py — shared machinery for the RHP extractors (PLAN.md Stage 8).

Every extracted value carries full provenance (Stage 8 step 5): the value, its original
unit, the value normalised to Rs crore, the page number, the exact source text line, the
document URL, the document SHA-256 and the extractor version.

Section location (step 2): the table of contents gives printed page numbers; the offset
between printed and PDF page index is measured from page footers rather than assumed. A
regex scan over headings is the fallback when the TOC cannot be parsed. Only the located
page ranges are ever extracted, so a 476-page document costs a few pages of work.

Memory (rule 14): `page_texts()` opens the PDF, extracts only the requested range, and
closes it before returning. Nothing holds a page object.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

EXTRACTOR_VERSION = "1.0.0"

# ---------------------------------------------------------------- units
# Indian RHPs mix lakh, million and crore, sometimes within one page. Everything is
# normalised to Rs crore, and the original unit is always preserved alongside.
UNIT_TO_CR = {
    "CRORE": 1.0, "CRORES": 1.0, "CR": 1.0, "CR.": 1.0,
    "MILLION": 0.1, "MN": 0.1, "MILLIONS": 0.1,
    "LAKH": 0.01, "LAKHS": 0.01, "LAC": 0.01, "LACS": 0.01,
    "BILLION": 100.0, "BN": 100.0,
    "THOUSAND": 0.0001,
}
MONEY_UNIT_RE = r"(CRORES?|CR\.?|MILLIONS?|MN|LAKHS?|LACS?|BILLION|BN|THOUSAND)"


def to_crore(value: float | None, unit: str | None) -> float | None:
    """Convert an amount to Rs crore. Returns None if the unit is unknown, never a guess."""
    if value is None or unit is None:
        return None
    f = UNIT_TO_CR.get(str(unit).strip().upper().rstrip("."))
    return None if f is None else float(value) * f


def num(s: str | None) -> float | None:
    """Parse an Indian-formatted number: '1,01,47,058' or '5,500.00' or '(123)' negative."""
    if s is None:
        return None
    t = str(s).strip().replace("₹", "").replace("`", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "").replace("%", "").strip()
    if not re.fullmatch(r"-?\d*\.?\d+", t or ""):
        return None
    v = float(t)
    return -v if neg else v


@dataclass
class Value:
    """One extracted datum with its provenance."""
    company: str
    doc_type: str
    variable: str
    value: float | None
    original_unit: str | None = None
    value_crore: float | None = None
    page: int | None = None                 # printed page number where found
    pdf_page_index: int | None = None
    source_text: str | None = None          # the exact line the value came from
    doc_url: str | None = None
    sha256: str | None = None
    extractor: str | None = None
    extractor_version: str = EXTRACTOR_VERSION
    status: str = "ok"                      # ok | not_found | unreadable | ambiguous
    note: str = ""

    def as_row(self) -> dict:
        d = asdict(self)
        if d["source_text"]:
            d["source_text"] = re.sub(r"\s+", " ", d["source_text"]).strip()[:300]
        return d


@dataclass
class Doc:
    """A verified document plus its located section ranges."""
    path: Path
    company: str
    doc_type: str
    sha256: str
    doc_url: str
    n_pages: int
    offset: int = 0                         # pdf_index - printed_page
    toc: dict = field(default_factory=dict)  # SECTION NAME -> printed start page

    def printed_to_index(self, printed: int) -> int:
        return max(0, min(self.n_pages - 1, printed + self.offset))

    def index_to_printed(self, idx: int) -> int:
        return idx - self.offset


# ---------------------------------------------------------------- pdf access
def page_texts(path: Path, first_idx: int, last_idx: int) -> dict[int, str]:
    """Text of PDF pages [first_idx, last_idx] inclusive. Opens and closes the file."""
    import pdfplumber
    out: dict[int, str] = {}
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in range(max(0, first_idx), min(n - 1, last_idx) + 1):
            try:
                out[i] = pdf.pages[i].extract_text() or ""
            except Exception:
                out[i] = ""
            finally:
                try:
                    pdf.pages[i].flush_cache()      # release per-page objects
                except Exception:
                    pass
    return out


def page_tables(path: Path, first_idx: int, last_idx: int) -> dict[int, list]:
    """Tables of PDF pages [first_idx, last_idx]. Opens and closes the file."""
    import pdfplumber
    out: dict[int, list] = {}
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in range(max(0, first_idx), min(n - 1, last_idx) + 1):
            try:
                out[i] = pdf.pages[i].extract_tables() or []
            except Exception:
                out[i] = []
            finally:
                try:
                    pdf.pages[i].flush_cache()
                except Exception:
                    pass
    return out


# ---------------------------------------------------------------- section location
# the ':' matters — TOC entries look like "SECTION II: RISK FACTORS ......... 16"
TOC_LINE = re.compile(r"^(?P<name>[A-Z][A-Z0-9 ,:'’\-&/\(\)\.]{6,90}?)\s*\.{3,}\s*(?P<page>\d{1,4})\s*$")

# canonical section -> ordered list of heading patterns to look for
SECTIONS = {
    "objects": [r"OBJECTS OF THE (?:OFFER|ISSUE)"],
    "basis": [r"BASIS FOR (?:THE )?(?:OFFER|ISSUE) PRICE"],
    "capital": [r"CAPITAL STRUCTURE"],
    "financials": [r"(?:RESTATED )?FINANCIAL (?:INFORMATION|STATEMENTS)",
                   r"SUMMARY OF FINANCIAL INFORMATION"],
    "rpt": [r"RELATED PARTY TRANSACTIONS"],
    "litigation": [r"OUTSTANDING LITIGATION", r"LEGAL PROCEEDINGS"],
    "risk": [r"(?:SECTION II:\s*)?RISK FACTORS"],
    "management": [r"OUR MANAGEMENT"],
    "promoters": [r"OUR PROMOTERS? AND PROMOTER GROUP"],
    "mda": [r"MANAGEMENT'?S DISCUSSION AND ANALYSIS"],
}


def measure_offset(path: Path, n_pages: int) -> int:
    """offset = pdf_index - printed_page, measured from page footers (the modal value)."""
    from collections import Counter
    probes = [i for i in (10, 25, 50, 80, 120, 200) if i < n_pages]
    texts = {}
    for i in probes:                                  # one open per probe keeps memory flat
        texts.update(page_texts(path, i, i))
    votes = []
    for i, t in texts.items():
        lines = [ln.strip() for ln in (t or "").splitlines() if ln.strip()]
        for ln in (lines[-1:] + lines[-2:-1]) if lines else []:
            m = re.fullmatch(r"(\d{1,4})", ln)
            if m:
                votes.append(i - int(m.group(1)))
                break
    return Counter(votes).most_common(1)[0][0] if votes else 0


def parse_toc(path: Path, n_pages: int) -> dict[str, int]:
    """SECTION NAME -> printed page, from the table of contents."""
    toc: dict[str, int] = {}
    texts = page_texts(path, 0, min(9, n_pages - 1))
    for i in sorted(texts):
        t = texts[i]
        if "TABLE OF CONTENTS" not in (t or "").upper():
            continue
        for ln in t.splitlines():
            m = TOC_LINE.match(ln.strip())
            if m:
                toc[re.sub(r"\s+", " ", m.group("name")).strip()] = int(m.group("page"))
    return toc


def locate(doc: Doc, key: str) -> tuple[int, int] | None:
    """(first_idx, last_idx) for a canonical section, from the TOC where possible.
    The end is the next TOC entry that starts after it, capped to 60 pages."""
    pats = SECTIONS[key]
    entries = sorted(doc.toc.items(), key=lambda kv: kv[1])
    for pat in pats:
        for j, (name, pg) in enumerate(entries):
            if re.search(pat, name):
                nxt = next((p for _, p in entries[j + 1:] if p > pg), pg + 40)
                a = doc.printed_to_index(pg)
                b = doc.printed_to_index(min(nxt - 1, pg + 60))
                return a, max(a, b)
    return None


def locate_by_scan(doc: Doc, key: str, window: int = 40) -> tuple[int, int] | None:
    """Regex fallback (step 2): scan page text for the heading itself."""
    pats = SECTIONS[key]
    step = 8
    for start in range(0, doc.n_pages, step):
        texts = page_texts(doc.path, start, min(start + step - 1, doc.n_pages - 1))
        for i in sorted(texts):
            head = "\n".join((texts[i] or "").splitlines()[:6]).upper()
            for pat in pats:
                if re.search(pat, head):
                    return i, min(i + window, doc.n_pages - 1)
    return None


def find(doc: Doc, key: str) -> tuple[tuple[int, int] | None, str]:
    r = locate(doc, key)
    if r:
        return r, "toc"
    r = locate_by_scan(doc, key)
    return (r, "scan") if r else (None, "not_located")

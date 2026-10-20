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
    # Decision H10. Why a value is absent, so that a field sitting at 45% at the end of the
    # batch is interpretable rather than just low. One of:
    #   not_present_on_page   the section was located and read; the document does not
    #                         disclose this field (or it is structurally inapplicable)
    #   present_but_unparsed  the disclosure IS on the page — a header, a column, a
    #                         partial match — but no value could be read from it safely
    #   section_not_found     the section carrying this field could not be located
    #   document_unavailable  no document was obtained, or it failed verification
    # Empty for a value that was extracted (status ok or ambiguous).
    missing_reason: str = ""

    def as_row(self) -> dict:
        d = asdict(self)
        if d["source_text"]:
            d["source_text"] = re.sub(r"\s+", " ", d["source_text"]).strip()[:300]
        if d["status"] in ("ok", "ambiguous"):
            d["missing_reason"] = ""            # nothing is missing
        elif not d["missing_reason"]:
            d["missing_reason"] = classify_missing_reason(d["note"], d["status"])
        return d


# ---------------------------------------------------------------- H10 classification
# The reason is set explicitly at each refusal site in `extract/h6.py`. This derives it from
# the note as a fallback, so rows already written by a running batch can be backfilled
# without re-reading a single PDF (`backfill_missing_reason.py`).
MISSING_REASON_VALUES = ("not_present_on_page", "present_but_unparsed",
                         "section_not_found", "document_unavailable")

_SECTION_NOT_FOUND = re.compile(
    r"(?i)section not located|not located by TOC|could not be located|"
    r"section heading was not found|not be located|heading was not found")
_PRESENT_UNPARSED = re.compile(
    r"(?i)withheld|exists but|column exists|not positionally identifiable|"
    r"no total row|unit NOT FOUND|could not be parsed|no name could be parsed|"
    r"no summable|a nearby clause is not attribution|no value could be read|"
    r"raised [A-Za-z]*Error|not produced by any extractor group")
_DOC_UNAVAILABLE = re.compile(
    r"(?i)source_unresolved|sha256_mismatch|missing_file|not_a_prospectus|"
    r"document unavailable|fetch_failed")


def classify_missing_reason(note: str | None, status: str = "not_found") -> str:
    """Map a refusal note to one of the four H10 reasons. Never guesses outside the four."""
    n = note or ""
    if _DOC_UNAVAILABLE.search(n):
        return "document_unavailable"
    if _SECTION_NOT_FOUND.search(n):
        return "section_not_found"
    if _PRESENT_UNPARSED.search(n) or status == "unreadable":
        return "present_but_unparsed"
    # The default is the honest one: the section was read and the field is simply not there.
    return "not_present_on_page"


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
def _from_cache(path, indices) -> dict[int, str] | None:
    """Page text from the text cache, or None if this document is not cached.

    Imported lazily and failure-tolerant on purpose: the cache is an accelerator, and a
    broken or absent cache must degrade to reading the PDF, never to returning nothing.
    """
    try:
        from . import textcache
        return textcache.pages_at(path, indices)
    except Exception:                                          # noqa: BLE001
        return None


def page_texts(path: Path, first_idx: int, last_idx: int) -> dict[int, str]:
    """Text of PDF pages [first_idx, last_idx] inclusive.

    Served from `extract/textcache.py` when that document has been cached, which is the
    whole point of the cache: every reader reads text through this function, so one
    lookup here puts all of them on the cache without a line changing in any reader. On a
    miss - no cache file, or a cache built from a different file at this path - the PDF is
    opened and closed exactly as before.
    """
    import pdfplumber
    hit = _from_cache(path, range(max(0, first_idx), last_idx + 1))
    if hit is not None:
        return hit
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


def page_texts_at(path: Path, indices) -> dict[int, str]:
    """Text of an arbitrary SET of page indices, in ONE open.

    `page_texts` takes a contiguous range, so reading the table of contents and the six
    offset probes meant seven opens of the same document - and each open re-parses the
    page tree, which on a 582-page prospectus is most of the cost. Per-page caches are
    still flushed, so memory stays flat.
    """
    import pdfplumber
    want = sorted({int(i) for i in indices})
    out: dict[int, str] = {}
    if not want:
        return out
    hit = _from_cache(path, want)
    if hit is not None:
        return hit
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in want:
            if not 0 <= i < n:
                continue
            try:
                out[i] = pdf.pages[i].extract_text() or ""
            except Exception:                                  # noqa: BLE001
                out[i] = ""
            finally:
                try:
                    pdf.pages[i].flush_cache()
                except Exception:                              # noqa: BLE001
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


OFFSET_PROBES = (10, 25, 50, 80, 120, 200)


def measure_offset(path: Path, n_pages: int, texts: dict[int, str] | None = None) -> int:
    """offset = pdf_index - printed_page, measured from page footers (the modal value).

    `texts` lets a caller that has ALREADY read the probe pages supply them instead. The
    original opened the document once per probe - six opens of a 582-page prospectus,
    which is a large share of the cost of extracting it, because every open re-parses the
    page tree. Callers that do not pass anything behave exactly as before.
    """
    from collections import Counter
    probes = [i for i in OFFSET_PROBES if i < n_pages]
    if texts is None:
        texts = {}
        for i in probes:                  # one open per probe keeps memory flat
            texts.update(page_texts(path, i, i))
    else:
        texts = {i: texts[i] for i in probes if i in texts}
    votes = []
    for i, t in texts.items():
        lines = [ln.strip() for ln in (t or "").splitlines() if ln.strip()]
        for ln in (lines[-1:] + lines[-2:-1]) if lines else []:
            m = re.fullmatch(r"(\d{1,4})", ln)
            if m:
                votes.append(i - int(m.group(1)))
                break
    return Counter(votes).most_common(1)[0][0] if votes else 0


def parse_toc(path: Path, n_pages: int,
              texts: dict[int, str] | None = None) -> dict[str, int]:
    """SECTION NAME -> printed page, from the table of contents.

    `texts` lets a caller supply the first ten pages it has already read, for the same
    reason `measure_offset` does: one open instead of two.
    """
    toc: dict[str, int] = {}
    if texts is None:
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

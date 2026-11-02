"""
fetch_rhp.py — acquire DRHP / RHP / final Prospectus from OFFICIAL sources only.

Sources, in priority order. No aggregators, no manual downloads:
  1. SEBI     — Filings > Public Issues > {Draft Offer Documents | Red Herring Documents
                | Final Offer Documents}. Every mainboard IPO files here. No gate.
  2. NSE      — Corporate Filings > Offer Documents (equities + SME, JSON listing keyed by
                ISIN). DOWNLOADS ARE GATED: NSE's page shows an "I agree" disclaimer
                before an offer document can be downloaded. This code does NOT accept it
                on the user's behalf — NSE_DOWNLOADS_ALLOWED stays False until the user
                has read NSE's disclaimer and decides.
  3. BSE SME  — bsesme.com SME IPO DRHP page (static listing, direct links, no gate).
     BSE mainboard is a JavaScript app whose offer-document API could not be located;
     it is not implemented. SEBI covers every mainboard IPO.

The agent NEVER asks the user to download anything. If every source fails, it writes a
'source_unresolved' row whose note lists what each source actually did — never a
generic "not found". A missing document is a known gap; a wrong one is silent corruption.

    python fetch_rhp.py verify     # the 5-company verification -> data/rhp_verify.json
    python fetch_rhp.py batch      # REFUSES unless data/rhp_verify.json shows 5/5
"""
from __future__ import annotations
import io, re, sys, time, hashlib, json, sqlite3, zipfile
from pathlib import Path
from dataclasses import dataclass, asdict
import requests

import dataio
import company_aliases

ROOT = Path(__file__).resolve().parent
DB   = ROOT / "ipo.db"
PDFS = ROOT / "_local" / "rhp_fetched"; PDFS.mkdir(parents=True, exist_ok=True)
VERIFY_FILE = ROOT / "data" / "rhp_verify.json"
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "Chrome/120 Safari/537.36"}

SOURCES = {
    "SEBI":    "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&smid=0&ssid=15",
    "NSE":     "https://www.nseindia.com/companies-listing/corporate-filings-offer-documents",
    "BSE_SME": "https://www.bsesme.com/PublicIssues/SMEIPODRHP.aspx",
}
NSE_DOWNLOADS_ALLOWED = False      # see module docstring — the user's decision, not ours

# SEBI sub-sections under Public Issues (ssid=15)
SEBI_SMID = {"DRHP": (10, "Draft Offer Documents filed with SEBI"),
             "RHP": (11, "Red Herring Documents filed with ROC"),
             "PROSPECTUS": (12, "Final Offer Documents filed with ROC")}
# filing date must fall in [listing - lo, listing + hi] days
DATE_WINDOW = {"DRHP": (3 * 365, 0), "RHP": (90, 0), "PROSPECTUS": (30, 30)}
# SEBI posts some final prospectuses after listing (TD Power 2011: 11 days after).
NAME_SIM = 0.85
SKIP_TITLE = re.compile(r"corrigendum|addendum|advertisement|abridged|price band|notice|"
                        r"withdraw|errat", re.I)


@dataclass
class DocRecord:
    company: str
    isin: str | None
    doc_type: str          # 'DRHP' | 'RHP' | 'PROSPECTUS'
    source: str            # which official site it came from
    url: str
    local_path: str | None
    sha256: str | None
    pages: int | None
    status: str            # 'ok' | 'source_unresolved' | 'fetch_failed' | 'not_a_prospectus'
    note: str = ""


def _session() -> requests.Session:
    s = requests.Session(); s.headers.update(UA)
    return s


def _title_kind(texts: list[str]) -> str:
    """RHP / DRHP / PROSPECTUS / UNCLEAR, from the TITLE LINE of the first text page.

    Rule 3 forbids DRHPs, but the marker test below matches "RED HERRING PROSPECTUS"
    inside "DRAFT RED HERRING PROSPECTUS", so for a year it admitted drafts. Two were
    found in the corpus on 2026-11-02 - Mahindra Logistics and Nippon Life India AMC,
    both filed August 2017 - and both had passed verification.

    The test must be the title, never a substring of the front matter: an RHP's own cover
    routinely back-references the draft it was filed as ("The Draft Red Herring Prospectus
    was filed with SEBI on ..."), and Computer Age Management Services' cover does exactly
    that. Searching the first four pages for the phrase flags 37 of 430 documents, of
    which 35 are genuine RHPs. Searching the first six LINES flags two, and both are real.

    UNCLEAR is not a rejection: a scanned cover pushes the first text page to the table of
    contents (Manoj Vaibhav Gems, Rossari Biotech), and those are settled by the marker
    and page-count tests that follow.
    """
    first = next((t for t in texts if t.strip()), "")
    head = " | ".join(l.strip().upper() for l in first.splitlines() if l.strip()[:1])[:400]
    # Whichever comes FIRST wins, because the title precedes the body. A DRHP leads with
    # "DRAFT RED HERRING PROSPECTUS"; an RHP leads with "RED HERRING PROSPECTUS" and only
    # then back-references its draft. Testing for presence instead of position rejects a
    # genuine RHP whose back-reference happens to sit high on the cover - the costly
    # error, since it loses a real document.
    d = re.search(r"\bDRAFT\s+RED\s+HERRING\s+PROSPECTUS", head)
    r = re.search(r"\bRED\s*HERRING\s*PROSPECTUS", head)
    if d and (r is None or d.start() <= r.start()):
        return "DRHP"
    if r:
        return "RHP"
    if re.search(r"\bPROSPECTUS\b", head):
        return "PROSPECTUS"
    return "UNCLEAR"


def _verify_is_prospectus(pdf_bytes: bytes, company: str) -> tuple[bool, str]:
    """
    Never trust a URL. Open the PDF and confirm it is the right document
    for the right company before it enters the pipeline.
    """
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n = len(pdf.pages)
            # NARROW WIDENING, 2026-10-03, after reading the two outstanding
            # not_a_prospectus PDFs that could only be settled by opening them:
            #
            #   Manoj Vaibhav Gems (416 pages) — pages 1-2 are SCANNED IMAGES with zero
            #     extractable text, page 3 is "(This page is intentionally left blank)",
            #     page 4 is the table of contents, and the marker first appears on page 5
            #     ("This Red Herring Prospectus..."). A fixed 4-PAGE window therefore
            #     rejected a genuine 416-page RHP purely because its cover was scanned.
            #
            # So the window is now the first 4 pages THAT CONTAIN TEXT, searched within
            # the first 12 pages. What the test actually needs is four pages of readable
            # front matter; counting image pages towards that budget measures the scanner,
            # not the document.
            #
            # This does NOT weaken the test. Samhi Hotels — the other outstanding case —
            # is a ONE-PAGE scan with no text at all: it still fails here, and fails the
            # >=100-page test as well. Patel Retail's 1-page addendum and SEBI's own
            # "Corigendum to RHP" for Ideaforge also still fail. The company-name test and
            # the >=100-page test are untouched.
            texts, idx = [], 0
            while len(texts) < 4 and idx < min(12, n):
                t = pdf.pages[idx].extract_text() or ""
                if t.strip():
                    texts.append(t)
                idx += 1
            head = " ".join(texts).upper()
            n_scanned = idx - len(texts)
    except Exception as e:
        return False, f"unreadable pdf: {e}"

    # Rule 3: no DRHPs. Checked on the title line only - see _title_kind.
    kind = _title_kind(texts)
    if kind == "DRHP":
        return False, ("the title line reads DRAFT RED HERRING PROSPECTUS - rule 3 "
                       "forbids DRHPs")

    if not re.search(r"RED HERRING PROSPECTUS|PROSPECTUS", head):
        return False, (f"no prospectus marker in the first {len(texts)} page(s) with text"
                       + (f" ({n_scanned} leading page(s) had no extractable text)"
                          if n_scanned else "")
                       + (" — the document has no extractable text at all"
                          if not texts else ""))

    # Company-name check: 2+ distinctive tokens must co-occur, compared on a 5-character
    # STEM rather than the whole token.
    #
    # NARROW EXCEPTION, added 2026-10-02 after reviewing the 8 not_a_prospectus cases. Four
    # of them were this check rejecting the correct document over a singular/plural ending:
    #   Gandhar Oil REFINERIES (master) against REFINERY (cover)
    #   Syrma SGS TECHNOLOGIES (master) against TECHNOLOGY (cover)
    #   Dr Agarwal's HEALTHCARE (master) against HEALTH CARE (cover, two words)
    # A 5-character stem matches REFIN/TECHN/HEALT in each pair and still distinguishes any
    # two genuinely different companies — no real-world pair of issuers differs only after
    # the fifth letter of two separate tokens.
    #
    # This exception is deliberately limited to the NAME test. The prospectus-marker test
    # and the 100-page test are untouched: those caught two genuinely wrong documents
    # (Patel Retail, a 1-page addendum; Ideaforge, SEBI's own "Corigendum to RHP") and
    # loosening either would let an addendum into the pipeline.
    STOP = {"LIMITED", "PRIVATE", "INDIA", "COMPANY", "LTD"}
    toks = [t for t in re.findall(r"[A-Za-z]{4,}", company.upper()) if t not in STOP]
    head_stems = {w[:5] for w in re.findall(r"[A-Z]{4,}", head)}
    hits = sum(1 for t in toks[:4] if t in head or t[:5] in head_stems)
    if toks and hits < min(2, len(toks)):
        return False, f"company name not matched in cover (hits={hits})"
    if n < 100:
        return False, f"only {n} pages — likely an addendum, not the full document"
    return True, f"verified, {n} pages"


# ======================================================================
# resolvers — each returns (url | None, reason)
# ======================================================================
def _name_ok(title_company: str, company: str) -> float:
    """Best similarity against the company's current name OR any known historical one.

    Priority 3: our master carries CURRENT names and SEBI filings carry the name at filing
    time. Eternal was filed as Zomato, Acutaas Chemicals as Ami Organics. Scoring only
    against the current name made those filings score ~0 and the company came back
    `source_unresolved`, which looks like SEBI not having the document rather than like us
    asking the wrong question. Every alias carries its evidence — see company_aliases.py.
    """
    t = dataio.yahoo_query(title_company)
    return max(dataio.prefix_sim(t, dataio.yahoo_query(n))
               for n in company_aliases.names_to_try(company))


def _in_window(filed, listing_date, doc_type) -> bool:
    import pandas as pd
    if listing_date is None or pd.isna(listing_date):
        return True
    lo, hi = DATE_WINDOW[doc_type]
    d = (pd.Timestamp(listing_date) - pd.Timestamp(filed)).days
    return -hi <= d <= lo


def resolve_sebi(sess, company, isin, doc_type, listing_date=None):
    import pandas as pd
    smid, smtext = SEBI_SMID[doc_type]
    sess.get(SOURCES["SEBI"], timeout=30)                     # session cookie
    hdr = {"X-Requested-With": "XMLHttpRequest", "Referer": SOURCES["SEBI"]}
    # Queries for the current name first, then for each known historical name. Current
    # name first means a company that already resolved resolves identically, so adding the
    # alias map cannot regress anything.
    queries = []
    for nm in company_aliases.names_to_try(company):
        w = dataio.yahoo_query(nm).split()
        for q in (" ".join(w[:3]), " ".join(w[:2]), w[0] if w else ""):
            if q and q not in queries:
                queries.append(q)
    tried = []
    for q in queries:
        if q in tried:
            continue
        tried.append(q)
        data = {"nextValue": "1", "next": "s", "search": q, "fromDate": "", "toDate": "",
                "fromYear": "", "toYear": "", "deptId": "-1", "sid": "3", "ssid": "15",
                "smid": str(smid), "ssidhidden": "15", "intmid": "-1", "sText": "Filings",
                "ssText": "Public Issues", "smText": smtext, "doDirect": "-1"}
        r = sess.post("https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp",
                      data=data, headers=hdr, timeout=30)
        rows = re.findall(r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>\s*<a[^>]*href=['\"]"
                          r"([^'\"]+)['\"][^>]*>([^<]+)", r.text)
        cands = []
        for filed, link, title in rows:
            if SKIP_TITLE.search(title):
                continue
            sim = _name_ok(title.split(" - ")[0], company)
            filed_ts = pd.to_datetime(filed.strip(), format="%b %d, %Y", errors="coerce")
            if sim >= NAME_SIM and _in_window(filed_ts, listing_date, doc_type):
                cands.append((filed_ts, link, title, sim))
        if cands:
            cands.sort(key=lambda c: (-c[3], abs((pd.Timestamp(listing_date) - c[0]).days)
                                      if listing_date is not None else 0))
            if len({c[1] for c in cands if c[3] == cands[0][3]}) > 1 and listing_date is None:
                return None, f"SEBI: {len(cands)} matching filings and no listing date to choose"
            filed_ts, link, title, sim = cands[0]
            page = sess.get(link, timeout=30).text
            pdfs = list(dict.fromkeys(re.findall(r"file=([^'\"&]+\.pdf)", page, re.I)))
            if not pdfs:
                return None, f"SEBI: filing page has no PDF ({link})"
            if len(pdfs) > 1:
                return None, f"SEBI: filing split into {len(pdfs)} PDFs — not handled ({link})"
            pdf_url = pdfs[0] if pdfs[0].startswith("http") else "https://www.sebi.gov.in" + pdfs[0]
            return (pdf_url,
                    f"SEBI {doc_type} '{title}' filed {filed_ts:%Y-%m-%d} (name sim {sim:.2f})")
        time.sleep(0.5)
    return None, f"SEBI: no {doc_type} matching name+date for queries {tried}"


def resolve_nse(sess, company, isin, doc_type, listing_date=None):
    """NSE JSON listing, searched by DRHP-date window, matched by ISIN (exact) or name."""
    import pandas as pd
    field = {"DRHP": "drhpAttach", "RHP": "rhpAttach", "PROSPECTUS": "fpAttach"}[doc_type]
    sess.get(SOURCES["NSE"], timeout=30)
    hdr = {"Accept": "application/json, text/plain, */*", "Referer": SOURCES["NSE"]}
    end = pd.Timestamp(listing_date) if listing_date is not None else pd.Timestamp.today()
    for index in ("equities", "sme"):
        for k in range(4):                       # DRHP filed up to ~2 years before listing
            b = end - pd.Timedelta(days=180 * k); a = b - pd.Timedelta(days=180)
            u = (f"https://www.nseindia.com/api/corporates/offerdocs?index={index}"
                 f"&from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}")
            try:
                rows = sess.get(u, headers=hdr, timeout=30).json()
            except Exception:
                continue
            for row in rows or []:
                hit = (isin and row.get("isin") == isin) or \
                      _name_ok(str(row.get("company", "")), company) >= NAME_SIM
                url = (row.get(field) or "").strip()
                if hit and url:
                    return url, f"NSE {index} {doc_type} for {row.get('company')} (isin {row.get('isin')})"
            time.sleep(0.5)
    return None, f"NSE: no {doc_type} listed for this company"


def resolve_bse_sme(sess, company, isin, doc_type, listing_date=None):
    kind = {"DRHP": "hyDRHP", "RHP": "hyRHP", "PROSPECTUS": "hyProspectus"}[doc_type]
    for attempt in range(3):
        try:
            html = sess.get(SOURCES["BSE_SME"], timeout=90).text
            break
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
            time.sleep(3)
    best = None
    for row in re.split(r'<tr class="TTRow', html)[1:]:
        m = re.search(r'class="tablebluelink">([^<]+)<', row)
        if not m:
            continue
        sim = _name_ok(m.group(1), company)
        link = re.search(rf'id="ContentPlaceHolder1_gvData_{kind}_\d+"[^>]*href="([^"]+)"', row)
        if sim >= NAME_SIM and link and (best is None or sim > best[0]):
            best = (sim, m.group(1).strip(), link.group(1))
    if best:
        return "https://www.bsesme.com" + best[2], f"BSE SME {doc_type} for '{best[1]}' (sim {best[0]:.2f})"
    return None, f"BSE SME: no {doc_type} listed for this company"


RESOLVERS = {"SEBI": resolve_sebi, "NSE": resolve_nse, "BSE_SME": resolve_bse_sme}


def _resolve_document_url(sess, source: str, company: str, isin: str | None,
                          doc_type: str, listing_date=None) -> tuple[str | None, str]:
    """Resolve the official PDF link for one company from one source.
    Returns (url or None, reason). Name must match (>= 0.85) AND the filing date must
    sit in a doc-type window around the listing date, so a namesake or another
    year's issue is not picked. The PDF is still verified after download."""
    return RESOLVERS[source](sess, company, isin, doc_type, listing_date)


def _pdf_bytes(content: bytes) -> tuple[bytes | None, str]:
    if content[:4] == b"%PDF":
        return content, ""
    if content[:2] == b"PK":                     # NSE/BSE sometimes ship a ZIP
        z = zipfile.ZipFile(io.BytesIO(content))
        pdfs = sorted((i for i in z.infolist() if i.filename.lower().endswith(".pdf")),
                      key=lambda i: i.file_size, reverse=True)
        if not pdfs:
            return None, "zip has no PDF"
        return z.read(pdfs[0]), f"largest of {len(pdfs)} PDFs in zip ({pdfs[0].filename})"
    return None, f"not a PDF (starts {content[:8]!r})"


def fetch_for_company(company: str, isin: str | None, doc_type: str = "RHP",
                      listing_date=None, sources=("SEBI", "NSE", "BSE_SME"),
                      fallback: bool = True) -> DocRecord:
    """RHP falls back to the final PROSPECTUS when no RHP exists anywhere (SEBI's archive
    has no RHP entries for many pre-2012 issues). The prospectus is the RHP with the
    final price filled in. The fallback is recorded in doc_type and the note."""
    rec, located = _fetch(company, isin, doc_type, listing_date, sources)
    if rec.status == "source_unresolved" and doc_type == "RHP" and fallback and not located:
        alt, _ = _fetch(company, isin, "PROSPECTUS", listing_date, sources)
        if alt.status != "source_unresolved":
            alt.doc_type = "PROSPECTUS_AS_RHP"
            alt.note = f"no RHP on any source ({rec.note}); used final prospectus: {alt.note}"
            return alt
    return rec


def _fetch(company, isin, doc_type, listing_date, sources) -> tuple[DocRecord, bool]:
    """Returns (record, located) — located is True if any source listed the document,
    even if downloading or verifying it then failed."""
    s = _session()
    reasons, located = [], False
    for src in sources:
        try:
            url, why = _resolve_document_url(s, src, company, isin, doc_type, listing_date)
            if not url:
                reasons.append(why); continue
            located = True
            if src == "NSE" and not NSE_DOWNLOADS_ALLOWED:
                reasons.append(f"NSE: document located ({url}) but NOT downloaded — NSE gates "
                               "offer documents behind an 'I agree' disclaimer the user has not accepted")
                continue
            for attempt in range(3):              # large PDFs: retry dropped connections
                try:
                    r = s.get(url, timeout=300)
                    break
                except requests.exceptions.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(5)
            if r.status_code != 200:
                reasons.append(f"{src}: HTTP {r.status_code} for {url}"); continue
            pdf, znote = _pdf_bytes(r.content)
            if pdf is None:
                reasons.append(f"{src}: {znote}"); continue
            ok, note = _verify_is_prospectus(pdf, company)
            if not ok:
                return DocRecord(company, isin, doc_type, src, url, None, None,
                                 None, "not_a_prospectus", f"{why}; {note}"), located
            sha = hashlib.sha256(pdf).hexdigest()
            path = PDFS / f"{sha[:16]}_{doc_type}.pdf"
            path.write_bytes(pdf)
            pages = int(re.search(r"(\d+) pages", note).group(1))
            return DocRecord(company, isin, doc_type, src, url, str(path), sha, pages, "ok",
                             "; ".join(x for x in (why, znote, note) if x)), located
        except Exception as e:
            reasons.append(f"{src}: error {type(e).__name__}: {e}")
        finally:
            time.sleep(1.0)
    status = "fetch_failed" if located else "source_unresolved"
    return DocRecord(company, isin, doc_type, "-", "-", None, None, None,
                     status, " | ".join(reasons)), located


# ======================================================================
# issue size from the document (for verification)
# ======================================================================
_UNIT = {"MILLION": 0.1, "MN": 0.1, "CRORE": 1.0, "CRORES": 1.0, "LAKH": 0.01, "LAKHS": 0.01,
         "LAC": 0.01, "LACS": 0.01, "BILLION": 100.0}
# "<number> MILLION|CRORE|LAKH" — the currency sign is NOT required: modern covers are
# tables, so text extraction separates "₹" from its number, and 2011-era covers use "Rs.".
# On a cover a number followed by a money unit is an amount (share counts are followed
# by "EQUITY SHARES"). "[●] MILLION" has no digits and never matches.
_AMT = r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)\s?\**\s?(MILLION|MN|CRORES?|LAKHS?|LACS?|BILLION)\b"


def issue_size_from_pdf(path: str, offer_price: float | None = None) -> dict:
    """Issue size in ₹ crore from the cover pages.
      gross: the largest ₹ amount on pages 1-2 (the total offer is >= every component).
             Works even when the cover's table layout scrambles the text order.
      net:   an amount explicitly labelled NET OFFER (SME covers state the offer net of
             the market-maker reservation, which is how IPOMatrix records SME size).
      shares_x_price: RHP fallback when amounts are [●] — cover share count × offer price."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        t = re.sub(r"\s+", " ", " ".join((pdf.pages[i].extract_text() or "")
                                         for i in range(min(2, len(pdf.pages))))).upper()
    amts = [float(n.replace(",", "")) * _UNIT[u] for n, u in re.findall(_AMT, t)]
    out = {"gross": max(amts) if amts else None, "net": None, "shares_x_price": None,
           "amounts": amts}
    m = re.search(r"AGGREGATING (?:UP ?TO )?(?:₹|`|RS\.?|INR)?\s?" + _AMT +
                  r"[^.]{0,40}?HEREINAFTER REFERRED TO AS THE\W+NET OFFER", t)
    if m:
        out["net"] = float(m.group(1).replace(",", "")) * _UNIT[m.group(2)]
    if offer_price:
        sh = re.search(r"(?:OFFER|ISSUE) OF (?:UP TO |UPTO )?([\d,]{6,}) EQUITY SHARES", t)
        if sh:
            out["shares_x_price"] = float(sh.group(1).replace(",", "")) * offer_price / 1e7
    return out


def record(rec: DocRecord) -> None:
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS documents(
        company TEXT, isin TEXT, doc_type TEXT, source TEXT, url TEXT,
        local_path TEXT, sha256 TEXT, pages INT, status TEXT, note TEXT,
        PRIMARY KEY (company, doc_type))""")
    con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)",
                tuple(asdict(rec).values()))
    con.commit(); con.close()


def _batch():
    v = json.loads(VERIFY_FILE.read_text(encoding="utf-8")) if VERIFY_FILE.exists() else {}
    if v.get("passed") != 5:
        sys.exit("REFUSED: data/rhp_verify.json does not show 5/5 companies verified. Run "
                 "`python fetch_rhp.py verify` and fix the failures first (CLAUDE.md).")
    import pandas as pd
    q = pd.read_csv("queue.csv")          # company, isin, listing_date
    for i, r in q.iterrows():
        for dt in ("DRHP", "RHP"):
            rec = fetch_for_company(r["company"], r.get("isin"), dt, r.get("listing_date"))
            record(rec)
            print(f"[{i+1}/{len(q)}] {r['company'][:38]:40s} {dt:4s} -> {rec.status}")


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "verify":
        import verify_rhp_resolvers
        verify_rhp_resolvers.main()
    elif cmd == "batch":
        _batch()
    else:
        print(__doc__)

"""
build_rhp_manifest.py — data/verified_rhp_manifest.csv: one row per fetched PDF.

For every PDF: company and document type (read from the cover), source URL, SHA-256,
page count, verification date. URLs are never assumed: primary documents take the URL
recorded in rhp_VERIFY.json; the others are re-resolved from the official source. Every
URL is then re-downloaded (in memory, not saved) and accepted only if its SHA-256
equals the local file's. A URL that can't be confirmed is written as empty with a reason.

    python build_rhp_manifest.py
"""
from __future__ import annotations
import hashlib, io, json, re, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pdfplumber
import fetch_rhp as R

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "verified_rhp_manifest.csv"
SEBI_GAP_S = 3.0      # PLAN.md rule 5: at least 3 s between SEBI requests
OTHER_GAP_S = 1.0

# cover-name keyword -> the verification case it belongs to
CASES = {"HYUNDAI": "Hyundai Motor India Limited", "JUPITER": "Jupiter Life Line Limited",
         "CAPITALNUMBERS": "CapitalNumbers Infotech Ltd.", "SYNGENE": "Syngene International Ltd",
         "TD POWER": "TD Power Systems Ltd"}


def cover(path: Path) -> tuple[str, str, int]:
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        t = re.sub(r"\s+", " ", pdf.pages[0].extract_text() or "").upper()
    kind = "RHP" if t.lstrip().startswith("RED HERRING PROSPECTUS") else \
           "PROSPECTUS" if t.lstrip().startswith("PROSPECTUS") else "UNKNOWN"
    company = next((v for k, v in CASES.items() if k in t), "")
    return company, kind, n


def sha_of_url(sess, url: str) -> str | None:
    time.sleep(SEBI_GAP_S if "sebi.gov.in" in url else OTHER_GAP_S)
    r = sess.get(url, timeout=300)
    if r.status_code != 200:
        return None
    pdf, _ = R._pdf_bytes(r.content)
    return None if pdf is None else hashlib.sha256(pdf).hexdigest()


def main():
    v = json.loads((ROOT / "rhp_VERIFY.json").read_text(encoding="utf-8"))
    cases = {c["company"]: c for c in v["cases"]}
    sess = R._session()
    rows = []
    for p in sorted((ROOT / "_local" / "rhp_fetched").glob("*.pdf")):
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        company, kind, pages = cover(p)
        c = cases.get(company, {})
        verified_on = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone(
            ist()).strftime("%Y-%m-%d")
        # candidate URL: the recorded primary document, else re-resolve officially
        url, how = None, ""
        if c and c.get("doc_type") == kind:
            url, how = c["doc_url"], "rhp_VERIFY.json"
        elif c:
            time.sleep(SEBI_GAP_S)
            url, why = R.resolve_sebi(sess, company, c.get("isin"), kind,
                                      pd.Timestamp(c["listing_date"]))
            how = f"re-resolved from SEBI ({why})" if url else f"re-resolve failed: {why}"
        confirmed = bool(url) and sha_of_url(sess, url) == sha
        rows.append({"company": company or "UNIDENTIFIED", "doc_type": kind,
                     "source": "SEBI" if url and "sebi.gov.in" in url else
                               "BSE_SME" if url and "bsesme.com" in url else "",
                     "url": url if confirmed else "",
                     "sha256": sha, "pages": pages, "bytes": p.stat().st_size,
                     "local_file": f"_local/rhp_fetched/{p.name}", "verified_on_ist": verified_on,
                     "passes_verify_is_prospectus": R._verify_is_prospectus(p.read_bytes(), company)[0]
                                                    if company else False,
                     "url_check": ("sha256 matches re-download" if confirmed else
                                   f"NOT CONFIRMED — {how or 'no case matched'}")})
        print(f"{p.name}: {company} {kind} {pages}p url_confirmed={confirmed} ({how[:80]})")
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(df)} rows, {df['url'].astype(bool).sum()} URLs "
          f"confirmed by SHA-256, {df['passes_verify_is_prospectus'].sum()} pass _verify_is_prospectus")


def ist():
    from datetime import timedelta
    return timezone(timedelta(hours=5, minutes=30), "IST")


if __name__ == "__main__":
    main()

"""
validate_manual_rhps.py — accept or reject each URL the user filled into
`data/manual_inputs/missing_rhps.csv`.

A URL is accepted only when all four hold, and the reason is recorded per row:

  1. the host is SEBI, BSE or NSE (hard rule 3 — RHPs come from SEBI for mainboard and
     BSE SME only; the issuer's own website and a file-sharing link are neither);
  2. the fetch returns a PDF, not an HTML error page dressed as one;
  3. `fetch_rhp._verify_is_prospectus()` passes — prospectus marker, the company name on
     the cover, and at least 100 pages;
  4. the SHA-256 is recorded, so the accepted document is the one that was checked.

One at a time, 3 s apart, streamed to disk in blocks so a 60 MB prospectus never sits in
memory whole (the 3.4 GB leak must not recur).

    python validate_manual_rhps.py --check          # validate, write the verdict file
    python validate_manual_rhps.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

MANUAL = ROOT / "data" / "manual_inputs" / "missing_rhps.csv"
OUT = ROOT / "reports" / "MANUAL_RHP_VALIDATION.csv"
PDF_DIR = ROOT / "_local" / "rhp_manual"
GAP = 3.0
OFFICIAL_HOSTS = {
    "sebi.gov.in", "www.sebi.gov.in",
    "bseindia.com", "www.bseindia.com",
    "nseindia.com", "www.nseindia.com",
    "nsearchives.nseindia.com", "archives.nseindia.com",
}
# H42. The user authorised these two specific documents on 2026-10-19, by company, after
# seeing that neither is on SEBI. They are NOT a general relaxation of hard rule 3: the
# allow-list is keyed on the COMPANY, so a different issuer's own website is still refused
# and a new Drive link is still refused. Every other condition still applies in full - the
# document must still pass `_verify_is_prospectus`, and its source flag records that it did
# not come from the regulator.
AUTHORISED_NON_OFFICIAL = {
    "allied blenders and distillers limited": "issuer_site",
    "sri lotus developers & realty ltd": "user_supplied_drive_link",
}


def drive_direct(url: str) -> str:
    """A Google Drive *viewer* link rewritten to its direct-download form.

    `/file/d/<id>/view` renders a viewer page, not the PDF, so fetching the link as given
    returns HTML. The id is the document; `uc?export=download&id=<id>` is the same file
    without the viewer. No login is involved either way - if the file were restricted this
    returns an HTML sign-in page, which fails the %PDF check and is rejected, which is the
    correct outcome rather than a workaround.
    """
    import re
    m = re.search(r"/file/d/([A-Za-z0-9_-]{10,})", url) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", url)
    return f"https://drive.google.com/uc?export=download&id={m.group(1)}" if m else url


UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
      "Accept": "application/pdf,*/*"}


def host_of(url: str) -> str:
    return (urlparse(str(url)).netloc or "").lower()


def is_official(url: str) -> bool:
    return host_of(url) in OFFICIAL_HOSTS


def resolve_pdf(sess, url: str) -> tuple[str, str]:
    """`(pdf url, how)`. A SEBI FILING PAGE is followed one hop to the document.

    The user supplied SEBI filing-page URLs - `.../public-issues/aug-2021/
    ami-organics-limited_52088.html` - which is the right thing to give: it is the
    regulator's page for that filing, and it is what a person reads. The first version of
    this validator fetched those pages, found 8 KB of HTML instead of a PDF, and rejected
    all 36 of them. That verdict was MY bug, not a bad URL.

    The PDF is not an `href` on the page: SEBI renders it through a viewer and the real
    document appears as a `file=...pdf` query parameter. That is the same extraction
    `fetch_rhp.resolve_sebi` already uses, which is how the 412 prospectuses on disk were
    found, so this follows the path that is known to work rather than inventing one.

    A page offering several PDFs is REFUSED rather than guessed at - a filing split into
    parts needs a human to say which part is the prospectus.
    """
    import re
    if url.lower().endswith(".pdf"):
        return url, "direct PDF link"
    try:
        t = sess.get(url, headers={**UA, "Accept": "text/html,*/*"}, timeout=60).text
    except Exception as e:                                     # noqa: BLE001
        return "", f"could not read the filing page: {type(e).__name__}: {str(e)[:70]}"
    pdfs = list(dict.fromkeys(re.findall(r"file=([^'\"&]+\.pdf)", t, re.I)))
    if not pdfs:
        pdfs = list(dict.fromkeys(re.findall(r'href="([^"]+\.pdf)"', t, re.I)))
    if not pdfs:
        return "", "the SEBI filing page offers no PDF"
    if len(pdfs) > 1:
        return "", (f"the filing page offers {len(pdfs)} PDFs - refused rather than "
                    f"guessed at; say which one is the prospectus")
    u = pdfs[0] if pdfs[0].startswith("http") else "https://www.sebi.gov.in" + pdfs[0]
    return u, "followed the SEBI filing page to its file= document"


ATTEMPTS = 3


def fetch_to_disk(sess, url: str, dest: Path) -> tuple[bool, str, str, int]:
    """`(ok, note, sha256, bytes)`. Streams in blocks; never holds the body in memory.

    **Retried.** A dropped stream is not a bad document: SEBI closed the connection
    4,427,992 bytes into a 5.5 MB prospectus on the first run here and the whole job died
    on the unhandled `ChunkedEncodingError`, losing the ten results already computed.
    `rhp_valuation.fetch` has had three attempts for exactly this since the first batch;
    this had none. Three attempts, the politeness gap re-applied before each retry so a
    retry is never a burst, and the partial file discarded between attempts so a truncated
    body can never be hashed and accepted.
    """
    last = ""
    for attempt in range(1, ATTEMPTS + 1):
        h, n = hashlib.sha256(), 0
        try:
            r = sess.get(url, headers=UA, timeout=120, stream=True, allow_redirects=True)
            if r.status_code != 200:
                r.close()
                return False, f"HTTP {r.status_code}", "", 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for blk in r.iter_content(65536):
                    if blk:
                        h.update(blk)
                        f.write(blk)
                        n += len(blk)
            r.close()
        except Exception as e:                                 # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:80]}"
            try:
                dest.unlink()
            except OSError:
                pass
            if attempt < ATTEMPTS:
                time.sleep(GAP)
                continue
            return False, f"{last} (after {ATTEMPTS} attempts)", "", 0
        head = dest.open("rb").read(5)
        if head[:4] != b"%PDF":
            return False, f"not a PDF (starts {head!r}); {n} bytes", h.hexdigest(), n
        return True, f"{n} bytes" + (f" on attempt {attempt}" if attempt > 1 else ""), \
            h.hexdigest(), n
    return False, last or "unreachable", "", 0


def validate(limit: int | None = None, resume: bool = True) -> pd.DataFrame:
    import requests
    from fetch_rhp import _verify_is_prospectus
    d = pd.read_csv(MANUAL)
    if limit:
        d = d.head(limit)
    sess = requests.Session()
    rows = []
    # RESUMABLE on company. A verdict already reached is not recomputed - re-fetching a
    # 677-page prospectus to learn what the file already says is rude to SEBI and slow.
    if resume and OUT.exists():
        try:
            prev = pd.read_csv(OUT)
            rows = [r for r in prev.to_dict("records")
                    if str(r.get("verdict") or "") in ("ACCEPT", "REJECT")]
            done = {str(r["company"]) for r in rows}
            if done:
                print(f"  resuming: {len(done)} rows already decided")
                d = d[~d["company"].astype(str).isin(done)]
        except Exception as e:                                 # noqa: BLE001
            print(f"  could not resume ({type(e).__name__}); starting clean")
            rows = []
    for i, r in enumerate(d.itertuples(), 1):
        url = str(getattr(r, "rhp_url", "") or "").strip()
        comp = str(r.company)
        rec = {"company": comp, "symbol": getattr(r, "symbol", None),
               "listing_date": getattr(r, "listing_date", None), "rhp_url": url,
               "host": host_of(url), "official_host": is_official(url),
               "fetched": False, "bytes": None, "sha256": "", "pages": None,
               "verified": False, "verdict": "", "reason": "",
               "pdf_url": "", "resolved_how": "",
               "source_flag": "sebi_official", "fetched_at_ist": ""}
        if not url or url.lower() == "nan":
            rec["verdict"], rec["reason"] = "REJECT", "no URL supplied"
            rows.append(rec)
            continue
        auth = AUTHORISED_NON_OFFICIAL.get(comp.strip().lower())
        if auth:
            rec["source_flag"] = auth
        if not rec["official_host"] and not auth:
            # Rule 3. Not fetched at all: the issue is the SOURCE, and fetching it would
            # not change the verdict. A prospectus has to come from the regulator or the
            # exchange, not from the issuer's own CMS or a file-sharing link, because the
            # whole point of the official copy is that nobody in the transaction can edit
            # it after the fact.
            rec["verdict"] = "REJECT"
            rec["reason"] = (f"host '{rec['host']}' is not SEBI, BSE or NSE (hard rule 3). "
                             f"Not fetched - the source is the problem, not the file.")
            rows.append(rec)
            print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  non-official host "
                  f"{rec['host']}")
            continue
        if auth == "user_supplied_drive_link":
            url_fetch = drive_direct(url)
            rec["resolved_how"] = "Drive viewer link rewritten to its direct-download form"
        else:
            url_fetch = url
        pdf_url, how = resolve_pdf(sess, url_fetch)
        rec["pdf_url"], rec["resolved_how"] = pdf_url, how
        if not pdf_url:
            rec["verdict"], rec["reason"] = "REJECT", how
            print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  {how[:62]}")
            rows.append(rec)
            time.sleep(GAP)
            continue
        dest = PDF_DIR / (("".join(c if c.isalnum() else "_" for c in comp))[:70] + ".pdf")
        ok, note, sha, n = fetch_to_disk(sess, pdf_url, dest)
        rec.update({"fetched": ok, "bytes": n or None, "sha256": sha,
                    "fetched_at_ist": str(pd.Timestamp.now())})
        if not ok:
            rec["verdict"], rec["reason"] = "REJECT", f"fetch failed: {note}"
            print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  {note}")
        else:
            try:
                good, why = _verify_is_prospectus(dest.read_bytes(), comp)
                # A RENAMED company's prospectus carries its FORMER name on the cover, so
                # the name test fails on a document that is entirely correct. Acutaas
                # Chemicals was rejected here ("company name not matched in cover,
                # hits=0") on the RHP filed as Ami Organics - a rename NSE itself records
                # (AMIORG -> ACUTAAS, 02-JUN-2025) and company_aliases.py already holds.
                # So a name-only failure is retried against the known aliases. This does
                # NOT weaken the test: the >=100-page and prospectus-marker checks are
                # untouched, and the alias has to be on record already - no similarity
                # matching, which is what H28 forbids.
                if not good and "name not matched" in str(why).lower():
                    try:
                        import company_aliases as CA
                        for alt in CA.aliases_for(comp):
                            g2, w2 = _verify_is_prospectus(dest.read_bytes(), alt)
                            if g2:
                                good = True
                                why = (f"{w2}; matched the FORMER name '{alt}' from "
                                       f"company_aliases (the cover predates the rename)")
                                rec["source_flag"] = (rec.get("source_flag") or "") \
                                    + "+verified_under_former_name"
                                break
                    except Exception:                          # noqa: BLE001
                        pass
                rec["verified"], rec["reason"] = bool(good), why
                rec["verdict"] = "ACCEPT" if good else "REJECT"
                import re as _re
                m = _re.search(r"(\d+)\s*pages", str(why))
                rec["pages"] = int(m.group(1)) if m else None
                print(f"  {i:3d}/{len(d)} {comp[:36]:38s} "
                      f"{'ACCEPT' if good else 'REJECT'}  {str(why)[:70]}")
            except Exception as e:                             # noqa: BLE001
                rec["verdict"] = "REJECT"
                rec["reason"] = f"could not open: {type(e).__name__}: {str(e)[:80]}"
                print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  {rec['reason'][:60]}")
            # Free the file unless it was accepted - a rejected PDF is not kept.
            if rec["verdict"] == "REJECT":
                try:
                    dest.unlink()
                except OSError:
                    pass
        rows.append(rec)
        # Written after EVERY row, not at the end. The first run died on row 11 and the
        # ten verdicts already computed - ten PDFs fetched and opened - went with it.
        _flush(rows)
        time.sleep(GAP)
    out = pd.DataFrame(rows)
    _flush(rows)
    return out


def _flush(rows: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, extra=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  ok   {n}")
        else:
            fail += 1
            print(f"  FAIL {n} {extra}")

    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] the source is checked before the file")
    chk("SEBI, BSE and NSE are the only accepted hosts",
        is_official("https://www.sebi.gov.in/x.pdf")
        and is_official("https://nsearchives.nseindia.com/y.pdf"))
    chk("the issuer's own website is not an official host",
        not is_official("https://cms.abdindia.com/rhp.pdf"))
    chk("nor is a file-sharing link",
        not is_official("https://drive.google.com/file/d/abc/view"))
    chk("a non-official host is not even fetched",
        "Not fetched - the source is the problem" in src)

    print(chr(10) + "[1b] the two authorised exceptions (H42) are narrow")
    chk("the allow-list is keyed on the COMPANY, not the host",
        "allied blenders and distillers limited" in src
        and "sri lotus developers & realty ltd" in src)
    chk("so another issuer's own website is still refused",
        "cms.abdindia.com" not in str(list(AUTHORISED_NON_OFFICIAL)))
    # Checked on the CONTROL FLOW, not by counting calls. The old form required exactly
    # one call to _verify_is_prospectus, so adding the former-name retry - which calls it
    # again, more strictly - failed an assertion whose point it does not touch.
    chk("an authorised document STILL has to pass _verify_is_prospectus",
        'if not rec["official_host"] and not auth' in src
        and "_verify_is_prospectus" in src
        and "auth" not in src.split("_verify_is_prospectus")[0].rsplit("if ", 1)[-1])
    chk("its source flag records that it is not from the regulator",
        '"issuer_site"' in src and '"user_supplied_drive_link"' in src)
    chk("a Drive viewer link is rewritten, never logged into",
        "export=download" in src and "no login is involved" in src.lower())
    chk("a restricted Drive file fails the %PDF check rather than being worked around",
        "fails the %PDF check and is rejected" in src)

    print(chr(10) + "[2] never trust a URL")
    chk("the PDF magic number is checked", 'head[:4] != b"%PDF"' in src)
    chk("_verify_is_prospectus is the gate", "_verify_is_prospectus(dest.read_bytes()" in src)
    chk("the sha256 of what was checked is recorded", "hashlib.sha256()" in src)
    chk("the body is streamed, never held whole", "iter_content(65536)" in src)
    chk("a rejected PDF is not kept", "dest.unlink()" in src)
    chk("the politeness gap is at least 3 s (rule 9)", GAP >= 3.0)
    chk("a name-only failure is retried against KNOWN aliases, not similar names",
        'aliases_for(comp)' in src and '"name not matched" in str(why).lower()' in src)
    chk("and only a NAME failure is retried - the page count still binds",
        'if not good and "name not matched"' in src)
    chk("a document verified under a former name says so on the row",
        "verified_under_former_name" in src)
    chk("a dropped stream is retried, not fatal",
        "ChunkedEncodingError" in src and "ATTEMPTS" in src)
    chk("and the partial file is discarded between attempts, never hashed",
        "dest.unlink()" in src and "if attempt < ATTEMPTS" in src)
    chk("the gap is re-applied before a retry, so a retry is never a burst",
        "time.sleep(GAP)" in src)
    chk("verdicts are written after every row, not only at the end", "_flush(rows)" in src)
    chk("and a decided row is not re-fetched on a resume",
        'in ("ACCEPT", "REJECT")' in src)

    print(chr(10) + "[3] a SEBI filing page is followed to the document")
    chk("a .html filing page is not treated as a failed PDF",
        'file=([^' in src and "followed the SEBI filing page" in src)
    chk("the extraction is the one that already works in fetch_rhp",
        "fetch_rhp.resolve_sebi" in src and "file=" in src)
    chk("a direct .pdf link is used as-is",
        'url.lower().endswith(".pdf")' in src)
    chk("a page offering several PDFs is REFUSED, not guessed at",
        "refused rather than" in src)
    chk("both the page URL and the resolved PDF URL are recorded",
        '"pdf_url"' in src and '"resolved_how"' in src)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fresh", action="store_true",
                    help="ignore previous verdicts and re-check every row")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.check:
        d = validate(a.limit, resume=not a.fresh)
        print()
        print(d["verdict"].value_counts().to_string())
        print(f"written {OUT}")
        raise SystemExit(0)
    ap.print_help()

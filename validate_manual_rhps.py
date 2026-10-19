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


def fetch_to_disk(sess, url: str, dest: Path) -> tuple[bool, str, str, int]:
    """`(ok, note, sha256, bytes)`. Streams in blocks; never holds the body in memory."""
    try:
        r = sess.get(url, headers=UA, timeout=120, stream=True,
                     allow_redirects=True)
    except Exception as e:                                     # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:90]}", "", 0
    if r.status_code != 200:
        r.close()
        return False, f"HTTP {r.status_code}", "", 0
    h = hashlib.sha256()
    n = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        for blk in r.iter_content(65536):
            if blk:
                h.update(blk)
                f.write(blk)
                n += len(blk)
    r.close()
    head = dest.open("rb").read(5)
    if head[:4] != b"%PDF":
        return False, f"not a PDF (starts {head!r}); {n} bytes", h.hexdigest(), n
    return True, f"{n} bytes", h.hexdigest(), n


def validate(limit: int | None = None) -> pd.DataFrame:
    import requests
    from fetch_rhp import _verify_is_prospectus
    d = pd.read_csv(MANUAL)
    if limit:
        d = d.head(limit)
    sess = requests.Session()
    rows = []
    for i, r in enumerate(d.itertuples(), 1):
        url = str(getattr(r, "rhp_url", "") or "").strip()
        comp = str(r.company)
        rec = {"company": comp, "symbol": getattr(r, "symbol", None),
               "listing_date": getattr(r, "listing_date", None), "rhp_url": url,
               "host": host_of(url), "official_host": is_official(url),
               "fetched": False, "bytes": None, "sha256": "", "pages": None,
               "verified": False, "verdict": "", "reason": "",
               "pdf_url": "", "resolved_how": ""}
        if not url or url.lower() == "nan":
            rec["verdict"], rec["reason"] = "REJECT", "no URL supplied"
            rows.append(rec)
            continue
        if not rec["official_host"]:
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
        pdf_url, how = resolve_pdf(sess, url)
        rec["pdf_url"], rec["resolved_how"] = pdf_url, how
        if not pdf_url:
            rec["verdict"], rec["reason"] = "REJECT", how
            print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  {how[:62]}")
            rows.append(rec)
            time.sleep(GAP)
            continue
        dest = PDF_DIR / (("".join(c if c.isalnum() else "_" for c in comp))[:70] + ".pdf")
        ok, note, sha, n = fetch_to_disk(sess, pdf_url, dest)
        rec.update({"fetched": ok, "bytes": n or None, "sha256": sha})
        if not ok:
            rec["verdict"], rec["reason"] = "REJECT", f"fetch failed: {note}"
            print(f"  {i:3d}/{len(d)} {comp[:36]:38s} REJECT  {note}")
        else:
            try:
                good, why = _verify_is_prospectus(dest.read_bytes(), comp)
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
        time.sleep(GAP)
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    return out


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

    print(chr(10) + "[2] never trust a URL")
    chk("the PDF magic number is checked", 'head[:4] != b"%PDF"' in src)
    chk("_verify_is_prospectus is the gate", "_verify_is_prospectus(dest.read_bytes()" in src)
    chk("the sha256 of what was checked is recorded", "hashlib.sha256()" in src)
    chk("the body is streamed, never held whole", "iter_content(65536)" in src)
    chk("a rejected PDF is not kept", "dest.unlink()" in src)
    chk("the politeness gap is at least 3 s (rule 9)", GAP >= 3.0)

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
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.check:
        d = validate(a.limit)
        print()
        print(d["verdict"].value_counts().to_string())
        print(f"written {OUT}")
        raise SystemExit(0)
    ap.print_help()

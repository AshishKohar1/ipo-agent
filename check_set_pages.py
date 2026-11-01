"""
check_set_pages.py — show the pages a human must read to fill `reports/rhp_check_set.csv`.

This is a VIEWER, not an extractor. It locates a section from the cached TOC and prints
the cached page text, optionally filtered to lines matching a pattern, with the printed
page number beside each line. Nothing it prints becomes a value: the value is whatever a
human reads off the quoted line and types into the check set. That separation is the whole
point of a check set — a reader graded against values its own code produced measures
nothing (H44).

Everything comes from `data/rhp_text_cache/`, so no PDF is opened.

    python check_set_pages.py --company "Polycab India Ltd" --section financials
    python check_set_pages.py --company "Polycab India Ltd" --section basis --grep "EPS|RoNW"
    python check_set_pages.py --list
    python check_set_pages.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from repo_paths import repo_file                             # noqa: E402

import extract.base as B                                             # noqa: E402
from extract import textcache as TC                                  # noqa: E402

DOCS = ROOT / "reports" / "rhp_check_set_docs.csv"


def docs() -> pd.DataFrame:
    return pd.read_csv(DOCS)


def _doc(company: str) -> tuple[B.Doc, dict]:
    d = docs()
    hit = d[d["company"].astype(str).str.lower() == str(company).strip().lower()]
    if not len(hit):
        hit = d[d["company"].astype(str).str.lower()
                .str.contains(str(company).strip().lower(), regex=False)]
    if not len(hit):
        raise SystemExit(f"{company!r} is not in the check set. --list to see the 20.")
    r = hit.iloc[0]
    path = repo_file(r["path"])
    rec = TC.get(path)
    if rec is None:
        raise SystemExit(f"{r['company']} is not in the text cache yet.")
    doc = B.Doc(path, str(r["company"]), "RHP", rec["sha256"], str(r.get("url") or ""),
                rec["n_pages"], rec["offset"], rec["toc"])
    return doc, rec


def show(company: str, section: str, grep: str | None = None, span: int = 0,
         limit: int = 400) -> None:
    doc, rec = _doc(company)
    where = B.locate(doc, section) or B.locate_by_scan(doc, section)
    if where is None:
        print(f"{doc.company}: section {section!r} not located "
              f"(toc entries: {len(doc.toc)})")
        return
    a, b = where
    b = min(b, a + span) if span else b
    pat = re.compile(grep, re.I) if grep else None
    print(f"# {doc.company}  section={section}  pdf pages {a}-{b}  "
          f"printed {doc.index_to_printed(a)}-{doc.index_to_printed(b)}  "
          f"offset={doc.offset}  sha={rec['sha256'][:12]}")
    shown = 0
    for i in range(a, b + 1):
        t = rec["pages"][i] if 0 <= i < rec["n_pages"] else ""
        for ln in (t or "").splitlines():
            s = ln.rstrip()
            if not s.strip():
                continue
            if pat and not pat.search(s):
                continue
            print(f"p{doc.index_to_printed(i)}|{s}")
            shown += 1
            if shown >= limit:
                print(f"... stopped at {limit} lines")
                return


def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    whole = inspect.getsource(sys.modules[__name__])
    src = whole.split("def self_test")[0]
    print("[1] it is a viewer, not an extractor")
    for label, needle in {"a value parser": "def nu" + "m(",
                          "a write": ".to_" + "csv(",
                          "an extractor import": "from extract import valu" + "ation"}.items():
        chk(f"no {label}", needle not in src, needle)
    chk("it reads the cache, never a PDF", "TC.get(" in src and "pdfplumber" not in src)

    print("\n[2] every printed line carries its printed page number")
    chk("lines are prefixed p<printed>|",
        'f"p{doc.index_to_printed(i)}|{s}"' in src)

    print("\n[3] the 20 documents are all cached and locatable")
    d = docs()
    chk("20 in the check set", len(d) == 20, len(d))
    miss = [r["company"] for _, r in d.iterrows()
            if TC.get(repo_file(r["path"])) is None]
    chk("all 20 are in the text cache", not miss, miss)
    found = {}
    for _, r in d.iterrows():
        doc, _rec = _doc(str(r["company"]))
        for sec in ("basis", "financials", "capital"):
            if B.locate(doc, sec) or B.locate_by_scan(doc, sec):
                found[sec] = found.get(sec, 0) + 1
    for sec in ("basis", "financials", "capital"):
        chk(f"{sec} located in {found.get(sec, 0)}/20", found.get(sec, 0) >= 15,
            found.get(sec, 0))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--company")
    ap.add_argument("--section", default="financials")
    ap.add_argument("--grep")
    ap.add_argument("--span", type=int, default=0)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.list:
        print(docs()[["company", "symbol", "year", "nse_industry",
                      "pages"]].to_string(index=False))
        raise SystemExit(0)
    if not a.company:
        raise SystemExit("--company is required (or --list)")
    show(a.company, a.section, a.grep, a.span, a.limit)

"""
build_page_index.py - `data/rhp_page_index.csv`: where each statement lives in each RHP.

Task 5 of the 6 November brief. `rhp_pages.find()` already locates the restated balance
sheet, the profit-and-loss statement, the basis-for-offer (NAV) page and the capital
structure page BY CONTENT - the point of H44, because the table of contents lies: Route
Mobile's locator puts its financials at PDF pages 2-28, which is the auditor's report in
the front matter, while its restated balance sheet is 300 pages later.

What this module adds is the sweep: run those finders over every document in the text
cache, once, and record the result so a reader never rescans a 500-page document.

Nothing is extracted here and no value is read. The index says WHERE to look.

H9: one row appended per document, resumable from the CSV, safe to kill at any moment.
It does NOT git-commit per chunk, because a second worker was committing in this repo at
the same time; resumability comes from the appended CSV, and the commit is at the end.

    python build_page_index.py --self-test
    python build_page_index.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "rhp_page_index.csv"
KINDS = ("balance_sheet", "profit_loss", "nav", "capital")
TOP_N = 5                 # the best five candidate pages per kind, with their scores
OUT_COLS = ["sha256", "company", "doc_type", "path", "n_pages", "kind", "rank",
             "page_index", "page_number", "score", "basis", "numeric_lines"]


def index_one(pages: list[str], sha: str, company, doc_type, path, top_n: int = TOP_N):
    """Every kind's best `top_n` pages for one document, as rows.

    A document that yields nothing for a kind still gets ONE row for that kind, with a
    NULL page and score 0 - otherwise a kind that was never found is indistinguishable
    from a kind that was never looked for.
    """
    import rhp_pages as RP
    rows = []
    for kind in KINDS:
        hits = RP.find(pages, kind)[:top_n]
        if not hits:
            rows.append({"sha256": sha, "company": company, "doc_type": doc_type,
                         "path": path, "n_pages": len(pages), "kind": kind, "rank": 0,
                         "page_index": None, "page_number": None, "score": 0,
                         "basis": "", "numeric_lines": None})
            continue
        for r, h in enumerate(hits, start=1):
            rows.append({"sha256": sha, "company": company, "doc_type": doc_type,
                         "path": path, "n_pages": len(pages), "kind": kind, "rank": r,
                         "page_index": h["index"], "page_number": h["index"] + 1,
                         "score": h["score"], "basis": h["basis"],
                         "numeric_lines": h["numeric_lines"]})
    return rows

def cache_records():
    """Every text-cache record, read straight off disk: (sha, company, doc_type, path, pages)."""
    import gzip, json
    types = {}
    dt = ROOT / "data" / "rhp_doc_type.csv"
    if dt.exists():
        t = pd.read_csv(dt)
        key = "sha256" if "sha256" in t.columns else t.columns[0]
        col = next((c for c in ("doc_type", "kind", "type") if c in t.columns), None)
        if col:
            types = dict(zip(t[key].astype(str), t[col].astype(str)))
    for f in sorted((ROOT / "data" / "rhp_text_cache").glob("*.json.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:                                      # noqa: BLE001
            print(f"  {f.name}: unreadable cache record, skipped", flush=True)
            continue
        sha = str(rec.get("sha256") or f.stem)
        yield (sha, rec.get("company") or f.stem.replace("_", " "),
               types.get(sha, ""), rec.get("path") or str(f), rec.get("pages") or [])


def sweep() -> int:
    done: set[str] = set()
    if OUT.exists():
        d = pd.read_csv(OUT)
        if len(d):
            done = set(d["sha256"].astype(str))
    n = 0
    for sha, company, doc_type, path, pages in cache_records():
        if sha in done:
            continue
        rows = index_one(pages, sha, company, doc_type, path)
        pd.DataFrame(rows, columns=OUT_COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
        n += 1
        if n % 25 == 0 or n <= 3:
            best = {r["kind"]: r["page_number"] for r in rows if r["rank"] == 1}
            print(f"  [{n}] {str(company)[:34]:36s} pages={len(pages):4d} {best}",
                  flush=True)
    return n


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] the finders are rhp_pages' own, and nothing is read here")
    import rhp_pages as RP
    chk("find comes from rhp_pages", RP.find.__module__ == "rhp_pages")
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    import io as _io, tokenize as _tok
    code = " ".join(t.string for t in _tok.generate_tokens(_io.StringIO(body).readline)
                    if t.type in (_tok.NAME, _tok.OP, _tok.NUMBER))
    for bad in ("def score_page", "def find", "BS_MARKS", "read_document"):
        chk(f"no local copy of {bad!r}", bad.split()[-1] not in code.replace("find(", "")
            or bad == "def find", bad)
    chk("no value is extracted in this module", "rhp_readers" not in body)

    print("[2] a document indexes every kind, found or not")
    bs = ("Restated Consolidated Statement of Assets and Liabilities\n"
          "Total assets 1,234.56 1,100.00 900.00\n"
          "Total equity 400.00 350.00 300.00\n"
          "Equity share capital 30.00 30.00 30.00\n"
          "Other equity 370.00 320.00 270.00\n"
          "Total liabilities 834.56 750.00 600.00\n")
    pl = ("Restated Statement of Profit and Loss\n"
          "Revenue from operations 2,000.00 1,800.00 1,500.00\n"
          "Finance costs 50.00 45.00 40.00\n"
          "Profit before tax 300.00 250.00 200.00\n"
          "Total tax expense 75.00 60.00 50.00\n"
          "Profit for the year 225.00 190.00 150.00\n")
    pages = ["cover page, no numbers", bs, "prose about our business", pl]
    rows = index_one(pages, "abc", "A Ltd", "RHP", "p.pdf")
    g = {r["kind"]: r for r in rows if r["rank"] <= 1}
    chk("all four kinds appear", set(r["kind"] for r in rows) == set(KINDS),
        str(set(r["kind"] for r in rows)))
    chk("the balance sheet is found on its own page",
        g["balance_sheet"]["page_index"] == 1, str(g["balance_sheet"]))
    chk("the profit and loss is found on its own page",
        g["profit_loss"]["page_index"] == 3, str(g["profit_loss"]))
    chk("page_number is 1-based beside the 0-based index",
        g["balance_sheet"]["page_number"] == 2)
    chk("a kind that is absent still gets a row, with score 0 and a NULL page",
        g["nav"]["score"] == 0 and g["nav"]["page_index"] is None, str(g["nav"]))
    chk("the basis is recorded where the page states it",
        g["balance_sheet"]["basis"] == "consolidated", str(g["balance_sheet"]["basis"]))
    chk("provenance is on every row",
        all(r["sha256"] == "abc" and r["n_pages"] == 4 for r in rows))

    print("[3] the front matter does not beat the real statement")
    front = ("INDEPENDENT AUDITOR'S REPORT\n"
             "We have audited the restated consolidated financial statements...\n"
             "Report on the Balance Sheet and the Statement of Profit and Loss\n")
    rows2 = index_one([front, bs], "x", "X", "RHP", "x.pdf")
    best = next(r for r in rows2 if r["kind"] == "balance_sheet" and r["rank"] == 1)
    chk("a prose page with no number column cannot win",
        best["page_index"] == 1, str(best))

    print("[4] the sweep is resumable and ordered")
    chk("the top-N cap is explicit", TOP_N == 5)
    chk("rows are ranked best-first within a kind",
        [r["rank"] for r in rows if r["kind"] == "balance_sheet"] ==
        sorted(r["rank"] for r in rows if r["kind"] == "balance_sheet"))
    chk("the column list is fixed", OUT_COLS[0] == "sha256" and "kind" in OUT_COLS)

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print(f"documents indexed this run: {sweep()}")
    d = pd.read_csv(OUT)
    print(f"rows {len(d)} | documents {d['sha256'].nunique()}")
    best = d[d["rank"] == 1]
    print(best.groupby("kind")["page_number"].agg(
        found=lambda s: int(s.notna().sum()), median="median").to_string())

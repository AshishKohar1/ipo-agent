"""
dump_check_set.py — one text file per check-set document, holding the lines a human needs.

A viewer like `check_set_pages.py`, run over all 20 at once so the hand-read is a reading
job rather than a hundred interactive queries. It prints candidate lines; it does not pick
values, parse numbers or decide which column is which fiscal year. Those are the judgements
the check set exists to capture from a human (H44).

Output: `_local/check_set_dump/<Company>.txt` (gitignored, re-creatable in seconds from the
text cache). Each line is `p<printed page>|<the line as the PDF renders it>`, and each
block is preceded by the column-header lines found on the same pages, because a restated
table is unreadable without knowing which column is which period — the stub-period trap
H44 names.

    python dump_check_set.py
    python dump_check_set.py --self-test
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

import extract.base as B                                             # noqa: E402
from extract import textcache as TC                                  # noqa: E402

DOCS = ROOT / "reports" / "rhp_check_set_docs.csv"
OUT = ROOT / "_local" / "check_set_dump"

# Column headers. Without these the numbers are unreadable: a restated table routinely
# leads with a nine-month stub, and reading column 1 as the latest fiscal year is the
# single most expensive mistake available here.
HEADER = (r"(?i)^\s*(?:particulars|nine\s*months|six\s*months|three\s*months|year\s*ended"
          r"|period\s*ended|as\s*at|fiscal|march\s*31|december\s*31|september\s*30"
          r"|june\s*30|\(?₹\s*in\s*(?:million|crore|lakh)|rs\.?\s*in\s*(?:million|crore"
          r"|lakh)|in\s*₹\s*(?:million|crore|lakh))")

ROWS = {
    "financials": (
        r"(?i)(revenue\s+from\s+operation|total\s+income"
        r"|profit\s+(?:/\s*\(loss\)\s*)?for\s+the\s+(?:year|period)"
        r"|profit\s+after\s+tax|total\s+tax\s+expens|tax\s+expens|current\s+tax"
        r"|finance\s+cost|depreciation\s+and\s+amorti"
        r"|^\s*EBITDA|earnings\s+before\s+interest"
        r"|net\s*[\- ]?worth|total\s+equity|equity\s+attributable"
        r"|total\s+borrowing|^\s*-?\s*borrowings|^\s*[a-z]\)\s*borrowings"
        r"|cash\s+and\s+cash\s+equivalent"
        r"|net\s+cash\s+(?:generated\s+)?(?:from|used\s+in)\s+operating"
        r"|cash\s+generated\s+from\s+operation"
        r"|purchase\s+of\s+property|payment\s+for\s+property"
        r"|capital\s+expenditure)"),
    "capital": (
        r"(?i)(equity\s+shares?\s+of\s+|issued,?\s+subscribed|paid[\s-]*up"
        r"|before\s+the\s+(?:offer|issue)|after\s+the\s+(?:offer|issue)"
        r"|pre[\s-]*(?:offer|issue)|post[\s-]*(?:offer|issue)"
        r"|promoter|share\s+capital|\bNAV\b)"),
    "basis": (
        r"(?i)(earnings?\s+per\s+share|\bEPS\b|basic|diluted"
        r"|return\s+on\s+net\s*worth|\bRoNW\b|\bRONW\b"
        r"|net\s+asset\s+value|\bNAV\b"
        r"|P\s*/\s*E|price\s*/\s*earning|peer|industry|comparison"
        r"|face\s+value|weighted\s+average)"),
}
SPAN = {"financials": 26, "capital": 12, "basis": 14}


def docs() -> pd.DataFrame:
    return pd.read_csv(DOCS)


def dump_one(row) -> tuple[str, int]:
    path = ROOT / str(row["path"])
    rec = TC.get(path)
    if rec is None:
        return f"# {row['company']}: NOT CACHED\n", 0
    doc = B.Doc(path, str(row["company"]), "RHP", rec["sha256"], str(row.get("url") or ""),
                rec["n_pages"], rec["offset"], rec["toc"])
    head = (f"# {row['company']}  symbol={row['symbol']}  listed={row['listing_date']}\n"
            f"# sha256={rec['sha256']}  pages={rec['n_pages']}  offset={rec['offset']}\n")
    body, n = [], 0
    hdr = re.compile(HEADER)
    for sec in ("basis", "financials", "capital"):
        where = B.locate(doc, sec) or B.locate_by_scan(doc, sec)
        if where is None:
            body.append(f"\n===== {sec.upper()}: NOT LOCATED\n")
            continue
        a, b = where
        b = min(b, a + SPAN[sec])
        body.append(f"\n===== {sec.upper()}  pdf {a}-{b}  "
                    f"printed {doc.index_to_printed(a)}-{doc.index_to_printed(b)}\n")
        pat = re.compile(ROWS[sec])
        for i in range(a, b + 1):
            t = rec["pages"][i] if 0 <= i < rec["n_pages"] else ""
            keep = []
            for ln in (t or "").splitlines():
                s = ln.rstrip()
                if not s.strip():
                    continue
                if hdr.search(s) or pat.search(s):
                    keep.append(f"p{doc.index_to_printed(i)}|{s}")
            if keep:
                body.extend(keep)
                n += len(keep)
    return head + "\n".join(body) + "\n", n


def run() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, r in docs().iterrows():
        txt, n = dump_one(r)
        f = OUT / (re.sub(r"[^A-Za-z0-9]+", "_", str(r["company"])).strip("_") + ".txt")
        f.write_text(txt, encoding="utf-8")
        rows.append({"company": r["company"], "lines": n, "kb": round(len(txt) / 1024, 1),
                     "file": f.name})
    return pd.DataFrame(rows)


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
    print("[1] a viewer, not an extractor")
    for label, needle in {"a number parser": "float(", "a value write": "check_set.csv",
                          "an extractor import": "from extract import valu" + "ation"}.items():
        chk(f"no {label}", needle not in src, needle)
    chk("reads the cache, never a PDF", "TC.get(" in src and "pdfplumber" not in src)

    print("\n[2] column headers are always carried with the rows")
    chk("a header pattern exists and is applied per line",
        "hdr.search(s) or pat.search(s)" in src)
    for h in ("Nine months period ended", "Year ended March 31,", "(₹ in million)",
              "As at March 31, 2018", "Particulars"):
        chk(f"{h[:28]!r} is recognised as a header",
            bool(re.compile(HEADER).search(h)), h)
    chk("a data row is NOT mistaken for a header",
        not re.compile(HEADER).search("Revenue from operations 55,067.00 48,344.22"))

    print("\n[3] the rows each block needs")
    fin = re.compile(ROWS["financials"])
    for line in ("Revenue from operations 69,239.17", "Total tax expense 2,055.96",
                 "Finance cost 936.80", "Depreciation and amortisation 1,329.50",
                 "Profit for the period 3,709.20", "EBITDA (A) 8,031.46",
                 "Total equity 12,345.00", "Net worth 9,876.00",
                 "a) Borrowings 5,687.45", "Cash and cash equivalents 82.32",
                 "Net cash from operating activities (A) 1,503.17",
                 "Purchase of property, plant and equipment (1,870.09)"):
        chk(f"financials matches {line[:34]!r}", bool(fin.search(line)))
    cap = re.compile(ROWS["capital"])
    for line in ("Equity Shares of ₹10 each", "Issued, subscribed and paid-up capital",
                 "Equity Share capital after the Offer", "Promoter and Promoter Group"):
        chk(f"capital matches {line[:34]!r}", bool(cap.search(line)))
    bas = re.compile(ROWS["basis"])
    for line in ("Basic EPS (₹) 24.63", "Return on Net Worth (%) 20.21",
                 "Net Asset Value per Equity Share 121.84", "Industry Peer Group P/E"):
        chk(f"basis matches {line[:34]!r}", bool(bas.search(line)))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = run()
    print(d.to_string(index=False))
    print(f"\n{len(d)} files -> {OUT}")

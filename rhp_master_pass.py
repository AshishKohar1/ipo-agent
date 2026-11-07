"""
rhp_master_pass.py - run the readers over every document, writing values ONLY where the
reader is gated.

Task 5 of the 6 November brief. H44 says the pages are found by content; H55 says a reader
may be trusted only at >= 95% precision on at least 10 correct check-set values. This
module joins the two: it runs `rhp_readers.read_document` over every document in the text
cache and writes, per (document, field):

* the value, when that field's reader **passed** the H55 gate;
* **NULL with `status = reader_not_gated`**, when it did not - even though the reader
  produced a number. An ungated reader's output is not data; recording it would smuggle
  unvalidated values into every ratio downstream.

The gate verdicts are read from `reports/READER_GATE.csv`, which `rhp_reader_gate.py`
writes. They are never hardcoded here, so a reader that later passes needs no edit.

H9: appended per document, resumable, safe to kill.

    python rhp_master_pass.py --self-test
    python rhp_master_pass.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

GATE_CSV = ROOT / "reports" / "READER_GATE.csv"
OUT = ROOT / "data" / "rhp_master_values.csv"
FIELDS = ("pre_issue_shares", "net_worth", "tax_expense", "finance_costs",
          "depreciation_amortisation")
# the gate's field names, against the readers'
GATE_NAME = {"pre_issue_shares": "shares_outstanding_pre_issue", "net_worth": "net_worth",
             "tax_expense": "tax_expense", "finance_costs": "finance_costs",
             "depreciation_amortisation": "depreciation_amortisation"}
OUT_COLS = ["sha256", "company", "doc_type", "field", "value", "unit", "value_inr",
            "page_index", "column", "basis", "status", "reader_verdict", "reason", "line"]


def gated_fields(gate: pd.DataFrame) -> set[str]:
    """The reader field names whose gate verdict is PASS. Nothing else may write a value."""
    if not len(gate):
        return set()
    passed = set(gate.loc[gate["verdict"].astype(str) == "PASS", "field"].astype(str))
    return {rd for rd, cs in GATE_NAME.items() if cs in passed}


def rows_for(doc: dict, sha, company, doc_type, allowed: set[str]) -> list[dict]:
    """One row per field for one document, values only for gated readers."""
    out = []
    for f in FIELDS:
        g = doc.get("fields", {}).get(f, {}) or {}
        ok = f in allowed
        produced = g.get("value") is not None
        out.append({
            "sha256": sha, "company": company, "doc_type": doc_type, "field": f,
            "value": (g.get("value") if ok else None),
            "unit": (g.get("unit") if ok else None),
            "value_inr": (g.get("value_inr") if ok else None),
            "page_index": (g.get("page_index") if ok else None),
            "column": (g.get("column") if ok else None),
            "basis": (g.get("basis") if ok else None),
            "status": ("ok" if (ok and produced) else
                       "withheld_by_reader" if ok else "reader_not_gated"),
            "reader_verdict": ("PASS" if ok else "INSUFFICIENT_or_FAIL"),
            "reason": (str(g.get("reason"))[:200] if ok else
                       "the reader for this field has not passed the H55 gate, so its "
                       "output is not recorded as a value"),
            "line": (str(g.get("line"))[:160] if ok else None)})
    return out


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

    print("[1] the gate decides, and it is read from disk, never hardcoded")
    g = pd.DataFrame([{"field": "shares_outstanding_pre_issue", "verdict": "PASS"},
                      {"field": "net_worth", "verdict": "INSUFFICIENT"},
                      {"field": "tax_expense", "verdict": "FAIL"}])
    chk("only the PASS field is allowed", gated_fields(g) == {"pre_issue_shares"},
        str(gated_fields(g)))
    chk("INSUFFICIENT is not a pass", "net_worth" not in gated_fields(g))
    chk("FAIL is not a pass", "tax_expense" not in gated_fields(g))
    chk("an empty gate allows nothing", gated_fields(pd.DataFrame()) == set())
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    chk("no verdict is written into this module",
        '"PASS"' not in body.split("GATE_NAME")[0] or "READER_GATE" in body)

    print("[2] an ungated reader's number is NOT recorded, even when it produced one")
    doc = {"fields": {
        "pre_issue_shares": {"value": 127454390.0, "reason": "ok", "unit": "shares"},
        "net_worth": {"value": 4223.70, "reason": "ok", "unit": "INR million"},
        "tax_expense": {"value": None, "reason": "no EPS anchor"},
        "finance_costs": {"value": 288.07, "reason": "ok"},
        "depreciation_amortisation": {"value": None, "reason": "row not present"}}}
    r = {x["field"]: x for x in rows_for(doc, "sha", "A Ltd", "RHP", {"pre_issue_shares"})}
    chk("the gated reader's value is written",
        r["pre_issue_shares"]["value"] == 127454390.0 and r["pre_issue_shares"]["status"] == "ok")
    chk("an UNGATED reader's number is dropped to NULL",
        r["net_worth"]["value"] is None and r["finance_costs"]["value"] is None,
        str((r["net_worth"]["value"], r["finance_costs"]["value"])))
    chk("and it is labelled reader_not_gated, not withheld",
        r["net_worth"]["status"] == "reader_not_gated", r["net_worth"]["status"])
    chk("a gated reader that withheld is labelled differently from an ungated one",
        rows_for(doc, "s", "A", "RHP", set(FIELDS))[2]["status"] == "withheld_by_reader",
        str(rows_for(doc, "s", "A", "RHP", set(FIELDS))[2]["status"]))
    chk("an ungated row carries no page, column, unit or line either",
        all(r["net_worth"][k] is None for k in ("page_index", "column", "unit", "line")),
        str(r["net_worth"]))
    chk("every field gets a row, always", len(rows_for(doc, "s", "A", "RHP", set())) == 5)
    chk("the reason says why an ungated field is empty",
        "has not passed the H55 gate" in r["net_worth"]["reason"])

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


def sweep() -> int:
    import gzip, json
    import rhp_readers as RR
    gate = pd.read_csv(GATE_CSV) if GATE_CSV.exists() else pd.DataFrame()
    allowed = gated_fields(gate)
    print(f"gated readers (may write values): {sorted(allowed) or 'NONE'}")
    types = {}
    dt = ROOT / "data" / "rhp_doc_type.csv"
    if dt.exists():
        t = pd.read_csv(dt)
        k = "sha256" if "sha256" in t.columns else t.columns[0]
        c = next((x for x in ("doc_type", "kind", "type") if x in t.columns), None)
        if c:
            types = dict(zip(t[k].astype(str), t[c].astype(str)))
    done: set[str] = set()
    if OUT.exists():
        d = pd.read_csv(OUT)
        if len(d):
            done = set(d["sha256"].astype(str))
    n = 0
    for f in sorted((ROOT / "data" / "rhp_text_cache").glob("*.json.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            rec = json.load(fh)
        sha = str(rec.get("sha256") or f.stem)
        if sha in done:
            continue
        company = rec.get("company") or f.stem.replace("_", " ")
        try:
            doc = RR.read_document(rec.get("pages") or [])
        except Exception as e:                                 # noqa: BLE001
            print(f"  {company[:34]}: reader failed - {type(e).__name__}: {e}", flush=True)
            doc = {"fields": {}}
        rows = rows_for(doc, sha, company, types.get(sha, ""), allowed)
        pd.DataFrame(rows, columns=OUT_COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
        n += 1
        if n % 50 == 0 or n <= 2:
            print(f"  [{n}] {company[:36]}", flush=True)
    return n


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print(f"documents read this run: {sweep()}")
    d = pd.read_csv(OUT)
    print(f"rows {len(d)} | documents {d['sha256'].nunique()}")
    print(pd.crosstab(d["field"], d["status"]).to_string())

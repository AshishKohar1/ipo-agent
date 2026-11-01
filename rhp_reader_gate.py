"""
rhp_reader_gate.py — score the five readers against the hand-read check set.

The gate: a reader runs on all 450 RHPs only if its PRECISION on the check set is at least
95%. Precision is measured on the values the reader produced, not on the ones it withheld:
a reader that says nothing is useless but not dangerous, while a reader that is confidently
wrong corrupts every ratio derived from it and will not be found by inspection.

Ground truth is `reports/rhp_check_set.csv`, read by hand from numbered pages with the
quoted line recorded. Comparison is relative, at 0.5%, because the truth was transcribed at
the precision the document prints and the reader reports the same figure in the page's own
unit.

    python rhp_reader_gate.py                # score, write the report
    python rhp_reader_gate.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import rhp_readers as RR                                    # noqa: E402
from repo_paths import repo_file                             # noqa: E402

TRUTH = ROOT / "reports" / "rhp_check_set.csv"
DOCS = ROOT / "reports" / "rhp_check_set_docs.csv"
OUT_CSV = ROOT / "reports" / "READER_GATE.csv"
OUT_MD = ROOT / "reports" / "READER_GATE.md"
GATE = 95.0
TOL_PCT = 0.5

# The check set's field names, against the readers'.
MAP = {
    "net_worth": "net_worth",
    "tax_expense": "tax_expense",
    "finance_costs": "finance_costs",
    "depreciation_amortisation": "depreciation_amortisation",
    "shares_outstanding_pre_issue": "pre_issue_shares",
}
# The reader reports the LATEST period, because that is the column the NAV anchors on. The
# check set records several years, so the truth for a money field is the set of values the
# document prints for that field - a reader landing on any of them has the right LINE, and
# landing on the one the anchor identifies has the right COLUMN. Both are reported, because
# they are different failures: the wrong line is a parsing error, the wrong column is the
# expensive one.
MONEY = ("net_worth", "tax_expense", "finance_costs", "depreciation_amortisation")


def truth() -> pd.DataFrame:
    d = pd.read_csv(TRUTH)
    d = d[d["status"].astype(str) == "value"]
    d["num"] = pd.to_numeric(d["value"].astype(str).str.replace(",", ""), errors="coerce")
    return d[d["num"].notna()]


def near(a, b, tol_pct: float = TOL_PCT) -> bool:
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    if a == 0 or b == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / max(abs(a), abs(b)) * 100 <= tol_pct


def score(reader_rows: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (document, field) the check set has truth for."""
    from extract import textcache as TC
    t = truth()
    docs = pd.read_csv(DOCS)
    out = []
    for r in docs.itertuples():
        tt = t[t["company"] == r.company]
        if tt.empty:
            continue
        # `Path(r.path)` was BOTH relative and Windows-separated: every lookup
        # missed, score() returned an empty frame, and summarise() died on
        # KeyError 'field'. See repo_paths.py. (2026-11-02, macOS move.)
        rec = TC.get(repo_file(r.path))
        if rec is None:
            continue
        got = RR.read_document(rec["pages"])["fields"]
        for cs_field, rd_field in MAP.items():
            vals = tt[tt["field"] == cs_field]
            if vals.empty:
                continue
            truths = sorted(vals["num"].tolist())
            g = got.get(rd_field, {})
            v = g.get("value")
            # The check set records the value in the document's own unit, and so does the
            # reader, so they are comparable without converting either.
            on_line = any(near(v, x) for x in truths) if v is not None else False
            # The target is the latest FULL FISCAL YEAR, which is what the readers aim at
            # and what every ratio downstream needs. A stub period - the check set records
            # them as "3M-Jun-2020" - is a different quantity, not a later version of the
            # same one, so it is NOT the target. Preferring the stub here scored the
            # readers against the wrong number: CAMS's FY2020 net worth of 5,398.12 was
            # marked wrong for not being the June stub's 5,281.97.
            if cs_field not in MONEY:
                # The pre-issue share count has no fiscal year - it is stated as of the
                # date of the RHP - so there is one truth and it is the target.
                want = float(truths[-1]) if len(truths) == 1 else None
            else:
                fy = pd.to_numeric(vals["fiscal_year"], errors="coerce")
                want = float(vals.loc[fy.idxmax(), "num"]) if fy.notna().any() else None
            if want is None:
                # No full fiscal year in the truth for this field, so there is nothing to
                # grade the column against. Skipped rather than graded on a stub.
                continue
            out.append({
                "company": r.company, "field": cs_field,
                "truth_latest": want, "truth_all": truths,
                "got": v, "reader_unit": g.get("unit"),
                "on_a_stated_line": on_line,
                "on_the_right_column": near(v, want) if v is not None else False,
                "withheld": v is None,
                "reason": str(g.get("reason"))[:140],
                "line": str(g.get("line"))[:120]})
    return pd.DataFrame(out)


def summarise(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f, g in d.groupby("field"):
        produced = g[~g["withheld"]]
        n_p = len(produced)
        right = int(produced["on_the_right_column"].sum())
        line_ok = int(produced["on_a_stated_line"].sum())
        rows.append({
            "field": f, "n_truth": len(g), "produced": n_p, "withheld": len(g) - n_p,
            "correct": right,
            "precision_pct": round(100.0 * right / n_p, 1) if n_p else None,
            "right_line_pct": round(100.0 * line_ok / n_p, 1) if n_p else None,
            "recall_pct": round(100.0 * right / len(g), 1) if len(g) else None,
            "passes_gate": bool(n_p and 100.0 * right / n_p >= GATE)})
    return pd.DataFrame(rows).sort_values("field")


def md(d: pd.DataFrame, s: pd.DataFrame) -> str:
    L = ["# The five readers, scored against the hand-read check set", "",
         f"Gate: a reader runs on all 450 RHPs only at **precision >= {GATE}%** on the "
         "values it produces. Precision is measured on what it said, not on what it "
         "withheld: silence is useless, a confident wrong value is corrupting.", "",
         "## Per field", "",
         "| field | truth rows | produced | withheld | correct | precision | right line | "
         "recall | gate |", "|---|---|---|---|---|---|---|---|---|"]
    for r in s.itertuples():
        L.append(f"| `{r.field}` | {r.n_truth} | {r.produced} | {r.withheld} | "
                 f"{r.correct} | **{r.precision_pct}%** | {r.right_line_pct}% | "
                 f"{r.recall_pct}% | {'PASS' if r.passes_gate else '**FAIL**'} |")
    L += ["", "`right line` is the share of produced values that match SOME year the "
          "document prints for that field; `precision` is the share that match the year "
          "the anchor should have picked. The gap between them is the column error, which "
          "is the expensive one: a correct figure filed against the wrong year corrupts "
          "every ratio built on it.", ""]
    wrong = d[(~d["withheld"]) & (~d["on_the_right_column"])]
    L += ["## Every wrong value", ""]
    if len(wrong):
        L += ["| RHP | field | got | wanted | right line? | line |",
              "|---|---|---|---|---|---|"]
        for r in wrong.itertuples():
            L.append(f"| {r.company} | `{r.field}` | {r.got} | {r.truth_latest} | "
                     f"{'yes' if r.on_a_stated_line else 'NO'} | `{r.line[:70]}` |")
    else:
        L.append("None.")
    held = d[d["withheld"]]
    L += ["", f"## Withheld ({len(held)}), with the reason", ""]
    if len(held):
        L += ["| RHP | field | reason |", "|---|---|---|"]
        for r in held.itertuples():
            L.append(f"| {r.company} | `{r.field}` | {r.reason} |")
    return "\n".join(L) + "\n"


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    print("[1] near(): relative, and None is never near anything")
    chk("exact", near(100.0, 100.0))
    chk("within 0.5%", near(100.0, 100.4))
    chk("outside 0.5%", not near(100.0, 101.0))
    chk("None against a number", not near(None, 100.0))
    chk("a number against None", not near(100.0, None))
    chk("zero against zero", near(0.0, 0.0))
    chk("zero against a number", not near(0.0, 1.0))

    print("\n[2] the gate is a floor on PRECISION, not on recall")
    d = pd.DataFrame([
        {"company": "A", "field": "f", "withheld": False, "on_the_right_column": True,
         "on_a_stated_line": True, "got": 1, "truth_latest": 1, "reason": "", "line": ""},
        {"company": "B", "field": "f", "withheld": True, "on_the_right_column": False,
         "on_a_stated_line": False, "got": None, "truth_latest": 1, "reason": "no anchor",
         "line": ""},
    ])
    s = summarise(d)
    chk("a withheld row does not count against precision",
        s.iloc[0]["precision_pct"] == 100.0, s.to_dict("records"))
    chk("but it does count against recall", s.iloc[0]["recall_pct"] == 50.0, s.to_dict())
    chk("and the gate passes on precision alone", bool(s.iloc[0]["passes_gate"]))
    d2 = d.copy()
    d2.loc[1, ["withheld", "on_the_right_column"]] = [False, False]
    s2 = summarise(d2)
    chk("one wrong value out of two fails the gate",
        not bool(s2.iloc[0]["passes_gate"]) and s2.iloc[0]["precision_pct"] == 50.0,
        s2.to_dict("records"))

    print("\n[3] the right line and the right column are scored apart")
    d3 = pd.DataFrame([{"company": "A", "field": "f", "withheld": False,
                        "on_the_right_column": False, "on_a_stated_line": True,
                        "got": 2, "truth_latest": 1, "reason": "", "line": ""}])
    s3 = summarise(d3)
    chk("a right line with the wrong column is 0% precise",
        s3.iloc[0]["precision_pct"] == 0.0)
    chk("and 100% on the line", s3.iloc[0]["right_line_pct"] == 100.0)

    print("\n[4] the truth set is what was read by hand, and only that")
    t = truth()
    chk("it loads", len(t) > 0, len(t))
    chk("nothing marked not_disclosed is used",
        "not_disclosed" not in set(t["status"]), set(t["status"]))
    chk("every row has a page", t["page"].notna().all())
    chk("every row has a quoted line",
        t["quoted_line"].astype(str).str.len().gt(0).all())

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = score()
    s = summarise(d)
    OUT_CSV.parent.mkdir(exist_ok=True)
    d.to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_MD.write_text(md(d, s), encoding="utf-8")
    print(s.to_string(index=False))
    print(f"\n{OUT_CSV}\n{OUT_MD}")
    raise SystemExit(0 if s["passes_gate"].all() else 1)

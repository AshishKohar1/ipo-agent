"""
h59_stability.py - the H59 valuation variables put through Model H's OWN stability analysis.

Task 2 of the 6 November brief: same schemes (A, B, C), same Y-2 embargo, same
STABLE / CURRENT / NOISE rules. **No rule is changed here.** Every rule, window, IV floor
and label comes from `model_h_stability`, imported rather than reimplemented - if this
module had its own copy of `classify()` the verdicts could drift from Model H's.

The valuation block is long (one row per IPO per variable, each with a status). Only values
that SURVIVED rule 2 are offered to the analysis: a withheld value is NULL, never its
pre-withholding number, so nothing the reconciliation refused can reach a verdict.

    python h59_stability.py --self-test
    python h59_stability.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

BLOCK = ROOT / "data" / "h59_valuation_block.csv"
WIDE = ROOT / "data" / "h59_valuation_wide.csv"
REPORT = ROOT / "reports" / "H59_STABILITY.md"
PREFIX = "val_"          # every valuation column is prefixed, so it can never be confused
                         # with a firm variable of the same name already in the table.

def to_wide(long: pd.DataFrame) -> pd.DataFrame:
    """The long block -> one row per IPO, one prefixed column per variable.

    `value` is the RECONCILED value: it is already NULL wherever rule 2 withheld it, and
    the pre-withholding figure in `primary_value` is deliberately NOT used. A variable the
    reconciliation refused must not reach a stability verdict through a side door.
    """
    x = long.copy()
    x["col"] = PREFIX + x["variable"].astype(str)
    # Two pandas traps, both hit on the way here.
    # 1. pivot_table DROPS a column whose every value is NaN, which silently deleted every
    #    variable the reconciliation withheld for all 482 IPOs - the opposite of reporting
    #    it. So the frame is reindexed to every variable the block contains.
    # 2. pivot_table(dropna=False) on a TWO-level index expands it to the full cartesian
    #    product of ipo_id x company, inventing rows for pairs that do not exist (ipo_id 1
    #    with another company's name). The pivot is therefore on ipo_id alone and the
    #    company name is mapped back afterwards.
    cols = sorted(set(x["col"]))
    names = x.dropna(subset=["company"]).drop_duplicates("ipo_id").set_index("ipo_id")[
        "company"]
    w = x.pivot_table(index="ipo_id", columns="col", values="value", aggfunc="first")
    w.columns = list(w.columns)
    w = w.reindex(columns=cols)
    w.insert(0, "company", w.index.map(names))
    return w.reset_index()


def attach(base: pd.DataFrame, wide: pd.DataFrame) -> pd.DataFrame:
    """Left-join the valuation columns onto Model H's own frame, on the normalised name.

    Left join on purpose: the target rows are the population, and an unmatched company
    gets NULL rather than a neighbour's value (H28 - name similarity identifies nothing).
    """
    from dataio import norm_name
    b = base.copy()
    b["_k"] = b["company"].map(norm_name)
    w = wide.copy()
    w["_k"] = w["company"].map(norm_name)
    w = w.drop(columns=["company", "ipo_id"], errors="ignore").drop_duplicates("_k")
    return b.merge(w, on="_k", how="left").drop(columns="_k")

def run(write: bool = True):
    """Model H's own stability analysis, over the valuation variables only."""
    import model_h_stability as MS
    long = pd.read_csv(BLOCK)
    wide = to_wide(long)
    wide.to_csv(WIDE, index=False, encoding="utf-8")
    base = MS.load()
    d = attach(base, wide)
    vcols = [c for c in d.columns if c.startswith(PREFIX)]
    # MS.candidates() applies the project's own admissibility floors (>= 30 non-null,
    # >= 2 distinct values). Running it on the joined frame and intersecting keeps those
    # floors exactly as Model H sets them.
    admissible = [c for c in MS.candidates(d) if c in vcols]
    dropped = sorted(set(vcols) - set(admissible))
    print(f"{len(d)} mainboard rows with a corrected 1y target | "
          f"{len(vcols)} valuation variables, {len(admissible)} admissible")
    if dropped:
        print("below Model H's own floors (>=30 non-null, >=2 distinct): "
              + ", ".join(c.replace(PREFIX, "") for c in dropped))
    keep = [c for c in d.columns if c in ("company", "symbol", "listing_date", "y", "year",
                                          "excess_corrected_pp", "H_label_corrected")] \
        + admissible
    dv = d[keep].copy()
    res = pd.concat([MS.run_scheme(dv, s) for s in ("A", "B", "C")], ignore_index=True)
    emb = pd.concat([MS.run_scheme(dv, s, embargo=True) for s in ("A", "B", "C")],
                    ignore_index=True)
    cls = {s: MS.classify(res[res["scheme"] == s]) for s in ("A", "B", "C")}
    cls_emb = {s: MS.classify(emb[emb["scheme"] == s]) for s in ("A", "B", "C")}
    if write:
        _write(d, dv, admissible, dropped, cls, cls_emb)
    return cls, cls_emb


def _summary(cl: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """| variable | coverage 2019+ | verdict | IV | sign |"""
    recent = d[pd.to_numeric(d["year"], errors="coerce") >= 2019]
    rows = []
    # classify() returns `variable` as a COLUMN, not the index. Iterating rows and using
    # the integer index as the name produced a table of nameless verdicts.
    for r in cl.to_dict("records"):
        v = r["variable"]
        col = v if v in d.columns else PREFIX + str(v)
        cov = (round(100.0 * recent[col].notna().sum() / len(recent), 1)
               if col in recent.columns and len(recent) else None)
        rows.append({"variable": str(v).replace(PREFIX, ""),
                     "coverage_2019_plus_pct": cov,
                     "verdict": r.get("label"),
                     "IV_median": r.get("median_iv"),
                     "sign": r.get("direction"),
                     "windows": r.get("windows"),
                     "same_sign": r.get("same_sign"),
                     "median_auc": r.get("median_auc"),
                     "why": r.get("why")})
    return pd.DataFrame(rows)


def _write(d, dv, admissible, dropped, cls, cls_emb):
    L = [f"# H59 valuation variables - Model H stability ({pd.Timestamp.now():%Y-%m-%d})",
         "",
         "Task 2 of the 6 November brief. **Analysis only.** No variable set is chosen "
         "here, no window is chosen and no model is fitted. Every rule, window, IV floor "
         "and label is `model_h_stability`'s own, imported rather than reimplemented.", "",
         f"- {len(d)} mainboard IPOs with a corrected 1y target",
         f"- {len(admissible)} valuation variables admissible under Model H's own floors "
         f"(>= 30 non-null, >= 2 distinct values)",
         "- a value the rule-2 reconciliation withheld is NULL here, never its "
         "pre-withholding figure", ""]
    if dropped:
        L += ["Below those floors, so never measured: "
              + ", ".join("`" + c.replace(PREFIX, "") + "`" for c in dropped), ""]
    for s in ("A", "B", "C"):
        L += [f"## Scheme {s}", "", _md(_summary(cls[s], dv)), ""]
    L += ["## Scheme C with the Y-2 embargo", "", _md(_summary(cls_emb["C"], dv)), ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def _md(t: pd.DataFrame) -> str:
    # The brief asks for | variable | coverage | verdict | IV | sign |. The median
    # out-of-sample AUC is printed beside them because without it the table reads as
    # though a STABLE label meant the variable predicts, and it does not: STABLE is a
    # CONSISTENCY label over in-fold IV and sign.
    out = ["| variable | coverage 2019+ | verdict | IV | sign | median AUC |",
           "|---|---|---|---|---|---|"]
    for r in t.itertuples(index=False):
        d = dict(r._asdict())
        out.append("| `" + str(d["variable"]) + "` | "
                   + f"{d['coverage_2019_plus_pct']}% | {d['verdict']} | "
                   + (f"{d['IV_median']:.4f}" if isinstance(d["IV_median"], float)
                      else str(d["IV_median"])) + f" | {d['sign']} | "
                   + (f"{d['median_auc']:.4f}" if isinstance(d["median_auc"], float)
                      else str(d["median_auc"])) + " |")
    return "\n".join(out)


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

    print("[1] the rules are Model H's own, imported not copied")
    import model_h_stability as MS
    for fn in ("windows", "run_scheme", "classify", "measure"):
        chk(f"{fn} comes from model_h_stability",
            getattr(MS, fn).__module__ == "model_h_stability")
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    for bad in ("STABLE_SIGN =", "STABLE_IV =", "IV_FLOOR =", "def classify"):
        chk(f"no local redefinition of {bad!r}", bad not in body)

    print("[2] only values that SURVIVED rule 2 are offered to the analysis")
    long = pd.DataFrame([
        {"ipo_id": 1, "company": "A Ltd", "variable": "pat_cr", "value": 80.0,
         "status": "reconciled"},
        {"ipo_id": 1, "company": "A Ltd", "variable": "borrowings_cr", "value": None,
         "status": "withheld_disagreement", "primary_value": 300.0},
        {"ipo_id": 1, "company": "A Ltd", "variable": "roce_pct", "value": 20.0,
         "status": "single_source_unverified"},
        {"ipo_id": 2, "company": "B Ltd", "variable": "pat_cr", "value": 50.0,
         "status": "reconciled"},
        {"ipo_id": 2, "company": "B Ltd", "variable": "ev_ebitda", "value": None,
         "status": "withheld_missing_input", "primary_value": None},
    ])
    w = to_wide(long)
    chk("one row per IPO", len(w) == 2 and set(w["ipo_id"]) == {1, 2}, str(w["ipo_id"].tolist()))
    chk("a reconciled value is carried", w.set_index("ipo_id").loc[1, PREFIX + "pat_cr"] == 80.0)
    chk("a single-source value is carried and NOT dropped",
        w.set_index("ipo_id").loc[1, PREFIX + "roce_pct"] == 20.0)
    chk("a WITHHELD value is NULL, never its pre-withholding number",
        pd.isna(w.set_index("ipo_id").loc[1, PREFIX + "borrowings_cr"]),
        str(w.set_index("ipo_id").loc[1, PREFIX + "borrowings_cr"]))
    chk("every column is prefixed, so it cannot shadow a firm variable",
        all(c.startswith(PREFIX) for c in w.columns if c not in ("ipo_id", "company")),
        str(list(w.columns)))

    print("[3] the join to the target table is by normalised name, exact (H28)")
    base = pd.DataFrame({"company": ["A Limited", "C Ltd"], "symbol": ["A", "C"],
                         "y": [1, 0], "year": [2021, 2022]})
    j = attach(base, w)
    chk("a suffix-different name joins", j.set_index("symbol").loc["A", PREFIX + "pat_cr"] == 80.0)
    chk("an unmatched company gets NULL, not a neighbour's value",
        pd.isna(j.set_index("symbol").loc["C", PREFIX + "pat_cr"]), str(j))
    chk("the target rows are never dropped by the join", len(j) == len(base))
    chk("no valuation row invents a target row", set(j["symbol"]) == {"A", "C"})

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    cls, cls_emb = run()
    import model_h_stability as _MS
    long = pd.read_csv(BLOCK)
    base = _MS.load()
    dd = attach(base, to_wide(long))
    for lbl, c in (("scheme C, Y-2 embargo (the H60 window)", cls_emb["C"]),
                   ("scheme A", cls["A"]), ("scheme B", cls["B"]), ("scheme C", cls["C"])):
        print(f"\n== {lbl}")
        print(_md(_summary(c, dd)))

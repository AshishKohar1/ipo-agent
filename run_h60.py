"""
run_h60.py - the ONE combined Model H fit, exactly as pre-registered in H60.

H60 was written and committed on 2026-11-08 BEFORE this module existed, and approved by
the user on 2026-11-09. Nothing here chooses anything: the thirteen variables, the method,
the windows and the bar were all fixed in advance.

- bar: **H29 unchanged** - top-20% band, >= 50 picks, >= 54% hit rate, Wilson 95% lower
  bound strictly above the base rate on the same scored population.
- method: **H30 unchanged** - WoE bins fitted in the training fold only, numpy logistic
  regression (no scikit-learn, rule 10), scheme C expanding with the Y-2 embargo, a
  missing value as its own bin, one variable per ten beat-Nifty outcomes.

Every one of those lives in `model_h_scorecard`, which is called rather than
reimplemented. This module only assembles the frame and prints the result.

    python run_h60.py --self-test
    python run_h60.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

REPORT = ROOT / "reports" / "H60_RESULT.md"

# The thirteen, in the pre-registered order (median in-fold IV, scheme C with the embargo).
# This list is a COPY of reports/H60_PREREGISTRATION.md section 3 and must not be edited.
H60_VARS = [
    "nifty_pe_vs_10y_median",                  # firm      0.4718
    "ipo_count_prior_3m",                      # firm      0.4371
    "val_ebitda_cr",                           # valuation 0.4051
    "val_issue_size_over_net_worth",           # valuation 0.3606
    "val_pat_margin_pct_on_total_income",      # valuation 0.3348
    "val_issue_size_cr",                       # valuation 0.3208
    "nifty_tri_ret_12m",                       # firm      0.3177
    "ipo_count_prior_6m",                      # firm      0.3103
    "promoter_dilution_pp_agg",                # firm      0.3055
    "val_total_income_cr",                     # valuation 0.3035
    "val_ebitda_margin_pct",                   # valuation 0.3030
    "sub_hni",                                 # firm      0.2907
    "promoter_holding_pre_pct_agg",            # firm      0.2814
]


def frame() -> pd.DataFrame:
    """Model H's own target frame with the valuation block joined on (Task 2's loader)."""
    import model_h_stability as MS
    import h59_stability as HS
    base = MS.load()
    wide = HS.to_wide(pd.read_csv(HS.BLOCK))
    return HS.attach(base, wide)


def run() -> dict:
    import model_h_scorecard as SC
    d = frame()
    missing = [v for v in H60_VARS if v not in d.columns]
    if missing:
        raise KeyError(f"pre-registered variables absent: {missing}")
    r = SC.walk_forward(d, verbose=False, variables=H60_VARS)
    return r


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

    print("[1] the list is the pre-registered one, unedited")
    pre = (ROOT / "reports" / "H60_PREREGISTRATION.md").read_text(encoding="utf-8")
    chk("exactly 13 variables", len(H60_VARS) == 13, str(len(H60_VARS)))
    chk("no duplicates", len(set(H60_VARS)) == 13)
    for v in H60_VARS:
        chk(f"{v} is named in the pre-registration", f"`{v}`" in pre)
    chk("7 firm and 6 valuation, as pre-registered",
        sum(1 for v in H60_VARS if v.startswith("val_")) == 6
        and sum(1 for v in H60_VARS if not v.startswith("val_")) == 7)

    print("[2] the bar and the method are the frozen ones, not local copies")
    import model_h_scorecard as SC
    chk("band 20%", SC.BAND == 0.20)
    chk("min picks 50", SC.MIN_PICKS == 50)
    chk("min hit rate 54%", SC.MIN_HIT == 0.54)
    chk("one variable per 10 outcomes", SC.MIN_OUTCOMES_PER_VAR == 10)
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    import io as _io, tokenize as _tok
    code = " ".join(t.string for t in _tok.generate_tokens(_io.StringIO(body).readline)
                    if t.type in (_tok.NAME, _tok.OP, _tok.NUMBER))
    for bad in ("BAND", "MIN_PICKS", "MIN_HIT", "wilson", "0.54", "50"):
        chk(f"no local redefinition of {bad!r}", f"{bad} =" not in code, bad)
    chk("no scikit-learn anywhere in this module", "sklearn" not in body)

    print("[3] the frame carries both blocks and the target")
    d = frame()
    chk("the target column is present", "y" in d.columns)
    chk("every pre-registered variable is a column",
        all(v in d.columns for v in H60_VARS),
        str([v for v in H60_VARS if v not in d.columns]))
    chk("the valuation columns came from the reconciled block",
        d["val_ebitda_cr"].notna().sum() > 0 and d["val_ebitda_cr"].isna().sum() > 0)

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    r = run()
    print(f"selection bypassed: {r['selection_bypassed']}")
    print(f"variables: {len(r['variables_kept'])}")
    py = pd.DataFrame(r["per_year"])
    cols = [c for c in ("year", "n_train", "n_train_outcomes", "n_vars_fitted", "n_test",
                        "auc", "band_picks", "band_hits", "band_hit_rate", "base_rate",
                        "note") if c in py.columns]
    print(py[cols].to_string(index=False))
    print()
    for k, v in r["pooled"].items():
        print(f"  {k}: {v}")

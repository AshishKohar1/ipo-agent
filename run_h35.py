"""
run_h35.py — Model H-market, exactly as H35 pre-registered it and H56 settled it.

    python run_h35.py --self-test
    python run_h35.py                 # run, write reports/H35_RESULT.md

H35 (13 Oct 2026) fixed the six heat variables, equal weights, scheme C expanding with the
Y-2 embargo, and three pass criteria. H56 (5 Nov 2026) fixed the two things H35 left open:
missing values use option B (average the z-scores present), with option A (complete cases)
reported as a diagnostic that cannot change the verdict; tercile cut-offs come from the
training fold only.

Nothing in this module may be changed after seeing a result. That is the whole point of
both decisions having been recorded first.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# H35's six, in H35's order. Not a configurable list: changing it changes the decision.
H35_VARS = ["ipo_count_prior_3m", "ipo_count_prior_6m", "mean_listing_gain_prior_3m",
            "nifty_tri_ret_12m", "listing_gain_minus_sector_day",
            "turnover_x_issue_size"]
# "signed so that higher means hotter". For all six the raw value already rises with heat:
# a crowded calendar, a hot recent cohort, a strong index, a big pop against the sector and
# heavy first-day churn. So every sign is +1 and none is a judgement call.
SIGNS = {v: 1 for v in H35_VARS}
GAP_MIN_PP = 10.0
SIGN_AGREE_MIN = 0.75
P_MAX = 0.05


def zscore_in_fold(train: pd.Series, test: pd.Series):
    """Standardise BOTH folds by the training fold's mean and sd (H35).

    A test fold re-centred on its own mean cannot say that one year was hotter than
    another, which is the only thing H35 asks.
    """
    mu = float(np.nanmean(train.astype(float))) if len(train) else np.nan
    sd = float(np.nanstd(train.astype(float), ddof=0)) if len(train) else np.nan
    if not np.isfinite(sd) or sd == 0:
        # A constant training fold carries no information. NaN, not zero: zero would
        # claim the variable said "average heat" when it said nothing.
        nan_tr = pd.Series(np.nan, index=train.index, dtype=float)
        nan_te = pd.Series(np.nan, index=test.index, dtype=float)
        return nan_tr, nan_te
    return ((train.astype(float) - mu) / sd), ((test.astype(float) - mu) / sd)


def heat_score(zrow: pd.Series, option: str):
    """Equal-weight heat score from one row of z-scores. `option` is H56's B or A.

    B averages the z-scores PRESENT. A requires all six. Neither imputes: a missing z
    treated as 0 would assert average heat where nothing was measured.
    """
    vals = [float(zrow[v]) for v in zrow.index if pd.notna(zrow[v])]
    if option == "A" and len(vals) != len(zrow.index):
        return None
    if not vals:
        return None
    return float(np.mean(vals))


def tercile_cuts(train_scores: pd.Series):
    """The training fold's 1/3 and 2/3 quantiles (H56)."""
    s = pd.Series(train_scores).dropna().astype(float)
    if len(s) < 3:
        return (np.nan, np.nan)
    return (float(s.quantile(1.0 / 3.0)), float(s.quantile(2.0 / 3.0)))


def band(score, cuts) -> str | None:
    """COOLEST / MID / HOTTEST against the training fold's cuts."""
    if score is None or (isinstance(score, float) and not np.isfinite(score)):
        return None
    lo, hi = cuts
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return None
    if score <= lo:
        return "COOLEST"
    if score > hi:
        return "HOTTEST"
    return "MID"


def two_proportion_one_sided(k1: int, n1: int, k2: int, n2: int):
    """One-sided two-proportion z test, H0: p1 <= p2, alternative p1 > p2.

    `erfc` rather than scipy: rule 10 bans scikit-learn and the project keeps its own
    numerics. p = 0.5 * erfc(z / sqrt(2)) is the exact upper tail of the standard normal.
    """
    import math
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    z = (p1 - p2) / se
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def criteria(gap_pp, sign_agree, p):
    """H35's three, unchanged. -> [(name, required, achieved, passed), ...]"""
    return [
        ("coolest beats hottest by >= 10pp (pooled)", f">= {GAP_MIN_PP}pp",
         None if gap_pp is None else round(float(gap_pp), 2),
         gap_pp is not None and float(gap_pp) >= GAP_MIN_PP),
        ("the gap's sign holds in >= 75% of test years", f">= {SIGN_AGREE_MIN:.0%}",
         None if sign_agree is None else f"{float(sign_agree):.0%}",
         sign_agree is not None and float(sign_agree) >= SIGN_AGREE_MIN),
        ("one-sided two-proportion test on the pooled gap", f"p < {P_MAX}",
         None if p is None else round(float(p), 5),
         p is not None and float(p) < P_MAX),
    ]


def walk_forward(d: pd.DataFrame, option: str, win_col: str) -> pd.DataFrame:
    """Score every test year out of fold. One row per scored IPO.

    Scheme C expanding with the Y-2 embargo comes from `model_h_stability.windows`, the
    same function the stability analysis used. A second copy here could drift from it and
    then H35 would not be the test that was pre-registered.
    """
    import model_h_stability as MS
    years = sorted(int(y) for y in d["_y"].dropna().unique())
    out = []
    for train_years, test_year in MS.windows(years, "C", embargo=True):
        tr = d[d["_y"].isin(train_years)]
        te = d[d["_y"] == test_year]
        if tr.empty or te.empty:
            continue
        ztr = pd.DataFrame(index=tr.index)
        zte = pd.DataFrame(index=te.index)
        for v in H35_VARS:
            a, b = zscore_in_fold(tr[v], te[v])
            ztr[v] = a * SIGNS[v]
            zte[v] = b * SIGNS[v]
        tr_scores = ztr.apply(lambda r: heat_score(r, option), axis=1)
        cuts = tercile_cuts(tr_scores)
        for idx, r in zte.iterrows():
            sc = heat_score(r, option)
            out.append({"company": d.at[idx, "company"], "_y": test_year,
                        "score": sc, "band": band(sc, cuts),
                        "win": int(d.at[idx, win_col]),
                        "cut_lo": cuts[0], "cut_hi": cuts[1]})
    return pd.DataFrame(out)


def load(target: str = "1y") -> pd.DataFrame:
    """Features joined to the corrected excess-return target. Read-only."""
    import dataio
    f = pd.read_csv(ROOT / "data" / "model_h_features_full.csv")
    tf = "holding_target.csv" if target == "1y" else "holding_target_3y.csv"
    t = pd.read_csv(ROOT / "data" / tf)
    excess = "excess_1y_pp" if target == "1y" else "excess_3y_pp"
    for d in (f, t):
        d["_n"] = d["company"].map(lambda c: dataio.norm_name(c) if pd.notna(c) else "")
    m = f.merge(t[["_n", excess]], on="_n", how="inner")
    m["_y"] = pd.to_datetime(m["listing_date"], errors="coerce").dt.year
    m["win"] = (pd.to_numeric(m[excess], errors="coerce") > 0).astype(int)
    m["excess"] = pd.to_numeric(m[excess], errors="coerce")
    return m[m["_y"].notna() & m["excess"].notna()].copy()


def summarise(r: pd.DataFrame, src: pd.DataFrame):
    """The three tables H35 asks for, plus the criteria."""
    scored = r[r["band"].notna()].copy()
    ex = dict(zip(src["company"], src["excess"]))
    scored["excess"] = scored["company"].map(ex)
    terc = []
    for b in ("COOLEST", "MID", "HOTTEST"):
        g = scored[scored["band"] == b]
        terc.append({"tercile": b, "n": len(g),
                     "beat_pct": round(100.0 * g["win"].mean(), 2) if len(g) else None,
                     "mean_excess": round(float(g["excess"].mean()), 2) if len(g) else None,
                     "median_excess": round(float(g["excess"].median()), 2) if len(g) else None})
    tt = pd.DataFrame(terc)
    cool = scored[scored["band"] == "COOLEST"]
    hot = scored[scored["band"] == "HOTTEST"]
    gap = (100.0 * cool["win"].mean() - 100.0 * hot["win"].mean()) if len(cool) and len(hot) else None
    p = two_proportion_one_sided(int(cool["win"].sum()), len(cool),
                                 int(hot["win"].sum()), len(hot))
    yr = []
    for y, g in scored.groupby("_y"):
        c, h = g[g["band"] == "COOLEST"], g[g["band"] == "HOTTEST"]
        d = (100.0 * c["win"].mean() - 100.0 * h["win"].mean()) if len(c) and len(h) else None
        yr.append({"test_year": int(y), "n_cool": len(c), "n_hot": len(h),
                   "gap_pp": None if d is None else round(d, 2),
                   "sign": None if d is None else ("+" if d > 0 else ("0" if d == 0 else "-"))})
    yt = pd.DataFrame(yr)
    measurable = yt[yt["gap_pp"].notna()]
    agree = (float((measurable["gap_pp"] > 0).mean()) if len(measurable)
             and gap is not None and gap > 0
             else (float((measurable["gap_pp"] < 0).mean()) if len(measurable) else None))
    return tt, yt, criteria(gap, agree, p), {"gap": gap, "p": p, "agree": agree,
                                             "n_cool": len(cool), "n_hot": len(hot),
                                             "scored": len(scored), "rows": len(r)}


def _md_table(d: pd.DataFrame) -> list[str]:
    cols = list(d.columns)
    L = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in d.itertuples(index=False):
        L.append("| " + " | ".join("" if pd.isna(x) else str(x) for x in r) + " |")
    return L


def main() -> int:
    L = ["# H35 — Model H-market, the pre-registered run (2026-11-05)", "",
         "Specified 13 Oct 2026 (H35); the two open choices settled 5 Nov 2026 (H56) "
         "**before** this module existed. **Option B is binding; option A is a "
         "diagnostic and cannot change the verdict.** Tercile cut-offs come from the "
         "training fold. Scheme C expanding, Y-2 embargo, equal weights, no fitted "
         "coefficients.", ""]
    print_blocks = []
    results = {}
    for target in ("1y", "3y"):
        src = load(target)
        L += [f"## excess_{target}" + ("" if target == "1y" else "  (secondary)"), "",
              f"{len(src)} IPOs with a corrected {target} target, "
              f"{int(src['win'].sum())} beat the Nifty 50 TRI "
              f"({100*src['win'].mean():.1f}%).", ""]
        per = {}
        for opt in ("B", "A"):
            r = walk_forward(src, opt, "win")
            tt, yt, crit, meta = summarise(r, src)
            per[opt] = (tt, yt, crit, meta)
            tag = "BINDING" if opt == "B" else "diagnostic only"
            L += [f"### Option {opt} ({tag})", "",
                  f"Scored {meta['scored']} of {meta['rows']} test rows; "
                  f"coolest {meta['n_cool']}, hottest {meta['n_hot']}.", ""]
            L += _md_table(tt) + [""]
            L += _md_table(yt) + [""]
            print_blocks.append((target, opt, tt, yt, crit, meta))
        cb, ca = per["B"][2], per["A"][2]
        L += ["### Criteria", "",
              "| criterion | required | achieved (B, binding) | achieved (A, diagnostic) "
              "| pass/fail (B) |", "|---|---|---|---|---|"]
        for (n, req, achB, okB), (_, _, achA, _) in zip(cb, ca):
            L.append(f"| {n} | {req} | {achB} | {achA} | "
                     f"{'**PASS**' if okB else '**FAIL**'} |")
        verdict = "PASS" if all(x[3] for x in cb) else "FAIL"
        results[target] = verdict
        L += ["", f"**Verdict on excess_{target}: {verdict}** "
              f"(option B; all three criteria must hold).", ""]
    (ROOT / "reports" / "H35_RESULT.md").write_text("\n".join(L) + "\n",
                                                    encoding="utf-8")
    for target, opt, tt, yt, crit, meta in print_blocks:
        print(f"\n===== excess_{target}  option {opt} "
              f"({'BINDING' if opt == 'B' else 'diagnostic'}) =====")
        print(tt.to_string(index=False))
        print(yt.to_string(index=False))
        for n, req, ach, okx in crit:
            print(f"  {'PASS' if okx else 'FAIL'}  {n}: required {req}, achieved {ach}")
    print(f"\nverdicts: {results}")
    print(ROOT / "reports" / "H35_RESULT.md")
    return 0


def self_test() -> int:
    ok = fail = 0

    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] standardisation uses the TRAINING fold's mean and sd, never the test's")
    tr = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    te = pd.Series([100.0, 200.0])
    z_tr, z_te = zscore_in_fold(tr, te)
    chk("the training fold standardises to mean 0", abs(float(np.nanmean(z_tr))) < 1e-9)
    chk("a test value far outside the training range keeps a large z, not a rescaled one",
        float(z_te.iloc[0]) > 50, float(z_te.iloc[0]))
    chk("the test fold is NOT re-centred on its own mean",
        abs(float(np.nanmean(z_te))) > 50, float(np.nanmean(z_te)))
    chk("a constant training fold yields no z rather than a divide-by-zero",
        zscore_in_fold(pd.Series([2.0, 2.0, 2.0]), pd.Series([2.0]))[1].isna().all())

    print("\n[2] option B averages the z-scores PRESENT; option A needs all six")
    row_all = pd.Series({"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0, "f": 1.0})
    row_five = row_all.copy(); row_five["f"] = np.nan
    row_none = pd.Series({k: np.nan for k in "abcdef"})
    chk("B on six present is their mean", heat_score(row_all, "B") == 1.0)
    chk("B on five present is the mean of the five, not of six with a zero",
        heat_score(row_five, "B") == 1.0)
    chk("B with nothing present is None, never 0", heat_score(row_none, "B") is None)
    chk("A on six present is the same number as B", heat_score(row_all, "A") == 1.0)
    chk("A on five present is None - that is what 'complete cases' means",
        heat_score(row_five, "A") is None)
    chk("B never imputes a missing z as zero",
        heat_score(pd.Series({"a": 3.0, "b": np.nan}), "B") == 3.0)

    print("\n[3] tercile cut-offs come from the training fold (H56)")
    train = pd.Series([float(i) for i in range(1, 10)])     # 1..9
    lo, hi = tercile_cuts(train)
    chk("the cuts are the training fold's 1/3 and 2/3 quantiles",
        abs(lo - 3.6667) < 1e-3 and abs(hi - 6.3333) < 1e-3, (lo, hi))
    chk("a test score below the training lower cut is COOLEST",
        band(0.0, (lo, hi)) == "COOLEST")
    chk("a test score above the training upper cut is HOTTEST",
        band(99.0, (lo, hi)) == "HOTTEST")
    chk("between the cuts is MID", band(5.0, (lo, hi)) == "MID")
    chk("a whole test year may land in ONE band, which is the point of in-fold cuts",
        {band(x, (lo, hi)) for x in (90.0, 91.0, 92.0)} == {"HOTTEST"})
    chk("no score yields no band", band(None, (lo, hi)) is None)

    print("\n[4] the one-sided two-proportion test")
    # 60/100 against 40/100: z = (0.6-0.4)/sqrt(0.5*0.5*(1/100+1/100)) = 2.828, p ~ 0.00234
    p = two_proportion_one_sided(60, 100, 40, 100)
    chk("a 20pp gap on 100 each gives p about 0.0023", abs(p - 0.00234) < 5e-4, p)
    chk("equal proportions give p = 0.5", abs(two_proportion_one_sided(50, 100, 50, 100) - 0.5) < 1e-9)
    chk("the test is ONE-sided: the coolest doing WORSE gives p well above 0.05",
        two_proportion_one_sided(40, 100, 60, 100) > 0.95)
    chk("an empty arm gives no p rather than a crash",
        two_proportion_one_sided(0, 0, 10, 20) is None)

    print("\n[5] the three criteria are H35's, unchanged")
    c = criteria(gap_pp=12.0, sign_agree=0.8, p=0.04)
    chk("12pp, 80% of years, p=0.04 passes all three", all(x[3] for x in c), c)
    chk("criterion 1 needs >= 10pp, so 9.9pp fails",
        not criteria(gap_pp=9.9, sign_agree=0.8, p=0.04)[0][3])
    chk("criterion 2 needs >= 75% of test years, so 0.74 fails",
        not criteria(gap_pp=12.0, sign_agree=0.74, p=0.04)[1][3])
    chk("criterion 3 needs p < 0.05, so p = 0.05 fails",
        not criteria(gap_pp=12.0, sign_agree=0.8, p=0.05)[2][3])
    chk("a missing p fails criterion 3 rather than passing by default",
        not criteria(gap_pp=12.0, sign_agree=0.8, p=None)[2][3])
    chk("all three must hold, so one failure fails the rule",
        not all(x[3] for x in criteria(gap_pp=12.0, sign_agree=0.8, p=0.06)))

    print("\n[6] the six variables and their signs are H35's, and all are read-only here")
    chk("exactly six variables", len(H35_VARS) == 6, H35_VARS)
    chk("they are H35's list, in H35's order",
        H35_VARS == ["ipo_count_prior_3m", "ipo_count_prior_6m",
                     "mean_listing_gain_prior_3m", "nifty_tri_ret_12m",
                     "listing_gain_minus_sector_day", "turnover_x_issue_size"])
    chk("every sign is +1: for all six, a higher raw value IS hotter",
        set(SIGNS.values()) == {1} and len(SIGNS) == 6, SIGNS)
    chk("equal weights, so no fitted coefficient can enter",
        "polyfit" not in Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
        and "lstsq" not in Path(__file__).read_text(encoding="utf-8").split("def self_test")[0])

    print("\n[7] the walk-forward is scheme C with the Y-2 embargo, borrowed not rebuilt")
    import model_h_stability as MS
    chk("the windows come from model_h_stability, not a second implementation",
        "MS.windows(" in body and "def windows" not in body)
    w = dict((te, tr) for tr, te in MS.windows([2016, 2017, 2018, 2019, 2020], "C",
                                               embargo=True))
    chk("scheme C is expanding: 2020 trains on every prior year up to the embargo",
        w.get(2020) == [2016, 2017, 2018], w.get(2020))
    chk("the Y-2 embargo drops 2019, whose 12-month outcomes close inside 2020",
        2019 not in (w.get(2020) or []))

    print("\n[8] the run assigns bands from the training fold and nothing else")
    rng = np.random.default_rng(0)
    rows = []
    for yr in range(2015, 2024):
        for i in range(40):
            rows.append({"company": f"{yr}_{i}", "_y": yr,
                         "ipo_count_prior_3m": float(rng.normal(10 + (yr - 2015), 3)),
                         "ipo_count_prior_6m": float(rng.normal(20 + (yr - 2015), 4)),
                         "mean_listing_gain_prior_3m": float(rng.normal(5, 10)),
                         "nifty_tri_ret_12m": float(rng.normal(8, 12)),
                         "listing_gain_minus_sector_day": (float(rng.normal(2, 15))
                                                           if i % 2 else np.nan),
                         "turnover_x_issue_size": float(rng.normal(1, 0.4)),
                         "win": int(rng.random() < 0.4)})
    synth = pd.DataFrame(rows)
    rb = walk_forward(synth, "B", "win")
    chk("option B scores every row, including those missing a variable",
        rb["band"].notna().sum() == len(rb), f"{rb['band'].notna().sum()} of {len(rb)}")
    ra = walk_forward(synth, "A", "win")
    chk("option A scores only complete cases, so it covers fewer rows",
        ra["band"].notna().sum() < rb["band"].notna().sum(),
        (ra["band"].notna().sum(), rb["band"].notna().sum()))
    chk("both use the same test years", set(ra["_y"]) == set(rb["_y"]))
    chk("every scored row carries the band's three values only",
        set(rb["band"].dropna().unique()) <= {"COOLEST", "MID", "HOTTEST"})
    chk("no training row is scored - a row is only ever in its own test year",
        rb.groupby("company").size().max() == 1)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    main()

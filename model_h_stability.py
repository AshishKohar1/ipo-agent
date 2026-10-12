"""
model_h_stability.py — Phase 2.6: is each variable's relationship stable, or just recent?

Analysis only. **No final model, no variable set chosen, no hold advice.** H29 is unchanged
and nothing here touches it. The question is narrower and prior to all of that: for each
candidate variable, does its relationship with "beat the Nifty 50 TRI over the first year"
hold up across time, or does it hold only in the last few years, or not at all?

Why one variable at a time
--------------------------
The early windows are small. 2010-14 carries a few dozen IPOs with a corrected target and
perhaps twenty "beat Nifty" outcomes among them. The standing limit is **one variable per
ten outcomes**, so a multivariable fit on those windows would be fitting noise with
confidence. Each variable is therefore measured alone: binned on the training window, WoE
derived on the training window, and scored out of sample on the test year. Nothing is
selected, so nothing needs a correlation or VIF filter here.

Three window schemes, side by side
----------------------------------
  A  rolling 5-year   2010-14 -> 2015, 2011-15 -> 2016, ... 2020-24 -> 2025
  B  rolling 4-year   2010-13 -> 2014, ...                  2021-24 -> 2025
  C  expanding        every prior year -> the next

A and C disagree exactly when something changed: C keeps 2010 in the training set forever,
A forgets it. That is the comparison, not a robustness check on one of them.

The embargo, which these windows do not have
--------------------------------------------
A row listing in 2014 has a 12-month window that closes in 2015, so its outcome is **not
knowable** at the start of 2015 - yet scheme A trains on it to test 2015. The existing
`model_h_scorecard.walk_forward` uses a `Y-2` embargo for exactly this reason. The windows
here are the ones that were specified, so they are computed as specified; the same table is
also computed WITH the embargo, under `embargo=True`, so the size of the effect is visible
rather than argued about. Where the two disagree, the embargoed number is the honest one.

    python model_h_stability.py --run
    python model_h_stability.py --self-test
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
import model_h_scorecard as SC                                 # noqa: E402

FEATURES_FULL = ROOT / "data" / "model_h_features_full.csv"
REPORT = ROOT / "reports" / "MODEL_H_STABILITY.md"

IV_FLOOR = 0.02                # the same floor the selection step uses
MIN_TEST_N = 10                # below this a test year's AUC is flagged, not trusted
MIN_TRAIN_OUTCOMES = 10        # one variable per ten outcomes
STABLE_SIGN = 0.75
STABLE_IV = 0.60
RECENT_WINDOWS = 4


def load() -> pd.DataFrame:
    """The full feature table joined to the CORRECTED 1y target (H30).

    Mainboard only (H33): Model H excludes SME, and `is_sme` is dropped rather than used
    as a control, because the master has no SME rows for it to separate.
    """
    import model_h_targets as MT
    f = pd.read_csv(FEATURES_FULL, low_memory=False)
    t = MT.latest("1y")
    t = t[t["excess_corrected_pp"].notna()][
        ["symbol", "excess_corrected_pp", "H_label_corrected", "listing_date"]]
    d = f.merge(t, on="symbol", how="inner", suffixes=("", "_t"))
    d["y"] = pd.to_numeric(d["H_label_corrected"], errors="coerce")
    d["year"] = pd.to_datetime(d["listing_date_t"] if "listing_date_t" in d
                               else d["listing_date"], errors="coerce").dt.year
    if "is_sme" in d.columns:
        d = d[d["is_sme"].fillna(0) == 0]
    return d.dropna(subset=["y", "year"]).reset_index(drop=True)


def candidates(d: pd.DataFrame) -> list[str]:
    skip = {"company", "symbol", "listing_date", "listing_date_t", "y", "year",
            "excess_corrected_pp", "H_label_corrected", "is_sme",
            "sector_index", "nse_industry", "sector_index_missing_reason",
            "anchor_is_recent_cohort"}
    out = []
    for c in d.columns:
        if c in skip or c.endswith("_status"):
            continue
        s = pd.to_numeric(d[c], errors="coerce")
        if s.notna().sum() < 30 or s.nunique(dropna=True) < 2:
            continue
        out.append(c)
    return out


def windows(years: list[int], scheme: str, embargo: bool = False):
    """(train_years, test_year) pairs. `embargo` drops the year immediately before the
    test year, whose 12-month outcomes close inside it."""
    ys = sorted(set(int(y) for y in years))
    lo, hi = min(ys), max(ys)
    out = []
    for test in range(lo + 1, hi + 1):
        last = test - (2 if embargo else 1)
        if scheme == "A":
            first = last - 4
        elif scheme == "B":
            first = last - 3
        else:
            first = lo
        tr = [y for y in ys if first <= y <= last]
        if tr and test in ys:
            out.append((tr, test))
    return out


def measure(d: pd.DataFrame, var: str, tr_years: list[int], test: int) -> dict:
    """One variable, one window. Binned and WoE'd on the TRAINING fold only.

    `direction` is the sign of the relationship, read off the WoE of the highest bin minus
    the WoE of the lowest - not a correlation, because the binning is what the model would
    actually use and a monotone correlation can hide a U shape.
    """
    tr = d[d["year"].isin(tr_years)]
    te = d[d["year"] == test]
    res = {"variable": var, "scheme_train": f"{min(tr_years)}-{max(tr_years)}",
           "test_year": test, "n_train": len(tr), "n_test": len(te),
           "train_outcomes": int((tr["y"] == 1).sum()),
           "iv": None, "direction": None, "auc": None, "note": ""}
    if res["train_outcomes"] < MIN_TRAIN_OUTCOMES:
        res["note"] = (f"only {res['train_outcomes']} beat-Nifty outcomes in training "
                       f"(limit {MIN_TRAIN_OUTCOMES}) - not measured")
        return res
    if len(te) == 0:
        res["note"] = "no test rows"
        return res
    edges = SC.bin_edges(tr[var])
    btr = SC.apply_bins(tr[var], edges)
    woe, iv = SC.woe_table(btr, tr["y"])
    if not woe:
        res["note"] = "training fold has only one outcome class"
        return res
    res["iv"] = round(float(iv), 4)
    num = {k: v for k, v in woe.items() if k != "MISSING"}
    if len(num) >= 2:
        lo_k, hi_k = min(num, key=lambda k: int(k)), max(num, key=lambda k: int(k))
        res["direction"] = 1 if num[hi_k] > num[lo_k] else -1
    bte = SC.apply_bins(te[var], edges)
    # A test bin the training fold never saw gets WoE 0 - neutral. Dropping the row would
    # quietly change which rows the AUC is computed on.
    score = bte.map(lambda b: woe.get(b, 0.0)).to_numpy(dtype=float)
    res["auc"] = SC._auc(te["y"].to_numpy(dtype=float), score)
    if len(te) < MIN_TEST_N:
        res["note"] = f"test year has only {len(te)} rows - AUC not trustworthy"
    return res


def run_scheme(d: pd.DataFrame, scheme: str, embargo: bool = False) -> pd.DataFrame:
    vs = candidates(d)
    wins = windows(sorted(d["year"].unique()), scheme, embargo)
    rows = []
    for v in vs:
        for tr, te in wins:
            rows.append({**measure(d, v, tr, te), "scheme": scheme,
                         "embargo": bool(embargo)})
    return pd.DataFrame(rows)


def iv_ok_pre(g: pd.DataFrame) -> int:
    return int((g["iv"] >= IV_FLOOR).sum())


def classify(res: pd.DataFrame) -> pd.DataFrame:
    """STABLE / CURRENT / NOISE, with the exact counts behind each label."""
    out = []
    for v, g in res.groupby("variable"):
        g = g[g["iv"].notna()].sort_values("test_year")
        n = len(g)
        if n == 0:
            out.append({"variable": v, "label": "NOT MEASURED", "windows": 0,
                        "same_sign": 0, "iv_ok": 0, "median_iv": None,
                        "median_auc": None,
                        "why": "no window had enough beat-Nifty outcomes to measure"})
            continue
        dirs = g["direction"].dropna()
        # A variable whose bins collapse to ONE has no direction to agree or disagree
        # with. Calling that "the sign flips in 14 of 14 windows" would be false: the sign
        # was never measurable. An almost-constant flag - 95% of RHPs disclose no auditor
        # qualification - is in this class, and it is a fact about the variable, not noise
        # in the relationship.
        if len(dirs) == 0:
            out.append({"variable": v, "label": "NO SPREAD", "windows": n,
                        "same_sign": 0, "iv_ok": iv_ok_pre(g),
                        "median_iv": round(float(g["iv"].median()), 4),
                        "median_auc": (None if g["auc"].dropna().empty
                                       else round(float(g["auc"].median()), 4)),
                        "direction": None,
                        "why": ("the quantile bins collapse to one, so there is no "
                                "direction to measure - near-constant in every window")})
            continue
        mode = None
        if len(dirs):
            mode = 1 if (dirs == 1).sum() >= (dirs == -1).sum() else -1
        same = int((dirs == mode).sum()) if mode is not None else 0
        iv_ok = int((g["iv"] >= IV_FLOOR).sum())
        frac_sign = same / len(dirs) if len(dirs) else 0.0
        frac_iv = iv_ok / n
        tail = g.tail(RECENT_WINDOWS)
        tail_dirs = tail["direction"].dropna()
        tail_ok = (len(tail) and (tail["iv"] >= IV_FLOOR).all()
                   and len(tail_dirs) == len(tail) and tail_dirs.nunique() == 1)
        if frac_sign >= STABLE_SIGN and frac_iv >= STABLE_IV:
            label = "STABLE"
            why = (f"sign agrees in {same}/{len(dirs)} windows (>= {STABLE_SIGN:.0%}) "
                   f"and IV >= {IV_FLOOR} in {iv_ok}/{n} (>= {STABLE_IV:.0%})")
        elif tail_ok:
            label = "CURRENT"
            why = (f"sign agrees and IV >= {IV_FLOOR} in all of the last "
                   f"{len(tail)} windows, but only {same}/{len(dirs)} and {iv_ok}/{n} "
                   f"overall")
        elif frac_sign < STABLE_SIGN or frac_iv < 0.5:
            label = "NOISE"
            why = (f"sign agrees in only {same}/{len(dirs)} windows and IV >= "
                   f"{IV_FLOOR} in {iv_ok}/{n}")
        else:
            label = "WEAK"
            why = (f"sign agrees in {same}/{len(dirs)} and IV >= {IV_FLOOR} in "
                   f"{iv_ok}/{n} - neither stable nor clearly noise")
        out.append({"variable": v, "label": label, "windows": n,
                    "same_sign": same, "iv_ok": iv_ok,
                    "median_iv": round(float(g["iv"].median()), 4),
                    "median_auc": (None if g["auc"].dropna().empty
                                   else round(float(g["auc"].median()), 4)),
                    "direction": mode, "why": why})
    order = {"STABLE": 0, "CURRENT": 1, "WEAK": 2, "NOISE": 3, "NO SPREAD": 4,
             "NOT MEASURED": 5}
    r = pd.DataFrame(out)
    return r.sort_values(["label", "median_iv"],
                         key=lambda s: s.map(order) if s.name == "label" else -s,
                         ).reset_index(drop=True)


def md_table(d: pd.DataFrame, cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    body = []
    for _, r in d.iterrows():
        body.append("| " + " | ".join(
            "" if pd.isna(r.get(c)) else str(r.get(c)) for c in cols) + " |")
    return "\n".join([head, sep] + body)


def main(write: bool = True) -> dict:
    d = load()
    vs = candidates(d)
    print(f"{len(d)} mainboard rows with a corrected 1y target, "
          f"{len(vs)} candidate variables, years {int(d['year'].min())}-"
          f"{int(d['year'].max())}")
    print(f"base rate {100 * d['y'].mean():.1f}%")

    res = pd.concat([run_scheme(d, s) for s in ("A", "B", "C")], ignore_index=True)
    emb = pd.concat([run_scheme(d, s, embargo=True) for s in ("A", "B", "C")],
                    ignore_index=True)

    cls = {s: classify(res[res["scheme"] == s]) for s in ("A", "B", "C")}
    cls_emb = classify(emb[emb["scheme"] == "A"])

    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        L = [f"# Model H — variable stability ({pd.Timestamp.now():%Y-%m-%d})", "",
             "Analysis only. **No variable set is chosen here, no window is chosen, and "
             "no model is fitted.** H29 is unchanged.", "",
             f"- {len(d)} mainboard IPOs with a corrected 1y target, "
             f"{int(d['year'].min())}-{int(d['year'].max())}",
             f"- base rate {100 * d['y'].mean():.1f}% beat the Nifty 50 TRI over their "
             f"first year",
             f"- {len(vs)} candidate variables, each measured **one at a time** "
             f"(one variable per {MIN_TRAIN_OUTCOMES} beat-Nifty outcomes)",
             f"- IV floor {IV_FLOOR}; a test year with fewer than {MIN_TEST_N} rows is "
             f"flagged and its AUC is not trusted", "",
             "## Labels", "",
             f"- **STABLE** — same direction in >= {STABLE_SIGN:.0%} of windows AND "
             f"IV >= {IV_FLOOR} in >= {STABLE_IV:.0%}",
             f"- **CURRENT** — sign and IV hold in the last {RECENT_WINDOWS} windows only",
             "- **NOISE** — direction flips in more than a quarter of windows, or IV is "
             "below the floor in most",
             "- **WEAK** — neither; the counts are given so the reader can judge",
             "- **NOT MEASURED** — no window had enough outcomes", ""]
        for s, name in (("A", "A — rolling 5-year"), ("B", "B — rolling 4-year"),
                        ("C", "C — expanding")):
            L += [f"## Scheme {name}", "",
                  md_table(cls[s], ["variable", "label", "windows", "same_sign",
                                    "iv_ok", "median_iv", "median_auc", "direction"]),
                  "", "Why each label:", ""]
            for _, r in cls[s].iterrows():
                L.append(f"- `{r['variable']}` **{r['label']}** — {r['why']}")
            L.append("")
        L += ["## The embargo", "",
              "Scheme A trains on the year immediately before the test year, whose "
              "12-month outcomes close **inside** it. Below is scheme A recomputed with "
              "that year dropped. Where the two disagree, this one is the honest number.",
              "",
              md_table(cls_emb, ["variable", "label", "windows", "same_sign", "iv_ok",
                                 "median_iv", "median_auc"]), ""]
        REPORT.write_text("\n".join(L), encoding="utf-8")
        res.to_csv(ROOT / "reports" / "model_h_stability_windows.csv", index=False,
                   encoding="utf-8")
        emb.to_csv(ROOT / "reports" / "model_h_stability_windows_embargo.csv",
                   index=False, encoding="utf-8")
    return {"rows": len(d), "variables": len(vs), "classified": cls,
            "embargoed": cls_emb, "windows": res, "windows_embargo": emb}


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  ok   {name}")
        else:
            fail += 1
            print(f"  FAIL {name} {extra}")

    print("[1] the windows are the ones that were specified")
    ys = list(range(2010, 2026))
    a = windows(ys, "A")
    chk("scheme A's first window is 2010-14 -> 2015",
        a[4] == ([2010, 2011, 2012, 2013, 2014], 2015), a[4])
    chk("and its last is 2020-24 -> 2025",
        a[-1] == ([2020, 2021, 2022, 2023, 2024], 2025), a[-1])
    b = windows(ys, "B")
    chk("scheme B's first full window is 2010-13 -> 2014",
        b[3] == ([2010, 2011, 2012, 2013], 2014), b[3])
    chk("and its last is 2021-24 -> 2025",
        b[-1] == ([2021, 2022, 2023, 2024], 2025), b[-1])
    c = windows(ys, "C")
    chk("scheme C expands: the last window trains on everything before 2025",
        c[-1][0][0] == 2010 and c[-1][0][-1] == 2024 and c[-1][1] == 2025, c[-1])
    chk("A forgets the early years and C does not",
        a[-1][0][0] == 2020 and c[-1][0][0] == 2010)

    print(chr(10) + "[2] the embargo drops the year whose outcomes close in the test year")
    ae = windows(ys, "A", embargo=True)
    last = [w for w in ae if w[1] == 2025][0]
    chk("with the embargo, testing 2025 does not train on 2024",
        2024 not in last[0], last)
    chk("and it still trains on five years", len(last[0]) == 5, last)
    chk("without the embargo it DOES train on 2024",
        2024 in [w for w in a if w[1] == 2025][0][0])

    print(chr(10) + "[3] a thin training fold is refused, not measured")
    rng = np.random.default_rng(7)
    tiny = pd.DataFrame({"year": [2010] * 12 + [2011] * 40,
                         "y": [1] * 3 + [0] * 9 + list(rng.integers(0, 2, 40)),
                         "v": rng.normal(size=52)})
    m = measure(tiny, "v", [2010], 2011)
    chk("3 outcomes in training is below the limit and is not measured",
        m["iv"] is None and "not measured" in m["note"], m["note"])
    chk("and the note says how many there were", "3 beat-Nifty" in m["note"], m["note"])

    print(chr(10) + "[4] bins and WoE come from the TRAINING fold only")
    src = __import__("inspect").getsource(measure)
    chk("edges are derived from tr, never from the whole frame",
        "SC.bin_edges(tr[var])" in src and "bin_edges(d[" not in src)
    chk("WoE is derived from the training bins",
        "SC.woe_table(btr, tr[" in src)
    chk("an unseen test bin scores 0 rather than being dropped",
        "woe.get(b, 0.0)" in src)

    print(chr(10) + "[5] the labels are arithmetic, not judgement")
    fake = pd.DataFrame({
        "variable": ["s"] * 8 + ["n"] * 8,
        "test_year": list(range(2018, 2026)) * 2,
        "iv": [0.05] * 8 + [0.001] * 8,
        "direction": [1] * 8 + [1, -1, 1, -1, 1, -1, 1, -1],
        "auc": [0.55] * 16})
    cl = classify(fake).set_index("variable")
    chk("a variable with one sign and IV above the floor is STABLE",
        cl.loc["s", "label"] == "STABLE", cl.loc["s", "why"])
    chk("a variable that flips every window is NOISE",
        cl.loc["n", "label"] == "NOISE", cl.loc["n", "why"])
    chk("and the counts behind the label are printed with it",
        "/8" in cl.loc["s", "why"] and "/8" in cl.loc["n", "why"])
    flat = pd.DataFrame({"variable": ["f"] * 6, "test_year": list(range(2020, 2026)),
                         "iv": [0.04] * 6, "direction": [None] * 6, "auc": [0.5] * 6})
    fl = classify(flat).iloc[0]
    chk("a variable whose bins collapse is NO SPREAD, not NOISE",
        fl["label"] == "NO SPREAD", fl.to_dict())
    chk("and the reason says the direction was never measurable",
        "no direction to measure" in fl["why"], fl["why"])

    recent = pd.DataFrame({
        "variable": ["r"] * 8, "test_year": list(range(2018, 2026)),
        "iv": [0.001, 0.001, 0.001, 0.001, 0.05, 0.05, 0.05, 0.05],
        "direction": [1, -1, 1, -1, 1, 1, 1, 1], "auc": [0.52] * 8})
    chk("a variable that only works lately is CURRENT, not STABLE",
        classify(recent).iloc[0]["label"] == "CURRENT",
        classify(recent).iloc[0].to_dict())

    print(chr(10) + "[6] it fits no final model and gives no advice")
    # The scan EXCLUDES this function's own source. Every earlier version of a check like
    # this searched the whole file, found its own needles, and passed or failed against
    # nothing - five times in this project before today. A needle is never a literal in
    # the text it searches, and the cleanest way to guarantee that is to cut the searching
    # code out of the haystack.
    import inspect as _i
    whole = Path(__file__).read_text(encoding="utf-8")
    haystack = whole.replace(_i.getsource(self_test), "")
    chk("the self-test's own source is removed before scanning",
        "haystack" not in haystack and len(haystack) < len(whole))
    n_wf = "walk_" + "forward"
    n_sel = "sel" + "ect("
    chk("no call into the scorecard's walk-forward or its selection step",
        f"SC.{n_wf}" not in haystack and f"SC.{n_sel}" not in haystack)
    # Searching the prose for the word was the wrong test - this module's docstring says
    # "no hold advice" and the check found that. What matters is that it DEFINES no such
    # quantity and RETURNS no such thing, which is a property of the code, not the prose.
    names = [k for k in globals()
             if any(w in k.lower() for w in ("hold", "band", "allot", "pct_to_keep"))]
    chk("the module defines no hold, band or allotment quantity", not names, names)
    chk("and its only outputs are counts, classifications and windows",
        set(["rows", "variables", "classified", "embargoed", "windows",
             "windows_embargo"])
        == {m.group(1) for m in __import__("re").finditer(
            r'"(\w+)":', _i.getsource(main).split("return {")[-1])},
        {m.group(1) for m in __import__("re").finditer(
            r'"(\w+)":', _i.getsource(main).split("return {")[-1])})
    n_hit = "MIN_" + "HIT"
    chk("H29's threshold is not imported, read or restated here",
        n_hit not in haystack and "0.54" not in haystack)
    chk("and H29 is mentioned, to say it is unchanged",
        "H29" in haystack)

    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.run:
        out = main()
        for s in ("A", "B", "C"):
            print(f"{chr(10)}=== scheme {s}")
            print(out["classified"][s][["variable", "label", "windows", "same_sign",
                                        "iv_ok", "median_iv", "median_auc",
                                        "direction"]].to_string(index=False))
        print(f"{chr(10)}=== scheme A WITH the embargo")
        print(out["embargoed"][["variable", "label", "windows", "same_sign", "iv_ok",
                               "median_iv", "median_auc"]].to_string(index=False))
        print(f"{chr(10)}wrote {REPORT.relative_to(ROOT)}")

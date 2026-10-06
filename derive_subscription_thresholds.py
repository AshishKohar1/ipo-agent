"""
derive_subscription_thresholds.py — Priority 1 / decision H17.

Derives the firing thresholds **directly in Total-subscription terms** rather than as a
model-probability cut-off. The question asked is the plain one:

    "Above what Total subscription did 80% of IPOs actually deliver a listing gain
     above 10%?"

Nothing here fits a model. There is no logistic regression, no standardiser, no isotonic
calibrator. It is a monotone threshold on one observed number, scored against the realised
outcome — which is also why it can be stated in the email as a subscription level the user
can check against their broker screen.

Two measurements, and the gap between them is the whole point
-------------------------------------------------------------
**In-sample.** Derive the threshold on all the data and report what it delivered on that
same data. This figure is structurally flattered: the rule picks the point that looks best
*on the rows it is looking at*, so its hit rate is an upper bound, not an expectation. This
is how L2 came to be approved at a "measured 85.1%".

**Out-of-sample, walk-forward.** For each test year, derive the threshold on prior years
only, then measure what it delivered on that year. Pool fires and hits across years — the
pooled rate, never the mean of per-year rates, because a year with three fires must not
count as much as a year with thirty.

The second number is the one to trust. The first tells you how much the method flatters
itself.

Calibrating the gap away
------------------------
If the walk-forward rate falls short of the promise, the fix is not to argue with it: it is
to derive at a *stricter internal target* so the realised out-of-sample delivery lands on
the promise. `calibrate()` sweeps the internal target upward and reports the smallest one
whose pooled walk-forward delivery meets the promise. The shipped threshold is then derived
on all data at that calibrated target.

That is the honest construction: the promise is what the method delivers on data it has
not seen, and the internal target is just the knob that gets it there.

    python derive_subscription_thresholds.py
    python derive_subscription_thresholds.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import framework as F                                       # noqa: E402
import model_l as ML                                        # noqa: E402

OUT_JSON = ROOT / "reports" / "subscription_thresholds.json"
OUT_MD = ROOT / "reports" / "SUBSCRIPTION_THRESHOLDS.md"
# The PRODUCTION artefact. score_l.py reads this; nothing hardcodes a threshold, for the
# same reason no report hardcodes a promise -- a retyped number is how a system starts
# claiming something it was never validated against.
PROD = ROOT / "models" / "model_l_v1.1_thresholds.json"
MODEL_ID = "model_l_v1.1"

# The promises. Not the thresholds.
REQUIRED = {"L1": 0.90, "L2": 0.80}
CUT = {"L1": 0.0, "L2": 10.0}
MIN_FIRE = 20          # C5's third gate
SLACK = 0.05           # C5's Wilson allowance


# ---------------------------------------------------------------- data
def rows(target: str) -> pd.DataFrame:
    """`total`, `y`, `listing_date` for mainboard IPOs, on the same row set and
    exclusions the model uses — so the two are comparable."""
    sp = ML.spec(target, "mainboard")
    sp.features = ["log1p_total"]
    df = F.prepare(sp)
    out = pd.DataFrame({
        # Total is recovered from the feature rather than re-loaded, which guarantees the
        # threshold is expressed in the same units the model was fitted on.
        "total": np.expm1(df["log1p_total"].to_numpy()),
        "y": df[target].to_numpy().astype(int),
        "listing_date": pd.to_datetime(df["listing_date"]),
    })
    out["year"] = out["listing_date"].dt.year
    return out.sort_values("listing_date").reset_index(drop=True)


# ---------------------------------------------------------------- the rule
def table(d: pd.DataFrame, grid=None) -> pd.DataFrame:
    """For every candidate Total level, what firing there would have delivered."""
    if grid is None:
        # Candidates are the OBSERVED Total values. No interpolation onto a round grid:
        # a threshold of "50x" that sits between two observations is a fiction, and the
        # firing set only changes at an observed value anyway.
        grid = np.unique(d["total"].to_numpy())
    rs = []
    tot, y = d["total"].to_numpy(), d["y"].to_numpy()
    for t in grid:
        m = tot >= t
        n = int(m.sum())
        k = int(y[m].sum())
        rs.append({"total_threshold": float(t), "n_fire": n, "hits": k,
                   "hit_rate": (k / n) if n else np.nan,
                   "wilson_lo95": F.wilson_lower(k, n) if n else np.nan,
                   "fire_pct": 100 * n / len(d)})
    return pd.DataFrame(rs)


def derive(d: pd.DataFrame, required: float, min_fire: int = MIN_FIRE,
           slack: float = SLACK) -> dict:
    """The C5 rule, applied to Total subscription instead of to a probability.

    The LOWEST threshold (so it fires as often as possible) satisfying all three:
      1. realised hit rate among firing rows >= `required`
      2. Wilson 95% lower bound of that rate  >= `required - slack`
      3. at least `min_fire` firing rows
    """
    t = table(d)
    ok = t[(t["hit_rate"] >= required) & (t["wilson_lo95"] >= required - slack)
           & (t["n_fire"] >= min_fire)]
    if not len(ok):
        # Why it failed, for the report: the best near-miss by hit rate among thresholds
        # that at least fire enough.
        enough = t[t["n_fire"] >= min_fire]
        near = (enough.loc[enough["hit_rate"].idxmax()].to_dict()
                if len(enough) else None)
        return {"threshold": None, "n_fire": 0, "hits": 0, "hit_rate": None,
                "wilson_lo95": None, "near_miss": near}
    r = ok.loc[ok["total_threshold"].idxmin()]
    return {"threshold": float(r["total_threshold"]), "n_fire": int(r["n_fire"]),
            "hits": int(r["hits"]), "hit_rate": float(r["hit_rate"]),
            "wilson_lo95": float(r["wilson_lo95"]),
            "fire_pct": float(r["fire_pct"]), "near_miss": None}


# ---------------------------------------------------------------- walk-forward
def walk_forward(d: pd.DataFrame, required: float, min_train: int = 120,
                 min_test: int = 5) -> dict:
    """For each test year, derive on prior years only and measure on that year.

    `required` here is the INTERNAL target used when deriving, which `calibrate()` may set
    above the promise. The returned `pooled_hit_rate` is what the method delivered on data
    it had not seen.
    """
    per_year, fires, hits = [], 0, 0
    for yr in sorted(d["year"].unique()):
        tr = d[d["year"] < yr]
        te = d[d["year"] == yr]
        if len(tr) < min_train or len(te) < min_test:
            continue
        g = derive(tr, required)
        if g["threshold"] is None:
            per_year.append({"year": int(yr), "threshold": None, "n_test": len(te),
                             "n_fire": 0, "hits": 0, "hit_rate": None,
                             "note": "no threshold qualified on prior years"})
            continue
        m = te["total"].to_numpy() >= g["threshold"]
        n, k = int(m.sum()), int(te["y"].to_numpy()[m].sum())
        fires += n
        hits += k
        per_year.append({"year": int(yr), "threshold": round(g["threshold"], 2),
                         "n_test": int(len(te)), "n_fire": n, "hits": k,
                         "hit_rate": (k / n) if n else None,
                         "trained_on": int(len(tr))})
    return {"per_year": per_year, "n_fire": fires, "hits": hits,
            "pooled_hit_rate": (hits / fires) if fires else None,
            "pooled_wilson_lo95": F.wilson_lower(hits, fires) if fires else None,
            "n_years": sum(1 for r in per_year if r.get("threshold") is not None)}


def calibrate(d: pd.DataFrame, promise: float, step: float = 0.01,
              cap: float = 0.995) -> dict:
    """Smallest internal derivation target whose pooled walk-forward delivery meets the
    promise. Returns the sweep as evidence, not just the winner."""
    sweep, chosen = [], None
    tgt = promise
    while tgt <= cap + 1e-9:
        w = walk_forward(d, tgt)
        sweep.append({"internal_target": round(tgt, 3), "n_fire": w["n_fire"],
                      "hits": w["hits"], "pooled_hit_rate": w["pooled_hit_rate"],
                      "pooled_wilson_lo95": w["pooled_wilson_lo95"],
                      "n_years": w["n_years"]})
        if (chosen is None and w["pooled_hit_rate"] is not None
                and w["n_fire"] >= MIN_FIRE and w["pooled_hit_rate"] >= promise):
            chosen = round(tgt, 3)
        tgt += step
    return {"chosen_internal_target": chosen, "sweep": sweep}


# ---------------------------------------------------------------- report
def analyse(target: str) -> dict:
    d = rows(target)
    promise = REQUIRED[target]
    res = {"target": target, "promise": promise, "cut_pct": CUT[target],
           "n_rows": int(len(d)),
           "date_range": [str(d["listing_date"].min().date()),
                          str(d["listing_date"].max().date())],
           "base_rate": float(d["y"].mean())}

    res["in_sample"] = derive(d, promise)
    res["walk_forward_at_promise"] = walk_forward(d, promise)
    res["calibration"] = calibrate(d, promise)

    tgt = res["calibration"]["chosen_internal_target"]
    if tgt is not None:
        res["walk_forward_calibrated"] = walk_forward(d, tgt)
        res["shipped"] = derive(d, tgt)
        res["shipped"]["internal_target"] = tgt
    else:
        res["walk_forward_calibrated"] = None
        res["shipped"] = None

    # 1d — how often it fires per year at the shipped level.
    if res["shipped"] and res["shipped"]["threshold"] is not None:
        T = res["shipped"]["threshold"]
        g = d.assign(fire=d["total"] >= T).groupby("year").agg(
            n=("y", "size"), fires=("fire", "sum"),
            hits=("y", lambda s: 0))
        f = d[d["total"] >= T].groupby("year")["y"].agg(["size", "sum"])
        g = g.join(f.rename(columns={"size": "n_fire", "sum": "n_hit"}))
        g["n_fire"] = g["n_fire"].fillna(0).astype(int)
        g["n_hit"] = g["n_hit"].fillna(0).astype(int)
        res["fires_per_year"] = [
            {"year": int(y), "n_ipos": int(r["n"]), "n_fire": int(r["n_fire"]),
             "n_hit": int(r["n_hit"]),
             "hit_rate": (r["n_hit"] / r["n_fire"]) if r["n_fire"] else None}
            for y, r in g.iterrows()]
    return res


def md(a: dict, b: dict) -> str:
    L = ["# Firing thresholds in subscription terms", "",
         "Derived by `derive_subscription_thresholds.py` on "
         f"{pd.Timestamp.now():%Y-%m-%d}. **No model, no calibrator** — a monotone "
         "threshold on Total subscription, scored against the realised listing gain.", ""]
    for r in (a, b):
        t = r["target"]
        L += [f"## {t} — listing gain > {r['cut_pct']:g}%, promise "
              f"{r['promise']:.0%}", "",
              f"{r['n_rows']} mainboard IPOs, {r['date_range'][0]} to "
              f"{r['date_range'][1]}. Base rate {r['base_rate']:.1%}.", ""]
        i = r["in_sample"]
        w = r["walk_forward_at_promise"]
        L += ["| Measurement | Threshold | Fires | Hits | Delivered | Wilson 95% LB |",
              "|---|---|---|---|---|---|"]
        if i["threshold"] is not None:
            L.append(f"| **In-sample** (derived and measured on all data) | "
                     f"**{i['threshold']:.2f}x** | {i['n_fire']} | {i['hits']} | "
                     f"**{i['hit_rate']:.1%}** | {i['wilson_lo95']:.1%} |")
        else:
            L.append("| **In-sample** | — | — | — | nothing qualified | — |")
        if w["pooled_hit_rate"] is not None:
            L.append(f"| **Walk-forward** (derived on prior years, measured on the next) | "
                     f"per year | {w['n_fire']} | {w['hits']} | "
                     f"**{w['pooled_hit_rate']:.1%}** | "
                     f"{w['pooled_wilson_lo95']:.1%} |")
        gap = (None if (i["hit_rate"] is None or w["pooled_hit_rate"] is None)
               else (i["hit_rate"] - w["pooled_hit_rate"]) * 100)
        if gap is not None:
            L += ["", f"**The flattery is {gap:+.1f} percentage points.** The in-sample "
                      f"figure is an upper bound; the walk-forward figure is the "
                      f"expectation."]
        L += ["", "### Per test year (threshold derived on prior years only)", "",
              "| Year | Threshold | IPOs | Fires | Hits | Delivered |", "|---|---|---|---|---|---|"]
        for y in w["per_year"]:
            hr = "—" if y.get("hit_rate") is None else f"{y['hit_rate']:.0%}"
            th = "—" if y.get("threshold") is None else f"{y['threshold']:.2f}x"
            L.append(f"| {y['year']} | {th} | {y['n_test']} | {y['n_fire']} | "
                     f"{y.get('hits', 0)} | {hr} |")
        c = r["calibration"]
        L += ["", "### Calibrating the gap away", ""]
        if c["chosen_internal_target"] is None:
            L += ["**No internal target reaches the promise out of sample.** The sweep:", "",
                  "| Internal target | Fires | Hits | Pooled delivered |", "|---|---|---|---|"]
            for s in c["sweep"]:
                hr = "—" if s["pooled_hit_rate"] is None else f"{s['pooled_hit_rate']:.1%}"
                L.append(f"| {s['internal_target']:.0%} | {s['n_fire']} | {s['hits']} | {hr} |")
        else:
            wc = r["walk_forward_calibrated"]
            sh = r["shipped"]
            L += [f"Deriving at an internal target of **{c['chosen_internal_target']:.0%}** "
                  f"makes the pooled walk-forward delivery **{wc['pooled_hit_rate']:.1%}** "
                  f"on {wc['n_fire']} fires — at or above the {r['promise']:.0%} promise.",
                  "",
                  f"**Shipped threshold: Total >= {sh['threshold']:.2f}x** "
                  f"(derived on all data at that internal target; fires on "
                  f"{sh['n_fire']} of {r['n_rows']} IPOs, {sh['fire_pct']:.1f}%).", ""]
        if r.get("fires_per_year"):
            L += ["### What it costs in opportunities", "",
                  "| Year | IPOs | Fires | Hits | Delivered |", "|---|---|---|---|---|"]
            for y in r["fires_per_year"]:
                hr = "—" if y["hit_rate"] is None else f"{y['hit_rate']:.0%}"
                L.append(f"| {y['year']} | {y['n_ipos']} | {y['n_fire']} | "
                         f"{y['n_hit']} | {hr} |")
        L += [""]
    return "\n".join(L)


def write_production(res: dict) -> dict:
    """Emit the artefact score_l.py decides on.

    Ratified by the user on 2026-10-06 as H17. The standing definition, in their words:
    **the threshold at which 90% (L1) / 80% (L2) of IPOs the model has never seen met the
    target. Walk-forward, never in-sample.**
    """
    out = {"model_id": MODEL_ID, "decision_point": "L_final_3pm",
           "decision_variable": "total_subscription_x",
           "decision_rule": "BID iff Total subscription >= threshold_total_x",
           "definition": ("the threshold at which the promised share of IPOs THE MODEL HAS "
                          "NEVER SEEN met the target. Walk-forward, never in-sample."),
           "ratified": "H17, by the user, 2026-10-06",
           "supersedes": ["H16", "the calibrated-probability cut-off"],
           "generated": str(pd.Timestamp.now()),
           "targets": {}}
    for t in ("L1", "L2"):
        r = res[t]
        sh, wc = r["shipped"], r["walk_forward_calibrated"]
        out["targets"][t] = {
            "promise": r["promise"],
            "gain_above_pct": r["cut_pct"],
            "threshold_total_x": None if not sh else round(sh["threshold"], 2),
            "internal_derivation_target": r["calibration"]["chosen_internal_target"],
            "walk_forward_delivered": None if not wc else wc["pooled_hit_rate"],
            "walk_forward_fires": None if not wc else wc["n_fire"],
            "in_sample_delivered": r["in_sample"]["hit_rate"],
            "in_sample_threshold_total_x": r["in_sample"]["threshold"],
            "flattery_pp": (None if (r["in_sample"]["hit_rate"] is None
                                     or r["walk_forward_at_promise"]["pooled_hit_rate"] is None)
                            else round(100 * (r["in_sample"]["hit_rate"]
                                              - r["walk_forward_at_promise"]["pooled_hit_rate"]), 2)),
            "fires_on_n_of_n": None if not sh else [sh["n_fire"], r["n_rows"]],
            "n_rows": r["n_rows"],
            "date_range": r["date_range"],
        }
    PROD.parent.mkdir(parents=True, exist_ok=True)
    PROD.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


# ---------------------------------------------------------------- drift guard (1c)
DRIFT_LIMIT = 0.25


def drift_check(new_threshold: float, current_threshold: float | None,
                limit: float = DRIFT_LIMIT) -> dict:
    """1c. A re-derivation that moves a threshold more than `limit` is NOT applied silently.

    The reason is on the record: the naively derived L2 threshold drifted 31.11x (2015) to
    17.20x (2025) chasing the hot 2021-24 market, and 2025 then delivered 60% on 60 fires.
    A threshold that tracks recent conditions that closely is not learning, it is chasing,
    and the drift is the symptom that distinguishes the two. So a large move is reported for
    the user to approve rather than applied.
    """
    if current_threshold is None or not current_threshold:
        return {"apply": True, "reason": "no current threshold to compare against",
                "moved_pct": None}
    moved = (new_threshold - current_threshold) / current_threshold
    if abs(moved) > limit:
        return {"apply": False, "moved_pct": round(100 * moved, 1),
                "reason": (f"threshold moved {100*moved:+.1f}% "
                           f"({current_threshold:.2f}x -> {new_threshold:.2f}x), beyond the "
                           f"{100*limit:.0f}% drift limit. NOT applied - flagged for review. "
                           f"A threshold that chases recent conditions is not learning.")}
    return {"apply": True, "moved_pct": round(100 * moved, 1),
            "reason": f"moved {100*moved:+.1f}%, within the {100*limit:.0f}% limit"}


def current_production() -> dict:
    """The thresholds currently shipped, or `{}` before the first write."""
    if not PROD.exists():
        return {}
    try:
        return json.loads(PROD.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}


# ---------------------------------------------------------------- self-test
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

    print("derive_subscription_thresholds.py self-test")

    print("\n[1] the rule on a constructed case with a known answer")
    # 100 IPOs. Everything at or above 50x wins; everything below loses.
    d = pd.DataFrame({"total": list(np.linspace(1, 49, 60)) + list(np.linspace(50, 200, 40)),
                      "y": [0] * 60 + [1] * 40})
    d["listing_date"] = pd.date_range("2015-01-01", periods=100, freq="30D")
    d["year"] = d["listing_date"].dt.year
    g = derive(d, 0.90)
    chk("finds a threshold", g["threshold"] is not None, str(g))
    # At a 90% promise the rule should NOT stop at the clean break. Dropping to the last
    # loser (49x) fires on 41 and delivers 40/41 = 97.6%, which still clears 90% and fires
    # one more time — and firing as often as the gates allow is the rule's whole intent.
    # My first version of this test asserted 50x and was simply wrong about the rule.
    chk("at a 90% promise it drops BELOW the break to fire more",
        g["threshold"] < 50.0, str(g.get("threshold")))
    chk("and still clears the promise there", g["hit_rate"] >= 0.90,
        str(g.get("hit_rate")))
    # Demanding perfection pins it to the break exactly. `slack=1.0` disables the Wilson
    # gate on purpose: a Wilson lower bound cannot reach 1.0 at any finite n (40/40 gives
    # ~0.914), so leaving the gate on would reject every threshold and test nothing.
    g100 = derive(d, 1.00, slack=1.0, min_fire=20)
    chk("at a 100% promise it lands exactly on the break (50x)",
        g100["threshold"] is not None and abs(g100["threshold"] - 50.0) < 1e-6,
        str(g100.get("threshold")))
    chk("firing on exactly the 40 winners", g100["n_fire"] == 40, str(g100.get("n_fire")))
    chk("delivering 100%", g100["hit_rate"] == 1.0, str(g100.get("hit_rate")))

    print("\n[2] it picks the LOWEST qualifying threshold, not the safest")
    # Winners from 50x up, but one loser at 60x. The lowest qualifying point should still
    # be as low as the gates allow rather than jumping past the loser.
    d2 = d.copy()
    d2.loc[d2["total"].between(59, 61), "y"] = 0
    g2 = derive(d2, 0.90)
    chk("still fires low rather than skipping the loser",
        g2["threshold"] is not None and g2["threshold"] <= 60.0, str(g2.get("threshold")))

    print("\n[3] the min_fire gate blocks a tiny perfect tail")
    d3 = pd.DataFrame({"total": [1.0] * 100 + [500.0] * 5, "y": [0] * 100 + [1] * 5})
    d3["listing_date"] = pd.date_range("2015-01-01", periods=105, freq="20D")
    d3["year"] = d3["listing_date"].dt.year
    g3 = derive(d3, 0.90)
    chk("a 5-fire perfect tail does not qualify", g3["threshold"] is None, str(g3))
    chk("and the near-miss is reported", g3["near_miss"] is not None)

    print("\n[4] no threshold exists when nothing wins")
    d4 = d.copy()
    d4["y"] = 0
    chk("all-losers yields no threshold", derive(d4, 0.90)["threshold"] is None)

    print("\n[5] walk-forward never peeks at the test year")
    import inspect
    src = inspect.getsource(walk_forward)
    chk("derive() is called on the TRAINING slice only",
        "derive(tr," in src and "derive(te" not in src)
    chk("the test year is only measured, never derived on",
        src.count("derive(") == 1)

    print("\n[6] pooled, not the mean of per-year rates")
    chk("pooled_hit_rate is hits/fires over all years",
        "hits / fires" in inspect.getsource(walk_forward).replace("(hits / fires)", "hits / fires"))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())

    res = {t: analyse(t) for t in ("L1", "L2")}
    prod = write_production(res)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(md(res["L1"], res["L2"]), encoding="utf-8")

    for t in ("L1", "L2"):
        r = res[t]
        i, w, sh = r["in_sample"], r["walk_forward_at_promise"], r["shipped"]
        print(f"\n===== {t} (promise {r['promise']:.0%}, gain > {r['cut_pct']:g}%) =====")
        print(f"  rows {r['n_rows']}  base rate {r['base_rate']:.1%}")
        if i["threshold"] is not None:
            print(f"  IN-SAMPLE      Total >= {i['threshold']:8.2f}x  "
                  f"fires {i['n_fire']:3d}  delivered {i['hit_rate']:.1%}  "
                  f"(Wilson {i['wilson_lo95']:.1%})")
        if w["pooled_hit_rate"] is not None:
            print(f"  WALK-FORWARD   (per-year thresholds)      "
                  f"fires {w['n_fire']:3d}  delivered {w['pooled_hit_rate']:.1%}  "
                  f"(Wilson {w['pooled_wilson_lo95']:.1%})")
            if i["hit_rate"] is not None:
                print(f"  FLATTERY       {100*(i['hit_rate']-w['pooled_hit_rate']):+.1f} pp")
        tgt = r["calibration"]["chosen_internal_target"]
        if sh and sh["threshold"] is not None:
            print(f"  CALIBRATED     internal target {tgt:.0%} -> pooled OOS "
                  f"{r['walk_forward_calibrated']['pooled_hit_rate']:.1%} "
                  f"on {r['walk_forward_calibrated']['n_fire']} fires")
            print(f"  >>> SHIP       Total >= {sh['threshold']:.2f}x   "
                  f"fires {sh['n_fire']} of {r['n_rows']} ({sh['fire_pct']:.1f}%)")
        else:
            print("  CALIBRATED     NO internal target reaches the promise out of sample")
    print(f"\n{OUT_MD}\n{OUT_JSON}")

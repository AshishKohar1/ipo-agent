"""
score_l.py — Model L scoring with **no modelling dependencies at all** (Priority 1b).

Why this module exists
----------------------
On 2–3 Oct 2026 every scheduled GitHub Actions run died in ~35 s with

    ModuleNotFoundError: No module named 'joblib'   (models/framework.py:32)

`send_daily_email.py` imported `model_l`, which imports `framework`, which imports
`joblib`. joblib is present on the laptop only because scikit-learn once pulled it in; the
project bans scikit-learn (PLAN.md rule 10), so requirements.txt never listed joblib and
the cloud never got it. The result: a *modelling* dependency broke *mail delivery*, which
is a coupling that should not exist. No email was sent for three days.

So the live path no longer touches the modelling stack. This module scores from the
portable coefficient JSON that `stage16_model_l.py` exports —
`models/model_l_v1.0_{l1,l2}_coefficients.json` — using **only the standard library**:
`json`, `math` and `bisect`. No numpy, no pandas, no joblib, no framework, no dataio.
Nothing that can be missing from a clean `pip install -r requirements.txt`.

The JSON is self-describing and carries its own 6-step recipe in its `scoring` key. This
file implements exactly that recipe, and `self_test()` checks it reproduces the joblib
bundle's verdicts where the bundle can be loaded (laptop only). The JSON is therefore the
artefact of record for live scoring, and the bundle is the artefact of record for fitting.

Output discipline (G2) is unchanged: the verdict and the threshold met, never the
calibrated probability as a literal chance. The probability stays under `diagnostics`.

    python score_l.py 12.4          # score a total subscription of 12.4x
    python score_l.py --self-test
"""
from __future__ import annotations
import bisect
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COEF_DIR = ROOT / "models"

MODEL_ID = "model_l_v1.1"
# H17, ratified by the user 2026-10-06. The DECISION is a plain subscription threshold.
# There is no calibrated probability anywhere in the decision path: `score_one` compares
# Total subscription to a number and that is the whole of it.
#
# The user's standing definition of that number, recorded verbatim:
#   "the threshold at which 90% (L1) / 80% (L2) of IPOs the model has never seen met the
#    target. Walk-forward, never in-sample."
# In-sample flatters by 3.8pp (L1) and 4.8pp (L2), and that gap produced BOTH earlier
# failures -- H16's apparent shortfall and the shipped bundle's over-conservatism.
#
# The probability is still COMPUTED, because it is worth logging for calibration drift, but
# it is confined to `diagnostics` and cannot reach a verdict.
THRESHOLDS = ROOT / "models" / "model_l_v1.1_thresholds.json"
# The fit whose coefficients feed the drift-monitoring probability (not the decision).
COEF_MODEL_ID = "model_l_v1.0"
DECISION_POINT = "L_final_3pm"
TARGETS = ("L1", "L2")
PROFILE_LABELS = ("institution-led", "balanced", "balanced", "retail-skewed")

# H11/H12: one variable only. log1p(Total subscription). Issue size is dropped.
FEATURES = ["log1p_total"]


class CoefficientsMissing(RuntimeError):
    """The portable JSON is absent or unreadable. Fail loudly — never score on a guess."""


_CACHE: dict[str, dict] = {}


def load(target: str) -> dict:
    """The portable coefficient JSON for L1 or L2."""
    if target in _CACHE:
        return _CACHE[target]
    # Pinned to v1.0 on purpose. Under H17 the coefficients no longer make the decision --
    # they only produce the drift-monitoring probability in `diagnostics` -- and that
    # probability is only comparable over time if it keeps coming from the SAME fit. Bumping
    # this with MODEL_ID would silently change what the drift series measures.
    path = COEF_DIR / f"{COEF_MODEL_ID}_{target.lower()}_coefficients.json"
    if not path.exists():
        raise CoefficientsMissing(
            f"{path} is missing. Live scoring reads the portable JSON, not the joblib "
            f"bundle (Priority 1b). Re-export it with `python stage16_model_l.py`.")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise CoefficientsMissing(f"{path} is unreadable: {type(e).__name__}: {e}") from e
    for k in ("features", "standardised_coefficients", "standardiser_mean",
              "standardiser_scale", "intercept", "required_hit_rate"):
        if k not in d:
            raise CoefficientsMissing(f"{path} has no '{k}' key — it is not a Model L export.")
    _CACHE[target] = d
    return d


# ---------------------------------------------------------------- the recipe
def make_features(total: float) -> dict[str, float]:
    """Step 1. The whole feature vector, which since H11 is one number."""
    return {"log1p_total": math.log1p(float(total))}


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    """numpy.interp on plain lists: linear between knots, flat outside them.

    `np.interp` clamps to the end values rather than extrapolating, and the isotonic
    calibrator cannot extrapolate anyway (models/calibration.py), so clamping is the
    correct behaviour and not a shortcut.
    """
    if not xs:
        return x
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    j = bisect.bisect_right(xs, x)
    x0, x1, y0, y1 = xs[j - 1], xs[j], ys[j - 1], ys[j]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


_TH: dict | None = None


def thresholds() -> dict:
    """The ratified subscription thresholds. Read from the artefact, never hardcoded."""
    global _TH
    if _TH is not None:
        return _TH
    if not THRESHOLDS.exists():
        raise CoefficientsMissing(
            f"{THRESHOLDS} is missing. The decision is a subscription threshold (H17); "
            f"re-derive it with `python derive_subscription_thresholds.py`.")
    try:
        d = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise CoefficientsMissing(f"{THRESHOLDS} unreadable: {type(e).__name__}: {e}") from e
    for t in TARGETS:
        if t not in d.get("targets", {}) or not d["targets"][t].get("threshold_total_x"):
            raise CoefficientsMissing(f"{THRESHOLDS} has no threshold for {t}.")
    _TH = d
    return _TH


def score_one(target: str, total: float) -> dict:
    """The decision. One comparison, in subscription units (H17).

    `diagnostics` still carries the old calibrated probability for drift monitoring, and
    `_probability_diagnostics` is explicitly NOT consulted for the verdict.
    """
    th = thresholds()["targets"][target]
    cut = float(th["threshold_total_x"])
    promise = float(th["promise"])
    try:
        tot = float(total)
    except (TypeError, ValueError):
        tot = float("nan")
    if not math.isfinite(tot):
        return {"model": f"{MODEL_ID}_{target.lower()}",
                "verdict": "NO CALL — missing input: total subscription",
                "required_hit_rate": promise, "threshold_total_x": cut}

    fired = tot >= cut
    return {"model": f"{MODEL_ID}_{target.lower()}",
            "bundle": MODEL_ID,
            "verdict": "BID" if fired else "no",
            # G2: the threshold met, never a probability as a literal chance. Under H17 the
            # threshold is a subscription level, so it can be stated outright.
            "threshold_met": (f"Total {tot:.2f}x >= {cut:.2f}x, the level at which "
                              f"{promise:.0%} of unseen IPOs met this target"
                              if fired else
                              f"Total {tot:.2f}x is below {cut:.2f}x"),
            "threshold_total_x": cut,
            "required_hit_rate": promise,
            "walk_forward_delivered": th.get("walk_forward_delivered"),
            "diagnostics": _probability_diagnostics(target, tot),
            }


def _probability_diagnostics(target: str, total: float) -> dict:
    """The old calibrated probability, for drift monitoring only.

    Kept because a diverging probability is an early warning that the subscription
    threshold needs re-deriving. **Never consulted for a verdict** — `score_one` decides
    before this is called and ignores what it returns.
    """
    out = {"note": "for predictions_log.csv only — NOT in the decision path (H17)"}
    try:
        d = load(target)
    except CoefficientsMissing:
        return {**out, "raw_p": None, "calibrated_p": None,
                "why": "coefficient export absent; the decision does not need it"}
    feats = make_features(total)
    logit = float(d["intercept"])
    for f in d["features"]:
        z = (feats[f] - d["standardiser_mean"][f]) / d["standardiser_scale"][f]
        logit += d["standardised_coefficients"][f] * z
    p_raw = 1.0 / (1.0 + math.exp(-logit))
    xs, ys = d.get("isotonic_x"), d.get("isotonic_y")
    p_cal = min(1.0, max(0.0, _interp(p_raw, xs, ys))) if xs and ys else None
    return {**out, "raw_p": round(p_raw, 4),
            "calibrated_p": None if p_cal is None else round(p_cal, 4),
            "superseded_probability_verdict": (
                None if p_cal is None else
                ("BID" if p_cal >= float(d["required_hit_rate"]) else "no"))}


def demand_profile(qib: float | None, rii: float | None,
                   cutpoints: list[float] | None) -> str:
    """`institution-led` | `balanced` | `retail-skewed`, or `unknown` when a leg is missing.

    Display only. Never influences a verdict (H3).
    """
    if qib is None or rii is None or cutpoints is None:
        return "unknown"
    try:
        q, r = float(qib), float(rii)
    except (TypeError, ValueError):
        return "unknown"
    if not (math.isfinite(q) and math.isfinite(r)):
        return "unknown"
    v = math.log1p(r) - math.log1p(q)
    i = bisect.bisect_right([float(c) for c in cutpoints], v)   # numpy side="right"
    return PROFILE_LABELS[min(i, 3)]


def required() -> dict[str, float]:
    """The promised hit rates, read from the artefact rather than hardcoded twice."""
    return {t: float(thresholds()["targets"][t]["promise"]) for t in TARGETS}


def firing_levels() -> dict[str, float]:
    """`{"L1": 28.39, "L2": 54.02}` — the subscription levels the email prints."""
    return {t: float(thresholds()["targets"][t]["threshold_total_x"]) for t in TARGETS}


def predict_live(total: float, qib: float | None = None, rii: float | None = None,
                 segment: str = "mainboard") -> dict:
    """Final-day total subscription -> L1 and L2 verdicts, plus the demand-profile label.

    Signature note: unlike `model_l.predict_live` there is no `issue_size_cr` argument.
    Issue size was dropped by H11 and ratified by H12, so accepting it would imply the
    model still reads it.
    """
    out = {"model_id": MODEL_ID, "decision_point": DECISION_POINT, "segment": segment,
           "scored_by": "score_l.py (portable JSON; no modelling dependencies)",
           "inputs": {"total": total, "qib": qib, "rii": rii}}
    for t in TARGETS:
        out[t] = score_one(t, total)
    try:
        cuts = load("L1").get("profile_cutpoints")
    except CoefficientsMissing:
        cuts = None
    out["demand_profile"] = demand_profile(qib, rii, cuts)
    out["demand_profile_note"] = "display only — not a model input and never a verdict (H3)"
    if segment != "mainboard":
        out["shadow_mode"] = "SME runs in shadow mode; logged, never a bid decision"
    return out


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    """Checks the recipe is internally consistent and, where the joblib bundle can be
    loaded, that this module reproduces its verdicts exactly. The bundle check is skipped
    in the cloud, which is the whole point of this module existing."""
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("score_l.py self-test")
    print("\n[1] the exports load and describe one feature (H11)")
    for t in TARGETS:
        d = load(t)
        chk(f"{t} features == {FEATURES}", d["features"] == FEATURES, str(d["features"]))
        chk(f"{t} half_life is None (H11)", d["half_life"] is None, str(d["half_life"]))

    print("\n[2] the DECISION is a subscription threshold and nothing else (H17)")
    lv = firing_levels()
    chk("L1 fires at 28.39x", abs(lv["L1"] - 28.39) < 1e-9, str(lv))
    chk("L2 fires at 54.02x", abs(lv["L2"] - 54.02) < 1e-9, str(lv))
    for t in TARGETS:
        cut = lv[t]
        chk(f"{t}: exactly at the threshold FIRES", score_one(t, cut)["verdict"] == "BID")
        chk(f"{t}: one paisa below does NOT fire",
            score_one(t, cut - 0.01)["verdict"] == "no")
        chk(f"{t}: the verdict is monotone in Total",
            all(score_one(t, x)["verdict"] == "no" for x in (0.1, 1, 5))
            and all(score_one(t, x)["verdict"] == "BID" for x in (cut, cut * 2, 500)))
        chk(f"{t}: the threshold is STATED in the verdict text",
            f"{cut:.2f}x" in score_one(t, cut)["threshold_met"])

    print("\n[3] no probability can reach a verdict")
    import inspect
    body = inspect.getsource(score_one)
    for banned in ("p_cal", "p_raw", "isotonic", "_interp"):
        chk(f"score_one does not use {banned!r}", banned not in body)
    chk("score_one compares Total to the threshold, and that is the decision",
        "tot >= cut" in body)
    d = predict_live(120.0)["L1"]["diagnostics"]
    chk("the probability is still logged for drift monitoring", "calibrated_p" in d, str(d))
    chk("and is labelled as outside the decision path",
        "NOT in the decision path" in d.get("note", ""), str(d.get("note")))
    mid = (lv["L2"] + 98.53) / 2
    r = score_one("L2", mid)
    chk("where H17 and the old probability rule disagree, H17 wins",
        r["verdict"] == "BID"
        and r["diagnostics"].get("superseded_probability_verdict") == "no",
        f"total={mid:.2f} {r['verdict']} vs "
        f"{r['diagnostics'].get('superseded_probability_verdict')}")

    print("\n[4] demand profile is a label, and missing legs stay unknown")
    cuts = load("L1").get("profile_cutpoints")
    chk("both legs missing -> unknown", demand_profile(None, None, cuts) == "unknown")
    chk("one leg missing -> unknown", demand_profile(10.0, None, cuts) == "unknown")
    chk("no cutpoints -> unknown", demand_profile(1.0, 10.0, None) == "unknown")
    chk("retail >> QIB -> retail-skewed",
        demand_profile(0.5, 50.0, cuts) == "retail-skewed", demand_profile(0.5, 50.0, cuts))
    chk("QIB >> retail -> institution-led",
        demand_profile(50.0, 0.5, cuts) == "institution-led", demand_profile(50.0, 0.5, cuts))

    print("\n[5] no modelling dependency was imported")
    banned = {"joblib", "sklearn", "framework", "dataio", "numpy", "pandas",
              "statsmodels", "model_l"}
    here = banned & set(sys.modules)
    # pandas/numpy may already be loaded by whoever imported us; what matters is that THIS
    # module did not pull them in. Re-import in a child with a bare interpreter.
    import subprocess
    probe = ("import sys, score_l; "
             "print(','.join(m for m in " + repr(sorted(banned)) + " if m in sys.modules))")
    try:
        p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=120)
        leaked = p.stdout.strip()
        chk("importing score_l pulls in no modelling package", leaked == "",
            f"leaked: {leaked}")
    except Exception as e:                                   # noqa: BLE001
        chk("import probe ran", False, f"{type(e).__name__}: {e}")
    if here:
        print(f"  note: {sorted(here)} were already in sys.modules from the test harness")

    print("\n[6] the artefact carries its own provenance")
    th = thresholds()
    chk("it names H17 as the ratification", "H17" in th.get("ratified", ""))
    chk("it records the walk-forward definition",
        "never in-sample" in th.get("definition", ""))
    chk("it says what it supersedes",
        any("probability" in x for x in th.get("supersedes", [])))
    for t in TARGETS:
        tt = th["targets"][t]
        chk(f"{t} was calibrated to deliver its promise out of sample",
            tt.get("walk_forward_delivered") is not None
            and tt["walk_forward_delivered"] >= tt["promise"] - 1e-9,
            f"{tt.get('walk_forward_delivered')} vs {tt.get('promise')}")
        chk(f"{t} records the in-sample flattery",
            tt.get("flattery_pp") is not None and tt["flattery_pp"] > 0,
            str(tt.get("flattery_pp")))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(0)
    r = predict_live(float(sys.argv[1]))
    print(json.dumps(r, indent=2))

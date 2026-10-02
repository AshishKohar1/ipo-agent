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

MODEL_ID = "model_l_v1.0"
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
    path = COEF_DIR / f"{MODEL_ID}_{target.lower()}_coefficients.json"
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


def score_one(target: str, total: float) -> dict:
    """Steps 1–6 of the JSON's own `scoring` recipe, for one target."""
    d = load(target)
    feats = make_features(total)
    missing = [f for f in d["features"] if f not in feats or feats[f] is None
               or not math.isfinite(feats[f])]
    if missing:
        return {"model": f"{MODEL_ID}_{target.lower()}",
                "verdict": f"NO CALL — missing input: {', '.join(missing)}"}

    logit = float(d["intercept"])
    for f in d["features"]:                                  # steps 2 and 3
        z = (feats[f] - d["standardiser_mean"][f]) / d["standardiser_scale"][f]
        logit += d["standardised_coefficients"][f] * z
    p_raw = 1.0 / (1.0 + math.exp(-logit))                   # step 4

    xs, ys = d.get("isotonic_x"), d.get("isotonic_y")        # step 5
    p_cal = min(1.0, max(0.0, _interp(p_raw, xs, ys))) if xs and ys else None

    req = float(d["required_hit_rate"])
    fired = p_cal is not None and p_cal >= req               # step 6
    return {"model": f"{MODEL_ID}_{target.lower()}",
            "bundle": d.get("model_id", MODEL_ID),
            "verdict": "BID" if fired else "no",
            # G2: the THRESHOLD MET, never the probability as a literal chance.
            "threshold_met": (f"validated hit rate >= {req:.0%}" if fired
                              else f"below the {req:.0%} threshold"),
            "half_life": d.get("half_life"),
            "required_hit_rate": req,
            "diagnostics": {"raw_p": round(p_raw, 4),
                            "calibrated_p": None if p_cal is None else round(p_cal, 4),
                            "raw_equivalent_threshold": d.get("raw_equivalent_threshold"),
                            "note": "for predictions_log.csv only — never shown as a "
                                    "chance (G2)"}}


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
    """The promised hit rates, read from the exports rather than hardcoded twice."""
    return {t: float(load(t)["required_hit_rate"]) for t in TARGETS}


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
    out["demand_profile"] = demand_profile(qib, rii, load("L1").get("profile_cutpoints"))
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

    print("\n[2] monotonicity: more subscription never lowers the verdict")
    for t in TARGETS:
        ps = [score_one(t, x)["diagnostics"]["calibrated_p"] for x in
              (0.1, 0.5, 1, 2, 5, 10, 25, 50, 100, 200)]
        chk(f"{t} calibrated p is non-decreasing in Total",
            all(a <= b + 1e-12 for a, b in zip(ps, ps[1:])), str(ps))

    print("\n[3] step 6's two forms pick the same firing point")
    # Step 6 can be read two ways: isotonic (`p_cal >= required_hit_rate`) or its stated
    # shortcut (`p_raw >= raw_equivalent_threshold`). They are not bit-identical, because
    # `raw_equivalent_threshold` lands ON an isotonic knot while the step function jumps AT
    # that knot. The band of Total values where they differ must be negligible, and
    # production uses the isotonic route. This measures the band rather than assuming it.
    def _raw_p(target, total):
        d, feats = load(target), make_features(total)
        logit = float(d["intercept"]) + sum(
            d["standardised_coefficients"][f]
            * (feats[f] - d["standardiser_mean"][f]) / d["standardiser_scale"][f]
            for f in d["features"])
        return 1.0 / (1.0 + math.exp(-logit))

    def _boundary(fires):
        lo, hi = 0.0, 5000.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if fires(mid):
                hi = mid
            else:
                lo = mid
        return hi

    for t in TARGETS:
        ret = load(t).get("raw_equivalent_threshold")
        if ret is None:
            continue
        b_iso = _boundary(lambda x, t=t: score_one(t, x)["verdict"] == "BID")
        b_raw = _boundary(lambda x, t=t, r=ret: _raw_p(t, x) >= r)
        gap = abs(b_iso - b_raw) / max(b_iso, b_raw)
        chk(f"{t} the two forms fire within 1% of the same Total",
            gap < 0.01,
            f"isotonic fires at {b_iso:.3f}x, shortcut at {b_raw:.3f}x "
            f"({gap * 100:.2f}% apart)")
        print(f"        {t}: BID from Total >= {b_iso:.2f}x "
              f"(shortcut {b_raw:.2f}x, {gap * 100:.2f}% apart)")

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

    print("\n[6] agreement with the joblib bundle (laptop only)")
    try:
        sys.path.insert(0, str(ROOT / "models"))
        import model_l as ML                                 # noqa: PLC0415
        agree = True
        detail = ""
        for x in (0.3, 1.0, 2.5, 6.0, 12.0, 30.0, 80.0, 150.0):
            mine = predict_live(x)
            theirs = ML.predict_live(total=x, issue_size_cr=None)
            for t in TARGETS:
                if mine[t]["verdict"] != theirs[t]["verdict"]:
                    agree = False
                    detail = (f"Total={x}x {t}: JSON {mine[t]['verdict']} vs bundle "
                              f"{theirs[t]['verdict']}")
        chk("JSON reproduces the bundle's verdicts", agree, detail)
    except Exception as e:                                   # noqa: BLE001
        print(f"  SKIP  bundle unavailable ({type(e).__name__}: {e}) — expected in the "
              f"cloud, which is exactly why this module exists")

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

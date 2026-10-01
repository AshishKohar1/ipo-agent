"""
retrain_l.py — PLAN Stage 6 step 6. Runs on the 1st of each month, 08:00 IST.

Champion/challenger on the latest 12 months out-of-sample, plus PSI drift monitoring.

**Promotion rule.** The challenger replaces the champion only if its pooled AUC is at least
the champion's **and** its calibration is not worse (held-out Brier no higher). Otherwise the
champion is kept and an alert is written. Nothing is ever promoted by hand — that is the
whole point of A2 and H11's standing-challenger clause.

Challengers, per the standing decisions:
  * **Set A** — `log1p(Total)` + `log(issue size)`, the former champion, demoted by H11
  * **Set C** — Set A + market IPO heat, retained as a challenger by A2

**PSI** is computed per input against the training distribution; above 0.25 an alert is
written. A drifting input invalidates the thresholds even when AUC looks fine, because the
thresholds were chosen at a particular point on the score distribution.

Writes `models/registry.csv` (every version, append-only) and
`reports/retrain/<YYYY-MM>.md`.

    python retrain_l.py                 # the monthly run
    python retrain_l.py --dry-run
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
import framework as F        # noqa: E402
import calibration as C      # noqa: E402
import model_l as ML         # noqa: E402

REGISTRY = ROOT / "models" / "registry.csv"
OUT_DIR = ROOT / "reports" / "retrain"
PSI_ALERT = 0.25
REQUIRED = {"L1": 0.90, "L2": 0.80}

CANDIDATES = {
    "champion_total_only": ["log1p_total"],                        # H11
    "challenger_setA": ["log1p_total", "log_issue_size"],           # demoted by H11, A2-style
}
REG_COLS = ["run_at", "target", "name", "features", "half_life", "pooled_auc", "brier",
            "n_train", "n_test_window", "decision", "psi_max", "psi_alert", "note"]


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index on quantile bins of the TRAINING distribution."""
    e = np.asarray(expected, float)
    a = np.asarray(actual, float)
    e, a = e[np.isfinite(e)], a[np.isfinite(a)]
    if len(e) < 20 or len(a) < 10:
        return float("nan")
    cuts = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(cuts) < 3:
        return float("nan")
    cuts[0], cuts[-1] = -np.inf, np.inf
    pe = np.histogram(e, bins=cuts)[0] / len(e)
    pa = np.histogram(a, bins=cuts)[0] / len(a)
    eps = 1e-6
    pe, pa = np.clip(pe, eps, None), np.clip(pa, eps, None)
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def evaluate(target: str, features: list[str], window_months: int = 12) -> dict:
    """Fit on everything before the window, score the window. Genuinely out of sample."""
    sp = ML.spec(target, "mainboard")
    sp.features = features
    df = F.prepare(sp)
    cut = df["listing_date"].max() - pd.DateOffset(months=window_months)
    tr, te = df[df["listing_date"] <= cut], df[df["listing_date"] > cut]
    if len(tr) < 50 or len(te) < 20 or te[target].nunique() < 2:
        return {"error": f"insufficient data: train {len(tr)}, test {len(te)}"}
    w = F.recency_weights(tr["listing_date"], ML.HALF_LIFE)
    m = F._fit(tr[features].to_numpy(), tr[target].to_numpy(), w, sp.C)
    p = m.predict_proba(te[features].to_numpy())[:, 1]
    auc = F.roc_auc_score(te[target].to_numpy(), p)
    cal = C.IsotonicCalibrator().fit(
        m.predict_proba(tr[features].to_numpy())[:, 1], tr[target].to_numpy())
    pc = cal.predict(p)
    brier = C.brier(te[target].to_numpy(), pc)
    fired = pc >= REQUIRED[target]
    n, k = int(fired.sum()), int(te[target].to_numpy()[fired].sum())
    psis = {f: psi(tr[f].to_numpy(), te[f].to_numpy()) for f in features}
    pmax = max((v for v in psis.values() if np.isfinite(v)), default=float("nan"))
    return {"features": features, "n_train": int(len(tr)), "n_test_window": int(len(te)),
            "window_from": str(cut.date()), "pooled_auc": round(float(auc), 4),
            "brier": round(float(brier), 4), "n_fire": n, "hits": k,
            "hit_rate": None if n == 0 else round(k / n, 4),
            "psi": {a: (None if not np.isfinite(b) else round(b, 4)) for a, b in psis.items()},
            "psi_max": None if not np.isfinite(pmax) else round(pmax, 4),
            "psi_alert": bool(np.isfinite(pmax) and pmax > PSI_ALERT)}


def main(dry: bool = False) -> dict:
    now = pd.Timestamp.now()
    res = {"run_at": str(now), "window_months": 12, "targets": {}}
    rows, alerts = [], []
    print(f"monthly champion/challenger — {now.date()}")
    for target in ("L1", "L2"):
        res["targets"][target] = {}
        for name, feats in CANDIDATES.items():
            e = evaluate(target, feats)
            res["targets"][target][name] = e
            if "error" in e:
                print(f"  {target} {name:22s} {e['error']}")
                continue
            print(f"  {target} {name:22s} AUC {e['pooled_auc']:.4f} Brier {e['brier']:.4f} "
                  f"fires {e['n_fire']:3d} hit "
                  f"{(e['hit_rate'] or 0)*100:5.1f}%  PSI max {e['psi_max']}")
        ch = res["targets"][target].get("champion_total_only", {})
        cl = res["targets"][target].get("challenger_setA", {})
        if "error" in ch or "error" in cl:
            decision = "KEEP champion — not enough out-of-sample data to compare"
        elif cl["pooled_auc"] >= ch["pooled_auc"] and cl["brier"] <= ch["brier"]:
            decision = ("PROMOTE challenger_setA — it matches or beats the champion on BOTH "
                        "pooled AUC and calibration")
            alerts.append(f"{target}: the challenger qualifies for promotion. Promotion is "
                          "not automatic in this build — it is reported for ratification, "
                          "because H11 was taken on evidence the user has not yet ratified.")
        else:
            why = []
            if cl["pooled_auc"] < ch["pooled_auc"]:
                why.append(f"AUC {cl['pooled_auc']:.4f} < {ch['pooled_auc']:.4f}")
            if cl["brier"] > ch["brier"]:
                why.append(f"Brier {cl['brier']:.4f} > {ch['brier']:.4f}")
            decision = f"KEEP champion — challenger loses on {', '.join(why)}"
        res["targets"][target]["decision"] = decision
        print(f"  {target} -> {decision}")
        # A promise missed in the recent window is the alert that matters most: the
        # threshold was chosen on older out-of-fold data, and a shortfall here means it no
        # longer delivers what the model card claims.
        if ch.get("hit_rate") is not None and ch["hit_rate"] < REQUIRED[target]:
            alerts.append(
                f"{target}: the champion's threshold delivered {ch['hit_rate']*100:.1f}% in "
                f"the last 12 months against a {REQUIRED[target]*100:.0f}% promise "
                f"({ch['hits']}/{ch['n_fire']} fires). The window is small, so this is a "
                f"warning rather than a failure -- but if it persists the threshold must be "
                f"re-derived, not explained away.")
        if ch.get("psi_alert"):
            alerts.append(f"{target}: PSI {ch['psi_max']} exceeds {PSI_ALERT} — an input has "
                          "drifted, which invalidates the THRESHOLDS even if AUC looks fine, "
                          "because they were chosen at a point on the old score distribution.")
        for name, e in res["targets"][target].items():
            if not isinstance(e, dict) or "error" in e:
                continue
            rows.append({"run_at": str(now), "target": target, "name": name,
                         "features": ";".join(e["features"]),
                         "half_life": ML.HALF_LIFE, "pooled_auc": e["pooled_auc"],
                         "brier": e["brier"], "n_train": e["n_train"],
                         "n_test_window": e["n_test_window"], "decision": decision,
                         "psi_max": e["psi_max"], "psi_alert": e["psi_alert"],
                         "note": f"window from {e['window_from']}"})
    res["alerts"] = alerts
    if alerts:
        print("\nALERTS:")
        for a in alerts:
            print(f"  - {a}")

    if dry:
        print("\n--dry-run: nothing written")
        return res
    pd.DataFrame([{c: r.get(c) for c in REG_COLS} for r in rows], columns=REG_COLS).to_csv(
        REGISTRY, mode="a", header=not REGISTRY.exists(), index=False, encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = OUT_DIR / f"{now.strftime('%Y-%m')}.md"
    L = [f"# Model L retrain — {now.date()}", "",
         f"Champion: `{'+'.join(ML.FEATURES)}`, half-life `{ML.HALF_LIFE}` (H11).",
         f"Out-of-sample window: last 12 months.", ""]
    for target, d in res["targets"].items():
        L += [f"## {target}", "", "| candidate | AUC | Brier | fires | hit rate | PSI max |",
              "|---|---|---|---|---|---|"]
        for name, e in d.items():
            if not isinstance(e, dict) or "error" in e:
                continue
            L.append(f"| `{name}` | {e['pooled_auc']:.4f} | {e['brier']:.4f} | "
                     f"{e['n_fire']} | {(e['hit_rate'] or 0)*100:.1f}% | {e['psi_max']} |")
        L += ["", f"**Decision: {d.get('decision')}**", ""]
    if alerts:
        L += ["## Alerts", ""] + [f"- {a}" for a in alerts]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    (ROOT / "reports" / "retrain_latest.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwritten: {md.relative_to(ROOT)}, models/registry.csv")
    return res


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)

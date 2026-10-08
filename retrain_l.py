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
        # NOTE: this measures the RETIRED calibrated-probability cut-off, which H17
        # removed from the decision path. It is kept as a drift monitor -- a diverging
        # probability is an early warning that the subscription threshold needs
        # re-deriving -- but it is no longer a promise the system makes, and the alert says
        # so explicitly. Reporting it as a live shortfall is exactly how H16 was produced.
        if ch.get("hit_rate") is not None and ch["hit_rate"] < REQUIRED[target]:
            alerts.append(
                f"{target}: MONITORING ONLY (not the live rule) -- the retired probability "
                f"cut-off would have delivered {ch['hit_rate']*100:.1f}% in the last 12 "
                f"months against a {REQUIRED[target]*100:.0f}% promise "
                f"({ch['hits']}/{ch['n_fire']} fires). Since H17 the decision is a "
                f"subscription threshold, so this is drift evidence rather than a failure. "
                f"The live rule's own delivery is in the threshold table above.")
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
    # ------------------------------------------------- 1c: re-derive the H17 thresholds
    # The decision is a subscription threshold now, so the thing that must be re-derived
    # monthly is the threshold itself, by the SAME walk-forward method that produced it --
    # not the probability model's AUC. The candidate comparison above is kept because it
    # still monitors the feature set; this block monitors the number that actually decides.
    res["thresholds"] = {}
    try:
        import derive_subscription_thresholds as DT
        cur = DT.current_production().get("targets", {})
        for target in ("L1", "L2"):
            a = DT.analyse(target)
            sh = a.get("shipped") or {}
            new_t = sh.get("threshold")
            old_t = (cur.get(target) or {}).get("threshold_total_x")
            if new_t is None:
                res["thresholds"][target] = {
                    "error": "no threshold qualified on current data"}
                alerts.append(f"{target}: NO subscription threshold qualifies on current "
                              f"data under the C5 gates. The shipped level is unchanged and "
                              f"this needs review.")
                continue
            g = DT.drift_check(new_t, old_t)
            res["thresholds"][target] = {
                "shipped_total_x": old_t, "re_derived_total_x": round(new_t, 2),
                "moved_pct": g["moved_pct"], "apply": g["apply"], "reason": g["reason"],
                "internal_target": a["calibration"]["chosen_internal_target"],
                "walk_forward_delivered": (a["walk_forward_calibrated"] or {}).get("pooled_hit_rate"),
                "walk_forward_fires": (a["walk_forward_calibrated"] or {}).get("n_fire"),
                "in_sample_delivered": a["in_sample"]["hit_rate"],
            }
            print(f"  {target} threshold: shipped {old_t}x -> re-derived {new_t:.2f}x "
                  f"({g['moved_pct']}%) {'APPLY' if g['apply'] else 'HOLD FOR REVIEW'}")
            if not g["apply"]:
                alerts.append(f"{target}: THRESHOLD DRIFT HELD FOR REVIEW. {g['reason']} "
                              f"Nothing was changed. The re-derived level would be "
                              f"{new_t:.2f}x against the shipped {old_t}x.")
            wf = (a["walk_forward_calibrated"] or {}).get("pooled_hit_rate")
            if wf is not None and wf < REQUIRED[target] - 1e-9:
                alerts.append(f"{target}: even after calibration the re-derived threshold "
                              f"delivers only {wf*100:.1f}% out of sample against a "
                              f"{REQUIRED[target]*100:.0f}% promise.")
    except Exception as e:                                  # noqa: BLE001
        res["thresholds"]["error"] = f"{type(e).__name__}: {e}"
        alerts.append(f"the H17 threshold re-derivation did not run: {type(e).__name__}: {e}")

    # H19, the two-window tripwire. Measured by the EMAIL backtest, not by a separate
    # reimplementation, so what is tripwired is what the email actually said. One
    # under-delivering window is recorded and deliberately NOT acted on; two consecutive
    # on the same target authorises re-deriving that threshold (and only re-deriving -
    # the 25% drift guard still holds a large move for review).
    try:
        import tripwire as TW
        res["tripwire"] = TW.evaluate(12)
        for target in ("L1", "L2"):
            m = res["tripwire"]["targets"][target].get("alert")
            if m:
                alerts.append(m)
    except Exception as e:                                  # noqa: BLE001
        res["tripwire"] = {"error": f"{type(e).__name__}: {e}"}
        alerts.append(f"the H19 tripwire did not run: {type(e).__name__}: {e}. The count "
                      f"is NOT advanced, so a window has been missed rather than passed.")

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
    if res.get("thresholds"):
        L += ["## Ratified thresholds (H17) — re-derived walk-forward", "",
              "| target | shipped | re-derived | moved | out-of-sample delivery | action |",
              "|---|---|---|---|---|---|"]
        for t, d in res["thresholds"].items():
            if not isinstance(d, dict) or "error" in d:
                L.append(f"| {t} | — | — | — | — | {d if not isinstance(d, dict) else d.get('error')} |")
                continue
            wf = d.get("walk_forward_delivered")
            if wf is None:
                delivery = "—"
            else:
                delivery = f"{wf * 100:.1f}% on {d.get('walk_forward_fires')} fires"
            action = "apply" if d.get("apply") else "**HOLD FOR REVIEW**"
            L.append(f"| {t} | {d.get('shipped_total_x')}x "
                     f"| {d.get('re_derived_total_x')}x | {d.get('moved_pct')}% "
                     f"| {delivery} | {action} |")
        L += ["", "A move beyond 25% is held rather than applied: the naive L2 threshold "
                  "drifted 31.11x to 17.20x chasing the hot 2021-24 market and 2025 then "
                  "delivered 60%. A threshold that chases recent conditions is not learning.",
              ""]
    tw = res.get("tripwire") or {}
    if tw and "error" not in tw:
        L += ["## H19 tripwire - trailing 12 months", "",
              "| target | delivered | promise | bids | counts? | consecutive | fired |",
              "|---|---|---|---|---|---|---|"]
        for t in ("L1", "L2"):
            r = tw["targets"][t]
            o = [x for x in __import__("tripwire")._load()["targets"][t]["observations"]
                 if x["window"] == r["window"]]
            dv = (o[0]["delivered"] if o and o[0]["delivered"] is not None else None)
            pr = (o[0]["promise"] if o else None)
            nb = (o[0]["n_bids"] if o else None)
            L.append(f"| {t} | {'-' if dv is None else f'{dv*100:.1f}%'} "
                     f"| {'-' if pr is None else f'{pr*100:.0f}%'} | {nb} "
                     f"| {'yes' if r['counts'] else 'no'} "
                     f"| {r['consecutive_under']} of {r['trigger_at']} "
                     f"| {'**YES - RE-DERIVE**' if r['fired'] else 'no'} |")
        L += ["", "Two consecutive under-delivering windows is the trigger; one is not "
                  "(H19). Firing authorises re-deriving the threshold, not applying the "
                  "result.", ""]
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

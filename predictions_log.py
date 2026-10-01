"""
predictions_log.py — the append-only prediction ledger (PLAN Stage 6 step 4).

Every live score writes one row and **nothing ever rewrites one**. That is the point: the
model's own claims have to be auditable against what happened, and a log that can be edited
after the fact proves nothing. Outcomes are filled in by `ingest_outcomes.py`, which appends
a *separate* `outcome` row keyed to the prediction's `prediction_id` rather than editing the
prediction.

Columns are fixed. A new field is added at the end, never inserted, so a file written by an
older version still parses.

    from predictions_log import log_prediction, log_outcome, load
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "predictions_log.csv"

COLS = [
    "row_type",              # prediction | outcome
    "prediction_id",         # sha1 of ipo|isin|capture_point|date — links the two row types
    "logged_at_ist",
    "ipo", "isin", "segment",
    "model_id", "decision_point", "model_version_sha",
    # inputs, exactly as scored
    "total_x", "qib_x", "hni_x", "rii_x", "issue_size_cr",
    "capture_point",         # 1500 | 1730 — which snapshot was scored
    "subscription_source",
    # outputs, per G2: the verdict and the threshold met
    "l1_verdict", "l1_threshold_met", "l2_verdict", "l2_threshold_met",
    "demand_profile",
    # diagnostics, for measuring calibration later. NEVER shown as a chance (G2).
    "l1_p_raw", "l1_p_cal", "l2_p_raw", "l2_p_cal",
    "veto_flags", "gmp_user_supplied",
    # outcome rows only
    "listing_date", "listing_gain_pct", "l1_actual", "l2_actual", "outcome_note",
]


def prediction_id(ipo: str, isin: str | None, capture_point, when) -> str:
    key = f"{ipo}|{isin or ''}|{capture_point}|{pd.Timestamp(when).date()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _append(row: dict) -> None:
    df = pd.DataFrame([{c: row.get(c) for c in COLS}], columns=COLS)
    df.to_csv(LOG, mode="a", header=not LOG.exists(), index=False, encoding="utf-8")


def log_prediction(ipo: str, isin: str | None, result: dict, capture_point: int = 1500,
                   source: str = "", veto_flags: str = "", gmp: str = "") -> str:
    """Append one prediction row. Returns its `prediction_id`."""
    now = pd.Timestamp.now()
    pid = prediction_id(ipo, isin, capture_point, now)
    i = result.get("inputs", {})
    d1, d2 = result["L1"].get("diagnostics", {}), result["L2"].get("diagnostics", {})
    _append({
        "row_type": "prediction", "prediction_id": pid, "logged_at_ist": str(now),
        "ipo": ipo, "isin": isin, "segment": result.get("segment"),
        "model_id": result.get("model_id"), "decision_point": result.get("decision_point"),
        "model_version_sha": result.get("model_version_sha"),
        "total_x": i.get("total"), "qib_x": i.get("qib"), "hni_x": i.get("hni"),
        "rii_x": i.get("rii"), "issue_size_cr": i.get("issue_size_cr"),
        "capture_point": capture_point, "subscription_source": source,
        "l1_verdict": result["L1"].get("verdict"),
        "l1_threshold_met": result["L1"].get("threshold_met"),
        "l2_verdict": result["L2"].get("verdict"),
        "l2_threshold_met": result["L2"].get("threshold_met"),
        "demand_profile": result.get("demand_profile"),
        "l1_p_raw": d1.get("raw_p"), "l1_p_cal": d1.get("calibrated_p"),
        "l2_p_raw": d2.get("raw_p"), "l2_p_cal": d2.get("calibrated_p"),
        "veto_flags": veto_flags, "gmp_user_supplied": gmp,
    })
    return pid


def log_outcome(prediction_id: str, ipo: str, listing_date, listing_gain_pct: float | None,
                note: str = "") -> None:
    """Append a SEPARATE outcome row. The prediction row is never touched."""
    g = listing_gain_pct
    _append({
        "row_type": "outcome", "prediction_id": prediction_id,
        "logged_at_ist": str(pd.Timestamp.now()), "ipo": ipo,
        "listing_date": str(listing_date) if listing_date is not None else None,
        "listing_gain_pct": g,
        "l1_actual": None if g is None else int(g > 0),
        "l2_actual": None if g is None else int(g > 10),
        "outcome_note": note,
    })


def load() -> pd.DataFrame:
    if not LOG.exists():
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(LOG, keep_default_na=False, na_values=[""])


def scored() -> pd.DataFrame:
    """Predictions joined to their outcomes, for measuring the delivered hit rate."""
    df = load()
    p = df[df["row_type"] == "prediction"]
    o = df[df["row_type"] == "outcome"][["prediction_id", "listing_gain_pct",
                                         "l1_actual", "l2_actual"]]
    return p.merge(o, on="prediction_id", how="left", suffixes=("", "_out"))


def verify_append_only() -> dict:
    """A cheap integrity check: the file's own row count against distinct prediction ids.

    It cannot prove nothing was edited — only a hash chain or an external store could — so
    this reports what it can and says what it cannot. It is here to catch accidents (a
    spreadsheet resaving the file), not tampering.
    """
    df = load()
    return {"rows": len(df),
            "predictions": int((df["row_type"] == "prediction").sum()),
            "outcomes": int((df["row_type"] == "outcome").sum()),
            "duplicate_prediction_ids": int(
                df[df["row_type"] == "prediction"]["prediction_id"].duplicated().sum()),
            "orphan_outcomes": int(
                (~df[df["row_type"] == "outcome"]["prediction_id"].isin(
                    df[df["row_type"] == "prediction"]["prediction_id"])).sum()),
            "caveat": "row counts only; this does not detect an edited row"}


if __name__ == "__main__":
    import json
    print(json.dumps(verify_append_only(), indent=2))

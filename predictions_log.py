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
import csv
import pandas as pd

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "data" / "predictions_log.csv"

COLS = [
    "row_type",              # prediction | outcome
    "prediction_id",         # sha1 of ipo|isin|capture_point|date — links the two row types
    "logged_at_ist",
    "ipo", "isin", "segment",
    "model_id", "decision_point", "model_version_sha",
    # inputs, exactly as scored
    "total_x", "qib_x", "hni_x", "rii_x", "issue_size_cr",
    "capture_point",         # 1500 | 1930 — which snapshot was scored
    "subscription_source",
    # outputs, per G2: the verdict and the threshold met
    "l1_verdict", "l1_threshold_met", "l2_verdict", "l2_threshold_met",
    "demand_profile",
    # diagnostics, for measuring calibration later. NEVER shown as a chance (G2).
    "l1_p_raw", "l1_p_cal", "l2_p_raw", "l2_p_cal",
    "veto_flags", "gmp_user_supplied",
    # outcome rows only
    "listing_date", "listing_gain_pct", "l1_actual", "l2_actual", "outcome_note",
    # Task 6: the 15:00 figures the DECISION was taken on, named for the capture point so
    # they can never be confused with the final figures. `total_x` above is whatever was
    # scored at whatever capture point; these four are specifically the 15:00 reading, and
    # they are written at send so the row records what the user was actually told.
    "sub_total_1500", "sub_qib_1500", "sub_hni_1500", "sub_rii_1500",
]

# Task 6: final subscription lands in its OWN file, keyed to the prediction, because rule
# 10 makes the prediction row immutable. Rewriting `total_x` with the final figure would
# destroy the only record of what the decision was actually taken on - which is the one
# number the whole backtest depends on.
FINALS = ROOT / "data" / "final_subscription.csv"
FINAL_COLS = ["prediction_id", "ipo", "isin", "date", "captured_at_ist", "capture_point",
              "sub_total_1500", "sub_total_final", "growth_x", "growth_pct",
              "sub_qib_final", "sub_hni_final", "sub_rii_final",
              "l1_threshold_total_x", "l2_threshold_total_x",
              "would_L1_fire_on_final", "would_L2_fire_on_final",
              "L1_fired_at_1500", "L2_fired_at_1500",
              "verdict_would_have_changed", "source", "note"]


def prediction_id(ipo: str, isin: str | None, capture_point, when) -> str:
    key = f"{ipo}|{isin or ''}|{capture_point}|{pd.Timestamp(when).date()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def header_on_disk() -> list[str]:
    """The column names the file actually starts with, or `[]` if there is no file."""
    if not LOG.exists():
        return []
    with LOG.open("r", encoding="utf-8", newline="") as f:
        line = f.readline()
    return next(csv.reader([line.rstrip("\r\n")])) if line else []


class SchemaMismatch(RuntimeError):
    """The file's header and `COLS` disagree, so a row would be written misaligned."""


def check_header(where: str = "") -> None:
    """Fail LOUDLY if the file header and COLS differ.

    Why this exists: four columns (`sub_*_1500`) were added to COLS and the file on disk
    was never migrated, so it carried a 32-column header above a 36-column row. Nothing
    complained. `pandas.read_csv` took the first line as the names and the wider row was
    then read with its last four values under no name at all - a silent misalignment in
    the only record of what the live model actually decided.

    An append is the dangerous direction: `to_csv(mode="a")` writes no header when the
    file exists, so a widened COLS appends wider rows under the old header indefinitely.
    This is therefore checked on every append AND every read, and in the pre-flight gate.
    """
    if not LOG.exists():
        return
    have = header_on_disk()
    if have == list(COLS):
        return
    missing = [c for c in COLS if c not in have]
    extra = [c for c in have if c not in COLS]
    raise SchemaMismatch(
        f"predictions_log.csv header has {len(have)} columns, COLS has {len(COLS)}"
        f"{' (' + where + ')' if where else ''}. "
        f"missing from the file: {missing or 'none'}; "
        f"on the file but not in COLS: {extra or 'none'}. "
        f"Run `python predictions_log.py --repair-header` if the new columns are appended "
        f"at the END and every existing row is therefore still correctly aligned; "
        f"otherwise the rows need migrating, not the header.")


def repair_header() -> dict:
    """Rewrite the HEADER LINE ONLY to the current `COLS`. Data rows are not touched.

    This is a header correction, not a data edit, and that distinction is the whole point
    (H39): the four new columns are appended at the END of COLS, so every existing 32-field
    row is still correctly aligned under the first 32 names and simply reads the four new
    ones as blank. No value changes meaning.

    It proves that rather than asserting it: every data row's bytes are hashed before and
    after, and the function refuses to write if any hash moves. It also refuses outright if
    the file's existing names are not a PREFIX of COLS, because then the columns were
    reordered or renamed and rewriting the header would silently relabel real data.
    """
    import hashlib
    raw = LOG.read_bytes()
    cut = raw.index(b"\n")
    old_head, body = raw[:cut], raw[cut + 1:]
    eol = b"\r\n" if old_head.endswith(b"\r") else b"\n"
    have = next(csv.reader([old_head.decode("utf-8").rstrip("\r\n")]))
    if have == list(COLS):
        return {"changed": False, "why": "the header already matches COLS"}
    if have != list(COLS)[:len(have)]:
        raise SchemaMismatch(
            f"refusing to rewrite the header: the names on disk are not a prefix of COLS, "
            f"so columns were reordered or renamed and the DATA needs migrating. "
            f"on disk: {have}")
    before = [hashlib.sha256(ln).hexdigest() for ln in body.split(b"\n") if ln.strip()]
    new_head = ",".join(COLS).encode("utf-8")
    LOG.write_bytes(new_head + eol + body)
    after_body = LOG.read_bytes()[len(new_head) + len(eol):]
    after = [hashlib.sha256(ln).hexdigest() for ln in after_body.split(b"\n")
             if ln.strip()]
    if before != after:
        LOG.write_bytes(raw)
        raise SchemaMismatch("a data row changed during the header repair; reverted")
    return {"changed": True, "old_columns": len(have), "new_columns": len(COLS),
            "added": [c for c in COLS if c not in have],
            "data_rows": len(before), "row_hashes_identical": before == after,
            "body_sha256": hashlib.sha256(body).hexdigest()}


def _append(row: dict) -> None:
    check_header("before appending")
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
        # Task 6. Only populated when this IS the 15:00 capture: labelling a 19:30 reading
        # as a 1500 figure would be worse than leaving it blank.
        "sub_total_1500": i.get("total") if capture_point == 1500 else None,
        "sub_qib_1500": i.get("qib") if capture_point == 1500 else None,
        "sub_hni_1500": i.get("hni") if capture_point == 1500 else None,
        "sub_rii_1500": i.get("rii") if capture_point == 1500 else None,
    })
    return pid


def predictions_for(date, capture_point: int = 1500) -> dict:
    """`{ipo: row}` for the prediction rows logged on `date` at `capture_point`.

    Used by the day-end leg to find the 15:00 prediction a final figure belongs to. Keyed
    on the IPO name as logged, so a renamed company is a miss rather than a wrong match.
    """
    if not LOG.exists():
        return {}
    try:
        d = pd.read_csv(LOG)
    except Exception:                                        # noqa: BLE001
        return {}
    if d.empty or "row_type" not in d:
        return {}
    d = d[(d["row_type"] == "prediction")
          & (pd.to_numeric(d["capture_point"], errors="coerce") == capture_point)]
    day = str(pd.Timestamp(date).date())
    d = d[pd.to_datetime(d["logged_at_ist"], errors="coerce").dt.date.astype(str) == day]
    return {str(r["ipo"]): r.to_dict() for _, r in d.iterrows()}


def log_final_subscription(prediction_id: str, ipo: str, isin: str | None, date,
                           final: dict, at_1500: dict, levels: dict,
                           source: str = "", note: str = "",
                           when=None, capture_point: int = 1930) -> dict:
    """Task 6. Append the FINAL subscription beside the 15:00 figure the decision used.

    Appends to `data/final_subscription.csv`. **The prediction row is never touched**
    (rule 11) - this is a second record keyed to `prediction_id`, exactly like an outcome
    row.

    `would_L*_fire_on_final` is the counterfactual the whole 3pm-understatement question
    turns on: the same ratified threshold, applied to the final figure instead of the
    15:00 one. If it fires on final but not at 15:00, the email was conservative and the
    user missed a qualifying IPO - and that is now a counted quantity rather than a caveat.
    """
    when = pd.Timestamp(when) if when is not None else pd.Timestamp.now()
    t15 = _f(at_1500.get("total"))
    tf = _f(final.get("total"))
    l1c, l2c = _f(levels.get("L1")), _f(levels.get("L2"))
    f1 = None if (tf is None or l1c is None) else bool(tf >= l1c)
    f2 = None if (tf is None or l2c is None) else bool(tf >= l2c)
    s1 = None if (t15 is None or l1c is None) else bool(t15 >= l1c)
    s2 = None if (t15 is None or l2c is None) else bool(t15 >= l2c)
    row = {
        "prediction_id": prediction_id, "ipo": ipo, "isin": isin,
        "date": str(pd.Timestamp(date).date()), "captured_at_ist": str(when),
        "capture_point": capture_point,
        "sub_total_1500": t15, "sub_total_final": tf,
        "growth_x": None if (t15 is None or tf is None or t15 <= 0) else round(tf / t15, 4),
        "growth_pct": None if (t15 is None or tf is None or t15 <= 0)
        else round(100 * (tf / t15 - 1), 2),
        "sub_qib_final": _f(final.get("qib")), "sub_hni_final": _f(final.get("hni")),
        "sub_rii_final": _f(final.get("rii")),
        "l1_threshold_total_x": l1c, "l2_threshold_total_x": l2c,
        "would_L1_fire_on_final": f1, "would_L2_fire_on_final": f2,
        "L1_fired_at_1500": s1, "L2_fired_at_1500": s2,
        "verdict_would_have_changed": None if (f1 is None or s1 is None or f2 is None
                                               or s2 is None) else bool(f1 != s1 or f2 != s2),
        "source": source, "note": note,
    }
    FINALS.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{c: row.get(c) for c in FINAL_COLS}], columns=FINAL_COLS).to_csv(
        FINALS, mode="a", header=not FINALS.exists(), index=False, encoding="utf-8")
    return row


def _f(v):
    """Numeric or None. Never a string that looks like a number in a numeric column."""
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(x) else x


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
    check_header("on load")
    return pd.read_csv(LOG, keep_default_na=False, na_values=[""])


def scored() -> pd.DataFrame:
    """Predictions joined to their outcomes, for measuring the delivered hit rate."""
    df = load()
    p = df[df["row_type"] == "prediction"]
    o = df[df["row_type"] == "outcome"].copy()
    # The NEWEST outcome row per prediction wins. This file is append-only (rule 11), so
    # a correction is a new row rather than an edit - and a prediction with two outcome
    # rows must not become two rows here, which would double-count it in the delivered
    # hit rate. HD Fire Protect is the case: its 21 Oct outcome carried a NULL gain
    # because the offer price was missing, and the corrected row came later.
    if len(o):
        o["_t"] = pd.to_datetime(o["logged_at_ist"], errors="coerce")
        o = o.sort_values("_t").drop_duplicates(subset=["prediction_id"], keep="last")
    o = o[["prediction_id", "listing_gain_pct", "l1_actual", "l2_actual"]]
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
    import argparse
    import json
    ap = argparse.ArgumentParser(description="predictions_log maintenance")
    ap.add_argument("--repair-header", action="store_true",
                    help="rewrite the HEADER LINE ONLY to the current COLS. Refuses if "
                         "the names on disk are not a prefix of COLS, and reverts if any "
                         "data row's bytes change.")
    ap.add_argument("--check-header", action="store_true",
                    help="fail if the file header and COLS disagree")
    a = ap.parse_args()
    if a.repair_header:
        print(json.dumps(repair_header(), indent=2))
    elif a.check_header:
        check_header("cli")
        print(f"ok: {len(header_on_disk())} columns, matching COLS")
    else:
        print(json.dumps(verify_append_only(), indent=2))

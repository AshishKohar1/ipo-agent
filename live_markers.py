"""
live_markers.py — idempotency markers for the scheduled live jobs (Priority 1f).

One implementation, shared by `send_daily_email.py` and `run_live_l.py`. It used to live
inside `run_live_l.py`, which meant the two legs of the same day could not see each other's
markers.

The bug this module fixes
-------------------------
`mark_ran()` wrote a marker even when the run captured **zero** rows, and `already_ran()`
only checked that the key existed. So a run that failed — exchange block, network error,
missing dependency — recorded itself as done and **locked out every retry for that slot**.
Three slots were stuck this way: `2026-10-01|1730`, `2026-10-02|1730`, `2026-10-02|1500`.
Each of those was a *failure* being remembered as a *success*.

The rule now: a marker only counts as "ran" if it captured at least one row. A marker with
`n_snapshots == 0` is a record that an attempt was made and produced nothing, which is
useful history but is **not** a reason to refuse a retry. Idempotency must suppress
duplicate *work*, never duplicate *attempts at work that has not happened*.

Markers are still append-only: the zero rows stay in the file as the audit trail of the
failed attempts.

    python live_markers.py                  # show the marker table and what it permits
    python live_markers.py --self-test
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
MARKERS = ROOT / "data" / "live_run_markers.csv"
COLS = ["key", "date", "capture_point", "ran_at", "n_snapshots"]


def _read(path: Path | None = None) -> pd.DataFrame:
    path = path or MARKERS
    if not path.exists():
        return pd.DataFrame(columns=COLS)
    try:
        m = pd.read_csv(path)
    except Exception:                                   # noqa: BLE001
        return pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in m.columns:
            m[c] = None
    return m


def key(capture_point: int, when) -> str:
    return f"{pd.Timestamp(when).date()}|{capture_point}"


def already_ran(capture_point: int, when, path: Path | None = None) -> bool:
    """True only if this slot has already done real work.

    GitHub's scheduler drifts and may retry, a manual dispatch can land on top of a
    scheduled run, and a failed job can be re-run — so a second *successful* run for the
    same date and capture point must be a no-op rather than a duplicate prediction row.

    But a previous attempt that captured nothing is not success. It returns False here, so
    the retry is allowed to proceed.
    """
    m = _read(path)
    if m.empty:
        return False
    hit = m[m["key"].astype(str) == key(capture_point, when)]
    if hit.empty:
        return False
    n = pd.to_numeric(hit["n_snapshots"], errors="coerce").fillna(0)
    return bool((n > 0).any())


def attempts(capture_point: int, when, path: Path | None = None) -> int:
    """How many times this slot has been attempted, successfully or not."""
    m = _read(path)
    if m.empty:
        return 0
    return int((m["key"].astype(str) == key(capture_point, when)).sum())


def mark_ran(capture_point: int, when, n: int, path: Path | None = None) -> None:
    """Record an attempt and what it captured. `n == 0` is recorded but does not lock."""
    path = path or MARKERS
    row = pd.DataFrame([{"key": key(capture_point, when), "date": str(pd.Timestamp(when).date()),
                         "capture_point": capture_point, "ran_at": str(when),
                         "n_snapshots": int(n)}], columns=COLS)
    path.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8")


def stuck(path: Path | None = None) -> pd.DataFrame:
    """Slots whose only markers captured nothing — i.e. the ones the old code locked out."""
    m = _read(path)
    if m.empty:
        return m
    m["n"] = pd.to_numeric(m["n_snapshots"], errors="coerce").fillna(0)
    g = m.groupby("key")["n"].max()
    return m[m["key"].isin(g[g <= 0].index)][COLS]


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    import tempfile
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("live_markers.py self-test")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.csv"
        when = pd.Timestamp("2026-10-05 15:00")

        chk("no file -> not yet run", already_ran(1500, when, p) is False)

        mark_ran(1500, when, 0, p)
        chk("a zero-row attempt does NOT lock the slot (the Priority 1f bug)",
            already_ran(1500, when, p) is False)
        chk("but the attempt is recorded", attempts(1500, when, p) == 1)
        chk("and the slot shows as stuck", len(stuck(p)) == 1)

        mark_ran(1500, when, 0, p)
        chk("a second failed attempt still does not lock", already_ran(1500, when, p) is False)

        mark_ran(1500, when, 4, p)
        chk("a real capture DOES lock the slot", already_ran(1500, when, p) is True)
        chk("and the slot is no longer stuck", len(stuck(p)) == 0)
        chk("every attempt is retained (append-only)", attempts(1500, when, p) == 3)

        chk("the other capture point is independent", already_ran(1930, when, p) is False)
        chk("the next day is independent",
            already_ran(1500, pd.Timestamp("2026-10-06 15:00"), p) is False)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    m = _read()
    print(f"{MARKERS}  ({len(m)} markers)\n")
    if m.empty:
        print("  (none)")
    else:
        print(m.to_string(index=False))
        s = stuck()
        print(f"\nSlots whose markers captured nothing — retries ARE now permitted "
              f"for these ({len(s)}):")
        print("  (none)" if s.empty else "\n".join(f"  {k}" for k in s["key"]))

"""
tripwire.py — H19: the two-window under-delivery tripwire.

> If the next monthly retrain also shows the trailing 12 months under-delivering on the
> same target, re-derive that threshold. **Two consecutive under-delivering windows is the
> trigger; one is not.**

Deciding the trigger before seeing the next window is the entire point, so the rule lives
in its own module with its own state file rather than inside a judgement call in the
retrain report.

Why two and not one. Both failures already on this project's record came from acting on a
single window:

* the naively derived L2 threshold drifted **31.11x (2015) → 17.20x (2025)** by chasing the
  hot 2021–24 market, and 2025 then delivered **60% on 60 fires**;
* H16 read one refitted window as a live shortfall and had the direction backwards.

One weak window is evidence about the year. Two consecutive weak windows on the same target
is evidence about the rule. H17's promise is the **pooled walk-forward** rate across every
test year, and its own per-year table already showed 2025 at 76% — so a single year below
the promise is the expected shape of the thing, not a breach of it.

What firing does and does not authorise: it authorises **re-deriving** the threshold. It
does not authorise applying the result. The 25% drift guard still sits on top, so a
re-derivation that moves a threshold a long way is still held for the user's review.

State is `data/tripwire_state.json`, one record per target: the consecutive count, the
window that produced it, and every observation so far. A window is only counted once —
re-running the retrain in the same month updates that month's observation instead of
incrementing, because the count must mean "consecutive windows", not "consecutive runs".

    python tripwire.py                 # evaluate the current window, update the state
    python tripwire.py --show
    python tripwire.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

STATE = ROOT / "data" / "tripwire_state.json"
TRIGGER_AT = 2                 # consecutive under-delivering windows. H19.


def _load(path: Path | None = None) -> dict:
    p = path or STATE
    if not p.exists():
        return {"rule": "H19", "trigger_at": TRIGGER_AT, "targets": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        # A corrupt state file must not silently reset the count to zero: that would
        # disarm the tripwire exactly when it matters. Fail loudly instead.
        raise RuntimeError(f"{p} is unreadable. Fix or delete it deliberately — a silent "
                           f"reset would disarm the tripwire.")


def _save(st: dict, path: Path | None = None) -> None:
    p = path or STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")


def update(target: str, window: str, delivered: float | None, promise: float,
           n_bids: int, path: Path | None = None, min_bids: int = 20) -> dict:
    """Record one window's delivery for one target and return what it now implies.

    `window` is the window's identity (e.g. "2026-10"), not the run time: re-running in the
    same month revises that observation rather than counting a second one.

    A window with fewer than `min_bids` bids is recorded but **does not count** toward the
    trigger. The same reason the derivation requires 20 fires: a hit rate on a handful of
    bids is noise, and letting it increment the count would fire the tripwire on sample
    size rather than on performance.
    """
    st = _load(path)
    st.setdefault("targets", {})
    t = st["targets"].setdefault(target, {"consecutive_under": 0, "observations": []})

    under = (delivered is not None and delivered < promise
             and n_bids >= min_bids)
    obs = {"window": window, "delivered": delivered, "promise": promise,
           "n_bids": n_bids, "counts": bool(n_bids >= min_bids),
           "under": bool(under)}

    prev = [o for o in t["observations"] if o.get("window") == window]
    if prev:
        # Revise, and recompute the count from scratch so a revision cannot leave the
        # count describing a reading that no longer exists.
        t["observations"] = [o for o in t["observations"] if o.get("window") != window]
        t["observations"].append(obs)
        t["observations"].sort(key=lambda o: str(o.get("window")))
        run = 0
        for o in t["observations"]:
            if not o.get("counts"):
                continue                                     # too thin either way
            run = run + 1 if o.get("under") else 0
        t["consecutive_under"] = run
    else:
        t["observations"].append(obs)
        if n_bids >= min_bids:
            t["consecutive_under"] = t["consecutive_under"] + 1 if under else 0

    t["fired"] = bool(t["consecutive_under"] >= TRIGGER_AT)
    t["last_window"] = window
    _save(st, path)
    return {"target": target, "window": window, "under": bool(under),
            "counts": bool(n_bids >= min_bids),
            "consecutive_under": int(t["consecutive_under"]),
            "fired": bool(t["fired"]), "trigger_at": TRIGGER_AT}


def alert(r: dict) -> str | None:
    """The line the retrain report should carry, or None when there is nothing to say."""
    t = r["target"]
    if r["fired"]:
        return (f"{t}: TRIPWIRE FIRED (H19). {r['consecutive_under']} consecutive "
                f"12-month windows have under-delivered on {t}. RE-DERIVE this threshold. "
                f"Re-deriving is authorised; APPLYING the result is not — the 25% drift "
                f"guard still holds a large move for review.")
    if r["under"]:
        return (f"{t}: one 12-month window under-delivered ({r['window']}). "
                f"Count is {r['consecutive_under']} of {r['trigger_at']}. "
                f"NO ACTION by design (H19): one window is evidence about the year, two "
                f"consecutive is evidence about the rule.")
    if not r["counts"]:
        return (f"{t}: the {r['window']} window has too few bids to count either way. "
                f"Recorded, not counted.")
    return None


def current_window() -> str:
    import pandas as pd
    return pd.Timestamp.now().strftime("%Y-%m")


def evaluate(months: int = 12, path: Path | None = None) -> dict:
    """Run the email backtest over the trailing window and update both targets.

    The backtest is the measurement, not a separate reimplementation: it calls
    `score_l.predict_live()`, so what is being tripwired is what the email actually said.
    """
    import backtest_email as BE
    _, s = BE.backtest(months)
    w = current_window()
    out = {"window": w, "months": months, "n_ipos": s["n_ipos"], "targets": {}}
    for target in ("L1", "L2"):
        d = s[target]
        r = update(target, w, d["bid_hit_rate"], d["promise"], d["bids"], path)
        r["alert"] = alert(r)
        out["targets"][target] = r
    return out


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    import tempfile
    print("[1] one window does not fire; two consecutive do")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        a = update("L1", "2026-10", 0.857, 0.90, 49, p)
        chk("one under-delivering window: counted, not fired",
            a["consecutive_under"] == 1 and a["fired"] is False, a)
        b = update("L1", "2026-11", 0.880, 0.90, 51, p)
        chk("a second consecutive one FIRES",
            b["consecutive_under"] == 2 and b["fired"] is True, b)
        c = update("L1", "2026-12", 0.930, 0.90, 55, p)
        chk("a window that delivers resets the count to zero",
            c["consecutive_under"] == 0 and c["fired"] is False, c)

    print("\n[2] a thin window is recorded but never counted")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        a = update("L2", "2026-10", 0.50, 0.80, 4, p)
        chk("4 bids does not increment", a["consecutive_under"] == 0, a)
        chk("and it says so rather than passing silently", a["counts"] is False)
        chk("the observation is still on the record",
            len(_load(p)["targets"]["L2"]["observations"]) == 1)
        b = update("L2", "2026-11", 0.50, 0.80, 30, p)
        chk("the next real window starts the count at 1",
            b["consecutive_under"] == 1 and b["fired"] is False, b)

    print("\n[3] re-running in the same month revises, never double-counts")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        update("L1", "2026-10", 0.857, 0.90, 49, p)
        a = update("L1", "2026-10", 0.857, 0.90, 49, p)
        chk("the same window twice is still a count of 1",
            a["consecutive_under"] == 1 and a["fired"] is False, a)
        chk("and only one observation is stored",
            len(_load(p)["targets"]["L1"]["observations"]) == 1)
        update("L1", "2026-11", 0.88, 0.90, 50, p)
        rev = update("L1", "2026-11", 0.95, 0.90, 50, p)
        chk("revising a window UP un-fires it, rather than leaving a stale count",
            rev["consecutive_under"] == 0 and rev["fired"] is False, rev)

    print("\n[4] a corrupt state file fails loudly, never resets to zero")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        p.write_text("{not json", encoding="utf-8")
        try:
            _load(p)
            chk("unreadable state raises", False)
        except RuntimeError as e:
            chk("unreadable state raises", True)
            chk("and the message says why a silent reset would be wrong",
                "disarm" in str(e))

    print("\n[5] firing authorises re-deriving, not applying")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        update("L2", "2026-10", 0.72, 0.80, 36, p)
        r = update("L2", "2026-11", 0.74, 0.80, 33, p)
        r["alert"] = alert(r)
        chk("the fired alert says RE-DERIVE", "RE-DERIVE" in r["alert"])
        chk("and says applying is NOT authorised",
            "APPLYING the result is not" in r["alert"])
        chk("and names the drift guard that still holds", "drift" in r["alert"])
        chk("the trigger is 2, from H19", TRIGGER_AT == 2)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.show:
        print(json.dumps(_load(), indent=2, default=str))
        raise SystemExit(0)
    r = evaluate(a.months)
    print(json.dumps(r, indent=2, default=str))
    for t in ("L1", "L2"):
        m = r["targets"][t].get("alert")
        if m:
            print(f"\n  - {m}")

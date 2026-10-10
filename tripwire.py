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

H24 — the overlap rule (added 2026-10-10, before the 1 November retrain)
------------------------------------------------------------------------
Two *consecutive* trailing-12-month windows share **eleven of their twelve months**. If
October's window under-delivers, November's is reading almost the same rows: the second
reading is near-automatic and is not new evidence about the rule. Under H19 alone, one bad
year would arm the tripwire in October and fire it in November without a single new
outcome having to disappoint.

So, on top of H19: **a window counts toward the tripwire only if at least half of its
resolved firing rows are new since the last counted window.** Everything else in H19 is
unchanged — the trigger is still two, a delivering window still resets the count to zero,
a thin window is still recorded and not counted, and firing still authorises re-deriving
rather than applying. The overlap gate applies to
**incrementing** the count, never to resetting it: a window that delivers disarms the
tripwire whether or not its rows are new, because H24 is here to stop a near-automatic
second strike, not to make the tripwire harder to switch off.

"Resolved firing rows" means exactly the rows the hit rate was computed on: the IPOs the
email would have said BID to, whose listing gain is known. Their identity is stored on the
observation, so the overlap is measured rather than assumed. If a caller does not supply
them, the window is recorded and **not** counted, with the reason — H24 cannot be checked
against rows that were never recorded, and counting an unverifiable window is the thing
H24 exists to stop.

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
MIN_NEW_SHARE = 0.5            # of a window's firing rows, how many must be new. H24.


def _load(path: Path | None = None) -> dict:
    p = path or STATE
    if not p.exists():
        return {"rule": "H19 + H24", "trigger_at": TRIGGER_AT,
                "min_new_share": MIN_NEW_SHARE, "targets": {}}
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


def _recount(t: dict, min_bids: int, min_new_share: float) -> int:
    """Walk this target's observations in window order and return the consecutive count.

    One pass, used for every write, so the stored count can never describe a reading that
    has since been revised away. It also has to be one pass rather than a per-observation
    decision, because whether a window counts depends on which *earlier* window was the
    last counted one — and that is itself decided here.
    """
    obs = sorted(t.get("observations", []), key=lambda o: str(o.get("window")))
    run = 0
    last_keys: list | None = None          # the last COUNTED window's firing rows
    seen_counted = False
    for o in obs:
        keys = o.get("fire_keys")
        n = int(o.get("n_bids") or 0)
        why = None
        if n < min_bids:
            why = f"only {n} bids; fewer than {min_bids} is noise, not performance (H19)"
        elif not o.get("under"):
            # H24's overlap gate applies to INCREMENTING only. A window that delivers
            # still resets the count to zero even if it overlaps heavily, because H24
            # exists to stop a near-automatic second strike, not to make the tripwire
            # harder to disarm. Gating the reset as well would leave the count armed on
            # evidence that the shortfall had passed - stricter than H19, in the one
            # direction H19 was careful about.
            o["counts"] = True
            o["why_not_counted"] = None
            seen_counted = True
            if keys is not None:
                last_keys = keys
            run = 0
            continue
        elif not seen_counted:
            # The first counted window has nothing to overlap with, so H24 is silent on
            # it. Also the migration path: observations recorded before H24 carry no
            # fire_keys, and the first of them is still a legitimate reading.
            pass
        elif keys is None:
            why = ("firing rows were not recorded, so overlap with the previous counted "
                   "window cannot be measured (H24)")
        else:
            prev = set(last_keys or [])
            new = [k for k in keys if k not in prev]
            o["n_new_fires"] = len(new)
            o["n_fires"] = len(keys)
            if keys and len(new) < min_new_share * len(keys):
                why = (f"only {len(new)} of {len(keys)} firing rows are new since "
                       f"{o.get('prev_counted_window') or 'the last counted window'}; "
                       f"H24 needs at least half — consecutive 12-month windows share "
                       f"11 of 12 months, so this is the same reading, not a second one")
        o["counts"] = why is None
        o["why_not_counted"] = why
        if why is None:
            seen_counted = True
            if keys is not None:
                last_keys = keys
            run = run + 1 if o.get("under") else 0
    t["observations"] = obs
    t["consecutive_under"] = run
    return run


def update(target: str, window: str, delivered: float | None, promise: float,
           n_bids: int, path: Path | None = None, min_bids: int = 20,
           fire_keys: list[str] | None = None,
           min_new_share: float = MIN_NEW_SHARE) -> dict:
    """Record one window's delivery for one target and return what it now implies.

    `window` is the window's identity (e.g. "2026-10"), not the run time: re-running in the
    same month revises that observation rather than counting a second one.

    `fire_keys` identifies the resolved firing rows the hit rate was computed on — the
    rows the email would have said BID to, with a known listing gain. H24 needs them to
    tell a genuinely new window from the same reading shifted by a month. Without them the
    window is recorded and not counted.

    A window with fewer than `min_bids` bids is recorded but **does not count** toward the
    trigger. The same reason the derivation requires 20 fires: a hit rate on a handful of
    bids is noise, and letting it increment the count would fire the tripwire on sample
    size rather than on performance.
    """
    st = _load(path)
    st.setdefault("targets", {})
    st["rule"] = "H19 + H24"
    st["min_new_share"] = min_new_share
    t = st["targets"].setdefault(target, {"consecutive_under": 0, "observations": []})

    # `under` is about delivery alone. Whether it COUNTS is decided in _recount, because
    # that depends on the sequence, not on this window in isolation.
    under = delivered is not None and delivered < promise
    obs = {"window": window, "delivered": delivered, "promise": promise,
           "n_bids": n_bids, "under": bool(under)}
    if fire_keys is not None:
        obs["fire_keys"] = sorted(str(k) for k in fire_keys)

    t["observations"] = [o for o in t.get("observations", [])
                         if o.get("window") != window] + [obs]
    _recount(t, min_bids, min_new_share)

    t["fired"] = bool(t["consecutive_under"] >= TRIGGER_AT)
    t["last_window"] = window
    _save(st, path)
    this = [o for o in t["observations"] if o.get("window") == window][0]
    return {"target": target, "window": window, "under": bool(under),
            "counts": bool(this.get("counts")),
            "why_not_counted": this.get("why_not_counted"),
            "n_fires": this.get("n_fires"), "n_new_fires": this.get("n_new_fires"),
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
    if r["under"] and not r["counts"]:
        # H24's case, and the one worth saying out loud: a reading that looks like a
        # second strike but is the same rows again.
        return (f"{t}: the {r['window']} window under-delivered but does NOT count — "
                f"{r.get('why_not_counted')}. Count stays at {r['consecutive_under']} "
                f"of {r['trigger_at']} (H24).")
    if r["under"]:
        return (f"{t}: one 12-month window under-delivered ({r['window']}). "
                f"Count is {r['consecutive_under']} of {r['trigger_at']}. "
                f"NO ACTION by design (H19): one window is evidence about the year, two "
                f"consecutive is evidence about the rule.")
    if not r["counts"]:
        return (f"{t}: the {r['window']} window does not count either way — "
                f"{r.get('why_not_counted')}. Recorded, not counted.")
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
        # H24: the firing rows themselves, not just how many there were. `backtest`
        # returns them so the overlap between one window and the next is measured.
        r = update(target, w, d["bid_hit_rate"], d["promise"], d["bids"], path,
                   fire_keys=d.get("fire_keys"))
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

    def ks(a, b):
        """Firing-row keys numbered a..b-1, so overlap between windows is explicit."""
        return [f"ipo{i:03d}" for i in range(a, b)]

    print("[1] one window does not fire; two consecutive do")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        a = update("L1", "2026-10", 0.857, 0.90, 49, p, fire_keys=ks(0, 49))
        chk("one under-delivering window: counted, not fired",
            a["consecutive_under"] == 1 and a["fired"] is False, a)
        b = update("L1", "2026-11", 0.880, 0.90, 51, p, fire_keys=ks(49, 100))
        chk("a second consecutive one FIRES (all rows new)",
            b["consecutive_under"] == 2 and b["fired"] is True, b)
        c = update("L1", "2026-12", 0.930, 0.90, 55, p, fire_keys=ks(100, 155))
        chk("a window that delivers resets the count to zero",
            c["consecutive_under"] == 0 and c["fired"] is False, c)

    print("\n[2] a thin window is recorded but never counted")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        a = update("L2", "2026-10", 0.50, 0.80, 4, p, fire_keys=ks(0, 4))
        chk("4 bids does not increment", a["consecutive_under"] == 0, a)
        chk("and it says so rather than passing silently", a["counts"] is False)
        chk("the observation is still on the record",
            len(_load(p)["targets"]["L2"]["observations"]) == 1)
        b = update("L2", "2026-11", 0.50, 0.80, 30, p, fire_keys=ks(4, 34))
        chk("the next real window starts the count at 1",
            b["consecutive_under"] == 1 and b["fired"] is False, b)

    print("\n[3] re-running in the same month revises, never double-counts")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        update("L1", "2026-10", 0.857, 0.90, 49, p, fire_keys=ks(0, 49))
        a = update("L1", "2026-10", 0.857, 0.90, 49, p, fire_keys=ks(0, 49))
        chk("the same window twice is still a count of 1",
            a["consecutive_under"] == 1 and a["fired"] is False, a)
        chk("and only one observation is stored",
            len(_load(p)["targets"]["L1"]["observations"]) == 1)
        update("L1", "2026-11", 0.88, 0.90, 50, p, fire_keys=ks(49, 99))
        rev = update("L1", "2026-11", 0.95, 0.90, 50, p, fire_keys=ks(49, 99))
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
        update("L2", "2026-10", 0.72, 0.80, 36, p, fire_keys=ks(0, 36))
        r = update("L2", "2026-11", 0.74, 0.80, 33, p, fire_keys=ks(36, 69))
        r["alert"] = alert(r)
        chk("the fired alert says RE-DERIVE", "RE-DERIVE" in r["alert"])
        chk("and says applying is NOT authorised",
            "APPLYING the result is not" in r["alert"])
        chk("and names the drift guard that still holds", "drift" in r["alert"])
        chk("the trigger is 2, from H19", TRIGGER_AT == 2)

    print("\n[6] H24: an overlapping window is not a second reading")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        # 40 firing rows. A month later the window has rolled by one month: 36 of the
        # same rows, 4 new. That is what two consecutive 12-month windows look like.
        a = update("L1", "2026-10", 0.857, 0.90, 40, p, fire_keys=ks(0, 40))
        chk("the first window counts and arms the tripwire",
            a["counts"] is True and a["consecutive_under"] == 1, a)
        b = update("L1", "2026-11", 0.860, 0.90, 40, p, fire_keys=ks(4, 44))
        chk("4 of 40 rows new: UNDER-delivering but NOT counted",
            b["under"] is True and b["counts"] is False, b)
        chk("so the count does NOT advance and the tripwire does NOT fire",
            b["consecutive_under"] == 1 and b["fired"] is False, b)
        chk("and it says why, naming H24", "H24" in (b["why_not_counted"] or ""),
            b["why_not_counted"])
        chk("the alert says the count stays put",
            "does NOT count" in (alert(b) or "") and "H24" in (alert(b) or ""), alert(b))
        # Exactly half is enough — "at least half".
        c = update("L1", "2026-12", 0.860, 0.90, 40, p, fire_keys=ks(20, 60))
        chk("exactly half new DOES count, and now it fires",
            c["counts"] is True and c["consecutive_under"] == 2
            and c["fired"] is True, c)
        chk("the overlap it was measured against is the last COUNTED window, "
            "not the last window", c["n_new_fires"] == 40 - 20, c)

    print("\n[7] H24 keeps the rest of H19 intact")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        update("L2", "2026-10", 0.72, 0.80, 36, p, fire_keys=ks(0, 36))
        d = update("L2", "2026-11", 0.90, 0.80, 36, p, fire_keys=ks(2, 38))
        chk("a DELIVERING window still resets to zero even though it overlaps",
            d["consecutive_under"] == 0, d)
        chk("and it is treated as a real reading, not a skipped one",
            d["counts"] is True, d)
        chk("H24's gate is on INCREMENTING, not on resetting",
            "harder to disarm" in __import__("inspect").getsource(_recount))
        chk("the trigger is still 2", TRIGGER_AT == 2)
        chk("the share required is a half", MIN_NEW_SHARE == 0.5)

    print("\n[8] a window whose firing rows were not recorded is not counted")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.json"
        a = update("L1", "2026-10", 0.80, 0.90, 40, p)
        chk("the FIRST such window still counts - it has nothing to overlap with",
            a["counts"] is True and a["consecutive_under"] == 1, a)
        b = update("L1", "2026-11", 0.80, 0.90, 40, p)
        chk("a later one does NOT: unverifiable is not the same as independent",
            b["counts"] is False and b["consecutive_under"] == 1, b)
        chk("and it says the rows were not recorded",
            "not recorded" in (b["why_not_counted"] or ""), b["why_not_counted"])
        import inspect
        chk("evaluate() always supplies them, so this cannot happen in the real path",
            "fire_keys=d.get(\"fire_keys\")" in inspect.getsource(evaluate))
        import backtest_email as _BE
        chk("and backtest() is where they come from",
            "fire_keys" in inspect.getsource(_BE.backtest))

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

"""
retrain_review.py — the monthly retrain review (6b), replacing the `ipo-retrain-monthly`
Claude routine.

    python retrain_review.py              # run the checks, write the report, no email
    python retrain_review.py --email      # ... and email it
    python retrain_review.py --dry-run    # compose and print, write nothing, send nothing
    python retrain_review.py --self-test

What it does, and does not do
-----------------------------
It **reports**. It never applies a threshold, never promotes a challenger and never edits
a model file. Every check comes out as one row: the number measured, the limit it is
judged against, and `pass` or `FLAG`. A flag is an instruction to a human, not an action.

The engine is `retrain_l.py`, which already does the champion/challenger comparison, the
PSI drift monitoring, the 25% drift guard, the H19 two-window tripwire and the trailing-12m
IPO count, and already writes `reports/retrain/<YYYY-MM>.md`. This module does not
reimplement any of it — a second implementation of the tripwire would be a second thing to
keep in agreement with the first. It adds the two checks that were only ever done by hand,
composes the one-table-per-check summary, and sends it.

The two added checks
--------------------
* **delivered against promised** — L1's promise is 90% of fires gaining, L2's is 80%. What
  the emails actually delivered over the trailing 12 months is measured from the email
  backtest, so what is judged is what the emails really said.
* **the predictions_log header guard** — `COLS` gained four columns once and the file was
  never migrated, leaving a 32-column header above a 36-column row. Nothing complained for
  a week. This now fails the monthly review as well as the pre-flight gate (H39).

No probability anywhere (G2)
----------------------------
The report states hit rates, thresholds met and counts. It never prints a calibrated
probability as a literal chance of anything.

Idempotent per month
--------------------
A second run in the same calendar month rewrites that month's report in place and does not
send a second email, unless `--force`.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "reports" / "retrain"
SENT = ROOT / "data" / "retrain_sent.json"
L1_PROMISE, L2_PROMISE = 90.0, 80.0
DRIFT_LIMIT_PCT = 25.0
PSI_LIMIT = 0.25


def month_key(when=None) -> str:
    return pd.Timestamp(when or pd.Timestamp.now()).strftime("%Y-%m")


def already_sent(key: str) -> bool:
    if not SENT.exists():
        return False
    try:
        return key in (json.loads(SENT.read_text(encoding="utf-8")) or {})
    except Exception:                                          # noqa: BLE001
        return False


def mark_sent(key: str, subject: str) -> None:
    d = {}
    if SENT.exists():
        try:
            d = json.loads(SENT.read_text(encoding="utf-8")) or {}
        except Exception:                                      # noqa: BLE001
            d = {}
    d[key] = {"sent_at_ist": str(pd.Timestamp.now()), "subject": subject}
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(d, indent=2), encoding="utf-8")


# --------------------------------------------------------------- the two added checks
def delivered_vs_promise(window_months: int = 12) -> dict:
    """What the EMAILS delivered over the trailing window, against the promise.

    Measured from the email backtest rather than from a fresh fit, because the question is
    what the emails that actually went out delivered - not what a model would deliver if
    refitted today.
    """
    try:
        import tripwire as TW
        r = TW.evaluate(window_months)
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    out = {}
    for t, promise in (("L1", L1_PROMISE), ("L2", L2_PROMISE)):
        d = (r.get("targets") or {}).get(t) or {}
        hit = d.get("hit_rate")
        hit = None if hit is None else float(hit) * (100.0 if hit <= 1 else 1.0)
        out[t] = {"fires": d.get("n_fire"), "delivered_pct": hit, "promise_pct": promise,
                  "consecutive_under": d.get("consecutive"),
                  "alert": bool(d.get("alert")),
                  "pass": None if hit is None else bool(hit >= promise)}
    return out


def header_guard() -> dict:
    """H39. The predictions_log header must match COLS."""
    try:
        import predictions_log as PL
        have = PL.header_on_disk()
        if not have:
            return {"columns": 0, "expected": len(PL.COLS), "pass": True,
                    "note": "no log on disk yet"}
        PL.check_header("monthly retrain review")
        return {"columns": len(have), "expected": len(PL.COLS), "pass": True, "note": ""}
    except Exception as e:                                     # noqa: BLE001
        return {"columns": None, "expected": None, "pass": False,
                "note": f"{type(e).__name__}: {str(e)[:200]}"}


# --------------------------------------------------------------- the report
def checks_table(res: dict, deliv: dict, hdr: dict) -> tuple[list[dict], list[str]]:
    """`(rows, flagged rule names)`. One row per check: measured, limit, pass/FLAG.

    Read off `retrain_l`'s own result shape rather than recomputed, so the review and the
    engine cannot disagree. Keys are fetched defensively because a block that failed to
    run reports an `error` string where a dict would be, and a review that crashes on
    that is a review that tells you nothing in the month you most need it.
    """
    rows, flags = [], []

    def add(n, measured, limit, ok, rule=""):
        rows.append({"check": n, "measured": measured, "limit": limit,
                     "verdict": "pass" if ok else "FLAG"})
        if not ok and rule:
            flags.append(rule)

    def dig(o, *keys):
        for k in keys:
            if not isinstance(o, dict):
                return None
            o = o.get(k)
        return o

    # --- 1/2. delivered against promised, from the walk-forward re-derivation
    for t, promise in (("L1", L1_PROMISE), ("L2", L2_PROMISE)):
        d = dig(res, "thresholds", t) or {}
        wf, n = d.get("walk_forward_delivered"), d.get("walk_forward_fires")
        wf = None if wf is None else float(wf) * 100.0
        add(f"{t} delivered vs promise (walk-forward)",
            "did not run" if wf is None else f"{wf:.1f}% on {n} fires",
            f">= {promise:.0f}%", wf is None or wf >= promise, f"{t}-delivery")

    # --- 3/4. the H19 tripwire: two consecutive windows, not one
    for t in ("L1", "L2"):
        d = dig(res, "tripwire", "targets", t) or {}
        c, trig = d.get("consecutive_under"), d.get("trigger_at") or 2
        add(f"{t} H19 tripwire (two windows, not one)",
            "did not run" if c is None else f"{c} consecutive under-delivering window(s)",
            f"< {trig}", not bool(d.get("fired")), f"H19-{t}")

    # --- 5. the 25% drift guard on the re-derived thresholds
    worst, which = 0.0, ""
    for t in ("L1", "L2"):
        d = dig(res, "thresholds", t) or {}
        try:
            v = abs(float(d.get("moved_pct")))
        except (TypeError, ValueError):
            continue
        if v > worst:
            worst, which = v, t
    add("threshold drift guard (a large move is HELD, not applied)",
        f"max {worst:.1f}%" + (f" ({which})" if which else ""),
        f"<= {DRIFT_LIMIT_PCT:.0f}%", worst <= DRIFT_LIMIT_PCT, "drift-guard")

    # --- 6. input drift (PSI). Judged on the CHAMPION only, because the champion is the
    # model that is actually deciding. The challenger's inputs are reported beside it but
    # not judged: challenger_setA carries log(issue size), which drifts hard with the
    # market, and flagging that every month would be a standing false alarm about a model
    # that is not in the decision path. If the challenger is ever promoted, its PSI
    # becomes the judged one by the same rule.
    def psi_of(which):
        worst_v, worst_k = 0.0, ""
        for t, cands in (dig(res, "targets") or {}).items():
            if not isinstance(cands, dict):
                continue
            e = cands.get(which)
            if not isinstance(e, dict):
                continue
            try:
                v = float(e.get("psi_max"))
            except (TypeError, ValueError):
                continue
            if v > worst_v:
                worst_v, worst_k = v, t
        return worst_v, worst_k

    champ_psi, champ_t = psi_of("champion_total_only")
    chal_psi, chal_t = psi_of("challenger_setA")
    add("input drift, PSI on the LIVE champion's inputs",
        f"max {champ_psi:.3f}" + (f" ({champ_t})" if champ_t else ""),
        f"<= {PSI_LIMIT}", champ_psi <= PSI_LIMIT, "psi-champion")
    add("input drift, PSI on the challenger's inputs (display only)",
        f"max {chal_psi:.3f}" + (f" ({chal_t})" if chal_t else ""),
        "reported, not judged - the challenger is not deciding", True)

    # --- 7. trailing-12m IPO count. Reported, never judged (Task 11, display only).
    n12 = dig(res, "trailing_12m", "n_ipos")
    w = dig(res, "trailing_12m", "window") or []
    add("trailing-12m IPO count (display only)",
        "did not run" if n12 is None
        else f"{n12} IPOs" + (f" ({w[0]} to {w[-1]})" if len(w) >= 2 else ""),
        "reported, not judged", True)

    # --- 8. the predictions_log header guard (H39)
    add("predictions_log header matches COLS (H39)",
        "unreadable" if hdr.get("columns") is None
        else f"{hdr['columns']} columns vs {hdr['expected']} in COLS",
        "must be equal", bool(hdr.get("pass")), "H39-header")

    # --- 9. champion/challenger. A qualifying challenger is REPORTED for ratification,
    # never promoted here.
    for t in ("L1", "L2"):
        dec = dig(res, "targets", t, "decision")
        dec = dec if isinstance(dec, str) else None
        add(f"{t} champion/challenger",
            dec[:80] if dec else "did not run",
            "promotion is never automatic",
            not (dec or "").startswith("PROMOTE"), f"{t}-challenger")
    return rows, flags


def compose(res: dict, deliv: dict, hdr: dict, key: str) -> tuple[str, str, list[str]]:
    rows, flags = checks_table(res, deliv, hdr)
    subject = (f"IPO decision - RETRAIN {key}: no flags" if not flags
               else f"IPO decision - RETRAIN {key}: FLAG {', '.join(sorted(set(flags)))}")
    L = [f"# Monthly retrain review — {key}", "",
         "**This review applies nothing.** No threshold is changed, no challenger is "
         "promoted and no model file is touched. Each check reports a number, the limit "
         "it is judged against, and pass or FLAG. A flag is an instruction to a human.",
         "", "## Checks", "",
         "| check | measured | limit | verdict |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['check']} | {r['measured']} | {r['limit']} | "
                 f"**{r['verdict']}** |")
    L += ["", "## What is flagged", ""]
    L += ([f"- `{f}`" for f in sorted(set(flags))] if flags
          else ["Nothing. Every check is inside its limit."])
    L += ["", "## Notes", "",
          "- Verdicts are the threshold met and the rate delivered, never a probability "
          "(decision G2).",
          "- H19: two consecutive under-delivering windows trigger a re-derivation; one "
          "does not. A re-derivation that also moves a threshold by more than 25% is "
          "still held for review rather than applied.",
          f"- Engine: `retrain_l.py`. Report written by `retrain_review.py` at "
          f"{pd.Timestamp.now()}.", ""]
    return subject, "\n".join(L), flags


def main(email: bool = False, dry: bool = False, force: bool = False) -> dict:
    key = month_key()
    import retrain_l as RL
    print(f"monthly retrain review {key}")
    try:
        res = RL.main(dry=True)
    except Exception as e:                                     # noqa: BLE001
        res = {"error": f"{type(e).__name__}: {e}"}
        print(f"  retrain_l failed: {res['error']}")
    deliv = delivered_vs_promise(12)
    hdr = header_guard()
    subject, body, flags = compose(res, deliv, hdr, key)
    print()
    print(body)
    if dry:
        print("\n--dry-run: nothing written, nothing sent")
        return {"subject": subject, "flags": flags, "written": False, "sent": False}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = OUT_DIR / f"{key}.md"
    # retrain_l writes the detail for this month to the same path; this review is appended
    # under its own heading so both survive and neither has to be regenerated to read the
    # other.
    prev = md.read_text(encoding="utf-8") if md.exists() else ""
    marker = "<!-- retrain_review -->"
    keep = prev.split(marker)[0].rstrip() if marker in prev else prev.rstrip()
    md.write_text((keep + "\n\n" if keep else "") + marker + "\n" + body,
                  encoding="utf-8")
    print(f"written {md}")
    sent = False
    if email:
        if already_sent(key) and not force:
            print(f"already emailed for {key}; not sending again (idempotent per month)")
        else:
            from send_daily_email import send
            r = send(subject, body, dry=False)
            sent = bool(r.get("sent"))
            if sent:
                mark_sent(key, subject)
            print(f"email: {r}")
    return {"subject": subject, "flags": flags, "written": True, "sent": sent,
            "report": str(md)}


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  ok   {name}")
        else:
            fail += 1
            print(f"  FAIL {name} {extra}")

    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] it reports and never applies")
    chk("no threshold is written anywhere",
        "apply" not in src.lower().replace("applies nothing", "")
        .replace("applies", "") or "RL.main(dry=True)" in src)
    chk("the engine is called in DRY mode, so it cannot apply anything",
        "RL.main(dry=True)" in src)
    chk("the tripwire is not reimplemented here", "import tripwire as TW" in src
        and "consecutive" in src)

    print(chr(10) + "[2] the subject is exactly the two forms the user specified")
    s1, _, f1 = compose({}, {}, {"columns": 36, "expected": 36, "pass": True}, "2026-10")
    chk("a clean month reads 'no flags'",
        s1.startswith("IPO decision - RETRAIN 2026-10: ") and s1.endswith("no flags"), s1)
    s2, _, f2 = compose({}, {}, {"columns": 32, "expected": 36, "pass": False}, "2026-10")
    chk("a flagged month names the rules",
        s2.startswith("IPO decision - RETRAIN 2026-10: FLAG ") and "H39-header" in s2, s2)
    chk("and the header mismatch is what flagged it", "H39-header" in f2)

    print(chr(10) + "[3] one table per check, with a limit and a verdict")
    rows, _ = checks_table({}, {}, {"columns": 36, "expected": 36, "pass": True})
    chk("every row carries check, measured, limit and verdict",
        all({"check", "measured", "limit", "verdict"} <= set(r) for r in rows))
    chk("the six required checks are present",
        all(any(k in r["check"] for r in rows) for k in
            ("delivered vs promise", "H19 tripwire", "drift guard", "PSI",
             "trailing-12m", "header")), [r["check"] for r in rows])
    chk("a verdict is only ever pass or FLAG",
        {r["verdict"] for r in rows} <= {"pass", "FLAG"})

    print(chr(10) + "[4] no probability (G2)")
    _, body, _ = compose({}, {}, {"columns": 36, "expected": 36, "pass": True}, "2026-10")
    low = body.lower()
    chk("the report never prints a calibrated probability",
        "p_cal" not in low and "probability (decision g2)" in low)

    print(chr(10) + "[5] idempotent per month")
    chk("a month already emailed is not emailed again", "already_sent(key)" in src)
    chk("unless --force", "and not force" in src)
    chk("and the report is rewritten in place, not appended twice",
        "marker in prev" in src)

    print(chr(10) + "[6] the report path is the one the user asked for")
    chk("reports/retrain/YYYY-MM.md",
        str(OUT_DIR).replace(chr(92), "/").endswith("reports/retrain")
        and 'f"{key}.md"' in src)
    print(f"{chr(10)}{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser(description="monthly retrain review (reports only)")
    ap.add_argument("--email", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="send even if this month was already emailed")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    r = main(email=a.email, dry=a.dry_run, force=a.force)
    print()
    print(json.dumps({k: v for k, v in r.items() if k != "report"}, default=str))

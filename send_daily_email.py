"""
send_daily_email.py — the single live pipeline for Model L (Priorities 1b–1g).

This is now **the only script the scheduled jobs call**:

    python send_daily_email.py            15:00 IST  fetch, score, snapshot, report, EMAIL
    python send_daily_email.py --final    17:30 IST  fetch, snapshot after close, NO email
    python send_daily_email.py --dry-run             compose and print, send nothing

`run_live_l.py` is no longer scheduled. It reads NSE and BSE, both of which refuse this
host, and it wrote to the *same* report path as this script — so on 2 Oct its failing
21:49 run overwrote the good Chittorgarh report. Per H14 Chittorgarh is the live source, so
there is one pipeline, one report path, and `run_live_l.py` survives only as an
exchange-access probe writing to `reports/live/exchange_probe/` (Priority 1c).

Why this file no longer imports the modelling stack (Priority 1b)
-----------------------------------------------------------------
It used to `import model_l`, which imports `framework`, which imports `joblib`. joblib was
never in requirements.txt — it arrives on the laptop only as a scikit-learn dependency, and
scikit-learn is banned (rule 10). So every cloud run died in ~35 s with
`ModuleNotFoundError: No module named 'joblib'` and no email was sent for three days.
Scoring now goes through `score_l.py`, which reads the portable coefficient JSON using
only the standard library. **A modelling dependency can no longer break mail delivery.**

Three rules this module exists to enforce, because each is easy to break by accident:

1. **Send every weekday without exception**, including days with no open IPO. Silence must
   always mean something broke, never that nothing happened.

2. **A verdict only where the model supports one.** Model L is trained on final-day
   subscription, and an IPO at 3x on day 1 can close at 150x — so a day-1 or day-2 reading
   cannot carry a verdict. Not closing today means **numbers only**. There is deliberately
   no "provisional", "indicative" or "estimated" verdict anywhere in this file for a
   mainboard IPO: inventing one the model cannot support is worse than showing none. SME is
   always PROVISIONAL regardless, per shadow mode.

3. **Fail loudly.** A missing secret, an SMTP refusal or a source failure raises and exits
   non-zero. It never silently skips the email, and it never sends a report with a verdict
   computed from data that did not arrive.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import chittorgarh_live as CL      # noqa: E402
import score_l as SL               # noqa: E402  — portable JSON, no joblib (Priority 1b)
import predictions_log as PL       # noqa: E402
import live_markers as LM          # noqa: E402
import market_context as MC        # noqa: E402

LIVE_DIR = ROOT / "reports" / "live"
SNAPSHOTS = ROOT / "data" / "subscription_snapshots.csv"
CUTOFF = "4:00 PM"

# Priority 1d: EXACTLY this. Plain ASCII hyphen-minus, lowercase "decision", one space
# either side, trailing space. Mail filters match literally, so an em dash would silently
# stop matching. Asserted in self_test().
SUBJECT_PREFIX = "IPO decision - "

# Priority 1g: both legs write here, so the 15:00-vs-close gap starts accumulating. The
# file had never been created, because the only leg that wrote it was the NSE/BSE one that
# always failed. `sector` is Priority 6 and is populated ONLY where the source page states
# it — never guessed.
SNAP_COLS = ["ipo", "isin", "ipo_id", "segment", "date", "timestamp_ist", "capture_point",
             "qib_x", "hni_x", "rii_x", "emp_x", "total_x", "sector",
             "source", "reconciled", "note"]

CAVEATS = [
    "3pm figures understate final demand; a near-threshold NO is uncertain.",
    "Subscription from a single source — verify on your broker app before bidding.",
    "Category figures are shown for your judgement only; the model uses total subscription.",
]


class MissingSecret(RuntimeError):
    pass


def secrets() -> tuple[str, str, str]:
    """`(sender, password, recipient)`, or a loud failure. Never a silent skip.

    Priority 1e: the recipient is the repo secret `EMAIL_TO`, falling back to
    `GMAIL_ADDRESS` when it is unset. EMAIL_TO is deliberately allowed to be a different
    provider from the sender — the user's GitHub account is on Yahoo while the Gmail
    account only sends.
    """
    addr = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    missing = [n for n, v in (("GMAIL_ADDRESS", addr), ("GMAIL_APP_PASSWORD", pw)) if not v]
    if missing:
        raise MissingSecret(
            f"missing repo secret(s): {', '.join(missing)}. The email was NOT sent and this "
            "run has failed deliberately — a silently skipped email would look identical to "
            "a quiet market. See EMAIL_SETUP.md.")
    to = os.environ.get("EMAIL_TO", "").strip() or addr
    return addr, pw, to


# ---------------------------------------------------------------- composition
def _verdict_block(res: dict) -> list[str]:
    """The thresholds are read from the model export, never retyped here — a hardcoded
    number is how a report starts claiming a promise the model was not validated against.
    """
    l1, l2 = res["L1"], res["L2"]
    t1 = l1.get("required_hit_rate", 0) * 100
    t2 = l2.get("required_hit_rate", 0) * 100
    return [f"  L1 (any listing gain):  {l1['verdict']:<10s} threshold {t1:.0f}%",
            f"  L2 (gain above 10%):    {l2['verdict']:<10s} threshold {t2:.0f}%"]


def _numbers(r: dict, as_of: str) -> list[str]:
    s = r.get("sub", {})

    def x(k):
        v = s.get(k)
        return "   -  " if v is None else f"{v:.2f}x"
    day = (f"   (Day {r['day_of']} of {r['days_total']})"
           if r.get("day_of") and r.get("days_total") else "")
    return [f"  Total subscription:     {x('total_x'):<7s} @ {as_of}{day}",
            f"  QIB {x('qib_x'):>7s} | HNI {x('hni_x'):>7s} | "
            f"Retail {x('rii_x'):>7s}        (display only)"]


def compose(mv: dict, scored: dict, today: pd.Timestamp | None = None) -> tuple[str, str]:
    # `today` is passed in rather than read from the clock, so the header date and the
    # market view can never disagree -- they did during the Monday rehearsal, which
    # printed Monday's market under Saturday's heading.
    now = pd.Timestamp.now()
    today = today or now
    as_of = now.strftime("%H:%M")
    closing = mv["closing_today"]
    open_not = mv["open_not_closing"]
    upcoming = mv["upcoming"]

    n_open = len(closing) + len(open_not)
    if closing:
        urgent = f"{len(closing)} closes today"
    elif open_not:
        soonest = min(open_not, key=lambda r: r["closes"])
        urgent = f"next closes {pd.Timestamp(soonest['closes']).strftime('%a')}"
    else:
        urgent = "none closing"
    subject = f"{SUBJECT_PREFIX}{n_open} open, {urgent}"

    L = [f"IPO MARKET — {today.strftime('%A %d %B').replace(' 0', ' ')}", ""]

    L += ["===== CLOSING TODAY — bid by 4:00 PM =====", ""]
    if not closing:
        L += ["  Nothing closes today.", ""]
    for r in closing:
        seg = "Mainboard" if r["segment"] == "mainboard" else "SME"
        L.append(f"[{r['ipo'].upper()}]  ({seg})")
        res = scored.get(r["ipo"])
        if r["segment"] != "mainboard":
            # SME is shadow mode: display, never decide.
            L += _numbers(r, as_of)
            L += ["  PROVISIONAL — SME model not validated for bid decisions.", ""]
            continue
        if res is None:
            L += _numbers(r, as_of)
            L += ["  NO VERDICT — subscription did not arrive, so the model's only input "
                  "is missing.", "  Verify on your broker app before the cutoff.", ""]
            continue
        L += _verdict_block(res)
        L += _numbers(r, as_of)
        L += [f"  Demand profile:         {res['demand_profile']}",
              "  Veto flags:             none",
              "  GMP: ______%            (not in model — your judgement)", ""]

    L += ["===== OPEN, NOT CLOSING TODAY =====", ""]
    if not open_not:
        L += ["  Nothing else is open.", ""]
    for r in open_not:
        seg = "Mainboard" if r["segment"] == "mainboard" else "SME"
        closes = pd.Timestamp(r["closes"]).strftime("%A")
        L.append(f"[{r['ipo'].upper()}]  ({seg})  closes {closes}")
        L += _numbers(r, as_of)
        if r["segment"] == "mainboard":
            L += ["  No verdict until the final day — early subscription does not "
                  "predict the close.", ""]
        else:
            L += ["  PROVISIONAL — SME model not validated for bid decisions.", ""]

    L += ["===== UPCOMING ====="]
    if not upcoming:
        L += ["  Nothing scheduled to open.", ""]
    for r in upcoming:
        L.append(f"  [{r['ipo'].upper()}] opens "
                 f"{pd.Timestamp(r['opens']).strftime('%A %d %b').replace(' 0', ' ')}")

    L += ["", "-----", f"Caveats: {CAVEATS[0]}"]
    for c in CAVEATS[1:]:
        L.append(f"         {c}")

    # Priority 6: display-only market context. Never a model input (H2).
    L += ["", MC.email_footer(), ""]

    if mv.get("diagnostics"):
        L += ["Diagnostics:"] + [f"  - {d}" for d in mv["diagnostics"]]
    L += ["", f"Model {SL.MODEL_ID} / {SL.DECISION_POINT}. Verdicts are the threshold met, "
              "never a probability.",
          "Source: chittorgarh.com (single source, decision H14). Every request logged "
          "with its timestamp and exact URL in data/live_fetch_log.csv."]
    return subject, "\n".join(L)


# ---------------------------------------------------------------- snapshots
def append_snapshots(mv: dict, capture_point: int, when: pd.Timestamp) -> int:
    """Priority 1g. Every open IPO's reading at this capture point, appended.

    Rows are written for failed reads too, with the reason in `note` and the figures NULL:
    a missing row and a row that says "the Total was not published yet" are different
    facts, and only the second one is evidence.
    """
    rows = []
    for r in mv["closing_today"] + mv["open_not_closing"]:
        s = r.get("sub", {}) or {}
        rows.append({
            "ipo": r.get("ipo"), "isin": r.get("isin"), "ipo_id": r.get("ipo_id"),
            "segment": r.get("segment"), "date": str(when.date()),
            "timestamp_ist": str(when), "capture_point": capture_point,
            "qib_x": s.get("qib_x"), "hni_x": s.get("hni_x"), "rii_x": s.get("rii_x"),
            "emp_x": s.get("emp_x"), "total_x": s.get("total_x"),
            # Priority 6: only where the source page states it. Chittorgarh's subscription
            # page does not, so this stays NULL rather than being inferred from the name.
            "sector": s.get("sector"),
            "source": "chittorgarh",
            "reconciled": "single_source_unverified",
            "note": "" if s.get("ok") else (s.get("why") or "no reading"),
        })
    if not rows:
        return 0
    df = pd.DataFrame([{c: r.get(c) for c in SNAP_COLS} for r in rows], columns=SNAP_COLS)
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOTS, mode="a", header=not SNAPSHOTS.exists(), index=False,
              encoding="utf-8")
    return len(rows)


# ---------------------------------------------------------------- send
def send(subject: str, body: str, dry: bool) -> dict:
    if dry:
        print(f"SUBJECT: {subject}\n")
        print(body)
        return {"sent": False, "dry_run": True, "subject": subject}
    addr, pw, to = secrets()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(addr, pw)
        smtp.send_message(msg)
    return {"sent": True, "subject": subject, "to": to, "from": addr}


# ---------------------------------------------------------------- entry points
def main(dry: bool = False, final: bool = False, force: bool = False) -> dict:
    """The 15:00 leg (`final=False`) scores, logs, snapshots, reports and emails.
    The 17:30 leg (`final=True`) snapshots only — the bid window has closed, so there is
    nothing left to decide and nothing to email."""
    today = pd.Timestamp.now()
    capture_point = 1730 if final else 1500

    if today.weekday() >= 5:
        print(f"{today.strftime('%A')} — no bidding at the weekend, no email.")
        return {"sent": False, "reason": "weekend"}

    # Idempotency (Priority 1f): a previous attempt that captured NOTHING does not lock
    # this slot. Only a real capture does.
    if not dry and not force and LM.already_ran(capture_point, today):
        print(f"{today.date()} {capture_point}: already captured. No-op.")
        return {"sent": False, "reason": "already_ran", "capture_point": capture_point}

    mv = CL.market_view(today)
    n_snap = 0 if dry else append_snapshots(mv, capture_point, today)

    # Priority 6: the 17:30 leg is where the index closes are captured — after the market
    # has actually closed. The 15:00 leg only reads back whatever is already on disk.
    ctx = MC.capture(today) if (final and not dry) else {"skipped": "not the 17:30 leg"}

    if final:
        if not dry:
            LM.mark_ran(capture_point, today, n_snap)
        print(f"17:30 final capture {today.date()}: {n_snap} snapshot rows, "
              f"{ctx.get('n_ok', 0)} index closes. No email at this capture point.")
        return {"sent": False, "mode": "final", "n_snapshots": n_snap,
                "capture_point": capture_point, "market_context": ctx}

    scored = {}
    for r in mv["closing_today"]:
        if r["segment"] != "mainboard":
            continue                      # SME never gets a verdict (shadow mode)
        s = r.get("sub", {})
        if not s.get("ok") or s.get("total_x") is None:
            continue                      # no input, no verdict
        res = SL.predict_live(total=s["total_x"], qib=s.get("qib_x"), rii=s.get("rii_x"),
                              segment=r["segment"])
        res["inputs"]["hni"] = s.get("hni_x")
        scored[r["ipo"]] = res
        if not dry:
            PL.log_prediction(r["ipo"], r.get("isin"), res, capture_point=capture_point,
                              source="chittorgarh single_source_unverified (H14)")

    subject, body = compose(mv, scored, today)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / f"{today.date()}.md").write_text(body, encoding="utf-8")
    out = send(subject, body, dry)
    if not dry:
        LM.mark_ran(capture_point, today, n_snap)
    out.update({"n_open": mv["n_open"], "n_closing": len(mv["closing_today"]),
                "n_verdicts": len(scored), "n_snapshots": n_snap,
                "capture_point": capture_point})
    return out


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("send_daily_email.py self-test (no network, no mail)")

    print("\n[1] subject line is byte-exact (Priority 1d)")
    chk("prefix == 'IPO decision - '", SUBJECT_PREFIX == "IPO decision - ",
        repr(SUBJECT_PREFIX))
    chk("prefix is pure ASCII — no em dash", SUBJECT_PREFIX.isascii(),
        repr(SUBJECT_PREFIX))
    chk("the dash is U+002D hyphen-minus",
        "-" in SUBJECT_PREFIX and "—" not in SUBJECT_PREFIX
        and "–" not in SUBJECT_PREFIX)
    chk("'decision' is lowercase", "decision" in SUBJECT_PREFIX
        and "Decision" not in SUBJECT_PREFIX)

    print("\n[2] recipient resolution (Priority 1e)")
    keep = {k: os.environ.get(k) for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_TO")}
    try:
        os.environ["GMAIL_ADDRESS"] = "sender@gmail.com"
        os.environ["GMAIL_APP_PASSWORD"] = "x"
        os.environ.pop("EMAIL_TO", None)
        chk("EMAIL_TO unset -> falls back to GMAIL_ADDRESS",
            secrets()[2] == "sender@gmail.com", str(secrets()))
        os.environ["EMAIL_TO"] = "me@yahoo.com"
        chk("EMAIL_TO set -> used as recipient", secrets()[2] == "me@yahoo.com")
        chk("sender stays GMAIL_ADDRESS", secrets()[0] == "sender@gmail.com")
        chk("a different provider for recipient is allowed",
            secrets()[0].split("@")[1] != secrets()[2].split("@")[1])
        os.environ["GMAIL_APP_PASSWORD"] = ""
        try:
            secrets()
            chk("a missing secret fails loudly", False, "no exception raised")
        except MissingSecret as e:
            chk("a missing secret fails loudly", "GMAIL_APP_PASSWORD" in str(e))
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("\n[3] no modelling dependency in the mail path (Priority 1b)")
    import subprocess
    probe = ("import sys, send_daily_email; "
             "print(','.join(m for m in ['joblib','sklearn','framework','model_l'] "
             "if m in sys.modules))")
    p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                       cwd=str(ROOT), timeout=180)
    chk("importing send_daily_email pulls in no joblib/framework/model_l",
        p.returncode == 0 and p.stdout.strip() == "",
        f"rc={p.returncode} leaked={p.stdout.strip()!r} err={p.stderr.strip()[-300:]}")

    print("\n[4] composition on a synthetic market — verdict discipline (Priority 1c)")
    mv = {
        "closing_today": [
            {"ipo": "Mainboard Closing", "segment": "mainboard", "ipo_id": 1, "isin": None,
             "day_of": 3, "days_total": 3,
             "sub": {"ok": True, "total_x": 120.0, "qib_x": 200.0, "rii_x": 40.0,
                     "hni_x": 90.0}},
            {"ipo": "Mainboard No Data", "segment": "mainboard", "ipo_id": 2, "isin": None,
             "sub": {"ok": False, "why": "no Total row yet"}},
            {"ipo": "Sme Closing", "segment": "sme", "ipo_id": 3, "isin": None,
             "sub": {"ok": True, "total_x": 300.0, "qib_x": 10.0, "rii_x": 500.0}},
        ],
        "open_not_closing": [
            {"ipo": "Mainboard Midweek", "segment": "mainboard", "ipo_id": 4, "isin": None,
             "closes": "2026-10-09", "day_of": 1, "days_total": 3,
             "sub": {"ok": True, "total_x": 2.0, "qib_x": 0.1, "rii_x": 5.0}},
        ],
        "upcoming": [], "diagnostics": ["robots.txt: ok"], "n_open": 4,
    }
    scored = {"Mainboard Closing": SL.predict_live(120.0, 200.0, 40.0),
              # deliberately NOT scored: the SME one, and the no-data one
              }
    subject, body = compose(mv, scored)
    chk("subject starts with the exact prefix", subject.startswith(SUBJECT_PREFIX), subject)
    chk("the closing mainboard IPO gets L1 and L2 verdict lines",
        "L1 (any listing gain)" in body and "L2 (gain above 10%)" in body)
    chk("the no-data IPO gets NO VERDICT, not a guess", "NO VERDICT" in body)
    chk("SME is PROVISIONAL", "PROVISIONAL" in body)
    chk("the midweek mainboard IPO gets no verdict",
        "No verdict until the final day" in body)
    for banned in ("provisional verdict", "indicative", "estimated verdict"):
        chk(f"no '{banned}' anywhere", banned.lower() not in body.lower())
    chk("the single-source caveat is present",
        "verify on your broker app" in body.lower())
    # The footer says "no index history captured yet" until the 17:30 leg has run, so the
    # test asserts the footer EXISTS, not that it carries a number it cannot have yet.
    chk("a market-context footer is present", "Market context:" in body)
    chk("the footer says it is not a model input", "not a model input" in body.lower())

    print("\n[5] snapshot schema (Priority 1g)")
    chk("sector column exists", "sector" in SNAP_COLS)
    chk("capture_point column exists", "capture_point" in SNAP_COLS)
    chk("segment is carried, not re-derived", "segment" in SNAP_COLS)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="compose and print, send nothing")
    ap.add_argument("--final", action="store_true",
                    help="17:30 leg: snapshot after close, no email")
    ap.add_argument("--force", action="store_true",
                    help="ignore the idempotency marker for this slot")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    try:
        r = main(a.dry_run, a.final, a.force)
    except Exception as e:
        print(f"\nFAILED LOUDLY: {type(e).__name__}: {e}", file=sys.stderr)
        raise
    print(f"\n{r}")

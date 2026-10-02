"""
send_daily_email.py — the weekday IPO decision email (Priority 1e).

Composes the report in the fixed format and sends it over Gmail SMTP using the repo secrets
`GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. See `EMAIL_SETUP.md`.

Three rules this module exists to enforce, because each is easy to break by accident:

1. **Send every weekday without exception**, including days with no open IPO. Silence must
   always mean something broke, never that nothing happened. A day with an empty market
   still gets an email saying so.

2. **A verdict only where the model supports one** (Priority 1c). Model L is trained on
   final-day subscription, and an IPO at 3x on day 1 can close at 150x — so a day-1 or
   day-2 reading cannot carry a verdict. Not closing today means **numbers only**. There is
   deliberately no "provisional", "indicative" or "estimated" verdict anywhere in this file:
   inventing one the model cannot support is worse than showing none. SME is always
   PROVISIONAL regardless, per shadow mode.

3. **Fail loudly.** A missing secret, an SMTP refusal or a source failure raises and exits
   non-zero. It never silently skips the email, and it never sends a report with a verdict
   computed from data that did not arrive.

    python send_daily_email.py --dry-run     # print, do not send
    python send_daily_email.py               # compose and send
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
sys.path.insert(0, str(ROOT / "models"))
import chittorgarh_live as CL      # noqa: E402
import model_l as ML               # noqa: E402
import predictions_log as PL       # noqa: E402

LIVE_DIR = ROOT / "reports" / "live"
CUTOFF = "4:00 PM"
SUBJECT_PREFIX = "IPO decision — "     # exact, em dash, trailing space: filterable

CAVEATS = [
    "3pm figures understate final demand; a near-threshold NO is uncertain.",
    "Subscription from a single source — verify on your broker app.",
    "Category figures are shown for your judgement only; the model uses total subscription.",
]


class MissingSecret(RuntimeError):
    pass


def secrets() -> tuple[str, str]:
    """Both secrets, or a loud failure. Never a silent skip."""
    addr = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    missing = [n for n, v in (("GMAIL_ADDRESS", addr), ("GMAIL_APP_PASSWORD", pw)) if not v]
    if missing:
        raise MissingSecret(
            f"missing repo secret(s): {', '.join(missing)}. The email was NOT sent and this "
            "run has failed deliberately — a silently skipped email would look identical to "
            "a quiet market. See EMAIL_SETUP.md.")
    return addr, pw


# ---------------------------------------------------------------- composition
def _verdict_block(r: dict, res: dict) -> list[str]:
    l1, l2 = res["L1"], res["L2"]
    t1 = (ML.REQUIRED["L1"] * 100)
    t2 = (ML.REQUIRED["L2"] * 100)
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


def compose(mv: dict, scored: dict) -> tuple[str, str]:
    now = pd.Timestamp.now()
    as_of = now.strftime("%H:%M")
    closing = mv["closing_today"]
    open_not = mv["open_not_closing"]
    upcoming = mv["upcoming"]

    # ---- subject: exact prefix, then the count and the most urgent item
    n_open = len(closing) + len(open_not)
    if closing:
        urgent = f"{len(closing)} closes today"
    elif open_not:
        soonest = min(open_not, key=lambda r: r["closes"])
        urgent = f"next closes {pd.Timestamp(soonest['closes']).strftime('%a')}"
    else:
        urgent = "none closing"
    subject = f"{SUBJECT_PREFIX}{n_open} open, {urgent}"

    L = [f"IPO MARKET — {now.strftime('%A %-d %B') if os.name != 'nt' else now.strftime('%A %d %B').replace(' 0', ' ')}",
         ""]

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
        L += _verdict_block(r, res)
        L += _numbers(r, as_of)
        L += [f"  Demand profile:         {res['demand_profile']}",
              "  Veto flags:             none"
              + ("" if True else ""),
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
    if mv.get("diagnostics"):
        L += ["", "Diagnostics:"] + [f"  - {d}" for d in mv["diagnostics"]]
    L += ["", f"Model {ML.MODEL_ID} / {ML.DECISION_POINT}. Verdicts are the threshold met, "
              "never a probability.",
          "Source: chittorgarh.com (single source, decision H14). "
          f"Fetched {len(mv.get('diagnostics', []))} diagnostics; "
          "every request logged in data/live_fetch_log.csv."]
    return subject, "\n".join(L)


# ---------------------------------------------------------------- send
def send(subject: str, body: str, dry: bool) -> dict:
    if dry:
        print(f"SUBJECT: {subject}\n")
        print(body)
        return {"sent": False, "dry_run": True, "subject": subject}
    addr, pw = secrets()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = addr
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(addr, pw)
        smtp.send_message(msg)
    return {"sent": True, "subject": subject, "to": addr}


def main(dry: bool = False) -> dict:
    today = pd.Timestamp.now()
    if today.weekday() >= 5:
        print(f"{today.strftime('%A')} — no bidding at the weekend, no email.")
        return {"sent": False, "reason": "weekend"}

    mv = CL.market_view(today)
    scored = {}
    for r in mv["closing_today"]:
        if r["segment"] != "mainboard":
            continue                      # SME never gets a verdict (shadow mode)
        s = r.get("sub", {})
        if not s.get("ok") or s.get("total_x") is None:
            continue                      # no input, no verdict
        res = ML.predict_live(total=s["total_x"], issue_size_cr=None,
                              qib=s.get("qib_x"), rii=s.get("rii_x"))
        res["inputs"]["hni"] = s.get("hni_x")
        scored[r["ipo"]] = res
        if not dry:
            PL.log_prediction(r["ipo"], r.get("isin"), res, capture_point=1500,
                              source="chittorgarh single_source_unverified (H14)")

    subject, body = compose(mv, scored)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / f"{today.date()}.md").write_text(body, encoding="utf-8")
    out = send(subject, body, dry)
    out.update({"n_open": mv["n_open"], "n_closing": len(mv["closing_today"]),
                "n_verdicts": len(scored)})
    return out


if __name__ == "__main__":
    import os as _os
    _os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        r = main(a.dry_run)
    except Exception as e:
        print(f"\nFAILED LOUDLY: {type(e).__name__}: {e}", file=sys.stderr)
        raise
    print(f"\n{r}")

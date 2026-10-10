"""
run_live_l.py — the NSE+BSE exchange-access PROBE. **No longer a scheduled job.**

Retired from the schedule on 2026-10-03 (Priority 1c). It is kept, not deleted, because
the moment NSE answers the access request this is the two-source reconciled pipeline that
H14 says becomes primary — with Chittorgarh demoted to corroborator. Deleting it would
mean rebuilding it from scratch to collect on that.

Why it was retired
------------------
It reads NSE (connection reset / read timeout for this project's User-Agent) and BSE (403
even on its own robots.txt), so it has never captured a single row. Worse, it wrote its
report to the SAME path as the working Chittorgarh pipeline — `reports/live/<date>.md` —
so on 2 Oct its failing 21:49 run overwrote the good report that had been produced minutes
earlier. A pipeline that cannot fetch anything was destroying the output of one that can.

Two things changed:
  * its reports now go to `reports/live/exchange_probe/<date>.md`, which nothing else
    writes and no email reads;
  * the 15:00 and 19:30 schedules both call `send_daily_email.py` instead. See
    LIVE_SETUP.md for the mapping of schedule to script.

`--notify` is gone with the schedule: the email IS the notification now, sent by
`send_daily_email.py` at the 15:00 leg.

**Run this by hand to test whether the exchanges have started answering.** It invents
nothing when they refuse; a run reporting "no subscription could be fetched" is the probe
working correctly.

    python run_live_l.py --probe        try both exchanges now, write the probe report
    python run_live_l.py --rehearse     exercise scoring/report contract without fetching

**GMP is never fetched** (D1). **No browser User-Agent is ever sent** (rule 3).
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import sys
import time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import score_l as ML               # noqa: E402  — portable JSON, no joblib
import predictions_log as PL       # noqa: E402
import live_markers as LM          # noqa: E402

SNAPSHOTS = ROOT / "data" / "subscription_snapshots.csv"
# Priority 1c: a path of its own. Nothing else writes here and no email reads it,
# so this probe can never again overwrite the Chittorgarh report.
LIVE_DIR = ROOT / "reports" / "live" / "exchange_probe"
TOL = 0.05                         # rule 2
CUTOFF = "4:00 PM"                 # Paytm Money, user-confirmed (E1)
UA = {"User-Agent": "ipo-agent/1.0 (personal research; contact ashishkohar4@gmail.com)",
      "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}

SNAP_COLS = ["ipo", "isin", "timestamp_ist", "capture_point", "qib_x", "hni_x", "rii_x",
             "total_x", "source", "reconciled", "note"]

STANDING_CAVEAT = (
    "3pm figures understate final demand — institutional bids concentrate in the last hours, "
    "and this model is trained on final-day subscription. A near-threshold \"no\" should be "
    "treated as UNCERTAIN, not as a negative verdict. The size of the gap is not yet "
    "measured; the 19:30 day-end capture is accumulating the data that will measure it.")


# ---------------------------------------------------------------- official APIs
def _session():
    import requests
    s = requests.Session()
    s.headers.update(UA)
    try:
        s.get("https://www.nseindia.com/", timeout=20)
    except Exception:
        pass
    return s


def nse_open_ipos(sess) -> tuple[list[dict], str]:
    """Live IPOs from NSE's official issue-information API."""
    try:
        r = sess.get("https://www.nseindia.com/api/ipo-current-issue", timeout=30)
        if r.status_code != 200:
            return [], f"NSE HTTP {r.status_code}"
        data = r.json() or []
        out = []
        for d in (data if isinstance(data, list) else data.get("data", [])):
            out.append({"ipo": d.get("companyName") or d.get("symbol"),
                        "symbol": d.get("symbol"), "isin": d.get("isin"),
                        "closes": d.get("biddingEndDate") or d.get("endDate"),
                        "issue_size_cr": None, "source": "nse_official"})
        return out, f"NSE returned {len(out)}"
    except Exception as e:
        return [], f"NSE {type(e).__name__}: {e}"


def nse_subscription(sess, symbol: str) -> dict:
    """Category-wise subscription from NSE's official active-category API."""
    try:
        r = sess.get("https://www.nseindia.com/api/ipo-active-category",
                     params={"symbol": symbol}, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "why": f"HTTP {r.status_code}"}
        rows = (r.json() or {}).get("data") or r.json() or []
        got = {}
        for d in (rows if isinstance(rows, list) else []):
            cat = str(d.get("category", "")).upper()
            x = d.get("noOfshareBid") and d.get("noOfSharesOffered")
            sub = d.get("subscriptionTimes") or d.get("subscription")
            if sub is None and x:
                sub = float(d["noOfshareBid"]) / float(d["noOfSharesOffered"])
            if sub is None:
                continue
            sub = float(sub)
            if "QIB" in cat or "QUALIFIED" in cat:
                got["qib_x"] = sub
            elif "NON INST" in cat or "NII" in cat or "HNI" in cat:
                got["hni_x"] = sub
            elif "RETAIL" in cat or "INDIVIDUAL" in cat:
                got["rii_x"] = sub
            elif cat.startswith("TOTAL"):
                got["total_x"] = sub
        if not got:
            return {"ok": False, "why": "no category rows"}
        got["source"] = "nse_official"
        got["ok"] = True
        return got
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def bse_subscription(sess, scrip: str | None) -> dict:
    """BSE's official IPO demand API — the independent second source for rule 2."""
    if not scrip:
        return {"ok": False, "why": "no BSE scrip code"}
    try:
        r = sess.get("https://api.bseindia.com/BseIndiaAPI/api/GetIPODemandSchedule/w",
                     params={"scripcode": str(scrip)},
                     headers={**UA, "Referer": "https://www.bseindia.com/"}, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "why": f"HTTP {r.status_code}"}
        rows = r.json() or []
        got = {}
        for d in (rows if isinstance(rows, list) else rows.get("Table", [])):
            cat = str(d.get("Category", "")).upper()
            sub = d.get("SubscriptionTimes") or d.get("NoofTimes")
            if sub is None:
                continue
            sub = float(sub)
            if "QIB" in cat:
                got["qib_x"] = sub
            elif "NII" in cat or "NON" in cat:
                got["hni_x"] = sub
            elif "RETAIL" in cat or "RII" in cat:
                got["rii_x"] = sub
            elif cat.startswith("TOTAL"):
                got["total_x"] = sub
        if not got:
            return {"ok": False, "why": "no category rows"}
        got["source"] = "bse_official"
        got["ok"] = True
        return got
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def reconcile(a: dict, b: dict) -> dict:
    """Rule 2 across the two official sources, per category.

    A category present in only one source is kept but flagged `single_source_unverified`
    (global rule 3). A pairwise relative difference above 5% makes it NULL with both values
    logged — because feeding a wrong Total straight into the only feature the model has is
    the single worst failure available to this pipeline.
    """
    out, notes, recon = {}, [], []
    for k in ("qib_x", "hni_x", "rii_x", "total_x"):
        va, vb = a.get(k) if a.get("ok") else None, b.get(k) if b.get("ok") else None
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            out[k] = va if va is not None else vb
            recon.append(f"{k}=single_source")
            continue
        hi = max(abs(va), abs(vb)) or 1.0
        diff = abs(va - vb) / hi
        if diff > TOL:
            out[k] = None
            recon.append(f"{k}=MISMATCH")
            notes.append(f"{k}: NSE {va:.2f} vs BSE {vb:.2f} differ {diff*100:.1f}% -> NULL")
        else:
            out[k] = round((va + vb) / 2, 4)
            recon.append(f"{k}=PASS")
    out["source"] = "+".join(s for s in (a.get("source") if a.get("ok") else None,
                                         b.get("source") if b.get("ok") else None) if s)
    out["reconciled"] = ";".join(recon)
    out["note"] = "; ".join(notes)
    return out


def append_snapshot(rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame([{c: r.get(c) for c in SNAP_COLS} for r in rows], columns=SNAP_COLS)
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOTS, mode="a", header=not SNAPSHOTS.exists(), index=False,
              encoding="utf-8")


# ---------------------------------------------------------------- the report
def write_report(scored: list[dict], when: pd.Timestamp, diag: list[str]) -> Path:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = LIVE_DIR / f"{when.date()}.md"
    L = [f"# IPO report — {when.date()} (scored {when.strftime('%H:%M')} IST)", "",
         f"**Decide before your broker's {CUTOFF} cutoff.**", "",
         f"> {STANDING_CAVEAT}", ""]
    if not scored:
        L += ["No IPO closes today, so there is nothing to decide.", "",
              "### Diagnostics", ""] + [f"- {d}" for d in diag]
        path.write_text("\n".join(L) + "\n", encoding="utf-8")
        return path
    for s in scored:
        r, i = s["result"], s["result"]["inputs"]
        L += [f"## {s['ipo']} — closing {s.get('closes') or 'today'}", "",
              "```",
              f"{ML.DECISION_POINT}  L1: {r['L1']['verdict']:<4s}  ({r['L1']['threshold_met']})",
              f"{' ' * len(ML.DECISION_POINT)}  L2: {r['L2']['verdict']:<4s}  "
              f"({r['L2']['threshold_met']})",
              "```", "",
              f"- **Subscription** [{s['capture_point']}]: Total {i.get('total')}x | "
              f"QIB {i.get('qib')}x | HNI {i.get('hni')}x | Retail {i.get('rii')}x",
              f"- **Source**: {s.get('source')} — reconciliation `{s.get('reconciled')}`",
              f"- **Demand profile**: {r['demand_profile']}   "
              f"*[NOT IN MODEL — context only, per H3]*",
              f"- **Veto flags**: {s.get('veto_flags') or 'none (no RHP data for this issue)'}",
              "- **GMP**: `____%`   *[NOT IN MODEL — your judgement only, per D1. "
              "Whatever you write here is logged so its value can be measured after ~12 "
              "months, per D2.]*", ""]
        if s.get("note"):
            L += [f"- Reconciliation notes: {s['note']}", ""]
    L += ["---", "", "### Diagnostics", ""] + [f"- {d}" for d in diag]
    L += ["", f"Model `{ML.MODEL_ID}` / `{ML.DECISION_POINT}`. Verdicts are the threshold "
              "met, never a probability (G2)."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- entry points
# Priority 1f: the marker logic moved to live_markers.py so both legs of a day share one
# implementation, and so a run that captured ZERO rows no longer locks out its retry.
already_ran, mark_ran = LM.already_ran, LM.mark_ran
MARKERS = LM.MARKERS


def capture(capture_point: int, score: bool, dry: bool = False) -> dict:
    when = pd.Timestamp.now()
    if not dry and already_ran(capture_point, when):
        out = {"when": str(when), "capture_point": capture_point, "skipped": True,
               "reason": (f"a {capture_point} capture is already recorded for "
                          f"{when.date()} — this run is a no-op by design (idempotent)")}
        print(json.dumps(out, indent=2))
        return out
    sess = _session()
    ipos, why = nse_open_ipos(sess)
    diag = [f"open-IPO lookup: {why}"]
    sym = pd.read_csv(ROOT / "data" / "master_with_symbols.csv")

    snaps, scored = [], []
    for d in ipos:
        time.sleep(1.0)
        a = nse_subscription(sess, d.get("symbol"))
        m = sym[sym["symbol"] == d.get("symbol")]
        scrip = m["bse_code"].iloc[0] if len(m) and "bse_code" in m else None
        b = bse_subscription(sess, scrip)
        rec = reconcile(a, b)
        if not rec.get("source"):
            diag.append(f"{d['ipo']}: no subscription from either source "
                        f"(NSE: {a.get('why')} | BSE: {b.get('why')})")
            continue
        snap = {"ipo": d["ipo"], "isin": d.get("isin"),
                "timestamp_ist": str(when), "capture_point": capture_point, **rec}
        snaps.append(snap)
        if score and rec.get("total_x"):
            res = ML.predict_live(total=rec["total_x"],
                                  qib=rec.get("qib_x"), rii=rec.get("rii_x"))
            res["inputs"]["hni"] = rec.get("hni_x")
            scored.append({"ipo": d["ipo"], "isin": d.get("isin"), "closes": d.get("closes"),
                           "capture_point": capture_point, "result": res,
                           "source": rec.get("source"), "reconciled": rec.get("reconciled"),
                           "note": rec.get("note")})
        elif score:
            diag.append(f"{d['ipo']}: NO CALL — Total subscription did not reconcile, so the "
                        "model's only input is NULL. Refusing to score (rule 2).")

    if not dry:
        append_snapshot(snaps)
        for s in scored:
            PL.log_prediction(s["ipo"], s["isin"], s["result"],
                              capture_point=capture_point, source=s["source"])
        mark_ran(capture_point, when, len(snaps))
    path = write_report(scored, when, diag) if score else None
    out = {"when": str(when), "capture_point": capture_point, "n_ipos": len(ipos),
           "n_snapshots": len(snaps), "n_scored": len(scored), "report": str(path) if path
           else None, "diagnostics": diag, "dry_run": dry}
    print(json.dumps(out, indent=2))
    return out


def rehearse(days: int = 30, dry: bool = True) -> dict:
    """Dry run on the most recent IPOs when none are open (PLAN Stage 6 step 9).

    Scores real IPOs from the master dataset, whose FINAL subscription we already hold, and
    writes the full report. It exercises everything except the two official fetches —
    feature building, calibration, thresholds, the demand-profile label, the report contract
    and the prediction log. It is explicitly labelled a rehearsal: the figures are final-day,
    not 15:00, so the verdicts are what the model would have said with perfect information,
    not what it would have said at 3pm.
    """
    when = pd.Timestamp.now()
    m = pd.read_csv(ROOT / "data" / "master_with_symbols.csv")
    m["ld"] = pd.to_datetime(m["listing_date"], errors="coerce")
    recent = m[m["ld"].notna()].sort_values("ld", ascending=False).head(5)
    scored, diag = [], [
        f"REHEARSAL on the {len(recent)} most recently listed IPOs — no IPO is open today.",
        "Subscription figures are FINAL-DAY from the master dataset, not a 15:00 capture, "
        "so these verdicts show what the model says with full information. At 3pm the same "
        "IPOs would score LOWER (see the standing caveat).",
    ]
    for r in recent.itertuples():
        tot = pd.to_numeric(pd.Series([r.Total]), errors="coerce").iloc[0]
        if pd.isna(tot):
            diag.append(f"{r.company}: NO CALL — Total subscription missing")
            continue
        res = ML.predict_live(total=float(tot),
                              qib=float(r.QIB) if pd.notna(r.QIB) else None,
                              rii=float(r.RII) if pd.notna(r.RII) else None)
        res["inputs"]["hni"] = float(r.HNI) if pd.notna(r.HNI) else None
        scored.append({"ipo": r.company, "isin": r.isin,
                       "closes": f"listed {r.ld.date()} (rehearsal)",
                       "capture_point": "FINAL (rehearsal)", "result": res,
                       "source": "master dataset", "reconciled": "n/a (rehearsal)",
                       "note": ""})
    if not dry:
        for s in scored:
            PL.log_prediction(s["ipo"], s["isin"], s["result"], capture_point=0,
                              source="REHEARSAL — master dataset, final-day figures")
    path = write_report(scored, when, diag)
    out = {"mode": "rehearse", "n_scored": len(scored), "report": str(path),
           "dry_run": dry}
    print(json.dumps(out, indent=2))
    print("\n" + "=" * 78 + "\n" + path.read_text(encoding="utf-8"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", "--score", dest="probe", action="store_true",
                    help="try both exchanges now and write the probe report")
    ap.add_argument("--final", action="store_true", help="capture only, no scoring")
    ap.add_argument("--rehearse", action="store_true",
                    help="dry run on the most recent IPOs when none are open")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.rehearse:
        return rehearse(dry=a.dry_run)
    if a.final:
        return capture(1930, score=False, dry=a.dry_run)
    return capture(1500, score=True, dry=a.dry_run)


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

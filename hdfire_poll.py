"""
hdfire_poll.py — Task 9: does NSE publish subscription intraday, or only at 19:00?

The question
------------
H22 made NSE `api/ipo-active-category` the primary subscription source, behind a freshness
gate, **provisionally**. The gate exists because one thing is unknown: every *closed* issue
shows a single `updateTime` of 19:00 on its final bidding day, which is equally consistent
with "published once at 19:00" and with "updated all day, and 19:00 is simply the last
one". Those two possibilities have opposite consequences for a 15:00 decision, and no
amount of looking at closed issues can separate them.

Only a **live** mainboard issue can. Confirmed from NSE's own calendar on 2026-10-08:

| | symbol | series | window |
|---|---|---|---|
| **HD Fire Protect Limited** | `HDFIRE` | **EQ → mainboard** | **13–15 Oct 2026** |
| Ravita Engineering Services | `RAVITA` | SME | 13–15 Oct 2026 |

`RAVITA` is polled too, as a control: it is SME over the same window, so if NSE's EQ book
behaves differently from its SME book that will show up side by side rather than being
mistaken for a date effect.

What it records
---------------
Four polls a day — nominally 11:00, 13:00, 15:00 and 17:30 IST — of **both** sources, with
≥3 s between requests. Every row carries the **real** poll time, not the nominal slot,
because the nominal slot is not reliable (see below). Appends to
`data/hdfire_poll.csv`; append-only, so a re-run adds rows rather than replacing them.

Per poll, per source: Total, QIB, HNI, RII, and for NSE the `updateTime` from the payload
itself. That last field is the actual evidence: if it advances between the 11:00 and the
15:00 poll, NSE publishes intraday and can carry the live decision. If it stays absent or
pinned to a single time, it cannot, and H22 must be reduced to an archival and
verification role.

A warning about the trigger
---------------------------
**A GitHub `schedule` cron cannot be trusted to land near its nominal time in this repo.**
Measured over nine scheduled runs, 2–8 Oct, the delay was **5h31m to 9h06m** — a job due at
09:30 UTC started between 15:53 and 18:36 UTC. A poll meant for 11:00 IST would arrive in
the evening and the whole test would answer the wrong question. So:

* the four crons below are a **backstop**, not the plan;
* the real trigger is an external one (cron-job.org, per `LIVE_SETUP.md`) or a manual
  `workflow_dispatch`;
* and every row records the real time, so a drifted poll is still usable data rather than
  a mislabelled row.

    python hdfire_poll.py --label 1500
    python hdfire_poll.py --label manual --symbols HDFIRE,RAVITA
    python hdfire_poll.py --report
    python hdfire_poll.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import nse_subscription as NSE                               # noqa: E402
import trading_day as TD                                     # noqa: E402

OUT = ROOT / "data" / "hdfire_poll.csv"
REPORT = ROOT / "reports" / "HDFIRE_INTRADAY.md"

COLS = ["trading_date", "polled_at_ist", "nominal_slot", "symbol", "series", "source",
         "total_x", "qib_x", "hni_x", "rii_x", "nse_update_time", "gate_ok", "note"]

# Confirmed from NSE's own api/all-upcoming-issues on 2026-10-08, not assumed.
SUBJECTS = [("HDFIRE", "EQ", "HD Fire Protect Limited", "mainboard"),
            ("RAVITA", "SME", "Ravita Engineering Services Limited", "sme (control)")]
WINDOW = ("2026-10-13", "2026-10-15")
SLOTS = (1100, 1300, 1500, 1730)


def in_window(day=None) -> bool:
    d = pd.Timestamp(day).normalize() if day is not None else TD.trading_date()
    return pd.Timestamp(WINDOW[0]) <= d <= pd.Timestamp(WINDOW[1])


def _append(rows: list[dict]) -> None:
    if not rows:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{c: r.get(c) for c in COLS} for r in rows], columns=COLS).to_csv(
        OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")


def poll_nse(symbol: str, series: str, f: NSE.Fetcher) -> dict:
    """Raw parse plus the gate verdict. The gate is RECORDED, never used to drop a row:
    a gate failure is the most informative outcome this test can produce."""
    if not f.warm():
        return {"source": "nse_active_category", "note": "warm-up/robots check failed"}
    payload, note = f.get_json(f"{NSE.ENDPOINT}?symbol={symbol}&series={series}")
    if payload is None:
        return {"source": "nse_active_category", "note": f"fetch failed: {note}"}
    p = NSE.parse(payload)
    ok, why = NSE.gate(p, symbol)
    return {"source": "nse_active_category", "total_x": p.get("total"),
            "qib_x": p.get("qib"), "hni_x": p.get("hni"), "rii_x": p.get("rii"),
            "nse_update_time": p.get("raw_update_time"), "gate_ok": bool(ok),
            "note": "" if ok else why}


def poll_chittorgarh(name: str) -> dict:
    """The same issue from Chittorgarh, for the per-poll difference between the two."""
    try:
        import chittorgarh_live as CL
        mv = CL.market_view()
        key = "".join(ch for ch in name.lower() if ch.isalnum())[:14]
        for r in mv.get("closing_today", []) + mv.get("open_not_closing", []):
            k = "".join(ch for ch in str(r.get("ipo", "")).lower() if ch.isalnum())
            if k.startswith(key[:10]) or key.startswith(k[:10]):
                s = r.get("sub", {}) or {}
                return {"source": "chittorgarh", "total_x": s.get("total_x"),
                        "qib_x": s.get("qib_x"), "hni_x": s.get("hni_x"),
                        "rii_x": s.get("rii_x"),
                        "note": "" if s.get("ok") else str(s.get("why") or "no figure")}
        return {"source": "chittorgarh", "note": "not on the Chittorgarh dashboard"}
    except Exception as e:                                   # noqa: BLE001
        return {"source": "chittorgarh", "note": f"{type(e).__name__}: {str(e)[:70]}"}


def poll(label: str = "manual", symbols: list[str] | None = None,
         force: bool = False) -> list[dict]:
    day = TD.trading_date()
    now = TD.ist_now()
    if not force and not in_window(day):
        print(f"{day.date()} is outside the HDFIRE window {WINDOW[0]}..{WINDOW[1]} — "
              f"nothing polled. (--force to poll anyway.)")
        return []
    want = [s.strip().upper() for s in (symbols or [])] or None
    subjects = [s for s in SUBJECTS if want is None or s[0] in want]

    f = NSE.Fetcher()
    rows = []
    for sym, series, name, kind in subjects:
        base = {"trading_date": str(day.date()), "polled_at_ist": str(now),
                "nominal_slot": label, "symbol": sym, "series": series}
        n = poll_nse(sym, series, f)
        rows.append({**base, **n})
        c = poll_chittorgarh(name)
        rows.append({**base, **c})
        print(f"  {sym:8s} {kind:16s} NSE total={n.get('total_x')} "
              f"update={n.get('nse_update_time')!r} gate={n.get('gate_ok')} "
              f"{n.get('note','')[:40]}")
        print(f"  {'':8s} {'':16s} CG  total={c.get('total_x')} {c.get('note','')[:40]}")
    _append(rows)
    print(f"{chr(10)}{len(rows)} rows appended to {OUT.name}")
    return rows


def report() -> str:
    """Update frequency per source, NSE-vs-Chittorgarh per poll, 15:00-to-final growth."""
    L = ["# HDFIRE intraday test — Task 9", "",
         f"Does NSE's `ipo-active-category` publish during the bidding day, or only at "
         f"19:00? Subjects: **HDFIRE** (EQ, mainboard) and **RAVITA** (SME, control), "
         f"both bidding {WINDOW[0]} to {WINDOW[1]}, confirmed from NSE's own calendar.", ""]
    if not OUT.exists():
        L += ["**No polls recorded yet.** The window has not started, or the poller has "
              "not run. Nothing is inferred from an empty file."]
        return chr(10).join(L) + chr(10)
    d = pd.read_csv(OUT)
    L += [f"`{len(d)}` rows recorded.", "",
          "## Every poll, as recorded", "",
          "| trading date | polled at (real) | slot | symbol | source | Total | QIB | HNI "
          "| RII | NSE updateTime | gate |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        f2 = lambda v: "—" if pd.isna(v) else f"{float(v):.2f}x"     # noqa: E731
        L.append(f"| {r.trading_date} | {str(r.polled_at_ist)[:19]} | {r.nominal_slot} "
                 f"| {r.symbol} | {r.source} | {f2(r.total_x)} | {f2(r.qib_x)} "
                 f"| {f2(r.hni_x)} | {f2(r.rii_x)} | {r.nse_update_time} "
                 f"| {r.gate_ok} |")

    L += ["", "## Did NSE's updateTime advance within a day?", "",
          "This is the whole test. An advancing `updateTime` means NSE publishes intraday "
          "and can carry the 15:00 decision; a single pinned value means it cannot.", "",
          "| trading date | symbol | distinct NSE updateTimes | values |",
          "|---|---|---|---|"]
    n = d[d["source"] == "nse_active_category"]
    for (day, sym), g in n.groupby(["trading_date", "symbol"]):
        vals = [str(x) for x in g["nse_update_time"].dropna().unique()]
        L.append(f"| {day} | {sym} | **{len(vals)}** | {'; '.join(vals) or '—'} |")

    L += ["", "## NSE versus Chittorgarh, per poll", "",
          "| trading date | slot | symbol | NSE Total | Chittorgarh Total | difference |",
          "|---|---|---|---|---|---|"]
    for (day, slot, sym), g in d.groupby(["trading_date", "nominal_slot", "symbol"]):
        a = g[g["source"] == "nse_active_category"]["total_x"]
        b = g[g["source"] == "chittorgarh"]["total_x"]
        av = None if a.empty or pd.isna(a.iloc[0]) else float(a.iloc[0])
        bv = None if b.empty or pd.isna(b.iloc[0]) else float(b.iloc[0])
        diff = ("—" if av is None or bv is None
                else f"{av - bv:+.2f}x ({100 * (av - bv) / bv:+.1f}%)" if bv
                else f"{av:+.2f}x vs 0")
        L.append(f"| {day} | {slot} | {sym} "
                 f"| {'—' if av is None else f'{av:.2f}x'} "
                 f"| {'—' if bv is None else f'{bv:.2f}x'} | {diff} |")

    L += ["", "## 15:00 to final growth (H23's unmeasured quantity)", "",
          "| trading date | symbol | 15:00 Total | last poll Total | growth |",
          "|---|---|---|---|---|"]
    for (day, sym), g in d[d["source"] == "nse_active_category"].groupby(
            ["trading_date", "symbol"]):
        at15 = g[g["nominal_slot"].astype(str) == "1500"]["total_x"]
        last = g.sort_values("polled_at_ist")["total_x"].dropna()
        a = None if at15.empty or pd.isna(at15.iloc[0]) else float(at15.iloc[0])
        b = None if last.empty else float(last.iloc[-1])
        gr = "—" if (a is None or b is None or a <= 0) else f"{b / a:.2f}x ({100*(b/a-1):+.1f}%)"
        L.append(f"| {day} | {sym} | {'—' if a is None else f'{a:.2f}x'} "
                 f"| {'—' if b is None else f'{b:.2f}x'} | {gr} |")

    L += ["", "## Verdict on H22", "",
          "**Not yet decided — this is filled in after 15 October.** The decision rule: if "
          "`updateTime` advances within a bidding day on HDFIRE, confirm H22 and let NSE "
          "carry the live 15:00 decision. If it does not, H22 is reduced to an archival "
          "and verification role and Chittorgarh stays primary for the live figure. The "
          "freshness gate already makes either outcome safe.", ""]
    return chr(10).join(L) + chr(10)


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

    print("[1] the subjects were confirmed from NSE, and one is a control")
    syms = [s[0] for s in SUBJECTS]
    chk("HDFIRE is a subject", "HDFIRE" in syms)
    chk("it is EQ, i.e. mainboard",
        [s[1] for s in SUBJECTS if s[0] == "HDFIRE"] == ["EQ"])
    chk("RAVITA is polled as an SME control", "RAVITA" in syms)
    chk("the window is 13-15 Oct 2026", WINDOW == ("2026-10-13", "2026-10-15"))
    chk("four slots a day", SLOTS == (1100, 1300, 1500, 1730))

    print("\n[2] the real poll time is always recorded, not just the nominal slot")
    chk("polled_at_ist is a column", "polled_at_ist" in COLS)
    chk("and so is the nominal slot, separately", "nominal_slot" in COLS)
    import inspect
    src = inspect.getsource(poll)
    chk("the real time comes from the IST clock", "TD.ist_now()" in src)

    print("\n[3] NSE's own updateTime is captured - it IS the evidence")
    chk("nse_update_time is a column", "nse_update_time" in COLS)
    nsrc = inspect.getsource(poll_nse)
    chk("the RAW string is stored, not a parsed guess",
        'p.get("raw_update_time")' in nsrc)
    chk("the gate verdict is recorded, not used to drop the row",
        '"gate_ok": bool(ok)' in nsrc and "return None" not in nsrc)

    print("\n[4] nothing is polled outside the window without --force")
    chk("a date before the window is refused", in_window("2026-10-12") is False)
    chk("the first day is in", in_window("2026-10-13") is True)
    chk("the last day is in", in_window("2026-10-15") is True)
    chk("a date after is refused", in_window("2026-10-16") is False)

    print("\n[5] ipo-detail is not used here either (H22)")
    body = "".join(inspect.getsource(x) for x in (poll, poll_nse, poll_chittorgarh))
    chk("no ipo-detail URL", "ipo-detail" not in body)
    chk("the endpoint comes from nse_subscription, not retyped", "NSE.ENDPOINT" in body)

    print("\n[6] an empty file infers nothing")
    chk("the report says so rather than printing zeros",
        "Nothing is inferred from an empty file" in inspect.getsource(report))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="manual", help="nominal slot, e.g. 1100")
    ap.add_argument("--symbols", default="", help="comma-separated; default both subjects")
    ap.add_argument("--force", action="store_true", help="poll outside the window")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report(), encoding="utf-8")
        print(f"written {REPORT}")
        raise SystemExit(0)
    poll(a.label, [s for s in a.symbols.split(",") if s.strip()], a.force)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report(), encoding="utf-8")
    print(f"written {REPORT}")

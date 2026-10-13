"""
watch_progress.py — read-only progress for the SEBI download / RHP extraction chain.

Double-click `watch_progress.bat`, or run `python watch_progress.py`. It reads files and
asks Windows for a process list. **It writes nothing except its own small state file and
never touches the running job**, so it is safe to run as often as you like.

Why a state file: the extraction output carries no timestamp column, and the job must not
be restarted to add one. So each run records `(companies done, time)` in
`data/.watch_state.json` and the next run computes the rate between the two. The first run
therefore shows a count but no ETA - run it again a minute later and it will.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
PDF_DIR = ROOT / "_local" / "rhp_valuation"
FETCH = DATA / "rhp_valuation_fetch.csv"
VALUES = DATA / "rhp_valuation_values.csv"
STATE = DATA / ".watch_state.json"
STALL_MIN = 15


def _now() -> float:
    return time.time()


def ist() -> str:
    import datetime
    import zoneinfo
    return datetime.datetime.now(
        zoneinfo.ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")


def chain_processes() -> list[dict]:
    """The python processes that belong to THIS chain, by command line.

    Matched on `rhp_valuation.py`, so the laptop's other python processes - a `main.py`
    and a telegram bot were both running alongside it - are never reported as part of the
    chain and never look like something to stop.
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object ProcessId,CommandLine,CreationDate | ConvertTo-Json -Depth 3"],
            capture_output=True, text=True, timeout=60).stdout
        rows = json.loads(out) if out.strip() else []
        if isinstance(rows, dict):
            rows = [rows]
    except Exception:                                          # noqa: BLE001
        return []
    mine = []
    for r in rows:
        cl = str(r.get("CommandLine") or "")
        if "rhp_valuation.py" in cl:
            stage = ("extract" if "--stage extract" in cl
                     else "fetch" if "--stage fetch" in cl else "?")
            mine.append({"pid": r.get("ProcessId"), "stage": stage, "cmd": cl.strip()})
    return mine


def counts() -> dict:
    import pandas as pd
    from extract.valuation import VALUATION_VERSION as V
    n_pdf = len(list(PDF_DIR.glob("*.pdf"))) if PDF_DIR.exists() else 0
    fetched = total = 0
    if FETCH.exists():
        try:
            f = pd.read_csv(FETCH, low_memory=False, on_bad_lines="skip")
            fetched = int(f["status"].astype(str).str.startswith("ok").sum())
            total = len(f)
        except Exception:                                      # noqa: BLE001
            pass
    # Per VERSION, not just the current one. A pass that is running loaded the module at
    # launch, so it keeps stamping the version it started with - and when the code is
    # bumped mid-run, a watcher that counted only the new version showed "0 of 412" while
    # a pass was 90 documents in. Useless exactly when it is most wanted.
    by_ver: dict[str, dict] = {}
    if VALUES.exists():
        try:
            # on_bad_lines="skip": the file is being APPENDED to while this reads, so the
            # last line can be half-written. Skipping it is right - it will be complete
            # the next time this runs.
            d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
            for ver, g in d.groupby(d["extractor_version"].astype(str)):
                by_ver[str(ver)] = {"companies": g["company"].nunique(),
                                    "rows": len(g),
                                    "ok": int((g["status"] == "ok").sum())}
        except Exception:                                      # noqa: BLE001
            pass
    return {"pdfs": n_pdf, "fetched": fetched, "fetch_total": total,
            "by_ver": by_ver, "version": V, "target": fetched or total}


def rate_and_eta(by_ver: dict, target: int) -> tuple[str, str, str]:
    """Rate on whichever version GREW since the last run - that is the pass in flight."""
    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            prev = {}
    now = _now()
    cur = {v: g["companies"] for v, g in by_ver.items()}
    try:
        STATE.write_text(json.dumps({"ver": cur, "t": now}), encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass
    old_ver = prev.get("ver") or {}
    if not old_ver:
        return "", "(run again in a minute for a rate)", ""
    grew = [(v, cur.get(v, 0) - old_ver.get(v, 0)) for v in cur]
    grew = [g for g in grew if g[1] > 0]
    if not grew:
        active = max(cur, key=lambda v: cur[v]) if cur else ""
        mins = (now - float(prev["t"])) / 60
        if mins >= STALL_MIN:
            return active, f"NO PROGRESS in {mins:.0f} min - looks STALLED", ""
        return active, f"no new document in {mins:.0f} min (still working on one)", ""
    ver, dd = max(grew, key=lambda g: g[1])
    done = cur[ver]
    dt = now - float(prev["t"])
    if dt <= 0:
        return ver, "(no elapsed time)", ""
    per = dt / dd
    left = max(target - done, 0)
    eta_min = left * per / 60
    return (ver, f"{per:.0f} s/document",
            f"{left} left, about {eta_min:.0f} min ({eta_min / 60:.1f} h)")


def main() -> int:
    print("=" * 66)
    print(f"  IPO agent - RHP chain progress      {ist()}")
    print("=" * 66)
    procs = chain_processes()
    if procs:
        for p in procs:
            print(f"  RUNNING   stage={p['stage']}   PID {p['pid']}")
    else:
        print("  NOT RUNNING - no python process has rhp_valuation.py on its command line")

    c = counts()
    print()
    print(f"  PDFs on disk        {c['pdfs']}")
    print(f"  downloaded ok       {c['fetched']} of {c['fetch_total']} attempted")
    if not c["by_ver"]:
        print("  extracted           nothing yet")
    for ver in sorted(c["by_ver"]):
        g = c["by_ver"][ver]
        tag = "  <- target" if ver == c["version"] else ""
        print(f"  extractor {ver:<8s}  {g['companies']:4d} of {c['target']} documents, "
              f"{g['rows']:6d} rows, {g['ok']:6d} with a value{tag}")
    active, r, eta = rate_and_eta(c["by_ver"], c["target"])
    if active:
        print(f"  pass in flight      extractor {active}")
    print(f"  rate                {r}")
    if eta:
        print(f"  remaining           {eta}")
    print()
    print(f"  PDF folder          {PDF_DIR}")
    print(f"  growing file        {VALUES}")
    print("=" * 66)
    other = [p for p in procs if p["stage"] == "?"]
    if other:
        print("  note: a chain process with an unrecognised stage is listed above")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
sent_markers.py — Task 4: did the bid email for this IPO, on this date, actually go out?

The problem
-----------
There are now four scheduled attempts at the 15:00 email (08:45, 09:00, 09:15 and 09:30
UTC), plus `workflow_dispatch`, plus whatever an external trigger adds. Without a record of
what was sent, four attempts means up to four identical emails. With one, the first attempt
that succeeds sends and the rest exit green having done nothing.

Why a separate file from `live_run_markers.csv`
-----------------------------------------------
That file answers "did this *slot* capture anything?". This one answers "did the decision
for *this IPO* reach the user?". They come apart in both directions, and the difference
matters:

* a run can capture snapshots for three IPOs and fail to send — slot marked, nothing
  delivered;
* a run can find nothing new to capture and still legitimately re-send nothing, because the
  email already went out an hour earlier.

Keying by IPO and date rather than by run is what makes the second attempt of the day able
to tell "already delivered" from "never delivered". A per-day marker alone would not: two
IPOs can close on the same date, one covered by an earlier send and one added later.

Append-only, like every other log here (rule 10). A re-send is a new row, never an edit, so
the file is also the delivery history.

    python sent_markers.py --show
    python sent_markers.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import hashlib
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

MARKERS = ROOT / "data" / "sent_markers.csv"
COLS = ["key", "date", "ipo", "isin", "subject", "kind", "sent_at_ist",
        "capture_point", "recipient_set", "note"]

# `kind` values. A dead-man notice is recorded so a later run does not send a second one,
# but it must NEVER satisfy "was the decision delivered?" — it is the opposite of that.
DECISION = "decision"
DEAD_MAN = "not_sent_notice"


def key(date, ipo: str) -> str:
    k = f"{pd.Timestamp(date).date()}|{str(ipo).strip().lower()}"
    return hashlib.sha1(k.encode("utf-8")).hexdigest()[:16]


def read(path: Path | None = None) -> pd.DataFrame:
    p = path or MARKERS
    if not p.exists():
        return pd.DataFrame(columns=COLS)
    try:
        d = pd.read_csv(p)
    except Exception:                                        # noqa: BLE001
        return pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in d:
            d[c] = None
    return d[COLS]


def already_sent(date, ipo: str, path: Path | None = None) -> bool:
    """True only if the DECISION email for this IPO and date went out.

    A dead-man notice does not count. That distinction is the whole point: if a
    `not_sent_notice` satisfied this check, the next day's logic would believe the decision
    had been delivered when what was delivered was the news that it had not been.
    """
    d = read(path)
    if d.empty:
        return False
    hit = d[(d["key"].astype(str) == key(date, ipo)) & (d["kind"] == DECISION)]
    return bool(len(hit))


def notice_sent(date, ipo: str, path: Path | None = None) -> bool:
    """True if a dead-man notice already went out for this IPO and date."""
    d = read(path)
    if d.empty:
        return False
    hit = d[(d["key"].astype(str) == key(date, ipo)) & (d["kind"] == DEAD_MAN)]
    return bool(len(hit))


def mark(date, ipo: str, isin: str | None, subject: str, when,
         kind: str = DECISION, capture_point: int = 1500,
         recipient_set: str = "", note: str = "", path: Path | None = None) -> None:
    p = path or MARKERS
    row = pd.DataFrame([{
        "key": key(date, ipo), "date": str(pd.Timestamp(date).date()), "ipo": ipo,
        "isin": isin, "subject": subject, "kind": kind, "sent_at_ist": str(when),
        "capture_point": capture_point, "recipient_set": recipient_set, "note": note,
    }], columns=COLS)
    p.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(p, mode="a", header=not p.exists(), index=False, encoding="utf-8")


def undelivered(date, ipos: list[str], path: Path | None = None) -> list[str]:
    """Which of today's closing IPOs have NOT had their decision delivered."""
    return [i for i in ipos if not already_sent(date, i, path)]


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
    print("[1] keyed by IPO AND date, so two IPOs on one day are independent")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.csv"
        mark("2026-10-09", "Alpha Ltd", "INE1", "IPO decision - Alpha Ltd",
             "2026-10-09 14:16", path=p)
        chk("Alpha is delivered", already_sent("2026-10-09", "Alpha Ltd", p) is True)
        chk("Beta on the same day is NOT",
            already_sent("2026-10-09", "Beta Ltd", p) is False)
        chk("Alpha on a DIFFERENT day is NOT",
            already_sent("2026-10-10", "Alpha Ltd", p) is False)
        chk("case and padding do not create a second identity",
            already_sent("2026-10-09", "  alpha ltd  ", p) is True)
        chk("undelivered lists only the gap",
            undelivered("2026-10-09", ["Alpha Ltd", "Beta Ltd"], p) == ["Beta Ltd"])

    print("\n[2] a dead-man notice is NOT a delivered decision")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.csv"
        mark("2026-10-09", "Alpha Ltd", None, "IPO decision - NOT SENT",
             "2026-10-09 16:05", kind=DEAD_MAN, path=p)
        chk("already_sent stays False", already_sent("2026-10-09", "Alpha Ltd", p) is False)
        chk("but the notice itself is recorded, so a second one is not sent",
            notice_sent("2026-10-09", "Alpha Ltd", p) is True)
        chk("and the IPO is still listed as undelivered",
            undelivered("2026-10-09", ["Alpha Ltd"], p) == ["Alpha Ltd"])

    print("\n[3] append-only: a re-send adds a row, never edits one")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.csv"
        mark("2026-10-09", "Alpha Ltd", None, "s1", "2026-10-09 14:16", path=p)
        mark("2026-10-09", "Alpha Ltd", None, "s2", "2026-10-09 14:31", path=p)
        d = read(p)
        chk("two rows, not one overwritten", len(d) == 2, len(d))
        chk("both timestamps survive", d["sent_at_ist"].nunique() == 2)

    print("\n[4] a missing or unreadable file means NOTHING was sent, never 'yes'")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "nope.csv"
        chk("absent file -> not sent", already_sent("2026-10-09", "Alpha", p) is False)
        bad = Path(td) / "bad.csv"
        bad.write_text("not,a,valid\ncsv\x00", encoding="utf-8")
        chk("unreadable file -> not sent (never a false 'already sent')",
            already_sent("2026-10-09", "Alpha", bad) is False)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = read()
    print(d.to_string(index=False) if len(d) else "no sent markers yet")

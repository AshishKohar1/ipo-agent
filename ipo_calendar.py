"""
ipo_calendar.py — which IPOs are open today, and from WHICH source (Phase 1, Task 1.2).

Why this module exists
----------------------
On 12 Oct 2026 the 15:00 email said "Nothing closes today / Nothing scheduled to open"
while NSE's calendar carried HD Fire Protect bidding 13-15 Oct. Two independent defects,
both in the single Chittorgarh parser the whole live path depended on:

1. Chittorgarh removed the open/past state badge from both dashboards. The row regex made
   that `<span><span title="Open">` block MANDATORY, so every row stopped matching and the
   dashboards reported "0 dated rows" while still listing every IPO on the page.
2. `_window` collapsed a same-month range - "13 - 15 Oct" has only one month token - to
   open == close. Cross-month ranges parsed fine, which is why it had never shown. HD Fire
   Protect's window is same-month.

Both are fixed in `chittorgarh_live.py`. But the deeper fault is that **the list of IPOs
had exactly one source** while H22 had already made NSE the source of record for the
subscription FIGURES. One parser against a third party's markup, with no second opinion,
produces silence that reads exactly like "no IPOs today". That is the failure mode a
decision system must never have: a missing input must never be presentable as a verdict.

What this module does
---------------------
* **NSE first** - `api/all-upcoming-issues?category=ipo` gives company, symbol, series and
  the real open/close dates, from the exchange running the book. `api/ipo-detail` is never
  touched (H22: its `bidDetails` block is an intermediate cut, 9-57% below the close).
* **Chittorgarh second**, for two jobs: it is the fallback when NSE is unreachable, and it
  is the only source for an SME issue on **BSE** SME, which is not in NSE's book at all.
  On 13 Oct 2026 NSE listed RAVITA (NSE Emerge) and Chittorgarh listed Vaibhav Vyapaar;
  neither page had both. So the two lists are UNIONED, not substituted.
* Where both have an issue, **NSE wins on dates, symbol and segment** and Chittorgarh
  contributes its `ipo_id`, which is what the live subscription page is keyed by.
* `list_source` on the view, and `source` on every row, record which page the row came
  from. A silent switch between two sources is how a divergence stops being detectable.

The data-check alarm
--------------------
If BOTH sources yield zero dated rows on a weekday, the view is flagged
`data_check_failed` and the caller must say so in the subject line. It is never reported
as "nothing closes today". A genuinely empty calendar and two broken parsers produce the
same empty list, and only one of them is safe to act on.

    python ipo_calendar.py              # today's merged view
    python ipo_calendar.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import chittorgarh_live as CL                                  # noqa: E402
import nse_subscription as NSE                                 # noqa: E402

NSE_LIST = "nse_all_upcoming_issues"
CG_LIST = "chittorgarh_dashboard"


def norm(name: str) -> str:
    """Company name reduced for matching only - never for deciding identity on its own.

    The suffixes go because NSE says "HD Fire Protect Limited" and Chittorgarh says
    "HD Fire Protect". Matching is used ONLY to attach a Chittorgarh id to a row NSE
    already vouched for; it never creates a row, and it never maps a symbol. H28 forbids
    name similarity as evidence of identity, and nothing here relies on it for that.
    """
    s = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
    s = re.sub(r"\b(limited|ltd|private|pvt|india|ipo)\b", " ", s)
    return re.sub(r"\s+", "", s)


def _state(opens, closes, today, status: str = "") -> str:
    st = (status or "").strip().lower()
    if st.startswith("active"):
        return "open"
    if st.startswith("forthcom") or st.startswith("upcom"):
        return "upcoming"
    if opens is None or closes is None:
        return "unknown"
    return ("open" if opens <= today <= closes else
            "upcoming" if opens > today else "past")


def from_nse(today: pd.Timestamp, f=None) -> tuple[list[dict], str]:
    """NSE's own calendar as live rows. Returns (rows, note)."""
    try:
        issues = NSE.open_issues(f or NSE.Fetcher())
    except Exception as e:                                     # noqa: BLE001
        return [], f"NSE calendar unavailable: {type(e).__name__}: {str(e)[:70]}"
    rows = []
    for it in issues:
        try:
            o = pd.Timestamp(it.get("opens"))
            c = pd.Timestamp(it.get("closes"))
        except Exception:                                      # noqa: BLE001
            continue
        if pd.isna(o) or pd.isna(c):
            continue
        series = str(it.get("series") or "EQ").upper()
        rows.append({
            "ipo": str(it.get("company") or "").strip(),
            "symbol": str(it.get("symbol") or "").strip() or None,
            "series": series,
            # Segment comes from the SERIES the exchange assigned, never from issue size.
            "segment": "sme" if series in ("SME", "SM", "ST") else "mainboard",
            "opens": o.normalize(), "closes": c.normalize(),
            "window": f"{o.strftime('%d %b')} - {c.strftime('%d %b')}",
            "nse_status": str(it.get("status") or ""),
            "source": NSE_LIST, "ipo_id": None, "slug": None, "dashboard": None,
        })
    return rows, f"NSE calendar: {len(rows)} dated rows"


def merge(nse_rows: list[dict], cg_rows: list[dict], today: pd.Timestamp) -> list[dict]:
    """Union. NSE wins on dates/symbol/segment; Chittorgarh supplies the id, and supplies
    whole rows for issues NSE's book does not carry (BSE SME)."""
    by_norm = {}
    for r in cg_rows:
        by_norm.setdefault(norm(r.get("ipo")), r)
    out, used = [], set()
    for r in nse_rows:
        k = norm(r["ipo"])
        cg = by_norm.get(k)
        row = dict(r)
        if cg is not None:
            used.add(k)
            row["ipo_id"] = cg.get("ipo_id")
            row["slug"] = cg.get("slug")
            row["dashboard"] = cg.get("dashboard")
            row["chittorgarh_name"] = cg.get("ipo")
            row["chittorgarh_window"] = cg.get("window")
            row["source"] = NSE_LIST + "+" + CG_LIST
        out.append(row)
    for k, r in by_norm.items():
        if k in used:
            continue
        row = dict(r)
        row.setdefault("symbol", None)
        row.setdefault("series", None)
        row["source"] = CG_LIST
        out.append(row)
    for r in out:
        r["state"] = _state(r.get("opens"), r.get("closes"), today, r.get("nse_status", ""))
        r["closes_today"] = bool(r.get("closes") is not None
                                 and pd.Timestamp(r["closes"]).date() == today.date())
        if r.get("opens") is not None and r.get("closes") is not None:
            r["day_of"] = (today - pd.Timestamp(r["opens"])).days + 1
            r["days_total"] = (pd.Timestamp(r["closes"]) - pd.Timestamp(r["opens"])).days + 1
    return out


def market_view(today: pd.Timestamp | None = None) -> dict:
    """The live view the email is built from. NSE primary, Chittorgarh fallback and union.

    Subscription figures are still fetched from Chittorgarh here (it is the only source
    publishing them per-issue DURING bidding on a page we may read); `nse_subscription
    .enrich_market_view` then overrides the mainboard closing-today rows from NSE under
    H22. Rows carried only by NSE have no Chittorgarh id and therefore no intraday figure
    until they are closing today - that is stated on the row, never left blank silently.
    """
    today = (today or pd.Timestamp.now()).normalize()
    diag = []

    nse_rows, nse_note = from_nse(today)
    diag.append(nse_note)

    cg_rows, lv = [], None
    try:
        lv = CL.Live()
        diag.append(f"robots.txt: {lv.robots_note}")
        cg_rows, cg_diag = lv.open_ipos(today)
        diag += cg_diag
    except Exception as e:                                     # noqa: BLE001
        diag.append(f"Chittorgarh dashboards unavailable: {type(e).__name__}: {str(e)[:70]}")

    rows = merge(nse_rows, cg_rows, today)

    if nse_rows and cg_rows:
        list_source = "NSE (primary) + Chittorgarh (union, SME on BSE)"
    elif nse_rows:
        list_source = "NSE (primary); Chittorgarh returned nothing"
    elif cg_rows:
        list_source = "Chittorgarh (fallback); NSE returned nothing"
    else:
        list_source = "NONE - both sources returned zero dated rows"

    # The alarm. A weekday on which neither source yields a single dated row is not a quiet
    # market, it is a broken read, and it must not be able to print as "nothing closes".
    data_check_failed = bool(today.weekday() < 5 and not nse_rows and not cg_rows)

    closing = [r for r in rows if r["state"] == "open" and r["closes_today"]]
    open_not = [r for r in rows if r["state"] == "open" and not r["closes_today"]]
    upcoming = [r for r in rows if r["state"] == "upcoming"]

    if lv is not None:
        for r in closing + open_not:
            if r.get("ipo_id") is None:
                r["sub"] = {"ok": False, "source": NSE_LIST,
                            "why": "not on the Chittorgarh dashboard, so no intraday "
                                   "figure from that source"}
                continue
            r["sub"] = lv.subscription(int(r["ipo_id"]))
            r["sub"].setdefault("source", "chittorgarh")
    else:
        for r in closing + open_not:
            r["sub"] = {"ok": False, "why": "Chittorgarh unavailable; no intraday figure"}

    return {"as_of": str(pd.Timestamp.now()), "today": str(today.date()),
            "closing_today": closing, "open_not_closing": open_not,
            "upcoming": upcoming, "diagnostics": diag,
            "list_source": list_source, "data_check_failed": data_check_failed,
            "n_nse_rows": len(nse_rows), "n_cg_rows": len(cg_rows),
            "n_open": len(closing) + len(open_not)}


# ---------------------------------------------------------------- self-test
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

    T = pd.Timestamp("2026-10-13")
    print("[1] the two defects that produced the 12 Oct silence")
    chk("same-month window keeps both ends (the HDFIRE case)",
        CL.Live._window("13 - 15 Oct", T) == (pd.Timestamp("2026-10-13"),
                                              pd.Timestamp("2026-10-15")),
        CL.Live._window("13 - 15 Oct", T))
    chk("cross-month window still parses",
        CL.Live._window("30 Sep - 05 Oct", T) == (pd.Timestamp("2026-09-30"),
                                                  pd.Timestamp("2026-10-05")))
    chk("a range straddling a month end puts the open in the previous month",
        CL.Live._window("28 - 02 Oct", T)[0] == pd.Timestamp("2026-09-28"))
    badge_less = ('<a href="/ipo/hd-fire-protect-ipo/2628/">HD Fire Protect <!-- --> '
                  '<!-- --> </a><span class="float-end ms-2">13 - 15 Oct</span>')
    m = CL.ROW.search(badge_less)
    chk("a row with NO state badge now matches", m is not None)
    chk("and its window is read", bool(m) and m.group("win") == "13 - 15 Oct")
    with_badge = ('<a href="/ipo/x-ipo/999/">X Co </a><span><span title="Open">O</span>'
                  '</span><span class="float-end">13 - 15 Oct</span>')
    m2 = CL.ROW.search(with_badge)
    chk("a row WITH the badge still matches, if the site restores it", m2 is not None)
    chk("and the badge's title is still read",
        bool(m2) and m2.group("state_title") == "Open")

    print("\n[2] the merge")
    nse = [{"ipo": "HD Fire Protect Limited", "symbol": "HDFIRE", "series": "EQ",
            "segment": "mainboard", "opens": pd.Timestamp("2026-10-13"),
            "closes": pd.Timestamp("2026-10-15"), "window": "13 Oct - 15 Oct",
            "nse_status": "Active", "source": NSE_LIST,
            "ipo_id": None, "slug": None, "dashboard": None}]
    cg = [{"ipo": "HD Fire Protect", "ipo_id": 2628, "slug": "hd-fire-protect-ipo",
           "segment": "mainboard", "opens": pd.Timestamp("2026-10-13"),
           "closes": pd.Timestamp("2026-10-15"), "window": "13 - 15 Oct",
           "dashboard": "cg", "state": "open"},
          {"ipo": "Vaibhav Vyapaar", "ipo_id": 2970, "slug": "vaibhav-vyapaar-ipo",
           "segment": "sme", "opens": pd.Timestamp("2026-10-13"),
           "closes": pd.Timestamp("2026-10-15"), "window": "13 - 15 Oct",
           "dashboard": "cg", "state": "open"}]
    out = merge(nse, cg, T)
    chk("the same issue on both pages makes ONE row", len(out) == 2, [r["ipo"] for r in out])
    hd = [r for r in out if r.get("symbol") == "HDFIRE"][0]
    chk("NSE's name and symbol win",
        hd["ipo"].endswith("Limited") and hd["symbol"] == "HDFIRE")
    chk("Chittorgarh's id is carried over, so the figure can still be fetched",
        hd["ipo_id"] == 2628)
    chk("the row says both sources contributed", hd["source"] == NSE_LIST + "+" + CG_LIST)
    vv = [r for r in out if r["ipo"] == "Vaibhav Vyapaar"][0]
    chk("a BSE SME issue NSE does not carry is KEPT, not dropped", vv["source"] == CG_LIST)
    chk("open on day 1 of 3 is open, not upcoming",
        hd["state"] == "open" and hd["day_of"] == 1 and hd["days_total"] == 3)
    chk("and it is not closing today", hd["closes_today"] is False)
    out15 = merge(nse, cg, pd.Timestamp("2026-10-15"))
    chk("on the last day it IS closing today",
        [r for r in out15 if r.get("symbol") == "HDFIRE"][0]["closes_today"] is True)

    print("\n[3] NSE alone is enough, and so is Chittorgarh alone")
    chk("NSE alone still yields the row", len(merge(nse, [], T)) == 1)
    chk("Chittorgarh alone still yields both rows", len(merge([], cg, T)) == 2)

    print("\n[4] the name match never invents identity")
    chk("suffixes are stripped so the two spellings meet",
        norm("HD Fire Protect Limited") == norm("HD Fire Protect"))
    chk("two different companies do NOT collide",
        norm("Ravita Engineering Services Limited") != norm("Ravi Infrastructure Limited"))
    chk("a Chittorgarh row that matches nothing on NSE keeps a null symbol",
        merge([], cg, T)[0].get("symbol") is None)

    print("\n[5] state, and the data-check alarm")
    chk("state falls back to the dates when NSE gives no status",
        _state(pd.Timestamp("2026-10-13"), pd.Timestamp("2026-10-15"), T, "") == "open")
    chk("NSE's own Active label is honoured over the dates",
        _state(pd.Timestamp("2026-10-20"), pd.Timestamp("2026-10-22"), T, "Active") == "open")
    chk("a past window is past",
        _state(pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-03"), T, "") == "past")

    print(f"\n{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    mv = market_view()
    if a.json:
        print(json.dumps(mv, indent=2, default=str))
    else:
        print(f"as of {mv['as_of']} - list source: {mv['list_source']}")
        print(f"  {mv['n_open']} open, {len(mv['closing_today'])} closing today, "
              f"data_check_failed={mv['data_check_failed']}")
        for k in ("closing_today", "open_not_closing", "upcoming"):
            for r in mv[k]:
                s = r.get("sub", {}) or {}
                tot = f"{s.get('total_x')}x" if s.get("ok") else "(no figure)"
                print(f"  [{k:17s}] {str(r['ipo'])[:32]:34s} {r['segment']:9s} "
                      f"{str(r.get('symbol')):10s} {str(r.get('window','')):16s} {tot}")
        for d in mv["diagnostics"]:
            print(f"    - {d}")

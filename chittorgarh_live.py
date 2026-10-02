"""
chittorgarh_live.py — the live subscription source for Model L (decision H14).

NSE times out on every path for our User-Agent and BSE returns 403 even on its own
robots.txt, so Chittorgarh is the only permitted source publishing subscription *during*
bidding. It is **single-source**: there is nothing to reconcile against, so every reading
carries `single_source_unverified` and every email carries the verify-on-your-broker caveat.

Two pages, both verified working 2026-10-02:

  `/ipo/`                        the dashboard calendar — company, id, an `O`(pen)/`P`(ast)
                                 badge, and the issue window "30 Sep - 05 Oct"
  `/ipo_subscription/x/{id}/`    live category-wise subscription while the IPO is open

**Politeness (B2, H14).** robots.txt is re-read at the start of every run and the run aborts
if it no longer permits access or if a Claude/Anthropic token ever appears in it. Minimum
3.2 s between requests, single-threaded, one non-browser User-Agent. **Every fetch is logged
with its timestamp and exact URL** to `data/live_fetch_log.csv`, so the request history is
auditable against the site's expectations.

**Segment comes from the source, not from a size heuristic.** The mainboard and SME
dashboards are separate pages; an IPO is tagged by which one listed it. Guessing SME from
issue size would silently misclassify, and an SME verdict must never be presented as a
mainboard one (shadow-mode decision).

    python chittorgarh_live.py            # today's market view
    python chittorgarh_live.py --json
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import io
import json
import re
import sys
import time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from stage4a_id_walk import robots_ok                     # noqa: E402

UA = {"User-Agent": "ipo-agent/1.0 (personal research; contact ashishkohar4@gmail.com)"}
MIN_GAP_S = 3.2
FETCH_LOG = ROOT / "data" / "live_fetch_log.csv"
DASHBOARDS = (("mainboard", "https://www.chittorgarh.com/ipo/"),
              ("sme", "https://www.chittorgarh.com/ipo/ipo_dashboard.asp?a=sme"))
SUB_URL = "https://www.chittorgarh.com/ipo_subscription/x/{id}/"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
# The real markup, verified against the page rather than assumed:
#   <a href="/ipo/nityas-gems-jewellery-ipo/2974/">Nityas Gems &amp; Jewellery <!-- --> </a>
#   <span><span ... title="Open">O</span></span><span class="float-end">30 Sep - 05 Oct</span>
# The badge letter is a rendering of `title`, so the TITLE is parsed instead: "Open" is
# unambiguous where a bare "O" is not, and the state is what decides whether a verdict may
# be printed at all.
ROW = re.compile(
    r'href="/ipo/([a-z0-9\-]+)/(\d{3,6})/"[^>]*>(?P<name>[^<]{2,70}?)\s*'
    r'(?:<!--[^>]*-->\s*)*</a>\s*<span>\s*<span[^>]*title="(?P<state_title>[^"]*)"[^>]*>'
    r'\s*(?P<badge>[A-Za-z])\s*</span>\s*</span>\s*<span[^>]*>\s*(?P<win>[^<]+?)\s*</span>',
    re.S)


class Blocked(RuntimeError):
    pass


def _log_fetch(url: str, status, nbytes, note: str = "") -> None:
    row = pd.DataFrame([{"fetched_at_ist": str(pd.Timestamp.now()), "url": url,
                         "http_status": status, "bytes": nbytes, "note": note}])
    FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(FETCH_LOG, mode="a", header=not FETCH_LOG.exists(), index=False,
               encoding="utf-8")


class Live:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(UA)
        self._last = 0.0
        ok, why = robots_ok(self.s)
        _log_fetch("https://www.chittorgarh.com/robots.txt", 200 if ok else "refused", 0, why)
        if not ok:
            raise Blocked(f"Chittorgarh robots.txt no longer permits this access: {why}")
        self.robots_note = why

    def get(self, url: str) -> str:
        gap = MIN_GAP_S - (time.time() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.time()
        r = self.s.get(url, timeout=40)
        _log_fetch(url, r.status_code, len(r.content))
        if r.status_code != 200:
            raise Blocked(f"{url} returned HTTP {r.status_code}")
        return r.text

    # ------------------------------------------------------------------ calendar
    def open_ipos(self, today: pd.Timestamp) -> tuple[list[dict], list[str]]:
        """Every IPO the dashboards mark open, plus the ones not yet opened."""
        out, diag = [], []
        for segment, url in DASHBOARDS:
            try:
                html = self.get(url)
            except Blocked as e:
                diag.append(f"{segment} dashboard unavailable: {e}")
                continue
            n = 0
            for m in ROW.finditer(html):
                name = re.sub(r"\s+", " ", m.group("name")).replace("&amp;", "&").strip()
                win = re.sub(r"\s+", " ", m.group("win"))
                o, c = self._window(win, today)
                if o is None:
                    continue
                n += 1
                out.append({"ipo": name, "ipo_id": int(m.group(2)), "slug": m.group(1),
                            "segment": segment, "badge": m.group("badge") or "",
                            "state_title": (m.group("state_title") or "").strip(),
                            "window": win, "opens": o, "closes": c,
                            "dashboard": url})
            diag.append(f"{segment} dashboard: {n} dated rows")
        # de-duplicate: an IPO can appear on both dashboards; mainboard wins
        seen, uniq = set(), []
        for r in sorted(out, key=lambda r: r["segment"] != "mainboard"):
            k = re.sub(r"[^a-z0-9]", "", r["ipo"].lower())
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        for r in uniq:
            # The site's own label wins over my date arithmetic: it knows about an
            # extended window or an early close, and the dates on the dashboard carry no
            # year. The dates are the fallback when no label is present.
            lbl = (r.get("state_title") or "").lower()
            if lbl.startswith("open"):
                r["state"] = "open"
            elif lbl.startswith("upcom") or lbl.startswith("forthcom"):
                r["state"] = "upcoming"
            elif lbl.startswith("past") or lbl.startswith("clos"):
                r["state"] = "past"
            else:
                r["state"] = ("open" if r["opens"] <= today <= r["closes"] else
                              "upcoming" if r["opens"] > today else "past")
            r["closes_today"] = bool(r["closes"].date() == today.date())
            r["day_of"] = (today - r["opens"]).days + 1
            r["days_total"] = (r["closes"] - r["opens"]).days + 1
        return uniq, diag

    @staticmethod
    def _window(win: str, today: pd.Timestamp):
        """'30 Sep - 05 Oct' -> (open, close). Year inferred from proximity to today."""
        parts = re.findall(r"(\d{1,2})\s*([A-Za-z]{3})", win)
        if not parts:
            return None, None

        def mk(d, mon):
            mo = MONTHS.get(mon[:3].lower())
            if not mo:
                return None
            # The calendar prints no year. Choose the year that puts the date nearest to
            # today, so a December window read in January resolves to last year rather than
            # eleven months into the future.
            best = None
            for y in (today.year - 1, today.year, today.year + 1):
                try:
                    cand = pd.Timestamp(year=y, month=mo, day=int(d))
                except ValueError:
                    continue
                if best is None or abs((cand - today).days) < abs((best - today).days):
                    best = cand
            return best
        o = mk(*parts[0])
        c = mk(*parts[-1]) if len(parts) > 1 else o
        if o is None or c is None:
            return None, None
        if c < o:                      # window crosses a year boundary
            c = c + pd.DateOffset(years=1)
        return o, c

    # ------------------------------------------------------------------ subscription
    def subscription(self, ipo_id: int) -> dict:
        """Current category-wise subscription. Returns {} with a reason on failure."""
        url = SUB_URL.format(id=ipo_id)
        try:
            html = self.get(url)
        except Blocked as e:
            return {"ok": False, "why": str(e), "url": url}
        try:
            tabs = pd.read_html(io.StringIO(html))
        except Exception as e:
            return {"ok": False, "why": f"no table: {type(e).__name__}", "url": url}
        got = {"ok": False, "url": url, "source": "chittorgarh",
               "reconciled": "single_source_unverified"}
        for t in tabs:
            hdr = " ".join(str(c) for c in t.columns).lower()
            if "subscription" not in hdr or t.shape[1] < 2:
                continue
            for a, b in zip(t.iloc[:, 0].astype(str), t.iloc[:, 1].astype(str)):
                lab = a.lower()
                v = re.search(r"([\d.]+)\s*x", b, re.I) or re.search(r"^([\d.]+)$", b.strip())
                if not v:
                    continue
                try:
                    x = float(v.group(1))
                except ValueError:
                    continue
                if "qualified" in lab or lab.startswith("qib"):
                    got["qib_x"] = x
                elif "non institutional" in lab or "nii" in lab or "hni" in lab:
                    got["hni_x"] = x
                elif "retail" in lab:
                    got["rii_x"] = x
                elif "employee" in lab:
                    got["emp_x"] = x
                elif lab.startswith("total"):
                    got["total_x"] = x
            if "total_x" in got:
                got["ok"] = True
                break
        if not got["ok"]:
            got["why"] = ("the subscription table has no Total row yet — normal before "
                          "bidding opens or very early on day 1")
        return got


def market_view(today: pd.Timestamp | None = None) -> dict:
    today = (today or pd.Timestamp.now()).normalize()
    lv = Live()
    ipos, diag = lv.open_ipos(today)
    diag.insert(0, f"robots.txt: {lv.robots_note}")
    closing = [r for r in ipos if r["state"] == "open" and r["closes_today"]]
    open_not = [r for r in ipos if r["state"] == "open" and not r["closes_today"]]
    upcoming = [r for r in ipos if r["state"] == "upcoming"]
    for r in closing + open_not:
        r["sub"] = lv.subscription(r["ipo_id"])
        if not r["sub"].get("ok"):
            diag.append(f"{r['ipo']}: {r['sub'].get('why')}")
    return {"as_of": str(pd.Timestamp.now()), "today": str(today.date()),
            "closing_today": closing, "open_not_closing": open_not,
            "upcoming": upcoming, "diagnostics": diag,
            "n_open": len(closing) + len(open_not)}


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    mv = market_view()
    if a.json:
        print(json.dumps(mv, indent=2, default=str))
    else:
        print(f"as of {mv['as_of']} — {mv['n_open']} open, "
              f"{len(mv['closing_today'])} closing today")
        for k in ("closing_today", "open_not_closing", "upcoming"):
            for r in mv[k]:
                s = r.get("sub", {})
                tot = f"{s.get('total_x')}x" if s.get("ok") else "(no subscription)"
                print(f"  [{k:17s}] {r['ipo'][:32]:34s} {r['segment']:9s} "
                      f"{r['window']:16s} day {r.get('day_of')}/{r.get('days_total')} {tot}")
        for d in mv["diagnostics"]:
            print(f"    - {d}")

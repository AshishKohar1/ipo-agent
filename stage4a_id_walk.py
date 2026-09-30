"""
stage4a_id_walk.py — Gate F capped ID probe of Chittorgarh subscription pages.

Authorised by the user's Gate F decision, under mandatory constraints:
  * re-read robots.txt first and ABORT if it no longer permits access
  * at most MAX_REQUESTS requests, at least MIN_GAP_S apart, single-threaded
  * IDs spread across the plausible range, not a sequential crawl of one block
  * stop immediately on repeated 4xx/5xx, rate-limiting or any sign of objection
  * one fixed User-Agent, never varied; no aggressive retry

The slug segment is ignored by the site (`/ipo_subscription/x/3007/` resolves), so the
walk varies only the numeric id and uses a constant placeholder slug.

Output: data/chittorgarh_id_probe.csv — one row per id attempted, resumable.

    python stage4a_id_walk.py            # coarse sweep
    python stage4a_id_walk.py 1200 1600 25   # targeted range: start stop step
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import re
import sys
import time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "chittorgarh_id_probe.csv"
BASE = "https://www.chittorgarh.com/ipo_subscription/x/{id}/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"}
MIN_GAP_S = 3.2                 # decision B2 requires >= 3 s
MAX_REQUESTS = 190              # user cap is 200; 3 already spent on pre-flight checks
MAX_CONSECUTIVE_ERRORS = 3      # stop immediately on repeated failures


def robots_ok(sess) -> tuple[bool, str]:
    r = sess.get("https://www.chittorgarh.com/robots.txt", timeout=30)
    if r.status_code != 200:
        return False, f"robots.txt returned HTTP {r.status_code}"
    star, dis = False, []
    for ln in r.text.splitlines():
        t = ln.split("#", 1)[0].strip()
        if not t:
            continue
        k, _, v = t.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            star = (v == "*")
        elif star and k == "disallow" and v:
            dis.append(v)
    if re.search(r"(?i)claudebot|anthropic", r.text):
        return False, "robots.txt now names an Anthropic crawler"
    if any(d == "/" or d.startswith("/ipo_subscription") for d in dis):
        return False, f"robots.txt now disallows the path: {dis}"
    return True, f"permitted; User-agent:* disallows {dis}"


def parse(html: str) -> dict:
    """Pull company, year, day-wise table shape, anchor and lock-in presence."""
    out = {"company": None, "ipo_year": None, "daywise_present": False, "bidding_days": 0,
           "categories": None, "anchor_table": False, "lockin": False, "day_labels": None}
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        t = re.split(r"\s+IPO\s+Subscription", t)[0].strip()
        out["company"] = t[:70] or None

    # the day-wise table is the one whose first header is "Date"
    for tm in re.finditer(r"<table", html):
        seg = html[tm.start():tm.start() + 4000]
        hdrs = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", seg, re.S)]
        if hdrs and hdrs[0].lower().startswith("date"):
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S)
            labels = []
            for r_ in rows:
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in
                         re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r_, re.S)]
                if cells and re.search(r"\(Day\s*\d+\)|Day\s*\d+", cells[0]):
                    labels.append(cells[0])
            out["daywise_present"] = len(labels) > 0
            out["bidding_days"] = len(labels)
            out["day_labels"] = " | ".join(labels)[:120] or None
            out["categories"] = " | ".join(h.replace("&#8377;", "Rs")
                                          for h in hdrs)[:160]
            break

    out["anchor_table"] = bool(re.search(r"Shares Allotted", html))
    out["lockin"] = bool(re.search(r"Shares Locked", html))
    # year: prefer the day-wise dates, else the IPO-opens row, else any 4-digit year
    yrs = re.findall(r"\b(20[0-2]\d)\b", html)
    dm = re.search(r"IPO opens On</td>\s*<td[^>]*>[^<]*?(20[0-2]\d)", html)
    if dm:
        out["ipo_year"] = int(dm.group(1))
    elif out["day_labels"]:
        ym = re.search(r"(20[0-2]\d)", out["day_labels"])
        out["ipo_year"] = int(ym.group(1)) if ym else None
    if out["ipo_year"] is None and yrs:
        from collections import Counter
        out["ipo_year"] = int(Counter(yrs).most_common(1)[0][0])
    return out


def main(argv):
    if len(argv) >= 3:
        ids = list(range(int(argv[0]), int(argv[1]) + 1, int(argv[2])))
    else:
        ids = list(range(50, 3051, 50))          # coarse spread across the whole range
    sess = requests.Session(); sess.headers.update(UA)

    ok, why = robots_ok(sess)
    print(f"robots.txt: {why}")
    if not ok:
        sys.exit("ABORT — robots.txt no longer permits this. Nothing fetched.")

    done = {}
    if OUT.exists():
        prev = pd.read_csv(OUT)
        done = {int(r.ipo_id): r._asdict() for r in prev.itertuples()}
        print(f"resuming: {len(done)} ids already probed")

    rows, n_req, consec_err = list(done.values()), 0, 0
    todo = [i for i in ids if i not in done]
    print(f"probing {len(todo)} ids (cap {MAX_REQUESTS}), >={MIN_GAP_S}s apart\n")
    for i in todo:
        if n_req >= MAX_REQUESTS:
            print(f"\nSTOP: request cap {MAX_REQUESTS} reached."); break
        time.sleep(MIN_GAP_S)
        rec = {"ipo_id": i, "http": None, "error": None}
        try:
            r = sess.get(BASE.format(id=i), timeout=45)
            n_req += 1
            rec["http"] = r.status_code
            if r.status_code == 429 or "too many requests" in r.text[:2000].lower():
                print("\nSTOP: rate-limited (HTTP 429 / body says too many requests).")
                rows.append(rec); break
            if r.status_code == 200:
                rec.update(parse(r.text)); consec_err = 0
            else:
                consec_err += 1
        except Exception as e:
            n_req += 1
            rec["error"] = f"{type(e).__name__}: {str(e)[:80]}"
            consec_err += 1
        rows.append(rec)
        d = rec.get("daywise_present")
        print(f"  id {i:5d} http {str(rec['http']):4s} {str(rec.get('ipo_year')):5s} "
              f"daywise={'Y' if d else 'n' if rec['http'] == 200 else '-'} "
              f"days={rec.get('bidding_days') or 0:2} {str(rec.get('company'))[:44]}")
        pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")
        if consec_err >= MAX_CONSECUTIVE_ERRORS:
            print(f"\nSTOP: {consec_err} consecutive failures — the site may be objecting.")
            break

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\nrequests this run: {n_req} | rows total: {len(df)} -> {OUT.name}")
    got = df[df["http"] == 200]
    if len(got):
        print(f"resolved 200: {len(got)} | with day-wise table: {int(got['daywise_present'].sum())}")
        print(got.groupby("ipo_year", dropna=True)
              .agg(ids=("ipo_id", "size"), daywise=("daywise_present", "sum"),
                   max_days=("bidding_days", "max")).to_string())
    return df


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main(sys.argv[1:])

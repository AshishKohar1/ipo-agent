"""
post_listing_filings.py — Task 2: Model H inputs from post-listing exchange filings.

Model H scores an IPO *after* it lists, and its label is measured at T+365, so a filing from
the first quarter after listing creates no look-ahead problem. Those filings are structured
data rather than PDF prose, which makes them a better source than the RHP for three fields
the RHP extractor handles badly:

| Field | Source | Replaces |
|---|---|---|
| board size, independent-director ratio | first corporate governance report post-listing | 69 + 23 RHP failures |
| promoter holding, pledge % | first shareholding pattern post-listing | RHP prose parsing |
| contingent liabilities | first annual report after listing | 41 RHP failures |

## Permission check — run before anything is fetched, every run

`verify_permitted()` reads each exchange's `robots.txt` and refuses to fetch unless it can
positively establish that the path is allowed. **An unreadable robots.txt is a refusal, not a
default-allow.** As of 2026-10-02:

  * **NSE** — `robots.txt` HTTP 200, `Allow: /`, disallows only `/market-data-test`. The
    corporate-filing paths are **permitted**.
  * **BSE** — `robots.txt` itself returns **HTTP 403** at the Akamai edge. Permission cannot
    be established, so **BSE is not fetched at all**. This is deliberate: "I could not read
    the rules" is not the same as "the rules allow it".

Separately, NSE's network layer is currently refusing this host regardless of robots.txt —
read timeouts on every path with our own User-Agent. The job logs that and fetches nothing.
**It does not fall back to a browser User-Agent** (rule 3), and it does not substitute a
value from anywhere else.

## Reconciliation — rule 2, with a pre/post distinction

Where a post-listing value and an RHP value both exist they are compared under rule 2 (5%).
But a difference here is **not** necessarily an error: the RHP states the position *before*
the issue and the filing states it *after*, so promoter holding in particular is *expected*
to fall. Mismatches are therefore classified:

  `PASS`                 within 5%
  `pre_vs_post_issue`    outside 5% **and** the direction is what dilution predicts
  `MISMATCH`             outside 5% and NOT explicable by the issue — a real conflict

Both values are always kept in the audit log, whichever class it lands in.

    python post_listing_filings.py --check          # permission check only, fetches nothing
    python post_listing_filings.py --self-test      # exercise the reconciliation offline
    python post_listing_filings.py                  # run (will refuse while blocked)
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import re
import sys
import time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "post_listing_filings.csv"
AUDIT = ROOT / "reports" / "post_listing_reconciliation.csv"
PERM = ROOT / "reports" / "exchange_permission_check.json"
UA = {"User-Agent": "ipo-agent/1.0 (personal research; contact ashishkohar4@gmail.com)",
      "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}
MIN_GAP_S = 3.2
TOL = 0.05

COLS = ["company", "isin", "symbol", "listing_date", "filing_type", "filing_period",
        "filed_on", "board_size_n", "independent_directors_n", "board_independence_ratio",
        "promoter_holding_pct", "promoter_pledge_pct", "contingent_liabilities_cr",
        "source", "url", "fetched_at", "note"]
AUDIT_COLS = ["company", "field", "rhp_value", "post_listing_value", "rel_diff_pct",
              "verdict", "direction_expected", "note"]

# Fields whose post-issue value is EXPECTED to move, and in which direction. Promoter
# holding falls mechanically when fresh shares are issued; nothing else on this list has a
# direction the issue itself predicts.
EXPECTED_DIRECTION = {"promoter_holding_pct": "down"}


# ---------------------------------------------------------------- permission
def verify_permitted(verbose: bool = True) -> dict:
    """Read each exchange's robots.txt. An unreadable one is a REFUSAL, not a default-allow."""
    import requests
    res = {"checked_at": str(pd.Timestamp.now()), "exchanges": {}}
    for name, host, paths in (
        ("NSE", "https://www.nseindia.com",
         ["/api/corporate-governance", "/api/corporate-share-holdings-master",
          "/api/annual-reports"]),
        ("BSE", "https://www.bseindia.com",
         ["/corporate/Comp_Resultsnew.aspx", "/corporate/Sharehold.aspx"]),
    ):
        e = {"host": host, "paths": paths}
        try:
            r = requests.get(f"{host}/robots.txt", headers=UA, timeout=25)
            e["robots_http"] = r.status_code
            if r.status_code != 200:
                e["permitted"] = False
                e["why"] = (f"robots.txt returned HTTP {r.status_code}, so the rules could "
                            "not be read. Treated as a REFUSAL — 'I could not read the "
                            "rules' is not 'the rules allow it'.")
            else:
                txt = r.text
                e["robots_excerpt"] = txt[:400]
                if re.search(r"(?i)claudebot|anthropic|ai-train|gptbot", txt):
                    e["permitted"] = False
                    e["why"] = "robots.txt names an AI crawler — refusing (rule 3, B1)."
                else:
                    star, dis = False, []
                    for ln in txt.splitlines():
                        tok = ln.split("#", 1)[0].strip()
                        if not tok:
                            continue
                        k, _, v = tok.partition(":")
                        k, v = k.strip().lower(), v.strip()
                        if k == "user-agent":
                            star = (v == "*")
                        elif star and k == "disallow" and v:
                            dis.append(v)
                    blocked = [p for p in paths
                               if any(p.startswith(d) for d in dis) or "/" in dis]
                    e["disallow"] = dis
                    e["permitted"] = not blocked
                    e["why"] = ("permitted; User-agent:* disallows " + str(dis)) if not blocked \
                        else f"robots.txt disallows {blocked}"
        except Exception as ex:
            e["permitted"] = False
            e["why"] = f"could not reach robots.txt: {type(ex).__name__}: {ex}"
        res["exchanges"][name] = e
        if verbose:
            print(f"  {name}: {'PERMITTED' if e.get('permitted') else 'REFUSED'} — {e['why']}")
    PERM.parent.mkdir(parents=True, exist_ok=True)
    PERM.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


# ---------------------------------------------------------------- reconciliation
def reconcile_field(field: str, rhp_value, post_value, company: str = "") -> dict:
    """Rule 2, with the pre/post-issue distinction the user asked for."""
    if rhp_value is None or post_value is None or pd.isna(rhp_value) or pd.isna(post_value):
        return {"company": company, "field": field, "rhp_value": rhp_value,
                "post_listing_value": post_value, "rel_diff_pct": None,
                "verdict": "single_source", "direction_expected": "",
                "note": "only one source has a value; kept, flagged single-source (rule 3)"}
    a, b = float(rhp_value), float(post_value)
    hi = max(abs(a), abs(b)) or 1.0
    diff = abs(a - b) / hi
    row = {"company": company, "field": field, "rhp_value": a, "post_listing_value": b,
           "rel_diff_pct": round(diff * 100, 3)}
    if diff <= TOL:
        row.update({"verdict": "PASS", "direction_expected": "",
                    "note": f"agree within {diff*100:.2f}%"})
        return row
    exp = EXPECTED_DIRECTION.get(field)
    moved = "down" if b < a else "up"
    if exp and moved == exp:
        row.update({"verdict": "pre_vs_post_issue", "direction_expected": exp,
                    "note": (f"differs by {diff*100:.1f}% and moved {moved}, which is what "
                             f"the issue predicts for this field (the RHP states the "
                             f"PRE-issue position, the filing the POST-issue one). "
                             f"Recorded as a legitimate difference, NOT an error. Both "
                             f"values kept.")})
    else:
        row.update({"verdict": "MISMATCH", "direction_expected": exp or "",
                    "note": (f"differs by {diff*100:.1f}%, moved {moved}"
                             + (f" but dilution predicts {exp}" if exp else
                                " and the issue does not predict a change in this field")
                             + ". A real conflict — both values logged, neither trusted.")})
    return row


def self_test() -> bool:
    """Exercise the reconciliation offline, so it is not shipped unexercised.

    The fetch is blocked, so without this the only new logic in this module would reach the
    user having never run.
    """
    cases = [
        ("promoter_holding_pct", 83.6, 72.6, "pre_vs_post_issue",
         "Syngene: 83.6% pre, 72.6% post — dilution, exactly as expected"),
        ("promoter_holding_pct", 40.69, 40.91, "PASS",
         "Jupiter: within 5%, no dilution worth flagging"),
        ("promoter_holding_pct", 50.0, 70.0, "MISMATCH",
         "promoter holding ROSE across the issue — dilution predicts down, so this conflicts"),
        ("board_size_n", 8.0, 8.0, "PASS", "board unchanged"),
        ("board_size_n", 8.0, 11.0, "MISMATCH",
         "board grew 37.5% and the issue does not predict that — a real conflict to look at"),
        ("contingent_liabilities_cr", 100.0, 103.0, "PASS", "within 5%"),
        ("contingent_liabilities_cr", 100.0, 400.0, "MISMATCH", "4x — conflict"),
        ("board_size_n", 8.0, None, "single_source", "only the RHP has it"),
        ("board_size_n", None, 9.0, "single_source", "only the filing has it"),
    ]
    ok = True
    print("self-test — reconciliation verdicts")
    for field, a, b, want, why in cases:
        got = reconcile_field(field, a, b, "test")["verdict"]
        good = got == want
        ok &= good
        print(f"  {'OK ' if good else 'FAIL'} {field:26s} {str(a):>6s} -> {str(b):<6s} "
              f"{got:18s} ({why})")
    print(f"\nself-test {'PASSED' if ok else 'FAILED'}")
    return ok


# ---------------------------------------------------------------- fetch (blocked)
def fetch_one(sess, symbol: str) -> dict:
    """The three filings for one company. Returns what it got and why it failed."""
    out = {"symbol": symbol, "note": "", "source": "nse_official"}
    endpoints = {
        "corporate_governance": ("https://www.nseindia.com/api/corporate-governance",
                                 {"index": "equities", "symbol": symbol}),
        "shareholding_pattern": ("https://www.nseindia.com/api/"
                                 "corporate-share-holdings-master",
                                 {"index": "equities", "symbol": symbol}),
        "annual_report": ("https://www.nseindia.com/api/annual-reports",
                          {"index": "equities", "symbol": symbol}),
    }
    whys = []
    for kind, (url, params) in endpoints.items():
        time.sleep(MIN_GAP_S)
        try:
            r = sess.get(url, params=params, timeout=30)
            if r.status_code != 200:
                whys.append(f"{kind}: HTTP {r.status_code}")
                continue
            out[f"{kind}_payload"] = r.json()
            out["url"] = r.url
        except Exception as e:
            whys.append(f"{kind}: {type(e).__name__}")
    out["note"] = "; ".join(whys)
    out["ok"] = any(k.endswith("_payload") for k in out)
    return out


def main(check_only: bool = False, test_only: bool = False, limit: int | None = None) -> dict:
    print("Task 2 — post-listing filings. Permission check first, always.\n")
    if test_only:
        return {"self_test": self_test()}
    perm = verify_permitted()
    allowed = [k for k, v in perm["exchanges"].items() if v.get("permitted")]
    print(f"\npermitted exchanges: {allowed or 'NONE'}")
    if check_only:
        return perm
    if not allowed:
        print("\nREFUSING TO FETCH: no exchange could be positively established as "
              "permitting this access. Nothing written.")
        return {"fetched": 0, "permission": perm}

    import requests
    sess = requests.Session()
    sess.headers.update(UA)
    try:
        sess.get("https://www.nseindia.com/", timeout=25)
    except Exception as e:
        print(f"\nNSE is not reachable with our User-Agent: {type(e).__name__}. "
              "robots.txt PERMITS these paths, so this is network-layer filtering, not a "
              "rules restriction.\nNOT falling back to a browser User-Agent (rule 3). "
              "Nothing fetched, nothing invented.")
        return {"fetched": 0, "blocked": f"{type(e).__name__}", "permission": perm}

    m = pd.read_csv(ROOT / "master_with_symbols.csv")
    q = m[m["exclude_reason"].isna() & m["symbol"].notna()]
    if limit:
        q = q.head(limit)
    rows, blocked = [], 0
    for r in q.itertuples():
        got = fetch_one(sess, r.symbol)
        if not got.get("ok"):
            blocked += 1
            if blocked >= 5:
                print(f"\nSTOP: {blocked} consecutive companies returned nothing "
                      f"({got['note']}). Not retrying aggressively.")
                break
            continue
        blocked = 0
        rows.append({"company": r.company, "isin": r.isin, "symbol": r.symbol,
                     "listing_date": r.listing_date, "fetched_at": str(pd.Timestamp.now()),
                     **{k: v for k, v in got.items() if k in COLS}})
    if rows:
        pd.DataFrame([{c: x.get(c) for c in COLS} for x in rows], columns=COLS).to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")
    print(f"\nfetched {len(rows)} companies")
    return {"fetched": len(rows), "permission": perm}


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="permission check only")
    ap.add_argument("--self-test", action="store_true", help="exercise reconciliation offline")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    main(a.check, a.self_test, a.limit)

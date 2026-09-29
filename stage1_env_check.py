"""
stage1_env_check.py — PLAN.md Stage 1 (environment check), steps 1, 3, 4 and 5.

Step 2 lives in check_env.py (run that separately). This script is deliberately
environment-agnostic so the same command can be run on the laptop and in the cloud and
the two reports compared:

  1  interpreter / OS / requirements-install state
  3  reachability of every domain the plan depends on, one light request each,
     plus robots.txt for the sites later stages intend to scrape (rule 5)
  4  dataset integrity: master rows, exclude_reason flags, excess_1y / excess_3y rows,
     Nifty TRI present and gap-free, numpy estimator regression test
  5  re-fetch Syngene's RHP from SEBI, confirm SHA-256 against the manifest, delete it

Writes reports/stage1_checks.json. Exit 0 only if every REQUIRED check passes.

    python stage1_env_check.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import hashlib, json, platform, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30), "IST")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"}
SEBI_GAP_S, OTHER_GAP_S = 3.0, 1.0

# domain -> (why it is needed, required now?, probe path)
# "required now" = the pipeline as already built cannot run without it. The rest are
# needed by a later stage; a block there is reported, and that stage must re-plan.
#
# The probe path matters. A bare "GET /" is the wrong test for an API host:
# query2.finance.yahoo.com/ returns 404 by design, and www.nseindia.com/ returns 403
# unless the request looks like a browser. Both are fully reachable on the endpoints the
# pipeline actually calls, so each host is probed on a light, representative endpoint.
DOMAINS = {
    "www.sebi.gov.in":          ("RHP / prospectus source (Stages 8-10)", True, "/"),
    "www.niftyindices.com":     ("official Nifty 50 TRI benchmark (Stage 3 target refresh)", True,
                                 "/reports/historical-data"),
    "query2.finance.yahoo.com": ("prices, symbols, listing dates (Job 1-3)", True,
                                 "/v1/finance/search?q=Reliance&quotesCount=1"),
    "www.nseindia.com":         ("equity list, offer-doc listing, spine refresh", True,
                                 "/api/marketStatus"),
    "www.bsesme.com":           ("SME prospectus source", True, "/"),
    "www.bseindia.com":         ("BSE mainboard (resolver not implemented; reconciliation)", False, "/"),
    "www.chittorgarh.com":      ("day-wise subscription (Stage 4)", False, "/"),
    "www.ipoji.com":            ("day-wise subscription, 2nd source (Stage 4)", False, "/"),
    "www.investorgain.com":     ("GMP history (Stage 4)", False, "/"),
    "www.screener.in":          ("financials reconciliation (Stage 8)", False, "/"),
    "www.rbi.org.in":           ("91-day T-bill for WACC proxy (Stage 11)", False, "/"),
}
# sites later stages intend to read programmatically -> check robots.txt up front (rule 5)
ROBOTS_TARGETS = ["www.chittorgarh.com", "www.ipoji.com", "www.investorgain.com",
                  "www.screener.in", "www.sebi.gov.in", "www.bsesme.com"]

out: dict = {"run_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"), "steps": {}}
fails: list[str] = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ----------------------------------------------------------------- step 1
def step1():
    head("STEP 1 — interpreter / OS / requirements")
    from importlib.metadata import version, PackageNotFoundError
    pins = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            n, v = line.split("==", 1)
            pins[n.strip()] = v.strip()
    installed, dev = {}, []
    for n, want in pins.items():
        try:
            got = version(n)
        except PackageNotFoundError:
            got = None
        installed[n] = got
        if got != want:
            dev.append(f"{n}: installed {got or 'MISSING'} != pinned {want}")
    is_linux = sys.platform.startswith("linux")
    d = {"platform": sys.platform, "platform_full": platform.platform(),
         "machine": platform.machine(), "python": platform.python_version(),
         "is_linux": is_linux, "pins": pins, "installed": installed,
         "requirements_clean": not dev, "deviations": dev}
    out["steps"]["1_interpreter"] = d
    print(f"  platform          : {sys.platform} ({platform.platform()}, {platform.machine()})")
    print(f"  python            : {platform.python_version()}")
    print(f"  on Linux (cloud)  : {is_linux}")
    print(f"  requirements clean: {not dev}" + ("" if not dev else f"  DEVIATIONS: {dev}"))
    if not is_linux:
        print("  NOTE: PLAN.md Stage 1 step 1 expects a Linux cloud session. This run is "
              f"on {sys.platform}; the Linux/install half must be re-verified in the "
              "first cloud session.")
    return True                      # informational: never fails the stage by itself


# ----------------------------------------------------------------- step 3
def step3():
    head("STEP 3 — domain reachability (one light request each)")
    s = requests.Session()
    s.headers.update({**UA, "Accept": "text/html,application/xhtml+xml,application/json,*/*",
                      "Accept-Language": "en-US,en;q=0.9"})
    rows, blocked_required = [], []
    for host, (why, required, path) in DOMAINS.items():
        gap = SEBI_GAP_S if "sebi.gov.in" in host else OTHER_GAP_S
        time.sleep(gap)
        url = f"https://{host}{path}"
        code, note, ok = None, "", False
        try:
            r = s.get(url, timeout=30, allow_redirects=True, stream=True)
            code = r.status_code
            r.close()
            ok = code < 400
            note = "" if ok else f"HTTP {code}"
        except Exception as e:
            note = f"{type(e).__name__}: {str(e)[:90]}"
        rows.append({"host": host, "why": why, "required_now": required, "probe": path,
                     "status": code, "reachable": ok, "note": note})
        print(f"  {'OK ' if ok else 'BAD'}  {host:26s} {str(code or note)[:18]:20s} "
              f"{path[:34]:36s} {'REQUIRED' if required else 'later stage'}")
        if required and not ok:
            blocked_required.append(host)
    out["steps"]["3_reachability"] = {"domains": rows, "blocked_required": blocked_required}
    if blocked_required:
        fails.append("blocked required domains: " + ", ".join(blocked_required))
        return False
    return True


def step3_robots():
    head("STEP 3b — robots.txt for sites later stages intend to read (rule 5)")
    s = requests.Session(); s.headers.update(UA)
    rows = []
    for host in ROBOTS_TARGETS:
        time.sleep(SEBI_GAP_S if "sebi.gov.in" in host else OTHER_GAP_S)
        txt, code = "", None
        try:
            r = s.get(f"https://{host}/robots.txt", timeout=30)
            code, txt = r.status_code, r.text if r.status_code == 200 else ""
        except Exception as e:
            code = f"{type(e).__name__}"
        # does a global (User-agent: *) block exist, and does it Disallow: / ?
        star, disallow_all, lines = False, False, []
        for ln in txt.splitlines():
            t = ln.split("#", 1)[0].strip()
            if not t:
                continue
            k, _, v = t.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                star = (v == "*")
            elif star and k == "disallow":
                lines.append(v)
                if v == "/":
                    disallow_all = True
        rows.append({"host": host, "status": code, "has_robots": bool(txt),
                     "disallow_all_for_star": disallow_all,
                     "star_disallows": lines[:12]})
        print(f"  {host:26s} robots {str(code):5s}  blanket-disallow={disallow_all}  "
              f"rules={lines[:5]}")
    out["steps"]["3b_robots"] = rows
    print("  (Stage 4 / 8 must honour these before scraping; not a Stage 1 pass/fail.)")
    return True


# ----------------------------------------------------------------- step 4
def step4():
    head("STEP 4 — dataset integrity")
    res, ok_all = {}, True

    def chk(name, got, want, detail=""):
        nonlocal ok_all
        good = got == want
        res[name] = {"got": got, "expected": want, "ok": good, "detail": detail}
        print(f"  {'OK ' if good else 'BAD'}  {name:34s} {got} (expected {want}) {detail}")
        if not good:
            ok_all = False
            fails.append(f"{name}: {got} != {want}")

    m = dataio.load_master_with_symbols()
    chk("master rows", len(m), 652)
    chk("exclude_reason flags", int(m["exclude_reason"].notna().sum()), 29,
        detail=str(m["exclude_reason"].value_counts().to_dict()))

    t1 = dataio.load_holding_target("holding_target.csv")
    t3 = dataio.load_holding_target("holding_target_3y.csv")
    chk("excess_1y rows", len(t1), 491)
    chk("excess_3y rows", len(t3), 331)

    # both targets must be labelled against the official TRI
    for nm, t in (("1y", t1), ("3y", t3)):
        b = sorted(t["benchmark"].dropna().unique().tolist())
        good = b == ["nifty50_tri"]
        res[f"benchmark_{nm}"] = {"got": b, "ok": good}
        print(f"  {'OK ' if good else 'BAD'}  benchmark {nm:24s} {b}")
        if not good:
            ok_all = False; fails.append(f"benchmark {nm} is {b}")

    # TRI: present, sorted, unique, no nulls, no suspicious calendar gap
    tri = dataio.load_nifty_tri()
    gaps = tri.index.to_series().diff().dt.days
    worst = int(gaps.max())
    big = gaps[gaps > 6]
    tri_ok = (len(tri) > 4000 and tri.notna().all() and tri.index.is_monotonic_increasing
              and tri.index.is_unique and worst <= 6)
    res["tri"] = {"rows": len(tri), "first": str(tri.index.min().date()),
                  "last": str(tri.index.max().date()), "max_gap_days": worst,
                  "gaps_over_6d": int(len(big)), "nulls": int(tri.isna().sum()),
                  "monotonic": bool(tri.index.is_monotonic_increasing),
                  "unique": bool(tri.index.is_unique), "ok": bool(tri_ok)}
    print(f"  {'OK ' if tri_ok else 'BAD'}  {'Nifty TRI gap-free':34s} {len(tri)} rows "
          f"{tri.index.min().date()}..{tri.index.max().date()}, max gap {worst}d, "
          f"nulls {int(tri.isna().sum())}")
    if not tri_ok:
        ok_all = False; fails.append(f"TRI integrity: max gap {worst}d, rows {len(tri)}")

    out["steps"]["4_integrity"] = res
    return ok_all


def step4_estimator():
    head("STEP 4b — numpy estimator regression test")
    sys.path.insert(0, str(ROOT / "models"))
    import framework as F
    from statsmodels.discrete.discrete_model import Logit
    from statsmodels.tools.tools import add_constant

    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 3)) * [1, 5, 0.2] + [0, 10, 1]
    y = (X @ [1, .2, -3] - 1 + rng.logistic(size=400) > 0).astype(int)
    Z = (X - X.mean(0)) / X.std(0)

    # 1. unpenalised, unbalanced == statsmodels MLE
    m = F.BalancedLogit(C=1e8, balanced=False).fit(X, y)
    ref = Logit(y, add_constant(Z)).fit(disp=0)
    d_mle = float(np.abs(np.r_[m.intercept_, m.coef_] - ref.params).max())

    # 2. penalised + balanced + weighted: gradient at the optimum must vanish
    w = rng.uniform(.2, 2, 400)
    mb = F.BalancedLogit(C=1.0).fit(X, y, sample_weight=w)
    Zc = np.column_stack([np.ones(400), Z])
    b = np.r_[mb.intercept_, mb.coef_]
    p = 1 / (1 + np.exp(-Zc @ b))
    cw = np.where(y == 1, 400 / (2 * y.sum()), 400 / (2 * (400 - y.sum())))
    g = Zc.T @ (w * cw * (p - y)); g[1:] += b[1:]
    d_grad = float(np.abs(g).max())

    # 3. AUC == brute-force pairwise count, ties at 0.5
    pp = np.round(rng.uniform(size=300), 1); yy = rng.integers(0, 2, 300)
    pos, neg = pp[yy == 1], pp[yy == 0]
    brute = ((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) \
        / (len(pos) * len(neg))
    d_auc = float(abs(F.roc_auc_score(yy, pp) - brute))

    ok = d_mle < 1e-6 and d_grad < 1e-8 and d_auc < 1e-12
    out["steps"]["4b_estimator"] = {"max_abs_diff_vs_statsmodels_mle": d_mle,
                                    "max_abs_penalised_gradient": d_grad,
                                    "auc_diff_vs_brute_force": d_auc, "ok": ok}
    print(f"  vs statsmodels MLE        : {d_mle:.2e}  (tol 1e-6)")
    print(f"  penalised gradient at opt : {d_grad:.2e}  (tol 1e-8)")
    print(f"  AUC vs brute force        : {d_auc:.2e}  (tol 1e-12)")
    print(f"  {'OK ' if ok else 'BAD'}  numpy estimator regression test")
    if not ok:
        fails.append("numpy estimator regression test failed")
    return ok


# ----------------------------------------------------------------- step 5
def step5():
    head("STEP 5 — re-fetch Syngene RHP from SEBI, verify SHA-256, delete")
    man = pd.read_csv(ROOT / "data" / "verified_rhp_manifest.csv")
    row = man[(man["company"].str.contains("Syngene", case=False, na=False)) &
              (man["doc_type"] == "RHP")]
    assert len(row) == 1, f"expected 1 Syngene RHP row in the manifest, found {len(row)}"
    row = row.iloc[0]
    url, want, pages = row["url"], row["sha256"], int(row["pages"])
    print(f"  manifest: {url}\n  expect sha256 {want[:24]}… , {pages} pages")

    tmp = ROOT / "_stage1_syngene_refetch.pdf"
    s = requests.Session(); s.headers.update(UA)
    time.sleep(SEBI_GAP_S)
    got_sha, note, ok = None, "", False
    try:
        r = s.get(url, timeout=300)
        if r.status_code != 200:
            note = f"HTTP {r.status_code}"
        elif r.content[:4] != b"%PDF":
            note = f"not a PDF (starts {r.content[:8]!r})"
        else:
            tmp.write_bytes(r.content)
            got_sha = hashlib.sha256(r.content).hexdigest()
            ok = got_sha == want
            note = "sha256 matches manifest" if ok else "SHA-256 MISMATCH"
            # confirm it still verifies as a prospectus before discarding it
            import fetch_rhp as R
            vok, vnote = R._verify_is_prospectus(r.content, "Syngene International Ltd")
            note += f"; _verify_is_prospectus={vok} ({vnote})"
            ok = ok and vok
    except Exception as e:
        note = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        if tmp.exists():
            tmp.unlink()                       # PLAN.md: verify, then discard the PDF
            note += "; temp file deleted"
    out["steps"]["5_sha_roundtrip"] = {"url": url, "expected_sha256": want,
                                       "got_sha256": got_sha, "ok": ok, "note": note}
    print(f"  {'OK ' if ok else 'BAD'}  {note}")
    if not ok:
        fails.append(f"Syngene SHA-256 round-trip: {note}")
    return ok


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    results = {"1": step1(), "3": step3(), "3b": step3_robots(),
               "4": step4(), "4b": step4_estimator(), "5": step5()}
    out["required_failures"] = fails
    out["passed"] = not fails
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "stage1_checks.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    head("SUMMARY")
    for k, v in results.items():
        print(f"  step {k:3s} {'PASS' if v else 'FAIL'}")
    print(f"\n{'ALL REQUIRED CHECKS PASSED' if not fails else 'FAILURES: ' + '; '.join(fails)}")
    print("written: reports/stage1_checks.json")
    sys.exit(0 if not fails else 1)

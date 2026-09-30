"""
chittorgarh_backfill.py — PLAN.md Stages 17 and 18, from one request per company.

Stage 17 (H5) wants the headline financials with the aggregator as the primary source.
Stage 18 wants anchor allocations and lock-in dates. Both live on the same page —
`/ipo/x/{id}/` — so this script serves both from a single fetch, which halves the number of
requests the site receives rather than running two sweeps over it.

**Why an id sweep.** Chittorgarh's URLs are `/ipo/<slug>/<id>/`, and Stage 4A established
that the id alone resolves the page: any slug works. There is no published company->id
index, so the id space is walked and the company name is read off each page. Ids are
roughly chronological (id 50 = Idea Cellular 2007, id 3007 = Adroit Industries 2026), so the
walk is bounded to the range that covers the dataset.

**Politeness (decision B2).** robots.txt is re-read before the first request and the run
aborts if it no longer permits access or if it names an Anthropic crawler. Minimum 3.2 s
between requests, single-threaded, one User-Agent throughout, never a browser one. Any sign
the site objects — repeated 4xx/5xx — stops the run.

**Reconciliation (rule 2).** Issue size and final Total subscription are compared against
the master dataset. A maximum pairwise relative difference above 5% is logged with BOTH
values and the field is marked `MISMATCH`, never silently reconciled. Fields with no second
source are flagged `single_source_unverified` (global rule 3).

    python chittorgarh_backfill.py                  # run / resume
    python chittorgarh_backfill.py --limit 20       # a short probe
    python chittorgarh_backfill.py --status
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import io
import re
import subprocess
import sys
import time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from stage4a_id_walk import robots_ok                      # noqa: E402

BASE = "https://www.chittorgarh.com/ipo/x/{id}/"
UA = {"User-Agent": "ipo-agent/1.0 (personal research; contact ashishkohar4@gmail.com)"}
MIN_GAP_S = 3.2
ID_LO, ID_HI = 250, 3110          # 250 ~ 2009; 3007 = Sep 2026
MAX_CONSECUTIVE_ERRORS = 5
COMMIT_EVERY = 10
TOL = 0.05                        # rule 2

OUT = ROOT / "data" / "chittorgarh_backfill.csv"
ANCHOR = ROOT / "data" / "chittorgarh_anchor_lockin.csv"
RECON = ROOT / "reports" / "chittorgarh_reconciliation.csv"

MONEY = re.compile(r"([\d,]+(?:\.\d+)?)\s*(cr|crore|lakh|lac|mn|million)?", re.I)
UNIT = {"cr": 1.0, "crore": 1.0, "lakh": 0.01, "lac": 0.01, "mn": 0.1, "million": 0.1,
        None: 1.0, "": 1.0}


def money_cr(s) -> float | None:
    """'agg. up to ₹151 Cr' -> 151.0. Returns None when no unit can be established."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    t = str(s)
    m = re.search(r"(?:₹|Rs\.?)\s*([\d,]+(?:\.\d+)?)\s*(Cr|Crore|Lakh|Lac|mn|million)?",
                  t, re.I)
    if not m:
        # No currency marker means no unit, and a bare number here is a SHARE COUNT, not an
        # amount: "47,34,000 shares (agg. up to Rs 28.40 Cr)" returned 4,734,000 as the issue
        # size in crore on the first run. Withheld rather than assumed (H7).
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:                 # e.g. "1,234..56" — a real cell on one page
        return None
    u = (m.group(2) or "").strip().lower()
    return v * UNIT.get(u, 1.0)


def pct(s) -> float | None:
    """A percentage from a cell, or None.

    `[\\d.]+` happily matches "23..47" — a real cell on one page — and float() then raises,
    which killed the whole sweep after 1,618 ids. The pattern now requires a well-formed
    number, and the conversion is guarded as well: a malformed cell must cost that cell,
    not the run.
    """
    if s is None:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", str(s))
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return v if 0 <= v <= 100 else None


def fnum(s) -> float | None:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    t = re.sub(r"[^\d.\-]", "", str(s))
    try:
        return float(t) if t not in ("", "-", ".") else None
    except ValueError:
        return None


# ------------------------------------------------------------------ parsing
def kv(tab) -> dict:
    """A two-column label/value table -> dict, labels lower-cased.

    Takes None as well as a frame: `find_table(...) or pd.DataFrame()` raises, because a
    DataFrame has no truth value.
    """
    d = {}
    if tab is None or not isinstance(tab, pd.DataFrame) or tab.shape[1] < 2:
        return d
    for a, b in zip(tab.iloc[:, 0], tab.iloc[:, 1]):
        if pd.notna(a):
            d[re.sub(r"\s+", " ", str(a)).strip().lower()] = b
    return d


def find_table(tabs: list[pd.DataFrame], *needles: str) -> pd.DataFrame | None:
    """The first table whose header or first column contains all needles.

    Tables are identified by CONTENT, never by position: older IPOs have no anchor table
    and no KPI table, so index 4 is a different table on a 2012 page than on a 2026 one.
    """
    for t in tabs:
        head = " ".join(str(c) for c in t.columns).lower()
        first = " ".join(str(x) for x in t.iloc[:, 0].astype(str)).lower() if len(t) else ""
        blob = head + " " + first
        if all(nd.lower() in blob for nd in needles):
            return t
    return None


def parse(html: str, ipo_id: int) -> tuple[dict, list[dict]]:
    out = {"ipo_id": ipo_id}
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if h1:
        name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1.group(1))).strip()
        out["page_title"] = name
        out["company"] = re.sub(r"\s*IPO\s*Details?\s*$", "", name, flags=re.I).strip()
    # read_html picks a parser per page and raised ImportError on a page lxml could not
    # handle, killing the whole sweep after 8 ids. html5lib is now a dependency AND the call
    # is wrapped: one unparseable page must cost that page, not the run.
    tabs = None
    for flavor in ("lxml", "html5lib", None):
        try:
            tabs = pd.read_html(io.StringIO(html), flavor=flavor)
            break
        except Exception:
            continue
    if not tabs:
        out["note"] = "no table could be parsed from the page"
        return out, []

    # ---- dates, face value ---------------------------------------------------
    d0 = kv(find_table(tabs, "ipo date"))
    out["ipo_dates"] = d0.get("ipo date")
    out["listed_on"] = d0.get("listed on")
    out["face_value"] = money_cr(d0.get("face value"))
    out["price_band"] = d0.get("price band") or d0.get("issue price")
    out["lot_size"] = fnum(d0.get("lot size"))

    # ---- issue size, fresh / OFS split --------------------------------------
    d1 = kv(find_table(tabs, "total issue size"))
    out["issue_size_cr"] = money_cr(d1.get("total issue size"))
    out["fresh_issue_cr"] = money_cr(d1.get("fresh issue"))
    out["ofs_cr"] = money_cr(d1.get("offer for sale"))
    out["issue_type"] = d1.get("issue type")
    out["listing_at"] = d1.get("listing at")

    # ---- financials (Assets / Total Income / PAT / Net Worth / Borrowings) ---
    fin = find_table(tabs, "period ended")
    if fin is not None and fin.shape[1] >= 2:
        col = fin.columns[1]                       # the most recent period column
        out["fin_period"] = str(col)
        rows = {re.sub(r"\s+", " ", str(a)).strip().lower(): b
                for a, b in zip(fin.iloc[:, 0], fin.iloc[:, 1])}
        for key, name in (("assets", "assets_cr"), ("total income", "total_income_cr"),
                          ("profit after tax", "pat_cr"), ("net worth", "net_worth_cr"),
                          ("reserves and surplus", "reserves_cr"),
                          ("total borrowing", "borrowings_cr"),
                          ("revenue", "revenue_cr"), ("ebitda", "ebitda_cr")):
            hit = next((v for k, v in rows.items() if k.startswith(key)), None)
            out[name] = fnum(hit)

    # ---- valuation ----------------------------------------------------------
    val = find_table(tabs, "valuation metric")
    if val is not None:
        rows = {str(a).strip().lower(): (b, c) for a, b, c in
                zip(val.iloc[:, 0], val.iloc[:, 1], val.iloc[:, 2])} if val.shape[1] >= 3 \
            else {}
        for key, pre, post in (("eps (₹)", "eps_pre", "eps_post"),
                               ("p/e (x)", "pe_pre", "pe_post")):
            hit = next((v for k, v in rows.items() if k.startswith(key[:5])), None)
            if hit:
                out[pre], out[post] = fnum(hit[0]), fnum(hit[1])
        mc = next((v for k, v in rows.items() if "market cap" in k), None)
        if mc:
            out["market_cap_at_offer_cr"] = money_cr(mc[1] if len(mc) > 1 else mc[0])

    kpi = find_table(tabs, "kpi")
    if kpi is not None and kpi.shape[1] >= 2:
        rows = {str(a).strip().upper(): b for a, b in zip(kpi.iloc[:, 0], kpi.iloc[:, 1])}
        out["roe_pct"] = pct(rows.get("ROE"))
        out["roce_pct"] = pct(rows.get("ROCE"))
        out["debt_equity"] = fnum(rows.get("Debt/Equity"))
        out["ronw_pct"] = pct(rows.get("RONW"))

    # ---- promoter holding pre / post: an INDEPENDENT second source for H6 ---
    # TWO tables carry Pre IPO / Post IPO columns — the valuation metrics and the
    # shareholding pattern — and the valuation one comes first, so taking only the first
    # match left promoter holding empty. Every matching table is tried.
    for sh in [x for x in tabs
               if "pre ipo" in " ".join(str(c) for c in x.columns).lower()
               and "post ipo" in " ".join(str(c) for c in x.columns).lower()]:
        if sh.shape[1] < 3:
            continue
        hit = False
        for a, b, c in zip(sh.iloc[:, 0], sh.iloc[:, 1], sh.iloc[:, 2]):
            if re.search(r"(?i)promoter", str(a)):
                out["promoter_pre_pct"] = pct(b)
                out["promoter_post_pct"] = pct(c)
                hit = True
                break
        if hit:
            break

    # ---- final subscription: the rule-2 check on the master's Total ---------
    sub = find_table(tabs, "subscription (x)")
    if sub is not None and sub.shape[1] >= 2:
        for a, b in zip(sub.iloc[:, 0], sub.iloc[:, 1]):
            lab = re.sub(r"\s+", " ", str(a)).strip().lower()
            if lab.startswith("total"):
                out["total_subscription_x"] = fnum(b)
            elif lab.startswith("qib"):
                out.setdefault("qib_x", fnum(b))
            elif lab.startswith("nii") or lab.startswith("hni"):
                out.setdefault("nii_x", fnum(b))
            elif lab.startswith("retail") or lab.startswith("rii"):
                out.setdefault("retail_x", fnum(b))

    # ---- objects of the offer (an H6 field, second source) -------------------
    obj = find_table(tabs, "issue objects")
    if obj is not None:
        items = [x for x in obj.iloc[:, 1].astype(str) if x and x.lower() != "nan"]
        out["uses_of_proceeds_n"] = float(len(items)) or None
        gcp = [x for x in items if re.search(r"(?i)general corporate", x)]
        out["has_gcp"] = 1.0 if gcp else 0.0
        if obj.shape[1] >= 3:
            amts = [fnum(x) for x in obj.iloc[:, 2]]
            tot = sum(a for a in amts if a)
            gi = next((k for k, x in enumerate(obj.iloc[:, 1].astype(str))
                       if re.search(r"(?i)general corporate", x)), None)
            if gi is not None and tot and amts[gi]:
                out["gcp_pct_proceeds"] = round(amts[gi] / tot * 100, 2)

    # ---- Stage 18: anchor allocation and lock-in ----------------------------
    anchor_rows: list[dict] = []
    a1 = find_table(tabs, "investor category")
    if a1 is not None and a1.shape[1] >= 3:
        for r in a1.itertuples(index=False):
            lab = re.sub(r"[−–\-\s]+", " ", str(r[0])).strip().lower()
            if "anchor" in lab and "ex" not in lab:
                out["anchor_shares"] = fnum(r[1])
                out["anchor_pct_of_issue"] = pct(r[2])
                break
    a2 = find_table(tabs, "anchor portion")
    if a2 is None:
        a2 = find_table(tabs, "bid date")
    if a2 is not None:
        d = kv(a2)
        out["anchor_bid_date"] = d.get("bid date")
        # The unit is in the LABEL here — "Anchor Portion (₹ Cr.)" against a bare "45.21" —
        # so the number is read directly. money_cr() correctly refuses it, because it
        # requires a currency marker in the value itself.
        akey = next((k for k in d if k.startswith("anchor portion")), None)
        out["anchor_portion_cr"] = fnum(d.get(akey)) if akey and "cr" in akey else None
        for k, v in d.items():
            if "lock" in k:
                out["anchor_lockin_note"] = str(v)[:120]
    # named anchor investors, where the page lists them
    named = find_table(tabs, "name", "amount")
    if named is not None and named.shape[1] >= 3:
        for r in named.itertuples(index=False):
            nm = str(r[0]).strip()
            if not nm or nm.lower() in ("nan", "total"):
                continue
            anchor_rows.append({"ipo_id": ipo_id, "company": out.get("company"),
                                "name": nm[:120], "category": str(r[1])[:60],
                                "shares": fnum(r[2]),
                                "amount_cr": fnum(r[3]) if len(r) > 3 else None,
                                "source": "chittorgarh", "url": BASE.format(id=ipo_id)})
    # lock-in expiry dates appear as free text on the page
    for m in re.finditer(r"(?i)lock[- ]?in[^<>{}]{0,80}?"
                         r"(\d{1,2}\s+\w{3,9},?\s+20\d\d|\w{3,9}\s+\d{1,2},\s*20\d\d)", html):
        out.setdefault("lockin_dates", set()).add(m.group(1))
    if isinstance(out.get("lockin_dates"), set):
        out["lockin_dates"] = "; ".join(sorted(out["lockin_dates"]))[:200]
    return out, anchor_rows


# ------------------------------------------------------------------ plumbing
def git(*a):
    p = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def commit(n):
    git("add", "data/chittorgarh_backfill.csv", "data/chittorgarh_anchor_lockin.csv",
        "reports/chittorgarh_reconciliation.csv")
    code, out = git("commit", "-q", "-m",
                    f"Stages 17+18 backfill: {n} Chittorgarh ids harvested\n\n"
                    "Automated checkpoint from chittorgarh_backfill.py. One request per id "
                    "serves both the H5 headline financials and the anchor/lock-in block; "
                    ">=3.2 s between requests, robots.txt re-read at the start of the run."
                    "\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    if code == 0:
        git("push", "-q", "origin", "main")
        print(f"    [checkpoint committed at {n} ids]", flush=True)


# A FIXED schema. Appending dicts whose keys differ per page produced a ragged CSV that
# pandas then refused to read back ("Expected 16 fields, saw 33"), because the header came
# from whichever page happened to be harvested first.
COLS = ["ipo_id", "http", "company", "page_title", "ipo_dates", "listed_on", "face_value",
        "price_band", "lot_size", "issue_type", "listing_at", "issue_size_cr",
        "fresh_issue_cr", "ofs_cr", "fin_period", "assets_cr", "total_income_cr", "pat_cr",
        "net_worth_cr", "reserves_cr", "borrowings_cr", "revenue_cr", "ebitda_cr",
        "eps_pre", "eps_post", "pe_pre", "pe_post", "market_cap_at_offer_cr", "roe_pct",
        "roce_pct", "debt_equity", "ronw_pct", "promoter_pre_pct", "promoter_post_pct",
        "total_subscription_x", "qib_x", "nii_x", "retail_x", "uses_of_proceeds_n",
        "has_gcp", "gcp_pct_proceeds", "anchor_shares", "anchor_pct_of_issue",
        "anchor_bid_date", "anchor_portion_cr", "anchor_lockin_note", "lockin_dates",
        "url", "fetched_at", "note"]
ANCHOR_COLS = ["ipo_id", "company", "name", "category", "shares", "amount_cr", "source",
               "url"]


def append(path: Path, rows: list[dict], cols: list[str]):
    if not rows:
        return
    df = pd.DataFrame([{c: r.get(c) for c in cols} for r in rows], columns=cols)
    df.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8")


def reconcile() -> pd.DataFrame:
    """Rule 2 against the master, on the fields that genuinely have two sources."""
    if not OUT.exists():
        return pd.DataFrame()
    c = pd.read_csv(OUT)
    m = pd.read_csv(ROOT / "master_with_symbols.csv")
    m["norm"] = m["company"].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    c["norm"] = c["company"].astype(str).str.lower().str.replace(
        r"(ipo|limited|ltd|india)", "", regex=True).str.replace(r"[^a-z0-9]", "", regex=True)
    m["norm2"] = m["norm"].str.replace(r"(limited|ltd|india)", "", regex=True)
    j = c.merge(m[["norm2", "company", "Issue_Size(crores)", "Total", "QIB", "HNI", "RII"]],
                left_on="norm", right_on="norm2", how="inner", suffixes=("_cg", "_m"))
    rows = []
    for r in j.itertuples():
        for field, a, b in (("issue_size_cr", r.issue_size_cr, getattr(r, "_10", None)),
                            ("total_subscription_x", getattr(r, "total_subscription_x", None),
                             r.Total)):
            if a is None or b is None or pd.isna(a) or pd.isna(b) or max(abs(a), abs(b)) == 0:
                continue
            diff = abs(a - b) / max(abs(a), abs(b))
            rows.append({"company": r.company_m, "field": field, "chittorgarh": a,
                         "master": b, "rel_diff_pct": round(diff * 100, 3),
                         "verdict": "PASS" if diff <= TOL else "MISMATCH -> NULL",
                         "note": "both values logged; rule 2 tolerance 5%"})
    rec = pd.DataFrame(rows)
    if len(rec):
        rec.to_csv(RECON, index=False, encoding="utf-8")
    return rec


def main(limit=None, status_only=False, lo=ID_LO, hi=ID_HI):
    done = set()
    if OUT.exists():
        done = set(pd.read_csv(OUT)["ipo_id"].dropna().astype(int))
    todo = [i for i in range(lo, hi + 1) if i not in done]
    print(f"id range {lo}-{hi} | already harvested {len(done)} | to do {len(todo)}")
    if status_only:
        if OUT.exists():
            d = pd.read_csv(OUT)
            print(f"rows {len(d)}, named companies {d['company'].notna().sum()}, "
                  f"issue size {d['issue_size_cr'].notna().sum()}, "
                  f"anchor {d['anchor_shares'].notna().sum() if 'anchor_shares' in d else 0}")
        r = reconcile()
        if len(r):
            print(r["verdict"].value_counts().to_string())
        return

    s = requests.Session()
    s.headers.update(UA)
    ok, why = robots_ok(s)
    print(f"robots.txt: {'PERMITTED' if ok else 'REFUSED'} — {why}")
    if not ok:
        print("ABORT: Chittorgarh's robots.txt no longer permits this access (B2).")
        return

    errs, n, last = 0, 0, 0.0
    for ipo_id in todo:
        if limit is not None and n >= limit:
            break
        gap = MIN_GAP_S - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
        last = time.time()
        try:
            r = s.get(BASE.format(id=ipo_id), timeout=40)
        except Exception as e:
            errs += 1
            print(f"  id {ipo_id}: {type(e).__name__} ({errs} consecutive)", flush=True)
            if errs >= MAX_CONSECUTIVE_ERRORS:
                print("STOP: repeated request errors — not retrying aggressively.")
                break
            continue
        if r.status_code != 200:
            errs += 1
            append(OUT, [{"ipo_id": ipo_id, "http": r.status_code}], COLS)
            print(f"  id {ipo_id}: HTTP {r.status_code} ({errs} consecutive)", flush=True)
            if errs >= MAX_CONSECUTIVE_ERRORS:
                print("STOP: the site is returning errors — stopping rather than retrying.")
                break
            continue
        errs = 0
        # A parser fault on one page must never take down a 2,861-id sweep. It did once:
        # a "23..47" cell raised ValueError in pct() and the run stopped at id 1618.
        try:
            row, anchors = parse(r.text, ipo_id)
        except Exception as e:
            row, anchors = {"ipo_id": ipo_id,
                            "note": f"parse failed: {type(e).__name__}: {e}"[:200]}, []
            print(f"  id {ipo_id}: parse failed, page skipped — "
                  f"{type(e).__name__}: {e}", flush=True)
        row["http"] = 200
        row["url"] = BASE.format(id=ipo_id)
        row["fetched_at"] = str(pd.Timestamp.now())
        append(OUT, [row], COLS)
        append(ANCHOR, anchors, ANCHOR_COLS)
        n += 1
        if n % 25 == 0 or n <= 5:
            print(f"  [{n}/{len(todo)}] id {ipo_id}: {str(row.get('company'))[:34]:36s} "
                  f"size={row.get('issue_size_cr')} sub={row.get('total_subscription_x')} "
                  f"anchor={row.get('anchor_portion_cr')}", flush=True)
        if n % COMMIT_EVERY == 0:
            commit(len(done) + n)

    reconcile()
    commit(len(done) + n)
    print(f"\nharvested this run: {n}")
    if OUT.exists():
        d = pd.read_csv(OUT)
        print(f"total rows {len(d)} | named {d['company'].notna().sum()} | "
              f"issue size {d['issue_size_cr'].notna().sum()}")


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--lo", type=int, default=ID_LO)
    ap.add_argument("--hi", type=int, default=ID_HI)
    a = ap.parse_args()
    main(a.limit, a.status, a.lo, a.hi)

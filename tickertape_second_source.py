"""
tickertape_second_source.py - Tickertape as the rule-2 second source for the H59 block.

H58 as amended on 6 November 2026 ratified Tickertape as the ONE permitted second source:
personal, non-commercial reading only, >=3 s between requests, no S&P-derived field, and
robots.txt re-read at the start of every run. Screener.in and Trendlyne are forbidden by
their own terms, and the paid financial MCPs are not to be used.

**How a company is resolved.** From Tickertape's own published stocks sitemap, matched on
`dataio.norm_name` EXACTLY. No fuzzy matching: H28 says name similarity cannot identify a
company, so a name that does not match exactly is simply not resolved.

**Which fields.** Only the four the aggregator also publishes, so that rule 2 has something
to compare:

    incTrev -> total_income_cr      balTeq  -> net_worth_cr
    incNinc -> pat_cr               balTdeb -> borrowings_cr
    incEbi  -> ebitda_cr            balCsti -> cash_cr

**Which fields are deliberately NOT taken.** Every per-share figure - EPS, NAV, book value,
and any ratio built on them. Tickertape restates per-share history for splits and bonuses,
so its `incEps` for Varun Beverages FY2016 is 0.1377 against an RHP EPS in rupees. The two
are not the same quantity and reconciling them would manufacture a mismatch. Per-share
values come from the RHP and from Chittorgarh's own stated figures. No S&P-derived field
(ratings, scores) is read at all.

**The unit is established by agreement, not assumed.** Tickertape does not label the unit in
this payload. Nothing is scaled; the values are compared as-is against the aggregator, and
the reconciliation itself is what establishes the scale. A field that disagrees by more than
5% is NULLed with both values logged (rule 2), which is also what a wrong unit would produce.

    python tickertape_second_source.py --self-test
    python tickertape_second_source.py --match      # resolve ids -> Tickertape urls
    python tickertape_second_source.py              # H9 batch: fetch, cache, extract
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dataio import norm_name                                     # noqa: E402

HOST = "https://www.tickertape.in"
SITEMAP = f"{HOST}/sitemaps/stocks/sitemap.xml"
UA = {"User-Agent": "ipo-agent/1.0 (personal non-commercial research)"}
MIN_GAP_S = 3.2                 # H58: >= 3 s
COMMIT_EVERY = 10               # H9
MAX_CONSECUTIVE_ERRORS = 5

LOCAL = ROOT / "_local" / "tickertape"
MATCH = ROOT / "data" / "tickertape_match.csv"
OUT = ROOT / "data" / "tickertape_annuals.csv"

# Tickertape field -> our name. Per-share fields are absent BY DESIGN (see the docstring).
INCOME = {"incTrev": "total_income_cr", "incNinc": "pat_cr", "incEbi": "ebitda_cr"}
BALANCE = {"balTeq": "net_worth_cr", "balTdeb": "borrowings_cr", "balCsti": "cash_cr"}
FORBIDDEN = ("incEps", "incDps", "balTcso", "eps", "nav", "bookValue", "rating", "score")
OUT_COLS = ["ipo_id", "company", "tt_code", "tt_url", "display_period", "end_date",
            "reporting", "total_income_cr", "pat_cr", "ebitda_cr", "net_worth_cr",
            "borrowings_cr", "cash_cr", "fetched_at"]


def slug_rows(xml: str) -> list[dict]:
    """Tickertape's stocks sitemap -> one row per stock, with its code and normalised name."""
    rows = []
    for u in re.findall(r"<loc>(.*?)</loc>", xml):
        slug = u.rsplit("/", 1)[1]
        m = re.match(r"(.+)-([A-Z0-9]{2,8})$", slug)
        if not m:
            continue
        name = m.group(1).replace("-", " ")
        rows.append({"tt_url": u, "tt_slug": slug, "tt_name": name, "tt_code": m.group(2),
                     "norm": norm_name(name)})
    return rows


def match_companies(companies: pd.DataFrame, sitemap_rows: list[dict]) -> pd.DataFrame:
    """Exact normalised-name resolution only (H28). Unresolved rows keep a NULL url."""
    tt = pd.DataFrame(sitemap_rows)
    if len(tt):
        tt = tt.drop_duplicates("norm")
    else:
        tt = pd.DataFrame(columns=["tt_url", "tt_slug", "tt_name", "tt_code", "norm"])
    c = companies.copy()
    c["norm"] = c["company"].map(norm_name)
    j = c.merge(tt[["norm", "tt_url", "tt_code", "tt_name"]], on="norm", how="left")
    j["resolved"] = j["tt_url"].notna()
    return j


def annual_rows(html: str, ipo_id: int, company: str | None = None,
                tt_code: str | None = None, tt_url: str | None = None) -> list[dict]:
    """The annual income and balance-sheet blocks of a stock page, joined on end date."""
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        pp = json.loads(m.group(1))["props"]["pageProps"]
    except Exception:
        return []
    by_date: dict[str, dict] = {}
    for key, mapping in (("income-normal-annual", INCOME),
                         ("balancesheet-normal-annual", BALANCE)):
        for rec in (pp.get(key) or []):
            if not isinstance(rec, dict):
                continue
            ed = str(rec.get("endDate") or "")[:10]
            if not re.match(r"\d{4}-\d{2}-\d{2}$", ed):
                continue
            r = by_date.setdefault(ed, {
                "ipo_id": ipo_id, "company": company, "tt_code": tt_code,
                "tt_url": tt_url, "end_date": ed,
                "display_period": rec.get("displayPeriod"),
                "reporting": rec.get("reporting")})
            for src, dst in mapping.items():
                v = rec.get(src)
                r[dst] = float(v) if isinstance(v, (int, float)) else None
    return [by_date[k] for k in sorted(by_date)]

# ------------------------------------------------------------------ the H9 batch
def robots_allows(session) -> tuple[bool, str]:
    """H58: robots.txt is re-read at the START OF EVERY RUN, never cached between runs."""
    r = session.get(f"{HOST}/robots.txt", timeout=30)
    if r.status_code != 200:
        return False, f"robots.txt returned HTTP {r.status_code} - treated as refused"
    groups, cur = {}, []
    for line in r.text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            cur = cur if cur and cur[-1] == "pending" else []
            cur.append(v)
            groups.setdefault(v, [])
        elif k == "disallow":
            for ua in cur:
                groups.setdefault(ua, []).append(v)
    for ua in ("ClaudeBot", "Claude-User", "ipo-agent", "*"):
        if ua in groups:
            bad = [d for d in groups[ua] if d in ("/", "/stocks", "/stocks/")]
            if bad:
                return False, f"robots.txt disallows {bad} for User-agent: {ua}"
    dis = groups.get("*", [])
    return True, f"permitted; User-agent:* disallows {dis}"


def fetch_sitemap(session) -> str:
    cached = LOCAL / "stocks_sitemap.xml"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    r = session.get(SITEMAP, timeout=60)
    r.raise_for_status()
    LOCAL.mkdir(parents=True, exist_ok=True)
    cached.write_text(r.text, encoding="utf-8")
    return r.text


def build_match() -> pd.DataFrame:
    import requests
    s = requests.Session()
    s.headers.update(UA)
    allowed, why = robots_allows(s)
    print(f"robots.txt: {'PERMITTED' if allowed else 'REFUSED'} - {why}")
    if not allowed:
        raise SystemExit("ABORT: Tickertape's robots.txt does not permit this access.")
    fy = pd.read_csv(ROOT / "data" / "chittorgarh_mainboard_fy.csv")
    j = match_companies(fy[["ipo_id", "company", "fy_period", "fy_period_parsed"]],
                        slug_rows(fetch_sitemap(s)))
    j.to_csv(MATCH, index=False, encoding="utf-8")
    print(f"resolved {int(j['resolved'].sum())} of {len(j)} mainboard companies")
    return j


def batch(limit=None) -> int:
    import time
    import requests
    if not MATCH.exists():
        build_match()
    m = pd.read_csv(MATCH)
    m = m[m["resolved"] == True]                                     # noqa: E712
    done: set[int] = set()
    if OUT.exists():
        d = pd.read_csv(OUT)
        if len(d):
            done = set(d["ipo_id"].dropna().astype(int))
    todo = m[~m["ipo_id"].astype(int).isin(done)]
    print(f"resolved companies to fetch: {len(todo)}")
    if not len(todo):
        return 0
    LOCAL.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    allowed, why = robots_allows(s)
    print(f"robots.txt: {'PERMITTED' if allowed else 'REFUSED'} - {why}")
    if not allowed:
        print("ABORT: Tickertape's robots.txt does not permit this access (H58).")
        return 0
    errs = n = 0
    last = 0.0
    for r0 in todo.itertuples(index=False):
        if limit is not None and n >= limit:
            break
        ipo_id, code, url = int(r0.ipo_id), str(r0.tt_code), str(r0.tt_url)
        cached = LOCAL / f"{code}.html"
        if cached.exists():
            html = cached.read_text(encoding="utf-8", errors="replace")
        else:
            gap = MIN_GAP_S - (time.time() - last)
            if gap > 0:
                time.sleep(gap)
            last = time.time()
            try:
                resp = s.get(url, timeout=40)
            except Exception as e:
                errs += 1
                print(f"  {code}: {type(e).__name__} ({errs} consecutive)", flush=True)
                if errs >= MAX_CONSECUTIVE_ERRORS:
                    print("STOP: repeated request errors - not retrying aggressively.")
                    break
                continue
            if resp.status_code != 200:
                # H58: a block is never worked around. Logged, failed over to the RHP.
                errs += 1
                print(f"  {code}: HTTP {resp.status_code} ({errs} consecutive)", flush=True)
                _append([{"ipo_id": ipo_id, "company": r0.company, "tt_code": code,
                          "tt_url": url, "reporting": f"HTTP_{resp.status_code}",
                          "fetched_at": str(pd.Timestamp.now())}])
                if errs >= MAX_CONSECUTIVE_ERRORS:
                    print("STOP: the site is returning errors - stopping, not retrying.")
                    break
                continue
            errs = 0
            html = resp.text
            cached.write_text(html, encoding="utf-8")
        rows = annual_rows(html, ipo_id, r0.company, code, url)
        stamp = str(pd.Timestamp.now())
        if not rows:
            rows = [{"ipo_id": ipo_id, "company": r0.company, "tt_code": code,
                     "tt_url": url, "reporting": "no_annual_block"}]
        for x in rows:
            x["fetched_at"] = stamp
        _append(rows)
        n += 1
        if n % 25 == 0 or n <= 3:
            print(f"  [{n}/{len(todo)}] {code}: {str(r0.company)[:30]:32s} "
                  f"years={len(rows)}", flush=True)
        if n % COMMIT_EVERY == 0:
            _checkpoint(n)
    _checkpoint(n)
    return n


def _append(rows: list[dict]):
    df = pd.DataFrame([{c: r.get(c) for c in OUT_COLS} for r in rows], columns=OUT_COLS)
    df.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")


def _checkpoint(n: int):
    import subprocess
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    g("add", "data/tickertape_annuals.csv", "data/tickertape_match.csv")
    r = g("commit", "-q", "-m",
          f"H59 Task 1: Tickertape second source, {n} companies read\n\n"
          "Automated H9 checkpoint. Personal non-commercial reading, >=3.2 s between "
          "requests, robots.txt re-read at the start of the run (H58). Only the six "
          "fields the aggregator also publishes; no per-share and no S&P-derived field. "
          "Nothing is scaled - the reconciliation establishes the scale."
          "\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    if r.returncode == 0:
        g("push", "-q", "origin", "main")
        print(f"    [checkpoint committed at {n} companies]", flush=True)


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

    print("[1] the sitemap is the resolver, and the match is EXACT (H28)")
    xml = ("<urlset><url><loc>https://www.tickertape.in/stocks/varun-beverages-VARB</loc>"
           "</url><url><loc>https://www.tickertape.in/stocks/varun-mercantile-VARU</loc>"
           "</url><url><loc>https://www.tickertape.in/stocks/3m-india-TMIN</loc></url>"
           "<url><loc>https://www.tickertape.in/mutualfunds/x</loc></url></urlset>")
    rows = slug_rows(xml)
    chk("a stock url yields name and code",
        {"tt_code": "VARB"}.items() <= rows[0].items() and rows[0]["tt_name"] == "varun beverages",
        str(rows[0]))
    chk("three stocks parsed, the non-stock url ignored", len(rows) == 3, str(len(rows)))
    comp = pd.DataFrame({"ipo_id": [1, 2, 3],
                         "company": ["Varun Beverages", "3M India Ltd", "Varun Beverage"]})
    j = match_companies(comp, rows).set_index("ipo_id")
    chk("an exact normalised name resolves", j.loc[1, "tt_code"] == "VARB")
    chk("a suffix difference still resolves (norm_name strips Ltd)",
        j.loc[2, "tt_code"] == "TMIN", str(j.loc[2, "tt_code"]))
    chk("a NEAR name does NOT resolve - no fuzzy matching (H28)",
        pd.isna(j.loc[3, "tt_url"]) and not j.loc[3, "resolved"], str(j.loc[3, "tt_url"]))

    print("[2] the annual blocks are read and joined on the end date")
    page = ('<html><script id="__NEXT_DATA__" type="application/json">' + json.dumps({
        "props": {"pageProps": {
            "income-normal-annual": [
                {"displayPeriod": "FY 2024", "endDate": "2024-03-31T00:00:00.000Z",
                 "reporting": "consolidated", "incTrev": 2470.89, "incNinc": 78.8,
                 "incEbi": 150.5, "incEps": 0.137},
                {"displayPeriod": "FY 2023", "endDate": "2023-03-31T00:00:00.000Z",
                 "reporting": "consolidated", "incTrev": 2422.57, "incNinc": 59.93,
                 "incEbi": None, "incEps": 0.1}],
            "balancesheet-normal-annual": [
                {"displayPeriod": "FY 2024", "endDate": "2024-03-31T00:00:00.000Z",
                 "reporting": "consolidated", "balTeq": 422.37, "balTdeb": 300.1,
                 "balCsti": 25.0, "balTcso": 123.4},
                {"displayPeriod": "FY 2023", "endDate": "2023-03-31T00:00:00.000Z",
                 "reporting": "consolidated", "balTeq": 282.51, "balTdeb": 280.0,
                 "balCsti": 10.0}],
        }}}) + "</script></html>")
    a = annual_rows(page, 1767, "Bansal Wire Industries", "BANW", "u")
    chk("one row per end date, oldest first",
        [r["end_date"] for r in a] == ["2023-03-31", "2024-03-31"],
        str([r["end_date"] for r in a]))
    chk("income and balance sheet land on the SAME row",
        a[1]["total_income_cr"] == 2470.89 and a[1]["net_worth_cr"] == 422.37
        and a[1]["pat_cr"] == 78.8 and a[1]["borrowings_cr"] == 300.1
        and a[1]["cash_cr"] == 25.0, str(a[1]))
    chk("a null in the payload stays None, never 0", a[0]["ebitda_cr"] is None, str(a[0]))
    chk("provenance travels with the row",
        a[1]["tt_url"] == "u" and a[1]["tt_code"] == "BANW"
        and a[1]["reporting"] == "consolidated" and a[1]["ipo_id"] == 1767, str(a[1]))

    print("[3] per-share and S&P-derived fields are NOT taken (H58)")
    chk("no EPS field on the row", not any(k for k in a[1] if "eps" in k.lower()), str(a[1].keys()))
    chk("no share-count field on the row", "balTcso" not in a[1] and not any(
        "share" in k.lower() for k in a[1]), str(a[1].keys()))
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    import io as _io, tokenize as _tok
    code = " ".join(t.string for t in _tok.generate_tokens(_io.StringIO(body).readline)
                    if t.type in (_tok.NAME, _tok.OP, _tok.NUMBER, _tok.STRING))
    for bad in ("incEps", "incDps", "balTcso"):
        chk(f"{bad} is never mapped to an output field",
            f'"{bad}": "' not in code, bad)
    chk("the mapped fields are exactly the six that the aggregator also publishes",
        sorted(list(INCOME.values()) + list(BALANCE.values())) ==
        ["borrowings_cr", "cash_cr", "ebitda_cr", "net_worth_cr", "pat_cr",
         "total_income_cr"], str(sorted(list(INCOME.values()) + list(BALANCE.values()))))

    print("[4] nothing is scaled, nothing is filled")
    for bad in ("* 10", "/ 10", "* 100", "fillna", "ffill", "annualis", "interpolat"):
        chk(f"no {bad!r} in the module code", bad not in code.lower())

    print("[5] a malformed page costs that page, not the run")
    chk("no __NEXT_DATA__ -> no rows", annual_rows("<html>x</html>", 1) == [])
    chk("bad json -> no rows",
        annual_rows('<script id="__NEXT_DATA__">{oops</script>', 1) == [])
    chk("missing blocks -> no rows",
        annual_rows('<script id="__NEXT_DATA__">{"props":{"pageProps":{}}}</script>', 1) == [])
    chk("a record with no end date is skipped",
        annual_rows('<script id="__NEXT_DATA__">' + json.dumps(
            {"props": {"pageProps": {"income-normal-annual": [{"incTrev": 1}]}}})
            + "</script>", 1) == [])

    print("[6] politeness is in the module, not in the operator's memory (H58)")
    chk("gap at least 3 s", MIN_GAP_S >= 3.0, str(MIN_GAP_S))
    chk("checkpoint at least every 10 items", COMMIT_EVERY <= 10, str(COMMIT_EVERY))
    chk("the User-Agent names the client and is not a browser",
        "ipo-agent" in UA["User-Agent"] and "Mozilla" not in UA["User-Agent"],
        UA["User-Agent"])
    chk("the User-Agent carries no email address", "@" not in UA["User-Agent"],
        UA["User-Agent"])

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--match", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.match:
        build_match()
    elif a.self_test:
        raise SystemExit(self_test())
    else:
        print(f"companies read this run: {batch(a.limit)}")

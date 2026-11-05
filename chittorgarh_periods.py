"""
chittorgarh_periods.py - every period column on a Chittorgarh IPO page, not just the latest.

Task 4.1(a) of the 5 November brief: a stub period (9M, 6M, any month-end that is not
31 March) is NEVER annualised. The full-year figure is taken from the same page if it is
shown, otherwise the value stays NULL.

`chittorgarh_backfill.parse()` reads only `fin.columns[1]`, the most recent period, which
is why 279 of 482 mainboard rows carry a stub. The page itself shows up to three periods
side by side (Bansal Wire: 31 Mar 2024 / 31 Mar 2023 / 31 Mar 2022), so the full year a
stub row needs is usually already on the page that was already fetched.

This module adds the long-form read - one row per (ipo_id, period) - and nothing else.
`parse()` is untouched, so `data/chittorgarh_backfill.csv` keeps its schema and its history.

    python chittorgarh_periods.py --self-test
    python chittorgarh_periods.py               # H9 batch: fetch, cache, parse, checkpoint
    python chittorgarh_periods.py --status
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from io import StringIO
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# `find_table()` and `fnum()` are REUSED, never copied: a second copy of the label matching
# would drift away from the one that produced the existing CSV.
from chittorgarh_backfill import BASE, find_table, fnum          # noqa: E402

# The same labels `parse()` reads, in the same order. Anything the table does not carry
# stays None - rule 1: a missing value costs one cell, a guessed one corrupts every ratio.
FIELDS = (("assets", "assets_cr"),
          ("total income", "total_income_cr"),
          ("profit after tax", "pat_cr"),
          ("net worth", "net_worth_cr"),
          ("reserves and surplus", "reserves_cr"),
          ("total borrowing", "borrowings_cr"),
          ("revenue", "revenue_cr"),
          ("ebitda", "ebitda_cr"))

UNIT = "INR_crore"        # verified on the page itself: "Amount in ₹ Crore" (Task 4.1)


def period_date(label) -> pd.Timestamp | None:
    """'31 Mar 2024' -> Timestamp. A column that is not a date (a note, a blank) -> None."""
    t = re.sub(r"\s+", " ", str(label)).strip()
    if not re.search(r"20\d\d", t):
        return None
    d = pd.to_datetime(t, dayfirst=True, errors="coerce")
    return None if pd.isna(d) else d


def period_kind(label) -> str:
    """31 March is a full Indian financial year. Any other month-end is a stub.

    The page gives a DATE, never a label like '9M', so the kind is established from the
    date and nothing else. A stub is marked, never scaled up to a year.
    """
    d = period_date(label)
    if d is None:
        return "MISSING"
    return "FULL_FY" if (d.month == 3 and d.day == 31) else "STUB"


def parse_periods(html: str, ipo_id: int) -> list[dict]:
    """One row per period column of the page's 'Period Ended' table, in page order.

    `parse()` keeps only `fin.columns[1]`, so a company that filed on a stub period had no
    full year in the dataset even when the page showed two beside it.
    """
    company = None
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if h1:
        name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1.group(1))).strip()
        company = re.sub(r"\s*IPO\s*Details?\s*$", "", name, flags=re.I).strip()

    tabs = None
    for flavor in ("lxml", "html5lib", None):
        try:
            tabs = pd.read_html(StringIO(html), flavor=flavor)
            break
        except Exception:
            continue
    if not tabs:
        return []
    fin = find_table(tabs, "period ended")
    if fin is None or fin.shape[1] < 2:
        return []

    labels = {re.sub(r"\s+", " ", str(a)).strip().lower(): i
              for i, a in enumerate(fin.iloc[:, 0])}
    rows: list[dict] = []
    for ci in range(1, fin.shape[1]):
        col = fin.columns[ci]
        d = period_date(col)
        if d is None:
            continue
        r = {"ipo_id": ipo_id, "company": company, "fin_period": str(col).strip(),
             "fin_period_parsed": d.date(), "period_kind": period_kind(col),
             "col_index": ci, "unit": UNIT, "url": BASE.format(id=ipo_id)}
        for key, name in FIELDS:
            i = next((i for lab, i in labels.items() if lab.startswith(key)), None)
            r[name] = fnum(fin.iloc[i, ci]) if i is not None else None
        rows.append(r)
    return rows


def latest_full_fy(rows: list[dict]) -> dict | None:
    """The newest 31-March row on the page, or None when the page shows no full year."""
    fy = [r for r in rows if r.get("period_kind") == "FULL_FY"]
    if not fy:
        return None
    return max(fy, key=lambda r: r["fin_period_parsed"])

# ------------------------------------------------------------------ the H9 batch
MAINBOARD = ROOT / "data" / "chittorgarh_mainboard_periods.csv"
OUT = ROOT / "data" / "chittorgarh_period_financials.csv"
CACHE = ROOT / "_local" / "cg_html_cache"      # gitignored; makes a re-parse free
MIN_GAP_S = 3.2                                # B2
COMMIT_EVERY = 10                              # H9
MAX_CONSECUTIVE_ERRORS = 5
OUT_COLS = ["ipo_id", "company", "fin_period", "fin_period_parsed", "period_kind",
            "col_index", "unit", "assets_cr", "total_income_cr", "pat_cr", "net_worth_cr",
            "reserves_cr", "borrowings_cr", "revenue_cr", "ebitda_cr", "url", "fetched_at"]


def id_from_url(u) -> int | None:
    m = re.search(r"/ipo/x/(\d+)/", str(u))
    return int(m.group(1)) if m else None


def work_list() -> list[int]:
    """Mainboard ids (H33) not yet harvested. Resumable by construction."""
    src = pd.read_csv(MAINBOARD)
    ids = [i for i in (id_from_url(u) for u in src["url"]) if i is not None]
    seen: list[int] = []
    for i in ids:                      # keep page order, drop duplicates
        if i not in seen:
            seen.append(i)
    done: set[int] = set()
    if Path(OUT).exists():
        d = pd.read_csv(OUT)
        if len(d):
            done = set(d["ipo_id"].dropna().astype(int))
    return [i for i in seen if i not in done]


def batch(limit=None) -> int:
    import time
    import requests
    from stage4a_id_walk import robots_ok
    from chittorgarh_backfill import UA, commit as _commit

    todo = work_list()
    print(f"mainboard ids to do: {len(todo)}")
    if not todo:
        return 0
    CACHE.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    ok, why = robots_ok(s)                 # B2: re-read at the start of EVERY run
    print(f"robots.txt: {'PERMITTED' if ok else 'REFUSED'} - {why}")
    if not ok:
        print("ABORT: Chittorgarh's robots.txt no longer permits this access (B2).")
        return 0

    errs = n = 0
    last = 0.0
    for ipo_id in todo:
        if limit is not None and n >= limit:
            break
        cached = CACHE / f"{ipo_id}.html"
        if cached.exists():
            html = cached.read_text(encoding="utf-8", errors="replace")
        else:
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
                    print("STOP: repeated request errors - not retrying aggressively.")
                    break
                continue
            if r.status_code != 200:
                errs += 1
                print(f"  id {ipo_id}: HTTP {r.status_code} ({errs} consecutive)", flush=True)
                if errs >= MAX_CONSECUTIVE_ERRORS:
                    print("STOP: the site is returning errors - stopping, not retrying.")
                    break
                continue
            errs = 0
            html = r.text
            cached.write_text(html, encoding="utf-8")
        try:
            rows = parse_periods(html, ipo_id)
        except Exception as e:
            print(f"  id {ipo_id}: parse failed - {type(e).__name__}: {e}", flush=True)
            rows = []
        stamp = str(pd.Timestamp.now())
        if not rows:
            rows = [{"ipo_id": ipo_id, "period_kind": "MISSING",
                     "url": BASE.format(id=ipo_id)}]
        for r0 in rows:
            r0["fetched_at"] = stamp
        frame = pd.DataFrame([{c: r0.get(c) for c in OUT_COLS} for r0 in rows],
                             columns=OUT_COLS)
        frame.to_csv(OUT, mode="a", header=not Path(OUT).exists(), index=False,
                     encoding="utf-8")
        n += 1
        if n % 25 == 0 or n <= 3:
            print(f"  [{n}/{len(todo)}] id {ipo_id}: "
                  f"{str(rows[0].get('company'))[:30]:32s} "
                  f"periods={len(rows)} kinds={[x.get('period_kind') for x in rows]}",
                  flush=True)
        if n % COMMIT_EVERY == 0:
            _git_checkpoint(n)
    _git_checkpoint(n)
    return n


def _git_checkpoint(n: int):
    import subprocess
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    g("add", "data/chittorgarh_period_financials.csv")
    r = g("commit", "-q", "-m",
          f"Task 4.1a: all period columns harvested for {n} mainboard ids\n\n"
          "Automated H9 checkpoint from chittorgarh_periods.py. One request per id, "
          ">=3.2 s apart, robots.txt re-read at the start of the run (B2). A stub period "
          "is marked, never annualised; the full year comes from another column of the "
          "same page or stays NULL."
          "\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    if r.returncode == 0:
        g("push", "-q", "origin", "main")
        print(f"    [checkpoint committed at {n} ids]", flush=True)


def write_fy_table() -> pd.DataFrame:
    """Collapse the harvested long table to one full-year row per IPO and write it."""
    long = pd.read_csv(OUT)
    t = full_fy_table(long)
    t.to_csv(FY_TABLE, index=False, encoding="utf-8")
    return t


def coverage(t: pd.DataFrame) -> pd.DataFrame:
    """Per field: how many IPOs now carry a full-year value, and on what basis."""
    rows = []
    for c in VALUE_COLS:
        rows.append({"field": c,
                     "full_fy_values": int(t[c].notna().sum()),
                     "of_ipos": len(t),
                     "coverage_pct": round(100.0 * t[c].notna().sum() / max(len(t), 1), 1),
                     "prev_fy_values": int(t[f"fy_prev_{c}"].notna().sum())})
    return pd.DataFrame(rows)


def status():
    if not Path(OUT).exists():
        print("nothing harvested yet")
        return
    d = pd.read_csv(OUT)
    print(f"rows {len(d)} | ids {d['ipo_id'].nunique()}")
    print(d["period_kind"].value_counts(dropna=False).to_string())

# ------------------------------------------------- one row per IPO, on a full year only
VALUE_COLS = [c for _, c in FIELDS]
FY_TABLE = ROOT / "data" / "chittorgarh_mainboard_fy.csv"


def full_fy_table(long: pd.DataFrame) -> pd.DataFrame:
    """The long per-period table collapsed to one row per ipo_id, on a FULL YEAR only.

    Task 4.1(a): a stub period is marked and the full-year figure is taken from another
    column of the SAME page; where the page shows no 31-March column the values stay NULL
    with the reason recorded. Nothing is scaled, nothing is carried from another company
    and nothing is carried from the stub.
    """
    out = []
    for ipo_id, g in long.groupby("ipo_id", sort=True):
        g = g.sort_values("col_index")
        latest = g.iloc[0]
        fy = g[g["period_kind"] == "FULL_FY"].sort_values("fin_period_parsed",
                                                          ascending=False)
        r = {"ipo_id": int(ipo_id),
             "company": next((c for c in g["company"] if isinstance(c, str)), None),
             "latest_period": latest.get("fin_period"),
             "latest_period_kind": latest.get("period_kind"),
             "n_periods_on_page": int((g["period_kind"] != "MISSING").sum()),
             "unit": UNIT, "url": BASE.format(id=int(ipo_id))}
        if len(fy):
            top = fy.iloc[0]
            r["fy_period"] = top["fin_period"]
            r["fy_period_parsed"] = top["fin_period_parsed"]
            r["fy_source"] = f"same_page_column_{int(top['col_index'])}"
            for c in VALUE_COLS:
                r[c] = top.get(c)
            r["usable_for_h59"] = True
            if len(fy) > 1:
                prev = fy.iloc[1]
                r["fy_prev_period"] = prev["fin_period"]
                for c in VALUE_COLS:
                    r[f"fy_prev_{c}"] = prev.get(c)
        else:
            r["fy_period"] = None
            r["fy_period_parsed"] = None
            r["fy_source"] = "no_full_fy_on_page"
            for c in VALUE_COLS:
                r[c] = None
            r["usable_for_h59"] = False
        out.append(r)
    cols = (["ipo_id", "company", "latest_period", "latest_period_kind",
             "n_periods_on_page", "fy_period", "fy_period_parsed", "fy_source",
             "usable_for_h59", "unit", "url"] + VALUE_COLS
            + ["fy_prev_period"] + [f"fy_prev_{c}" for c in VALUE_COLS])
    return pd.DataFrame(out).reindex(columns=cols)


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

    THREE = """<html><h1>Bansal Wire Industries IPO Details</h1>
    <table><tr><th>Period Ended</th><th>31 Mar 2024</th><th>31 Mar 2023</th>
      <th>31 Mar 2022</th></tr>
    <tr><td>Assets</td><td>1,562.74</td><td>1,344.55</td><td>1,089.23</td></tr>
    <tr><td>Total Income</td><td>2,466.17</td><td>2,421.69</td><td>1,834.95</td></tr>
    <tr><td>Profit After Tax</td><td>78.80</td><td>59.76</td><td>47.26</td></tr>
    <tr><td>Net Worth</td><td>310.31</td><td>231.42</td><td>171.64</td></tr>
    <tr><td>Reserves and Surplus</td><td>280.31</td><td>201.42</td><td>141.64</td></tr>
    <tr><td>Total Borrowing</td><td>841.23</td><td>761.15</td><td>614.84</td></tr>
    </table></html>"""

    STUB_THEN_FY = """<html><h1>ACME Solar Holdings IPO Details</h1>
    <table><tr><th>Period Ended</th><th>30 Jun 2024</th><th>31 Mar 2024</th>
      <th>31 Mar 2023</th></tr>
    <tr><td>Assets</td><td>13,985.14</td><td>13,447.00</td><td>9,880.00</td></tr>
    <tr><td>Total Income</td><td>340.01</td><td>1,466.00</td><td>1,361.00</td></tr>
    <tr><td>Profit After Tax</td><td>1.39</td><td>697.78</td><td>-3.17</td></tr>
    <tr><td>Net Worth</td><td>1,942.12</td><td>1,940.00</td><td>1,230.00</td></tr>
    </table></html>"""

    print("[1] every period column is read, not only the most recent")
    rows = parse_periods(THREE, 1)
    chk("three periods -> three rows", len(rows) == 3, f"got {len(rows)}")
    chk("periods in page order",
        [r["fin_period"] for r in rows] == ["31 Mar 2024", "31 Mar 2023", "31 Mar 2022"],
        str([r.get("fin_period") for r in rows]))
    chk("column 1 matches parse()'s single row",
        rows[0]["net_worth_cr"] == 310.31 and rows[0]["pat_cr"] == 78.80,
        str(rows[0]))
    chk("the prior year is read from column 2",
        rows[1]["net_worth_cr"] == 231.42 and rows[1]["total_income_cr"] == 2421.69,
        str(rows[1]))
    chk("the oldest year is read from column 3",
        rows[2]["borrowings_cr"] == 614.84, str(rows[2]))
    chk("ipo_id and company on every row",
        all(r["ipo_id"] == 1 and r["company"] == "Bansal Wire Industries" for r in rows),
        str([r.get("company") for r in rows]))

    print("[2] period_kind: 31 March is a full Indian FY, any other month-end is a stub")
    chk("31 Mar -> FULL_FY", all(r["period_kind"] == "FULL_FY" for r in rows))
    s = parse_periods(STUB_THEN_FY, 2)
    chk("30 Jun -> STUB", s[0]["period_kind"] == "STUB", str(s[0]))
    chk("the FULL_FY beside a stub is kept as its own row",
        s[1]["fin_period"] == "31 Mar 2024" and s[1]["period_kind"] == "FULL_FY"
        and s[1]["pat_cr"] == 697.78, str(s[1]))
    chk("fin_period_parsed is a date", str(s[0]["fin_period_parsed"]) == "2024-06-30",
        str(s[0].get("fin_period_parsed")))

    print("[3] NOTHING is annualised and nothing is carried across periods (rule 1)")
    # CODE only: comments and docstrings are stripped, so the prohibition is tested
    # against what runs, not against the prose that describes it. A test that a word is
    # absent from a docstring tests the documentation.
    import io as _io, tokenize as _tok
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    code = " ".join(
        t.string for t in _tok.generate_tokens(_io.StringIO(body).readline)
        if t.type in (_tok.NAME, _tok.OP, _tok.NUMBER)).lower()
    for bad in ("* 12", "/ 9", "/ 6", "annualis", "annualiz", "ffill", "fillna",
                "interpolat", "bfill"):
        chk(f"no {bad!r} in the module CODE", bad not in code)
    chk("the prohibition test can fail", "annualis" in ("x annualise y"))
    chk("a field absent from the table is None, never 0",
        s[0].get("ebitda_cr") is None and s[0].get("reserves_cr") is None, str(s[0]))

    print("[4] latest_full_fy picks the newest 31 March row, or None")
    chk("stub page -> 31 Mar 2024", latest_full_fy(s)["fin_period"] == "31 Mar 2024")
    chk("three FY page -> the newest", latest_full_fy(rows)["fin_period"] == "31 Mar 2024")
    chk("no FY column -> None", latest_full_fy(
        parse_periods(STUB_THEN_FY.replace("31 Mar 2024", "30 Sep 2023")
                      .replace("31 Mar 2023", "30 Sep 2022"), 3)) is None)

    print("[5] a malformed page costs that page, not the run")
    chk("no table -> no rows", parse_periods("<html>no tables here</html>", 4) == [])
    chk("no period table -> no rows",
        parse_periods("<html><table><tr><th>Lot Size</th><th>x</th></tr>"
                      "<tr><td>a</td><td>1</td></tr></table></html>", 5) == [])
    chk("a '23..47' cell costs the cell",
        parse_periods(THREE.replace("78.80", "23..47"), 6)[0]["pat_cr"] is None)

    print("[6] the unit is recorded, never inferred per row")
    chk("unit column on every row", all(r["unit"] == "INR_crore" for r in rows))
    chk("source url on every row",
        all(r["url"] == "https://www.chittorgarh.com/ipo/x/1/" for r in rows))

    print("[7] the H9 batch: resumable, mainboard only, one request per id")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "periods.csv"
        pd.DataFrame({"company": ["A", "B", "C"],
                      "url": ["https://www.chittorgarh.com/ipo/x/11/",
                              "https://www.chittorgarh.com/ipo/x/22/",
                              "https://www.chittorgarh.com/ipo/x/33/"]}).to_csv(src, index=False)
        out = td / "out.csv"
        globals()["MAINBOARD"], globals()["OUT"] = src, out
        chk("all mainboard ids when nothing is done", work_list() == [11, 22, 33],
            str(work_list()))
        pd.DataFrame([{"ipo_id": 11, "fin_period": "31 Mar 2024"},
                      {"ipo_id": 11, "fin_period": "31 Mar 2023"}]).to_csv(out, index=False)
        chk("an id already harvested is not fetched again", work_list() == [22, 33],
            str(work_list()))
        chk("ids come from the mainboard list only (H33), never the full id range",
            max(work_list()) <= 33)
    chk("the gap between requests is at least 3 s (B2)", MIN_GAP_S >= 3.0, str(MIN_GAP_S))
    chk("a checkpoint at least every 10 items (H9)", COMMIT_EVERY <= 10, str(COMMIT_EVERY))


    print("[8] full_fy_table: the full year a stub row needs, or NULL - never a guess")
    long = pd.DataFrame([
        # a stub filer whose page also shows two full years
        {"ipo_id": 11, "company": "A", "fin_period": "30 Jun 2024",
         "fin_period_parsed": "2024-06-30", "period_kind": "STUB", "col_index": 1,
         "net_worth_cr": 1942.12, "pat_cr": 1.39},
        {"ipo_id": 11, "company": "A", "fin_period": "31 Mar 2024",
         "fin_period_parsed": "2024-03-31", "period_kind": "FULL_FY", "col_index": 2,
         "net_worth_cr": 2590.87, "pat_cr": 697.78},
        {"ipo_id": 11, "company": "A", "fin_period": "31 Mar 2023",
         "fin_period_parsed": "2023-03-31", "period_kind": "FULL_FY", "col_index": 3,
         "net_worth_cr": 1900.56, "pat_cr": -3.17},
        # a full-year filer: nothing to fill
        {"ipo_id": 22, "company": "B", "fin_period": "31 Mar 2024",
         "fin_period_parsed": "2024-03-31", "period_kind": "FULL_FY", "col_index": 1,
         "net_worth_cr": 422.37, "pat_cr": 78.8},
        # a stub filer whose page shows NO full year at all
        {"ipo_id": 33, "company": "C", "fin_period": "30 Sep 2023",
         "fin_period_parsed": "2023-09-30", "period_kind": "STUB", "col_index": 1,
         "net_worth_cr": 50.0, "pat_cr": 5.0},
        # a page with no financial table at all
        {"ipo_id": 44, "company": None, "fin_period": None, "fin_period_parsed": None,
         "period_kind": "MISSING", "col_index": None},
    ])
    t = full_fy_table(long).set_index("ipo_id")
    chk("one row per ipo_id", len(t) == 4 and sorted(t.index) == [11, 22, 33, 44])
    chk("a stub filer gets the newest full year from the same page",
        t.loc[11, "fy_period"] == "31 Mar 2024" and t.loc[11, "net_worth_cr"] == 2590.87
        and t.loc[11, "pat_cr"] == 697.78, str(dict(t.loc[11])))
    chk("the stub is kept, labelled, and not used as the year",
        t.loc[11, "latest_period"] == "30 Jun 2024"
        and t.loc[11, "latest_period_kind"] == "STUB", str(dict(t.loc[11])))
    chk("the fill is traceable to its column",
        t.loc[11, "fy_source"] == "same_page_column_2", str(t.loc[11, "fy_source"]))
    chk("a full-year filer is unchanged and marked as such",
        t.loc[22, "fy_period"] == "31 Mar 2024" and t.loc[22, "net_worth_cr"] == 422.37
        and t.loc[22, "fy_source"] == "same_page_column_1", str(dict(t.loc[22])))
    chk("no full year on the page -> NULL and a reason, NEVER the stub's number",
        pd.isna(t.loc[33, "fy_period"]) and pd.isna(t.loc[33, "net_worth_cr"])
        and t.loc[33, "fy_source"] == "no_full_fy_on_page", str(dict(t.loc[33])))
    chk("no table on the page -> NULL and a reason",
        pd.isna(t.loc[44, "net_worth_cr"]) and t.loc[44, "fy_source"] == "no_full_fy_on_page",
        str(dict(t.loc[44])))
    chk("usable_for_h59 is exactly 'a full year was found'",
        [bool(t.loc[i, "usable_for_h59"]) for i in (11, 22, 33, 44)] == [1, 1, 0, 0],
        str([t.loc[i, "usable_for_h59"] for i in (11, 22, 33, 44)]))
    chk("provenance: the source url is on every collapsed row",
        t.loc[11, "url"] == "https://www.chittorgarh.com/ipo/x/11/", str(t.loc[11, "url"]))
    chk("the prior full year is carried as a SEPARATE labelled column, not merged",
        t.loc[11, "fy_prev_period"] == "31 Mar 2023"
        and t.loc[11, "fy_prev_net_worth_cr"] == 1900.56
        and pd.isna(t.loc[22, "fy_prev_period"]), str(dict(t.loc[11])))


    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fy-table", action="store_true")
    a = ap.parse_args()
    if a.fy_table:
        t = write_fy_table()
        print(t["latest_period_kind"].value_counts(dropna=False).to_string())
        print(t["fy_source"].str.replace(r"_\d+$", "_N", regex=True)
              .value_counts(dropna=False).to_string())
        print(coverage(t).to_string(index=False))
    elif a.status:
        status()
    elif a.self_test:
        raise SystemExit(self_test())
    else:
        print(f"harvested this run: {batch(a.limit)}")

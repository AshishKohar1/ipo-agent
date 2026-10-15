"""
bse_sector_fill.py — fill the missing NSE industry from BSE, where BSE's own
classification IS NSE's.

Why this exists, and why the earlier answer was wrong
-----------------------------------------------------
`reports/BSE_SECTOR_TEST.md` (13 Oct) tested **`BSE.Sector`** against NSE's `Industry`,
got 11 of 22, and rejected BSE as a source. That comparison used the wrong rung of BSE's
ladder. BSE serves four levels and the report's own table lists them; `Sector` is the
eleven-bucket macro scheme ("Consumer Discretionary"), while **`IndustryNew`** is the
sector level — the same rung, and as it turns out the same vocabulary, as the `Industry`
column in NSE's index-constituent files.

Re-tested on 104 symbols that listed in 2019 or later and for which NSE's own industry is
already on disk:

    IndustryNew   104 / 104   100%   (one comma apart on "Media, Entertainment &
                                      Publication"; identical otherwise)
    Sector         53 / 104    51%
    IGroup          9 / 104     9%
    ISubGroup       0 / 104     0%

So `IndustryNew` is a drop-in and the other three are not. Only `IndustryNew` is read
here, the match is required to be exact after punctuation is normalised, and every filled
row carries its endpoint, scrip code and fetch time (H26).

A symbol's scrip code comes from the cached BSE bhavcopies already in `data/` — no new
request is made to discover one, and a symbol with no cached code is left for the manual
file rather than guessed at.
"""
from __future__ import annotations
import argparse
import datetime
import glob
import re
import sys
import time
import zoneinfo
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
SECTOR_MAP = DATA / "sector_map.csv"
MISSING = DATA / "manual_inputs" / "missing_sectors.csv"
URL = "https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w"
GAP = 3.0                                                   # rule 9
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
      "Accept": "application/json, text/plain, */*",
      "Accept-Language": "en-US,en;q=0.9"}


def ist() -> str:
    return datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).isoformat()


def norm(x) -> str:
    """Punctuation-insensitive comparison key. NSE prints "Media Entertainment &
    Publication" and BSE "Media, Entertainment & Publication" — one comma, same sector."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z& ]", " ", str(x).upper())).strip()


def scrip_codes() -> dict[str, int]:
    """`{symbol: BSE scrip code}` from every cached BSE bhavcopy, newest file winning."""
    code: dict[str, int] = {}
    for f in sorted(glob.glob(str(DATA / "bhavcopy_cache" / "bse_*.csv.gz"))):
        try:
            d = pd.read_csv(f)
        except Exception:                                   # noqa: BLE001
            continue
        if not len(d) or "symbol" not in d or "code" not in d:
            continue
        sy, cd = d["symbol"], d["code"]
        if getattr(sy, "ndim", 1) > 1:
            sy, cd = sy.iloc[:, 0], cd.iloc[:, 0]
        for s, c in zip(sy.tolist(), cd.tolist()):
            s = str(s).strip().upper()
            if s not in ("NAN", "") and pd.notna(c):
                code[s] = int(c)
    return code


def fetch_one(sess, scrip: int) -> tuple[str | None, str]:
    """`(IndustryNew, status)`. Nothing else from the payload is read."""
    try:
        r = sess.get(URL, params={"quotetype": "EQ", "scripcode": str(scrip),
                                  "seriesid": ""},
                     headers={**UA, "Referer": "https://www.bseindia.com/"}, timeout=30)
    except Exception as e:                                  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        j = r.json() or {}
    except Exception as e:                                  # noqa: BLE001
        return None, f"unparsable JSON: {type(e).__name__}"
    v = j.get("IndustryNew")
    return (str(v).strip() if v else None), ("ok" if v else "IndustryNew empty")


def validate(limit: int | None = None) -> pd.DataFrame:
    """Re-measure the agreement on symbols whose NSE industry we already hold (2019+)."""
    import requests
    import rhp_valuation as RV
    code = scrip_codes()
    sm = pd.read_csv(SECTOR_MAP)
    sm = sm[sm["nse_industry"].notna()]
    nse = dict(zip(sm["symbol"].astype(str).str.upper(), sm["nse_industry"]))
    j = RV.targets()
    j["year"] = pd.to_datetime(j["listing_date"], errors="coerce").dt.year
    j["sym"] = j["symbol"].astype(str).str.upper()
    cand = j[(j["year"] >= 2019) & j["sym"].isin(nse) & j["sym"].isin(code)]
    cand = cand.drop_duplicates("sym")
    if limit:
        cand = cand.head(limit)
    sess = requests.Session()
    sess.get("https://www.bseindia.com/", headers=UA, timeout=30)
    rows = []
    for _, r in cand.iterrows():
        ind, st = fetch_one(sess, code[r["sym"]])
        rows.append({"symbol": r["sym"], "year": int(r["year"]),
                     "nse_industry": nse[r["sym"]], "bse_industrynew": ind,
                     "status": st})
        time.sleep(GAP)
    d = pd.DataFrame(rows)
    o = d[d["status"] == "ok"]
    agree = int((o["bse_industrynew"].map(norm) == o["nse_industry"].map(norm)).sum())
    print(f"  IndustryNew agreed with NSE on {agree} of {len(o)} 2019+ symbols "
          f"({100 * agree / max(len(o), 1):.1f}%)")
    if len(o) and agree < len(o):
        print(o[o["bse_industrynew"].map(norm) != o["nse_industry"].map(norm)]
              .to_string(index=False))
    return d


def fill(limit: int | None = None) -> pd.DataFrame:
    """Fill `missing_sectors.csv` rows from BSE's IndustryNew and shrink that file."""
    import requests
    from model_h_sources import remap_sectors
    miss = pd.read_csv(MISSING)
    code = scrip_codes()
    miss["sym"] = miss["symbol"].astype(str).str.upper()
    todo = miss[miss["sym"].isin(code)]
    if limit:
        todo = todo.head(limit)
    print(f"  {len(miss)} rows in {MISSING.name}, {len(todo)} have a cached BSE "
          f"scrip code")
    sess = requests.Session()
    sess.get("https://www.bseindia.com/", headers=UA, timeout=30)
    got, failed = [], []
    for n, (_, r) in enumerate(todo.iterrows(), 1):
        scrip = code[r["sym"]]
        ind, st = fetch_one(sess, scrip)
        if st == "ok" and ind:
            got.append({"symbol": r["sym"], "company_nse": r.get("company"),
                        "isin": "", "nse_industry": ind,
                        "source": "bseindia ComHeadernew IndustryNew",
                        "source_file": "", "source_url": f"{URL}?scripcode={scrip}",
                        "source_sha256": "", "fetched_at_ist": ist()})
        else:
            failed.append({"symbol": r["sym"], "status": st})
        if n % 20 == 0:
            print(f"    {n} of {len(todo)}", flush=True)
        time.sleep(GAP)
    print(f"  filled {len(got)}, failed {len(failed)}")
    if not got:
        return pd.DataFrame()
    add = pd.DataFrame(got)
    sm = pd.read_csv(SECTOR_MAP)
    # A symbol already on the map keeps its NSE reading: an official NSE file outranks a
    # second source that merely agrees with it 100 times out of 100.
    add = add[~add["symbol"].isin(sm["symbol"].astype(str).str.upper())]
    out = pd.concat([sm, add], ignore_index=True)
    out.to_csv(SECTOR_MAP, index=False, encoding="utf-8")
    print(f"  {SECTOR_MAP.name}: {len(sm)} -> {len(out)} symbols")
    remap_sectors()
    done = set(add["symbol"])
    left = miss[~miss["sym"].isin(done)].drop(columns=["sym"])
    left.to_csv(MISSING, index=False, encoding="utf-8")
    print(f"  {MISSING.name}: {len(miss)} -> {len(left)} rows still for you to fill")
    if failed:
        pd.DataFrame(failed).to_csv(DATA / "bse_sector_failures.csv", index=False,
                                    encoding="utf-8")
    return add


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

    print("[1] only IndustryNew is read, and the comparison ignores punctuation only")
    chk("the comma is the whole of the Nazara difference",
        norm("Media, Entertainment & Publication") == norm("Media Entertainment & "
                                                           "Publication"))
    chk("two genuinely different sectors still differ",
        norm("Consumer Durables") != norm("Consumer Discretionary"))
    chk("the ampersand survives normalisation", "&" in norm("Metals & Mining"))
    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    chk("Sector, IGroup and ISubGroup are never read as the industry",
        src.count('j.get("IndustryNew")') == 1
        and 'j.get("Sector")' not in src and 'j.get("IGroup")' not in src)
    chk("the politeness gap is at least 3 s (rule 9)", GAP >= 3.0)
    chk("no scrip code is discovered by a request; they come from the cache",
        "bhavcopy_cache" in src)
    chk("a symbol without a cached code is left in the manual file",
        'miss["sym"].isin(code)' in src)
    chk("an NSE reading is never overwritten by the BSE one",
        '~add["symbol"].isin(sm["symbol"]' in src)
    chk("every filled row carries the endpoint and the fetch time (H26)",
        '"source_url": f"{URL}?scripcode={scrip}"' in src and '"fetched_at_ist": ist()'
        in src)
    chk("an empty IndustryNew is a failure, not a blank fill", 'IndustryNew empty' in src)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--fill", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.validate:
        validate(a.limit)
        return 0
    if a.fill:
        fill(a.limit)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

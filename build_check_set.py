"""
build_check_set.py — choose the 20 prospectuses the readers are graded on (Task 3).

The point of a check set is that it is chosen BEFORE the answers are known and WITHOUT
reference to whether the readers succeed on it. So the selection here looks only at
listing year and NSE industry, never at `data/rhp_valuation_values.csv`: picking documents
the current readers happen to parse would measure the readers against their own
successes, which is how a 24% extractor came to be reported as working.

Strata: listing year (2019-2025) crossed with NSE industry, largest industries first,
one document per cell, walking the years in turn so no year is over-represented. The
order within a cell is by company name - a fixed, reproducible order, not a random draw,
so the same 20 come out on any machine and the set can be re-derived after a rebuild.

    python build_check_set.py            # writes reports/rhp_check_set_docs.csv
    python build_check_set.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
OUT = ROOT / "reports" / "rhp_check_set_docs.csv"
N = 20
ERA = "2019-01-01"


def universe() -> pd.DataFrame:
    """The 2019+ prospectuses on disk, with listing year and NSE industry."""
    f = pd.read_csv(DATA / "rhp_valuation_fetch.csv")
    f = f[f["status"].astype(str).str.startswith("ok")]
    f = f.drop_duplicates(subset=["company"], keep="last").copy()
    f["listing_date"] = pd.to_datetime(f["listing_date"], errors="coerce")
    f = f[f["listing_date"] >= ERA].copy()
    sec = pd.concat([
        pd.read_csv(DATA / "sector_map.csv")[["symbol", "nse_industry"]],
        pd.read_csv(DATA / "manual_inputs" / "missing_sectors.csv")[
            ["symbol", "nse_industry"]],
    ]).dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="first")
    f = f.merge(sec, on="symbol", how="left")
    f["nse_industry"] = f["nse_industry"].fillna("(unmapped)")
    f["year"] = f["listing_date"].dt.year
    return f.sort_values(["company"]).reset_index(drop=True)


def choose(n: int = N) -> pd.DataFrame:
    """Round-robin over years, taking a not-yet-used industry each time.

    Industries are offered in descending size, so Capital Goods (44 documents) and
    Financial Services (41) are represented before Textiles (2), but **an industry is
    taken at most once until every industry has been taken once**. An earlier version
    looped industries on the outside and produced three industries out of twenty-two: it
    filled all its year slots from the two largest before reaching the third.
    """
    u = universe()
    years = sorted(u["year"].unique())
    inds = list(u["nse_industry"].value_counts().index)
    picked: list[int] = []
    ind_used: dict[str, int] = {i: 0 for i in inds}
    per_year: dict[int, int] = {y: 0 for y in years}
    cap_year = -(-n // len(years))               # ceil: 3 for 20 over 7 years
    while len(picked) < n:
        progress = False
        for y in years:
            if len(picked) >= n or per_year[y] >= cap_year:
                continue
            # the least-used industry that has a document in this year
            for ind in sorted(inds, key=lambda i: (ind_used[i], inds.index(i))):
                cand = u[(u["year"] == y) & (u["nse_industry"] == ind)
                         & (~u.index.isin(picked))]
                if len(cand):
                    picked.append(cand.index[0])
                    ind_used[ind] += 1
                    per_year[y] += 1
                    progress = True
                    break
        if not progress:
            cap_year += 1                        # a thin year must not stall the fill
            if cap_year > n:
                break
    return u.loc[picked].sort_values(["year", "company"]).reset_index(drop=True)


def write(d: pd.DataFrame | None = None) -> pd.DataFrame:
    d = choose() if d is None else d
    OUT.parent.mkdir(exist_ok=True)
    d[["company", "symbol", "listing_date", "year", "nse_industry", "pages",
       "path", "url", "sha256_now"]].to_csv(OUT, index=False, encoding="utf-8")
    return d


def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    u = universe()
    d = choose()
    print("[1] the set is 20 documents from 2019 onward")
    chk("20 chosen", len(d) == N, len(d))
    chk("all 2019+", (d["listing_date"] >= ERA).all())
    chk("no duplicates", d["company"].nunique() == len(d))
    chk("every one is on disk",
        all((ROOT / str(p)).exists() for p in d["path"]))

    print("\n[2] spread across years and sectors")
    chk("at least 6 of the 7 years", d["year"].nunique() >= 6,
        sorted(d["year"].unique()))
    chk("no year above 4", d["year"].value_counts().max() <= 4,
        d["year"].value_counts().to_dict())
    chk("at least 8 industries", d["nse_industry"].nunique() >= 8,
        d["nse_industry"].nunique())
    chk("no industry above 4", d["nse_industry"].value_counts().max() <= 4,
        d["nse_industry"].value_counts().to_dict())

    print("\n[3] chosen WITHOUT looking at whether the readers succeed")
    # Only the CODE is searched. This module's own docstring explains why it must not
    # read the values file, so searching the whole source finds the explanation and
    # fails - a trap three earlier self-tests in this project fell into.
    import re as _re
    src = inspect.getsource(sys.modules[__name__])
    code = _re.sub(r'(?s)""".*?"""', "", src)
    code = "\n".join(ln for ln in code.splitlines() if not ln.strip().startswith("#"))
    # The needles are assembled at runtime. Written as literals they would find
    # THEMSELVES in the source they are searching and pass for the wrong reason.
    # The LABELS avoid the words too: "a random draw" put the word back into the source
    # being searched and failed the check it was describing.
    needles = {"the extracted-values file": "rhp_valuation" + "_values",
               "an extractor import": "import " + "extract",
               "a pseudo-chance draw": "ran" + "dom",
               "a subset draw": "sam" + "ple("}
    for label, needle in needles.items():
        chk(f"no {label} in the selection code", needle not in code, needle)

    print("\n[4] reproducible")
    chk("two calls give the same set", list(choose()["company"]) == list(d["company"]))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = write()
    print(d[["company", "symbol", "year", "nse_industry", "pages"]].to_string(index=False))
    print(f"\n{len(d)} documents -> {OUT}")

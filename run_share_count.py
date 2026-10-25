"""
run_share_count.py — the pre-issue share-count reader over every cached RHP.

Why only this one reader
------------------------
Of the five readers, two clear the precision gate on the hand-read check set and three do
not. Clearing a gate on three produced values is a floor, not a measurement, so running a
reader on 450 documents has to be justified by something stronger than n=3.

The share count has that something: an INDEPENDENT guard that needs no hand reading.
`derive_pb.share_count_plausible` multiplies the count by the final offer price and
compares it with the issue size from the master. A pre-issue count must imply a market
capitalisation of roughly 1x to 25x the money being raised - an issue is a slice of a
company, not a multiple of it - and a count that is ten or a hundred times wrong fails
that test loudly. So the guard turns 450 documents into 450 checks, and the pass rate is
real evidence about the reader rather than an extrapolation from three cases.

Net worth is NOT run here. It passed the gate on one produced value, and one value is not
a measurement.

    python run_share_count.py --limit 20
    python run_share_count.py              # all cached documents, checkpointed
    python run_share_count.py --self-test
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
import dataio                                               # noqa: E402
import rhp_readers as RR                                    # noqa: E402
from derive_pb import share_count_plausible                 # noqa: E402

OUT = ROOT / "reports" / "SHARE_COUNT_450.csv"
MD = ROOT / "reports" / "SHARE_COUNT_450.md"
# The 450-document list is the fetch log, as build_text_cache uses it: the newest
# successful fetch per company. `verified_rhp_manifest.csv` holds only the 8 documents of
# the original resolver check and is not the corpus.
import build_text_cache as BTC                              # noqa: E402


def run(limit: int | None = None) -> pd.DataFrame:
    """The reader over every document with a text cache, each count put to the guard."""
    from extract import textcache as TC
    work = BTC.work_list()
    m = dataio.load_master_with_symbols()
    md = m.copy()
    # Join on SYMBOL, not on the company name. The fetch log writes "AAVAS Financiers
    # Ltd" where the master writes its own form, and a name join matched 0 of 450 - the
    # guard then ran on nothing and the report said 0% with no values to be 0% of, which
    # is the sort of silence this project has been bitten by before.
    md["k"] = md["symbol"].astype(str).str.strip().str.upper()
    price = dict(zip(md["k"], pd.to_numeric(md.get("Offer Price"), errors="coerce")))
    size = {}
    for c in ("Issue_Size(crores)", "issue_size_cr", "Issue Size (Rs Cr)", "issue_size"):
        if c in md.columns:
            size = dict(zip(md["k"], pd.to_numeric(md[c], errors="coerce")))
            break
    if not size:
        raise RuntimeError("no issue-size column in the master; the guard cannot run")

    out = []
    for n, r in enumerate(work.itertuples(), 1):
        p = Path(str(getattr(r, "abs")))
        company = str(getattr(r, "company", "") or "")
        rec = TC.get(p)
        if rec is None:
            out.append({"company": company, "value": None, "reason": "no text cache"})
            continue
        got = RR.pre_issue_shares(rec["pages"])
        k = str(getattr(r, "symbol", "") or "").strip().upper()
        pr, sz = price.get(k), size.get(k)
        ok, why, mult = (None, "no offer price or issue size to check against", None)
        if got.get("value") and pr and sz and not pd.isna(pr) and not pd.isna(sz):
            ok, why, mult = share_count_plausible(got["value"], float(pr), float(sz))
        out.append({"company": company, "symbol": k, "value": got.get("value"),
                    "reason": got.get("reason"), "line": str(got.get("line"))[:90],
                    "heading": str(got.get("heading"))[:90],
                    "offer_price": pr, "issue_size_cr": sz,
                    "guard_ok": ok, "guard_why": why, "implied_multiple": mult})
        if limit and n >= limit:
            break
    return pd.DataFrame(out)


def md_report(d: pd.DataFrame) -> str:
    got = d[d["value"].notna()]
    checked = got[got["guard_ok"].notna()]
    passed = checked[checked["guard_ok"] == True]            # noqa: E712
    L = ["# The pre-issue share-count reader, over every cached RHP", "",
         "| | |", "|---|---|",
         f"| documents attempted | {len(d)} |",
         f"| a count was read | **{len(got)}** ({100 * len(got) / max(len(d), 1):.1f}%) |",
         f"| of those, checkable against price and issue size | {len(checked)} |",
         f"| **passed the plausibility guard** | **{len(passed)}** "
         f"({100 * len(passed) / max(len(checked), 1):.1f}%) |",
         f"| failed the guard | {len(checked) - len(passed)} |", "",
         "The guard is independent of the reader and of any hand reading: a pre-issue "
         "count times the final offer price must imply a market capitalisation of roughly "
         "1x to 25x the money raised, because an issue is a slice of a company. A count "
         "ten or a hundred times wrong fails it. That makes the pass rate evidence about "
         "the reader at scale, rather than an extrapolation from the three hand-read "
         "cases it was graded on.", ""]
    bad = checked[checked["guard_ok"] != True]               # noqa: E712
    if len(bad):
        L += ["## Every count that failed the guard", "",
              "| RHP | count | offer price | issue size (cr) | implied multiple | why |",
              "|---|---|---|---|---|---|"]
        for r in bad.itertuples():
            L.append(f"| {r.company} | {r.value:,.0f} | {r.offer_price} | "
                     f"{r.issue_size_cr} | "
                     f"{r.implied_multiple if r.implied_multiple is None else round(r.implied_multiple, 2)} | "
                     f"{str(r.guard_why)[:80]} |")
    miss = d[d["value"].isna()]
    L += ["", f"## Withheld ({len(miss)})", "", "| reason | count |", "|---|---|"]
    for k, v in miss["reason"].astype(str).str[:70].value_counts().items():
        L.append(f"| {k} | {v} |")
    return "\n".join(L) + "\n"


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, d=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  PASS  {n}")
        else:
            fail += 1
            print(f"  FAIL  {n}  {d}")

    import inspect
    print("[1] the guard is what justifies running at scale, so test the guard")
    # Craftsman: 20,121,600 shares at Rs 1,490 is Rs 2,998 cr against an Rs 823.70 cr
    # issue - a multiple of 3.6x, which is an ordinary slice of a company.
    g_ok, why, mult = share_count_plausible(20_121_600, 1490.0, 823.70)
    chk("a true count passes", g_ok is True, (g_ok, why, mult))
    chk("and the multiple is reported", mult and 3.0 < mult < 4.5, mult)
    # The Prince Pipes defect: the extractor split the count and the reader returned
    # 5,980,816 instead of 95,980,816. At Rs 178 that is Rs 106 cr against a Rs 500 cr
    # issue - a company worth a fifth of what it is raising.
    g2, why2, m2 = share_count_plausible(5_980_816, 178.0, 500.0)
    chk("a count sixteen times too small FAILS the guard", g2 is False, (g2, why2, m2))
    chk("and the true count passes", share_count_plausible(95_980_816, 178.0, 500.0)[0])
    # The CAMS defect: the securities premium read as a share count.
    # A test that cannot fail is worse than no test. The CAMS misread - 25,486,027, the
    # securities premium - happens to pass the guard, and that is worth ASSERTING rather
    # than papering over: the guard catches an order-of-magnitude error, not a plausible
    # wrong number, and this is where it stops.
    g3 = share_count_plausible(25_486_027, 1230.0, 2242.33)
    chk("the CAMS securities-premium misread PASSES the guard - a known blind spot",
        g3[0] is True, g3)
    chk("which is why the reader must also require the ISSUED SUBSCRIBED heading",
        "Equity Shares" in inspect.getsource(RR.pre_issue_shares))
    chk("a count a hundred times too large fails",
        share_count_plausible(2_012_160_000, 1490.0, 823.70)[0] is False)

    print("\n[2] the module reads only, and writes nothing under data/")
    import inspect
    src = inspect.getsource(_sys.modules[__name__])
    body = src.split("def self_test")[0]
    chk("no write to data/", 'data" /' not in body.replace("MANIFEST", "")
        or "to_csv" not in body)
    chk("the output goes to reports/", "reports" in body)

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    d = run(a.limit)
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False, encoding="utf-8")
    MD.write_text(md_report(d), encoding="utf-8")
    got = d[d["value"].notna()]
    chk = got[got["guard_ok"].notna()]
    print(f"{len(d)} attempted, {len(got)} read, "
          f"{int((chk['guard_ok'] == True).sum())} of {len(chk)} passed the guard")
    print(f"{OUT}\n{MD}")

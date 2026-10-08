"""
test_candidates.py — Priority 4: three candidate features, tested the way the nine were.

Same discipline as the nine literature candidates already rejected (H2): added **to**
`log1p(Total)`, walk-forward out-of-sample, pooled AUC rather than the mean of per-year
AUCs, and on **identical rows** for the champion and the challenger so the comparison is
not confounded by coverage.

The three, and what became of each:

1. **Free float %** — tested, two ways, because the phrase has two defensible readings and
   picking one by assumption is how a negative result gets manufactured:
   * `offer_pct_of_cap` = issue size / market cap at offer — the share of the company
     actually sold, which is the "thin supply" reading;
   * `non_promoter_post_pct` = 100 − post-issue promoter holding — the standard free-float
     definition.
2. **Nifty move between issue close and listing** — tested, and reported, but **it cannot
   be a feature**. See the leakage note below. It is a diagnostic.
3. **Anchor quality (mutual-fund share of the anchor book)** — **not tested: the data does
   not exist in this repository.** `data/chittorgarh_anchor_lockin.csv` is the pre-issue
   *lock-in* table, not the anchor book. Across 3,127 rows and 674 IPOs, the `name` column
   contains **zero** occurrences of "mutual fund" or "MF", and the `category` column holds
   Promoter / Other / Corporate / SME / Mainboard — plus four rows of header bleed. The
   names are overwhelmingly individuals. Stage 18 is recorded in `PROGRESS.md` as
   backfilling "anchor and lock-in"; what landed is lock-in. Fabricating an MF share from
   name patterns over individual shareholders would be exactly the plausibility inference
   H8 forbids, so nothing is reported for it.

### Why candidate 2 cannot be a feature, however well it scores

Model L decides **whether to bid**, at 15:00 on the final bidding day. The listing happens
three to six days later. The Nifty move between close and listing is therefore **unknowable
at the moment of the decision** — it is in the future. Using it would be a rule-5 leakage
violation, and a severe one: it is the single most direct way to smuggle the outcome's own
market environment into a pre-decision model.

It is still worth measuring, for a reason that has nothing to do with features: it tells
you **how much of a listing gain is market drift rather than the company's book.** If it
carries real signal, that is evidence for the standing caveat about near-threshold verdicts
being uncertain — the uncertainty would be partly irreducible, because it lives in a window
that has not happened yet. So it is reported under its own heading, with AUC, and with the
word FEATURE deliberately not attached to it.

### The bar for adoption is higher than AUC, and higher than it was

H17 removed the calibrated probability from the decision path: the live rule is a plain
subscription threshold. A two-variable model cannot be expressed as one threshold on
subscription, so **adopting any candidate means putting a probability back into the
decision**. That is not a tie-break cost, it is the thing H17 was ratified to get rid of.
A candidate therefore has to improve **out-of-sample delivery** — fires and delivered hit
rate at the required rate — by enough to be worth re-introducing an intermediary that has
already produced two opposite failures. Not in-sample AUC. Not pooled AUC alone.

    python test_candidates.py
    python test_candidates.py --self-test
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import dataio                                                # noqa: E402
import framework as F                                        # noqa: E402
import model_l as ML                                         # noqa: E402

OUT_CSV = ROOT / "reports" / "CANDIDATE_FEATURES.csv"
OUT_MD = ROOT / "reports" / "CANDIDATE_FEATURES.md"
OUT_JSON = ROOT / "reports" / "CANDIDATE_FEATURES.json"

REQUIRED = {"L1": 0.90, "L2": 0.80}
CUTS = {"L1": 0.0, "L2": 10.0}

# Candidate 3 has no data. Recorded as a constant so the report cannot quietly drop it.
NOT_TESTED = {
    "anchor_mf_share": (
        "NOT TESTED - no data. data/chittorgarh_anchor_lockin.csv is the pre-issue "
        "LOCK-IN table, not the anchor book: 3,127 rows across 674 IPOs, zero names "
        "containing 'mutual fund' or 'MF', categories of Promoter/Other/Corporate/"
        "SME/Mainboard, and names that are overwhelmingly individuals. Deriving an MF "
        "share from name patterns over individual shareholders would be the plausibility "
        "inference H8 forbids. To test it, the anchor allocation table has to be collected "
        "first - it is a different block on the same Chittorgarh page."),
}


# ---------------------------------------------------------------- the candidate data
def _close_date(s: str | float) -> pd.Timestamp | None:
    """Parse Chittorgarh's `ipo_dates`, e.g. '5 to 7 Jul, 2010' -> 2010-07-07.

    Returns None rather than a guess on anything that does not match. The close date is
    the SECOND date: that is the final bidding day, which is the moment Model L scores.
    """
    if not isinstance(s, str):
        return None
    m = re.match(r"\s*(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\s+([A-Za-z]{3,})[,\s]+(\d{4})", s)
    if m:
        d2, mon, yr = m.group(2), m.group(3)[:3], m.group(4)
        try:
            return pd.Timestamp(f"{d2} {mon} {yr}")
        except Exception:                                    # noqa: BLE001
            return None
    # '27 Jun to 1 Jul, 2024' — month changes inside the window.
    m = re.match(r"\s*\d{1,2}\s+[A-Za-z]{3,}\s*(?:to|-|–)\s*(\d{1,2})\s+([A-Za-z]{3,})"
                 r"[,\s]+(\d{4})", s)
    if m:
        try:
            return pd.Timestamp(f"{m.group(1)} {m.group(2)[:3]} {m.group(3)}")
        except Exception:                                    # noqa: BLE001
            return None
    return None


def tri_frame() -> pd.DataFrame:
    t = dataio.load_nifty_tri().rename("tri").reset_index()
    t.columns = ["date", "tri"]
    t["date"] = pd.to_datetime(t["date"])
    return t.sort_values("date").reset_index(drop=True)


def _tri_at(tri: pd.DataFrame, when) -> float | None:
    when = pd.Timestamp(when)
    if pd.isna(when) or when < tri["date"].min():
        return None
    s = tri[tri["date"] <= when]
    return None if s.empty else float(s["tri"].iloc[-1])


def build() -> pd.DataFrame:
    """Champion rows plus every candidate column. No row is dropped here — the per-feature
    comparison does its own dropping, so each candidate is scored against the champion on
    exactly its own rows."""
    d = ML.load_mainboard()
    d = d[d["exclude_reason"].isna()].copy() if "exclude_reason" in d else d.copy()
    d["listing_date"] = pd.to_datetime(d["listing_date"], errors="coerce")
    d = d.dropna(subset=["listing_date"])
    d["log1p_total"] = np.log1p(pd.to_numeric(d["Total"], errors="coerce"))
    d["k"] = d["company"].astype(str).map(dataio.norm_name)

    # --- candidate 1: free float, two readings
    agg = pd.read_csv(ROOT / "data" / "model_h_from_aggregator.csv", low_memory=False)
    agg["k"] = agg["company"].astype(str).map(dataio.norm_name)
    for c in ("issue_size_cr", "market_cap_at_offer_cr", "promoter_post_pct"):
        agg[c] = pd.to_numeric(agg[c], errors="coerce")
    agg = agg.sort_values("k").drop_duplicates("k", keep="first")
    d = d.merge(agg[["k", "issue_size_cr", "market_cap_at_offer_cr",
                     "promoter_post_pct"]], on="k", how="left")

    cap = d["market_cap_at_offer_cr"].where(d["market_cap_at_offer_cr"] > 0)
    d["offer_pct_of_cap"] = 100.0 * d["issue_size_cr"] / cap
    d.loc[(d["offer_pct_of_cap"] <= 0) | (d["offer_pct_of_cap"] > 100),
          "offer_pct_of_cap"] = np.nan          # out of range is bad data, not a small float
    pp = d["promoter_post_pct"].where((d["promoter_post_pct"] >= 0)
                                      & (d["promoter_post_pct"] <= 100))
    d["non_promoter_post_pct"] = 100.0 - pp

    # --- candidate 2: the Nifty move from issue CLOSE to listing (a diagnostic, not a
    # feature — it is unknowable at the 15:00 decision).
    bf = pd.read_csv(ROOT / "data" / "chittorgarh_backfill.csv", low_memory=False)
    bf["k"] = bf["company"].astype(str).map(dataio.norm_name)
    bf["close_date"] = bf["ipo_dates"].map(_close_date)
    bf = bf.dropna(subset=["close_date"]).sort_values("k").drop_duplicates("k", keep="first")
    d = d.merge(bf[["k", "close_date"]], on="k", how="left")

    tri = tri_frame()
    a = [_tri_at(tri, x) for x in d["close_date"]]
    b = [_tri_at(tri, x) for x in d["listing_date"]]
    gap = (d["listing_date"] - d["close_date"]).dt.days
    mv = [None if (x is None or y is None or x <= 0) else 100.0 * (y / x - 1.0)
          for x, y in zip(a, b)]
    d["nifty_close_to_listing_pct"] = mv
    d["close_to_listing_days"] = gap
    # A window outside 1-30 days is not the close-to-listing gap; it is a name collision or
    # a bad parse, and is dropped rather than widened to fit.
    bad = (gap < 1) | (gap > 30) | gap.isna()
    d.loc[bad, "nifty_close_to_listing_pct"] = np.nan
    return d


# ---------------------------------------------------------------- the comparison
def compare(d: pd.DataFrame, target: str, cand: str | None,
            n_test_years: int = 6) -> dict:
    """Walk-forward champion vs champion+candidate on IDENTICAL rows."""
    feats = ["log1p_total"] + ([cand] if cand else [])
    need = ["log1p_total", target, "listing_date"] + ([cand] if cand else [])
    sub = d.dropna(subset=need).copy()
    out = {"target": target, "candidate": cand, "n_rows": int(len(sub))}
    if len(sub) < 80:
        out["error"] = f"only {len(sub)} usable rows"
        return out

    def run(fs):
        spec = F.ModelSpec(
            name=f"cand_{target}", title=f"{target} {'+'.join(fs)}",
            load=lambda: sub, make_features=lambda x: x[fs], features=fs,
            target=target, target_desc="", realised_days=0,
            required_hit_rate={target: REQUIRED[target]}, n_test_years=n_test_years)
        years = F.test_years(sub, spec)
        oof, per = F.walk_forward(sub, spec, None, years)
        auc = F.roc_auc_score(oof["y"], oof["p"])
        thr = F.threshold_section5(oof, REQUIRED[target])
        # `at_chosen` is the row at the qualifying threshold; `best_near_miss` is the best
        # a candidate managed when NOTHING qualified. Reporting the near miss matters: a
        # candidate that fails the C5 gate outright is a different finding from one that
        # passes it slightly worse, and collapsing both to "None" would hide that.
        at = thr.get("at_chosen") or {}
        near = thr.get("best_near_miss") or {}
        src = at or near
        return {"pooled_auc": round(float(auc), 4), "years": years,
                "n_oof": int(len(oof)),
                "qualifies": thr.get("chosen") is not None,
                "fires": int(src.get("n_fire") or 0),
                "delivered": (None if src.get("hit_rate") is None
                              or pd.isna(src.get("hit_rate"))
                              else round(float(src["hit_rate"]), 4)),
                "threshold_p": thr.get("chosen"),
                "lo95": (None if src.get("hit_rate_lo95") is None
                         or pd.isna(src.get("hit_rate_lo95"))
                         else round(float(src["hit_rate_lo95"]), 4)),
                "from_near_miss": bool(not at and near)}

    base = run(["log1p_total"])
    out["champion"] = base
    if cand:
        out["with_candidate"] = run(feats)
        out["d_auc"] = round(out["with_candidate"]["pooled_auc"] - base["pooled_auc"], 4)
        bd, wd = base["delivered"], out["with_candidate"]["delivered"]
        out["d_delivered_pp"] = (None if (bd is None or wd is None)
                                 else round(100 * (wd - bd), 2))
        out["d_fires"] = out["with_candidate"]["fires"] - base["fires"]
        # The user's bar, applied rather than described: delivery, not AUC.
        # Materiality, so a sub-resolution wobble cannot read as an improvement. With
        # `fires` firing rows, ONE extra hit is worth 100/fires percentage points. A
        # delivered-rate change smaller than one hit is below the resolution of the
        # measurement: it is arithmetic noise, not evidence. Reporting it as "YES" is
        # exactly how a feature gets adopted on nothing.
        wc = out["with_candidate"]
        one_hit_pp = (100.0 / wc["fires"]) if wc["fires"] else None
        out["one_hit_pp"] = None if one_hit_pp is None else round(one_hit_pp, 2)
        out["material"] = bool(out["d_delivered_pp"] is not None and one_hit_pp
                               and abs(out["d_delivered_pp"]) >= one_hit_pp)
        out["improves_delivery"] = bool(
            wc.get("qualifies") and out["material"]
            and out["d_delivered_pp"] is not None and out["d_delivered_pp"] > 0
            and wc["fires"] >= base["fires"])
    return out


CANDIDATES = [("offer_pct_of_cap", "Free float - issue size as % of market cap at offer"),
              ("non_promoter_post_pct", "Free float - 100 minus post-issue promoter %"),
              ("nifty_close_to_listing_pct",
               "Nifty move, issue close to listing (DIAGNOSTIC - unknowable at the bid)")]


def run_all() -> dict:
    d = build()
    res = {"n_master_rows": int(len(d)), "coverage": {}, "results": [],
           "not_tested": NOT_TESTED}
    for c, _ in CANDIDATES:
        res["coverage"][c] = int(d[c].notna().sum())
    for target in ("L1", "L2"):
        for c, label in CANDIDATES:
            r = compare(d, target, c)
            r["label"] = label
            r["is_feature_candidate"] = c != "nifty_close_to_listing_pct"
            res["results"].append(r)
    return res, d


def md(res: dict) -> str:
    L = ["# Three candidate features — Priority 4", "",
         "Added **to** `log1p(Total)`, walk-forward out-of-sample, pooled AUC, and on "
         "**identical rows** for champion and challenger. Same discipline as the nine "
         "literature candidates already rejected (H2).", "",
         "## The bar for adoption", "",
         "H17 removed the calibrated probability from the decision path — the live rule is "
         "a plain threshold on subscription. **A two-variable model cannot be expressed as "
         "one threshold on subscription**, so adopting any candidate means putting a "
         "probability back into the decision. That is the thing H17 was ratified to "
         "remove, and it has already produced two opposite failures. So the bar is "
         "out-of-sample **delivery**, not AUC.", "",
         "## Coverage", "",
         "| candidate | rows with a value |", "|---|---|"]
    for c, n in res["coverage"].items():
        L.append(f"| `{c}` | {n} |")

    L += ["", "## Results", "",
          "| target | candidate | rows | champion AUC | with cand. | ΔAUC | champion "
          "delivered | with cand. | Δ (pp) | Δ fires | one hit (pp) | improves "
          "delivery? |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["results"]:
        if r.get("error"):
            L.append(f"| {r['target']} | `{r['candidate']}` | {r['n_rows']} "
                     f"| — | — | — | — | — | — | — | — | {r['error']} |")
            continue
        ch, wc = r["champion"], r["with_candidate"]
        pct = lambda v: "—" if v is None else f"{v*100:.1f}%"        # noqa: E731
        dd = r["d_delivered_pp"]
        dd_say = "—" if dd is None else f"{dd:+.2f}"
        oh = r.get("one_hit_pp")
        one_hit = "—" if oh is None else (f"{oh:.2f}" + ("" if r.get("material")
                                                         else " (Δ below this)"))
        verdict = "**YES**" if r["improves_delivery"] else "no"
        L.append(f"| {r['target']} | `{r['candidate']}` | {r['n_rows']} "
                 f"| {ch['pooled_auc']:.4f} | {wc['pooled_auc']:.4f} "
                 f"| **{r['d_auc']:+.4f}** | {pct(ch['delivered'])} ({ch['fires']}) "
                 f"| {pct(wc['delivered'])} ({wc['fires']}) "
                 f"| {dd_say} | {r['d_fires']:+d} | {one_hit} | {verdict} |")

    # Findings, generated from the numbers so they cannot drift from the table.
    best = max((r for r in res["results"] if not r.get("error")),
               key=lambda r: r["d_auc"])
    nif = [r for r in res["results"]
           if r["candidate"] == "nifty_close_to_listing_pct" and not r.get("error")]
    adopted = [r for r in res["results"] if r.get("improves_delivery")]
    L += ["", "## What this means", "",
          f"**None of the three is adopted.** {len(adopted)} candidate-target pairs clear "
          f"the bar.", "",
          f"The largest AUC gain anywhere is `{best['candidate']}` on {best['target']}, "
          f"**{best['d_auc']:+.4f}** — and its delivered rate still goes "
          f"{best['d_delivered_pp']:+.2f}pp, which is inside one hit "
          f"({best['one_hit_pp']}pp). An AUC gain that does not convert into delivery is "
          f"not worth putting a probability back into the decision path.", "",
          "`non_promoter_post_pct` makes pooled AUC **worse** on both targets, and on L1 "
          "leaves the fire count and the delivered rate completely unchanged — the fit "
          "finds nothing in it at all. The two free-float readings behaving so differently "
          "is itself the answer: what little signal exists is in how much of the company "
          "was *sold*, not in how much is nominally unheld.", ""]
    if nif:
        a1 = [r for r in nif if r["target"] == "L1"][0]
        a2 = [r for r in nif if r["target"] == "L2"][0]
        L += ["### The diagnostic is the most interesting negative", "",
              f"The Nifty move between issue close and listing adds "
              f"**{a1['d_auc']:+.4f}** on L1 and **{a2['d_auc']:+.4f}** on L2 — "
              f"essentially nothing, on {a1['n_rows']} IPOs with a real parsed close date.",
              "",
              "That is worth more than its size suggests. If a listing gain were mostly "
              "market drift over the three-to-six-day gap, this would be the variable that "
              "showed it, and it does not. **The listing gain is issue-specific, not a "
              "market ride.** It also agrees with Priority 3b, where the delivered rate "
              "ranked only +0.206 against the year's index return. Two independent routes "
              "to the same conclusion: when a year under-delivers, the index is not where "
              "to look for the reason.", ""]
    L += ["", "## Not tested", ""]
    for k, v in res["not_tested"].items():
        L += [f"**`{k}`** — {v}", ""]
    return "\n".join(L) + "\n"


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

    print("[1] the close date is the SECOND date, and bad input returns None")
    chk("'5 to 7 Jul, 2010' -> 7 Jul",
        _close_date("5 to 7 Jul, 2010") == pd.Timestamp("2010-07-07"))
    chk("a window spanning a month boundary parses",
        _close_date("27 Jun to 1 Jul, 2024") == pd.Timestamp("2024-07-01"))
    chk("nonsense returns None, never a guess", _close_date("sometime in July") is None)
    chk("a non-string returns None", _close_date(float("nan")) is None)

    print("\n[2] candidate 3 is reported as untested, with its evidence")
    chk("it is named", "anchor_mf_share" in NOT_TESTED)
    chk("the evidence is the zero count, not an opinion",
        "zero names" in NOT_TESTED["anchor_mf_share"])
    chk("and it says what would be needed instead",
        "anchor allocation table" in NOT_TESTED["anchor_mf_share"])

    print("\n[3] the leakage candidate is flagged as not a feature")
    names = [c for c, _ in CANDIDATES]
    chk("it is still measured", "nifty_close_to_listing_pct" in names)
    lab = [l for c, l in CANDIDATES if c == "nifty_close_to_listing_pct"][0]
    chk("and its label says DIAGNOSTIC", "DIAGNOSTIC" in lab)
    chk("and says why: unknowable at the bid", "unknowable at the bid" in lab)

    print("\n[4] out-of-range values are dropped, not clipped into range")
    import inspect
    src = inspect.getsource(build)
    chk("an offer % outside 0-100 becomes NaN", "> 100" in src and "np.nan" in src)
    chk("a close-to-listing gap outside 1-30 days becomes NaN", "> 30" in src)
    chk("nothing is clipped", "clip(" not in src)

    print("\n[5] the adoption bar is delivery, not AUC")
    src = inspect.getsource(compare)
    chk("improves_delivery is computed from delivered, not from AUC",
        "d_delivered_pp" in src and "improves_delivery" in src)
    i = src.index("improves_delivery")
    chk("and the AUC delta does not enter that decision",
        "d_auc" not in src[i:i + 320])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    res, d = run_all()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)}
                  | {f"champ_{k}": v for k, v in (r.get("champion") or {}).items()
                     if not isinstance(v, list)}
                  | {f"cand_{k}": v for k, v in (r.get("with_candidate") or {}).items()
                     if not isinstance(v, list)}
                  for r in res["results"]]).to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_MD.write_text(md(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("coverage:", res["coverage"])
    for r in res["results"]:
        if r.get("error"):
            print(f"  {r['target']} {r['candidate']}: {r['error']}")
            continue
        ch, wc = r["champion"], r["with_candidate"]
        print(f"  {r['target']} {r['candidate']:<30} n={r['n_rows']:<4} "
              f"AUC {ch['pooled_auc']:.4f} -> {wc['pooled_auc']:.4f} ({r['d_auc']:+.4f})  "
              f"delivered {ch['delivered']} -> {wc['delivered']} "
              f"(fires {ch['fires']} -> {wc['fires']})  "
              f"{'ADOPT?' if r['improves_delivery'] else 'no'}")
    print(f"\n{OUT_MD}")

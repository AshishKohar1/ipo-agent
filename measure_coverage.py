"""
measure_coverage.py — Task 5: what actually changed, with variance beside coverage.

The point the user made, and it is the right one: *a field that moves from 40% to 95%
coverage while being 97% a single value has gained nothing.* So coverage is never reported
alone here. Every field gets both, and the recommendation is driven by the pair.

Three verdicts:
  `scorecard`     enough coverage AND enough variance to carry signal
  `collect-only`  worth keeping in the dataset but not worth a scorecard weight yet —
                  either too sparse or too one-sided
  `drop`          no realistic path to being useful

Writes reports/COVERAGE_BEFORE_AFTER.md and reports/coverage_after.csv.

    python measure_coverage.py
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract import h6                                   # noqa: E402

REASONS = ["not_present_on_page", "present_but_unparsed", "section_not_found",
           "document_unavailable", "unit_undetermined"]
# The thresholds the verdict uses. Stated here rather than buried in the logic.
MIN_COVERAGE_SCORECARD = 0.50
MAX_MAJORITY_SCORECARD = 0.90
MIN_COVERAGE_KEEP = 0.10


def load_all() -> pd.DataFrame:
    parts = []
    for f in ("reports/h6_observations.csv", "reports/h6_batch_observations.csv",
              "reports/h6_document_unavailable.csv"):
        p = ROOT / f
        if p.exists():
            d = pd.read_csv(p, keep_default_na=False, na_values=[""])
            if "missing_reason" not in d:
                d["missing_reason"] = ""
            parts.append(d)
    o = pd.concat(parts, ignore_index=True)
    o["value"] = pd.to_numeric(o["value"], errors="coerce")
    return o[o["variable"].isin(h6.FIELDS)]


def main() -> pd.DataFrame:
    o = load_all()
    ncomp = o["company"].nunique()
    print(f"{len(o)} field-cells across {ncomp} companies\n")

    rows = []
    for f in h6.FIELDS:
        s = o[o["variable"] == f]
        n = len(s)
        got = s[s["status"].isin(["ok", "ambiguous"]) & s["value"].notna()]
        cov = len(got) / n if n else 0.0
        # variance, on the extracted values only
        v = got["value"]
        if len(v):
            counts = v.value_counts()
            majority = float(counts.iloc[0] / len(v))
            distinct = int(v.nunique())
        else:
            majority, distinct = None, 0
        r = {"field": f, "n_cells": n, "extracted": len(got),
             "coverage_pct": round(cov * 100, 1),
             "distinct_values": distinct,
             "majority_share_pct": None if majority is None else round(majority * 100, 1),
             "ok": int((s["status"] == "ok").sum()),
             "ambiguous": int((s["status"] == "ambiguous").sum()),
             "not_applicable": int((s["status"] == "not_applicable").sum())}
        for reason in REASONS:
            r[reason] = int((s["missing_reason"] == reason).sum())

        # ---- verdict: coverage AND variance, never one alone
        if distinct <= 1 and len(got):
            r["verdict"] = "drop"
            r["why"] = (f"every one of the {len(got)} extracted values is identical "
                        f"({v.iloc[0] if len(v) else '-'}) — it cannot separate any two "
                        "companies, whatever its coverage")
        elif cov < MIN_COVERAGE_KEEP:
            r["verdict"] = "drop"
            r["why"] = (f"{cov*100:.0f}% coverage; too sparse to impute and too sparse to "
                        "weight")
        elif majority is not None and majority > MAX_MAJORITY_SCORECARD:
            r["verdict"] = "collect-only"
            r["why"] = (f"{majority*100:.0f}% of extracted values are the same — coverage "
                        f"{cov*100:.0f}% is real but the field barely discriminates")
        elif cov < MIN_COVERAGE_SCORECARD:
            r["verdict"] = "collect-only"
            r["why"] = (f"{cov*100:.0f}% coverage is below the {MIN_COVERAGE_SCORECARD:.0%} "
                        "floor; variance is fine, so it becomes useful if coverage improves")
        else:
            r["verdict"] = "scorecard"
            r["why"] = (f"{cov*100:.0f}% coverage, {distinct} distinct values, majority "
                        f"share {majority*100:.0f}%")
        rows.append(r)

    t = pd.DataFrame(rows).sort_values(
        ["verdict", "coverage_pct"], ascending=[True, False]).reset_index(drop=True)
    t.to_csv(ROOT / "reports" / "coverage_after.csv", index=False, encoding="utf-8")

    print(f"{'field':42s} {'cov%':>6s} {'distinct':>8s} {'major%':>7s}  verdict")
    for r in t.itertuples():
        ms = "" if r.majority_share_pct is None else f"{r.majority_share_pct:6.1f}%"
        print(f"{r.field:42s} {r.coverage_pct:5.1f}% {r.distinct_values:8d} {ms:>7s}  "
              f"{r.verdict}")

    # ---- the markdown report
    L = ["# Coverage and variance, side by side — Task 5", "",
         f"{len(o)} field-cells across {ncomp} companies. "
         "Coverage is never reported alone: a field that reaches 95% while being 97% one "
         "value has gained nothing, so both numbers appear in every row and the verdict "
         "uses the pair.", "",
         "| Field | Coverage | Distinct | Majority share | Verdict |",
         "|---|---|---|---|---|"]
    for r in t.itertuples():
        ms = "—" if r.majority_share_pct is None else f"{r.majority_share_pct:.1f}%"
        L.append(f"| `{r.field}` | {r.coverage_pct:.1f}% | {r.distinct_values} | {ms} | "
                 f"**{r.verdict}** |")
    L += ["", "## Why a gap exists, per field (decision H10)", "",
          "| Field | not_present | unparsed | section_missing | no_document | unit_undet |",
          "|---|---|---|---|---|---|"]
    for r in t.itertuples():
        L.append(f"| `{r.field}` | {r.not_present_on_page} | {r.present_but_unparsed} | "
                 f"{r.section_not_found} | {r.document_unavailable} | "
                 f"{r.unit_undetermined} |")
    L += ["", "## Recommendation", ""]
    for verdict, head in (("scorecard", "Good enough for the scorecard"),
                          ("collect-only", "Collect-only — keep, do not weight yet"),
                          ("drop", "Drop")):
        sub = t[t["verdict"] == verdict]
        L += [f"### {head} ({len(sub)})", ""]
        for r in sub.itertuples():
            L.append(f"- **`{r.field}`** — {r.why}")
        L.append("")
    (ROOT / "reports" / "COVERAGE_BEFORE_AFTER.md").write_text("\n".join(L) + "\n",
                                                               encoding="utf-8")
    print(f"\n{t['verdict'].value_counts().to_string()}")
    print("\nwritten: reports/COVERAGE_BEFORE_AFTER.md, reports/coverage_after.csv")
    return t


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

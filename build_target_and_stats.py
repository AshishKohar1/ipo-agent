"""
build_target_and_stats.py

Stage 1: build the holding target  excess_1y = IPO_ret(list -> +365d) - NIFTY_ret(same)
Stage 2: emit the statistics review pack you asked for.

RUN IN CLAUDE CODE (needs yfinance / open network).
"""
from __future__ import annotations
import numpy as np, pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parent / "review"; OUT.mkdir(exist_ok=True)


# ======================================================================
# STAGE 1 — THE HOLDING TARGET
# One implementation only: run_overnight.job2_build_target (listing-date logic,
# checkpoints and miss logging live there). Writes holding_target.csv and
# target_MISSES.csv.
# ======================================================================
def build_holding_target() -> pd.DataFrame:
    from run_overnight import job2_build_target
    return job2_build_target()


# ======================================================================
# STAGE 2 — STATISTICS REVIEW PACK
# ======================================================================
def stats_pack(dataset_csv="dataset_reconciled.csv",
               audit_csv="reconciliation_audit.csv") -> None:
    df    = pd.read_csv(dataset_csv)
    audit = pd.read_csv(audit_csv)
    lines: list[str] = []
    def P(s=""): lines.append(str(s)); print(s)

    P("="*78); P("IPO DATASET — STATISTICS FOR REVIEW"); P("="*78)
    P(f"Rows: {len(df)}   Variables: {len([c for c in df.columns if not c.endswith('__status')])}")

    P("\n" + "-"*78); P("1. RECONCILIATION OUTCOME (your 5% rule)"); P("-"*78)
    vc = audit["status"].value_counts()
    for k, v in vc.items():
        P(f"  {k:28s} {v:6d}  ({v/len(audit)*100:5.1f}%)")
    rej = audit[audit["status"] == "REJECTED_DISAGREE"]
    P(f"\n  Values NULLed for >5% disagreement: {len(rej)}")

    P("\n" + "-"*78); P("2. PER-VARIABLE QUALITY"); P("-"*78)
    P(f"  {'variable':26s} {'coverage%':>9s} {'reconc%':>8s} {'rejected%':>9s} {'1-src%':>7s}")
    for var in sorted(audit["variable"].unique()):
        a = audit[audit["variable"] == var]
        cov  = a["value"].notna().mean()*100
        rec  = (a["status"] == "reconciled").mean()*100
        rj   = (a["status"] == "REJECTED_DISAGREE").mean()*100
        one  = (a["status"] == "single_source_unverified").mean()*100
        flag = "  <-- REVIEW" if (rj > 15 or cov < 60) else ""
        P(f"  {var:26s} {cov:8.1f}% {rec:7.1f}% {rj:8.1f}% {one:6.1f}%{flag}")

    P("\n" + "-"*78); P("3. WORST DISAGREEMENTS (inspect these by hand)"); P("-"*78)
    if len(rej):
        w = rej.nlargest(15, "max_rel_diff")[["isin","variable","max_rel_diff","detail"]]
        for _, r in w.iterrows():
            P(f"  {str(r['isin'])[:14]:16s} {r['variable']:22s} diff={r['max_rel_diff']*100:6.1f}%  {str(r['detail'])[:60]}")
    else:
        P("  none")

    P("\n" + "-"*78); P("4. DISTRIBUTIONS"); P("-"*78)
    num = df.select_dtypes(include=[np.number])
    P(num.describe().T[["count","mean","50%","std","min","max"]].round(2).to_string())

    P("\n" + "-"*78); P("5. MODEL-READINESS"); P("-"*78)
    complete = df[[c for c in df.columns if not c.endswith('__status')]].dropna()
    P(f"  Rows complete on ALL variables : {len(complete)}")
    for k in (10, 15, 20, 25):
        sub = [c for c in num.columns][:k]
        P(f"  Rows complete on first {k:2d} vars : {df[sub].dropna().shape[0]}")
    P(f"\n  Rule of thumb: need 10-15 rows per feature.")
    P(f"  -> at {len(complete)} complete rows, max defensible features = {len(complete)//12}")

    P("\n" + "-"*78); P("6. EXCLUDE FROM ANY 'RECONCILED' MODEL"); P("-"*78)
    single = audit[audit["status"] == "single_source_unverified"]["variable"].unique()
    for v in sorted(single):
        P(f"  {v}  — single source, no independent check possible")

    (OUT / "STATS_REVIEW.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWritten: {OUT/'STATS_REVIEW.txt'}")


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "target":
        build_holding_target()
    else:
        stats_pack()

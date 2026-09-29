"""
models/model_h.py — Model H: P(IPO beats the Nifty 50 TRI after listing), on framework.py.

Same interface as model_l: ModelSpec -> framework.run() -> bundle, card, predict_live().

  model_h1_baseline   H_label  = excess_1y > 0   (listing close -> +365d)   PRIMARY
  model_h3_baseline   H3_label = excess_3y > 0   (listing close -> +1095d)  secondary

Embargo: realised_days = 365 / 1095, so a training row is used for test year T only if
listing_date + horizon < Jan 1 of T. Without it, training labels would contain returns
earned during the test period.

DECISION TIME: the baseline uses listing gain, known only at the listing-day close. So
the baseline answers "hold from the listing close?" — the point the target is measured
from. It is NOT a pre-bid model. The RHP blocks are all knowable pre-bid; a pre-bid
variant is the baseline minus listing_gain plus RHP blocks.

THE BASELINE IS THE BAR. An RHP block earns its place only if adding it raises
walk-forward AUC over the baseline on the SAME test years (compare_blocks()).

    python models/model_h.py                 # fit both baselines, write cards
    python models/model_h.py compare         # baseline vs baseline + each available block
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import framework as F
import dataio
from model_l import mb_features

HORIZONS = {"1y": dict(file="holding_target.csv", label="H_label", days=365,
                       excess="excess_1y_pp"),
            "3y": dict(file="holding_target_3y.csv", label="H3_label", days=1095,
                       excess="excess_3y_pp")}

BASELINE_FEATURES = ["log1p_total", "log1p_qib", "log1p_hni", "log1p_rii", "log_issue_size",
                     "listing_gain"]

# ----------------------------------------------------------------------
# RHP FEATURE BLOCKS — PLACEHOLDERS (IPO-Model-Build-Spec-v2.md, Part C.4)
# ----------------------------------------------------------------------
# Each block lists the columns it will contribute. Until the RHP extraction writes them
# (observations table -> reconcile.py -> dataset_reconciled.csv), every column is NaN
# and the block is skipped automatically. To plug a block in: make rhp_block_values()
# return real values for its columns. Nothing else changes.
#
# `single_source`: True for variables that exist ONLY in the RHP (CLAUDE.md "Known
# biases"): they are flagged single_source_unverified by reconcile.py and must never be
# described as reconciled.
RHP_BLOCKS: dict[str, dict] = {
    "valuation": dict(status="placeholder", single_source=False, features=[
        "pe_issue_vs_peer_median",       # P/E at issue price / peer median P/E
        "pb_issue_vs_peer_median",       # P/B / peer median
        "ev_ebitda_vs_peer_median",      # EV/EBITDA / peer median
        "ps_vs_peer_median",             # P/S / peer median (loss-makers)
        "industry_pe",                   # industry P/E, absolute level
        "mcap_to_trailing_revenue",      # implied market cap / trailing revenue
    ]),
    "quality_moat": dict(status="placeholder", single_source=False, features=[
        "roce_3y_avg",
        "roce_minus_wacc",               # WACC proxy: 91-day T-bill + 6% equity premium
        "gross_margin_3y_std",           # lower = pricing power
        "gross_margin_vs_industry",
        "revenue_cagr_3y",
        "pat_cagr_3y",
        "ocf_to_pat_3y_avg",
        "fcf_positive_years_of_3",
    ]),
    "balance_sheet": dict(status="placeholder", single_source=False, features=[
        "debt_equity_post_issue",
        "interest_coverage",
        "working_capital_days",          # receivable + inventory - payable
        "contingent_liab_to_networth",
    ]),
    "governance": dict(status="placeholder", single_source=True, features=[
        "governance_score_0_100",        # IiAS/IFC/BSE scorecard, 4 equal-weight categories
        "rpt_pct_revenue",               # single-source (RHP only)
        "auditor_qualified",             # single-source (RHP only)
        "board_independence_ratio",
        "promoter_pledge_pct",
    ]),
    "ownership": dict(status="placeholder", single_source=False, features=[
        "promoter_post_pct",
        "promoter_change_pre_post_pp",
        "fresh_issue_pct",
        "pre_ipo_placement_to_issue_price",
        "anchor_mf_share",
    ]),
    "business_risk": dict(status="placeholder", single_source=True, features=[
        "customer_conc_top10_pct",       # single-source (RHP only)
        "geo_conc_pct",
        "promoter_exp_years",            # single-source (RHP only)
        "company_age_years",
        "litigation_top5_to_networth",   # single-source (RHP only)
    ]),
    # Part C.4 also has a sector / macro block. It isn't RHP-sourced (sector from the
    # listing, momentum from the TRI), so it can be built before the RHP batch.
    "sector_macro": dict(status="placeholder", single_source=False, features=[
        "sector_hist_1y_base_rate",      # must be computed walk-forward (no look-ahead)
        "nifty_tri_30d_momentum_at_issue",
    ]),
}
RHP_DATASET = "dataset_reconciled.csv"   # written by reconcile.py once extraction exists


def rhp_block_values(df: pd.DataFrame, block: str) -> pd.DataFrame:
    """Columns of one block for the rows in df (keyed by isin). PLACEHOLDER: returns
    NaN until reconcile.py has produced dataset_reconciled.csv with these columns."""
    cols = RHP_BLOCKS[block]["features"]
    path = dataio.ROOT / RHP_DATASET
    out = pd.DataFrame(np.nan, index=df.index, columns=cols)
    if path.exists() and "isin" in df:
        rec = pd.read_csv(path)
        have = [c for c in cols if c in rec]
        if have:
            m = df[["isin"]].merge(rec[["isin"] + have], on="isin", how="left")
            out[have] = m[have].to_numpy()
    return out


def available_blocks() -> list[str]:
    path = dataio.ROOT / RHP_DATASET
    if not path.exists():
        return []
    cols = set(pd.read_csv(path, nrows=0).columns)
    return [b for b, v in RHP_BLOCKS.items() if any(c in cols for c in v["features"])]


# ----------------------------------------------------------------------
# loaders + features
# ----------------------------------------------------------------------
def load(horizon: str) -> pd.DataFrame:
    h = HORIZONS[horizon]
    t = dataio.load_holding_target(h["file"])
    m = dataio.load_master_with_symbols()
    m = m[m["symbol"].notna()]
    keep =["symbol", "Total", "QIB", "HNI", "RII", "Issue_Size(crores)", "Listing Gain",
            "exclude_reason"]
    df = t.merge(m[keep], on="symbol", how="left", validate="one_to_one")
    df["isin"] = df["isin"].where(df["isin"].notna(),
                                  df["symbol"].map(m.set_index("symbol")["isin"]))
    return df


def features_with(blocks: list[str]):
    def make(df: pd.DataFrame) -> pd.DataFrame:
        out = mb_features(df)
        out["listing_gain"] = pd.to_numeric(df.get("Listing Gain", df.get("listing_gain")),
                                            errors="coerce")
        for b in blocks:
            out = out.join(rhp_block_values(df, b))
        return out
    return make


NOTES = {
    "1y": [
        "**Decision time: listing-day close.** The baseline uses listing gain, so it can't be "
        "used before bidding. It answers 'hold from the listing close?', which is where the "
        "target starts.",
        "Benchmark: official Nifty 50 TRI (NSE Indices). IPO prices are dividend-adjusted (Yahoo "
        "auto_adjust), so both legs are total return.",
        "**Survivorship.** 63 seasoned, unflagged IPOs have no target (60 never resolved to a "
        "symbol, 3 with no price series). They are mostly wiped-out 2010-11 small caps (median "
        "current gain −96%). The observed base rate overstates by ~3pp. `target_MISSES.csv` "
        "must be read alongside.",
        "Baseline features share Model L's collinearity (VIF Total 83). Coefficients on "
        "QIB/HNI/RII are conditional on Total.",
        "Embargo: a training row counts for test year T only if listing + 365d < Jan 1 of T, "
        "so the most recent training rows are 1-2 years older than the test year.",
        "RHP blocks are placeholders (all NaN) until the RHP batch + reconcile.py run.",
    ],
    "3y": [
        "**Decision time: listing-day close** (baseline includes listing gain).",
        "Benchmark: official Nifty 50 TRI. Six rows exceed +500pp excess (MAZDOCK, NBCC, KAYNES, "
        "IRFC, ANANDRATHI, ANGELONE). They're genuine and don't affect the binary label.",
        "**Survivorship.** 58 seasoned, unflagged IPOs have no 3y target. Observed base rate "
        "overstates by ~4pp.",
        "**3-year embargo.** Test year T trains only on IPOs listed before T-3. Every fold "
        "trains on data at least 3 years stale, and early folds are small.",
        "RHP blocks are placeholders (all NaN) until the RHP batch + reconcile.py run.",
    ],
}


def spec(horizon: str = "1y", blocks: list[str] | None = None) -> F.ModelSpec:
    blocks = blocks or []
    h = HORIZONS[horizon]
    feats = BASELINE_FEATURES + [c for b in blocks for c in RHP_BLOCKS[b]["features"]]
    tag = "baseline" if not blocks else "+".join(blocks)
    return F.ModelSpec(
        name=f"model_h{horizon[0]}_{tag}",
        title=f"Model H{horizon[0]} ({horizon}) — {tag}",
        load=lambda: load(horizon),
        make_features=features_with(blocks),
        features=feats,
        target=h["label"],
        target_desc=f"1 if {h['excess']} (IPO return − Nifty 50 TRI return, listing close → "
                    f"+{h['days']}d) > 0",
        realised_days=h["days"],
        required_hit_rate={},              # no agreed hit-rate requirement for H yet
        notes=NOTES[horizon],
    )


def predict_live(features: dict, horizon: str = "1y") -> dict:
    """Raw inputs: Total, QIB, HNI, RII, Issue_Size, listing_gain (and RHP block values
    once those models exist)."""
    return F.predict_live(f"model_h{horizon[0]}_baseline", features, features_with([]))


def compare_blocks(horizon: str = "1y") -> pd.DataFrame:
    """Baseline vs baseline + each available RHP block, same test years, unweighted and
    at the baseline's chosen half-life. A block must beat the baseline to be kept."""
    base = spec(horizon)
    dfb = F.prepare(base)
    best, _, runs, years = F.select_half_life(dfb, base)
    rows = [{"model": "baseline", "n": len(dfb), "mean_auc": runs[best][1]["auc"].mean()}]
    for b in available_blocks():
        s = spec(horizon, [b]); d = F.prepare(s)
        if len(d) < 50:
            rows.append({"model": f"+{b}", "n": len(d), "mean_auc": np.nan}); continue
        _, per = F.walk_forward(d, s, best, years)
        rows.append({"model": f"+{b}", "n": len(d), "mean_auc": per["auc"].mean()})
    out = pd.DataFrame(rows)
    out["delta_vs_baseline"] = out["mean_auc"] - out.loc[0, "mean_auc"]
    return out


def main():
    res = {}
    for horizon in ("1y", "3y"):
        r = F.run(spec(horizon))
        res[horizon] = r
        print(f"{r['spec'].name:20s} n={len(r['df'])} half-life={r['best']} "
              f"mean AUC={r['per_best']['auc'].mean():.3f} (unweighted "
              f"{r['per_base']['auc'].mean():.3f}) years={r['years']} -> {r['card'].name}")
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        for h in ("1y", "3y"):
            print(h, "\n", compare_blocks(h).to_string(index=False))
    else:
        main()

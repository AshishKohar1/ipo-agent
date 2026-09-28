"""
reconcile.py — every value, every row, checked against independent sources.

RULE (as specified):
  For each variable on each row, compare all available independent sources.
  If max pairwise relative difference > 5%  -> value becomes NULL.
  A value with only ONE source is NOT reconciled -> it is flagged, and whether
  it survives depends on the variable's policy below.

Design principle: a NULL costs you one row of one feature. A silently wrong
value corrupts every ratio derived from it AND the fitted model weights, and
you will never find it by inspection. Always prefer the NULL.
"""
from __future__ import annotations
import numpy as np, pandas as pd, sqlite3
from dataclasses import dataclass
from pathlib import Path

TOL = 0.05          # 5% — the threshold you set
DB  = Path(__file__).resolve().parent / "ipo.db"


# ----------------------------------------------------------------------
# WHICH SOURCES ARE INDEPENDENT FOR WHICH VARIABLE
# Two derivations from the same upstream feed are NOT independent.
# ----------------------------------------------------------------------
SOURCE_MAP: dict[str, dict] = {
    # --- issue mechanics -------------------------------------------------
    "issue_size_cr": dict(
        sources=["rhp_objects", "nse_spine", "tracker", "master_dataset"],
        policy="require_2", kind="numeric"),
    "offer_price": dict(
        sources=["rhp_basis", "nse_spine", "master_dataset"],
        policy="require_2", kind="numeric"),
    "fresh_issue_cr": dict(
        sources=["rhp_objects", "chittorgarh"],
        policy="require_2", kind="numeric"),
    "ofs_cr": dict(
        sources=["rhp_objects", "chittorgarh"],
        policy="require_2", kind="numeric"),

    # --- subscription ----------------------------------------------------
    "sub_total_x": dict(
        sources=["master_dataset", "tracker", "nse_bse_live"],
        policy="require_2", kind="numeric"),
    "sub_qib_x": dict(sources=["master_dataset", "chittorgarh"],
                      policy="require_2", kind="numeric"),
    "sub_hni_x": dict(sources=["master_dataset", "chittorgarh"],
                      policy="require_2", kind="numeric"),
    "sub_rii_x": dict(sources=["master_dataset", "chittorgarh"],
                      policy="require_2", kind="numeric"),

    # --- prices / targets ------------------------------------------------
    "list_price": dict(
        sources=["master_dataset", "tracker", "nse_bhavcopy"],
        policy="require_2", kind="numeric"),
    "price_t365": dict(
        sources=["yf_nse", "yf_bse"],       # two exchanges = quasi-independent
        policy="require_2", kind="numeric"),

    # --- financials from RHP ---------------------------------------------
    "revenue_fy0_cr": dict(
        sources=["rhp_financials", "chittorgarh", "screener"],
        policy="require_2", kind="numeric"),
    "pat_fy0_cr": dict(
        sources=["rhp_financials", "chittorgarh", "screener"],
        policy="require_2", kind="numeric"),
    "roce_fy0_pct": dict(sources=["rhp_basis", "computed_from_financials"],
                         policy="require_2", kind="numeric"),
    "debt_equity": dict(sources=["rhp_financials", "chittorgarh"],
                        policy="require_2", kind="numeric"),
    "pe_at_issue": dict(sources=["rhp_basis", "computed_from_pat"],
                        policy="require_2", kind="numeric"),

    # --- single-source-by-nature: no independent check exists -------------
    # These live in the RHP only. They cannot be reconciled, so they are
    # marked unverified and EXCLUDED from any model that claims reconciliation.
    "rpt_pct_revenue":     dict(sources=["rhp_rpt"], policy="single_flag", kind="numeric"),
    "litigation_top5_cr":  dict(sources=["rhp_litigation"], policy="single_flag", kind="numeric"),
    "customer_conc_pct":   dict(sources=["rhp_risk"], policy="single_flag", kind="numeric"),
    "promoter_exp_years":  dict(sources=["rhp_management"], policy="single_flag", kind="numeric"),
    "uses_of_proceeds_n":  dict(sources=["rhp_objects"], policy="single_flag", kind="count"),
    "auditor_qualified":   dict(sources=["rhp_audit"], policy="single_flag", kind="boolean"),
    "promoter_post_pct":   dict(sources=["rhp_capital", "chittorgarh"],
                                policy="require_2", kind="numeric"),
}


@dataclass
class Result:
    value: float | None
    status: str          # reconciled | single_source_unverified | REJECTED_DISAGREE | missing
    n_sources: int
    max_rel_diff: float | None
    detail: str


def reconcile_value(var: str, observations: dict[str, float | None]) -> Result:
    """observations = {source_name: value}. None/NaN means that source had nothing."""
    cfg = SOURCE_MAP.get(var)
    if cfg is None:
        return Result(None, "missing", 0, None, f"{var} not in SOURCE_MAP")

    obs = {k: float(v) for k, v in observations.items()
           if v is not None and not (isinstance(v, float) and np.isnan(v))}

    if not obs:
        return Result(None, "missing", 0, None, "no source returned a value")

    if cfg["kind"] == "boolean":
        vals = set(bool(v) for v in obs.values())
        if len(vals) == 1:
            return Result(float(vals.pop()), "reconciled" if len(obs) > 1
                          else "single_source_unverified", len(obs), 0.0, "")
        return Result(None, "REJECTED_DISAGREE", len(obs), 1.0, "boolean sources conflict")

    vals = list(obs.values())

    if len(vals) == 1:
        src = list(obs)[0]
        if cfg["policy"] == "single_flag":
            return Result(vals[0], "single_source_unverified", 1, None,
                          f"only source: {src} — no independent check exists")
        return Result(None, "missing", 1, None,
                      f"only {src}; policy requires 2 independent sources")

    # max pairwise relative difference, using the larger magnitude as base
    mx = 0.0
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            base = max(abs(vals[i]), abs(vals[j]))
            if base == 0:
                d = 0.0 if vals[i] == vals[j] else 1.0
            else:
                d = abs(vals[i] - vals[j]) / base
            mx = max(mx, d)

    if mx > TOL:
        return Result(None, "REJECTED_DISAGREE", len(vals), mx,
                      "; ".join(f"{k}={v:,.4g}" for k, v in obs.items()))

    return Result(float(np.median(vals)), "reconciled", len(vals), mx,
                  "; ".join(f"{k}={v:,.4g}" for k, v in obs.items()))


def reconcile_frame(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    long_df columns: isin, variable, source, value
    Returns (wide reconciled dataset, full audit log).
    """
    rows, audit = [], []
    for isin, g in long_df.groupby("isin"):
        rec = {"isin": isin}
        for var, gg in g.groupby("variable"):
            obs = dict(zip(gg["source"], gg["value"]))
            r = reconcile_value(var, obs)
            rec[var] = r.value
            rec[f"{var}__status"] = r.status
            audit.append(dict(isin=isin, variable=var, status=r.status,
                              n_sources=r.n_sources, max_rel_diff=r.max_rel_diff,
                              detail=r.detail, value=r.value))
        rows.append(rec)
    return pd.DataFrame(rows), pd.DataFrame(audit)


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    con = sqlite3.connect(DB)
    long_df = pd.read_sql("SELECT isin, variable, source, value FROM observations", con)
    wide, audit = reconcile_frame(long_df)
    wide.to_csv("dataset_reconciled.csv", index=False)
    audit.to_csv("reconciliation_audit.csv", index=False)
    print(f"Rows: {len(wide)} | audit entries: {len(audit)}")
    print(audit["status"].value_counts().to_string())

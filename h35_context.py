"""
h35_context.py - the IPO-market-heat context line for the day-end report. DISPLAY ONLY.

Task 4 of the 6 November brief. H35 was run exactly as pre-registered and **failed**: the
pooled gap was 14.47pp (criterion 1 PASS) and p = 0.00883 (criterion 3 PASS), but the sign
held in only 33% of test years against a required 75% (criterion 2 FAIL), and excess_3y
failed all three. So the heat score is **not** a hold signal and nothing here may enter a
decision path.

What this module does: computes H35's own heat score over the **trailing twelve months** of
listings, bands it against the historical distribution of that same score, and returns one
line for the report. It changes no threshold and no bid logic.

The score and the variables are H35's, imported from `run_h35` rather than copied, so the
line can never drift away from the thing that was tested.

    python h35_context.py --self-test
    python h35_context.py            # print the line as it would appear
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TRAILING_MONTHS = 12
DISCLAIMER = ("context only, not a hold signal; H35 failed its pre-set test")

# H35's own variables and its own score function. Imported, never copied: a second copy
# would drift away from the thing that was tested and failed.
from run_h35 import H35_VARS as VARS, heat_score as score_row      # noqa: E402


def trailing_window(d: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    """The listings in the twelve months up to and including `today`.

    An unparseable listing date is dropped rather than guessed, and a listing dated in the
    future is not counted - both would otherwise shift the window silently.
    """
    x = d.copy()
    x["_d"] = pd.to_datetime(x["listing_date"], errors="coerce")
    lo = today - pd.DateOffset(months=TRAILING_MONTHS)
    return x[x["_d"].notna() & (x["_d"] >= lo) & (x["_d"] <= today)].drop(columns="_d")


def band_for(score, hist: pd.Series) -> str | None:
    """COOL / MID / HOT against the terciles of the historical score distribution.

    The cut-offs are the history's own terciles and are printed with the line, so the band
    is never a hidden judgement. With no history there is no band - never a default.
    """
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return None
    h = pd.to_numeric(pd.Series(hist), errors="coerce").dropna()
    if len(h) < 3:
        return None
    lo, hi = h.quantile(1 / 3), h.quantile(2 / 3)
    if score < lo:
        return "COOL"
    return "HOT" if score > hi else "MID"


def heat_line(score, hist: pd.Series, n: int, last_listing=None) -> str:
    """The one line the report prints. Always carries the disclaimer, band or no band."""
    b = band_for(score, hist)
    if b is None:
        return (f"IPO market heat (trailing {TRAILING_MONTHS}m): UNAVAILABLE "
                f"(n={n}) - {DISCLAIMER}.")
    upto = "" if not last_listing else f" to {last_listing}"
    return (f"IPO market heat (trailing {TRAILING_MONTHS}m): {b} "
            f"(score {score:+.2f} on {n} listings{upto}) - {DISCLAIMER}.")


def current(today: pd.Timestamp | None = None) -> tuple[str, dict]:
    """The line for today, plus the numbers behind it.

    Read from `model_h_features_full.csv` DIRECTLY, not through `run_h35.load()`: that
    loader inner-joins the 1-year excess-return target, which by construction cannot exist
    for a listing less than a year old, so the trailing-twelve-month window came back empty.
    The heat variables need no target.
    """
    today = today or pd.Timestamp.now()
    z = pd.read_csv(ROOT / "data" / "model_h_features_full.csv")
    for v in VARS:
        col = pd.to_numeric(z.get(v), errors="coerce")
        sd = col.std(ddof=0)
        z["z_" + v] = 0.0 if (sd is None or pd.isna(sd) or sd == 0) else \
            (col - col.mean()) / sd
    hist = pd.to_numeric(
        z.apply(lambda r: score_row(pd.Series({v: r.get("z_" + v) for v in VARS}),
                                    "B"), axis=1), errors="coerce")
    z["_heat"] = hist
    win = trailing_window(z, today)
    score = None
    last = None
    if len(win):
        s2 = pd.to_numeric(win["_heat"], errors="coerce").dropna()
        score = float(s2.mean()) if len(s2) else None
        d = pd.to_datetime(win["listing_date"], errors="coerce").dropna()
        last = None if d.empty else str(d.max().date())
    return heat_line(score, hist, n=len(win), last_listing=last), {
        "score": score, "n": len(win), "last_listing": last,
        "tercile_cuts": [None, None] if hist.dropna().empty else
        [round(float(hist.quantile(1 / 3)), 4), round(float(hist.quantile(2 / 3)), 4)]}


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

    print("[1] the variables and the score are H35's own, imported not copied")
    import run_h35
    chk("the six variables come from run_h35", VARS is run_h35.H35_VARS, str(VARS))
    chk("the score function is run_h35's", score_row.__module__ == "run_h35"
        or score_row is run_h35.heat_score, str(score_row))
    body = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    chk("no second copy of the variable list in this module",
        body.count("ipo_count_prior_3m") == 0, body.count("ipo_count_prior_3m"))

    print("[2] the window is the trailing twelve months of LISTINGS, by date")
    d = pd.DataFrame({"listing_date": ["2025-01-10", "2025-06-30", "2026-01-05",
                                       "2026-10-20", "2026-11-01"]})
    w = trailing_window(d, pd.Timestamp("2026-11-07"))
    chk("rows inside twelve months are kept", len(w) == 3, str(len(w)))
    chk("a listing 22 months back is excluded",
        "2025-01-10" not in set(w["listing_date"].astype(str)), str(list(w["listing_date"])))
    chk("the boundary is inclusive at exactly twelve months",
        len(trailing_window(pd.DataFrame({"listing_date": ["2025-11-07"]}),
                            pd.Timestamp("2026-11-07"))) == 1)
    chk("a future listing is not counted",
        len(trailing_window(pd.DataFrame({"listing_date": ["2026-12-01"]}),
                            pd.Timestamp("2026-11-07"))) == 0)
    chk("an unparseable date is dropped, not guessed",
        len(trailing_window(pd.DataFrame({"listing_date": ["not a date"]}),
                            pd.Timestamp("2026-11-07"))) == 0)

    print("[3] the band comes from the HISTORICAL distribution, stated not invented")
    hist = pd.Series([float(i) for i in range(90)])        # 0..89, terciles at 29.67, 59.33
    chk("below the lower tercile -> COOL", band_for(10.0, hist) == "COOL")
    chk("between the terciles -> MID", band_for(45.0, hist) == "MID")
    chk("above the upper tercile -> HOT", band_for(80.0, hist) == "HOT")
    chk("exactly on the lower cut -> MID, not COOL",
        band_for(float(hist.quantile(1 / 3)), hist) == "MID")
    chk("no history -> no band, never a default",
        band_for(10.0, pd.Series(dtype=float)) is None)
    chk("no score -> no band", band_for(None, hist) is None)

    print("[4] the line says what it is, and what it is NOT")
    # The history here is 0..89, so a score of 0.9 is COOL, not HOT - the first version
    # of this test asserted HOT against that history and was simply wrong.
    line = heat_line(80.0, pd.Series([float(i) for i in range(90)]), n=37)
    chk("the line names the window and the band",
        "trailing 12m" in line and "HOT" in line, line)
    chk("a cool score gives a COOL line against the same history",
        "COOL" in heat_line(0.9, pd.Series([float(i) for i in range(90)]), n=37))
    chk("the line carries the failure disclaimer verbatim", DISCLAIMER in line, line)
    chk("the line says it is not a hold signal", "not a hold signal" in line, line)
    chk("the line reports how many listings it is computed on", "37" in line, line)
    chk("no band -> the line says UNAVAILABLE and still disclaims",
        "UNAVAILABLE" in heat_line(None, pd.Series(dtype=float), n=0)
        and DISCLAIMER in heat_line(None, pd.Series(dtype=float), n=0),
        heat_line(None, pd.Series(dtype=float), n=0))
    chk("the line is ONE line", "\\n" not in line, repr(line))
    # The feature table stops at the last listing whose heat variables exist, which can be
    # months behind today. The line must say WHICH listings it covers, or a reader will
    # take it for current.
    dated = heat_line(80.0, pd.Series([float(i) for i in range(90)]), n=41,
                      last_listing="2026-05-08")
    chk("the line names the most recent listing it actually covers",
        "2026-05-08" in dated, dated)
    chk("with no listings the line still disclaims and names no date",
        "UNAVAILABLE" in heat_line(None, pd.Series(dtype=float), n=0, last_listing=None))

    print("[5] this module can never enter a decision path")
    import io as _io, tokenize as _tok
    code = " ".join(t.string for t in _tok.generate_tokens(_io.StringIO(body).readline)
                    if t.type in (_tok.NAME, _tok.OP, _tok.NUMBER))
    for bad in ("predictions_log", "score_l", "threshold", "BID", "firing_levels"):
        chk(f"no reference to {bad!r}", bad not in code, bad)

    print(f"\\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    line, info = current()
    print(line)
    print(info)

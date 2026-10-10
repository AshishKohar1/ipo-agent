"""
clean_master.py — reviewed, idempotent cleaning on data/master_with_symbols.csv.

  merge   merge reports/intermediate/symbols_CANDIDATES_cleanquery.csv:
            first trading day within ±10 days of the listing date (the master's
            'issue_open_date' column IS the listing date — see CLAUDE.md),
            no duplicate symbol, no conflict with an existing value.
          Every rejection -> reports/intermediate/merge_REJECTIONS.csv, with its reason.
  nselist resolve remaining symbols from NSE's official equity list (name + listing
          date within ±10 days); fill missing ISINs by exact symbol match
  scan    first-bar scan of every resolved symbol: a stock that traded >30 days
          before its listing date is a follow-on offer (or a reused symbol).
          -> reports/intermediate/first_bar_scan.csv (cached in checkpoints/)
  flag    write exclude_reason (fpo | reit_invit | idr | bad_listing_date). Flag, never delete.

    python clean_master.py merge
    python clean_master.py scan
    python clean_master.py flag
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
import pandas as pd

# Housekeeping, 2026-10-10. These intermediates used to be written as bare
# `to_csv("name.csv")`. The script chdir's to the project root first, so they landed in
# the ROOT by design - which is how the root accumulated twenty-odd loose files. They go
# to reports/intermediate/ now, named from __file__ so the chdir is no longer load-bearing.
INTERMEDIATE = Path(__file__).resolve().parent / "reports" / "intermediate"
INTERMEDIATE.mkdir(parents=True, exist_ok=True)


MASTER = Path(__file__).resolve().parent / "data" / "master_with_symbols.csv"
MATCH_DAYS = 10
PRE_LISTING_DAYS = 30

# Follow-on offers, identified by (a) the first-bar scan — stock traded long before the
# master's listing date — or (b) the clean-query diagnostic rejecting the company's own
# long-listed ticker. Keyed by (name regex, listing year). Each verified by hand.
FPOS = [
    (r"^Vodafone Idea", 2024),                 # IDEAFPO
    (r"^Yes Bank", 2020),                      # listed 2005; diag: first bar -5494d
    (r"^Patanjali Foods.*Ruchi Soya", 2022),   # listed as Ruchi Soya; first bar -8131d
    (r"^NTPC Limited", 2010),                  # listed 2004
    (r"^NMDC Limited", 2010),                  # listed 2008 (NSE)
    (r"^Shipping Corporation of India", 2010), # listed 1992
    (r"^Power Grid Corporation", 2010),        # listed 2007; first bar -1147d
    (r"^Power Grid Corporation", 2013),        # first bar -2267d
    (r"^Engineers India", 2010),               # listed 2006
    (r"^Engineers India", 2014),
    (r"^Tata Steel", 2011),                    # listed decades earlier
    (r"^Power Finance Corporation", 2011),     # listed 2007; first bar -1554d
    (r"^REC Limited", 2010),                   # Rural Electrification Corp, listed 2008
]
# Indian Depository Receipts: a foreign company's receipts, not an Indian equity IPO
IDRS = [(r"^Standard Chartered", 2010)]
REIT_INVIT = r"REIT|InvIT|Investment Trust|Real Estate Trust|Infra Trust|Highways Trust|Realty Trust|Nexus Select Trust|Infrastructure Fund"
BAD_LISTING_DATE = {"PROTEAN": "master listing_date 2025-02-06 is the NSE date; BSE listing 2023-11-13"}


def read():
    return pd.read_csv(MASTER, parse_dates=["issue_open_date", "listing_date"])


def merge():
    m = read()
    c = pd.read_csv(INTERMEDIATE / "symbols_CANDIDATES_cleanquery.csv",
                    parse_dates=["first_bar"])
    c["sym"] = c["candidate"].str.replace(r"\.(NS|BO)$", "", regex=True)
    dup_cands = set(c["sym"].dropna()[c["sym"].dropna().duplicated(keep=False)])
    existing = set(m["symbol"].dropna())
    rej, n = [], 0
    for _, r in c.iterrows():
        hit = m.index[m["company"] == r["company"]]
        def reject(why):
            rej.append({"company": r["company"], "candidate": r["candidate"], "reason": why})
        if len(hit) != 1:
            reject(f"company matches {len(hit)} master rows"); continue
        i = hit[0]
        if pd.isna(r["candidate"]):
            reject("no candidate: " + str(r["note"])); continue
        if pd.notna(m.at[i, "symbol"]):
            if m.at[i, "symbol"] == r["sym"]:
                continue                                   # already merged (idempotent)
            reject(f"conflict: master already has {m.at[i, 'symbol']}"); continue
        gap = (r["first_bar"] - m.at[i, "issue_open_date"]).days
        if abs(gap) > MATCH_DAYS:
            reject(f"first bar {gap:+d}d from listing date (> ±{MATCH_DAYS})"); continue
        if r["sym"] in dup_cands:
            reject("duplicate: same symbol proposed for another row"); continue
        if r["sym"] in existing:
            reject("duplicate: symbol already used by another master row"); continue
        m.at[i, "symbol"] = r["sym"]
        m.at[i, "symbol_source"] = "yahoo_cleanquery"
        existing.add(r["sym"]); n += 1
    m.to_csv(MASTER, index=False)
    pd.DataFrame(rej).to_csv(INTERMEDIATE / "merge_REJECTIONS.csv", index=False)
    print(f"merged {n} | rejected {len(rej)} -> merge_REJECTIONS.csv | "
          f"symbols now {m['symbol'].notna().sum()}/{len(m)}")
    print(pd.DataFrame(rej)["reason"].str.replace(r":.*|\d+", "", regex=True).value_counts().to_string())


def nselist():
    """Resolve remaining symbols from NSE's official equity list: name similarity
    >= 0.85 AND NSE listing date within ±MATCH_DAYS of the master listing date.
    Also fills a missing ISIN where the master symbol equals the NSE symbol exactly."""
    import dataio
    m = read(); e = dataio.load_nse_equity_list()
    existing = set(m["symbol"].dropna()); rej = []; n_sym = n_isin = 0
    win = pd.Timedelta(days=MATCH_DAYS)
    for i in m.index[m["symbol"].isna()]:
        L = m.at[i, "issue_open_date"]
        w = e[(e["listing_date"] - L).abs() <= win]
        sc = sorted(((dataio.prefix_sim(dataio.yahoo_query(m.at[i, "company"]),
                                        dataio.yahoo_query(c)), j) for j, c in w["company"].items()),
                    reverse=True)
        sc = [x for x in sc if x[0] >= 0.85]
        if not sc:
            continue
        top = [j for v, j in sc if v == sc[0][0]]
        if len(top) > 1:
            rej.append({"company": m.at[i, "company"], "candidate": "|".join(e.loc[top, "symbol"]),
                        "reason": "nselist: ambiguous"}); continue
        sym = e.at[top[0], "symbol"]
        if sym in existing:
            rej.append({"company": m.at[i, "company"], "candidate": sym,
                        "reason": "nselist: symbol already used by another master row"}); continue
        m.at[i, "symbol"] = sym; m.at[i, "symbol_source"] = "nse_equity_list"
        if pd.isna(m.at[i, "isin"]):
            m.at[i, "isin"] = e.at[top[0], "isin"]; m.at[i, "isin_source"] = "nse_equity_list"
        existing.add(sym); n_sym += 1
        print(f"  + {m.at[i, 'company'][:45]:47s} -> {sym:12s} (sim {sc[0][0]:.2f}, "
              f"NSE listed {e.at[top[0], 'listing_date'].date()}, master {L.date()})")
    bysym = e.drop_duplicates("symbol").set_index("symbol")
    for i in m.index[m["symbol"].notna() & m["isin"].isna()]:
        s = m.at[i, "symbol"]
        if s in bysym.index:
            m.at[i, "isin"] = bysym.at[s, "isin"]; m.at[i, "isin_source"] = "nse_equity_list"; n_isin += 1
    m.to_csv(MASTER, index=False)
    if rej:
        old = pd.read_csv(INTERMEDIATE / "merge_REJECTIONS.csv")
        pd.concat([old, pd.DataFrame(rej)]).to_csv("merge_REJECTIONS.csv", index=False)
    print(f"nselist: +{n_sym} symbols, +{n_isin} ISINs (exact symbol match) | rejected {len(rej)} | "
          f"symbols now {m['symbol'].notna().sum()}/{len(m)}")


def scan():
    import yfinance as yf
    m = read()
    ck = Path("checkpoints/first_bar.json")
    cache = json.loads(ck.read_text(encoding="utf-8")) if ck.exists() else {}
    for s in m["symbol"].dropna().unique():
        if s in cache:
            continue
        fb = None
        for suf in (".NS", ".BO"):
            try:
                h = yf.Ticker(s + suf).history(period="max", auto_adjust=True)
                if len(h):
                    fb = str(h.index[0].date()); break
            except Exception:
                pass
        cache[s] = fb
        ck.write_text(json.dumps(cache), encoding="utf-8")
        time.sleep(0.3)
    m["first_bar"] = pd.to_datetime(m["symbol"].map(cache))
    m["pre_listing_days"] = (m["issue_open_date"] - m["first_bar"]).dt.days
    out = m.loc[m["symbol"].notna(), ["company", "symbol", "issue_open_date", "first_bar",
                                      "pre_listing_days"]]
    out.to_csv(INTERMEDIATE / "first_bar_scan.csv", index=False)
    sus = out[out["pre_listing_days"] > PRE_LISTING_DAYS]
    print(f"scanned {len(out)} | no history {out['first_bar'].isna().sum()} | "
          f"traded >{PRE_LISTING_DAYS}d before listing: {len(sus)}")
    print(sus.to_string())


def flag():
    m = read()
    m["exclude_reason"] = None
    yr = m["issue_open_date"].dt.year
    for pat, y in FPOS:
        hit = m["company"].str.contains(pat, regex=True) & (yr == y)
        assert hit.sum() == 1, f"FPO rule {pat} {y} matched {hit.sum()} rows"
        m.loc[hit, "exclude_reason"] = "fpo"
    for pat, y in IDRS:
        hit = m["company"].str.contains(pat, regex=True) & (yr == y)
        assert hit.sum() == 1, f"IDR rule {pat} {y} matched {hit.sum()} rows"
        m.loc[hit, "exclude_reason"] = "idr"
    ri = m["company"].str.contains(REIT_INVIT, case=False, regex=True)
    m.loc[ri & m["exclude_reason"].isna(), "exclude_reason"] = "reit_invit"
    for s in BAD_LISTING_DATE:
        m.loc[m["symbol"] == s, "exclude_reason"] = "bad_listing_date"
    m.to_csv(MASTER, index=False)
    print(m["exclude_reason"].value_counts(dropna=False).to_string())
    print(m.loc[m["exclude_reason"].notna(), ["company", "symbol", "issue_open_date",
                                              "exclude_reason"]].to_string())


if __name__ == "__main__":
    import os as _os
    _os.chdir(Path(__file__).resolve().parent)   # paths are repo-root relative on any OS
    {"merge": merge, "nselist": nselist, "scan": scan, "flag": flag}[sys.argv[1]]()

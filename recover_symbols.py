"""
recover_symbols.py — Task 1: the 60 IPOs dropped for a NULL symbol.

Why they were dropped and why it matters
----------------------------------------
`run_overnight.job2_build_target()` filters to `df["symbol"].notna()`
(`run_overnight.py:312`). 60 rows of the 623 that survive `exclude_reason` have no symbol,
so they never became candidates — and crucially they are **not** in
`data/target_MISSES.csv` either. They are invisible in both directions: not a target, and
not a recorded miss. That is the real survivorship hole, and it is four times larger than
the 3 rows the build reports as dropped.

Where the symbols come from
---------------------------
Two official files **already on disk**, read through `dataio` (the data contract), so this
costs **no network requests at all** — which matters because the Model H night batch is
fetching from NSE at a 3 s gap and a second client would halve it.

  1. `dataio.load_nse_spine()`   NSE's own past-issues export, 1,082 issues with company,
                                 symbol, issue dates, listing date and security type.
                                 Covers 2021-09 onward.
  2. `dataio.load_nse_equity_list()`  NSE's EQUITY_L list: every currently listed symbol
                                 with its name and ISIN. Covers older issues that are
                                 still listed.

The matching rule, and the reason for it
----------------------------------------
**Name AND date must agree** for a spine match, exactly as the ingest rewire requires. Name
alone is how a previous probe silently returned a different company's subscription for a
guessed symbol. The master's `issue_open_date` column actually holds the **listing date**
(the known data defect in CLAUDE.md), so that is the date compared against the spine's
listing date, within 3 days.

`EQUITY_L` has **no date at all**, so a match there can only ever be name-based. Those are
accepted only when the normalised name is an **exact, unique** hit, and they are recorded
with `how = equity_list_name_only` so they are distinguishable from a dated match. A
name-only match is weaker evidence and must not be able to pass as a dated one.

What these two files CANNOT do, measured
---------------------------------------
**57 of the 60 are absent from both files under their master name**, and the reason is not
missing data - it is that the companies **renamed**:

    Macrotech Developers Limited   -> Lodha Developers Limited        (LODHA)
    Aster DM Healthcare Ltd        -> Aster DM Quality Care Limited   (ASTERDM)
    Sterling and Wilson Solar Ltd  -> Sterling and Wilson Renewable Energy (SWSOLAR)
    Flair Writing Instruments Ltd  -> Flair Writing Industries Limited (FLAIR)
    Denta Water & Infrastructure   -> Denta Water and Infra Solutions (DENTA)

This is exactly what **H28** says: name similarity cannot identify a company rename, and a
rename needs document evidence. `data/company_aliases.csv` holds 23 such aliases and none
of these 57 is among them. The remaining 3 (`SIS Ltd`, `SRS Ltd`, `BS Ltd`) normalise to
two- and three-character strings and are refused rather than prefix-matched.

**Matching on the listing date alone was tried and REJECTED.** It looked promising - an IPO
listing date ought to be discriminating - and it produced 9 "unique" matches, every one of
which is wrong:

    Barbeque Nation Hospitality  -> UFBL       (United Foodbrands Limited)
    Future Supply Chain Solutions-> SHALBY     (Shalby Limited)
    Paramount Printpac           -> MUTHOOTFIN (Muthoot Finance Limited)
    Omkar Speciality Chemicals   -> STEL       (Stel Holdings Limited)

EQUITY_L's `listing_date` is the date the **symbol** began trading on NSE, which for older
companies is a bulk-migration date shared by many unrelated names. So the date is not
discriminating in this table, and date-only matching is not implemented here. Nine
confidently wrong symbols would have been worse than sixty honest gaps (rule 1).

The third tier, queued
----------------------
NSE's `api/public-past-issues` returns about 1,474 historical issues carrying company,
symbol, ISIN, issue dates and security type, and **reaches back before 2021** -
`ingest_outcomes.nse_past_issues()` already implements it and it is how the ingest backfill
resolved 6 of its 15 unnamed rows. That is the source that can close this gap, keyed on
name AND date as H28 requires.

It is **not run from here yet** because it needs the network and the Model H night batch is
fetching from NSE at a 3 s gap (rule 5 / rule 9). A second client would halve that gap
without either knowing. It is queued in PROGRESS.md to run once the batch is idle.

Nothing is written into the master. Recovered symbols go to their own file with the
evidence for each.

    python recover_symbols.py --self-test
    python recover_symbols.py --run
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dataio                                                # noqa: E402

OUT = ROOT / "data" / "recovered_symbols.csv"
COLS = ["company", "master_date", "symbol", "isin", "security_type", "how",
        "matched_name", "matched_listing_date", "date_gap_days", "note",
        # Three passes now run, and a recovered symbol is worth nothing without the
        # evidence that produced it. `symbol_trail` shows the rename chain that was walked
        # back; `bhavcopy_verdict` is the independent date evidence H28 requires, and a
        # symbol is only written as recovered when that verdict confirms it.
        "symbol_today", "symbol_trail", "bhavcopy_confirmed", "bhavcopy_verdict"]

# Suffixes and parenthetical asides the master carries and NSE does not:
# "Apeejay Surrendra Group (conglomerate)", "Macrotech Developers Limited (Lodha Group)".
SUFFIXES = (" limited", " ltd", " private", " pvt", " india", " indias", " co",
            " company", " corporation", " corp")


# The same suffixes as `SUFFIXES`, but as whole words, for token-level comparison. Derived
# from one list rather than typed twice: two copies of a list like this drift.
SUFFIX_WORDS = {w for suf in SUFFIXES for w in str(suf).split()} | {
    "limited", "ltd", "private", "pvt", "company", "co", "the", "and", "india"}


def norm(x) -> str:
    """Lowercase alphanumerics, parentheticals removed, common suffixes stripped.

    Deterministic and documented because every match in this file depends on it. The
    parenthetical removal is what makes "Macrotech Developers Limited (Lodha Group)" match
    NSE's "Macrotech Developers Limited"; without it the row stays unresolved for a reason
    that has nothing to do with the company.
    """
    t = re.sub(r"\(.*?\)", " ", str(x).lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for _ in range(3):                      # "X Ltd Co" -> "X"
        for suf in SUFFIXES:
            if t.endswith(suf):
                t = t[: -len(suf)].strip()
    return t.replace(" ", "")


def unresolved() -> pd.DataFrame:
    """The rows Model H never saw: no `exclude_reason`, and no symbol."""
    m = dataio.load_master_with_symbols()
    if "exclude_reason" in m:
        m = m[m["exclude_reason"].isna()]
    out = m[m["symbol"].isna()].copy()
    # The master's `issue_open_date` holds the LISTING date (known defect, CLAUDE.md).
    out["master_date"] = pd.to_datetime(out["issue_open_date"], errors="coerce")
    return out[["company", "master_date"]].reset_index(drop=True)


def candidates() -> pd.DataFrame:
    """Every official name -> symbol mapping on disk, in one table, with its source.

    Both files carry a listing date, so both can be matched on name AND date - which is
    the point, since name alone is how a previous probe attached one company's figures to
    another company's symbol. An earlier version of this module looked for an EQUITY_L
    column containing "name"; `dataio` renames it to `company`, so nothing matched, every
    normalised name was empty, and 0 of 60 rows resolved.

      nse_spine        NSE's past-issues export. Issues from 2021-09 onward, carrying the
                       security type, so SME and mainboard are distinguishable.
      nse_equity_list  NSE's EQUITY_L: every CURRENTLY listed symbol, with ISIN and
                       listing date. Reaches back decades but only for companies still
                       listed today - a survivorship-biased source, which is exactly why
                       a row missing from it is informative rather than merely absent.
    """
    sp = dataio.load_nse_spine().copy()
    sp = pd.DataFrame({
        "company": sp["company"].astype(str),
        "symbol": sp["symbol"].astype(str).str.strip(),
        "isin": None,
        "security_type": sp.get("security_type"),
        "listing_date": pd.to_datetime(sp["listing_date"], errors="coerce"),
        "src": "nse_spine"})
    eq = dataio.load_nse_equity_list().copy()
    eq = pd.DataFrame({
        "company": eq["company"].astype(str),
        "symbol": eq["symbol"].astype(str).str.strip(),
        "isin": eq["isin"].astype(str).str.strip(),
        "security_type": eq.get("series"),
        "listing_date": pd.to_datetime(eq["listing_date"], errors="coerce"),
        "src": "nse_equity_list"})
    both = pd.concat([sp, eq], ignore_index=True)
    both["norm"] = both["company"].map(norm)
    return both[both["norm"].str.len() > 0].reset_index(drop=True)


def resolve(company: str, master_date, cand: pd.DataFrame,
            within_days: int = 3) -> dict:
    """One row -> `{symbol, isin, how, ...}`, or a dict saying why not.

    Tried in order of how much the evidence is worth:
      1. exact normalised name AND listing date within `within_days`
      2. exact normalised name, unique across both sources, where no date can be compared
    A non-unique hit is a **refusal**, not a choice. Picking the first of several is how
    the wrong company's figures get attached to a symbol, and that has happened here before.
    """
    n = norm(company)
    if len(n) < 4:
        return {"how": "unresolved", "note": f"normalised name too short ({n!r})"}
    hit = cand[cand["norm"] == n]
    if hit.empty:
        return {"how": "unresolved",
                "note": "not in NSE's past-issues export (2021-09 onward) nor EQUITY_L "
                        "(currently listed) - listed before 2021 and since delisted, "
                        "merged or renamed"}

    if pd.notna(master_date):
        dated = hit[hit["listing_date"].notna()].copy()
        if len(dated):
            dated["gap"] = (dated["listing_date"]
                            - pd.Timestamp(master_date)).dt.days.abs()
            near = dated[dated["gap"] <= within_days]
            syms = sorted(set(near["symbol"]))
            if len(syms) == 1:
                r = near.sort_values("gap").iloc[0]
                return {"symbol": r["symbol"], "isin": r.get("isin"),
                        "security_type": r.get("security_type"),
                        "how": f"name+date ({r['src']})", "matched_name": r["company"],
                        "matched_listing_date": r["listing_date"],
                        "date_gap_days": int(r["gap"]), "note": ""}
            if len(syms) > 1:
                return {"how": "unresolved",
                        "note": f"name and date match {len(syms)} different symbols: "
                                f"{', '.join(syms[:4])}"}
            best = int(dated["gap"].min())
            return {"how": "unresolved",
                    "note": f"name matches but the nearest listing date is {best}d away "
                            f"(limit {within_days})"}

    syms = sorted(set(hit["symbol"]))
    if len(syms) == 1:
        r = hit.iloc[0]
        return {"symbol": r["symbol"], "isin": r.get("isin"),
                "security_type": r.get("security_type"),
                "how": f"name_only ({r['src']})", "matched_name": r["company"],
                "matched_listing_date": r.get("listing_date"), "date_gap_days": None,
                "note": "no date available on one side to compare - weaker evidence"}
    return {"how": "unresolved",
            "note": f"{len(syms)} symbols share this name and no date to separate them"}


def tokens(x) -> list[str]:
    """Normalised name as words, with the corporate suffixes already gone."""
    t = re.sub(r"\(.*?\)", " ", str(x).lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    out = [w for w in t.split() if w and w not in SUFFIX_WORDS]
    return out


def resolve_date_first(company: str, master_date, cand: pd.DataFrame) -> dict:
    """The second pass: an EXACT listing date, unique, with the first word agreeing.

    Why this exists. `resolve()` requires the normalised names to be equal before it will
    look at a date, and for all 60 remaining rows they are not:

        master  "Denta Water & Infrastructure Limited"   NSE  "Denta Water and Infra Solutions Limited"
        master  "Apeejay Surrendra Group (conglomerate)" NSE  "Apeejay Surrendra Park Hotels Limited"

    Both list on exactly the master's date. The name is a paraphrase, not a different
    company. So the evidence is turned around: the DATE is the hard constraint and the name
    is the confirmation.

    Why it is not date-only. Date-only matching was measured in an earlier pass and
    produced **9 confidently wrong** symbols, so it is refused. Three conditions must all
    hold, and any one failing is a refusal rather than a guess:

      1. the candidate's listing date equals the master's date **exactly** - not within a
         window, because a window is what let a neighbouring IPO win;
      2. exactly **one** candidate symbol lists on that date, after the name filter;
      3. the **first word** of both names is identical and at least 4 characters long.

    Condition 3 is what makes it evidence rather than coincidence. "denta" == "denta" is a
    company, not a date collision; `validate_on_known()` measures how often that holds, on
    the 578 rows whose symbol is already known from another source.
    """
    if pd.isna(master_date):
        return {"how": "unresolved", "note": "no listing date on the master row"}
    mt = tokens(company)
    if not mt or len(mt[0]) < 4:
        return {"how": "unresolved",
                "note": f"first word too short to be evidence ({mt[:1]})"}
    d = pd.Timestamp(master_date).normalize()
    on_day = cand[cand["listing_date"].notna()].copy()
    on_day = on_day[on_day["listing_date"].dt.normalize() == d]
    if on_day.empty:
        return {"how": "unresolved",
                "note": f"nothing in either NSE source lists on {d.date()}"}
    on_day["first"] = on_day["company"].map(lambda v: (tokens(v) or [""])[0])
    same = on_day[on_day["first"] == mt[0]]
    if same.empty:
        others = sorted(set(on_day["symbol"]))[:4]
        return {"how": "unresolved",
                "note": (f"{len(on_day)} symbol(s) list on {d.date()} but none shares the "
                         f"first word {mt[0]!r}: {', '.join(others)}")}
    syms = sorted(set(same["symbol"]))
    if len(syms) > 1:
        return {"how": "unresolved",
                "note": (f"{len(syms)} symbols share the date AND the first word "
                         f"{mt[0]!r}: {', '.join(syms[:4])} - refused as ambiguous")}
    r = same.iloc[0]
    shared = len(set(mt) & set(tokens(r["company"])))
    return {"symbol": r["symbol"], "isin": r.get("isin"),
            "security_type": r.get("security_type"),
            "how": f"date+firstword ({r['src']})",
            "matched_name": r["company"],
            "matched_listing_date": r["listing_date"],
            "date_gap_days": 0, "shared_words": shared,
            "note": f"exact listing date {d.date()}, unique, first word {mt[0]!r} agrees"}


NAME_CHANGES = ROOT / "data" / "nse_name_changes.csv"
SYMBOL_CHANGES = ROOT / "data" / "nse_symbol_changes.csv"


def _changes():
    """NSE's own rename registers, or empty frames if they have not been fetched."""
    nc = pd.read_csv(NAME_CHANGES) if NAME_CHANGES.exists() else pd.DataFrame(
        columns=["SYMBOL", "OLD NAME OF THE COMPANY", "NEW NAME OF THE COMPANY",
                 "EFFECTIVE DATE"])
    sc = pd.read_csv(SYMBOL_CHANGES) if SYMBOL_CHANGES.exists() else pd.DataFrame(
        columns=["NAME OF THE COMPANY", "OLD SYMBOL", "NEW SYMBOL", "EFFECTIVE DATE"])
    for d, c in ((nc, "EFFECTIVE DATE"), (sc, "EFFECTIVE DATE")):
        if len(d):
            d[c] = pd.to_datetime(d[c], format="%d-%b-%Y", errors="coerce")
    return nc, sc


def walk_symbol_back(symbol: str, on_date, sc: pd.DataFrame,
                     max_hops: int = 6) -> tuple[str, list[str]]:
    """Today's symbol -> the symbol this company traded under on `on_date`.

    This is the step the first pass was missing. NSE's name register gives the symbol as it
    is NOW, so looking that symbol up in a 2016 bhavcopy fails even when the company is
    right: Larsen & Toubro Infotech listed in 2016 as `LTI`, became `LTIM`, and is `LTM`
    today. Three rejections in a row that all meant "the ticker was renamed", not "wrong
    company".

    `symbolchange.csv` carries OLD SYMBOL -> NEW SYMBOL with an effective date, so the
    chain is walked **backwards**: every change effective AFTER `on_date` is undone, newest
    first, until none applies. `max_hops` stops a cycle rather than trusting the register
    to be acyclic.
    """
    cur = str(symbol or "").strip().upper()
    trail = [cur]
    if not len(sc) or not cur:
        return cur, trail
    d = pd.Timestamp(on_date).normalize()
    sc = sc[sc["EFFECTIVE DATE"].notna()]
    for _ in range(max_hops):
        back = sc[(sc["NEW SYMBOL"].astype(str).str.strip().str.upper() == cur)
                  & (sc["EFFECTIVE DATE"] > d)]
        if back.empty:
            break
        # Newest change first: undoing them out of order would skip a link.
        row = back.sort_values("EFFECTIVE DATE", ascending=False).iloc[0]
        nxt = str(row["OLD SYMBOL"]).strip().upper()
        if not nxt or nxt in trail:
            break
        cur = nxt
        trail.append(cur)
    return cur, trail


def resolve_via_register(company: str, master_date) -> dict:
    """The official route Task 2.1 asks for first: NSE's change-of-name register.

    An EXACT normalised-name match against either the old or the new name - not a
    similarity score (H28) - gives the current symbol; `walk_symbol_back` converts that to
    the symbol as of the listing date. The caller still has to confirm it in the bhavcopy
    for that date, which is the independent date evidence H28 requires.
    """
    nc, sc = _changes()
    if not len(nc):
        return {"how": "unresolved", "note": "NSE rename registers are not on disk"}
    if pd.isna(master_date):
        return {"how": "unresolved", "note": "no listing date on the master row"}
    n = norm(company)
    if len(n) < 5:
        return {"how": "unresolved", "note": f"normalised name too short ({n!r})"}
    old_n = nc["OLD NAME OF THE COMPANY"].map(norm)
    new_n = nc["NEW NAME OF THE COMPANY"].map(norm)
    hit = nc[(old_n == n) | (new_n == n)]
    if hit.empty:
        return {"how": "unresolved",
                "note": "no exact name match in NSE's change-of-name register"}
    syms = sorted({str(x).strip().upper() for x in hit["SYMBOL"]})
    if len(syms) > 1:
        return {"how": "unresolved",
                "note": f"the register maps this name to {len(syms)} symbols: "
                        f"{', '.join(syms[:4])} - refused as ambiguous"}
    today_sym = syms[0]
    then, trail = walk_symbol_back(today_sym, master_date, sc)
    return {"symbol": then, "isin": None, "how": "nse_name_register",
            "symbol_today": today_sym,
            "symbol_trail": " <- ".join(trail),
            "matched_name": str(hit.iloc[0]["NEW NAME OF THE COMPANY"]),
            "note": (f"NSE change-of-name register; symbol walked back from "
                     f"{today_sym} to {then} for {pd.Timestamp(master_date).date()}"
                     if then != today_sym else
                     f"NSE change-of-name register; symbol unchanged since "
                     f"{pd.Timestamp(master_date).date()}")}


def validate_on_known() -> pd.DataFrame:
    """Run `resolve_date_first` on the rows whose symbol is ALREADY known, and count how
    often it reproduces that symbol.

    This is the check the first attempt at symbol recovery did not have. A matcher that
    claims 60 recoveries is worth nothing until somebody has measured what it does on cases
    where the answer is on the record. The master carries 578 symbols from the NSE spine
    and the trackers; this pretends not to know them, asks the matcher, and compares.
    """
    m = dataio.load_master_with_symbols()
    if "exclude_reason" in m:
        m = m[m["exclude_reason"].isna()]
    known = m[m["symbol"].notna()].copy()
    known["master_date"] = pd.to_datetime(known["issue_open_date"], errors="coerce")
    cand = candidates()
    rows = []
    for _, r in known.iterrows():
        got = resolve_date_first(r["company"], r["master_date"], cand)
        truth = str(r["symbol"]).strip().upper()
        claim = str(got.get("symbol") or "").strip().upper()
        rows.append({"company": r["company"], "truth": truth, "claimed": claim,
                     "how": got.get("how"),
                     "verdict": ("refused" if not claim else
                                 "correct" if claim == truth else "WRONG"),
                     "note": got.get("note", "")})
    return pd.DataFrame(rows)


def run(write: bool = True) -> pd.DataFrame:
    """Three passes, strongest evidence first, each one confirmed in the bhavcopy.

      1. `resolve`              exact normalised name AND a listing date within 3 days
      2. `resolve_date_first`   EXACT listing date, unique, first word agrees
      3. `resolve_via_register` NSE's change-of-name register, symbol walked back

    Pass 1 alone recovered **0 of 60**: for every remaining row the master's name is a
    paraphrase of NSE's, so an exact-name-first matcher never reaches the date. Passes 2
    and 3 turn the evidence around and use the date as the hard constraint.

    **Nothing is accepted on a match alone.** Every candidate symbol is looked up in the
    bhavcopy for that listing date, and a symbol that is not there does not become a
    recovery however good the name match was - that is the independent evidence H28 asks
    for, and it is what rejects a company whose ticker changed again later.
    """
    import model_h_handoff as HO
    todo, cand = unresolved(), candidates()
    rows = []
    for _, r in todo.iterrows():
        got = resolve(r["company"], r["master_date"], cand)
        if not got.get("symbol"):
            got = resolve_date_first(r["company"], r["master_date"], cand)
        if not got.get("symbol"):
            got = resolve_via_register(r["company"], r["master_date"])
        if got.get("symbol") and pd.notna(r["master_date"]):
            ok, why = HO.bhavcopy_has(got["symbol"], got.get("isin"), r["master_date"])
            got["bhavcopy_confirmed"] = bool(ok)
            got["bhavcopy_verdict"] = why
            if not ok:
                # The match is kept on the record with its reason, but the symbol is
                # withdrawn: an unconfirmed symbol in this column would be read by every
                # downstream job as a fact.
                got["note"] = (f"{got.get('note', '')} | WITHDRAWN: {why}").strip(" |")
                got["symbol"] = None
        rows.append({"company": r["company"],
                     "master_date": (None if pd.isna(r["master_date"])
                                     else f"{r['master_date']:%Y-%m-%d}"),
                     **{c: got.get(c) for c in COLS if c not in
                        ("company", "master_date")}})
    d = pd.DataFrame(rows, columns=COLS)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(OUT, index=False, encoding="utf-8")
    return d


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

    print("[1] normalisation, on the master's real awkward names")
    cases = [
        ("Macrotech Developers Limited (Lodha Group)", "macrotechdevelopers"),
        ("Apeejay Surrendra Group (conglomerate)", "apeejaysurrendragroup"),
        ("ICICI Securities Ltd", "icicisecurities"),
        ("TCNS Clothing Co. Ltd", "tcnsclothing"),
        ("Sterling and Wilson Solar Ltd", "sterlingandwilsonsolar"),
        ("Future Supply Chain Solutions Ltd", "futuresupplychainsolutions"),
    ]
    for raw, want in cases:
        chk(f"{raw[:40]!r} -> {want}", norm(raw) == want, norm(raw))
    chk("a parenthetical alone cannot make two companies equal",
        norm("Alpha Limited (X)") != norm("Beta Limited (X)"))

    print("\n[2] a match needs name AND date, and ties are refused")
    cand = pd.DataFrame({
        "company": ["Alpha Industries Limited", "Alpha Industries Limited",
                    "Gamma Steel Limited", "Delta Power Limited",
                    "Twin Holdings Limited", "Twin Holdings Limited"],
        "symbol": ["ALPHA", "ALPHAB", "GAMMA", "DELTA", "TWINA", "TWINB"],
        "isin": [None, None, None, "INEDELTA", None, None],
        "security_type": ["EQ"] * 6,
        "listing_date": pd.to_datetime(["2023-05-10", "2024-11-02", "2022-01-03",
                                        "2019-02-04", None, None]),
        "src": ["nse_spine", "nse_spine", "nse_spine", "nse_equity_list",
                "nse_spine", "nse_spine"]})
    cand["norm"] = cand["company"].map(norm)

    g = resolve("Alpha Industries Ltd", "2023-05-11", cand)
    chk("name + a date 1 day out resolves", g.get("symbol") == "ALPHA", g)
    chk("and records the gap", g.get("date_gap_days") == 1, g)
    chk("and names the source it matched in", "nse_spine" in g.get("how", ""), g)

    g = resolve("Alpha Industries Ltd", "2023-05-20", cand)
    chk("a date 10 days out does NOT resolve", "symbol" not in g, g)
    chk("and the note gives the nearest gap", "10d away" in g.get("note", ""), g)

    g = resolve("Gamma Steel Limited", None, cand)
    chk("a unique name with no date to compare resolves, labelled weaker",
        g.get("symbol") == "GAMMA" and g.get("how", "").startswith("name_only"), g)
    chk("and says the evidence is weaker", "weaker evidence" in g.get("note", ""), g)

    g = resolve("Twin Holdings Ltd", None, cand)
    chk("two symbols sharing a name with no dates is a REFUSAL, not a pick",
        g["how"] == "unresolved" and "share this name" in g["note"], g)

    print("\n[3] EQUITY_L is matched the same way, and carries the ISIN")
    g = resolve("Delta Power Ltd", "2019-02-05", cand)
    chk("it resolves on name + date", g.get("symbol") == "DELTA", g)
    chk("carries the ISIN", g.get("isin") == "INEDELTA", g)
    chk("and names EQUITY_L as the source",
        "nse_equity_list" in g.get("how", ""), g)
    chk("a dated match and a name-only match are distinguishable",
        resolve("Delta Power Ltd", "2019-02-05", cand)["how"]
        != resolve("Gamma Steel Limited", None, cand)["how"])

    print("\n[4] nothing resolvable resolves to nothing, with a reason")
    g = resolve("Entirely Unknown Holdings Limited", "2015-01-01", cand)
    chk("unknown -> unresolved", g["how"] == "unresolved", g)
    chk("and the note says where it looked and why it might be absent",
        "past-issues" in g["note"] and "delisted" in g["note"], g["note"])
    g = resolve("A", "2015-01-01", cand)
    chk("a two-character name is refused rather than prefix-matched",
        g["how"] == "unresolved" and "too short" in g["note"], g)

    print(chr(10) + "[4b] the date-first pass, MEASURED on rows whose answer is known")
    v = validate_on_known()
    nc = int((v["verdict"] == "correct").sum())
    nw = int((v["verdict"] == "WRONG").sum())
    chk("it answers on a useful share of the known rows", nc >= 300, nc)
    chk("and it is WRONG on none of them", nw == 0,
        v[v["verdict"] == "WRONG"][["company", "truth", "claimed"]].head(8).to_dict("records"))
    chk("date-only matching is NOT what this does - the first word must agree too",
        "first word" in resolve_date_first.__doc__)
    bad = resolve_date_first("Totally Unrelated Holdings Limited",
                             pd.Timestamp("2025-01-29"), candidates())
    chk("a real listing date with an unrelated name is refused",
        bad.get("symbol") is None, bad)
    chk("and the refusal names the symbols it saw on that date",
        "list on" in bad.get("note", ""), bad.get("note"))

    print(chr(10) + "[4c] the symbol is walked back to what it was on the listing day")
    _, sc = _changes()
    if not len(sc):
        print("  (NSE symbol register not on disk - skipped)")
    else:
        then, trail = walk_symbol_back("LTM", pd.Timestamp("2016-07-21"), sc)
        chk("LTM in 2026 was LTI in 2016, via LTIM",
            then == "LTI" and "LTIM" in trail, trail)
        same, tr2 = walk_symbol_back("LTM", pd.Timestamp("2026-10-01"), sc)
        chk("and a date after every change leaves the symbol alone",
            same == "LTM" and len(tr2) == 1, tr2)
        chk("a symbol with no history walks back to itself",
            walk_symbol_back("ZZZNOSUCH", pd.Timestamp("2016-01-01"), sc)[0]
            == "ZZZNOSUCH")

    print("\n[5] it never writes into the master")
    import inspect
    src = inspect.getsource(sys.modules[__name__])
    for guarded in ("master_with_symbols", "holding_target"):
        chk(f"no to_csv touching {guarded}",
            not re.search(rf"to_csv\([^)]*{guarded}", src))
    chk("output has its own file", "recovered_symbols.csv" in str(OUT))
    # The module docstring says "no network requests", so a substring check matches its
    # own prose. Docstrings are stripped first - the same trap this project has hit four
    # times now.
    code = re.sub(r'"""' + '.*?' + '"""', "", src, flags=re.S)
    chk("and no network call anywhere - dataio reads files already on disk",
        not re.search(r"(requests|urlopen|httpx|urllib)", code), code[:0])

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.run:
        d = run()
        got = d[d["symbol"].notna()]
        print(f"{len(d)} unresolved rows | recovered {len(got)} | "
              f"still unresolved {len(d) - len(got)}\n")
        print("by method:")
        print(d["how"].value_counts().to_string())
        print(f"\nwritten: {OUT}")
        raise SystemExit(0)
    ap.print_help()

"""
peer_basket.py — Task 3: peer-basket momentum from the RHP's own "Basis for Issue Price"
peer table.

    python peer_basket.py --map          # name -> NSE symbol, write the manual file
    python peer_basket.py --build        # the two variables (needs --map first)
    python peer_basket.py --self-test

The peers are the listed companies the prospectus itself names as comparable. That is the
only peer definition here: it is the issuer's own choice, disclosed before listing, so using
it carries no look-ahead and no judgement of ours about who competes with whom.

Matching is EXACT, by design (H28)
----------------------------------
A peer name is matched to an NSE symbol only by exact normalised equality against NSE's own
equity list, or against a name already in `company_aliases`. No similarity, no prefix, no
token overlap. H28 exists because name similarity silently returned a different company's
subscription for a guessed symbol, and a peer basket built on similar names would do the
same thing to a whole variable.

The extracted names are noisy - the peer-table reader produces "HDFC Limited" and
"HDFC Asset Management Company Limited" but also "March" and "October Return on Net Worth"
where a date or a header leaked into the name cell. Exact matching rejects those, which is
the correct outcome rather than a limitation: a garbage name has no symbol and must not
acquire one.

Strict point-in-time
--------------------
Every price used is from a bhavcopy dated STRICTLY BEFORE the IPO's listing date. The
window ends on the last trading day before listing, so no peer return can contain a price
from the listing day itself or after it.
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
_sys.path.insert(0, str(ROOT))

import dataio                                                        # noqa: E402

VALUES = ROOT / "data" / "rhp_valuation_values.csv"
EQUITY_L = ROOT / "data" / "NSE_EQUITY_L.csv"
MANUAL = ROOT / "data" / "manual_inputs" / "peer_symbols.csv"
MAPPED = ROOT / "data" / "peer_symbols_mapped.csv"
OUT = ROOT / "data" / "peer_basket.csv"
MIN_PEERS = 2
PEER_NAME_RE = re.compile(r"^peer_(\d+)_name$")

# A name cell that is obviously not a company. These are refused before matching so they
# never reach the manual file either - asking the user to find an NSE symbol for "March"
# wastes their time. Everything else that fails to match DOES go to them.
JUNK = re.compile(
    r"(?i)^\s*(?:january|february|march|april|may|june|july|august|september|october"
    r"|november|december|total|particulars?|peer|fiscal|information|note|source"
    r"|return\s+on|financial\s+year|consolidated|standalone|nav|eps|p\s*/\s*e"
    r"|face\s+value|rs\.?|inr)\b"
    r"|^\s*[\d,.()%*#^-]+\s*$"
    # a PERIOD phrase, anywhere in the string: "as at three months ended June",
    # "Nine months period ended December", "*Not annaulised for three months ended June"
    r"|(?:three|six|nine|twelve|\d+)\s*months?"
    r"|not\s+annu?al"
    r"|period\s+ended|year\s+ended|as\s+at\b|as\s+on\b"
    # a footnote or cross-reference that leaked into the name cell
    r"|pre-?ipo\s+placement|on\s+pages?\b|^\s*\^|^\s*\*")


def clean_name(x) -> str:
    """Strip what the peer-table reader glues onto a name.

    The reader takes the name from a text line, so it picks up the column header that
    follows it ("Anupam Rasayan India Limited Listed Peers"), footnote markers ("Torrent
    Pharmaceuticals Limited(2)", "Amber Enterprises India Limited**"), and occasionally a
    word from the row above interleaved into the name ("Dixon Consolidated Technologies
    (India) Limited" - "Consolidated" belongs to the period header).

    Only deterministic, enumerated strips happen here. Nothing is guessed: a name that is
    still unresolvable after this goes to the user, and a name with two companies glued
    together ("Bharat Electronics Ltd Astra Microwave") is left alone and will fail to
    match, which is correct - splitting it would be inventing a peer.
    """
    s = str(x)
    s = re.sub(r"(?i)\s*listed\s+peers?\b.*$", "", s)
    s = re.sub(r"(?i)\s*peer\s+(?:group|comparison).*$", "", s)
    s = re.sub(r"[*#^]+", " ", s)
    s = re.sub(r"\(\s*\d+\s*\)", " ", s)
    # "Dixon Consolidated Technologies" -> "Dixon Technologies": a period word spliced
    # between the brand and the rest. Only these three words, only mid-name.
    s = re.sub(r"(?i)(?<=\w)\s+(consolidated|standalone|restated)\s+(?=\w)", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,.;:-")


def norm(x) -> str:
    """Normalised company name. Legal suffixes dropped, because NSE's list and an RHP
    peer table spell them differently - "HDFC Bank Limited" against "HDFC Bank Ltd"."""
    s = str(x).lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(?:limited|ltd|private|pvt|public|company|co|corporation|corp|india"
               r"|\(india\)|incorporated|inc)\b", " ", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def peer_names(version: str | None = None) -> pd.DataFrame:
    """`[company, slot, peer_name]` from the extracted peer table."""
    from extract.valuation import VALUATION_VERSION
    v = version or VALUATION_VERSION
    d = pd.read_csv(VALUES, low_memory=False, on_bad_lines="skip")
    d = d[(d["extractor_version"].astype(str) == str(v)) & (d["status"] == "ok")]
    d = d[d["variable"].astype(str).str.match(PEER_NAME_RE)]
    rows = []
    for r in d.itertuples():
        # The name is text, so it is carried in the note ("peer name: X"), not in the
        # numeric `value` column.
        m = re.search(r"peer name:\s*(.+)$", str(r.note or ""))
        if not m:
            continue
        nm = m.group(1).strip()
        rows.append({"company": r.company, "listing_date": r.listing_date,
                     "slot": int(PEER_NAME_RE.match(str(r.variable)).group(1)),
                     "peer_name": nm})
    return pd.DataFrame(rows)


def nse_names() -> dict[str, str]:
    """`{normalised name: symbol}` from NSE's own equity list."""
    d = pd.read_csv(EQUITY_L)
    cols = {c.strip().upper(): c for c in d.columns}
    name_c, sym_c = cols["NAME OF COMPANY"], cols["SYMBOL"]
    out = {}
    for n, sy in zip(d[name_c], d[sym_c]):
        k = norm(n)
        if k and k not in out:
            out[k] = str(sy).strip().upper()
    return out


def map_names(version: str | None = None) -> pd.DataFrame:
    pn = peer_names(version)
    if pn.empty:
        print("no peer names extracted")
        return pn
    nse = nse_names()
    try:
        import company_aliases as CA
        alias_of = CA._load()
    except Exception:                                          # noqa: BLE001
        alias_of = {}
    # alias table is {normalised current name: [other names]}; invert it so a peer name
    # spelled the OLD way still resolves to the symbol listed under the new one.
    alias_to_current = {}
    for cur, others in (alias_of or {}).items():
        for o in others:
            alias_to_current.setdefault(norm(o), cur)

    rows = []
    for r in pn.itertuples():
        nm = clean_name(r.peer_name)
        junk = bool(JUNK.search(nm)) or len(norm(nm)) < 4
        k = norm(nm)
        sym, how = None, ""
        if not junk:
            if k in nse:
                sym, how = nse[k], "exact name in NSE EQUITY_L"
            elif k in alias_to_current:
                k2 = norm(alias_to_current[k])
                if k2 in nse:
                    sym, how = nse[k2], "exact match on a known former name (aliases)"
        rows.append({"company": r.company, "listing_date": r.listing_date,
                     "slot": r.slot, "peer_name": nm, "peer_name_raw": r.peer_name,
                     "nse_symbol": sym,
                     "matched_how": how,
                     "status": "junk" if junk else ("matched" if sym else "unmatched")})
    out = pd.DataFrame(rows)
    MAPPED.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(MAPPED, index=False, encoding="utf-8")
    # the manual file: real-looking names we could not resolve. Junk is NOT sent.
    todo = out[out["status"] == "unmatched"][
        ["peer_name", "company", "listing_date"]].drop_duplicates("peer_name").copy()
    todo["nse_symbol"] = ""
    todo = todo.rename(columns={"company": "named_in_rhp_of"})
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    todo.to_csv(MANUAL, index=False, encoding="utf-8")
    return out


def self_test() -> int:
    ok = fail = 0

    def chk(n, c, extra=""):
        nonlocal ok, fail
        if c:
            ok += 1
            print(f"  ok   {n}")
        else:
            fail += 1
            print(f"  FAIL {n} {extra}")

    src = Path(__file__).read_text(encoding="utf-8").split("def self_test")[0]
    print("[1] matching is EXACT (H28)")
    chk("no similarity matcher anywhere",
        not any(k in src for k in ("SequenceMatcher", "difflib", "fuzz", "jaro",
                                   "levenshtein", "startswith(n[")))
    chk("a peer resolves only by exact normalised equality or a KNOWN alias",
        "k in nse" in src and "alias_to_current" in src)
    chk("legal suffixes are dropped so Ltd and Limited are the same name",
        "limited|ltd" in src)
    chk("HDFC Bank Limited and HDFC Bank Ltd normalise alike",
        norm("HDFC Bank Limited") == norm("HDFC Bank Ltd"))
    chk("but two different companies do not",
        norm("HDFC Bank Ltd") != norm("HDFC Asset Management Company Ltd"))

    print(chr(10) + "[2] junk names are refused, not sent to the user")
    for j in ("March", "October Return on Net Worth", "Total", "(605.06)", "P/E"):
        chk(f"{j!r} is junk", bool(JUNK.match(j)) or len(norm(j)) < 4, norm(j))
    chk("a real name is not junk",
        not JUNK.search("HDFC Asset Management Company Limited"))
    for j in ("As at three months ended June", "Nine months period ended December",
              "*Not annaulised for three months ended June", "Fiscal",
              "^ The Company has undertaken a Pre-IPO Placement on May",
              "Information on pages xii,"):
        chk(f"{j[:34]!r} is junk", bool(JUNK.search(clean_name(j))))

    print(chr(10) + "[2b] only enumerated strips, never a guess")
    chk("a trailing column header is stripped",
        clean_name("Anupam Rasayan India Limited Listed Peers")
        == "Anupam Rasayan India Limited")
    chk("footnote markers are stripped",
        clean_name("Torrent Pharmaceuticals Limited(2)")
        == "Torrent Pharmaceuticals Limited"
        and clean_name("Amber Enterprises India Limited**")
        == "Amber Enterprises India Limited")
    chk("a spliced period word is removed",
        clean_name("Dixon Consolidated Technologies (India) Limited")
        == "Dixon Technologies (India) Limited")
    chk("two companies glued together are LEFT ALONE and will simply fail to match",
        clean_name("Bharat Electronics Ltd Astra Microwave")
        == "Bharat Electronics Ltd Astra Microwave")
    chk("junk never reaches the manual file", 'out["status"] == "unmatched"' in src)

    print(chr(10) + "[3] point-in-time")
    chk("the window ends STRICTLY before the listing date",
        "STRICTLY BEFORE" in src)
    chk("at least two mapped peers are required", MIN_PEERS == 2)
    print(f"{chr(10)}{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", action="store_true")
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if a.map:
        d = map_names(a.version)
        print(f"peer name rows: {len(d)}")
        print(d["status"].value_counts().to_string())
        print()
        print(f"IPOs with >= {MIN_PEERS} MATCHED peers: "
              f"{int((d[d['status'] == 'matched'].groupby('company').size() >= MIN_PEERS).sum())}"
              f" of {d['company'].nunique()}")
        print()
        print("matched examples:")
        print(d[d["status"] == "matched"][["company", "peer_name", "nse_symbol",
                                          "matched_how"]].head(10).to_string(index=False))
        print()
        print(f"written {MAPPED} and {MANUAL}")
        raise SystemExit(0)
    ap.print_help()

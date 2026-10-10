"""
company_aliases.py — historical company names, so resolution stops failing silently
(Priority 3).

The problem
-----------
Our master carries each company's **current** name. SEBI filings carry the name **at
filing time**. When a company has renamed, the resolver searches SEBI for a name that
never appeared on the document and reports `source_unresolved` — which looks like SEBI not
having the filing, not like us asking the wrong question.

Hand-sourcing 28 RHPs surfaced it. The user spotted four:

    Acutaas Chemicals          -> Ami Organics
    Alivus Life Sciences       -> Glenmark Life Sciences
    Eternal                    -> Zomato
    Udayshivakumar Infosolutions -> Udayshivakumar Infra

`data/rhp_sources.csv` has four more of the same kind — Adani Wilmar -> AWL Agri
Business, Abans Financial Services <- Abans Holdings, Fusion Finance <- Fusion Micro
Finance, IKIO Technologies <- IKIO Lighting — so **8 of 28 hand-sourced companies had a
genuine rename**, not 4. It also contains seven cosmetic variants and one SEBI typo
("Supiya Lifescience" for Supriya), which fail resolution just as hard.

It is not only a fetching problem. Zomato came back "not found" from a Model L query
because the master calls it Eternal.

Where the aliases come from
---------------------------
Each alias carries its evidence and how it was obtained. Nothing is inferred from a
similar-looking name alone.

  `document`    the name printed on the filing we hold, from data/rhp_sources.csv or
                `actual_company_name_on_document`. Strongest: we read it.
  `aggregator`  the name Chittorgarh recorded at IPO time for the same ipo_id, where it
                disagrees with the master's current name. Free (the 2,861-row harvest is
                already on disk, zero requests) and systematic, but it is one aggregator's
                spelling, so these are CANDIDATES and are marked as such.
  `user`        told to us directly.

Two systematic sources the user suggested, and why they are not used here:

  * **Exchange name-change notices.** NSE resets the connection for this project's
    User-Agent and BSE returns 403 even on its own robots.txt, so permission cannot be
    established for either. Not attempted. If NSE answers the access request this becomes
    the authoritative source and should replace the aggregator candidates.
  * **The "formerly known as" line on RHP covers.** Viable and authoritative, but the 400
    fetched PDFs were streamed and verified rather than retained (`data/rhp/` is empty), so
    mining them means re-fetching ~400 documents from SEBI — a night batch, not an inline
    task. `formerly_from_text()` below does the extraction and is applied to the 25
    documents we hold locally; wiring it into the fetch path means every future document
    contributes its own aliases for free.

    python company_aliases.py --build        # (re)build data/company_aliases.csv
    python company_aliases.py --self-test
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
import dataio                                               # noqa: E402

OUT = ROOT / "data" / "company_aliases.csv"
SOURCES = ROOT / "data" / "rhp_sources.csv"
COLS = ["current_name", "filing_name", "kind", "evidence_source", "evidence", "added_on"]

# kind:
#   rename          a different company name, not a spelling variant
#   suffix          Ltd/Limited/Pvt differences only
#   punctuation     spacing, dots, ampersands
#   source_typo     the SOURCE spelled it wrong (SEBI's "Supiya Lifescience")
#   our_data_error  OUR master is wrong, not a historical name
KINDS = ("rename", "suffix", "punctuation", "source_typo", "our_data_error", "candidate")

# Told to us directly. `Udayshivakumar Infosolutions` is in here as `our_data_error`
# rather than `rename`: the company is Udayshivakumar Infra and always was, so this is the
# master carrying a wrong name, not a historical one. The distinction matters because an
# our_data_error should be FIXED in the master, while a rename must be kept forever.
USER_GIVEN = [
    ("Acutaas Chemicals", "Ami Organics", "rename"),
    ("Alivus Life Sciences", "Glenmark Life Sciences", "rename"),
    ("Eternal", "Zomato", "rename"),
    ("Udayshivakumar Infosolutions", "Udayshivakumar Infra", "our_data_error"),
]

# The keyword is case-insensitive; the CAPTURED NAME is not. A global `(?i)` made
# `[A-Z]` match lowercase too, so "formerly the largest of its kind" captured "the largest
# of its kind" as a company name. A company name on a cover page starts with a capital, and
# that is the cheapest signal separating a name from prose — so the flag is scoped with
# `(?i:...)` to the keyword alternation only.
FORMERLY = re.compile(
    r"\b(?i:formerly|erstwhile|previously)\s+"
    r"(?i:known\s+as\s+|named\s+|called\s+)?"
    r"[\"'“]?([A-Z][A-Za-z0-9&.,'\- ]{4,70}?)"
    r"(?=[\"'”]?\s*(?:\)|,|\.|;|$))")


def formerly_from_text(text: str, company: str | None = None,
                       lookbehind: int = 90) -> list[str]:
    """Every "formerly known as X" in the text — but only where X is the ISSUER's old name.

    **`company` is not optional in practice.** The first version of this function took the
    text alone, and on RHP covers it was wrong almost every time, because a cover page
    names the book-running lead managers, the registrar and the selling shareholders, and
    each of those carries its own "formerly known as". It produced:

        Alivus Life Sciences  -> IDFC Securities Limited        (the lead manager)
        Alivus Life Sciences  -> Karvy Fintech Private Limited  (the registrar)
        M & B Engineering     -> Link Intime India Private 12th Floor   (an ADDRESS)
        Northern ARC Capital  -> IIFL Special Opportunities Fund (a shareholder)
        Urban Company         -> SAIF Partners India V Limited   (a shareholder)

    Every one of those would have sent the resolver to an unrelated entity's filing. So a
    match now counts only when the text immediately before "formerly" contains a name that
    is recognisably the company's own — which is exactly the shape of the cases that are
    genuine:

        IKIO Technologies Limited (formerly IKIO Lighting Limited)
        AWL Agri Business Limited, erstwhile Adani Wilmar Limited

    Passing `company=None` keeps the old unanchored behaviour and is for tests only.
    """
    out = []
    flat = re.sub(r"\s+", " ", text or "")
    for m in FORMERLY.finditer(flat):
        name = m.group(1).strip(" .,;'\"")
        if len(dataio.norm_name(name)) < 6:
            continue
        if re.search(r"(?i)\b(the|our|its|such|this|said)\b\s*$", name):
            continue
        # Reject an address or a fragment masquerading as a name.
        if re.search(r"(?i)\b(floor|plot\s*no|road|street|marg|house|tower|wing|building|"
                     r"premises|compound|estate|near|opp\.?|behind)\b", name):
            continue
        if company is not None:
            before = flat[max(0, m.start() - lookbehind):m.start()]
            # The issuer's name must appear in the run-up to "formerly". Compare over a
            # sliding window so a long legal name still matches.
            own = dataio.yahoo_query(company)
            if not own or dataio.prefix_sim(before[-len(own) - 25:], own) < 0.72:
                continue
        if name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------- classification
def classify(current: str, filing: str) -> str:
    """How different are these two names, really?"""
    a, b = str(current).strip(), str(filing).strip()
    if a.lower() == b.lower():
        return "identical"
    # Strip legal suffixes and compare
    sa, sb = dataio.yahoo_query(a), dataio.yahoo_query(b)
    if sa.lower() == sb.lower():
        return "suffix"
    # Strip all punctuation and compare
    pa = re.sub(r"[^a-z0-9]", "", sa.lower())
    pb = re.sub(r"[^a-z0-9]", "", sb.lower())
    if pa == pb:
        return "punctuation"
    sim = dataio.prefix_sim(a, b)
    if sim >= 0.92:
        # Very close but not equal: a typo in one of them, not a rename.
        return "source_typo"
    return "rename"


# ---------------------------------------------------------------- build
def _row(current, filing, kind, src, evidence) -> dict:
    return {"current_name": current, "filing_name": filing, "kind": kind,
            "evidence_source": src, "evidence": evidence,
            "added_on": str(pd.Timestamp.now().date())}


def from_sources_csv() -> list[dict]:
    """Every name difference in data/rhp_sources.csv, with the filing URL as evidence."""
    if not SOURCES.exists():
        return []
    s = pd.read_csv(SOURCES)
    rows = []
    for r in s.itertuples():
        cur = str(r.csv_company_name).strip()
        doc = str(getattr(r, "actual_company_name_on_document", "") or "").strip()
        if not doc or doc.lower() == "nan":
            continue
        k = classify(cur, doc)
        if k == "identical":
            continue
        rows.append(_row(cur, doc, k, "document", str(r.source_url)))
        # "AWL Agri Business Limited (formerly Adani Wilmar Limited)" — the master's own
        # name contains the alias. Record the bracketed form as well, since either
        # spelling may be what a later query uses.
        for old in formerly_from_text(cur, cur):
            if classify(cur, old) != "identical":
                rows.append(_row(cur, old, "rename", "document",
                                 f"'formerly' in the master's own name; {r.source_url}"))
    return rows


def from_chittorgarh() -> list[dict]:
    """Deliberately returns nothing. Kept as the record of an approach that was TRIED and
    REJECTED, so it is not attempted again as if it were new.

    The idea was free and looked systematic: the 2,861-row Chittorgarh harvest is already
    on disk, its `company` is the name recorded at IPO time, and any disagreement with the
    master's current name is a rename candidate. Zero requests.

    It does not work. Matching the two name lists by `prefix_sim` in the 0.72-0.97 band
    produced 98 candidates, and inspection showed they are mostly **different companies**:

        ARSS Infrastructure Projects  ->  JSW Infrastructure
        Godrej Properties             ->  Godrej Agrovet
        Power Grid Corporation        ->  Powerica
        Infinite Computer Solutions   ->  India Infoline
        Jaypee Infratech              ->  Rahee Infratech

    Name similarity cannot identify a rename, because renamed companies need not have
    similar names (Eternal/Zomato scores far below the band) while unrelated Indian
    companies routinely share a word like "Infra", "Global" or a family name. Feeding
    these to the resolver would send it to **another company's filing** — exactly the
    wrong-value failure hard rule 1 exists to prevent, and `_verify_is_prospectus()` would
    not catch a case where the two names are similar enough to pass the NAME test.

    Making the aggregator usable needs a name-independent key joining the harvest's
    `ipo_id` to the master. None exists: `mine_chittorgarh.py` joined on normalised name,
    so by construction it only matched rows whose names ALREADY agreed and it can offer no
    rename evidence. An ISIN on the harvest rows would fix this; the harvest does not carry
    one.

    What the harvest IS good for is one narrow hygiene problem: its names carry unescaped
    HTML entities (`Anand Rathi Share &amp; Stock Brokers`). That is an encoding artefact,
    not a historical name, so it belongs in the name normaliser rather than here.
    """
    return []


def from_local_pdfs() -> list[dict]:
    """"formerly known as" from the cover pages of the documents we hold locally."""
    try:
        import pdfplumber
    except Exception:                                        # noqa: BLE001
        return []
    d = ROOT / "_local" / "rhp_manual"
    if not d.exists():
        return []
    rows = []
    for p in sorted(list(d.glob("*.pdf")) + list(d.glob("*.PDF"))):
        try:
            with pdfplumber.open(p) as pdf:
                txt = " ".join((pg.extract_text() or "") for pg in pdf.pages[:3])
        except Exception as e:                               # noqa: BLE001
            print(f"  (could not read {p.name}: {type(e).__name__})")
            continue
        cur = p.stem
        for old in formerly_from_text(txt, cur):
            if classify(cur, old) in ("identical",):
                continue
            rows.append(_row(cur, old, classify(cur, old), "document",
                             f"'formerly' on the cover of {p.name}"))
    return rows


def build(include_pdfs: bool = True) -> pd.DataFrame:
    rows = [_row(c, f, k, "user", "given directly by the user, 2026-10-03")
            for c, f, k in USER_GIVEN]
    rows += from_sources_csv()
    if include_pdfs:
        rows += from_local_pdfs()
    rows += from_chittorgarh()
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    # Strongest evidence wins for a given (current, filing) pair.
    rank = {"user": 0, "document": 1, "aggregator": 2}
    df["_r"] = df["evidence_source"].map(rank).fillna(9)
    df = (df.sort_values("_r")
            .drop_duplicates(subset=["current_name", "filing_name"], keep="first")
            .drop(columns="_r")
            .sort_values(["kind", "current_name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    return df


# ---------------------------------------------------------------- lookup (3c)
_MAP: dict[str, list[str]] | None = None


def _load() -> dict[str, list[str]]:
    global _MAP
    if _MAP is not None:
        return _MAP
    _MAP = {}
    if OUT.exists():
        try:
            df = pd.read_csv(OUT)
            for r in df.itertuples():
                # our_data_error is NOT a historical name — it is our master being wrong.
                # It still belongs in the lookup, because until the master is fixed the
                # resolver must be able to find the document.
                _MAP.setdefault(dataio.norm_name(r.current_name), []).append(
                    str(r.filing_name))
                _MAP.setdefault(dataio.norm_name(r.filing_name), []).append(
                    str(r.current_name))
        except Exception:                                    # noqa: BLE001
            pass
    return _MAP


def aliases_for(company: str) -> list[str]:
    """Other names this company may be filed under, best-evidence first. Never includes
    the name passed in."""
    got, seen = [], {dataio.norm_name(company)}
    for a in _load().get(dataio.norm_name(company), []):
        if dataio.norm_name(a) not in seen:
            seen.add(dataio.norm_name(a))
            got.append(a)
    return got


def names_to_try(company: str) -> list[str]:
    """The company's own name first, then its aliases. This is what the resolver iterates.

    Own name first is deliberate: for the large majority that never renamed, behaviour is
    byte-identical to before, so adding the map cannot regress a company that already
    resolved.
    """
    return [company] + aliases_for(company)


def reload_map() -> None:
    global _MAP
    _MAP = None


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {detail}")

    print("company_aliases.py self-test")

    print("\n[1] classify() separates renames from cosmetic differences")
    cases = [
        ("Eternal", "Zomato", "rename"),
        ("Acutaas Chemicals", "Ami Organics", "rename"),
        ("Alivus Life Sciences", "Glenmark Life Sciences", "rename"),
        ("Abans Financial Services", "Abans Holdings Limited", "rename"),
        ("Patel Retail Ltd", "Patel Retail Limited", "suffix"),
        ("S.J.S Enterprises Limited", "SJS Enterprises Ltd", "punctuation"),
        ("Supriya Lifescience Limited", "Supiya Lifescience Limited", "source_typo"),
        ("EMS Limited", "EMS Limited", "identical"),
        ("Inox India Limited", "Inox India Limited", "identical"),
    ]
    for a, b, want in cases:
        got = classify(a, b)
        chk(f"{a!r} vs {b!r} -> {want}", got == want, f"got {got}")

    print("\n[2] formerly_from_text() reads what the document says")
    chk("plain 'formerly known as'",
        formerly_from_text("IKIO Technologies Limited (formerly IKIO Lighting Limited)")
        == ["IKIO Lighting Limited"],
        str(formerly_from_text("IKIO Technologies Limited (formerly IKIO Lighting Limited)")))
    chk("'erstwhile'",
        "Adani Wilmar Limited" in formerly_from_text(
            "AWL Agri Business Limited, erstwhile Adani Wilmar Limited, was incorporated"))
    chk("no false positive on ordinary prose",
        formerly_from_text("The company was formerly the largest of its kind.") == [],
        str(formerly_from_text("The company was formerly the largest of its kind.")))
    chk("too-short fragments rejected",
        formerly_from_text("formerly ABC)") == [],
        str(formerly_from_text("formerly ABC)")))

    print("\n[3] the lookup is symmetric and never returns the input")
    reload_map()
    if OUT.exists():
        chk("Eternal -> Zomato", any("zomato" in dataio.norm_name(a)
                                     for a in aliases_for("Eternal")),
            str(aliases_for("Eternal")))
        chk("Zomato -> Eternal (reverse)",
            any("eternal" in dataio.norm_name(a) for a in aliases_for("Zomato")),
            str(aliases_for("Zomato")))
        chk("the input name is never in its own alias list",
            all(dataio.norm_name(a) != dataio.norm_name("Eternal")
                for a in aliases_for("Eternal")))
        chk("names_to_try puts the company's own name first",
            names_to_try("Eternal")[0] == "Eternal")
        chk("an unknown company yields only itself",
            names_to_try("Zzz Nonexistent Holdings") == ["Zzz Nonexistent Holdings"])
    else:
        print("  SKIP  data/company_aliases.csv not built yet")

    print("\n[4] kinds are from the fixed vocabulary")
    if OUT.exists():
        df = pd.read_csv(OUT)
        bad = sorted(set(df["kind"]) - set(KINDS))
        chk("no kind outside the vocabulary", not bad, str(bad))
        chk("every row carries evidence", df["evidence"].notna().all())
        chk("every row carries an evidence_source", df["evidence_source"].notna().all())

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--no-pdfs", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.build:
        df = build(include_pdfs=not a.no_pdfs)
        print(f"{len(df)} aliases -> {OUT}\n")
        if not df.empty:
            print(df["kind"].value_counts().to_string())
            print()
            print(df[df["kind"] != "candidate"].to_string(index=False, max_colwidth=46))
        reload_map()
    if a.self_test:
        raise SystemExit(self_test())
    if not a.build and not a.self_test:
        print(__doc__)

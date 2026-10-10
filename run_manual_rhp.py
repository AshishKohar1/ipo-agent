"""
run_manual_rhp.py — extract the 28 hand-supplied documents (Priority 4).

They go through **exactly the same pipeline as a fetched document**: SHA-256,
`_verify_is_prospectus()` (which accepts DRHP, RHP and final Prospectus, since a DRHP
cover reads "DRAFT RED HERRING PROSPECTUS" and contains the marker), and full provenance.
No exceptions because they arrived by hand — a hand-supplied document that skipped
verification would be the one row nobody ever checks again.

Two things make this different from `rhp_night_batch.py`:

**It makes no network requests.** The PDFs are already on disk in `_local/rhp_manual/`, so this
can run alongside the SEBI batch without touching the source.

**It branches on `doc_type` (4a).** A DRHP is an earlier draft, not a broken RHP. Fields
that *cannot exist yet* in a DRHP are recorded as `missing_reason = not_in_drhp` rather
than as extraction failures. Mixing the two would make the extractor look broken where the
document is simply earlier, and would corrupt the coverage statistics being used to decide
which fields the scorecard can use. Coverage is reported split by `doc_type` so RHP-only
fields are never judged against DRHP documents.

Which fields are `not_in_drhp`, and why — each is a thing the document cannot know yet,
not a thing it merely omits:

  `anchor_portion_shares`      the anchor allocation is made ONE DAY before the issue
  `anchor_mf_reserved_pct`     opens, months after the DRHP is filed
  `promoter_holding_post_pct`  post-issue holding needs the final issue size and offer
                               price, neither of which is fixed in a DRHP
  `gcp_pct_proceeds`           general-corporate-purposes share of proceeds needs the
                               final issue size; a DRHP prints "[●]" for the amounts

Everything else IS in a DRHP and is judged normally: the objects count, the lock-in (a
regulatory requirement stated up front), related-party percentages, litigation, board
composition, contingent liabilities.

    python run_manual_rhp.py --check      # verify + SHA-256 only, no extraction
    python run_manual_rhp.py              # full run, resumable
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import gc
import hashlib
import sys
import time
import traceback
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import company_aliases                                     # noqa: E402
import dataio                                              # noqa: E402
from extract.base import Doc, Value                        # noqa: E402
from extract import h6                                     # noqa: E402
from fetch_rhp import _verify_is_prospectus                 # noqa: E402
# Reuse the night batch's page reader rather than writing another one. A naive
#   pages = [pg.extract_text() for pg in pdf.pages]
# never releases pdfplumber's per-page layout cache: on the first 400-page document it
# reached 3.4 GB and left this 8 GB laptop with 424 MB free, which is why that reader
# calls pg.flush_cache() and gc.collect() as it goes. The lesson was already paid for once.
from rhp_night_batch import page_texts_all                  # noqa: E402

MANUAL = ROOT / "_local" / "rhp_manual"
SOURCES = MANUAL / "SOURCES.csv"
OUT = ROOT / "data" / "manual_rhp_values.csv"
PROGRESS = ROOT / "data" / "manual_rhp_progress.csv"
LOG = ROOT / "reports" / "manual_rhp.log"

# 4a. Fields a DRHP cannot carry yet. See the module docstring for why each one.
NOT_IN_DRHP = ("anchor_portion_shares", "anchor_mf_reserved_pct",
               "promoter_holding_post_pct", "gcp_pct_proceeds")

PROG_COLS = ["csv_company_name", "file", "doc_type", "status", "sha256", "pages",
             "name_on_document", "name_check", "source_url", "n_ok", "n_ambiguous",
             "n_not_in_drhp", "n_missing", "secs", "note", "ran_at"]


def log(msg: str) -> None:
    print(msg, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}  {msg}\n")


# ---------------------------------------------------------------- pairing
def _norm_file(p: Path) -> str:
    return dataio.norm_name(p.stem)


def pair() -> tuple[list[dict], list[str]]:
    """Match each SOURCES.csv row to its PDF. Reports both directions of mismatch."""
    if not SOURCES.exists():
        return [], [f"{SOURCES} is missing"]
    s = pd.read_csv(SOURCES)
    pdfs = sorted(list(MANUAL.glob("*.pdf")) + list(MANUAL.glob("*.PDF")))
    by_norm = {}
    for p in pdfs:
        by_norm.setdefault(_norm_file(p), p)

    rows, notes = [], []
    used = set()
    for r in s.itertuples():
        cur = str(r.csv_company_name).strip()
        doc_name = str(getattr(r, "actual_company_name_on_document", "") or "").strip()
        cand = by_norm.get(dataio.norm_name(cur))
        if cand is None:
            # The file may be named after the name ON THE DOCUMENT instead, or after an
            # alias. Try every name we know for this company (Priority 3/4d).
            for nm in company_aliases.names_to_try(cur) + [doc_name]:
                cand = by_norm.get(dataio.norm_name(nm))
                if cand is not None:
                    notes.append(f"{cur!r}: file found under the name {nm!r}")
                    break
        if cand is None:
            notes.append(f"{cur!r}: NO PDF in _local/rhp_manual/ — cannot process")
            continue
        used.add(cand)
        rows.append({"csv_company_name": cur, "file": cand,
                     "doc_type": str(r.doc_type).strip().upper(),
                     "source_url": str(r.source_url).strip(),
                     "name_on_document": doc_name})
    for p in pdfs:
        if p not in used:
            notes.append(f"{p.name}: PDF present but no SOURCES.csv row — not processed")
    return rows, notes


# ---------------------------------------------------------------- one document
def process(row: dict, check_only: bool = False) -> dict:
    t0 = time.time()
    p: Path = row["file"]
    out = {k: row.get(k) for k in ("csv_company_name", "doc_type", "source_url",
                                   "name_on_document")}
    out["file"] = p.name
    out["ran_at"] = str(pd.Timestamp.now())

    raw = p.read_bytes()
    # 4b. SHA-256 of the exact bytes extracted from, before anything reads it.
    out["sha256"] = hashlib.sha256(raw).hexdigest()

    # 4d. Cross-check the name on the document. The name we SEARCH with is the one on the
    # document where SOURCES.csv gives it, because that is what the cover actually says.
    verify_name = row.get("name_on_document") or row["csv_company_name"]
    okv, whyv = _verify_is_prospectus(raw, verify_name)
    out["name_check"] = ("matched the name on the document" if okv else whyv)
    if not okv and verify_name != row["csv_company_name"]:
        # Try our own name too, so a SOURCES.csv typo cannot reject a good document.
        okv2, whyv2 = _verify_is_prospectus(raw, row["csv_company_name"])
        if okv2:
            okv, out["name_check"] = True, ("matched our master's name, not the name "
                                            "recorded on the document")
    if not okv:
        out.update({"status": "not_a_prospectus", "note": whyv,
                    "secs": round(time.time() - t0, 1)})
        return out

    del raw                      # ~10-60 MB per document; not needed past verification
    import pdfplumber
    with pdfplumber.open(p) as pdf:
        out["pages"] = len(pdf.pages)
    if check_only:
        out.update({"status": "verified", "note": "",
                    "secs": round(time.time() - t0, 1)})
        return out
    pages = page_texts_all(p)

    doc = Doc(path=p, company=row["csv_company_name"], doc_type=row["doc_type"],
              sha256=out["sha256"], doc_url=row["source_url"], n_pages=out["pages"])
    vals: list[Value] = h6.extract(doc, pages)

    # 4a. Re-label the DRHP-impossible fields. Done AFTER extraction, not by skipping them:
    # if a DRHP does somehow carry a real value we keep it, and only a miss is re-labelled.
    n_drhp = 0
    if row["doc_type"] == "DRHP":
        for v in vals:
            if v.variable in NOT_IN_DRHP and v.status not in ("ok", "ambiguous"):
                v.missing_reason = "not_in_drhp"
                v.note = (f"{v.note} | DRHP: this field cannot exist before the issue is "
                          f"priced — not an extraction failure").strip(" |")
                n_drhp += 1

    rows_out = []
    for v in vals:
        d = v.as_row()
        # 4c. The URL is recorded exactly as SOURCES.csv gives it. Never a URL we
        # did not observe, and never reconstructed.
        d["url"] = row["source_url"]
        d["source"] = "manual_rhp"
        d["doc_type"] = row["doc_type"]
        d["name_on_document"] = row.get("name_on_document")
        rows_out.append(d)
    df = pd.DataFrame(rows_out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8")

    st = df["status"].value_counts()
    out.update({"status": "done", "n_ok": int(st.get("ok", 0)),
                "n_ambiguous": int(st.get("ambiguous", 0)), "n_not_in_drhp": n_drhp,
                "n_missing": int(len(df) - st.get("ok", 0) - st.get("ambiguous", 0)),
                "note": "", "secs": round(time.time() - t0, 1)})
    return out


# ---------------------------------------------------------------- batch
def done_already() -> set[str]:
    if not PROGRESS.exists():
        return set()
    try:
        d = pd.read_csv(PROGRESS)
    except Exception:                                       # noqa: BLE001
        return set()
    return set(d.loc[d["status"].isin(["done", "verified"]), "csv_company_name"]
               .astype(str))


def record(out: dict) -> None:
    pd.DataFrame([{c: out.get(c) for c in PROG_COLS}], columns=PROG_COLS).to_csv(
        PROGRESS, mode="a", header=not PROGRESS.exists(), index=False, encoding="utf-8")


def main(check_only: bool = False) -> dict:
    rows, notes = pair()
    for n in notes:
        log(f"  pairing: {n}")
    skip = done_already()
    todo = [r for r in rows if r["csv_company_name"] not in skip]
    log(f"manual_rhp: {len(rows)} paired, {len(skip)} already settled, {len(todo)} to do"
        + (" (CHECK ONLY)" if check_only else ""))

    counts = {}
    for i, r in enumerate(todo, 1):
        try:
            out = process(r, check_only)
        except Exception as e:                              # noqa: BLE001
            out = {**{k: r.get(k) for k in ("csv_company_name", "doc_type", "source_url",
                                            "name_on_document")},
                   "file": r["file"].name, "status": "error",
                   "note": f"{type(e).__name__}: {e}", "ran_at": str(pd.Timestamp.now())}
            log(f"  [{i:3d}/{len(todo)}] {r['csv_company_name'][:34]:36s} ERROR "
                f"{type(e).__name__}: {e}")
            traceback.print_exc()
        else:
            log(f"  [{i:3d}/{len(todo)}] {r['csv_company_name'][:34]:36s} "
                f"{r['doc_type']:5s} {out['status']:16s} "
                f"ok={out.get('n_ok', 0):3d} amb={out.get('n_ambiguous', 0):2d} "
                f"drhp={out.get('n_not_in_drhp', 0):2d} miss={out.get('n_missing', 0):3d} "
                f"{out.get('secs', 0):5.0f}s"
                + (f"  <-- {out.get('note', '')[:70]}" if out["status"] != "done" else ""))
        record(out)
        gc.collect()
        counts[out["status"]] = counts.get(out["status"], 0) + 1
    log(f"manual_rhp finished: {counts}")
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify + SHA-256 only")
    a = ap.parse_args()
    print(main(a.check))

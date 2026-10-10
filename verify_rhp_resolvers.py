"""
verify_rhp_resolvers.py — the CLAUDE.md verification protocol for fetch_rhp.py.

Five companies: a mainboard large-cap, a mainboard mid-cap, an SME, a 2015 issue and a
2011 issue. Each must (1) resolve to a document that passes _verify_is_prospectus() and
(2) state an issue size within 1% of the master dataset. Writes data/rhp_verify.json; the
batch refuses to run unless passed == 5. Nothing is written to ipo.db.

The master dataset has no SME rows, so the SME test uses an IPOMatrix tracker row (its
issue size is single-source).
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # ₹ on Windows consoles
import json
import pandas as pd
import dataio
import fetch_rhp as R

TOL = 0.01


def _cases():
    m = dataio.load_master_with_symbols()
    def mb(pat, slot):
        r = m[m["company"].str.contains(pat, regex=True)].iloc[0]
        return dict(slot=slot, company=r["company"], isin=r["isin"],
                    listing_date=r["listing_date_master"], size_cr=float(r["Issue_Size(crores)"]),
                    offer_price=float(r["Offer Price"]), size_source="master",
                    doc_type="RHP", sources=("SEBI", "NSE"))
    t = dataio.load_trackers()
    s = t[t["company"].str.contains("CapitalNumbers")].iloc[0]
    return [
        mb(r"^Hyundai Motor India", "mainboard large-cap"),
        mb(r"^Jupiter Life Line", "mainboard mid-cap"),
        dict(slot="SME", company=s["company"], isin=s["isin"], listing_date=s["listing_date"],
             size_cr=float(s["issue_size_cr"]), offer_price=float(s["issue_price"]),
             size_source="tracker (single-source; master has no SME rows)",
             doc_type="PROSPECTUS", sources=("SEBI", "BSE_SME", "NSE")),
        mb(r"^Syngene", "2015 issue"),
        mb(r"^TD Power Systems", "2011 issue"),
    ]


def main():
    out = []
    for c in _cases():
        print(f"\n=== {c['slot']}: {c['company']} (listed {c['listing_date']:%Y-%m-%d}, "
              f"₹{c['size_cr']:,.2f}cr)")
        doc = R.fetch_for_company(c["company"], c["isin"], c["doc_type"], c["listing_date"],
                                  sources=c["sources"])
        print(f"  {c['doc_type']}: {doc.status} via {doc.source} — {doc.note[:300]}")
        size, how, size_doc = None, "", None
        if doc.status == "ok":
            # issue size: the final prospectus states it; else RHP shares × offer price
            fp = doc if doc.doc_type.startswith("PROSPECTUS") else R.fetch_for_company(
                c["company"], c["isin"], "PROSPECTUS", c["listing_date"], sources=c["sources"],
                fallback=False)
            tries = []
            if fp.status == "ok":
                x = R.issue_size_from_pdf(fp.local_path)
                tries += [("gross", x["gross"], "PROSPECTUS"), ("net offer", x["net"], "PROSPECTUS")]
            x = R.issue_size_from_pdf(doc.local_path, c["offer_price"])
            tries += [("shares × offer price", x["shares_x_price"], doc.doc_type)]
            tries = [t for t in tries if t[1] is not None]
            print(f"  issue size candidates: {[(k, round(v, 2), d) for k, v, d in tries]}")
            if tries:                        # the candidate closest to the reference
                k, size, size_doc = min(tries, key=lambda t: abs(t[1] - c["size_cr"]))
                how = f"{k} from {size_doc}; all: " + ", ".join(f"{k2}={v2:,.2f}" for k2, v2, _ in tries)
        diff = None if size is None else abs(size - c["size_cr"]) / c["size_cr"]
        passed = doc.status == "ok" and diff is not None and diff <= TOL
        why = ("PASS" if passed else
               f"document: {doc.status} — {doc.note}" if doc.status != "ok" else
               "issue size not found on cover" if size is None else
               f"issue size {size:,.2f}cr vs {c['size_source']} {c['size_cr']:,.2f}cr "
               f"({diff*100:.2f}% > 1%)")
        print(f"  -> {why[:300]}")
        out.append({**{k: (str(v) if k == "listing_date" else v) for k, v in c.items()
                       if k != "sources"},
                    "doc_status": doc.status, "doc_source": doc.source, "doc_url": doc.url,
                    "doc_pages": doc.pages, "doc_note": doc.note, "size_from_doc_cr": size,
                    "size_method": how, "size_doc": size_doc,
                    "size_diff_pct": None if diff is None else round(diff * 100, 3),
                    "passed": passed, "reason": why})
    n = sum(o["passed"] for o in out)
    R.VERIFY_FILE.write_text(json.dumps({"passed": n, "of": len(out), "run_at": str(pd.Timestamp.now()),
                                         "cases": out}, indent=2, default=str), encoding="utf-8")
    print(f"\n{n}/{len(out)} verified -> {R.VERIFY_FILE.name}")
    return out


if __name__ == "__main__":
    main()

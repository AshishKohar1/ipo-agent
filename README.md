# RHP Agent — run order and rules

Runs in **Claude Code on your machine**. Will not run in claude.ai (sandbox has no
network access, so it cannot fetch PDFs).

```bash
pip install pandas numpy requests yfinance pdfplumber camelot-py[cv] \
            statsmodels scikit-learn beautifulsoup4 lxml
```

---

## Run order

| # | Command | Produces | Time |
|---|---|---|---|
| 0 | `python check_env.py` | pass/fail | seconds |
| 1 | `python run_overnight.py` (or `build_target_and_stats.py target`, same code) | `master_with_symbols.csv`, `holding_target.csv`, `target_MISSES.csv` | 6–8 h |
| 2 | *implement resolvers* (see below) | — | ~half a day |
| 3 | `python fetch_rhp.py` | `rhp_pdfs/`, `documents` table | 20–40 h |
| 4 | `python extract_batch.py` | `observations` table | 40–60 h |
| 5 | `python reconcile.py` | `dataset_reconciled.csv`, `reconciliation_audit.csv` | minutes |
| 6 | `python build_target_and_stats.py` | `review/STATS_REVIEW.txt` | minutes |

Do step 1 first. It's independent of the RHP work and it unblocks the holding model.

---

## Step 2 — the one thing you must do by hand

`_resolve_document_url()` in `fetch_rhp.py` raises `NotImplementedError` deliberately.

I could not verify SEBI/NSE/BSE's current DOM structure and JSON endpoints from my
sandbox — it has no network access to those sites. Writing plausible-looking selectors
I hadn't tested would have been the single most damaging thing I could hand you: they'd
look right, fail silently or fetch the wrong PDF, and quietly poison the dataset.

**Verification protocol before running the batch:**

1. Implement one resolver per source against the live page.
2. Run it against **five companies whose RHP you can eyeball**, spanning a mainboard
   large-cap, a mainboard mid, an SME, a 2015-vintage issue, and a 2011-vintage issue.
3. Confirm all five pass `_verify_is_prospectus()`.
4. Confirm the extracted issue size matches the master dataset within 1%.
5. Only then queue the remaining ~475.

`_verify_is_prospectus()` already guards the pipeline: it opens every PDF, requires a
prospectus marker in the first four pages, requires the company name to appear, and
rejects anything under 100 pages as an addendum. A wrong URL therefore produces a
logged failure, not a corrupt row.

---

## Reconciliation rules as implemented

- Every variable, every row, compared across the independent sources in `SOURCE_MAP`.
- Max pairwise relative difference **> 5% → value becomes NULL**, status
  `REJECTED_DISAGREE`, both values preserved in the audit log.
- `policy="require_2"` — fewer than two independent sources → NULL. Most variables.
- `policy="single_flag"` — variables that exist **only** in the RHP and have no
  independent check anywhere (RPT %, litigation quantum, customer concentration,
  promoter experience, uses-of-proceeds count, auditor qualification). These are kept
  but marked `single_source_unverified`, and Section 6 of the stats pack lists them.

**Decision you need to make after seeing the stats:** those single-source variables
cannot be reconciled by any method, because no second source exists. Either accept
them as unverified, or drop them. Do not let them sit in a dataset you describe as
"fully reconciled" — that's how a caveat gets lost.

Two derivations from the same upstream feed are **not** independent. Chittorgarh and
IPOMatrix share a parent, so they never count as two sources for the same field.

---

## Known failure modes

| Failure | Expected rate | Handling |
|---|---|---|
| Scanned-image RHPs (pre-2015) | ~15% of that vintage | Needs OCR; logged as `unreadable pdf` |
| Document not on any official site | 5–10% | `source_unresolved` — logged, never guessed |
| Delisted/suspended before T+365 | ~8% of target rows | `target_MISSES.csv` — **biases base rate upward** |
| TOC won't parse | ~10% | Regex fallback on section headers |

The survivorship one matters most. Companies that vanish from yfinance are
disproportionately the failures, so your measured "beat Nifty" base rate will be
optimistic. Read `target_MISSES.csv` before quoting any number from this dataset.

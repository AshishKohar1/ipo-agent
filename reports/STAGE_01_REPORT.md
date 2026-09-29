# Stage 1 — Environment check

**Status:** DONE (on the laptop). Every check that can be executed here passes: 13/13 in
`check_env.py` plus all of `stage1_env_check.py`. **One half of step 1 is deliberately
unverified** — this ran on Windows, not the Linux cloud session, so the `pip install -r
requirements.txt` path in the cloud is still untested. See Deviations.

## What was done
- Extended `check_env.py` from 9 to **13 checks**, making the laptop's implicit assumptions explicit and OS-aware. No existing check was removed.
- Added `stage1_env_check.py` (steps 1, 3, 4, 5) so the laptop and a future cloud session can be compared run-for-run; results land in `reports/stage1_checks.json`.
- All 11 required domains reachable; robots.txt captured for the six sites later stages intend to read.
- Dataset integrity and the numpy estimator regression test pass; Syngene's RHP round-tripped from SEBI by SHA-256 and was deleted.

## Key numbers

| Check | Result |
|---|---|
| `check_env.py` | **13/13 PASS** (was 9/9) |
| Interpreter | Python 3.14.5, win32, Windows-11-10.0.26200, AMD64 |
| `requirements.txt` pins vs installed | **9/9 match exactly** — no install was needed |
| Domains reachable | **11/11** (5 required, 6 needed by later stages) |
| `robots.txt` blanket disallow | **none** of the 6 scraping targets |
| master rows | 652 = expected |
| `exclude_reason` flags | 29 = expected (reit_invit 14, fpo 13, bad_listing_date 1, idr 1) |
| `excess_1y` rows | 491 = expected |
| `excess_3y` rows | 331 = expected |
| Benchmark on both targets | `nifty50_tri` only |
| Nifty TRI | 4,395 rows, 2009-01-01 → 2026-09-25, **max calendar gap 6 days**, 0 nulls, sorted, unique |
| Estimator vs statsmodels MLE | 3.01e-10 (tol 1e-6) |
| Estimator penalised gradient at optimum | 9.21e-15 (tol 1e-8) |
| AUC vs brute-force pairwise | 0.00e+00 (tol 1e-12) |
| Syngene RHP SHA-256 round-trip | **matches**, `_verify_is_prospectus` True, 401 pages, temp file deleted |

### New `check_env.py` checks (step 2)

| Check | Why it is OS-aware |
|---|---|
| `platform` | Reports OS, arch, interpreter — makes the environment part of the record instead of an assumption |
| `requirements.txt pins match what is installed` | Reports per-package mismatches rather than failing outright, so an older cloud interpreter that cannot take numpy 2.5.1 surfaces as a visible deviation. Also states the interpreter version the pins imply (3.12+) |
| `scikit-learn absent (rule 10) and no module imports it` | Asserts no module imports sklearn on any OS. Honest note: **sklearn is present in this environment** (installed in an earlier session) but unused and absent from `requirements.txt` |
| `statsmodels Logit import path` | The laptop-specific Application Control block is turned into a portable requirement: `statsmodels.discrete.discrete_model.Logit` must import everywhere. It also records whether `statsmodels.api` is importable — blocked here, expected to work in the cloud |

### Domain reachability (step 3)

| Domain | Probe | Status | Needed for |
|---|---|---|---|
| www.sebi.gov.in | `/` | 200 | RHP / prospectus (Stages 8–10) — **required** |
| www.niftyindices.com | `/reports/historical-data` | 200 | Nifty 50 TRI — **required** |
| query2.finance.yahoo.com | `/v1/finance/search?q=Reliance` | 200 | prices, symbols — **required** |
| www.nseindia.com | `/api/marketStatus` | 200 | equity list, offer-doc listing — **required** |
| www.bsesme.com | `/` | 200 | SME prospectus — **required** |
| www.bseindia.com | `/` | 200 | reconciliation (later) |
| www.chittorgarh.com | `/` | 200 | day-wise subscription (Stage 4) |
| www.ipoji.com | `/` | 200 | subscription, 2nd source (Stage 4) |
| www.investorgain.com | `/` | 200 | GMP history (Stage 4) |
| www.screener.in | `/` | 200 | financials reconciliation (Stage 8) |
| www.rbi.org.in | `/` | 200 | 91-day T-bill (Stage 11) |

**A first pass wrongly reported Yahoo and NSE as blocked**, and would have failed Stage 1.
The probe was at fault, not the network: a bare `GET /` is meaningless for an API host —
`query2.finance.yahoo.com/` returns 404 by design, and `www.nseindia.com/` returns 403
unless the request carries browser-like `Accept` headers. Both answer 200 on the endpoints
the pipeline actually calls (NSE's archives CSV also 200). Each host is now probed on a
light, representative endpoint. Recorded because the same false alarm would otherwise
recur in the cloud.

### robots.txt (step 3b, added beyond the plan)

Rule 5 requires respecting robots.txt, and Stage 4 is the first stage that scrapes. Checking
now rather than mid-batch:

| Site | `User-agent: *` disallow rules | Matters for |
|---|---|---|
| chittorgarh.com | `/ipo/ipo_discussions.asp` | Stage 4 — subscription pages themselves are allowed |
| ipoji.com | `/profile`, `/bids` | Stage 4 — **`/bids` is disallowed**; the subscription path must avoid it |
| investorgain.com | none | Stage 4 GMP |
| screener.in | `/user/*`, `/*?q=`, `/*?sort=`, `/*?limit=`, `/*?page=` | Stage 8 — **query-string URLs are disallowed**; use clean company paths |
| sebi.gov.in | `/js`, `/hindi/js`, `/css`, `/hindi/css` | filings and PDFs allowed |
| bsesme.com | none | SME prospectus |

No site blanket-disallows crawling. Two constraints to carry into later stages: ipoji's
`/bids` and screener's query-string patterns.

## Deviations from plan
1. **Step 1 ran on Windows, not a Linux cloud session.** `PLAN.md` section 3 permits stages 1+ on the laptop, but step 1's wording ("confirm the session is on Linux and `requirements.txt` installed cleanly") cannot be satisfied here. What *was* verified: all 9 pins match the installed versions exactly, so the pin set is internally consistent. What was **not** verified: that `pip install -r requirements.txt` resolves cleanly on a fresh Linux image. **The first cloud session must re-run `python check_env.py` and `python stage1_env_check.py` before any stage runs there.**
2. **The Python-version contingency did not apply.** This laptop runs 3.14.5, so numpy 2.5.1 installed without issue and no downgrade was needed. If a cloud image ships Python 3.11 or older, the pin-match check will report it per-package as a deviation.
3. **Added `stage1_env_check.py` and step 3b (robots.txt).** Not in the plan's step list; both serve rule 5 and make Stage 1 reproducible across environments.
4. **scikit-learn is installed in this environment** though rule 10 forbids adding it. It is not in `requirements.txt` and no module imports it, so a fresh clone or cloud environment will not have it. Left in place rather than uninstalled, since removing it changes nothing the repo depends on.

## Open issues
1. The cloud half of step 1 is outstanding (deviation 1). Until then, "the environment is validated" means the laptop only.
2. `statsmodels.api` is blocked on this laptop by Windows Application Control. Code must keep importing `Logit` from `statsmodels.discrete.discrete_model`; `check_env.py` now enforces that path.
3. Stage 4 and Stage 8 must honour the two robots.txt constraints above.

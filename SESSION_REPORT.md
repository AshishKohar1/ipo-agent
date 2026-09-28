# Session report: Model L framework, Model H start

Started 2026-09-28. This file is updated after each task, so partial progress stays usable if the session stops.
Backups of the files this session changes are in `_backup_session2/`.

| Task | Status |
|---|---|
| 1. Clean dataset | ✅ done |
| 2. Framework + Model L | ✅ done |
| 3. Model H targets | ✅ done |
| 4. Model H skeleton | ✅ done |
| 5. RHP resolvers | ✅ done (5/5 verified, batch not started) |

---

## Task 1: clean the dataset ✅

### 1.1 Merge clean-query candidates: 117 merged, 85 rejected

`clean_master.py merge` applied the pipeline's bar itself rather than trusting the diagnostic's verdict: first trading day within ±10 days of the listing date, no duplicate symbol, no conflict with an existing value. All 117 candidates passed, with no duplicates or conflicts. The 85 rejections are logged with their reasons in `merge_REJECTIONS.csv`: 83 had no candidate, and 2 were the two Power Grid FPO rows, whose name matches two master rows.

**Extra step, `clean_master.py nselist`: +11 symbols.** Yahoo search still returned nothing for live companies such as SBI Cards, IRCTC, HUDCO and ICICI Pru Life, because it mishandles long names and "&". NSE's official securities list (`EQUITY_L.csv`, saved as `data/NSE_EQUITY_L.csv` and loaded via `dataio.load_nse_equity_list()`) has every live stock's listing date. Matching on name similarity ≥0.85 **and** NSE listing date within ±10 days recovered 11 more, every one with an exact date match. It also filled **426 ISINs** by exact symbol match. 431 of the 437 filled rows have NSE listing dates within 10 days. The other 6 are the same companies, which listed on BSE first and joined NSE later.

That also explains **PROTEAN**: it listed on BSE on 2023-11-13 and on NSE on 2025-02-06, and the master had taken the NSE date.

**Symbols: 450 → 567 (clean-query merge) → 578 (NSE list) of 652 = 88.7%.**

### 1.2 Job 1c fixed permanently

- `dataio.yahoo_query()` strips Ltd/Limited/Pvt/Company and bracketed aliases, including unclosed brackets. Job 1c uses it.
- The 1c checkpoint key is now `q2:<cleaned query>`. Rows cached as misses under the old raw-name query get retried rather than skipped.
- 1c's match bar is tightened from ±400 days to ±10 days (`SYMBOL_MATCH_DAYS`). ±400 days was loose enough to accept a namesake or an FPO.

### 1.3 `exclude_reason`: 29 rows flagged, none deleted

| Reason | n | Rows |
|---|---|---|
| fpo | 13 | Vodafone Idea 2024, Yes Bank 2020, Ruchi Soya/Patanjali 2022, NTPC 2010, NMDC 2010, REC 2010, Shipping Corp 2010, Power Grid 2010 and 2013, Engineers India 2010 and 2014, Tata Steel 2011, Power Finance Corp 2011 |
| reit_invit | 14 | The 13 identified overnight, **plus IndiGrid Infrastructure Fund 2017**, which is also an InvIT |
| idr | 1 | Standard Chartered 2010, an Indian Depository Receipt. That's not an equity IPO and not an FPO either, so it gets its own reason |
| bad_listing_date | 1 | PROTEAN |

The FPOs were identified by name, confirmed by the clean-query diagnostic rejecting each company's own long-listed ticker, and then checked by hand. `clean_master.py scan` checked all 567 resolved symbols for trading before their listing date: **none did**. So no follow-on offers are hidden among the resolved rows.

### 1.4 Corrected base rate: arithmetic shown and revised

**Why the old 34.6–37.8% didn't add up.** It was (152 hits + 117×0.411 + 92×0) / 579 = 34.6%. Adding the 117 at the *observed* rate leaves the rate unchanged, so the only thing that moved it was the 92 dropouts set to 0. That contradicted my own evidence that the 117 were winners. The denominator also still included FPO and REIT rows.

**Now measured, not assumed.** Job 2 was re-run on the merged symbols:

| Set | n | H base rate |
|---|---|---|
| Night run, all rows | 370 | 41.1% |
| Night run, flagged rows excluded | 362 | 40.3% |
| **Newly merged rows** | 127 | **45.7%** (the winners pull the rate *up*, as expected) |
| **Cleaned set (flagged rows excluded)** | **489** | **41.7%**; median excess −10.3pp |

**Survivorship.** 554 seasoned, unflagged rows = 489 built + 5 Job 2 misses + 60 never resolved. Base rate across all 554 is (204 + 65 × r) / 554, where r is the rate at which the 65 missing rows beat the Nifty:

| Assumption about the 65 missing | Base rate |
|---|---|
| All fail (r = 0) | **36.8%** |
| Beat at half the observed rate (r = 0.209) | 39.3% |
| Beat at the observed rate (r = 0.417) | 41.7% |

The 65 missing are nearly wiped out: median current gain is **−96%**, and 72% are down more than 50%. They're mostly 2010–11 small caps (40 of 65). The realistic range is **~37–39%**, so **survivorship overstates 41.7% by about 3–5pp**.

Files changed: `master_with_symbols.csv` (symbols, ISINs, `exclude_reason`), `dataio.py`, `run_overnight.py` (1c), `holding_target.csv` and `target_MISSES.csv` (re-run). New files: `clean_master.py`, `merge_REJECTIONS.csv`, `first_bar_scan.csv`, `data/NSE_EQUITY_L.csv`, `task1_baserate.txt`.

---

## Task 2: shared framework + Model L ✅

### Environment problem: scikit-learn and part of statsmodels are blocked

**Windows Application Control policy on this PC blocks compiled DLLs** from scikit-learn (`_cd_fast`, installed this session) and from statsmodels' time-series module (`_innovations`, which `statsmodels.api` imports). I did not try to get around the policy. Instead:
- **The estimator is pure numpy** (`framework.BalancedLogit`). It reproduces sklearn's `LogisticRegression(penalty='l2', C=1, class_weight='balanced')` objective exactly, solved by Newton's method, and I validated it:
  - unpenalised fit vs statsmodels' Logit MLE: max coefficient difference 3e-10;
  - penalised, balanced, weighted fit: gradient at the optimum 1e-14;
  - AUC vs brute-force pairwise count, ties included: exact match.
- **The robust-SE Logit** is imported directly from `statsmodels.discrete`, which loads fine. One caveat: statsmodels' discrete Logit gives *identical* SEs for HC0, HC1 and HC3. It applies a generic robust sandwich estimator, not HC3's small-sample leverage correction. The cards say so.

If you want sklearn itself, it would need an allow-rule in Windows security, which is your decision.

### `models/framework.py`: reusable by every model

A model is a `ModelSpec`: a loader (via `dataio` only), a feature builder, a target, `realised_days` and thresholds. The framework does the rest identically for every model:
- drops rows with an `exclude_reason`;
- recency weights 0.5^(age/half-life), with effective n = (Σw)²/Σw² reported alongside raw n;
- walk-forward validation over the last 5 test years with enough data, with out-of-fold probabilities only and weights applied to training rows only;
- the **target-window embargo**: a training row is eligible only if listing date + `realised_days` falls before Jan 1 of the test year;
- half-life selection over {2, 3, 5, 8, none} by mean walk-forward AUC;
- calibration by decile, winner vs unweighted, side by side;
- a threshold table with Wilson 95% lower bounds, and threshold verification;
- standardised coefficients and the robust-SE Logit summary;
- a final fit saved with joblib, `predict_live()`, and an auto-generated model card.

Weights are normalised to mean 1 in each training set. Otherwise their absolute scale, which depends on today's date, would silently change the L2 penalty.

**Threshold rule:** "fire at ≥t" promises an out-of-fold hit rate of at least t, on at least 10 fires. A failing threshold is **never kept**; it's replaced by the lowest threshold that does deliver t.

### Model L results: `models/model_l.py`, four models, segments never pooled

| Model | n (eff. n) | Half-life | Walk-forward AUC by year | **Mean AUC** | Unweighted | Base rate |
|---|---|---|---|---|---|---|
| L1 mainboard (gain > 0) | 620 (620) | none | 2022 .699, 2023 .804, 2024 .818, 2025 .804, 2026 .698 | **0.765** | 0.765 | 68.4% |
| L2 mainboard (gain > 10) | 620 (323) | 2y | .908, .865, .889, .866, .863 | **0.878** | 0.865 | 43.5% |
| L1 SME | 402 (391) | 2y* | 2026 only: .796 | **0.796** | 0.795 | 62.2% |
| L2 SME | 402 (391) | 2y* | 2026 only: .824 | **0.824** | 0.824 | 36.3% |

\*SME half-life selection is meaningless: every half-life scored within 0.001. See the SME caveat below.

**The CLAUDE.md claim of "AUC 0.883" came from 5-fold CV.** Under honest walk-forward validation, L2 reaches 0.878, which is close. **L1 reaches only 0.765.** Its weakest years are 2022 (0.699) and 2026 (0.698, n=20).

### Thresholds re-verified out-of-sample

| Threshold | Fires | OOF hit rate | 95% lower bound | Verdict |
|---|---|---|---|---|
| **L1 mainboard ≥90%** | 88 (29.5% of IPOs) | **97.7%** | 92.1% | ✅ **PASS**. Also beats the spec's claimed 92.5% |
| **L2 mainboard ≥80%** | 123 | **79.7%** | 71.7% | ❌ **FAIL** (98/123). **Use ≥85%**: 90/107 = 84.1% (lower bound 76%) |
| L1 SME ≥90% | 0 | — | — | ❌ nothing reaches 0.90. **Use ≥55%**: 47/52 = 90.4% (lower bound 79%) |
| L2 SME ≥80% | 34 | 76.5% | 60.0% | ❌ **FAIL**. **Use ≥85%** |

The spec's claim for L2 ≥80% (94.4% hit on about 10% of IPOs) **does not hold out-of-sample**. At ≥90%, L2 hits 91.1% on 79 fires; at ≥95%, it hits 36 of 36. The saved bundles use the verified thresholds: mainboard L1 0.90, L2 0.85; SME L1 0.55, L2 0.85.

### Calibration

`class_weight='balanced'` pulls probabilities towards 0.5, so they are **not** calibrated to the base rate:
- **L1 mainboard** is under-confident at the low end: rows scored 0.1–0.2 actually list up 46% of the time.
- **L2 mainboard** is over-confident from 0.6 to 0.9: in the 0.8–0.9 bin, the predicted 86% becomes 59% actual. That's why L2's ≥80% threshold fails.

The per-decile tables for the winner and the unweighted baseline are in each card.

### Findings you should act on

1. **Severe collinearity in the mainboard features.** VIF is 83 for Total, 20 for HNI, 20 for QIB and 8 for RII, against the spec's limit of 5. The negative QIB/HNI/RII coefficients are conditional on Total, not real effects. The category split adds almost nothing out of sample: L1 AUC 0.765 vs 0.760 on Total + size alone, and L2 is *better* without it (0.871 vs 0.865). **Recommendation:** use Total + log size, or the three categories without Total. I kept your specified features.
2. **Half-life selection by mean per-year AUC** lets the 2026 fold (n=20) count as much as 2025 (n=102), and for L1 that decides the choice. On pooled out-of-fold AUC, 2y would win.
3. **Decision time.** Every Model L variant uses *final* subscription, which is only knowable at bid close. These are D3 models, not valid for a day 1–2 bid.
4. **SME history is too thin.** Two calendar years give **one** walk-forward fold (test 2026, trained on 2025 alone). There's no year-to-year spread to judge stability by. Recency weighting over 1–2-year-old data is almost flat (effective n 391 of 402), so half-life selection is noise. Treat every SME number as provisional.
5. **The targets aren't comparable.** SME listing gain is the listing-day close (tracker); mainboard's `Listing Gain` comes from the master, whose open/close basis isn't documented.

### Files
- `models/framework.py`, `models/model_l.py`
- `models/model_{l1,l2}_{mainboard,sme}.joblib` and `_CARD.md`
- `dataio.py`: tracker loader now returns issue size, subscription and reconciled listing gain; new `load_master_with_symbols()` and `load_holding_target()`

Live prediction:
```python
from models.model_l import predict_live
predict_live("mainboard", {"Total": 120, "QIB": 180, "HNI": 250, "RII": 30, "Issue_Size": 900})
# L1 p=0.909 FIRE, L2 p=0.876 FIRE
```
A missing input returns `NO CALL`; it is never imputed.

---

## Task 3: Model H targets ✅

### 3.1 Benchmark: official Nifty 50 TRI obtained

- **Source:** NSE Indices Ltd (niftyindices.com), using the same `POST /BackPage/getTotalReturnIndexString` call its Historical Data page makes. The site caps requests at one year, so `fetch_nifty_tri.py` pages through in 360-day chunks. The result is `data/NIFTY50_TRI.csv`: 4,395 daily rows from 2009-01-01 to 2026-09-25, with no nulls. It's loaded via `dataio.load_nifty_tri()`.
- **Validation against ^NSEI:**
  - daily-return correlation is 0.9999;
  - the TRI/price ratio never decreases;
  - there are no calendar gaps over 6 days;
  - **TRI beat the price index in every year from 2010 to 2026, by 1.32pp a year on average.** That's the dividend yield, and it confirms the ~1.2pp bias you cited. It's now removed.
- **Effect:** the benchmark return rose by 1.29pp on average across 362 common rows, and **5 labels flipped** from beat to miss.
- Every target row has `benchmark = nifty50_tri`. ^NSEI is still available as `job2_build_target(h, "nsei")` for comparison only.

### 3.2 / 3.3 Targets, rebuilt on the cleaned set (29 flagged rows skipped)

`run_overnight.job2_build_target(horizon, benchmark)` now handles both horizons with the same method and checks. It writes `holding_target.csv` / `target_MISSES.csv` for 1y and `holding_target_3y.csv` / `target_MISSES_3y.csv` for 3y.

**One method fix.** Job 2 used to take the `.NS` series whenever it had more than 20 bars. For BSE-first IPOs, NSE trading can start years later, so those rows were being dropped. It now prefers whichever exchange's series starts at the listing. That recovered IGIL, FCONSUMER and others: 1y misses went from 5 to 3.

| | **excess_1y (primary)** | **excess_3y (secondary)** |
|---|---|---|
| Rows built | **491** | **331** |
| Listing-date path | known 238, derived 253 | known 83, derived 248 |
| **Base rate** (beat the TRI) | **40.3%** (41.7% on ^NSEI) | **36.0%** |
| Median excess | **−11.6pp** | **−34.6pp** |
| Mean / p10 / p90 | +4.8 / −56.3 / +83.6 | +10.5 / −99.4 / +163.7 |
| Job 2 misses | 3 (ARISINFRA, SGLTL, SAH: no price series) | 1 (SAH) |
| Never resolved, seasoned | 60 | 57 |
| **Survivorship misses** | **63** of 554 seasoned | **58** of 389 seasoned |
| Base rate if all misses failed / beat at half rate | 35.7% / 38.0% | 30.6% / 33.3% |

**Checks, both horizons, all passed:**
- label equals excess > 0 on every row;
- returns recomputed from prices match within 1e-13;
- the identity excess = IPO return − benchmark return holds within 1e-13;
- no duplicate symbols and no non-positive prices.

On 1y, nothing exceeds 500pp. **On 3y, six rows do**, and all are genuine multibaggers with consistent adjusted prices:

| Symbol | Listed | 3y excess |
|---|---|---|
| MAZDOCK | 2020 | +1170pp |
| NBCC | 2012 | +907pp |
| KAYNES | 2022 | +705pp |
| IRFC | 2021 | +635pp |
| ANANDRATHI | 2021 | +613pp |
| ANGELONE | 2020 | +611pp |

Winsorise any continuous 3y target. The binary label isn't affected.

**Survivorship.** The missing rows are nearly wiped-out 2010–11 small caps, with a median current gain of −96%. Realistic central estimates are **~37% (1y)** and **~32% (3y)**. So the observed rates overstate by roughly 3pp and 4pp.

---

## Task 4: Model H skeleton ✅

`models/model_h.py` is built on the same framework, with the same interface as Model L: `spec()` → `framework.run()` → joblib bundle, model card and `predict_live()`.

### Baseline: the bar every RHP block must beat

Features: log1p of Total, QIB, HNI and RII; log issue size; listing gain. Validation used the same half-life selection and walk-forward protocol as Model L, **with the target-window embargo**: a training row counts for test year T only if listing date + 365d (or + 1095d) falls before Jan 1 of T.

| | **H1: excess_1y > 0 (primary)** | **H3: excess_3y > 0 (secondary)** |
|---|---|---|
| n (base rate) | 490 (40.3%) | 330 (36.0%) |
| Test years | 2021–2025 | 2017, 2018, 2021, 2022, 2023 (2019 and 2020 have fewer than 20 rows) |
| Per-year AUC | .461, .670, .447, .552, .494 | .462, .583, .591, .487, .689 |
| Chosen half-life | 8y (0.525 vs 0.524 unweighted: a meaningless gap) | none |
| **Mean walk-forward AUC** | **0.525** | **0.562** |
| Pooled out-of-fold AUC | 0.545 | 0.556 |

**The baseline has essentially no predictive power.** No coefficient is significant: robust p-values are all above 0.07, and above 0.2 for listing gain. Per-year AUC swings between 0.42 and 0.69 around 0.5. This matches the spec's finding (Part C.3) that listing gain and long-run return correlate at only 0.218: **pre-listing demand and the listing pop don't tell you who wins over a year.**

That makes the bar easy to state. **To earn its place, an RHP block must lift mean walk-forward AUC clearly above 0.525 (1y) and 0.562 (3y) on the same test years.** `python models/model_h.py compare` runs exactly that comparison for every block with data, and reports the change in AUC against the baseline.

The embargo costs data. The 2021 test fold trains only on IPOs listed before 2020 (n=190), and 3y folds train on data at least 3 years old (n=76 for 2017). That's the price of not leaking returns from the test period, and it's why H folds are smaller than L folds.

**Decision time.** Because the baseline includes listing gain, H-baseline answers "hold from the listing-day close?", which is exactly where the target starts. It can't be used before bidding. Every RHP block is knowable pre-bid, so a pre-bid H is the baseline minus listing gain, plus RHP blocks. The spec supports this directly.

### RHP feature-block placeholders (Part C.4)

`RHP_BLOCKS` defines 35 feature columns in 7 blocks, each marked `status="placeholder"`:

| Block | Columns |
|---|---|
| valuation | 6 |
| quality_moat | 8 |
| balance_sheet | 4 |
| governance | 5 |
| ownership | 5 |
| business_risk | 5 |
| sector_macro | 2 |

Sector/macro is Part C.4's seventh block. It isn't RHP-sourced, so it can be built before the RHP batch.

- `rhp_block_values(df, block)` returns NaN for every column until `reconcile.py` writes `dataset_reconciled.csv` with those columns. **To plug a block in, only that file needs to exist; nothing is restructured.** `spec(horizon, blocks=[...])` adds a block's columns, and `compare_blocks()` tests each one against the baseline.
- Blocks containing RHP-only variables are marked `single_source=True`: governance (RPT %, auditor qualification) and business_risk (customer concentration, promoter experience, litigation). This follows CLAUDE.md: they will be flagged `single_source_unverified` and must never be called reconciled.
- The spec warns that ~35 features on ~480 rows is too many and must be cut to 15–18. Given a baseline AUC of 0.525, **test blocks one at a time and keep only those that lift AUC**, rather than fitting them all at once.

`predict_live({'Total':…, 'QIB':…, 'HNI':…, 'RII':…, 'Issue_Size':…, 'listing_gain':…}, '1y' | '3y')` works. There are no H thresholds yet, and at an AUC near 0.5 none should be set.

Files: `models/model_h.py`, `models/model_h{1,3}_baseline.joblib` and `_CARD.md`.

---

## Task 5: RHP resolvers ✅ (5/5 verified; batch NOT started)

### Resolvers in `fetch_rhp.py`, built by inspecting each live site

| Source | How it works | Status |
|---|---|---|
| **SEBI** | Keyword search on Public Issues, then the filing page, then its PDF. Sub-sections: DRHP = 10, RHP = 11, final Prospectus = 12. | ✅ implemented and verified. Covers every mainboard IPO. No gate. |
| **NSE** | JSON listing at `/api/corporates/offerdocs?index=equities\|sme&from_date&to_date`. Matched by **ISIN** (exact) or name. Returns DRHP/RHP/prospectus links, PDF or ZIP. | ✅ locating works. ⚠️ **Downloads are switched off**; see below. |
| **BSE SME** | A static listing page with direct DRHP and prospectus links. | ✅ implemented and verified. No gate. |
| BSE mainboard | A JavaScript app that loads its offer-document screen lazily; I couldn't locate the API. | ❌ not implemented. SEBI covers every mainboard IPO, so nothing is lost. |

**Matching rule.** A filing is accepted only if its name similarity is ≥0.85 **and** its filing date falls in a window around the listing date:

| Document | Window |
|---|---|
| DRHP | up to 3 years before listing |
| RHP | up to 90 days before listing |
| Prospectus | 30 days either side of listing |

That stops a namesake or another year's issue being picked. Every PDF is then still checked with `_verify_is_prospectus()`.

**Honesty rules.**
- A `source_unresolved` note now lists what each source actually did.
- A document that was found but couldn't be downloaded is recorded as `fetch_failed`, not "not found".
- **RHP → final Prospectus fallback** happens only when no source lists an RHP at all. SEBI's archive has no RHP entries for many pre-2012 issues, and the Prospectus is the RHP with the final price filled in. It's recorded as `doc_type = PROSPECTUS_AS_RHP` and never triggered by a failed download.

### Verification: `python fetch_rhp.py verify` → `rhp_VERIFY.json`

| Slot | Company | Document | Pages | Issue size from document | Reference | Diff | Result |
|---|---|---|---|---|---|---|---|
| Mainboard large-cap | Hyundai Motor India (2024) | SEBI RHP | 476 | ₹27,855.68cr (prospectus cover) | master ₹27,858.80cr | 0.011% | ✅ |
| Mainboard mid-cap | Jupiter Life Line (2023) | SEBI RHP | 442 | ₹869.08cr | master ₹869.08cr | 0.000% | ✅ |
| **SME** | CapitalNumbers Infotech (2025, BSE SME) | BSE SME prospectus | 369 | **net offer** ₹160.69cr (gross ₹169.37cr) | tracker ₹160.69cr | 0.000% (net) | ✅ see note |
| 2015 issue | Syngene International | SEBI RHP | 401 | ₹550.00cr (prospectus; also 22,000,000 shares × ₹250) | master ₹550.00cr | 0.000% | ✅ |
| 2011 issue | TD Power Systems | **SEBI final Prospectus** (no 2011 RHP on SEBI) | 345 | ₹227.00cr | master ₹227.00cr | 0.000% | ✅ |

**All five pass both `_verify_is_prospectus()` and the 1% issue-size check.**

**Things to know before trusting this:**
1. **The SME slot passes on the *net* offer.** IPOMatrix records SME issue size **net of the market-maker reservation**. For CapitalNumbers, the gross offer is ₹169.37cr and the market-maker portion is ₹8.68cr, which leaves the ₹160.69cr net offer the prospectus itself labels "Net Offer". The document is correct; the definitions differ. Against the gross figure it would fail (5.4%). This also means **Model L SME's issue-size feature is net-of-market-maker throughout**. That's consistent within the tracker data, but it's not comparable to mainboard sizes.
2. **The master has no SME rows**, so the SME test used a tracker row, which is single-source. That's a deviation from "five companies from the master".
3. **The NSE download path was never exercised.** NSE puts offer-document downloads behind an **"I agree" disclaimer** (the `offerDocsAgreeCheckbox` modal). I did not accept it on your behalf. `NSE_DOWNLOADS_ALLOWED = False`, and `check_env.py` asserts it stays False. If you read NSE's disclaimer and are happy to accept it, set it to True. Until then, **NSE-Emerge SME IPOs have no gate-free source**. BSE SME and SEBI cover everything else.
4. The issue-size reader takes the **largest money amount on the prospectus cover** (the total offer is at least as large as each component). The currency sign isn't required, because table-layout covers separate "₹" from its number. It found the right total on all five, but it's a heuristic. In the batch, any mismatch against the master should be treated as a failure, never overridden.

### Guard rails left in place
- `python fetch_rhp.py batch` **refuses to run** unless `rhp_VERIFY.json` shows 5/5 passed. It now does, so the batch is technically unlocked. **I did not start it**, as instructed.
- No `ipo.db` exists. The only files downloaded are the verification PDFs in `rhp_pdfs/` (8 files, 57 MB).
- `check_env.py`: 9/9 passing. The old "resolver raises NotImplementedError" check is replaced by "batch gated on 5/5 verification; NSE disclaimer not auto-accepted".

---

## Session summary

| | Before | After |
|---|---|---|
| Symbols | 450 / 652 | **578 / 652 (88.7%)**; ISINs on 437 more rows |
| Flagged, not deleted | — | 29 (13 fpo, 14 reit_invit, 1 idr, 1 bad_listing_date) |
| Benchmark | ^NSEI price index | **official Nifty 50 TRI** (+1.32pp/yr dividend bias removed) |
| H 1y target | 370 rows, 41.1% | **491 rows, 40.3%** (realistically ~37% after survivorship) |
| H 3y target | — | **331 rows, 36.0%** (realistically ~32%) |
| Model L | K-fold AUC 0.883 claimed | walk-forward: **L1 0.765, L2 0.878** mainboard; SME 0.80 / 0.82 on a single fold |
| L thresholds | L1 ≥90%, L2 ≥80% | **L1 ≥90% holds (97.7%)**; **L2 ≥80% fails (79.7%) → ≥85%** |
| Model H baseline | — | **AUC 0.525 (1y), 0.562 (3y)**: the bar for RHP features |
| RHP resolvers | not implemented | **5/5 verified** (SEBI + BSE SME); NSE gated by its disclaimer |

### Decisions waiting for you
1. **Start the RHP batch?** It's unlocked (5/5 verified) but not started.
2. **Accept NSE's offer-document disclaimer?** This is only needed for NSE-Emerge SMEs.
3. **Model L features:** drop Total or the category split, given VIF 83 and no out-of-sample gain.
4. **scikit-learn:** it needs a Windows Application Control allow-rule if you want it instead of the validated numpy estimator.
5. **Half-life rule:** switch from the plain mean of per-year AUCs to pooled or n-weighted AUC, so a 20-row year doesn't decide the choice.

# Model H — readiness (Task 6, 2026-11-02)

What exists on the rebuilt Mac, what it rests on, and what is in the way. **Nothing was
fitted for this report**: every number below is read from a committed card, report or data
file, or counted from one. H29 is untouched.

## The table

| component | state | evidence | blocked by |
|---|---|---|---|
| **1y target** (`excess_1y`) | **READY** | `data/holding_target.csv`, 491 rows, all non-null; 40.3% beat the Nifty 50 TRI. Card: 490 usable after `exclude_reason`, final fit n=490, effective n=436.2 | nothing — but survivorship: 63 seasoned IPOs have no target, median current gain −96%, so the base rate overstates by ~3pp (`data/target_MISSES.csv`) |
| **3y target** (`excess_3y`) | **READY** | `data/holding_target_3y.csv`, 331 rows, all non-null; 36.0% beat. Card: 330 usable, unweighted | the same survivorship bias, plus only 5 test years (2017, 2018, 2021–2023) |
| **Baseline fit** | **DONE, below the stop rule** | `models/model_h1_baseline_CARD.md` mean AUC **0.525**, pooled OOF 0.545; `model_h3_baseline_CARD.md` mean AUC **0.562**, pooled OOF 0.556 | H29 is not met and cannot be met by a reader fix: at AUC 0.525 the top band has no edge to find |
| **Stable core** | **IDENTIFIED, 6 variables** | `reports/MODEL_H_STABILITY.md`: STABLE in all three window schemes **and** the embargoed run — `ipo_count_prior_3m`, `ipo_count_prior_6m`, `mean_listing_gain_prior_3m`, `nifty_tri_ret_12m`, `rhp_uses_of_proceeds_n`, `turnover_x_issue_size` | two of the six are not free: `rhp_uses_of_proceeds_n` comes only from the RHP, and `turnover_x_issue_size` needs the bhavcopy cache, which was lost with the disk |
| **H45 ratio coverage** | **PARTIAL — the P/B leg is empty** | `data/valuation_ratios_h45.csv`, 433 rows: `ipo_pe` 263 (60.7%), `ipo_pe_weighted` 256 (59.1%), `pe_premium_vs_peers` 123 (28.4%), `pat_cagr` 49 (11.3%), `ipo_peg` 30 (6.9%), **`ipo_pb` 7 (1.6%)**, **`ipo_pb_pre_issue` 0 (0.0%)**. 291 of 433 rows carry at least one ratio | the NAV readers. H45(b) withholds rather than approximates, so a missing NAV is a NULL by design — but 0 of 433 is not coverage, it is an absent variable |
| **Check set** | **20 chosen, 7 transcribed** | `reports/rhp_check_set_docs.csv` 20 documents, all 20 cached; `reports/CHECK_SET_COVERAGE.md`: **3** at 5/5, 4 partial, **13 at 0/5 — not transcribed** | hand transcription. 124 `status = value` truth rows cover 7 documents; the other 13 contribute nothing to the gate |
| **Five readers** | **3 of 5 pass the 95% gate, on thin evidence** | `reports/READER_GATE.md`, regenerated 2026-11-02 (H53): `net_worth` 100% on **1** value, `tax_expense` 100% on **1**, `shares_outstanding_pre_issue` 100% on **5**; `finance_costs` 50% on 2, `depreciation_amortisation` 0% on 1 | recall, not precision. 21 truth rows yield 10 produced values. A 95% precision floor measured on one value is a coin, not a gate (H53 §2) |
| **H29 stop rule** | **NOT TESTED** | H29 needs a walk-forward top-20% band with ≥50 picks, ≥54% hit vs TRI and a Wilson 95% lower bound above the base rate. No run has produced a band; the baseline's AUC 0.525 would not clear it | the stable core cannot be assembled while `rhp_uses_of_proceeds_n` and `turnover_x_issue_size` are incomplete. Until then Model H stays **display-only** by H29's own terms |
| **H35 fallback** (Model H-market) | **SPECIFIED, NOT RUN** | H35, specified 2026-10-13 before any combined fit: a tercile statement about market heat at listing rather than a per-IPO ranking | nothing technical — it needs the same 6-variable core, but it is a coarser claim and may survive where the per-IPO one does not. It is the next thing to try, not the last |

## What the table says, in one line each

1. **Both targets are ready.** They are the only part of Model H that is finished.
2. **The blocker is not the model, it is two variables.** Four of the six stable-core
   variables are market and calendar data already in `data/`. The two that are not —
   uses-of-proceeds count and turnover — are the entire gap between a baseline and a
   testable H29 run.
3. **The P/B leg of H45 does not exist.** `ipo_pb_pre_issue` is 0 of 433, `ipo_pb` is 7.
   H45 is right to withhold, but a variable that is NULL for 98% of rows cannot enter a
   model, and no amount of reader precision changes that — it is a recall problem.
4. **The gate's passes are thin.** Three readers pass at 100% on one, one and five values.
   The honest summary is H50's: the readers withhold rather than err.
5. **13 of 20 check-set documents have no ground truth.** The gate cannot get stronger
   until they are transcribed, and transcription is hand work, not a batch.

## Not done here

No fit, no refit, no threshold, no new variable, and no change to H29. The brief said to
stop at this table.

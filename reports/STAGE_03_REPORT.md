# Stage 3 — Calibration curve and final thresholds

**Status:** DONE (analysis complete and verified). **Isotonic calibration is adopted for
both targets.** One housekeeping item outstanding: `reports/stage3_calibration.json` still
holds the first, superseded run — see "Open issues".

## What was done
- Implemented both calibrators in pure numpy (`models/calibration.py`): PAV isotonic and two-parameter Platt, since scikit-learn is unavailable. Both unit-checked.
- Fitted them **out of time** on Set A's out-of-fold predictions: for test year T, fit on years before T, apply to T. Held-out sample 260 rows (2023–2026) per target.
- Compared raw / Platt / isotonic by held-out Brier score and decile reliability.
- Derived thresholds both ways **and corrected a flaw in my own first comparison** (below).
- Applied the adoption test in PLAN.md Stage 3 step 5.

## The flaw I had to fix first

My first pass chose the bucket-rule threshold by scanning the **same 260 held-out rows it
was then scored on**. That inflates it: the threshold is selected *because* it satisfies the
constraint on those rows. The calibrated rule had no such advantage — its calibrator only
ever saw earlier years. The comparison was not apples-to-apples and favoured the bucket rule.

Corrected: the bucket threshold is now also chosen **out of time** (on years < T, applied to
year T), exactly as the calibrators are. That reverses the conclusion.

| L2, required 80% | Threshold chosen on… | Fires | Hit rate | Verdict |
|---|---|---|---|---|
| Bucket rule, first pass | the same rows it is scored on | 104 | 83.7% | looked like a PASS |
| Bucket rule, out of time | prior years only | 83 | **77.1%** | **FAILS the 80% promise** |

The 83.7% was an artefact of threshold selection. Honestly measured, the section-5 bucket
rule **does not deliver L2's 80% hit rate** when its threshold has to be picked from history.

## Key numbers

### Held-out Brier score (lower is better), 260 rows per target

| Target | raw | Platt | isotonic | Best |
|---|---|---|---|---|
| L1 | 0.1596 | 0.1583 | **0.1579** | isotonic |
| L2 | 0.1624 | **0.1557** | 0.1586 | Platt |

Both calibrators beat raw on both targets, so the first adoption condition is met throughout.

### Thresholds, both rules, both out of time

| Target | Method | Fires | Hit rate | Wilson 95% lower | C5 verdict |
|---|---|---|---|---|---|
| **L1** (needs 90%, lower bound ≥85%) | bucket, out-of-time | 92 | 92.4% | 85.1% | PASS (by 0.1pp) |
| | Platt, `p_cal ≥ 0.90` | 81 | 98.8% | 93.3% | PASS |
| | **isotonic, `p_cal ≥ 0.90`** | **117** | **94.0%** | **88.2%** | **PASS** |
| **L2** (needs 80%, lower bound ≥75%) | bucket, out-of-time | 83 | 77.1% | 67.0% | **FAIL** |
| | Platt, `p_cal ≥ 0.80` | 113 | 82.3% | 74.2% | **FAIL** (bound 74.2% < 75%) |
| | **isotonic, `p_cal ≥ 0.80`** | **96** | **87.5%** | **79.4%** | **PASS** |

Per-year bucket thresholds were unstable, which is part of why it underperforms: L1 picked
0.81 → 0.77 → 0.73 across 2024–2026, L2 picked 0.89 → 0.75 → 0.85. 2023 could not be scored
at all (no prior year to choose a threshold on).

**Isotonic dominates on both targets: it fires more often than the bucket rule (117 vs 92,
and 96 vs 83) *and* achieves a higher hit rate.** More bid opportunities and a better
promise, from the same model.

## Adopted (PLAN.md Stage 3 step 5)

| Target | Method | Firing rule | Raw-score equivalent |
|---|---|---|---|
| **L1** | **isotonic calibration** | fire iff calibrated p ≥ **0.90** | ≈ raw p 0.75 |
| **L2** | **isotonic calibration** | fire iff calibrated p ≥ **0.80** | ≈ raw p 0.74 |

Both conditions of step 5 are satisfied for isotonic on both targets: held-out Brier beats
raw (0.1579 vs 0.1596; 0.1586 vs 0.1624) **and** the threshold passes the C5 hit-rate,
Wilson and 20-fire gates on held-out data.

Isotonic is preferred over Platt even though Platt wins L2's Brier, because Brier is not the
decision criterion — the C5 gates are, and Platt's L2 threshold fails them (Wilson 74.2%
against the 75% floor). Judging the threshold, not just the average probability, is the
whole point of the C5 rule.

**A caveat that must appear in the live report.** Isotonic's probabilities remain
**optimistic in the top tail**: among rows it puts above the requirement it claims a mean of
98.5% but delivers 94.0% (L1), and claims 99.2% but delivers 87.5% (L2). The *threshold*
is trustworthy; the printed number is not a precise chance. Live output should show the
verdict and the validated hit rate for the firing band, not present the raw probability as
a literal probability.

## Deviations from plan
1. **The bucket rule is measured out-of-time**, which the plan did not specify. Without it the comparison was invalid (above). This is a methodology correction, not a change to decision C5 — C5's gates are applied exactly as written, just to honestly held-out data.
2. **Rule (b) is implemented as the literal reading:** fire when the calibrated probability reaches the requirement. My first implementation used the *mean* calibrated probability of the fired set, which is a looser and less natural reading; it made both calibrators appear to fail. Both readings are in the code history; the literal one is adopted.
3. 2023 is unscoreable for the bucket rule (no prior year), so its held-out sample is smaller than the calibrators'. Noted rather than papered over.
4. Calibration is fitted on **Set A only**, per Gate A decision A1. Set C (the standing challenger, A2) will need its own calibration if it is ever promoted.

## Open issues
1. **`reports/stage3_calibration.json` is stale** — it holds the first run, before the out-of-time correction. The script now in the repo implements the corrected method; regenerate with `python stage3_calibration.py`. The numbers in this report come from the verified direct computation, not from that file.
2. Held-out n is 260 with roughly 100 firing rows, so the Wilson bounds are wide. L1's bucket margin (85.1% against an 85.0% floor) is inside noise either way — another reason to prefer isotonic, which clears the floor by 3.2pp.
3. When the three decision-point models arrive (Stage 5, decision C5), each needs its own calibrator and threshold. The isotonic machinery here applies unchanged.
4. Isotonic cannot extrapolate beyond the probability range it was fitted on; as new years arrive its top bin should be watched.

# Stage 2 — Model L feature comparison → GATE A

**Status:** AWAITING_USER (Gate A). All four candidate sets were fitted for both targets on
an identical row set, with walk-forward validation, pooled-AUC half-life selection and the
section-5 threshold rule. A decision is needed before Stage 3.

## What was done
- Built `market_heat.py`: mean listing gain of mainboard IPOs that **listed** before this IPO's bidding opened (30d → 60d → expanding median), leak-free by construction.
- Fitted Sets A/B/C/D × L1/L2 on the same 616 mainboard IPOs; 298 out-of-fold predictions per combination, saved to `reports/oof/` (Stage 3's input).
- Implemented two agreed decisions that the framework was not yet following: half-life by **pooled** AUC, and the **section-5 threshold rule** (hit rate + Wilson bound within 5pp + ≥20 fires).
- Added a **paired bootstrap** (3,000 resamples on identical rows) so set differences are judged against sampling noise rather than eyeballed.

## Key numbers

| | L1 pooled AUC | L1 Gini | L1 threshold → fires / hit rate | L2 pooled AUC | L2 Gini | L2 threshold → fires / hit rate | max VIF |
|---|---|---|---|---|---|---|---|
| **A** Total + size | 0.8084 | 0.617 | 0.75 → 47.3% / **91.5%** | **0.8809** | **0.762** | 0.85 → 35.9% / **84.1%** | **1.0** |
| **B** QIB+HNI+RII + size | 0.7980 | 0.596 | 0.75 → 48.0% / 90.9% | 0.8721 | 0.744 | 0.85 → 35.6% / 84.9% | 5.3 |
| **C** A + market heat | **0.8137** | **0.627** | 0.76 → **52.0%** / 91.0% | 0.8755 | 0.751 | 0.91 → 32.9% / 84.7% | 1.1 |
| **D** B + market heat | 0.8098 | 0.620 | 0.80 → 49.7% / 91.2% | 0.8718 | 0.744 | 0.89 → 36.6% / 83.5% | 5.3 |

- n = 616 rows (L1 positive rate 68.2%, L2 43.7%); 298 out-of-fold predictions; test years **2022–2026**.
- **Half-life 2 years wins for all 8 combinations**, monotonically (2 > 3 > 5 > 8 > none). Effective n 323 of 616.
- **Every subscription coefficient is positive in every set** — the plan's sign requirement is met.
- **All four sets clear both hit-rate requirements.** L1 90% and L2 80% are achievable; the question is only which set.

### Per-year AUC (walk-forward)

| Set | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| L1 A | 0.699 | 0.804 | 0.833 | 0.847 | **0.448** |
| L1 B | 0.702 | 0.790 | 0.820 | 0.829 | **0.406** |
| L1 C | 0.702 | 0.804 | 0.863 | 0.839 | **0.521** |
| L1 D | 0.715 | 0.792 | 0.855 | 0.831 | **0.479** |
| L2 A | 0.905 | 0.868 | 0.887 | 0.868 | 0.863 |
| L2 B | 0.905 | 0.844 | 0.880 | 0.858 | 0.843 |
| L2 C | 0.911 | 0.891 | 0.901 | 0.861 | 0.863 |
| L2 D | 0.917 | 0.875 | 0.883 | 0.851 | 0.843 |

**L1's 2026 fold collapses to near-random in every set** (n = 20, 40% positive rate — an unusually cold year). L2 is stable everywhere (0.84–0.92). This is exactly why the plan mandates pooled AUC: the mean of per-year AUCs would let that 20-row year swing the choice.

### Are the differences real? (paired bootstrap, 3,000 resamples, identical rows)

| Comparison | L1 difference (95% CI) | L2 difference (95% CI) |
|---|---|---|
| **A − B** | **+0.0103 [+0.0008, +0.0207]** ✅ excludes 0 | **+0.0088 [+0.0020, +0.0159]** ✅ excludes 0 |
| C − A | +0.0053 [−0.0097, +0.0196] | −0.0053 [−0.0165, +0.0053] |
| C − B | +0.0156 [−0.0025, +0.0330] | +0.0034 [−0.0106, +0.0178] |
| D − B | +0.0117 [−0.0035, +0.0266] | −0.0003 [−0.0116, +0.0111] |
| C − D | +0.0039 [−0.0050, +0.0133] | +0.0038 [−0.0054, +0.0127] |
| A − D | −0.0014 [−0.0167, +0.0137] | +0.0091 [−0.0019, +0.0201] |

**Only one difference is statistically reliable: Total (A) beats the category split (B), on both targets.** Every other gap — including whether market heat helps at all — sits inside sampling noise.

### Collinearity, and the VIF 83 problem

`PLAN.md` section 2 lists "Total vs QIB/HNI/RII collinearity (VIF 83) unresolved". **Stage 2 resolves it: no candidate set contains Total *and* the categories together**, which is what produced VIF 83. Within the sets:

| Set | VIF per feature |
|---|---|
| A | total 1.00, size 1.00 |
| B | qib 4.64, **hni 5.28**, rii 3.23, size 1.75 |
| C | total 1.08, size 1.02, heat 1.11 |
| D | qib 4.64, **hni 5.32**, rii 3.56, size 1.84, heat 1.20 |

B and D still breach the spec's limit of 5 (HNI ≈ 5.3), mildly. A and C are effectively orthogonal.

### Coefficient significance (HC-robust, standardised, unweighted)

| Set | Subscription terms | Issue size | Market heat |
|---|---|---|---|
| L1 A | total +1.49 (p<0.001) | −0.16 (p=0.105) | — |
| L1 B | qib +0.83 (p<0.001), hni +0.58 (p=0.011), **rii +0.13 (p=0.488)** | −0.23 (p=0.079) | — |
| L1 C | total +1.65 (p<0.001) | −0.09 (p=0.349) | **−0.44 (p<0.001)** |
| L1 D | qib +0.86 (p<0.001), hni +0.49 (p=0.033), rii +0.40 (p=0.066) | −0.13 (p=0.361) | **−0.42 (p<0.001)** |
| L2 A | total +1.95 (p<0.001) | −0.04 (p=0.723) | — |
| L2 B | qib +0.74 (p=0.001), hni +0.93 (p<0.001), rii +0.34 (p=0.064) | +0.02 (p=0.908) | — |
| L2 C | total +2.03 (p<0.001) | −0.02 (p=0.856) | −0.25 (p=0.024) |
| L2 D | qib +0.76 (p=0.001), hni +0.87 (p<0.001), rii +0.48 (p=0.019) | +0.07 (p=0.632) | −0.24 (p=0.038) |

Two findings worth stating plainly:

1. **Market heat's coefficient is negative and significant.** A hotter recent IPO market *lowers* P(listing gain), holding subscription fixed. That is the opposite of a naive momentum reading, but economically coherent: hot markets invite more aggressive pricing and heavier supply, so a given subscription level buys less of a pop. It is a real conditional effect — yet it does **not** produce a reliable AUC gain (see bootstrap). A significant coefficient and a better ranking are different things.
2. **Issue size is not an established contributor.** Its sign flips between the recency-weighted final fit (positive) and the unweighted HC Logit (negative), and it is insignificant in HC in all eight fits. It is kept because the plan specifies it, but no directional claim should be made about it.

## Deviations from plan
1. **Two agreed decisions were not yet implemented in the framework**, so I implemented them before comparing: half-life selection now uses **pooled** AUC (was the mean of per-year AUCs), and thresholds now use the **section-5 rule** (was "hit rate ≥ threshold", min 10 fires). Both are `PLAN.md` section 5 requirements. Consequence: **numbers are not comparable to the previous session's.** L1's headline moved 0.765 → 0.808 purely because pooled AUC replaced the mean of per-year AUCs — the same model, a different mandated statistic. Under the old rule L2's "≥80%" was reported as failing; under the correct rule L2 clears 80% comfortably at t = 0.85.
2. **5 rows dropped so all four sets see identical rows** (616, not 621): 4 IPOs from the first days of Jan 2010 have no prior listing from which to compute market heat, and Coffee Day Enterprises (Nov 2015) has no subscription data at all. Comparing sets on different samples would have confounded the result.
3. **The long-run-median fallback uses an expanding median, not the full-sample median.** The plan says "long-run median"; a full-sample median would leak future listing gains into early rows. 52 rows use this fallback, 97 use the widened 60-day window, 499 use the plain 30-day window.
4. **Added a paired bootstrap**, not requested by the plan. Without it, "Set C is best" would rest on a 0.005 AUC gap that the data cannot support.
5. **Out-of-fold predictions computed one combination at a time** (`stage2_oof.py`). Running all eight in one process exhausted this laptop's memory (7.9 GB total, 0.35 GB free) and pandas failed reading a 127 KB CSV. The saved predictions are also Stage 3's required input.

## Open issues
1. L1's 2026 fold is near-random in every set (n = 20). Worth revisiting once 2026 has more listings; it does not affect the pooled comparison much but it caps confidence in L1 for cold markets.
2. Market heat's cutoff is the recovered true open date for 313 rows and `listing date − 10 days` for 339. The fallback is an approximation; pre-2021 rows have no recovered open date (`CLAUDE.md`, known data defect).
3. `log_issue_size` is insignificant and sign-unstable (above). A future stage could test dropping it.
4. B and D exceed the VIF limit of 5 on HNI (≈5.3). If the category split is chosen, the spec's own rule says drop one of the offending pair.

---

# GATE A — decision needed

## The decision
**Which feature set does Model L use for L1 and L2?** Stage 3 (calibration and final
thresholds) and Stage 5 (the final-day forecaster) both depend on this answer.

## Options

| Option | What it costs operationally | Evidence |
|---|---|---|
| **A — Total + log size** | Forecaster predicts **one** number: final-day Total | Only set with a statistically reliable edge (beats B on both targets). Best L2 (0.8809). VIF ≈ 1. Most generous L2 threshold: 0.85 → fires 35.9% at 84.1% hit rate |
| **B — QIB + HNI + RII + log size** | Forecaster predicts **three** numbers | Reliably the **worst** on both targets. VIF 5.3 on HNI. RII insignificant for L1 (p=0.49) |
| **C — A + market heat** | One number; heat needs **no** forecast (known before bidding) | Best L1 point estimate (0.8137) and fires most at the 90% promise: **52.0% vs 47.3%**. Not statistically separable from A. Slightly worse L2 |
| **D — B + market heat** | Three numbers | No reliable gain over B or A. Highest VIF |

## The forecaster consequence (as the plan requires this stated)
Choosing **B or D commits Stage 5 to forecasting three final-day categories instead of
one**, and **QIB is the hardest of the three**: institutions typically place most of their
bids on the final day, so the day-before signal for QIB is weakest exactly where the
forecast matters most. Each category forecast carries its own error, and those errors feed
Model L together. Set A or C needs only a Total forecast — one error distribution, and
Total is the category that moves earliest and most smoothly.

**You have said you lean towards the category split.** The evidence does not support it:
Set B is the only set that is *reliably beaten*, on both targets, and it also carries the
collinearity problem and three times the forecasting burden. If the appeal of the split is
diagnostic (seeing who is bidding), that can be reported alongside the model's output
without putting the categories in the model.

## Recommendation
**Set A for both L1 and L2.** It is the only set with a statistically established
advantage, the simplest to forecast, effectively free of collinearity, and it gives L2 the
best discrimination and the most generous threshold.

**One upgrade worth considering: Set C for L1 only.** It fires on 52.0% of IPOs versus
47.3% at the same 90% promise — meaningfully more opportunities — and market heat requires
no forecast because it is known before bidding opens. The honest caveat is that C's edge
over A is **not** statistically established (95% CI −0.010 to +0.020), and heat's effect is
a regime-dependent one that could weaken. For L2, heat slightly hurts and tightens the
threshold to 0.91, so L2 should stay on Set A either way.

Reply in the form:
- `Gate A decision: Set A for both targets`, or
- `Gate A decision: Set C for L1, Set A for L2`, or
- any other choice, and I will record it verbatim in `DECISIONS.md` and continue.

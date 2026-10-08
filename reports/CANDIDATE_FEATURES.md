# Three candidate features — Priority 4

Added **to** `log1p(Total)`, walk-forward out-of-sample, pooled AUC, and on **identical rows** for champion and challenger. Same discipline as the nine literature candidates already rejected (H2).

## The bar for adoption

H17 removed the calibrated probability from the decision path — the live rule is a plain threshold on subscription. **A two-variable model cannot be expressed as one threshold on subscription**, so adopting any candidate means putting a probability back into the decision. That is the thing H17 was ratified to remove, and it has already produced two opposite failures. So the bar is out-of-sample **delivery**, not AUC.

## Coverage

| candidate | rows with a value |
|---|---|
| `offer_pct_of_cap` | 329 |
| `non_promoter_post_pct` | 456 |
| `nifty_close_to_listing_pct` | 471 |

## Results

| target | candidate | rows | champion AUC | with cand. | ΔAUC | champion delivered | with cand. | Δ (pp) | Δ fires | one hit (pp) | improves delivery? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 | `offer_pct_of_cap` | 326 | 0.8054 | 0.8344 | **+0.0290** | 91.5% (130) | 91.2% (137) | -0.30 | +7 | 0.73 (Δ below this) | no |
| L1 | `non_promoter_post_pct` | 453 | 0.8246 | 0.8174 | **-0.0072** | 90.6% (160) | 90.6% (160) | +0.00 | +0 | 0.62 (Δ below this) | no |
| L1 | `nifty_close_to_listing_pct` | 468 | 0.8109 | 0.8172 | **+0.0063** | 91.1% (157) | 90.7% (162) | -0.34 | +5 | 0.62 (Δ below this) | no |
| L2 | `offer_pct_of_cap` | 326 | 0.8688 | 0.8864 | **+0.0176** | 84.0% (94) | 84.2% (101) | +0.12 | +7 | 0.99 (Δ below this) | no |
| L2 | `non_promoter_post_pct` | 453 | 0.8793 | 0.8772 | **-0.0021** | 84.2% (114) | 84.4% (115) | +0.14 | +1 | 0.87 (Δ below this) | no |
| L2 | `nifty_close_to_listing_pct` | 468 | 0.8721 | 0.8722 | **+0.0001** | 84.4% (115) | 83.6% (122) | -0.74 | +7 | 0.82 (Δ below this) | no |

## What this means

**None of the three is adopted.** 0 candidate-target pairs clear the bar.

The largest AUC gain anywhere is `offer_pct_of_cap` on L1, **+0.0290** — and its delivered rate still goes -0.30pp, which is inside one hit (0.73pp). An AUC gain that does not convert into delivery is not worth putting a probability back into the decision path.

`non_promoter_post_pct` makes pooled AUC **worse** on both targets, and on L1 leaves the fire count and the delivered rate completely unchanged — the fit finds nothing in it at all. The two free-float readings behaving so differently is itself the answer: what little signal exists is in how much of the company was *sold*, not in how much is nominally unheld.

### The diagnostic is the most interesting negative

The Nifty move between issue close and listing adds **+0.0063** on L1 and **+0.0001** on L2 — essentially nothing, on 468 IPOs with a real parsed close date.

That is worth more than its size suggests. If a listing gain were mostly market drift over the three-to-six-day gap, this would be the variable that showed it, and it does not. **The listing gain is issue-specific, not a market ride.** It also agrees with Priority 3b, where the delivered rate ranked only +0.206 against the year's index return. Two independent routes to the same conclusion: when a year under-delivers, the index is not where to look for the reason.


## Not tested

**`anchor_mf_share`** — NOT TESTED - no data. data/chittorgarh_anchor_lockin.csv is the pre-issue LOCK-IN table, not the anchor book: 3,127 rows across 674 IPOs, zero names containing 'mutual fund' or 'MF', categories of Promoter/Other/Corporate/SME/Mainboard, and names that are overwhelmingly individuals. Deriving an MF share from name patterns over individual shareholders would be the plausibility inference H8 forbids. To test it, the anchor allocation table has to be collected first - it is a different block on the same Chittorgarh page.


# Email backtest — last 12 months

What the daily email **would have said** for every IPO that closed between 2025-05-27 and 2026-05-08, and what then happened.

Rule under test (H17, ratified): **L1 bids at Total ≥ 28.39x, L2 at ≥ 54.02x.** Verdicts come from the live `score_l.predict_live()`, not a reimplementation.

`113` IPOs. Labels: 112 from exchange bhavcopy (H18), 1 from master Listing Gain.

> **This is optimistic about how often the email would have fired.** The email scores the ~15:00 figure; what is on record historically is the FINAL figure, which is higher. So treat the bid COUNT as an upper bound. The hit rate among those bids is the honest number, because it conditions on the same rows either way.

## Summary

| | L1 (gain > 0%) | L2 (gain > 10%) |
|---|---|---|
| Promise | 90% | 80% |
| Fires above | 28.39x | 54.02x |
| **BIDs** | **49** | **36** |
| of which hit | 42 | 26 |
| **hit rate among BIDs** | **85.7%** | **72.2%** |
| said no | 64 | 77 |
| winners it said no to | 27 | 13 |
| base rate (all IPOs) | 61.1% | 34.5% |
| verdict accuracy | 69.9% | 79.6% |

## L1 — any listing gain

### Backed and it fell

| date | company | Total | gain |
|---|---|---|---|
| 2026-03-02 | Shree Ram Twistex Ltd. | 43.66x | **-34.6%** |
| 2026-01-21 | Amagi Media Labs Ltd. | 30.22x | **-11.9%** |
| 2025-11-07 | Studds Accessories Ltd. | 73.25x | **-3.4%** |
| 2025-11-21 | Capillary Technologies India Ltd. | 52.95x | **-0.9%** |
| 2025-06-04 | Scoda Tubes Limited | 53.78x | **+0.0%** |
| 2025-08-06 | M & B Engineering Ltd | 36.20x | **+0.0%** |
| 2025-09-17 | Dev Accelerator Ltd. | 63.97x | **+0.0%** |

### Said no and it soared

| date | company | Total | gain |
|---|---|---|---|
| 2025-11-18 | Physicswallah Ltd | 1.81x | **+33.0%** |
| 2025-07-01 | Ellenbarrie Industrial Gases Limited | 22.19x | **+21.5%** |
| 2025-10-01 | Jain Resource Recycling Ltd. | 15.90x | **+14.2%** |
| 2026-03-11 | SEDEMAC Mechatronics Ltd. | 2.68x | **+13.5%** |
| 2025-08-14 | All Time Plastics Ltd. | 8.34x | **+13.2%** |
| 2025-07-02 | HDB Financial Services Limited | 16.69x | **+12.8%** |
| 2025-11-12 | Billionbrains Garage Ventures Ltd. | 17.60x | **+12.0%** |
| 2026-05-08 | OnEMI Technology Solutions Ltd. | 9.50x | **+11.1%** |

## L2 — gain above 10%

### Backed and it fell

| date | company | Total | gain |
|---|---|---|---|
| 2025-11-07 | Studds Accessories Ltd. | 73.25x | **-3.4%** |
| 2025-09-17 | Dev Accelerator Ltd. | 63.97x | **+0.0%** |
| 2025-08-26 | Vikram Solar Ltd | 54.63x | **+1.8%** |
| 2025-09-30 | Seshaasai Technologies Ltd. | 68.13x | **+2.1%** |
| 2025-10-03 | Jinkushal Industries Ltd. | 65.10x | **+3.3%** |
| 2025-09-24 | VMS TMT Ltd | 102.26x | **+6.0%** |
| 2025-08-26 | Shreeji Shipping Global Ltd. | 58.10x | **+7.1%** |
| 2025-09-09 | Amanta Healthcare Ltd. | 82.61x | **+7.1%** |

### Said no and it soared

| date | company | Total | gain |
|---|---|---|---|
| 2025-07-02 | Sambhv Steel Tubes Limited | 28.46x | **+34.1%** |
| 2025-11-18 | Physicswallah Ltd | 1.81x | **+33.0%** |
| 2025-07-01 | Ellenbarrie Industrial Gases Limited | 22.19x | **+21.5%** |
| 2025-12-19 | ICICI Prudential Asset Management Co.Ltd. | 39.17x | **+20.1%** |
| 2025-10-01 | Jain Resource Recycling Ltd. | 15.90x | **+14.2%** |
| 2026-03-11 | SEDEMAC Mechatronics Ltd. | 2.68x | **+13.5%** |
| 2025-08-14 | All Time Plastics Ltd. | 8.34x | **+13.2%** |
| 2025-07-02 | HDB Financial Services Limited | 16.69x | **+12.8%** |

# Did the world change, or did the model? — Priority 3b

Delivered hit rate per listing year at the **ratified** thresholds (L1 >= 28.39x, L2 >= 54.02x), against what the market was doing that year. 620 IPOs, 2010-2026.

> **What this does not measure.** FII/DII flows. NSE's api/fiidiiTradeReact returns the current day only; ?date= and ?from=&to= are accepted with HTTP 200 and ignored. The historical FII/FPI/DII archive page is JS-rendered and exposes no static file links, and the two report-API shapes tried returned HTTP 503 and {"error": "file is unavailable"}. No permitted historical series was reached, so none is reported. Nothing here is a stand-in for it.

## Year by year

| year | IPOs | median Total | Nifty TRI yr | Nifty 5d to listing (median) | L1 fires | L1 delivered | L2 fires | L2 delivered |
|---|---|---|---|---|---|---|---|---|
| 2010 | 67 | 7.48x | +19.2% | +0.5% | 15 | 100.0% | 4 | 100.0% |
| 2011 | 37 | 1.68x | -23.8% | -0.8% | 1 | 100.0% | 0 | — |
| 2012 | 11 | 2.54x | +29.4% | -0.1% | 2 | 100.0% | 1 | 100.0% |
| 2013 | 3 | 1.65x | +7.2% | +1.0% | 0 | — | 0 | — |
| 2014 | 5 | 38.06x | +33.0% | +0.0% | 3 | 100.0% | 2 | 100.0% |
| 2015 | 19 | 2.04x | -3.0% | +0.4% | 5 | 80.0% | 1 | 100.0% |
| 2016 | 27 | 10.80x | +4.2% | +0.3% | 10 | 100.0% | 7 | 85.7% |
| 2017 | 36 | 8.24x | +30.3% | +0.4% | 16 | 100.0% | 11 | 81.8% |
| 2018 | 24 | 5.12x | +5.6% | +0.4% | 4 | 100.0% | 4 | 75.0% |
| 2019 | 16 | 4.54x | +13.0% | +0.4% | 6 | 100.0% | 4 | 100.0% |
| 2020 | 14 | 60.14x | +16.0% | +0.5% | 8 | 100.0% | 7 | 100.0% |
| 2021 | 63 | 29.04x | +25.3% | +0.1% | 32 | 96.9% | 23 | 91.3% |
| 2022 | 38 | 3.08x | +5.7% | +0.3% | 8 | 100.0% | 3 | 100.0% |
| 2023 | 58 | 33.91x | +21.3% | +0.3% | 32 | 96.9% | 21 | 95.2% |
| 2024 | 80 | 39.59x | +10.0% | +0.2% | 45 | 93.3% | 37 | 89.2% |
| 2025 | 102 | 29.37x | +11.4% | +0.1% | 52 | 90.4% | 41 | 75.6% |
| 2026 | 20 | 2.67x | -10.7% | -1.0% | 3 | 33.3% | 1 | 100.0% |

## Does the delivered rate track the market?

Spearman rank correlation, years with at least 10 fires only — a 100% rate on two fires is noise, and including it is how a spurious correlation gets manufactured.

| | L1 | L2 |
|---|---|---|
| Nifty TRI return that year | 0.206 | 0.1 |
| Nifty move, 5d before listing | 0.805 | 0.3 |
| IPO supply that year | -0.767 | -0.4 |
| median subscription that year | -0.823 | 0.3 |

## What this says about 2025

2025 is the year under suspicion, and it was **not** a weak market. The Nifty 50 TRI returned **+11.4%** that year, and the median Nifty move in the five days before each listing was **+0.05%** — flat, not falling.

What was unusual about 2025 is **supply**: 102 IPOs, the largest year in the dataset, at a median subscription of 29.37x.

Across the years thick enough to count, L1's delivered rate ranks **-0.767 against IPO supply** and **0.805 against the pre-listing Nifty move**, but only **0.206 against the year's index return**. So the annual market direction is not where the signal is. With only 7 usable years for L1 and 5 for L2, none of this is significant on its own — L2's figures in particular are noise at that sample size and should not be read as a pattern.

**The FII hypothesis is neither confirmed nor refuted here**, because no permitted historical FII series was reachable. What can be said is that the two market measures that *were* available do not show 2025 as a bad tape, so if FII outflows were heavy that year they did not show up in the index level or in the window where a listing gain is actually realised.


L1 years used: [2010, 2016, 2017, 2021, 2023, 2024, 2025]

L2 years used: [2017, 2021, 2023, 2024, 2025]


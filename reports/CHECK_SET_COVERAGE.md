# Check-set transcription: what ground truth exists

One row per document. `x/5` counts the five target fields for which a value was read by hand from a numbered page, with the line quoted. `derived` counts: a figure the document does not print but that its own components or ratios fix exactly is still ground truth, and is marked as derived.

| RHP | year | industry | five fields | which | notes |
|---|---|---|---|---|---|
| Polycab India Ltd | 2019 | Capital Goods | **5/5** | net worth*, tax, finance, D&A, pre-issue shares | complete |
| Prince Pipes and Fittings Ltd | 2019 | Capital Goods | **4/5** | net worth, tax, finance, D&A | missing: pre-issue shares |
| Vishwaraj Sugar Industries Ltd | 2019 | Fast Moving Consumer Goods | **1/5** | pre-issue shares | missing: net worth, tax, finance, D&A |
| Computer Age Management Services Ltd | 2020 | Financial Services | **2/5** | net worth, pre-issue shares | missing: tax, finance, D&A |
| Likhitha Infrastructure Ltd | 2020 | Construction | **3/5** | net worth, finance, pre-issue shares | missing: tax, D&A |
| Route Mobile Ltd | 2020 | Telecommunication | **0/5** | - | not transcribed |
| Antony Waste Handling Cell Ltd | 2021 | Utilities | **0/5** | - | not transcribed |
| CarTrade Tech Limited | 2021 | Consumer Services | **0/5** | - | not transcribed |
| Craftsman Automation Limited | 2021 | Automobile and Auto Components | **5/5** | net worth*, tax*, finance, D&A, pre-issue shares | complete |
| AGS Transact Technologies Limited | 2022 | Financial Services | **0/5** | - | not transcribed |
| Delhivery Limited | 2022 | Services | **0/5** | - | not transcribed |
| Global Health Limited | 2022 | Healthcare | **5/5** | net worth, tax*, finance, D&A, pre-issue shares | complete |
| Cello World Limited | 2023 | Consumer Durables | **0/5** | - | not transcribed |
| IRM Energy Limited | 2023 | Oil, Gas & Consumable Fuels | **0/5** | - | not transcribed |
| Signature Global India Limited | 2023 | Realty | **0/5** | - | not transcribed |
| ACME Solar Holdings Limited | 2024 | Power | **0/5** | - | not transcribed |
| Bansal Wire Industries Limited | 2024 | Metals & Mining | **0/5** | - | not transcribed |
| Godavari Biorefineries Limited | 2024 | Chemicals | **0/5** | - | not transcribed |
| Borana Weaves Limited | 2025 | Textiles | **0/5** | - | not transcribed |
| GNG Electronics Limited | 2025 | Information Technology | **0/5** | - | not transcribed |

`*` = derived rather than printed.

**3 of 20 documents complete; 7 transcribed at all; 25 of 100 field-slots filled.**

The 13 untranscribed documents are the gap between this and Task 3 step 1, which asked for all 15 remaining. Seven were done; the readers were built and measured on those seven instead of transcribing the rest, because a reader that fails on seven documents fails on twenty and the diagnosis does not need the other thirteen.

## What the transcription itself turned up

| finding | documents |
|---|---|
| **No total tax expense is printed** - only the components, and `tax = profit before tax - profit after tax` reproduces them exactly | Craftsman (168.35 + (5.18) = 163.17 = 573.90 - 410.73), Medanta (856.62 + (13.03) = 843.59 = 2,805.61 - 1,962.02) |
| Net worth is printed as its own `Total Equity` line, so it is read rather than cross-footed | Prince Pipes, Likhitha, Medanta, Route Mobile |
| Net worth is NOT the balance sheet's total equity, and only the RoNW line says so | Craftsman, 7.7% apart |
| The share count behind a stated NAV is the PERIOD-END count | Prince Pipes (-4.5% against the RHP-date count), Medanta (+0.03%) |
| The unit is settled by arithmetic, not by finding the word | Likhitha: 6,995.58 lakh / 14,625,000 = Rs 47.8330 against a stated NAV of 47.83 |
| A pure offer for sale states the post-issue count | CAMS, 48,786,800 before and after |
| A fixed-share-count fresh issue states it too | Vishwaraj (3,000,000 fresh), Likhitha (5,100,000 fresh) |
| A derivation left as `[*]` on one page is STATED on another | Medanta's fresh issue: `[*]` on p125, Rs 5,000 million on p92 - which makes Task 5's derivation exact |


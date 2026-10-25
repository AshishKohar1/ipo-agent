# H48 hand-validation on the transcribed check set

Every input below was read by hand from a numbered page and is quoted in `reports/H48_VALIDATION.csv`. Issue expenses are ignored throughout, which OVERSTATES post-issue book value and understates P/B; every row says so.

## Results

| RHP | post shares | post NAV | promoter pre % | promoter post % | pages | check |
|---|---|---|---|---|---|---|
| Polycab India Ltd (2019) | 148,640,782 | Rs 184.97 | 66.32% | 57.41% | pre-issue shares and fresh issue p102 | MATCH |
| Craftsman Automation Limited (2021) | 21,128,311 | Rs 409.97 | 52.83% | 49.70% | pre-issue shares and fresh issue p71 | MATCH |
| Global Health Limited (Medanta) (2022) | 268,184,882 | Rs 78.90 | 35.0% | 33.08% | pre-issue shares p125 and p92 | MATCH |
| Computer Age Management Services Ltd (2020) | 48,786,800 | Rs 108.27 | 30.98% | 30.98% | pre- AND post-issue shares p60 | MATCH |
| Vishwaraj Sugar Industries Ltd (2019) | 37,556,000 | Rs 61.10 | 33.96% | 30.18% | pre- and post-issue shares p70 | MATCH |
| Likhitha Infrastructure Ltd (2020) | 19,725,000 | Rs 66.49 | 97.46% | 72.26% | pre-issue shares and fresh issue p71 (header: 'Rs. in Lakhs except the share data') | MATCH |
| Prince Pipes and Fittings Ltd (2019) | 110,025,760 | Rs 61.61 | 88.08% | 64.07% | pre-issue shares and fresh issue p81 | MATCH |

## Branch taken, per document

| RHP | branch |
|---|---|
| Polycab India Ltd | fresh issue stated as a RUPEE amount - needs the price. The promoters ARE selling, so the promoter percentage needs their own OFS share count, not the offer's total |
| Craftsman Automation Limited | fresh issue stated as a RUPEE amount - needs the price |
| Global Health Limited (Medanta) | fresh issue stated as a RUPEE amount - needs the price. The amount IS stated here (Rs 5,000 million on p92), which validates the derivation used on it in Task 5 exactly |
| Computer Age Management Services Ltd | PURE OFFER FOR SALE - no shares created, so the RHP states the post-issue count, and the NAV does not move either |
| Vishwaraj Sugar Industries Ltd | fresh issue stated as a fixed SHARE COUNT (3,000,000) - knowable before pricing, so the RHP states the post-issue total |
| Likhitha Infrastructure Ltd | fresh issue stated as a fixed SHARE COUNT (5,100,000), 100% fresh - no offer for sale |
| Prince Pipes and Fittings Ltd | fresh issue AND offer for sale both stated as RUPEE amounts - the promoter's own OFS share count is price-dependent too |

## Cross-checks in full

| RHP | checks |
|---|---|
| Polycab India Ltd | net worth / stated NAV = 141,196,767 shares, -0.01% vs the pre-issue count | promoter pre 66.32% vs stated 66.32%: MATCH |
| Craftsman Automation Limited | net worth / stated NAV = 20,121,600 shares, +0.00% vs the pre-issue count | promoter pre 52.83% vs stated 52.83%: MATCH |
| Global Health Limited (Medanta) | net worth / stated NAV = 253,213,883 shares, -0.04% vs the pre-issue count | promoter pre 35.03% vs stated 35.0%: MATCH |
| Computer Age Management Services Ltd | post shares vs STATED 48,786,800: MATCH | post NAV vs STATED 108.27: MATCH | promoter post vs STATED 30.98%: MATCH | net worth / stated NAV = 48,785,167 shares, -0.00% vs the pre-issue count | promoter pre 30.98% vs stated 30.98%: MATCH |
| Vishwaraj Sugar Industries Ltd | post shares vs STATED 37,556,000: MATCH | net worth / stated NAV = 34,556,000 shares, +0.00% vs the pre-issue count | promoter pre 33.96% vs stated 33.96%: MATCH |
| Likhitha Infrastructure Ltd | net worth / stated NAV = 14,625,925 shares, +0.01% vs the pre-issue count | promoter pre 97.46% vs stated 97.46%: MATCH |
| Prince Pipes and Fittings Ltd | net worth / stated NAV = 91,617,987 shares, -4.55% vs the pre-issue count | promoter pre 88.08% vs stated 88.08%: MATCH |

## Which net worth was used, and why

| RHP | basis |
|---|---|
| Polycab India Ltd | stated net worth, Rs 23,493.73 million at 31 Mar 2018 |
| Craftsman Automation Limited | implied by the stated NAV (355.93 x 20,121,600 = Rs 7,161.88 million); CORROBORATED by the stated RoNW of 7.07% on a profit of Rs 506.60 million, which needs ~Rs 7,165 million. The balance sheet's own total equity sub-total of Rs 7,716.11 million would give RoNW 6.57% and is NOT the net worth this RHP uses |
| Global Health Limited (Medanta) | total equity at 31 Mar 2022, Rs 16,160.11 million (p97). Cross-foots to the stated NAV within 0.03% on the PERIOD-END share count of 253,225,000 (share capital 506.45 / face value 2), not the RHP-date count of 253,303,930 |
| Computer Age Management Services Ltd | stated net worth Rs 5,281.97 million at 30 Jun 2020 (p11). Cross-foots to the stated NAV of 108.27 on 48.785 million shares, exact |
| Vishwaraj Sugar Industries Ltd | implied by the stated NAV at 31 Mar 2019 (61.20 x 34,556,000 = Rs 2,114.83 million). The RHP defines net worth as share capital + securities premium + general reserve + surplus, EXCLUDING preference capital and revaluation reserve (p110-111) |
| Likhitha Infrastructure Ltd | stated Total Equity Rs 6,995.58 LAKH at 31 Mar 2020. The unit was unconfirmed until now and is settled by the cross-check: 699,558,000 / 14,625,000 = Rs 47.8330, against a stated NAV of 47.83 |
| Prince Pipes and Fittings Ltd | stated Total Equity Rs 4,278.56 million at 30 Jun 2019. Net worth is DEFINED on p110 as equity share capital + reserves and surplus under section 2(57), so the cross-foot is valid. It reproduces the stated NAV on 91,617,988 shares - the PERIOD-END count, 4.5% below the RHP-date count of 95,980,816 |

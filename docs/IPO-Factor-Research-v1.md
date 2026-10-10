# Indian IPO Factor Model — Research Base v1.0

Evidence synthesis for the IPO analyst agent. Sources: 8 uploaded papers (incl. the SEBI
regulator study), 5 accessible practitioner links, plus literature traced from the reference
lists, and original analysis of the 1,082-row NSE past-issues file.

---

## PART 0 — DATA REALITY CHECK (read this before the model design)

### 0.1 The Excel does not contain what the plan assumes

I audited `IPO-PastIssue-17-09-2021-to-17-09-2026.xlsx` column by column. It has **8 columns
and only 8**: Company Name, Security Type, Issue Price, Symbol, Issue Start Date, Issue End
Date, Price Range, Date of Listing.

**These 8 columns are identical for a 2021 row and a 2026 row.** There is no extra information
for Jan-2025 onward. Specifically, the file contains:

- ❌ No listing price / listing-day close → **the target variable does not exist**
- ❌ No subscription data (QIB / NII / Retail)
- ❌ No GMP
- ❌ No issue size, no fresh-vs-OFS split
- ❌ No financials, no promoter holding, no sector
- ❌ No current market price

**Consequence:** the 70/30 train-test plan cannot be executed today. Not because the split is
wrong — it's the right design — but because there is no y to regress on and only ~6 usable x's.
This is a data-acquisition problem, not a modelling problem, and Part 5 is the fix.

### 0.2 Data quality issues found

| Issue | Count | Action |
|---|---|---|
| Exact duplicate rows | 77 | Dropped |
| Non-equity instruments (DEBT, InvIT, N0, Z9, RR, IV…) | 77 | Dropped — these are NCDs/InvITs/REITs, not IPOs |
| Issue price = "-" (not yet priced) | 36 | Retained, flagged as pending |
| **Clean equity IPO universe** | **928** | 909 listed, 19 pending |

Segment split of the clean universe: 391 mainboard, 537 SME. Note the SME majority — any model
trained on the pooled file will be an SME model wearing a mainboard costume unless you stratify.

### 0.3 What the spine *can* already produce

Six features are derivable from the raw file alone, and I built them:

| Feature | Literature basis | Status in modern regime |
|---|---|---|
| `f_ipos_prev_30d` (IPOs opening in trailing 30d) | Ritter (1991) windows-of-opportunity; Karki & Jha | **LIVE** — range 2 to 43, high variance |
| `f_band_width_pct` (cap−floor)/floor | Beatty & Ritter (1985) ex-ante uncertainty | **WEAK** — clustered at 5.4% (SEBI's 20% band cap compresses it) |
| `f_is_fixed_price` | Bansal & Khanna (2012) | **SME-ONLY** — 90% modal; mainboard is 99% book-built |
| `f_listing_delay_days` | Sehgal & Sinha (2013), significant +ve, t=1.74 | **DEAD** — see 0.4 |
| `f_priced_at_cap` | Sehgal & Sinha D1/D2 offer-price dummy | **DEAD** — see 0.4 |
| `f_bid_window_days`, `f_segment`, `f_year/quarter` | control variables | Live as controls |

### 0.4 Original finding: regulation has killed two of the literature's variables

This is not in any of the uploaded papers, and it matters for the agent's design.

**Listing delay** — Sehgal & Sinha (2013) found listing delay significantly and positively
predicts underpricing (longer wait → more uncertainty → more underpricing demanded). In this
dataset the median listing delay collapsed:

| Year | Median listing delay (days) |
|---|---|
| 2021 | 8 |
| 2022 | 8 |
| 2023 | 8 |
| 2024 | **5** |
| 2025 | **5** |
| 2026 | **5** |

SEBI's T+3 listing mandate compressed this to a near-constant. A variable with no variance
cannot predict anything. **Drop it.**

**Priced-at-cap dummy** — Sehgal & Sinha used a dummy for whether the final price lands near the
top vs bottom of the band. In 2024-26, **98.7% of book-built Indian IPOs price at the cap**
(2021: 100%, 2022: 86%, 2026: 100%). The variable is effectively a constant. **Drop it.**

**Design implication for the agent:** any factor sourced from pre-2020 literature must pass a
variance check against recent data before it enters the model. I've built that check into the
spine script. Several more 2013-era variables will likely fail it once you have the full dataset.

---

## PART 1 — MASTER FACTOR LIST

Organised by the layer of the problem each factor addresses. Weights in Part 3.

### A. Issue Structure & Mechanics

- **Total subscription multiple** — the single strongest listing-day predictor in the evidence
  base. Sehgal & Sinha: t = 11.69, by a wide margin the largest t-statistic of any variable in
  their 9-factor model. SEBI's own study gives the calibration table (Part 4.1).
- **QIB subscription specifically** — institutional validation. Weighted separately from headline
  subscription because they measure different things (see contradiction C2).
- **NII subscription and the NII/QIB ratio** — leverage-funded demand; SEBI found NII exit 63.3%
  within a week vs retail 42.7%.
- **Retail subscription** — weakest standalone predictor; useful mainly as a rejection signal
  (near-zero retail = market has voted).
- **Fresh issue % vs OFS %** — Viswan (2026), n=236: full-OFS IPOs averaged **20.61%**
  underpricing, 100%-fresh averaged **8.04%**, mixed **16.59%** (ANOVA sig. at 10%). Sign flips
  by horizon — see contradiction C1.
- **Issue size (gross proceeds)** — Sehgal & Sinha: negatively related to underpricing (t = −4.79).
  Larger issues are more fairly priced. Also SEBI: exits are far higher in sub-₹1,000cr issues.
- **Number of stated uses of proceeds** — Beatty & Ritter (1985) ex-ante uncertainty proxy;
  Sehgal & Sinha confirm positive (t = 1.81). *More* stated uses = vaguer plan = more
  underpricing. **We never counted this. It is a free variable sitting in every RHP.**
- **"General corporate purposes" share of proceeds** — SEBI caps at 25%; approaching the cap is a
  vagueness flag (SMC).
- **Fixed-price vs book-built** — book-built are less underpriced (Bansal & Khanna 2012;
  Ranjan & Madhusoodanan 2004). Now only discriminating within SME.
- **Price band width %** — ex-ante uncertainty proxy. Weak now but retain as control.
- **Anchor book: size, quality, and lock-in expiry date** — SMC flags this; SEBI data shows
  anchors are the stickiest holders (QIB ex-anchor exited 65.4% in week 1, anchors far less).
  Anchor lock-in expiry is a *dated future supply event* — the agent should calendar it.
- **Insider retention ratio (post-IPO promoter holding)** — Sehgal & Sinha include it (IRR);
  practitioner sources treat it as a skin-in-the-game signal.

### B. Firm Fundamentals

- Revenue 3-yr CAGR and its *consistency* (one-year spikes flagged — INDmoney)
- PAT growth and margin trend; **margin expansion immediately pre-IPO is an earnings-quality flag**
- **Operating cash flow vs net profit** — INDmoney's most-underrated check; OCF ≥ PAT is healthy
- RoE / RoNW / RoCE — *level and trend*; declining RoCE off a small base is the classic
  small-company scaling illusion
- Debt-to-equity, and the *direction* of change in the 6 months before filing
- NAV / book value per share — Prosad & Singh (2023) found NAV and ROA significantly determine
  the offer price itself
- Working capital cycle: receivable days, inventory days, payable days (SMC)
- Contingent liabilities as % of net worth
- Customer concentration (top-10 %), geographic concentration
- Related-party transactions as % of revenue
- Age of company — **note: Ghosh (2002) found age does NOT explain Indian initial returns**,
  because nearly all Indian IPO candidates are young. Keep as a hard-filter (<3 yrs = cap the
  score) rather than as a continuous predictor.

### C. Valuation

- P/E at issue price vs listed peers (from RHP "Basis for Issue Price")
- P/B vs peers — Viswan uses P/B as the dependent variable for pricing aggression
- EV/EBITDA for low/volatile-profit firms; P/S for loss-makers (INDmoney)
- **Industry P/E ratio as a separate variable from company P/E** — Sehgal & Sinha: industry P/E
  is *positively* related to underpricing (t = 1.63). High-P/E sectors carry more uncertainty
  about whether the newcomer can keep up. **We conflated this with company valuation. Split it.**
- Peer-set integrity check — cherry-picked or non-comparable peers is itself a red flag (SMC;
  and the IPO Watch reviewer's "eyewash" call on Vinod Texworld is exactly this)
- Valuation step-up vs recent pre-IPO private transactions (SEBI now mandates this disclosure
  with 3-year look-back — CWM India)

### D. Management, Governance, Ownership

- Promoter track record, prior regulatory action, defaults
- Post-IPO promoter holding and lock-in schedule
- Corporate governance: auditor qualifications, auditor resignations, board independence
- Litigation: pending cases against company, promoters, directors
- Group structure opacity (SMC: "complex, opaque group structures are a reason to slow down")
- **Lead manager / investment bank reputation** — Sehgal & Sinha operationalise this as the
  underwriter's *share of total IPO proceeds* in the period; negatively related to underpricing
  (t = −1.18). Viswan finds underwriter reputation significantly *raises* the P/B the issuer can
  command (t = 2.269). **We said "lead manager track record" in the earlier spec but never
  defined a metric. This is the metric.**
- Private vs PSU dummy — Sehgal & Sinha: private IPOs significantly less underpriced (t = −2.60)

### E. Sector & Industry

- Sector classification, with historical base rates. Kundnani et al. (2024), 500 NSE IPOs
  2014-23, average 1-year post-IPO return by sector: **Technology 18.23%, Pharma 16.89%,
  Consumer Goods 14.56%, Financial Services 13.78%, Real Estate 9.12%.**
- **"New economy" dummy** (IT/ITeS, biotech, pharma, telecom, media) — Sehgal & Sinha: positively
  related to underpricing (t = 1.40); Karlis (2000): shorter/less informative history and
  intangible assets → harder to value → more underpricing.
- Industry growth runway, regulatory exposure, input-cost linkage (crude, coal, steel)

### F. Market & Macro Conditions

- **IPO market hotness** — count of IPOs in trailing 30/90 days. Ritter (1991) windows of
  opportunity; Baker & Wurgler (2002) market timing; Lowry, Officer & Schwert (2010) IPO volume
  responds to market instability. Karki & Jha confirm the Indian cycle empirically.
- Index level and trend (Nifty) in the month before issue — Sehgal & Sinha's market-climate dummy
- Sector index momentum
- **Macro set** (Sehgal & Sinha tested all of these): GDP growth, net FII inflows, inflation (WPI),
  IIP industrial growth, 91-day T-bill yield as opportunity cost of capital. Most were dropped for
  multicollinearity — but FII flows and T-bill yield are worth re-testing on current data.
- **Issue clustering / same-week listing congestion** — the Dasari (2026) paper notes crowded
  primary supply splits grey-market demand. Our own spine shows 2 to 43 IPOs per 30-day window.

### G. Sentiment (treat separately — different epistemic status)

- **GMP level** and, more importantly, **GMP trend over the final 3-5 days**
- Kostak rate and "subject to sauda" rates (secondary grey-market signals)
- Finfluencer/social volume — Dasari (2026) explicitly flags that finfluencer commentary and GMP
  narratives "disproportionately mobilise retail participation and distort price discovery"
- Put-call ratio on Nifty as a market sentiment proxy (Sehgal & Sinha) — but see contradiction C4

### H. Post-Listing Microstructure — **entirely missing from our earlier framework**

This is the biggest gap in what we built before, and it comes from Dasari (2026).

- **Bid-ask spread at listing** — a wide spread means the quoted listing price is not a price you
  can actually transact at
- **Order-book depth** on both sides
- **Rate at which sell-side offers get absorbed**
- **Circuit-band behaviour** (upper/lower band lock)

Dasari's core argument: *"a positive listing price does not guarantee that an investor can exit a
meaningful quantity of shares at that price."* For SME issues with thin order books this is the
difference between a paper gain and a realised one. His two-stage framework — separating the
**bidding decision** from the **post-listing bid-ask decision** — is a better structure than my
earlier single flip/hold call, and I'd adopt it.

### I. Flipping Pressure / Supply Dynamics — also missing before

From the SEBI study (the most credible single source in this whole set):

- **54% of all IPO shares (ex-anchor) are sold within one week of listing.**
- Individual investors: 50.2%. NII: 63.3%. Retail: 42.7%. **Banks: 79.8%. Mutual funds: 3.3%.**
- **Disposition effect**: investors dump winners and hold losers. Individuals sold 67.6% when
  week-1 returns exceeded 20%, but only 23.3% when returns were negative.
- Correlation between week-1 listing gain and retail exit % = **0.7**
- Post-SEBI/RBI April-2022 rules (NII lottery allotment, ₹1cr NBFC funding cap), NII
  oversubscription fell from 38x to 17x, and big-ticket NII applications fell from ~626 per IPO
  to ~20 per IPO.

**Why this matters for your specific question:** you assumed "the market corrects its value
within a week of listing." SEBI's data says the *selling* concentrates in that week — which is
the mechanism that would produce your assumed correction. But the correction is asymmetric: it
is far stronger for IPOs that popped, because that's where the disposition-effect selling lands.

---

## PART 2 — ADDITIONAL CREDIBLE SOURCES TRACED FROM THE REFERENCE LISTS

Beyond your 8 PDFs and 7 links, these are the sources the literature reviews point to that
carry real weight for factor selection. I've marked which I read in full vs. cited-via.

**Read in full (fetched):**
- **Viswan M G (2026)**, *The Strategic Role of Issue Composition and Market Sentiment in
  Determining IPO Underpricing and Valuation in India*, IJLTEMAS XV(IV). n=236, 2009-2020. This
  is what your `share.google` link resolves to. Most directly useful new paper in the set.
- **SEBI, Department of Economic and Policy Analysis (Sept 2024)**, *Analysis of Investor
  Behavior in IPOs*. n=144 mainboard IPOs, FY22-FY24, 2.9 crore shareholder records. Peer
  reviewed by a working group with academic, merchant-banking and AMC representation. **This is
  the highest-authority source you have — it's the regulator using depository-level data no
  private researcher can access.**

**Cited-via, worth sourcing before you finalise weights:**
- **Chatterjee, Bhattacharjee & Chakraborty (2024)**, *A systematic literature review of the
  Indian IPO market*, Journal of Risk and Financial Management 17(6), 251. Reviews 111 Indian IPO
  studies 2002-2021. The definitive map of what's been tested.
- **Ahuja, Kumar & Bisht (2024)**, *A review of IPO pricing and performance: Evidence from the
  Indian capital market*, JRFM 17(4). Identifies investor sentiment, corporate governance,
  institutional participation, market conditions, information asymmetry as the significant blocks.
- **Prosad & Singh (2023)**, *Pre-IPO financial performance and offer price estimation: Evidence
  from India*, JRFM 16(2), 135. Finds NAV and ROA significantly determine offer price — directly
  relevant to an under/fair/over-valued verdict.
- **Neupane, Neupane, Paudyal & Thapa (2017)**, *Domestic and foreign institutional investors in
  IPOs: Who wins?*, Pacific-Basin Finance Journal 45. Splits institutional demand by
  domestic/foreign — a finer cut than the QIB aggregate.
- **Neupane & Poshakwale (2012)**, *Transparency in IPO mechanism: Retail investors'
  participation, IPO pricing and returns*, Journal of Banking & Finance 36(7).
- **Dhamija & Arora (2017)**, *Impact of Quality Certification on IPO Underpricing*, Global
  Business Review 18(2). The counterweight to Viswan on the OFS question.
- **Loughran & Ritter (2002)** prospect theory; **Rock (1986)** winner's curse;
  **Benveniste & Spindt (1989)** book-building demand revelation; **Beatty & Ritter (1985)**
  ex-ante uncertainty. These four are the theoretical spine.
- **Lin & Hsu (2008)**, Hong Kong/Taiwan — found **allotment ratio** (shares offered ÷ shares
  bid for) the most consistent underpricing determinant. Directly computable from Indian
  subscription data and **not in any of your uploaded papers.** Worth adding.
- **Das (2025)**, *Return and volatility behaviour of Indian start-up IPOs under bull and bear
  market regimes*, Journal of Financial Economic Policy.
- **Yalçın & Ünlü (2018)** — your VIKOR PDF. Its value isn't the Turkish results; it's the
  **CRITIC objective weighting method**, which derives criteria weights from the data's own
  correlation/variance structure instead of from analyst judgement. That's a direct answer to
  "how do I set the weights without guessing." See Part 3.4.

---

## PART 3 — WEIGHTS

### 3.1 Why two separate scorecards, and why that's now three

The evidence is unambiguous that short-run and long-run performance have **different, sometimes
opposite, drivers**. Kundnani et al.: average listing-day returns 18.98-26.35% across 2014-23,
but 5-year average returns only 6.12-9.56% with many negative. Sehgal & Sinha: +24.93% day 1,
then −1.21% cumulative by month 6 — the Indian market takes about 6 months to price an IPO
correctly. Hawaldar et al. (2018): book-built IPOs show *negative* cumulative abnormal returns
out to 5 years.

So: **Scorecard A = listing-day/flip. Scorecard B = long-term hold. Scorecard C = valuation
(under/fair/over).** Your question list has three questions; they need three models.

### 3.2 Scorecard A — Listing-Day Return (weights sum to 100)

Grounded on: SEBI Table 4 (hard empirical), Sehgal & Sinha t-statistics, Viswan ANOVA.

| Factor | Weight | Direction | Evidence strength |
|---|---|---|---|
| Total subscription multiple | **26** | + | **Strong** — SEBI n=144 calibration table; S&S t=11.69 |
| GMP level and final-3-day trend | **16** | + | Medium — practitioner only, unaudited, no peer-reviewed Indian study in this set uses it |
| QIB subscription multiple | **12** | + | Medium-strong |
| Issue size / gross proceeds | **10** | **−** | Strong — S&S t=−4.79; SEBI exit data |
| NII/QIB demand ratio (fade risk) | **8** | − | Medium — SEBI NII exit 63.3% |
| Market hotness (IPOs trailing 30d, index momentum) | **8** | + | Medium — Ritter, Baker & Wurgler, Karki & Jha |
| Sector / new-economy dummy | **6** | + | Medium — S&S t=1.40; Karlis |
| OFS proportion | **5** | **+** | Medium — Viswan: full-OFS 20.61% vs full-fresh 8.04%. **Note sign.** |
| Number of uses of proceeds (vagueness) | **4** | + | Medium — Beatty & Ritter; S&S t=1.81 |
| Lead manager reputation (share of IPO proceeds) | **3** | − | Weak-medium — S&S t=−1.18, authors call it weak |
| Industry P/E | **2** | + | Weak — S&S t=1.63 |

**Hard override, not a weighted factor:** if segment = SME, apply the post-listing liquidity gate
from Part 1.H before any flip verdict. A 25% paper gain on an untradeable order book is not 25%.

### 3.3 Scorecard B — Long-Term Hold (weights sum to 100)

Grounded on: Kundnani regression (firm size β=0.245, market sentiment β=0.198, financial health
β=0.128, all p<0.01), Prosad & Singh, Viswan, and practitioner consensus across INDmoney/SMC/CWM.

| Factor | Weight | Direction |
|---|---|---|
| Financial health: revenue & PAT CAGR, margin trend, OCF/PAT | **20** | + |
| Firm size / scale | **14** | + (note: opposite sign to Scorecard A) |
| Valuation vs peers (P/E, P/B, EV/EBITDA) | **14** | − |
| Balance sheet: D/E, RoE, RoCE — level *and* trend | **12** | + |
| Fresh issue % (growth capital) | **10** | **+** (opposite sign to Scorecard A) |
| Governance & related-party flags | **10** | − |
| Business moat, customer/geographic concentration | **8** | + |
| Promoter post-IPO holding & credibility | **6** | + |
| Sector base rate (Kundnani 1-yr returns by sector) | **4** | + |
| Lead manager reputation | **2** | + |

### 3.4 Don't hard-code these weights — derive them

The numbers above are **priors from literature, not fitted coefficients.** They're defensible
starting points but they are my judgement calls translated from t-statistics, and t-statistics
are not weights.

Two better options once you have the data:

1. **CRITIC objective weighting** (Yalçın & Ünlü 2018, your VIKOR PDF). Derives weights from each
   criterion's standard deviation and its correlation with other criteria — factors that carry
   independent information get more weight automatically. No analyst judgement required. This is
   the right method while your labelled sample is still small.
2. **Regularised regression / gradient boosting** once you have 400+ labelled mainboard rows.
   Then the weights *are* the fitted coefficients and Part 3.2 becomes the sanity check rather
   than the model.

Use CRITIC first, move to fitted weights when n supports it, and keep the literature priors as a
guardrail: if a fitted coefficient flips sign against strong prior evidence, that's a data bug,
not a discovery.

---

## PART 4 — WHAT WAS MISSING, AND WHERE I NOW DISAGREE WITH MYSELF

### 4.1 Missing from our earlier framework (high value)

1. **The SEBI subscription→return calibration table.** This is the single most useful number set
   in the whole corpus and it replaces guesswork in the flip model:

   | Subscription | n | **Median listing-day return** |
   |---|---|---|
   | >100x | 17 | **+82%** |
   | 10x–100x | 75 | **+22%** |
   | 5x–10x | 10 | **+10%** |
   | 1x–5x | 40 | **−2%** |
   | Undersubscribed | 2 | +2% |

   Note the sign flip below 5x. An IPO subscribed 1-5x has a *negative* median listing return.
   My earlier per-IPO commentary treated 2-4x as "decent demand" — by this table it's the
   danger zone.

2. **Post-listing bid-ask depth and spread** (Dasari) — whether the gain is realisable at all.
3. **Flipping pressure and the disposition effect** (SEBI) — week-1 supply is predictable and
   concentrated in the IPOs that popped.
4. **Number of uses of proceeds** as an ex-ante uncertainty proxy — free, sitting in every RHP.
5. **Allotment ratio** (Lin & Hsu) — most consistent determinant in HK/Taiwan, computable here.
6. **Lead manager reputation as a quantified metric** (share of IPO proceeds managed), not a
   vibe.
7. **Industry P/E as separate from company P/E.**
8. **Anchor lock-in expiry as a dated supply event.**
9. **Risk-adjusted return (Sharpe)** — Gopal & Reshma compute it per IPO (Ather 2.02 vs Travel
   Food 0.84). We ranked on raw return only.
10. **Macro block** — FII flows, T-bill yield, inflation, IIP.

### 4.2 Things we used that the sources barely mention

- **GMP.** I gave it 30% of the flip scorecard. Not one peer-reviewed paper in this corpus uses
  GMP as a variable. SMC says studies find it tracks listing-day gains; Dasari treats it as a
  sentiment distortion channel; INDmoney says explicitly it "does not tell you anything about the
  company." I've cut it to 16% and put subscription first. **This is a change from what I told
  you earlier and the earlier weighting was not evidence-based.**
- **12-month news-based red-flag scanning.** Sensible, but no source in this set formalises it.
  Keep it as a hard-override gate rather than a weighted factor — it's high-precision,
  low-recall.
- **"Window dressing" / pre-IPO margin manipulation.** Practitioner reviewers flag it; academic
  literature here doesn't operationalise it. Closest formal proxy is Teoh, Welch & Wong (1998) on
  earnings management around IPOs, cited in Kundnani. Worth adding as a computed check:
  margin in final pre-IPO year vs 3-year mean.

### 4.3 Where I now hold a contradicting view

**C1 — OFS proportion: I had the sign wrong for listing day.**
I told you OFS-heavy issues were a negative signal, full stop. Viswan (2026, n=236) finds the
opposite for *listing day*: full-OFS averaged 20.61% underpricing, 100%-fresh only 8.04%. The
mechanism is that selling shareholders who know intrinsic value price aggressively (higher P/B),
and aggressive pricing gets compensated with higher initial returns. **Correct treatment: OFS% is
a mild positive for Scorecard A and a clear negative for Scorecard B.** Note the literature is
itself split — Dhamija & Arora (2017) found the reverse direction in India. Flag as contested,
low weight, and re-test on your own data.

**C2 — Subscription vs QIB: the practitioner sources and the data disagree.**
INDmoney and SMC both say headline subscription is noise and QIB is the real signal. The
quantitative evidence says headline subscription is the *strongest single predictor of listing-day
return* (S&S t=11.69; SEBI's table). Both are right about different things: **total subscription
predicts the pop; QIB quality predicts whether the pop survives.** My earlier framework weighted
QIB at 30% and dismissed headline subscription — that was wrong for a flip model.

**C3 — Firm size: two of your own papers directly contradict each other.**
Sehgal & Sinha: company size *negatively* related to initial return (t = −4.79). Kundnani et al.:
firm size *positively* affects IPO performance, and it's their largest coefficient (β = 0.245,
p = 0.002). This is not a data error — they have different dependent variables. S&S measure
day-1 underpricing; Kundnani measure long-run abnormal return. **Resolution: big IPOs pop less
and compound better.** That single fact justifies the whole two-scorecard architecture, and it's
why NSE (₹22,562cr) reads differently on the two models.

**C4 — Investor sentiment sign is unresolved.**
Sehgal & Sinha find sentiment (Nifty put-call ratio) *negatively* related to underpricing — i.e.
bearish market → *more* underpricing — which is counterintuitive and contradicts the hot-market
narrative in Kundnani, Karki & Jha, and Ljungqvist et al. (2006). I suspect the put-call proxy is
the problem rather than the finding. **Do not use put-call ratio.** Use index momentum and IPO
count directly.

**C5 — On the uploaded corpus's own quality.**
Being straight with you, since you'll outsource this: these papers are not of uniform quality.
Sehgal & Sinha (Ministry of Finance / DU, 432 IPOs, full OLS with diagnostics) and the SEBI study
are rigorous. Kundnani et al. (2024) reports suspiciously smooth regression tables and its
sector/year figures should be independently verified before you rely on the exact numbers. Dasari
(2026) is a **preprint that has not undergone peer review** (stated on its own cover page) and is
explicitly descriptive, not inferential — its bid-ask framework is a good *idea*, not a tested
model. Gopal & Reshma (2025) is a student conference paper; its Sharpe ratios use standard
deviations whose derivation isn't shown. **Weight the SEBI study and Sehgal & Sinha heavily;
treat the rest as hypothesis generators.**

---

## PART 5 — THE MISSING VARIABLES AND HOW TO GET THEM

### 5.1 I could not fetch current prices for 909 companies — and why

You asked me to fetch all remaining variables including current-to-date performance for every
company in the Excel. I can't do that in this session, and I'd rather say so than hand you a
partially-invented table:

- This container's network is restricted to package repositories (pypi, npm, github). It cannot
  reach NSE, BSE, Yahoo Finance or any market-data host. So no bulk `yfinance` pull from here.
- Web search works one query at a time. 909 companies × (listing price + current price +
  subscription + financials) is several thousand lookups.
- Fabricating any of it would poison the training set silently, which is the single worst outcome
  for a model you intend to give other people.

So Part 5.2 is the acquisition map and `fetch_ipo_data.py` is the runnable fetcher, to be run on
your machine where the network is open.

### 5.2 Variable acquisition map

| Variable block | Source | Method | Est. coverage |
|---|---|---|---|
| Listing price, listing-day OHLC | NSE bhavcopy archives (daily ZIP, free, by date) | We have listing date + symbol for all 909 → direct join | ~95% |
| Current price, full price history | `yfinance` with `SYMBOL.NS` / `.BO` | Symbol column already present | ~90% mainboard, ~70% SME |
| Subscription by category | NSE `/api/ipo-detail`, Chittorgarh, IPO Ji | Scrape by symbol | ~85% |
| Issue size, fresh vs OFS split | RHP (SEBI/exchange PDF), or Chittorgarh summary | PDF parse or scrape | ~90% |
| Financials (3-yr), RoE, D/E, OCF | RHP "Basis for Issue Price" + "Financial Statements" | PDF table extraction | ~80% |
| P/E, P/B, peer comparison | RHP "Basis for Issue Price" — it's tabulated there | PDF parse | ~85% |
| Promoter holding pre/post | RHP "Capital Structure" | PDF parse | ~90% |
| Lead manager | Already in most trackers; RHP cover page | Scrape | ~95% |
| GMP history | InvestorGain/IPO Watch archives | Scrape; **sparse pre-2023** | ~50% |
| Sector | NSE industry classification | API | ~95% |
| Nifty level/momentum | `yfinance` `^NSEI` | Direct | 100% |
| Bid-ask/depth at listing | Paid tick data or broker API | **Hardest; likely skip v1** | <20% |

**Realistic v1 target:** listing price + subscription + issue structure + sector + macro for
mainboard IPOs 2023-2026. That's roughly 320 rows with a clean target — enough for a regularised
model with 8-12 features, not enough for 40 features. Plan the feature count around the sample
size, or you'll overfit spectacularly and it'll look great in backtest.

### 5.3 Two design warnings for the build

**Survivorship and delisting.** Companies that delisted or were suspended will silently drop out
of any `yfinance` pull, and they're disproportionately the failures. Your long-run returns will
be biased upward. Karki & Jha explicitly exclude firms delisted within 6 months — note that this
is a *choice* that removes the worst outcomes. Log the misses rather than dropping them.

**Look-ahead leakage.** The flip model must only use information available *before* the bid
deadline. Final-day subscription is available before you bid on day 3 only if you bid late.
Listing-day volume is not available at all. Timestamp every feature with when it becomes
knowable, and exclude anything that post-dates the decision point. This is the single most common
way backtests lie.

---

## PART 6 — LINKS: STATUS AND OPEN QUESTIONS

### Link status

| Link | Status |
|---|---|
| cwmindia.com/evaluating-ipos-in-india | ✅ Read — 8-factor retail framework |
| finxl.in/blogs/ipo-valuation-model-guide | ✅ Read — DCF/comps/VC methods, book-building vs fixed |
| indmoney.com/learn/ipo/how-to-analyse-ipo | ✅ Read — 7-parameter framework + 35-point scorecard |
| smctradeonline.com/blog/ipo/how-to-evaluate-an-ipo | ✅ Read — RHP-first framework, anchor/lock-in |
| share.google/T0THXbSHDB5m6BBSX | ✅ Resolved → Viswan (2026) IJLTEMAS. **Best new source in the set** |
| **maliktimes.in/how-to-read-ipo-rhp** | ❌ **Blocked — site disallows automated access.** Please paste the text if you want it included. Note SMC has an equivalent 12-point RHP checklist that likely covers the same ground |
| reddit.com/r/IndiaInvestments/…/screening_an_ipo | ⚠️ **Not fetched.** Reddit blocks automated access, and separately I'd weight an anonymous 2021 forum post far below the SEBI study and the peer-reviewed set. Paste it if you want it in, but I'd not let it move any weights |

### Questions I need answered before the build

1. **Scope:** mainboard-only, or mainboard + SME? SME is 58% of your file but has the worst data
   coverage and the thinnest liquidity. My recommendation: build and validate on mainboard, add
   SME as a separate model with its own weights, never pool them.
2. **Target definition:** listing-day *close* vs listing-day *open*? These differ materially and
   the literature uses both. SEBI uses close-vs-issue-price. I'd match SEBI so the calibration
   table transfers directly.
3. **Your holding horizon for "long run"** — 1 year, 3 years, or 5? The evidence says 1-year and
   5-year behave very differently (Kundnani: 1-yr avg ~15%, 5-yr avg ~8% with heavy negative tail).
4. **Do you have, or can you get, paid data access** (Prime Database, Capitaline, Trendlyne Pro)?
   That collapses Part 5.2 from weeks of scraping to a single download, and Prime is what Sehgal &
   Sinha used.
5. **Budget for GMP history.** It's the weakest-provenance variable and the hardest to backfill
   before 2023. If you can't get clean history, the honest move is to exclude it from the trained
   model and use it only as a live-time overlay.

---

## PART 7 — WHAT I'D BUILD FIRST

Not the full 40-factor agent. In order:

1. **Acquire the target.** Listing price for all 909 rows via NSE bhavcopy join. Nothing else
   matters until y exists. One weekend.
2. **Reproduce SEBI's Table 4 on your own data.** If you can recover the subscription→listing
   return relationship on your 2021-2026 sample, your pipeline is trustworthy. If you can't, fix
   the pipeline before adding features. This is your validation gate.
3. **Then** add issue structure, then fundamentals, then sentiment — in that order, measuring
   incremental R² at each step. Stop when the increments stop paying.
4. Keep the literature weights (Part 3.2/3.3) as the fallback scorecard for live IPOs where the
   model lacks features — which will be most of them at first.

The honest expectation on accuracy: Sehgal & Sinha's full 9-factor model achieved **R² = 0.38**
on 432 IPOs. They argue — correctly — that a *low* R² is what ex-ante uncertainty theory predicts,
because if initial returns were highly predictable the underpricing would be arbitraged away.
Anyone promising you a high-R² IPO listing-gain model is either overfitting or lying. Build for
a well-calibrated 60-65% directional hit rate, not for precision.

# IPO Model Build Spec v2.0 — Final Variable List & Agent Architecture

Supersedes the weighting in v1.0 Part 3.2 where they conflict. All numbers below are
measured on your own data, not borrowed from literature.

---

## PART A — WHAT THE NEW DATASET CHANGED

`Initial_Public_Offering__Updated_.xlsx`: **652 IPOs, Jan-2010 to May-2026**, mainboard,
with the QIB/HNI/RII split. Integrity is good — Listing Gain reconciles against
(List−Offer)/Offer for 99.7% of rows, zero exact duplicates, 2-10 nulls per column.

**Name completion:** 69 truncated names (49 from 2025, 20 from 2026). I auto-resolved
**38 of 69** by matching date-window + prefix against your tracker files. The remaining
**31 need a web lookup** — the agent can do these one at a time.

### A.1 Settled: Total subscription beats QIB. The practitioner consensus is wrong.

I said in v1.0 this was contested (contradiction C2). It isn't anymore. AUC for
P(listing gain > 10%), 624 IPOs, 5-fold out-of-fold:

| Feature set | AUC |
|---|---|
| **Total subscription + size** | **0.8831** |
| QIB + HNI + RII split + size | 0.8757 |
| Total + QIB + size | 0.8819 |
| All four + size | 0.8807 |
| QIB only + size | 0.8579 |

Total alone wins. Adding QIB makes it *worse*. INDmoney and SMC both say headline
subscription is noise and QIB is the real signal — **for listing-day prediction that is
false**, and now it's false on 624 Indian IPOs rather than on my opinion.

### A.2 Surprise: HNI is the strongest category, not QIB

Within the split model, standardised logistic coefficients:

| Category | Coefficient | Weight |
|---|---|---|
| **HNI** | +1.023 | **50.5%** |
| QIB | +0.681 | 33.7% |
| RII | +0.287 | 14.2% |
| log issue size | +0.032 | 1.6% |

This contradicts my v1.0 Scorecard A, which treated a high NII/QIB ratio as a *negative*
(fade risk). For listing-day magnitude, HNI demand is the single most informative category.
The fade risk is real but it shows up *after* listing day, not on it — which is exactly why
the two models must stay separate.

**Use Total as the primary feature. Keep the three categories as secondary features for
the fade/hold signal, not for the listing call.**

---

## PART B — LISTING MODEL (L1 / L2)

### B.1 Specification

| Item | Choice |
|---|---|
| Method | Logistic regression, L2 penalty |
| Target L1 | `listing_gain > 0` → bid/no-bid |
| Target L2 | `listing_gain > 10` → aggressive flip |
| Split | Separate models for Mainboard and SME (coefficients differ in sign — v1 Fix 2) |
| Validation | 5-fold stratified, out-of-fold probabilities only |
| Primary metric | AUC, then calibration gap per probability decile |
| Decision threshold L1 | **≥90%** → fires on ~28% of mainboard IPOs, 92.5% actual hit rate |
| Decision threshold L2 | **≥80%** → fires on ~10%, 94.4% actual hit rate |

Do not use a 90% threshold on L2. It fired once in 186 mainboard IPOs and was wrong.

### B.2 Feature list, ordered by decision-time availability

The four models D0–D3 from the last round each use a cumulative slice of this list.

| # | Feature | Transform | D0 | D1 | D2 | D3 |
|---|---|---|---|---|---|---|
| 1 | Total subscription | log1p | | ✓ | ✓ | ✓ |
| 2 | QIB subscription | log1p | | ✓ | ✓ | ✓ |
| 3 | HNI subscription | log1p | | ✓ | ✓ | ✓ |
| 4 | RII subscription | log1p | | ✓ | ✓ | ✓ |
| 5 | Issue size ₹cr | log | ✓ | ✓ | ✓ | ✓ |
| 6 | GMP % of cap | raw | ✓ | ✓ | ✓ | ✓ |
| 7 | GMP 3-day slope | raw | ✓ | ✓ | ✓ | ✓ |
| 8 | GMP−subscription divergence | z(GMP)−z(sub) | | ✓ | ✓ | ✓ |
| 9 | Segment (SME/mainboard) | binary | ✓ | ✓ | ✓ | ✓ |
| 10 | Price band width % | raw | ✓ | ✓ | ✓ | ✓ |
| 11 | Fresh issue % of total | raw | ✓ | ✓ | ✓ | ✓ |
| 12 | # of stated uses of proceeds | count | ✓ | ✓ | ✓ | ✓ |
| 13 | GCP as % of proceeds | raw | ✓ | ✓ | ✓ | ✓ |
| 14 | Anchor ₹ as % of issue | raw | ✓ | ✓ | ✓ | ✓ |
| 15 | Post-issue promoter holding % | raw | ✓ | ✓ | ✓ | ✓ |
| 16 | IPOs open in trailing 30d | count | ✓ | ✓ | ✓ | ✓ |
| 17 | Nifty 30d return | % | ✓ | ✓ | ✓ | ✓ |
| 18 | Nifty 30d realised vol | % | ✓ | ✓ | ✓ | ✓ |
| 19 | Sector (one-hot, ~12 levels) | dummy | ✓ | ✓ | ✓ | ✓ |
| 20 | New-economy dummy | binary | ✓ | ✓ | ✓ | ✓ |
| 21 | Lead manager 3yr proceeds share | % | ✓ | ✓ | ✓ | ✓ |
| 22 | P/E vs peer median | ratio | ✓ | ✓ | ✓ | ✓ |

**Feature budget:** you have 624 usable mainboard rows. At 10-15 rows per feature that
supports 22 features comfortably. Don't exceed ~40 even as data grows — check VIF on every
addition and drop one of any pair above 5.

---

## PART C — HOLDING MODEL (H)

### C.1 Your proposed target is broken. Here's the proof and the fix.

You proposed: *"1-year excess return over Nifty… if higher than 1.2 times bid price then Y."*

That is two incompatible definitions in one sentence. **Excess return over Nifty** is
relative and time-normalised. **1.2× bid price** is absolute and ignores the market entirely.
An IPO that returned +20% in a year when Nifty returned +25% destroyed relative value — your
rule would label it Y.

Worse, `Current Gains` in the new file is **not a 1-year return at all**. Median holding
period across the 580 seasoned rows is **5.5 years**, ranging 1.0 to 16.7. Labelling on it
measures vintage, not quality:

| Vintage | n | Y-rate under "Current Gains > 20%" | Median years held |
|---|---|---|---|
| 2011 | 39 | 28.2% | 15.3 |
| 2019 | 17 | 76.5% | 7.2 |
| 2020 | 16 | **87.5%** | 6.0 |
| 2025 | 60 | **30.0%** | 1.2 |

A 58-percentage-point spread driven purely by when you bought. Annualising to CAGR narrows
it to 33pp — better, still not clean. Only Nifty-relative normalisation closes it.

### C.2 The target to use

```
excess_1y = IPO_return(listing_close → listing_close + 365d)
          − NIFTY_return(same two dates)

H_label = 1 if excess_1y > 0 else 0        # "beat the index over year one"
```

Optionally tighten to `excess_1y > 10pp` if the base rate comes out near 50/50 and you want
a higher-conviction positive class. Decide that *after* you see the base rate, not before.

**This cannot be computed from the files you have.** `CMP` is today's price, not price at
T+365. You need a price series per symbol. That's Stage 2 of `fetch_ipo_data.py`.

**Eligible sample:** IPOs listed before ~Sep-2025 → roughly **480 rows** from the new
dataset. That's a genuinely trainable holding model, which I couldn't say last round.

### C.3 Independent confirmation that two models are needed

Correlation between listing gain and long-run CAGR: **Pearson 0.218, Spearman 0.264**.
Of IPOs that popped >20% on listing, 47.1% went on to beat a 12% CAGR. Of IPOs that listed
flat or negative, 18.5% did.

So listing gain carries *some* long-run signal — a 2.5× lift — but explains almost none of
the variance. One model cannot serve both decisions.

### C.4 Holding model feature list

Method: logistic regression, same discipline as L. All features knowable pre-bid.

**Valuation block** — the part entirely absent today
- P/E at issue price ÷ peer median P/E
- P/B at issue price ÷ peer median P/B
- EV/EBITDA ÷ peer median
- P/S ÷ peer median (for loss-makers)
- Industry P/E (absolute level)
- Implied market cap ÷ trailing revenue

**Quality / moat block** (S&P Economic Moat Index logic, adapted to 3-yr RHP data)
- RoCE 3-yr average
- RoCE − cost of capital spread (use 91-day T-bill + 6% equity premium as WACC proxy)
- Gross margin 3-yr standard deviation (lower = pricing power)
- Gross margin level vs industry median
- Revenue CAGR 3-yr
- PAT CAGR 3-yr
- OCF ÷ PAT (3-yr average)
- Free cash flow positive in n of 3 years (count)

**Balance sheet block**
- Debt-to-equity post-issue
- Interest coverage ratio
- Working capital days (receivable + inventory − payable)
- Contingent liabilities ÷ net worth

**Governance block** (IiAS/IFC/BSE scorecard framework, four equal-weight categories)
- Composite governance score 0–100
- Related-party transactions ÷ revenue
- Auditor qualification present (binary)
- Board independence ratio
- Promoter pledge % (and trend if available)

**Ownership / structure block**
- Post-issue promoter holding %
- Change in promoter holding pre→post
- Fresh issue % of total
- Pre-IPO placement price ÷ issue price
- Anchor allocation to mutual funds ÷ total anchor

**Business risk block**
- Top-10 customer concentration %
- Geographic concentration %
- Promoter years of industry experience
- Company age at IPO (years)
- Litigation: ₹ quantum of top 5 cases ÷ net worth

**Sector / macro block**
- Sector dummies
- Sector historical 1-yr post-IPO base rate
- Nifty 30d momentum at issue

That is ~35 features on ~480 rows. **Too many.** Run CRITIC weighting or L1-regularised
selection to cut to 15-18 before fitting. Do not fit all 35.

---

## PART D — RHP EXTRACTION AGENT

You're right that this is crucial, and right that "I can't read 10 RHPs in a chat turn" is a
statement about chat turns, not about agents. Here's the design.

### D.1 Why it fails in chat and works as an agent

An RHP is 300-600 pages. Reading one end-to-end burns most of a context window. In a single
chat turn I get one, maybe two. An agent has no such limit — it loops, processes one document
per invocation, writes results to disk, and resumes. The fix is **targeted extraction**, not
brute-force reading: every variable you need lives in one of eight known sections.

### D.2 Architecture

```
rhp_agent/
├── SKILL.md                 # extraction rules + validation thresholds
├── locate.py                # TOC parse → page ranges for 8 target sections
├── extract/
│   ├── objects.py           # Objects of the Issue      → fresh/OFS, uses count, GCP%
│   ├── capital.py           # Capital Structure         → promoter %, pre-IPO placements, lock-in
│   ├── financials.py        # Restated Financials       → revenue, PAT, margins, OCF, D/E
│   ├── basis.py             # Basis for Issue Price     → P/E, P/B, RoNW, NAV, PEER TABLE
│   ├── rpt.py               # Related Party Transactions→ RPT ÷ revenue
│   ├── litigation.py        # Outstanding Litigation    → count + ₹ quantum top 5
│   ├── risk.py              # Risk Factors              → customer/geo concentration
│   └── management.py        # Our Management            → promoter experience, board independence
├── validate.py              # cross-check vs Chittorgarh summary
└── run_batch.py             # queue → extract → validate → DB
```

### D.3 The extraction loop

1. **Fetch** the RHP PDF from the NSE/BSE offer-documents page (link is on every IPO page).
2. **Locate** — parse the table of contents to get page ranges for the eight sections. RHPs
   follow a SEBI-mandated order, so the TOC is reliable. Fall back to regex on section
   headers if the TOC doesn't parse.
3. **Slice** — extract only those page ranges to text. This cuts 500 pages to ~60.
4. **Extract per section** — each module pulls its named fields. Tables go through
   `camelot`/`pdfplumber`; narrative fields through targeted LLM extraction on that slice
   only.
5. **Validate** — this is the step that decides whether the whole thing is trustworthy:
   - Revenue and PAT must match the Chittorgarh/tracker summary within 2%
   - Fresh + OFS must equal total issue size within 1%
   - Post-issue promoter % must be between 0 and 100
   - Any field failing → write `NULL` plus a `needs_review` flag. **Never** write a guessed
     value.
6. **Persist** — one row per IPO into SQLite/Postgres, keyed on ISIN.

### D.4 Operating characteristics

| | |
|---|---|
| Runtime | 5-12 min per RHP |
| Live agent load | 5-10 open IPOs → run overnight before the Mon/Thu brief, not during it |
| Historical backfill | 480 RHPs ≈ 60-90 hours of compute, run as a one-time queue |
| Where it runs | **Claude Code on your machine.** claude.ai skills have no network access in the sandbox — it cannot fetch PDFs |
| Failure mode to expect | Older RHPs (pre-2015) are scanned images, not text. Needs OCR. Budget ~15% failure on the 2010-2015 vintage |

### D.5 Non-negotiable rule

The validation step must fail loudly. A silently wrong revenue figure is far more damaging
than a missing one — it propagates into every ratio downstream and into the model weights,
and you will never find it by inspection.

---

## PART E — FINAL MASTER VARIABLE LIST

| # | Variable | Source | Period needed | Model |
|---|---|---|---|---|
| **Already in hand** ||||
| 1 | Listing gain % | New dataset | 2010-2026, 652 rows | L (target) |
| 2 | Total subscription | New dataset | 2010-2026 | L, H |
| 3 | QIB / HNI / RII split | New dataset | 2010-2026 | L, H |
| 4 | Issue size ₹cr | New dataset | 2010-2026 | L, H |
| 5 | Offer price, list price | New dataset | 2010-2026 | both |
| 6 | Current price BSE/NSE | New dataset | snapshot | diagnostics only |
| 7 | Segment SME/mainboard | Tracker files | 2025-26 | both |
| 8 | Price band width % | NSE spine | 2021-26 | L |
| 9 | Fixed vs book-built | NSE spine | 2021-26 | L |
| 10 | IPOs in trailing 30d | Computed from spine | 2010-2026 | both |
| **Must fetch — market data** ||||
| 11 | Price at listing+365d | yfinance `SYMBOL.NS` | 2010-2025 listings | **H target** |
| 12 | Nifty at listing & +365d | yfinance `^NSEI` | 2010-2026 daily | **H target** |
| 13 | Nifty 30d return / vol at issue | yfinance `^NSEI` | 2010-2026 daily | both |
| 14 | Sector classification | NSE industry API / ISIN map | all rows | both |
| 15 | GMP level + 3d slope | InvestorGain, IPO Watch | 2023-26 (sparse before) | L |
| 16 | Day-1 / day-2 subscription | Chittorgarh per-IPO pages | 2021-26 | L (D1/D2) |
| **Must extract — RHP agent** ||||
| 17 | Fresh vs OFS split | Objects of the Issue | per IPO | both |
| 18 | # uses of proceeds, GCP % | Objects of the Issue | per IPO | L |
| 19 | Post-issue promoter %, lock-in | Capital Structure | per IPO | H |
| 20 | Pre-IPO placement price ratio | Capital Structure | per IPO | H |
| 21 | Revenue / PAT 3yr, margins | Restated Financials | per IPO | H |
| 22 | OCF, FCF, D/E, interest cover | Restated Financials | per IPO | H |
| 23 | RoCE 3yr avg + WACC spread | Computed from financials | per IPO | H (moat) |
| 24 | Gross margin 3yr std dev | Computed from financials | per IPO | H (moat) |
| 25 | P/E, P/B, RoNW, NAV at issue | Basis for Issue Price | per IPO | both |
| 26 | **Peer table + peer multiples** | Basis for Issue Price | per IPO | H (valuation) |
| 27 | RPT ÷ revenue | Related Party section | per IPO | H |
| 28 | Litigation count + ₹ top 5 | Outstanding Litigation | per IPO | H |
| 29 | Customer / geo concentration | Risk Factors | per IPO | H |
| 30 | Promoter experience, board indep. | Our Management | per IPO | H |
| 31 | Auditor qualification | Audit report | per IPO | H |
| 32 | Governance composite 0-100 | Scored from 19/27/30/31 per IiAS framework | per IPO | H |
| 33 | Anchor ₹, MF share | Exchange anchor disclosure | per IPO | L |
| 34 | Lead manager 3yr proceeds share | Computed from your own dataset | rolling 3yr | both |

**Live peer multiples (for #26 at prediction time):** the RHP peer table gives multiples as
of the filing date. For a live IPO you also want *current* peer multiples — source from
Screener.in or Trendlyne by peer symbol at run time.

### E.1 Build order

1. **Nifty + price history** (#11-13). Unblocks the H target. One yfinance script, a few hours.
2. **Name completion** for the 31 unresolved, then **join** new dataset ↔ trackers ↔ spine on
   name+date. Gets you segment and band data on the 2021-26 rows.
3. **Retrain L** on 624 mainboard rows with the QIB/HNI/RII split. Expect AUC ~0.88.
4. **Build the RHP agent**, run it on the ~480 H-eligible IPOs.
5. **Train H.** Only after #4 — it has no valuation features before then.
6. GMP backfill last. It's the weakest-provenance variable and only affects L, which already
   works without it.

---

## PART F — WHAT `cov_type='HC3'` MEANS

`sm.OLS(y, X).fit(cov_type='HC3')` is **statsmodels**, the Python stats library.

- `sm.OLS(y, X)` — set up an ordinary least squares regression of y on X
- `.fit()` — estimate it
- `cov_type='HC3'` — compute the standard errors using heteroscedasticity-consistent method 3

In plain terms: your prediction errors are small for boring IPOs and huge for hyped ones.
Default OLS assumes they're the same size everywhere and therefore reports confidence figures
that are wrong. `HC3` tells it to measure actual error size at each point instead of assuming.
**Your coefficients don't change. Only the error bars around them become honest.** HC3 is the
variant that behaves best on samples under ~1,000 rows, which is yours.

Since both your models are now logistic rather than OLS, the equivalent is:

```python
import statsmodels.api as sm
model = sm.Logit(y, sm.add_constant(X)).fit(cov_type='HC3')
print(model.summary())
```

Use `sklearn` for prediction and cross-validation; use `statsmodels` when you want to read
which coefficients are actually significant.

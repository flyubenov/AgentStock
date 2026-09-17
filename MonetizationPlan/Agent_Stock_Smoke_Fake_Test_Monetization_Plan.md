# Agent Stock — Smoke/Fake-Door Test & Monetization Plan

## 1. Objective

The smoke/fake-door test should validate four things before significant investment in commercial infrastructure:

1. Does the positioning attract serious investors?
2. Does Agent Stock create enough perceived value to make investors consider paying?
3. Which paid tier and price level do they prefer?
4. Will they proceed far enough toward payment to demonstrate genuine willingness to pay?

The objective is **not** to maximize email registrations. The strongest signals are plan selection, checkout progression, final purchase intent, and—if appropriate—a real refundable founding commitment.

---

# 2. Core Smoke-Test Funnel

The recommended flow is:

**Landing page → Analyze a stock → See compelling result → Understand methodology → Hit paid feature → Pricing → Checkout → Commitment**

Example:

> **Find great businesses before you overpay.**
>
> Enter any ticker.
>
> `NVDA` → **Analyze**

Then show a compelling Agent Stock result using the actual engine.

### Example result structure

| Signal | Result |
|---|---:|
| **Quality** | 9.4 / 10 |
| **Moat** | 92 / 100 |
| **Fair Value** | $180–250 |
| **Risk / Reward** | 0.8× |

The exact numbers must come from the real engine rather than marketing examples.

The visitor should **experience the product before being asked to pay**.

---

# 3. Landing-Page Experiment Setup

## One canonical public URL

Do **not** make users choose between multiple landing pages or randomly navigate between pages.

Use one public URL and assign each visitor to an experiment variant behind the scenes.

Example:

```text
Visitor
   ↓
Experiment assignment
   ↓
A / B / C
   ↓
Same URL / same coherent experience
```

Persist the assignment using a cookie, local storage, session, or account so the same visitor continues seeing the same variant.

The user should never have to know that multiple variants exist.

### Example positioning variants

**A — Value proposition**

> **Find great businesses before you overpay.**

Focus: Quality + Moat + Fair Value + Risk/Reward.

**B — Second opinion**

> **A second opinion for every stock you own.**

Focus: reducing uncertainty and checking an existing investment thesis.

**C — Systematic analysis**

> **Your systematic stock analysis engine.**

Focus: repeatability, consistency, and replacing ad-hoc spreadsheet/research work.

---

# 4. Don't Test Messaging and Price Simultaneously Initially

If the first experiment changes both positioning and price, it becomes difficult to know what caused differences in conversion.

## Phase 1 — Test the pitch

Keep the following substantially the same:

- Product/demo
- Features
- Pricing
- CTA
- Methodology explanation

Change primarily the positioning/headline.

Measure how far users progress through the funnel.

## Phase 2 — Test monetization

Take the strongest positioning and then test:

- Paid tier preference
- Price sensitivity
- Monthly vs annual preference
- Checkout progression

This produces cleaner experimental data.

---

# 5. Pricing Structure to Test

A simple two-tier paid structure is recommended.

## Pro

**$14.99/month**

or

**$149/year**

Purpose: serious individual investor.

Potential functionality:

- Unlimited stock analysis
- Quality
- Moat
- Fair Value
- Risk/Reward
- Detailed score breakdown
- Valuation-method breakdown
- Methodology transparency
- Basic stock comparisons
- Watchlists

## Power Investor

**$24.99/month**

or

**$199/year**

Purpose: investor with a larger research universe or portfolio.

Everything in Pro, plus:

- Bulk/watchlist analysis
- Portfolio analytics
- Historical score tracking
- Score-change monitoring
- Alerts
- “What changed?”
- Data export

The higher tier should sell **workflow and scale**, rather than merely more numbers.

---

# 6. Free Preview vs Production Free Tier

For the **smoke test**, do not spend time building a sophisticated formal free subscription tier.

Instead provide a:

## Free interactive preview

Let the visitor:

- Enter a ticker
- See the four headline signals
- See a concise methodology overview
- See enough of the analysis to understand the value

Then gate deeper functionality.

This tests whether the product can convert interest into payment intent rather than whether users will create free accounts.

For the eventual production product, a genuine free tier can be introduced if useful. It should provide meaningful value rather than making the free experience worthless.

---

# 7. What the Free Preview Should Show

The smoke-test preview should show the core concept:

- Quality headline
- Moat headline
- Fair Value headline/range
- Risk/Reward headline
- High-level methodology
- Selected calibration/trust information

Then:

> **Unlock full analysis**

The paid experience can reveal:

- Detailed Quality breakdown
- Detailed Moat breakdown
- Complete Fair Value model breakdown
- Individual valuation legs
- Calculation drivers
- Calibration/adjustment details
- Comparisons
- Watchlists
- Bulk analysis
- Historical data
- Alerts
- Portfolio functionality, depending on tier

The principle is:

> **Gate depth and workflow, not the core value proposition.**

---

# 8. What Actually Counts as Willingness to Pay?

Email registration is a weak signal.

Track a progression of increasingly strong signals.

### Level 1 — Interest

User:

- Enters a ticker
- Views analysis

### Level 2 — Commercial interest

User:

- Clicks “Unlock full analysis”
- Opens pricing
- Selects a plan

### Level 3 — Purchase intent

User:

- Chooses monthly/annual
- Starts checkout
- Enters email/payment information

### Level 4 — Commitment

User reaches:

> **Complete Purchase**

and clicks it.

This is the strongest fake-door signal if no real payment is taken.

---

# 9. Stronger Validation: A Real Refundable Founding Offer

If you want the strongest possible validation, consider a clearly disclosed founding offer.

Example:

> **Founding Investor**
>
> Lock in launch pricing:
>
> **$149/year**
>
> Fully refundable until launch.

If you actually accept money, only do so if you are comfortable legally and operationally supporting the stated refund and launch terms.

A real monetary commitment is considerably stronger evidence than an email address.

If you do not want to accept money yet, use the fake checkout and be completely transparent that no payment is taken.

---

# 10. Fake Checkout Flow

Suppose the visitor chooses:

> **Power Investor — Annual — $199**

and reaches checkout.

For the smoke test:

1. Confirm the selected plan.
2. Collect minimal information such as email.
3. Optionally display a realistic payment form.
4. Do **not** charge the card.
5. Record the final purchase-intent action.
6. Immediately explain that this is a pre-launch validation.

Example message:

> **You're on the Agent Stock founding list.**
>
> Agent Stock isn't commercially available yet, so no payment was taken.
>
> We've recorded your request for the **Power Investor — Annual** plan and will contact you when early access opens.

Never imply that a payment was made when it wasn't.

---

# 11. What to Record

Every meaningful funnel step should generate an event.

At minimum:

```text
visitor_id
experiment_variant
ticker
timestamp

analysis_started
analysis_completed

pricing_viewed

selected_plan
    Pro / Power

selected_billing
    Monthly / Annual

checkout_started

payment_form_started

purchase_button_clicked

actual_payment
    if a real founding offer is eventually used
```

This lets you calculate conversion through the actual commercial funnel rather than just signup rate.

---

# 12. Pricing Screen

Show both paid plans and both billing choices.

Example:

### Pro

$14.99/month

or $149/year

### Power Investor

$24.99/month

or $199/year

Track:

```text
Pro monthly
Pro annual

Power monthly
Power annual
```

A roughly 15–20% annual discount is a reasonable initial hypothesis, but should be treated as something to validate.

Do not hide monthly pricing.

---

# 13. The Four-Signal Product Pitch

The four engines should be the center of the product story.

## Quality

> **How good is the business?**

Based on fundamental business economics such as:

- Profitability
- ROIC / capital efficiency
- Margins
- Cash generation
- FCF conversion
- Growth
- Financial strength
- Consistency

Use only metrics actually implemented in the engine.

## Moat

> **How durable are those economics?**

The quantitative approach can emphasize characteristics such as:

- Long-term ROIC
- Persistence of attractive returns
- Margins
- Cash-flow economics
- Incremental capital efficiency
- Durability/consistency of business economics

Do not imply that the engine performs qualitative competitive analysis if it does not.

## Fair Value

> **What is the business worth?**

The Fair Value engine can combine multiple valuation “legs” depending on company classification.

Examples include:

- DCF
- P/E / earnings multiples
- EV/EBIT or EV/EBITDA approaches
- FCF multiples
- Owner-earnings-type approaches
- Historical valuation
- Relative valuation
- Industry/company-specific approaches where supported

The key selling point is:

> **You don't have to trust one valuation model.**

## Risk / Reward

> **Is today's price attractive relative to estimated value and downside risk?**

This connects intrinsic valuation to the actual market price.

It reinforces an important concept:

> **A great business is not automatically a great investment at any price.**

---

# 14. Explain the Valuation Methodology Without Exact Formulas

A landing page should provide a concise “How Fair Value works” section.

### DCF

Looks at expected future cash flows, growth, margins/cash conversion, reinvestment needs, discount rate, and terminal assumptions.

### Earnings multiples

Values the company using normalized earnings and an appropriate earnings multiple.

### EV-based valuation

Relates enterprise value to normalized operating earnings such as EBIT/EBITDA, particularly useful when capital structure or industry economics make P/E less informative.

### FCF valuation

Uses normalized free cash flow and an appropriate valuation multiple.

### Owner earnings

Focuses on cash economics available to owners after the reinvestment required to sustain the business.

### Historical valuation

Looks at how the company's current valuation compares with its own historical valuation characteristics.

### Relative valuation

Considers valuation relative to relevant comparable businesses/metrics.

Then explain:

> **Agent Stock selects/blends valuation approaches according to the characteristics of the company rather than blindly applying the same model to every stock.**

The exact list should match the valuation methods actually implemented.

---

# 15. Calculation Transparency

Avoid calling this “detailed reasoning,” because Agent Stock does not generate textual AI reasoning.

Better terminology:

- Calculation breakdown
- Methodology breakdown
- Valuation breakdown
- Key drivers
- Model transparency

Example:

### Moat — 92/100

**Major contributors**

- Long-term ROIC
- ROIC consistency
- Margin characteristics
- FCF economics
- Incremental capital efficiency

### Fair Value — $180–250

| Method | Estimate |
|---|---:|
| DCF | $X |
| Earnings multiple | $Y |
| FCF multiple | $Z |
| Historical | $W |

The exact metrics and methods should come from the implementation.

---

# 16. Calibration and Edge-Case Differentiation

This is potentially one of Agent Stock's strongest trust signals.

A landing-page section could say:

## Built for real companies, not textbook companies

The engine is designed/tested to account for difficult financial-data situations such as:

- One-time gains and losses
- Unusual tax releases
- Asset sales
- Acquisition goodwill
- Cyclical peaks/troughs
- Capital-intensive businesses
- Share dilution/share-count issues
- Spin-offs
- Dual-class structures
- Industry-specific financial characteristics
- REITs
- Banks
- Crypto miners

Only claim the specific cases that the current implementation actually handles and has been tested against.

The message should be:

> **Financial statements are messy. The model is designed with those edge cases in mind.**

---

# 17. 500+ Automated Tests

Use the test count as an engineering/trust signal, not as proof of investment accuracy.

Good wording:

> **500+ automated tests guard the calculation engine against financial-data and modelling edge cases.**

Avoid:

> “500+ tests guarantee accurate investment decisions.”

Testing protects calculation quality; it does not prove that an investment thesis or valuation is objectively correct.

---

# 18. Deterministic Engine as a Differentiator

This should be prominent.

Suggested message:

> ### Not an AI guess.
>
> Agent Stock's core calculations are deterministic and formula-based.
>
> The same company, the same data, and the same methodology produce reproducible results.

This distinguishes the product from simply asking an LLM:

> “Is NVIDIA a good investment?”

The proposition is:

**structured methodology + repeatable calculations + consistent application across companies.**

---

# 19. Model Integrity

Make this a visible component of the stock analysis.

### Model Integrity

**Company classification**

The classification used by the engine.

**Valuation methods used**

The valuation approaches selected for this company.

**Adjustments applied**

For example:

- One-off normalization
- Share-count adjustment
- Cyclical normalization
- Other applicable calibrations

**Data quality**

A confidence/data-quality indicator can potentially be added later.

The purpose is to answer:

> **“Why should I trust this particular valuation?”**

rather than simply:

> “What number did the algorithm produce?”

---

# 20. Potential Future Confidence Signal

A confidence indicator is a possible future enhancement rather than an existing Agent Stock feature unless already implemented.

For example:

> **Fair Value: $180–250**
>
> **Confidence: Medium**

or:

> **High model agreement**

This could communicate uncertainty and avoid false precision, particularly for cyclical, capital-intensive, or otherwise difficult businesses.

---

# 21. Core Long-Term Moat

Do not claim that the four scores themselves are the moat.

A stronger long-term defensibility story is:

### 1. Engineering moat

Calibrated deterministic logic + extensive automated testing.

### 2. Methodology moat

A coherent, transparent framework for Quality, Moat, Fair Value, and Risk/Reward.

### 3. Historical-data moat

Store years of model states and score evolution.

### 4. Workflow moat

Watchlists, comparisons, portfolio analysis, alerts, and thesis tracking.

### 5. Data/API moat

Eventually develop a proprietary historical dataset connecting:

**company → financial state → Agent Stock scores → valuation → subsequent outcomes**

That could become significantly more defensible than the initial scoring engine.

---

# 22. The Stronger Long-Term Workflow

The product can eventually become:

**Discover → Analyze → Compare → Monitor → Re-evaluate**

Example:

### Discover

“I have 40 stocks I'm interested in.”

↓

### Analyze

Agent Stock calculates the four signals.

↓

### Compare

Compare:

**NVDA vs AMD vs AVGO vs TSM vs ASML**

↓

### Monitor

Save them to a watchlist.

↓

### Re-evaluate

Agent Stock detects:

> Quality ↓  
> Fair Value ↓  
> Risk/Reward ↓

and highlights:

> **Something changed.**

This recurring workflow is more commercially valuable than a one-off “What is NVDA worth?” tool.

---

# 23. Recommended Landing Page Structure

## 1. Hero

**Find great businesses before you overpay.**

Four signals:

**Quality · Moat · Fair Value · Risk/Reward**

Ticker input:

**[ Enter ticker ] [ Analyze ]**

## 2. Instant demo

Show an actual stock analysis with the four signals.

## 3. Why four signals?

Explain how:

**Business quality + durable economics + intrinsic value + current price**

work together.

## 4. How the engine works

Explain:

- Quality methodology
- Moat methodology
- Fair Value methodology
- Risk/Reward methodology

## 5. Why Agent Stock is different

Highlight:

- Deterministic calculations
- Formula-based methodology
- Transparency
- Multiple valuation methods
- Consistent methodology
- Calibration for difficult financial-data cases
- 500+ automated tests

## 6. Model Integrity

Show:

- Methods used
- Adjustments applied
- Company classification

## 7. Investor workflow

**Analyze → Compare → Watchlist → Monitor**

## 8. CTA

> **Unlock full analysis**

## 9. Pricing

Free preview / Pro / Power.

Monthly + annual.

## 10. Checkout

Low friction and transparent.

---

# 24. Funnel Analytics

Build a simple experiment dashboard.

Example:

| Funnel stage | Variant A | Variant B | Variant C |
|---|---:|---:|---:|
| Visitors | 1,000 | 1,000 | 1,000 |
| Ticker submitted | 410 | 460 | 380 |
| Analysis viewed | 390 | 440 | 360 |
| Pricing viewed | 150 | 190 | 120 |
| Plan selected | 62 | 81 | 44 |
| Checkout started | 35 | 49 | 21 |
| Final purchase click | 18 | 29 | 11 |

Separately:

| | Pro | Power |
|---|---:|---:|
| Monthly | X | X |
| Annual | X | X |

The objective is to identify where users drop off and which positioning/offer produces the strongest paid intent.

---

# 25. Primary Success Metric

The main metric should be something like:

**Paid-intent conversion = unique visitors reaching final purchase commitment / unique visitors**

rather than:

- Email signup
- Page views
- Social followers
- Ticker searches

Those are useful funnel metrics, but they are not proof of willingness to pay.

The strongest possible validation is:

> **Actual money committed through a clearly disclosed refundable founding offer.**

---

# 26. Recommended Implementation Sequence

## Stage 1 — Smoke-test infrastructure

Build only:

- One public landing URL
- A/B/C positioning assignment
- Ticker input
- Real engine demo
- Four headline signals
- Methodology section
- Calibration section
- Pricing modal/page
- Fake checkout
- Analytics/events

Do **not** refactor the entire application yet.

## Stage 2 — Test the pitch

Keep pricing constant.

Test:

> **Find great businesses before you overpay.**

> **A second opinion for every stock you own.**

> **Your systematic stock analysis engine.**

Measure how far users progress.

## Stage 3 — Test monetization

Use the strongest positioning.

Offer:

**Pro — $14.99/mo / $149/year**

**Power — $24.99/mo / $199/year**

Measure:

- Pro vs Power
- Monthly vs annual
- Checkout starts
- Final purchase clicks

## Stage 4 — Stronger WTP validation

If the funnel looks promising:

> **Founding Investor — actual refundable commitment**

Only then begin committing significant resources to:

- Commercial financial-data licensing
- Production infrastructure
- Authentication
- Billing
- Portfolio/watchlist infrastructure
- Scalability
- Security

---

# 27. Central Pitch

A concise positioning statement for the experiment:

> **Agent Stock helps fundamental investors answer four questions about any stock:**
>
> **Is this a good business?**  
> **Does it have durable economics?**  
> **What is it worth?**  
> **Is today's price attractive enough?**
>
> **One systematic framework. Multiple valuation methods. Transparent calculations. Built to handle the messy edge cases of real financial data.**

Primary CTA:

> **Analyze your first stock →**

Then:

> **Unlock the full investment analysis →**

---

# 28. Key Terminology Recommendation

Because Agent Stock is not generating textual reasoning, avoid:

> “Detailed reasoning”

Use:

- **Calculation breakdown**
- **Methodology breakdown**
- **Valuation breakdown**
- **Key drivers**
- **Model transparency**

This is more accurate and also reinforces the product's core trust proposition.

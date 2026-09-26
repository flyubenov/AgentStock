/** Copy for the "How Intrinsica works" section (spec 5.4). It lives here rather
 *  than in Framework.tsx for one reason: the spec requires the four detail
 *  panels to be *identical in shape*, and a shape requirement can only be
 *  enforced against data. framework.test.ts asserts the key list itself, so an
 *  assessment that quietly grows a field or loses one fails the build.
 *
 *  Two standing rules govern every string below (spec section 8):
 *  never the word "signal" — it is an *assessment*; and never "Risk/Reward" —
 *  it is "Reward / Risk" or "Reward ÷ Risk".
 *
 *  Weights, point maxima and the outcome bands a finished score falls into are
 *  public (spec 5.4 item 4). The per-metric cut-offs that produce those scores
 *  are NOT: nothing here may say what value earns what points. */

export interface AssessmentGroup {
  title: string
  weight: string
  metrics: string
  hi: string
  lo: string
}

export interface AssessmentContent {
  name: string
  color: string
  question: string
  scale: string
  what: string
  hiLabel: string
  loLabel: string
  groups: AssessmentGroup[]
  note: string
}

export interface Calibration {
  name: string
  summary: string
  when: string
  effect: string
  affects: string[]
  guarded: boolean
  example?: string
}

/** Ordered and coloured to match Hero's ASSESSMENTS exactly — the array index is
 *  the `AssessmentId` the hero cards, the breakdown tab strip and these cards
 *  all share. framework.test.ts pins the two lists together. */
export const FRAMEWORK: AssessmentContent[] = [
  {
    name: 'Quality', color: 'var(--q)',
    question: 'How strong is the underlying business?',
    scale: '0–10 · sector-aware',
    what: 'A composite of the fundamentals that make a business good, weighted to the sector profile of the company.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Growth & Margins', weight: '35% of the score · 7 metrics',
        metrics: 'Revenue / EPS / FCF growth (3-yr) · operating & gross margin · margin trend · FCF margin',
        hi: 'revenue compounds and margins hold or widen while it does.',
        lo: 'growth stalls, or margins slide to pay for it.' },
      { title: 'Returns on Capital', weight: '30% of the score · 4 metrics',
        metrics: 'ROIC (trailing & 5-yr) · ROIC − WACC spread · return on tangible equity',
        hi: 'the business earns well above what its capital costs, year after year.',
        lo: 'returns merely match the cost of capital.' },
      { title: 'Balance-Sheet Strength', weight: '15% of the score · 3 metrics',
        metrics: 'Net debt / EBITDA · net debt / FCF · operating cash flow / capex',
        hi: 'little net debt, with cash flow covering capex several times over.',
        lo: 'leverage that depends on the cycle staying friendly.' },
      { title: 'Shareholder Alignment', weight: '20% of the score · 5 metrics',
        metrics: 'Share-count trend · stock comp % of revenue · earnings quality (FCF / net income) · insider ownership · shareholder yield',
        hi: 'a shrinking share count, modest stock comp, earnings that arrive as cash.',
        lo: 'steady dilution, or earnings that never become cash.' },
    ],
    note: 'Every metric is scored against fixed thresholds and averaged inside its category; the categories are then weighted by profile — Tech / Growth (shown), Balanced, Defensive / Income, Industrial / Cyclical, Financials, REIT. As a rough read: 9+ is top-decile, 8–9 excellent, 7–8 strong, below 5 weak.',
  },
  {
    name: 'Moat', color: 'var(--mo)',
    question: 'How durable are its competitive advantages?',
    scale: '0–100',
    // Deliberately says what this is NOT without naming a moat source the engine
    // cannot measure — see framework.test.ts, "names no moat source it cannot
    // measure". Nothing here claims to read network effects or switching costs.
    what: 'Durability of economic profit — how consistently the business out-earns its cost of capital. Not a narrative or reputation score.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Magnitude', weight: '40 of 100 points',
        metrics: 'ROIC level (up to 20 pts) · economic spread, ROIC − WACC (up to 20 pts)',
        hi: 'returns far above the cost of capital.',
        lo: 'returns that merely match it.' },
      { title: 'Durability', weight: '50 of 100 points',
        metrics: 'Persistence of economic profit (25 pts) · consistency of returns (10 pts) · margin durability (15 pts)',
        hi: 'a decade of above-cost returns, with margins that hold.',
        lo: 'a good couple of years inside a cyclical swing.' },
      { title: 'Cash-backing', weight: '10 of 100 points',
        metrics: 'Free-cash-flow conversion (10 pts)',
        hi: 'profit that turns into cash.',
        lo: 'profit that never leaves the income statement.' },
    ],
    note: 'Points add up to the 0–100 score: roughly 80+ reads as a wide moat, 60–79 established, 40–59 narrow, below 40 little or none. An economic-profit gate caps any company that does not out-earn its cost of capital.',
  },
  {
    name: 'Fair Value', color: 'var(--fv)',
    question: 'What is a share actually worth?',
    scale: '$ per share',
    what: 'An estimate of what one share is worth judged on the fundamentals of the business itself — its cash flows, earnings and assets — rather than on what the market happens to be paying today. Comparing that estimate with the live price is what tells you whether the stock looks cheap or expensive.',
    // Fair Value has no score to be high or low: a method is weighted up or down
    // in the blend. Same panel shape, different vocabulary (spec 5.4 item 3).
    hiLabel: 'Weighted up', loLabel: 'Weighted down',
    groups: [
      { title: 'Cash-flow models', weight: 'typically 40–60% of the blend',
        metrics: 'Discounted cash flow · free cash flow to equity',
        hi: 'cash flows are established and predictable — the anchor for most profitable businesses.',
        lo: 'cash flows are erratic, or the company is pre-profit.' },
      { title: 'Earnings multiples', weight: 'typically 20–40%',
        metrics: 'EV / EBITDA · P / E (forward earnings when trailing ones are distorted)',
        hi: 'profits are meaningful and comparable across peers.',
        lo: 'earnings are negative, or distorted by acquisition amortization.' },
      { title: 'Sales multiples', weight: '0–20%',
        metrics: 'EV / Sales',
        hi: 'a fast-growing company is not earning yet.',
        lo: 'the company is mature and profitable.' },
      { title: 'Income & asset models', weight: '0–60%',
        metrics: 'Dividend discount · price / book · residual income · net asset value',
        hi: 'the company is a dividend payer, a lender or asset-heavy.',
        lo: 'the business is asset-light.' },
    ],
    note: 'The company is classified first, and the classification sets the blend — a mega cap leans on cash-flow models plus EV / EBITDA, a bank on price / book plus residual income, an asset-heavy name on net asset value. Every analysis shows the exact blend it used and what each method returned.',
  },
  {
    name: 'Reward / Risk', color: 'var(--rr)',
    question: 'Is the price today worth the downside?',
    scale: 'ratio · 0.2–5.0×',
    what: 'Connects intrinsic value to the live market price and the downside — a great business is not automatically a great investment at any price.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Reward axis', weight: '6 factors · scored 1–5',
        metrics: 'Discount to 52-week high (24%) · valuation (18%) · growth (18%) · RSI (16%) · profitability (12%) · analyst upside (8–18%, weighted by how many analysts agree)',
        hi: 'a growing, profitable business is trading well below its highs.',
        lo: 'the price is full, with little left to re-rate.' },
      // The direction has to be stated outright, exactly as the breakdown
      // panel's own risk axis does: on this one category a high score is bad.
      { title: 'Risk axis · a high score here is the bad one', weight: '6 factors · scored 1–5',
        metrics: 'Volatility (22%) · leverage (18%) · trend vs 200-day (18%) · burn / margin (15%) · beta (15%) · liquidity (12%)',
        hi: 'leverage and volatility stack up.',
        lo: 'light debt, a steady price, a business that funds itself.' },
    ],
    note: 'Reward ÷ risk, clamped to 0.2–5.0×. Roughly: 2.0× and above is Asymmetric Upside, 1.3–2.0× Reward-Favored, 0.8–1.3× Balanced, 0.5–0.8× Risk-Favored, below that a Value Trap.',
  },
]

/** The framework section's overview card (variant D3, user decision 2026-09-26): two
 *  sentences and the judgment note, side by side. The rest of the "how" lives in the
 *  tabbed detail panel beneath it, so the card does not repeat it. The calibration
 *  count in the lead is rendered from CALIBRATIONS.length, never written here. */
export const OVERVIEW = {
  lead: {
    before: 'Four separate engines turn the latest fundamentals into four scores, using explicit formulas and',
    bold: 'data-triggered calibrations',
    after: 'Same data, same score.',
  },
  /** Said plainly because it is true: three of the four assessments are judgments,
   *  not quantities with a correct value. Intrinsica's scores are the product of its
   *  own methodology, and the page's transparency is what makes that honest. */
  judgment: {
    title: 'A methodology, not a measurement.',
    body: 'Quality, Moat and Reward/Risk have no single correct formula. Intrinsica’s weights are its judgment — all on the page, so you can disagree.',
  },
  tail: 'Click an assessment for every category, weight and calibration.',
}

/** The hero's pipeline strip: what goes in, what Intrinsica adds, what comes out.
 *  The last step names the four assessments set directly beneath it. */
export const PIPELINE = [
  'Dozens of fundamentals',
  'Intrinsica methodology · weights & calibrations',
  'Four scores',
] as const

/** `affects` holds assessment NAMES, matched against FRAMEWORK rather than an
 *  index, so a reordered FRAMEWORK cannot silently re-point a calibration at the
 *  wrong panel. `guarded: true` is a claim about the engine — the adjustment is
 *  one-directional and can only correct a distortion, never inflate a score. */
export const CALIBRATIONS: Calibration[] = [
  { name: 'Tangible-ROIC (ex-goodwill)', summary: 'Capital efficiency without acquisition goodwill.',
    when: 'Only when goodwill & intangibles are a large share of invested capital, tangible ROIC is higher than reported, and trailing earnings are amortization-depressed.',
    effect: 'ROIC is scored on tangible invested capital, so a past acquisition is not misread as poor capital efficiency.',
    affects: ['Quality', 'Moat'], guarded: true, example: 'AMD after the Xilinx acquisition.' },
  { name: 'Forward-EPS swap', summary: 'Forward earnings when trailing EPS is depressed.',
    when: 'Only when trailing P/E runs far above forward P/E — trailing GAAP earnings depressed by amortization or a one-off trough.',
    effect: 'The P/E leg and the EPS-growth metric use forward (normalized) earnings.',
    affects: ['Fair Value', 'Quality'], guarded: true, example: 'AVGO after the VMware acquisition.' },
  { name: 'Heavy-capex FCF exclusion', summary: 'Ignores FCF metrics when capex is deliberately consuming cash.',
    when: 'Only when a profitable company’s trailing FCF is a tiny fraction of EBITDA due to heavy reinvestment.',
    effect: 'FCF-derived metrics are excluded; the balance sheet is judged on EBITDA leverage.',
    affects: ['Quality'], guarded: true, example: 'A hyperscaler during a data-centre build-out.' },
  { name: 'Financials basis', summary: 'Return-on-equity & book-value methods for lenders.',
    when: 'Automatically for banks, lenders and insurers.',
    effect: 'Moat uses ROTE vs cost of equity; Fair Value uses P/B + residual income; metrics that do not fit a lender are excluded.',
    affects: ['Quality', 'Moat', 'Fair Value'], guarded: false },
  { name: 'De-financialization', summary: 'Re-classifies miners & payment networks mis-tagged "Financial Services".',
    when: 'When a Financial-Services name is really a crypto miner, data-centre operator or asset-light payment network with no loan book.',
    effect: 'Book-value methods are dropped; the company is valued by the rules that fit it.',
    affects: ['Fair Value'], guarded: false },
  { name: 'Dominant fresh-acquisition', summary: 'Handles a just-closed deal that dominates the balance sheet.',
    when: 'When goodwill & intangibles are the overwhelming majority of invested capital right after a large acquisition.',
    effect: 'Amortization-depressed margin and mismatched leverage are excluded.',
    affects: ['Quality'], guarded: true, example: 'Synopsys after the Ansys deal.' },
  { name: 'Cyclical normalization', summary: 'Normalizes peak/trough earnings.',
    when: 'For cyclical sectors (energy, materials) or names that trade like cyclicals.',
    effect: 'Earnings are normalized across the cycle and confidence in the valuation is lowered.',
    affects: ['Fair Value', 'Reward / Risk'], guarded: false },
  { name: 'Economic-profit gate', summary: 'Caps the moat of businesses that do not beat their cost of capital.',
    when: 'When returns do not exceed cost of capital.',
    effect: 'The moat score is capped — no durable advantage without economic profit.',
    affects: ['Moat'], guarded: false },
  { name: 'Unprofitable cap & pre-profit path', summary: 'Growth + cash-runway scoring for pre-profit names, capped.',
    when: 'When net income or free cash flow is negative.',
    effect: 'Quality is capped and, for operating losses, blended with a Rule-of-40 + cash-runway read.',
    affects: ['Quality'], guarded: false },
  { name: 'Analyst-confidence weighting', summary: 'Weights the analyst-upside factor by coverage & agreement.',
    when: 'When a stock has analyst coverage.',
    effect: 'The analyst-upside factor counts for more when many analysts cover it and agree.',
    affects: ['Reward / Risk'], guarded: false },
  { name: 'Statement-corroboration guard', summary: 'Cross-checks growth and burn against annual statements.',
    when: 'For capex-heavy names where quarterly figures understate the annual reality.',
    effect: 'Growth & burn factors are overridden by the annual statement only when it reads materially better — never worse.',
    affects: ['Reward / Risk'], guarded: true },
]

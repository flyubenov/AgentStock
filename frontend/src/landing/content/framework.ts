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
  /** One plain line under the title, shown on the closed row. */
  question: string
  /** Shown on the closed row: '35%', '40%', 'typically 40–60%', '6 factors · scored 1–5'. */
  weight: string
  /** The fixed share behind the row's mini bar (Quality and Moat, in %); null for ranges. */
  share: number | null
  /** One chip each. */
  metrics: string[]
  /** A few words each, after ▲ High / ▼ Low. */
  hi: string
  lo: string
}

export interface AssessmentContent {
  name: string
  color: string
  question: string
  scale: string
  what: string
  /** 'High' / 'Low' (Fair Value: 'Weighted up' / 'Weighted down'). */
  hiLabel: string
  loLabel: string
  groups: AssessmentGroup[]
  /** The scale strip's cells, worst → best; empty for Fair Value, which has no score. */
  bands: string[]
  /** The one line under the strip. */
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
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Growth & Margins', question: 'Is it growing — and profitably?', weight: '35%', share: 35,
        metrics: ['Revenue growth (3-yr)', 'EPS growth (3-yr)', 'FCF growth (3-yr)', 'Operating margin', 'Gross margin', 'Margin trend', 'FCF margin'],
        hi: 'compounding revenue, margins holding', lo: 'stalled growth, margins sliding' },
      { title: 'Returns on Capital', question: 'Does it earn more than its capital costs?', weight: '30%', share: 30,
        metrics: ['ROIC (trailing)', 'ROIC (5-yr)', 'ROIC − WACC spread', 'Return on tangible equity'],
        hi: 'well above its cost of capital', lo: 'barely matches it' },
      { title: 'Balance-Sheet Strength', question: 'Can it weather a bad year?', weight: '15%', share: 15,
        metrics: ['Net debt / EBITDA', 'Net debt / FCF', 'Operating cash flow / capex'],
        hi: 'little debt, capex easily funded', lo: 'leverage that needs a kind cycle' },
      { title: 'Shareholder Alignment', question: 'Are owners treated well?', weight: '20%', share: 20,
        metrics: ['Share-count trend', 'Stock comp % of revenue', 'Earnings quality (FCF / net income)', 'Insider ownership', 'Shareholder yield'],
        hi: 'buybacks, earnings that arrive as cash', lo: 'steady dilution, paper earnings' },
    ],
    bands: ['below 5 · Weak', '5–7 · Moderate', '7–8 · Strong', '8–9 · Excellent', '9+ · Top-decile'],
    note: 'Each metric is scored against fixed thresholds; the category weights follow the sector profile (Tech / Growth shown).',

  },
  {
    name: 'Moat', color: 'var(--mo)',
    question: 'How durable are its competitive advantages?',
    scale: '0–10',
    // Deliberately says what this is NOT without naming a moat source the engine
    // cannot measure — see framework.test.ts, "names no moat source it cannot
    // measure". Nothing here claims to read network effects or switching costs.
    what: 'Durability of economic profit — how consistently the business out-earns its cost of capital. Not a narrative or reputation score.',
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Magnitude', question: 'How far above its cost of capital does it earn?', weight: '40%', share: 40,
        metrics: ['ROIC level (20%)', 'Economic spread, ROIC − WACC (20%)'],
        hi: 'returns far above the cost of capital', lo: 'returns that merely match it' },
      { title: 'Durability', question: 'Does the edge last, year after year?', weight: '50%', share: 50,
        metrics: ['Persistence of economic profit (25%)', 'Consistency of returns (10%)', 'Margin durability (15%)'],
        hi: 'a decade of above-cost returns, margins that hold', lo: 'a good spell inside a cyclical swing' },
      { title: 'Cash-backing', question: 'Does the profit turn into cash?', weight: '10%', share: 10,
        metrics: ['Free-cash-flow conversion (10%)'],
        hi: 'profit that becomes cash', lo: 'profit that stays on paper' },
    ],
    bands: ['below 4 · Little or none', '4–6 · Narrow', '6–8 · Established', '8+ · Wide'],
    note: 'An economic-profit gate caps any company that does not out-earn its cost of capital.',

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
      { title: 'Cash-flow models', question: 'What will the business pay out over time?', weight: 'typically 40–60%', share: null,
        metrics: ['Discounted cash flow', 'Free cash flow to equity'],
        hi: 'steady, predictable cash flows', lo: 'erratic cash flows, or pre-profit' },
      { title: 'Earnings multiples', question: 'How is it priced against its earnings?', weight: 'typically 20–40%', share: null,
        metrics: ['EV / EBITDA', 'P / E (forward earnings when trailing ones are distorted)'],
        hi: 'meaningful profits, comparable with peers', lo: 'losses, or earnings distorted by amortization' },
      { title: 'Sales multiples', question: 'What is growth worth before profit?', weight: '0–20%', share: null,
        metrics: ['EV / Sales'],
        hi: 'fast growth, no profit yet', lo: 'a mature, profitable company' },
      { title: 'Income & asset models', question: 'What do its dividends or assets say?', weight: '0–60%', share: null,
        metrics: ['Dividend discount', 'Price / book', 'Residual income', 'Net asset value'],
        hi: 'dividend payers, lenders, asset-heavy names', lo: 'asset-light businesses' },
    ],
    bands: [],
    note: 'The company’s type sets the blend — a bank leans on price / book, a mega cap on cash flows. Every analysis shows the exact blend it used.',

  },
  {
    name: 'Reward / Risk', color: 'var(--rr)',
    question: 'Is the price today worth the downside?',
    scale: 'ratio · 0.2–5.0×',
    what: 'Connects intrinsic value to the live market price and the downside — a great business is not automatically a great investment at any price.',
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Reward axis', question: 'How much upside is left?', weight: '6 factors · scored 1–5', share: null,
        metrics: ['Discount to 52-week high (24%)', 'Valuation (18%)', 'Growth (18%)', 'RSI (16%)', 'Profitability (12%)',
                  'Analyst upside (8–18%, weighted by how many analysts agree)'],
        hi: 'a growing business well below its highs', lo: 'a full price, little left to re-rate' },
      // The direction has to be stated outright, exactly as the breakdown
      // panel's own risk axis does: on this one category a high score is bad.
      { title: 'Risk axis · a high score here is the bad one', question: 'How much can go wrong?', weight: '6 factors · scored 1–5', share: null,
        metrics: ['Volatility (22%)', 'Leverage (18%)', 'Trend vs 200-day (18%)', 'Burn / margin (15%)', 'Beta (15%)', 'Liquidity (12%)'],
        hi: 'leverage and volatility stacking up', lo: 'light debt, a steady price, self-funded' },
    ],
    bands: ['below 0.5× · Value Trap', '0.5–0.8× · Risk-Favored', '0.8–1.3× · Balanced', '1.3–2.0× · Reward-Favored', '2.0×+ · Asymmetric Upside'],
    note: 'Reward ÷ risk, clamped to 0.2–5.0×.',
  },
]

/** The framework section's overview card (variant D3, user decision 2026-09-26): a
 *  two-sentence lead, then the judgment note as a second paragraph (option B,
 *  2026-09-27 — its original, fuller wording restored). The rest of the "how" lives in the
 *  tabbed detail panel beneath it, so the card does not repeat it. The calibration
 *  count in the lead is rendered from CALIBRATIONS.length, never written here. */
export const OVERVIEW = {
  lead: {
    before: 'Four separate engines turn the latest fundamentals into four scores, using explicit formulas and',
    bold: 'data-triggered calibrations',
    after: 'Same data, same score.',
  },
  /** Said plainly because it is true: three of the four assessments are judgments,
   *  not quantities with a correct value. Reworded 2026-09-29 (user decision): the
   *  old "no single agreed way" read as if Intrinsica had no settled method, so the
   *  note now states the method as fixed — the same for every company. */
  judgment: {
    title: 'Intrinsica’s own method.',
    body: 'Quality, Moat and Reward/Risk aren’t printed in any filing; they have to be assessed. ' +
      'Intrinsica assesses them with one fixed methodology: it takes the fundamentals that matter for each, ' +
      'weights them and condenses them into a single score, the same way for every company. ' +
      'Each score opens up to the inputs and weights behind it.',
  },
  tail: 'Click an assessment for every category, weight and calibration.',
}

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

/** The band before the Framework (spec 5.4, hero rework 2026-09-27): the investor's
 *  question, then how Intrinsica answers it. */
export const QUESTION_BAND = {
  title: 'Is it a good business, at a good price?',
  body: 'Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show.',
} as const

/** Labels over the Framework tabs, one per pair in FRAMEWORK order: Quality + Moat
 *  answer the first, Fair Value + Reward / Risk the second. */
export const TAB_PAIRS = ['Is it a good business?', 'At a good price?'] as const

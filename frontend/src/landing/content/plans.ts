/** Copy for the pricing section (spec 5.7). It lives here rather than in
 *  Pricing.tsx for the same reason the framework copy lives in framework.ts: the
 *  plan matrix is a table that has to agree with itself, and agreement can only
 *  be enforced against data. plans.test.ts recomputes every derived price string
 *  from the two raw numbers, so a price changed in one place and not the other
 *  three fails the build.
 *
 *  Four rules govern every string below:
 *
 *  1. Spec section 8: never the word "signal" — it is an *assessment*; and the
 *     label is "Reward / Risk", spelled exactly as `FRAMEWORK[3].name` spells it.
 *  2. No scoring cut-offs. There is no outcome band in this file either — plan
 *     allowances are the only numbers here, and an allowance is not a score.
 *  3. No invented urgency. No countdown, no seat count, no "limited time". This
 *     page is a smoke test measuring genuine willingness to pay, and
 *     manufactured pressure corrupts the very number it exists to collect.
 *  4. Free is described honestly (spec 5.7): every analysis is complete and
 *     nothing is blurred, but volume, watchlists, history and discovery are
 *     capped. It is never "the full product".
 *
 *  The Free caps are not aspirational: `~5 analyses a month` is demoLimit.ts's
 *  own allowance and `3 tickers per run` is the backend's per-run cap. The hero
 *  free-note quotes both as well. One pair of numbers, four places, and
 *  plans.test.ts derives its assertion from the constants rather than retyping
 *  them.
 *
 *  Every string the pricing section renders is here, including the two that
 *  used to sit in Pricing.tsx: the billing toggle's `save ~17%` tag (a pricing
 *  number, and a pricing number in a component is one no data test can reach)
 *  and the three who-it-is-for cards. */

export type Billing = 'annual' | 'monthly'

/** The annual band. `yearly` is the raw number — what one year actually costs —
 *  and `sub` is the copy that quotes it. Keeping the number rather than parsing
 *  it back out of the sentence is what lets `totalFor` name a year's total
 *  without a regex that can quietly match nothing. plans.test.ts pins the two
 *  against each other and against the effective monthly price. */
export interface AnnualBand {
  effective: string
  yearly: number
  sub: string
}

export interface Plan {
  name: 'Free' | 'Pro' | 'Unlimited'
  title: string
  forLine: string
  featured?: boolean
  cta: string
  /** Absent on Free, which costs nothing on either period. */
  annual?: AnnualBand
  monthly?: { effective: string; sub: string }
  features: string[]
}

export interface CompareRow {
  label: string
  /** Shown inline beneath the label. Deliberately not a `title` attribute: a
   *  hover tooltip is invisible on a phone and unreachable from a keyboard. */
  note?: string
  values: [string, string, string]
  /** Which cells the mock highlights green, per plan. Explicit rather than
   *  inferred from the value: the mock lights Unlimited's "Yes" for monitoring
   *  but not Pro's "Yes" for charts. */
  on?: [boolean, boolean, boolean]
}

export const PLANS: Plan[] = [
  {
    name: 'Free',
    title: 'Try Intrinsica',
    forLine: 'Full-depth analysis, small volume.',
    cta: 'Start free',
    features: [
      '~5 full-depth analyses / month',
      'Every analysis complete — Quality, Moat, Fair Value & Reward/Risk with the full breakdown, nothing blurred',
      'Up to 3 tickers per analysis run',
      '1 watchlist, up to 5 stocks',
      '6 months of score history (2 quarters)',
      'Discovery: see the filters, results locked',
    ],
  },
  {
    name: 'Pro',
    title: 'Deep Stock Analysis',
    forLine: 'Unlimited analysis & your research workflow.',
    featured: true,
    cta: 'Choose Pro',
    annual: { effective: '$18.00', yearly: 216,
              sub: 'billed annually · $216/yr · save 18%' },
    monthly: { effective: '$21.99', sub: 'billed monthly · $21.99/mo' },
    features: [
      'Everything in Free (same full depth), plus:',
      'Unlimited analyses — no monthly cap',
      'Up to 10 tickers per analysis run · side-by-side breakdown of 3',
      '5–10 watchlists of 50 stocks · ~2 years of score history & charts',
      'Score-change alerts (10–20) · CSV / PDF export · basic portfolio analysis',
    ],
  },
  {
    name: 'Unlimited',
    title: 'Discover, Monitor & Automate at Scale',
    forLine: 'Automated, systematic research across your universe.',
    cta: 'Choose Unlimited',
    annual: { effective: '$25.00', yearly: 300,
              sub: 'billed annually · $300/yr · save 17%' },
    monthly: { effective: '$29.99', sub: 'billed monthly · $29.99/mo' },
    features: [
      'Everything in Pro, plus:',
      'Bulk / parallel analysis — 25, 50, 100+ tickers in one run',
      'Screen on Quality/Moat/FV/Reward/Risk across hundreds of stocks',
      'Unlimited watchlists · advanced portfolio analysis',
      'Full score-history evolution & “What Changed?”',
      'Automated monitoring · unlimited alerts · bulk exports',
    ],
  },
]

/** The card price: effective-monthly headline, with the period detail beneath
 *  (spec 5.7). Free costs nothing on either period, so it answers the same way
 *  for both rather than pretending to have an annual band. */
export function priceFor(plan: Plan, billing: Billing): { headline: string; sub: string } {
  if (plan.name === 'Free') return { headline: '$0', sub: 'No card, ever' }
  const band = billing === 'annual' ? plan.annual! : plan.monthly!
  return { headline: band.effective, sub: band.sub }
}

export interface Period {
  id: Billing
  label: string
  /** Annual only. Bounded by Pricing.test.tsx, off the rendered button: the
   *  toggle may never advertise more than the smallest saving a paid plan
   *  really offers. It lives here rather than in Pricing.tsx because it is a
   *  pricing number, and a pricing number written in a component is one no data
   *  test can reach. */
  save?: string
}

export const PERIODS: Period[] = [
  { id: 'annual', label: 'Annual', save: 'save ~17%' },
  { id: 'monthly', label: 'Monthly' },
]

/** What the checkout (Task 14) names as the total for a chosen plan and period.
 *  Derived from the same PLANS entries the cards render, so the checkout can
 *  never quote a figure the card did not show.
 *
 *  The unknown-plan branch is separate from Free on purpose. The checkout reads
 *  its plan from `?plan=`, which any visitor can edit, and folding an
 *  unrecognised name into the Free branch would answer `/checkout?plan=Bogus`
 *  with "$0 — free plan": a page telling a visitor something false about money.
 *  It says nothing about price instead, and the caller sends the reader back to
 *  the plans. */
export function totalFor(planName: string, billing: Billing): string {
  const plan = PLANS.find(p => p.name === planName)
  if (!plan) return 'No plan selected'
  if (plan.name === 'Free') return '$0 — free plan'
  if (billing === 'monthly') return `${plan.monthly!.effective} / month`
  return `$${plan.annual!.yearly} / year (${plan.annual!.effective}/mo)`
}

/** The three "who it is for" cards above the matrix (spec 5.7). Copy, so it
 *  lives with the rest of the copy: each card restates one plan's promise, and
 *  a restatement kept in a different file from the thing it restates drifts.
 *  `tag` opens with the plan name, in PLANS order — plans.test.ts pins that. */
export interface Audience {
  tag: string
  title: string
  who: string
  focus: string
}

export const WHO: Audience[] = [
  {
    tag: 'Free · Try',
    title: 'Experience the framework',
    who: 'For the curious investor judging the framework on stocks they already know.',
    focus: 'every analysis is complete and nothing is blurred — but volume, watchlists, history and discovery are capped.',
  },
  {
    tag: 'Pro · Depth',
    title: 'Deep individual research',
    who: 'For the serious individual investor researching the stocks they care about.',
    focus: 'unlimited analysis on the names you pick, plus your research workflow.',
  },
  {
    tag: 'Unlimited · Scale',
    title: 'Systematic & automated',
    who: 'For investors scanning & monitoring a whole universe or portfolio.',
    focus: 'discover across the market and let Intrinsica monitor it for you.',
  },
]

/** The canonical plan matrix (spec 5.7). Two resolutions are encoded here:
 *
 *  - Compare is split in two. "Tickers per analysis run" is the results grid
 *    (3 / 10 / 100+); "Side-by-side breakdown" is a separate view capped at 3 by
 *    screen width. This replaces the undeliverable "5–10 side by side".
 *  - The first two rows are identical across all three plans on purpose. That is
 *    the product's central claim — the depth never changes, only the volume and
 *    the automation — so a matrix where they differed would be selling something
 *    else. plans.test.ts pins those two as the only uniform rows. */
export const COMPARE_ROWS: CompareRow[] = [
  { label: 'Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk)',
    values: ['Full', 'Full', 'Full'], on: [true, true, true] },
  { label: 'Breakdown, methodology & calibrations',
    values: ['Full', 'Full', 'Full'], on: [true, true, true] },
  { label: 'Analyses per month',
    values: ['~5', 'Unlimited', 'Unlimited'] },
  { label: 'Tickers per analysis run',
    note: 'They come back in one results grid, ranked side by side',
    values: ['3', '10', '100+ (bulk)'], on: [false, false, true] },
  { label: 'Side-by-side breakdown',
    note: 'Full factor tables of 3 companies in one view',
    values: ['—', 'Up to 3', 'Up to 3'], on: [false, true, true] },
  { label: 'Watchlists', values: ['1', '5–10', 'Unlimited'] },
  { label: 'Stocks per watchlist', values: ['5', '50', 'Unlimited'] },
  { label: 'Portfolio analysis', values: ['—', 'Basic', 'Advanced'] },
  { label: 'Score history', values: ['6 months', '~2 years', 'Full history'] },
  { label: 'Score-history charts', values: ['6 months', 'Yes', 'Advanced'] },
  { label: 'Bulk / parallel analysis', values: ['—', '—', 'Yes'], on: [false, false, true] },
  { label: 'Discovery — screen on Quality/Moat/FV/Reward/Risk',
    note: 'Preview = the filters are visible, running them is locked',
    values: ['Preview', 'Preview', 'Full'], on: [false, false, true] },
  { label: 'Full stock universe', values: ['Preview', 'Preview', 'Yes'], on: [false, false, true] },
  { label: 'Score-change alerts',
    note: 'You are told when a score crosses a threshold you set',
    values: ['—', '10–20', 'Unlimited'] },
  { label: 'Automated monitoring',
    note: 'Intrinsica re-runs your watchlists on a schedule, unprompted',
    values: ['—', '—', 'Yes'], on: [false, false, true] },
  { label: '“What Changed?”',
    note: 'Which factor moved a score, this run versus the last',
    values: ['—', '—', 'Yes'], on: [false, false, true] },
  { label: 'Exports', values: ['—', 'CSV / PDF', 'Bulk'] },
]

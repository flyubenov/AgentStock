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
 *  own allowance and `3 tickers per run` is the backend's per-run cap. One pair
 *  of numbers, several places, and
 *  plans.test.ts derives its assertion from the constants rather than retyping
 *  them.
 *
 *  Every string the pricing section renders is here, including the two that
 *  used to sit in Pricing.tsx: the billing toggle's `save ~17%` tag (a pricing
 *  number, and a pricing number in a component is one no data test can reach). */

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
  /** The refund promise printed under a paid plan's button. Absent on Free,
   *  which takes no money to refund. It is a promise the real launch must keep,
   *  so it is written once here and nowhere else. */
  guarantee?: string
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
    forLine: 'For the curious investor judging the framework on stocks they already know.',
    cta: 'Start free',
    features: [
      'Every analysis complete — nothing blurred',
      '~5 analyses a month · up to 3 tickers per run',
      '1 watchlist of 5 · 6 months of score history',
    ],
  },
  {
    name: 'Pro',
    title: 'Deep Stock Analysis',
    forLine: 'For the serious individual investor researching the stocks they care about.',
    featured: true,
    cta: 'Choose Pro',
    guarantee: '7-day money-back guarantee',
    annual: { effective: '$18.00', yearly: 216,
              sub: 'billed annually · $216/yr · save 18%' },
    monthly: { effective: '$21.99', sub: 'billed monthly · $21.99/mo' },
    features: [
      'Unlimited analyses — no monthly cap',
      'Up to 10 tickers per run · side-by-side breakdown of 3',
      'Watchlists, ~2 years of history, alerts & exports',
    ],
  },
  {
    name: 'Unlimited',
    title: 'Discover & Automate at Scale',
    forLine: 'For investors scanning & monitoring a whole universe or portfolio.',
    cta: 'Choose Unlimited',
    guarantee: '7-day money-back guarantee',
    annual: { effective: '$25.00', yearly: 300,
              sub: 'billed annually · $300/yr · save 17%' },
    monthly: { effective: '$29.99', sub: 'billed monthly · $29.99/mo' },
    features: [
      'Bulk runs — 100+ tickers in one run, results stream in as each finishes',
      'Screen hundreds of stocks on all four scores',
      'Automated monitoring, unlimited alerts & “What Changed?”',
    ],
  },
]

/** The card price: effective-monthly headline, with the period detail beneath
 *  (spec 5.7). Free costs nothing on either period, so it answers the same way
 *  for both rather than pretending to have an annual band. */
export function priceFor(plan: Plan, billing: Billing): { headline: string; sub: string } {
  if (plan.name === 'Free') return { headline: '$0', sub: 'No sign-up · no card, ever' }
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

/** The canonical plan matrix (spec 5.7). Two resolutions are encoded here:
 *
 *  - Compare is split in two. "Tickers per run" is the results grid
 *    (3 / 10 / 100+); "Side-by-side breakdown" is a separate view capped at 3 by
 *    screen width. This replaces the undeliverable "5–10 side by side".
 *  - Tickers per run is the ONLY run-size limit (user decision 2026-09-27). How
 *    many tickers are analyzed at the same moment is a server setting shared by
 *    every plan (orchestrator/batch.py runs a pool of 3, bounded by the data
 *    source's rate limit), so it is never sold as a plan feature — the old "Bulk /
 *    parallel analysis" row claimed Unlimited ran 100+ at once, which it does not.
 *    Re-checking a watchlist runs the whole list regardless of this cap.
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
  { label: 'Tickers per run',
    note: 'How many you can enter in one go. Re-checking a watchlist always runs the whole list',
    values: ['3', '10', '100+ (bulk)'], on: [false, false, true] },
  { label: 'Side-by-side breakdown',
    note: 'Full factor tables of 3 companies in one view',
    values: ['—', 'Up to 3', 'Up to 3'], on: [false, true, true] },
  { label: 'Watchlists', values: ['1', '5–10', 'Unlimited'] },
  { label: 'Stocks per watchlist', values: ['5', '50', 'Unlimited'] },
  { label: 'Portfolio analysis', values: ['—', 'Basic', 'Advanced'] },
  { label: 'Score history', values: ['6 months', '~2 years', 'Full history'] },
  { label: 'Score-history charts', values: ['6 months', 'Yes', 'Advanced'] },
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

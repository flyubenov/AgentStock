import { describe, it, expect } from 'vitest'
import { PLANS, COMPARE_ROWS, PERIODS, WHO, priceFor, totalFor } from './plans'
import { DEMO_RUN_LIMIT } from '../demoLimit'
import { MAX_TICKERS } from '../components/Hero'

/** The pricing copy is data for the same reason the framework copy is: the plan
 *  matrix has to agree with itself. The card prices, the annual totals, the
 *  advertised saving and the checkout total are four views of two numbers, and
 *  four hand-written views of two numbers drift.
 *
 *  The arithmetic tests below are the point of this file. Changing one price
 *  without changing the three strings derived from it fails here rather than
 *  shipping a card that says "$18.00/mo · $216/yr" beside a checkout that
 *  charges something else. */

const ALL_LABELS = [
  'Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk)',
  'Breakdown, methodology & calibrations',
  'Analyses per month',
  'Tickers per analysis run',
  'Side-by-side breakdown',
  'Watchlists',
  'Stocks per watchlist',
  'Portfolio analysis',
  'Score history',
  'Score-history charts',
  'Bulk / parallel analysis',
  'Discovery — screen on Quality/Moat/FV/Reward/Risk',
  'Full stock universe',
  'Score-change alerts',
  'Automated monitoring',
  '“What Changed?”',
  'Exports',
]

/** The whole matrix, one ordered triple per row, positionally aligned with
 *  ALL_LABELS above.
 *
 *  ALL_LABELS pinned the rows; only column 0 was ever pinned to a plan, so a
 *  Pro/Unlimited column swap authored in this data passed the entire suite —
 *  verified before this was written, by swapping `Watchlists` to
 *  `['1', 'Unlimited', '5–10']`: 21 of 21 tests still passed, and the matrix
 *  would have shipped offering Pro unlimited watchlists. Every cell is retyped
 *  here rather than read back out of COMPARE_ROWS, because an expectation
 *  derived from the data it checks asserts nothing.
 *
 *  The two Free cells that also exist as running code stay derived from the
 *  constants (see the demo-caps test below) so the copy still cannot drift from
 *  the limit a visitor actually hits; their Pro and Unlimited cells are literal
 *  like every other. */
const ALL_VALUES: [string, string, string][] = [
  ['Full', 'Full', 'Full'],
  ['Full', 'Full', 'Full'],
  [`~${DEMO_RUN_LIMIT}`, 'Unlimited', 'Unlimited'],
  [String(MAX_TICKERS), '10', '100+ (bulk)'],
  ['—', 'Up to 3', 'Up to 3'],
  ['1', '5–10', 'Unlimited'],
  ['5', '50', 'Unlimited'],
  ['—', 'Basic', 'Advanced'],
  ['6 months', '~2 years', 'Full history'],
  ['6 months', 'Yes', 'Advanced'],
  ['—', '—', 'Yes'],
  ['Preview', 'Preview', 'Full'],
  ['Preview', 'Preview', 'Yes'],
  ['—', '10–20', 'Unlimited'],
  ['—', '—', 'Yes'],
  ['—', '—', 'Yes'],
  ['—', 'CSV / PDF', 'Bulk'],
]

describe('plans', () => {
  it('offers exactly Free, Pro and Unlimited, with Pro featured', () => {
    expect(PLANS.map(p => p.name)).toEqual(['Free', 'Pro', 'Unlimited'])
    expect(PLANS.filter(p => p.featured).map(p => p.name)).toEqual(['Pro'])
  })

  it('gives every plan a title, a for-line, a CTA and features', () => {
    expect(PLANS.map(p => p.title)).toEqual([
      'Try Intrinsica',
      'Deep Stock Analysis',
      'Discover, Monitor & Automate at Scale',
    ])
    expect(PLANS.map(p => p.cta)).toEqual(['Start free', 'Choose Pro', 'Choose Unlimited'])
    for (const p of PLANS) {
      expect(p.forLine.length).toBeGreaterThan(20)
      expect(p.features.length).toBeGreaterThanOrEqual(5)
      for (const f of p.features) expect(f.length).toBeGreaterThan(10)
    }
  })

  // Pinned by equality, and the order is part of it: each paid plan opens with
  // its "everything in the tier below, plus" line, and the caps that follow read
  // as a list of what the extra money buys. A shuffled list still contains the
  // same words and says something different.
  it('lists each plan’s features in order', () => {
    expect(PLANS[0].features).toEqual([
      '~5 full-depth analyses / month',
      'Every analysis complete — Quality, Moat, Fair Value & Reward/Risk with the full breakdown, nothing blurred',
      'Up to 3 tickers per analysis run',
      '1 watchlist, up to 5 stocks',
      '6 months of score history (2 quarters)',
      'Discovery: see the filters, results locked',
    ])
    expect(PLANS[1].features).toEqual([
      'Everything in Free (same full depth), plus:',
      'Unlimited analyses — no monthly cap',
      'Up to 10 tickers per analysis run · side-by-side breakdown of 3',
      '5–10 watchlists of 50 stocks · ~2 years of score history & charts',
      'Score-change alerts (10–20) · CSV / PDF export · basic portfolio analysis',
    ])
    expect(PLANS[2].features).toEqual([
      'Everything in Pro, plus:',
      'Bulk / parallel analysis — 25, 50, 100+ tickers in one run',
      'Screen on Quality/Moat/FV/Reward/Risk across hundreds of stocks',
      'Unlimited watchlists · advanced portfolio analysis',
      'Full score-history evolution & “What Changed?”',
      'Automated monitoring · unlimited alerts · bulk exports',
    ])
    // Each paid tier must open by inheriting the one below it, or the cards
    // read as three unrelated products rather than three rungs.
    expect(PLANS[1].features[0]).toMatch(/^Everything in Free\b/)
    expect(PLANS[2].features[0]).toMatch(/^Everything in Pro\b/)
  })

  it('shows the effective monthly price on annual billing', () => {
    const pro = PLANS[1]
    expect(priceFor(pro, 'annual').headline).toBe('$18.00')
    expect(priceFor(pro, 'annual').sub).toBe('billed annually · $216/yr · save 18%')
    expect(priceFor(pro, 'monthly').headline).toBe('$21.99')
    expect(priceFor(pro, 'monthly').sub).toBe('billed monthly · $21.99/mo')
  })

  it('prices Unlimited at $25 effective and $29.99 monthly', () => {
    const unlimited = PLANS[2]
    expect(priceFor(unlimited, 'annual').headline).toBe('$25.00')
    expect(priceFor(unlimited, 'annual').sub).toBe('billed annually · $300/yr · save 17%')
    expect(priceFor(unlimited, 'monthly').headline).toBe('$29.99')
    expect(priceFor(unlimited, 'monthly').sub).toBe('billed monthly · $29.99/mo')
  })

  it('charges nothing for Free on either billing period, and promises no card', () => {
    const free = PLANS[0]
    for (const billing of ['annual', 'monthly'] as const) {
      expect(priceFor(free, billing).headline).toBe('$0')
      expect(priceFor(free, billing).sub).toBe('No card, ever')
    }
  })

  // The real guard on the prices: every derived string is recomputed from the
  // two raw numbers. A price edited in one place and not the others fails here.
  it.each([
    ['Pro', 1],
    ['Unlimited', 2],
  ] as const)('keeps %s’s annual total and advertised saving arithmetically true',
    (_name, i) => {
      const plan = PLANS[i]
      const effective = Number(plan.annual!.effective.replace('$', ''))
      const monthly = Number(plan.monthly!.effective.replace('$', ''))
      expect(Number.isFinite(effective)).toBe(true)
      expect(Number.isFinite(monthly)).toBe(true)

      // The yearly figure is a number now, so the checkout quotes it without a
      // regex that could match nothing; both it and the sentence on the card are
      // recomputed here from the effective monthly price.
      expect(plan.annual!.yearly).toBe(effective * 12)
      const stated = plan.annual!.sub.match(/\$(\d+)\/yr/)
      expect(stated).not.toBeNull()
      expect(Number(stated![1])).toBe(plan.annual!.yearly)

      const saving = plan.annual!.sub.match(/save (\d+)%/)
      expect(saving).not.toBeNull()
      const full = monthly * 12
      expect(Number(saving![1])).toBe(Math.round(((full - effective * 12) / full) * 100))

      // Annual must actually be cheaper than monthly, or the toggle's "save"
      // tag is a lie.
      expect(effective).toBeLessThan(monthly)
    })

  it('states the checkout total per plan and billing period', () => {
    expect(totalFor('Pro', 'annual')).toBe('$216 / year ($18.00/mo)')
    expect(totalFor('Pro', 'monthly')).toBe('$21.99 / month')
    expect(totalFor('Unlimited', 'annual')).toBe('$300 / year ($25.00/mo)')
    expect(totalFor('Unlimited', 'monthly')).toBe('$29.99 / month')
    expect(totalFor('Free', 'annual')).toBe('$0 — free plan')
    expect(totalFor('Free', 'monthly')).toBe('$0 — free plan')
  })

  // The checkout reads its plan from `?plan=`, which any visitor can edit. An
  // unrecognised name must not fall through to the Free branch: `?plan=Bogus`
  // answered with "$0 — free plan" is a fake door telling a visitor something
  // false about money, which is the one thing this page may never do.
  it('names no price at all for a plan it does not recognise', () => {
    for (const billing of ['annual', 'monthly'] as const) {
      for (const name of ['Bogus', '', 'free', 'PRO', 'Unlimited ']) {
        const total = totalFor(name, billing)
        expect(total).toBe('No plan selected')
        expect(total).not.toMatch(/\$/)
        expect(total).not.toMatch(/free/i)
      }
    }
  })

  // The checkout (Task 14) shows only `totalFor`. If it disagreed with the card
  // the visitor just clicked, the card would be advertising a price the checkout
  // does not name.
  it('quotes the same numbers in the checkout total as on the card', () => {
    for (const plan of PLANS.slice(1)) {
      expect(totalFor(plan.name, 'annual')).toContain(plan.annual!.effective)
      expect(totalFor(plan.name, 'annual'))
        .toContain(plan.annual!.sub.match(/\$(\d+)\/yr/)![1])
      expect(totalFor(plan.name, 'monthly')).toContain(plan.monthly!.effective)
    }
  })

  it('carries all seventeen compare rows, in spec order, with the split compare feature', () => {
    expect(COMPARE_ROWS).toHaveLength(17)
    expect(COMPARE_ROWS.map(r => r.label)).toEqual(ALL_LABELS)
    const sbs = COMPARE_ROWS.find(r => r.label === 'Side-by-side breakdown')
    expect(sbs).toBeDefined()
    expect(sbs!.values).toEqual(['—', 'Up to 3', 'Up to 3'])
    const run = COMPARE_ROWS.find(r => r.label === 'Tickers per analysis run')
    expect(run).toBeDefined()
    expect(run!.values).toEqual(['3', '10', '100+ (bulk)'])
  })

  // Task 13's fix round pinned the *render* order against this data; it did not
  // pin this data against the plans. Both columns of every row are pinned here,
  // so a Pro/Unlimited swap fails on the row it was authored in — and it fails
  // naming the row, because the labels are asserted alongside the values.
  it('pins all three columns of every row, not only Free’s', () => {
    expect(COMPARE_ROWS.map(r => r.label)).toEqual(ALL_LABELS)
    expect(COMPARE_ROWS.map(r => r.values)).toEqual(ALL_VALUES)
  })

  it('gives every compare row exactly three values, one per plan', () => {
    for (const row of COMPARE_ROWS) {
      expect(row.values).toHaveLength(3)
      for (const v of row.values) expect(v.length).toBeGreaterThan(0)
    }
  })

  // Every row has to say something a reader can act on: a row that is "—" in
  // all three columns advertises nothing, and one that is identical in all
  // three outside the two deliberate "same depth everywhere" rows is not a
  // reason to upgrade.
  it('never offers a row that is empty for every plan', () => {
    for (const row of COMPARE_ROWS) {
      expect(row.values.some(v => v !== '—')).toBe(true)
    }
    const uniform = COMPARE_ROWS.filter(r => new Set(r.values).size === 1)
    expect(uniform.map(r => r.label)).toEqual([
      'Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk)',
      'Breakdown, methodology & calibrations',
    ])
  })

  it('caps the Free tier the way the spec does', () => {
    const byLabel = (l: string) => {
      const row = COMPARE_ROWS.find(r => r.label === l)
      expect(row).toBeDefined()
      return row!.values[0]
    }
    expect(byLabel('Analyses per month')).toBe('~5')
    expect(byLabel('Tickers per analysis run')).toBe('3')
    expect(byLabel('Watchlists')).toBe('1')
    expect(byLabel('Stocks per watchlist')).toBe('5')
    expect(byLabel('Score history')).toBe('6 months')
    expect(byLabel('Score-history charts')).toBe('6 months')
  })

  // The two Free caps that also exist as running code, and both are imported
  // rather than retyped — the point of this test is that the copy cannot drift
  // from the limit the visitor actually hits.
  //
  //   - DEMO_RUN_LIMIT (demoLimit.ts) is the whole monthly allowance.
  //   - MAX_TICKERS (components/Hero.tsx) is the per-run cap the shipped demo
  //     pre-checks and names in its error message. The server holds the real
  //     one, in backend/routers/landing.py (MAX_TICKERS, line 13); that file is
  //     Python and unimportable from here, and Hero's constant is documented as
  //     its client mirror, so this pins the mirror and the server cap is
  //     asserted in the backend's own suite.
  //
  // The matrix is pinned as well as the bullet: the card and the compare row
  // quote the same allowance to the same reader, and only one of them was
  // checked before.
  it('quotes the same Free caps the shipped demo enforces', () => {
    const free = PLANS[0]
    expect(free.features.some(f => f.includes(`~${DEMO_RUN_LIMIT}`))).toBe(true)
    expect(free.features.some(f => f.includes(`${MAX_TICKERS} tickers`))).toBe(true)

    const byLabel = (l: string) => {
      const row = COMPARE_ROWS.find(r => r.label === l)
      expect(row).toBeDefined()
      return row!.values[0]
    }
    expect(byLabel('Analyses per month')).toBe(`~${DEMO_RUN_LIMIT}`)
    expect(byLabel('Tickers per analysis run')).toBe(String(MAX_TICKERS))
  })

  // Moved out of Pricing.tsx: the toggle's tag is a pricing number, and a
  // pricing number written in a component is one no data test can reach. The
  // bound on the percentage it claims stays in Pricing.test.tsx, where it is
  // read off the rendered button — that is what the visitor is promised.
  it('offers annual and monthly, and advertises a saving on annual only', () => {
    expect(PERIODS.map(p => p.id)).toEqual(['annual', 'monthly'])
    expect(PERIODS.map(p => p.label)).toEqual(['Annual', 'Monthly'])
    expect(PERIODS[0].save).toBe('save ~17%')
    // Nothing is saved by paying monthly, so nothing may claim otherwise.
    expect(PERIODS[1].save).toBeUndefined()
  })

  // The who-cards restate one plan each, in PLANS order. A card that opened
  // with a different plan than the one it describes would sell the wrong tier.
  it('gives each plan one who-it-is-for card, in plan order', () => {
    expect(WHO).toHaveLength(PLANS.length)
    WHO.forEach((w, i) => {
      expect(w.tag.startsWith(PLANS[i].name)).toBe(true)
      expect(w.title.length).toBeGreaterThan(10)
      expect(w.who.length).toBeGreaterThan(40)
      expect(w.focus.length).toBeGreaterThan(40)
    })
    expect(WHO.map(w => w.tag))
      .toEqual(['Free · Try', 'Pro · Depth', 'Unlimited · Scale'])
  })

  it('never calls Free the full product', () => {
    const free = PLANS[0]
    expect(free.forLine).toBe('Full-depth analysis, small volume.')
    expect(JSON.stringify(free)).not.toMatch(/full product/i)
    // Spec 5.7: Free is honest — complete analysis, capped volume. Both halves
    // have to be present, not just the flattering one.
    expect(JSON.stringify(free)).toMatch(/nothing blurred/i)
  })

  // Spec section 8, rules 1 and 2 — anchored on a string that is really there, so
  // an empty module could not satisfy it. The approved mock writes the label
  // "Reward/Risk" in running copy (and "Reward / Risk" as a heading); either is the
  // right direction. What is banned is the reversed ratio, the hyphenated compound
  // and the R/R abbreviation.
  it('says assessment rather than signal, and Reward/Risk rather than Risk/Reward', () => {
    const text = JSON.stringify([PLANS, COMPARE_ROWS, WHO, PERIODS])
    expect(text).toMatch(/Reward\s?\/\s?Risk/)
    expect(text).not.toMatch(/signal/i)
    expect(text).not.toMatch(/Risk\s*[/-]\s*Reward/)
    expect(text).not.toMatch(/Reward\s*-\s*Risk\b/)
    expect(text).not.toMatch(/\bR\s*[/-]\s*R\b/)
  })

  // Spec section 8 rules 3 and 5, and the fake-door rule on invented urgency.
  it('publishes no scoring cut-off, no internal identifier and no manufactured scarcity', () => {
    const text = JSON.stringify([PLANS, COMPARE_ROWS, WHO, PERIODS])
    expect(text.length).toBeGreaterThan(500)
    expect(text).not.toMatch(/[<>≥≤]\s*\d/)
    expect(text).not.toMatch(/scores?\s+\d/i)
    expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
    expect(text).not.toMatch(/\.py\b/)
    expect(text).not.toMatch(/only \d+|seats? left|hurry|limited time|expires?\b|countdown/i)
    expect(text).not.toMatch(/card number|cvc|cvv|expiry|billing address/i)
  })
})

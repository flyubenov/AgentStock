import { describe, it, expect } from 'vitest'
import { ASSESSMENTS } from '../components/Hero'
import { CALIBRATIONS, FRAMEWORK, OVERVIEW } from './framework'

/** Spec section 5.4: the detail panel is "identical in shape across all four —
 *  this consistency is a requirement; they had drifted". Asserting the key list
 *  itself is what makes that structural rather than a promise: adding a fifth
 *  field to one assessment, or dropping `note` from another, fails here. */
const SHAPE = ['name', 'color', 'question', 'scale', 'what',
               'hiLabel', 'loLabel', 'groups', 'bands', 'note']
const GROUP_SHAPE = ['title', 'question', 'weight', 'share', 'metrics', 'hi', 'lo']

const everyString = (o: object): string => JSON.stringify(o)

describe('framework content', () => {
  it('covers the four assessments in page order', () => {
    expect(FRAMEWORK.map(a => a.name)).toEqual(
      ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'])
  })

  // `AssessmentId` is a bare index shared by the hero cards, the breakdown tab
  // strip and these framework cards — all three read and write one `assessment`
  // on LandingPage. If the lists ever drift, clicking "Moat" in the hero opens
  // "Fair Value" here and nothing else would catch it. Breakdown.test.tsx pins
  // its own strip to the same source.
  it('indexes identically to the hero assessment cards', () => {
    expect(FRAMEWORK.map(a => a.name)).toEqual(ASSESSMENTS.map(a => a.name))
    expect(FRAMEWORK.map(a => a.color)).toEqual(ASSESSMENTS.map(a => a.color))
  })

  it('gives every assessment the same fields, in the same order', () => {
    for (const a of FRAMEWORK) {
      expect(Object.keys(a)).toEqual(SHAPE)
      expect(a.groups.length).toBeGreaterThan(0)
      for (const g of a.groups) expect(Object.keys(g)).toEqual(GROUP_SHAPE)
    }
  })

  it('leaves no field of any assessment or group empty', () => {
    for (const a of FRAMEWORK) {
      for (const k of SHAPE) {
        if (k === 'groups' || k === 'bands') continue
        expect(a[k as 'name']).toBeTruthy()
      }
      for (const g of a.groups) {
        for (const k of ['title', 'question', 'weight', 'hi', 'lo'] as const) expect(g[k]).toBeTruthy()
        expect(g.metrics.length).toBeGreaterThan(0)
        for (const m of g.metrics) expect(m).toBeTruthy()
      }
    }
  })

  // Spec 5.4 item 1 names all four pills verbatim.
  it('carries the scale pill the spec names for each assessment', () => {
    expect(FRAMEWORK.map(a => a.scale)).toEqual(
      ['0–10 · sector-aware', '0–10', '$ per share', 'ratio · 0.2–5.0×'])
  })

  // Spec 5.4 item 3 (2026-09-29): ▲ High / ▼ Low everywhere, except Fair Value,
  // which has no score to be high or low — a method is weighted up or down.
  it('uses the high / low vocabulary, weighted only for Fair Value', () => {
    expect(FRAMEWORK.map(a => a.hiLabel)).toEqual(['High', 'High', 'Weighted up', 'High'])
    expect(FRAMEWORK.map(a => a.loLabel)).toEqual(['Low', 'Low', 'Weighted down', 'Low'])
  })

  // Spec 5.4 item 3, last clause. A bare ratio leaves a reader guessing which
  // way is good; the breakdown panel says the same thing on its own risk axis.
  it('titles the Reward / Risk risk category with its direction', () => {
    expect(FRAMEWORK[3].groups.map(g => g.title)).toContain(
      'Risk axis · a high score here is the bad one')
  })

  it('paints every assessment from a theme token, never a colour literal', () => {
    expect(FRAMEWORK.map(a => a.color)).toEqual(
      ['var(--q)', 'var(--mo)', 'var(--fv)', 'var(--rr)'])
    expect(everyString(FRAMEWORK)).not.toMatch(/#[0-9a-f]{3,8}\b/i)
  })

  it('never says signal, and never says Risk/Reward', () => {
    const text = everyString(FRAMEWORK) + everyString(CALIBRATIONS) + everyString(OVERVIEW)
    expect(text).toMatch(/assessment/i)
    expect(text).not.toMatch(/signal/i)
    expect(text).not.toMatch(/Risk\s*\/\s*Reward/)
  })

  it('names no moat source it cannot measure', () => {
    const moat = everyString(FRAMEWORK[1])
    expect(moat).toMatch(/economic profit/i)
    expect(moat).not.toMatch(/network effect|switching cost|brand/i)
  })

  // Spec section 8 rule 5. The anchor keeps this from passing on an empty blob.
  it('leaks no internal identifier or module name through any string', () => {
    const text = everyString(FRAMEWORK) + everyString(CALIBRATIONS) + everyString(OVERVIEW)
    expect(text).toContain('Returns on Capital')
    expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
    expect(text).not.toMatch(/\.py\b|backend\/|scoring\./)
  })

  // Variant D3 (user decision 2026-09-26): the four highlights were cut. The lead
  // leaves the calibration count to the component, which renders CALIBRATIONS.length.
  it('carries the short overview lead, the judgment note and the closing line', () => {
    expect(OVERVIEW).not.toHaveProperty('points')
    expect(`${OVERVIEW.lead.before} ${OVERVIEW.lead.bold}`).not.toMatch(/\d/)
    expect(OVERVIEW.lead.after).toBe('Same data, same score.')
    expect(OVERVIEW.judgment.title).toBe('Intrinsica’s own method.')
    expect(OVERVIEW.tail).toMatch(/Click an assessment/)
  })

  it('attaches every calibration to at least one assessment', () => {
    const names = new Set(FRAMEWORK.map(a => a.name))
    expect(CALIBRATIONS.length).toBeGreaterThan(0)
    for (const c of CALIBRATIONS) {
      expect(c.affects.length).toBeGreaterThan(0)
      for (const target of c.affects) expect(names.has(target)).toBe(true)
    }
  })

  // Each assessment's detail panel renders its own calibration list. An
  // assessment nothing points at renders a heading over nothing.
  it('leaves no assessment without a calibration of its own', () => {
    const covered = new Set(CALIBRATIONS.flatMap(c => c.affects))
    expect([...FRAMEWORK.map(a => a.name)].filter(n => !covered.has(n))).toEqual([])
  })

  it('gives every calibration the copy its expanded row needs', () => {
    for (const c of CALIBRATIONS) {
      expect(c.name).toBeTruthy()
      expect(c.summary).toBeTruthy()
      expect(c.when).toBeTruthy()
      expect(c.effect).toBeTruthy()
      expect(typeof c.guarded).toBe('boolean')
      if (c.example !== undefined) expect(c.example).toBeTruthy()
    }
  })

  // "Guarded" is a claim about the engine, not decoration: spec 5.4 item 5 tags
  // it "only where the engine guard is one-directional" — the adjustment can
  // correct a distortion and never inflate a score. Pinned as a set in both
  // directions, so flipping any single flag fails, and so the component's
  // conditional Guarded tag always has both cases to render.
  it('tags exactly the one-directional calibrations as guarded', () => {
    expect(CALIBRATIONS.filter(c => c.guarded).map(c => c.name)).toEqual([
      'Tangible-ROIC (ex-goodwill)',
      'Forward-EPS swap',
      'Heavy-capex FCF exclusion',
      'Dominant fresh-acquisition',
      'Statement-corroboration guard',
    ])
    expect(CALIBRATIONS.some(c => !c.guarded)).toBe(true)
  })

  // Spec 5.4 item 3 — the approved copy table, verbatim.
  const COPY: [string, string, string, string][] = [
    ['Growth & Margins', 'Is it growing — and profitably?', 'compounding revenue, margins holding', 'stalled growth, margins sliding'],
    ['Returns on Capital', 'Does it earn more than its capital costs?', 'well above its cost of capital', 'barely matches it'],
    ['Balance-Sheet Strength', 'Can it weather a bad year?', 'little debt, capex easily funded', 'leverage that needs a kind cycle'],
    ['Shareholder Alignment', 'Are owners treated well?', 'buybacks, earnings that arrive as cash', 'steady dilution, paper earnings'],
    ['Magnitude', 'How far above its cost of capital does it earn?', 'returns far above the cost of capital', 'returns that merely match it'],
    ['Durability', 'Does the edge last, year after year?', 'a decade of above-cost returns, margins that hold', 'a good spell inside a cyclical swing'],
    ['Cash-backing', 'Does the profit turn into cash?', 'profit that becomes cash', 'profit that stays on paper'],
    ['Cash-flow models', 'What will the business pay out over time?', 'steady, predictable cash flows', 'erratic cash flows, or pre-profit'],
    ['Earnings multiples', 'How is it priced against its earnings?', 'meaningful profits, comparable with peers', 'losses, or earnings distorted by amortization'],
    ['Sales multiples', 'What is growth worth before profit?', 'fast growth, no profit yet', 'a mature, profitable company'],
    ['Income & asset models', 'What do its dividends or assets say?', 'dividend payers, lenders, asset-heavy names', 'asset-light businesses'],
    ['Reward axis', 'How much upside is left?', 'a growing business well below its highs', 'a full price, little left to re-rate'],
    ['Risk axis · a high score here is the bad one', 'How much can go wrong?', 'leverage and volatility stacking up', 'light debt, a steady price, self-funded'],
  ]
  it('carries the approved question and ▲ / ▼ line for every category', () => {
    expect(FRAMEWORK.flatMap(a => a.groups.map(g => [g.title, g.question, g.hi, g.lo]))).toEqual(COPY)
  })

  // Categories, weights and metric lists are unchanged (spec 5.4): the chips
  // are the old metric string split one metric per chip, so the counts match
  // the "N metrics" the old pills announced.
  it('keeps the weights, shares and metric counts', () => {
    const [q, m, fv, rr] = FRAMEWORK
    expect(q.groups.map(g => g.weight)).toEqual(['35%', '30%', '15%', '20%'])
    expect(q.groups.map(g => g.share)).toEqual([35, 30, 15, 20])
    expect(q.groups.map(g => g.metrics.length)).toEqual([7, 4, 3, 5])
    expect(m.groups.map(g => g.weight)).toEqual(['40%', '50%', '10%'])
    expect(m.groups.map(g => g.share)).toEqual([40, 50, 10])
    expect(m.groups.map(g => g.metrics.length)).toEqual([2, 3, 1])
    expect(fv.groups.map(g => g.weight)).toEqual(['typically 40–60%', 'typically 20–40%', '0–20%', '0–60%'])
    expect(fv.groups.every(g => g.share === null)).toBe(true)
    expect(rr.groups.map(g => g.weight)).toEqual(['6 factors · scored 1–5', '6 factors · scored 1–5'])
    expect(rr.groups.every(g => g.share === null)).toBe(true)
    expect(rr.groups.map(g => g.metrics.length)).toEqual([6, 6])
  })

  // Spec 5.4 item 4: the closing note becomes a scale strip plus one line.
  it('carries the scale strip and its line for each assessment', () => {
    expect(FRAMEWORK.map(a => a.bands)).toEqual([
      ['below 5 · Weak', '5–7 · Moderate', '7–8 · Strong', '8–9 · Excellent', '9+ · Top-decile'],
      ['below 4 · Little or none', '4–6 · Narrow', '6–8 · Established', '8+ · Wide'],
      [],
      ['below 0.5× · Value Trap', '0.5–0.8× · Risk-Favored', '0.8–1.3× · Balanced', '1.3–2.0× · Reward-Favored', '2.0×+ · Asymmetric Upside'],
    ])
    expect(FRAMEWORK.map(a => a.note)).toEqual([
      'Each metric is scored against fixed thresholds; the category weights follow the sector profile (Tech / Growth shown).',
      'An economic-profit gate caps any company that does not out-earn its cost of capital.',
      'The company’s type sets the blend — a bank leans on price / book, a mega cap on cash flows. Every analysis shows the exact blend it used.',
      'Reward ÷ risk, clamped to 0.2–5.0×.',
    ])
  })

  // Spec 5.4 overview item 2, reworded 2026-09-29: the method is stated as fixed.
  it('states the method as fixed, and drops "no single agreed"', () => {
    expect(OVERVIEW.judgment.body).toBe(
      'Quality, Moat and Reward/Risk aren’t printed in any filing; they have to be assessed. ' +
      'Intrinsica assesses them with one fixed methodology: it takes the fundamentals that matter for each, ' +
      'weights them and condenses them into a single score, the same way for every company. ' +
      'Each score opens up to the inputs and weights behind it.')
    expect(everyString(OVERVIEW)).not.toMatch(/no single agreed/i)
  })
})

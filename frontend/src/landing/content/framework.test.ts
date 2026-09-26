import { describe, it, expect } from 'vitest'
import { ASSESSMENTS } from '../components/Hero'
import { CALIBRATIONS, FRAMEWORK, OVERVIEW } from './framework'

/** Spec section 5.4: the detail panel is "identical in shape across all four —
 *  this consistency is a requirement; they had drifted". Asserting the key list
 *  itself is what makes that structural rather than a promise: adding a fifth
 *  field to one assessment, or dropping `note` from another, fails here. */
const SHAPE = ['name', 'color', 'question', 'scale', 'what',
               'hiLabel', 'loLabel', 'groups', 'note']
const GROUP_SHAPE = ['title', 'weight', 'metrics', 'hi', 'lo']

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
        if (k === 'groups') continue
        expect(a[k as 'name']).toBeTruthy()
      }
      for (const g of a.groups) {
        for (const k of GROUP_SHAPE) expect(g[k as 'title']).toBeTruthy()
      }
    }
  })

  // Spec 5.4 item 1 names all four pills verbatim.
  it('carries the scale pill the spec names for each assessment', () => {
    expect(FRAMEWORK.map(a => a.scale)).toEqual(
      ['0–10 · sector-aware', '0–100', '$ per share', 'ratio · 0.2–5.0×'])
  })

  // Spec 5.4 item 3: "Scores high / Scores low" everywhere, except Fair Value,
  // which has no score to be high or low — a method is weighted up or down.
  it('uses the scores-high / scores-low vocabulary, weighted only for Fair Value', () => {
    expect(FRAMEWORK.map(a => a.hiLabel)).toEqual(
      ['Scores high', 'Scores high', 'Weighted up', 'Scores high'])
    expect(FRAMEWORK.map(a => a.loLabel)).toEqual(
      ['Scores low', 'Scores low', 'Weighted down', 'Scores low'])
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
    expect(OVERVIEW.judgment.title).toBe('A methodology, not a measurement.')
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
})

import { describe, it, expect } from 'vitest'
import { money, num, pct, gapClass, figure, weight, dollars, gapPct, qualityTier, moatTier, fvCaption,
         UNSUPPORTED_CURRENCY, unsupportedNotice } from './format'
import type { TickerPayload } from './types'

describe('formatters', () => {
  it('renders an em dash for every absent value', () => {
    expect(money(null)).toBe('—')
    expect(num(null)).toBe('—')
    expect(pct(null)).toBe('—')
  })

  it('formats money and percentages', () => {
    expect(money(211)).toBe('$211.00')
    expect(pct(-9.05)).toBe('-9.1%')
    expect(pct(17)).toBe('+17.0%')
  })

  it('rounds numbers to the requested precision', () => {
    expect(num(9.14, 1)).toBe('9.1')
    expect(num(0.92, 2)).toBe('0.92')
  })

  it('never emits NaN or Infinity', () => {
    expect(num(NaN)).toBe('—')
    expect(pct(Infinity)).toBe('—')
    expect(money(-Infinity)).toBe('—')
  })

  it('bands the fair-value gap by size and direction', () => {
    expect(gapClass(12)).toBe('gap-pos')
    expect(gapClass(4)).toBe('gap-near')
    expect(gapClass(-4)).toBe('gap-warn')
    expect(gapClass(-18)).toBe('gap-neg')
    expect(gapClass(null)).toBe('gap-none')
  })

  // Fix round 1: gapClass leans on the same finite() guard the formatters use,
  // but only its null case was ever exercised. A non-finite gap must never band
  // a cell as if it were a real number.
  it('bands a non-finite gap as absent, never as a direction', () => {
    expect(gapClass(NaN)).toBe('gap-none')
    expect(gapClass(Infinity)).toBe('gap-none')
    expect(gapClass(-Infinity)).toBe('gap-none')
  })

  // Fix round 1: a value that rounds to zero must not carry a sign. "-0.0%"
  // reads as a bug on a page that promises every number is checkable. Nothing
  // pinned pct(0) === '+0.0%' before this, so zero is now unsigned in both
  // directions rather than positive-by-default.
  it('never prints a signed zero', () => {
    expect(pct(-0.04)).toBe('0.0%')
    expect(pct(0.04)).toBe('0.0%')
    expect(pct(0)).toBe('0.0%')
    expect(pct(-0)).toBe('0.0%')
  })

  it('still signs a value that survives rounding', () => {
    expect(pct(0.05)).toBe('+0.1%')
    expect(pct(-0.06)).toBe('-0.1%')
  })
})

// Task 10: the breakdown table shows a metric's underlying figure and its share
// of a category. Neither job fits num()/pct(): a raw figure spans margins (0.08)
// and multiples (55.2) so a fixed decimal count is wrong for one of them, and a
// weight is unsigned and must not read "+35.0%". Both live here rather than
// inline in Breakdown.tsx so the em-dash guarantee has exactly one implementation.
describe('figure', () => {
  it('renders an em dash for every absent or non-finite value', () => {
    expect(figure(null)).toBe('—')
    expect(figure(NaN)).toBe('—')
    expect(figure(Infinity)).toBe('—')
  })

  it('trims a floating-point tail the backend never rounded', () => {
    expect(figure(0.08123456789)).toBe('0.08123')
    expect(figure(55.234567)).toBe('55.23')
  })

  it('leaves a clean value clean', () => {
    expect(figure(232)).toBe('232')
    expect(figure(0.3)).toBe('0.3')
    expect(figure(-3.43)).toBe('-3.43')
  })

  it('prints zero unsigned', () => {
    expect(figure(0)).toBe('0')
    expect(figure(-0)).toBe('0')
  })

  // Prelude to task 11. figure() leans on String(Number(...)), which switches to
  // exponent notation outside roughly 1e-6 … 1e21. Pinned rather than clamped:
  // see the rationale on figure() itself. These two tests exist so the boundary
  // is a decision on record, not an accident — a later clamp to toFixed() would
  // fail the second one and have to argue with the comment.
  it('keeps fixed notation across the whole range any real metric occupies', () => {
    expect(figure(0.000001)).toBe('0.000001')
    expect(figure(-0.0000123)).toBe('-0.0000123')
    expect(figure(999900000000000000000)).toBe('999900000000000000000')
  })

  it('falls back to exponent notation past that range, never to NaN or null', () => {
    expect(figure(5e-7)).toBe('5e-7')
    expect(figure(-5e-7)).toBe('-5e-7')
    expect(figure(1.5e21)).toBe('1.5e+21')
    for (const v of [5e-7, -5e-7, 1.5e21]) {
      expect(figure(v)).not.toMatch(/NaN|Infinity|null|undefined/)
    }
  })
})

describe('weight', () => {
  it('renders an em dash for every absent or non-finite value', () => {
    expect(weight(null)).toBe('—')
    expect(weight(NaN)).toBe('—')
  })

  it('drops a pointless decimal but keeps a real one', () => {
    expect(weight(35)).toBe('35%')
    expect(weight(17.5)).toBe('17.5%')
    expect(weight(11.67)).toBe('11.7%')
    expect(weight(0)).toBe('0%')
  })

  it('never signs a weight — a share of a category has no direction', () => {
    expect(weight(35)).not.toContain('+')
    expect(weight(-0)).toBe('0%')
  })
})

describe('mock headline forms', () => {
  it('rounds fair value to whole dollars and the gap to a signed whole percent', () => {
    expect(dollars(192.71)).toBe('$193')
    expect(dollars(null)).toBe('—')
    expect(gapPct(-43.5)).toBe('−43%')
    expect(gapPct(5.2)).toBe('+5%')
    expect(gapPct(0.4)).toBe('0%')
    expect(gapPct(NaN)).toBe('—')
  })

  it('reads the published outcome bands back onto a score, edges included', () => {
    expect(qualityTier(9)).toBe('Top-decile')
    expect(qualityTier(8.99)).toBe('Excellent')
    expect(qualityTier(7)).toBe('Strong')
    expect(qualityTier(6.9)).toBe('Moderate')
    expect(qualityTier(4.9)).toBe('Weak')
    expect(moatTier(8)).toBe('Wide')
    expect(moatTier(7.9)).toBe('Established')
    expect(moatTier(6)).toBe('Established')
    expect(moatTier(5.9)).toBe('Narrow')
    expect(moatTier(4)).toBe('Narrow')
    expect(moatTier(3.9)).toBe('Little or none')
    expect(moatTier(null)).toBeNull()
  })
})

describe('fvCaption', () => {
  // gap_pct is (fair value - price) / price, so it is measured against the PRICE.
  it('says how far fair value sits from the price, measured against the price', () => {
    expect(fvCaption(-53.43)).toBe('Fair value 53% below price')
    expect(fvCaption(12.4)).toBe('Fair value 12% above price')
  })
  it('says "at price" when the gap rounds to zero, never "0% above"', () => {
    expect(fvCaption(0.4)).toBe('Fair value at price')
    expect(fvCaption(-0.4)).toBe('Fair value at price')
  })
  it('falls back to the em dash for a missing or broken gap', () => {
    expect(fvCaption(null)).toBe('—')
    expect(fvCaption(Number.NaN)).toBe('—')
  })
})

describe('unsupportedNotice', () => {
  const row = (ticker: string, errors: string[], ok = false) => ({
    ticker, company_name: null, price: null, calibrations: [], errors,
    quality: ok ? { score: 7 } : null, moat: null, fair_value: null, reward_risk: null,
  }) as unknown as TickerPayload

  it('names every stock declined for its reporting currency, once', () => {
    expect(unsupportedNotice([row('KSPI', [UNSUPPORTED_CURRENCY]), row('AAPL', [], true), row('TM', [UNSUPPORTED_CURRENCY])]))
      .toBe(`KSPI, TM: ${UNSUPPORTED_CURRENCY}.`)
  })

  it('says nothing for other failures, for computed rows, or for rows without errors', () => {
    expect(unsupportedNotice([row('NVDA', ['Market data unavailable'])])).toBeNull()
    expect(unsupportedNotice([row('AAPL', [UNSUPPORTED_CURRENCY], true)])).toBeNull()
    expect(unsupportedNotice([{ ticker: 'NVDA' } as TickerPayload])).toBeNull()
  })
})

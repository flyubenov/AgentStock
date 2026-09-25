import { describe, it, expect } from 'vitest'
import { money, num, pct, gapClass, figure, weight } from './format'

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

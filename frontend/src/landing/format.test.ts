import { describe, it, expect } from 'vitest'
import { money, num, pct, gapClass } from './format'

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

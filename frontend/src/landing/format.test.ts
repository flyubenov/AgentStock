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
})

import { describe, it, expect } from 'vitest'
import cases from './ticker-cases.json'
import { normalizeTicker, noticeLabel } from './ticker'

describe('normalizeTicker', () => {
  it.each(cases as [string, string | null][])('%j → %j', (raw, want) => {
    expect(normalizeTicker(raw)).toBe(want)
  })
})

describe('noticeLabel', () => {
  it('uses the canonical form when there is one', () => {
    expect(noticeLabel('brk-b')).toBe('BRK.B')
  })
  it('strips anything but letters, digits, dot and dash, and cuts at 12', () => {
    expect(noticeLabel('<script>alert(1)</script>')).toBe('SCRIPTALERT1')
    expect(noticeLabel('a,b')).toBe('AB')
  })
  it('never returns an empty label', () => {
    expect(noticeLabel('<<>>')).toBe('that ticker')
  })
})

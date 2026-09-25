import { describe, it, expect, vi } from 'vitest'
import { DEMO_RUN_LIMIT, DEMO_WINDOW_DAYS, runsUsed, canAnalyze, recordRun } from './demoLimit'

// localStorage.clear() runs in the global beforeEach (src/test/setup.ts), so every
// test here starts with a clean slate.

describe('demoLimit', () => {
  it('lets a fresh visitor analyze; runsUsed is 0', () => {
    expect(runsUsed()).toBe(0)
    expect(canAnalyze()).toBe(true)
  })

  it('blocks once DEMO_RUN_LIMIT runs have been recorded', () => {
    for (let i = 0; i < DEMO_RUN_LIMIT; i++) recordRun()
    expect(runsUsed()).toBe(DEMO_RUN_LIMIT)
    expect(canAnalyze()).toBe(false)
  })

  it('resets after the window elapses (aged timestamp, not sleep)', () => {
    const windowMs = DEMO_WINDOW_DAYS * 24 * 60 * 60 * 1000
    const aged = { count: DEMO_RUN_LIMIT, windowStart: Date.now() - windowMs - 1000 }
    localStorage.setItem('intrinsica_demo_runs', JSON.stringify(aged))

    expect(canAnalyze()).toBe(true)
    expect(runsUsed()).toBe(0)
  })

  it('fails open when storage throws on read: canAnalyze is true and the throwing accessor is actually invoked', () => {
    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(() => canAnalyze()).not.toThrow()
    expect(canAnalyze()).toBe(true)
    expect(getItemSpy).toHaveBeenCalled()
  })

  it('fails open when storage throws on write: recordRun does not throw and does not block the visitor', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })

    expect(() => recordRun()).not.toThrow()
    expect(setItemSpy).toHaveBeenCalled()
    // The write never landed, so storage never recorded the run — the visitor
    // remains unblocked rather than being locked out by a failed write.
    expect(canAnalyze()).toBe(true)
  })

  it('treats corrupt stored JSON as a fresh visitor rather than crashing', () => {
    localStorage.setItem('intrinsica_demo_runs', '{not valid json')

    expect(() => canAnalyze()).not.toThrow()
    expect(canAnalyze()).toBe(true)
    expect(runsUsed()).toBe(0)
  })
})

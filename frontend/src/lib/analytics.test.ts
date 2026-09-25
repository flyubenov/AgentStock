import { describe, it, expect, vi } from 'vitest'
import { track, visitorId, EVENTS } from './analytics'

/** Spec section 9's event list, hand-transcribed from
 *  docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md — the
 *  funnel sentence, plus `free_plan_clicked`, which that section names
 *  separately as its own event excluded from paid-intent conversion.
 *
 *  Transcribed and NOT imported from `./analytics`. An expectation derived from
 *  the constant under test compares the module to itself and passes whatever it
 *  contains, which is a failure mode this branch has shipped before. These
 *  eleven strings are the spec's, typed out; if the two lists disagree, one of
 *  the two documents is wrong and a human has to say which. */
const SPEC_EVENTS = [
  'page_view',
  'analysis_started',
  'analysis_completed',
  'breakdown_opened',
  'methodology_viewed',
  'pricing_viewed',
  'plan_selected',
  'checkout_started',
  'payment_button_clicked',
  'email_submitted',
  'free_plan_clicked',
]

/** THE LIST IS CLOSED — spec section 9 says so in as many words: "this list is
 *  the whole of it — there is no blanket click or scroll tracking", and names
 *  scroll depth, nav clicks, hovers, tooltip opens, calibration expands,
 *  breakdown tab switches and the billing toggle as deliberately uninstrumented.
 *  On a page with no accounts, every extra event is a privacy liability with no
 *  payoff, so the closure is the point and not a formality.
 *
 *  Nothing pinned it. funnel.test.tsx has its own copy of this list, but it
 *  compares it only against the events that reach the wire during the three
 *  journeys that file walks — so a twelfth event added to the map and fired
 *  from an interaction nobody walks is invisible there. `track('rage_click_v2')`
 *  planted in LandingPage's breakdown toggle left funnel.test.tsx 7/7 green.
 *
 *  This assertion is about the MAP, not about any journey, which is why it
 *  lives here beside the module it constrains rather than in the funnel file:
 *  it holds without rendering anything, and it cannot be weakened by a journey
 *  that stops exercising some step. */
describe('EVENTS', () => {
  it('is exactly spec section 9 list, in both directions', () => {
    const inCode: string[] = Object.values(EVENTS)

    expect(inCode.filter(e => !SPEC_EVENTS.includes(e)),
           'fired by the code, absent from spec section 9 — the list is closed')
      .toEqual([])
    expect(SPEC_EVENTS.filter(e => !inCode.includes(e)),
           'named by spec section 9, missing from EVENTS — the funnel has a hole')
      .toEqual([])
    // Sorted arrays rather than Sets: set equality would hide two keys that had
    // drifted onto the same name, which loses a funnel step just as silently as
    // deleting one.
    expect([...inCode].sort(), 'EVENTS and spec section 9 hold the same names')
      .toEqual([...SPEC_EVENTS].sort())
  })
})

describe('visitorId', () => {
  it('is stable across calls', () => {
    expect(visitorId()).toBe(visitorId())
  })

  it('survives a localStorage that throws', async () => {
    // visitorId() memoizes in a module-level variable, so reusing the
    // top-level import here would short-circuit before ever touching
    // localStorage. Reset the module registry and re-import so this test
    // exercises a fresh instance with nothing cached yet.
    vi.resetModules()
    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    const fresh = await import('./analytics')
    const id = fresh.visitorId()

    expect(getItemSpy).toHaveBeenCalled()
    expect(id).toMatch(/^v-/)
    expect(id.length).toBeGreaterThan(2)
  })
})

describe('track', () => {
  it('posts the event to /api/events', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    track(EVENTS.paymentButtonClicked, { plan: 'Pro', billing: 'annual' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/events$/)
    const body = JSON.parse(init.body)
    expect(body.event).toBe('payment_button_clicked')
    expect(body.props).toEqual({ plan: 'Pro', billing: 'annual' })
    expect(body.visitor_id).toBe(visitorId())
  })

  it('does not throw when the network rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(() => track(EVENTS.pageView)).not.toThrow()
    await Promise.resolve()
  })

  it('does not throw when fetch itself is unavailable', () => {
    vi.stubGlobal('fetch', undefined)
    expect(() => track(EVENTS.pageView)).not.toThrow()
  })

  it('returns synchronously so a click handler is never awaited', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    expect(track(EVENTS.checkoutStarted, { plan: 'Pro' })).toBeUndefined()
  })
})

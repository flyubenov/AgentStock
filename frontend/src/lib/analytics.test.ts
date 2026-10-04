import { describe, it, expect, vi } from 'vitest'
import { track, visitorId, EVENTS } from './analytics'

/** A COMPILE-TIME assertion, deliberately not a runtime one: vitest never
 *  typechecks this file, so this line proves nothing when the suite is green —
 *  it does its whole job under `tsc -b --force`, which is in the gate.
 *
 *  `track` takes FunnelEvent, so an off-spec name is a build error and the
 *  directive below absorbs it. Widen the parameter back to `string` and the
 *  directive becomes unused, which is itself an error (TS2578) — that is what
 *  holds the narrowing in place. The EVENTS assertion further down pins the map
 *  to the spec; this pins every caller to the map. Neither substitutes for the
 *  other: `track('rage_click_v2')` consults EVENTS not at all, and left the
 *  whole suite green before the parameter was narrowed. */
// @ts-expect-error 'rage_click_v2' is not one of spec section 9's event names.
void (() => track('rage_click_v2'))

/** Spec section 9's event list, hand-transcribed from
 *  docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md — the
 *  funnel sentence, plus `free_plan_clicked`, which that section names
 *  separately as its own event excluded from paid-intent conversion, plus
 *  `watchlist_clicked` (added 2026-09-26 by user decision, likewise outside it).
 *
 *  Transcribed and NOT imported from `./analytics`. An expectation derived from
 *  the constant under test compares the module to itself and passes whatever it
 *  contains, which is a failure mode this branch has shipped before. These
 *  twelve strings are the spec's, typed out; if the two lists disagree, one of
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
  'watchlist_clicked',
  'ticker_link_opened', // added 2026-10-03 (ticker links spec §7)
  'share_clicked', // added 2026-10-03 (ticker links spec §7)
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

  it('sends where the visitor came from beside the props, never inside them', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    track(EVENTS.planSelected, { plan: 'Pro' })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.props).toEqual({ plan: 'Pro' })
    expect(body.attribution).toMatchObject({ channel: expect.any(String),
                                             visit_channel: expect.any(String) })
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

/** The owner marker (2026-10-04): the founder opens intrinsica.io/?me=1 once in each
 *  browser they use, and that browser's events go out as "me-<id>", so the events
 *  sheet can exclude them whatever the device. analytics.ts memoizes, so each test
 *  imports a fresh copy after arranging the URL and storage. */
describe('the ?me=1 owner marker', () => {
  async function freshAt(url: string) {
    window.history.replaceState(null, '', url)
    vi.resetModules()
    return import('./analytics')
  }

  it('prefixes the same visitor ID with me- once the browser is marked, and remembers it', async () => {
    localStorage.clear()
    const before = (await freshAt('/')).visitorId()
    expect(before).toMatch(/^v-/)

    const marked = await freshAt('/?me=1')
    marked.markOwnerFromUrl()
    expect(marked.visitorId()).toBe(`me-${before}`)

    const later = await freshAt('/t/NVDA')
    later.markOwnerFromUrl()
    expect(later.visitorId()).toBe(`me-${before}`)
    expect(later.isOwner()).toBe(true)
  })

  it('unmarks the browser with ?me=0', async () => {
    localStorage.clear()
    ;(await freshAt('/?me=1')).markOwnerFromUrl()
    const off = await freshAt('/?me=0')
    off.markOwnerFromUrl()
    expect(off.isOwner()).toBe(false)
    expect(off.visitorId()).toMatch(/^v-/)
  })

  it('leaves an unmarked browser alone, whatever else the URL carries', async () => {
    localStorage.clear()
    const a = await freshAt('/?utm_source=x&me=yes')
    a.markOwnerFromUrl()
    expect(a.isOwner()).toBe(false)
  })

  it('still marks this page load when storage is blocked', async () => {
    localStorage.clear()
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    const a = await freshAt('/?me=1')
    a.markOwnerFromUrl()
    expect(a.visitorId()).toMatch(/^me-v-/)
    set.mockRestore(); get.mockRestore()
  })
})

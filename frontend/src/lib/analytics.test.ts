import { describe, it, expect, vi } from 'vitest'
import { track, visitorId, EVENTS } from './analytics'

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

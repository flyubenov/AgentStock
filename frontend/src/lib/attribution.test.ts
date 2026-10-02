import { describe, it, expect, vi, beforeEach } from 'vitest'

/** attribution.ts memoizes the visit in module state, so every test imports a
 *  fresh copy after arranging the URL, the referrer and storage. */
async function fresh(url: string, referrer = '') {
  window.history.replaceState(null, '', url)
  Object.defineProperty(document, 'referrer', { value: referrer, configurable: true })
  vi.resetModules()
  return import('./attribution')
}

beforeEach(() => {
  sessionStorage.clear()
})

describe('readTouch', () => {
  it('takes the channel from utm_source and keeps the other tags', async () => {
    const { readTouch } = await fresh('/t/NVDA?utm_source=X&utm_medium=paid&utm_campaign=oct-nvda&utm_content=card-a')
    expect(readTouch()).toEqual({
      channel: 'x', utm_source: 'x', utm_medium: 'paid', utm_campaign: 'oct-nvda',
      utm_content: 'card-a', landing: '/t/NVDA',
    })
  })

  it('falls back to ?ref when there is no utm_source', async () => {
    const { readTouch } = await fresh('/?ref=x')
    expect(readTouch()).toMatchObject({ channel: 'x', ref: 'x' })
  })

  it('falls back to the referring domain, keeping only the domain', async () => {
    const { readTouch } = await fresh('/', 'https://www.google.com/search?q=nvda+fair+value')
    const touch = readTouch()
    expect(touch).toMatchObject({ channel: 'google.com', referrer: 'google.com' })
    expect(JSON.stringify(touch)).not.toContain('nvda')
  })

  it('is direct with no tags and no referrer', async () => {
    const { readTouch } = await fresh('/')
    expect(readTouch()).toEqual({ channel: 'direct', landing: '/' })
  })

  it('ignores a referrer from our own site', async () => {
    const { readTouch } = await fresh('/checkout', `${window.location.origin}/`)
    expect(readTouch()).toEqual({ channel: 'direct', landing: '/checkout' })
  })

  it('cleans and shortens values so a hand-made link cannot stuff the sheet', async () => {
    const long = 'a'.repeat(300)
    const { readTouch } = await fresh(`/?utm_source=%3Cscript%3E&utm_campaign=${long}`)
    const touch = readTouch()
    expect(touch.channel).toBe('script')
    expect(touch.utm_campaign!.length).toBeLessThanOrEqual(100)
  })
})

describe('attribution', () => {
  it('keeps the first visit as the channel and reports this visit separately', async () => {
    const first = await fresh('/t/NVDA?utm_source=x')
    expect(first.attribution()).toMatchObject({ channel: 'x', visit_channel: 'x' })

    sessionStorage.clear() // a later visit: new tab, typed address
    const later = await fresh('/')
    expect(later.attribution()).toMatchObject({
      channel: 'x', utm_source: 'x', landing: '/t/NVDA', visit_channel: 'direct',
    })
  })

  it('keeps this visit\'s channel across an in-visit reload without tags', async () => {
    const first = await fresh('/?utm_source=reddit')
    first.captureAttribution()
    const reloaded = await fresh('/checkout')
    expect(reloaded.attribution().visit_channel).toBe('reddit')
  })

  it('removes the tags from the address bar so a copied link does not carry them', async () => {
    const { captureAttribution } = await fresh('/t/NVDA?utm_source=x&ref=x&keep=1#top')
    captureAttribution()
    expect(window.location.pathname + window.location.search + window.location.hash)
      .toBe('/t/NVDA?keep=1#top')
  })

  it('still works when storage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const { attribution } = await fresh('/?utm_source=hn')
    expect(attribution()).toMatchObject({ channel: 'hn', visit_channel: 'hn' })
  })
})

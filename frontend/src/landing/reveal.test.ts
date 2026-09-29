import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { REVEAL_SELECTOR, startReveal, STAGGER_MS } from './reveal'

type IOCb = (entries: { isIntersecting: boolean; target: Element }[]) => void
let observed: Element[] = []
let unobserved: Element[] = []
let fire: IOCb = () => {}
let disconnected = false

function stubBrowser({ reduced = false } = {}) {
  vi.stubGlobal('matchMedia', vi.fn((q: string) => ({ matches: reduced && q.includes('reduce') })))
  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: IOCb) { fire = cb }
    observe(e: Element) { observed.push(e) }
    unobserve(e: Element) { unobserved.push(e) }
    disconnect() { disconnected = true }
  })
}

/** Everything sits below the fold except what is listed in `inView`. */
function page(inView: string[] = []) {
  document.body.innerHTML = `
    <section class="hero"><div id="analyze" class="kicker">hero</div></section>
    <div class="qband"><div class="container">band</div></div>
    <section id="why"><div class="container"><div class="kicker">k</div>
      <div class="diff-grid">${'<div class="diff">c</div>'.repeat(5)}</div></div></section>
    <section id="pricing"><div class="container"><div class="price-grid">
      <div class="price-card" id="p1"></div><div class="price-card" id="p2"></div></div></div></section>`
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const top = inView.some(s => this.matches(s)) ? 100 : 2000
    return { top, bottom: top + 50, left: 0, right: 0, width: 0, height: 50, x: 0, y: top, toJSON: () => ({}) } as DOMRect
  })
  vi.stubGlobal('innerHeight', 900)
}

beforeEach(() => { observed = []; unobserved = []; disconnected = false; document.body.innerHTML = '' })
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('startReveal (spec §4 Motion)', () => {
  // Review Focus 1: jsdom has no matchMedia; the funnel tests stub only
  // IntersectionObserver and fire every callback — the reveal must stay out.
  it('does nothing where matchMedia or IntersectionObserver is missing', () => {
    page()
    vi.stubGlobal('matchMedia', undefined)
    vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} })
    startReveal()
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })

  it('does nothing when the visitor asks for reduced motion', () => {
    page(); stubBrowser({ reduced: true })
    startReveal()
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })

  it('hides below-the-fold blocks until they scroll in, never the hero', () => {
    page(); stubBrowser()
    startReveal()
    expect(document.querySelector('.hero .kicker')).not.toHaveClass('rv')
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
    expect(document.querySelectorAll('#why .diff.rv')).toHaveLength(5)
    expect(observed.length).toBe(document.querySelectorAll('.rv').length)
  })

  // Review Focus 2: a visitor landing on /#pricing sees the plans at once.
  it('leaves blocks that are already on screen alone', () => {
    page(['.price-card']); stubBrowser()
    startReveal()
    expect(document.querySelectorAll('.price-card.rv')).toHaveLength(0)
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
  })

  it('staggers cards in a row by 90 ms, capped at four steps', () => {
    page(); stubBrowser()
    startReveal()
    const delays = Array.from(document.querySelectorAll<HTMLElement>('#why .diff')).map(e => e.style.transitionDelay)
    expect(delays).toEqual(['0ms', `${STAGGER_MS}ms`, `${2 * STAGGER_MS}ms`, `${3 * STAGGER_MS}ms`, `${3 * STAGGER_MS}ms`])
  })

  it('shows a block once it intersects, and stops watching it', () => {
    page(); stubBrowser()
    startReveal()
    const band = document.querySelector('.qband .container')!
    fire([{ isIntersecting: false, target: band }])
    expect(band).not.toHaveClass('in')
    fire([{ isIntersecting: true, target: band }])
    expect(band).toHaveClass('in')
    expect(unobserved).toContain(band)
  })

  it('cleans up: disconnects and leaves everything visible', () => {
    page(); stubBrowser()
    const stop = startReveal()
    stop()
    expect(disconnected).toBe(true)
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })

  // The footer carries the not-investment-advice disclaimer. It is short, and at
  // the very bottom of a tall viewport it may never cross the observer's
  // threshold, so it must never be hidden in the first place.
  it('never hides the footer', () => {
    document.body.innerHTML = '<footer class="footer"><p>Not personalized investment advice.</p></footer>'
    expect(document.querySelector('.footer')!.matches(REVEAL_SELECTOR)).toBe(false)
    expect(document.querySelector('.footer p')!.matches(REVEAL_SELECTOR)).toBe(false)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from './LandingPage'
import { DEMO_RUN_LIMIT, runsUsed } from './demoLimit'
import type { TickerPayload } from './types'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    pageView: 'page_view', analysisStarted: 'analysis_started',
    analysisCompleted: 'analysis_completed', breakdownOpened: 'breakdown_opened',
    methodologyViewed: 'methodology_viewed', pricingViewed: 'pricing_viewed',
    planSelected: 'plan_selected', freePlanClicked: 'free_plan_clicked',
    watchlistClicked: 'watchlist_clicked', tickerLinkOpened: 'ticker_link_opened',
    shareClicked: 'share_clicked',
  },
}))

function payload(ticker: string, ok = true): TickerPayload {
  return {
    ticker, company_name: `${ticker} Inc.`, price: 100,
    quality: ok ? { score: 7, fundamentals_composite: 7, profile_label: 'Tech', categories: [] } as never : null,
    moat: null, fair_value: null, reward_risk: null, calibrations: [], errors: ok ? [] : ['failed'],
  }
}

/** Routes the two endpoints: the ticker check, and analyze (which echoes the asked
 *  tickers back as rows, failing any in `failing`). `check` overrides the ticker
 *  check's whole response (e.g. a 429). */
function server({ known = true, failing = [] as string[], check = undefined as unknown } = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/api/landing/ticker/')) {
      if (check) return check
      const t = decodeURIComponent(url.split('/').pop()!)
      return { ok: true, json: async () => ({ ticker: t, known, name: null }) }
    }
    const { tickers } = JSON.parse(String(init?.body))
    return { ok: true, json: async () => ({
      results: tickers.map((t: string) => payload(t, !failing.includes(t))),
      invalid: [], error: null }) }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function tracked() {
  const { track } = await import('../lib/analytics')
  return vi.mocked(track)
}

function show(raw: string) {
  return render(<MemoryRouter initialEntries={[`/t/${raw}`]}><LandingPage linkTicker={raw} /></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  window.history.replaceState(null, '', '/t/x')
})

describe('a /t/ link', () => {
  it('names the stock in the headline and shows its result, not AAPL', async () => {
    server()
    show('nvda')
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('NVDA: judge the business.'))
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(screen.queryByText('AAPL Inc.')).toBeNull()
    expect(screen.getByPlaceholderText('Try another ticker…')).toBeInTheDocument()
    expect(screen.getByText(/Live analysis · computed just now/)).toBeInTheDocument()
    expect(document.title).toBe('NVDA: Quality, Moat, Fair Value · Intrinsica')
  })

  it('fires ticker_link_opened once and runs as source link', async () => {
    server()
    show('NVDA')
    const track = await tracked()
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(track.mock.calls.filter(c => c[0] === 'ticker_link_opened'))
      .toEqual([['ticker_link_opened', { ticker: 'NVDA', known: true }]])
    expect(track).toHaveBeenCalledWith('analysis_started', expect.objectContaining({ source: 'link' }))
  })

  it('uses one free analysis while some remain, and another on a repeat visit', async () => {
    server()
    const first = show('NVDA')
    await waitFor(() => expect(runsUsed()).toBe(1))
    first.unmount()
    show('NVDA')
    await waitFor(() => expect(runsUsed()).toBe(2))
  })

  it('still shows the linked stock when the free analyses are used up, without counting', async () => {
    localStorage.setItem('intrinsica_demo_runs',
      JSON.stringify({ count: DEMO_RUN_LIMIT, windowStart: Date.now() }))
    server()
    show('NVDA')
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(runsUsed()).toBe(DEMO_RUN_LIMIT)
    expect(screen.getByText(/You've used all/)).toBeInTheDocument()
  })

  it.each([
    ['an unknown ticker', 'XYZQ', { known: false }, 'XYZQ'],
    ['a malformed link', 'a,b', {}, 'AB'],
    ['a failed analysis', 'NVDA', { failing: ['NVDA'] }, 'NVDA'],
  ])('falls back to the AAPL example for %s, in place', async (_label, raw, opts, shown) => {
    server(opts as never)
    show(raw)
    await waitFor(() => expect(screen.getByText('AAPL Inc.')).toBeInTheDocument())
    expect(screen.getByText(`We couldn't find ${shown}. Here's an example instead.`)).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^Judge the business/)
    expect(runsUsed()).toBe(0)
  })

  it('still shows the stock when the ticker check is rate-limited (429)', async () => {
    server({ check: { ok: false, status: 429,
      json: async () => ({ ticker: null, known: false, name: null }) } })
    show('NVDA')
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(screen.queryByText(/We couldn't find/)).toBeNull()
    expect(runsUsed()).toBe(1)
  })

  it('puts the card right after the headline on phones (class hook for the CSS)', async () => {
    server()
    const { container } = show('NVDA')
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(container.querySelector('header.hero.linked')).not.toBeNull()
  })
})

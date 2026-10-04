import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderToString } from 'react-dom/server'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import LandingPage, { FETCH_TIMEOUT_MS } from './LandingPage'
import { runsUsed } from './demoLimit'
import Layout from '../components/Layout'
import type { TickerPayload } from './types'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    pageView: 'page_view',
    analysisStarted: 'analysis_started',
    analysisCompleted: 'analysis_completed',
    breakdownOpened: 'breakdown_opened',
    methodologyViewed: 'methodology_viewed',
    pricingViewed: 'pricing_viewed',
    planSelected: 'plan_selected',
    freePlanClicked: 'free_plan_clicked',
    watchlistClicked: 'watchlist_clicked',
    tickerLinkOpened: 'ticker_link_opened',
    shareClicked: 'share_clicked',
  },
}))

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: async () => ({ results: [], invalid: [], error: null }),
  }))
})

function renderPage() {
  return render(<MemoryRouter><LandingPage /></MemoryRouter>)
}

// LandingPage kicks off an automatic sample analyze() on mount (plan-mandated —
// see LandingPage.tsx). That call is synchronous up to its first `await`, so
// `busy` is already true by the time `render()` returns, but the fetch/json
// resolution and the following setState calls land in a later microtask. Every
// test below waits for the button to settle back to its idle label before
// asserting or unmounting, so that settle happens inside `waitFor`'s act-aware
// polling instead of after the test body returns — the fix for the act(...)
// warnings this task's mount-effect change introduced. Do NOT drop this wait
// or replace it with a console mock: it must observe the real settle.
async function renderSettled() {
  const utils = renderPage()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
  })
  return utils
}

describe('LandingPage shell', () => {
  it('links to every section from the nav', async () => {
    await renderSettled()
    const hrefs = screen.getAllByRole('link').map(a => a.getAttribute('href'))
    for (const anchor of ['#analyze', '#how', '#why', '#workflow', '#pricing']) {
      expect(hrefs).toContain(anchor)
    }
  })

  // The nav test above only proves the links exist. This proves they land
  // somewhere: every anchor the nav offers has a section to scroll to, and the
  // page is assembled in the reading order the spec lays out — methodology,
  // then why, then the workflow. A section built but never mounted, or mounted
  // in the wrong place, fails here rather than in a screenshot.
  it('mounts the why and workflow sections, in order, after the framework', async () => {
    const { container } = await renderSettled()
    const ids = Array.from(container.querySelectorAll('main section[id]'))
      .map(s => s.id)
    expect(ids).toContain('how')
    expect(ids).toContain('why')
    expect(ids).toContain('workflow')
    expect(ids.indexOf('how')).toBeLessThan(ids.indexOf('why'))
    expect(ids.indexOf('why')).toBeLessThan(ids.indexOf('workflow'))
    expect(screen.getByText('Trust the analysis')).toBeInTheDocument()
    expect(screen.getByText('Analyze → Compare → Watch → Monitor')).toBeInTheDocument()
  })

  it('scopes its own light theme instead of changing the global dark one', async () => {
    const { container } = await renderSettled()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
  })

  it('leaves the global dark theme exactly as it found it', async () => {
    const before = document.body.style.backgroundColor
    const { unmount, container } = await renderSettled()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
    unmount()
    expect(document.body.style.backgroundColor).toBe(before)
  })

  it('records a page view once', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    expect(track).toHaveBeenCalledWith('page_view')
  })

  it('carries no card or payment input', async () => {
    const { container } = await renderSettled()
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs.some(i => /card|cvc|cvv|payment|expiry/i.test(i.outerHTML))).toBe(false)
  })

  it('never renders the analyst app nav — the landing page renders outside Layout', async () => {
    await renderSettled()
    expect(screen.queryByText('Database')).not.toBeInTheDocument()
  })
})

describe('LandingPage analyze (controller addition)', () => {
  it('renders the server error verbatim, not a locally generated message', async () => {
    const serverMessage = 'The analysis service is temporarily overloaded. Please try again in a minute.'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: [], error: serverMessage }),
    }))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(serverMessage)).toBeInTheDocument()
    })
  })
})

describe('LandingPage analyze (fix round 2)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('aborts a fetch that never settles: readable notice, button re-enabled', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url: string, opts: RequestInit) => new Promise((_resolve, reject) => {
      // Never resolves on its own — only reacts to the abort signal, exactly
      // like a stalled connection that never delivers a response.
      opts.signal?.addEventListener('abort', () => {
        reject(new DOMException('The operation was aborted.', 'AbortError'))
      })
    })))

    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    // The mount's automatic sample analyze has already set busy synchronously
    // (see LandingPage.tsx: setBusy(true) runs before the first await), so the
    // button reads its busy label immediately, before the timeout ever fires.
    expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(FETCH_TIMEOUT_MS)
    })

    expect(screen.getByText(
      'The analysis is taking longer than expected. Please try again.'
    )).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
    expect((screen.getByRole('button', { name: 'Analyze →' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('does not let a missing results field overwrite the server error', async () => {
    const serverMessage = 'A specific, server-written error message.'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      // `results` is deliberately absent — the backend always sends it, but this
      // proves a malformed response can't silently clobber the server's error
      // with the generic "could not be reached" fallback.
      json: async () => ({ invalid: [], error: serverMessage }),
    }))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(serverMessage)).toBeInTheDocument()
    })
    expect(screen.queryByText('The analysis could not be reached. Please try again.'))
      .not.toBeInTheDocument()
  })
})

describe('LandingPage demo limit (controller addition)', () => {
  it('records only typed runs, never the mount sample, in the analysis_started source prop', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
    })

    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['AAPL'], count: 1, source: 'sample' })
    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['NVDA'], count: 1, source: 'typed' })
  })

  it('shows the wall after the fifth typed run and still lets a sample run through', async () => {
    localStorage.setItem('intrinsica_demo_runs', JSON.stringify({
      count: 4, windowStart: Date.now(),
    }))
    // The typed run below must actually produce a row to count (fix round 1) —
    // the default beforeEach mock returns empty results, which would no longer
    // be recorded.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [{ ticker: 'NVDA' }], invalid: [], error: null }),
    }))
    await renderSettled()

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText(/see the plans/i)).toBeInTheDocument()
    })
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

    // A stored count of 5 means only the fifth typed run above landed — the
    // mount's sample run never touched the counter.
    expect(JSON.parse(localStorage.getItem('intrinsica_demo_runs')!).count).toBe(5)
  })

  it('refuses a typed run once already exhausted, but a fresh sample run at mount still fires', async () => {
    localStorage.setItem('intrinsica_demo_runs', JSON.stringify({
      count: 5, windowStart: Date.now(),
    }))
    const { track } = await import('../lib/analytics')
    // The wall is already exhausted at mount, so there is never an "Analyze →"
    // button to wait for here (renderSettled's own wait relies on it) — wait on
    // the wall text and the sample's track() call settling instead.
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/see the plans/i)).toBeInTheDocument()
    })

    // The wall replaces the input entirely — there is no control left to submit
    // a typed run through.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(track).toHaveBeenCalledWith('analysis_started',
        { tickers: ['AAPL'], count: 1, source: 'sample' })
    })
  })
})

// Fix round 1: a typed run must only consume an allowance once it actually
// produced something the visitor could see. analysis_started (asserted above)
// still fires unconditionally — it means "attempted", not "counted". These
// tests assert on the real counter (runsUsed(), backed by the same localStorage
// key demoLimit.ts reads) rather than a mock of it.
describe('LandingPage demo limit — only a successful typed run counts (fix round 1)', () => {
  it('does not count a typed run when the fetch throws', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText('The analysis could not be reached. Please try again.'))
        .toBeInTheDocument()
    })

    expect(runsUsed()).toBe(0)
  })

  it('shows the rate-limit message from a 429 and does not count the run', async () => {
    await renderSettled()
    const limited = 'Too many analyses from your network. Please wait a minute and try again.'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 429,
      json: async () => ({ results: [], invalid: [], error: limited }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText(limited)).toBeInTheDocument()
    })

    expect(runsUsed()).toBe(0)
  })

  it('does not count a typed run when the server returns an error (over the cap, empty input)', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: [], error: 'Over the free demo cap.' }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText('Over the free demo cap.')).toBeInTheDocument()
    })

    expect(runsUsed()).toBe(0)
  })

  it('does not count a typed run when every ticker came back invalid', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: ['ZZZZ'], error: null }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'ZZZZ')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText('Not recognised: ZZZZ')).toBeInTheDocument()
    })

    expect(runsUsed()).toBe(0)
  })

  it('says why a typed stock that reports in another currency was not computed', async () => {
    await renderSettled()
    const msg = "Data not available for companies that don't report in US dollars under US GAAP"
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [{ ticker: 'TM', errors: [msg] }], invalid: ['ZZZZ'], error: null }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'TM, ZZZZ')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText(`Not recognised: ZZZZ TM: ${msg}.`)).toBeInTheDocument()
    })
  })

  it('counts a typed run on a partial success — one bad ticker, one rendered result', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [{ ticker: 'NVDA' }], invalid: ['ZZZZ'], error: null }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'NVDA, ZZZZ')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText('Not recognised: ZZZZ')).toBeInTheDocument()
    })

    expect(runsUsed()).toBe(1)
  })
})

// Controller Addition 2: the compare chip is a prefill shortcut into the same
// analyze() path as the button, tagged 'sample', rendering into the same
// result card. Assertions are on rendered output (the DOM the
// real ResultCard produces), never on the fetch mock echoing itself.
// Every highlighted column carries DISTINCT values, and the winner is a
// different row in three of the four — a fixture where all three tickers share
// a moat, a gap and a ratio (as this one first did) cannot tell a working
// best-in-column highlight from a broken one.
const COMPARE_FIXTURE = {
  AAPL: { quality: 8.0, moat: 8.1, gap: 5, ratio: 2.4, value: 110 },
  MSFT: { quality: 9.5, moat: 7.2, gap: -3, ratio: 0.8, value: 120 },
  NVDA: { quality: 7.0, moat: 4.5, gap: 12, ratio: 1.1, value: 130 },
}

function compareRow(ticker: keyof typeof COMPARE_FIXTURE, over: { company_name?: string } = {}) {
  const f = COMPARE_FIXTURE[ticker]
  return {
    ticker, company_name: `${ticker} Inc.`, price: 100,
    quality: { score: f.quality, fundamentals_composite: f.quality,
               profile_label: null, categories: [] },
    moat: { score: f.moat, gated: false, excluded: [], factors: [] },
    fair_value: { value: f.value, gap_pct: f.gap, type_label: null, methods: [] },
    reward_risk: { ratio: f.ratio, tier: null, reward_score: 1, risk_score: 1,
                   reward: [], risk: [] },
    calibrations: [], errors: [],
    ...over,
  }
}

const COMPARE_RESULTS = () => ({
  results: [compareRow('AAPL'), compareRow('MSFT'), compareRow('NVDA')],
  invalid: [], error: null,
})

// The hero's result card and the breakdown dock (hero rework 2026-09-27).
const cardOf = () => document.querySelector<HTMLElement>('.hero-r .rc')!
const dockOf = () => document.querySelector<HTMLElement>('section.bk-dock')
const tile = (name: string) => within(cardOf()).getByRole('button', { name: new RegExp(`^${name}`) })

describe('LandingPage compare chip (controller addition 2)', () => {
  it('fills the input, analyzes the fixed trio as a sample run, and renders all three rows with the best-in-column highlight', async () => {
    const { track } = await import('../lib/analytics')
    // The mount's sample run uses the default empty-results stub, so the grid
    // is empty until the chip runs — every row asserted below is the chip's.
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))

    await waitFor(() => {
      expect(within(cardOf()).getByText('MSFT')).toBeInTheDocument()
    })
    expect(within(cardOf()).getByText('AAPL')).toBeInTheDocument()
    expect(within(cardOf()).getByText('NVDA')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('AAPL, MSFT, NVDA')
    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['AAPL', 'MSFT', 'NVDA'], count: 3, source: 'sample' })
    // Three tickers ran at once, so the card's header carries the run summary (spec 5.2).
    expect(cardOf().querySelector('.rc-head')).toHaveTextContent(/3 tickers · \d+\.\d s/)
    // The chip is a sample run, so the card keeps the live-example pill.
    expect(within(cardOf()).getByText(/Live example/)).toBeInTheDocument()

    // A different row wins quality, moat and the fair-value gap, so a
    // highlight stuck on one row — or on all of them — fails here.
    const rowOf = (t: string) => within(cardOf()).getByRole('button', { name: t }).closest('.rc-row') as HTMLElement
    const cell = (t: string, text: string) => within(rowOf(t)).getByText(text).closest('.rc-cell')!
    expect(cell('MSFT', '9.5')).toHaveClass('best')
    expect(cell('AAPL', '8.1')).toHaveClass('best')
    expect(cell('NVDA', '+12%')).toHaveClass('best')
    expect(cell('AAPL', '2.4×')).toHaveClass('best')
    expect(cell('AAPL', '8.0')).not.toHaveClass('best')
    expect(cell('NVDA', '4.5')).not.toHaveClass('best')
    expect(cardOf().querySelectorAll('.rc-cell.best')).toHaveLength(4)
  })

  it('keeps working after the typed allowance is exhausted, and never consumes it', async () => {
    const { track } = await import('../lib/analytics')
    localStorage.setItem('intrinsica_demo_runs', JSON.stringify({
      count: 5, windowStart: Date.now(),
    }))
    // The mount auto-run is NOT gated on `exhausted`, so it puts its own row in
    // the grid before the chip is ever clicked. Give it a fixture the chip's
    // rows cannot be confused with, and wait for it — otherwise every
    // assertion below would still pass with the chip's onClick deleted, which
    // is exactly how the previous version of this test passed vacuously.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({
        results: [compareRow('AAPL', { company_name: 'Mount Sample Only Inc.' })],
        invalid: [], error: null,
      }),
    }))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/see the plans/i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('Mount Sample Only Inc.')).toBeInTheDocument()
    })
    // The wall replaced the input/button, but the chip must still be present.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
    await waitFor(() => {
      expect(within(cardOf()).getByText('MSFT')).toBeInTheDocument()
    })
    // The chip's own run replaced the mount's single row with its three.
    expect(screen.queryByText('Mount Sample Only Inc.')).not.toBeInTheDocument()
    expect(within(cardOf()).getByText('NVDA')).toBeInTheDocument()
    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['AAPL', 'MSFT', 'NVDA'], count: 3, source: 'sample' })
    expect(screen.getByText(/see the plans/i)).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('intrinsica_demo_runs')!).count).toBe(5)
  })
  it('answers a watchlist star with the toast and records which ticker', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
    await waitFor(() => { expect(within(cardOf()).getByText('NVDA')).toBeInTheDocument() })
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Add NVDA to a watchlist' }))
    expect(track).toHaveBeenCalledWith('watchlist_clicked', { ticker: 'NVDA' })
    expect(screen.getByRole('status')).toHaveTextContent('Watchlists require an Intrinsica account. Start with Free.')
    await userEvent.click(screen.getByRole('button', { name: 'Add MSFT to a watchlist' }))
    expect(track).toHaveBeenCalledWith('watchlist_clicked', { ticker: 'MSFT' })
    expect(screen.getAllByRole('status')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  // Loading variant E (user decision 2026-09-26): from the click until the answer,
  // the button spins with the count, the live strip names the pending trio, and
  // the previous result is dimmed; all three clear when the rows land.
  it('shows the run in flight — button, live strip, dimmed old result — then settles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL', { company_name: 'Old Result Inc.' })],
                           invalid: [], error: null }),
    }))
    await renderSettled()
    await waitFor(() => { expect(screen.getByText('Old Result Inc.')).toBeInTheDocument() })

    let answer!: (v: unknown) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise(r => { answer = r })))
    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))

    expect(screen.getByRole('button', { name: 'Analyzing 3…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/Computing in parallel:.*AAPL.*MSFT.*NVDA/)
    expect(cardOf().querySelector('.stale')).not.toBeNull()

    await act(async () => { answer({ json: async () => COMPARE_RESULTS() }) })
    await waitFor(() => { expect(within(cardOf()).getByText('NVDA')).toBeInTheDocument() })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(cardOf().querySelector('.rc-head')).toHaveTextContent(/3 tickers · \d+\.\d s/)
    expect(cardOf().querySelector('.stale')).toBeNull()
    expect(screen.getByRole('button', { name: 'Analyze →' })).toBeEnabled()
  })
})

// Fix round 16d: `analysis_completed` was the only event on the branch whose
// PROPS nothing asserted — it appears elsewhere in event-NAME lists only
// (funnel.test.tsx, analytics.test.ts), so stripping it to
// `track(EVENTS.analysisCompleted)` left all 297 tests green. It also fired
// without `source`, while `analysis_started` four lines above carried it, so
// every page load emitted an unattributable completion: the mount auto-run is
// marketing, not visitor work, and could not be filtered out of the
// started -> completed step.
describe('LandingPage analysis_completed props (fix round 16d)', () => {
  const completions = (track: unknown) =>
    vi.mocked(track as (...a: unknown[]) => void).mock.calls
      .filter(c => c[0] === 'analysis_completed')
      .map(c => c[1] as Record<string, unknown>)

  it('stamps the mount sample and a typed run apart, on identical counts', async () => {
    const { track } = await import('../lib/analytics')
    // One row for BOTH runs on purpose. `count` is the only other prop that
    // could conceivably attribute a completion, and this is the ordinary case
    // where it cannot: sample AAPL is 1 and a typed single ticker is 1. If
    // `source` is dropped, the two payloads below become indistinguishable —
    // which is the whole defect.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL')], invalid: [], error: null }),
    }))
    await renderSettled()

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(completions(track)).toHaveLength(2)
    })

    const [sample, typed] = completions(track)
    // Exact key sets, both ways: a prop silently dropped fails here, and so
    // does an unplanned prop appearing. `duration_ms` is a clock reading, so
    // its VALUE is pinned by type and range below rather than by a literal —
    // everything else is pinned exactly.
    expect(Object.keys(sample).sort()).toEqual(['count', 'duration_ms', 'source'])
    expect(Object.keys(typed).sort()).toEqual(['count', 'duration_ms', 'source'])

    expect(sample.source).toBe('sample')
    expect(typed.source).toBe('typed')
    // Stated as its own assertion rather than left implicit: the two runs agree
    // on `count`, so `source` is doing the attributing and nothing else can.
    expect(typed.count).toBe(sample.count)
    expect(sample.count).toBe(1)

    for (const props of [sample, typed]) {
      expect(typeof props.duration_ms).toBe('number')
      expect(Number.isFinite(props.duration_ms as number)).toBe(true)
      expect(props.duration_ms as number).toBeGreaterThanOrEqual(0)
    }
  })

  // The compare chip runs three tickers AS A SAMPLE. Without `source` this
  // completion is the one most easily mistaken for a visitor's own multi-ticker
  // run, and its duration is a cold three-engine fetch that would otherwise be
  // averaged in with warm cached AAPL.
  it('stamps the three-ticker compare chip as a sample, not as visitor work', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => COMPARE_RESULTS(),
    }))
    await renderSettled()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: /compare/i }))
    await waitFor(() => {
      expect(completions(track)).toHaveLength(1)
    })

    expect(completions(track)[0]).toMatchObject({ source: 'sample', count: 3 })
    expect(Object.keys(completions(track)[0]).sort())
      .toEqual(['count', 'duration_ms', 'source'])
  })
})

// Fix round 1: `track` used to be called from inside the setOpen updater.
// React requires updaters to be pure and StrictMode (main.tsx) deliberately
// double-invokes them, so breakdown_opened fired twice per expand in
// development. This is the only render in the suite wrapped in StrictMode —
// without it the assertion below cannot observe the defect at all.
describe('LandingPage breakdown analytics under StrictMode', () => {
  const opens = (track: unknown) =>
    vi.mocked(track as (...a: unknown[]) => void).mock.calls.filter(c => c[0] === 'breakdown_opened')
  const mount = async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL')], invalid: [], error: null }),
    }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => { expect(within(cardOf()).getByText('AAPL Inc.')).toBeInTheDocument() })
  }

  // Spec 5.2 (hero rework): nothing opens by itself any more.
  it('opens nothing on load and records nothing', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('fires breakdown_opened exactly once when a tile opens it, with that tile as the tab', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    vi.mocked(track).mockClear()
    await userEvent.click(tile('Moat'))
    expect(dockOf()).not.toBeNull()
    expect(opens(track)).toEqual([['breakdown_opened', { ticker: 'AAPL', assessment: 'Moat' }]])
  })

  it('switches tab from another tile without recording a second open, and folds from the same tile', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    await userEvent.click(tile('Moat'))
    vi.mocked(track).mockClear()

    await userEvent.click(tile('Fair Value'))
    expect(dockOf()).not.toBeNull()
    expect(tile('Fair Value')).toHaveAttribute('aria-pressed', 'true')
    expect(tile('Moat')).toHaveAttribute('aria-pressed', 'false')
    expect(opens(track)).toEqual([])

    await userEvent.click(tile('Fair Value'))
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('folds from Close and records nothing for it', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    await userEvent.click(tile('Quality'))
    vi.mocked(track).mockClear()
    await userEvent.click(within(dockOf()!).getByRole('button', { name: 'Close' }))
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('opens a comparison row on the current tab, once, and folds it from the same row', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => { expect(within(cardOf()).getByRole('button', { name: 'NVDA' })).toBeInTheDocument() })
    // Move the shared assessment to Reward / Risk from the Framework tabs first.
    await userEvent.click(document.querySelectorAll<HTMLElement>('.mcards button')[3])
    vi.mocked(track).mockClear()

    const nvda = within(cardOf()).getByRole('button', { name: 'NVDA' })
    await userEvent.click(nvda)
    expect(nvda).toHaveAttribute('aria-expanded', 'true')
    expect(opens(track)).toEqual([['breakdown_opened', { ticker: 'NVDA', assessment: 'Reward / Risk' }]])

    await userEvent.click(nvda)
    expect(nvda).toHaveAttribute('aria-expanded', 'false')
    expect(dockOf()).toBeNull()
    expect(opens(track)).toHaveLength(1)
  })
})

describe('Layout nav (controller addition)', () => {
  it('points the Analyse link at /app, not /', () => {
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Layout><div /></Layout>
      </MemoryRouter>
    )
    const analyse = screen.getByRole('link', { name: 'Analyse' })
    expect(analyse.getAttribute('href')).toBe('/app')
  })

  it('highlights Analyse when on /app', () => {
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Layout><div /></Layout>
      </MemoryRouter>
    )
    const analyse = screen.getByRole('link', { name: 'Analyse' })
    expect(analyse.className).toContain('text-blue-400')
  })
})

// Task 10: `renderBreakdown` used to return null, so nothing here proved the
// expanded row renders anything at all. These assert on the real Breakdown's
// output and on the one piece of state the page shares with it — `assessment`,
// which the card tiles write and the dock reads.
const BREAKDOWN_ROW: TickerPayload = {
  ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
  quality: {
    score: 9.1, fundamentals_composite: 9.1, profile_label: 'Tech / Growth',
    categories: [{
      key: 'I', name: 'Growth & Margins', weight_pct: 35, score: 8,
      metrics: [{ label: 'Revenue growth (3-yr)', raw: 8.1, display: '+8.1% / yr', score: 6,
                  weight_pct: 17.5, excluded: false, excluded_by: null }],
    }],
  },
  moat: { score: 9, gated: false, excluded: [],
          factors: [{ label: 'ROIC level', group: 'Magnitude', display: '55%', score: 9, weight_pct: 20 }] },
  fair_value: { value: 211, gap_pct: -9.05, type_label: 'Mega Cap', methods: [] },
  reward_risk: { ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
                 reward: [], risk: [] },
  calibrations: [], errors: [],
}

describe('LandingPage breakdown dock', () => {
  async function openFromTile(name = 'Quality') {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const utils = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    await userEvent.click(tile(name))
    return utils
  }

  it('opens the real factor table under the hero, not an empty panel', async () => {
    await openFromTile()
    const dock = dockOf()!
    expect(dock.previousElementSibling).toHaveClass('hero')
    expect(within(dock).getByText(/Growth & Margins/)).toBeInTheDocument()
    expect(within(dock).getByText('Revenue growth (3-yr)')).toBeInTheDocument()
    expect(within(dock).getByText('+8.1% / yr')).toBeInTheDocument()
  })

  it('opens on the tab of the tile that was clicked', async () => {
    await openFromTile('Moat')
    expect(within(dockOf()!).getAllByText('ROIC level').length).toBeGreaterThan(0)
    expect(within(dockOf()!).queryByText(/Growth & Margins/)).not.toBeInTheDocument()
  })

  it('switches the open panel from its own tabs, and the tile highlight follows', async () => {
    await openFromTile()
    await userEvent.click(within(dockOf()!).getByRole('button', { name: /^Fair Value/ }))
    expect(within(dockOf()!).getByText('Mega Cap valuation blend')).toBeInTheDocument()
    expect(tile('Fair Value')).toHaveAttribute('aria-pressed', 'true')
  })

  it('closes when a new run lands', async () => {
    await openFromTile()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
    await waitFor(() => { expect(within(cardOf()).getByRole('button', { name: 'MSFT' })).toBeInTheDocument() })
    expect(dockOf()).toBeNull()
  })
})

describe('LandingPage result card states (hero rework)', () => {
  // Final review: the mount sample starts in a passive effect, which the browser may
  // paint before. The first frame must already say the sample is running — never the
  // could-not-load message. A server render runs no effects, so it shows that frame.
  it('paints "running" in the very first frame, before the sample has even started', () => {
    const html = renderToString(<MemoryRouter><LandingPage /></MemoryRouter>)
    expect(html).toContain('Running the analysis…')
    expect(html).not.toContain('could not be loaded')
  })

  it('shows the running frame, then the could-not-load message, when the sample fails', async () => {
    let fail!: (e: unknown) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise((_r, rej) => { fail = rej })))
    renderPage()
    expect(cardOf()).toHaveTextContent('Running the analysis…')
    await act(async () => { fail(new TypeError('network down')) })
    await waitFor(() => {
      expect(cardOf()).toHaveTextContent('The live example could not be loaded. Try a ticker on the left.')
    })
    expect(document.querySelector('.hero-l')).toHaveTextContent('The analysis could not be reached. Please try again.')
  })

  it('keeps the previous card and its open breakdown when a run returns no rows', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    await userEvent.click(tile('Moat'))

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: ['ZZZZ'], error: null }),
    }))
    await userEvent.type(screen.getByRole('textbox'), 'ZZZZ')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => { expect(screen.getByText('Not recognised: ZZZZ')).toBeInTheDocument() })

    expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument()
    expect(dockOf()).not.toBeNull()
  })

  it('labels a typed run as the visitor’s own', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('NVDA')], invalid: [], error: null }),
    }))
    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => { expect(within(cardOf()).getByText('Your analysis')).toBeInTheDocument() })
  })

  it('places the question band between the hero and the Framework', async () => {
    const { container } = await renderSettled()
    const band = container.querySelector('.qband')!
    const how = container.querySelector('section#how')!
    expect(band.compareDocumentPosition(how) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.querySelector('.hero')!.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

// Task 11: the framework section reads and writes the SAME `assessment` the
// card tiles and the open breakdown dock use. There is one piece of
// state for the concept, so these tests assert the jump in both directions —
// card -> framework and framework -> an already-open breakdown dock.
describe('LandingPage framework section (task 11)', () => {
  const detail = (c: HTMLElement) => c.querySelector<HTMLElement>('.mdetail')!

  it('moves the Framework panel when a card tile picks an assessment — one shared state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    expect(detail(container).querySelector('.dh')).toHaveTextContent('Quality')
    await userEvent.click(tile('Moat'))
    expect(detail(container).querySelector('.dh')).toHaveTextContent('Moat')
    expect(detail(container)).toHaveTextContent('Cash-backing')
  })

  it('moves an already-open breakdown panel when a framework card is clicked', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    })
    await userEvent.click(tile('Quality'))
    const panel = dockOf()!
    expect(within(panel).getByText(/Growth & Margins/)).toBeInTheDocument()

    await userEvent.click(container.querySelectorAll('.mcards button')[1])

    expect(within(dockOf()!).getAllByText('ROIC level').length)
      .toBeGreaterThan(0)
    expect(within(dockOf()!).queryByText(/Growth & Margins/))
      .not.toBeInTheDocument()
  })

  it('records methodology_viewed with the assessment chosen, and only from here', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    vi.mocked(track).mockClear()

    // A card tile writes the same state but is not the methodology section, so it
    // must not fire the event (spec section 9).
    await userEvent.click(tile('Reward / Risk'))
    expect(track).not.toHaveBeenCalledWith('methodology_viewed', expect.anything())

    await userEvent.click(container.querySelectorAll('.mcards button')[2])
    expect(track).toHaveBeenCalledWith('methodology_viewed', { assessment: 'Fair Value' })
  })

  it('fires nothing when a calibration row is expanded — spec section 9 excludes it', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))

    expect(screen.getByText(/When it applies/)).toBeInTheDocument()
    expect(track).not.toHaveBeenCalled()
  })
})

// Task 13: the pricing section is the closest thing on this page to a purchase
// flow, and the analytics rule that governs it is not symmetric. plan_selected
// and free_plan_clicked carry the same props and route to the same checkout,
// but free_plan_clicked is excluded from paid-intent conversion — so the two
// must never fire for each other. Each test below asserts both the event that
// should fire and the one that must not.
describe('LandingPage pricing section (task 13)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('mounts the pricing section last, after the workflow', async () => {
    const { container } = await renderSettled()
    const ids = Array.from(container.querySelectorAll('main section[id]')).map(s => s.id)
    // Presence first, then order: indexOf returns -1 for a section that never
    // mounted, so "workflow before pricing" is otherwise satisfied by a page
    // with no workflow section at all.
    expect(ids).toContain('workflow')
    expect(ids).toContain('pricing')
    expect(ids.indexOf('workflow')).toBeLessThan(ids.indexOf('pricing'))
    // "Last" is the claim in the name, so it is the claim asserted: pricing is
    // the end of the page, with nothing mounted below the plans.
    expect(ids[ids.length - 1]).toBe('pricing')
    expect(screen.getByText('Choose your plan')).toBeInTheDocument()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose Pro' })).toBeInTheDocument()
  })

  it('records plan_selected with the plan and billing period, not free_plan_clicked', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))

    expect(track).toHaveBeenCalledWith('plan_selected', { plan: 'Pro', billing: 'annual' })
    expect(track).not.toHaveBeenCalledWith('free_plan_clicked', expect.anything())
  })

  // Spec section 9 and spec 6: "Free clicks must be logged as their own
  // analytics event and must never be counted in paid-intent conversion."
  it('records a Free click as its own event, and never as plan_selected', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))

    expect(track).toHaveBeenCalledWith('free_plan_clicked',
      { plan: 'Free', billing: 'annual', source: 'pricing' })
    expect(track).not.toHaveBeenCalledWith('plan_selected', expect.anything())
    // Nor may it carry a prop that would let it be re-counted as paid intent:
    // `source` says WHERE the free click happened, never that it was a purchase.
    const call = vi.mocked(track).mock.calls.find(c => c[0] === 'free_plan_clicked')!
    expect(Object.keys(call[1] as object).sort()).toEqual(['billing', 'plan', 'source'])
  })

  /** Task 16c. free_plan_clicked fires from TWO places — this CTA and the
   *  checkout's confirm button — and both used to carry only { plan, billing },
   *  so the two fires were indistinguishable on the wire. The cost is not a
   *  doubled count (which is at least visible); it is that free drop-off —
   *  of the visitors who clicked Free here, how many went on to confirm there —
   *  cannot be computed at all, and it is the only drop-off number the Free
   *  funnel has. `source` is the same disambiguation Task 8d gave
   *  analysis_started for the same reason. A second event name is NOT the fix:
   *  spec section 9's list is closed.
   *
   *  plan_selected, the paid CTA on this very line, deliberately does NOT carry
   *  it: it fires from one site only, and the paid funnel's two stages are
   *  already separate event names (plan_selected, then payment_button_clicked).
   *  A prop that can only ever hold one value carries no information and would
   *  invite the false inference that a `source: 'checkout'` plan_selected
   *  exists. The test above pins plan_selected's props exactly, so adding one
   *  there fails loudly rather than silently. */
  it('stamps a Free click with the pricing CTA as its source', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))

    const free = vi.mocked(track).mock.calls.filter(c => c[0] === 'free_plan_clicked')
    expect(free).toHaveLength(1)
    expect(free[0][1]).toEqual({ plan: 'Free', billing: 'annual', source: 'pricing' })
    // Asserted as a mis-stamp, not merely as a missing stamp: 'checkout' here
    // would report a confirm that never happened, which is worse than no prop.
    expect(track).not.toHaveBeenCalledWith('free_plan_clicked',
      expect.objectContaining({ source: 'checkout' }))
  })

  // Spec section 9: the billing toggle is deliberately uninstrumented. It still
  // has to work — the prices and the period carried into the checkout both move.
  it('switches the prices on the toggle and fires nothing for the switch itself', async () => {
    const { track } = await import('../lib/analytics')
    await renderSettled()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Monthly' }))

    expect(screen.getByText('$21.99')).toBeInTheDocument()
    expect(screen.queryByText('$18.00')).not.toBeInTheDocument()
    expect(track).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))
    expect(track).toHaveBeenCalledWith('plan_selected',
      { plan: 'Unlimited', billing: 'monthly' })
  })

  it('reports pricing_viewed once, when the section is scrolled to rather than mounted', async () => {
    const seen: ((entries: { isIntersecting: boolean }[]) => void)[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: (entries: { isIntersecting: boolean }[]) => void) { seen.push(cb) }
      observe() {}
      disconnect() {}
    })
    const { track } = await import('../lib/analytics')
    await renderSettled()
    expect(track).not.toHaveBeenCalledWith('pricing_viewed')

    expect(seen).toHaveLength(1)
    seen[0]([{ isIntersecting: true }])
    seen[0]([{ isIntersecting: true }])

    expect(vi.mocked(track).mock.calls.filter(c => c[0] === 'pricing_viewed'))
      .toHaveLength(1)
  })

  it('routes the chosen plan and billing period to the checkout', async () => {
    function CheckoutStub() {
      const { search } = useLocation()
      return <div>checkout{search}</div>
    }
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/checkout" element={<CheckoutStub />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'Monthly' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))

    expect(screen.getByText('checkout?plan=Unlimited&billing=monthly')).toBeInTheDocument()
  })

  // The single hardest constraint in the project, asserted against the whole
  // assembled page rather than the section alone — anchored on the pricing
  // content really being there first.
  it('adds no card, payment, address or name field to the page', async () => {
    const { container } = await renderSettled()
    const pricing = container.querySelector<HTMLElement>('section#pricing')
    expect(pricing).not.toBeNull()
    expect(within(pricing!).getByText('Choose your plan')).toBeInTheDocument()
    expect(within(pricing!).getByText('$35.00')).toBeInTheDocument()

    expect(pricing!.querySelectorAll('input, textarea, select, form')).toHaveLength(0)
    // The analyzer's ticker box is the page's only input, and it takes a ticker.
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs).toHaveLength(1)
    expect(inputs[0].outerHTML).not.toMatch(/card|cvc|cvv|payment|expiry|address|cardholder/i)
    expect(container.textContent).not.toMatch(/card number|cvc|cvv|billing address/i)
  })
})

describe('LandingPage — scroll reveal', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

  it('starts the reveal once the page has mounted', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
    vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue(
      { top: 5000, bottom: 5050, left: 0, right: 0, width: 0, height: 50, x: 0, y: 5000, toJSON: () => ({}) } as DOMRect)
    await renderSettled()
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
    expect(document.querySelector('#analyze')!.closest('.rv')).toBeNull()
  })
})

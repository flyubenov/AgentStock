import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
// ResultGrid this task wires up. Assertions are on rendered output (the DOM the
// real ResultGrid produces), never on the fetch mock echoing itself.
// Every highlighted column carries DISTINCT values, and the winner is a
// different row in three of the four — a fixture where all three tickers share
// a moat, a gap and a ratio (as this one first did) cannot tell a working
// best-in-column highlight from a broken one.
const COMPARE_FIXTURE = {
  AAPL: { quality: 8.0, moat: 81, gap: 5, ratio: 2.4, value: 110 },
  MSFT: { quality: 9.5, moat: 72, gap: -3, ratio: 0.8, value: 120 },
  NVDA: { quality: 7.0, moat: 45, gap: 12, ratio: 1.1, value: 130 },
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
      expect(screen.getByText('MSFT')).toBeInTheDocument()
    })
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('NVDA')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('AAPL, MSFT, NVDA')
    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['AAPL', 'MSFT', 'NVDA'], count: 3, source: 'sample' })

    // A different row wins quality, moat and the fair-value gap, so a
    // highlight stuck on one row — or on all of them — fails here.
    const grid = screen.getByText('MSFT').closest('table')!
    const rowOf = (t: string) => within(grid).getByText(t).closest('tr')!
    expect(within(rowOf('MSFT')).getByText('9.5')).toHaveClass('best')
    expect(within(rowOf('AAPL')).getByText('81')).toHaveClass('best')
    expect(within(rowOf('NVDA')).getByText('+12.0%')).toHaveClass('best')
    expect(within(rowOf('AAPL')).getByText('2.4')).toHaveClass('best')
    expect(within(rowOf('AAPL')).getByText('8.0')).not.toHaveClass('best')
    expect(within(rowOf('NVDA')).getByText('45')).not.toHaveClass('best')
    expect(grid.querySelectorAll('.best')).toHaveLength(4)
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
      expect(screen.getByText('MSFT')).toBeInTheDocument()
    })
    // The chip's own run replaced the mount's single row with its three.
    expect(screen.queryByText('Mount Sample Only Inc.')).not.toBeInTheDocument()
    expect(screen.getByText('NVDA')).toBeInTheDocument()
    expect(track).toHaveBeenCalledWith('analysis_started',
      { tickers: ['AAPL', 'MSFT', 'NVDA'], count: 3, source: 'sample' })
    expect(screen.getByText(/see the plans/i)).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('intrinsica_demo_runs')!).count).toBe(5)
  })
})

// Fix round 1: `track` used to be called from inside the setOpen updater.
// React requires updaters to be pure and StrictMode (main.tsx) deliberately
// double-invokes them, so breakdown_opened fired twice per expand in
// development. This is the only render in the suite wrapped in StrictMode —
// without it the assertion below cannot observe the defect at all.
describe('LandingPage breakdown analytics under StrictMode (fix round 1)', () => {
  const opens = (track: unknown) =>
    vi.mocked(track as (...a: unknown[]) => void).mock.calls
      .filter(c => c[0] === 'breakdown_opened')

  it('fires breakdown_opened exactly once per expand', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL')], invalid: [], error: null }),
    }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => {
      expect(screen.getByText('AAPL Inc.')).toBeInTheDocument()
    })
    vi.mocked(track).mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'AAPL' }))

    expect(opens(track)).toEqual([['breakdown_opened', { ticker: 'AAPL' }]])
  })

  it('fires nothing when the row is collapsed again', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL')], invalid: [], error: null }),
    }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => {
      expect(screen.getByText('AAPL Inc.')).toBeInTheDocument()
    })
    vi.mocked(track).mockClear()

    const control = screen.getByRole('button', { name: 'AAPL' })
    await userEvent.click(control)
    expect(control).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(control)
    expect(control).toHaveAttribute('aria-expanded', 'false')

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
// which the hero cards write and the panel reads.
const BREAKDOWN_ROW: TickerPayload = {
  ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
  quality: {
    score: 9.1, fundamentals_composite: 9.1, profile_label: 'Tech / Growth',
    categories: [{
      key: 'I', name: 'Growth & Margins', weight_pct: 35, score: 8,
      metrics: [{ label: 'Revenue growth (3-yr)', raw: 0.08, score: 6,
                  weight_pct: 17.5, excluded: false, excluded_by: null }],
    }],
  },
  moat: { score: 90, gated: false, excluded: [],
          factors: [{ label: 'ROIC level', points: 18, max_points: 20, weight_pct: 20 }] },
  fair_value: { value: 211, gap_pct: -9.05, type_label: 'Mega Cap', methods: [] },
  reward_risk: { ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
                 reward: [], risk: [] },
  calibrations: [], errors: [],
}

describe('LandingPage breakdown panel (task 10)', () => {
  async function openRow() {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const utils = renderPage()
    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button', { name: 'AAPL' }))
    return utils
  }

  // Scoped to the expanded row's own `.bd` panel since task 11: the framework
  // section below the grid names the same Quality category, so an unscoped
  // getByText would now match two elements and fail on ambiguity rather than on
  // anything real.
  it('expands a row into the real factor table, not an empty panel', async () => {
    const { container } = await openRow()
    const panel = container.querySelector<HTMLElement>('.bd')!
    expect(within(panel).getByText('Growth & Margins')).toBeInTheDocument()
    expect(within(panel).getByText('Revenue growth (3-yr)')).toBeInTheDocument()
    for (const name of ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('switches the open panel when a breakdown tab is clicked', async () => {
    const { container } = await openRow()
    await userEvent.click(screen.getByRole('button', { name: 'Moat' }))
    const panel = container.querySelector<HTMLElement>('.bd')!
    expect(within(panel).getByText('ROIC level')).toBeInTheDocument()
    expect(within(panel).queryByText('Growth & Margins')).not.toBeInTheDocument()
  })

  // The hero cards and the breakdown share one `assessment`, so choosing an
  // assessment up in the hero must move the panel already open below it.
  it('follows the hero assessment cards, which write the same assessment state', async () => {
    const { container } = await openRow()
    const cards = container.querySelectorAll('.assess4 .it')
    await userEvent.click(cards[2])
    expect(screen.getByText('Mega Cap')).toBeInTheDocument()
    expect(screen.queryByText('Growth & Margins')).not.toBeInTheDocument()
  })
})

// Task 11: the framework section reads and writes the SAME `assessment` the
// hero cards and every expanded breakdown panel use. There is one piece of
// state for the concept, so these tests assert the jump in both directions —
// hero -> framework and framework -> an already-open breakdown panel.
describe('LandingPage framework section (task 11)', () => {
  const detail = (c: HTMLElement) => c.querySelector<HTMLElement>('.mdetail')!

  it('shows the framework panel for the assessment the hero cards select', async () => {
    const { container } = await renderSettled()
    expect(detail(container)).toHaveTextContent('How strong is the underlying business?')
    expect(detail(container)).toHaveTextContent('35% of the score · 7 metrics')

    await userEvent.click(container.querySelectorAll('.assess4 .it')[1])

    expect(detail(container)).toHaveTextContent('How durable are its competitive advantages?')
    expect(detail(container)).toHaveTextContent('40 of 100 points')
    expect(detail(container)).not.toHaveTextContent('35% of the score · 7 metrics')
  })

  it('moves an already-open breakdown panel when a framework card is clicked', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button', { name: 'AAPL' }))
    const panel = container.querySelector<HTMLElement>('.bd')!
    expect(within(panel).getByText('Growth & Margins')).toBeInTheDocument()

    await userEvent.click(container.querySelectorAll('.mcards button')[1])

    expect(within(container.querySelector<HTMLElement>('.bd')!).getByText('ROIC level')).toBeInTheDocument()
    expect(within(container.querySelector<HTMLElement>('.bd')!).queryByText('Growth & Margins'))
      .not.toBeInTheDocument()
  })

  it('records methodology_viewed with the assessment chosen, and only from here', async () => {
    const { track } = await import('../lib/analytics')
    const { container } = await renderSettled()
    vi.mocked(track).mockClear()

    // A hero card writes the same state but is not the methodology section, so
    // it must not fire the event (spec section 9's list is closed and is about
    // funnel steps, not every control that touches `assessment`).
    await userEvent.click(container.querySelectorAll('.assess4 .it')[3])
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
    expect(ids).toContain('pricing')
    expect(ids.indexOf('workflow')).toBeLessThan(ids.indexOf('pricing'))
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

    expect(track).toHaveBeenCalledWith('free_plan_clicked', { plan: 'Free', billing: 'annual' })
    expect(track).not.toHaveBeenCalledWith('plan_selected', expect.anything())
    // Nor may it carry a prop that would let it be re-counted as paid intent.
    const call = vi.mocked(track).mock.calls.find(c => c[0] === 'free_plan_clicked')!
    expect(Object.keys(call[1] as object).sort()).toEqual(['billing', 'plan'])
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
    expect(within(pricing!).getByText('$25.00')).toBeInTheDocument()

    expect(pricing!.querySelectorAll('input, textarea, select, form')).toHaveLength(0)
    // The analyzer's ticker box is the page's only input, and it takes a ticker.
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs).toHaveLength(1)
    expect(inputs[0].outerHTML).not.toMatch(/card|cvc|cvv|payment|expiry|address|cardholder/i)
    expect(container.textContent).not.toMatch(/card number|cvc|cvv|billing address/i)
  })
})

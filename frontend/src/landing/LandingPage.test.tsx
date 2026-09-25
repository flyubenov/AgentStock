import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import LandingPage, { FETCH_TIMEOUT_MS } from './LandingPage'
import Layout from '../components/Layout'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    pageView: 'page_view',
    analysisStarted: 'analysis_started',
    analysisCompleted: 'analysis_completed',
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

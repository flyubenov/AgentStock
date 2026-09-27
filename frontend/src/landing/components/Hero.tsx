import { useState, type ReactNode } from 'react'
import { DEMO_RUN_LIMIT, DEMO_WINDOW_DAYS } from '../demoLimit'
import type { AnalyzeSource } from '../types'

// The demo/UX pre-check only. The server (backend/routers/landing.py MAX_TICKERS)
// is the source of truth for the real cap — this value and its message can drift
// from the server's; if they ever do, the server's `error` string wins (see
// LandingPage.tsx, which renders it verbatim over anything generated here).
export const MAX_TICKERS = 3

// Fixed compare trio. All three are seeded into the server cache at startup (see
// backend), so a chip run resolves from cache and feels instant. Read from this
// one exported constant rather than re-typed anywhere else.
export const COMPARE_TICKERS = ['AAPL', 'MSFT', 'NVDA'] as const

export const ASSESSMENTS = [
  { name: 'Quality', color: 'var(--q)',
    question: 'How strong is the underlying business?' },
  { name: 'Moat', color: 'var(--mo)',
    question: 'How durable are its competitive advantages?' },
  { name: 'Fair Value', color: 'var(--fv)',
    question: 'What is the business worth based on its fundamentals and valuation methods?' },
  { name: 'Reward / Risk', color: 'var(--rr)',
    question: 'How attractive is the current price relative to intrinsic value and downside risk?' },
]

interface Props {
  /** Called for both a typed submission ('typed') and the compare chip
   *  ('sample') — the source travels through to analysis_started and to the
   *  no-account demo limit, which only 'typed' runs consume. */
  onAnalyze: (tickers: string[], source: AnalyzeSource) => void
  /** True while an analysis is in flight. Disables BOTH the Analyze button
   *  and the compare chip: concurrent chip clicks would each fire their own
   *  analysis_started, inflating the very metric the chip exists to measure. */
  busy: boolean
  /** How many tickers the in-flight run covers ("Analyzing 3…"). Loading variant E. */
  busyCount?: number
  /** True once this browser has used up its free demo runs (demoLimit.ts). */
  exhausted: boolean
  /** A run's notice ("Not recognised: X", a server error, a timeout), shown under the
   *  input it is about (spec 5.2, hero rework 2026-09-27). */
  notice?: string | null
  /** The result card: the hero's right column (spec 5.1). */
  card: ReactNode
}

export default function Hero({ onAnalyze, busy, busyCount = 0, exhausted, notice, card }: Props) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit() {
    const tickers = value.split(',').map(t => t.trim().toUpperCase()).filter(Boolean)
    if (tickers.length === 0) {
      setError('Enter at least one ticker.')
      return
    }
    if (tickers.length > MAX_TICKERS) {
      setError(`Up to ${MAX_TICKERS} tickers per analysis run.`)
      return
    }
    setError(null)
    onAnalyze(tickers, 'typed')
  }

  // The compare chip is a prefill shortcut, not a mode toggle: it writes the
  // trio into the visible input (so the visitor learns what they would have
  // typed) and runs the exact same analyze() path as the button, tagged
  // 'sample' so it never counts against the typed demo allowance.
  function runCompare() {
    setValue(COMPARE_TICKERS.join(', '))
    setError(null)
    onAnalyze([...COMPARE_TICKERS], 'sample')
  }

  // Spec 5.1 (hero rework 2026-09-27): promise and analyzer on the left, the live
  // result card on the right; one column on a phone, input first. The wordmark
  // heading, the pipeline strip and the four assessment links are gone — the card
  // shows the four scores themselves, and the questions live in the Framework.
  return (
    <header className="hero">
      <div className="hero-in">
        <div className="hero-l">
          <h1 className="hero-h1">Judge the business.{' '}<br />Then judge the price.</h1>
          <p className="hero-sub">
            Quality and Moat tell you how good the company is; Fair Value and Reward/Risk
            tell you whether the price makes sense. All from the fundamentals, all shown.
          </p>
          <div className="analyzer" id="analyze">
            {exhausted ? (
              <p className="an-wall">
                You've used all {DEMO_RUN_LIMIT} free analyses in a rolling{' '}
                {DEMO_WINDOW_DAYS}-day window. <a href="#pricing">See the plans</a> to
                keep analyzing.
              </p>
            ) : (
              <>
                <div className="an-row">
                  <div className="an-field">
                    <input
                      value={value}
                      aria-label="Tickers"
                      onChange={e => setValue(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') submit() }}
                      placeholder="Enter one or more tickers — e.g. NVDA, AMD, AVGO"
                    />
                  </div>
                  <button className="an-btn" type="button" onClick={submit} disabled={busy}>
                    {busy
                      ? <><span className="spin" aria-hidden="true" />
                          {busyCount > 1 ? `Analyzing ${busyCount}…` : 'Analyzing…'}</>
                      : 'Analyze →'}
                  </button>
                </div>
                {error && <p className="an-error">{error}</p>}
              </>
            )}

            {/* Outside the exhausted branch on purpose: chip runs never consume the
                typed allowance, so this keeps working after the wall appears. */}
            <div className="chips">
              <span className="lbl">Or try:</span>
              <button type="button" className="chip" onClick={runCompare} disabled={busy}>
                Compare {COMPARE_TICKERS.join(' · ')}
              </button>
            </div>
            {!exhausted && (
              <p className="an-micro">Up to {MAX_TICKERS} tickers at a time · no account needed</p>
            )}
          </div>
          {notice && <p className="notice">{notice}</p>}
        </div>
        <div className="hero-r">{card}</div>
      </div>
    </header>
  )
}

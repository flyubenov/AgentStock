import { useState } from 'react'
import { DEMO_RUN_LIMIT, DEMO_WINDOW_DAYS } from '../demoLimit'
import { PIPELINE } from '../content/framework'
import type { AnalyzeSource, AssessmentId } from '../types'

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
  onSelectAssessment: (id: AssessmentId) => void
  /** True while an analysis is in flight. Disables BOTH the Analyze button
   *  and the compare chip: concurrent chip clicks would each fire their own
   *  analysis_started, inflating the very metric the chip exists to measure. */
  busy: boolean
  /** True once this browser has used up its free demo runs (frontend/src/
   *  landing/demoLimit.ts). Replaces the ticker input/button with a short
   *  message pointing at pricing — sample and compare-chip runs are unaffected,
   *  since those never go through this control. */
  exhausted: boolean
}

export default function Hero({ onAnalyze, onSelectAssessment, busy, exhausted }: Props) {
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

  return (
    <header className="hero">
      <div className="container">
        <div className="brand">Intrinsica</div>
        <div className="h3">Fundamental Stock Analysis</div>

        {/* What Intrinsica is, as a flow: it does not show raw financial data, it
            turns the fundamentals into four scores through its own methodology.
            The last step lands on the four assessments directly below. This
            replaces the v21 sub-line (user decision, variant B3). */}
        <div className="pipe">
          {PIPELINE.map((step, i) => (
            <span key={step} className="pipe-step-wrap">
              {i > 0 && <span className="ar" aria-hidden="true">→</span>}
              <span className={i === PIPELINE.length - 1 ? 'st out' : 'st'}>{step}</span>
            </span>
          ))}
        </div>

        {/* Each assessment is a link to the methodology section that also selects
            that assessment's tab there (spec 5.1: "clicking jumps to the
            methodology section and selects that assessment's tab"). */}
        <div className="assess4">
          {ASSESSMENTS.map((a, i) => (
            <a
              key={a.name}
              className="it"
              href="#how"
              title={`How ${a.name} is assessed`}
              onClick={() => onSelectAssessment(i as AssessmentId)}
            >
              <div className="nm">
                <span className="dot" style={{ background: a.color }} />
                {a.name} <span className="go" aria-hidden="true">→</span>
              </div>
              <div className="q">{a.question}</div>
            </a>
          ))}
        </div>

        <div className="analyzer" id="analyze">
          {exhausted ? (
            <p className="an-wall">
              You've used all {DEMO_RUN_LIMIT} free analyses this browser gets in a
              rolling {DEMO_WINDOW_DAYS}-day window. <a href="#pricing">See the plans</a> to
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
                  {busy ? 'Analyzing…' : 'Analyze →'}
                </button>
              </div>
              {error && <p className="an-error">{error}</p>}
            </>
          )}

          {/* Outside the exhausted branch on purpose: chip runs are served from
              the server cache at zero cost to the visitor's typed allowance, so
              this must keep working after the wall above appears. Styled with the
              mock's own `.chips` / `.chip` rules, which v21 defines under the
              analyzer. */}
          <div className="chips">
            <span className="lbl">Or try:</span>
            <button type="button" className="chip" onClick={runCompare} disabled={busy}>
              Compare {COMPARE_TICKERS.join(' · ')}
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

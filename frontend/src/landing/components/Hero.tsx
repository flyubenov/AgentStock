import { useState } from 'react'
import type { AssessmentId } from '../types'

// The demo/UX pre-check only. The server (backend/routers/landing.py MAX_TICKERS)
// is the source of truth for the real cap — this value and its message can drift
// from the server's; if they ever do, the server's `error` string wins (see
// LandingPage.tsx, which renders it verbatim over anything generated here).
export const MAX_TICKERS = 3

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
  onAnalyze: (tickers: string[]) => void
  onSelectAssessment: (id: AssessmentId) => void
  busy: boolean
}

export default function Hero({ onAnalyze, onSelectAssessment, busy }: Props) {
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
    onAnalyze(tickers)
  }

  return (
    <header className="hero">
      <div className="container">
        <div className="brand">Intrinsica</div>
        <div className="h3">Fundamental Stock Analysis</div>

        <div className="assess4">
          {ASSESSMENTS.map((a, i) => (
            <button
              key={a.name}
              type="button"
              className="it"
              onClick={() => onSelectAssessment(i as AssessmentId)}
            >
              <span className="nm">
                <span className="dot" style={{ background: a.color }} />
                {a.name} <span className="go">→</span>
              </span>
              <span className="q">{a.question}</span>
            </button>
          ))}
        </div>

        <p className="sub">
          Evaluate stocks using a consistent, transparent fundamental framework.
        </p>

        <div className="analyzer" id="analyze">
          <div className="an-row">
            <div className="an-field">
              <input
                value={value}
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
        </div>
      </div>
    </header>
  )
}

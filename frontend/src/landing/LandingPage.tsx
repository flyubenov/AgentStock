import { useCallback, useEffect, useState } from 'react'
import './theme.css'
import Nav from './components/Nav'
import Hero from './components/Hero'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'
import { API_BASE } from '../lib/api'
import type { AnalyzeResponse, AssessmentId, TickerPayload } from './types'

const SAMPLE = 'AAPL'

export default function LandingPage() {
  const [rows, setRows] = useState<TickerPayload[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<AssessmentId>(0)

  const analyze = useCallback(async (tickers: string[]) => {
    setBusy(true)
    setNotice(null)
    track(EVENTS.analysisStarted, { tickers, count: tickers.length })
    const started = Date.now()
    try {
      const resp = await fetch(`${API_BASE}/api/landing/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers }),
      })
      const body: AnalyzeResponse = await resp.json()
      // The server's `error` is already reader-facing copy (landing.py checks the
      // real cap before anything expensive); render it verbatim rather than any
      // locally-generated message so client/server cap drift never reaches a
      // visitor as a stale guess.
      if (body.error) setNotice(body.error)
      else if (body.invalid.length) setNotice(`Not recognised: ${body.invalid.join(', ')}`)
      setRows(body.results)
      track(EVENTS.analysisCompleted, { duration_ms: Date.now() - started,
                                        count: body.results.length })
    } catch {
      setNotice('The analysis could not be reached. Please try again.')
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    track(EVENTS.pageView)
    void analyze([SAMPLE])
  }, [analyze])

  // index.css sets a global dark body background; the elastic overscroll gutter
  // (below short content, and the rubber-band area past the top/bottom on touch
  // devices) shows through the .intrinsica wrapper straight to that dark body. Set
  // the body background to match this page's own light background while mounted,
  // and restore whatever was there before on unmount so the dark analyst app gets
  // its background back untouched.
  useEffect(() => {
    const previous = document.body.style.backgroundColor
    document.body.style.backgroundColor = '#ffffff'
    return () => {
      document.body.style.backgroundColor = previous
    }
  }, [])

  // `rows` and `assessment` are held here for the results/framework sections Tasks
  // 9–13 add to this file — they read these values as props, not this component.
  // Referencing them as a no-op keeps this file compiling under noUnusedLocals on
  // its own until those tasks land; delete this line when they consume the state.
  void rows
  void assessment

  return (
    <div className="intrinsica">
      <Nav />
      <main>
        <Hero onAnalyze={analyze} onSelectAssessment={setAssessment} busy={busy} />
        {notice && <p className="notice container">{notice}</p>}
        {/* The results grid, methodology, why, workflow and pricing sections mount
            here in the tasks that follow; `rows` and `assessment` feed them. */}
      </main>
      <SiteFooter />
    </div>
  )
}

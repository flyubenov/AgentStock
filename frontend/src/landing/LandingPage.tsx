import { useCallback, useEffect, useState } from 'react'
import './theme.css'
import Nav from './components/Nav'
import Hero from './components/Hero'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'
import { API_BASE } from '../lib/api'
import { canAnalyze, recordRun } from './demoLimit'
import type { AnalyzeResponse, AssessmentId, TickerPayload } from './types'

/** 'sample' is the mount auto-run (and, from Task 9, the compare chip) — served
 *  from cache, marketing content, never counted against the demo limit.
 *  'typed' is a visitor's own analysis and is the only source that consumes an
 *  allowance (see demoLimit.ts). */
type AnalyzeSource = 'sample' | 'typed'

const SAMPLE = 'AAPL'

// Guards a dead connection, not a slow engine — the backend's own per-ticker
// guard (PER_TICKER_TIMEOUT, backend/orchestrator/batch.py, 120s at the time of
// writing) already fails a hung engine fast, and landing.py's three tickers run
// concurrently rather than serially, so a legitimate run never approaches this.
// This timeout exists only to abort a stalled connection whose response never
// arrives, so it is set well above the server's own cap rather than anywhere
// near it — the goal is to catch "gone", not to race "slow".
export const FETCH_TIMEOUT_MS = 150_000

export default function LandingPage() {
  const [rows, setRows] = useState<TickerPayload[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<AssessmentId>(0)
  // Whether this browser has used up its free demo runs. Checked once at mount
  // and re-checked after every typed run; sample runs never touch it. Backed by
  // demoLimit.ts, which fails open — so this starts `false` (not exhausted)
  // whenever storage is unavailable, never locking out a real visitor.
  const [exhausted, setExhausted] = useState(() => !canAnalyze())

  const analyze = useCallback(async (tickers: string[], source: AnalyzeSource) => {
    setBusy(true)
    setNotice(null)
    if (source === 'typed') {
      recordRun()
      setExhausted(!canAnalyze())
    }
    track(EVENTS.analysisStarted, { tickers, count: tickers.length, source })
    const started = Date.now()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
    try {
      const resp = await fetch(`${API_BASE}/api/landing/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers }),
        signal: controller.signal,
      })
      const body: AnalyzeResponse = await resp.json()
      // The backend's four return paths always emit the full three-key shape, so
      // `results` is never actually missing — but if it ever were, an unguarded
      // `.length`/`setRows` here would throw and fall into the catch below,
      // silently overwriting a real server `error` with the generic network
      // message. `?? []` keeps that guarantee from being load-bearing.
      const results = body.results ?? []
      // The server's `error` is already reader-facing copy (landing.py checks the
      // real cap before anything expensive); render it verbatim rather than any
      // locally-generated message so client/server cap drift never reaches a
      // visitor as a stale guess.
      if (body.error) setNotice(body.error)
      else if (body.invalid.length) setNotice(`Not recognised: ${body.invalid.join(', ')}`)
      setRows(results)
      track(EVENTS.analysisCompleted, { duration_ms: Date.now() - started,
                                        count: results.length })
    } catch (err) {
      // A raw AbortError (or any other exception) must never reach the DOM as
      // its own text — both branches below are fixed, reader-facing copy.
      const aborted = err instanceof DOMException && err.name === 'AbortError'
      setNotice(aborted
        ? 'The analysis is taking longer than expected. Please try again.'
        : 'The analysis could not be reached. Please try again.')
    } finally {
      clearTimeout(timeoutId)
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    track(EVENTS.pageView)
    void analyze([SAMPLE], 'sample')
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
        <Hero
          onAnalyze={tickers => analyze(tickers, 'typed')}
          onSelectAssessment={setAssessment}
          busy={busy}
          exhausted={exhausted}
        />
        {notice && <p className="notice container">{notice}</p>}
        {/* The results grid, methodology, why, workflow and pricing sections mount
            here in the tasks that follow; `rows` and `assessment` feed them. */}
      </main>
      <SiteFooter />
    </div>
  )
}

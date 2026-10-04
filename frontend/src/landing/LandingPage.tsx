import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './theme.css'
import Nav from './components/Nav'
import Hero from './components/Hero'
import ResultCard from './components/ResultCard'
import OpenBreakdown from './components/OpenBreakdown'
import QuestionBand from './components/QuestionBand'
import WatchToast from './components/WatchToast'
import Framework from './components/Framework'
import Why from './components/Why'
import Workflow from './components/Workflow'
import Pricing from './components/Pricing'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'
import { API_BASE } from '../lib/api'
import { canAnalyze, recordRun } from './demoLimit'
import { normalizeTicker, noticeLabel } from './ticker'
import { computed, unsupportedNotice } from './format'
import { FRAMEWORK } from './content/framework'
import { startReveal } from './reveal'
import type { Billing } from './content/plans'
import type {
  AnalyzeResponse, AnalyzeSource, AssessmentId, FreeClickSource, TickerPayload,
} from './types'

const SAMPLE = 'AAPL'

// Guards a dead connection, not a slow engine — the backend's own per-ticker
// guard (PER_TICKER_TIMEOUT, backend/orchestrator/batch.py, 120s at the time of
// writing) already fails a hung engine fast, and landing.py's three tickers run
// concurrently rather than serially, so a legitimate run never approaches this.
// This timeout exists only to abort a stalled connection whose response never
// arrives, so it is set well above the server's own cap rather than anywhere
// near it — the goal is to catch "gone", not to race "slow".
export const FETCH_TIMEOUT_MS = 150_000


type AnalyzeOutcome = 'ok' | 'empty' | 'error'

export default function LandingPage({ linkTicker }: { linkTicker?: string } = {}) {
  const [rows, setRows] = useState<TickerPayload[]>([])
  // True from the first render: the mount sample (below) always runs, but it starts in
  // a passive effect the browser may paint before. Starting idle would flash the
  // card's could-not-load message for a frame on every page load (final review).
  const [busy, setBusy] = useState(true)
  // The tickers of the run in flight, for the live strip and the button count.
  const [pending, setPending] = useState<string[]>([])
  // The watchlist toast: null when hidden, otherwise a click counter that re-keys
  // the toast so a second click restarts its timer. The clicked ticker goes on the
  // event only — the toast's copy does not name it.
  const [watch, setWatch] = useState<number | null>(null)
  const watchFor = useCallback((ticker: string) => {
    track(EVENTS.watchlistClicked, { ticker })
    setWatch(w => (w ?? 0) + 1)
  }, [])
  const closeWatch = useCallback(() => setWatch(null), [])
  const [notice, setNotice] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<AssessmentId>(0)
  // Whether this browser has used up its free demo runs. Checked once at mount
  // and re-checked after every typed run; sample runs never touch it. Backed by
  // demoLimit.ts, which fails open — so this starts `false` (not exhausted)
  // whenever storage is unavailable, never locking out a real visitor.
  const [exhausted, setExhausted] = useState(() => !canAnalyze())
  // How long the last run took, for the card's run summary (spec 5.2).
  const [lastMs, setLastMs] = useState<number | null>(null)
  // The billing period the pricing cards show, and the one a plan choice carries
  // into the checkout. Annual by default (spec 5.7). Owned here rather than
  // inside Pricing because the checkout has to be told which period was on
  // screen when the visitor chose. Switching it fires no analytics: spec
  // section 9's list is closed and names the billing toggle among the things
  // deliberately left uninstrumented — plan_selected already carries the period
  // that was actually chosen, which is the only one worth counting.
  const [billing, setBilling] = useState<Billing>('annual')
  const navigate = useNavigate()

  // Both branches route to the same checkout, worded differently there (spec 6):
  // pointing Free back at the demo was considered and rejected, because the demo
  // is not the Free plan. The event, however, is deliberately NOT the same.
  // free_plan_clicked is its own event and is excluded from paid-intent
  // conversion — clicking Free is the opposite of a purchase signal — so it
  // carries the same props but never rides plan_selected, and nothing here lets
  // it be counted as one.
  const choosePlan = useCallback((plan: string, b: Billing) => {
    if (plan === 'Free') {
      // `source` because free_plan_clicked ALSO fires from the checkout's
      // confirm button with the same plan and billing. Without it the two
      // funnel stages increment one undifferentiated counter and free drop-off
      // — of those who clicked Free here, how many confirmed there — is not
      // derivable at all. Spec section 9's list is closed, so this is a prop on
      // the existing event and not a second event name; analysis_started makes
      // the identical move with AnalyzeSource. Written as an if/else rather
      // than the previous ternary because the two branches no longer post the
      // same props, and a ternary that hides that is how they drifted.
      track(EVENTS.freePlanClicked,
            { plan, billing: b, source: 'pricing' satisfies FreeClickSource })
    } else {
      // Deliberately unstamped: plan_selected fires here and nowhere else, and
      // the paid stages are already separate names (plan_selected, then
      // payment_button_clicked). A constant prop would add no information.
      track(EVENTS.planSelected, { plan, billing: b })
    }
    navigate(`/checkout?plan=${encodeURIComponent(plan)}&billing=${b}`)
  }, [navigate])

  // Stable identity on purpose: Pricing's intersection observer is keyed on this
  // callback, so an inline arrow would tear the observer down and rebuild it on
  // every render of the page.
  const reportPricingView = useCallback(() => track(EVENTS.pricingViewed), [])

  // Which ticker's breakdown the dock under the hero is showing, if any (spec 5.3,
  // hero rework 2026-09-27). The tab is the page's single `assessment`, shared with
  // the card's tiles, the dock's own tabs and the Framework section.
  const [openTicker, setOpenTicker] = useState<string | null>(null)
  // The source of the run whose rows the card shows: it picks the card's pill
  // ("Live example" for a sample, "Your analysis" for a typed run).
  const [rowsSource, setRowsSource] = useState<AnalyzeSource | null>(null)
  // The canonical ticker while the page is featuring a /t/ link; null otherwise
  // (including after a link falls back to the example).
  const [linked, setLinked] = useState<string | null>(null)
  // The last run's "declined for its reporting currency" notice, read by the /t/ link
  // fallback so it says why rather than "couldn't find" (format.unsupportedNotice).
  const declined = useRef<string | null>(null)

  // breakdown_opened fires only on a closed -> open transition, and beside the state
  // change, never inside an updater (StrictMode double-invokes updaters — fix round 1).
  // A tile on the ticker already open switches the tab; the same tile again folds it.
  // Tab switches and folds are uninstrumented (spec section 9).
  const openTile = useCallback((ticker: string, tab: AssessmentId) => {
    const wasOpen = openTicker === ticker
    if (wasOpen && assessment === tab) { setOpenTicker(null); return }
    setAssessment(tab)
    setOpenTicker(ticker)
    if (!wasOpen) track(EVENTS.breakdownOpened, { ticker, assessment: FRAMEWORK[tab].name })
  }, [openTicker, assessment])

  // A comparison row opens on whichever tab the page is on.
  const openRow = useCallback((ticker: string) => {
    if (openTicker === ticker) { setOpenTicker(null); return }
    setOpenTicker(ticker)
    track(EVENTS.breakdownOpened, { ticker, assessment: FRAMEWORK[assessment].name })
  }, [openTicker, assessment])
  const closeBreakdown = useCallback(() => setOpenTicker(null), [])

  // `countRun`: whether a successful run uses one of the free analyses. Typed runs
  // do; a link run passes canAnalyze() (spec D5: a link always shows its stock, but
  // only uses an analysis while one remains). Resolves true when a usable row came
  // back, so the link flow can fall back when it did not.
  // Resolves 'ok' (a usable row came back), 'empty' (an answer with no usable row: the
  // stock did not compute) or 'error' (the server refused or the fetch failed: nothing
  // is known about the stock). The link flow falls back to "couldn't find" only on
  // 'empty'. `keepNotice`: leave the current notice standing as this run starts.
  const analyze = useCallback(async (
    tickers: string[], source: AnalyzeSource, countRun = source === 'typed', keepNotice = false,
  ): Promise<AnalyzeOutcome> => {
    setBusy(true)
    setPending(tickers)
    // A run the visitor starts themselves (or the example) ends the linked view:
    // headline, title and phone order go back to normal. The link run itself keeps it.
    if (source !== 'link') setLinked(null)
    if (!keepNotice) setNotice(null)
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
      declined.current = body.error ? null : unsupportedNotice(results)
      if (body.error) setNotice(body.error)
      else {
        const parts = [body.invalid.length ? `Not recognised: ${body.invalid.join(', ')}` : null, declined.current]
          .filter(Boolean)
        if (parts.length) setNotice(parts.join(' '))
      }
      // A run that produced no rows (all invalid, a server error) leaves the previous
      // card — and any open breakdown — in place: an empty card would leave a hole in
      // the hero (spec 5.2, hero rework). The notice above says what happened.
      if (results.length > 0) {
        setRows(results)
        setRowsSource(source)
        setOpenTicker(null)
        setLastMs(Date.now() - started)
      }
      // The allowance means "a run the visitor got value from" — distinct from
      // analysis_started above, which means "a run was attempted" and fires
      // unconditionally. Only count a typed run once it actually produced at
      // least one row: a partial success (one bad ticker, others rendered) still
      // showed the visitor something and counts; a server error (over the cap,
      // empty input — no engines ran) or an all-invalid response (no rows) does
      // not. A thrown/aborted fetch never reaches here at all, so it can't count
      // either — see the catch block below.
      // A link run counts only when its stock actually showed (a failed link run
      // falls back to the example and must cost the visitor nothing); typed runs keep
      // the row-count rule.
      if (countRun && !body.error
          && (source === 'link' ? results.some(computed) : results.length > 0)) {
        recordRun()
        setExhausted(!canAnalyze())
      }
      // `source` rides the completion for the same reason it rides
      // analysis_started (Task 8d): the mount auto-run below fires one of
      // these on every single page load, and nothing else in the payload can
      // tell it from a visitor's own run — sample AAPL is count 1 and a typed
      // single ticker is count 1, and the compare chip's three tickers are a
      // sample too. Without it the started -> completed step reads ~100% for
      // everyone and duration_ms averages a warm cached AAPL against cold
      // multi-ticker work. It is already in scope and already tested above.
      // A link run that showed nothing falls back to the example; it is not a completed
      // analysis, so it must not inflate the started -> completed step.
      if (source !== 'link' || results.some(computed)) {
        track(EVENTS.analysisCompleted, { duration_ms: Date.now() - started,
                                          count: results.length, source })
      }
      if (body.error) return 'error'
      return results.some(computed) ? 'ok' : 'empty'
    } catch (err) {
      // A raw AbortError (or any other exception) must never reach the DOM as
      // its own text — both branches below are fixed, reader-facing copy.
      const aborted = err instanceof DOMException && err.name === 'AbortError'
      setNotice(aborted
        ? 'The analysis is taking longer than expected. Please try again.'
        : 'The analysis could not be reached. Please try again.')
      return 'error'
    } finally {
      clearTimeout(timeoutId)
      setBusy(false)
      setPending([])
    }
  }, [])

  useEffect(() => {
    track(EVENTS.pageView)
    if (linkTicker === undefined) {
      void analyze([SAMPLE], 'sample')
      return
    }
    let live = true
    const fallBack = (reason: string | null = null) => {
      if (!live) return
      setLinked(null)
      // replaceState, not navigate(): navigating to "/" would unmount this page and
      // mount a fresh one, losing the notice. The router doesn't need to know — the
      // page already renders what "/" renders.
      window.history.replaceState(window.history.state, '', '/')
      void analyze([SAMPLE], 'sample')
      setNotice(reason
        ? `${reason} Here's an example instead.`
        : `We couldn't find ${noticeLabel(linkTicker)}. Here's an example instead.`)
    }
    void (async () => {
      const t = normalizeTicker(linkTicker)
      let known = false
      if (t) {
        // Show the ticker at once (spec 4): the headline and phone order must not flip
        // after the check. fallBack() undoes this if the link turns out unusable.
        setLinked(t)
        setPending([t])
        try {
          const r = await fetch(`${API_BASE}/api/landing/ticker/${encodeURIComponent(t)}`)
          // A non-OK answer (e.g. the 429 rate limit, whose body says known:false) is
          // a failed check, not a verdict: try the analysis, fall back only if it fails.
          known = r.ok ? Boolean((await r.json()).known) : true
        } catch {
          known = true // the check itself failed: try the analysis, fall back if it fails
        }
      }
      if (!live) return
      track(EVENTS.tickerLinkOpened, { ticker: t ?? noticeLabel(linkTicker), known })
      if (!t || !known) return fallBack()
      // Spec D5: a link always shows its stock; it uses a free analysis only while
      // one remains. canAnalyze() is read BEFORE the run.
      const outcome = await analyze([t], 'link', canAnalyze())
      if (!live) return
      if (outcome === 'empty') return fallBack(declined.current)
      if (outcome === 'error') {
        // Rate limited, or the server could not be reached: that says nothing about the
        // stock, so no "couldn't find" and the address stays (spec 9: the 429 copy is the
        // notice and the example card stays). analyze() has put its own notice up; the
        // example runs under it, and the headline stops naming a stock with no card.
        setLinked(null)
        void analyze([SAMPLE], 'sample', false, true)
      }
    })()
    return () => { live = false }
  }, [analyze, linkTicker])

  useEffect(() => {
    if (!linked) return
    const previous = document.title
    document.title = `${linked}: Quality, Moat, Fair Value · Intrinsica`
    return () => { document.title = previous }
  }, [linked])

  // Spec §4 Motion: sections float in on scroll. Started once, after the first
  // render has put every section in the DOM.
  useEffect(() => startReveal(), [])

  // index.css sets a global dark body background; the elastic overscroll gutter
  // (below short content, and the rubber-band area past the top/bottom on touch
  // devices) shows through the .intrinsica wrapper straight to that dark body. Set
  // the body background to match this page's own light background while mounted,
  // and restore whatever was there before on unmount so the dark analyst app gets
  // its background back untouched.
  // The mock's smooth in-page scrolling (nav anchors) is set on
  // <html>, so it is applied and restored the same way.
  useEffect(() => {
    const previous = document.body.style.backgroundColor
    const previousScroll = document.documentElement.style.scrollBehavior
    document.body.style.backgroundColor = '#ffffff'
    document.documentElement.style.scrollBehavior = 'smooth'
    return () => {
      document.body.style.backgroundColor = previous
      document.documentElement.style.scrollBehavior = previousScroll
    }
  }, [])

  const openRowData = rows.find(r => r.ticker === openTicker) ?? null

  return (
    <div className="intrinsica">
      <Nav />
      <main>
        <Hero
          onAnalyze={analyze}
          busy={busy}
          busyCount={pending.length}
          exhausted={exhausted}
          notice={notice}
          linked={linked}
          card={
            <ResultCard
              rows={rows}
              source={rowsSource}
              pending={pending}
              busy={busy}
              ms={lastMs}
              open={openTicker ? { ticker: openTicker, tab: assessment } : null}
              onTile={openTile}
              onRow={openRow}
              onWatch={watchFor}
            />
          }
        />
        {openRowData && (
          <OpenBreakdown row={openRowData} tab={assessment} onTab={setAssessment} onClose={closeBreakdown} />
        )}
        <QuestionBand />
        {/* The framework tabs are the third reader of the page's single
            `assessment`, beside the result card's tiles and the open
            breakdown dock — picking "Moat" in any of the three shows Moat in
            all three, which is the point of there being one piece of state.
            methodology_viewed is fired here rather than inside Framework so the
            component that owns the state owns its instrumentation; the event
            itself is spec section 9's, and nothing new is introduced. Framework
            tab switches are not otherwise tracked, and neither are its
            calibration row expands — section 9 names both as deliberately
            uninstrumented. */}
        <Framework
          tab={assessment}
          onTab={id => {
            setAssessment(id)
            track(EVENTS.methodologyViewed, { assessment: FRAMEWORK[id].name })
          }}
        />
        {/* Both are content-only and prop-less: nothing in either reads or
            writes the page's `assessment`, so neither is wired to it. */}
        <Why />
        <Workflow />
        {/* pricing_viewed is fired from here, not from inside Pricing, for the
            same reason methodology_viewed is: the component that owns the state
            owns the instrumentation. Pricing only reports that it scrolled into
            view; whether that is worth an event is this page's decision. */}
        <Pricing
          billing={billing}
          onBilling={setBilling}
          onChoose={choosePlan}
          onView={reportPricingView}
        />
      </main>
      {watch !== null && <WatchToast key={watch} onClose={closeWatch} />}
      <SiteFooter />
    </div>
  )
}

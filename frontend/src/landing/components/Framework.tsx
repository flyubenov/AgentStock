import { useState } from 'react'
import { CALIBRATIONS, FRAMEWORK, OVERVIEW } from '../content/framework'
import Tip from './Tip'
import type { AssessmentId } from '../types'

/** What each calibration tag means, shown as the mock's hover tooltip (also on
 *  keyboard focus — see Tip). */
const TAG_TIPS = {
  cond: "Not always on — this calibration fires only when the company's data matches a specific pattern.",
  guard: 'Guarded: it can only ever correct a distortion — never inflate a score.',
  live: "Whether it fired for a given stock is shown on that stock's result.",
}

/** Spec 5.4: overview card -> four clickable assessment cards -> one detail
 *  panel, identical in shape for all four.
 *
 *  Every string comes from content/framework.ts, and this file renders the same
 *  markup for whichever assessment is selected. That is the whole reason the
 *  copy is data: the panels are required to be structurally identical, and a
 *  requirement that lives in four hand-written JSX blocks is a requirement that
 *  drifts. Framework.test.tsx walks all four tabs against the content module.
 *
 *  `tab` is the page's single `assessment` (LandingPage.tsx) — the same value
 *  the hero cards write and every expanded row's breakdown panel reads. There is
 *  deliberately no local copy of it here: picking "Moat" in this section and
 *  expanding a grid row must show the same assessment.
 *
 *  Switching assessment fires no analytics: spec section 9's event list is
 *  closed and does not instrument framework tab switches. `methodology_viewed`
 *  is fired by LandingPage, which owns the state this section writes. */
export default function Framework({ tab, onTab }: {
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
}) {
  // Which calibration row is expanded, by name. Collapsed by default (spec 5.4
  // item 5), and one at a time — these rows are long, and two open at once
  // pushes the second one's trigger off the screen that opened it. Purely local
  // presentation state, unlike `tab`, which the whole page shares.
  const [openCal, setOpenCal] = useState<string | null>(null)
  // A calibration can affect two assessments — Tangible-ROIC is listed under
  // both Quality and Moat — so without this an expanded row follows the reader
  // across a tab switch and greets them already open on a panel they have only
  // just arrived at. Spec 5.4 item 5's "all collapsed by default" is about
  // arriving at a panel, not about this section's first render, so the
  // expansion is dropped whenever `tab` moves. Deliberately React's documented
  // render-phase adjustment rather than an effect: an effect would paint the
  // stale open row for a frame before collapsing it, and it would be a second
  // set-state-in-effect on a page that already carries one.
  const [shownTab, setShownTab] = useState<AssessmentId>(tab)
  if (shownTab !== tab) {
    setShownTab(tab)
    setOpenCal(null)
  }
  const a = FRAMEWORK[tab]
  const cals = CALIBRATIONS.filter(c => c.affects.includes(a.name))

  return (
    <section className="section stage" id="how">
      <div className="container">
        <div className="ovcard">
          <div className="kicker">The framework</div>
          <h2 className="stitle">How Intrinsica works</h2>
          <p className="ssub">
            {OVERVIEW.lead.before}{' '}
            <b>{CALIBRATIONS.length} {OVERVIEW.lead.bold}</b>. {OVERVIEW.lead.after}
          </p>
          {/* The judgment note is the overview's second paragraph, not a side box
              (option B, user decision 2026-09-27): what the engines do, then what
              kind of thing their scores are. */}
          <p className="ssub judg"><b>{OVERVIEW.judgment.title}</b> {OVERVIEW.judgment.body}</p>
          <p className="ovtail">{OVERVIEW.tail}</p>
        </div>

        {/* Variant D3: the four assessments are tabs joined to the top of the detail
            panel, one box, like a result's breakdown. A tab carries only the name —
            the question, scale, weights and counts are all in the panel below it. */}
        <div className="mbox">

          {/* Plain buttons with aria-pressed rather than a real tablist, for the
              same reason Breakdown's strip uses them: a tablist owes a screen
              reader roving tabindex and arrow-key navigation, and a half-built one
              is worse than none. These are toggle buttons and get Enter/Space and
              a focus ring for free. */}
          <div className="mcards">
            {FRAMEWORK.map((x, i) => (
              <button key={x.name} type="button"
                      className={i === tab ? 'mcard on' : 'mcard'}
                      aria-pressed={i === tab}
                      onClick={() => onTab(i as AssessmentId)}>
                <span className="cn">
                  <span className="dot" style={{ background: x.color }} />{x.name}
                </span>
              </button>
            ))}
          </div>

          <div className="mdetail">
            <div className="dh">
              <span className="dot" style={{ background: a.color }} />
              {a.name} <span className="scale">{a.scale}</span>
            </div>
            <div className="d-q">{a.question}</div>
            <div className="d-what">{a.what}</div>

            {a.groups.map(g => (
              <div key={g.title} className="grpblock">
                <div className="grp">{g.title}<span className="wt2">{g.weight}</span></div>
                <div className="gmetrics">{g.metrics}</div>
                <div className="gwhen"><b className="up">{a.hiLabel}:</b> {g.hi}</div>
                <div className="gwhen"><b className="dn">{a.loLabel}:</b> {g.lo}</div>
              </div>
            ))}

            <p className="note">{a.note}</p>

            <div className="cal-wrap">
              <div className="cal-title">
                ◆ Calibrations for {a.name} — data-triggered, click to see when
              </div>
              {cals.map(c => {
                const open = openCal === c.name
                return (
                  <div key={c.name} className={open ? 'arow open' : 'arow'}>
                    <button type="button" className="ah" aria-expanded={open}
                            onClick={() => setOpenCal(open ? null : c.name)}>
                      <span>
                        <span className="nm">{c.name}</span>
                        <span className="sm">{c.summary}</span>
                      </span>
                      <span className="chev" aria-hidden="true">▾</span>
                    </button>
                    {open && (
                      <div className="ab">
                        <div className="kv"><div className="k when">◆ When it applies</div>
                          <p>{c.when}</p></div>
                        <div className="kv"><div className="k">What it does</div>
                          <p>{c.effect}</p></div>
                        {c.example && <div className="ex"><b>Example:</b> {c.example}</div>}
                        <div className="tags">
                          <Tip label="Conditional" tip={TAG_TIPS.cond} className="tg cond" />
                          {c.guarded && <Tip label="Guarded" tip={TAG_TIPS.guard} className="tg guard" />}
                          <Tip label="Shown live" tip={TAG_TIPS.live} className="tg live" />
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

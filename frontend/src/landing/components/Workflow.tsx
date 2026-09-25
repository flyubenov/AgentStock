/** The workflow (spec 5.6): Analyze → Compare → Watch → Monitor, as four equal
 *  steps, word for word from the approved mock full-page-v21.html.
 *
 *  Three things the spec asks for by omission, and they are the easy ones to put
 *  back by accident: Discover is folded into step 1 and is *not* a fifth step; there
 *  is no per-tier limit strip under the cards; and there is no "feeds back into
 *  Analyze" line closing the loop. WhyWorkflow.test.tsx pins the step list by
 *  equality, so a fifth card fails rather than ships. */

interface Step {
  title: string
  body: string
}

const STEPS: Step[] = [
  { title: 'Analyze or discover',
    body: 'Start from tickers you already follow — or find new ones by screening the universe on the four assessments. Either way you get the full breakdown.' },
  { title: 'Compare', body: 'Rank stocks side by side, computed in parallel.' },
  { title: 'Watch & re-evaluate', body: 'Save watchlists and re-score them in one bulk, parallel run.' },
  { title: 'Monitor & automate', body: 'Scheduled re-checks, alerts and “What changed?” when scores move.' },
]

export default function Workflow() {
  return (
    <section className="section stage" id="workflow">
      <div className="container">
        <div className="kicker">The workflow</div>
        <h2 className="stitle">Analyze → Compare → Watch → Monitor</h2>
        <p className="ssub">
          A recurring research loop, not a one-off “what's it worth?” lookup. Every step
          uses the same full-depth analysis; plans differ in how much you can do and how
          much runs automatically.
        </p>
        <div className="workflow">
          {STEPS.map((s, i) => (
            <div key={s.title} className="wf">
              <div className="step">{`STEP ${i + 1}`}</div>
              <h4>{s.title}</h4>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

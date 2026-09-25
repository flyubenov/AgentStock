/** The workflow (spec 5.6): Analyze → Compare → Watch → Monitor, as four equal
 *  steps.
 *
 *  Three things the spec asks for by omission, and they are the easy ones to
 *  put back by accident: Discover is folded into step 1 and is *not* a fifth
 *  step; there is no per-tier limit strip under the cards; and there is no
 *  "feeds back into Analyze" line closing the loop. WhyWorkflow.test.tsx pins
 *  the step list by equality, so a fifth card fails rather than ships.
 *
 *  Content-only and prop-less, like Why — nothing here selects an assessment or
 *  reads a result.
 *
 *  The only numbers in this section are the step ordinals. No scoring cut-off,
 *  no per-plan allowance: the one nod to plans is qualitative, and the actual
 *  numbers live in Task 13's pricing section. */

interface Step {
  title: string
  body: string
}

const STEPS: Step[] = [
  {
    title: 'Analyze or discover',
    body: 'Start from the tickers you already follow — or find new ones by screening the market on the four assessments. Either route ends at the same full breakdown.',
  },
  {
    title: 'Compare',
    body: 'Rank a shortlist side by side, every name computed in parallel from the same fundamentals on the same day.',
  },
  {
    title: 'Watch & re-evaluate',
    body: 'Save watchlists and re-score them in one bulk, parallel run, as often as the filings behind them change.',
  },
  {
    title: 'Monitor & automate',
    body: 'Scheduled re-checks, alerts, and “What changed?” when a score moves — the loop keeps running whether or not you open the page.',
  },
]

export default function Workflow() {
  return (
    <section className="section stage" id="workflow">
      <div className="container">
        <div className="kicker">The workflow</div>
        <h2 className="stitle">Analyze → Compare → Watch → Monitor</h2>
        <p className="ssub">
          A recurring research loop, not a one-off “what is it worth?” lookup. Every step
          runs the same full-depth analysis you have just seen; plans differ in how much
          you can put through it and how much of it runs without you.
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

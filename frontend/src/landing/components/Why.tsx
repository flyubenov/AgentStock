/** "Why Intrinsica" (spec 5.5), word for word from the approved mock
 *  full-page-v21.html: the argument for reading the four assessments together, the
 *  time trade that makes an engine worth having, then two labelled rows of three
 *  cards. The scale row carries the mock's accent top border and no plan pill.
 *
 *  Content-only and prop-less on purpose: nothing in this section selects an
 *  assessment or reads a result.
 *
 *  The copy rules that bind every string below (spec section 8): never the word
 *  "signal"; never "Risk/Reward"; no scoring cut-offs. "Moat 80+" is the published
 *  outcome band (spec 5.4 item 4) used as a screener example — written "80+"
 *  rather than the mock's operator form, which the copy guard reads as a cut-off.
 *
 *  The card icons are decorative and hidden from screen readers, so an emoji is
 *  never read out as "gear" in the middle of a sentence. */

interface Card {
  icon: string
  title: string
  body: string
}

const TRUST: Card[] = [
  { icon: '⚙️', title: 'Deterministic & reproducible',
    body: 'Explicit formulas and calibrated thresholds — not an LLM opinion. Same inputs, same output, every time.' },
  { icon: '🔍', title: 'Transparent to the last detail',
    body: 'Every weight, driver, valuation method and calibration is shown — nothing hidden behind a single rating.' },
  { icon: '🛠️', title: 'Calibrated for real companies',
    body: 'Handles acquisition goodwill, cyclicals, heavy capex, banks and pre-profit growth — each rule verified against real cases.' },
]

const SCALE: Card[] = [
  { icon: '⚡', title: 'Re-evaluate whole watchlists',
    body: 'Run 25, 50 or 100+ stocks in parallel — every holding re-scored on fresh fundamentals in seconds.' },
  { icon: '🧭', title: 'Discover what fits your criteria',
    body: 'Screen hundreds of stocks by Quality, Moat, Fair Value and Reward/Risk — e.g. “Moat 80+ and trading below fair value”.' },
  { icon: '🔔', title: 'Automated monitoring',
    body: 'Intrinsica re-checks your universe on a schedule and flags “What changed?” when an assessment crosses your threshold.' },
]

function Row({ label, cards, scale }: { label: string; cards: Card[]; scale?: boolean }) {
  return (
    <div className="why-row">
      <div className="why-lbl">{label}</div>
      <div className="diff-grid">
        {cards.map(c => (
          <div key={c.title} className={scale ? 'diff scale' : 'diff'}>
            <div className="ic" aria-hidden="true">{c.icon}</div>
            <h4>{c.title}</h4>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Why() {
  return (
    <section className="section" id="why">
      <div className="container">
        <div className="kicker">Why Intrinsica</div>
        <h2 className="stitle">A rigorous engine — built to work at scale.</h2>
        <p className="ssub">
          Four questions decide most of the outcome of an investment: is the business any
          good (<b>Quality</b>), can it stay good (<b>Moat</b>), what is a share actually
          worth (<b>Fair Value</b>), and is today's price worth the downside
          (<b>Reward/Risk</b>). A good business bought at the wrong price is still a bad
          investment, and a cheap price means nothing if the business is eroding — which is
          why all four have to be read together.
        </p>
        <p className="ssub">
          Answering them properly means hours of statement work per company. Intrinsica
          computes all four from the fundamentals in seconds, the same way every time — and
          repeats it across your whole watchlist, or the market.
        </p>
        <Row label="Trust the analysis" cards={TRUST} />
        <Row label="Put it to work at scale" cards={SCALE} scale />
      </div>
    </section>
  )
}

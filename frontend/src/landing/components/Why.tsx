/** "Why Intrinsica" (spec 5.5): the argument for reading the four assessments
 *  together, the time trade that makes an engine worth having, then two
 *  labelled rows of three cards — what makes the analysis trustworthy, and what
 *  makes it useful beyond a single lookup.
 *
 *  Content-only and prop-less on purpose. There is no shared state to consume
 *  here: nothing in this section selects an assessment or reads a result, and
 *  wiring it to LandingPage's `assessment` would invent a coupling the page
 *  does not have.
 *
 *  The copy rules that bind every string below (spec section 8): never the word
 *  "signal" — it is an *assessment*; never "Risk/Reward"; and no scoring
 *  cut-offs. Only three numbers appear in this section — the count of
 *  assessments, the 25 / 50 / 100+ batch sizes spec 5.5 names, and "Moat 80+",
 *  which is the published outcome band from the framework panel above (spec 5.4
 *  item 4), used here as a screener example on a score the reader is already
 *  shown. None of them maps a raw metric to a score.
 *
 *  Deliberately no icons. The brief for this task pencilled an emoji per card;
 *  the rest of the page has no emoji at all — its glyph vocabulary is the
 *  geometric one shared with the framework and the results grid — and an
 *  unlabelled emoji is read out in full by a screen reader for no gain. */

interface Card {
  title: string
  body: string
}

const TRUST: Card[] = [
  {
    title: 'Deterministic & reproducible',
    body: 'Run the same company on the same filings again tomorrow and the number comes back identical. Nothing is sampled and nothing drifts between two readings, so every figure on this page is one you can go and check.',
  },
  {
    title: 'Transparent to the last detail',
    body: 'Every category weight, the metrics underneath it, the valuation methods in the blend and the calibrations that fired are all on screen — never a single rating you are asked to take on trust.',
  },
  {
    title: 'Calibrated for real companies',
    body: 'Acquisition goodwill, lenders, cyclicals, heavy capex and pre-profit growth each have a named rule, written for the awkward cases and verified against the companies that forced it to exist.',
  },
]

const SCALE: Card[] = [
  {
    title: 'Re-evaluate whole watchlists',
    body: 'Run 25, 50 or 100+ stocks in one parallel pass, so every holding is re-scored on the fundamentals as they stand now rather than on the note you made about it last quarter.',
  },
  {
    title: 'Discover what fits your criteria',
    body: 'Screen the market on the four assessments themselves — “Moat 80+ and trading below fair value” — instead of on the handful of ratios a conventional stock screener can offer you.',
  },
  {
    title: 'Automated monitoring',
    body: 'Intrinsica re-checks your universe on a schedule and tells you what moved, and why, when an assessment crosses a threshold you set for it.',
  },
]

function Row({ label, cards }: { label: string; cards: Card[] }) {
  return (
    <div className="why-row">
      <div className="why-lbl">{label}</div>
      <div className="diff-grid">
        {cards.map(c => (
          <div key={c.title} className="diff">
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
        <p className="ssub why-lead">
          Four questions decide most of the outcome of an investment: is the business any
          good (<b>Quality</b>), can it stay good (<b>Moat</b>), what is a share actually
          worth (<b>Fair Value</b>), and is the price today worth the downside
          (<b>Reward / Risk</b>). A good business bought at the wrong price is still a bad
          investment, and a cheap price means nothing if the business is eroding — which is
          why all four have to be read together rather than one at a time.
        </p>
        <p className="ssub why-lead">
          Answering them properly by hand is hours of statement work per company, which is
          why almost nobody does it twice. Intrinsica computes all four from the
          fundamentals in seconds, the same way every time — and repeats it across a whole
          watchlist, or the whole market.
        </p>
        {/* Spec 5.5 ends "No plan pill on this row": the scale row describes
            what the product does, and hanging a plan name off each capability
            turns it into a pricing table two sections early. Pricing is Task
            13's section and stays there. */}
        <Row label="Trust the analysis" cards={TRUST} />
        <Row label="Put it to work at scale" cards={SCALE} />
      </div>
    </section>
  )
}

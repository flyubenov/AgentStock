import { useEffect, useRef } from 'react'
import { COMPARE_ROWS, PERIODS, PLANS, WHO, priceFor, type Billing } from '../content/plans'

/** The pricing section (spec 5.7): three plan cards over a billing toggle, then
 *  the who-it-is-for cards and the canonical plan matrix.
 *
 *  Every string comes from content/plans.ts, for the same reason the framework
 *  panels do: the matrix and the cards quote the same allowances, and two
 *  hand-written copies of one table drift.
 *
 *  This is a fake door, and this section is the closest thing on the page to a
 *  purchase flow. Three things follow from that and are load-bearing:
 *
 *  - There is no input of any kind here, and there never may be. No card, no
 *    address, no name — not disabled, not a placeholder, not behind a flag. The
 *    page has to be structurally incapable of taking money.
 *  - Nothing invents urgency. No countdown, no seat count, no deadline. The test
 *    measures genuine willingness to pay, and manufactured pressure corrupts
 *    exactly the number it exists to collect.
 *  - The CTAs hand the choice upward and nothing else. They do not imply a
 *    charge is imminent, that an account exists, or that a trial has begun.
 *
 *  Controlled, like the framework tabs: `billing` is owned by LandingPage, and
 *  the toggle asks for a change rather than making one. The toggle itself fires
 *  no analytics — spec section 9's list is closed and names the annual/monthly
 *  toggle among the things deliberately left uninstrumented, because
 *  `plan_selected` already carries the period actually chosen. */

export default function Pricing({ billing, onBilling, onChoose, onView }: {
  billing: Billing
  onBilling: (b: Billing) => void
  onChoose: (plan: string, billing: Billing) => void
  onView?: () => void
}) {
  const section = useRef<HTMLElement | null>(null)
  const reported = useRef(false)

  // "Viewed" means scrolled to, not merely mounted — this section renders with
  // the page, well below the fold, so firing on mount would report a view for
  // every visitor who never reached it. Where IntersectionObserver is
  // unavailable the event is simply skipped: analytics is never load-bearing,
  // and an unobservable section is better unreported than wrongly reported.
  useEffect(() => {
    if (!onView || typeof IntersectionObserver !== 'function' || !section.current) return
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting) && !reported.current) {
        reported.current = true
        onView()
      }
    })
    io.observe(section.current)
    return () => io.disconnect()
  }, [onView])

  return (
    <section className="section" id="pricing" ref={section}>
      <div className="container">
        <div className="kicker">Pricing</div>
        <h2 className="stitle">Choose your plan</h2>
        <p className="ssub">
          Every plan gets the same full-depth analysis. Upgrade to Pro for unlimited
          analysis — or Unlimited to discover, monitor & automate at scale.
        </p>

        {/* Plain aria-pressed buttons rather than a tablist, the same choice the
            framework cards and the breakdown strip make: a half-built tablist
            owes a screen reader roving tabindex and arrow keys, and owing them
            is worse than not claiming the role. */}
        <div className="billing-toggle">
          {PERIODS.map(p => (
            <button key={p.id} type="button"
                    className={billing === p.id ? 'on' : undefined}
                    aria-pressed={billing === p.id}
                    onClick={() => onBilling(p.id)}>
              {p.label}
              {p.save && <span className="save">{p.save}</span>}
            </button>
          ))}
        </div>

        <div className="price-grid">
          {PLANS.map(p => {
            const price = priceFor(p, billing)
            return (
              <div key={p.name}
                   className={p.featured ? 'price-card featured' : 'price-card'}>
                <div className={p.name === 'Free' ? 'pc-badge free' : 'pc-badge'}>
                  {p.name}
                </div>
                <h3>{p.title}</h3>
                <div className="pc-for">{p.forLine}</div>
                {/* The amount is its own element so the "/mo" suffix cannot be
                    read as part of the price, by a test or by a reader. */}
                <div className="price">
                  <span className="amt">{price.headline}</span><span className="per">/mo</span>
                </div>
                <div className="price-alt">{price.sub}</div>
                <ul className="feature-list">
                  {p.features.map(f => <li key={f}>{f}</li>)}
                </ul>
                {/* Hands the choice upward and does nothing else — no charge is
                    made or implied here, and none is made anywhere. */}
                <button type="button" className="btn-plan"
                        onClick={() => onChoose(p.name, billing)}>
                  {p.cta}
                </button>
              </div>
            )
          })}
        </div>

        <div className="compare">
          <h3 className="compare-h">Compare plans</h3>
          <p className="compare-sub">
            The same deep analysis in every tier — you unlock more <b>volume</b>, then{' '}
            <b>scale & automation</b>.
          </p>
          <div className="who">
            {WHO.map(w => (
              <div key={w.tag} className="who-card">
                <div className="wtag">{w.tag}</div>
                <div className="wt">{w.title}</div>
                <div className="wfor">{w.who}</div>
                <div className="wfocus"><b>Focus:</b> {w.focus}</div>
              </div>
            ))}
          </div>
          <div className="cmp-wrap">
            <table className="cmp-plans">
              <thead>
                {/* scope on every header, and the feature name below is a
                    `th scope="row"`: read cell by cell, a screen reader then
                    says "Watchlists, Pro, 5–10" rather than a bare "5–10". */}
                <tr>
                  <th scope="col">Feature</th>
                  {PLANS.map(p => (
                    <th key={p.name} scope="col"
                        className={p.name === 'Unlimited' ? 'u' : undefined}>
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARE_ROWS.map(r => (
                  <tr key={r.label}>
                    <th scope="row">
                      {r.label}
                      {/* Rendered, not hung off `title`: a hover tooltip is
                          invisible on a phone and unreachable by keyboard. */}
                      {r.note && <span className="sub">{r.note}</span>}
                    </th>
                    {/* Positional: value `i` is plan `i`, and Pricing.test.tsx
                        pins each row's cells to the row's own values so a
                        reordered map cannot silently re-attribute an
                        allowance to the wrong plan. */}
                    {r.values.map((v, i) => (
                      <td key={i} className={v === '—' ? 'no' : r.on?.[i] ? 'on' : undefined}>
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="compare-note">
            Free sells the framework · Pro sells depth & unlimited use · Unlimited sells
            scale, discovery & automation.
          </p>
        </div>
      </div>
    </section>
  )
}

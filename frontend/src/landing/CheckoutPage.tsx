import { useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import './theme.css'
import { PERIODS, PLANS, totalFor, type Billing } from './content/plans'
import { MAX_TICKERS } from './components/Hero'
import { track, EVENTS } from '../lib/analytics'
import type { FreeClickSource } from './types'

/** The last step of the fake door (spec section 6), and the one page on the site
 *  that must be structurally incapable of taking money.
 *
 *  Three rules govern everything below.
 *
 *  1. **No card, payment, address or name field anywhere** — not disabled, not a
 *     placeholder, not behind a flag. Spec section 6 sanctions exactly one input
 *     on this page: the optional email, and only after the click.
 *  2. **The fine print is hidden until the click.** Telling a visitor up front
 *     that there is nothing to pay removes the very commitment this test
 *     measures, so "no card required / you won't be charged" appears with the
 *     disclosure and not before it.
 *  3. **Both disclosure variants are fixed copy.** Paid says *no payment was
 *     taken*; free says *no account was created*. They are the honesty claims
 *     the whole fake door rests on and they are not interchangeable — nothing
 *     was charged on the free path because nothing was ever going to be, and
 *     what did not happen there is that an account was created.
 *
 *  Every number the page quotes comes from `totalFor`, which derives it from the
 *  same PLANS entries the pricing cards render, so the checkout can never name a
 *  figure the card did not show. The period label comes from PERIODS for the
 *  same reason: the toggle the visitor clicked and the line they land on have to
 *  spell the period the same way.
 *
 *  This page renders outside `<Layout>` — Layout is the analyst app's dark
 *  chrome and this is the light marketing surface, the same arrangement the
 *  landing page at `/` uses. */

/** The chrome both states share. Nav and footer rather than the landing page's
 *  own components: the nav here offers one link back to the plans instead of the
 *  page-section anchors, which lead nowhere from this route, and spec 5.8 asks
 *  for a *short form* of the footer — the modeling-tool disclaimer alone. */
function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="intrinsica">
      <nav className="nav">
        <div className="nav-in">
          <div className="logo">Intrinsica</div>
          <div className="links"><a href="/#pricing">← Back to pricing</a></div>
        </div>
      </nav>

      <section className="section stage" id="checkout">
        <div className="container">
          <div className="kicker">Checkout</div>
          <h1 className="stitle">{title}</h1>
          <div className="checkout">{children}</div>
        </div>
      </section>

      <footer className="footer">
        <div className="container">
          <p className="legal">
            <b>Intrinsica</b> provides automated quantitative financial-data modeling tools
            for informational analysis. Nothing on this platform constitutes personalized
            investment advice.
          </p>
        </div>
      </footer>
    </div>
  )
}

export default function CheckoutPage() {
  const [params] = useSearchParams()
  // Both of these come out of the address bar, so both are treated as untrusted.
  // The plan is resolved against PLANS rather than echoed: an unrecognised name
  // is not shown back to the visitor, which keeps arbitrary query text off the
  // page and keeps the page from claiming to have recorded a request for
  // something that does not exist.
  const plan = PLANS.find(p => p.name === params.get('plan'))
  // Anything that is not a period we actually sell falls back to annual, which
  // is the period the pricing cards open on (spec 5.7) and the one LandingPage
  // defaults its toggle to.
  const billing: Billing = params.get('billing') === 'monthly' ? 'monthly' : 'annual'
  const free = plan?.name === 'Free'

  const [clicked, setClicked] = useState(false)
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)

  useEffect(() => {
    // Deliberately not fired for an unrecognised plan: that state shows no
    // button, so counting it would inflate the denominator of the derived
    // abandonment rate with visitors who were never given anything to abandon.
    if (!plan) return
    // ABANDONMENT IS DERIVED, NOT LOGGED (spec line 378): checkout_started minus
    // payment_button_clicked. That subtraction is WRONG computed globally. Free
    // routes through this same screen and fires free_plan_clicked on its click,
    // never payment_button_clicked — so every completed Free journey would be
    // counted as an abandonment. Compute it over `plan !== 'Free'` only, which
    // is why this event carries `plan` on every path that fires it. Do not
    // "fix" it by adding an event (spec section 9's list is closed) or by
    // dropping this one for Free (that loses the Free funnel entirely).
    track(EVENTS.checkoutStarted, { plan: plan.name, billing })
  }, [plan, billing])

  if (!plan) {
    return (
      <Shell title="No plan selected">
        <p className="co-none">
          This link does not name a plan we offer, so there is nothing to confirm here.
          Nothing has been charged and no account exists. Choose a plan and we will bring
          you straight back.
        </p>
        <a className="btn-buy" href="/#pricing">See the plans</a>
      </Shell>
    )
  }

  // Read out once, past the guard above, so the two handlers below carry the
  // plan without a non-null assertion. They are function declarations and so
  // hoisted above that guard, which is why `plan` does not narrow inside them —
  // and on this page a `!` is a claim about money that the compiler cannot
  // check, which is the one kind of claim this page may not make.
  const name = plan.name

  function proceed() {
    // AT MOST ONCE PER VISITOR. The button stays mounted and enabled after the
    // click — the click only reveals the disclosure beneath it — so an
    // impatient double-click posted the paid intent twice. Abandonment is
    // derived as checkout_started minus payment_button_clicked (spec line 378):
    // repeats do not merely inflate paid-intent conversion, they can drive that
    // subtraction negative. Guarded on the fire, not with `disabled`, which
    // would take the button out of the tab order and change what the visitor
    // sees — the same line Pricing's `reported` ref and LandingPage's `opening`
    // already draw.
    if (clicked) return
    // The whole measurement: reaching this button and pressing it. Nothing is
    // charged, and no card was ever asked for.
    //
    // Free gets its own event and must never ride the paid one — clicking Free
    // is the opposite of a purchase signal, and free_plan_clicked is excluded
    // from paid-intent conversion (spec lines 299-300, and the comment on EVENTS
    // itself). LandingPage draws the same line on the CTA that sent the visitor
    // here; this is the second half of it.
    if (free) {
      // `source` because free_plan_clicked fires from LandingPage's pricing CTA
      // too, with the same plan and billing — this is the SECOND of its two
      // sites. Undistinguished, the two stages share one counter and free
      // drop-off (clicked Free, then confirmed here) cannot be computed, which
      // is the Free funnel's only drop-off number. A third event name is not
      // available: spec section 9's list is closed.
      track(EVENTS.freePlanClicked,
            { plan: name, billing, source: 'checkout' satisfies FreeClickSource })
    } else {
      // Deliberately unstamped: this is payment_button_clicked's only fire
      // site, and it is already a distinct name from plan_selected upstream.
      track(EVENTS.paymentButtonClicked, { plan: name, billing })
    }
    setClicked(true)
  }

  function notify() {
    // One post per address, not per press. Deliberately keyed on `sent` and not
    // on a once-ever latch: the input's onChange clears `sent`, so a visitor who
    // spots a typo and corrects it re-arms the event and gets the invitation the
    // copy beside it promised, while a second press on an unchanged address
    // posts nothing. A permanent latch here would silently drop the correction.
    if (sent) return
    // Optional means optional: an empty field is not an error, it simply posts
    // nothing. There is no validation gate and nothing on this page waits on it
    // — spec line 13 frames the experiment as willingness to pay, "not email
    // curiosity", and an email field that becomes a gate inverts that.
    const address = email.trim()
    if (!address) return
    // The address rides the event because the copy beside it promises an
    // invitation, and a page that asks for an email and throws it away has made
    // a promise it cannot keep — on the one page whose entire product is that
    // its promises are true.
    track(EVENTS.emailSubmitted, { plan: name, billing, email: address })
    setSent(true)
  }

  const periodLabel = PERIODS.find(p => p.id === billing)!.label

  return (
    <Shell title={free ? 'Create your free account' : 'Confirm your plan'}>
      <dl className="co-lines">
        <dt>Plan</dt>
        <dd>{plan.name}</dd>
        <dt>Billing</dt>
        <dd>{free ? 'No billing' : periodLabel}</dd>
        <dt className="co-total">Total</dt>
        <dd className="co-total">{totalFor(plan.name, billing)}</dd>
      </dl>

      <button type="button" className="btn-buy" onClick={proceed}>
        {free ? 'Create free account' : 'Proceed to payment'}
      </button>

      {clicked && (
        <>
          <div className="disclosure">
            <h2>
              {free
                ? "✓ You're on the Intrinsica early-access list"
                : "✓ You're on the Intrinsica founding list"}
            </h2>
            {/* The cap is interpolated from MAX_TICKERS, never retyped: a second
                copy of that number is a false statement about the product the
                moment the demo cap moves, and this sentence sits inside the
                honesty copy. The demo is linked rather than merely named because
                it is not on this route and the mini-nav only offers the plans —
                `#analyze` is Hero's analyzer, absolute so it resolves from
                /checkout. */}
            <p>
              {free ? (
                <>
                  Accounts aren't open yet, so <b>no account was created</b>. We've recorded
                  your interest in <b>the Free plan</b> and will invite you when early access
                  opens. In the meantime <a href="/#analyze">the demo</a> stays open — up
                  to {MAX_TICKERS} tickers per run, no account needed.
                </>
              ) : (
                <>
                  Intrinsica isn't commercially available yet, so <b>no payment was taken</b>.
                  We've recorded your request for <b>{plan.name} — {periodLabel}</b> and will
                  contact you when early access opens.
                </>
              )}
            </p>

            <label className="co-opt" htmlFor="co-email">
              Optional — add your email for an early-access invite.
            </label>
            {/* Deliberately not a <form>: a form element on this page is one edit
                away from being a checkout. That leaves nothing to supply the
                submit gesture, so Enter is wired by hand — a visitor who types an
                address and presses Enter must not have the invitation the copy
                just promised them dropped silently, and the email leg of the
                funnel must not undercount because of it. Blank + Enter still
                posts nothing: `notify` already returns on an empty field. */}
            <div className="co-email">
              <input id="co-email" type="email" value={email}
                     placeholder="you@email.com"
                     onChange={e => { setEmail(e.target.value); setSent(false) }}
                     onKeyDown={e => { if (e.key === 'Enter') notify() }} />
              <button type="button" onClick={notify}>Notify me</button>
            </div>
            {sent && (
              <p className="co-opt">Thanks — we'll email you when early access opens.</p>
            )}
          </div>

          {/* Deliberately after the click: telling people up front that there is
              nothing to pay removes the commitment this test measures. */}
          <p className="co-fine">
            {free
              ? 'No card required — the free plan never asks for one.'
              : "No card required. This is a pre-launch validation — you won't be charged."}
          </p>
        </>
      )}
    </Shell>
  )
}

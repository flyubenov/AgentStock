import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

/** The end-to-end gate (spec section 9, and the whole point of the fake door).
 *
 *  Every other test on this project checks one component with its collaborators
 *  mocked. This one renders `<App />` through the REAL router and the REAL
 *  analytics module, with only `fetch` stubbed, and walks a visitor from `/` to
 *  the payment click. Three things are therefore exercised here and nowhere
 *  else:
 *
 *  1. The event NAMES are the real ones. A mocked `EVENTS` map is a tautology —
 *     it asserts the test's own copy of the names against itself. Here the
 *     strings come out of `lib/analytics.ts` via the real `track()`, and the
 *     test reads them off the wire, out of the POST body.
 *  2. The ROUTE is real. Task 13 shipped plan CTAs that navigated to a
 *     `/checkout` that did not exist, and a `MemoryRouter` stub with a
 *     hand-written `<Route>` is exactly what hid it. `render(<App />)` cannot
 *     hide it: if `App.tsx` stops mounting `/checkout`, this file fails.
 *  3. The FUNNEL ORDER is real, and asserted with presence FIRST.
 *
 *  On that last point, at length, because it is the trap this file exists to
 *  avoid. `Array.indexOf` returns -1 for an absent item, so
 *
 *      expect(names.indexOf('plan_selected'))
 *        .toBeLessThan(names.indexOf('checkout_started'))
 *
 *  is `-1 < 2` — PASSING — when `plan_selected` never fired at all. A bare
 *  index comparison is not an order assertion; it is an order assertion OR a
 *  silent hole, and on the last gate before ship the hole is the likelier
 *  outcome. `expectFunnel` below asserts every name is present, then that each
 *  appears exactly once, and only then compares positions.
 *
 *  Nothing here mocks a component. A failure in this file is a real funnel
 *  defect: fix the page, not the test. */

type IOEntry = { isIntersecting: boolean }
type IOCallback = (entries: IOEntry[]) => void

/** Node's `process`, reached through `globalThis` and narrowed to the two
 *  methods used. `tsconfig.app.json` types this project for the browser
 *  (`types: ["vite/client"]`), so a bare `process` does not compile here, and
 *  pulling @types/node into the app's type graph for one listener would put
 *  Node's globals in scope for every source file on a page that must never
 *  acquire a server-side habit by accident. */
type RejectionHook = {
  on(event: 'unhandledRejection', fn: (reason: unknown) => void): void
  off(event: 'unhandledRejection', fn: (reason: unknown) => void): void
}
const nodeProcess = (globalThis as unknown as { process: RejectionHook }).process

/** The event names this page may ever post, straight from spec section 9's
 *  closed list. Written out rather than imported from `lib/analytics`: importing
 *  `EVENTS` here would compare the module to itself, which is the tautology this
 *  file is meant to be free of. If a new event is invented, this fails. */
const SPEC_EVENTS = [
  'page_view', 'analysis_started', 'analysis_completed', 'breakdown_opened',
  'methodology_viewed', 'pricing_viewed', 'plan_selected', 'checkout_started',
  'payment_button_clicked', 'email_submitted', 'free_plan_clicked',
]

type Posted = { event: string; props: Record<string, unknown> }

/** Captures the real event names the real analytics module posts, and hands back
 *  the observer callbacks Pricing registers — jsdom has no IntersectionObserver,
 *  so without this stub `pricing_viewed` can never fire and any assertion about
 *  it is vacuous. */
function captureFunnel() {
  const seen: Posted[] = []
  const observers: IOCallback[] = []

  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: IOCallback) { observers.push(cb) }
    observe() {}
    unobserve() {}
    disconnect() {}
  })

  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    if (String(url).endsWith('/api/events')) {
      seen.push(JSON.parse(String(init?.body)) as Posted)
      return { ok: true, json: async () => ({ recorded: true }) }
    }
    return { ok: true, json: async () => ({ results: [], invalid: [], error: null }) }
  }))

  return { seen, observers, names: () => seen.map(e => e.event) }
}

/** LandingPage kicks off a sample AAPL analysis on mount, so there is an
 *  in-flight fetch at render time. Settle it before clicking anything, or the
 *  interaction races the mount and the output fills with act(...) warnings. The
 *  wait observes the real settle — the button returning to its idle label — and
 *  it also guarantees `analysis_completed` has already been posted, since
 *  `analyze` tracks it before the `finally` that clears `busy`. */
async function settled() {
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
  })
}

/** Presence, then uniqueness, then order. In that order, and never order alone.
 *
 *  `render(<App />)` mounts OUTSIDE StrictMode — main.tsx owns the StrictMode
 *  wrapper, not App — so every effect runs once here and exact counts are
 *  meaningful. Under StrictMode (i.e. in `npm run dev`) `page_view` and
 *  `checkout_started` double-fire; that is a development-only artefact of the
 *  double-invoked effect and the production bundle fires once. Asserting
 *  exactly-once here is therefore the stronger claim, not a weaker one: it
 *  catches a component that starts firing twice on its own. */
function expectFunnel(names: string[], expected: string[]) {
  for (const event of expected) {
    expect(names, `funnel is missing ${event}`).toContain(event)
    expect(names.filter(n => n === event), `${event} fired more than once`)
      .toHaveLength(1)
  }
  const positions = expected.map(e => names.indexOf(e))
  // Compared as a whole rather than pairwise, so the assertion message shows the
  // real sequence when it breaks.
  expect(positions, `funnel out of order: ${names.join(' → ')}`)
    .toEqual([...positions].sort((a, b) => a - b))
}

/** Card, CVC, expiry, bank details — the things this page must be structurally
 *  incapable of asking for. Deliberately precise: the checkout's honesty copy
 *  says "No card required", so a bare /card/i would flag the very sentence that
 *  makes the fake door honest. */
const PAYMENT_WORDS =
  /card number|cardholder|name on card|credit card|debit card|\bcvc\b|\bcvv\b|expir|security code|\biban\b|sort.?code|account.?number|routing/i

/** The only input types this site may render. The ticker box in Hero carries no
 *  `type` attribute, which the DOM normalises to `text`; the checkout's optional
 *  email is `type="email"` and appears only AFTER the payment click. Everything
 *  else — `password`, `tel`, `number`, `month` — is banned outright. */
const ALLOWED_INPUT_TYPES = new Set(['text', 'email'])

/** Address, postal and name terms, checked ONLY against an input's own naming
 *  attributes and its label — never against `outerHTML`, which is why they were
 *  missing from PAYMENT_WORDS above: that sweep runs over the whole element, so
 *  a bare /name/ there matches every `name="..."` attribute in the document and
 *  fires on everything. Kept off `textContent` too: "Billing" is legitimate
 *  copy on the checkout's summary line. */
const IDENTITY_WORDS =
  /address|street|\bcity\b|postal|post.?code|\bzip\b|full name|first name|last name|surname|billing name/i

/** An input this site is allowed to render, named by WHERE it lives rather than
 *  by what it is called. The whitelist below is the point of this file's
 *  strongest guarantee: a blacklist of forbidden words can always be walked
 *  around by a word nobody thought of — `Billing address` and `Full name` both
 *  cleared PAYMENT_WORDS, and a planted pair of them left this file 7/7 green —
 *  whereas an input that is not one of these cannot exist at all. */
type SanctionedInput = { selector: string; type: string; what: string }

/** Hero's ticker box. Matched through its container, not through a word in its
 *  placeholder, so re-wording the placeholder does not silently widen the
 *  whitelist and a payment field dropped beside it does not silently fit. */
const HERO_TICKER: SanctionedInput =
  { selector: '#analyze .an-field input', type: 'text', what: 'the Hero ticker box' }

/** The checkout's optional email, which exists only after the payment click. */
const CHECKOUT_EMAIL: SanctionedInput =
  { selector: 'input#co-email', type: 'email', what: 'the optional email' }

function expectNoPaymentSurface(
  container: HTMLElement,
  where: string,
  sanctioned: SanctionedInput[],
) {
  const inputs = Array.from(container.querySelectorAll('input'))
  // WHITELIST FIRST, and by count AND identity. Count alone would accept a
  // payment field that had displaced a sanctioned one; identity alone would
  // accept a payment field standing beside it.
  expect(inputs.map(i => i.outerHTML), `${where}: unsanctioned input(s) present`)
    .toHaveLength(sanctioned.length)
  for (const { selector, type, what } of sanctioned) {
    const matched = Array.from(container.querySelectorAll(selector))
    expect(matched, `${where}: expected exactly one input for ${what}`).toHaveLength(1)
    expect((matched[0] as HTMLInputElement).type, `${where}: ${what}`).toBe(type)
  }

  // Then the blacklists, unchanged and deliberately kept: defence in depth, and
  // the word sweeps also catch a payment surface built from elements that are
  // not inputs at all, which no input whitelist can see.
  for (const input of inputs) {
    expect(ALLOWED_INPUT_TYPES.has(input.type), `${where}: <input type=${input.type}>`)
      .toBe(true)
    expect(input.outerHTML, where).not.toMatch(PAYMENT_WORDS)
    // Scoped to what the field calls itself and to the label a visitor reads,
    // for the reason given on IDENTITY_WORDS.
    const labels = Array.from(input.labels ?? []).map(l => l.textContent ?? '')
    const naming = [
      input.getAttribute('placeholder') ?? '',
      input.getAttribute('aria-label') ?? '',
      input.getAttribute('name') ?? '',
      input.getAttribute('autocomplete') ?? '',
      ...labels,
    ].join(' | ')
    expect(naming, `${where}: an input asking for an address or a name`)
      .not.toMatch(IDENTITY_WORDS)
    // Browsers autofill card details off this attribute; `cc-number`, `cc-exp`,
    // `cc-csc` would each be a payment field in all but name.
    expect(input.getAttribute('autocomplete') ?? '', where).not.toMatch(/^cc-/)
  }
  // Nothing to submit and nothing to embed. A <form> is one edit away from being
  // a checkout (CheckoutPage says so in its own header comment, and wires Enter
  // by hand rather than take one), and a hosted card field arrives as an
  // <iframe> — the usual way a page acquires the ability to take money without
  // any of these greps ever seeing a card input.
  expect(container.querySelectorAll('form'), `${where}: a form element`).toHaveLength(0)
  expect(container.querySelectorAll('iframe'), `${where}: an iframe`).toHaveLength(0)
  // A <select> on this site would be an expiry month or year; there is no other
  // reason for one to exist here.
  expect(container.querySelectorAll('select'), `${where}: a select`).toHaveLength(0)
  expect(container.textContent, where).not.toMatch(PAYMENT_WORDS)
}

beforeEach(() => {
  window.history.pushState({}, '', '/')
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('the fake-door funnel, end to end', () => {
  it('records every paid step once, in order, ending at the payment click', async () => {
    const { seen, observers, names } = captureFunnel()
    render(<App />)
    await settled()

    // Scrolling the plans into view is a funnel step, not a formality: it is the
    // denominator every conversion below is measured against.
    expect(observers.length).toBeGreaterThan(0)
    act(() => observers[0]([{ isIntersecting: true }]))

    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Proceed to payment' }))
    // The disclosure is the product of this page. A checkout that silently did
    // nothing on click would satisfy every "no payment input" and "no forbidden
    // event" assertion in this file.
    expect(await screen.findByText(/no payment was taken/i)).toBeInTheDocument()
    expect(screen.queryByText(/no account was created/i)).not.toBeInTheDocument()

    expectFunnel(names(), [
      'page_view',
      'analysis_started',
      'analysis_completed',
      'pricing_viewed',
      'plan_selected',
      'checkout_started',
      'payment_button_clicked',
    ])

    // The real router really moved.
    expect(window.location.pathname).toBe('/checkout')

    const props = (event: string) => seen.find(e => e.event === event)!.props
    expect(props('plan_selected')).toEqual({ plan: 'Pro', billing: 'annual' })
    expect(props('checkout_started')).toEqual({ plan: 'Pro', billing: 'annual' })
    expect(props('payment_button_clicked')).toEqual({ plan: 'Pro', billing: 'annual' })

    // Free must never be reachable from the paid walk.
    expect(names()).not.toContain('free_plan_clicked')
    // And nothing off spec section 9's closed list may appear on the wire.
    expect(names().filter(n => !SPEC_EVENTS.includes(n))).toEqual([])
  })

  it('carries the chosen billing period all the way to the payment click', async () => {
    const { seen, observers, names } = captureFunnel()
    render(<App />)
    await settled()
    act(() => observers[0]([{ isIntersecting: true }]))

    // The toggle itself is deliberately uninstrumented (spec section 9); the
    // period it sets has to survive the hop to the checkout regardless, which is
    // the only thing that makes that decision safe.
    await userEvent.click(screen.getByRole('button', { name: 'Monthly' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Proceed to payment' }))

    expectFunnel(names(), ['plan_selected', 'checkout_started', 'payment_button_clicked'])
    for (const event of ['plan_selected', 'checkout_started', 'payment_button_clicked']) {
      expect(seen.find(e => e.event === event)!.props, event)
        .toEqual({ plan: 'Unlimited', billing: 'monthly' })
    }
  })

  it('keeps a free click out of the paid funnel, start to finish', async () => {
    const { seen, observers, names } = captureFunnel()
    render(<App />)
    await settled()
    act(() => observers[0]([{ isIntersecting: true }]))

    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Create free account' }))
    expect(await screen.findByText(/no account was created/i)).toBeInTheDocument()
    expect(screen.queryByText(/no payment was taken/i)).not.toBeInTheDocument()

    expect(names()).toContain('free_plan_clicked')
    expect(names()).not.toContain('payment_button_clicked')
    expect(names()).not.toContain('plan_selected')

    // Both ends of the free walk fire free_plan_clicked — the pricing CTA and
    // the checkout confirm. They used to carry IDENTICAL props, so the two
    // funnel stages incremented one undifferentiated counter and free drop-off
    // (clicked Free, then confirmed) could not be computed from the wire at
    // all. `source` separates them (Task 16c, the same move Task 8d made for
    // analysis_started). Asserted here rather than only in the two component
    // tests because this is the only place that walks BOTH ends in one journey
    // — the component tests each see one site and so cannot tell whether the
    // two stamps differ.
    const freeClicks = seen.filter(e => e.event === 'free_plan_clicked')
    expect(freeClicks).toHaveLength(2)
    expect(freeClicks.map(c => c.props)).toEqual([
      { plan: 'Free', billing: 'annual', source: 'pricing' },
      { plan: 'Free', billing: 'annual', source: 'checkout' },
    ])
    // Stated as the property that matters, so a future third fire site cannot
    // satisfy the pair above by reusing a stamp: every fire is distinguishable.
    expect(new Set(freeClicks.map(c => c.props.source)).size).toBe(freeClicks.length)

    // THE ABANDONMENT TRAP, pinned end to end. Abandonment is derived as
    // checkout_started − payment_button_clicked (spec line 378). Free routes
    // through the same checkout and fires checkout_started with plan: 'Free',
    // but never payment_button_clicked — so every COMPLETED free journey looks
    // like an abandoned paid one unless the subtraction is filtered to
    // plan !== 'Free'. This asserts the shape that makes the filter possible:
    // checkout_started carries the plan on the free path too.
    const started = seen.filter(e => e.event === 'checkout_started')
    expect(started).toHaveLength(1)
    expect(started[0].props).toEqual({ plan: 'Free', billing: 'annual' })
    expect(names().filter(n => !SPEC_EVENTS.includes(n))).toEqual([])
  })

  /** The claim in the name is "anywhere", so the assertion has to be closed,
   *  not enumerated: every input on the page is checked against the list of the
   *  ones that may exist, rather than against a list of words that may not
   *  appear. The enumerated version of this test passed with a `Billing
   *  address` and a `Full name` field planted on the landing page. */
  it('never renders a payment surface anywhere in the funnel', async () => {
    const { observers } = captureFunnel()
    const { container } = render(<App />)
    await settled()

    expectNoPaymentSurface(container, 'landing page', [HERO_TICKER])
    act(() => observers[0]([{ isIntersecting: true }]))

    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))
    await screen.findByRole('button', { name: 'Proceed to payment' })
    expectNoPaymentSurface(container, 'checkout before the click', [])

    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))
    await screen.findByText(/no payment was taken/i)
    expectNoPaymentSurface(container, 'checkout after the click', [CHECKOUT_EMAIL])

    // The one sanctioned input on this page, and only after the click: an
    // optional email with a real label. The whitelist above already pins its
    // count, position and type; what is added here is that it is LABELLED — a
    // field a visitor can read the purpose of, rather than one identified only
    // by an id the test happens to know.
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs).toHaveLength(1)
    expect(screen.getByLabelText(/optional/i)).toBe(inputs[0])
  })

  /** A rejected POST: the ad blocker the page will actually meet, since
   *  `/api/events` is precisely the URL shape the filter lists match.
   *
   *  Two things have to hold, and only the first of them is obvious. The funnel
   *  must finish — and it must finish QUIETLY. `track` fires and forgets with
   *  `void fetch(...).catch(() => {})`; drop that `.catch` and the page still
   *  works, so a test that only clicks through passes over the regression
   *  without noticing. What actually changes is that every blocked event becomes
   *  an unhandled promise rejection, on the page whose entire job is to be
   *  measured, for the visitors most likely to be blocking it.
   *
   *  The stub is a plain async function and deliberately NOT `vi.fn`: vitest's
   *  mock wrapper attaches its own settlement handler to each returned promise
   *  to populate `mock.settledResults`, which marks the rejection as handled and
   *  hides the exact signal this test is here to read. With `vi.fn` the
   *  dropped-`.catch` regression causes zero failures; with a plain stub the
   *  listener below sees one rejection per blocked event. */
  it('completes the paid funnel, and stays quiet, with the events POST rejecting', async () => {
    const unhandled: unknown[] = []
    const onReject = (reason: unknown) => { unhandled.push(reason) }
    nodeProcess.on('unhandledRejection', onReject)
    try {
      vi.stubGlobal('IntersectionObserver', class {
        observe() {}
        unobserve() {}
        disconnect() {}
      })
      vi.stubGlobal('fetch', async (url: RequestInfo | URL) => {
        if (String(url).endsWith('/api/events')) throw new Error('blocked')
        return { ok: true, json: async () => ({ results: [], invalid: [], error: null }) }
      })
      render(<App />)
      await settled()

      await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
      const button = await screen.findByRole('button', { name: 'Proceed to payment' })
      expect(button).toBeEnabled()
      await userEvent.click(button)
      expect(await screen.findByText(/no payment was taken/i)).toBeInTheDocument()

      // Node reports an unhandled rejection once the microtask queue has
      // drained, so give it a macrotask before looking.
      await new Promise(resolve => setTimeout(resolve, 30))
      expect(unhandled, 'a blocked analytics POST escaped as an unhandled rejection')
        .toEqual([])
    } finally {
      nodeProcess.off('unhandledRejection', onReject)
    }
  })

  /** The other blocking shape, and the one `track`'s try/catch is for: an
   *  extension that replaces `window.fetch` with a function which throws on the
   *  spot rather than returning a rejected promise. That throw lands inside a
   *  click handler and inside a mount effect — unguarded it takes
   *  `setClicked(true)` with it, so the disclosure never renders and the fake
   *  door silently stops working. Asserted through the UI because that is where
   *  the damage would be. */
  it('completes the paid funnel with fetch itself throwing on the spot', async () => {
    vi.stubGlobal('IntersectionObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    })
    vi.stubGlobal('fetch', () => { throw new Error('blocked') })
    render(<App />)
    await settled()

    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Proceed to payment' }))
    expect(await screen.findByText(/no payment was taken/i)).toBeInTheDocument()
  })

  // A plan the site does not sell must not be echoed back, priced, or counted.
  it('shows no price and starts no checkout for a plan that does not exist', async () => {
    const { names } = captureFunnel()
    window.history.pushState({}, '', '/checkout?plan=pro&billing=weekly')
    const { container } = render(<App />)

    expect(await screen.findByText('No plan selected')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\$/)
    expect(screen.queryByRole('button', { name: 'Proceed to payment' })).not.toBeInTheDocument()
    expect(names()).not.toContain('checkout_started')
    expectNoPaymentSurface(container, 'unknown plan', [])
  })
})

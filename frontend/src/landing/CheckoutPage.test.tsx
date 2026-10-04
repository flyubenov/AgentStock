import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CheckoutPage from './CheckoutPage'
import App from '../App'

/** The last step of the fake door, and the one that must never take money.
 *
 *  Every negative assertion below is anchored: a real string and a real element
 *  are asserted before the negative, so a CheckoutPage that rendered nothing
 *  could not satisfy a guard by being empty. That matters more here than
 *  anywhere else on the site — "the DOM contains no card field" is trivially
 *  true of an empty DOM, and this is the page where it has to mean something.
 *
 *  `track` is the only thing mocked. `EVENTS` comes through `importActual`, so
 *  the event names asserted below are the real frozen ones (spec section 9) and
 *  the mock cannot drift from the module it stands in for — the brief's
 *  hand-written EVENTS object had already lost `freePlanClicked`. The literal
 *  strings in the expectations are retyped rather than read back out of EVENTS,
 *  because an expectation derived from the same constant the component renders
 *  from asserts nothing. */
vi.mock('../lib/analytics', async importActual => ({
  ...(await importActual<typeof import('../lib/analytics')>()),
  track: vi.fn(),
}))

async function tracker() {
  const { track } = await import('../lib/analytics')
  return vi.mocked(track)
}

const callsOf = (track: ReturnType<typeof vi.fn>, name: string) =>
  track.mock.calls.filter(c => c[0] === name)

function show(query = '?plan=Pro&billing=annual') {
  return render(
    <MemoryRouter initialEntries={[`/checkout${query}`]}>
      <CheckoutPage />
    </MemoryRouter>,
  )
}

const proceed = () => screen.getByRole('button', { name: 'Proceed to payment' })

beforeEach(() => vi.clearAllMocks())

describe('CheckoutPage', () => {
  it('summarises the chosen plan, billing period and total', () => {
    show()
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Annual')).toBeInTheDocument()
    expect(screen.getByText('$216 / year ($18.00/mo)')).toBeInTheDocument()
  })

  // The period the visitor had on screen when they chose has to survive the
  // hop: quoting the annual price to someone who picked monthly is quoting a
  // price they did not choose.
  it('quotes the monthly total when monthly was chosen', () => {
    show('?plan=Unlimited&billing=monthly')
    expect(screen.getByText('Unlimited')).toBeInTheDocument()
    expect(screen.getByText('Monthly')).toBeInTheDocument()
    expect(screen.getByText('$41.99 / month')).toBeInTheDocument()
    expect(screen.queryByText('$420 / year ($35.00/mo)')).not.toBeInTheDocument()
  })

  it('labels the paid button Proceed to payment', () => {
    show()
    expect(proceed()).toBeInTheDocument()
  })

  // The single hardest constraint in the project, and this is the page it binds
  // hardest on. Spec section 6 sanctions exactly one input here — the optional
  // email — and it does not exist until the visitor has been told there is
  // nothing to pay. Checked in both states, because "no card field" proved
  // before the click says nothing about the DOM after it.
  it('has no card, payment, address or name field anywhere, before or after the click', async () => {
    const { container } = show()
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(screen.getByText('$216 / year ($18.00/mo)')).toBeInTheDocument()
    expect(container.querySelector('section#checkout')).toBeInTheDocument()

    expect(container.querySelectorAll('input')).toHaveLength(0)
    expect(container.querySelectorAll('form')).toHaveLength(0)
    expect(container.querySelectorAll('select')).toHaveLength(0)
    expect(container.querySelectorAll('textarea')).toHaveLength(0)

    await userEvent.click(proceed())
    expect(screen.getByText(/no payment was taken/i)).toBeInTheDocument()

    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs).toHaveLength(1)
    expect(inputs[0]).toHaveAttribute('type', 'email')
    expect(container.querySelectorAll('form')).toHaveLength(0)
    expect(container.querySelectorAll('select')).toHaveLength(0)
    expect(container.querySelectorAll('textarea')).toHaveLength(0)
    expect(container.querySelectorAll('input[type="password"]')).toHaveLength(0)
    expect(container.textContent)
      .not.toMatch(/card number|cvc|cvv|expiry|cardholder|billing address|postcode|zip/i)
  })

  // Spec section 6: telling people up front that there is nothing to pay
  // removes the very commitment this test measures.
  it('hides the no-card fine print until after the click', async () => {
    const { container } = show()
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/no card required/i)
    expect(container.textContent).not.toMatch(/you won[’']t be charged/i)

    await userEvent.click(proceed())
    expect(screen.getByText(/no card required/i)).toBeInTheDocument()
    expect(screen.getByText(/you won[’']t be charged/i)).toBeInTheDocument()
  })

  // The honesty claim the entire fake door rests on. The paid variant says "no
  // payment was taken"; it may not be softened, reworded, or merged with the
  // free one.
  it('discloses that no payment was taken, and records the paid click', async () => {
    const track = await tracker()
    show()
    await userEvent.click(proceed())

    expect(screen.getByText(/founding list/i)).toBeInTheDocument()
    expect(screen.getByText(/no payment was taken/i)).toBeInTheDocument()
    expect(screen.getByText(/Pro — Annual/)).toBeInTheDocument()
    expect(screen.queryByText(/no account was created/i)).not.toBeInTheDocument()

    expect(callsOf(track, 'payment_button_clicked'))
      .toEqual([['payment_button_clicked', { plan: 'Pro', billing: 'annual' }]])
  })

  // The free variant is its own copy, not a reworded paid one: nothing was
  // charged because nothing was ever going to be, and what did not happen is
  // that an account was created.
  it('words the free path as an invite and says no account was created', async () => {
    show('?plan=Free&billing=annual')
    expect(screen.getByText('Create your free account')).toBeInTheDocument()
    expect(screen.getByText('Free')).toBeInTheDocument()
    expect(screen.getByText('No billing')).toBeInTheDocument()
    expect(screen.getByText('$0 — free plan')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))
    expect(screen.getByText(/early-access list/i)).toBeInTheDocument()
    expect(screen.getByText(/no account was created/i)).toBeInTheDocument()
    expect(screen.queryByText(/no payment was taken/i)).not.toBeInTheDocument()
  })

  // THE ANALYTICS TRAP. free_plan_clicked is excluded from paid-intent
  // conversion (spec lines 299-300), so a Free click may never fire
  // payment_button_clicked. checkout_started still fires for Free — dropping it
  // would lose the Free funnel entirely — which is exactly why it has to carry
  // the plan: abandonment is derived as checkout_started minus
  // payment_button_clicked, and that subtraction is only correct over
  // plan !== 'Free'.
  it('never routes a Free click through the paid-intent event', async () => {
    const track = await tracker()
    show('?plan=Free&billing=monthly')
    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))

    expect(screen.getByText(/no account was created/i)).toBeInTheDocument()
    expect(callsOf(track, 'free_plan_clicked'))
      .toEqual([['free_plan_clicked',
                 { plan: 'Free', billing: 'monthly', source: 'checkout' }]])
    expect(callsOf(track, 'payment_button_clicked')).toHaveLength(0)
    expect(callsOf(track, 'checkout_started'))
      .toEqual([['checkout_started', { plan: 'Free', billing: 'monthly' }]])
  })

  /** Task 16c. This button is the SECOND of the two sites that fire
   *  free_plan_clicked; the pricing CTA on the landing page is the first, and
   *  it stamps `source: 'pricing'`. With both carrying only { plan, billing }
   *  the two funnel stages incremented one undifferentiated counter, so free
   *  drop-off — clicked Free, then confirmed — was not derivable from the data
   *  at all. `source` is the disambiguation Task 8d already used for
   *  analysis_started; a new event name is not available, spec section 9's list
   *  being closed.
   *
   *  payment_button_clicked, the paid branch of this same handler, is
   *  deliberately left unstamped: it fires from here and nowhere else, and the
   *  paid funnel's stages are already distinct event names. The tests below pin
   *  its props exactly, so a stamp added there fails rather than drifts in. */
  it('stamps a Free confirm with the checkout as its source', async () => {
    const track = await tracker()
    show('?plan=Free&billing=annual')

    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))

    expect(callsOf(track, 'free_plan_clicked')).toEqual([
      ['free_plan_clicked', { plan: 'Free', billing: 'annual', source: 'checkout' }],
    ])
    // What used to sit here was `.not.toMatchObject({ source: 'pricing' })`,
    // which could not fail on its own: the toEqual above already pins `source`
    // to 'checkout' exactly, so no mutation reaches the negative without
    // breaking the line above it first. It read as coverage of the mis-stamp
    // and was none.
    //
    // This pins what that line only gestured at, and can fail while the
    // assertion above still passes: the entire event stream this journey
    // produces, in order. A second free_plan_clicked, a plan_selected
    // manufactured out of the confirm (it belongs to the pricing CTA and to
    // nothing else), a payment_button_clicked leaking into the free branch, or
    // the checkout_started that carries the whole Free funnel going missing —
    // each one breaks this and only this.
    expect(track.mock.calls.map(c => c[0]))
      .toEqual(['checkout_started', 'free_plan_clicked'])
  })

  // Placement is the whole point. Asking for an email while the visitor still
  // believes a purchase is in progress collects it under a false pretense; after
  // the disclosure they know there is nothing to pay, and the ask is honest.
  it('offers the email only after the disclosure, and never as a gate', async () => {
    show()
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Notify me' })).not.toBeInTheDocument()

    await userEvent.click(proceed())
    expect(screen.getByText(/no payment was taken/i)).toBeInTheDocument()
    const h2 = document.querySelector('.disclosure h2')!
    expect(h2.querySelector('svg.lucide-check')).toBeInTheDocument()
    expect(h2.textContent).not.toContain('✓')

    const box = screen.getByRole('textbox', { name: /optional/i })
    expect(box).toBeInTheDocument()
    expect(box).not.toBeRequired()
    expect(box).not.toHaveAttribute('pattern')
    expect(box).not.toBeDisabled()
    expect(screen.getByText(/^Optional —/)).toBeInTheDocument()
  })

  it('records the address when an email is given, and nothing when it is not', async () => {
    const track = await tracker()
    show()
    await userEvent.click(proceed())

    const notify = screen.getByRole('button', { name: 'Notify me' })
    await userEvent.click(notify)
    expect(screen.getByRole('textbox', { name: /optional/i })).toBeInTheDocument()
    expect(callsOf(track, 'email_submitted')).toHaveLength(0)

    await userEvent.type(screen.getByRole('textbox', { name: /optional/i }), 'a@b.com')
    await userEvent.click(notify)
    expect(callsOf(track, 'email_submitted')).toEqual([
      ['email_submitted', { plan: 'Pro', billing: 'annual', email: 'a@b.com' }],
    ])
    expect(screen.getByText(/we[’']ll email you when early access opens/i))
      .toBeInTheDocument()
  })

  // The input is deliberately not inside a <form> — a form on this page is one
  // edit away from being a checkout — so nothing supplies the submit gesture by
  // default. Without this, a visitor types an address, presses Enter and the page
  // silently drops the invitation the copy directly above has just promised,
  // while the email leg of the funnel quietly undercounts.
  it('submits the email on Enter, and still posts nothing for a blank field', async () => {
    const track = await tracker()
    show()
    await userEvent.click(proceed())

    const box = screen.getByRole('textbox', { name: /optional/i })
    await userEvent.type(box, '{Enter}')
    expect(callsOf(track, 'email_submitted')).toHaveLength(0)
    expect(screen.queryByText(/we[’']ll email you when early access opens/i))
      .not.toBeInTheDocument()

    await userEvent.type(box, 'keys@b.com{Enter}')
    expect(callsOf(track, 'email_submitted')).toEqual([
      ['email_submitted', { plan: 'Pro', billing: 'annual', email: 'keys@b.com' }],
    ])
    expect(screen.getByText(/we[’']ll email you when early access opens/i))
      .toBeInTheDocument()
  })

  // Fires on arrival and stays fired: a re-render — clicking through, typing an
  // email — must not post the funnel step again.
  it('records the checkout view once on arrival, carrying the plan', async () => {
    const track = await tracker()
    show()
    expect(callsOf(track, 'checkout_started'))
      .toEqual([['checkout_started', { plan: 'Pro', billing: 'annual' }]])

    await userEvent.click(proceed())
    await userEvent.type(screen.getByRole('textbox', { name: /optional/i }), 'x')
    expect(callsOf(track, 'checkout_started')).toHaveLength(1)
  })

  // The sentence points the reader at a demo that is not on this route, and the
  // mini-nav only offers the plans — so the pointer has to be a link or it is an
  // instruction the page cannot carry out.
  it('links the demo it points at, so the reader can reach it from here', async () => {
    show('?plan=Free&billing=annual')
    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))
    expect(screen.getByRole('link', { name: /the demo/i }))
      .toHaveAttribute('href', '/#analyze')
  })

  it('offers a way back to pricing', () => {
    show()
    expect(screen.getByRole('link', { name: /Back to pricing/ }))
      .toHaveAttribute('href', '/#pricing')
  })
})

/** `?plan=` and `?billing=` are in the address bar, so anyone can edit them. A
 *  fake door may not answer a hand-edited URL with a blank page, an `undefined`,
 *  or — worst of all — something false about money. */
describe('CheckoutPage degenerate query strings', () => {
  it.each([
    ['nothing at all', ''],
    ['no plan', '?billing=annual'],
    ['an empty plan', '?plan=&billing=annual'],
    ['an unknown plan', '?plan=Bogus&billing=annual'],
    ['a plan whose case is wrong', '?plan=pro&billing=annual'],
  ])('sends the reader back to the plans when the link names %s', async (_what, query) => {
    const track = await tracker()
    const { container } = show(query)

    expect(screen.getByText('No plan selected')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See the plans' }))
      .toHaveAttribute('href', '/#pricing')

    // Nothing about money, no purchase button, and nothing invented: naming a
    // plan the visitor did not choose would put a paid tier in front of someone
    // who chose none, and `?plan=Bogus` answered with "$0 — free plan" would be
    // a fake door telling a visitor something false about money.
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/\$/)
    expect(text).not.toMatch(/undefined|NaN|null/)
    expect(text).not.toMatch(/Bogus/)
    expect(screen.queryByRole('button', { name: 'Proceed to payment' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create free account' })).not.toBeInTheDocument()

    // No checkout was reached, so no checkout step may be posted. Counting
    // these would inflate the denominator of the derived abandonment rate with
    // visitors who were never shown a button to abandon.
    expect(callsOf(track, 'checkout_started')).toHaveLength(0)
  })

  it.each([
    ['is missing', '?plan=Pro'],
    ['is not a period we sell', '?plan=Pro&billing=weekly'],
    ['is empty', '?plan=Pro&billing='],
  ])('falls back to the annual period when billing %s', async (_what, query) => {
    const track = await tracker()
    show(query)
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Annual')).toBeInTheDocument()
    expect(screen.getByText('$216 / year ($18.00/mo)')).toBeInTheDocument()
    expect(callsOf(track, 'checkout_started'))
      .toEqual([['checkout_started', { plan: 'Pro', billing: 'annual' }]])
  })
})

describe('CheckoutPage copy rules', () => {
  const states = async () => {
    const paid = show()
    await userEvent.click(proceed())
    const free = show('?plan=Free&billing=monthly')
    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))
    const none = show('?plan=Bogus')
    return [paid, free, none]
  }

  // The single absolute constraint of this project, proven on every state the
  // page can reach rather than on the paid one alone. The DOM is correct today
  // because both paths share one input in one place — but before this loop
  // existed, an edit that added a field to the `!plan` branch would have passed
  // the entire suite.
  it('offers no form, select, textarea or non-email input in any state', async () => {
    const rendered = await states()
    expect(rendered).toHaveLength(3)
    for (const { container } of rendered) {
      // Anchored: an empty container satisfies every negative below for free.
      expect(container.querySelector('section#checkout')).toBeInTheDocument()
      expect(container.textContent).toMatch(/Intrinsica/)

      expect(container.querySelectorAll('form,select,textarea,input:not([type="email"])'))
        .toHaveLength(0)
      expect(container.querySelectorAll('input').length).toBeLessThanOrEqual(1)
    }
  })

  // A standalone route opens at h1: /checkout is its own document, not a section
  // of the landing page. Levels may not skip either — h2 straight to h4 reads as
  // a missing section to anything navigating by heading.
  it('opens at h1 and skips no heading level, in every state', async () => {
    for (const { container } of await states()) {
      const levels = [...container.querySelectorAll('h1,h2,h3,h4,h5,h6')]
        .map(h => Number(h.tagName[1]))
      expect(levels.length).toBeGreaterThan(0)
      expect(container.querySelectorAll('h1')).toHaveLength(1)
      expect(levels[0]).toBe(1)
      for (let i = 1; i < levels.length; i++) {
        expect(levels[i]).toBeLessThanOrEqual(levels[i - 1] + 1)
      }
    }
  })

  // Spec section 8, and the fake-door rule on invented urgency. A countdown or
  // a seat count corrupts the one number this page exists to collect.
  it('leaks no banned word, internal identifier, scoring cut-off or manufactured urgency', async () => {
    const rendered = await states()
    for (const { container } of rendered) {
      const text = container.textContent ?? ''
      expect(container.querySelector('.kicker')?.textContent?.length).toBeGreaterThan(3)
      expect(container.querySelector('.stitle')?.textContent?.length).toBeGreaterThan(10)
      expect(text).toMatch(/Intrinsica/)
      expect(text).not.toMatch(/signal/i)
      expect(text).not.toMatch(/Risk\s*[/-]\s*Reward/)
      expect(text).not.toMatch(/Reward[/-]Risk/)
      expect(text).not.toMatch(/[<>≥≤]\s*\d/)
      expect(text).not.toMatch(/scores?\s+\d/i)
      expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
      expect(text).not.toMatch(/\.py\b|\.tsx?\b/)
      expect(text).not.toMatch(/only \d+|seats? (left|remaining)|spots? left/i)
      expect(text).not.toMatch(/hurry|limited time|offer ends|expires?\b|countdown|act now/i)
      expect(text).not.toMatch(/free trial|trial (started|begins)|your account/i)
      expect(text).not.toMatch(/you will be charged|charged today|payment due/i)
      expect(container.querySelector('[title]')).toBeNull()
    }
  })

  // Repeats the site footer's short form (spec 5.8) rather than dropping the
  // disclaimer on the one page that talks about money.
  it('repeats the modeling-tool disclaimer on every state', async () => {
    for (const { container } of await states()) {
      expect(container.textContent)
        .toMatch(/Nothing on this platform constitutes personalized investment advice/)
    }
  })

  // Two briefs in a row invented class names and shipped no CSS for any of
  // them. Every class this page renders, in every state it can render, must
  // have a rule in theme.css or the page ships unstyled and nothing notices.
  it('styles every class it renders, in every state', async () => {
    // Resolved relative to this file, not process.cwd(): run from the repo root
    // a cwd-relative path does not merely fail, it throws ENOENT and the guard
    // reports an error instead of a verdict.
    const here = dirname(fileURLToPath(import.meta.url))
    const css = readFileSync(resolve(here, 'theme.css'), 'utf8')
    expect(css.length).toBeGreaterThan(1000)

    const used = new Set<string>()
    for (const { container } of await states()) {
      for (const el of container.querySelectorAll('*')) {
        for (const cls of el.classList) used.add(cls)
      }
    }
    expect(used.size).toBeGreaterThan(10)
    // lucide-react stamps its own `lucide` / `lucide-<name>` classes on every
    // icon; they are the library's, not ours to style (spec §4 line icons).
    const unstyled = [...used].filter(c => !/^lucide(-|$)/.test(c))
      .filter(c => !new RegExp(`\\.${c}(?![\\w-])`).test(css))
    expect(unstyled).toEqual([])
  })
})

/** The free disclosure quotes the demo's per-run cap, and this project's
 *  convention is that no second copy of that number exists anywhere. Proven by
 *  moving the constant: the module is re-mocked with a different cap and the copy
 *  has to follow it, which a hardcoded "3" cannot do. Asserting the shipped
 *  value against the shipped constant would have been a tautology — it passes
 *  just as happily against a number typed into the copy by hand. */
describe('CheckoutPage free disclosure tracks the demo cap', () => {
  it('quotes MAX_TICKERS rather than a number of its own', async () => {
    vi.resetModules()
    vi.doMock('./components/Hero', async importActual => ({
      ...(await importActual<typeof import('./components/Hero')>()),
      MAX_TICKERS: 7,
    }))
    try {
      const { default: Fresh } = await import('./CheckoutPage')
      const { container } = render(
        <MemoryRouter initialEntries={['/checkout?plan=Free&billing=annual']}>
          <Fresh />
        </MemoryRouter>,
      )
      await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))
      expect(container.textContent).toMatch(/no account was created/i)
      expect(container.textContent).toMatch(/up to 7 tickers per run/i)
      expect(container.textContent).not.toMatch(/up to 3 tickers/i)
    } finally {
      vi.doUnmock('./components/Hero')
      vi.resetModules()
    }
  })
})

/** Through the REAL router. Task 13 mounted its own CheckoutStub inside a
 *  MemoryRouter, which is correct for the URL it asserts but stands in for a
 *  route that did not exist — so clicking any plan CTA in the shipped app
 *  rendered a blank page and nothing in the suite noticed. A stub cannot be the
 *  only coverage of a seam. */
describe('/checkout route (controller addition)', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: [], error: null }),
    }))
  })

  it('mounts the real checkout page at /checkout', async () => {
    window.history.pushState({}, '', '/checkout?plan=Unlimited&billing=monthly')
    render(<App />)
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(screen.getByText('Unlimited')).toBeInTheDocument()
    expect(screen.getByText('Monthly')).toBeInTheDocument()
    expect(screen.getByText('$41.99 / month')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Proceed to payment' })).toBeInTheDocument()
  })

  // The landing page renders outside Layout — Layout is the analyst app's dark
  // chrome — and so must the checkout.
  it('renders outside the analyst app chrome', () => {
    window.history.pushState({}, '', '/checkout?plan=Pro&billing=annual')
    const { container } = render(<App />)
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
    expect(screen.queryByText('Database')).not.toBeInTheDocument()
    expect(screen.queryByText('New Analysis')).not.toBeInTheDocument()
  })

  // The one check nobody has been able to run since Task 13: the whole journey,
  // end to end, through the router the application actually ships.
  it('carries a plan CTA click from the landing page to a rendered checkout', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'Monthly' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))

    expect(window.location.pathname).toBe('/checkout')
    expect(window.location.search).toBe('?plan=Pro&billing=monthly')
    expect(screen.getByText('Confirm your plan')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Monthly')).toBeInTheDocument()
    expect(screen.getByText('$21.99 / month')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Choose Pro' })).not.toBeInTheDocument()
  })

  it('carries a Free CTA click to the free wording, not the paid one', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Analyze →' })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))

    expect(window.location.search).toBe('?plan=Free&billing=annual')
    expect(screen.getByText('Create your free account')).toBeInTheDocument()
    expect(screen.getByText('$0 — free plan')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Proceed to payment' })).not.toBeInTheDocument()
  })
})

/** AT MOST ONCE PER VISITOR. Paid-intent conversion is the single number this
 *  whole fake door exists to produce, and the button stays mounted and enabled
 *  after the click — `setClicked(true)` only reveals the disclosure beneath it.
 *  An impatient double-click therefore posted the intent twice. Spec line 378
 *  derives abandonment as checkout_started minus payment_button_clicked, so
 *  repeats do not merely inflate a rate, they can drive that subtraction
 *  NEGATIVE. At-most-once is entailed by the spec's own arithmetic.
 *
 *  The guard is on the FIRE, not on the button: `disabled` would take the
 *  button out of the tab order and change what the visitor sees, and this page
 *  already draws that line twice — Pricing's `reported` ref, LandingPage's
 *  `opening`. Counts are asserted, never mere presence: "the event fired" is
 *  true of three events as happily as of one. */
describe('CheckoutPage counts intent once per visitor', () => {
  it('posts payment_button_clicked once however often the button is pressed', async () => {
    const track = await tracker()
    show()

    await userEvent.click(proceed())
    await userEvent.click(proceed())
    await userEvent.click(proceed())

    expect(callsOf(track, 'payment_button_clicked')).toEqual([
      ['payment_button_clicked', { plan: 'Pro', billing: 'annual' }],
    ])
  })

  it('posts free_plan_clicked once however often the free button is pressed', async () => {
    const track = await tracker()
    show('?plan=Free&billing=monthly')
    const free = () => screen.getByRole('button', { name: 'Create free account' })

    await userEvent.click(free())
    await userEvent.click(free())
    await userEvent.click(free())

    expect(callsOf(track, 'free_plan_clicked')).toEqual([
      ['free_plan_clicked', { plan: 'Free', billing: 'monthly', source: 'checkout' }],
    ])
    expect(callsOf(track, 'payment_button_clicked')).toHaveLength(0)
  })

  // The guard may not swallow the state change it guards: the disclosure is the
  // honesty claim the entire fake door rests on, and a visitor who clicks twice
  // must still be looking at it — in its paid wording, with the fine print.
  it('still shows the disclosure, in its paid wording, after repeated clicks', async () => {
    show()
    await userEvent.click(proceed())
    await userEvent.click(proceed())

    expect(screen.getByText(/founding list/i)).toBeInTheDocument()
    expect(screen.getByText(/no payment was taken/i)).toBeInTheDocument()
    expect(screen.getByText(/Pro — Annual/)).toBeInTheDocument()
    expect(screen.getByText(/no card required/i)).toBeInTheDocument()
    expect(screen.queryByText(/no account was created/i)).not.toBeInTheDocument()
    expect(proceed()).toBeInTheDocument()
  })

  it('posts email_submitted once when Notify me is pressed twice on one address', async () => {
    const track = await tracker()
    show()
    await userEvent.click(proceed())

    const notify = screen.getByRole('button', { name: 'Notify me' })
    await userEvent.type(screen.getByRole('textbox', { name: /optional/i }), 'a@b.com')
    await userEvent.click(notify)
    await userEvent.click(notify)

    expect(callsOf(track, 'email_submitted')).toEqual([
      ['email_submitted', { plan: 'Pro', billing: 'annual', email: 'a@b.com' }],
    ])
    expect(screen.getByText(/we[’']ll email you when early access opens/i))
      .toBeInTheDocument()
  })

  // THE RE-ARM CASE, and the reason the email guard reads `sent` rather than a
  // permanent latch: `onChange` already clears `sent`, so a visitor who notices
  // a typo and corrects it gets the invitation the copy promised them. Anyone
  // "simplifying" the guard into a once-ever flag breaks exactly this, and a
  // fake door that silently drops the corrected address has broken the one
  // promise it is able to keep.
  it('re-arms the email when the address is corrected, and posts the correction', async () => {
    const track = await tracker()
    show()
    await userEvent.click(proceed())

    const box = screen.getByRole('textbox', { name: /optional/i })
    const notify = screen.getByRole('button', { name: 'Notify me' })

    await userEvent.type(box, 'typo@b.com')
    await userEvent.click(notify)
    await userEvent.clear(box)
    await userEvent.type(box, 'fixed@b.com')
    await userEvent.click(notify)

    expect(callsOf(track, 'email_submitted')).toEqual([
      ['email_submitted', { plan: 'Pro', billing: 'annual', email: 'typo@b.com' }],
      ['email_submitted', { plan: 'Pro', billing: 'annual', email: 'fixed@b.com' }],
    ])
  })
})

describe('privacy links on the checkout (launch checklist B4)', () => {
  it('links the privacy notice from the footer and beside the email field', async () => {
    show()
    await userEvent.click(proceed())
    const links = screen.getAllByRole('link', { name: /privacy/i })
    expect(links.length).toBeGreaterThanOrEqual(2)
    links.forEach(l => expect(l).toHaveAttribute('href', '/privacy'))
  })
})

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
    expect(screen.getByText('$29.99 / month')).toBeInTheDocument()
    expect(screen.queryByText('$300 / year ($25.00/mo)')).not.toBeInTheDocument()
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
      .toEqual([['free_plan_clicked', { plan: 'Free', billing: 'monthly' }]])
    expect(callsOf(track, 'payment_button_clicked')).toHaveLength(0)
    expect(callsOf(track, 'plan_selected')).toHaveLength(0)
    expect(callsOf(track, 'checkout_started'))
      .toEqual([['checkout_started', { plan: 'Free', billing: 'monthly' }]])
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
    const unstyled = [...used].filter(c => !new RegExp(`\\.${c}(?![\\w-])`).test(css))
    expect(unstyled).toEqual([])
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
    expect(screen.getByText('$29.99 / month')).toBeInTheDocument()
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

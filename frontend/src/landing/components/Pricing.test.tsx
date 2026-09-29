import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pricing from './Pricing'
import { COMPARE_ROWS, PLANS } from '../content/plans'

const GLYPHS = /[☆✕✓▾]/

/** Every negative assertion below is anchored: a real string and a real element
 *  are asserted first, so a Pricing that rendered nothing could not satisfy the
 *  guard by being empty. That matters most for the card/payment guard — this
 *  section is the closest thing on the page to a purchase flow, and "the DOM
 *  contains no card field" is trivially true of an empty DOM. */

type Entry = { isIntersecting: boolean }
type IOCallback = (entries: Entry[]) => void

afterEach(() => {
  vi.unstubAllGlobals()
})

const show = (billing: 'annual' | 'monthly' = 'annual', onChoose = vi.fn(),
              onBilling = vi.fn()) => {
  const utils = render(
    <Pricing billing={billing} onBilling={onBilling} onChoose={onChoose} />)
  return { ...utils, onChoose, onBilling }
}

describe('Pricing', () => {
  it('anchors the section the nav points at, and heads it', () => {
    const { container } = show()
    expect(container.querySelector('section#pricing')).toBeInTheDocument()
    expect(screen.getByText('Choose your plan')).toBeInTheDocument()
  })

  it('shows the annual effective prices by default', () => {
    show()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
    expect(screen.getByText('$25.00')).toBeInTheDocument()
    expect(screen.getByText('billed annually · $216/yr · save 18%')).toBeInTheDocument()
    expect(screen.getByText('billed annually · $300/yr · save 17%')).toBeInTheDocument()
    expect(screen.queryByText('$21.99')).not.toBeInTheDocument()
  })

  it('switches to monthly prices', () => {
    show('monthly')
    expect(screen.getByText('$21.99')).toBeInTheDocument()
    expect(screen.getByText('$29.99')).toBeInTheDocument()
    expect(screen.queryByText('$18.00')).not.toBeInTheDocument()
    expect(screen.queryByText('$25.00')).not.toBeInTheDocument()
  })

  it('costs nothing on Free, on either billing period', () => {
    for (const billing of ['annual', 'monthly'] as const) {
      const { container, unmount } = render(
        <Pricing billing={billing} onBilling={vi.fn()} onChoose={vi.fn()} />)
      const free = container.querySelectorAll<HTMLElement>('.price-card')[0]
      expect(within(free).getByText('$0')).toBeInTheDocument()
      expect(within(free).getByText('No card, ever')).toBeInTheDocument()
      unmount()
    }
  })

  // The toggle is a pair of aria-pressed buttons, the same pattern the framework
  // cards use. It is a controlled pair: it asks the page to change billing and
  // renders whatever comes back, so `billing` is the only source of truth.
  it('marks the active billing period and asks for the other one', async () => {
    const { onBilling } = show('annual')
    const annual = screen.getByRole('button', { name: /Annual/ })
    const monthly = screen.getByRole('button', { name: 'Monthly' })
    expect(annual).toHaveAttribute('aria-pressed', 'true')
    expect(monthly).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(monthly)
    expect(onBilling).toHaveBeenCalledWith('monthly')
    // Controlled: nothing moved on its own, because `billing` did not change.
    expect(screen.getByRole('button', { name: /Annual/ }))
      .toHaveAttribute('aria-pressed', 'true')
  })

  // The toggle advertises a saving of its own, and until this test nothing in
  // the suite checked it against the savings the cards actually quote: raising
  // it to "save ~40%" broke nothing. An overstated discount on the one page
  // whose job is to measure genuine willingness to pay corrupts the number it
  // exists to collect, so the tag is both pinned and bounded — it may never
  // claim more than the smallest saving a paid plan really offers.
  it('advertises an annual saving that neither plan overstates', () => {
    show()
    const annual = screen.getByRole('button', { name: /Annual/ })
    const tag = annual.querySelector('.save')
    expect(tag).not.toBeNull()
    expect(tag!.textContent).toBe('save ~17%')

    const claimed = Number(tag!.textContent!.match(/(\d+)%/)![1])
    const real = PLANS.slice(1).map(p => {
      const m = p.annual!.sub.match(/save (\d+)%/)
      expect(m).not.toBeNull()
      return Number(m![1])
    })
    expect(real).toHaveLength(2)
    expect(claimed).toBeLessThanOrEqual(Math.min(...real))

    // Monthly carries no tag: there is nothing saved by paying monthly.
    expect(screen.getByRole('button', { name: 'Monthly' }).querySelector('.save'))
      .toBeNull()
  })

  it('reports the chosen plan and billing period', async () => {
    const { onChoose } = show('annual')
    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    expect(onChoose).toHaveBeenCalledWith('Pro', 'annual')
  })

  it('carries the billing period actually showing into the choice', async () => {
    const { onChoose } = show('monthly')
    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))
    expect(onChoose).toHaveBeenCalledWith('Unlimited', 'monthly')
  })

  it('routes Free through the same chooser', async () => {
    const { onChoose } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))
    expect(onChoose).toHaveBeenCalledWith('Free', 'annual')
  })

  it('features Pro and only Pro, with no "most popular" text', () => {
    const { container } = show()
    const cards = Array.from(container.querySelectorAll<HTMLElement>('.price-card'))
    expect(cards).toHaveLength(3)
    expect(cards.map(c => c.classList.contains('featured')))
      .toEqual([false, true, false])
    expect(within(cards[1]).getByText('Deep Stock Analysis')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/most popular|best value|recommended/i)
  })

  it('renders every feature bullet of every plan', () => {
    const { container } = show()
    const bullets = Array.from(container.querySelectorAll('.feature-list li'))
    expect(bullets).toHaveLength(9)
    expect(screen.getByText('Unlimited analyses — no monthly cap')).toBeInTheDocument()
    expect(screen.getByText('~5 analyses a month · up to 3 tickers per run')).toBeInTheDocument()
  })

  // plans.test.ts pins the order of the arrays; this pins the order the reader
  // actually sees. Without it a component that sorted or reversed `p.features`
  // would still render all nine bullets and satisfy every other assertion here.
  // (The slim cards dropped the "Everything in Free, plus:" openers; the section
  // subtitle and the matrix's all-"Full" depth rows now carry that claim.)
  it('renders each card’s bullets in the order its plan declares them', () => {
    const { container } = show()
    const cards = Array.from(container.querySelectorAll<HTMLElement>('.price-card'))
    expect(cards).toHaveLength(PLANS.length)
    cards.forEach((card, i) => {
      const bullets = Array.from(card.querySelectorAll('.feature-list li'))
        .map(li => li.textContent)
      expect(bullets).toEqual(PLANS[i].features)
    })
  })

  // Nothing in the DOM ties a value to its column — the cells are rendered in
  // array order and read as a row of four — so the pinning has to be here.
  // Until this test, reversing `r.values.map(...)` broke nothing: every row
  // still had four cells, every label still matched, `cmp-no` still appeared,
  // and the page showed Free offering unlimited analyses and 100+ tickers while
  // Unlimited offered "—" for everything. A matrix that misstates every plan's
  // allowances, on the page whose whole purpose is measuring willingness to pay.
  // Each row's cells are pinned to that row's own values, in order.
  it('renders the whole compare matrix, every value under its own plan', () => {
    const { container } = show()
    const rows = Array.from(container.querySelectorAll('.cmp-plans tbody tr'))
    expect(rows).toHaveLength(COMPARE_ROWS.length)
    // The columns the values are pinned against, in PLANS order.
    expect(Array.from(container.querySelectorAll('.cmp-plans thead th'))
      .map(th => th.textContent))
      .toEqual(['Feature', ...PLANS.map(p => p.name)])

    rows.forEach((row, i) => {
      // `toBe(true)` rather than a negated contains: a row with no header cell
      // yields undefined, and undefined must fail rather than slip through.
      expect(row.querySelector('th')?.textContent?.startsWith(COMPARE_ROWS[i].label))
        .toBe(true)
      expect(Array.from(row.querySelectorAll('td')).map(td => td.textContent))
        .toEqual(COMPARE_ROWS[i].values)
    })

    expect(screen.getByText('Stocks per watchlist')).toBeInTheDocument()
    expect(screen.getByText(/Preview = the filters are visible/)).toBeInTheDocument()
  })

  // Task 9 made the results grid keyboard-operable and hover tooltips were ruled
  // out for being keyboard-unreachable; a sixteen-row matrix read cell by cell
  // with no row or column association is the same failure one level down. With
  // the scopes, a screen reader says "Watchlists, Pro, 5–10" instead of "5–10".
  it('associates every matrix cell with its row and its column', () => {
    const { container } = show()
    const cols = Array.from(container.querySelectorAll('.cmp-plans thead th'))
    expect(cols).toHaveLength(PLANS.length + 1)
    expect(cols.map(th => th.getAttribute('scope')))
      .toEqual(cols.map(() => 'col'))

    const rows = Array.from(container.querySelectorAll('.cmp-plans tbody tr'))
    expect(rows).toHaveLength(COMPARE_ROWS.length)
    for (const row of rows) {
      const heads = Array.from(row.querySelectorAll('th'))
      expect(heads).toHaveLength(1)
      expect(heads[0].getAttribute('scope')).toBe('row')
      // The feature name is the row's header, not a value cell beside it.
      expect(row.firstElementChild).toBe(heads[0])
    }
  })

  // Slim pricing (user decision 2026-09-27): the who-it-is-for cards and the
  // closing line are gone — each card's for-line now says who the plan is for.
  it('says who each plan is for on its own card, with no separate who-cards or closing line', () => {
    const { container } = show()
    const fors = Array.from(container.querySelectorAll('.price-card .pc-for')).map(e => e.textContent)
    expect(fors).toEqual(PLANS.map(p => p.forLine))
    for (const f of fors) expect(f).toMatch(/^For /)
    expect(container.querySelector('.who, .who-card, .compare-note')).toBeNull()
    expect(container).not.toHaveTextContent(/Free sells the framework/)
  })

  // The single hardest constraint in the project: the page must be structurally
  // incapable of taking money. Anchored on content that is really there, so an
  // empty render fails rather than passes.
  it('exposes no card, payment, address or name field anywhere', () => {
    const { container } = render(
      <Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()} />)
    expect(screen.getByText('Choose your plan')).toBeInTheDocument()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
    expect(container.querySelectorAll('.price-card')).toHaveLength(3)

    expect(container.querySelectorAll('input')).toHaveLength(0)
    expect(container.querySelectorAll('form')).toHaveLength(0)
    expect(container.querySelectorAll('textarea')).toHaveLength(0)
    expect(container.querySelectorAll('select')).toHaveLength(0)
    expect(container.querySelectorAll('input[type="password"]')).toHaveLength(0)
    expect(container.querySelectorAll('[autocomplete]')).toHaveLength(0)
    expect(container.textContent)
      .not.toMatch(/card number|cvc|cvv|expiry|billing address|cardholder/i)
  })

  // A smoke test measures willingness to pay. Manufactured pressure — a
  // countdown, a seat count, a deadline — corrupts the one number this page
  // exists to collect, so none of it may exist.
  it('invents no urgency and promises no account or charge', () => {
    const { container } = show()
    expect(screen.getByText('Choose Unlimited')).toBeInTheDocument()
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/only \d+|seats? (left|remaining)|spots? left/i)
    expect(text).not.toMatch(/hurry|limited time|offer ends|expires?\b|countdown|act now/i)
    expect(text).not.toMatch(/free trial|trial (started|begins)|your account/i)
    expect(text).not.toMatch(/you will be charged|charged today|payment due/i)
  })

  // Spec section 8, and the same two regexes Framework.test.tsx and
  // WhyWorkflow.test.tsx use. An outcome band ("Moat 80+") carries no inequality
  // operator; a published cut-off does, which is what separates them.
  it('leaks no banned word, internal identifier or scoring cut-off', () => {
    const { container } = show()
    const text = container.textContent ?? ''
    expect(container.querySelector('.stitle')?.textContent?.length).toBeGreaterThan(10)
    expect(container.querySelector('.kicker')?.textContent?.length).toBeGreaterThan(3)
    expect(text).toContain('Reward/Risk')
    expect(text).not.toMatch(/signal/i)
    expect(text).not.toMatch(/Risk\s*[/-]\s*Reward/)
    expect(text).not.toMatch(/Reward\s*-\s*Risk\b/)
    expect(text).not.toMatch(/[<>≥≤]\s*\d/)
    expect(text).not.toMatch(/scores?\s+\d/i)
    expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
    expect(text).not.toMatch(/\.py\b/)
  })

  // Controller ruling: nothing on this page hides behind hover. Every note in
  // the matrix is rendered inline instead.
  it('hides nothing behind a hover tooltip', () => {
    const { container } = show()
    expect(screen.getByText(/Intrinsica re-runs your watchlists/)).toBeInTheDocument()
    expect(container.querySelector('[title]')).toBeNull()
  })

  // Two briefs in a row invented class names and shipped no CSS for any of them.
  // Every class this section renders must have a rule in theme.css, or the
  // section ships unstyled and nothing in the suite notices.
  it('styles every class it renders', () => {
    // Resolved relative to this file, not to process.cwd(): run from the repo
    // root rather than frontend/, a cwd-relative path does not merely fail, it
    // throws ENOENT and the guard reports an error instead of a verdict.
    const here = dirname(fileURLToPath(import.meta.url))
    const css = readFileSync(resolve(here, '../theme.css'), 'utf8')
    expect(css.length).toBeGreaterThan(1000)
    const { container } = show()
    const used = new Set<string>()
    for (const el of container.querySelectorAll('*')) {
      for (const cls of el.classList) used.add(cls)
    }
    expect(used.size).toBeGreaterThan(15)
    // lucide-react stamps its own `lucide` / `lucide-<name>` classes on every
    // icon; they are the library's, not ours to style (spec §4 line icons).
    const unstyled = [...used].filter(c => !/^lucide(-|$)/.test(c))
      .filter(c => !new RegExp(`\\.${c}(?![\\w-])`).test(css))
    expect(unstyled).toEqual([])
  })

  it('reports the section as viewed once it scrolls into view', () => {
    const observers: IOCallback[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: IOCallback) { observers.push(cb) }
      observe() {}
      disconnect() {}
    })
    const onView = vi.fn()
    render(<Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()}
                    onView={onView} />)
    expect(onView).not.toHaveBeenCalled()

    observers[0]([{ isIntersecting: true }])
    observers[0]([{ isIntersecting: true }])
    expect(onView).toHaveBeenCalledTimes(1)
  })

  // Mounting is not viewing: this section renders with the page, well below the
  // fold. An observer that never reports an intersection must never report a view.
  it('does not report a view for a section that merely mounted', () => {
    const observers: IOCallback[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: IOCallback) { observers.push(cb) }
      observe() {}
      disconnect() {}
    })
    const onView = vi.fn()
    render(<Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()}
                    onView={onView} />)
    expect(observers).toHaveLength(1)
    observers[0]([{ isIntersecting: false }])
    expect(onView).not.toHaveBeenCalled()
  })

  it('does not break where IntersectionObserver is unavailable', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    expect(() => render(
      <Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()}
               onView={vi.fn()} />)).not.toThrow()
    expect(screen.getByText('Choose your plan')).toBeInTheDocument()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
  })
})

describe('Pricing — line icons (spec §4)', () => {
  it('checks each plan bullet with a drawn check, text unchanged', () => {
    const { container } = render(<Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()} />)
    const bullets = Array.from(container.querySelectorAll('.feature-list li'))
    expect(bullets.length).toBeGreaterThan(0)
    for (const li of bullets) {
      expect(li.firstElementChild).toHaveClass('fl-check')
      expect(li.textContent).not.toMatch(GLYPHS)
    }
  })
})

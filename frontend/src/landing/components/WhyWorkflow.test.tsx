import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import Why from './Why'
import Workflow from './Workflow'

/** Both sections are pure copy, which is exactly why every guard below names a
 *  real string or a real element before it asserts an absence. A test made only
 *  of `not` assertions is satisfied by a component that renders nothing at all,
 *  and this project has shipped that mistake twice. */

const TRUST_CARDS = [
  'Deterministic & reproducible',
  'Transparent to the last detail',
  'Calibrated for real companies',
]

const SCALE_CARDS = [
  'Re-evaluate whole watchlists',
  'Discover what fits your criteria',
  'Automated monitoring',
]

const STEP_TITLES = [
  'Analyze or discover',
  'Compare',
  'Watch & re-evaluate',
  'Monitor & automate',
]

describe('Why Intrinsica', () => {
  it('anchors the section the nav points at', () => {
    const { container } = render(<Why />)
    expect(container.querySelector('section#why')).toBeInTheDocument()
    expect(screen.getByText(/Why Intrinsica/)).toBeInTheDocument()
  })

  it('names all four assessments and says they must be read together', () => {
    const { container } = render(<Why />)
    const text = container.textContent ?? ''
    for (const name of ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']) {
      expect(text).toContain(name)
    }
    expect(text).toMatch(/read together/i)
    expect(text).toMatch(/wrong price/i)
    expect(text).toMatch(/eroding/i)
  })

  // Spec 5.5's second half: answering the four by hand costs hours per company,
  // and the engine costs seconds. Dropping either half of that trade leaves the
  // "why not do it yourself" question unanswered, so both are pinned.
  it('makes the time argument, hours against seconds', () => {
    const { container } = render(<Why />)
    const text = container.textContent ?? ''
    expect(text).toMatch(/hours of statement work/i)
    expect(text).toMatch(/in seconds/i)
    expect(text).toMatch(/watchlist/i)
  })

  it('shows two labelled rows of three cards each, in spec order', () => {
    const { container } = render(<Why />)
    const rows = Array.from(container.querySelectorAll<HTMLElement>('.why-row'))
    expect(rows).toHaveLength(2)
    expect(rows.map(r => r.querySelector('.why-lbl')?.textContent))
      .toEqual(['Trust the analysis', 'Put it to work at scale'])
    expect(rows.map(r => Array.from(r.querySelectorAll('.diff h4')).map(h => h.textContent)))
      .toEqual([TRUST_CARDS, SCALE_CARDS])
  })

  it('gives every card a body, not just a heading', () => {
    const { container } = render(<Why />)
    const bodies = Array.from(container.querySelectorAll('.diff p'))
    expect(bodies).toHaveLength(6)
    for (const p of bodies) expect((p.textContent ?? '').length).toBeGreaterThan(60)
  })

  // Spec 5.5 ends "*No plan pill on this row.*" — the scale row describes the
  // product, and naming a plan beside each capability turns it into a pricing
  // table two sections early.
  it('carries no plan pill and names no plan on the scale row', () => {
    const { container } = render(<Why />)
    const scale = Array.from(container.querySelectorAll<HTMLElement>('.why-row'))
      .find(r => r.querySelector('.why-lbl')?.textContent === 'Put it to work at scale')!
    expect(within(scale).getByText('Re-evaluate whole watchlists')).toBeInTheDocument()
    expect(scale.querySelector('.pill')).toBeNull()
    expect(scale.textContent).not.toMatch(/\b(Unlimited|Pro|Free|per month|\$)\b/)
  })
})

describe('Workflow', () => {
  it('anchors the section the nav points at', () => {
    const { container } = render(<Workflow />)
    expect(container.querySelector('section#workflow')).toBeInTheDocument()
    expect(screen.getByText('Analyze → Compare → Watch → Monitor')).toBeInTheDocument()
  })

  it('has exactly four numbered steps, in order, ending at monitor and automate', () => {
    const { container } = render(<Workflow />)
    expect(Array.from(container.querySelectorAll('.wf .step')).map(s => s.textContent))
      .toEqual(['STEP 1', 'STEP 2', 'STEP 3', 'STEP 4'])
    expect(Array.from(container.querySelectorAll('.wf h4')).map(h => h.textContent))
      .toEqual(STEP_TITLES)
  })

  it('gives every step a body', () => {
    const { container } = render(<Workflow />)
    const bodies = Array.from(container.querySelectorAll('.wf p'))
    expect(bodies).toHaveLength(4)
    for (const p of bodies) expect((p.textContent ?? '').length).toBeGreaterThan(50)
  })

  // Spec 5.6: "Discover is folded in here; it is not its own step." The title
  // equality above is what actually enforces that — a fifth card, or a card
  // renamed to Discover, fails it. These two assertions pin the wording that
  // does the folding.
  it('folds discover into the first step rather than giving it one of its own', () => {
    const { container } = render(<Workflow />)
    const first = container.querySelector<HTMLElement>('.wf')!
    expect(within(first).getByText('Analyze or discover')).toBeInTheDocument()
    expect(first.textContent).toMatch(/screening/i)
    expect(container.textContent).not.toMatch(/STEP 5/)
  })

  // Spec 5.6: "no per-tier limit strips and no 'feeds back into Analyze' line".
  it('shows no per-tier limit strip and no loop-back line', () => {
    const { container } = render(<Workflow />)
    expect(within(container).getByText('Monitor & automate')).toBeInTheDocument()
    expect(container.querySelector('.tiers')).toBeNull()
    expect(container.textContent).not.toMatch(/feeds back into Analyze/)
    expect(container.textContent).not.toMatch(/\b(Unlimited|\d+\s*(analyses|tickers)\s*(a|per)\s*month)\b/)
  })
})

describe('Why and Workflow — page rules', () => {
  const sections: [string, () => HTMLElement][] = [
    ['Why', () => render(<Why />).container],
    ['Workflow', () => render(<Workflow />).container],
  ]

  // Spec section 8 rules 1 and 2. Anchored on the section's own heading, so a
  // component that rendered nothing could not satisfy these by default.
  it.each(sections)('%s never says signal, and never says Risk/Reward', (_n, mount) => {
    const container = mount()
    const text = container.textContent ?? ''
    expect(container.querySelector('.stitle')?.textContent?.length).toBeGreaterThan(10)
    expect(text).not.toMatch(/signal/i)
    expect(text).not.toMatch(/Risk\s*\/\s*Reward/)
  })

  // Spec section 8 rules 3 and 5. A per-metric cut-off reads "ROIC > 15% scores
  // 8"; the published outcome bands ("Moat 80+") carry no inequality operator,
  // which is what separates the two here as it does in Framework.test.tsx.
  it.each(sections)('%s leaks no internal identifier, module name or scoring cut-off',
    (_n, mount) => {
      const container = mount()
      const text = container.textContent ?? ''
      expect(container.querySelector('.kicker')?.textContent?.length).toBeGreaterThan(3)
      expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
      expect(text).not.toMatch(/\.py\b/)
      expect(text).not.toMatch(/[<>≥≤]\s*\d/)
      expect(text).not.toMatch(/scores?\s+\d/i)
    })

  // Controller ruling: no hover-only affordance anywhere on this page — mobile
  // never sees a `title`, and a keyboard cannot reach one.
  it.each(sections)('%s takes no input and hides nothing behind hover', (_n, mount) => {
    const container = mount()
    expect(container.querySelector('section')).toBeInTheDocument()
    expect(container.querySelector('.container')).toBeInTheDocument()
    expect(container.querySelector('input')).toBeNull()
    expect(container.querySelector('form')).toBeNull()
    expect(container.querySelector('textarea')).toBeNull()
    expect(container.querySelector('[title]')).toBeNull()
  })
})

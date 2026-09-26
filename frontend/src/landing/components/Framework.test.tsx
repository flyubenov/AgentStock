import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Framework from './Framework'
import { CALIBRATIONS, FRAMEWORK } from '../content/framework'
import type { AssessmentId } from '../types'

const TABS = [0, 1, 2, 3] as const

const show = (tab: AssessmentId = 0, onTab = vi.fn()) =>
  render(<Framework tab={tab} onTab={onTab} />)

describe('Framework — overview card', () => {
  // Variant D3 (user decision): a two-sentence lead, then the judgment note; the
  // four highlights it used to carry are gone, not moved.
  it('shows the short lead, with the real calibration count, and the closing line', () => {
    const { container } = show()
    const lead = container.querySelector('.ovcard .ssub')!
    expect(lead).toHaveTextContent(/Four separate engines turn the latest fundamentals into four scores/)
    expect(lead.querySelector('b')).toHaveTextContent(`${CALIBRATIONS.length} data-triggered calibrations`)
    expect(lead).toHaveTextContent(/Same data, same score\./)
    expect(screen.getByText(/Click an assessment for every category/)).toBeInTheDocument()
    expect(container.querySelector('.ovpts')).not.toBeInTheDocument()
  })

  it('anchors the section the nav points at', () => {
    const { container } = show()
    expect(container.querySelector('section#how')).toBeInTheDocument()
  })
})

describe('Framework — assessment cards', () => {
  // D3: a tab is the name alone — the question, scale, weights and counts are
  // all in the panel, and the question is said once, in the panel's header.
  it('labels each tab with the assessment name only, and puts its question in the panel', () => {
    const { container } = show(1)
    for (const b of container.querySelectorAll('.mcards button')) {
      expect(FRAMEWORK.map(a => a.name)).toContain(b.textContent)
    }
    expect(container.querySelector('.mdetail .d-q')).toHaveTextContent(FRAMEWORK[1].question)
    expect(container.querySelector('.mbox .mcards + .mdetail')).toBeInTheDocument()
  })

  it('offers a card per assessment, in the shared assessment order', () => {
    const { container } = show()
    const labels = Array.from(container.querySelectorAll('.mcards .cn'))
      .map(n => n.textContent)
    expect(labels).toEqual(FRAMEWORK.map(a => a.name))
  })

  it('marks the selected card as pressed and the others as not', () => {
    const { container } = show(2)
    const cards = Array.from(container.querySelectorAll<HTMLButtonElement>('.mcards button'))
    expect(cards.map(c => c.getAttribute('aria-pressed')))
      .toEqual(['false', 'false', 'true', 'false'])
  })

  it('asks for the clicked assessment by its assessment id', async () => {
    const onTab = vi.fn()
    show(0, onTab)
    await userEvent.click(screen.getByRole('button', { name: /Fair Value/ }))
    expect(onTab).toHaveBeenCalledWith(2)
    await userEvent.click(screen.getByRole('button', { name: /Reward \/ Risk/ }))
    expect(onTab).toHaveBeenCalledWith(3)
  })
})

describe('Framework — detail panel', () => {
  it('shows the selected assessment with its weights and scores-high pair', () => {
    show()
    expect(screen.getByText('35% of the score · 7 metrics')).toBeInTheDocument()
    expect(screen.getAllByText(/Scores high:/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Scores low:/).length).toBeGreaterThan(0)
  })

  // Spec 5.4: the panel is "identical in shape across all four — this
  // consistency is a requirement; they had drifted". This is the test that
  // enforces it. Every field the content module declares has to reach the DOM
  // on every tab, so dropping `note` from the markup, rendering only the first
  // group, or losing one hi/lo line all fail here rather than shipping a panel
  // that is quietly thinner than its three siblings.
  it('renders every declared field of every assessment, on every tab', () => {
    for (const tab of TABS) {
      const a = FRAMEWORK[tab]
      const { container, unmount } = show(tab)
      const panel = container.querySelector<HTMLElement>('.mdetail')!

      expect(panel).toHaveTextContent(a.name)
      expect(panel).toHaveTextContent(a.scale)
      expect(panel).toHaveTextContent(a.what)
      expect(panel).toHaveTextContent(a.note)
      expect(panel.querySelectorAll('.grpblock')).toHaveLength(a.groups.length)
      for (const g of a.groups) {
        expect(panel).toHaveTextContent(g.title)
        expect(panel).toHaveTextContent(g.weight)
        expect(panel).toHaveTextContent(g.metrics)
        expect(panel).toHaveTextContent(g.hi)
        expect(panel).toHaveTextContent(g.lo)
      }
      expect(within(panel).getAllByText(`${a.hiLabel}:`)).toHaveLength(a.groups.length)
      expect(within(panel).getAllByText(`${a.loLabel}:`)).toHaveLength(a.groups.length)
      unmount()
    }
  })

  it('switches the whole panel when the selected assessment changes', () => {
    const { unmount } = show(0)
    expect(screen.getByText('Growth & Margins')).toBeInTheDocument()
    expect(screen.queryByText('Cash-backing')).not.toBeInTheDocument()
    unmount()

    show(1)
    expect(screen.getByText('Cash-backing')).toBeInTheDocument()
    expect(screen.queryByText('Growth & Margins')).not.toBeInTheDocument()
  })

  it('says Weighted up / down on Fair Value and Scores high / low elsewhere', () => {
    const { unmount } = show(2)
    expect(screen.getAllByText('Weighted up:').length).toBeGreaterThan(0)
    expect(screen.queryByText('Scores high:')).not.toBeInTheDocument()
    unmount()

    show(3)
    expect(screen.getAllByText('Scores high:').length).toBeGreaterThan(0)
    expect(screen.queryByText('Weighted up:')).not.toBeInTheDocument()
  })
})

describe('Framework — calibrations', () => {
  const expected = (tab: AssessmentId) =>
    CALIBRATIONS.filter(c => c.affects.includes(FRAMEWORK[tab].name)).map(c => c.name)

  it('lists exactly the calibrations that touch the selected assessment', () => {
    for (const tab of TABS) {
      const { container, unmount } = show(tab)
      const names = Array.from(container.querySelectorAll('.arow .nm')).map(n => n.textContent)
      expect(names.length).toBeGreaterThan(0)
      expect(names).toEqual(expected(tab))
      unmount()
    }
  })

  it('lists only the calibrations that touch the selected assessment', () => {
    show(1)
    expect(screen.getByText('Economic-profit gate')).toBeInTheDocument()
    expect(screen.queryByText('De-financialization')).not.toBeInTheDocument()
  })

  it('keeps calibration detail collapsed until asked, and folds it away again', async () => {
    show(1)
    expect(screen.queryByText(/When it applies/)).not.toBeInTheDocument()

    const row = screen.getByRole('button', { name: /Economic-profit gate/ })
    expect(row).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(screen.getByText('Economic-profit gate'))
    expect(screen.getByText(/When it applies/)).toBeInTheDocument()
    expect(screen.getByText(/What it does/)).toBeInTheDocument()
    expect(row).toHaveAttribute('aria-expanded', 'true')

    await userEvent.click(row)
    expect(screen.queryByText(/When it applies/)).not.toBeInTheDocument()
    expect(row).toHaveAttribute('aria-expanded', 'false')
  })

  it('opens one calibration at a time', async () => {
    const { container } = show(1)
    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))
    expect(container.querySelectorAll('.arow.open')).toHaveLength(1)
    await userEvent.click(screen.getByText('Economic-profit gate'))
    expect(container.querySelectorAll('.arow.open')).toHaveLength(1)
    expect(screen.getByText(/no durable advantage without economic profit/i))
      .toBeInTheDocument()
  })

  // Spec 5.4 item 5 — "all collapsed by default" reads as *on arrival at a
  // panel*, not merely on the section's first render. Tangible-ROIC affects
  // both Quality and Moat, so without a reset an expanded row follows the
  // reader onto a panel they have only just opened.
  it('collapses an expanded calibration when the assessment changes', async () => {
    const { rerender } = render(<Framework tab={0} onTab={vi.fn()} />)
    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))
    expect(screen.getByText(/When it applies/)).toBeInTheDocument()

    rerender(<Framework tab={1} onTab={vi.fn()} />)
    // The row itself is still listed — Moat is its second assessment — so this
    // is a statement about its expansion, not about it disappearing.
    expect(screen.getByText('Tangible-ROIC (ex-goodwill)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Tangible-ROIC/ }))
      .toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText(/When it applies/)).not.toBeInTheDocument()
  })

  it('tags a one-directional calibration Guarded and a plain one only Conditional', async () => {
    const { container } = show(1)
    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))
    expect(within(container.querySelector<HTMLElement>('.arow.open')!).getByText('Guarded'))
      .toBeInTheDocument()

    await userEvent.click(screen.getByText('Economic-profit gate'))
    const plain = within(container.querySelector<HTMLElement>('.arow.open')!)
    expect(plain.getByText('Conditional')).toBeInTheDocument()
    expect(plain.queryByText('Guarded')).not.toBeInTheDocument()
  })

  it('shows an example only for a calibration that has one', async () => {
    show(1)
    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))
    expect(screen.getByText(/AMD after the Xilinx acquisition/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Economic-profit gate'))
    expect(screen.queryByText(/Example:/)).not.toBeInTheDocument()
  })
})

describe('Framework — page rules', () => {
  // Controller ruling: no hover-only affordance on this page. It is public
  // marketing with heavy mobile traffic, where `title` never appears at all, so
  // the tag explanations are rendered inline instead.
  // The mock explains each tag in a hover tooltip. Here the tooltip is also
  // reachable by keyboard focus (and by tap on a phone), its text is always in
  // the DOM for a screen reader, and nothing hangs off a `title` attribute.
  it('explains its tags in a focusable tooltip, never a title attribute', async () => {
    const { container } = show(1)
    await userEvent.click(screen.getByText('Tangible-ROIC (ex-goodwill)'))
    const tip = screen.getByText(/only when the company's data matches/i)
    expect(tip).toHaveAttribute('role', 'tooltip')
    expect(tip.closest('.tagwrap')).toHaveAttribute('tabindex', '0')
    expect(container.querySelector('[title]')).toBeNull()
  })

  // Spec section 8 rules 5 and 8. The anchors make this non-vacuous: a panel
  // that rendered nothing, or the wrong assessment, fails before any regex.
  it('leaks no internal identifier, module name or scoring cut-off', () => {
    const anchors = ['Growth & Margins', 'Cash-backing', 'Sales multiples', 'Reward axis']
    for (const tab of TABS) {
      const { container, unmount } = show(tab)
      const text = container.textContent ?? ''
      expect(text).toContain(anchors[tab])
      expect(container.querySelector('.mdetail')).toBeInTheDocument()
      expect(text).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
      expect(text).not.toMatch(/\.py\b/)
      // A per-metric cut-off would read "ROIC > 15% scores 8". Outcome bands
      // ("9+ is top-decile") carry no inequality operator.
      expect(text).not.toMatch(/[<>≥≤]\s*\d/)
      unmount()
    }
  })

  it('never says signal, and never says Risk/Reward, on any tab', () => {
    const anchors = ['Growth & Margins', 'Cash-backing', 'Sales multiples', 'Reward axis']
    for (const tab of TABS) {
      const { container, unmount } = show(tab)
      const text = container.textContent ?? ''
      expect(text).toContain(anchors[tab])
      expect(text).not.toMatch(/signal/i)
      expect(text).not.toMatch(/Risk\s*\/\s*Reward/)
      unmount()
    }
  })

  // Anchored for the same reason as the two guards above: three `not` assertions
  // on their own are satisfied by a component that rendered nothing at all, so
  // the panel has to be proved present before its emptiness means anything.
  it('takes no card, payment, address or name input', () => {
    const { container } = show()
    expect(container.querySelector('.mdetail')).toBeInTheDocument()
    expect(screen.getByText('How Intrinsica works')).toBeInTheDocument()
    expect(container.querySelector('input')).not.toBeInTheDocument()
    expect(container.querySelector('form')).not.toBeInTheDocument()
    expect(container.querySelector('textarea')).not.toBeInTheDocument()
  })

  // Variant E (user decision): three of the four assessments are judgments, and
  // the overview card says so — as its second paragraph, in the original wording
  // (option B, 2026-09-27).
  it('says plainly that the scores are a methodology, not a measurement', () => {
    const { container } = show(0)
    const note = container.querySelector('.ovcard .judg')!
    expect(note).toHaveTextContent('A methodology, not a measurement.')
    expect(note).toHaveTextContent(/Quality, Moat and Reward\/Risk have no single correct formula/)
    expect(note).toHaveTextContent(/assembles the fundamentals that bear on each/)
    expect(note).toHaveTextContent(/see exactly how a score was reached, and disagree with it\./)
    const order = Array.from(container.querySelectorAll('.ovcard > p')).map(p => p.className)
    expect(order).toEqual(['ssub', 'ssub judg', 'ovtail'])
    expect(container.querySelector('.ovsplit')).toBeNull()
  })
})

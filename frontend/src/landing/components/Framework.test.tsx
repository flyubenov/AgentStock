import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Framework from './Framework'
import { CALIBRATIONS, FRAMEWORK } from '../content/framework'
import type { AssessmentId } from '../types'

const GLYPHS = /[☆✕✓▾]/

const TABS = [0, 1, 2, 3] as const

const show = (tab: AssessmentId = 0, onTab = vi.fn()) =>
  render(<Framework tab={tab} onTab={onTab} />)

const rows = (c: HTMLElement) => Array.from(c.querySelectorAll<HTMLElement>('.mdetail .crow'))
const openAll = async (c: HTMLElement) => {
  for (const b of c.querySelectorAll<HTMLButtonElement>('.crow .ch')) await userEvent.click(b)
}

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
  it('groups the tabs under the two questions: the business, then the price', () => {
    const { container } = show()
    const pairs = Array.from(container.querySelectorAll('.mpair'))
    expect(pairs.map(p => p.querySelector('.mpl')?.textContent))
      .toEqual(['Is it a good business?', 'At a good price?'])
    expect(pairs.map(p => Array.from(p.querySelectorAll('.cn')).map(n => n.textContent)))
      .toEqual([['Quality', 'Moat'], ['Fair Value', 'Reward / Risk']])
  })
  // D3: a tab is the name alone — the question, scale, weights and counts are
  // all in the panel, and the question is said once, in the panel's header.
  it('labels each tab with the assessment name only, and puts its question in the panel', () => {
    const { container } = show(1)
    for (const b of container.querySelectorAll('.mcards button')) {
      expect(FRAMEWORK.map(a => a.name)).toContain(b.textContent)
    }
    expect(container.querySelector('.mdetail .d-q')).toHaveTextContent(FRAMEWORK[1].question)
    expect(container.querySelector('.mbox .mpairs + .mdetail')).toBeInTheDocument()
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
  it('shows every category collapsed: title, question and weight, no metrics yet', () => {
    const { container } = show(0)
    const rs = rows(container)
    expect(rs).toHaveLength(FRAMEWORK[0].groups.length)
    FRAMEWORK[0].groups.forEach((g, i) => {
      expect(rs[i].querySelector('.nm')).toHaveTextContent(g.title)
      expect(rs[i].querySelector('.cq')).toHaveTextContent(g.question)
      expect(rs[i].querySelector('.cw')).toHaveTextContent(g.weight)
      expect(rs[i].querySelector('.ch')).toHaveAttribute('aria-expanded', 'false')
      expect(rs[i].querySelector('.chips')).toBeNull()
    })
  })

  it('opens a row to its metric chips and one ▲ / ▼ line, and rows toggle independently', async () => {
    const { container } = show(0)
    const [first, second] = FRAMEWORK[0].groups
    await userEvent.click(screen.getByRole('button', { name: new RegExp(first.title) }))
    let rs = rows(container)
    expect(rs[0]).toHaveClass('open')
    expect(rs[0].querySelectorAll('.chips li')).toHaveLength(first.metrics.length)
    expect(rs[0].querySelector('.chl')).toHaveTextContent(`High: ${first.hi}`)
    expect(rs[0].querySelector('.chl')).toHaveTextContent(`Low: ${first.lo}`)
    expect(rs[1]).not.toHaveClass('open')

    await userEvent.click(screen.getByRole('button', { name: new RegExp(second.title) }))
    rs = rows(container)
    expect(rs[0]).toHaveClass('open')
    expect(rs[1]).toHaveClass('open')

    await userEvent.click(screen.getByRole('button', { name: new RegExp(first.title) }))
    expect(rows(container)[0]).not.toHaveClass('open')
  })

  // Spec 5.4: "identical in shape across all four". Every field has to reach
  // the DOM on every tab once the rows are open.
  it('renders every declared field of every assessment, on every tab', async () => {
    for (const tab of TABS) {
      const a = FRAMEWORK[tab]
      const { container, unmount } = show(tab)
      await openAll(container)
      const panel = container.querySelector<HTMLElement>('.mdetail')!
      expect(panel).toHaveTextContent(a.name)
      expect(panel).toHaveTextContent(a.scale)
      expect(panel).toHaveTextContent(a.what)
      expect(panel.querySelector('.note')).toHaveTextContent(a.note)
      expect(panel.querySelectorAll('.bands li')).toHaveLength(a.bands.length)
      for (const g of a.groups) {
        expect(panel).toHaveTextContent(g.title)
        expect(panel).toHaveTextContent(g.question)
        for (const m of g.metrics) expect(panel).toHaveTextContent(m)
        expect(panel).toHaveTextContent(g.hi)
        expect(panel).toHaveTextContent(g.lo)
      }
      expect(within(panel).getAllByText(`${a.hiLabel}:`)).toHaveLength(a.groups.length)
      expect(within(panel).getAllByText(`${a.loLabel}:`)).toHaveLength(a.groups.length)
      unmount()
    }
  })

  it('draws a weight bar only for fixed shares, scaled to the largest category', () => {
    const { container, unmount } = show(0)
    const widths = rows(container).map(r => r.querySelector<HTMLElement>('.cbar i')!.style.width)
    expect(widths).toEqual(['100%', '86%', '43%', '57%'])   // 35 / 30 / 15 / 20 of 35
    unmount()
    const fv = show(2)
    expect(fv.container.querySelector('.cbar')).toBeNull()
  })

  it('shows the scale strip, or only the line for Fair Value', () => {
    const { container, unmount } = show(0)
    expect(Array.from(container.querySelectorAll('.bands li')).map(l => l.textContent))
      .toEqual(FRAMEWORK[0].bands)
    unmount()
    const fv = show(2)
    expect(fv.container.querySelector('.bands')).toBeNull()
    expect(fv.container.querySelector('.note')).toHaveTextContent(FRAMEWORK[2].note)
  })

  // Review Focus 3: a new panel arrives with every row collapsed.
  it('collapses open rows when the assessment changes', async () => {
    const { container, rerender } = show(0)
    await openAll(container)
    rerender(<Framework tab={1} onTab={vi.fn()} />)
    expect(rows(container).every(r => !r.classList.contains('open'))).toBe(true)
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

  it('says Weighted up / down on Fair Value and High / Low elsewhere', async () => {
    const fv = show(2)
    await openAll(fv.container)
    expect(screen.getAllByText('Weighted up:').length).toBeGreaterThan(0)
    expect(screen.queryByText('High:')).not.toBeInTheDocument()
    fv.unmount()
    const rr = show(3)
    await openAll(rr.container)
    expect(screen.getAllByText('High:').length).toBeGreaterThan(0)
    expect(screen.queryByText('Weighted up:')).not.toBeInTheDocument()
  })
})

describe('Framework — calibrations', () => {
  const expected = (tab: AssessmentId) =>
    CALIBRATIONS.filter(c => c.affects.includes(FRAMEWORK[tab].name)).map(c => c.name)

  it('lists exactly the calibrations that touch the selected assessment', () => {
    for (const tab of TABS) {
      const { container, unmount } = show(tab)
      const names = Array.from(container.querySelectorAll('.cal-wrap .arow .nm')).map(n => n.textContent)
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
    expect(container.querySelectorAll('.cal-wrap .arow.open')).toHaveLength(1)
    await userEvent.click(screen.getByText('Economic-profit gate'))
    expect(container.querySelectorAll('.cal-wrap .arow.open')).toHaveLength(1)
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
    expect(within(container.querySelector<HTMLElement>('.cal-wrap .arow.open')!).getByText('Guarded'))
      .toBeInTheDocument()

    await userEvent.click(screen.getByText('Economic-profit gate'))
    const plain = within(container.querySelector<HTMLElement>('.cal-wrap .arow.open')!)
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

  it('opens calibration rows with a drawn chevron', () => {
    const { container } = show(0)
    const heads = Array.from(container.querySelectorAll('.cal-wrap .arow .ah'))
    expect(heads.length).toBeGreaterThan(0)
    for (const h of heads) {
      expect(h.querySelector('svg.chev')).toBeInTheDocument()
      expect(h.textContent).not.toMatch(GLYPHS)
    }
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
  it('says plainly that the scores come from Intrinsica’s own method', () => {
    const { container } = show(0)
    const note = container.querySelector('.ovcard .judg')!
    // Wording chosen 2026-09-27 (variant 3): explains the method and states the
    // judgment plainly, without a warning tone or a "disagree with it" ending.
    expect(note.querySelector('b')).toHaveTextContent('Intrinsica’s own method.')
    // General concepts, lower case (user decision): capitalised, "Quality, Moat or
    // Reward/Risk" would read as Intrinsica's own scores having no agreed formula.
    // Reworded 2026-09-29 (user decision): the old "no single agreed way…" read as
    // if Intrinsica itself had no settled method.
    expect(note).toHaveTextContent(/aren’t printed in any filing; they have to be assessed\./)
    expect(note).toHaveTextContent(/one fixed methodology/)
    expect(note).toHaveTextContent(/the same way for every company\./)
    expect(note).toHaveTextContent(/Each score opens up to the inputs and weights behind it\.$/)
    expect(note).not.toHaveTextContent(/no single agreed/i)
    expect(note).not.toHaveTextContent(/disagree/i)
    const order = Array.from(container.querySelectorAll('.ovcard > p')).map(p => p.className)
    expect(order).toEqual(['ssub', 'ssub judg', 'ovtail'])
    expect(container.querySelector('.ovsplit')).toBeNull()
  })
})

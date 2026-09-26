import { afterEach, describe, it, expect, vi } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultGrid, { RunBar } from './ResultGrid'
import type { TickerPayload } from '../types'

function row(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
    quality: { score: 9.1, fundamentals_composite: 9.1, profile_label: 'Tech / Growth', categories: [] },
    moat: { score: 90, gated: false, excluded: [], factors: [] },
    fair_value: { value: 211, gap_pct: -9.05, type_label: 'Mega Cap', methods: [] },
    reward_risk: { ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
                   reward: [], risk: [] },
    calibrations: [], errors: [],
    ...over,
  }
}

const render1 = (rows: TickerPayload[], open = {}) =>
  render(<ResultGrid rows={rows} open={open} onToggle={vi.fn()}
                     renderBreakdown={() => <div>BREAKDOWN</div>} />)

describe('ResultGrid', () => {
  it('puts the units in the header, not the cells', () => {
    render1([row()])
    const header = screen.getAllByRole('row')[0]
    expect(within(header).getByText(/Quality/)).toHaveTextContent('/10')
    expect(within(header).getByText(/Moat/)).toHaveTextContent('/100')
    expect(within(header).getByText(/Reward\/Risk/)).toBeInTheDocument()
    const cells = screen.getAllByRole('cell').map(c => c.textContent)
    expect(cells).toContain('9.1')
    expect(cells).toContain('90')
  })

  it('never labels the ratio Risk/Reward', () => {
    const { container } = render1([row()])
    expect(container.textContent).not.toMatch(/Risk\/Reward|Risk \/ Reward/)
  })

  it('shows no tier word in the grid', () => {
    const { container } = render1([row()])
    expect(container.textContent).not.toMatch(/Balanced/)
  })

  it('colour-bands the fair-value gap', () => {
    const { container } = render1([row()])
    expect(container.querySelector('.gap-warn')).toBeInTheDocument()
  })

  // --- Review Focus 1: one engine failed ---
  it('renders a row whose quality and moat are missing', () => {
    const { container } = render1([row({ quality: null, moat: null })])
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/NaN|null|undefined/)
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  // --- Review Focus 2: no fair value ---
  it('renders a row with no fair value without inventing a gap', () => {
    const { container } = render1([row({ fair_value: null })])
    expect(container.textContent).not.toMatch(/NaN|Infinity/)
    expect(container.querySelector('.gap-none')).toBeInTheDocument()
  })

  it('expands a row on click and shows its breakdown', async () => {
    const onToggle = vi.fn()
    render(<ResultGrid rows={[row()]} open={{}} onToggle={onToggle}
                       renderBreakdown={() => <div>BREAKDOWN</div>} />)
    await userEvent.click(screen.getByText('AAPL'))
    expect(onToggle).toHaveBeenCalledWith('AAPL')
    expect(screen.queryByText('BREAKDOWN')).not.toBeInTheDocument()
  })

  it('shows the breakdown for an already-open row', () => {
    render1([row()], { AAPL: true })
    expect(screen.getByText('BREAKDOWN')).toBeInTheDocument()
  })

  // --- Compare mode: best-in-column highlight (spec 5.2), Controller Addition 2 ---
  it('never highlights a column when only a single row is rendered', () => {
    const { container } = render1([row()])
    expect(container.querySelector('.best')).not.toBeInTheDocument()
  })

  it('highlights the best value per column only when comparing more than one row', () => {
    const rows = [
      row({ ticker: 'AAPL', quality: { score: 8.0, fundamentals_composite: 8.0, profile_label: null, categories: [] } }),
      row({ ticker: 'MSFT', quality: { score: 9.5, fundamentals_composite: 9.5, profile_label: null, categories: [] } }),
    ]
    const { container } = render1(rows)
    const msftRow = screen.getByText('MSFT').closest('tr')!
    expect(within(msftRow).getByText('9.5')).toHaveClass('best')
    const aaplRow = screen.getByText('AAPL').closest('tr')!
    expect(within(aaplRow).getByText('8.0')).not.toHaveClass('best')
    // Quality is the only column these two rows differ in, so it is the only
    // cell that may carry the highlight — the shared moat/gap/ratio columns
    // must stay plain (see the tie test below).
    expect(container.querySelectorAll('.best')).toHaveLength(1)
  })

  // --- Fix round 1: ties are not standouts ---
  it('highlights nothing in a column where every row shows the same value', () => {
    // Identical rows apart from the ticker: max === every value, so an
    // equality test alone would paint the entire grid "best", which reads as
    // "all best" rather than "no standout".
    const { container } = render1([row({ ticker: 'AAPL' }), row({ ticker: 'MSFT' })])
    expect(container.querySelector('.best')).not.toBeInTheDocument()
  })

  it('still highlights the shared leader when only some rows tie at the top', () => {
    const q = (score: number) => ({ score, fundamentals_composite: score,
                                    profile_label: null, categories: [] })
    render1([
      row({ ticker: 'AAPL', quality: q(9.5) }),
      row({ ticker: 'MSFT', quality: q(9.5) }),
      row({ ticker: 'NVDA', quality: q(7.0) }),
    ])
    for (const t of ['AAPL', 'MSFT']) {
      expect(within(screen.getByText(t).closest('tr')!).getByText('9.5')).toHaveClass('best')
    }
    expect(within(screen.getByText('NVDA').closest('tr')!).getByText('7.0'))
      .not.toHaveClass('best')
  })

  it('does not call a lone value best when the other rows have no value at all', () => {
    const { container } = render1([
      row({ ticker: 'AAPL', moat: { score: 90, gated: false, excluded: [], factors: [] } }),
      row({ ticker: 'MSFT', moat: null }),
    ])
    expect(within(screen.getByText('AAPL').closest('tr')!).getByText('90'))
      .not.toHaveClass('best')
    expect(container.querySelector('.best')).not.toBeInTheDocument()
  })

  // --- Fix round 1: the row must be operable without a mouse ---
  it('exposes each row as a named, expandable control', () => {
    render1([row()])
    const control = screen.getByRole('button', { name: 'AAPL' })
    expect(control).toHaveAttribute('aria-expanded', 'false')
  })

  it('reports the open state on the row control', () => {
    render1([row()], { AAPL: true })
    expect(screen.getByRole('button', { name: 'AAPL' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('expands a row from the keyboard with Enter and with Space', async () => {
    const onToggle = vi.fn()
    render(<ResultGrid rows={[row()]} open={{}} onToggle={onToggle}
                       renderBreakdown={() => <div>BREAKDOWN</div>} />)
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'AAPL' })).toHaveFocus()

    await userEvent.keyboard('{Enter}')
    expect(onToggle).toHaveBeenCalledWith('AAPL')
    expect(onToggle).toHaveBeenCalledTimes(1)

    await userEvent.keyboard(' ')
    expect(onToggle).toHaveBeenCalledTimes(2)
  })

  it('toggles once, not twice, when the ticker itself is clicked', async () => {
    // The row control sits inside the row's own onClick. Without
    // stopPropagation both handlers fire and the row opens and shuts again.
    const onToggle = vi.fn()
    render(<ResultGrid rows={[row()]} open={{}} onToggle={onToggle}
                       renderBreakdown={() => <div>BREAKDOWN</div>} />)
    await userEvent.click(screen.getByRole('button', { name: 'AAPL' }))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('still toggles from anywhere else in the row', async () => {
    const onToggle = vi.fn()
    render(<ResultGrid rows={[row()]} open={{}} onToggle={onToggle}
                       renderBreakdown={() => <div>BREAKDOWN</div>} />)
    await userEvent.click(screen.getByText('Apple Inc.'))
    expect(onToggle).toHaveBeenCalledTimes(1)
    expect(onToggle).toHaveBeenCalledWith('AAPL')
  })

  it('keeps the caret out of the accessibility tree', () => {
    const { container } = render1([row()])
    const caret = container.querySelector('.chev')!
    expect(caret).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('ResultGrid — watchlist star', () => {
  const noop = () => null
  it('offers an unlocked star beside every ticker that reports the ticker, without opening the row', async () => {
    const onWatch = vi.fn(), onToggle = vi.fn()
    render(<ResultGrid rows={[row(), row({ ticker: 'MSFT' })]} open={{}} onToggle={onToggle}
                       renderBreakdown={noop} onWatch={onWatch} />)
    const star = screen.getByRole('button', { name: 'Add MSFT to a watchlist' })
    expect(star).toHaveTextContent('☆')
    expect(star).not.toHaveTextContent('🔒')
    await userEvent.click(star)
    expect(onWatch).toHaveBeenCalledWith('MSFT')
    expect(onToggle).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Add AAPL to a watchlist' })).toBeInTheDocument()
  })

  it('shows no star when the page does not ask for one', () => {
    render(<ResultGrid rows={[row()]} open={{}} onToggle={noop} renderBreakdown={noop} />)
    expect(screen.queryByRole('button', { name: /watchlist/ })).not.toBeInTheDocument()
  })
})

describe('RunBar', () => {
  it('reports each ticker, the count and the time when more than one ran', () => {
    const { container } = render(
      <RunBar rows={[row(), row({ ticker: 'MSFT' }), row({ ticker: 'NVDA' })]} ms={2140} />)
    expect(container).toHaveTextContent('Computed in parallel:')
    expect(container).toHaveTextContent('3 tickers · 2.1s')
    expect(screen.getAllByLabelText('done')).toHaveLength(3)
  })

  it('marks a ticker whose engines all declined as failed, not done', () => {
    render(<RunBar rows={[row(), row({ ticker: 'ZZZZ', quality: null, moat: null,
                                          fair_value: null, reward_risk: null })]} ms={900} />)
    expect(screen.getAllByLabelText('done')).toHaveLength(1)
    expect(screen.getAllByLabelText('failed')).toHaveLength(1)
  })

  it('stays out of the way for a single ticker', () => {
    const { container } = render(<RunBar rows={[row()]} ms={500} />)
    expect(container).toBeEmptyDOMElement()
  })

  // Loading variant E (user decision): a multi-ticker run in flight shows the strip
  // at once, live, over whatever the previous result was. It never marks a ticker
  // done — the backend answers all of them in one response.
  describe('while a run is in flight', () => {
    afterEach(() => { vi.useRealTimers() })

    it('says it is computing, names every pending ticker and counts the time up', async () => {
      vi.useFakeTimers()
      const { container } = render(
        <RunBar rows={[row()]} ms={500} pending={['AAPL', 'MSFT', 'NVDA']} />)
      const bar = screen.getByRole('status')
      expect(bar).toHaveTextContent('Computing in parallel:')
      for (const t of ['AAPL', 'MSFT', 'NVDA']) expect(bar).toHaveTextContent(t)
      expect(bar).toHaveTextContent('3 tickers · 0.0s')
      expect(container.querySelectorAll('.mini.ind')).toHaveLength(3)
      expect(screen.queryByLabelText('done')).not.toBeInTheDocument()
      await act(async () => { await vi.advanceTimersByTimeAsync(1250) })
      expect(bar).toHaveTextContent('3 tickers · 1.2s')
    })

    it('shows nothing live for a single pending ticker — the button covers that', () => {
      const { container } = render(<RunBar rows={[]} ms={null} pending={['AAPL']} />)
      expect(container).toBeEmptyDOMElement()
    })
  })
})

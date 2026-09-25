import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultGrid from './ResultGrid'
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
    expect(container.querySelectorAll('.best').length).toBeGreaterThan(0)
    const msftRow = screen.getByText('MSFT').closest('tr')!
    expect(within(msftRow).getByText('9.5')).toHaveClass('best')
    const aaplRow = screen.getByText('AAPL').closest('tr')!
    expect(within(aaplRow).getByText('8.0')).not.toHaveClass('best')
  })
})

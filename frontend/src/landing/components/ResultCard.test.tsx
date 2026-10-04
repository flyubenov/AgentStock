import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultCard, { type ResultCardProps } from './ResultCard'
import type { TickerPayload } from '../types'

const GLYPHS = /[☆✕✓▾]/

function row(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 341.07,
    quality: { score: 7.8, fundamentals_composite: 7.84, profile_label: 'Tech / Growth', categories: [] },
    moat: { score: 9.5, gated: false, excluded: [], factors: [] },
    fair_value: { value: 158.83, gap_pct: -53.43, type_label: 'Mega Cap', methods: [] },
    reward_risk: { ratio: 1.06, tier: 'Balanced', reward_score: 2.13, risk_score: 2.01, reward: [], risk: [] },
    calibrations: [], errors: [],
    ...over,
  }
}

function show(over: Partial<ResultCardProps> = {}) {
  const props: ResultCardProps = {
    rows: [row()], source: 'sample', pending: [], busy: false, ms: null, open: null,
    onTile: vi.fn(), onRow: vi.fn(), onWatch: vi.fn(), ...over,
  }
  return { ...render(<ResultCard {...props} />), props }
}

describe('ResultCard — before any result', () => {
  it('shows a frame, not a hole, while the first run is in flight', () => {
    const { container } = show({ rows: [], busy: true, pending: ['AAPL'] })
    expect(container.querySelector('.rc')).toHaveTextContent('Running the analysis…')
    expect(container.querySelector('.rc')).not.toHaveTextContent(/\d/)
  })
  it('says the live example could not be loaded when there is nothing to show', () => {
    const { container } = show({ rows: [], busy: false })
    expect(container.querySelector('.rc'))
      .toHaveTextContent('The live example could not be loaded. Try a ticker on the left.')
  })
})

describe('ResultCard — tiles view (one ticker)', () => {
  it('shows the four scores in assessment order with units and tier captions', () => {
    show()
    const tiles = screen.getAllByRole('button', { name: /^(Quality|Moat|Fair Value|Reward \/ Risk)/ })
    expect(tiles.map(t => t.textContent)).toEqual([
      expect.stringMatching(/^Quality.*7\.8.*\/10.*Strong/),
      expect.stringMatching(/^Moat.*9\.5.*\/10.*Wide/),
      expect.stringMatching(/^Fair Value.*\$159.*Fair value 53% below price/),
      expect.stringMatching(/^Reward \/ Risk.*1\.1.*×.*Balanced/),
    ])
  })
  it('colours the Fair Value caption with the % vs price band', () => {
    show()
    expect(screen.getByText('Fair value 53% below price')).toHaveClass('gap-neg')
  })
  it('labels a sample run as the live example and a typed run as the visitor’s own', () => {
    const { unmount } = show({ source: 'sample' })
    expect(screen.getByText(/Live example · computed just now/)).toBeInTheDocument()
    unmount()
    show({ source: 'typed' })
    expect(screen.getByText('Your analysis')).toBeInTheDocument()
    expect(screen.queryByText(/Live example/)).not.toBeInTheDocument()
  })
  it('shows ticker, company, price and profile in the header', () => {
    const { container } = show()
    const head = container.querySelector('.rc-head')!
    expect(head).toHaveTextContent('AAPL')
    expect(head).toHaveTextContent('Apple Inc.')
    expect(head).toHaveTextContent('$341.07 · Tech / Growth profile')
  })
  it('asks for the breakdown of the clicked score, by ticker and tab', async () => {
    const { props } = show()
    await userEvent.click(screen.getByRole('button', { name: /^Moat/ }))
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 1)
    await userEvent.click(screen.getByRole('button', { name: /^Reward \/ Risk/ }))
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 3)
  })
  // User 2026-10-05: the footer line read like a link and did nothing when clicked.
  it('opens the Quality breakdown from the footer line', async () => {
    const { props } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Click any score for its full breakdown ↓' }))
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 0)
  })
  it('leaves an open Quality breakdown open when the footer line is clicked again', async () => {
    const { props } = show({ open: { ticker: 'AAPL', tab: 0 } })
    await userEvent.click(screen.getByRole('button', { name: 'Click any score for its full breakdown ↓' }))
    expect(props.onTile).not.toHaveBeenCalled()
  })
  it('marks only the tile whose breakdown is open as pressed', () => {
    show({ open: { ticker: 'AAPL', tab: 2 } })
    const pressed = screen.getAllByRole('button', { name: /^(Quality|Moat|Fair Value|Reward \/ Risk)/ })
      .map(t => t.getAttribute('aria-pressed'))
    expect(pressed).toEqual(['false', 'false', 'true', 'false'])
  })
  it('renders a failed assessment as a dash that can still be clicked', async () => {
    const { props } = show({ rows: [row({ quality: null, fair_value: null })] })
    const q = screen.getByRole('button', { name: /^Quality/ })
    expect(q).toHaveTextContent('—')
    expect(q).toHaveTextContent('Could not be computed')
    expect(screen.getByRole('button', { name: /^Fair Value/ })).toHaveTextContent('Could not be computed')
    await userEvent.click(q)
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 0)
  })
  it('offers the watchlist star without opening anything', async () => {
    const { props } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Add AAPL to a watchlist' }))
    expect(props.onWatch).toHaveBeenCalledWith('AAPL')
    expect(props.onTile).not.toHaveBeenCalled()
  })
  it('never says Risk/Reward or signal', () => {
    const { container } = show()
    expect(container.textContent).not.toMatch(/Risk\s*\/\s*Reward|signal/i)
  })
})

const trio = () => [
  row({ ticker: 'NVDA', company_name: 'NVIDIA Corporation', price: 225.07,
        quality: { score: 9.2, fundamentals_composite: 9.2, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 6.98, gated: false, excluded: [], factors: [] },
        fair_value: { value: 172.62, gap_pct: -23.31, type_label: null, methods: [] },
        reward_risk: { ratio: 1.85, tier: 'Reward-Favored', reward_score: 3.7, risk_score: 2, reward: [], risk: [] } }),
  row({ ticker: 'AMD', company_name: 'Advanced Micro Devices, Inc.', price: 630.63,
        quality: { score: 7.2, fundamentals_composite: 7.2, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 2.5, gated: false, excluded: [], factors: [] },
        fair_value: { value: 308.92, gap_pct: -51.01, type_label: null, methods: [] },
        reward_risk: { ratio: 1.08, tier: 'Balanced', reward_score: 2.7, risk_score: 2.5, reward: [], risk: [] } }),
  row({ ticker: 'AVGO', company_name: 'Broadcom Inc.', price: 352.81,
        quality: { score: 8.8, fundamentals_composite: 8.8, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 8.65, gated: false, excluded: [], factors: [] },
        fair_value: { value: 216.1, gap_pct: -38.75, type_label: null, methods: [] },
        reward_risk: { ratio: 1.88, tier: 'Reward-Favored', reward_score: 3.8, risk_score: 2, reward: [], risk: [] } }),
]

describe('ResultCard — comparison view (two or three tickers)', () => {
  it('shows one row per ticker with its scores and tier captions', () => {
    const { container } = show({ rows: trio(), source: 'typed' })
    expect(container.querySelector('.rc-head')).toHaveTextContent('Comparing 3')
    const rows = container.querySelectorAll('.rc-row')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent(/NVDA.*9\.2.*Top-decile.*7\.0.*Established.*\$173.*−23%.*1\.9×.*Reward-Favored/)
    expect(rows[1]).toHaveTextContent(/AMD.*Little or none/)
  })
  it('highlights the best value per column, and only there', () => {
    const { container } = show({ rows: trio() })
    const cellsOf = (t: string) => within(screen.getByRole('button', { name: t }).closest('.rc-row') as HTMLElement)
    expect(cellsOf('NVDA').getByText('9.2').closest('.rc-cell')).toHaveClass('best')   // quality
    expect(cellsOf('AVGO').getByText('8.7').closest('.rc-cell')).toHaveClass('best')    // moat
    expect(cellsOf('NVDA').getByText('−23%').closest('.rc-cell')).toHaveClass('best')  // gap: -23 is highest
    expect(cellsOf('AVGO').getByText('1.9×').closest('.rc-cell')).toHaveClass('best')  // 1.88 > 1.85
    expect(container.querySelectorAll('.rc-cell.best')).toHaveLength(4)
  })
  it('asks for a ticker’s breakdown from its row button and from anywhere in the row', async () => {
    const { container, props } = show({ rows: trio() })
    await userEvent.click(screen.getByRole('button', { name: 'AMD' }))
    expect(props.onRow).toHaveBeenCalledTimes(1)
    expect(props.onRow).toHaveBeenLastCalledWith('AMD')
    await userEvent.click(container.querySelectorAll('.rc-row')[2].querySelector('.rc-cell')!)
    expect(props.onRow).toHaveBeenLastCalledWith('AVGO')
    expect(props.onRow).toHaveBeenCalledTimes(2)
  })
  it('reports which row is open on its button', () => {
    show({ rows: trio(), open: { ticker: 'AVGO', tab: 0 } })
    expect(screen.getByRole('button', { name: 'AVGO' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'NVDA' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('stars a ticker without opening its row', async () => {
    const { props } = show({ rows: trio() })
    await userEvent.click(screen.getByRole('button', { name: 'Add AMD to a watchlist' }))
    expect(props.onWatch).toHaveBeenCalledWith('AMD')
    expect(props.onRow).not.toHaveBeenCalled()
  })
  it('carries the run summary in the header once the run is done', () => {
    const { container } = show({ rows: trio(), ms: 2100 })
    expect(container.querySelector('.rc-head')).toHaveTextContent('3 tickers · 2.1 s')
  })
  it('keeps the comparison footer line as plain text: each row opens its own breakdown', () => {
    show({ rows: [row(), row({ ticker: 'MSFT' })] })
    expect(screen.getByText('Click a ticker for its full breakdown ↓').closest('button')).toBeNull()
  })
  it('shows a failed cell as a dash', () => {
    const rows = trio(); rows[1] = { ...rows[1], moat: null }
    show({ rows })
    const amd = screen.getByRole('button', { name: 'AMD' }).closest('.rc-row') as HTMLElement
    expect(within(amd).getAllByText('—').length).toBeGreaterThan(0)
  })
})

describe('ResultCard — while a run is in flight', () => {
  it('shows the live strip for several tickers and dims the previous result', () => {
    const { container } = show({ busy: true, pending: ['NVDA', 'AMD', 'AVGO'] })
    expect(screen.getByRole('status')).toHaveTextContent(/Computing in parallel:.*NVDA.*AMD.*AVGO/)
    const body = container.querySelector('.stale')!
    expect(body).toHaveAttribute('aria-busy', 'true')
    expect(body).toHaveTextContent('AAPL')
  })
  it('dims without a strip for a single pending ticker — the button covers that', () => {
    const { container } = show({ busy: true, pending: ['NVDA'] })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(container.querySelector('.stale')).not.toBeNull()
  })
  it('hides the run summary while a new run is in flight', () => {
    const { container } = show({ rows: trio(), ms: 2100, busy: true, pending: ['AAPL', 'MSFT'] })
    expect(container.querySelector('.rc-head')).not.toHaveTextContent('2.1 s')
  })
})

describe('ResultCard — line icons (spec §4)', () => {
  it('draws the watch button as a bookmark and keeps its name', () => {
    const { container } = show()
    const watch = screen.getByRole('button', { name: 'Add AAPL to a watchlist' })
    expect(watch.querySelector('svg.lucide-bookmark')).toBeInTheDocument()
    expect(watch.textContent).not.toMatch(GLYPHS)
    // spec §4: the brand mark never appears on a result
    expect(container.querySelector('.brandmark')).toBeNull()
  })

  it('ends every score tile in a drawn chevron', () => {
    const { container } = show()
    const tiles = Array.from(container.querySelectorAll('.rc-tile'))
    expect(tiles).toHaveLength(4)
    for (const t of tiles) expect(t.querySelector('svg.tile-chev')).toBeInTheDocument()
  })
})

describe('ResultCard — Moat on 0–10 (spec §5.2)', () => {
  it('shows Moat like Quality: one decimal out of 10, with its tier', () => {
    const { container } = show()
    const tile = Array.from(container.querySelectorAll('.rc-tile'))[1]
    expect(tile).toHaveTextContent('9.5')
    expect(tile).toHaveTextContent('/10')
    expect(tile).not.toHaveTextContent('/100')
    expect(tile).toHaveTextContent('Wide')
  })

  // User decision 2026-10-03: Share sat squeezed between the bookmark and the
  // company name. One result: bottom right, beside the breakdown hint, labelled
  // with the stock. Comparison: an icon at the end of each row's name cell.
  it('puts Share for a single result in the footer, labelled with the stock', () => {
    const { container } = show({ rows: [row()] })
    const share = screen.getByRole('button', { name: 'Share AAPL' })
    expect(share).toHaveTextContent('Share AAPL')
    expect(container.querySelector('.rc-foot')!.contains(share)).toBe(true)
    expect(container.querySelector('.rc-head')!.contains(share)).toBe(false)
  })

  // User decision 2026-10-03 (option A): in a comparison the bookmark and an
  // icon-only Share sit together on the ticker's line, the same spot on every row
  // whatever the name's length; the company name gets its own line below.
  it('groups bookmark and icon-only Share on each compared row, before the name', () => {
    const { container } = show({ rows: [row(), row({ ticker: 'MSFT', company_name: 'Microsoft Corporation' })] })
    for (const t of ['AAPL', 'MSFT']) {
      const share = screen.getByRole('button', { name: `Share ${t}` })
      expect(share.textContent).toBe('')
      const acts = share.closest('.rc-acts')!
      expect(acts).not.toBeNull()
      expect(acts.querySelector('.watch')).not.toBeNull()
      const name = acts.closest('.rc-id')!.querySelector('.nm')!
      expect(acts.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
    expect(container.querySelector('.rc-foot')!.querySelector('button')).toBeNull()
  })

  // User report 2026-10-03: BRK.B computed nothing ("Could not be computed") yet
  // offered Share, which hands out a link to a stock with no result.
  it('offers no Share for a result that did not compute', () => {
    const failed = row({ ticker: 'BRK.B', quality: null, moat: null, fair_value: null,
                         reward_risk: null, errors: ['insufficient data for any model'] })
    const { rerender, props } = show({ rows: [failed] })
    expect(screen.queryByRole('button', { name: 'Share BRK.B' })).toBeNull()
    rerender(<ResultCard {...props} rows={[row(), failed]} />)
    expect(screen.queryByRole('button', { name: 'Share BRK.B' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Share AAPL' })).toBeInTheDocument()
  })
})

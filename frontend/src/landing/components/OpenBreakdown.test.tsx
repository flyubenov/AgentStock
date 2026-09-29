import { afterEach, describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OpenBreakdown from './OpenBreakdown'
import type { TickerPayload } from '../types'

const GLYPHS = /[☆✕✓▾]/

const ROW: TickerPayload = {
  ticker: 'AMD', company_name: 'Advanced Micro Devices, Inc.', price: 630.63,
  quality: { score: 7.2, fundamentals_composite: 7.2, profile_label: 'Tech / Growth', categories: [] },
  moat: { score: 25, gated: false, excluded: [],
          factors: [{ label: 'ROIC level', group: 'Magnitude', display: '9.8%', points: 4, max_points: 20, weight_pct: 20 }] },
  fair_value: null, reward_risk: null, calibrations: [], errors: [],
}

describe('OpenBreakdown', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('names the ticker and company above the unchanged breakdown', () => {
    render(<OpenBreakdown row={ROW} tab={1} onTab={vi.fn()} onClose={vi.fn()} />)
    const dock = screen.getByRole('region', { name: 'AMD full breakdown' })
    expect(dock).toHaveTextContent('AMD Advanced Micro Devices, Inc. · full breakdown')
    expect(dock.querySelector('.bd')).not.toBeNull()
    expect(dock).toHaveTextContent('ROIC level')
  })

  it('closes from its Close button', async () => {
    const onClose = vi.fn()
    render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('passes tab switches through to the page', async () => {
    const onTab = vi.fn()
    render(<OpenBreakdown row={ROW} tab={0} onTab={onTab} onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /^Moat/ }))
    expect(onTab).toHaveBeenCalledWith(1)
  })

  it('scrolls itself into view only when it opens off screen', () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    vi.spyOn(Element.prototype, 'getBoundingClientRect')
      .mockReturnValue({ top: 5000, bottom: 5600 } as DOMRect)
    const { unmount } = render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={vi.fn()} />)
    expect(scroll).toHaveBeenCalledTimes(1)
    unmount()

    scroll.mockClear()
    vi.spyOn(Element.prototype, 'getBoundingClientRect')
      .mockReturnValue({ top: 200, bottom: 800 } as DOMRect)
    render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={vi.fn()} />)
    expect(scroll).not.toHaveBeenCalled()
  })

  it('closes with a drawn × and keeps the name Close', () => {
    render(<OpenBreakdown row={ROW} tab={1} onTab={vi.fn()} onClose={vi.fn()} />)
    const x = screen.getByRole('button', { name: 'Close' })
    expect(x.querySelector('svg.lucide-x')).toBeInTheDocument()
    expect(x.textContent).not.toMatch(GLYPHS)
  })
})

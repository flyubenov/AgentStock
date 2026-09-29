import { afterEach, describe, it, expect, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import LiveRunBar from './LiveRunBar'

describe('LiveRunBar', () => {
  afterEach(() => { vi.useRealTimers() })

  it('says it is computing, names every pending ticker and counts the time up', async () => {
    vi.useFakeTimers()
    render(<LiveRunBar tickers={['AAPL', 'MSFT', 'NVDA']} />)
    const bar = screen.getByRole('status')
    expect(bar).toHaveTextContent(/Computing in parallel:.*AAPL.*MSFT.*NVDA/)
    expect(bar).toHaveTextContent('3 tickers · 0.0s')
    await act(async () => { vi.advanceTimersByTime(1200) })
    expect(bar).toHaveTextContent(/3 tickers · 1\.[12]s/)
  })

  it('keeps the sweeping bars out of the accessibility tree', () => {
    const { container } = render(<LiveRunBar tickers={['AAPL', 'MSFT']} />)
    const bars = container.querySelectorAll('.mini.ind')
    expect(bars).toHaveLength(2)
    for (const b of bars) expect(b).toHaveAttribute('aria-hidden', 'true')
  })
})

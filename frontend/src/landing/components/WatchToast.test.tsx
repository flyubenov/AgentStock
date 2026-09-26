import { afterEach, describe, it, expect, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WatchToast, { WATCH_TOAST_MS } from './WatchToast'

describe('WatchToast', () => {
  afterEach(() => { vi.useRealTimers() })

  it('says the ticker was not saved, that Free includes a watchlist, and links to the plans', () => {
    render(<WatchToast ticker="MSFT" onClose={vi.fn()} />)
    const toast = screen.getByRole('status')
    expect(toast).toHaveTextContent('MSFT not saved')
    expect(toast).toHaveTextContent(/Free\s+includes one/)
    expect(screen.getByRole('link', { name: 'See plans →' })).toHaveAttribute('href', '#pricing')
    // A fake door never claims a watchlist or an account now exists.
    expect(toast).not.toHaveTextContent(/added|saved to|created|your watchlist/i)
  })

  it('closes itself after ten seconds, not before', async () => {
    vi.useFakeTimers()
    const onClose = vi.fn()
    render(<WatchToast ticker="AAPL" onClose={onClose} />)
    expect(WATCH_TOAST_MS).toBe(10_000)
    await act(async () => { await vi.advanceTimersByTimeAsync(WATCH_TOAST_MS - 100) })
    expect(onClose).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(100) })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on the dismiss button and on the plans link', async () => {
    const onClose = vi.fn()
    render(<WatchToast ticker="AAPL" onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await userEvent.click(screen.getByRole('link', { name: 'See plans →' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})

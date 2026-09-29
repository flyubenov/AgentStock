import { afterEach, describe, it, expect, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WatchToast, { WATCH_TOAST_MS } from './WatchToast'

const GLYPHS = /[☆✕✓▾]/

describe('WatchToast', () => {
  afterEach(() => { vi.useRealTimers() })

  it('says a watchlist needs an account, points to Free, and links to the plans', () => {
    render(<WatchToast onClose={vi.fn()} />)
    const toast = screen.getByRole('status')
    expect(toast).toHaveTextContent('Watchlists require an Intrinsica account. Start with Free.')
    expect(screen.getByRole('link', { name: 'See plans →' })).toHaveAttribute('href', '#pricing')
    // A fake door never claims a watchlist or an account now exists.
    expect(toast).not.toHaveTextContent(/added|saved to|created|your watchlist/i)
  })

  it('closes itself after ten seconds, not before', async () => {
    vi.useFakeTimers()
    const onClose = vi.fn()
    render(<WatchToast onClose={onClose} />)
    expect(WATCH_TOAST_MS).toBe(10_000)
    await act(async () => { await vi.advanceTimersByTimeAsync(WATCH_TOAST_MS - 100) })
    expect(onClose).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(100) })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on the dismiss button and on the plans link', async () => {
    const onClose = vi.fn()
    render(<WatchToast onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await userEvent.click(screen.getByRole('link', { name: 'See plans →' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})

describe('WatchToast — line icons (spec §4)', () => {
  it('closes with a drawn × and keeps the name Dismiss', () => {
    render(<WatchToast onClose={vi.fn()} />)
    const x = screen.getByRole('button', { name: 'Dismiss' })
    expect(x.querySelector('svg.lucide-x')).toBeInTheDocument()
    expect(x.textContent).not.toMatch(GLYPHS)
  })
})

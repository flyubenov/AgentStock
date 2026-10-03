import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ShareButton from './ShareButton'
import { shareUrl, shareText } from '../share'

vi.mock('../../lib/analytics', async importActual => ({
  ...(await importActual<typeof import('../../lib/analytics')>()),
  track: vi.fn(),
}))

async function tracked() {
  const { track } = await import('../../lib/analytics')
  return vi.mocked(track)
}

beforeEach(() => {
  vi.clearAllMocks()
  Reflect.deleteProperty(navigator, 'share')
})

describe('share link and text', () => {
  it('always points at the canonical site with ref=share', () => {
    expect(shareUrl('BRK.B')).toBe('https://intrinsica.io/t/BRK.B?ref=share')
    expect(shareText('NVDA')).toBe('NVDA on Intrinsica: quality business? Durable moat? Fair price?')
  })
})

describe('ShareButton', () => {
  it('opens the native share sheet when there is one', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    render(<ShareButton ticker="NVDA" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(share).toHaveBeenCalledWith({
      title: 'NVDA on Intrinsica', text: shareText('NVDA'), url: shareUrl('NVDA') })
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'native' })
  })

  it('stays quiet when the visitor cancels the share sheet', async () => {
    Object.defineProperty(navigator, 'share', {
      value: vi.fn().mockRejectedValue(new DOMException('cancel', 'AbortError')), configurable: true })
    render(<ShareButton ticker="NVDA" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(screen.queryByText('Link copied')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('copies the link on a desktop and says so', async () => {
    const user = userEvent.setup()
    const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(<ShareButton ticker="NVDA" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(write).toHaveBeenCalledWith(shareUrl('NVDA'))
    expect(await screen.findByText('Link copied')).toBeInTheDocument()
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'copy' })
  })

  it('shows the link to copy by hand when the clipboard refuses', async () => {
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    render(<ShareButton ticker="NVDA" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(await screen.findByDisplayValue(shareUrl('NVDA'))).toBeInTheDocument()
  })
})

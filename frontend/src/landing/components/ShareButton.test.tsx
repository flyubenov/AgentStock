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
  it('points the production build at the canonical site with ref=share', () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    expect(shareUrl('BRK.B')).toBe('https://intrinsica.io/t/BRK.B?ref=share')
    vi.unstubAllEnvs()
  })

  // User decision 2026-10-03: a link shared from a local or preview build must open
  // on that build, so the feature can be tried end to end before it is deployed.
  it('points any other build at the address it is running on', () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '')
    expect(shareUrl('JPM')).toBe(`${window.location.origin}/t/JPM?ref=share`)
    vi.unstubAllEnvs()
  })

  it('words the share text around the stock', () => {
    expect(shareText('NVDA')).toBe('NVDA on Intrinsica: quality business? Durable moat? Fair price?')
  })
})

describe('ShareButton', () => {
  // User decision 2026-10-03: share_clicked says which of the three spots was used.
  it('records where it was pressed', async () => {
    const user = userEvent.setup() // installs the clipboard jsdom lacks
    vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(<ShareButton ticker="AMD" place="breakdown" />)
    await user.click(screen.getByRole('button', { name: 'Share AMD' }))
    expect(await tracked()).toHaveBeenCalledWith('share_clicked',
      expect.objectContaining({ ticker: 'AMD', place: 'breakdown' }))
  })

  it('can carry a visible label, keeping the accessible name', () => {
    render(<ShareButton ticker="JPM" place="card" label="Share JPM" />)
    const button = screen.getByRole('button', { name: 'Share JPM' })
    expect(button).toHaveTextContent('Share JPM')
  })

  it('can be icon-only, keeping the accessible name', () => {
    render(<ShareButton ticker="MSFT" place="row" iconOnly />)
    const button = screen.getByRole('button', { name: 'Share MSFT' })
    expect(button.textContent).toBe('')
  })

  it('opens the native share sheet when there is one', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    render(<ShareButton ticker="NVDA" place="card" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(share).toHaveBeenCalledWith({
      title: 'NVDA on Intrinsica', text: shareText('NVDA'), url: shareUrl('NVDA') })
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'native', place: 'card' })
  })

  it('stays quiet when the visitor cancels the share sheet', async () => {
    Object.defineProperty(navigator, 'share', {
      value: vi.fn().mockRejectedValue(new DOMException('cancel', 'AbortError')), configurable: true })
    render(<ShareButton ticker="NVDA" place="card" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(screen.queryByText('Link copied')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('copies the link on a desktop and says so', async () => {
    const user = userEvent.setup()
    const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(<ShareButton ticker="NVDA" place="card" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(write).toHaveBeenCalledWith(shareUrl('NVDA'))
    expect(await screen.findByText('Link copied')).toBeInTheDocument()
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'copy', place: 'card' })
  })

  it('shows the link to copy by hand when the clipboard refuses', async () => {
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    render(<ShareButton ticker="NVDA" place="card" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(await screen.findByDisplayValue(shareUrl('NVDA'))).toBeInTheDocument()
  })
})

import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./landing/LandingPage', () => ({ default: () => <div>landing-page</div> }))
vi.mock('./landing/CheckoutPage', () => ({ default: () => <div>checkout-page</div> }))
vi.mock('./landing/PrivacyPage', () => ({ default: () => <div>privacy-page</div> }))
vi.mock('./pages/Home', () => ({ default: () => <div>home-page</div> }))
vi.mock('./pages/Database', () => ({ default: () => <div>database-page</div> }))
vi.mock('./pages/Progress', () => ({ default: () => <div>progress-page</div> }))
vi.mock('./pages/Results', () => ({ default: () => <div>results-page</div> }))
vi.mock('./pages/TickerDetail', () => ({ default: () => <div>ticker-page</div> }))
vi.mock('./components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

// App reads VITE_PUBLIC_MODE once at module load (so a production build can drop the
// analyst pages), so each case re-imports it after stubbing the env.
async function renderAt(path: string) {
  window.history.pushState({}, '', path)
  vi.resetModules()
  const { default: App } = await import('./App')
  render(<App />)
}

afterEach(() => {
  vi.unstubAllEnvs()
  window.history.pushState({}, '', '/')
})

describe('App routes in public mode (production)', () => {
  it.each(['/app', '/database', '/results/j1', '/progress/j1', '/ticker/j1/AAPL'])(
    'shows the landing page instead of the analyst page at %s', async (path) => {
      vi.stubEnv('VITE_PUBLIC_MODE', '1')
      await renderAt(path)
      expect(screen.getByText('landing-page')).toBeInTheDocument()
      expect(screen.queryByText(/^(home|database|progress|results|ticker)-page$/)).toBeNull()
    })

  it('shows the landing page for unknown paths such as future share links', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/t/AMZN')
    expect(screen.getByText('landing-page')).toBeInTheDocument()
  })

  it('serves the privacy notice', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/privacy')
    expect(screen.getByText('privacy-page')).toBeInTheDocument()
  })

  it('keeps the checkout page', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/checkout')
    expect(screen.getByText('checkout-page')).toBeInTheDocument()
  })
})

describe('App routes in local dev (flag unset)', () => {
  it('still serves the analyst app', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '')
    await renderAt('/database')
    expect(screen.getByText('database-page')).toBeInTheDocument()
    expect(screen.queryByText('landing-page')).toBeNull()
  })
})

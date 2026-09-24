import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from './LandingPage'
import Layout from '../components/Layout'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: { pageView: 'page_view' },
}))

function renderPage() {
  return render(<MemoryRouter><LandingPage /></MemoryRouter>)
}

describe('LandingPage shell', () => {
  it('links to every section from the nav', () => {
    renderPage()
    const hrefs = screen.getAllByRole('link').map(a => a.getAttribute('href'))
    for (const anchor of ['#analyze', '#how', '#why', '#workflow', '#pricing']) {
      expect(hrefs).toContain(anchor)
    }
  })

  it('scopes its own light theme instead of changing the global dark one', () => {
    const { container } = renderPage()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
  })

  it('leaves the global dark theme exactly as it found it', () => {
    const before = document.body.style.backgroundColor
    const { unmount, container } = renderPage()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
    unmount()
    expect(document.body.style.backgroundColor).toBe(before)
  })

  it('records a page view once', async () => {
    const { track } = await import('../lib/analytics')
    renderPage()
    expect(track).toHaveBeenCalledWith('page_view')
  })

  it('carries no card or payment input', () => {
    const { container } = renderPage()
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs.some(i => /card|cvc|cvv|payment|expiry/i.test(i.outerHTML))).toBe(false)
  })
})

describe('Layout nav (controller addition)', () => {
  it('points the Analyse link at /app, not /', () => {
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Layout><div /></Layout>
      </MemoryRouter>
    )
    const analyse = screen.getByRole('link', { name: 'Analyse' })
    expect(analyse.getAttribute('href')).toBe('/app')
  })

  it('highlights Analyse when on /app', () => {
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Layout><div /></Layout>
      </MemoryRouter>
    )
    const analyse = screen.getByRole('link', { name: 'Analyse' })
    expect(analyse.className).toContain('text-blue-400')
  })
})

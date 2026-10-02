import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PrivacyPage, { CONTACT_EMAIL } from './PrivacyPage'
import SiteFooter from './components/SiteFooter'

/** Launch checklist B4: the checkout collects an optional email and every visitor
 *  gets a browser ID, so the site needs a privacy notice linked from both. */
describe('PrivacyPage', () => {
  function show() {
    return render(<MemoryRouter><PrivacyPage /></MemoryRouter>)
  }

  it('names the controller and a contact address as a mail link', () => {
    show()
    expect(screen.getByRole('heading', { level: 1, name: /privacy/i })).toBeInTheDocument()
    expect(CONTACT_EMAIL).toBe('contact@intrinsica.io')
    const links = screen.getAllByRole('link', { name: CONTACT_EMAIL })
    expect(links[0]).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`)
  })

  it('discloses everything the site actually collects', () => {
    const { container } = show()
    const text = container.textContent ?? ''
    for (const item of [
      /visitor ID/i,          // analytics.ts, stored in the browser
      /optional email/i,      // checkout
      /tickers/i,             // analysis_started props
      /where you came from/i, // attribution (B1)
      /IP address/i,          // rate limiting and hosting logs
      /Google Fonts/i,        // theme.css loads fonts from Google
      /Google Sheets/i,       // the events sink
    ]) expect(text).toMatch(item)
  })

  it('tells the visitor how to exercise their rights', () => {
    const { container } = show()
    expect(container.textContent).toMatch(/delete/i)
    expect(container.textContent).toMatch(/complaint/i)
  })
})

describe('the privacy link', () => {
  it('is in the site footer', () => {
    render(<SiteFooter />)
    const footer = screen.getByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: /privacy/i })).toHaveAttribute('href', '/privacy')
  })
})

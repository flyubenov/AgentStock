import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Hero, { ASSESSMENTS } from './Hero'

const noop = () => {}

describe('Hero', () => {
  it('shows the four assessments with their questions', () => {
    render(<Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} />)
    expect(ASSESSMENTS.map(a => a.name)).toEqual(
      ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'])
    for (const a of ASSESSMENTS) {
      expect(screen.getByText(a.question)).toBeInTheDocument()
    }
  })

  it('selects that assessment when one is clicked', async () => {
    const onSelect = vi.fn()
    render(<Hero onAnalyze={noop} onSelectAssessment={onSelect} busy={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Moat/ }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('splits a comma-separated list, upper-cases it and drops blanks', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'nvda, amd ,, avgo')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD', 'AVGO'])
  })

  it('refuses a fourth ticker with a readable message and does not submit', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'A,B,C,D')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
    expect(screen.getByText('Up to 3 tickers per analysis run.')).toBeInTheDocument()
  })

  it('does not submit an empty field', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('never uses the word signal', () => {
    const { container } = render(
      <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} />)
    expect(container.textContent).not.toMatch(/signal/i)
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Hero, { ASSESSMENTS, COMPARE_TICKERS } from './Hero'

const noop = () => {}

describe('Hero', () => {
  it('shows the four assessments with their questions', () => {
    render(<Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={false} />)
    expect(ASSESSMENTS.map(a => a.name)).toEqual(
      ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'])
    for (const a of ASSESSMENTS) {
      expect(screen.getByText(a.question)).toBeInTheDocument()
    }
  })

  it('selects that assessment when one is clicked', async () => {
    const onSelect = vi.fn()
    render(<Hero onAnalyze={noop} onSelectAssessment={onSelect} busy={false} exhausted={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Moat/ }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('splits a comma-separated list, upper-cases it and drops blanks', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} exhausted={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'nvda, amd ,, avgo')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD', 'AVGO'], 'typed')
  })

  it('refuses a fourth ticker with a readable message and does not submit', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} exhausted={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'A,B,C,D')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
    expect(screen.getByText('Up to 3 tickers per analysis run.')).toBeInTheDocument()
  })

  it('does not submit an empty field', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} exhausted={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('never uses the word signal', () => {
    const { container } = render(
      <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={false} />)
    expect(container.textContent).not.toMatch(/signal/i)
  })

  describe('exhausted (demo limit reached)', () => {
    it('shows a wall instead of the input and button, linking to pricing', () => {
      render(<Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={true} />)
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Analyze/ })).not.toBeInTheDocument()
      const link = screen.getByRole('link', { name: /see the plans/i })
      expect(link.getAttribute('href')).toBe('#pricing')
    })

    it('never uses the word signal in the wall copy either', () => {
      const { container } = render(
        <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={true} />)
      expect(container.textContent).not.toMatch(/signal/i)
    })

    it('does not claim an account or invent urgency', () => {
      const { container } = render(
        <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={true} />)
      expect(container.textContent).not.toMatch(/account/i)
      expect(container.textContent).not.toMatch(/hurry|limited time|act now/i)
    })

    it('still renders the four assessment chips when exhausted', () => {
      render(<Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={true} />)
      for (const a of ASSESSMENTS) {
        expect(screen.getByText(a.question)).toBeInTheDocument()
      }
    })
  })

  // --- Controller Addition 2: the compare chip ---
  describe('compare chip', () => {
    it('fills the input with the fixed trio and analyzes it as a sample run', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} exhausted={false} />)
      await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
      expect(onAnalyze).toHaveBeenCalledWith(COMPARE_TICKERS, 'sample')
      expect(screen.getByRole('textbox')).toHaveValue(COMPARE_TICKERS.join(', '))
    })

    it('still renders and works when the typed allowance is exhausted', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} exhausted={true} />)
      // The wall is up — no textbox, no Analyze button — but the chip survives.
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
      const chip = screen.getByRole('button', { name: /Compare/ })
      await userEvent.click(chip)
      expect(onAnalyze).toHaveBeenCalledWith(COMPARE_TICKERS, 'sample')
    })

    it('does not use the internal word signal in the chip copy', () => {
      const { container } = render(
        <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} exhausted={false} />)
      expect(container.textContent).not.toMatch(/signal/i)
    })
  })
})

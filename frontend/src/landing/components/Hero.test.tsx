import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Hero, { COMPARE_TICKERS, MAX_TICKERS } from './Hero'

const noop = () => {}

describe('Hero', () => {
  it('splits a comma-separated list, upper-cases it and drops blanks', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} busy={false} exhausted={false} card={<div>CARD</div>} />)
    await userEvent.type(screen.getByRole('textbox'), 'nvda, amd ,, avgo')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD', 'AVGO'], 'typed')
  })

  it('refuses a fourth ticker with a readable message and does not submit', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} busy={false} exhausted={false} card={<div>CARD</div>} />)
    await userEvent.type(screen.getByRole('textbox'), 'A,B,C,D')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
    expect(screen.getByText('Up to 3 tickers per analysis run.')).toBeInTheDocument()
  })

  // Final review: the button is disabled while busy, but Enter reached submit() anyway.
  // A second run racing the first can land out of order and replace the visitor's
  // own result with the mount sample.
  it('does not start a second run from the Enter key while one is in flight', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} busy={true} exhausted={false} card={<div>CARD</div>} />)
    await userEvent.type(screen.getByRole('textbox'), 'NVDA{Enter}')
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('does not submit an empty field', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} busy={false} exhausted={false} card={<div>CARD</div>} />)
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('never uses the word signal', () => {
    const { container } = render(
      <Hero onAnalyze={noop} busy={false} exhausted={false} card={<div>CARD</div>} />)
    expect(container.textContent).not.toMatch(/signal/i)
  })

  describe('exhausted (demo limit reached)', () => {
    it('shows a wall instead of the input and button, linking to pricing', () => {
      render(<Hero onAnalyze={noop} busy={false} exhausted={true} card={<div>CARD</div>} />)
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Analyze/ })).not.toBeInTheDocument()
      const link = screen.getByRole('link', { name: /see the plans/i })
      expect(link.getAttribute('href')).toBe('#pricing')
    })

    it('never uses the word signal in the wall copy either', () => {
      const { container } = render(
        <Hero onAnalyze={noop} busy={false} exhausted={true} card={<div>CARD</div>} />)
      expect(container.textContent).not.toMatch(/signal/i)
    })

    it('does not claim an account or invent urgency', () => {
      const { container } = render(
        <Hero onAnalyze={noop} busy={false} exhausted={true} card={<div>CARD</div>} />)
      expect(container.textContent).not.toMatch(/account/i)
      expect(container.textContent).not.toMatch(/hurry|limited time|act now/i)
    })

  })

  // --- Controller Addition 2: the compare chip ---
  describe('compare chip', () => {
    it('fills the input with the fixed trio and analyzes it as a sample run', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} busy={false} exhausted={false} card={<div>CARD</div>} />)
      await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
      expect(onAnalyze).toHaveBeenCalledWith(COMPARE_TICKERS, 'sample')
      expect(screen.getByRole('textbox')).toHaveValue(COMPARE_TICKERS.join(', '))
    })

    it('still renders and works when the typed allowance is exhausted', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} busy={false} exhausted={true} card={<div>CARD</div>} />)
      // The wall is up — no textbox, no Analyze button — but the chip survives.
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
      const chip = screen.getByRole('button', { name: /Compare/ })
      await userEvent.click(chip)
      expect(onAnalyze).toHaveBeenCalledWith(COMPARE_TICKERS, 'sample')
    })

    // Fix round 1: the chip had no busy guard while its sibling Analyze button
    // did. Repeated clicks fire concurrent analyze() calls, each emitting its
    // own analysis_started{source:'sample'} — inflating exactly the metric the
    // chip exists to produce.
    it('is disabled while an analysis is already running', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} busy={true} exhausted={false} card={<div>CARD</div>} />)
      const chip = screen.getByRole('button', { name: /Compare/ })
      expect(chip).toBeDisabled()
      await userEvent.click(chip)
      expect(onAnalyze).not.toHaveBeenCalled()
    })

    // Loading variant E: the busy button spins and says how many tickers it is on.
    it('shows a spinner and the ticker count on the busy Analyze button', () => {
      const { container, rerender } = render(
        <Hero onAnalyze={noop} busy={true} busyCount={3} exhausted={false} card={<div>CARD</div>} />)
      expect(screen.getByRole('button', { name: 'Analyzing 3…' })).toBeDisabled()
      expect(container.querySelector('.an-btn .spin')).toHaveAttribute('aria-hidden', 'true')
      rerender(<Hero onAnalyze={noop} busy={true} busyCount={1} exhausted={false} card={<div>CARD</div>} />)
      expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeInTheDocument()
      rerender(<Hero onAnalyze={noop} busy={false} busyCount={0} exhausted={false} card={<div>CARD</div>} />)
      expect(container.querySelector('.an-btn .spin')).not.toBeInTheDocument()
    })

    it('is disabled while busy even behind the exhausted wall, where it is the only control', async () => {
      const onAnalyze = vi.fn()
      render(<Hero onAnalyze={onAnalyze} busy={true} exhausted={true} card={<div>CARD</div>} />)
      const chip = screen.getByRole('button', { name: /Compare/ })
      expect(chip).toBeDisabled()
      await userEvent.click(chip)
      expect(onAnalyze).not.toHaveBeenCalled()
    })

    it('does not use the internal word signal in the chip copy', () => {
      const { container } = render(
        <Hero onAnalyze={noop} busy={false} exhausted={false} card={<div>CARD</div>} />)
      expect(container.textContent).not.toMatch(/signal/i)
    })
  })

})

describe('Hero — promise and layout (hero rework 2026-09-27)', () => {
  const card = <div data-testid="card">CARD</div>
  it('leads with the promise headline and its subline', () => {
    render(<Hero onAnalyze={noop} busy={false} exhausted={false} card={card} />)
    expect(screen.getByRole('heading', { level: 1 }))
      .toHaveTextContent('Judge the business. Then judge the price.')
    expect(screen.getByText(/^Quality and Moat tell you how good the company is;/))
      .toHaveTextContent('Quality and Moat tell you how good the company is; Fair Value and Reward/Risk tell you whether the price makes sense. All from the fundamentals, all shown.')
  })
  it('no longer carries the wordmark heading, the pipeline strip or the assessment links', () => {
    const { container } = render(<Hero onAnalyze={noop} busy={false} exhausted={false} card={card} />)
    expect(screen.queryByText('Fundamental Stock Analysis')).not.toBeInTheDocument()
    expect(container.querySelector('.pipe, .assess4, .brand')).toBeNull()
    expect(screen.queryByRole('link', { name: /Moat/ })).not.toBeInTheDocument()
  })
  it('puts the input column first and the card beside it', () => {
    const { container } = render(<Hero onAnalyze={noop} busy={false} exhausted={false} card={card} />)
    const cols = container.querySelectorAll('.hero-in > div')
    expect(cols).toHaveLength(2)
    expect(cols[0]).toContainElement(screen.getByRole('textbox'))
    expect(cols[1]).toContainElement(screen.getByTestId('card'))
  })
  it('states the per-run cap and that no account is needed', () => {
    render(<Hero onAnalyze={noop} busy={false} exhausted={false} card={card} />)
    expect(screen.getByText(`Up to ${MAX_TICKERS} tickers at a time · no account needed`)).toBeInTheDocument()
  })
  it('drops the no-account line once the demo wall is up', () => {
    render(<Hero onAnalyze={noop} busy={false} exhausted card={card} />)
    expect(screen.queryByText(/no account needed/)).not.toBeInTheDocument()
  })
  it('shows a notice in the input column', () => {
    const { container } = render(
      <Hero onAnalyze={noop} busy={false} exhausted={false} notice="Not recognised: ZZZZ" card={card} />)
    expect(container.querySelector('.hero-l')).toHaveTextContent('Not recognised: ZZZZ')
  })
})

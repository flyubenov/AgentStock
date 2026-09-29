import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import QuestionBand from './QuestionBand'

describe('QuestionBand', () => {
  it('asks the investor’s question and says how Intrinsica answers it', () => {
    const { container } = render(<QuestionBand />)
    expect(screen.getByRole('heading', { name: 'Is it a good business, at a good price?' })).toBeInTheDocument()
    expect(container).toHaveTextContent(
      'Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show.')
    expect(container.querySelector('section')).toBeNull()
  })
})

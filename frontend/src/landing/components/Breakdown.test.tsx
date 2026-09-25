import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Breakdown from './Breakdown'
import { ASSESSMENTS } from './Hero'
import type { AssessmentId, QualityBlock, TickerPayload } from '../types'

// The fixtures below mirror what backend/landing/contract.py actually emits, not
// the engine's internal vocabulary. In particular `excluded_by` and the
// calibration chips arrive already mapped through landing/labels.py's
// EXCLUSION_LABELS ("Heavy-capex FCF exclusion" -> "Skipped during a heavy capex
// cycle"), so asserting on the raw internal key would test a string that can
// never reach this component.
const CAPEX_LABEL = 'Skipped during a heavy capex cycle'

function quality(over: Partial<QualityBlock> = {}): QualityBlock {
  return {
    score: 9.1,
    fundamentals_composite: 9.1,
    profile_label: 'Tech / Growth',
    categories: [{
      key: 'I', name: 'Growth & Margins', weight_pct: 35, score: 8,
      metrics: [
        // A deliberately untidy float: the backend does not round `raw`, so a
        // naive String(raw) would put 0.08123456789 on a page whose whole pitch
        // is that every number is checkable.
        { label: 'Revenue growth (3-yr)', raw: 0.08123456789, score: 6,
          weight_pct: 17.5, excluded: false, excluded_by: null },
        { label: 'FCF margin', raw: null, score: null, weight_pct: 0,
          excluded: true, excluded_by: CAPEX_LABEL },
      ],
    }],
    ...over,
  }
}

function payload(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
    quality: quality(),
    moat: {
      score: 90, gated: false, excluded: [],
      factors: [{ label: 'ROIC level', points: 18, max_points: 20, weight_pct: 20 }],
    },
    fair_value: {
      value: 211, gap_pct: -9.05, type_label: 'Mega Cap',
      methods: [{ label: 'Discounted cash flow', value: 205, weight_pct: 55,
                  contribution: 112.75 }],
    },
    reward_risk: {
      ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
      reward: [{ label: 'Discount to 52-week high', raw: 0.05, score: 2,
                 weight_pct: 24, dropped: false }],
      risk: [{ label: 'Volatility', raw: 0.3, score: 3, weight_pct: 22, dropped: false }],
    },
    calibrations: [CAPEX_LABEL], errors: [],
    ...over,
  }
}

const show = (p = payload(), tab: AssessmentId = 0) =>
  render(<Breakdown row={p} tab={tab} onTab={vi.fn()} />)

describe('Breakdown tabs', () => {
  it('offers a tab per assessment, labelled Reward / Risk', () => {
    show()
    for (const name of ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  // `AssessmentId` is a bare index shared with Hero's assessment cards, which
  // call onSelectAssessment(i). If the two label lists ever drift, clicking
  // "Moat" in the hero opens "Fair Value" here and nothing else would catch it.
  it('keeps its tab labels and order identical to the hero assessment cards', () => {
    const { container } = show()
    const labels = Array.from(container.querySelectorAll('.bd-tabs button'))
      .map(b => b.textContent)
    expect(labels).toEqual(ASSESSMENTS.map(a => a.name))
  })

  it('marks the open tab as pressed and the others as not', () => {
    show(payload(), 2)
    expect(screen.getByRole('button', { name: 'Fair Value' }))
      .toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Quality' }))
      .toHaveAttribute('aria-pressed', 'false')
  })

  it('asks for the requested tab by its assessment id', async () => {
    const onTab = vi.fn()
    render(<Breakdown row={payload()} tab={0} onTab={onTab} />)
    await userEvent.click(screen.getByRole('button', { name: 'Moat' }))
    expect(onTab).toHaveBeenCalledWith(1)
    await userEvent.click(screen.getByRole('button', { name: 'Reward / Risk' }))
    expect(onTab).toHaveBeenCalledWith(3)
  })

  // Anchored the same way as the leak test below (prelude to task 11): without a
  // positive assertion first, a component that rendered nothing at all would
  // satisfy the negative regex and this test would prove only that.
  it('never labels the ratio Risk/Reward, on any tab', () => {
    const anchors = ['Growth & Margins', 'ROIC level', 'Discounted cash flow', 'Volatility']
    for (const tab of [0, 1, 2, 3] as const) {
      const { container, unmount } = render(
        <Breakdown row={payload()} tab={tab} onTab={vi.fn()} />)
      expect(container.textContent).toContain(anchors[tab])
      expect(container.querySelector('table')).toBeInTheDocument()
      expect(container.textContent).not.toMatch(/Risk\s*\/\s*Reward/)
      unmount()
    }
  })
})

describe('Breakdown — Quality', () => {
  it('shows the four columns and the category weight', () => {
    show()
    for (const h of ['Factor', 'Data', 'Score', 'Weight']) {
      expect(screen.getByText(h)).toBeInTheDocument()
    }
    expect(screen.getByText(/Growth & Margins/)).toBeInTheDocument()
    expect(screen.getByText('35%')).toBeInTheDocument()
    expect(screen.getByText('17.5%')).toBeInTheDocument()
  })

  it('names the profile the company was scored against', () => {
    show()
    expect(screen.getByText(/Tech \/ Growth/)).toBeInTheDocument()
  })

  it('trims a raw figure instead of printing its floating-point tail', () => {
    show()
    expect(screen.getByText('0.08123')).toBeInTheDocument()
    expect(screen.queryByText('0.08123456789')).not.toBeInTheDocument()
  })

  it('strikes an excluded metric through at zero weight and names the calibration', () => {
    const { container } = show()
    const excluded = container.querySelector('.metric.excluded')
    expect(excluded).toHaveTextContent('FCF margin')
    expect(excluded).toHaveTextContent('0%')
    expect(excluded).toHaveTextContent(CAPEX_LABEL)
    // An excluded metric has no score at all — "— / 10" would read as a broken
    // scale rather than a metric that was deliberately not scored.
    expect(excluded).not.toHaveTextContent('/ 10')
  })
})

// CONTROLLER ADDITION: quality.score is the published headline and can
// legitimately diverge from what the categories roll up to. A headline that
// contradicts its own table is the worst thing this panel could do.
describe('Breakdown — Quality headline vs. its own categories', () => {
  const diverged = payload({
    quality: quality({ score: 6, fundamentals_composite: 8.4 }),
    calibrations: ['Pre-profit growth blend', 'Unprofitable cap'],
  })

  it('explains the gap when the published score is not what the categories roll up to', () => {
    show(diverged)
    const line = screen.getByText(/roll up to/i)
    expect(line).toHaveTextContent('8.4')
    expect(line).toHaveTextContent('6.0')
    expect(line).toHaveTextContent(/calibration/i)
  })

  it('says nothing when the headline and the categories agree', () => {
    show()
    expect(screen.queryByText(/roll up to/i)).not.toBeInTheDocument()
  })

  it('says nothing when the two agree to within rounding', () => {
    show(payload({ quality: quality({ score: 9.1, fundamentals_composite: 9.12 }) }))
    expect(screen.queryByText(/roll up to/i)).not.toBeInTheDocument()
  })

  it('says nothing when the engine never reached a composite', () => {
    show(payload({ quality: quality({ score: 6, fundamentals_composite: null }) }))
    expect(screen.queryByText(/roll up to/i)).not.toBeInTheDocument()
  })
})

describe('Breakdown — Moat', () => {
  it('shows moat factors as points over their max', () => {
    show(payload(), 1)
    expect(screen.getByText('18 / 20')).toBeInTheDocument()
    expect(screen.getByText('ROIC level')).toBeInTheDocument()
  })

  it('names the pillars left out of the score in readable words', () => {
    show(payload({
      moat: { score: 70, gated: false, excluded: ['Margin durability'],
              factors: [{ label: 'ROIC level', points: 18, max_points: 20, weight_pct: 20 }] },
    }), 1)
    expect(screen.getByText(/Margin durability/)).toBeInTheDocument()
  })

  it('reports the economic-profit gate only when it actually fired', () => {
    const gated = {
      score: 40, gated: true, excluded: [],
      factors: [{ label: 'ROIC level', points: 4, max_points: 20, weight_pct: 20 }],
    }
    const { unmount } = show(payload({ moat: gated }), 1)
    expect(screen.getByText(/gate/i)).toBeInTheDocument()
    unmount()

    show(payload(), 1)
    expect(screen.queryByText(/gate/i)).not.toBeInTheDocument()
  })
})

describe('Breakdown — Fair Value', () => {
  it('shows the blend as one exact number, not a range', () => {
    const { container } = show(payload(), 2)
    expect(screen.getByText('Discounted cash flow')).toBeInTheDocument()
    expect(screen.getByText('$211.00')).toBeInTheDocument()
    expect(screen.getByText('$205.00')).toBeInTheDocument()
    expect(screen.getByText('$112.75')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\$\d[\d.]*\s*[–-]\s*\$\d/)
  })

  it('names the valuation blend it was judged on', () => {
    show(payload(), 2)
    expect(screen.getByText(/Mega Cap/)).toBeInTheDocument()
  })
})

describe('Breakdown — Reward / Risk', () => {
  it('states the ratio direction and shows both axes', () => {
    show(payload(), 3)
    expect(screen.getByText(/Reward ÷ Risk/)).toHaveTextContent('higher is better')
    expect(screen.getByText(/Reward ÷ Risk/)).toHaveTextContent('Balanced')
    expect(screen.getByText('Discount to 52-week high')).toBeInTheDocument()
    expect(screen.getByText('Volatility')).toBeInTheDocument()
  })

  it('says outright that a high risk score is the bad direction', () => {
    const { container } = show(payload(), 3)
    const risk = container.querySelectorAll('.cat')[1]
    expect(risk).toHaveTextContent(/Risk/)
    expect(risk).toHaveTextContent(/high score here is the bad one/i)
  })

  it('drops a dropped factor to zero weight with no score', () => {
    const { container } = show(payload({
      reward_risk: {
        ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
        reward: [{ label: 'Analyst upside', raw: null, score: null,
                   weight_pct: 0, dropped: true }],
        risk: [{ label: 'Volatility', raw: 0.3, score: 3, weight_pct: 100, dropped: false }],
      },
    }), 3)
    const dropped = container.querySelector('.metric.excluded')!
    expect(dropped).toHaveTextContent('Analyst upside')
    expect(dropped).toHaveTextContent('0%')
    expect(dropped).not.toHaveTextContent('/ 5')
  })
})

describe('Breakdown — calibrations and absent assessments', () => {
  it('lists only the calibrations that fired', () => {
    const { container } = show(payload({
      calibrations: ['ROIC on tangible capital', 'Economic-profit gate'],
    }))
    const chips = Array.from(container.querySelectorAll('.cal')).map(c => c.textContent)
    expect(chips).toEqual(['ROIC on tangible capital', 'Economic-profit gate'])
  })

  it('renders no calibration strip at all when none fired', () => {
    const { container } = show(payload({ calibrations: [] }))
    expect(container.querySelector('.cals')).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/Calibrations/i)
  })

  it('renders a missing assessment as a note rather than an empty table', () => {
    const { container } = show(payload({ moat: null }), 1)
    expect(screen.getByText(/could not be computed/i)).toBeInTheDocument()
    expect(container.querySelector('table')).not.toBeInTheDocument()
  })

  it('has a note for every assessment, and never writes Risk/Reward in it', () => {
    const missing = payload({ quality: null, moat: null, fair_value: null, reward_risk: null })
    for (const tab of [0, 1, 2, 3] as const) {
      const { container, unmount } = render(
        <Breakdown row={missing} tab={tab} onTab={vi.fn()} />)
      expect(within(container).getByText(/could not be computed/i)).toBeInTheDocument()
      expect(container.querySelector('table')).not.toBeInTheDocument()
      unmount()
    }
  })

  it('shows an em dash rather than NaN, null or Infinity when every figure is absent', () => {
    const blank = payload({
      quality: quality({
        score: null, fundamentals_composite: null, profile_label: null,
        categories: [{
          key: 'II', name: 'Returns on Capital', weight_pct: 30, score: null,
          metrics: [{ label: 'ROIC (trailing)', raw: null, score: null, weight_pct: 0,
                      excluded: false, excluded_by: null }],
        }],
      }),
      moat: { score: null, gated: false, excluded: [],
              factors: [{ label: 'ROIC level', points: null, max_points: 20, weight_pct: 20 }] },
      fair_value: { value: null, gap_pct: null, type_label: null,
                    methods: [{ label: 'Discounted cash flow', value: null,
                                weight_pct: 0, contribution: null }] },
      reward_risk: { ratio: null, tier: null, reward_score: null, risk_score: null,
                     reward: [{ label: 'Valuation', raw: null, score: null,
                                weight_pct: 0, dropped: false }],
                     risk: [{ label: 'Beta', raw: null, score: null,
                              weight_pct: 0, dropped: false }] },
    })
    for (const tab of [0, 1, 2, 3] as const) {
      const { container, unmount } = render(
        <Breakdown row={blank} tab={tab} onTab={vi.fn()} />)
      expect(container.textContent).not.toMatch(/NaN|Infinity|null|undefined/)
      expect(container.textContent).toContain('—')
      unmount()
    }
  })

  // Spec section 8 rule 5. The anchors make this non-vacuous: an empty panel,
  // or one rendering the wrong assessment, fails before the regex is reached.
  it('renders real content on every tab and leaks no internal classifier code', () => {
    const anchors = ['Growth & Margins', 'ROIC level', 'Discounted cash flow', 'Volatility']
    for (const tab of [0, 1, 2, 3] as const) {
      const { container, unmount } = render(
        <Breakdown row={payload()} tab={tab} onTab={vi.fn()} />)
      expect(container.textContent).toContain(anchors[tab])
      expect(container.querySelector('table')).toBeInTheDocument()
      expect(container.textContent).not.toMatch(/[A-Z]{2,}_[A-Z]{2,}/)
      unmount()
    }
  })

  it('takes no card, payment or name input', () => {
    const { container } = show()
    expect(container.querySelector('input')).not.toBeInTheDocument()
    expect(container.querySelector('form')).not.toBeInTheDocument()
  })
})

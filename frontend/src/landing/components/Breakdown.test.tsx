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
        // `display` is the backend's formatted figure (landing/figures.py). The raw
        // float beside it is deliberately untidy, so a panel that printed `raw`
        // instead would put 8.123456789 on the page and fail below.
        { label: 'Revenue growth (3-yr)', raw: 8.123456789, display: '+8.1% / yr', score: 6,
          weight_pct: 17.5, excluded: false, excluded_by: null },
        { label: 'FCF margin', raw: 26.4, display: '26%', score: null, weight_pct: 0,
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
      factors: [{ label: 'ROIC level', group: 'Magnitude', display: '55%', points: 18,
                  max_points: 20, weight_pct: 20 }],
    },
    fair_value: {
      value: 211, gap_pct: -9.05, type_label: 'Mega Cap',
      methods: [{ label: 'Discounted cash flow', value: 205, weight_pct: 55,
                  contribution: 112.75 }],
    },
    reward_risk: {
      ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
      reward: [{ label: 'Discount to 52-week high', raw: 0.05, display: '5.0% below high',
                 score: 2, weight_pct: 24, dropped: false }],
      risk: [{ label: 'Volatility', raw: 0.3, display: '30% ann.', score: 3, weight_pct: 22,
               dropped: false }],
    },
    calibrations: [CAPEX_LABEL], errors: [],
    ...over,
  }
}

const show = (p = payload(), tab: AssessmentId = 0) =>
  render(<Breakdown row={p} tab={tab} onTab={vi.fn()} />)

// A tab's accessible name is its label followed by its headline value
// ("Quality9.1"), so tabs are found by the label they start with.
const tabNamed = (name: string) =>
  screen.getByRole('button', { name: new RegExp(`^${name.replace('/', '\\/')}`) })

describe('Breakdown tabs', () => {
  it('offers a tab per assessment, labelled Reward / Risk', () => {
    show()
    for (const name of ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']) {
      expect(tabNamed(name)).toBeInTheDocument()
    }
  })

  // `AssessmentId` is a bare index shared with the result card's tiles (Hero's
  // ASSESSMENTS order), which call onTile(ticker, i). If the two label lists drift, clicking
  // the "Moat" tile opens "Fair Value" here and nothing else would catch it.
  it('keeps its tab labels and order identical to the hero assessment cards', () => {
    const { container } = show()
    const labels = Array.from(container.querySelectorAll('.bd .tabs button'))
      .map(b => b.firstChild?.textContent)
    expect(labels).toEqual(ASSESSMENTS.map(a => a.name))
  })

  // The mock's slim tabs carry each assessment's headline, so the strip reads as a
  // summary before any tab is opened.
  it('carries each assessment headline in its tab', () => {
    const { container } = show()
    const values = Array.from(container.querySelectorAll('.bd .tabs button b'))
      .map(b => b.textContent)
    expect(values).toEqual(['9.1', '90', '$211', '0.9×'])
  })

  it('marks the open tab as pressed and the others as not', () => {
    show(payload(), 2)
    expect(tabNamed('Fair Value')).toHaveAttribute('aria-pressed', 'true')
    expect(tabNamed('Quality')).toHaveAttribute('aria-pressed', 'false')
  })

  it('asks for the requested tab by its assessment id', async () => {
    const onTab = vi.fn()
    render(<Breakdown row={payload()} tab={0} onTab={onTab} />)
    await userEvent.click(tabNamed('Moat'))
    expect(onTab).toHaveBeenCalledWith(1)
    await userEvent.click(tabNamed('Reward / Risk'))
    expect(onTab).toHaveBeenCalledWith(3)
  })

  // Anchored first: without a positive assertion, a component that rendered
  // nothing at all would satisfy the negative regex.
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
  it('shows the four columns, the category row and the total', () => {
    const { container } = show()
    for (const h of ['Factor', 'Data', 'Score', 'Weight']) {
      expect(screen.getByText(h)).toBeInTheDocument()
    }
    // The category row: its 0–10 score scaled to its weight (8/10 of 35 = 28.0).
    const sec = container.querySelector('tr.sec')!
    expect(sec).toHaveTextContent('1 · Growth & Margins')
    expect(sec).toHaveTextContent('28.0 / 35')
    expect(sec).toHaveTextContent('35%')
    expect(screen.getByText('17.5%')).toBeInTheDocument()
    // The total is the categories' own roll-up on the 100 scale.
    expect(container.querySelector('tr.tot')).toHaveTextContent('91.0 / 100')
  })

  it('names the profile and reads the score back onto its published band', () => {
    const { container } = show()
    expect(container.querySelector('.sum')).toHaveTextContent('Tech / Growth profile')
    expect(container.querySelector('.sum .pill')).toHaveTextContent('Top-decile')
  })

  it('prints the formatted figure with its unit, never the raw float', () => {
    const { container } = show()
    expect(screen.getByText('+8.1% / yr')).toBeInTheDocument()
    expect(container.textContent).not.toContain('8.123456789')
  })

  it('draws a strength bar sized to the score', () => {
    const { container } = show()
    const bar = container.querySelector('.sc .bar i') as HTMLElement
    expect(bar.style.width).toBe('60%')          // 6 / 10
  })

  it('strikes an excluded metric through at zero weight and names the calibration', () => {
    const { container } = show()
    const excluded = container.querySelector('tr.off')
    expect(excluded).toHaveTextContent('FCF margin')
    expect(excluded).toHaveTextContent('0%')
    expect(excluded).toHaveTextContent(CAPEX_LABEL)
    // Not shown as if it counted: no figure, and no "— / 10", which would read as
    // a broken scale rather than a metric that was deliberately not scored.
    expect(excluded).not.toHaveTextContent('26%')
    expect(excluded).not.toHaveTextContent('/10')
  })
})

// quality.score is the published headline and can legitimately diverge from what
// the categories roll up to. A headline that contradicts its own table is the
// worst thing this panel could do.
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
  it('shows moat factors as points over their max, with the figure behind them', () => {
    const { container } = show(payload(), 1)
    expect(screen.getByText('18/20')).toBeInTheDocument()
    expect(screen.getByText('55%')).toBeInTheDocument()
    // Grouped under its pillar, whose shaded row totals the group.
    const sec = container.querySelector('tr.sec')!
    expect(sec).toHaveTextContent('Magnitude')
    expect(sec).toHaveTextContent('18 / 20')
  })

  it('explains a factor in concept only, in a tooltip', () => {
    show(payload(), 1)
    const tip = screen.getByText(/Worth 20 of the 100 points/)
    expect(tip).toHaveAttribute('role', 'tooltip')
    // Concept, never a cut-off: no "x% earns y points" in the explanation.
    expect(tip.textContent).not.toMatch(/\d+\s*%/)
  })

  it('names the pillars left out of the score in readable words', () => {
    show(payload({
      moat: { score: 70, gated: false, excluded: ['Margin durability'],
              factors: [{ label: 'ROIC level', group: 'Magnitude', display: null, points: 18,
                          max_points: 20, weight_pct: 20 }] },
    }), 1)
    expect(screen.getByText(/re-weighted out: Margin durability/)).toBeInTheDocument()
  })

  it('says whether the economic-profit gate capped the score', () => {
    const gated = {
      score: 25, gated: true, excluded: [],
      factors: [{ label: 'ROIC level', group: 'Magnitude', display: null, points: 4,
                  max_points: 20, weight_pct: 20 }],
    }
    const { unmount } = show(payload({ moat: gated }), 1)
    expect(screen.getByText(/gate ✗ Moat capped/)).toBeInTheDocument()
    expect(screen.queryByText(/gate ✓ passed/)).not.toBeInTheDocument()
    unmount()

    show(payload(), 1)
    expect(screen.getByText(/gate ✓ passed/)).toBeInTheDocument()
    expect(screen.queryByText(/gate ✗/)).not.toBeInTheDocument()
  })
})

describe('Breakdown — Fair Value', () => {
  it('shows the blend as one exact number, not a range', () => {
    const { container } = show(payload(), 2)
    expect(screen.getByText('Discounted cash flow')).toBeInTheDocument()
    // The exact blend on the total row; the headline rounds it to whole dollars.
    expect(container.querySelector('tr.tot')).toHaveTextContent('$211.00')
    expect(container.querySelector('.sum .big')).toHaveTextContent('$211')
    expect(screen.getByText('$205.00')).toBeInTheDocument()
    expect(screen.getByText('$112.75')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\$\d[\d.]*\s*[–-]\s*\$\d/)
  })

  it('sets the blend against the live price', () => {
    const { container } = show(payload(), 2)
    const sum = container.querySelector('.sum')!
    expect(sum).toHaveTextContent('vs price $232.00')
    expect(within(sum as HTMLElement).getByText('−9%')).toHaveClass('gap-warn')
  })

  it('names the valuation blend it was judged on', () => {
    show(payload(), 2)
    expect(screen.getByText('Mega Cap valuation blend')).toBeInTheDocument()
  })
})

describe('Breakdown — Reward / Risk', () => {
  it('states the ratio direction and range, and shows both axes', () => {
    const { container } = show(payload(), 3)
    const sum = container.querySelector('.sum')!
    expect(sum).toHaveTextContent('0.9×')
    expect(sum).toHaveTextContent('Balanced')
    expect(sum).toHaveTextContent('Reward 2.8 ÷ Risk 3.1')
    expect(sum).toHaveTextContent('Range 0.2×–5.0× · above 1.0 = more reward than risk')
    expect(screen.getByText('Discount to 52-week high')).toBeInTheDocument()
    expect(screen.getByText('5.0% below high')).toBeInTheDocument()
    expect(screen.getByText('Volatility')).toBeInTheDocument()
  })

  it('says outright that a high risk score is the bad direction', () => {
    const { container } = show(payload(), 3)
    const axes = container.querySelectorAll('tr.sec')
    expect(axes[0]).toHaveTextContent('Reward axis · higher is better')
    expect(axes[1]).toHaveTextContent('Risk axis · higher = more risk')
  })

  it('lights the tier it landed on in the ladder, and only that one', () => {
    const { container } = show(payload(), 3)
    const steps = Array.from(container.querySelectorAll('.ladder .step'))
    expect(steps.map(s => s.textContent)).toEqual(
      ['Value Trap', 'Risk-Favored', 'Balanced', 'Reward-Favored', 'Asymmetric Upside'])
    expect(steps.filter(s => s.classList.contains('on')).map(s => s.textContent))
      .toEqual(['Balanced'])
  })

  it('drops a dropped factor to zero weight with no score', () => {
    const { container } = show(payload({
      reward_risk: {
        ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
        reward: [{ label: 'Analyst upside', raw: null, display: null, score: null,
                   weight_pct: 0, dropped: true }],
        risk: [{ label: 'Volatility', raw: 0.3, display: '30% ann.', score: 3, weight_pct: 100,
                 dropped: false }],
      },
    }), 3)
    const dropped = container.querySelector('tr.off')!
    expect(dropped).toHaveTextContent('Analyst upside')
    expect(dropped).toHaveTextContent('0%')
    expect(dropped).not.toHaveTextContent('/5')
  })
})

describe('Breakdown — calibrations and absent assessments', () => {
  it('lists only the calibrations that fired and touch the assessment on screen', () => {
    const fired = payload({ calibrations: ['ROIC on tangible capital', 'Economic-profit gate'] })
    const chipsOn = (tab: AssessmentId) => {
      const { container, unmount } = render(<Breakdown row={fired} tab={tab} onTab={vi.fn()} />)
      const chips = Array.from(container.querySelectorAll('.cal')).map(c => c.textContent)
      unmount()
      return chips
    }
    expect(chipsOn(0)).toEqual(['ROIC on tangible capital'])
    expect(chipsOn(1)).toEqual(['ROIC on tangible capital', 'Economic-profit gate'])
    expect(chipsOn(2)).toEqual([])
  })

  it('still shows a calibration it has no explanation for, on every tab', () => {
    const { container } = show(payload({ calibrations: ['Some future calibration'] }), 2)
    expect(container.querySelector('.cal')).toHaveTextContent('Some future calibration')
  })

  it('explains each fired calibration in a tooltip', () => {
    show(payload({ calibrations: ['Economic-profit gate'] }), 1)
    expect(screen.getByText(/no durable advantage without economic profit/))
      .toHaveAttribute('role', 'tooltip')
  })

  it('renders no calibration strip at all when none fired', () => {
    const { container } = show(payload({ calibrations: [] }))
    expect(container.querySelector('.applied')).not.toBeInTheDocument()
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
      expect(container.textContent).not.toMatch(/Risk\s*\/\s*Reward/)
      unmount()
    }
  })

  it('shows an em dash rather than NaN, null or Infinity when every figure is absent', () => {
    const blank = payload({
      quality: quality({
        score: null, fundamentals_composite: null, profile_label: null,
        categories: [{
          key: 'II', name: 'Returns on Capital', weight_pct: 30, score: null,
          metrics: [{ label: 'ROIC (trailing)', raw: null, display: null, score: null,
                      weight_pct: 0, excluded: false, excluded_by: null }],
        }],
      }),
      moat: { score: null, gated: false, excluded: [],
              factors: [{ label: 'ROIC level', group: 'Magnitude', display: null, points: null,
                          max_points: 20, weight_pct: 20 }] },
      fair_value: { value: null, gap_pct: null, type_label: null,
                    methods: [{ label: 'Discounted cash flow', value: null,
                                weight_pct: 0, contribution: null }] },
      reward_risk: { ratio: null, tier: null, reward_score: null, risk_score: null,
                     reward: [{ label: 'Valuation', raw: null, display: null, score: null,
                                weight_pct: 0, dropped: false }],
                     risk: [{ label: 'Beta', raw: null, display: null, score: null,
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

# Hero Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the landing page's centred hero and results grid with a two-column hero. The left column holds a promise headline and the analyzer; the right column holds a live result card. The card opens the breakdown under the hero on click. A question band and tab-pair labels are added to the Framework section.

**Architecture:**
- **New focused components under `frontend/src/landing/components/`:**
  - `ResultCard` (tiles view and comparison view);
  - `LiveRunBar` (moved out of `ResultGrid`);
  - `OpenBreakdown` (a header, a Close button, and the existing `Breakdown`);
  - `QuestionBand`.
- **`Hero` changes:** it becomes the left column and takes the card as a slot.
- **`LandingPage` changes:**
  - It owns an `openTicker` state beside the existing shared `assessment`.
  - It fires `breakdown_opened` only on a closed→open transition.
  - It keeps the previous card when a run yields no rows.
- **Deletions:** `ResultGrid.tsx` and its test go, along with the hero pipeline strip and the assessment links.

**Tech Stack:** React 19 + TypeScript + Vite, Vitest + React Testing Library + user-event. Plain CSS scoped under `.intrinsica` in `frontend/src/landing/theme.css`.

**Spec:** `docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md`. See the "REVISION 2026-09-27" banner, §5.1–§5.4, §9 and §11. Mock-ups are in `.superpowers/brainstorm/hero/` (git-ignored). `own-run-v2.html` is the desktop card and breakdown; `hero-phone-v2.html` is phone.

## Global Constraints

- Work on branch `01-fake-door-test`. Never merge or push. Never commit `backend/tests/__pycache__/*.pyc`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- All CSS is scoped under `.intrinsica`. Colours come from the existing tokens (`--q --mo --fv --rr --accent --pos --neg --warn --blue --mute --dim --border --border2 --bg --bg2 --bg3 --accent-soft`). This round adds no new palette.
- **Copy rules (spec §8):**
  - never "signal";
  - never "Risk/Reward" (the ratio is "Reward / Risk");
  - no raw `ALL_CAPS_IDS` in copy;
  - no fair-value range;
  - no card or payment fields;
  - no published scoring cut-offs.
  `copy-guard.test.ts` enforces these.
- **Analytics (spec §9):** the closed list stays at 12 events. No new event names and no new props.
  - `breakdown_opened` = `{ ticker, assessment }`, where `assessment` is the tab's human name (`FRAMEWORK[i].name`).
  - Never call `track` inside a state updater: `main.tsx` runs under StrictMode.
- **Hero copy, verbatim:**
  - Headline: `Judge the business.` / `Then judge the price.` (two lines).
  - Subline: `Quality and Moat tell you how good the company is; Fair Value and Reward/Risk tell you whether the price makes sense. All from the fundamentals, all shown.`
  - Micro-line: `Up to 3 tickers at a time · no account needed` (3 = `MAX_TICKERS`).
- **Question band copy, verbatim:**
  - Heading: `Is it a good business, at a good price?`
  - Line: `Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show.`
- **Tab-pair labels, verbatim:** `Is it a good business?` over Quality and Moat; `At a good price?` over Fair Value and Reward / Risk.
- **Card pill:** `Live example · computed just now` when the rows came from `source === 'sample'`; `Your analysis` when they came from `'typed'`.
- **Fair Value caption:**
  - `Fair value N% below price` / `Fair value N% above price`, where N = |round(gap_pct)|;
  - `Fair value at price` when it rounds to 0;
  - coloured by `gapClass`.
- **Tier captions** come only from `qualityTier`, `moatTier` (`landing/format.ts`) and `reward_risk.tier`.
- **Typecheck with `npx tsc -b --force`** from `frontend/`. `tsc --noEmit` is a no-op in this repo.
- **Commands** run from `frontend/`: `npx vitest run <path>` for one file, `npx vitest run` for the suite, `npx eslint src` for lint. The lint baseline is 6 problems; do not add any.

## Review Focus

1. **Page load before the sample returns, and when the sample fails.** The card must show a frame with "Running the analysis…", then (on failure) "The live example could not be loaded. Try a ticker on the left.". It must never show an empty hole or placeholder numbers. Tested in Task 3 (component) and Task 6 (page).
2. **A run that yields no rows after a good one** (all invalid, server error, network failure) must leave the previous card and its open breakdown intact, and show the notice. Tested in Task 6.
3. **A ticker whose engines partly failed** (`quality: null`, `fair_value: null`, etc.) must render "—" with "Could not be computed" in that tile or cell. It must not throw, and clicking the tile must still open the breakdown (which shows its own "could not be computed" panel). Tested in Task 3.
4. **Toggle semantics under StrictMode.**
   - A tile click on the ticker already open, but on a different tab, switches the tab and fires nothing.
   - The same tile again folds it.
   - A row click folds or opens it.
   - Exactly one `breakdown_opened` per closed→open transition.
   Tested in Task 6.
5. **A new run while a breakdown is open** closes the breakdown when the new rows land (their tickers may differ). Tested in Task 6.

---

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/landing/format.ts` (modify) | + `fvCaption(gap)` |
| `frontend/src/landing/components/LiveRunBar.tsx` (create) | the in-flight "Computing in parallel" strip, moved verbatim from `ResultGrid.tsx` |
| `frontend/src/landing/components/ResultCard.tsx` (create) | the hero's right column: empty / tiles / comparison views, pill, star, loading dim, best-in-column |
| `frontend/src/landing/components/OpenBreakdown.tsx` (create) | the full-width dock under the hero: header, Close, scroll-into-view if off screen, wraps the unchanged `Breakdown` |
| `frontend/src/landing/components/QuestionBand.tsx` (create) | the band before the Framework |
| `frontend/src/landing/content/framework.ts` (modify) | − `PIPELINE`; + `QUESTION_BAND`, `TAB_PAIRS` |
| `frontend/src/landing/components/Framework.tsx` (modify) | tabs split into two labelled pairs |
| `frontend/src/landing/components/Hero.tsx` (modify) | two-column hero; left column content; `card` slot; `notice`; − pipeline, − assessment links, − `onSelectAssessment` |
| `frontend/src/landing/LandingPage.tsx` (modify) | wiring: `openTicker`, `rowsSource`, keep-previous-rows, open handlers, dock, band |
| `frontend/src/landing/components/ResultGrid.tsx` + `.test.tsx` (delete) | replaced by the card |
| `frontend/src/landing/theme.css` (modify) | new hero, card, dock, band and pair styles; remove dead hero and grid rules |
| tests | `format.test.ts`, `LiveRunBar.test.tsx` (new), `ResultCard.test.tsx` (new), `OpenBreakdown.test.tsx` (new), `QuestionBand.test.tsx` (new), `Framework.test.tsx`, `Hero.test.tsx`, `LandingPage.test.tsx`, `copy-guard.test.ts` |

---

### Task 1: `fvCaption` helper

**Files:**
- Modify: `frontend/src/landing/format.ts` (append after `gapPct`)
- Test: `frontend/src/landing/format.test.ts`

**Interfaces:**
- Produces: `export function fvCaption(v: number | null): string`

- [ ] **Step 1: Write the failing test.** Append to `format.test.ts`, and add `fvCaption` to that file's existing import from `./format`:

```ts
describe('fvCaption', () => {
  // gap_pct is (fair value - price) / price, so it is measured against the PRICE.
  it('says how far fair value sits from the price, measured against the price', () => {
    expect(fvCaption(-53.43)).toBe('Fair value 53% below price')
    expect(fvCaption(12.4)).toBe('Fair value 12% above price')
  })
  it('says "at price" when the gap rounds to zero, never "0% above"', () => {
    expect(fvCaption(0.4)).toBe('Fair value at price')
    expect(fvCaption(-0.4)).toBe('Fair value at price')
  })
  it('falls back to the em dash for a missing or broken gap', () => {
    expect(fvCaption(null)).toBe('—')
    expect(fvCaption(Number.NaN)).toBe('—')
  })
})
```

- [ ] **Step 2: Run it and confirm it fails.** `npx vitest run src/landing/format.test.ts`. Expected: FAIL, `fvCaption` is not exported.

- [ ] **Step 3: Implement.** Append to `format.ts` after `gapPct`:

```ts
/** The result card's Fair Value caption (spec 5.2). `gap_pct` is measured against the
 *  price, so the sentence is about where fair value sits relative to the price —
 *  "Price 53% above fair value" would silently change the base of the percentage. */
export function fvCaption(v: number | null): string {
  if (!finite(v)) return DASH
  const r = Math.round(v)
  if (r === 0) return 'Fair value at price'
  return `Fair value ${Math.abs(r)}% ${r > 0 ? 'above' : 'below'} price`
}
```

- [ ] **Step 4: Run it and confirm it passes.** `npx vitest run src/landing/format.test.ts`. Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/landing/format.ts frontend/src/landing/format.test.ts
git commit -m "feat(landing): fvCaption — the card's Fair Value sentence

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Move `LiveRunBar` into its own file

**Files:**
- Create: `frontend/src/landing/components/LiveRunBar.tsx`
- Create: `frontend/src/landing/components/LiveRunBar.test.tsx`
- Modify: `frontend/src/landing/components/ResultGrid.tsx`. It imports the bar instead of defining it, so `RunBar` keeps working until Task 6 deletes the file.

**Interfaces:**
- Produces: `export default function LiveRunBar({ tickers }: { tickers: string[] })`. Renders `role="status"` with text `Computing in parallel:`, each ticker, and `N tickers · X.Xs`.

- [ ] **Step 1: Write the failing test.** Create `LiveRunBar.test.tsx`:

```tsx
import { afterEach, describe, it, expect, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import LiveRunBar from './LiveRunBar'

describe('LiveRunBar', () => {
  afterEach(() => { vi.useRealTimers() })

  it('says it is computing, names every pending ticker and counts the time up', async () => {
    vi.useFakeTimers()
    render(<LiveRunBar tickers={['AAPL', 'MSFT', 'NVDA']} />)
    const bar = screen.getByRole('status')
    expect(bar).toHaveTextContent(/Computing in parallel:.*AAPL.*MSFT.*NVDA/)
    expect(bar).toHaveTextContent('3 tickers · 0.0s')
    await act(async () => { vi.advanceTimersByTime(1200) })
    expect(bar).toHaveTextContent(/3 tickers · 1\.[12]s/)
  })

  it('keeps the sweeping bars out of the accessibility tree', () => {
    const { container } = render(<LiveRunBar tickers={['AAPL', 'MSFT']} />)
    const bars = container.querySelectorAll('.mini.ind')
    expect(bars).toHaveLength(2)
    for (const b of bars) expect(b).toHaveAttribute('aria-hidden', 'true')
  })
})
```

- [ ] **Step 2: Run it and confirm it fails.** `npx vitest run src/landing/components/LiveRunBar.test.tsx`. Expected: FAIL, the module is not found.

- [ ] **Step 3: Implement.** Create `LiveRunBar.tsx`. The function body is moved verbatim from `ResultGrid.tsx`, lines 139–162:

```tsx
import { useEffect, useState } from 'react'

/** While a multi-ticker run is in flight the strip says so at once — every
 *  ticker's bar sweeps and the clock counts up (loading variant E, user decision
 *  2026-09-26). Since the 2026-09-27 hero rework it sits at the top of the result
 *  card. The backend answers all tickers in one response, so no ticker is ever
 *  shown as done before the others: the strip claims only what the page knows. */
export default function LiveRunBar({ tickers }: { tickers: string[] }) {
  const [ms, setMs] = useState(0)
  useEffect(() => {
    const t0 = Date.now()
    const id = setInterval(() => setMs(Date.now() - t0), 100)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="runbar live" role="status">
      <span className="rp wait">Computing in parallel:</span>
      {tickers.map(t => (
        <span key={t} className="rp">
          {t} <span className="mini ind" aria-hidden="true"><span /></span>
        </span>
      ))}
      <span className="rp total">{tickers.length} tickers · {(ms / 1000).toFixed(1)}s</span>
    </div>
  )
}
```

In `ResultGrid.tsx`:
- delete the local `LiveRunBar` function and its doc comment (lines 139–162);
- change line 1 to `import { Fragment, type ReactNode } from 'react'`;
- add `import LiveRunBar from './LiveRunBar'`.

- [ ] **Step 4: Run both test files and confirm they pass.** `npx vitest run src/landing/components/LiveRunBar.test.tsx src/landing/components/ResultGrid.test.tsx`. Expected: PASS.

- [ ] **Step 4b: Keep the copy guard's file census true.** `copy-guard.test.ts` pins the number of landing source files. Change `expect(sources.length).toBe(18)` to `toBe(19)`, and add `'./components/LiveRunBar.tsx',` to the named list in `'covers every surface that renders copy…'`. Run `npx vitest run src/landing/copy-guard.test.ts`. Expected: PASS, and the new file's copy passes every banned-vocabulary check.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/landing/copy-guard.test.ts frontend/src/landing/components/LiveRunBar.tsx frontend/src/landing/components/LiveRunBar.test.tsx frontend/src/landing/components/ResultGrid.tsx
git commit -m "refactor(landing): LiveRunBar in its own file, ready for the result card

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `ResultCard`

**Files:**
- Create: `frontend/src/landing/components/ResultCard.tsx`
- Create: `frontend/src/landing/components/ResultCard.test.tsx`
- Modify: `frontend/src/landing/theme.css`. Append the "result card" block from Step 3b.

**Interfaces:**
- Consumes:
  - `LiveRunBar` (Task 2);
  - `fvCaption`, `gapClass`, `gapPct`, `dollars`, `money`, `num`, `qualityTier`, `moatTier`, `DASH` from `../format`;
  - `ASSESSMENTS` from `./Hero`, i.e. `{ name, color, question }[]` in Quality, Moat, Fair Value, Reward / Risk order;
  - `TickerPayload`, `AnalyzeSource`, `AssessmentId` from `../types`.
- Produces:

```ts
export interface OpenState { ticker: string; tab: AssessmentId }
export interface ResultCardProps {
  rows: TickerPayload[]
  source: AnalyzeSource | null      // source of the run that produced `rows`
  pending: string[]                 // tickers of the run in flight ([] when idle)
  busy: boolean
  ms: number | null                 // duration of the run that produced `rows`
  open: OpenState | null            // what the breakdown dock is showing, if anything
  onTile: (ticker: string, tab: AssessmentId) => void
  onRow: (ticker: string) => void
  onWatch: (ticker: string) => void
}
export default function ResultCard(props: ResultCardProps): JSX.Element
```

**DOM contract that later tasks' tests rely on:**
- The root is `div.rc`.
- The tiles view has four `button.rc-tile` elements (`aria-pressed`) in assessment order. Each accessible name starts with the assessment name.
- The comparison view has one `div.rc-row` per ticker, each with a `button.rc-open` (accessible name = ticker, `aria-expanded`).
- The best cells carry `.best`.
- The star is `button.watch` with `aria-label="Add {T} to a watchlist"`.
- While busy, the body is wrapped in `.stale` with `aria-busy="true"`.

- [ ] **Step 1: Write the failing tests.** Create `ResultCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultCard, { type ResultCardProps } from './ResultCard'
import type { TickerPayload } from '../types'

function row(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 341.07,
    quality: { score: 7.8, fundamentals_composite: 7.84, profile_label: 'Tech / Growth', categories: [] },
    moat: { score: 95, gated: false, excluded: [], factors: [] },
    fair_value: { value: 158.83, gap_pct: -53.43, type_label: 'Mega Cap', methods: [] },
    reward_risk: { ratio: 1.06, tier: 'Balanced', reward_score: 2.13, risk_score: 2.01, reward: [], risk: [] },
    calibrations: [], errors: [],
    ...over,
  }
}

function show(over: Partial<ResultCardProps> = {}) {
  const props: ResultCardProps = {
    rows: [row()], source: 'sample', pending: [], busy: false, ms: null, open: null,
    onTile: vi.fn(), onRow: vi.fn(), onWatch: vi.fn(), ...over,
  }
  return { ...render(<ResultCard {...props} />), props }
}

describe('ResultCard — before any result', () => {
  it('shows a frame, not a hole, while the first run is in flight', () => {
    const { container } = show({ rows: [], busy: true, pending: ['AAPL'] })
    expect(container.querySelector('.rc')).toHaveTextContent('Running the analysis…')
    expect(container.querySelector('.rc')).not.toHaveTextContent(/\d/)
  })
  it('says the live example could not be loaded when there is nothing to show', () => {
    const { container } = show({ rows: [], busy: false })
    expect(container.querySelector('.rc'))
      .toHaveTextContent('The live example could not be loaded. Try a ticker on the left.')
  })
})

describe('ResultCard — tiles view (one ticker)', () => {
  it('shows the four scores in assessment order with units and tier captions', () => {
    show()
    const tiles = screen.getAllByRole('button', { name: /^(Quality|Moat|Fair Value|Reward \/ Risk)/ })
    expect(tiles.map(t => t.textContent)).toEqual([
      expect.stringMatching(/^Quality.*7\.8.*\/10.*Strong/),
      expect.stringMatching(/^Moat.*95.*\/100.*Wide/),
      expect.stringMatching(/^Fair Value.*\$159.*Fair value 53% below price/),
      expect.stringMatching(/^Reward \/ Risk.*1\.1.*×.*Balanced/),
    ])
  })
  it('colours the Fair Value caption with the % vs price band', () => {
    show()
    expect(screen.getByText('Fair value 53% below price')).toHaveClass('gap-neg')
  })
  it('labels a sample run as the live example and a typed run as the visitor’s own', () => {
    const { unmount } = show({ source: 'sample' })
    expect(screen.getByText(/Live example · computed just now/)).toBeInTheDocument()
    unmount()
    show({ source: 'typed' })
    expect(screen.getByText('Your analysis')).toBeInTheDocument()
    expect(screen.queryByText(/Live example/)).not.toBeInTheDocument()
  })
  it('shows ticker, company, price and profile in the header', () => {
    const { container } = show()
    const head = container.querySelector('.rc-head')!
    expect(head).toHaveTextContent('AAPL')
    expect(head).toHaveTextContent('Apple Inc.')
    expect(head).toHaveTextContent('$341.07 · Tech / Growth profile')
  })
  it('asks for the breakdown of the clicked score, by ticker and tab', async () => {
    const { props } = show()
    await userEvent.click(screen.getByRole('button', { name: /^Moat/ }))
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 1)
    await userEvent.click(screen.getByRole('button', { name: /^Reward \/ Risk/ }))
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 3)
  })
  it('marks only the tile whose breakdown is open as pressed', () => {
    show({ open: { ticker: 'AAPL', tab: 2 } })
    const pressed = screen.getAllByRole('button', { name: /^(Quality|Moat|Fair Value|Reward \/ Risk)/ })
      .map(t => t.getAttribute('aria-pressed'))
    expect(pressed).toEqual(['false', 'false', 'true', 'false'])
  })
  it('renders a failed assessment as a dash that can still be clicked', async () => {
    const { props } = show({ rows: [row({ quality: null, fair_value: null })] })
    const q = screen.getByRole('button', { name: /^Quality/ })
    expect(q).toHaveTextContent('—')
    expect(q).toHaveTextContent('Could not be computed')
    expect(screen.getByRole('button', { name: /^Fair Value/ })).toHaveTextContent('Could not be computed')
    await userEvent.click(q)
    expect(props.onTile).toHaveBeenCalledWith('AAPL', 0)
  })
  it('offers the watchlist star without opening anything', async () => {
    const { props } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Add AAPL to a watchlist' }))
    expect(props.onWatch).toHaveBeenCalledWith('AAPL')
    expect(props.onTile).not.toHaveBeenCalled()
  })
  it('never says Risk/Reward or signal', () => {
    const { container } = show()
    expect(container.textContent).not.toMatch(/Risk\s*\/\s*Reward|signal/i)
  })
})

const trio = () => [
  row({ ticker: 'NVDA', company_name: 'NVIDIA Corporation', price: 225.07,
        quality: { score: 9.2, fundamentals_composite: 9.2, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 69.8, gated: false, excluded: [], factors: [] },
        fair_value: { value: 172.62, gap_pct: -23.31, type_label: null, methods: [] },
        reward_risk: { ratio: 1.85, tier: 'Reward-Favored', reward_score: 3.7, risk_score: 2, reward: [], risk: [] } }),
  row({ ticker: 'AMD', company_name: 'Advanced Micro Devices, Inc.', price: 630.63,
        quality: { score: 7.2, fundamentals_composite: 7.2, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 25, gated: false, excluded: [], factors: [] },
        fair_value: { value: 308.92, gap_pct: -51.01, type_label: null, methods: [] },
        reward_risk: { ratio: 1.08, tier: 'Balanced', reward_score: 2.7, risk_score: 2.5, reward: [], risk: [] } }),
  row({ ticker: 'AVGO', company_name: 'Broadcom Inc.', price: 352.81,
        quality: { score: 8.8, fundamentals_composite: 8.8, profile_label: 'Tech / Growth', categories: [] },
        moat: { score: 86.5, gated: false, excluded: [], factors: [] },
        fair_value: { value: 216.1, gap_pct: -38.75, type_label: null, methods: [] },
        reward_risk: { ratio: 1.88, tier: 'Reward-Favored', reward_score: 3.8, risk_score: 2, reward: [], risk: [] } }),
]

describe('ResultCard — comparison view (two or three tickers)', () => {
  it('shows one row per ticker with its scores and tier captions', () => {
    const { container } = show({ rows: trio(), source: 'typed' })
    expect(container.querySelector('.rc-head')).toHaveTextContent('Comparing 3')
    const rows = container.querySelectorAll('.rc-row')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent(/NVDA.*9\.2.*Top-decile.*70.*Established.*\$173.*−23%.*1\.9×.*Reward-Favored/)
    expect(rows[1]).toHaveTextContent(/AMD.*Little or none/)
  })
  it('highlights the best value per column, and only there', () => {
    const { container } = show({ rows: trio() })
    const cellsOf = (t: string) => within(screen.getByRole('button', { name: t }).closest('.rc-row') as HTMLElement)
    expect(cellsOf('NVDA').getByText('9.2').closest('.rc-cell')).toHaveClass('best')   // quality
    expect(cellsOf('AVGO').getByText('87').closest('.rc-cell')).toHaveClass('best')    // moat
    expect(cellsOf('NVDA').getByText('−23%').closest('.rc-cell')).toHaveClass('best')  // gap: -23 is highest
    expect(cellsOf('AVGO').getByText('1.9×').closest('.rc-cell')).toHaveClass('best')  // 1.88 > 1.85
    expect(container.querySelectorAll('.rc-cell.best')).toHaveLength(4)
  })
  it('asks for a ticker’s breakdown from its row button and from anywhere in the row', async () => {
    const { container, props } = show({ rows: trio() })
    await userEvent.click(screen.getByRole('button', { name: 'AMD' }))
    expect(props.onRow).toHaveBeenCalledTimes(1)
    expect(props.onRow).toHaveBeenLastCalledWith('AMD')
    await userEvent.click(container.querySelectorAll('.rc-row')[2].querySelector('.rc-cell')!)
    expect(props.onRow).toHaveBeenLastCalledWith('AVGO')
    expect(props.onRow).toHaveBeenCalledTimes(2)
  })
  it('reports which row is open on its button', () => {
    show({ rows: trio(), open: { ticker: 'AVGO', tab: 0 } })
    expect(screen.getByRole('button', { name: 'AVGO' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'NVDA' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('stars a ticker without opening its row', async () => {
    const { props } = show({ rows: trio() })
    await userEvent.click(screen.getByRole('button', { name: 'Add AMD to a watchlist' }))
    expect(props.onWatch).toHaveBeenCalledWith('AMD')
    expect(props.onRow).not.toHaveBeenCalled()
  })
  it('carries the run summary in the header once the run is done', () => {
    const { container } = show({ rows: trio(), ms: 2100 })
    expect(container.querySelector('.rc-head')).toHaveTextContent('3 tickers · 2.1 s')
  })
  it('shows a failed cell as a dash', () => {
    const rows = trio(); rows[1] = { ...rows[1], moat: null }
    show({ rows })
    const amd = screen.getByRole('button', { name: 'AMD' }).closest('.rc-row') as HTMLElement
    expect(within(amd).getAllByText('—').length).toBeGreaterThan(0)
  })
})

describe('ResultCard — while a run is in flight', () => {
  it('shows the live strip for several tickers and dims the previous result', () => {
    const { container } = show({ busy: true, pending: ['NVDA', 'AMD', 'AVGO'] })
    expect(screen.getByRole('status')).toHaveTextContent(/Computing in parallel:.*NVDA.*AMD.*AVGO/)
    const body = container.querySelector('.stale')!
    expect(body).toHaveAttribute('aria-busy', 'true')
    expect(body).toHaveTextContent('AAPL')
  })
  it('dims without a strip for a single pending ticker — the button covers that', () => {
    const { container } = show({ busy: true, pending: ['NVDA'] })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(container.querySelector('.stale')).not.toBeNull()
  })
  it('hides the run summary while a new run is in flight', () => {
    const { container } = show({ rows: trio(), ms: 2100, busy: true, pending: ['AAPL', 'MSFT'] })
    expect(container.querySelector('.rc-head')).not.toHaveTextContent('2.1 s')
  })
})
```

- [ ] **Step 2: Run them and confirm they fail.** `npx vitest run src/landing/components/ResultCard.test.tsx`. Expected: FAIL, the module is not found.

- [ ] **Step 3a: Implement the component.** Create `ResultCard.tsx`:

```tsx
import type { ReactNode } from 'react'
import type { AnalyzeSource, AssessmentId, TickerPayload } from '../types'
import {
  DASH, dollars, fvCaption, gapClass, gapPct, money, moatTier, num, qualityTier,
} from '../format'
import { ASSESSMENTS } from './Hero'
import LiveRunBar from './LiveRunBar'

export interface OpenState { ticker: string; tab: AssessmentId }

export interface ResultCardProps {
  rows: TickerPayload[]
  source: AnalyzeSource | null
  pending: string[]
  busy: boolean
  ms: number | null
  open: OpenState | null
  onTile: (ticker: string, tab: AssessmentId) => void
  onRow: (ticker: string) => void
  onWatch: (ticker: string) => void
}

const FAILED = 'Could not be computed'

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

/** Share of a bar, clamped to 2–100% so a real zero still shows a sliver. */
function share(v: number | null, max: number): string {
  return finite(v) ? `${Math.max(2, Math.min(100, (v / max) * 100))}%` : '0%'
}

/** The highest finite value across a column, or null when there is nothing to
 *  single out (fewer than two DISTINCT finite values). Carried over from the grid
 *  (spec 5.2: best-in-column, comparison view only). */
function bestOf(values: (number | null)[]): number | null {
  const f = values.filter(finite)
  if (new Set(f).size < 2) return null
  return Math.max(...f)
}

function Star({ ticker, onWatch }: { ticker: string; onWatch: (t: string) => void }) {
  return (
    <button type="button" className="watch" aria-label={`Add ${ticker} to a watchlist`}
            title="Add to watchlist"
            onClick={e => { e.stopPropagation(); onWatch(ticker) }}>☆</button>
  )
}

function Pill({ source }: { source: AnalyzeSource | null }) {
  return source === 'typed'
    ? <span className="rc-pill yours">Your analysis</span>
    : <span className="rc-pill live"><i aria-hidden="true" />Live example · computed just now</span>
}

/** Two bars on one scale: fair value vs price, or reward vs risk. */
function Pair({ a, b }: { a: [string, number | null, string, string]; b: [string, number | null, string, string] }) {
  const max = Math.max(finite(a[1]) ? a[1] : 0, finite(b[1]) ? b[1] : 0) * 1.08 || 1
  return (
    <span className="rc-pair" aria-hidden="true">
      {[a, b].map(([label, v, text, color]) => (
        <span key={label} className="r">
          <span>{label}</span>
          <span className="t"><b style={{ width: share(v, max), background: color }} /></span>
          <em>{text}</em>
        </span>
      ))}
    </span>
  )
}

function Gauge({ v, max, color }: { v: number | null; max: number; color: string }) {
  return <span className="rc-g" aria-hidden="true"><b style={{ width: share(v, max), background: color }} /></span>
}

function Tile({ i, on, onClick, value, unit, visual, caption, captionClass }: {
  i: AssessmentId; on: boolean; onClick: () => void
  value: string; unit?: string; visual: ReactNode; caption: string; captionClass?: string
}) {
  const a = ASSESSMENTS[i]
  const failed = value === DASH
  return (
    <button type="button" className={on ? 'rc-tile on' : 'rc-tile'} aria-pressed={on} onClick={onClick}>
      <span className="n"><span className="dot" style={{ background: a.color }} />{a.name}</span>
      <span className="v">{value}{!failed && unit && <small>{unit}</small>}</span>
      {!failed && visual}
      <span className={['c', failed ? '' : captionClass ?? ''].filter(Boolean).join(' ')}>
        {failed ? FAILED : caption}
      </span>
    </button>
  )
}

function TilesView({ r, open, onTile }: { r: TickerPayload; open: OpenState | null; onTile: ResultCardProps['onTile'] }) {
  const on = (i: AssessmentId) => open?.ticker === r.ticker && open.tab === i
  const q = r.quality?.score ?? null
  const m = r.moat?.score ?? null
  const fv = r.fair_value?.value ?? null
  const gap = r.fair_value?.gap_pct ?? null
  const rr = r.reward_risk
  return (
    <div className="rc-tiles">
      <Tile i={0} on={on(0)} onClick={() => onTile(r.ticker, 0)}
            value={num(q, 1)} unit="/10" visual={<Gauge v={q} max={10} color="var(--q)" />}
            caption={qualityTier(q) ?? ''} />
      <Tile i={1} on={on(1)} onClick={() => onTile(r.ticker, 1)}
            value={num(m, 0)} unit="/100" visual={<Gauge v={m} max={100} color="var(--mo)" />}
            caption={moatTier(m) ?? ''} />
      <Tile i={2} on={on(2)} onClick={() => onTile(r.ticker, 2)}
            value={dollars(fv)}
            visual={<Pair a={['Fair value', fv, dollars(fv), 'var(--fv)']} b={['Price', r.price, dollars(r.price), 'var(--mute)']} />}
            caption={fvCaption(gap)} captionClass={gapClass(gap)} />
      <Tile i={3} on={on(3)} onClick={() => onTile(r.ticker, 3)}
            value={rr && finite(rr.ratio) ? num(rr.ratio, 1) : DASH} unit="×"
            visual={<Pair a={['Reward', rr?.reward_score ?? null, num(rr?.reward_score ?? null, 1), 'var(--pos)']}
                          b={['Risk', rr?.risk_score ?? null, num(rr?.risk_score ?? null, 1), 'var(--neg)']} />}
            caption={rr?.tier ?? ''} />
    </div>
  )
}

function Cell({ best, value, sub, subClass }: { best: boolean; value: string; sub: string; subClass?: string }) {
  const failed = value === DASH
  return (
    <span className={best ? 'rc-cell best' : 'rc-cell'}>
      <b>{value}</b>
      <span className={['s', failed ? '' : subClass ?? ''].filter(Boolean).join(' ')}>{failed ? FAILED : sub}</span>
    </span>
  )
}

function CompareView({ rows, open, onRow, onWatch }: {
  rows: TickerPayload[]; open: OpenState | null
  onRow: ResultCardProps['onRow']; onWatch: ResultCardProps['onWatch']
}) {
  const bq = bestOf(rows.map(r => r.quality?.score ?? null))
  const bm = bestOf(rows.map(r => r.moat?.score ?? null))
  const bg = bestOf(rows.map(r => r.fair_value?.gap_pct ?? null))
  const br = bestOf(rows.map(r => r.reward_risk?.ratio ?? null))
  const is = (v: number | null, b: number | null) => b !== null && v === b
  return (
    <div className="rc-cmp">
      {/* Column heads on a wide card; the colour key replaces them on a phone. */}
      <div className="rc-cols" aria-hidden="true">
        <span />
        {ASSESSMENTS.map(a => (
          <span key={a.name}><span className="dot" style={{ background: a.color }} />{a.name}</span>
        ))}
      </div>
      {rows.map(r => {
        const isOpen = open?.ticker === r.ticker
        const q = r.quality?.score ?? null
        const m = r.moat?.score ?? null
        const gap = r.fair_value?.gap_pct ?? null
        const rr = r.reward_risk?.ratio ?? null
        return (
          // The whole row is clickable for a mouse; the keyboard and screen-reader
          // affordance is the real button on the ticker, as in the old grid.
          <div key={r.ticker} className={isOpen ? 'rc-row on' : 'rc-row'} onClick={() => onRow(r.ticker)}>
            <span className="rc-id">
              <button type="button" className="rc-open" aria-expanded={isOpen}
                      onClick={e => { e.stopPropagation(); onRow(r.ticker) }}>{r.ticker}</button>
              <Star ticker={r.ticker} onWatch={onWatch} />
              <span className="nm">{r.company_name ?? ''}</span>
              <span className="chev" aria-hidden="true">▾</span>
            </span>
            <Cell best={is(q, bq)} value={num(q, 1)} sub={qualityTier(q) ?? ''} />
            <Cell best={is(m, bm)} value={num(m, 0)} sub={moatTier(m) ?? ''} />
            <Cell best={is(gap, bg)} value={dollars(r.fair_value?.value ?? null)}
                  sub={gapPct(gap)} subClass={gapClass(gap)} />
            <Cell best={is(rr, br)} value={finite(rr) ? `${num(rr, 1)}×` : DASH}
                  sub={r.reward_risk?.tier ?? ''} />
          </div>
        )
      })}
    </div>
  )
}

/** The hero's right column (spec 5.2, hero rework 2026-09-27). One ticker renders as
 *  four tiles, two or three as a compact comparison. Clicking a tile or a row asks the
 *  page to open that breakdown under the hero; the card itself holds no open state. */
export default function ResultCard(p: ResultCardProps) {
  if (p.rows.length === 0) {
    return (
      <div className="rc rc-empty">
        <p>{p.busy ? 'Running the analysis…' : 'The live example could not be loaded. Try a ticker on the left.'}</p>
      </div>
    )
  }
  const one = p.rows.length === 1
  const r = p.rows[0]
  const summary = !one && !p.busy && p.ms !== null
    ? `${p.rows.length} tickers · ${(p.ms / 1000).toFixed(1)} s` : null
  return (
    <div className="rc">
      {p.pending.length > 1 && <LiveRunBar tickers={p.pending} />}
      <div className={p.busy ? 'stale' : undefined} aria-busy={p.busy}>
        <div className="rc-head">
          {one ? (
            <div>
              <span className="tk">{r.ticker}</span> <Star ticker={r.ticker} onWatch={p.onWatch} />{' '}
              <span className="co">{r.company_name ?? ''}</span>
              <div className="px">
                {money(r.price)}{r.quality?.profile_label ? ` · ${r.quality.profile_label} profile` : ''}
              </div>
            </div>
          ) : (
            <div>
              <span className="tk">Comparing {p.rows.length}</span>
              <div className="px">{p.rows.map(x => x.ticker).join(' · ')}{summary ? ` · ${summary}` : ''}</div>
            </div>
          )}
          <Pill source={p.source} />
        </div>
        {one
          ? <TilesView r={r} open={p.open} onTile={p.onTile} />
          : <CompareView rows={p.rows} open={p.open} onRow={p.onRow} onWatch={p.onWatch} />}
        <p className="rc-foot">
          {one ? 'Click any score for its full breakdown ↓' : 'Click a ticker for its full breakdown ↓'}
        </p>
      </div>
    </div>
  )
}
```

Note on the gap cell: `gapPct(-23.31)` renders `−23%` with a real minus (U+2212). The test above matches on that exact string.

- [ ] **Step 3b: Add the card's CSS.** Append to `theme.css`:

```css
/* Result card — the hero's right column (hero rework 2026-09-27). One ticker: four
 * tiles; two or three: a compact comparison. Mock: .superpowers/brainstorm/hero/. */
.intrinsica .rc { background: var(--bg); border: 1px solid var(--border2); border-radius: 18px; padding: 18px 20px 14px;
  box-shadow: 0 1px 2px rgba(11,11,15,.05), 0 24px 60px rgba(11,11,15,.10); text-align: left; }
.intrinsica .rc .runbar { margin: 0 0 12px; box-shadow: none; }
.intrinsica .rc-empty { min-height: 280px; display: grid; place-items: center; color: var(--mute); font-size: 14px; text-align: center; }
.intrinsica .rc-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
  padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.intrinsica .rc-head .tk { font: 700 20px var(--fh); }
.intrinsica .rc-head .co { color: var(--dim); font-size: 14px; }
.intrinsica .rc-head .px { font: 500 13px var(--fm); color: var(--mute); margin-top: 2px; }
.intrinsica .rc-pill { display: inline-flex; align-items: center; gap: 7px; font: 600 11.5px var(--fb); border-radius: 99px;
  padding: 5px 10px; white-space: nowrap; }
.intrinsica .rc-pill.live { color: var(--pos); background: #ecfdf3; }
.intrinsica .rc-pill.live i { width: 7px; height: 7px; border-radius: 50%; background: var(--pos); animation: rc-pulse 1.6s ease-in-out infinite; }
.intrinsica .rc-pill.yours { color: var(--accent); background: var(--accent-soft); }
@keyframes rc-pulse { 50% { opacity: .3; } }
.intrinsica .rc .watch { background: none; border: 1px solid var(--border2); cursor: pointer; color: var(--dim); font: 400 14px var(--fb);
  line-height: 1; padding: 4px 7px; border-radius: 7px; vertical-align: 2px; }
.intrinsica .rc .watch:hover, .intrinsica .rc .watch:focus-visible { color: var(--warn); background: var(--bg3); }
.intrinsica .rc .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.intrinsica .rc-tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border); margin: 12px 0;
  border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.intrinsica .rc-tile { background: var(--bg); border: 0; padding: 13px 15px; text-align: left; cursor: pointer; display: flex;
  flex-direction: column; gap: 0; font: inherit; color: inherit; position: relative; }
.intrinsica .rc-tile::after { content: "↓"; position: absolute; right: 12px; top: 12px; font-size: 13px; color: var(--mute); }
.intrinsica .rc-tile:hover { background: var(--bg2); }
.intrinsica .rc-tile.on { background: var(--accent-soft); box-shadow: inset 0 0 0 2px var(--accent); }
.intrinsica .rc-tile.on::after { color: var(--accent); }
.intrinsica .rc-tile .n { font: 600 13px var(--fb); display: flex; align-items: center; }
.intrinsica .rc-tile .v { font: 700 32px/1.1 var(--fh); letter-spacing: -.02em; margin-top: 6px; }
.intrinsica .rc-tile .v small { font: 500 13px var(--fm); color: var(--mute); margin-left: 3px; }
.intrinsica .rc-tile .c { font-size: 12.5px; color: var(--dim); margin-top: 8px; }
.intrinsica .rc-g { display: block; height: 6px; background: var(--bg3); border-radius: 9px; margin-top: 10px; overflow: hidden; }
.intrinsica .rc-g b, .intrinsica .rc-pair .t b { display: block; height: 100%; border-radius: 9px; }
.intrinsica .rc-pair { display: grid; gap: 4px; margin-top: 10px; }
.intrinsica .rc-pair .r { display: grid; grid-template-columns: 58px 1fr 40px; align-items: center; gap: 8px; font-size: 11px; color: var(--mute); }
.intrinsica .rc-pair .t { height: 6px; background: var(--bg3); border-radius: 9px; overflow: hidden; }
.intrinsica .rc-pair em { font: 500 11px var(--fm); font-style: normal; color: var(--dim); text-align: right; }
.intrinsica .rc-foot { font-size: 12.5px; color: var(--mute); padding-top: 10px; border-top: 1px solid var(--border); }
.intrinsica .rc-cmp { margin: 8px 0 10px; }
.intrinsica .rc-cols, .intrinsica .rc-row { display: grid; grid-template-columns: 1.35fr repeat(4, 1fr); gap: 8px; align-items: start; }
.intrinsica .rc-cols { font: 600 11.5px var(--fb); color: var(--dim); padding: 6px 8px; }
.intrinsica .rc-row { padding: 11px 8px; border-top: 1px solid var(--border); cursor: pointer; }
.intrinsica .rc-row:hover { background: var(--bg2); }
.intrinsica .rc-row.on { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
.intrinsica .rc-id { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; }
.intrinsica .rc-open { background: none; border: 0; padding: 0; font: 700 15px var(--fh); color: inherit; cursor: pointer; }
.intrinsica .rc-id .nm { flex-basis: 100%; font-size: 11.5px; color: var(--mute); }
.intrinsica .rc-id .chev { display: none; }
.intrinsica .rc-cell b { display: block; font: 700 18px var(--fh); }
.intrinsica .rc-cell .s { display: block; font-size: 11.5px; color: var(--dim); margin-top: 2px; }
.intrinsica .rc-cell.best b { color: var(--accent); }
@media (max-width: 600px) {
  .intrinsica .rc { padding: 16px 14px 12px; }
  .intrinsica .rc-tile { padding: 12px; }
  .intrinsica .rc-tile .v { font-size: 28px; }
  .intrinsica .rc-pair .r { grid-template-columns: 40px 1fr 32px; gap: 5px; font-size: 10px; }
  .intrinsica .rc-cols { grid-template-columns: repeat(4, 1fr); font-size: 11px; }
  .intrinsica .rc-cols > span:first-child { display: none; }
  .intrinsica .rc-row { grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .intrinsica .rc-id { grid-column: 1 / -1; }
  .intrinsica .rc-id .nm { flex-basis: auto; }
  .intrinsica .rc-id .chev { display: inline; margin-left: auto; color: var(--mute); }
  .intrinsica .rc-cell { background: var(--bg2); border-radius: 8px; padding: 7px 8px; }
  .intrinsica .rc-cell b { font-size: 16px; }
}
@media (prefers-reduced-motion: reduce) { .intrinsica .rc-pill.live i { animation: none; } }
```

- [ ] **Step 4: Run the tests and confirm they pass.** `npx vitest run src/landing/components/ResultCard.test.tsx`. Expected: PASS.

- [ ] **Step 4b: Keep the copy guard's file census true.** `copy-guard.test.ts` pins the number of landing source files. Change `expect(sources.length).toBe(19)` to `toBe(20)`, and add `'./components/ResultCard.tsx',` to the named list in `'covers every surface that renders copy…'`. Run `npx vitest run src/landing/copy-guard.test.ts`. Expected: PASS, and the new file's copy passes every banned-vocabulary check.

- [ ] **Step 5: Typecheck.** `npx tsc -b --force`. Expected: no errors.

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/landing/copy-guard.test.ts frontend/src/landing/components/ResultCard.tsx frontend/src/landing/components/ResultCard.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): ResultCard — tiles for one ticker, comparison for several

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `OpenBreakdown` dock

**Files:**
- Create: `frontend/src/landing/components/OpenBreakdown.tsx`
- Create: `frontend/src/landing/components/OpenBreakdown.test.tsx`
- Modify: `frontend/src/landing/theme.css`. Append the "breakdown dock" block.

**Interfaces:**
- Consumes: `Breakdown` (unchanged, `{ row, tab, onTab }`), `TickerPayload`, `AssessmentId`.
- Produces: `export default function OpenBreakdown({ row, tab, onTab, onClose }: { row: TickerPayload; tab: AssessmentId; onTab: (id: AssessmentId) => void; onClose: () => void })`. The root is `section.bk-dock` with `aria-label="{T} full breakdown"`. The Close button's accessible name is `Close`.

- [ ] **Step 1: Write the failing tests.** Create `OpenBreakdown.test.tsx`:

```tsx
import { afterEach, describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OpenBreakdown from './OpenBreakdown'
import type { TickerPayload } from '../types'

const ROW: TickerPayload = {
  ticker: 'AMD', company_name: 'Advanced Micro Devices, Inc.', price: 630.63,
  quality: { score: 7.2, fundamentals_composite: 7.2, profile_label: 'Tech / Growth', categories: [] },
  moat: { score: 25, gated: false, excluded: [],
          factors: [{ label: 'ROIC level', group: 'Magnitude', display: '9.8%', points: 4, max_points: 20, weight_pct: 20 }] },
  fair_value: null, reward_risk: null, calibrations: [], errors: [],
}

describe('OpenBreakdown', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('names the ticker and company above the unchanged breakdown', () => {
    render(<OpenBreakdown row={ROW} tab={1} onTab={vi.fn()} onClose={vi.fn()} />)
    const dock = screen.getByRole('region', { name: 'AMD full breakdown' })
    expect(dock).toHaveTextContent('AMD Advanced Micro Devices, Inc. · full breakdown')
    expect(dock.querySelector('.bd')).not.toBeNull()
    expect(dock).toHaveTextContent('ROIC level')
  })

  it('closes from its Close button', async () => {
    const onClose = vi.fn()
    render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('passes tab switches through to the page', async () => {
    const onTab = vi.fn()
    render(<OpenBreakdown row={ROW} tab={0} onTab={onTab} onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /^Moat/ }))
    expect(onTab).toHaveBeenCalledWith(1)
  })

  it('scrolls itself into view only when it opens off screen', () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    vi.spyOn(Element.prototype, 'getBoundingClientRect')
      .mockReturnValue({ top: 5000, bottom: 5600 } as DOMRect)
    const { unmount } = render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={vi.fn()} />)
    expect(scroll).toHaveBeenCalledTimes(1)
    unmount()

    scroll.mockClear()
    vi.spyOn(Element.prototype, 'getBoundingClientRect')
      .mockReturnValue({ top: 200, bottom: 800 } as DOMRect)
    render(<OpenBreakdown row={ROW} tab={0} onTab={vi.fn()} onClose={vi.fn()} />)
    expect(scroll).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run them and confirm they fail.** `npx vitest run src/landing/components/OpenBreakdown.test.tsx`. Expected: FAIL, the module is not found.

- [ ] **Step 3: Implement.** Create `OpenBreakdown.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import Breakdown from './Breakdown'
import type { AssessmentId, TickerPayload } from '../types'

/** The one place a breakdown opens (spec 5.3, hero rework 2026-09-27): full width,
 *  directly under the hero, whichever tile or row opened it. The panel itself is the
 *  unchanged Breakdown; this adds only its header, a Close, and a scroll that happens
 *  only when the dock opened below the fold — never a jump the visitor did not need. */
export default function OpenBreakdown({ row, tab, onTab, onClose }: {
  row: TickerPayload
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { top } = el.getBoundingClientRect()
    if (top > window.innerHeight - 80) el.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [row.ticker])

  return (
    <section ref={ref} className="bk-dock" aria-label={`${row.ticker} full breakdown`}>
      <div className="bk-in">
        <div className="bk-head">
          <b>{row.ticker}</b> {row.company_name ?? ''} · full breakdown
          <button type="button" className="bk-x" onClick={onClose}>Close <span aria-hidden="true">✕</span></button>
        </div>
        <Breakdown row={row} tab={tab} onTab={onTab} />
      </div>
    </section>
  )
}
```

Append to `theme.css`:

```css
/* Breakdown dock — opens full-width under the hero (hero rework 2026-09-27). */
.intrinsica .bk-dock { background: var(--bg2); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.intrinsica .bk-in { max-width: 1160px; margin: 0 auto; padding: 22px 24px 26px; }
.intrinsica .bk-head { display: flex; align-items: baseline; gap: 8px; font-size: 15px; color: var(--dim); margin-bottom: 12px; }
.intrinsica .bk-head b { font: 700 18px var(--fh); color: var(--text); }
.intrinsica .bk-x { margin-left: auto; background: none; border: 1px solid var(--border2); border-radius: 8px; padding: 6px 12px;
  font: 600 13px var(--fb); color: var(--dim); cursor: pointer; min-height: 36px; }
.intrinsica .bk-x:hover { color: var(--text); background: var(--bg); }
.intrinsica .bk-dock .bd { background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 6px 16px 18px; }
@media (max-width: 600px) { .intrinsica .bk-in { padding: 18px 16px 22px; } }
```

- [ ] **Step 4: Run the tests and confirm they pass.** `npx vitest run src/landing/components/OpenBreakdown.test.tsx`. Expected: PASS.

- [ ] **Step 4b: Keep the copy guard's file census true.** `copy-guard.test.ts` pins the number of landing source files. Change `expect(sources.length).toBe(20)` to `toBe(21)`, and add `'./components/OpenBreakdown.tsx',` to the named list in `'covers every surface that renders copy…'`. Run `npx vitest run src/landing/copy-guard.test.ts`. Expected: PASS, and the new file's copy passes every banned-vocabulary check.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/landing/copy-guard.test.ts frontend/src/landing/components/OpenBreakdown.tsx frontend/src/landing/components/OpenBreakdown.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): OpenBreakdown — the breakdown's one place under the hero

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Question band and tab-pair labels

**Files:**
- Modify: `frontend/src/landing/content/framework.ts`. Add `QUESTION_BAND` and `TAB_PAIRS`. Leave `PIPELINE` alone: `Hero.tsx` still uses it, and Task 6 deletes both.
- Create: `frontend/src/landing/components/QuestionBand.tsx`
- Create: `frontend/src/landing/components/QuestionBand.test.tsx`
- Modify: `frontend/src/landing/components/Framework.tsx`. Replace the `<div className="mcards">…</div>` block.
- Modify: `frontend/src/landing/components/Framework.test.tsx`
- Modify: `frontend/src/landing/theme.css`

**Interfaces:**
- Produces: `QUESTION_BAND: { title: string; body: string }`; `TAB_PAIRS: readonly [string, string]`; `export default function QuestionBand()`. The root is `div.qband` (not a `section`, so the page's `main section[id]` order tests are unaffected).

- [ ] **Step 1: Write the failing tests.** Create `QuestionBand.test.tsx`:

```tsx
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
```

In `Framework.test.tsx`:
- replace the selector `'.mbox .mcards + .mdetail'` with `'.mbox .mpairs + .mdetail'`;
- add this test inside `describe('Framework — assessment cards', …)`:

```tsx
  it('groups the tabs under the two questions: the business, then the price', () => {
    const { container } = show()
    const pairs = Array.from(container.querySelectorAll('.mpair'))
    expect(pairs.map(p => p.querySelector('.mpl')?.textContent))
      .toEqual(['Is it a good business?', 'At a good price?'])
    expect(pairs.map(p => Array.from(p.querySelectorAll('.cn')).map(n => n.textContent)))
      .toEqual([['Quality', 'Moat'], ['Fair Value', 'Reward / Risk']])
  })
```

- [ ] **Step 2: Run them and confirm they fail.** `npx vitest run src/landing/components/QuestionBand.test.tsx src/landing/components/Framework.test.tsx`. Expected: FAIL. `QuestionBand` is missing, `.mpairs` is missing, `.mpair` is missing.

- [ ] **Step 3: Implement.** Append to `content/framework.ts`:

```ts
/** The band before the Framework (spec 5.4, hero rework 2026-09-27): the investor's
 *  question, then how Intrinsica answers it. */
export const QUESTION_BAND = {
  title: 'Is it a good business, at a good price?',
  body: 'Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show.',
} as const

/** Labels over the Framework tabs, one per pair in FRAMEWORK order: Quality + Moat
 *  answer the first, Fair Value + Reward / Risk the second. */
export const TAB_PAIRS = ['Is it a good business?', 'At a good price?'] as const
```

Create `QuestionBand.tsx`:

```tsx
import { QUESTION_BAND } from '../content/framework'

/** Bridges the live result above to the Framework's explanation below (spec 5.4).
 *  A div, not a section: it is not a nav destination. */
export default function QuestionBand() {
  return (
    <div className="qband">
      <div className="container">
        <h2>{QUESTION_BAND.title}</h2>
        <p>{QUESTION_BAND.body}</p>
      </div>
    </div>
  )
}
```

In `Framework.tsx`:
- add `TAB_PAIRS` to the import from `'../content/framework'`;
- replace the whole `<div className="mcards">…</div>` block with:

```tsx
          <div className="mpairs">
            {TAB_PAIRS.map((label, p) => (
              <div key={label} className="mpair">
                <div className="mpl">{label}</div>
                <div className="mcards">
                  {FRAMEWORK.slice(p * 2, p * 2 + 2).map((x, k) => {
                    const i = p * 2 + k
                    return (
                      <button key={x.name} type="button"
                              className={i === tab ? 'mcard on' : 'mcard'}
                              aria-pressed={i === tab}
                              onClick={() => onTab(i as AssessmentId)}>
                        <span className="cn">
                          <span className="dot" style={{ background: x.color }} />{x.name}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
```

Keep the existing comment above the old block, and add one line to it: "Split into two labelled pairs (hero rework 2026-09-27): the business, then the price."

In `theme.css`, replace the `.mcards` grid rule and its `@media (max-width: 600px)` rule (current lines 229 and 236) with:

```css
.intrinsica .mpairs { display: grid; grid-template-columns: 1fr 1fr; background: var(--bg2); border-bottom: 1px solid var(--border); }
.intrinsica .mpl { font: 600 11px var(--fb); letter-spacing: .08em; text-transform: uppercase; color: var(--dim);
  text-align: center; padding: 10px 8px 4px; }
.intrinsica .mpair + .mpair { border-left: 1px solid var(--border); }
.intrinsica .mcards { display: grid; grid-template-columns: repeat(2, 1fr); }
@media (max-width: 600px) { .intrinsica .mpairs { grid-template-columns: 1fr; } .intrinsica .mpair + .mpair { border-left: 0; border-top: 1px solid var(--border); } }
.intrinsica .qband { background: var(--bg2); border-top: 1px solid var(--border); padding: 48px 0 8px; text-align: center; }
.intrinsica .qband h2 { font: 700 34px/1.15 var(--fh); letter-spacing: -.02em; text-wrap: balance; }
.intrinsica .qband p { color: var(--dim); font-size: 17px; max-width: 62ch; margin: 12px auto 0; }
@media (max-width: 600px) { .intrinsica .qband h2 { font-size: 26px; } .intrinsica .qband p { font-size: 15px; } }
```

- [ ] **Step 4: Run the tests and confirm they pass.** `npx vitest run src/landing/components/QuestionBand.test.tsx src/landing/components/Framework.test.tsx src/landing/content/framework.test.ts`. Expected: PASS. The existing `.mcards button` and `.mcards .cn` queries still find four buttons in order.

- [ ] **Step 4b: Keep the copy guard's file census true.** `copy-guard.test.ts` pins the number of landing source files. Change `expect(sources.length).toBe(21)` to `toBe(22)`, and add `'./components/QuestionBand.tsx',` to the named list in `'covers every surface that renders copy…'`. Run `npx vitest run src/landing/copy-guard.test.ts`. Expected: PASS, and the new file's copy passes every banned-vocabulary check.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/landing/copy-guard.test.ts frontend/src/landing/content/framework.ts frontend/src/landing/components/QuestionBand.tsx frontend/src/landing/components/QuestionBand.test.tsx frontend/src/landing/components/Framework.tsx frontend/src/landing/components/Framework.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): question band before the Framework, tabs in two labelled pairs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Two-column hero, page wiring, grid removal

This is one task because the hero, the page and the grid only make sense together. The page cannot render the new hero without the new wiring, and the grid cannot go until the page stops using it.

**Files:**
- Modify: `frontend/src/landing/components/Hero.tsx`, `frontend/src/landing/components/Hero.test.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`, `frontend/src/landing/LandingPage.test.tsx`
- Modify: `frontend/src/landing/content/framework.ts` (delete `PIPELINE`)
- Modify: `frontend/src/landing/copy-guard.test.ts`
- Modify: `frontend/src/landing/theme.css`
- Delete: `frontend/src/landing/components/ResultGrid.tsx`, `frontend/src/landing/components/ResultGrid.test.tsx`

**Interfaces:**
- Consumes: `ResultCard` and `OpenState` (Task 3), `OpenBreakdown` (Task 4), `QuestionBand` (Task 5).
- New `Hero` props:

```ts
interface Props {
  onAnalyze: (tickers: string[], source: AnalyzeSource) => void
  busy: boolean
  busyCount?: number
  exhausted: boolean
  notice?: string | null
  card: ReactNode
}
```

  `ASSESSMENTS`, `COMPARE_TICKERS` and `MAX_TICKERS` stay exported, unchanged. `onSelectAssessment` is removed.

- [ ] **Step 1: Rewrite the Hero tests (failing).** In `Hero.test.tsx`:
  - Change every render to `<Hero onAnalyze={…} busy={…} exhausted={…} card={<div>CARD</div>} />`, dropping `onSelectAssessment`.
  - **Delete these tests:**
    - `shows the four assessments with their questions`;
    - `jumps to the methodology section…`;
    - `still renders the four assessment chips when exhausted`;
    - the whole `describe('pipeline strip', …)`.
  - **Keep the tests for:** ticker parsing, the fourth-ticker refusal, the empty field, the exhausted wall, the compare chip, the busy button, and "never uses the word signal".
  - **Add:**

```tsx
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
```

Update the import at the top to `import Hero, { COMPARE_TICKERS, MAX_TICKERS } from './Hero'`. Drop `ASSESSMENTS` if nothing else in the file uses it.

- [ ] **Step 2: Run them and confirm they fail.** `npx vitest run src/landing/components/Hero.test.tsx`. Expected: FAIL. There is no `h1` with the headline and no `.hero-in`; the TS prop errors surface only in `tsc`.

- [ ] **Step 3: Rewrite `Hero.tsx`.**
  - Replace the whole `return (…)` block and the `Props` interface as below.
  - Delete the `PIPELINE` import.
  - Delete the `onSelectAssessment` parameter.
  - Keep `submit`, `runCompare`, `ASSESSMENTS`, `COMPARE_TICKERS` and `MAX_TICKERS` as they are.
  - Add `import type { ReactNode } from 'react'`, alongside `useState`.

```tsx
interface Props {
  /** Called for both a typed submission ('typed') and the compare chip
   *  ('sample') — the source travels through to analysis_started and to the
   *  no-account demo limit, which only 'typed' runs consume. */
  onAnalyze: (tickers: string[], source: AnalyzeSource) => void
  /** True while an analysis is in flight. Disables BOTH the Analyze button
   *  and the compare chip: concurrent chip clicks would each fire their own
   *  analysis_started, inflating the very metric the chip exists to measure. */
  busy: boolean
  /** How many tickers the in-flight run covers ("Analyzing 3…"). Loading variant E. */
  busyCount?: number
  /** True once this browser has used up its free demo runs (demoLimit.ts). */
  exhausted: boolean
  /** A run's notice ("Not recognised: X", a server error, a timeout), shown under the
   *  input it is about (spec 5.2, hero rework 2026-09-27). */
  notice?: string | null
  /** The result card: the hero's right column (spec 5.1). */
  card: ReactNode
}

export default function Hero({ onAnalyze, busy, busyCount = 0, exhausted, notice, card }: Props) {
  // … keep `value`, `error`, submit() and runCompare() exactly as they are …

  // Spec 5.1 (hero rework 2026-09-27): promise and analyzer on the left, the live
  // result card on the right; one column on a phone, input first. The wordmark
  // heading, the pipeline strip and the four assessment links are gone — the card
  // shows the four scores themselves, and the questions live in the Framework.
  return (
    <header className="hero">
      <div className="hero-in">
        <div className="hero-l">
          <h1 className="hero-h1">Judge the business.<br />Then judge the price.</h1>
          <p className="hero-sub">
            Quality and Moat tell you how good the company is; Fair Value and Reward/Risk
            tell you whether the price makes sense. All from the fundamentals, all shown.
          </p>
          <div className="analyzer" id="analyze">
            {exhausted ? (
              <p className="an-wall">
                You've used all {DEMO_RUN_LIMIT} free analyses in a rolling{' '}
                {DEMO_WINDOW_DAYS}-day window. <a href="#pricing">See the plans</a> to
                keep analyzing.
              </p>
            ) : (
              <>
                <div className="an-row">
                  <div className="an-field">
                    <input
                      value={value}
                      aria-label="Tickers"
                      onChange={e => setValue(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') submit() }}
                      placeholder="Enter one or more tickers — e.g. NVDA, AMD, AVGO"
                    />
                  </div>
                  <button className="an-btn" type="button" onClick={submit} disabled={busy}>
                    {busy
                      ? <><span className="spin" aria-hidden="true" />
                          {busyCount > 1 ? `Analyzing ${busyCount}…` : 'Analyzing…'}</>
                      : 'Analyze →'}
                  </button>
                </div>
                {error && <p className="an-error">{error}</p>}
              </>
            )}

            {/* Outside the exhausted branch on purpose: chip runs never consume the
                typed allowance, so this keeps working after the wall appears. */}
            <div className="chips">
              <span className="lbl">Or try:</span>
              <button type="button" className="chip" onClick={runCompare} disabled={busy}>
                Compare {COMPARE_TICKERS.join(' · ')}
              </button>
            </div>
            {!exhausted && (
              <p className="an-micro">Up to {MAX_TICKERS} tickers at a time · no account needed</p>
            )}
          </div>
          {notice && <p className="notice">{notice}</p>}
        </div>
        <div className="hero-r">{card}</div>
      </div>
    </header>
  )
}
```

The micro-line's JSX renders `Up to 3 tickers at a time · no account needed` as one text node, because React joins adjacent string and expression children into one text node in the DOM. If `getByText` fails on it, wrap the line as `{`Up to ${MAX_TICKERS} tickers at a time · no account needed`}`.

Then delete `PIPELINE` from `content/framework.ts`, together with its doc comment.

- [ ] **Step 4: Run the Hero tests and confirm they pass.** `npx vitest run src/landing/components/Hero.test.tsx`. Expected: PASS.

- [ ] **Step 5: Rewrite the page tests (failing).** In `LandingPage.test.tsx`:

(a) Replace `gridOf` (line 339) with the card and dock helpers:

```tsx
// The hero's result card and the breakdown dock (hero rework 2026-09-27).
const cardOf = () => document.querySelector<HTMLElement>('.hero-r .rc')!
const dockOf = () => document.querySelector<HTMLElement>('section.bk-dock')
const tile = (name: string) => within(cardOf()).getByRole('button', { name: new RegExp(`^${name}`) })
```

(b) In `describe('LandingPage compare chip …')`:
- replace every `within(gridOf())` with `within(cardOf())`;
- replace `const rowOf = (t: string) => within(grid).getByText(t).closest('tr')!` with `const rowOf = (t: string) => within(cardOf()).getByRole('button', { name: t }).closest('.rc-row') as HTMLElement`;
- replace the four `toHaveClass('best')` / `not.toHaveClass('best')` assertions with the `.rc-cell` form:

```tsx
    const cell = (t: string, text: string) => within(rowOf(t)).getByText(text).closest('.rc-cell')!
    expect(cell('MSFT', '9.5')).toHaveClass('best')
    expect(cell('AAPL', '81')).toHaveClass('best')
    expect(cell('NVDA', '+12%')).toHaveClass('best')
    expect(cell('AAPL', '2.4×')).toHaveClass('best')
    expect(cell('AAPL', '8.0')).not.toHaveClass('best')
    expect(cell('NVDA', '45')).not.toHaveClass('best')
    expect(cardOf().querySelectorAll('.rc-cell.best')).toHaveLength(4)
```

- replace `expect(screen.getByText(/Computed in parallel/)).toBeInTheDocument()` with `expect(cardOf().querySelector('.rc-head')).toHaveTextContent(/3 tickers · \d+\.\d s/)`;
- add `expect(within(cardOf()).getByText(/Live example/)).toBeInTheDocument()`. The chip is a sample.

(c) In `'shows the run in flight …'`:
- replace `gridOf().closest('.stale')` with `cardOf().querySelector('.stale')` in both places;
- replace `expect(screen.getByText(/Computed in parallel/))…` with the `.rc-head` assertion from (b).

(d) Replace the whole `describe('LandingPage breakdown analytics under StrictMode (fix round 1)', …)` with:

```tsx
describe('LandingPage breakdown analytics under StrictMode', () => {
  const opens = (track: unknown) =>
    vi.mocked(track as (...a: unknown[]) => void).mock.calls.filter(c => c[0] === 'breakdown_opened')
  const mount = async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('AAPL')], invalid: [], error: null }),
    }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => { expect(within(cardOf()).getByText('AAPL Inc.')).toBeInTheDocument() })
  }

  // Spec 5.2 (hero rework): nothing opens by itself any more.
  it('opens nothing on load and records nothing', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('fires breakdown_opened exactly once when a tile opens it, with that tile as the tab', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    vi.mocked(track).mockClear()
    await userEvent.click(tile('Moat'))
    expect(dockOf()).not.toBeNull()
    expect(opens(track)).toEqual([['breakdown_opened', { ticker: 'AAPL', assessment: 'Moat' }]])
  })

  it('switches tab from another tile without recording a second open, and folds from the same tile', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    await userEvent.click(tile('Moat'))
    vi.mocked(track).mockClear()

    await userEvent.click(tile('Fair Value'))
    expect(dockOf()).not.toBeNull()
    expect(tile('Fair Value')).toHaveAttribute('aria-pressed', 'true')
    expect(tile('Moat')).toHaveAttribute('aria-pressed', 'false')
    expect(opens(track)).toEqual([])

    await userEvent.click(tile('Fair Value'))
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('folds from Close and records nothing for it', async () => {
    const { track } = await import('../lib/analytics')
    await mount()
    await userEvent.click(tile('Quality'))
    vi.mocked(track).mockClear()
    await userEvent.click(within(dockOf()!).getByRole('button', { name: 'Close' }))
    expect(dockOf()).toBeNull()
    expect(opens(track)).toEqual([])
  })

  it('opens a comparison row on the current tab, once, and folds it from the same row', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    render(<StrictMode><MemoryRouter><LandingPage /></MemoryRouter></StrictMode>)
    await waitFor(() => { expect(within(cardOf()).getByRole('button', { name: 'NVDA' })).toBeInTheDocument() })
    // Move the shared assessment to Reward / Risk from the Framework tabs first.
    await userEvent.click(document.querySelectorAll<HTMLElement>('.mcards button')[3])
    vi.mocked(track).mockClear()

    const nvda = within(cardOf()).getByRole('button', { name: 'NVDA' })
    await userEvent.click(nvda)
    expect(nvda).toHaveAttribute('aria-expanded', 'true')
    expect(opens(track)).toEqual([['breakdown_opened', { ticker: 'NVDA', assessment: 'Reward / Risk' }]])

    await userEvent.click(nvda)
    expect(nvda).toHaveAttribute('aria-expanded', 'false')
    expect(dockOf()).toBeNull()
    expect(opens(track)).toHaveLength(1)
  })
})
```

(e) Replace `describe('LandingPage breakdown panel (task 10)', …)` with:

```tsx
describe('LandingPage breakdown dock', () => {
  async function openFromTile(name = 'Quality') {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const utils = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    await userEvent.click(tile(name))
    return utils
  }

  it('opens the real factor table under the hero, not an empty panel', async () => {
    await openFromTile()
    const dock = dockOf()!
    expect(dock.previousElementSibling).toHaveClass('hero')
    expect(within(dock).getByText(/Growth & Margins/)).toBeInTheDocument()
    expect(within(dock).getByText('Revenue growth (3-yr)')).toBeInTheDocument()
    expect(within(dock).getByText('+8.1% / yr')).toBeInTheDocument()
  })

  it('opens on the tab of the tile that was clicked', async () => {
    await openFromTile('Moat')
    expect(within(dockOf()!).getAllByText('ROIC level').length).toBeGreaterThan(0)
    expect(within(dockOf()!).queryByText(/Growth & Margins/)).not.toBeInTheDocument()
  })

  it('switches the open panel from its own tabs, and the tile highlight follows', async () => {
    await openFromTile()
    await userEvent.click(within(dockOf()!).getByRole('button', { name: /^Fair Value/ }))
    expect(within(dockOf()!).getByText('Mega Cap valuation blend')).toBeInTheDocument()
    expect(tile('Fair Value')).toHaveAttribute('aria-pressed', 'true')
  })

  it('closes when a new run lands', async () => {
    await openFromTile()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => COMPARE_RESULTS() }))
    await userEvent.click(screen.getByRole('button', { name: /Compare/ }))
    await waitFor(() => { expect(within(cardOf()).getByRole('button', { name: 'MSFT' })).toBeInTheDocument() })
    expect(dockOf()).toBeNull()
  })
})
```

(f) In `describe('LandingPage framework section (task 11)', …)`:

- Replace the first test with:

```tsx
  it('moves the Framework panel when a card tile picks an assessment — one shared state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    expect(detail(container).querySelector('.dh')).toHaveTextContent('Quality')
    await userEvent.click(tile('Moat'))
    expect(detail(container).querySelector('.dh')).toHaveTextContent('Moat')
    expect(detail(container)).toHaveTextContent('40 of 100 points')
  })
```

- In `'moves an already-open breakdown panel when a framework card is clicked'`:
  - after the `waitFor`, add `await userEvent.click(tile('Quality'))`;
  - use `dockOf()!` in place of `container.querySelector<HTMLElement>('.bd')!` three times.
- Replace `'records methodology_viewed with the assessment chosen, and only from here'` with:

```tsx
  it('records methodology_viewed with the assessment chosen, and only from here', async () => {
    const { track } = await import('../lib/analytics')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    const { container } = renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    vi.mocked(track).mockClear()

    // A card tile writes the same state but is not the methodology section, so it
    // must not fire the event (spec section 9).
    await userEvent.click(tile('Reward \/ Risk'))
    expect(track).not.toHaveBeenCalledWith('methodology_viewed', expect.anything())

    await userEvent.click(container.querySelectorAll('.mcards button')[2])
    expect(track).toHaveBeenCalledWith('methodology_viewed', { assessment: 'Fair Value' })
  })
```

(g) Add a new describe for the page-level states from the Review Focus:

```tsx
describe('LandingPage result card states (hero rework)', () => {
  it('shows the running frame, then the could-not-load message, when the sample fails', async () => {
    let fail!: (e: unknown) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise((_r, rej) => { fail = rej })))
    renderPage()
    expect(cardOf()).toHaveTextContent('Running the analysis…')
    await act(async () => { fail(new TypeError('network down')) })
    await waitFor(() => {
      expect(cardOf()).toHaveTextContent('The live example could not be loaded. Try a ticker on the left.')
    })
    expect(document.querySelector('.hero-l')).toHaveTextContent('The analysis could not be reached. Please try again.')
  })

  it('keeps the previous card and its open breakdown when a run returns no rows', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [BREAKDOWN_ROW], invalid: [], error: null }),
    }))
    renderPage()
    await waitFor(() => { expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument() })
    await userEvent.click(tile('Moat'))

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [], invalid: ['ZZZZ'], error: null }),
    }))
    await userEvent.type(screen.getByRole('textbox'), 'ZZZZ')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => { expect(screen.getByText('Not recognised: ZZZZ')).toBeInTheDocument() })

    expect(within(cardOf()).getByText('Apple Inc.')).toBeInTheDocument()
    expect(dockOf()).not.toBeNull()
  })

  it('labels a typed run as the visitor’s own', async () => {
    await renderSettled()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ results: [compareRow('NVDA')], invalid: [], error: null }),
    }))
    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => { expect(within(cardOf()).getByText('Your analysis')).toBeInTheDocument() })
  })

  it('places the question band between the hero and the Framework', async () => {
    const { container } = await renderSettled()
    const band = container.querySelector('.qband')!
    const how = container.querySelector('section#how')!
    expect(band.compareDocumentPosition(how) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.querySelector('.hero')!.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
```

(h) The watchlist test (`'answers a watchlist star …'`) needs only `gridOf()` → `cardOf()`. The star labels are unchanged.

(i) `'counts a typed run on a partial success …'` uses `results: [{ ticker: 'NVDA' }]`, a partial payload. The card must not throw on it: `quality`, `moat`, `fair_value` and `reward_risk` are all `undefined`. The `?? null` guards in `ResultCard` cover that. Leave the test as is.

- [ ] **Step 6: Run the page tests and confirm they fail.** `npx vitest run src/landing/LandingPage.test.tsx`. Expected: FAIL. The page still renders the grid, and there is no `.rc`, `.bk-dock` or `.qband`.

- [ ] **Step 7: Rewire `LandingPage.tsx`.**

In the imports:
- replace `import ResultGrid, { RunBar } from './components/ResultGrid'` with:

```tsx
import ResultCard from './components/ResultCard'
import OpenBreakdown from './components/OpenBreakdown'
import QuestionBand from './components/QuestionBand'
```

- remove the `Breakdown` import, because `OpenBreakdown` renders it.

State:
- delete `const [open, setOpen] = useState<Record<string, boolean>>({})`, the whole `isOpen`/`toggle` block (lines ~102–137, with its comment) and the `effectiveOpen` loop;
- add:

```tsx
  // Which ticker's breakdown the dock under the hero is showing, if any (spec 5.3,
  // hero rework 2026-09-27). The tab is the page's single `assessment`, shared with
  // the card's tiles, the dock's own tabs and the Framework section.
  const [openTicker, setOpenTicker] = useState<string | null>(null)
  // The source of the run whose rows the card shows: it picks the card's pill
  // ("Live example" for a sample, "Your analysis" for a typed run).
  const [rowsSource, setRowsSource] = useState<AnalyzeSource | null>(null)

  // breakdown_opened fires only on a closed -> open transition, and beside the state
  // change, never inside an updater (StrictMode double-invokes updaters — fix round 1).
  // A tile on the ticker already open switches the tab; the same tile again folds it.
  // Tab switches and folds are uninstrumented (spec section 9).
  const openTile = useCallback((ticker: string, tab: AssessmentId) => {
    const wasOpen = openTicker === ticker
    if (wasOpen && assessment === tab) { setOpenTicker(null); return }
    setAssessment(tab)
    setOpenTicker(ticker)
    if (!wasOpen) track(EVENTS.breakdownOpened, { ticker, assessment: FRAMEWORK[tab].name })
  }, [openTicker, assessment])

  // A comparison row opens on whichever tab the page is on.
  const openRow = useCallback((ticker: string) => {
    if (openTicker === ticker) { setOpenTicker(null); return }
    setOpenTicker(ticker)
    track(EVENTS.breakdownOpened, { ticker, assessment: FRAMEWORK[assessment].name })
  }, [openTicker, assessment])
  const closeBreakdown = useCallback(() => setOpenTicker(null), [])
```

In `analyze`, replace:

```tsx
      setRows(results)
      // A new result set starts from its own default expansion.
      setOpen({})
      setLastMs(Date.now() - started)
```

with:

```tsx
      // A run that produced no rows (all invalid, a server error) leaves the previous
      // card — and any open breakdown — in place: an empty card would leave a hole in
      // the hero (spec 5.2, hero rework). The notice above says what happened.
      if (results.length > 0) {
        setRows(results)
        setRowsSource(source)
        setOpenTicker(null)
        setLastMs(Date.now() - started)
      }
```

Replace everything from `<Hero` down to the closing `</section>` of `#result` with:

```tsx
        <Hero
          onAnalyze={analyze}
          busy={busy}
          busyCount={pending.length}
          exhausted={exhausted}
          notice={notice}
          card={
            <ResultCard
              rows={rows}
              source={rowsSource}
              pending={pending}
              busy={busy}
              ms={lastMs}
              open={openTicker ? { ticker: openTicker, tab: assessment } : null}
              onTile={openTile}
              onRow={openRow}
              onWatch={watchFor}
            />
          }
        />
        {openRowData && (
          <OpenBreakdown row={openRowData} tab={assessment} onTab={setAssessment} onClose={closeBreakdown} />
        )}
        <QuestionBand />
```

Just above `return (`, add:

```tsx
  const openRowData = rows.find(r => r.ticker === openTicker) ?? null
```

Leave the `<Framework … />` block and everything after it unchanged. `effectiveOpen` is deleted. The `notice` paragraph that used to follow `<Hero>` is deleted, because Hero renders it now.

- [ ] **Step 8: Delete the grid and fix the copy guard.**

```bash
git rm frontend/src/landing/components/ResultGrid.tsx frontend/src/landing/components/ResultGrid.test.tsx
```

In `copy-guard.test.ts`:
- `expect(sources.length).toBe(22)` → `toBe(21)`, because ResultGrid is gone. Tasks 2–5 already raised it from 18 to 22.
- Delete `'./components/ResultGrid.tsx',` from the named list.

- `expect(copy).toMatch(/Fundamental Stock Analysis/)       // JSX text in Hero` → `expect(copy).toMatch(/Then judge the price/)       // JSX text in Hero`.

- [ ] **Step 9: Replace the dead hero and grid CSS.** In `theme.css`:
  - **Delete these rules:**
    - `.intrinsica .hero`, `.intrinsica .brand`, `.intrinsica .h3`;
    - the `@media (max-width: 720px) { .intrinsica .brand … }` line;
    - the whole "pipeline strip" block and the whole "four assessments — inline under headline (V2)" block, including its media line;
    - `.intrinsica #result { … }`;
    - every `.intrinsica .tB …` rule, including `.intrinsica .tB .watch` and its `:hover` rule;
    - the "Computed in parallel" (done-state) rules `.intrinsica .runbar .mini > span`, `.intrinsica .runbar .mini.fail > span` and `.intrinsica .runbar .done …/.fail`. Only the live strip remains.
  - **Keep:** `.runbar`, `.runbar .rp`, `.runbar .mini`, `.runbar .total`, `.runbar .wait`, `.runbar .mini.ind*`, `.gap-*`, `.stale`, `.wtoast*`, `table.cmp` media.
  - **Change `.intrinsica .analyzer`** to `{ max-width: none; margin: 26px 0 0; }` and `.intrinsica .chips` to `justify-content: flex-start;` (keep its other declarations). **Change `.intrinsica .notice`** to `{ color: var(--neg); font-size: 14px; margin-top: 12px; }`.
  - **Add:**

```css
/* hero — promise + analyzer left, result card right (hero rework 2026-09-27) */
.intrinsica .hero { padding: 56px 0 48px; }
.intrinsica .hero-in { max-width: 1160px; margin: 0 auto; padding: 0 24px; display: grid; grid-template-columns: 1fr 1fr;
  gap: 48px; align-items: center; }
.intrinsica .hero-h1 { font: 700 48px/1.08 var(--fh); letter-spacing: -.03em; text-wrap: balance; }
.intrinsica .hero-sub { color: var(--dim); font-size: 17px; margin-top: 16px; max-width: 46ch; }
.intrinsica .an-micro { font-size: 13px; color: var(--mute); margin-top: 10px; }
@media (max-width: 900px) {
  .intrinsica .hero { padding: 32px 0 36px; }
  .intrinsica .hero-in { grid-template-columns: 1fr; gap: 26px; padding: 0 16px; }
  .intrinsica .hero-h1 { font-size: 34px; }
  .intrinsica .hero-sub { font-size: 15.5px; }
}
```

- [ ] **Step 10: Run the full frontend suite and the typecheck.**

```bash
npx tsc -b --force
npx vitest run
npx eslint src
```

Expected:
- tsc: no errors;
- vitest: all files pass. The old count was 331 tests in 16 files. The new count will differ: ResultGrid's 26 tests are removed, and roughly 50 are added.
- eslint: 6 problems (the baseline), no new ones.

If `funnel.test.tsx` fails, check whether it relied on a row button or on the auto-expanded breakdown. If so, open the breakdown with a tile click (`within(document.querySelector('.hero-r .rc')!).getByRole('button', { name: /^Quality/ })`) before asserting on it.

- [ ] **Step 11: Commit.**

```bash
git add -A frontend/src/landing
git status --short   # confirm: no backend/tests/__pycache__ entries staged
git commit -m "feat(landing): two-column hero with the live result card; grid removed

Hero: 'Judge the business. Then judge the price.' beside the result card;
wordmark heading, pipeline strip and assessment links gone. The card opens
the breakdown under the hero on a tile or row click — never by itself — and
a run with no rows keeps the previous card. Question band before the
Framework. No new analytics events.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Visual check in the real app, and branch memory

**Files:**
- No source changes unless the check finds a defect. If it does, fix it in the owning component or CSS and commit it separately.

- [ ] **Step 1: Start the app.** The backend runs on port 8000 and the frontend on port 5173 (`npx vite` in `frontend/`). If either is already running, reuse it.

- [ ] **Step 2: Take screenshots** of `http://localhost:5173/` with headless Chrome:
  - desktop, `--window-size=1440,1400`;
  - phone-width content: use Chrome DevTools device emulation, or a 390px iframe wrapper page. Plain headless `--window-size=390,…` does not narrow the layout reliably on Windows.
  - Compare them with `.superpowers/brainstorm/hero/own-run-v2.html` (desktop) and `hero-phone-v2.html` (phone).

- [ ] **Step 3: Check these by hand.**
  - The AAPL tiles are fully above the fold at 1440×900.
  - A tile click opens the dock directly under the hero.
  - The Compare chip gives three rows, a "Live example" pill and "3 tickers · N s".
  - On a phone the order is input, then card.
  - The comparison rows reflow into blocks.
  - The question band sits before "How Intrinsica works".
  - The tab-pair labels sit over the tabs, and stack in two rows on a phone.

- [ ] **Step 4: Run the backend suite once** to confirm nothing outside the landing folder moved. From `backend/`: `python -m pytest -q`. Expected: 688 passed.

- [ ] **Step 5: Report** the numbers (tests, tsc, eslint) and the screenshots to the user. Do not merge or push.

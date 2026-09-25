import { Fragment, type ReactNode } from 'react'
import type { TickerPayload } from '../types'
import { gapClass, money, num, pct } from '../format'

interface Props {
  rows: TickerPayload[]
  open: Record<string, boolean>
  onToggle: (ticker: string) => void
  renderBreakdown: (row: TickerPayload) => ReactNode
}

/** Units live in the header so the cells stay numeric (style B). Tier words such as
 *  "Balanced" belong in the breakdown, never here. */
const HEAD: { label: string; unit?: string }[] = [
  { label: 'Company' },
  { label: 'Quality', unit: '/10' },
  { label: 'Moat', unit: '/100' },
  { label: 'Fair Value' },
  { label: '% vs Price' },
  { label: 'Price' },
  { label: 'Reward/Risk', unit: '×' },
  { label: '' },
]

/** The highest finite value across a column, or null when there is nothing to
 *  single out. A column needs at least two DISTINCT finite values before any
 *  cell in it can be "best": when every row shows the same number, highlighting
 *  all of them reads as "all best" rather than "no standout", and a lone value
 *  among em dashes has nothing to be better than. Callers only use this in
 *  compare mode (more than one row). */
function bestOf(values: (number | null)[]): number | null {
  const finite = values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (new Set(finite).size < 2) return null
  return Math.max(...finite)
}

export default function ResultGrid({ rows, open, onToggle, renderBreakdown }: Props) {
  if (rows.length === 0) return null

  // Best-in-column highlight (spec 5.2) applies only in compare mode — more than
  // one ticker in the run, whether that came from a typed multi-ticker analysis
  // or the compare chip. A single row never highlights anything.
  const compare = rows.length > 1
  const bestQuality = compare ? bestOf(rows.map(r => r.quality?.score ?? null)) : null
  const bestMoat = compare ? bestOf(rows.map(r => r.moat?.score ?? null)) : null
  const bestGap = compare ? bestOf(rows.map(r => r.fair_value?.gap_pct ?? null)) : null
  const bestRR = compare ? bestOf(rows.map(r => r.reward_risk?.ratio ?? null)) : null

  const isBest = (v: number | null, best: number | null) =>
    compare && best !== null && v !== null && v === best

  return (
    <div className="tB">
      <table className="g">
        <thead>
          <tr>
            {HEAD.map(h => (
              <th key={h.label}>
                {h.label}
                {h.unit && <u> {h.unit}</u>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const isOpen = !!open[r.ticker]
            const quality = r.quality?.score ?? null
            const moat = r.moat?.score ?? null
            const gap = r.fair_value?.gap_pct ?? null
            const rr = r.reward_risk?.ratio ?? null
            return (
              <Fragment key={r.ticker}>
                <tr className={isOpen ? 'row open' : 'row'}
                    onClick={() => onToggle(r.ticker)}>
                  <td className="co">
                    {/* The whole row stays clickable for a mouse, but the
                        keyboard and screen-reader affordance is a real <button>
                        in the first cell rather than a role on the <tr>: a row
                        carrying role="button" stops being a row for assistive
                        technology and takes the cells with it. The button gets
                        Enter/Space and a focus ring for free, and its own click
                        is stopped from bubbling so a mouse click on the ticker
                        toggles once, not twice. */}
                    <button
                      type="button"
                      className="rowx"
                      aria-expanded={isOpen}
                      onClick={e => { e.stopPropagation(); onToggle(r.ticker) }}
                    >
                      <b>{r.ticker}</b>
                    </button>
                    <span className="cn">{r.company_name ?? ''}</span>
                  </td>
                  <td className={isBest(quality, bestQuality) ? 'best' : undefined}>
                    {num(quality, 1)}
                  </td>
                  <td className={isBest(moat, bestMoat) ? 'best' : undefined}>
                    {num(moat, 0)}
                  </td>
                  <td>{money(r.fair_value?.value ?? null)}</td>
                  <td className={
                    [gapClass(gap), isBest(gap, bestGap) ? 'best' : ''].filter(Boolean).join(' ')
                  }>
                    {pct(gap)}
                  </td>
                  <td>{money(r.price)}</td>
                  <td className={isBest(rr, bestRR) ? 'best' : undefined}>
                    {num(rr, 1)}
                  </td>
                  {/* Decoration only: the expanded/collapsed state is already
                      announced by the row button's aria-expanded, so the caret
                      would just add an unnamed glyph to the accessibility tree. */}
                  <td className="ex"><span aria-hidden="true">{isOpen ? '▴' : '▾'}</span></td>
                </tr>
                {isOpen && (
                  <tr className="exp">
                    <td colSpan={HEAD.length}>{renderBreakdown(r)}</td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

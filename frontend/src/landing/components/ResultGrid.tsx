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

/** The highest finite value across a column, or null when every row lacks it.
 *  Never invents a "best" from a single value — callers only use this in
 *  compare mode (more than one row). */
function bestOf(values: (number | null)[]): number | null {
  const finite = values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  return finite.length ? Math.max(...finite) : null
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
                    <b>{r.ticker}</b>
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
                  <td className="ex">{isOpen ? '▴' : '▾'}</td>
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

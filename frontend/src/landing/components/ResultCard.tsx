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

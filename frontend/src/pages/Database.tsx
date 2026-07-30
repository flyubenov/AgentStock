import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { TickerResult } from '../types'
import { fvGapColor, qualityScoreColor } from '../types'

const API = 'http://localhost:8000'

type SortKey = 'quality' | 'fair_value' | 'price_vs_fair_value_pct'

// ---- Filtering -------------------------------------------------------------

/** Sentinel checkbox value representing a null stock_type. */
const NONE = '(none)'

type ColKey = 'ticker' | 'stockType' | 'quality' | 'gap'
type NumRange = { min: number | null; max: number | null }
type Filters = {
  tickers: Set<string>
  stockTypes: Set<string>
  quality: NumRange
  gap: NumRange
}

const EMPTY_FILTERS: Filters = {
  tickers: new Set(),
  stockTypes: new Set(),
  quality: { min: null, max: null },
  gap: { min: null, max: null },
}

const rangeActive = (r: NumRange) => r.min != null || r.max != null

const inRange = (v: number | null | undefined, r: NumRange): boolean => {
  if (r.min == null && r.max == null) return true
  if (v == null) return false // a bound is set; a null value can't satisfy it
  if (r.min != null && v < r.min) return false
  if (r.max != null && v > r.max) return false
  return true
}

// ---- Header funnel + popover ----------------------------------------------

/** Funnel glyph; inherits the button's text color via currentColor. */
function FunnelIcon() {
  return (
    <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor" aria-hidden="true" className="inline-block align-middle">
      <path d="M2 3H14L9 9V13L7 12V9Z" />
    </svg>
  )
}

/**
 * A column header that renders its label plus a funnel toggle. The popover is
 * portalled to <body> with fixed positioning so the table's horizontal-scroll
 * container can't clip it. `data-colfilter` marks the button and the popover so
 * the outside-click handler can tell clicks inside a filter from clicks outside.
 */
function FilterHeader({
  label, active, open, align, onToggle, children,
}: {
  label: ReactNode
  active: boolean
  open: boolean
  align: 'left' | 'right'
  onToggle: () => void
  children: ReactNode
}) {
  const btnRef = useRef<HTMLButtonElement>(null)
  const [pos, setPos] = useState<{ top: number; left?: number; right?: number } | null>(null)

  useLayoutEffect(() => {
    if (open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      setPos(
        align === 'right'
          ? { top: r.bottom + 4, right: window.innerWidth - r.right }
          : { top: r.bottom + 4, left: r.left },
      )
    } else {
      setPos(null)
    }
  }, [open, align])

  return (
    <span data-colfilter className="relative inline-flex items-center gap-1">
      {label}
      <button
        ref={btnRef}
        onClick={onToggle}
        title="Filter"
        className={`p-0.5 rounded hover:bg-[#242433] ${active ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
      >
        <FunnelIcon />
      </button>
      {open && pos && createPortal(
        <div
          data-colfilter
          style={{ position: 'fixed', top: pos.top, left: pos.left, right: pos.right }}
          className="z-50 bg-[#16161e] border border-[#2a2a38] rounded-md shadow-xl p-2 text-left"
        >
          {children}
        </div>,
        document.body,
      )}
    </span>
  )
}

function MultiSelectFilter({
  options, selected, searchable, onChange,
}: {
  options: string[]
  selected: Set<string>
  searchable?: boolean
  onChange: (next: Set<string>) => void
}) {
  const [q, setQ] = useState('')
  const shown = searchable && q.trim()
    ? options.filter(o => o.toLowerCase().includes(q.trim().toLowerCase()))
    : options
  const toggle = (o: string) => {
    const n = new Set(selected)
    if (n.has(o)) n.delete(o); else n.add(o)
    onChange(n)
  }
  return (
    <div className="w-56">
      {searchable && (
        <input
          autoFocus
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search…"
          className="w-full mb-1 px-2 py-1 text-xs bg-[#0f0f16] border border-[#2a2a38] rounded text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500"
        />
      )}
      <div className="flex justify-between text-[11px] text-slate-500 mb-1 px-1">
        <button className="hover:text-slate-300" onClick={() => onChange(new Set(options))}>Select all</button>
        <button className="hover:text-slate-300" onClick={() => onChange(new Set())}>Clear</button>
      </div>
      <div className="max-h-60 overflow-y-auto">
        {shown.length === 0 ? (
          <div className="text-xs text-slate-600 px-1 py-2">No matches</div>
        ) : shown.map(o => (
          <label key={o} className="flex items-center gap-2 px-1 py-0.5 text-xs text-slate-300 hover:bg-[#1a1a24] rounded cursor-pointer">
            <input type="checkbox" checked={selected.has(o)} onChange={() => toggle(o)} className="accent-blue-500" />
            <span className="font-mono truncate">{o}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

function RangeFilter({
  value, step, onChange,
}: {
  value: NumRange
  step?: string
  onChange: (next: NumRange) => void
}) {
  const parse = (s: string): number | null => {
    if (s.trim() === '') return null
    const n = Number(s)
    return Number.isFinite(n) ? n : null
  }
  const box = 'w-24 px-2 py-1 text-xs bg-[#0f0f16] border border-[#2a2a38] rounded text-slate-200 focus:outline-none focus:border-blue-500'
  return (
    <div className="w-44 flex flex-col gap-2">
      <label className="flex items-center gap-2 text-xs text-slate-400">
        <span className="w-4 text-right">≥</span>
        <input type="number" step={step} value={value.min ?? ''} placeholder="min"
          onChange={e => onChange({ ...value, min: parse(e.target.value) })} className={box} />
      </label>
      <label className="flex items-center gap-2 text-xs text-slate-400">
        <span className="w-4 text-right">≤</span>
        <input type="number" step={step} value={value.max ?? ''} placeholder="max"
          onChange={e => onChange({ ...value, max: parse(e.target.value) })} className={box} />
      </label>
      <button
        onClick={() => onChange({ min: null, max: null })}
        className="self-end text-[11px] text-slate-500 hover:text-slate-300"
      >
        Clear
      </button>
    </div>
  )
}

// ---- Page ------------------------------------------------------------------

export default function Database() {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [recalcAll, setRecalcAll] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('price_vs_fair_value_pct')
  const [sortAsc, setSortAsc] = useState(false)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [openFilter, setOpenFilter] = useState<ColKey | null>(null)
  const navigate = useNavigate()

  const toggleFilter = (k: ColKey) => setOpenFilter(prev => (prev === k ? null : k))

  // Close the open popover on outside-click or Escape.
  useEffect(() => {
    if (!openFilter) return
    const onDown = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('[data-colfilter]')) setOpenFilter(null)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpenFilter(null) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [openFilter])

  // Distinct value lists for the multi-selects, sorted, from loaded rows.
  const tickerOptions = useMemo(
    () => [...new Set(results.map(r => r.ticker))].sort(),
    [results],
  )
  const stockTypeOptions = useMemo(
    () => [...new Set(results.map(r => r.stock_type ?? NONE))].sort(),
    [results],
  )

  const colActive = {
    ticker: filters.tickers.size > 0,
    stockType: filters.stockTypes.size > 0,
    quality: rangeActive(filters.quality),
    gap: rangeActive(filters.gap),
  }
  const anyActive = Object.values(colActive).some(Boolean)
  const clearAll = () => setFilters(EMPTY_FILTERS)

  const rowMatches = (r: TickerResult): boolean => {
    if (filters.tickers.size && !filters.tickers.has(r.ticker)) return false
    if (filters.stockTypes.size && !filters.stockTypes.has(r.stock_type ?? NONE)) return false
    if (!inRange(r.quality_score, filters.quality)) return false
    if (!inRange(r.price_vs_fair_value_pct, filters.gap)) return false
    return true
  }

  const sortVal = (r: TickerResult, key: SortKey): number | null => {
    if (key === 'quality') return r.quality_score ?? null
    return r[key] ?? null
  }
  const filtered = results.filter(rowMatches)
  const sorted = [...filtered].sort((a, b) => {
    const av = sortVal(a, sortKey) ?? (sortAsc ? Infinity : -Infinity)
    const bv = sortVal(b, sortKey) ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/database`)
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResults(data.results)
    } catch {
      setError('Failed to load database. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const recalcOne = async (ticker: string) => {
    setBusy(ticker)
    try {
      await fetch(`${API}/api/ticker/${ticker}/recalculate`, { method: 'POST' })
      await load()
    } catch {
      setError(`Failed to recalculate ${ticker}. Is the backend running?`)
    } finally {
      setBusy(null)
    }
  }

  const removeOne = async (ticker: string, name?: string | null) => {
    const label = name ? `${ticker} (${name})` : ticker
    if (!confirm(`Delete ${label} from the database?\n\nIts Fair Value and Screener records are removed permanently and it will no longer be recalculated.`)) return
    setBusy(ticker)
    try {
      const res = await fetch(`${API}/api/database/${ticker}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResults(prev => prev.filter(r => r.ticker !== ticker))
    } catch {
      setError(`Failed to delete ${ticker}. Is the backend running?`)
    } finally {
      setBusy(null)
    }
  }

  const recalcEverything = async () => {
    setRecalcAll(true)
    try {
      const res = await fetch(`${API}/api/recalculate-all`, { method: 'POST' })
      const data = await res.json()
      if (data.error) setError(data.error)
      else if (data.job_id) navigate(`/progress/${data.job_id}`, { state: { total: data.total } })
    } catch {
      setError('Failed to start recalculate-all. Is the backend running?')
    } finally {
      setRecalcAll(false)
    }
  }

  if (loading) return (
    <div className="text-slate-500 text-center py-20 animate-pulse">Loading database...</div>
  )

  if (error) return (
    <div className="text-red-400 text-center py-20">{error}</div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">
          Database — {anyActive ? `${sorted.length} of ${results.length}` : results.length} records
        </h1>
        <div className="flex items-center gap-2">
          {anyActive && (
            <button
              onClick={clearAll}
              className="text-sm text-blue-400 hover:text-blue-300 border border-[#1e1e2a] px-3 py-1.5 rounded"
            >
              Clear filters
            </button>
          )}
          <button
            onClick={recalcEverything}
            disabled={recalcAll}
            className="text-sm text-slate-300 hover:text-white border border-[#1e1e2a] px-3 py-1.5 rounded disabled:opacity-50"
          >
            {recalcAll ? 'Starting…' : 'Recalculate All'}
          </button>
          <button
            onClick={load}
            className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded"
          >
            Refresh
          </button>
        </div>
      </div>

      {results.length === 0 ? (
        <div className="text-slate-500 text-center py-20">
          No records yet. <Link to="/" className="text-blue-400">Run a calculation</Link>.
        </div>
      ) : (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
                <th className="text-left py-2 px-4">
                  <FilterHeader
                    label={<span>Ticker</span>}
                    active={colActive.ticker}
                    open={openFilter === 'ticker'}
                    align="left"
                    onToggle={() => toggleFilter('ticker')}
                  >
                    <MultiSelectFilter
                      options={tickerOptions}
                      selected={filters.tickers}
                      searchable
                      onChange={s => setFilters(f => ({ ...f, tickers: s }))}
                    />
                  </FilterHeader>
                </th>
                <th className="text-left py-2">Company</th>
                <th className="text-left py-2 px-2">
                  <FilterHeader
                    label={<span>Stock Type</span>}
                    active={colActive.stockType}
                    open={openFilter === 'stockType'}
                    align="left"
                    onToggle={() => toggleFilter('stockType')}
                  >
                    <MultiSelectFilter
                      options={stockTypeOptions}
                      selected={filters.stockTypes}
                      onChange={s => setFilters(f => ({ ...f, stockTypes: s }))}
                    />
                  </FilterHeader>
                </th>
                <th className="text-right py-2 px-2">
                  <FilterHeader
                    label={<span className="cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('quality')}>Quality</span>}
                    active={colActive.quality}
                    open={openFilter === 'quality'}
                    align="right"
                    onToggle={() => toggleFilter('quality')}
                  >
                    <RangeFilter value={filters.quality} step="0.1" onChange={v => setFilters(f => ({ ...f, quality: v }))} />
                  </FilterHeader>
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('fair_value')}>Fair Value</th>
                <th className="text-right py-2 px-2">Price</th>
                <th className="text-right py-2 px-4">
                  <FilterHeader
                    label={<span className="cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('price_vs_fair_value_pct')}>Gap%</span>}
                    active={colActive.gap}
                    open={openFilter === 'gap'}
                    align="right"
                    onToggle={() => toggleFilter('gap')}
                  >
                    <RangeFilter value={filters.gap} step="1" onChange={v => setFilters(f => ({ ...f, gap: v }))} />
                  </FilterHeader>
                </th>
                <th className="text-right py-2 px-4">Evaluated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4">
                    <Link
                      to={`/ticker/db/${r.ticker}`}
                      state={{ result: r }}
                      className="font-mono font-semibold text-blue-400 hover:text-blue-300"
                    >
                      {r.ticker}
                    </Link>
                  </td>
                  <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                  <td className="py-2 px-2 text-xs text-slate-500 font-mono">{r.stock_type || '—'}</td>
                  <td className={`py-2 px-2 text-right font-mono text-xs ${qualityScoreColor(r.quality_score)}`}>
                    {r.quality_score != null ? r.quality_score.toFixed(1) : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                    {r.fair_value != null ? `$${r.fair_value.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                    {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                  </td>
                  <td className={`py-2 px-4 text-right font-mono text-xs ${fvGapColor(r.price_vs_fair_value_pct)}`}>
                    {r.price_vs_fair_value_pct != null
                      ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="py-2 px-4 text-right text-xs text-slate-600">
                    {r.last_evaluated ? new Date(r.last_evaluated).toLocaleDateString() : '—'}
                  </td>
                  <td className="py-2 px-2 text-right whitespace-nowrap">
                    <button
                      onClick={() => recalcOne(r.ticker)}
                      disabled={busy === r.ticker}
                      title="Recalculate Fair Value + Screener"
                      className="text-xs text-slate-500 hover:text-blue-400 disabled:opacity-50"
                    >
                      {busy === r.ticker ? '…' : '↻'}
                    </button>
                    <button
                      onClick={() => removeOne(r.ticker, r.company_name)}
                      disabled={busy === r.ticker}
                      title="Delete from database — stops it being recalculated"
                      className="ml-3 text-xs text-slate-600 hover:text-red-400 disabled:opacity-50"
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

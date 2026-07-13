import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvGapColor, qualityScoreColor } from '../types'

const API = 'http://localhost:8000'

type SortKey = 'quality' | 'fair_value' | 'price_vs_fair_value_pct'

export default function Database() {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [recalcAll, setRecalcAll] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('price_vs_fair_value_pct')
  const [sortAsc, setSortAsc] = useState(false)
  const navigate = useNavigate()

  const sortVal = (r: TickerResult, key: SortKey): number | null => {
    if (key === 'quality') return r.quality_score ?? null
    return r[key] ?? null
  }
  const sorted = [...results].sort((a, b) => {
    const av = sortVal(a, sortKey) ?? (sortAsc ? Infinity : -Infinity)
    const bv = sortVal(b, sortKey) ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }
  const arrow = (key: SortKey) => (sortKey === key ? (sortAsc ? ' ▲' : ' ▼') : '')

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
        <h1 className="text-xl font-bold text-slate-100">Database — {results.length} records</h1>
        <div className="flex items-center gap-2">
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
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-left py-2 px-2">Stock Type</th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('quality')}>Quality{arrow('quality')}</th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('fair_value')}>Fair Value{arrow('fair_value')}</th>
                <th className="text-right py-2 px-2">Price</th>
                <th className="text-right py-2 px-4 cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('price_vs_fair_value_pct')}>Gap%{arrow('price_vs_fair_value_pct')}</th>
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
                  <td className="py-2 px-2 text-right">
                    <button
                      onClick={() => recalcOne(r.ticker)}
                      disabled={busy === r.ticker}
                      title="Recalculate Fair Value + Screener"
                      className="text-xs text-slate-500 hover:text-blue-400 disabled:opacity-50"
                    >
                      {busy === r.ticker ? '…' : '↻'}
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

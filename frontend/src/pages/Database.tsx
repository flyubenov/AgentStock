import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TickerResult, scoreToColor } from '../types'
import ScoreBadge from '../components/ScoreBadge'

const API = 'http://localhost:8000'

const SCORE_COLS = [
  { key: 'buffett_munger_score' as const, label: 'B-M' },
  { key: 'lynch_garp_score' as const, label: 'Lynch' },
  { key: 'growth_analyzer_score' as const, label: 'Growth' },
  { key: 'business_engine_score' as const, label: 'Biz Eng' },
  { key: 'canslim_score' as const, label: 'CAN' },
  { key: 'pre_screener_score' as const, label: 'Screen' },
]

export default function Database() {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        <button
          onClick={load}
          className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded"
        >
          Refresh
        </button>
      </div>

      {results.length === 0 ? (
        <div className="text-slate-500 text-center py-20">
          No records yet. <Link to="/" className="text-blue-400">Run an analysis</Link>.
        </div>
      ) : (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-right py-2 px-2">Score</th>
                {SCORE_COLS.map(c => (
                  <th key={c.key} className="text-right py-2 px-2">{c.label}</th>
                ))}
                <th className="text-right py-2 px-2">FV</th>
                <th className="text-right py-2 px-2">Price</th>
                <th className="text-right py-2 px-4">Gap%</th>
                <th className="text-right py-2 px-4">Evaluated</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
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
                  <td className="py-2 px-2 text-right">
                    <ScoreBadge score={r.overall_final_score} size="sm" />
                  </td>
                  {SCORE_COLS.map(c => (
                    <td key={c.key} className={`py-2 px-2 text-right font-mono text-xs ${scoreToColor(r[c.key])}`}>
                      {r[c.key]?.toFixed(2) ?? '—'}
                    </td>
                  ))}
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                    {r.blended_fair_value != null ? `$${r.blended_fair_value.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                    {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                  </td>
                  <td className={`py-2 px-4 text-right font-mono text-xs ${r.price_vs_fair_value_pct != null && r.price_vs_fair_value_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {r.price_vs_fair_value_pct != null
                      ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="py-2 px-4 text-right text-xs text-slate-600">
                    {r.last_evaluated ? new Date(r.last_evaluated).toLocaleDateString() : '—'}
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

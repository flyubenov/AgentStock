import { useState } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import ScoreBadge from '../components/ScoreBadge'
import { TickerResult, scoreToColor } from '../types'

const AGENT_COLS = [
  { key: 'buffett_munger_score' as const, label: 'B-M' },
  { key: 'lynch_garp_score' as const, label: 'Lynch' },
  { key: 'growth_analyzer_score' as const, label: 'Growth' },
  { key: 'business_engine_score' as const, label: 'Biz Eng' },
  { key: 'canslim_score' as const, label: 'CAN' },
  { key: 'pre_screener_score' as const, label: 'Screen' },
]

type SortKey = 'overall_final_score' | 'price_vs_fair_value_pct' | 'ticker'

export default function Results() {
  const { jobId } = useParams()
  const location = useLocation()
  const results: TickerResult[] = location.state?.results || []
  const [sortKey, setSortKey] = useState<SortKey>('overall_final_score')
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...results].sort((a, b) => {
    const av = a[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    const bv = b[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const exportCSV = () => {
    const headers = ['Ticker', 'Company', 'Score', 'B-M', 'Lynch', 'Growth', 'Biz Eng', 'CANSLIM', 'Screen', 'Blended FV', 'Price', 'FV Gap%']
    const rows = sorted.map(r => [
      r.ticker, r.company_name, r.overall_final_score,
      r.buffett_munger_score, r.lynch_garp_score, r.growth_analyzer_score,
      r.business_engine_score, r.canslim_score, r.pre_screener_score,
      r.blended_fair_value, r.current_price, r.price_vs_fair_value_pct,
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'results.csv'; a.click()
  }

  if (!results.length) return (
    <div className="text-slate-500 text-center py-20">
      No results. <Link to="/" className="text-blue-400">Run a new analysis</Link>.
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Results — {results.length} tickers</h1>
        <button onClick={exportCSV} className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded">
          Export CSV
        </button>
      </div>
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
              <th className="text-left py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('ticker')}>Ticker</th>
              <th className="text-left py-2">Company</th>
              <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('overall_final_score')}>Score</th>
              {AGENT_COLS.map(c => <th key={c.key} className="text-right py-2 px-2">{c.label}</th>)}
              <th className="text-right py-2 px-2">Blended FV</th>
              <th className="text-right py-2 px-2">Price</th>
              <th className="text-right py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('price_vs_fair_value_pct')}>FV Gap%</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => (
              <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                <td className="py-2 px-4">
                  <Link to={`/ticker/${jobId}/${r.ticker}`} state={{ result: r }} className="font-mono font-semibold text-blue-400 hover:text-blue-300">
                    {r.ticker}
                  </Link>
                </td>
                <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                <td className="py-2 px-2 text-right"><ScoreBadge score={r.overall_final_score} /></td>
                {AGENT_COLS.map(c => (
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
                  {r.price_vs_fair_value_pct != null ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

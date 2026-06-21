import { useState } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvGapColor, fvGapLabel } from '../types'

type SortKey = 'fair_value' | 'price_vs_fair_value_pct' | 'ticker'

export default function Results() {
  const { jobId } = useParams()
  const location = useLocation()
  const results: TickerResult[] = location.state?.results || []
  const [sortKey, setSortKey] = useState<SortKey>('price_vs_fair_value_pct')
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
    const headers = ['Ticker', 'Company', 'Stock Type', 'Fair Value', 'Price', 'FV Gap%', 'Verdict']
    const rows = sorted.map(r => [
      r.ticker, r.company_name, r.stock_type,
      r.fair_value, r.current_price, r.price_vs_fair_value_pct,
      fvGapLabel(r.price_vs_fair_value_pct),
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'fair_values.csv'; a.click()
  }

  if (!results.length) return (
    <div className="text-slate-500 text-center py-20">
      No results. <Link to="/" className="text-blue-400">Run a new calculation</Link>.
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Fair Values — {results.length} tickers</h1>
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
              <th className="text-left py-2 px-2">Stock Type</th>
              <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('fair_value')}>Fair Value</th>
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
                <td className="py-2 px-2 text-xs text-slate-500 font-mono">{r.stock_type || '—'}</td>
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                  {r.fair_value != null ? `$${r.fair_value.toFixed(2)}` : '—'}
                </td>
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                  {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                </td>
                <td className={`py-2 px-4 text-right font-mono text-xs ${fvGapColor(r.price_vs_fair_value_pct)}`}>
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

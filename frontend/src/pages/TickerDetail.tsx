import { useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvBadgeClass, fvGapLabel } from '../types'
import FairValuePanel from '../components/FairValuePanel'

export default function TickerDetail() {
  const location = useLocation()
  const result: TickerResult | undefined = location.state?.result

  if (!result) {
    return (
      <div className="text-slate-500 text-center py-20">
        Result not found. <Link to="/" className="text-blue-400">Go home</Link>.
      </div>
    )
  }

  const verdict = fvGapLabel(result.price_vs_fair_value_pct)

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-4">
        <button
          onClick={() => window.history.back()}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          ← Back
        </button>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold font-mono text-slate-100">{result.ticker}</h1>
            <p className="text-slate-400 mt-0.5">{result.company_name || '—'}</p>
            <p className="text-xs text-slate-600 mt-1">
              {result.stock_type || '—'}{result.last_evaluated ? ` · ${result.last_evaluated}` : ''}
            </p>
          </div>
          <div className="text-right">
            {verdict && (
              <span className={`rounded font-mono font-semibold inline-flex items-center px-3 py-1.5 text-sm ${fvBadgeClass(result.price_vs_fair_value_pct)}`}>
                {verdict}
              </span>
            )}
            <div className="text-slate-300 font-mono mt-2">
              FV {result.fair_value != null ? `$${result.fair_value.toFixed(2)}` : '—'}
            </div>
            {result.current_price != null && (
              <div className="text-slate-500 font-mono text-sm">Price ${result.current_price.toFixed(2)}</div>
            )}
          </div>
        </div>
      </div>

      <FairValuePanel result={result} />

      {result.errors.length > 0 && (
        <div className="mt-6 bg-red-900/10 border border-red-900/50 rounded-lg p-4">
          <p className="text-xs text-red-400 font-semibold mb-2">Errors</p>
          <ul className="text-xs text-red-300 space-y-1">
            {result.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

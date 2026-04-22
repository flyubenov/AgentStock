import { useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import AgentCard from '../components/AgentCard'
import FairValuePanel from '../components/FairValuePanel'

const AGENTS = ['buffett_munger', 'lynch_garp', 'growth_stock', 'business_engine', 'canslim', 'pre_screener']

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
            <p className="text-xs text-slate-600 mt-1">{result.last_evaluated}</p>
          </div>
          <div className="text-right">
            <ScoreBadge score={result.overall_final_score} size="lg" showLabel />
            {result.overall_label && (
              <div className="text-xs text-slate-500 mt-1">{result.overall_label}</div>
            )}
            {result.current_price != null && (
              <div className="text-slate-300 font-mono mt-2">${result.current_price.toFixed(2)}</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {AGENTS.map(key => (
          <AgentCard key={key} agentName={key} result={result.agent_results[key] ?? null} />
        ))}
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

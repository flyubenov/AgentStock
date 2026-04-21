import { useState } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import AgentCard from '../components/AgentCard'
import FairValuePanel from '../components/FairValuePanel'

const AGENTS = ['buffett_munger', 'lynch_garp', 'growth_stock', 'business_engine', 'canslim', 'pre_screener']

export default function TickerDetail() {
  const { jobId, ticker } = useParams()
  const location = useLocation()
  const result: TickerResult | undefined = location.state?.result
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)

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
        <Link
          to={jobId && jobId !== 'db' ? `/results/${jobId}` : '/database'}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          ← Back to results
        </Link>
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

      <div className="mb-6">
        <FairValuePanel result={result} />
      </div>

      <div className="space-y-2">
        <h2 className="text-xs text-slate-500 uppercase tracking-wide mb-3">Agent Reports</h2>
        {AGENTS.map(key => {
          const ar = result.agent_results[key]
          if (!ar?.report) return null
          return (
            <div key={key} className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedAgent(expandedAgent === key ? null : key)}
                className="w-full text-left px-4 py-3 flex justify-between items-center hover:bg-[#1a1a24]"
              >
                <span className="text-sm text-slate-300 capitalize">{key.replace(/_/g, ' ')}</span>
                <span className="text-slate-600 text-lg">{expandedAgent === key ? '−' : '+'}</span>
              </button>
              {expandedAgent === key && (
                <div className="px-4 pb-4 text-xs text-slate-400 whitespace-pre-wrap leading-relaxed border-t border-[#1e1e2a] pt-3">
                  {ar.report}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

import type { AgentResult } from '../types'
import ScoreBadge from './ScoreBadge'
import { cn } from '../lib/utils'

interface AgentCardProps {
  agentName: string
  result: AgentResult | null
  isLoading?: boolean
}

const AGENT_LABELS: Record<string, string> = {
  buffett_munger: 'Buffett-Munger',
  lynch_garp: 'Lynch GARP',
  growth_stock: 'Growth Stock',
  business_engine: 'Business Engine',
  canslim: 'CANSLIM',
  pre_screener: 'Pre-Screener',
}

export default function AgentCard({ agentName, result, isLoading }: AgentCardProps) {
  const label = AGENT_LABELS[agentName] || agentName

  if (isLoading) {
    return (
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-[#1e1e2a] rounded w-32 mb-2" />
        <div className="h-8 bg-[#1e1e2a] rounded w-16" />
      </div>
    )
  }

  if (!result) return null

  return (
    <div
      className={cn(
        'bg-[#16161e] border rounded-lg p-4',
        result.status === 'failed' ? 'border-red-900' : 'border-[#1e1e2a]'
      )}
    >
      <div className="text-xs text-slate-500 mb-1 uppercase tracking-wide">{label}</div>
      {result.status === 'failed' ? (
        <div className="text-red-400 text-sm">Failed</div>
      ) : (
        <>
          <ScoreBadge score={result.normalised_score} size="lg" />
          {result.recommendation && (
            <div className="text-xs text-slate-400 mt-1">{result.recommendation}</div>
          )}
          {result.rationale && (
            <div className="text-xs text-slate-500 mt-1 italic leading-snug">
              {result.rationale}
            </div>
          )}
        </>
      )}
    </div>
  )
}

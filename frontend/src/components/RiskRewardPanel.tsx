import type { RiskRewardResult } from '../types'
import { riskRewardBadgeClass, riskRewardTier } from '../types'

/** Order the metric rows reward-axis-first, then risk-axis, then any extras. */
const REWARD_SLOTS = ['valuation', 'growth', 'profitability', 'analyst_upside', 'discount', 'rsi']
const RISK_SLOTS = ['leverage', 'burn', 'liquidity', 'volatility', 'trend', 'beta']  // matches config.RISK_SLOTS order

function fmt(v: number | null, digits = 2): string {
  return v == null ? '—' : v.toFixed(digits)
}

export default function RiskRewardPanel({ result }: { result: RiskRewardResult }) {
  if (result.status === 'insufficient_data') {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        Not enough covered metrics to compute a Risk-Reward rating for this ticker.
      </div>
    )
  }
  if (result.status === 'failed' || result.ratio == null) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        No Risk-Reward data for this ticker yet.
      </div>
    )
  }

  const slots = [...REWARD_SLOTS, ...RISK_SLOTS]
  const known = new Set(slots)
  const rows = [
    ...slots.filter(s => result.metric_scores[s]),
    ...Object.keys(result.metric_scores).filter(s => !known.has(s)),
  ]

  return (
    <div className="space-y-6">
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-3xl font-bold font-mono text-slate-100">{fmt(result.ratio)}</div>
            <div className="text-xs text-slate-500 mt-1">Reward ÷ Risk</div>
          </div>
          <span className={`rounded font-mono font-semibold inline-flex items-center px-3 py-1.5 text-sm ${riskRewardBadgeClass(result.ratio)}`}>
            {result.tier || riskRewardTier(result.ratio)}
          </span>
        </div>
        <div className="flex gap-8 mt-4 text-sm font-mono">
          <div><span className="text-slate-500">Reward </span><span className="text-green-400">{fmt(result.reward_score)}</span><span className="text-slate-600"> /5</span></div>
          <div><span className="text-slate-500">Risk </span><span className="text-red-400">{fmt(result.risk_score)}</span><span className="text-slate-600"> /5</span></div>
        </div>
        {result.actionable_insight && (
          <p className="text-sm text-slate-400 mt-4">{result.actionable_insight}</p>
        )}
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
              <th className="text-left py-2 px-4">Metric</th>
              <th className="text-left py-2 px-2">Source</th>
              <th className="text-right py-2 px-2">Raw</th>
              <th className="text-right py-2 px-2">Score</th>
              <th className="text-right py-2 px-4">Weight</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(slot => {
              const m = result.metric_scores[slot]
              return (
                <tr key={slot} className={`border-b border-[#1e1e2a] ${m.dropped ? 'opacity-40' : ''}`}>
                  <td className="py-2 px-4 text-slate-300 font-mono text-xs">{slot}</td>
                  <td className="py-2 px-2 text-slate-500 font-mono text-xs">{m.source || '—'}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">{fmt(m.raw)}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">{m.dropped ? '—' : fmt(m.score, 1)}</td>
                  <td className="py-2 px-4 text-right font-mono text-xs text-slate-500">{(m.weight * 100).toFixed(0)}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

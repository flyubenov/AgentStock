import type { FairValueResult, TickerResult } from '../types'

interface FairValuePanelProps {
  result: TickerResult
  compact?: boolean
}

function FVRow({ label, result }: { label: string; result: FairValueResult | undefined }) {
  if (!result) return null
  return (
    <tr className="border-b border-[#1e1e2a]">
      <td className="py-2 pr-4 text-slate-400 text-sm">{label}</td>
      <td className="py-2 pr-4 text-right font-mono">
        {result.pre_mos_value != null ? `$${result.pre_mos_value.toFixed(2)}` : '—'}
      </td>
      <td className="py-2 text-right font-mono text-blue-400">
        {result.post_mos_value != null ? `$${result.post_mos_value.toFixed(2)}` : '—'}
      </td>
    </tr>
  )
}

export default function FairValuePanel({ result }: FairValuePanelProps) {
  const fvGemini = result.fair_value_results['gemini_fv']
  const fvCalc1 = result.fair_value_results['calculator_1']
  const fvCalc2 = result.fair_value_results['calculator_2']

  const gapPct = result.price_vs_fair_value_pct
  const gapColor = gapPct == null ? 'text-slate-400'
    : gapPct > 10 ? 'text-green-400'
    : gapPct > 0 ? 'text-blue-400'
    : gapPct > -10 ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-3">Fair Value</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1e1e2a]">
            <th className="text-left py-1 text-xs text-slate-600 font-normal">Method</th>
            <th className="text-right py-1 text-xs text-slate-600 font-normal">Pre-MOS</th>
            <th className="text-right py-1 text-xs text-slate-600 font-normal">Post-MOS</th>
          </tr>
        </thead>
        <tbody>
          <FVRow label="Gemini FV" result={fvGemini} />
          <FVRow label="Calculator 1" result={fvCalc1} />
          <FVRow label="Calculator 2" result={fvCalc2} />
        </tbody>
      </table>
      <div className="mt-3 pt-3 border-t border-[#1e1e2a] flex justify-between items-center">
        <div>
          <div className="text-xs text-slate-500">Blended Fair Value</div>
          <div className="text-lg font-mono text-slate-200">
            {result.blended_fair_value != null ? `$${result.blended_fair_value.toFixed(2)}` : '—'}
          </div>
        </div>
        {gapPct != null && (
          <div className="text-right">
            <div className="text-xs text-slate-500">vs Current Price</div>
            <div className={`text-lg font-mono ${gapColor}`}>
              {gapPct > 0 ? '+' : ''}{gapPct.toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

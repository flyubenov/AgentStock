import type { TickerResult, ModelBreakdown } from '../types'
import { METHOD_LABELS, fvGapColor } from '../types'

interface FairValuePanelProps {
  result: TickerResult
}

function money(v: number | null | undefined): string {
  return v != null ? `$${v.toFixed(2)}` : '—'
}

function ModelRow({ id, model }: { id: string; model: ModelBreakdown }) {
  const s = model.scenarios || { optimistic: null, realistic: null, pessimistic: null }
  return (
    <tr className="border-b border-[#1e1e2a]">
      <td className="py-2 pr-4 text-slate-400 text-sm">
        {METHOD_LABELS[id] ?? id}
        {model.is_approx && <span className="ml-1 text-[10px] text-amber-500 uppercase">approx</span>}
      </td>
      <td className="py-2 pr-4 text-right font-mono text-xs text-slate-500">{((model.weight ?? 0) * 100).toFixed(0)}%</td>
      <td className="py-2 pr-4 text-right font-mono text-blue-400">{money(model.fair_value)}</td>
      <td className="py-2 text-right font-mono text-xs text-slate-500">
        {money(s.pessimistic)} / {money(s.realistic)} / {money(s.optimistic)}
      </td>
    </tr>
  )
}

export default function FairValuePanel({ result }: FairValuePanelProps) {
  const entries = Object.entries(result.fair_value_breakdown || {})
  const gapPct = result.price_vs_fair_value_pct

  return (
    <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-3">
        Fair Value Breakdown{result.stock_type ? ` — ${result.stock_type}` : ''}
      </div>
      {entries.length === 0 ? (
        <div className="text-sm text-slate-500">No models resolved for this ticker.</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a]">
              <th className="text-left py-1 text-xs text-slate-600 font-normal">Model</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Weight</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Fair Value</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Pess / Real / Opt</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([id, model]) => <ModelRow key={id} id={id} model={model} />)}
          </tbody>
        </table>
      )}
      <div className="mt-3 pt-3 border-t border-[#1e1e2a] flex justify-between items-center">
        <div>
          <div className="text-xs text-slate-500">Composite Fair Value</div>
          <div className="text-lg font-mono text-slate-200">{money(result.fair_value)}</div>
        </div>
        {gapPct != null && (
          <div className="text-right">
            <div className="text-xs text-slate-500">vs Current Price</div>
            <div className={`text-lg font-mono ${fvGapColor(gapPct)}`}>
              {gapPct > 0 ? '+' : ''}{gapPct.toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

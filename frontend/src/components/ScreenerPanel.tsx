import type { ScreenerResult } from '../types'
import { qualityScoreColor, qualityScoreBadgeClass } from '../types'

const SECTIONS: [string, string][] = [
  ['I', 'Growth & Trajectory'],
  ['II', 'Capital Efficiency'],
  ['III', 'Balance Sheet'],
  ['IV', 'Dilution & Quality'],
]

// [field, label, format] — grouped by section for display
const METRIC_GROUPS: { title: string; rows: [string, string, 'pct' | 'ratio' | 'money'][] }[] = [
  { title: 'I · Growth & Trajectory', rows: [
    ['revenue_cagr_3y', 'Revenue CAGR 3Y', 'pct'],
    ['eps_cagr_3y', 'EPS CAGR 3Y', 'pct'],
    ['fcf_cagr_3y', 'FCF CAGR 3Y', 'pct'],
    ['fcf_margin', 'FCF Margin', 'pct'],
    ['op_margin', 'Operating Margin', 'pct'],
    ['op_margin_trajectory', 'Op Margin Δ (pp)', 'pct'],
    ['gross_margin', 'Gross Margin', 'pct'],
  ]},
  { title: 'II · Capital Efficiency', rows: [
    ['roic_ttm', 'ROIC (TTM)', 'pct'],
    ['roic_5y_avg', 'ROIC 5Y avg', 'pct'],
    ['wacc', 'WACC', 'pct'],
    ['roic_wacc_spread', 'ROIC − WACC (pp)', 'pct'],
    ['rote', 'ROTE', 'pct'],
  ]},
  { title: 'III · Balance Sheet', rows: [
    ['net_debt_ebitda', 'Net Debt / EBITDA', 'ratio'],
    ['net_debt_fcf', 'Net Debt / FCF', 'ratio'],
    ['ocf_capex', 'OCF / CapEx', 'ratio'],
    ['tangible_bv_per_share', 'Tangible BV / Share', 'money'],
  ]},
  { title: 'IV · Dilution & Quality', rows: [
    ['shares_cagr_3y', 'Shares CAGR 3Y', 'pct'],
    ['sbc_pct_rev', 'SBC % of Revenue', 'pct'],
    ['earnings_quality', 'Earnings Quality (OCF/NI)', 'ratio'],
    ['insider_ownership', 'Insider Ownership', 'pct'],
    ['shareholder_yield', 'Shareholder Yield', 'pct'],
  ]},
  { title: 'V · Valuation (reference — not scored)', rows: [
    ['trailing_pe', 'Trailing P/E', 'ratio'],
    ['forward_pe', 'Forward P/E', 'ratio'],
    ['peg', 'PEG', 'ratio'],
    ['price_fcf', 'Price / FCF', 'ratio'],
    ['price_sales', 'Price / Sales', 'ratio'],
    ['fcf_yield', 'FCF Yield (FCF/EV)', 'pct'],
    ['owner_earnings_yield', 'Owner Earnings Yield vs 10Y', 'pct'],
    ['price_cagr_3y', 'Price CAGR 3Y', 'pct'],
    ['price_cagr_5y', 'Price CAGR 5Y', 'pct'],
  ]},
]

function fmt(v: number | null | undefined, kind: 'pct' | 'ratio' | 'money'): string {
  if (v == null) return '—'
  if (kind === 'pct') return `${v.toFixed(1)}%`
  if (kind === 'money') return `$${v.toFixed(2)}`
  return v.toFixed(2)
}

export default function ScreenerPanel({ result }: { result: ScreenerResult }) {
  const m = result.metrics || {}
  const sections = result.section_scores || {}

  return (
    <div className="space-y-6">
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wide">Business Quality Score</div>
          <div className={`text-4xl font-mono font-bold mt-1 ${qualityScoreColor(result.quality_score)}`}>
            {result.quality_score != null ? result.quality_score.toFixed(1) : '—'}
            <span className="text-lg text-slate-600">/10</span>
          </div>
          <div className="text-xs text-slate-600 mt-2">
            {result.sector || '—'}{result.sector_profile ? ` · ${result.sector_profile}` : ''}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {SECTIONS.map(([key, label]) => (
            <div key={key} className="text-right">
              <span className="text-[11px] text-slate-500">{label}</span>
              <span className={`ml-2 font-mono text-sm px-2 py-0.5 rounded ${qualityScoreBadgeClass(sections[key])}`}>
                {sections[key] != null ? sections[key]!.toFixed(1) : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {METRIC_GROUPS.map(group => (
        <div key={group.title} className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">{group.title}</div>
          <table className="w-full text-sm">
            <tbody>
              {group.rows.map(([field, label, kind]) => (
                <tr key={field} className="border-b border-[#1e1e2a] last:border-0">
                  <td className="py-1.5 text-slate-400">{label}</td>
                  <td className="py-1.5 text-right font-mono text-slate-300">
                    {fmt(m[field] as number | null | undefined, kind)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {result.errors && result.errors.length > 0 && (
        <div className="bg-amber-900/10 border border-amber-900/50 rounded-lg p-4">
          <p className="text-xs text-amber-400 font-semibold mb-2">Screener notes</p>
          <ul className="text-xs text-amber-300 space-y-1">
            {result.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

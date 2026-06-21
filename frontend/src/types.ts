export interface ModelBreakdown {
  weight: number
  fair_value: number
  scenarios: {
    optimistic: number | null
    realistic: number | null
    pessimistic: number | null
  }
  is_approx: boolean
}

export interface TickerResult {
  ticker: string
  company_name: string | null
  current_price: number | null
  last_evaluated: string | null
  stock_type: string | null
  fair_value: number | null
  price_vs_fair_value_pct: number | null
  fair_value_breakdown: Record<string, ModelBreakdown>
  status: 'completed' | 'failed'
  errors: string[]
}

export interface JobStatus {
  job_id: string
  total: number
  completed: number
  failed: number
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  results: TickerResult[]
}

/** Display labels for model ids, matching backend valuation/models.ALL_METHODS. */
export const METHOD_LABELS: Record<string, string> = {
  dcf: 'DCF (FCFF)',
  fcfe: 'FCFE DCF',
  ev_ebitda: 'EV/EBITDA',
  ev_sales: 'EV/Sales',
  pe: 'P/E',
  ddm: 'DDM',
  rim: 'RIM',
  pb: 'P/B',
  sotp: 'SOTP',
  nav: 'NAV',
}

export type ValuationLabel = 'Undervalued' | 'Fairly valued' | 'Overvalued'

/** price_vs_fair_value_pct > 0 means fair value exceeds price (undervalued). */
export function fvGapLabel(pct: number | null): ValuationLabel | null {
  if (pct == null) return null
  if (pct > 10) return 'Undervalued'
  if (pct < -10) return 'Overvalued'
  return 'Fairly valued'
}

export function fvGapColor(pct: number | null): string {
  if (pct == null) return 'text-slate-400'
  if (pct > 10) return 'text-green-400'
  if (pct > 0) return 'text-blue-400'
  if (pct > -10) return 'text-yellow-400'
  return 'text-red-400'
}

export function fvBadgeClass(pct: number | null): string {
  if (pct == null) return 'bg-slate-800 text-slate-300'
  if (pct > 10) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (pct > 0) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (pct > -10) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}

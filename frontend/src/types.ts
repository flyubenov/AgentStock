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
  quality_score?: number | null
  screener?: ScreenerResult | null
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

export interface ScreenerMetrics {
  revenue_cagr_3y: number | null
  eps_cagr_3y: number | null
  fcf_cagr_3y: number | null
  fcf_margin: number | null
  op_margin: number | null
  op_margin_trajectory: number | null
  gross_margin: number | null
  roic_ttm: number | null
  roic_5y_avg: number | null
  wacc: number | null
  roic_wacc_spread: number | null
  rote: number | null
  net_debt_ebitda: number | null
  net_debt_fcf: number | null
  ocf_capex: number | null
  tangible_bv_per_share: number | null
  shares_cagr_3y: number | null
  sbc_pct_rev: number | null
  earnings_quality: number | null
  insider_ownership: number | null
  shareholder_yield: number | null
  trailing_pe: number | null
  forward_pe: number | null
  peg: number | null
  price_fcf: number | null
  price_sales: number | null
  fcf_yield: number | null
  owner_earnings_yield: number | null
  price_cagr_3y: number | null
  price_cagr_5y: number | null
  [key: string]: number | null | string | undefined
}

export interface PreProfitBreakdown {
  applied: boolean
  rule_of_40: number | null
  runway_months: number | 'inf' | null
  growth_score: number | null
  blend_weight: number
  capped: boolean
}

export interface SectorAdjustment {
  profile: string
  excluded: string[]
  note: string
}

export interface ScoreBreakdown {
  fundamentals_composite?: number
  section_weights?: Record<string, number>
  pre_profit?: PreProfitBreakdown | null
  sector_adjustment?: SectorAdjustment
  final?: number
}

export interface ScreenerResult {
  ticker: string
  company_name: string | null
  last_evaluated: string | null
  quality_score: number | null
  sector: string | null
  sector_profile: string | null
  section_scores: Record<string, number | null>
  metrics: Partial<ScreenerMetrics>
  score_breakdown?: ScoreBreakdown
  status: 'completed' | 'failed'
  errors: string[]
}

/** 1-10 quality score -> text color band. */
export function qualityScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-slate-400'
  if (score >= 8) return 'text-green-400'
  if (score >= 6.5) return 'text-blue-400'
  if (score >= 5) return 'text-yellow-400'
  return 'text-red-400'
}

export function qualityScoreBadgeClass(score: number | null | undefined): string {
  if (score == null) return 'bg-slate-800 text-slate-300'
  if (score >= 8) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (score >= 6.5) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (score >= 5) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}

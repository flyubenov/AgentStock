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
  moat_score?: number | null                 // mirrored number — Database grid (persisted rows)
  screener?: ScreenerResult | null
  risk_reward?: RiskRewardResult | null      // nested object — Results grid + detail
  risk_reward_ratio?: number | null          // mirrored number — Database grid
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
  capex_adjustment?: SectorAdjustment
  roic_adjustment?: SectorAdjustment
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
  moat_score?: number | null                 // nested — live Results/Progress grids
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

/** 0-100 moat score -> text color band (gate ceiling is 35). */
export function moatScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-slate-400'
  if (score >= 70) return 'text-green-400'
  if (score >= 50) return 'text-blue-400'
  if (score >= 35) return 'text-yellow-400'
  return 'text-red-400'
}

export interface RiskRewardMetricScore {
  raw: number | null
  source: string | null
  score: number | null
  weight: number
  dropped: boolean
}

export interface RiskRewardResult {
  ticker: string
  company_name: string | null
  last_evaluated: string | null
  ratio: number | null
  tier: string | null
  reward_score: number | null
  risk_score: number | null
  actionable_insight: string | null
  metric_scores: Record<string, RiskRewardMetricScore>
  raw_snapshot: Record<string, number | null>
  status: 'completed' | 'insufficient_data' | 'failed'
  errors: string[]
}

/** The Results grid carries the nested object; the Database grid carries the
 *  mirrored number. One helper reads whichever is present. */
export function riskRewardRatio(
  r: { risk_reward?: RiskRewardResult | null; risk_reward_ratio?: number | null },
): number | null {
  return r.risk_reward?.ratio ?? r.risk_reward_ratio ?? null
}

/** Live grids carry moat nested under screener; the Database grid carries the
 *  mirrored top-level number. One helper reads whichever is present. */
export function moatScore(
  r: { moat_score?: number | null; screener?: ScreenerResult | null },
): number | null {
  return r.moat_score ?? r.screener?.moat_score ?? null
}

export function riskRewardTier(ratio: number | null | undefined): string | null {
  if (ratio == null) return null
  if (ratio >= 2.0) return 'Asymmetric Upside'
  if (ratio >= 1.3) return 'Reward-Favored'
  if (ratio >= 0.8) return 'Balanced'
  if (ratio >= 0.5) return 'Risk-Favored'
  return 'Value Trap'
}

export function riskRewardColor(ratio: number | null | undefined): string {
  if (ratio == null) return 'text-slate-400'
  if (ratio >= 2.0) return 'text-green-400'
  if (ratio >= 1.3) return 'text-blue-400'
  if (ratio >= 0.8) return 'text-yellow-400'
  return 'text-red-400'
}

export function riskRewardBadgeClass(ratio: number | null | undefined): string {
  if (ratio == null) return 'bg-slate-800 text-slate-300'
  if (ratio >= 2.0) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (ratio >= 1.3) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (ratio >= 0.8) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}

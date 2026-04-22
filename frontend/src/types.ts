export interface AgentResult {
  agent_name: string
  ticker: string
  raw_score: number | null
  normalised_score: number | null
  recommendation: string | null
  rationale: string | null
  raw_response: string
  report: string
  status: 'completed' | 'failed'
  error: string | null
}

export interface FairValueResult {
  ticker: string
  method_name: string
  pre_mos_value: number | null
  post_mos_value: number | null
  methods_breakdown: Record<string, unknown>
  data_sources: string[]
  status: 'completed' | 'failed'
  error: string | null
}

export interface TickerResult {
  ticker: string
  company_name: string | null
  current_price: number | null
  last_evaluated: string | null
  buffett_munger_score: number | null
  lynch_garp_score: number | null
  growth_analyzer_score: number | null
  business_engine_score: number | null
  canslim_score: number | null
  pre_screener_score: number | null
  overall_final_score: number | null
  overall_label: string | null
  fair_value_gemini: number | null
  fair_value_calculator_1: number | null
  fair_value_calculator_2: number | null
  blended_fair_value: number | null
  price_vs_fair_value_pct: number | null
  agent_results: Record<string, AgentResult>
  fair_value_results: Record<string, FairValueResult>
  status: 'completed' | 'partial' | 'failed'
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

export interface BatchRequestCounts {
  processing: number
  succeeded: number
  errored: number
  total: number
}

export interface BatchJobStatus {
  job_id: string
  status: 'in_progress' | 'ended' | 'canceling' | 'canceled'
  submitted_at: string
  failed_prefetch: string[]
  request_counts: BatchRequestCounts
}

export interface BatchJobResults {
  job_id: string
  ticker_results: TickerResult[]
  failed_prefetch: string[]
}

export type ScoreLabel = 'Strong Buy' | 'Buy' | 'Hold / Watch' | 'Underperform' | 'Sell / Avoid'

export function scoreToLabel(score: number | null): ScoreLabel | null {
  if (score == null) return null
  if (score >= 4.5) return 'Strong Buy'
  if (score >= 3.5) return 'Buy'
  if (score >= 2.5) return 'Hold / Watch'
  if (score >= 1.5) return 'Underperform'
  return 'Sell / Avoid'
}

export function scoreToColor(score: number | null): string {
  if (score == null) return 'text-slate-400'
  if (score >= 4.5) return 'text-green-500'
  if (score >= 3.5) return 'text-blue-500'
  if (score >= 2.5) return 'text-yellow-500'
  if (score >= 1.5) return 'text-orange-500'
  return 'text-red-500'
}

export function scoreToBgColor(score: number | null): string {
  if (score == null) return 'bg-slate-800 text-slate-300'
  if (score >= 4.5) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (score >= 3.5) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (score >= 2.5) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  if (score >= 1.5) return 'bg-orange-900/40 text-orange-400 border border-orange-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}

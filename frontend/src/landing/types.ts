/** Mirrors backend/landing/contract.py — keep the two in step. */
export interface MetricRow {
  label: string
  raw: number | null
  score: number | null
  weight_pct: number
  excluded: boolean
  excluded_by: string | null
}

export interface QualityCategory {
  key: 'I' | 'II' | 'III' | 'IV'
  name: string
  weight_pct: number
  score: number | null
  metrics: MetricRow[]
}

export interface QualityBlock {
  score: number | null
  /** The section-weighted composite before any pre-profit blend or unprofitable cap.
   *  This is what `categories` actually rolls up to; `score` is the published
   *  headline, which can legitimately diverge from it. Null when the engine never
   *  reached the composite step. */
  fundamentals_composite: number | null
  profile_label: string | null
  categories: QualityCategory[]
}

export interface MoatBlock {
  score: number | null
  gated: boolean
  excluded: string[]
  factors: { label: string; points: number | null; max_points: number; weight_pct: number }[]
}

export interface FairValueBlock {
  value: number | null
  gap_pct: number | null
  type_label: string | null
  methods: { label: string; value: number | null; weight_pct: number; contribution: number | null }[]
}

export interface RewardRiskFactor {
  label: string
  raw: number | null
  score: number | null
  weight_pct: number
  dropped: boolean
}

export interface RewardRiskBlock {
  ratio: number | null
  tier: string | null
  reward_score: number | null
  risk_score: number | null
  reward: RewardRiskFactor[]
  risk: RewardRiskFactor[]
}

export interface TickerPayload {
  ticker: string
  company_name: string | null
  price: number | null
  quality: QualityBlock | null
  moat: MoatBlock | null
  fair_value: FairValueBlock | null
  reward_risk: RewardRiskBlock | null
  calibrations: string[]
  errors: string[]
}

export interface AnalyzeResponse {
  results: TickerPayload[]
  invalid: string[]
  error: string | null
}

/** The four assessments, in page order. Index doubles as the framework tab id. */
export type AssessmentId = 0 | 1 | 2 | 3

/** Where an analyze run came from. 'sample' is the mount auto-run and the
 *  compare chip — served from cache, marketing content, never counted against
 *  the demo limit. 'typed' is a visitor's own analysis and is the only source
 *  that consumes an allowance (see demoLimit.ts). Declared here so the page and
 *  the Hero that calls it cannot drift apart. */
export type AnalyzeSource = 'sample' | 'typed'

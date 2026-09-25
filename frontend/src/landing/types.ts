/** Mirrors backend/landing/contract.py — keep the two in step. */
export interface MetricRow {
  label: string
  raw: number | null
  /** `raw` in its own unit, ready to print ("32%", "0.4×", "Net cash") —
   *  backend/landing/figures.py. Null when there is no figure. */
  display: string | null
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

export interface MoatFactor {
  label: string
  /** Magnitude, Durability or Cash-backing — the three pillar groups. */
  group: string
  /** The input the pillar was scored from, formatted ("55%", "9 of 10 yrs"). */
  display: string | null
  points: number | null
  max_points: number
  weight_pct: number
}

export interface MoatBlock {
  score: number | null
  gated: boolean
  excluded: string[]
  factors: MoatFactor[]
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
  /** Formatted by the source that scored the slot ("ROE 149%", "β 1.08"). */
  display: string | null
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

/** Which of the two sites fired `free_plan_clicked`. The event is the only one
 *  on the site that fires from two places — the pricing CTA and the checkout's
 *  confirm button — and spec section 9's event list is closed, so the stages are
 *  told apart by a prop rather than by a second name (the same move
 *  `analysis_started` makes with AnalyzeSource above). Declared here because two
 *  separate files have to spell these two words identically or the free funnel
 *  silently splits into three buckets.
 *
 *  Only free_plan_clicked carries it. plan_selected and payment_button_clicked
 *  each fire from exactly one site, and the paid funnel's stages are already
 *  distinct event names; a prop that can hold only one value would carry no
 *  information and would imply a fire site that does not exist. */
export type FreeClickSource = 'pricing' | 'checkout'

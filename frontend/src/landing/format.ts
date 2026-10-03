import type { TickerPayload } from './types'

/** Every absent, non-finite or engine-declined value renders as an em dash. A grid
 *  cell must never show NaN, Infinity or "null". */
export const DASH = '—'

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

export function money(v: number | null): string {
  return finite(v) ? `$${v.toFixed(2)}` : DASH
}

export function num(v: number | null, dp = 1): string {
  return finite(v) ? v.toFixed(dp) : DASH
}

export function pct(v: number | null): string {
  if (!finite(v)) return DASH
  // The sign comes from the ROUNDED value, not the raw one: -0.04 rounds to
  // 0.0, and "-0.0%" reads as a bug on a page whose whole pitch is that every
  // number is checkable. Anything that rounds to zero prints unsigned.
  const text = v.toFixed(1)
  // Number('-0.0') is -0, and -0 === 0, so this catches both signed zeroes.
  if (Number(text) === 0) return '0.0%'
  return `${Number(text) > 0 ? '+' : ''}${text}%`
}

/** A metric's underlying figure for the breakdown's Data column. Unlike `num`
 *  this cannot take a fixed decimal count: the same column carries margins
 *  (0.08), multiples (55.2) and ratios (-3.43), and any single precision is
 *  wrong for one of them. Four significant digits, with the trailing zeros
 *  dropped — the backend does not round `raw`, so the alternative is printing
 *  0.08123456789 on a page whose pitch is that every number is checkable.
 *
 *  `String(Number(...))` switches to exponent notation outside roughly
 *  1e-6 … 1e21, so figure(5e-7) is "5e-7". That is deliberate and pinned in
 *  format.test.ts rather than clamped: no metric the contract emits (margins,
 *  multiples, ratios, leverage) comes near either bound, and at a magnitude
 *  that did, both fixed alternatives read worse than the exponent — "0.0000005"
 *  is a column of leading zeros and 1e21 fixed is a 22-digit integer. The
 *  em-dash guarantee is unaffected: an exponent string is still a real number,
 *  never NaN, Infinity or "null". */
export function figure(v: number | null): string {
  if (!finite(v)) return DASH
  // -0 === 0, so this catches both signed zeroes before toPrecision can turn
  // one of them into "-0.000".
  if (v === 0) return '0'
  return String(Number(v.toPrecision(4)))
}

/** A weight or share of a category: unsigned, and without the decimal point a
 *  whole number does not need. `pct` is the wrong tool — it always signs and
 *  always prints one decimal, so a 35% category weight would read "+35.0%". */
export function weight(v: number | null): string {
  if (!finite(v)) return DASH
  return `${Number.isInteger(v) ? String(v + 0) : v.toFixed(1)}%`
}

/** Spec section 5.2: >= +10% green, 0..+10% blue, -10..0 amber, < -10% red. */
export function gapClass(v: number | null): string {
  if (!finite(v)) return 'gap-none'
  if (v >= 10) return 'gap-pos'
  if (v >= 0) return 'gap-near'
  if (v >= -10) return 'gap-warn'
  return 'gap-neg'
}

/** Whole dollars — the mock's headline form for fair value ("$193"). The exact
 *  blended figure still appears, to the cent, on the breakdown's total row. */
export function dollars(v: number | null): string {
  return finite(v) ? `$${Math.round(v)}` : DASH
}

/** The fair-value gap as the grid shows it: signed, whole percent ("+5%", "−44%"). */
export function gapPct(v: number | null): string {
  if (!finite(v)) return DASH
  const r = Math.round(v)
  if (r === 0) return '0%'
  return `${r > 0 ? '+' : '−'}${Math.abs(r)}%`
}

/** The result card's Fair Value caption (spec 5.2). `gap_pct` is measured against the
 *  price, so the sentence is about where fair value sits relative to the price —
 *  "Price 53% above fair value" would silently change the base of the percentage. */
export function fvCaption(v: number | null): string {
  if (!finite(v)) return DASH
  const r = Math.round(v)
  if (r === 0) return 'Fair value at price'
  return `Fair value ${Math.abs(r)}% ${r > 0 ? 'above' : 'below'} price`
}

/** The outcome bands the framework section publishes (spec 5.4 item 4), read back
 *  onto one score. These are the public bands, never a metric's scoring cut-off. */
export function qualityTier(v: number | null): string | null {
  if (!finite(v)) return null
  if (v >= 9) return 'Top-decile'
  if (v >= 8) return 'Excellent'
  if (v >= 7) return 'Strong'
  if (v >= 5) return 'Moderate'
  return 'Weak'
}

/** Moat tiers on the 0–10 scale (spec §5.2, 2026-09-29). */
export function moatTier(v: number | null): string | null {
  if (!finite(v)) return null
  if (v >= 8) return 'Wide'
  if (v >= 6) return 'Established'
  if (v >= 4) return 'Narrow'
  return 'Little or none'
}

/** Reward/Risk tiers, highest first — risk_reward/config.py's tier ladder. */
export const RR_TIERS = ['Asymmetric Upside', 'Reward-Favored', 'Balanced', 'Risk-Favored', 'Value Trap'] as const

/** A result worth featuring or sharing: at least one of the four assessments came
 *  back. A ticker that does not exist, or that the engines could not compute (BRK.B
 *  before the Yahoo-symbol fix: "Could not be computed"), comes back as a row with
 *  every block null. The /t/ link flow and the Share buttons both use this. */
export function computed(r: TickerPayload): boolean {
  return Boolean(r.quality || r.moat || r.fair_value || r.reward_risk)
}

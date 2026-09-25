/** Every absent, non-finite or engine-declined value renders as an em dash. A grid
 *  cell must never show NaN, Infinity or "null". */
const DASH = '—'

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
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

/** Spec section 5.2: >= +10% green, 0..+10% blue, -10..0 amber, < -10% red. */
export function gapClass(v: number | null): string {
  if (!finite(v)) return 'gap-none'
  if (v >= 10) return 'gap-pos'
  if (v >= 0) return 'gap-near'
  if (v >= -10) return 'gap-warn'
  return 'gap-neg'
}

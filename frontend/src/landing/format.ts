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
  // The sign comes from the ROUNDED value, not the raw one: -0.04 rounds to
  // 0.0, and "-0.0%" reads as a bug on a page whose whole pitch is that every
  // number is checkable. Anything that rounds to zero prints unsigned.
  const text = v.toFixed(1)
  // Number('-0.0') is -0, and -0 === 0, so this catches both signed zeroes.
  if (Number(text) === 0) return '0.0%'
  return `${Number(text) > 0 ? '+' : ''}${text}%`
}

/** Spec section 5.2: >= +10% green, 0..+10% blue, -10..0 amber, < -10% red. */
export function gapClass(v: number | null): string {
  if (!finite(v)) return 'gap-none'
  if (v >= 10) return 'gap-pos'
  if (v >= 0) return 'gap-near'
  if (v >= -10) return 'gap-warn'
  return 'gap-neg'
}

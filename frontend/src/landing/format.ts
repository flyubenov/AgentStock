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
 *  0.08123456789 on a page whose pitch is that every number is checkable. */
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

/** Ticker-link normalisation (spec 2026-10-03 §3). Mirrors backend/landing/tickers.py;
 *  ticker-cases.json pins both. Canonical form uses a dot (BRK.B) because
 *  /api/landing/analyze validates that shape and rejects the dash form. */
const SHAPE = /^[A-Z]{1,5}([.-][A-Z]{1,2})?$/

export function normalizeTicker(raw: string): string | null {
  const t = raw.trim().toUpperCase()
  return SHAPE.test(t) ? t.replace('-', '.') : null
}

/** What the fallback notice calls a link it could not use. Never echoes markup. */
export function noticeLabel(raw: string): string {
  const t = normalizeTicker(raw)
  if (t) return t
  const cleaned = raw.toUpperCase().replace(/[^A-Z0-9.-]/g, '').slice(0, 12)
  return cleaned || 'that ticker'
}

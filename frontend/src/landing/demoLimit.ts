// The no-account demo limit. This module holds the allowance logic only — no
// rendering, no analytics. It caps the number of visitor-initiated analyses,
// not the tickers inside one (that's Hero's MAX_TICKERS).
//
// Soft and client-side by design (spec §10: "tracked client-side (soft,
// non-enforced; adequate for a fake door)"). No accounts, no fingerprinting,
// no server enforcement.
//
// Fail-open is the single most important behaviour here: if localStorage is
// unavailable or throws — Safari private mode, blocked site data, a quota
// error — the visitor is never blocked. Every read and write gets its own
// try/catch, following the exact pattern in ../lib/analytics.ts:33-51
// (visitorId), and any failure means "allowance not exhausted".

export const DEMO_RUN_LIMIT = 5
export const DEMO_WINDOW_DAYS = 30

const KEY = 'intrinsica_demo_runs'
const WINDOW_MS = DEMO_WINDOW_DAYS * 24 * 60 * 60 * 1000

interface DemoRunState {
  count: number
  windowStart: number
}

function isDemoRunState(value: unknown): value is DemoRunState {
  return (
    typeof value === 'object' && value !== null &&
    typeof (value as DemoRunState).count === 'number' &&
    typeof (value as DemoRunState).windowStart === 'number'
  )
}

/** Reads the raw stored state. Returns null on anything abnormal — missing key,
 *  a storage throw, or corrupt JSON — rather than letting a caller crash. */
function readState(): DemoRunState | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isDemoRunState(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** Best-effort write. A failure here is silently accepted: it just means this
 *  run goes untracked, which is the fail-open outcome we want anyway. */
function writeState(state: DemoRunState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    /* fail open: an unrecorded run costs nothing but a slightly generous demo */
  }
}

/** The state to reason about right now: a fresh window when nothing usable is
 *  stored, or the stored window has aged out. */
function currentState(): DemoRunState {
  const stored = readState()
  const now = Date.now()
  if (!stored || now - stored.windowStart >= WINDOW_MS) {
    return { count: 0, windowStart: now }
  }
  return stored
}

/** Runs used inside the current window. 0 when storage is unavailable. */
export function runsUsed(): number {
  return currentState().count
}

/** True when the visitor may still analyze. Always true if storage is
 *  unavailable — a broken counter must never lock out a real person. */
export function canAnalyze(): boolean {
  return currentState().count < DEMO_RUN_LIMIT
}

/** Record one typed run. No-op when storage is unavailable. Never throws.
 *  Sample runs (the mount auto-run, the future compare chip) must never call
 *  this — only a visitor-initiated analysis counts. */
export function recordRun(): void {
  const state = currentState()
  writeState({ count: state.count + 1, windowStart: state.windowStart })
}

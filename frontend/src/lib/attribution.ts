/** Where a visitor came from (launch checklist B1). Read once on arrival and sent
 *  with every funnel event, so the events sheet can be split by channel for the
 *  keep/stop rules (checklist B3).
 *
 *  `channel` is the visitor's FIRST arrival (user decision 2026-10-02): someone
 *  who clicks an X ad and comes back two days later by typing the address still
 *  counts toward X. `visit_channel` is this visit's own channel, kept beside it.
 *
 *  Only the referring DOMAIN is kept, never the full address: a search engine's
 *  address can carry what the person typed. */

export interface Touch {
  channel: string
  utm_source?: string
  utm_medium?: string
  utm_campaign?: string
  utm_content?: string
  ref?: string
  referrer?: string
  landing: string
}

export type Attribution = Touch & { visit_channel: string }

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'] as const
/** Stripped from the address bar after reading, so a visitor who copies the link
 *  doesn't pass an ad's tags on to the people they share it with. */
const STRIPPED = [...UTM_KEYS, 'utm_term', 'ref']
const FIRST_KEY = 'intrinsica_first_touch'
const VISIT_KEY = 'intrinsica_visit_touch'
const MAX_LEN = 100

/** Lowercase letters, digits and . _ - only, at most MAX_LEN characters. Anyone
 *  can hand-make a link, and these values end up as spreadsheet cells. */
function clean(value: string | null): string | undefined {
  if (!value) return undefined
  const out = value.toLowerCase().replace(/[^a-z0-9._-]+/g, '').slice(0, MAX_LEN)
  return out || undefined
}

function referringDomain(): string | undefined {
  try {
    if (!document.referrer) return undefined
    const url = new URL(document.referrer)
    if (url.host === window.location.host) return undefined
    return clean(url.hostname.replace(/^www\./, ''))
  } catch {
    return undefined
  }
}

/** This page load's own touch, from the address and the referrer. */
export function readTouch(): Touch {
  const params = new URLSearchParams(window.location.search)
  const touch: Touch = { channel: 'direct', landing: window.location.pathname.slice(0, MAX_LEN) }
  for (const key of UTM_KEYS) {
    const v = clean(params.get(key))
    if (v) touch[key] = v
  }
  const ref = clean(params.get('ref'))
  if (ref) touch.ref = ref
  const referrer = referringDomain()
  if (referrer) touch.referrer = referrer
  touch.channel = touch.utm_source ?? touch.ref ?? touch.referrer ?? 'direct'
  return touch
}

function load(storage: () => Storage, key: string): Touch | null {
  try {
    const raw = storage().getItem(key)
    return raw ? (JSON.parse(raw) as Touch) : null
  } catch {
    return null
  }
}

function save(storage: () => Storage, key: string, touch: Touch): void {
  try {
    storage().setItem(key, JSON.stringify(touch))
  } catch {
    /* blocked storage: the memoized values below still cover this page load */
  }
}

let cached: Attribution | null = null

/** Read the arrival, remember it, and clean the tags out of the address bar.
 *  Called from main.tsx before the first render; safe to call again. */
export function captureAttribution(): Attribution {
  if (cached) return cached
  const now = readTouch()
  // A tagged or referred arrival starts a new visit. An untagged load (a reload,
  // or opening /checkout in the same tab) keeps the visit's stored channel.
  const visit = now.channel !== 'direct' ? now : (load(() => sessionStorage, VISIT_KEY) ?? now)
  save(() => sessionStorage, VISIT_KEY, visit)
  let first = load(() => localStorage, FIRST_KEY)
  if (!first) {
    first = visit
    save(() => localStorage, FIRST_KEY, first)
  }
  cached = { ...first, visit_channel: visit.channel }

  try {
    const url = new URL(window.location.href)
    if (STRIPPED.some(k => url.searchParams.has(k))) {
      STRIPPED.forEach(k => url.searchParams.delete(k))
      window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
    }
  } catch {
    /* never block the page over a cosmetic address-bar cleanup */
  }
  return cached
}

/** The attribution sent with every event. */
export function attribution(): Attribution {
  return cached ?? captureAttribution()
}

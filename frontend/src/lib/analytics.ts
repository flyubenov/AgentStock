import { API_BASE } from './api'

/** The complete funnel event list (spec section 9). There is deliberately no
 *  scroll, hover, or billing-toggle event: the chosen billing period rides on
 *  plan_selected. */
export const EVENTS = Object.freeze({
  pageView: 'page_view',
  analysisStarted: 'analysis_started',
  analysisCompleted: 'analysis_completed',
  breakdownOpened: 'breakdown_opened',
  methodologyViewed: 'methodology_viewed',
  pricingViewed: 'pricing_viewed',
  planSelected: 'plan_selected',
  checkoutStarted: 'checkout_started',
  paymentButtonClicked: 'payment_button_clicked',
  emailSubmitted: 'email_submitted',
  /** Kept apart from the paid funnel on purpose — never counted in paid-intent
   *  conversion. */
  freePlanClicked: 'free_plan_clicked',
})

const KEY = 'intrinsica_vid'
let cached: string | null = null

function newId(): string {
  return `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/** A stable per-browser id. Private mode, cleared storage and blocked storage all
 *  degrade to a per-session id rather than throwing. */
export function visitorId(): string {
  if (cached) return cached
  try {
    const stored = localStorage.getItem(KEY)
    if (stored) {
      cached = stored
      return cached
    }
    cached = newId()
    localStorage.setItem(KEY, cached)
    return cached
  } catch {
    cached = cached ?? newId()
    return cached
  }
}

/** Fire-and-forget. Returns immediately and swallows every failure: a dead
 *  endpoint, an ad blocker or an offline browser must never break the funnel. */
export function track(event: string, props: Record<string, unknown> = {}): void {
  try {
    if (typeof fetch !== 'function') return
    void fetch(`${API_BASE}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event,
        visitor_id: visitorId(),
        ts: new Date().toISOString(),
        props,
      }),
      keepalive: true,
    }).catch(() => {})
  } catch {
    /* analytics is never load-bearing */
  }
}

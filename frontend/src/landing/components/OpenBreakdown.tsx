import { useEffect, useRef } from 'react'
import Breakdown from './Breakdown'
import type { AssessmentId, TickerPayload } from '../types'
import { X } from 'lucide-react'

/** The one place a breakdown opens (spec 5.3, hero rework 2026-09-27): full width,
 *  directly under the hero, whichever tile or row opened it. The panel itself is the
 *  unchanged Breakdown; this adds only its header, a Close, and a scroll that happens
 *  only when the dock opened below the fold — never a jump the visitor did not need. */
export default function OpenBreakdown({ row, tab, onTab, onClose }: {
  row: TickerPayload
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { top } = el.getBoundingClientRect()
    if (top > window.innerHeight - 80) el.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [row.ticker])

  return (
    <section ref={ref} className="bk-dock" aria-label={`${row.ticker} full breakdown`}>
      <div className="bk-in">
        <div className="bk-head">
          <b>{row.ticker}</b> {row.company_name ?? ''} · full breakdown
          <button type="button" className="bk-x" onClick={onClose}>Close <X size={14} aria-hidden="true" /></button>
        </div>
        <Breakdown row={row} tab={tab} onTab={onTab} />
      </div>
    </section>
  )
}

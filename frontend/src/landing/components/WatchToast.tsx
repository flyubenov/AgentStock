import { useEffect } from 'react'

/** How long the watchlist toast stays up unless dismissed (user decision). */
export const WATCH_TOAST_MS = 10_000

/** The answer to the watchlist star (spec section 9, `watchlist_clicked`). A fake
 *  door: it says a watchlist needs an account and points at the plans, never
 *  implying a watchlist or an account now exists. The clicked ticker travels on the
 *  analytics event, not in the copy.
 *
 *  A fixed toast rather than an inline message or a popover: it takes no room in
 *  the layout, so the grid never jumps, and nothing in a sideways-scrolling table
 *  can clip it. At phone width it spans the screen above the home indicator. The
 *  parent re-keys it on every click, which restarts the timer. */
export default function WatchToast({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const id = setTimeout(onClose, WATCH_TOAST_MS)
    return () => clearTimeout(id)
  }, [onClose])

  return (
    <div className="wtoast" role="status">
      <p>
        <b>Watchlists require an Intrinsica account.</b> Start with Free.
      </p>
      <a href="#pricing" onClick={onClose}>See plans →</a>
      <button type="button" className="x" aria-label="Dismiss" onClick={onClose}>✕</button>
    </div>
  )
}

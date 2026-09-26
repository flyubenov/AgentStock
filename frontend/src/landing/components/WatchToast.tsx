import { useEffect } from 'react'

/** How long the watchlist toast stays up unless dismissed (user decision). */
export const WATCH_TOAST_MS = 10_000

/** The answer to the watchlist star (spec section 9, `watchlist_clicked`). A fake
 *  door: it says plainly that nothing was saved and points at the plans, never
 *  implying a watchlist or an account now exists.
 *
 *  A fixed toast rather than an inline message or a popover: it takes no room in
 *  the layout, so the grid never jumps, and nothing in a sideways-scrolling table
 *  can clip it. At phone width it spans the screen above the home indicator. The
 *  parent re-keys it on every click, which restarts the timer. */
export default function WatchToast({ ticker, onClose }: {
  ticker: string
  onClose: () => void
}) {
  useEffect(() => {
    const id = setTimeout(onClose, WATCH_TOAST_MS)
    return () => clearTimeout(id)
  }, [onClose])

  return (
    <div className="wtoast" role="status">
      <p>
        <b>{ticker} not saved</b> — watchlists come with an Intrinsica account, and Free
        includes one.
      </p>
      <a href="#pricing" onClick={onClose}>See plans →</a>
      <button type="button" className="x" aria-label="Dismiss" onClick={onClose}>✕</button>
    </div>
  )
}

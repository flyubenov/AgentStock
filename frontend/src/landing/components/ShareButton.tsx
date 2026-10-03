import { useState, type MouseEvent } from 'react'
import { Share2 } from 'lucide-react'
import { track, EVENTS } from '../../lib/analytics'
import { shareText, shareUrl } from '../share'

/** Share one result (ticker links spec §6): the phone's own share sheet where there
 *  is one, otherwise copy the link. Fires share_clicked on the click itself.
 *  `label` is the visible text (default "Share"); `iconOnly` drops it for the
 *  compact comparison rows. The accessible name always names the stock. `place`
 *  rides on share_clicked so the three spots can be compared (user decision
 *  2026-10-03): the single-result footer, a comparison row, or the breakdown. */
export type SharePlace = 'card' | 'row' | 'breakdown'

export default function ShareButton({ ticker, place, label = 'Share', iconOnly = false }: {
  ticker: string; place: SharePlace; label?: string; iconOnly?: boolean
}) {
  const [state, setState] = useState<'idle' | 'copied' | 'manual'>('idle')
  const url = shareUrl(ticker)

  async function onClick(e: MouseEvent) {
    e.stopPropagation() // inside a clickable comparison row
    const native = typeof navigator.share === 'function'
    track(EVENTS.shareClicked, { ticker, method: native ? 'native' : 'copy', place })
    if (native) {
      try { await navigator.share({ title: `${ticker} on Intrinsica`, text: shareText(ticker), url }) }
      catch { /* cancelled or refused: nothing to say */ }
      return
    }
    try {
      await navigator.clipboard.writeText(url)
      setState('copied')
      setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('manual')
    }
  }

  return (
    <span className="share-wrap">
      <button type="button" className={iconOnly ? 'share icon' : 'share'} aria-label={`Share ${ticker}`} title="Share" onClick={onClick}>
        <Share2 size={14} strokeWidth={1.9} aria-hidden="true" />{!iconOnly && <span className="share-l">{label}</span>}
      </button>
      <span className="share-msg" aria-live="polite">{state === 'copied' ? 'Link copied' : ''}</span>
      {state === 'manual' && (
        <input className="share-url" readOnly value={url} aria-label="Link to copy"
               onFocus={e => e.currentTarget.select()} autoFocus
               onClick={e => e.stopPropagation()} />
      )}
    </span>
  )
}

import { useId } from 'react'
import { KEYHOLE, MARK } from './mark'

/** "Light through the keyhole", always fully lit. The head holds Quality |
 *  Moat and the slot holds Fair Value | Reward/Risk. It appears only as the
 *  logo and the favicon (spec §4), never on a result. */
export default function BrandMark({ size = 42 }: { size?: number }) {
  // useId keeps two marks on one page from sharing a gradient or clip id.
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const plate = `bm-p-${id}`, clip = `bm-k-${id}`
  return (
    <svg className="brandmark" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={plate} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={MARK.plateTop} />
          <stop offset="1" stopColor={MARK.plateBot} />
        </linearGradient>
        <clipPath id={clip}><path d={KEYHOLE} /></clipPath>
      </defs>
      <rect x="4" y="4" width="92" height="92" rx="22" fill={`url(#${plate})`} />
      <g clipPath={`url(#${clip})`}>
        <rect x="0" y="0" width="50" height="53" fill={MARK.q} />
        <rect x="50" y="0" width="50" height="53" fill={MARK.mo} />
        <rect x="0" y="53" width="50" height="47" fill={MARK.fv} />
        <rect x="50" y="53" width="50" height="47" fill={MARK.rr} />
      </g>
      <path d={KEYHOLE} fill="none" stroke={MARK.rim} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

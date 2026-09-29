import type { ReactNode } from 'react'

/** The mock's hover tooltip (`.tagwrap` / `.tip`). The wrapper is focusable and the
 *  tip is shown on focus as well as hover (theme.css), so a keyboard user reaches it
 *  too; the text is always in the DOM, which is also what a screen reader reads. */
export default function Tip({ label, tip, className = 'help' }: {
  label: ReactNode
  tip: string
  className?: string
}) {
  return (
    <span className="tagwrap" tabIndex={0}>
      <span className={className}>{label}</span>
      <span className="tip" role="tooltip">{tip}</span>
    </span>
  )
}

import { useEffect, useState } from 'react'

/** While a multi-ticker run is in flight the strip says so at once — every
 *  ticker's bar sweeps and the clock counts up (loading variant E, user decision
 *  2026-09-26). Since the 2026-09-27 hero rework it sits at the top of the result
 *  card. The backend answers all tickers in one response, so no ticker is ever
 *  shown as done before the others: the strip claims only what the page knows. */
export default function LiveRunBar({ tickers }: { tickers: string[] }) {
  const [ms, setMs] = useState(0)
  useEffect(() => {
    const t0 = Date.now()
    const id = setInterval(() => setMs(Date.now() - t0), 100)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="runbar live" role="status">
      <span className="rp wait">Computing in parallel:</span>
      {tickers.map(t => (
        <span key={t} className="rp">
          {t} <span className="mini ind" aria-hidden="true"><span /></span>
        </span>
      ))}
      <span className="rp total">{tickers.length} tickers · {(ms / 1000).toFixed(1)}s</span>
    </div>
  )
}

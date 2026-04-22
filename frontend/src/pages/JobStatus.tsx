import { useState, useEffect, useCallback } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import type { BatchJobStatus, BatchJobResults, TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'

const API = 'http://localhost:8000'
const POLL_INTERVAL_MS = 30_000

export default function JobStatus() {
  const { jobId } = useParams<{ jobId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [status, setStatus] = useState<BatchJobStatus | null>(null)
  const [results, setResults] = useState<TickerResult[] | null>(null)
  const [failedPrefetch, setFailedPrefetch] = useState<string[]>(
    location.state?.failedPrefetch ?? []
  )
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [cancelling, setCancelling] = useState(false)

  const fetchResults = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await fetch(`${API}/api/jobs/${jobId}/results`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BatchJobResults = await res.json()
      setResults(data.ticker_results)
      setFailedPrefetch(data.failed_prefetch)
    } catch (e) {
      setError(String(e))
    }
  }, [jobId])

  const fetchStatus = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await fetch(`${API}/api/jobs/${jobId}/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BatchJobStatus = await res.json()
      setStatus(data)
      setLastChecked(new Date())
      if (data.status === 'ended') {
        await fetchResults()
      }
    } catch (e) {
      setError(String(e))
    }
  }, [jobId, fetchResults])

  const handleCancel = async () => {
    if (!jobId || cancelling) return
    setCancelling(true)
    await fetch(`${API}/api/jobs/${jobId}`, { method: 'DELETE' })
    setCancelling(false)
    navigate('/')
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(() => {
      if (!results) fetchStatus()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchStatus, results])

  const progress = status?.request_counts
    ? Math.round(
        ((status.request_counts.succeeded + status.request_counts.errored) /
          Math.max(status.request_counts.total, 1)) *
          100
      )
    : 0

  const isDone = status?.status === 'ended' || status?.status === 'canceled'

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-xl font-bold text-slate-100 mb-1">Batch Job</h1>
      <p className="text-xs text-slate-500 font-mono mb-6">{jobId}</p>

      {!isDone && (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-300">
              {status ? (
                <>
                  {status.request_counts.succeeded + status.request_counts.errored} /{' '}
                  {status.request_counts.total} agent calls complete
                </>
              ) : (
                'Checking status...'
              )}
            </span>
            <span className="text-xs text-slate-500">{progress}%</span>
          </div>

          <div className="w-full bg-[#0a0a0f] rounded-full h-2 mb-4">
            <div
              className="bg-green-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          <p className="text-xs text-slate-500 mb-4">
            Batch jobs typically complete in 15–60 min. Submitted:{' '}
            {status?.submitted_at
              ? new Date(status.submitted_at).toLocaleTimeString()
              : '—'}
          </p>

          {error && (
            <div className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded px-3 py-2 mb-3">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={fetchStatus}
              className="px-4 py-2 text-sm bg-[#1e1e2a] hover:bg-[#2a2a3a] text-slate-300 rounded transition-colors"
            >
              Check now
            </button>
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="px-4 py-2 text-sm bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded transition-colors"
            >
              {cancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          </div>

          {lastChecked && (
            <p className="text-xs text-slate-600 mt-2">
              Last checked: {lastChecked.toLocaleTimeString()}
            </p>
          )}

          {status?.submitted_at && (() => {
            const elapsed = Date.now() - new Date(status.submitted_at).getTime()
            return elapsed > 2 * 60 * 60 * 1000 ? (
              <div className="mt-3 text-yellow-400 text-xs bg-yellow-900/20 border border-yellow-900/50 rounded px-3 py-2">
                This batch is taking longer than expected. You can wait or cancel and resubmit as Run now.
              </div>
            ) : null
          })()}
        </div>
      )}

      {failedPrefetch.length > 0 && (
        <div className="bg-red-900/10 border border-red-900/50 rounded-lg p-4 mb-6">
          <p className="text-xs text-red-400 font-semibold mb-1">
            Tickers aborted (yfinance data unavailable):
          </p>
          <p className="text-xs text-red-300 font-mono">{failedPrefetch.join(', ')}</p>
        </div>
      )}

      {results && (
        <div>
          <h2 className="text-lg font-semibold text-slate-200 mb-4">
            Results — {results.length} ticker{results.length !== 1 ? 's' : ''}
          </h2>
          <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e1e2a] text-xs text-slate-500 uppercase">
                  <th className="text-left px-4 py-3">Ticker</th>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Score</th>
                  <th className="text-right px-4 py-3">Price</th>
                  <th className="text-right px-4 py-3">FV Gap %</th>
                  <th className="text-left px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr
                    key={r.ticker}
                    className="border-b border-[#1e1e2a] hover:bg-[#1e1e2a] cursor-pointer"
                    onClick={() =>
                      navigate(`/ticker/batch/${r.ticker}`, { state: { result: r } })
                    }
                  >
                    <td className="px-4 py-3 font-mono font-bold text-slate-100">{r.ticker}</td>
                    <td className="px-4 py-3 text-slate-400 max-w-[180px] truncate">
                      {r.company_name ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={r.overall_final_score} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {r.price_vs_fair_value_pct != null ? (
                        <span
                          className={
                            r.price_vs_fair_value_pct > 0 ? 'text-green-400' : 'text-red-400'
                          }
                        >
                          {r.price_vs_fair_value_pct > 0 ? '+' : ''}
                          {r.price_vs_fair_value_pct.toFixed(1)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          r.status === 'completed'
                            ? 'bg-green-900/30 text-green-400'
                            : r.status === 'partial'
                            ? 'bg-yellow-900/30 text-yellow-400'
                            : 'bg-red-900/30 text-red-400'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

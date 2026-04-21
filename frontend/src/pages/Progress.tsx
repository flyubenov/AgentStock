import { useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useAnalysisStream } from '../hooks/useAnalysisStream'
import ProgressBar from '../components/ProgressBar'
import ScoreBadge from '../components/ScoreBadge'
import { cn } from '../lib/utils'

export default function Progress() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { status, total, completed, failed, results, tickerStatuses, cancel } = useAnalysisStream(jobId ?? null)

  useEffect(() => {
    if (status === 'completed') {
      navigate(`/results/${jobId}`, { state: { results } })
    }
  }, [status])

  const allTickers = Object.keys(tickerStatuses)
  const displayTotal = total || (location.state?.total ?? 0)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-100">Analysis in Progress</h1>
        <button
          onClick={cancel}
          className="text-sm text-red-400 hover:text-red-300 border border-red-900 px-3 py-1.5 rounded"
        >
          Cancel
        </button>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4 mb-6">
        <ProgressBar
          current={completed + failed}
          total={displayTotal}
          label={`Analysed ${completed + failed} / ${displayTotal} tickers`}
        />
        <div className="flex gap-4 mt-2 text-xs text-slate-500">
          <span className="text-green-400">{completed} completed</span>
          {failed > 0 && <span className="text-red-400">{failed} failed</span>}
          {status === 'running' && <span className="text-blue-400 animate-pulse">Running...</span>}
        </div>
      </div>

      {allTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {allTickers.map(ticker => {
            const s = tickerStatuses[ticker]
            return (
              <span key={ticker} className={cn(
                'px-2 py-1 rounded text-xs font-mono border',
                s === 'done' ? 'border-green-800 text-green-400 bg-green-900/20' :
                s === 'failed' ? 'border-red-800 text-red-400 bg-red-900/20' :
                s === 'running' ? 'border-blue-800 text-blue-400 bg-blue-900/20 animate-pulse' :
                'border-slate-800 text-slate-500'
              )}>
                {ticker}
              </span>
            )
          })}
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
          <div className="text-xs text-slate-500 uppercase tracking-wide px-4 py-2 border-b border-[#1e1e2a]">
            Live Results
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-600">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-right py-2 pr-4">Score</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4 font-mono font-semibold text-blue-400">{r.ticker}</td>
                  <td className="py-2 text-slate-400 text-xs">{r.company_name || '—'}</td>
                  <td className="py-2 pr-4 text-right">
                    <ScoreBadge score={r.overall_final_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

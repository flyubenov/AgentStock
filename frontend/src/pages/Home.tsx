import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000'
const MODE_KEY = 'analysis_mode'

export default function Home() {
  const [tickers, setTickers] = useState('')
  const [useSheets, setUseSheets] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'batch' | 'live'>(() => {
    return (localStorage.getItem(MODE_KEY) as 'batch' | 'live') ?? 'batch'
  })
  const navigate = useNavigate()

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  const handleAnalyse = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers
        .split(/[\s,]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean)

      const body: Record<string, unknown> = { mode }
      if (tickerList.length > 0) body.tickers = tickerList
      if (useSheets) body.sheets_url = 'from_sheets'

      const res = await fetch(`${API}/api/analyse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (data.error) {
        setError(data.error)
      } else if (data.mode === 'batch') {
        navigate(`/jobs/${data.job_id}`, {
          state: { total: data.total, invalid: data.invalid, failedPrefetch: data.failed_prefetch },
        })
      } else {
        navigate(`/progress/${data.job_id}`, { state: { total: data.total, invalid: data.invalid } })
      }
    } catch {
      setError('Failed to connect to backend. Is uvicorn running on port 8000?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Stock Analysis</h1>
      <p className="text-slate-500 text-sm mb-8">
        Enter up to 150 tickers for AI-powered analysis across 9 evaluation models.
      </p>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">
            Ticker Symbols (comma or space separated)
          </label>
          <textarea
            value={tickers}
            onChange={e => setTickers(e.target.value)}
            placeholder="AAPL, MSFT, GOOGL, NVDA..."
            className="w-full bg-[#0a0a0f] border border-[#1e1e2a] rounded px-3 py-2 text-slate-200 font-mono text-sm resize-none focus:outline-none focus:border-blue-700 h-24"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1 border-t border-[#1e1e2a]" />
          <span className="text-xs text-slate-600">OR</span>
          <div className="flex-1 border-t border-[#1e1e2a]" />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useSheets}
            onChange={e => setUseSheets(e.target.checked)}
            className="w-4 h-4 rounded border-slate-600 bg-[#0a0a0f]"
          />
          <span className="text-sm text-slate-300">Load tickers from Google Sheets</span>
        </label>

        {/* Mode toggle */}
        <div>
          <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">
            Analysis Mode
          </label>
          <div className="flex rounded overflow-hidden border border-[#1e1e2a]">
            <button
              onClick={() => setMode('live')}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === 'live'
                  ? 'bg-blue-700 text-white'
                  : 'bg-[#0a0a0f] text-slate-400 hover:text-slate-200'
              }`}
            >
              ⚡ Run now
            </button>
            <button
              onClick={() => setMode('batch')}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === 'batch'
                  ? 'bg-green-800 text-white'
                  : 'bg-[#0a0a0f] text-slate-400 hover:text-slate-200'
              }`}
            >
              💰 Batch — cheaper
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            {mode === 'batch'
              ? 'Results ready in 15–60 min. ~$0.21/ticker.'
              : 'Live streaming results. ~$0.34/ticker.'}
          </p>
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded px-3 py-2">
            {error}
          </div>
        )}

        <button
          onClick={handleAnalyse}
          disabled={loading || (!tickers.trim() && !useSheets)}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold py-3 rounded transition-colors text-sm uppercase tracking-wide"
        >
          {loading ? 'Submitting...' : mode === 'batch' ? 'Submit Batch' : 'Analyse Now'}
        </button>
      </div>
    </div>
  )
}

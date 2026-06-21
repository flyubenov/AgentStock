import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000'

export default function Home() {
  const [tickers, setTickers] = useState('')
  const [useSheets, setUseSheets] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleAnalyse = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers
        .split(/[\s,]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean)

      const body: Record<string, unknown> = {}
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
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Fair Value Calculator</h1>
      <p className="text-slate-500 text-sm mb-8">
        Enter tickers (or load from Google Sheets) to compute an adaptive, sector-aware fair value for each. Free — no API costs.
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
          {loading ? 'Submitting...' : 'Calculate Fair Values'}
        </button>
      </div>
    </div>
  )
}

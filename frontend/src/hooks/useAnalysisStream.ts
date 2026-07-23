import { useEffect, useRef, useState } from 'react'
import type { TickerResult, JobStatus } from '../types'

interface StreamState {
  status: JobStatus['status']
  total: number
  completed: number
  failed: number
  results: TickerResult[]
  running: string[]
  tickerStatuses: Record<string, 'queued' | 'running' | 'done' | 'failed'>
}

const API = 'http://localhost:8000'

export function useAnalysisStream(jobId: string | null) {
  const [state, setState] = useState<StreamState>({
    status: 'running',
    total: 0,
    completed: 0,
    failed: 0,
    results: [],
    running: [],
    tickerStatuses: {},
  })
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) return
    const es = new EventSource(`${API}/api/stream/${jobId}`)
    esRef.current = es

    es.addEventListener('ticker_done', (e) => {
      const result: TickerResult = JSON.parse(e.data)
      setState(prev => ({
        ...prev,
        results: [...prev.results, result],
        tickerStatuses: { ...prev.tickerStatuses, [result.ticker]: result.status === 'failed' ? 'failed' : 'done' },
      }))
    })

    es.addEventListener('status', (e) => {
      const data: Partial<StreamState> = JSON.parse(e.data)
      setState(prev => {
        const running = data.running ?? prev.running
        // Mark the currently-in-flight tickers as 'running' so their chips pulse —
        // but never override a ticker that already finished (done/failed wins).
        const tickerStatuses = { ...prev.tickerStatuses }
        for (const t of running) {
          if (tickerStatuses[t] !== 'done' && tickerStatuses[t] !== 'failed') {
            tickerStatuses[t] = 'running'
          }
        }
        return { ...prev, ...data, running, tickerStatuses }
      })
      if (data.status && ['completed', 'failed', 'cancelled'].includes(data.status)) {
        es.close()
      }
    })

    es.onerror = () => {
      setState(prev => ({ ...prev, status: 'failed' }))
      es.close()
    }

    return () => es.close()
  }, [jobId])

  const cancel = async () => {
    if (!jobId) return
    await fetch(`${API}/api/cancel/${jobId}`, { method: 'POST' })
    esRef.current?.close()
  }

  return { ...state, cancel }
}

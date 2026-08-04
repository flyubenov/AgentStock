import { API_BASE as API } from './api'

export type NumRange = { min: number | null; max: number | null }

export interface SerializedFilters {
  tickers: string[]
  stockTypes: string[]
  quality: NumRange
  gap: NumRange
}

export interface Watchlist {
  name: string
  filter: SerializedFilters
  created: string
}

export async function fetchWatchlists(): Promise<Watchlist[]> {
  const res = await fetch(`${API}/api/watchlists`)
  const data = await res.json()
  if (data.error) throw new Error(data.error)
  return (data.results ?? []) as Watchlist[]
}

export async function saveWatchlist(name: string, filter: SerializedFilters): Promise<void> {
  const res = await fetch(`${API}/api/watchlists/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filter }),
  })
  const data = await res.json()
  if (!data.saved) throw new Error(data.error || 'Failed to save watchlist')
}

export async function deleteWatchlist(name: string): Promise<void> {
  const res = await fetch(`${API}/api/watchlists/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  const data = await res.json()
  if (!data.deleted) throw new Error(data.error || 'Failed to delete watchlist')
}

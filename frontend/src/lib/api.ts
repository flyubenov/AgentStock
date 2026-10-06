// Backend API base URL. Set VITE_API_BASE at build time per deploy environment
// (e.g. the Cloud Run / Railway / Render backend URL); falls back to the local
// dev backend so `npm run dev` + start.sh keep working with no config.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// The backend requires a shared API token (X-Api-Key). It is never baked into
// the bundle: the user types it once per device and it lives in localStorage.
const TOKEN_KEY = 'agentStockApiToken'

// Fallback when localStorage is unavailable (private mode / blocked storage):
// the token then lasts only until reload.
let memoryToken: string | null = null

function currentToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken
  } catch {
    return memoryToken
  }
}

function saveToken(token: string) {
  memoryToken = token
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // keep the in-memory copy
  }
}

function promptForToken(): boolean {
  const entered = window.prompt('Enter your Agent Stock API token')?.trim()
  if (!entered) return false
  saveToken(entered)
  return true
}

// fetch() against the backend with the token attached. On a 401 it asks for the
// token once and retries; if another request already stored a new token while
// this one was in flight, it retries with that instead of prompting again.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const send = (token: string | null) => {
    const headers = new Headers(init.headers)
    if (token) headers.set('X-Api-Key', token)
    return fetch(`${API_BASE}${path}`, { ...init, headers })
  }
  const sent = currentToken()
  const res = await send(sent)
  if (res.status !== 401) return res
  if (currentToken() !== sent || promptForToken()) return send(currentToken())
  return res
}

// EventSource can't send headers, so the stream gets the token as ?token=.
export function streamUrl(path: string): string {
  const token = currentToken()
  return token
    ? `${API_BASE}${path}?token=${encodeURIComponent(token)}`
    : `${API_BASE}${path}`
}

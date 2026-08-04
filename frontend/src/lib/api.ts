// Backend API base URL. Set VITE_API_BASE at build time per deploy environment
// (e.g. the Cloud Run / Railway / Render backend URL); falls back to the local
// dev backend so `npm run dev` + start.sh keep working with no config.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// Backend API base URL. VITE_API_BASE overrides it at build time. Otherwise a
// production build calls its own origin (the Cloud Run service serves the page and
// /api together), and dev/test fall back to the local backend so `npm run dev` +
// start.sh keep working with no config.
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')

# Deploying Agent Stock

Agent Stock is two deployables from this one repo:

- **Backend** (`backend/`) — a **persistent** FastAPI/uvicorn process. It streams
  Server-Sent Events (the live recalc progress) and runs in-process worker pools,
  so it needs a real container/VM, **not** short-timeout serverless functions.
- **Frontend** (`frontend/`) — a static Vite/React build (just HTML/JS/CSS).

There is **no database to provision** — state lives in a Google Sheet. The backend
only needs the sheet id and a Google service-account credential.

This repo ships configs for three hosting paths so you can compare them:

| Path | Backend | Frontend | Cost | Cold starts |
|------|---------|----------|------|-------------|
| **A (recommended, $0)** | Google Cloud Run (scale-to-zero) | Vercel | $0 | yes, after idle |
| **B** | Railway | Vercel (or Railway) | ~$5/mo | no (always-on) |
| **C** | Render (free) | Render static (free) | $0 | yes, after idle |

---

## Prerequisites (all paths)

1. **A Google service-account JSON key** with access to your sheet.
   - In Google Cloud Console: create a service account → create a JSON key.
   - Share your Google Sheet with the service account's email (Editor).
   - Keep this file secret. It is **gitignored** (`backend/credentials/`) and must
     never be committed.
2. **Your Google Sheet id** (the long id in the sheet's URL).
3. These commits pushed to GitHub (the configs below deploy from the repo).

### Environment variables the backend reads

| Var | Required | Purpose |
|-----|----------|---------|
| `GOOGLE_SHEETS_ID` | yes | The spreadsheet the app uses as its DB |
| `GOOGLE_SHEETS_CREDS_JSON` | cloud | The **entire** service-account JSON, as one env value |
| `GOOGLE_SHEETS_CREDS_PATH` | local only | Path to the key file (default `./credentials/service_account.json`); ignored when `GOOGLE_SHEETS_CREDS_JSON` is set |
| `CORS_ORIGINS` | cloud | Comma-separated allowed frontend origin(s), e.g. `https://your-frontend.vercel.app` |

### Environment variable the frontend reads (build time)

| Var | Purpose |
|-----|---------|
| `VITE_API_BASE` | The deployed backend URL, e.g. `https://agentstock-xxxx.run.app`. Unset → defaults to `http://localhost:8000`. |

> **Order of operations:** deploy the **backend first** to get its URL, set that as
> the frontend's `VITE_API_BASE`, deploy the frontend, then set the backend's
> `CORS_ORIGINS` to the frontend's URL and redeploy the backend.

---

## Path A — Cloud Run (backend) + Vercel (frontend) — $0

Uses `backend/Dockerfile`. Cloud Run scales to zero, so at low traffic it stays
within the always-free tier.

### A1. Backend on Cloud Run

Requires the `gcloud` CLI and a GCP project with billing enabled (free tier still
applies). From the repo root:

```bash
gcloud config set project YOUR_PROJECT_ID

gcloud run deploy agentstock-backend \
  --source ./backend \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_SHEETS_ID=YOUR_SHEET_ID,CORS_ORIGINS=https://TEMP" \
  --set-env-vars "GOOGLE_SHEETS_CREDS_JSON=$(tr -d '\n' < backend/credentials/service_account.json)"
```

- `--source ./backend` makes Cloud Build build the Dockerfile for you (no manual
  image push).
- Note the service URL it prints (e.g. `https://agentstock-backend-xxxx.run.app`).

**Continuous deploy from GitHub (optional):** Cloud Run console → your service →
"Set up continuous deployment" → pick this repo, branch, and `/backend` as the
build context. After that, every push redeploys.

**Cleaner credentials on Cloud Run (optional):** instead of pasting
`GOOGLE_SHEETS_CREDS_JSON`, you can grant the sheet to Cloud Run's **runtime
service account** and drop the env var entirely — the Google client falls back to
Application Default Credentials. (Requires no code change only if you later add an
ADC branch; the current code path expects the JSON env var or a file.)

### A2. Frontend on Vercel

1. Vercel → "Add New Project" → import this GitHub repo.
2. **Root Directory: `frontend`** (important — this is a monorepo). Vercel then
   reads `frontend/vercel.json` and auto-detects Vite.
3. Add env var **`VITE_API_BASE`** = your Cloud Run URL from A1.
4. Deploy. Note the frontend URL (e.g. `https://agentstock.vercel.app`).

### A3. Close the CORS loop

Update the backend's `CORS_ORIGINS` to the Vercel URL and redeploy:

```bash
gcloud run services update agentstock-backend --region us-central1 \
  --update-env-vars "CORS_ORIGINS=https://agentstock.vercel.app"
```

### Flip to always-on (no cold starts) — one flag

```bash
gcloud run services update agentstock-backend --region us-central1 --min-instances 1
```

This keeps one instance warm (no cold starts) but leaves the free tier, costing
roughly ~$5–15/mo. Set back to `--min-instances 0` to return to $0.

---

## Path B — Railway (backend) + Vercel (frontend) — ~$5/mo

Railway doesn't scale to zero, so **no cold starts**, but there's no real free tier
(~$5/mo Hobby, usage-based). Uses `backend/railway.json` + `backend/Dockerfile`.

1. Railway → "New Project" → "Deploy from GitHub repo" → pick this repo.
2. In the service settings, set **Root Directory: `backend`**. Railway reads
   `backend/railway.json` and builds the Dockerfile.
3. Variables tab — add `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDS_JSON`,
   `CORS_ORIGINS`.
4. Railway assigns a domain (Settings → Networking → Generate Domain). That's your
   backend URL.
5. Frontend: same as **A2/A3** (Vercel with `VITE_API_BASE` = the Railway URL; then
   set the backend `CORS_ORIGINS` to the Vercel URL).

You can alternatively host the frontend on Railway too (add a second service, root
`frontend`, static build), but Vercel is simpler for a static SPA.

---

## Path C — Render (backend + frontend, free) — $0

Uses `render.yaml` at the repo root (a Blueprint defining both services). Backend
free plan spins down after ~15 min idle (cold start on next request).

1. Render → "New" → **"Blueprint"** → connect this repo. Render reads `render.yaml`
   and proposes both services.
2. It will prompt for the `sync: false` env vars — fill in:
   - backend: `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDS_JSON`, `CORS_ORIGINS`
   - frontend: `VITE_API_BASE`
3. First deploy: since the two URLs don't exist yet, you can deploy once, read the
   assigned URLs, then set `VITE_API_BASE` (frontend) and `CORS_ORIGINS` (backend)
   and trigger a redeploy of each.
4. Always-on backend: change the backend service `plan: free` → `plan: starter`
   (~$7/mo) in `render.yaml` or the dashboard.

> The static-site block in `render.yaml` (`runtime: static`) follows Render's
> current Blueprint schema; if Render flags it, create the static site manually in
> the dashboard (root `frontend`, build `npm ci && npm run build`, publish `dist`,
> add the SPA rewrite `/*` → `/index.html`) — the backend service block is the part
> that matters most.

---

## Local development is unchanged

All the above is additive and backward-compatible. Locally, nothing new is
required — `./start.sh` still runs the backend on `:8000` and the frontend on
`:5173`, using the on-disk credential file and the localhost defaults.

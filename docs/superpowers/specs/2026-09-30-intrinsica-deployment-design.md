# Intrinsica deployment — design

**Date:** 2026-09-30
**Status:** approved in brainstorming (sections 1–3); awaiting written-spec review
**Goal:** put the Intrinsica fake-door page live at `https://intrinsica.io` on Google Cloud Run: one provider, always on, and deployed automatically whenever `main` changes.

---

## 1. Requirements and decisions

| # | Requirement / decision | Source |
|---|---|---|
| R1 | Every push or merge to `main` on `github.com/intrinsica-io/intrinsica` builds, tests and deploys **both** the frontend and the backend | user |
| R2 | **One provider: Google Cloud Run.** No Vercel, Railway or Render | user |
| R3 | **Always on.** No cold starts | user |
| R4 | Served over **HTTPS** at **`intrinsica.io`** (bought at spaceship.com; its DNS is managed there) | user |
| R5 | **No relation, dependency or touch point with Agent Stock.** Separate GCP project, service accounts, sheet, images and triggers. No `GOOGLE_SHEETS_ID` and no Agent Stock credentials in production | user |
| R6 | Funnel data (events, tickers, emails) is written to the dedicated sheet `1e4U4roainSuDJPHwsxkVrZezlA2InDPHV1zaQHuCzqY` | user |
| R7 | The live ticker evaluation (all four engines) stays public. The backend must not have a second public address; it is reachable only as `intrinsica.io/api/...` | user |
| R8 | Cache: fundamentals (Quality, Moat, Fair Value) **7 days**; price, and the price-dependent R/R and FV gap %, **4 hours**. The same TTLs apply to every ticker | user |
| R9 | Changes reach `main` only through PRs. The PRs get an automatic test run | user (standing rule) + approved |
| R10 | A detailed step-by-step setup guide (section 8). It also becomes the new `DEPLOY.md` | user |
| D1 | **Approach A:** one Cloud Run service, Cloud Run domain mapping (free managed TLS), and a Cloud Build trigger | approved |
| D2 | Shareable ticker links (`/t/AMZN`) are **a separate follow-up project**. This design only guarantees that any non-`/api` path serves the app, so that work needs no deployment change | approved |
| D3 | Yahoo Finance stays for the smoke test (no charging, no accounts). A licensed feed is a prerequisite for a real launch | approved |

**Subscription (Q3):** Google Cloud has no subscription tier. You need a normal **pay-as-you-go Cloud Billing account** linked to the project. Expected run cost is **about $10–15 a month**, almost all of it the one always-warm instance. Builds, image storage and domain mapping cost about nothing. Before launch, confirm the figure with the Google Cloud Pricing Calculator for europe-west1 (1 vCPU, 1 GiB, min instances 1, request-based billing). A budget alert guards it (§8 step 2).

---

## 2. Architecture

```
 visitor ──HTTPS──▶ intrinsica.io  (Cloud Run domain mapping, Google-managed cert)
                         │
                         ▼
          Cloud Run service "intrinsica"  (europe-west1, min 1 / max 3)
          ┌──────────────────────────────────────────────┐
          │ one container (root Dockerfile)              │
          │  FastAPI / uvicorn                           │
          │   /api/landing/*, /api/events, /api/health   │
          │   everything else → built React app (dist/)  │
          └───────────┬──────────────────────┬───────────┘
                      │ ADC (runtime SA)     │ HTTPS
                      ▼                      ▼
        Google Sheet 1e4U4…  (Events tab)   Yahoo Finance (yfinance)

 GitHub intrinsica-io/intrinsica
   PR → main   ──▶ Cloud Build trigger "intrinsica-pr"     : tests only
   push main   ──▶ Cloud Build trigger "intrinsica-deploy" : tests → image → Artifact Registry → Cloud Run → smoke check
```

### 2.1 GCP project
- A new, dedicated project (suggested ID `intrinsica-prod`; the guide uses `$PROJECT_ID`).
- It is linked to a pay-as-you-go billing account. Region is **`europe-west1`**, which supports Cloud Run domain mappings.
- It shares nothing with `agent-stock-493915`.

### 2.2 Container (new root `Dockerfile` + root `.dockerignore`)
- **Stage 1 (`node:22-slim`):** `npm ci` and `npm run build` in `frontend/`. The build args are:
  - `VITE_API_BASE=""`: `api.ts` uses `??`, so an empty string is kept, and calls go to relative `/api/...` on the same origin.
  - `VITE_PUBLIC_MODE=1`: see §2.4.
- **Stage 2 (`python:3.12-slim`):** today's backend image (`pip install -r backend/requirements.txt`, then copy `backend/`), plus `frontend/dist` copied to `/app/static`.
- The command is unchanged: `uvicorn main:app --host 0.0.0.0 --port ${PORT}`.
- The root `.dockerignore` excludes `.git`, `**/node_modules`, `frontend/dist`, `backend/credentials`, `backend/tests`, `**/__pycache__`, `**/.pytest_cache`, `.env*`, `brand/`, `docs/`, `MonetizationPlan/`, `.superpowers/` and `.claude/`.
- `backend/Dockerfile` and `backend/.dockerignore` are **removed**. The root Dockerfile is the only build.

### 2.3 FastAPI serves the frontend (`backend/main.py`, a small new module)
- **Enabling it:** set `INTRINSICA_STATIC_DIR` (the image sets `/app/static`). When it is unset or the directory is missing (local dev), nothing changes and Vite serves the frontend as today.
- **Order of routes:**
  1. The API routers.
  2. `/api/{anything unmatched}` returns a JSON **404**. It never returns `index.html`.
  3. `GET /{path}`: if the path is a real file inside the static dir, that file is served (with path-traversal protection). Otherwise `index.html` is served, which covers the React routes and the future `/t/AMZN`.
- **Cache headers:**
  - `/assets/*` (hashed file names): `Cache-Control: public, max-age=31536000, immutable`.
  - `index.html`: `no-cache`, so a deploy is visible immediately.
- **Canonical-host middleware:** a request whose `Host` starts with `www.` gets a **301** to `https://intrinsica.io{path}{query}`. The target host comes from `CANONICAL_HOST`; when that is unset (local dev), there is no redirect.

### 2.4 Public mode (`INTRINSICA_PUBLIC_MODE=1` backend, `VITE_PUBLIC_MODE=1` frontend)
- **Backend:** mounts only the `landing`, `events` and health routes. The `analysis`, `database` and `watchlists` routers are **not included**, so their paths return 404. Nothing in the process reads `GOOGLE_SHEETS_ID`.
- **Frontend:** `App.tsx` registers only `/` and `/checkout`, plus a catch-all `*` → `LandingPage`. The analyst pages (`/app`, `/progress`, `/results`, `/ticker`, `/database`) are not registered. Because Vite replaces `import.meta.env.VITE_PUBLIC_MODE` at build time, they are also tree-shaken out of the production bundle.
- **Without the flags** (local dev): behaviour is exactly as today.
- Deleting the analyst code outright is **out of scope**. It would be a large refactor that adds nothing to the launch.

### 2.5 Cloud Run service `intrinsica`

| Setting | Value | Reason |
|---|---|---|
| min instances | 1 | R3: no cold starts, and the in-memory cache stays resident |
| max instances | 3 | Cost cap |
| CPU / memory | 1 vCPU / 1 GiB | pandas + yfinance, and a 256-entry cache |
| Billing | request-based (CPU throttled between requests), **startup CPU boost** on | Cheapest with min 1. `events_sheets.py` already flushes on requests, not only on its timer |
| Concurrency / timeout | 80 / 300 s | Defaults. A cold evaluation of a new ticker can take tens of seconds |
| Ingress / auth | all traffic, `--allow-unauthenticated` | Public site |
| Runtime identity | `intrinsica-run@$PROJECT_ID.iam.gserviceaccount.com` | Holds **no** project roles. Its only access is Editor on the events sheet |
| Default `*.run.app` URL | **disabled** once the domain works (§8 step 11) | R7 |

### 2.6 Environment variables (all set by `cloudbuild.yaml`; no secrets exist)

| Var | Value | Notes |
|---|---|---|
| `INTRINSICA_PUBLIC_MODE` | `1` | §2.4 |
| `INTRINSICA_STATIC_DIR` | `/app/static` | Baked into the image (Dockerfile `ENV`), not set by the deploy |
| `CANONICAL_HOST` | `intrinsica.io` | §2.3 |
| `CORS_ORIGINS` | `https://intrinsica.io` | Same-origin already. This blocks other sites' pages |
| `INTRINSICA_EVENTS_SHEET_ID` | `1e4U4roainSuDJPHwsxkVrZezlA2InDPHV1zaQHuCzqY` | R6 |
| `LANDING_SLOW_TTL` | `604800` | 7 days (R8) |
| `LANDING_FAST_TTL` | `14400` | 4 hours (R8) |
| `LANDING_CACHE_MAX_ENTRIES` | `256` | New. Replaces the hard-coded 64 |
| `LANDING_RATE_LIMIT` / `LANDING_RATE_WINDOW_SECONDS` | `20` / `60` | New (§5) |

- The deploy uses `--set-env-vars`, so **the repo is the single source of truth**. An env var edited by hand in the console is overwritten by the next deploy; change config through a PR instead.
- `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDS_JSON` and `GOOGLE_SHEETS_CREDS_PATH` are **never set** in production.

---

## 3. CI/CD

### 3.1 Triggers (Cloud Build, 2nd-gen GitHub connection)
- **Connection:** the Cloud Build GitHub App is installed on the **`intrinsica-io`** org and limited to the `intrinsica` repo.
- **`intrinsica-deploy`:** event *Push to a branch*, `^main$`, config `cloudbuild.yaml`, service account `intrinsica-build`.
- **`intrinsica-pr`:** event *Pull request*, base branch `^main$`, config `cloudbuild-pr.yaml`, the same service account. Its results show as a check on the PR.

### 3.2 `cloudbuild.yaml` (deploy)

| # | Step | Image |
|---|---|---|
| 1 | Backend tests: `pip install -r backend/requirements.txt pytest` → `cd backend && pytest -q` | `python:3.12-slim` |
| 2 | Frontend tests: `cd frontend && npm ci && npx vitest run` | `node:22-slim` |
| 3 | `docker build -t $_IMAGE:$SHORT_SHA .` (the frontend type check and build run inside it) | `gcr.io/cloud-builders/docker` |
| 4 | `docker push $_IMAGE:$SHORT_SHA` | same |
| 5 | `gcloud run deploy $_SERVICE --image $_IMAGE:$SHORT_SHA` plus every §2.5 setting and every §2.6 env var | `gcr.io/google.com/cloudsdktool/cloud-sdk:slim` |
| 6 | Smoke check: if `_SMOKE_URL` is non-empty, `curl` `$_SMOKE_URL/api/health` up to 5 times, 10 s apart, and fail unless it returns `{"status":"ok"}` | `curlimages/curl` |

- **Substitutions:**
  - `_REGION=europe-west1`
  - `_SERVICE=intrinsica`
  - `_IMAGE=europe-west1-docker.pkg.dev/$PROJECT_ID/intrinsica/app`
  - `_SMOKE_URL=""`: empty until the domain works; then it is set to `https://intrinsica.io` on the trigger.
- **Options:** `logging: CLOUD_LOGGING_ONLY`, which a user-specified build service account requires.
- **Failure semantics:** if steps 1–5 fail, the running revision is untouched. Step 6 runs after the traffic switch; its failure turns the build red and tells you to roll back (§8.13).
- **ESLint is not a gate** (known baseline of 6 findings).

### 3.3 `cloudbuild-pr.yaml`
Steps 1 and 2 only, plus `npm run build`, so the type check also gates PRs. Nothing is pushed or deployed.

### 3.4 Identities

| Service account | Roles |
|---|---|
| `intrinsica-build` | `roles/run.admin` (deploy and set public access), `roles/artifactregistry.writer`, `roles/logging.logWriter`; `roles/iam.serviceAccountUser` **on `intrinsica-run` only** |
| `intrinsica-run` | No project roles. Editor on the events sheet (granted in Google Sheets, not IAM) |

### 3.5 Artifact Registry
- A Docker repo named `intrinsica` in `europe-west1`.
- A cleanup policy **keeps the 10 most recent** images and deletes others older than 30 days.

---

## 4. Domain and HTTPS
1. **Ownership:** verify `intrinsica.io` in Google Search Console with a TXT record in Spaceship DNS.
2. **Apex mapping:** `intrinsica.io` → `intrinsica`. Google returns **4 A + 4 AAAA** records, which go into Spaceship and **replace** any parking or default records on `@`.
3. **`www` mapping:** `www.intrinsica.io` → `intrinsica` as a CNAME to `ghs.googlehosted.com.`. The app 301-redirects `www` to the apex (§2.3).
4. **Certificates:** Google provisions and renews them automatically, and HTTP redirects to HTTPS. Issue takes about 15 minutes to 24 hours after DNS propagates.
5. **Default URL:** after `https://intrinsica.io` serves correctly, disable the default `*.run.app` URL. Re-verify the domain afterwards; if the mapping ever stops serving, re-enable it (it's the same app, so this is harmless).
6. **Caveat:** Cloud Run domain mapping is a Preview feature (slightly higher latency, no Cloud Armor or CDN). Moving to a Global HTTPS Load Balancer later (about +$18–25 a month) needs **no code change**.

---

## 5. Google Sheet, security and abuse

### 5.1 Sheet access without keys
- **Code change in `services/sheets.py` `_get_service()`:**
  1. `GOOGLE_SHEETS_CREDS_JSON` if set.
  2. Otherwise, the key file if `GOOGLE_SHEETS_CREDS_PATH` (default `./credentials/service_account.json`) **exists**.
  3. Otherwise `google.auth.default(scopes=SCOPES)`, which on Cloud Run is the runtime service account.
  - Local dev is unchanged.
- **Sheet setup:**
  - Enable the Sheets API in the project.
  - Share the sheet with `intrinsica-run@$PROJECT_ID.iam.gserviceaccount.com` as **Editor**.
  - Keep General access **Restricted**, because the sheet ID sits in the repo.
- On the first write, the app creates the tab **`Events`** with the headers `Timestamp | Event | VisitorId | Props`; tickers and emails are in `Props` (JSON). Other tabs are untouched.
- **Local dev** leaves `INTRINSICA_EVENTS_SHEET_ID` unset (events stay in memory), so the demo sheet only ever holds production data.

### 5.2 Rate limiting
- **Shared module:** the events router's limiter (sliding window, bounded client table, right-most `X-Forwarded-For` as the client key) moves into a shared **`services/rate_limit.py`** (`RateLimiter(limit, window, max_clients)` plus `client_key(request)`). `routers/events.py` uses it with unchanged behaviour.
- **`POST /api/landing/analyze`:** gets its own limiter, 20 requests per 60 s per IP. Above that it returns **429** with a JSON `detail`.
- **Frontend:** shows a friendly "Too many requests, try again in a minute" message instead of a generic error.

### 5.3 Other controls
- CORS locked to `https://intrinsica.io`.
- Max 3 instances and a billing budget alert.
- The cache is capped at 256 entries.
- Analyst APIs are absent (§2.4), and there is no `*.run.app` URL (§4).

---

## 6. Cache (R8)
The two-layer cache in `backend/landing/cache.py` already implements the rule. Only the numbers change, plus the cap and a guard test:

- **Slow layer:** the full Quality, Moat and FV engine run, plus the R/R inputs, for `LANDING_SLOW_TTL` = **7 days**.
- **Fast layer:** after `LANDING_FAST_TTL` = **4 hours**, one yfinance quote call re-scores R/R and recomputes the FV gap % from the cached inputs. No other Yahoo call is made.
- **Applies to every ticker**, not only the demo ones.
- **`MAX_ENTRIES` becomes `LANDING_CACHE_MAX_ENTRIES`** (default **256**).
- **Chip-sync test (new):** a backend test asserts that `LANDING_MARQUEE_TICKERS` in `main.py` equals `COMPARE_TICKERS` in `frontend/src/landing/components/Hero.tsx` (currently `AAPL, MSFT, NVDA`). This keeps every compare chip pre-warmed at startup.
- **Known, accepted behaviour:**
  - Each new deploy or instance starts with an empty cache (the chip tickers re-warm at boot).
  - Each instance has its own cache.
  - A failed price refresh serves stale data and retries after 60 s.
  - A failed evaluation retries after 15 minutes.

---

## 7. Yahoo Finance (Q9)
- **Allowed for the smoke test**, with two risks:
  1. Yahoo's terms don't permit commercial use or redistribution; a public marketing page is a grey area.
  2. Yahoo often rate-limits datacenter IPs, including Cloud Run's.
- **Existing mitigations:** the 7-day/4-hour cache, the per-IP limit, stale-serving, and the existing rate-limit backoff.
- **Monitoring:** a saved Cloud Logging query (§8.13) for Yahoo errors.
- **Exit criterion:** move to a licensed feed before accounts or billing go live. Not legal advice.

---

## 8. Step-by-step setup guide

> Run commands in **Google Cloud Shell** (console → the `>_` icon, top right). It is already authenticated and has `gcloud`, so nothing is needed on Windows. Anything done in a browser UI is marked **[Console]**, **[Spaceship]**, **[Sheets]** or **[GitHub]**.
> Steps 1–5 can be done at any time. Step 6 needs the implementation PR (the pipeline files) merged first.

### Step 1: Create the project and enable APIs
1. **[Console]** Billing → confirm you have an active **billing account**. If not, create one (pay-as-you-go; a card is required).
2. In Cloud Shell:
   ```bash
   export PROJECT_ID=intrinsica-prod      # must be globally unique; add a suffix if taken
   export REGION=europe-west1
   gcloud projects create $PROJECT_ID --name="Intrinsica"
   gcloud billing accounts list           # copy the ACCOUNT_ID
   gcloud billing projects link $PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX
   gcloud config set project $PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
     artifactregistry.googleapis.com sheets.googleapis.com iam.googleapis.com \
     secretmanager.googleapis.com
   ```
   Secret Manager is only used internally by the Cloud Build GitHub connection to store its token. The app has no secrets.
3. **Check:** `gcloud services list --enabled` shows all six.

> Cloud Shell sessions forget variables. At the start of each later session, run `export PROJECT_ID=… REGION=europe-west1` and `gcloud config set project $PROJECT_ID` again.

### Step 2: Budget alert
**[Console]** Billing → Budgets & alerts → **Create budget**:
- Scope: project `Intrinsica`.
- Amount: 25 (in your billing currency).
- Thresholds: 50%, 90% and 100%, with email to billing admins.

A budget **alerts** you; it does not stop spending. The real cap is max instances = 3.

### Step 3: Service accounts
```bash
gcloud iam service-accounts create intrinsica-run   --display-name="Intrinsica runtime"
gcloud iam service-accounts create intrinsica-build --display-name="Intrinsica build/deploy"

export RUN_SA=intrinsica-run@$PROJECT_ID.iam.gserviceaccount.com
export BUILD_SA=intrinsica-build@$PROJECT_ID.iam.gserviceaccount.com

for ROLE in roles/run.admin roles/artifactregistry.writer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$BUILD_SA --role=$ROLE --condition=None
done

gcloud iam service-accounts add-iam-policy-binding $RUN_SA \
  --member=serviceAccount:$BUILD_SA --role=roles/iam.serviceAccountUser
```
**Check:** `gcloud projects get-iam-policy $PROJECT_ID --flatten=bindings --filter="bindings.members:$BUILD_SA" --format="value(bindings.role)"` lists the three roles.

### Step 4: Artifact Registry
```bash
gcloud artifacts repositories create intrinsica \
  --repository-format=docker --location=$REGION --description="Intrinsica images"

cat > cleanup.json <<'EOF'
[
  {"name": "keep-recent-10", "action": {"type": "Keep"},
   "mostRecentVersions": {"keepCount": 10}},
  {"name": "delete-older-30d", "action": {"type": "Delete"},
   "condition": {"tagState": "any", "olderThan": "30d"}}
]
EOF
gcloud artifacts repositories set-cleanup-policies intrinsica \
  --location=$REGION --policy=cleanup.json --no-dry-run
```

### Step 5: Connect the Google Sheet
1. **[Sheets]** Open `https://docs.google.com/spreadsheets/d/1e4U4roainSuDJPHwsxkVrZezlA2InDPHV1zaQHuCzqY/edit`.
2. **Share** → add `intrinsica-run@<PROJECT_ID>.iam.gserviceaccount.com` → role **Editor** → untick "Notify people" → **Share**. Google may warn that the address is outside your organisation; that is expected.
3. In the same dialog, confirm **General access = Restricted**.
4. Do **not** create the `Events` tab yourself. The app creates it with the right headers on its first write. If you want to pre-create it, name it exactly `Events` and put `Timestamp | Event | VisitorId | Props` in row 1.

### Step 6: Connect GitHub and create the triggers
*Prerequisite: the implementation PR (Dockerfile, `cloudbuild*.yaml`, code changes) has been merged to `main`.*

1. **[Console]** Cloud Build → **Repositories** → **2nd gen** tab → **Create host connection**:
   - Provider GitHub, region `europe-west1`, name `github-intrinsica`.
   - **Connect** → authorise → **Install in a new account**, choose the **`intrinsica-io`** org → **Only select repositories** → `intrinsica` → Install.
   - If prompted to grant the Cloud Build service agent the Secret Manager Admin role, accept.
2. On the connection → **Link repository** → `intrinsica-io/intrinsica` → Link.
3. **[Console]** Cloud Build → **Triggers** (region `europe-west1`) → **Create trigger**. Create two:

| Field | `intrinsica-deploy` | `intrinsica-pr` |
|---|---|---|
| Event | Push to a branch | Pull request |
| Repository | `intrinsica-io/intrinsica` (2nd gen) | same |
| Branch | `^main$` | Base branch `^main$` |
| Comment control | — | Required except for owners and collaborators |
| Configuration | Cloud Build config file, `/cloudbuild.yaml` | `/cloudbuild-pr.yaml` |
| Substitution | `_SMOKE_URL` = *(leave empty for now)* | — |
| Service account | `intrinsica-build@…` | `intrinsica-build@…` |

4. **[GitHub]** (optional, recommended) Repo → Settings → Branches → the rule for `main` → *Require status checks* → select the `intrinsica-pr` check.

### Step 7: First deploy
1. **[Console]** Triggers → `intrinsica-deploy` → **Run** → branch `main`.
2. Watch Cloud Build → History. The first build takes about 5–8 minutes; later ones are faster thanks to layer cache.
3. When it is green:
   ```bash
   gcloud run services describe intrinsica --region=$REGION --format="value(status.url)"
   ```
   Open that `https://intrinsica-…run.app` URL. The page loads and the AAPL, MSFT and NVDA tiles render.
4. **Check the sheet:** type a ticker on the page, wait about 30 s, and an `Events` tab with rows appears.

### Step 8: Verify domain ownership
```bash
gcloud domains verify intrinsica.io
```
This opens Google Search Console. Choose **Domain** property → copy the **TXT** record → **[Spaceship]** Domains → `intrinsica.io` → **DNS / Nameservers** → Add record: type **TXT**, host `@`, value `google-site-verification=…`, TTL default → Save. Back in Search Console → **Verify**. It can take a few minutes; retry if it fails at first.

Use the **same Google account** that runs `gcloud` in Cloud Shell. Only a verified owner can create the mapping.

### Step 9: Map the domain
```bash
gcloud beta run domain-mappings create --service=intrinsica --domain=intrinsica.io     --region=$REGION
gcloud beta run domain-mappings create --service=intrinsica --domain=www.intrinsica.io --region=$REGION
gcloud beta run domain-mappings describe --domain=intrinsica.io --region=$REGION
```
The `describe` output lists `resourceRecords`: 4 × `A` and 4 × `AAAA` for `intrinsica.io`, and 1 × `CNAME` → `ghs.googlehosted.com.` for `www`.

### Step 10: DNS records at Spaceship
**[Spaceship]** `intrinsica.io` → DNS records:
1. **Delete** any existing records on host `@` or `www` of type A, AAAA or CNAME, and any Spaceship parking or URL-redirect records. Keep the TXT verification record.
2. Add the **4 A** records: host `@`, each IP from step 9.
3. Add the **4 AAAA** records: host `@`, each IPv6 address from step 9.
4. Add **1 CNAME**: host `www`, value `ghs.googlehosted.com.`.
5. Save, then watch the mapping status:
   ```bash
   gcloud beta run domain-mappings describe --domain=intrinsica.io --region=$REGION \
     --format="value(status.conditions)"
   ```
   Wait until `Ready` and `CertificateProvisioned` are `True`. That takes 15 minutes to 24 hours; propagation can be checked at dnschecker.org.

### Step 11: Lock down and turn on the smoke check
1. Confirm that `https://intrinsica.io` and `https://www.intrinsica.io` work, and that `www` redirects to the apex.
2. Disable the default URL:
   ```bash
   gcloud run services update intrinsica --region=$REGION --no-default-url
   ```
   Re-open `https://intrinsica.io`; it must still work. The old `run.app` URL now returns 404. If the domain stopped serving, revert with `--default-url` and note it.
3. **[Console]** Triggers → `intrinsica-deploy` → Edit → set `_SMOKE_URL` = `https://intrinsica.io` → Save.

### Step 12: Launch checklist
- [ ] `https://intrinsica.io` shows a valid padlock. `http://intrinsica.io` and `https://www.intrinsica.io` both end at `https://intrinsica.io/`.
- [ ] `https://intrinsica.io/api/health` returns `{"status":"ok"}`.
- [ ] `https://intrinsica.io/api/database` and `/api/analysis` return 404, and `/app` shows the landing page.
- [ ] The AAPL, MSFT and NVDA tiles are instant. A new ticker (e.g. AMZN) evaluates live, and a second view of it is instant.
- [ ] New rows in the sheet's `Events` tab.
- [ ] View source shows the `og:title`, `og:image` and `og:url` tags. The X card preview is checked (post a draft or use a card-preview tool).
- [ ] The `run.app` URL no longer serves.
- [ ] Open a trivial PR → `intrinsica-pr` runs green on it → merge → `intrinsica-deploy` runs green → the change is live.
- [ ] Cloud Run → `intrinsica` → Metrics shows 1 instance idle-warm.

### Step 13: Day-to-day operations
- **Deploy:** merge a PR to `main`. Nothing else.
- **Change config** (cache TTLs, rate limit, sheet): edit the env vars in `cloudbuild.yaml` in a PR. Console edits are overwritten on the next deploy.
- **Roll back:**
  ```bash
  gcloud run revisions list --service=intrinsica --region=$REGION
  gcloud run services update-traffic intrinsica --region=$REGION --to-revisions=<GOOD_REVISION>=100
  ```
  Then fix forward with a PR. After it deploys, `gcloud run services update-traffic intrinsica --region=$REGION --to-latest` returns traffic to the newest revision.
- **Logs:** Cloud Run → `intrinsica` → Logs. Save this Logs Explorer query as "Yahoo errors":
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="intrinsica"
  (textPayload=~"429|Too Many Requests|YFRateLimit|rate limit" OR severity>=ERROR)
  ```
  Frequent hits mean Yahoo is throttling Cloud Run IPs; revisit §7.
- **Cost:** Billing → Reports, filtered to project Intrinsica.

---

## 9. Code and repo changes (for the implementation plan)
1. A root `Dockerfile` (multi-stage) and root `.dockerignore`. Remove `backend/Dockerfile` and `backend/.dockerignore`.
2. `cloudbuild.yaml` and `cloudbuild-pr.yaml` at the repo root.
3. `backend/main.py`: public-mode router gating, static-file and SPA serving, the `/api/*` 404, and the `www` → apex redirect.
4. `backend/services/sheets.py`: the ADC fallback.
5. `backend/services/rate_limit.py` (new, extracted from `routers/events.py`). `routers/landing.py` gets a 429 limit.
6. `backend/landing/cache.py`: `LANDING_CACHE_MAX_ENTRIES` (default 256).
7. A backend test for chip-list sync (`main.py` ↔ `Hero.tsx`).
8. `frontend/src/App.tsx`: `VITE_PUBLIC_MODE` route gating. `vite-env.d.ts` types. A friendly message for a landing-analysis 429.
9. Delete `frontend/vercel.json`, `backend/railway.json` and `render.yaml`. Rewrite `DEPLOY.md` as §8. Update both `.env.example` files (drop the Vercel and Agent Stock wording; document the new vars).
10. Tests for each backend behaviour change (public mode, static/SPA and the API 404, the redirect, the ADC branch, the landing limiter, the cache cap). A frontend test for public-mode routes and the 429 message.

## 10. Out of scope
- Shareable ticker links `/t/{TICKER}` with per-ticker OG tags and images (next project; D2).
- A load balancer, Cloud Armor or CDN.
- A licensed market-data feed.
- Deleting the analyst code.
- Staging environments.
- The pricing trust copy (separate parked item).

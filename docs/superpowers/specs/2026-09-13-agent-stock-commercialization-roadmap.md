# Agent Stock Commercialization — Decomposition & Sequencing Roadmap

**Date:** 2026-09-13
**Status:** Draft for review (decomposition only — not an implementation spec)
**Scope note:** This document decomposes the `MonetizationPlan/` PRD set into
independent, individually-shippable sub-projects and sequences them by *cheapest
path to first paid user*. Each sub-project below gets its own
brainstorm → spec → plan → implementation cycle later; this roadmap only
establishes what the pieces are, what they depend on, and what order to build
them in.

**Out of scope for the entire program (per owner decision):**
- **B2B / advisor tier** — ignored entirely. Not planned, not sequenced, not
  challenged. (PRD Section 5 Phase 3, PRD Section 1 Tiers 4–5, all B2B legal
  wrappers.)
- **Shared-engine extraction** — the four engines are *copied* at fork time and
  allowed to diverge. No shared package / submodule is planned. Manual
  cherry-picking of engine improvements between repos is accepted and left out
  of scope.

---

## 1. Guiding decisions carried in from the plan pressure-test

These conclusions from the 2026-09-13 pressure-test shape the sequencing below.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Data-feed + licensing is the load-bearing risk; de-risk it FIRST as a spike, before committing any migration work.** | The product's substance is calibration against yfinance's exact field semantics. Any provider swap re-validates every distortion guard and re-baselines 500+ tests. Redistribution rights (publishing computed values publicly / via API) are a separate, pricier license and are mandatory for a public product. |
| D2 | **No Next.js migration for launch.** Achieve crawlable pages via SSG / prerendering (or FastAPI-served pre-rendered HTML). | The frontend is already React 19 + react-router-dom 7 + Vite 8 + TS + Tailwind + Radix. Next.js is a rewrite, not an upgrade, and is the heaviest possible answer to "make ~130 pages crawlable." |
| D3 | **No Redis, no Celery/RQ for launch.** | Postgres serves a few hundred precomputed rows trivially; the existing bounded worker pool + cron already handles batch. Defer until a metered API or real scale need appears. |
| D4 | **No LLM "Bear-Case" agent for launch.** | Contradicts the core "deterministic, no LLM in compute path" differentiator; reintroduces per-query cost, prompt drift, 10-K hallucination risk, and advice-shaped output. Park as a later experiment. |
| D5 | **Sheets → Postgres IS required** and is the one clearly-justified migration (auth / multi-tenancy / row-level isolation are impossible on Sheets). Skip the historical-snapshot "charting" table for launch. | |
| D6 | **Ticker-universe expansion is a prerequisite for the SEO thesis, not a Phase 2 afterthought.** | You can only rank for tickers you cover; ~130 (mostly megacaps) is both too few and the most competitive SERPs. SEO-led acquisition needs breadth. Its timing is gated by the D1 data-feed decision (rate limits / cost). |
| D7 | **Legal review is a launch-gating item and must run in parallel from the start**, with a real securities attorney — focused on the *advice-shaped* surfaces (tier labels like "Asymmetric Upside"/"Value Trap", and the newsletter framing), not just boilerplate disclaimers. AI-drafted legal copy is not shippable as-is (it contains errors in the operative clauses). | |

---

## 2. Repo & access strategy — Option 1 (Two Repos)

**Decision:** Fork a new commercial repository. The current repo, its Render
deployment, its Google Sheets datastore, and its yfinance data path **remain
untouched** and continue to serve as the owner's permanent, free, unrestricted
personal tool.

- **Personal instance:** the existing repo/deploy as-is. No auth, no billing, no
  paywall, no changes forced by commercialization. This is how the owner keeps
  unrestricted access — there is **no auth-bypass backdoor** anywhere in the
  commercial codebase (PRD Section 6's env-flag bypass is therefore **not
  adopted**; if a local offline mode is ever wanted, it lives only in the
  personal repo as a dev convenience).
- **Commercial instance:** a clean fork with its own repo, its own deployment
  pipeline, its own domain, and its own datastore. All commercialization work
  (Postgres, auth, billing, paywall, SEO, PWA) happens **only here**.
- **Engine divergence:** accepted and unmanaged (per owner decision). The four
  engines are copied at fork time; future improvements are synced manually if
  and when desired. No shared package is built.

**Implication for sequencing:** because personal access is fully preserved by
the untouched personal repo, the commercial repo does **not** need a comped-admin
account or any special owner-access mechanism. This removes a whole class of work.

---

## 3. Sub-project decomposition

Each sub-project is independently understandable and shippable, with a single
clear purpose. `SP0` is setup; `SP1` is a gating spike; `SP2`–`SP6` are the MVP
critical path to first revenue; `SP7`–`SP8` are growth; the rest are explicitly
deferred.

### SP0 — Fork & commercial baseline
- **Purpose:** Stand up the commercial repo as a clean fork with a green test
  suite and its own deploy pipeline.
- **Scope:** New repo from current `HEAD`; new deployment target (Render or
  equivalent) wired to a throwaway/staging domain; CI running the existing
  pytest suite; strip nothing engine-related (engines copied verbatim).
- **Depends on:** nothing.
- **Deferred out:** any datastore/auth/billing change (later SPs).

### SP1 — Data-feed & licensing spike *(GATING — do before SP2+)*
- **Purpose:** Answer the crux question cheaply before building on top of it.
- **Scope (output is a decision + budget, not production code):**
  - Compare candidate providers (FMP, Polygon.io, others) on: **redistribution
    license cost**, field coverage vs. the inputs the four engines actually
    consume, and rate limits at the target ticker volume (SP7).
  - Map which distortion guards are keyed to yfinance-specific field semantics
    and would need re-validation under each provider.
  - Produce a recommendation: which provider (or "stay on yfinance for MVP,
    accept ToS risk, defer redistribution"), the recalibration burden estimate,
    and the monthly cost that any pricing model must clear.
- **Depends on:** nothing (can run parallel to SP0).
- **Note:** This spike's outcome directly gates SP7 (expansion) and informs
  pricing.

### SP2 — Persistence migration: Google Sheets → PostgreSQL
- **Purpose:** Replace Sheets with a relational store that can support
  multi-tenancy and isolation.
- **Scope:** Schema for `users`, `subscriptions`, `watchlists`,
  `ticker_snapshots` (latest snapshot only). Port the existing read/recalc paths
  to Postgres. Keep the data-feed decision from SP1 orthogonal (migrate storage
  first; data-source swap, if any, is its own change).
- **Depends on:** SP0.
- **Deferred out:** historical-versions/charting table; Redis cache.

### SP3 — Authentication + multi-tenancy + click-wrap TOS
- **Purpose:** Real user accounts with hard data isolation.
- **Scope:** Auth provider (Clerk or Supabase Auth); row-level isolation so no
  user can read/mutate another's watchlists; mandatory unchecked click-wrap TOS
  box at registration with **timestamped acceptance logged** in Postgres.
- **Depends on:** SP2.

### SP4 — Billing & entitlements (Stripe)
- **Purpose:** Take money and toggle features by tier.
- **Scope:** Stripe subscriptions for the B2C tiers (Premium; Pro optional at
  launch); a webhook worker that flips entitlements on subscribe/cancel/change
  in real time. Entitlement flags read by the gating layer (SP5).
- **Depends on:** SP3.
- **Deferred out:** metered/API billing (Tier 5); B2B seats (excluded).

### SP5 — Paywall & server-side entitlement gating
- **Purpose:** Free Quality Score public; Fair Value, Moat, and Risk/Reward
  gated.
- **Scope:** **Server-side** gating is the non-negotiable core: premium values
  must never be sent in unauthenticated/guest JSON payloads (guests/crawlers
  receive empty or filler fields). Client-side blur is presentation only, on top
  of already-absent data. Upgrade CTA modals on gated blocks.
- **Depends on:** SP4 (entitlements), SP2 (data), SP3 (identity).

### SP6 — Public SEO stock pages (MVP crawlability)
- **Purpose:** The organic-acquisition surface and the first-paid-user funnel.
- **Scope:** Public `/stocks/[ticker]` routes rendered so crawlers see full HTML
  (SSG/prerender per D2 — **no Next.js**); `sitemap.xml`; per-page meta title/
  description/OG tags and Schema.org JSON-LD; clean indexable 404 for unknown
  tickers; persistent legal-disclaimer footer (see SP-Legal). Free Quality block
  visible; premium blocks gated per SP5.
- **Depends on:** SP5.

> **MVP / first-revenue line:** SP0 → SP1 → SP2 → SP3 → SP4 → SP5 → SP6, with
> SP-Legal running in parallel. Everything below is growth, built only after the
> funnel is live and generating signal.

### SP7 — Ticker-universe expansion
- **Purpose:** Make the SEO thesis actually viable (D6).
- **Scope:** Expand coverage well beyond ~130 across major US exchanges, sized to
  what SP1's data-feed decision affords (rate limits / cost). Batch pipeline
  scaling stays on the existing bounded worker pool + cron (no Celery per D3).
- **Depends on:** SP1 (data feed), SP6 (pages to expand into).

### SP8 — PWA + growth SEO surfaces
- **Purpose:** Mobile installability and additional organic surfaces.
- **Scope:** `manifest.json` + service worker (network-first for calc endpoints,
  cache-first for static shell, offline watchlist fallback banner); public
  leaderboards ("top N by structural metric"); automated data-driven newsletter
  (**pending SP-Legal sign-off on recommendation-shaped framing**).
- **Depends on:** SP6 (and SP7 for leaderboards/newsletter to be meaningful).

### SP-Legal — Compliance hardening *(parallel, launch-gating — D7)*
- **Purpose:** Insulate an *investment* product from liability, correctly.
- **Scope:** Securities-attorney-reviewed TOS (Limitation of Liability, AS-IS,
  Indemnification), persistent footer disclaimer, per-leg `[i]` tooltips,
  slider-scenario disclaimers, and — the exposed edge — attorney review of the
  **tier labels** and any **newsletter** framing for investment-adviser risk. Fix
  the AI-draft errors before anything ships.
- **Depends on:** nothing to start; **blocks public launch (SP6) and the
  newsletter (SP8).**

---

## 4. Dependency graph & sequencing

```
        ┌─────────────────────────── parallel ───────────────────────────┐
 SP0 Fork/baseline        SP1 Data+licensing spike        SP-Legal (attorney)
        │                        │  (gates SP7, informs pricing)    │
        ▼                        │                                  │
 SP2 Postgres  ◄─────────────────┘                                  │
        ▼                                                           │
 SP3 Auth + multi-tenancy + click-wrap                              │
        ▼                                                           │
 SP4 Stripe billing + entitlements                                  │
        ▼                                                           │
 SP5 Server-side paywall gating                                     │
        ▼                                                           │
 SP6 Public SEO pages  ◄──────────── launch-gated by ───────────────┘
        │
        ├──► SP7 Ticker expansion   (needs SP1 outcome)
        └──► SP8 PWA + growth SEO   (newsletter needs SP-Legal sign-off)
```

**Critical path to first paid user:** SP0 → SP2 → SP3 → SP4 → SP5 → SP6, with
SP1 and SP-Legal running alongside and gating.

---

## 5. Explicitly deferred / out of scope (with rationale)

| Item | Disposition | Why |
|------|-------------|-----|
| B2B / advisor tier, PDF memos, portfolio audit, team seats | **Excluded entirely** | Owner decision. |
| Shared-engine package/submodule | **Not built** | Owner accepts divergence. |
| Next.js migration | **Not for launch** | Rewrite, not upgrade; SSG/prerender suffices (D2). |
| Redis cache | **Deferred** | No benefit at a few hundred rows (D3). |
| Celery / Redis Queue | **Deferred** | Existing worker pool + cron suffices (D3). |
| LLM "Bear-Case Challenge" agent | **Deferred** | Contradicts differentiator; cost/drift/legal risk (D4). |
| Historical-snapshot / charting table | **Deferred** | Launch scope creep (D5). |
| Data API tier (Tier 5) | **Deferred** | Needs metering + redistribution license clarity from SP1. |
| PRD Section 6 env-flag auth bypass | **Not adopted** | Option 1 fork preserves access without a backdoor. |

---

## 6. Open questions to resolve during the first sub-project brainstorms

1. **SP1 outcome:** which data provider, or yfinance-for-MVP with accepted ToS
   risk? This unblocks pricing and SP7 sizing.
2. **Pricing validation:** the pressure-test flagged $39–59/mo as high vs. comps
   (Simply Wall St, etc.). Not a build task, but should be validated before SP4
   pricing is hard-coded.
3. **Auth provider:** Clerk vs. Supabase Auth (Supabase also gives Postgres —
   possible SP2/SP3 consolidation). Decide at SP2 brainstorm.
4. **Pro tier at launch?** Or launch Premium-only and add Pro (alerts/expanded
   watchlists) post-revenue?

---

## 7. Next step

Per the brainstorming process, each sub-project gets its own cycle. The natural
first move is a **brainstorm of SP1 (data-feed & licensing spike)** — it gates
the most and is cheap to run — optionally in parallel with **SP0 (fork &
baseline)**, which has no dependencies. Neither is started until its own design
is approved.

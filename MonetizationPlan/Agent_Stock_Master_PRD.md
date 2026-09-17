# Product Requirement Document (PRD): Agent Stock Commercialization Platform

## 1. Executive Summary & Core Objective
Agent Stock is transforming from a single-user, personal investment utility backed by Google Sheets into a multi-tenant, enterprise-grade, web-based financial analytics platform. The core goal is to commercialize its highly calibrated, deterministic, non-LLM calculation engines (Fair Value, Quality Score, Moat Score, and Risk/Reward Tier) using a high-velocity, high-feedback **B2C-First Evolution Strategy** that naturally upscales into a lucrative **B2B Wealth Advisor Tier**.

The platform maintains its signature design philosophy: preserving absolute separation between valuation, fundamental business quality, long-term moat durability, and point-in-time trade execution risk rather than collapsing them into a single blended rating.

---

## 2. Product Phasing & Strategy Evolution

```
[Phase 1: B2C Launch (Months 1–6)] ──► [Phase 2: Authority Bridge (Months 6–12)] ──► [Phase 3: B2B Enterprise (Month 12+)]
  - Self-serve Web Platform             - Universe Expansion (1,000+ Tickers)     - "For Advisors" Tab Deployment
  - Free Quality / Paid Moat & FV        - Automated Financial Newsletter          - Client-Ready PDF Report Engine
  - Infrastructure & Logic Hardening    - B2B Organic Lead Generation             - Compliance Audit Trail Logging
```

- **Phase 1: The B2C Engine (Months 1–6):** Focuses heavily on codebase stability, user onboarding optimization, organic search presence (SEO), and securing the first 100 paying retail power-users.
- **Phase 2: The Reputation Bridge (Months 6–12):** Expands the covered ticker universe from 130 to 1,000+, launching structured outreach via data-driven newsletters on LinkedIn and Substack to attract high-value eyes.
- **Phase 3: The B2B Institutional Expansion (Month 12+):** Layers on the premium wealth advisor subscription tier, exposing programmatic report exporting and white-label client tools.

---

## 3. High-Level Technical Architecture & Migrations

To transition the prototype codebase (`backend/` packages: `valuation`, `screener`, `moat`, `risk_reward`) into a scalable cloud infrastructure, the development team must execute three core technical shifts:

```
┌───────────────────────────────┐     Paid API Stream (REST/Webhooks)     ┌─────────────────────────────────────┐
│  Financial Data Provider      │ ─────────────────────────────────────▶ │ FastAPI Microservices Engine        │
│ (Financial Modeling Prep /    │                                        │  • Multi-Tenant Scoring Workers     │
│  Polygon.io Commercial Feed)  │                                        │  • Real-Time Queue Orchestration    │
└───────────────────────────────┘                                        └──────────────────┬──────────────────┘
                                                                                            │
                                                  ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
                                                  ▼                                                                                   ▼
                               ┌─────────────────────────────────────┐                                             ┌─────────────────────────────────────┐
                               │     Redis Distributed Cache         │                                             │    PostgreSQL Multi-Tenant DB       │
                               │  - Caches computed ticker rows      │                                             │  - User tables & isolated rows      │
                               │  - Eliminates duplicate API charges │                                             │  - Saved watchlists & billing state │
                               └─────────────────────────────────────┘                                             └─────────────────────────────────────┘
                                                  │                                                                                   │
                                                  └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                                                                            ▼
                                                                           ┌─────────────────────────────────────┐
                                                                           │  Next.js App Router Frontend        │
                                                                           │  - Server-Side Rendered SEO Pages   │
                                                                           │  - Interactive DCF Value Sliders    │
                                                                           │  - Native Clerk Auth & Stripe UI    │
                                                                           └─────────────────────────────────────┘
```

1. **Data Feed Layer:** Deprecate the open-source `yfinance` parsing framework due to commercial terms-of-use constraints and IP block risks. Migrate to a commercial financial feed platform (e.g., Financial Modeling Prep or Polygon.io).
2. **Datastore Layer:** Deprecate Google Sheets. Implement **PostgreSQL** with appropriate normalization patterns for user profiles, watchlists, and billing flags, fronted by a distributed **Redis distributed cache** to control third-party data request expenses.
3. **Frontend Layer:** Upgrade the React+Vite architecture to a hybrid framework (e.g., **Next.js App Router**) to execute programmatic Server-Side Rendering (SSR) for seamless search engine indexing.

---

## 4. Universal Requirements Matrix

### 4.1 Security, Auth, & Access Control
- The system must integrate a cloud authorization standard (e.g., Clerk or Supabase Auth).
- Complete data isolation must be enforced via row-level security policies to ensure users cannot view or mutate other users' watchlists.

### 4.2 Billing, Webhooks, & Entitlements
- Integration with Stripe Billing is required to handle credit card validation, metered requests, and recurring subscription tokens.
- A background listening worker must process Stripe webhooks cleanly to toggle features on or off in real-time if a user cancels or changes tiers.

### 4.3 System Analytics & Error Logging
- All calculation pipelines must emit structured audit events to central logging tools (e.g., Sentry) to trace any structural data changes or API calculation failures immediately.

---

This is for informational purposes only. For medical advice or diagnosis, consult a professional. AI responses may include mistakes.

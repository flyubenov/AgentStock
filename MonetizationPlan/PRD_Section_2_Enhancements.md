# PRD Section 2: Essential Enhancements & Features Needed to Ship

## 1. Technical Infrastructure Migrations

```
  [ Legacy Architecture ]                     [ Production Target Infrastructure ]
┌─────────────────────────┐                 ┌──────────────────────────────────────┐
│ yfinance Scraper Feed   │   ─────────►    │ Commercial REST Data Feed (Licensed) │
└─────────────────────────┘                 └──────────────────────────────────────┘
┌─────────────────────────┐                 ┌──────────────────────────────────────┐
│ Google Sheets Database  │   ─────────►    │ PostgreSQL Database Core + Schema    │
└─────────────────────────┘                 └──────────────────────────────────────┘
┌─────────────────────────┐                 ┌──────────────────────────────────────┐
│ Single-User Python App  │   ─────────►    │ Clerk Auth + Stripe Webhook Gateway  │
└─────────────────────────┘                 └──────────────────────────────────────┘
```

### 1.1 Data Feed Modernization
- **Requirement:** Completely remove the open-source `yfinance` script from all production loops. Replace it with an enterprise REST financial data provider (e.g., Financial Modeling Prep or Polygon.io).
- **Functionality:** Create a unified interface abstraction data-layer so that internal pipelines query an internal contract layer rather than directly talking to external schemas.
- **Handling Rates:** Implement robust connection handling and request back-offs to remain compliant with data subscription tiers.

### 1.2 Datastore Architecture Transition
- **Requirement:** Deprecate Google Sheets. Set up a relational production instance (e.g., AWS RDS PostgreSQL or Supabase PostgreSQL).
- **Schema Constraints:** Construct relational models for `users`, `subscriptions`, `watchlists`, and `ticker_snapshots`. A historical table must capture all calculated versions of the 4 engine parameters over time to drive charting capabilities.
- **Caching Layer:** Set up a Redis layer running in front of the primary application nodes. The system must verify if a valid ticker calculation snapshot exists in Redis before pulling from database rows or requesting external paid APIs.

---

## 2. Advanced Product & AI Feature Implementations

### 2.1 Interactive Valuation Adjustment Engine (Sliders)
- **Frontend Capability:** Provide custom slider nodes on the dynamic React pages. Users can override default system assumptions such as **Terminal Growth Rate**, **Discount Rate (WACC Base Spread)**, or **Target EV/EBITDA Multiples**.
- **Backend Capability:** The FastAPI calculation worker must handle real-time override request bodies via endpoint queries, returning immediate calculations without modifying the master background data snapshots.

### 2.2 LLM "Bear-Case Challenge" Agent
- **System Logic:** Create a specialized analytical chat framework utilizing an execution model (e.g., Claude 3.5 Sonnet) connected via a semantic extraction library (e.g., LlamaIndex).
- **Context Boundaries:** The LLM cannot calculate raw numerical values. It accepts the numerical outputs from the deterministic database rows and cross-references them with raw text sections extracted from recent corporate 10-K filings.
- **Functional Output:** When a premium subscriber triggers the "Challenge Engine" action, the conversational window provides a well-structured response explaining why the asset was categorized in a specific tier (e.g., highlighting operational issues like poor cash conversion or leverage increases).

---

This is for informational purposes only. For medical advice or diagnosis, consult a professional. AI responses may include mistakes.

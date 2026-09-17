# Product Requirement Document (PRD)
## Section 5: B2C-First Execution Roadmap & B2B Expansion Cycles

### 1. Document Control
- **Title:** B2C-First Execution Roadmap & B2B Expansion Cycles
- **Component Owner:** Lead Software Engineer / Product Founder
- **Status:** Approved for Implementation
- **Target Audience:** Engineering, Product Marketing

---

### 2. Component Vision & Strategic Objective
The strategic objective of this roadmap is to establish a risk-mitigated path to commercialization. By launching a self-serve B2C product first, the platform gathers rapid user telemetry, hardens the quantitative scoring logic against diverse edge cases under public load, and builds search engine authority. Once stabilized, the system leverages this reputation to scale into a high-ticket, institutional-lite B2B tier targeting Registered Investment Advisors (RIAs) and wealth managers.

---

### 3. Chronological Phasing Blueprint

```
┌────────────────────────────────┐
│  Phase 1: B2C Core Validation  │  ► Timeline: Months 1–6
└───────────────┬────────────────┘  ► Metric: 100 Paid Subscriptions, Zero Data Stalls
                ▼
┌────────────────────────────────┐
│  Phase 2: Reputation Bridge    │  ► Timeline: Months 6–12
└───────────────┬────────────────┘  ► Metric: Index 1,000+ Tickers, Launch Active Newsletter
                ▼
┌────────────────────────────────┐
│  Phase 3: B2B Enterprise Ramp  │  ► Timeline: Months 12+
└────────────────────────────────┘  ► Metric: Secure High-Ticket Seat Contracts ($249+/mo)
```

#### 3.1 Phase 1: The B2C Core Validation (Months 1–6)
*   **Strategic Focus:** Production hardening, system stabilization under multi-tenant load, and core subscription monetization.
*   **Infrastructure State:**
    *   Complete migration from `yfinance` to a licensed financial API.
    *   Google Sheets replaced by PostgreSQL and Redis.
    *   Implementation of Clerk/Supabase Auth and Stripe Billing.
*   **Functional Deliverables:**
    *   Responsive web interface running Next.js for Server-Side Rendering (SSR).
    *   Publicly indexable stock profile pages displaying the free 0–10 Quality Score.
    *   Gated paywall protecting Fair Value methods, Moat calculations, and Risk/Reward tier indicators.
*   **Success Metrics:**
    *   Acquisition of **100 active paying retail subscribers** via self-serve channels.
    *   System availability >= 99.9% with zero data ingestion stalls or IP bans from financial data providers.

#### 3.2 Phase 2: The Reputation & Discovery Bridge (Months 6–12)
*   **Strategic Focus:** Portfolio scalability, data expansion, and building B2B discovery channels.
*   **Infrastructure State:**
    *   Expansion of data processing pipelines to track a universe of **1,000+ tickers** across all major US exchanges (NYSE, NASDAQ, AMEX).
    *   Batch processing cron jobs shifted to decoupled asynchronous tasks managed via Celery or Redis Queues.
*   **Functional Deliverables:**
    *   **Automated Data-Driven Financial Newsletter Engine:** A system that queries the PostgreSQL database weekly to isolate high-signal volatility anomalies (e.g., *“Top 5 Stocks Migrating into the Asymmetric Upside Tier this Week”* or *“Moat Score Upgrades Following 10-Q Filings”*).
    *   **Public Multi-Stock Leaderboards:** SEO-optimized landing pages displaying dynamically updated lists of the top 20 highest-scoring stocks in the market based on structural business metrics.
*   **Success Metrics:**
    *   Domain Authority growth driven by search engine crawl budgets.
    *   Capture of high-intent organic search impressions on LinkedIn and professional platforms, signaling awareness among investment professionals.

#### 3.3 Phase 3: The B2B Enterprise Tier Launch (Month 12+)
*   **Strategic Focus:** Enterprise monetization, workflow software expansion, and high-ticket sales.
*   **Infrastructure State:**
    *   Enterprise-tier multi-tenancy support (team accounts, seat licenses, shared company watchlists).
    *   Strict adherence to B2B performance Service Level Agreements (SLAs).
*   **Functional Deliverables:**
    *   **The "For Advisors" Portal:** A dedicated enterprise workspace accessible via top navigation routing.
    *   **Automated PDF Client Memo Generator:** A server-side printing utility that exports white-labeled investment theses.
    *   **Portfolio Health Audit Module:** A comprehensive reporting engine analyzing entire aggregated stock portfolios.

---

### 4. Technical Specifications: Phase 3 B2B Core Features

#### 4.1 Client-Ready White-Labeled PDF Memo Generation
*   **Functional Description:** A system enabling independent financial advisors to generate structured, professional PDF documents summarizing Agent Stock's deterministic metrics for any single ticker.
*   **Inputs:**
    *   Target Ticker String (`ticker`).
    *   Advisor Workspace Identity (`advisor_id`).
    *   Uploaded Advisor Firm Asset (`logo_file_url` or `firm_metadata`).
*   **Processing Framework:**
    *   The system initializes a backend PDF rendering container using a headless browser context (e.g., `Puppeteer`) or a native document canvas engine (e.g., `WeasyPrint`, `ReportLab`).
    *   The backend retrieves quantitative data from the database, formatting it into a pre-defined CSS template layout styled specifically for professional client interactions.
    *   An offline LLM orchestration layer safely parses text summary data to construct a descriptive commentary block (e.g., explaining why a stock was assigned a specific classification tier), appending it to the quantitative calculations.
*   **Output Parameters:**
    *   A beautifully formatted, un-editable **2-Page PDF document**.
    *   **Page 1:** Structured header containing the Advisor Firm’s custom branding and logo, followed by the specific stock classification profile, the 0–10 Quality Score breakdown, and the Moat durability overview.
    *   **Page 2:** Explicit Fair Value leg weight visualization (DCF, EV/EBITDA, P/E matrices), Risk/Reward tier justifications, and a standardized financial liability disclaimer.
*   **Security & Compliance Constraints:**
    *   The generated PDF document must be fully watermarked or signed via cryptographic hash to ensure the advisor cannot modify the deterministic metrics externally before passing them to a client.

#### 4.2 Portfolio Health Audit Module
*   **Functional Description:** A high-end workflow feature allowing advisors to review and audit a prospective client's entire current investment portfolio in an aggregated, clean layout.
*   **UI/UX Component Requirements:**
    *   **Bulk CSV Upload Interface:** A drag-and-drop file target parsing standard portfolio exports containing Ticker symbols and holding allocations (e.g., Share Count or Weight Percentage).
    *   **Aggregated Portfolio Matrix View:** An active tabular interface displaying all portfolio holdings alongside their independent Agent Stock ratings.
*   **Data Processing & Aggregation Logic:**
    *   The backend validates all uploaded tickers against the local database, triggering immediate background processing jobs for any unrecognized valid symbols.
    *   **Blended Portfolio Quality Rating:** The system computes a weighted average fundamental quality score:
    
    Weighted Portfolio Quality = Sum( Quality Score_i * ( Value of Holding_i / Total Portfolio Value ) )

    *   Concentrated Risk Flags: A separate algorithmic rule flags any holding tagged as a Value Trap by the Risk/Reward engine that occupies >= 5% of the total uploaded portfolio weight.
    *   Aggregated Margin of Safety: Calculates the difference between the blended portfolio market price and the blended internal Fair Value target.

---

### 5. Analytics, Telemetry, and Guardrails

#### 5.1 Telemetry Requirements
*   **B2C Metrics Tracking:** Implement instrumentation tracking page views to premium conversion rates on every distinct `stocks/[ticker]` endpoint to maximize paywall messaging performance.
*   **B2B Activity Auditing:** Every instance of a PDF Generation call or Portfolio CSV Upload must be logged with timestamp indicators and user IDs to prevent systemic automated scraping of the raw dataset under single user licenses.

#### 5.2 Regulatory & Legal Guardrails
*   **B2C Footers:** Every page layout must display a prominent legal note: *“Agent Stock provides automated quantitative financial data modeling tools for informational analysis. Nothing on this platform constitutes personalized investment advice.”*
*   **B2B Client Disclaimers:** Every exported PDF memo generated for an advisory client must automatically attach a compliant fiduciary wrapper detailing that the ratings are derived from algorithmic processing of public data endpoints and do not replace the primary due diligence obligations of the professional manager.

# PRD Section 1: Recommended Business Models & Monetization Paths

## 1. Feature / Strategy Matrix
The product capitalizes on its deterministic, cost-reproducible calculations to offer distinct software experiences targeting retail power-users, institutional allocators, and third-party algorithmic platforms.

| Strategic Tier | Core Customer | Targeted Price Point | Functional Access Delivery | Primary Core Hook |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Free Layer** | Anonymous Web Traffic / Casual Investors | \$0 | Un-authenticated public responsive pages. | Baseline 0-10 Quality Score, core operational sector metadata, and industry descriptions. |
| **Tier 2: Premium B2C** | Self-directed retail value investors, swing traders | \$39 – \$59 / month | Self-service multi-tenant authenticated dashboard portal. | Full multi-leg Fair Value breakdown (DCF, EV/EBITDA, P/E ratios) and detailed Moat metrics. |
| **Tier 3: Pro B2C** | Active portfolio managers, retail power users | \$89 / month | Real-time email/SMS system hooks and expanded dynamic watchlists. | Point-in-time Risk/Reward axis alerts ("Asymmetric Upside", "Value Trap" logs) and on-demand recalc triggers. |
| **Tier 4: B2B Enterprise** | Registered Investment Advisors (RIAs), wealth firms | \$250 – \$500 / month / seat | Dedicated team workspace portal with white-label configuration settings. | Automated, compliance-ready Client Investment Thesis Memos and aggregated Portfolio Audits. |
| **Tier 5: Data API** | Fintech startups, programmatic algo developers | \$199+/mo metered base | Programmatic REST / GraphQL endpoint gateway access layers. | Direct numeric delivery of calculated flags via routes like `/api/v1/moat/ticker`. |

---

## 2. Detailed Value Architecture & Entitlements

```
               [ Guest Visitor ]
                       │
                       ▼
          ┌─────────────────────────┐
          │ Free Tier Landing Page  │ ──► (Quality Score & Profile)
          └─────────────────────────┘
                       │
                       ▼  Stripe Checkout ($39-$59/mo)
          ┌─────────────────────────┐
          │ Premium B2C Dashboard   │ ──► (Fair Value Legs & Moat Specs)
          └─────────────────────────┘
                       │
                       ▼  Stripe Upgrade ($89/mo)
          ┌─────────────────────────┐
          │ Pro B2C Alert Engine    │ ──► (Risk/Reward Axis & Live Recalc)
          └─────────────────────────┘
                       │
                       ▼  Enterprise Contract ($250+/mo)
          ┌─────────────────────────┐
          │ B2B Wealth Advisor Hub  │ ──► (Compliant PDF Export & Audits)
          └─────────────────────────┘
```

### 2.1 Free Tier Target Specifications
- Access is public and does not require authentication.
- Users can view the composite 0-10 Quality Score alongside basic descriptive stock data.
- The interface restricts access to deep analytical fields by overlaying payment modal prompts when premium variables are touched.

### 2.2 Premium B2C Target Specifications
- Access is gated behind active Stripe subscriptions.
- Exposes all structural calculations used to build the final Intrinsic Fair Value estimate.
- Renders detailed historical information on capital distribution patterns and Moat sustainability thresholds.

### 2.3 Pro B2C Target Specifications
- Provides immediate notifications when a target security migrates into extreme scoring brackets (e.g., hitting an "Asymmetric Upside" or "Value Trap" signal).
- Authorizes users to execute up to 50 active ticker watchlists with dedicated background worker queues.

### 2.4 B2B Enterprise Target Specifications
- Enables advisors to run detailed compliance audits and multi-page printable portfolio summaries matching strict legal parameters.
- Provides granular team seat management capabilities.

### 2.5 Data API Target Specifications
- Grants full pipeline access without an HTML web app frontend wrapper.
- Enforces access rules using individual cryptographically signed API token headers.

---

This is for informational purposes only. For medical advice or diagnosis, consult a professional. AI responses may include mistakes.

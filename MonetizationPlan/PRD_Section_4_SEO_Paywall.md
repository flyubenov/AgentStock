# PRD Section 4: Metadata Generation & Indexable SEO Web Pages

## 1. Architecture for Indexable Web Pages
To drive unpaid organic customer acquisition, Agent Stock will expose its 130+ stock profiles to search engines using programmatic Server-Side Rendering (SSR). The target architecture prevents indexation gaps by serving full HTML profiles directly to automated crawlers.

```
                  ┌──────────────────────┐
                  │ Google / Bing Engine │
                  └──────────┬───────────┘
                             │
                             ▼ Requests: /stocks/AAPL
                  ┌──────────────────────┐
                  │ Next.js Server Node  │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│ Fetch Metadata from DB│         │ Run Deterministic Calcs│
└───────────┬───────────┘         └───────────┬───────────┘
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ Generates Complete   │
                  │ HTML Profile Page    │
                  └──────────┬───────────┘
                             │
                             ▼ Renders response
                  ┌──────────────────────┐
                  │ Browser/Crawler view │
                  └──────────────────────┘
```

### 1.1 Target Routing Layout
The application must support a structured, programmatic directory format: `agentstock.com/stocks/[ticker]`. Passing an invalid identifier must immediately return a clean, indexable 404 error page recommending active database assets.

### 1.2 Programmatic Sitemap Delivery
A dynamic endpoint must output an XML dataset at `agentstock.com/sitemap.xml`. This file must list all monitored tickers, their calculation timestamps, and update interval flags.

---

## 2. Human & Bot Metadata Specifications

Every stock target view must construct metadata containers inside the output document header.

### 2.1 Bot-Facing HTML Layout Specifications
```html
<title>Apple (AAPL) Fundamental Quality Score & Investment Analysis | Agent Stock</title>
<meta name="description" content="Explore the comprehensive 0-10 quantitative Quality Score for Apple (AAPL). Review detailed margin trajectories, structural returns on capital, and balance sheet leverage analytics." />
<meta property="og:title" content="Apple (AAPL) Investment Research Framework - Agent Stock" />
<meta property="og:description" content="Review intrinsic values, defensive moat scores, and risk/reward setups for AAPL." />
<meta property="og:type" content="website" />
```

### 2.2 Schema.org JSON-LD Structured Data
To trigger rich graphical components in search engine results, an operational data schema block must be injected on every profile view:
```json
{
  "@context": "https://schema.org",
  "@type": "FinancialProduct",
  "name": "Apple Inc. Equity Analysis Snapshot",
  "tickerSymbol": "AAPL",
  "description": "Deterministic quantitative system tracing intrinsic financial health parameters.",
  "provider": {
    "@type": "Organization",
    "name": "Agent Stock Platform"
  }
}
```

---

## 3. Visual UI Paywall & Gating Design

```
┌────────────────────────────────────────────────────────────────────────┐
│  🟢 PUBLIC DATA VIEW (Visible to Crawlers & Guests)                    │
│  [AAPL] Apple Inc. | Technology - Consumer Electronics                 │
│  Quality Score: 8.4 / 10  [====================]                       │
│  - Returns on Capital: Excellent (ROIC-WACC Spread +12.4%)             │
│  - Balance Sheet: Solid (Net-Debt/EBITDA 0.4x)                         │
├────────────────────────────────────────────────────────────────────────┤
│  🔒 PREMIUM PAYWALL INTERFACE (Obscured Content Layer)                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 🚫 Fair Value Analysis Engine                                    │  │
│  │ [ BLURRED TEXT ELEMENT ] Intrinsic Target: $XX.XX                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 🚫 Economic Moat Assessment                                      │  │
│  │ [ BLURRED TEXT ELEMENT ] Economic Gate Status: XXXXXX            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 🚫 Risk/Reward Trading Setup                                     │  │
│  │ [ BLURRED TEXT ELEMENT ] Operational Allocation Tier: XXXXXXX     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│            [ 💳 UNLOCK INSTITUTIONAL VALUATION LEG DETAILS ]          │
│                     Access Premium Features for $39/mo                 │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Un-Gated Visual Layout Components
- Render complete textual name tags, operational sector identifiers, and general summary descriptions.
- Expose the comprehensive **0-10 Quality Score** card layout, complete with the sub-component calculation breakdowns.

### 3.2 Gated Visual Layout Components
- **Fair Value Block:** The absolute currency target figure and internal calculation leg allocations must be visually obscured.
- **Moat Assessment Block:** The final 0-100 summary figure and data metrics must be hidden from view.
- **Risk/Reward Block:** The current trading category ("Asymmetric Upside" or "Value Trap") must be fully protected by the paywall element.

### 3.3 Paywall Engineering Constraints
- Premium fields must be entirely obscured using visual CSS styling components (e.g., `filter: blur(8px)` layouts).
- The underlying high-value numerical calculations **must never be sent in the JSON data payload** of un-authenticated requests. Crawlers and guests should receive empty parameters or generalized filler strings for premium properties. This ensures malicious users cannot bypass the subscription system by inspecting browser network components.

---

This is for informational purposes only. For medical advice or diagnosis, consult a professional. AI responses may include mistakes.

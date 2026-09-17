# Agent Stock — Product Summary, Business Model & Pitch

> **What this document is.** A single, self-contained summary of *what Agent Stock does*
> and *how it is planned to be monetized*, written to be handed to a third party — a human
> reviewer or another AI agent — to **pressure-test and validate**. It is factual first and
> promotional second: current limitations (data source, persistence, single-user
> deployment) are stated plainly, because a validator needs them.
>
> **Date:** 2026-09-15 · **Status:** pre-launch; monetization is at the *smoke-test /
> demand-validation* stage, not built.

---

## ⭐ The headline capability (read this first)

**Agent Stock computes a full four-engine analysis of *any* stock the user names —
on demand, from live data, in a matter of seconds. It does not look values up. It
calculates them on the fly.**

- **Any ticker, not a fixed list.** The user types a ticker; the engine pulls that
  company's current financials and computes a fresh result. There is no requirement that
  the ticker was seen before. The curated ~130-name database is a *cache and a browsing
  funnel*, **not** the product — the product is the compute.
- **Not pre-computed.** Every number is produced at request time by deterministic financial
  models running over the company's latest fundamentals. Nothing is a stored lookup of a
  human analyst's opinion.
- **Seconds, not modeling sessions.** What would take an analyst hours of spreadsheet
  work — classify the company, pick valuation methods, run a DCF, sanity-check against
  accounting distortions — the engine does in seconds, reproducibly.
- **Parallel by design.** The engine evaluates **many tickers concurrently** via a
  bounded, rate-limit-aware worker pool. A user can point it at a whole watchlist and get
  the full grid back, computed in parallel, rather than one-at-a-time.
- **Four independent answers per ticker, every time:** **Fair Value**, **Quality Score**,
  **Moat Score**, and **Risk/Reward rating** — each a separate engine, computed live.

Everything else in this document — the tiers, the pricing, the funnel — is built on top of
that one capability. **The thing being sold is real-time, on-demand, any-ticker
computation of institutional-style analysis.**

---

## 1. What Agent Stock is

Agent Stock is an **automated equity-analysis engine**. Given a stock ticker, it computes
four independent, quantitative assessments of the company:

| Engine | Question it answers | Output |
|---|---|---|
| **Fair Value (FV)** | What is the intrinsic value per share — cheap or expensive vs. price? | A dollar fair value + % upside/downside |
| **Quality Score** | How good is the *business* on fundamentals? | A 0–10 score, sector-aware |
| **Moat Score** | How *durable* is the company's economic advantage? | A 0–100 score |
| **Risk / Reward (R-R)** | Is the risk-adjusted setup attractive *right now*? | A reward÷risk ratio + tier label |

The four engines are deliberately **not blended into one number**. The design philosophy is
that *valuation, business quality, moat durability, and tradability are distinct axes* an
analyst wants to see separately: a cheap stock (good FV) can be a poor business (low
Quality); a great business (high Quality/Moat) can be a bad entry point (poor R-R).

### Why it is defensible

- **Deterministic — no LLM in the compute path.** All four scores come from explicit
  financial formulas and calibrated thresholds. No per-ticker AI inference cost, no prompt
  drift, fully reproducible. (An LLM is used *offline* to develop and validate the logic,
  never at runtime.)
- **Hardened against real-world distortions.** The engines have been calibrated against
  dozens of documented edge cases — spin-offs, dual-class share counts, one-off tax
  releases, acquisition goodwill, cyclical peaks, capex-heavy build-outs, crypto-miner
  mis-classification, and more. **This accumulated calibration is the real technical moat
  of the product** and is not trivially reproducible. 500+ automated tests cover it.
- **Cheap to run.** Compute is light (no model inference at query time); the only variable
  cost is the market-data feed.

---

## 2. How it works (current architecture)

```
Live market data ──▶  Python / FastAPI backend ──▶  results
 (yfinance today)      • valuation      → Fair Value
                       • screener       → Quality Score
                       • moat           → Moat Score
                       • risk_reward    → Risk/Reward
                       • orchestrator   → parallel batch runs
                              │
                              ▼  cached for browsing
                       Google Sheets (datastore today)
                              │
                              ▼
                       React / Vite frontend (browse, filter, recalc)
```

- **Backend:** Python + FastAPI. Each engine is an isolated package (`valuation/`,
  `screener/`, `moat/`, `risk_reward/`) with its own tests. A dedicated, bounded worker
  pool with adaptive rate-limit pacing runs data fetches **concurrently** — this is what
  makes parallel multi-ticker evaluation fast and stall-free.
- **The compute is live and on-demand.** For any ticker, a recalculation pulls the latest
  fundamentals and runs all four engines in seconds. The stored rows are a **cache/browse
  layer**, not the source of the numbers.
- **Persistence (today):** Google Sheets — one row per ticker, one column per engine, plus
  a saved-watchlists tab. Fine for a personal universe; not a multi-tenant production
  backend (see §6).
- **Frontend:** React + Vite — browse, filter, saved watchlists, scoped "Recalculate All".
- **Data source (today):** Yahoo Finance via the open-source `yfinance` library. Free —
  good for margins, but a **terms-of-use / redistribution dependency** to resolve before
  commercial launch (see §6).

*(Brief engine internals are in `Agent_Stock_Capabilities_Overview.md`: FV blends up to 9
valuation legs weighted by a company-type classifier; Quality is a sector-profiled
4-section composite; Moat is a 40/50/10 magnitude/durability/cash model with an
economic-profit gate; R-R is a 12-signal reward-vs-risk ratio mapped to tiers.)*

---

## 3. The core value proposition

**For a self-directed investor:** *"Type any ticker. In seconds, get a fair value, a
quality score, a moat score, and a risk/reward read — computed live from the latest
financials, not pulled from a stale list. Point it at your whole watchlist and get the
grid back at once."*

This collapses hours of spreadsheet modeling into one action, and — unlike a static
screener or a fixed research database — **works on whatever the user asks for, the moment
they ask.** The separation of the four axes is a differentiator against tools that hide
everything behind a single star-rating.

---

## 4. Business model

### 4.1 Positioning: the compute is the product, the database is the funnel

The monetized asset is **on-demand computation of any ticker**, plus the premium engines
(Moat, R-R) and multi-ticker/watchlist workflows. A public, crawlable set of pre-computed
pages (the ~130-name universe, later expanded) exists to **acquire traffic via SEO for
free** and to demonstrate the engines — then convert that traffic to the real value:
*compute on demand for the tickers **they** care about.*

### 4.2 Tier ladder (current, reframed plan)

| Tier | Price (target) | What the user gets |
|---|---|---|
| **Free** | \$0 | Quality Score (0–10) + basic profile, on public/indexable pages for the covered universe. The SEO funnel. |
| **Mid** | ~\$25 / mo | Everything in Free **+ Fair Value** (the full multi-leg intrinsic-value estimate). |
| **Premium** | ~\$35 / mo | Everything in Mid **+ Moat Score + Risk/Reward + on-demand compute of *any* ticker + saved watchlists (parallel multi-ticker evaluation).** |

The **on-demand "any ticker" compute and watchlists are intentionally the Premium hook** —
they are the capability nothing else on the free/SEO layer provides, and the reason a power
user pays.

> **Note on scope.** An earlier, more expansive PRD draft proposed five tiers up to a
> \$250–500/seat B2B advisor tier and a \$199+/mo metered API. Those are **explicitly
> deferred / out of scope** for launch (see §7). The three-tier B2C ladder above is the
> current plan.

### 4.3 Cost & margin shape

- **Variable cost is dominated by the market-data feed.** On the free `yfinance` source,
  marginal cost is ~zero but carries ToS/redistribution risk. A licensed commercial feed
  (e.g., Financial Modeling Prep, Polygon.io) is likely required for a public product and
  becomes the **floor any pricing must clear** — de-risking this is the #1 open item (§7).
- **Compute is cheap and deterministic** — no per-query AI cost, so gross margin is
  attractive once the data-license cost is fixed.

---

## 5. Go-to-market: validate demand *before* building

The current stance is deliberately conservative: **do not build the SaaS until willingness
to use/pay is demonstrated.**

- **Smoke test (next concrete step):** a public, rate-limited **interactive demo** — *type
  any ticker → live Quality Score, with Fair Value / Moat / R-R shown blurred* — behind an
  **email "unlock early access"** fake-door gate. Measures real demand for the on-demand
  compute cheaply, before any billing or auth is built.
- **Traffic for the test comes from active channels** (small paid ads and/or organic forum
  posts). **SEO is *not* the smoke-test channel** — it takes 6–12 months and is a *later
  growth* engine, not a validation tool.
- **Rough go/no-go:** ~2–3 weeks, a few hundred visitors; strong signal ≈ ≥8% email
  capture plus unprompted "when can I pay" interest.

---

## 6. Honest current-state limitations (a validator must weigh these)

- **Data dependency.** Runs on free `yfinance` today. Redistributing computed values
  publicly / via API needs a **paid data license**; swapping providers means
  **re-validating every distortion guard** (the engines are calibrated to the current
  feed's exact field semantics) and re-baselining the test suite. This is the biggest
  single risk and cost.
- **Single-user architecture today.** No authentication, no multi-tenancy, no billing.
  Google Sheets is the datastore. A commercial launch requires **Sheets → PostgreSQL**,
  auth + row-level isolation, and Stripe billing — none of which exist yet.
- **Coverage is a curated watchlist** (~130, mostly mega-caps) for the *pre-computed*
  pages. The on-demand engine already computes any US-listed ticker, but the public/SEO
  surface must be broadened to rank.
- **UI serves cached rows; it is not live-per-view.** The engine computes live *on
  recalculation / on demand*; the browse grid shows the last stored result. (This is a
  caching choice, not a limit of the compute.)
- **Not financial advice.** Tier labels like "Asymmetric Upside" / "Value Trap" are
  advice-*shaped* and need real securities-law review before public launch.
- **Commodity-perception risk.** Scores compete with entrenched incumbents (Morningstar,
  Simply Wall St, Bloomberg). The defensibility case rests on the *on-demand any-ticker
  compute*, the *four-axis separation*, and the *calibration depth* — a validator should
  probe whether that is enough differentiation to command the target price.

---

## 7. What's explicitly deferred / out of scope for launch

Decided during an earlier pressure-test of the PRD set:

- **B2B / advisor tier and the metered Data API** — excluded from the launch program.
- **Next.js rewrite, Redis, Celery/RQ, and an LLM "bear-case" agent** — dropped for launch
  (the last one contradicts the "no LLM in compute path" differentiator).
- **The one required migration is Sheets → PostgreSQL.** Crawlable pages are achieved via
  static prerendering, not a framework rewrite.
- **Repo strategy:** the commercial product is a **fork**; the owner's personal instance
  (free, unrestricted) stays untouched. Engine improvements are synced manually; no shared
  package.

---

## 8. Questions for a third-party validator

A reviewer or agent pressure-testing this plan should focus on:

1. **Willingness to pay.** Is ~\$25/\$35/mo realistic for on-demand compute + Moat/R-R +
   watchlists, given free/cheap incumbents? What would move the smoke-test signal?
2. **Differentiation.** Is "compute *any* ticker live, four separated axes, deep
   distortion-calibration" a *durable* edge, or a feature incumbents can match?
3. **Data economics.** Does a licensed feed's cost (redistribution rights included) leave a
   viable margin at these prices and expected volume?
4. **Funnel realism.** Free-Quality-pages → SEO → Premium conversion — plausible rates, and
   is the "any-ticker compute" hook strong enough to convert?
5. **Smoke-test design.** Is the email fake-door a fair proxy for *paid* demand, or does it
   over-read intent? What cheap addition would test price directly?
6. **Sequencing / risk.** Right call to validate demand before building auth/billing/
   Postgres? Any launch-blocking risk (esp. legal, data ToS) underweighted here?

---

*Source material: `Agent_Stock_Capabilities_Overview.md` (engine mechanics, all
implemented and test-covered) and the `MonetizationPlan/` PRD set. Engine figures — method
weights, section structure, moat pillars, R-R anchors — are taken directly from the source
configuration. Nothing here is financial advice.*

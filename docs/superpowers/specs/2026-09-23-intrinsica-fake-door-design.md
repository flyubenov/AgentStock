# Intrinsica Fake-Door Landing Page — Design Spec

- **Date:** 2026-09-23
- **Status:** Design approved by the user (mock `full-page-v21.html`); spec awaiting review → implementation plan.
- **Author:** f_lub (with Claude)
- **Branch:** `01-fake-door-test`
- **Source material:** `MonetizationPlan/Agent_Stock_Smoke_Fake_Test_Monetization_Plan.md`, `MonetizationPlan/FreeProUnlimited.md`, `MonetizationPlan/NewPlatformName-Branding-Positioning.txt`
- **Approved visual reference:** `.superpowers/brainstorm/1294-1790189388/content/full-page-v21.html` (self-contained HTML/CSS/JS mock — the normative source for layout, copy and interaction)

## 1. Summary

Build a public **smoke-test / fake-door funnel** for **Intrinsica** that validates
**willingness to pay**, not email curiosity. A visitor lands, runs a real analysis on
tickers they choose, reads the full methodology, sees the plans, picks one, and clicks
**Proceed to payment** — at which point the product honestly discloses that nothing is
for sale yet and nothing was charged.

There are **no card fields anywhere in the funnel**. The measured signal is
*reaching and clicking the payment button*, which is the strongest intent signal
obtainable without taking money.

Two things are being validated at once:

1. **Willingness to pay** — unique visitors who click "Proceed to payment" / unique visitors.
2. **Plan shape** — which of Free / Pro / Unlimited, and which billing period, people pick.

The page is simultaneously the first real presentation of the engine: the demo is a
genuine analysis, at full depth, with the real breakdown. Nothing is blurred or faked
except the transaction.

## 2. Non-goals / out of scope

- **No payment integration.** No Stripe, no card fields, no tokenization, no PCI surface.
- **No accounts, no auth, no personalisation.** Watchlists, history, alerts, portfolio and
  discovery are *described and priced*, not built. The Free plan's CTA creates nothing.
- **No A/B positioning test.** A single fixed positioning from the branding file.
- **No blurred or degraded demo.** Depth is never gated in the demo.
- **No API tier** — the PRD marks it future; it does not appear on the page.
- **No new engine work.** The engines exist; this spec defines what they must *expose*
  (§7), not new scoring.
- **Pre-computed universe vs on-demand analysis is explicitly deferred** (§12.1).

## 3. Product architecture

Two pages, one route each, sharing nav/footer chrome:

| Route | Contents |
|---|---|
| `/` (landing) | nav · hero + analyzer · results · methodology · why · workflow · pricing + compare · footer |
| `/checkout` | mini-nav ("← Back to pricing") · plan summary · **Proceed to payment** · post-click disclosure · short legal footer |

**Checkout is a separate page, not a section.** In the mock this is `#site` vs
`#checkoutPage` toggled by `body.co`; in the React app it is a real route, so the URL,
the back button and the analytics funnel step are all unambiguous. Entering checkout
resets the disclosure state and scrolls to top; "← Back to pricing" returns to `/#pricing`.

Stack: the existing `frontend/` (React 19 + Vite + Tailwind + react-router). The landing
page is added as a new route tree; `/database`, `/results/:jobId` and friends are untouched.

## 4. Visual system

Light theme, defined as CSS custom properties on `:root` (carried into the Tailwind theme):

- **Type:** Space Grotesk (headings, brand, numbers) · Inter (body) · JetBrains Mono
  (ticker input, tabular values, weights, scales).
- **Colour:** white background, indigo accent `#4f46e5` with a soft tint for pills;
  assessment dots Quality `#22c55e`, Moat `#3b82f6`, Fair Value `#4f46e5`,
  Reward/Risk `#f59e0b`; positive `#16a34a`, warn amber, negative red.
- **Surfaces:** rounded cards, soft shadows, a light "stage" background on alternating
  sections.
- Responsive to phone width; the breakdown tab strip collapses to two columns and strength
  bars are hidden below 700px.

## 5. Page sections (landing)

Nav is sticky with an anchor per section: **Analyze · Methodology · Why Intrinsica ·
Workflow · Pricing · Sign up (CTA)**.

### 5.1 Hero

- Wordmark **Intrinsica**, then **Fundamental Stock Analysis**.
- **The four assessments inline under the headline** (placement "V2", locked), each a
  coloured dot + name + its plain-English question, and each **clickable**: clicking jumps
  to the methodology section and selects that assessment's tab.
  - Quality — *How strong is the underlying business?*
  - Moat — *How durable are its competitive advantages?*
  - Fair Value — *What is the business worth based on its fundamentals and valuation methods?*
  - Reward / Risk — *How attractive is the current price relative to intrinsic value and downside risk?*
- Sub-line: "Evaluate stocks using a consistent, transparent fundamental framework."
- **Analyzer** immediately below: one rounded field (mono, focus glow, no magnifier icon),
  placeholder "Enter one or more tickers — e.g. NVDA, AMD, AVGO", and an **Analyze →**
  button. No popular-ticker chips and no trust line — the field sits directly above the
  results grid so input and output read as one unit.

### 5.2 Results

Results **always render as the grid**, including for a single ticker (one row,
auto-expanded). Above it, when more than one ticker ran, a parallel-run bar
("Computed in parallel: AAPL ✓ AMD ✓ … · 3 tickers · 2.1s").

**Grid columns (style B · Institutional — chosen over Terminal and Scorecard):**

`Company | Quality /10 | Moat /100 | Fair Value | % vs Price | Price | Reward/Risk × | (expand)`

- Values only — **no tier words in the grid** (Strong / Excellent / Wide live in the breakdown).
- `/10`, `/100` and `×` are rendered as small units in the header, not in the cells.
- **% vs Price** = (fair value − price) / price, signed and colour-coded:
  ≥ +10% green · 0…+10% blue · −10…0 amber · < −10% red.
- Best-in-column highlight (blue) in compare mode only; no stars; cells top-aligned.
- Clicking a row expands the **breakdown** inline (§5.3). No "rows are expandable" hint text.

Below the grid, the **free-note** states the demo reality honestly: everything shown is the
real analysis at full depth; the demo is open to everyone at up to 3 tickers per run with no
account; at launch Free keeps that depth at about 5 analyses a month, and Pro removes the cap.

### 5.3 Breakdown (inside an expanded row)

A slim tab strip across the **full grid width** — Quality · Moat · Fair Value · Reward/Risk —
with one panel below. Every panel is the same four-column table:

| Factor | Data | Score | Weight |
|---|---|---|---|

- **Quality:** four categories (Growth & Margins · Returns on Capital · Balance-Sheet
  Strength · Shareholder Alignment), each with the profile's category weight as a pill; each
  metric row shows the actual figure (e.g. `ROIC ~55%`, `Net debt/EBITDA ~0.4×`), its 0–10
  score and its weight. Metrics are **equally weighted inside a category**, so a metric's
  weight = category weight ÷ number of active metrics. A metric excluded by a calibration is
  shown **struck through at 0%** and the remainder are re-weighted.
- **Moat:** factors with `points / max`, which is also the weight (40 / 50 / 10 across
  Magnitude / Durability / Cash-backing). Hover tooltips explain what each factor measures —
  concept only, never thresholds. The economic-profit gate is shown as a Moat-wide cap check.
- **Fair Value:** `Method | Value | Contribution | Weight` per method in the blend, rolling up
  to **one exact blended number** — never a range. The blend used is named.
- **Reward / Risk:** all 6 reward and 6 risk factors, each scored 1–5 with its config weight;
  the two axis scores, the clamped ratio and the tier are **computed from those factors**, and
  a pill states "Reward ÷ Risk · range 0.2×–5.0× · higher is better".
- **Calibrations:** only the ones that actually fired for that stock, as chips with a
  stock-specific hover explanation of what changed.
- **Model-integrity strip:** Quality profile · Valuation type · Moat basis · Data quality,
  with internal classifiers rendered through a human label map (`TECH_GROWTH` →
  "Tech / Growth", `MEGA_CAP` → "Mega Cap valuation blend"). **Raw ALL_CAPS / underscore
  identifiers must never reach the UI.**

**Every headline number in the grid is derived from the factors in the breakdown.** The grid
and the breakdown can never disagree, because the grid does not carry numbers of its own.

### 5.4 "How Intrinsica works" (the framework)

One consolidated section — overview card → four clickable assessment cards → detail panel —
replacing the previously overlapping why / how / methodology / calibration sections.

**Overview card.** Lead paragraph: four independent engines read the latest fundamentals and
score the company live; they stay separate, with no single blended rating, because whether a
business is good and whether its price is fair are different questions; the calculations are
explicit formulas rather than an AI opinion, so the same company on the same data always
returns the same result. Then a 2×2 highlight grid:

- **Scored for its sector.** Quality category weights shift with the company profile, so a
  software business is not judged by the standards of a REIT or a bank.
- **Valued for its type.** The company is classified first, and that decides which of nine
  valuation methods carry weight.
- **Calibrated for distortions.** Acquisition goodwill, amortization-depressed earnings, heavy
  capex, cyclicals and pre-profit growth — every calibration that fires is named on the
  result, with the reason.
- **Built to run in parallel.** One ticker or a hundred are computed concurrently — the same
  engine behind a single lookup, a watchlist re-run and a universe screen.

Closing line: "Click any assessment below for its categories, weights and calibrations."

**Detail panel** — one per assessment, and **identical in shape across all four** (this
consistency is a requirement; they had drifted):

1. Name + **scale** pill (`0–10 · sector-aware`, `0–100`, `$ per share`, `ratio · 0.2–5.0×`).
2. The question, then a one-line "what it measures".
3. **Categories**, each with a weight / points pill, its metric list, and a two-line pair:
   green **Scores high:** … / amber **Scores low:** … in plain sentences. Fair Value uses
   **Weighted up / Weighted down**; the Reward/Risk risk category is titled
   "Risk axis · a high score here is the bad one".
4. A closing note carrying the outcome bands only (9+ top-decile · 80+ wide moat ·
   1.3–2.0× Reward-Favored, etc.).
5. **Calibrations for this assessment** as expandable rows: *When it applies* / *What it does*
   / example, each tagged **Conditional** (all), **Guarded** (only where the engine guard is
   one-directional) and **Shown live**, with the tag explanation on hover. All collapsed by
   default.

### 5.5 Why Intrinsica

Lead paragraph explains the four assessments and **why they must be read together** — a good
business bought at the wrong price is still a bad investment, and a cheap price means nothing
if the business is eroding — followed by the time argument: answering these properly means
hours of statement work per company; Intrinsica computes all four in seconds, identically
every time, across a whole watchlist or the market.

Then two labelled rows of three cards:

- **Trust the analysis** — Deterministic & reproducible · Transparent to the last detail ·
  Calibrated for real companies.
- **Put it to work at scale** — Re-evaluate whole watchlists (25 / 50 / 100+ in parallel) ·
  Discover what fits your criteria (screen on the four assessments) · Automated monitoring
  ("What changed?" when an assessment crosses your threshold). *No plan pill on this row.*

### 5.6 Workflow

**Analyze → Compare → Watch → Monitor**, four cards, with no per-tier limit strips and no
"feeds back into Analyze" line:

1. **Analyze or discover** — start from tickers you already follow, or find new ones by
   screening the universe on the four assessments. (Discover is folded in here; it is not its
   own step.)
2. **Compare** — rank stocks side by side, computed in parallel.
3. **Watch & re-evaluate** — save watchlists and re-score them in one bulk, parallel run.
4. **Monitor & automate** — scheduled re-checks, alerts and "What changed?" when scores move.

### 5.7 Pricing

Billing toggle (**Annual**, default, tagged "save ~17%" / **Monthly**). Prices display
**effective-monthly, AlphaSpread-style**: the big number is the discounted monthly rate when
billed annually, with the annual total beneath.

| | Free · Try Intrinsica | **Pro · Deep Stock Analysis** (featured) | Unlimited · Discover, Monitor & Automate at Scale |
|---|---|---|---|
| Annual | $0/mo — "No card, ever" | **$18.00/mo** · billed annually · $216/yr · save 18% | **$25.00/mo** · billed annually · $300/yr · save 17% |
| Monthly | $0 | $21.99/mo | $29.99/mo |
| For | Full-depth analysis, small volume. | Unlimited analysis & your research workflow. | Automated, systematic research across your universe. |
| CTA | Start free | Choose Pro | Choose Unlimited |

Cards are equal height with the button pinned to the bottom. Pro carries the subtle
`featured` highlight (no "most popular" text).

**Canonical plan matrix** — the "Compare plans" table, preceded by three who-it's-for cards
(Free · Try = experience the framework; Pro · Depth = deep individual research;
Unlimited · Scale = systematic & automated):

| Feature | Free | Pro | Unlimited |
|---|---|---|---|
| Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk) | Full | Full | Full |
| Breakdown, methodology & calibrations | Full | Full | Full |
| Analyses per month | ~5 | Unlimited | Unlimited |
| Tickers per analysis run *(one results grid, ranked side by side)* | 3 | 10 | 100+ (bulk) |
| Side-by-side breakdown *(full factor tables of 3 companies in one view)* | — | Up to 3 | Up to 3 |
| Watchlists | 1 | 5–10 | Unlimited |
| Stocks per watchlist | 5 | 50 | Unlimited |
| Portfolio analysis | — | Basic | Advanced |
| Score history | 6 months | ~2 years | Full history |
| Score-history charts | 6 months | Yes | Advanced |
| Bulk / parallel analysis | — | — | Yes |
| Discovery — screen on the four assessments *(Preview = filters visible, running them locked)* | Preview | Preview | Full |
| Full stock universe | Preview | Preview | Yes |
| Score-change alerts *(told when a score crosses a threshold you set)* | — | 10–20 | Unlimited |
| Automated monitoring *(Intrinsica re-runs your watchlists on a schedule, unprompted)* | — | — | Yes |
| "What Changed?" *(which factor moved a score, this run versus the last)* | — | — | Yes |
| Exports | — | CSV / PDF | Bulk |

Closing line: "Free sells the framework · Pro sells depth & unlimited use · Unlimited sells
scale, discovery & automation."

Two deliberate resolutions are encoded in this table:

- **Compare is split in two.** "Tickers per analysis run" is the results grid (3 / 10 / 100+).
  "Side-by-side breakdown" is a separate view **capped at 3 by screen width**, Pro and above.
  This replaces the undeliverable "5–10 side by side".
- **Free is labelled honestly.** It is *not* "the full product, capped" — every analysis is
  complete and nothing is blurred, **but volume, watchlists, history and discovery are capped.**

### 5.8 Footer

Two lines: the modeling-tool / not-personalized-advice disclaimer, and the positioning line.
A short form repeats on the checkout page.

## 6. Checkout page and the fake door

Flow: a pricing card CTA → `/checkout`, carrying the selected plan and billing period.

The page shows **Plan · Billing · Total** and a single **Proceed to payment** button
(Free shows **Create free account**, Billing "No billing", Total "$0 — free plan").
There are **no card, address or name fields**.

**The "no card required / you won't be charged" fine print is hidden before the click.** It
appears only *after* the click, together with the disclosure. Rationale: telling people
up-front that there is nothing to pay removes the very commitment the test measures.

On click, the disclosure panel reveals in place:

- **Paid:** "✓ You're on the Intrinsica founding list — Intrinsica isn't commercially
  available yet, so **no payment was taken**. We've recorded your request for *Pro — Annual*
  and will contact you when early access opens."
- **Free:** "✓ You're on the Intrinsica early-access list — Accounts aren't open yet, so
  **no account was created**. We've recorded your interest in the Free plan and will invite
  you when early access opens. In the meantime the demo above stays open — up to 3 tickers
  per run, no account needed."

Plus an **optional** email field ("Notify me", explicitly marked optional). Email is a bonus,
never a gate.

**Free routes through the same checkout screen**, worded for free. This was chosen over
pointing the Free CTA back at the demo, because the demo is not the Free plan (the demo is
3 tickers, no watchlist, no history). **Free clicks must be logged as their own analytics
event and must never be counted in paid-intent conversion.**

## 7. Engine → UI data contract

The breakdown is only honest if the backend exposes the components, not just the headlines.
Per analysed ticker the API must return:

- **Quality:** the resolved profile id *and* its human label; per category the weight and
  earned points; per metric the raw figure (formatted + numeric), its 0–10 score, its
  effective weight, and an `excluded` flag naming the calibration that excluded it.
- **Moat:** per factor the points earned and the max (= its weight), the pillar totals, and
  whether the economic-profit gate capped the score.
- **Fair Value:** the classified type (id + label), per method the returned value with its
  blend weight and contribution, and the single blended fair value. **One number, never a
  range** — the per-method optimistic / realistic / pessimistic scenarios exist internally but
  are not surfaced on this page.
- **Reward / Risk:** all 12 factor slot scores (1–5) with their config weights, both axis
  scores, the clamped ratio, and the tier label.
- **Calibrations:** the list that actually fired, each with its name, what it changed, and
  which assessment(s) it touched.
- **Live layer:** the current price, and the `% vs price` gap computed at read time (§12.1).

Grid values are **computed from these components in the UI**; the API should not send a
separately-rounded headline that could disagree with its own breakdown.

## 8. Copy rules (binding on this page and all future marketing copy)

1. **The word "signal" is banned** in user-facing copy — use **assessment** (Reward/Risk uses
   "factors"). It reads as trading jargon and collides with the product's own vocabulary.
2. **The label is "Reward/Risk", never "Risk/Reward"** — the ratio is reward ÷ risk, so above
   1 means more reward. Applies to "R/R", "R-R" and chart axes too.
3. **Explain concepts and weights publicly; never publish scoring thresholds, bands or
   curves.** Weights, point maxima, metric names and outcome bands are public; the mapping
   from a raw metric to a score is internal. This is a deliberate IP boundary.
4. **No invented moat sources.** The Moat score is durability of economic profit measured from
   statements — never imply brand, network effects or switching costs.
5. **No internal identifiers in the UI** — always through the human label map.
6. **No investor-facing engineering jargon.** "500+ automated tests" was removed; it means
   nothing to the reader it was aimed at.
7. **Fair Value is an exact number.** Ranges appear nowhere on this page.
8. **Numbers in explanatory copy stay minimal** — weight / points pills, per-factor weights in
   the metric lists, and the outcome bands. Threshold examples inside the "Scores high /
   Scores low" lines were tried and rejected as too complicated.

## 9. Analytics

One event per funnel step, each carrying `visitor_id` and a timestamp:

`page_view` → `analysis_started` (tickers, count) → `analysis_completed` (duration) →
`breakdown_opened` (ticker, assessment tab) → `methodology_viewed` (assessment) →
`pricing_viewed` → `plan_selected` (plan, billing) → `checkout_started` (plan, billing) →
**`payment_button_clicked`** (plan, billing) → `email_submitted` (optional).

- **Primary metric:** unique visitors reaching `payment_button_clicked` ÷ unique visitors.
- **`free_plan_clicked` is a separate event** and is excluded from that ratio.
- Secondary: plan mix, billing mix, methodology engagement before conversion, drop-off per step.
- De-duplicate server-side by `visitor_id`; `localStorage` is a convenience, never the source
  of truth.

## 10. Demo limits and abuse

- Tasting stays **login-free** — forcing registration would depress the very signal being
  measured.
- Demo cap: **3 tickers per run**, tracked client-side (soft, non-enforced; adequate for a
  fake door).
- Cost is bounded by **caching**, not by users: the first run of a ticker caches it, later
  requests are cheap reads. A light per-IP throttle applies to **cache-miss** runs only.
- Residual leakage is accepted as research spend.

## 11. Testing

- **Unit:** the derivation helpers — category roll-ups, per-metric weight = category weight ÷
  active metric count, the fair-value blend, the reward/risk axes + clamp + tier mapping, and
  the `% vs price` colour banding.
- **Contract:** a golden-file test per sample ticker asserting each grid headline equals the
  value derived from the breakdown components, so the two cannot drift.
- **Component:** tab selection from a hero assessment click; row expand / collapse; the
  billing toggle updating both the card prices and the checkout total; checkout state reset on
  re-entry.
- **Funnel:** an end-to-end test walking analyze → pricing → checkout → click, asserting the
  analytics events fire in order, once each, with the right plan and billing — **and that no
  card or payment input exists anywhere in the DOM.**
- **Copy guard:** a lint test that fails on "signal", "Risk/Reward", and raw `[A-Z_]{4,}`
  classifier ids in user-facing strings.

## 12. Open items — decide before or during implementation

### 12.1 Pre-computed universe vs on-demand analysis *(needs its own brainstorm)*

If thousands of tickers are pre-evaluated in the database, what does a user-entered ticker run
actually compute, and what are we metering?

- **Two-speed freshness.** Price-derived outputs change daily — the **Fair-Value % gap** above
  all — and must be computed on the fly at read time (cheap, no engine run). The **whole
  Reward/Risk assessment is price-sensitive too** (discount to 52-week high, RSI, trend vs
  200-day, volatility, beta, the valuation leg), so it belongs in the same fast layer.
- **Slow layer = fundamentals.** Quality, Moat and the Fair-Value $/share hold until that
  company's **next earnings report** — a per-ticker, event-driven invalidation, not a nightly
  global rebuild. Guards are also needed for restatements, splits, M&A and ticker changes.
- **Precompute is a cache, not a catalog.** On-demand runs still matter for names outside the
  cached universe (small caps, foreign listings, new IPOs), for forced refreshes, and because
  "judge the name I hold" is a different question from "find names I don't know". Discovery is
  the same store queried differently.
- **Monetisation consequence:** if reads are cheap, "analyses per month" is a weak metering
  unit and will feel arbitrary. Candidate replacement: cap **stocks viewed in full depth per
  month** and gate persistence, refresh-on-demand and monitoring instead. **This would change
  the plan matrix in §5.7** — settle it before the pricing copy ships.

### 12.2 "Portfolio analysis — Basic / Advanced"

Inherited from the PRD with no definition anywhere. Either define it — Basic = one portfolio,
a holdings table plus a weighted roll-up of the four assessments; Advanced = multiple
portfolios, position-size weighting, sector drill-down, what-if, portfolio score over time and
portfolio-level alerts — or cut the row from the fake door.

### 12.3 "Score history" vs "Score-history charts"

These are one feature split across two rows (retention vs visualisation). Recommendation:
merge into a single row carrying the retention values, and define Unlimited's "Advanced" as
multi-stock / multi-assessment overlays, earnings markers, full range and export.

### 12.4 Default marquee ticker

AAPL opens on an honest but downbeat −9% gap; NVDA opens friendlier at +5%. Unresolved.

## 13. Implementation notes

- **The repo-wide rename "Agent Stock" → "Intrinsica"** (docs, frontend copy, backend strings,
  page titles, metadata) is part of this work item and has not been done.
- Build the landing page as a new route tree under `frontend/src/pages`, with the results grid,
  the breakdown and the methodology panel as separate components — the mock's single-file
  structure is a prototype, not the target architecture.
- Port the mock's CSS tokens into the Tailwind theme rather than copying the raw stylesheet.
- Analytics wiring (§9) and the copy-guard lint (§11) land with the page, not after it.

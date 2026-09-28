# Intrinsica Fake-Door Landing Page — Design Spec

- **Date:** 2026-09-23 (corrected 2026-09-25 after implementation)
- **Status:** **IMPLEMENTED** on branch `01-fake-door-test`. Design approved by the user
  (mock `full-page-v21.html`).

> ⚠ **Two things in §9 were wrong and are corrected inline below.** The shipped code is
> the source of truth where they disagree.
>
> 1. **Abandonment must be filtered to `plan != 'Free'`.** Computed globally as written,
>    it counts every completed Free journey as an abandonment.
> 2. **Three events gained a `source` prop** (`analysis_started`, `analysis_completed`,
>    `free_plan_clicked`) because each was firing from two places into one counter. The
>    event list itself did not grow — it is still closed, and now enforced at build time.
>
> Full decision record: <https://claude.ai/artifact/QrzYRX1oAr6kYzAcENbkn2>

> **REVISION 2026-09-27 — hero rework (approved by the user, NOT yet implemented).**
> §5.1, §5.2, §5.3, §5.4, §9 and §11 are revised below. In summary:
> - The hero becomes a promise headline beside a live result card.
> - The results grid is replaced by that card.
> - The breakdown opens under the hero.
> - The Framework section gains a question band and two tab-pair labels.
>
> Background: a competitor review at <https://claude.ai/artifact/M4aHVziuvx5mE3PczL9YL9>,
> item 1 of its suggested order. Mock-ups and their builders are in
> `.superpowers/brainstorm/hero/` (`build_runflow2.py` for the card, `build_phone.py` for phone).
>
> *Status 2026-09-29: the hero rework is implemented and pushed.*

> **REVISION 2026-09-29 — brand, palette and page polish (approved by the user, NOT yet
> implemented).** Item 2 of the same competitor review. §4 is rewritten; §5, §5.1, §5.2,
> §5.4, §5.7, §5.8 and §11 are revised below. In summary:
> - A brand mark: a keyhole on a teal plate, lit in the four assessment colours.
> - A new palette: a deep-teal accent on warm paper. The assessment colours are re-balanced so none is confused with another.
> - One set of line icons, one full-width teal band, and sections that float in on scroll.
> - A static share image.
> - A shorter Framework panel, with collapsible categories.
> - The "Intrinsica's own method." paragraph is reworded.
>
> The fonts are unchanged. Mock-ups and their builders are in `.superpowers/brainstorm/brand/`; the colour
> measurements (CIEDE2000 and colour-blind simulation) are in `colours.py`.
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
| `/` (landing) | nav · hero (analyzer + result card) · breakdown (when open) · question band · methodology · why · workflow · pricing + compare · footer |
| `/checkout` | mini-nav ("← Back to pricing") · plan summary · **Proceed to payment** · post-click disclosure · short legal footer |

**Checkout is a separate page, not a section.** In the mock this is `#site` vs
`#checkoutPage` toggled by `body.co`; in the React app it is a real route, so the URL,
the back button and the analytics funnel step are all unambiguous. Entering checkout
resets the disclosure state and scrolls to top; "← Back to pricing" returns to `/#pricing`.

Stack: the existing `frontend/` (React 19 + Vite + Tailwind + react-router). The landing
page is added as a new route tree; `/database`, `/results/:jobId` and friends are untouched.

## 4. Visual system

*Rewritten 2026-09-29 (brand round, user decisions throughout). The tokens live on
`.intrinsica` in `frontend/src/landing/theme.css`, scoped so the dark analyst app is untouched.*

**Principle: colour means data.** The four assessment colours and gain / loss green and red
use up the colour wheel. So the interface accent is one dark teal that sits clear of all six. Every
chromatic accent that was measured collided with one of them: orange with Quality for
colour-blind readers, red with loss, and navy and indigo with the violet. Indigo, today's accent, read as a fifth colour on the page.

**Type — unchanged:** Space Grotesk (headings, brand, big numbers) · Inter (body) ·
JetBrains Mono (ticker input, tabular values, weights, scales). Serif and single-family
pairings were mocked and rejected.

**Palette tokens** *(deep teal accent · warm paper page)*:

| Token | Value | Was |
|---|---|---|
| `--bg` / `--bg2` / `--bg3` | `#fdfcf9` / `#f6f3ec` / `#efebe2` | `#ffffff` / `#f7f8fa` / `#f1f2f6` |
| `--border` / `--border2` | `#e8e3d8` / `#ddd7ca` | `#e9ebef` / `#e0e2e8` |
| `--text` / `--dim` / `--mute` | `#141414` / `#57534b` / `#8c877c` | `#0b0b0f` / `#54545f` / `#8b8b97` |
| `--accent` / `--accent-d` / `--accent-soft` | `#0f5257` / `#0a3d41` / `#e4eee9` | `#4f46e5` / `#4338ca` / `#eef0ff` |
| `--pos` / `--neg` / `--warn` / `--blue` | unchanged | |

The accent drives buttons, links, the active tab underline, the billing toggle, the plan badges and the featured
card. It is the same teal as the logo plate.

**Hard-coded colours that follow the palette** (every other literal in `theme.css` stays):
- nav background: `rgba(255,255,255,.86)` → `rgba(253,252,249,.88)`;
- `.runbar .mini.ind`: `#e0e7ff` → `#dfe6df`;
- `.wtoast a` (on the dark toast): `#c7c3ff` → `#9fd3cf`;
- the Proceed-to-payment shadow: `rgba(79,70,229,.28)` → `rgba(15,82,87,.28)`;
- the old gradient logo tile `.logo .mk` (`#7c74f2`) is removed and replaced by the brand mark below.

**Assessment colours** — one fixed colour per assessment everywhere on the page: dots, gauge
bars, tabs and the Framework panel. The score moves a bar's length, never its shade.

| Assessment | Page token | Logo (keyhole) | Was |
|---|---|---|---|
| Quality | `--q: #22c55e` (unchanged) | aqua `#66fff7` | `#22c55e` |
| Moat | `--mo: #3d8bff` azure | `#3d8bff` | `#3b82f6` |
| Fair Value | `--fv: #d4b106` gold | yellow `#fae842` | `#4f46e5` |
| Reward / Risk | `--rr: #440ab8` violet | `#440ab8` | `#f59e0b` |

- The page and the logo differ on purpose for two assessments, with the user's approval:
  - **Quality:** green melts into the teal plate, so the logo uses aqua.
  - **Fair Value:** the bright yellow almost disappears on warm paper (1.2 : 1), so small marks on the page use the deeper gold (2.0 : 1). The keyhole keeps the bright yellow.
- The closest pair is Moat azure vs Reward/Risk violet: 36 apart (CIEDE2000), and 27 for deuteranopia. That is clearly apart, and the tightest spot in the set.

**Brand mark — "light through the keyhole".** The keyhole reads as the letter i.
- **Geometry:** a 100 × 100 viewBox.
  - **Plate:** a rounded square, x/y 4–96, `rx 22`, filled with a vertical gradient `#17696f → #0a3a3e`.
  - **Keyhole:** one path, `M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z`, with a rim stroke `#8fc4c5` at width 1.6 and round joins.
- **Colours:** the mark is always **fully lit**, in four quadrants clipped to the keyhole.
  - The head (y 23–53) is aqua on the left and azure on the right: Quality | Moat.
  - The slot (y 53–80) is yellow on the left and violet on the right: Fair Value | Reward/Risk.
  - The split is at x = 50.
- **No partial version.** A partly lit, per-result mark was designed and dropped. The mark appears **only** as the logo and the favicon, never on result cards, comparison rows or per-stock images.
- **Nav:** the mark at **42 px** beside the "Intrinsica" wordmark (23 px, gap 11 px).
- **Favicon:** the same SVG replaces Vite's `public/favicon.svg`. It is app-wide, because `index.html` serves every route.

**Line icons.** One drawn set replaces the typed glyphs everywhere except the Why section.
- **Style:** stroke 1.8–2.4, round caps, `currentColor` or a CSS mask.
- **Replacements:**

  | Where | Today | Becomes |
  |---|---|---|
  | Watch button | ☆ | bookmark (it saves to a watchlist; a star reads as "rate") |
  | Result tiles | ↓ after the name | chevron-down |
  | Plan-card bullets | ✓ | teal check |
  | Close buttons (breakdown and toast) | ✕ | × |
  | Calibration rows | ▾ | chevron |
  | Checkout confirmation line | ✓ | check |
- **Unchanged:**
  - arrows inside sentences ("Analyze →", "breakdown ↓", "See plans →") stay as text;
  - the tooltip text "gate ✓ passed" stays as text;
  - the Why section's emoji are **never** changed: the user's standing rule is that the Why section stays exactly as it is.

**Rhythm.** One full-width band in the brand teal breaks the even paper/beige alternation: the question band (§5.4).

**Motion — sections float in on scroll.**
- Content below the first screen starts 32 px lower and transparent. It slides up and fades in as it enters the view:
  - 0.7 s, `cubic-bezier(.2,.7,.2,1)`, fired by an IntersectionObserver with a −8 % bottom margin;
  - **once** per element, never replayed on scrolling back.
- Cards in a row stagger by 90 ms each, capped at four steps. These are the Framework tabs, the Why cards, the Workflow steps and the plan cards.
- **It is an animation, not lazy loading.** Every section is in the DOM from the first render, so search engines, link previews and nav anchors see the whole page.
- **The hero is never animated.** With `prefers-reduced-motion: reduce` nothing animates. If the script does not run, everything is simply visible (the hidden state is applied by the script, never by static CSS).

**Surfaces:** rounded cards and soft shadows. The "stage" sections alternate on `--bg2`.

**Responsive:** the page works down to phone width. The breakdown tab strip collapses to two columns, and the strength bars are hidden below 700px.

## 5. Page sections (landing)

Nav is sticky with an anchor per section: **Analyze · Methodology · Why Intrinsica ·
Workflow · Pricing · Sign up (CTA)**. On the left sits the brand mark (42 px, §4) and the "Intrinsica" wordmark.

### 5.1 Hero

*Rewritten 2026-09-27 (hero rework, user decisions throughout).*

**Removed in this rework:**
- the "Intrinsica / Fundamental Stock Analysis" heading (the wordmark stays in the nav);
- the pipeline strip (variant B3, 2026-09-26);
- the four clickable assessment questions (placement "V2").

The questions still live in each Framework detail panel (§5.4). A "numbers band" of fixed facts was designed and **rejected**: three of its four figures never change and they are abstract without the detail. The per-ticker "◆ N calibrations applied" card line was designed and **rejected** too. The breakdown's calibration chips (§5.3) stay the only place fired calibrations are shown.

**Layout.**
- **Desktop:** two columns of equal weight, with a container wider than the page's 1040px (about 1160px). The **left** column holds the promise and the analyzer; the **right** holds the result card (§5.2).
- **Phone:** one column in the order headline → subline → analyzer → card. The input comes first on purpose: card-first was mocked and rejected, because it pushed the input below the fold and put the input between the card and its breakdown.

**Left column, top to bottom:**
- **Headline:** "Judge the business. Then judge the price."
  - Chosen from seven options; "Is it a good business, at a good price?" was the runner-up and now opens the question band (§5.4).
  - One fixed headline: no rotation and no A/B split.
- **Subline:** "Quality and Moat tell you how good the company is; Fair Value and Reward/Risk tell you whether the price makes sense. All from the fundamentals, all shown."
- **Analyzer:** as before.
  - One rounded field (mono, focus glow, no magnifier icon) with the placeholder "Enter one or more tickers — e.g. NVDA, AMD, AVGO", and an **Analyze →** button.
  - On a phone the button goes full width under the field.
- **Compare chip** under the analyzer *(user decision, 2026-09-26)*: "Or try: Compare AAPL · MSFT · NVDA".
  - It fills the input with the three tickers and runs them as a sample run.
  - It never consumes the typed demo allowance and stays available after the allowance is used up.
- **Micro-line:** "Up to 3 tickers at a time · no account needed".
- **Demo-limit wall:** when it applies, it replaces the field and button in this column, unchanged.

### 5.2 Results — the result card

*Rewritten 2026-09-27. **The results grid is removed.** Every result renders in one card in the hero's right column; there is no results table below the hero.*

**Tiles view** is used for the page-load sample (AAPL) and for any one-ticker run.
- **Header:**
  - ticker, company name, the watchlist button (§9; drawn as a bookmark icon since 2026-09-29, §4), then price and profile ("$341.07 · Tech / Growth profile");
  - a pill on the right, set by the run's `source`: "Live example · computed just now" (pulsing dot) for a **sample** run (the page-load AAPL and the Compare chip), "Your analysis" for a **typed** run. *(Clarified 2026-09-27: a Compare-chip comparison is a sample, so it is not labelled "Your analysis".)*
- **Tiles:** a 2×2 grid in the order Quality, Moat (top row, the business), then Fair Value, Reward / Risk (bottom row, the price). Each tile has:
  - a coloured dot and the name;
  - the big number with its unit (`7.8 /10`, `95 /100`, `$159`, `1.1 ×`);
  - one small visual:
    - Quality and Moat: a gauge bar;
    - Fair Value: two bars, fair value against price on one scale;
    - Reward / Risk: two bars, the reward score against the risk score;
  - a caption.
- **Tile captions** come from the product's **existing** tier labels. No new wording is introduced.
  - Quality: `qualityTier` (Top-decile / Excellent / Strong / Moderate / Weak).
  - Moat: `moatTier` (Wide / Established / Narrow / Little or none).
  - Fair Value: "Fair value N% below price" / "Fair value N% above price" (or "Fair value at price" when it rounds to 0), coloured with the % vs price bands below. *(Corrected 2026-09-27: the approved wording, "Price N% above fair value", reversed the base of the percentage. `gap_pct` is measured against the price.)*
  - Reward / Risk: the engine's tier (e.g. Balanced, Reward-Favored).
- **Footer:** "Click any score for its full breakdown ↓".

**Comparison view** is used for two or three tickers (the landing cap is 3, so it always fits).
- **Header:** "Comparing N", the tickers, and the same source-driven pill as the tiles view.
- **Rows:** one per ticker. Each has:
  - ticker, name and star;
  - Quality, Moat, Fair Value (with "% vs price") and Reward / Risk, each with its tier caption;
  - a ▾ affordance.
- **Footer:** "Click a ticker for its full breakdown ↓".
- **On a phone** each ticker becomes a block: ticker, star and name on one line, then its four scores as four small boxes. A colour key sits above the blocks.

**Rules carried over from the grid:**
- **% vs Price** = (fair value − price) / price, signed and colour-coded: ≥ +10% green · 0…+10% blue · −10…0 amber · < −10% red.
- Best-in-column highlight in the comparison view only.
- Every number in the card is derived from the breakdown's factors (see the end of §5.3).

**Tier words: this REVERSES the grid's rule.** The grid's rule was "Values only — no tier words in the grid". The card shows tier words as captions; the user approved this with the mock-ups on 2026-09-27.

**Interaction.**
- Clicking a **tile** opens the breakdown (§5.3) on that tile's tab.
- Clicking a **comparison row** opens that ticker's breakdown on the current tab.
- The clicked tile or row is highlighted. Clicking it again, or using the breakdown's Close, folds the breakdown.
- **Nothing opens by itself:** the old "one row, auto-expanded" behaviour is gone.

**After a visitor's run** the card shows that run: tiles for one ticker, comparison for two or three. The sample never comes back on its own.

**While a run is in flight** *(loading variant E, 2026-09-26, now placed inside the card)*:
- The Analyze button shows a spinner and the count ("Analyzing 3…"; "Analyzing…" for one).
- For more than one ticker, the top of the card shows "Computing in parallel: AAPL · MSFT · NVDA", with a sweeping bar per ticker and an elapsed-time counter.
- The card's previous result is dimmed underneath until the new one lands.
- No ticker is shown as done before the others: the endpoint answers all of them in one response.
- Reduced motion stops the spinner and the sweep.
- After a multi-ticker run, the card header carries the run summary ("3 tickers · 2.1 s") in place of the old parallel-run bar.

**Before the first result.**
- While the page-load sample is still running, the card shows its frame with "Running the analysis…" and no numbers (generic on purpose: a typed run can also land on an empty card after a failed sample).
- If that sample fails, the card says "The live example could not be loaded. Try a ticker on the left." It never shows invented or placeholder figures.

**Notice line.** The notices ("Not recognised: X", server errors, timeouts) render in the left column, under the micro-line, next to the input they are about.

**Errors.**
- A ticker whose assessment could not be computed shows "—" and "could not be computed" in that tile or comparison cell.
- A partly invalid run shows the valid tickers in the card and today's "Not recognised: X" notice.
- An all-invalid run, a server error or a failed fetch shows today's notice line and **leaves the previous card in place**. This is a change: today the grid is emptied. An empty card would leave a hole in the hero.

~~Below the grid, a **free-note** …~~ *Removed 2026-09-26 (user decision).* It was
inaccurate — it called the demo open with no account but never mentioned the 5-run limit,
and presented that demo limit as the Free plan's monthly allowance — and every true part of
it is already said by the pricing matrix and the demo-limit message.

### 5.3 Breakdown (opens under the hero)

*Placement revised 2026-09-27. The contents are unchanged.*

The breakdown opens **full-width directly under the hero**, below both columns, when a tile or comparison row is clicked (§5.2). It is always in the same place, whichever ticker or score opened it.
- It gains a small header, "TICKER Company · full breakdown", and a **Close ✕**.
- Opening it scrolls it into view only if it is off screen.

A slim tab strip across the **full container width** — Quality · Moat · Fair Value · Reward/Risk —
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

**Every headline number in the card is derived from the factors in the breakdown.** The card
and the breakdown can never disagree, because the card does not carry numbers of its own.
(This was written for the grid; it carries over to the card unchanged.)

### 5.4 "How Intrinsica works" (the framework)

**Question band** *(added 2026-09-27, user decision, placement option 2)*:
- A short full-width band **immediately before** this section. *Revised 2026-09-29:* it is the page's one teal band (§4 Rhythm) instead of the stage background:
  - background `--accent` (`#0f5257`), no top border, padding 64 px above and below;
  - heading `#fff`, body `#cfe3e1`;
  - the Framework section below keeps its own top padding.
- It has the question as a heading, **"Is it a good business, at a good price?"**, then one line: "Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show."
- It bridges the live result above to the explanation below.
- The overview card's heading and text are **not** changed. Putting the question into the card was rejected, because it would repeat "four scores from the fundamentals" back to back.

**Tab-pair labels** *(added 2026-09-27)*: two small uppercase labels sit above the assessment tabs.
- "Is it a good business?" spans Quality and Moat.
- "At a good price?" spans Fair Value and Reward/Risk.
- They echo the hero headline and the card's two tile rows.
- On a phone, where the tabs are 2×2, each label sits above its pair.

One consolidated section — overview card → four assessment tabs joined to one detail
panel — replacing the previously overlapping why / how / methodology / calibration sections.

*Revised 2026-09-26, user decision, variant D3. The original overview — a lead paragraph
plus a 2×2 grid of highlights "Scored for its sector / Valued for its type / Calibrated for
distortions / Built to run in parallel" — and the four question-and-scale cards were judged
a wall of text. The highlights were cut: determinism, calibrations and parallel scale are
already said in 5.5 Why Intrinsica, and the sector and company-type weighting are in each
detail panel.*

**Overview card**, one column *(option B, user decision 2026-09-27 — the judgment note moved
from a side box into the text, and its original wording was restored)*:

1. Lead: "Four separate engines turn the latest fundamentals into four scores, using explicit
   formulas and **N data-triggered calibrations**. Same data, same score." — N is the live
   count of calibrations, never a hand-written number.
2. Second paragraph, bold opener. *Reworded again 2026-09-29, user decision.* "There is no single agreed way to score…" read as if Intrinsica itself had no settled method. The new text states the honest part as a fact about the subject, and says outright that the method is fixed:

   **"Intrinsica's own method."** Quality, Moat and Reward/Risk aren't printed in any filing;
   they have to be assessed. Intrinsica assesses them with one fixed methodology: it takes the
   fundamentals that matter for each, weights them and condenses them into a single score,
   the same way for every company. Each score opens up to the inputs and weights behind it.
3. Closing line: "Click an assessment for every category, weight and calibration."

**Assessment tabs.** One box: a row of four tabs (dot + name only; 2×2 on a phone) forms
the top edge of the detail panel, like the result breakdown's tabs. The selected tab is
underlined in the accent colour. The question, scale, weights and counts are not repeated
on the tabs — they are in the panel.

**Detail panel** — one per assessment, and **identical in shape across all four** (this
consistency is a requirement; they had drifted):

1. Name + **scale** pill (`0–10 · sector-aware`, `0–100`, `$ per share`, `ratio · 0.2–5.0×`).
2. The question (the only place in this section it appears), then a one-line "what it
   measures".
3. **Categories as collapsed rows**. *Revised 2026-09-29, user decision, variant A. Four categories, each with a metric list and two "Scores high / Scores low" sentences, read as a wall of text.* Each category is one row, styled like a calibration row and **collapsed by default**:
   - **Row, closed:** the category name, then a one-line plain question under it. On the right sit the weight and a chevron.
     - Where the weight is a fixed share (Quality %, Moat points), the weight also gets a small bar in the assessment's colour, scaled to the largest category in that panel.
     - Where it is a range ("typically 40–60%", "6 factors"), the text alone is shown.
   - **Row, open:** the metrics as chips, then one short line: **▲ High:** … · **▼ Low:** … (Fair Value: **▲ Weighted up:** … · **▼ Weighted down:** …).
   - Rows open and close independently, like the calibrations.
   - The Reward/Risk risk category keeps the title "Risk axis · a high score here is the bad one".
   - Categories, weights and metric lists are **unchanged**, and no threshold is shown.
   - The copy, which replaces the `hi` / `lo` sentences:

   | Assessment · category | Question | ▲ | ▼ |
   |---|---|---|---|
   | Quality · Growth & Margins (35%) | Is it growing — and profitably? | compounding revenue, margins holding | stalled growth, margins sliding |
   | Quality · Returns on Capital (30%) | Does it earn more than its capital costs? | well above its cost of capital | barely matches it |
   | Quality · Balance-Sheet Strength (15%) | Can it weather a bad year? | little debt, capex easily funded | leverage that needs a kind cycle |
   | Quality · Shareholder Alignment (20%) | Are owners treated well? | buybacks, earnings that arrive as cash | steady dilution, paper earnings |
   | Moat · Magnitude (40 pts) | How far above its cost of capital does it earn? | returns far above the cost of capital | returns that merely match it |
   | Moat · Durability (50 pts) | Does the edge last, year after year? | a decade of above-cost returns, margins that hold | a good spell inside a cyclical swing |
   | Moat · Cash-backing (10 pts) | Does the profit turn into cash? | profit that becomes cash | profit that stays on paper |
   | Fair Value · Cash-flow models | What will the business pay out over time? | steady, predictable cash flows | erratic cash flows, or pre-profit |
   | Fair Value · Earnings multiples | How is it priced against its earnings? | meaningful profits, comparable with peers | losses, or earnings distorted by amortization |
   | Fair Value · Sales multiples | What is growth worth before profit? | fast growth, no profit yet | a mature, profitable company |
   | Fair Value · Income & asset models | What do its dividends or assets say? | dividend payers, lenders, asset-heavy names | asset-light businesses |
   | Reward/Risk · Reward axis | How much upside is left? | a growing business well below its highs | a full price, little left to re-rate |
   | Reward/Risk · Risk axis | How much can go wrong? | leverage and volatility stacking up | light debt, a steady price, self-funded |

4. **Closing note becomes a scale strip.** Five or four tinted cells, tinted in the assessment's colour and deepening toward the best band. Under them is one short line:
   - **Quality:** below 5 Weak · 5–7 Moderate · 7–8 Strong · 8–9 Excellent · 9+ Top-decile. Line: "Each metric is scored against fixed thresholds; the category weights follow the sector profile (Tech / Growth shown)." The band names are `qualityTier`'s.
   - **Moat:** below 40 Little or none · 40–59 Narrow · 60–79 Established · 80+ Wide. Line: "An economic-profit gate caps any company that does not out-earn its cost of capital."
   - **Fair Value:** no strip, because it has no score to band. Line: "The company's type sets the blend — a bank leans on price / book, a mega cap on cash flows. Every analysis shows the exact blend it used."
   - **Reward/Risk:** below 0.5× Value Trap · 0.5–0.8× Risk-Favored · 0.8–1.3× Balanced · 1.3–2.0× Reward-Favored · 2.0×+ Asymmetric Upside. Line: "Reward ÷ risk, clamped to 0.2–5.0×."
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
- **Put it to work at scale** — Re-evaluate whole watchlists ("Submit 25, 50 or 100+ stocks in
  one run — results stream in as each finishes"; *revised 2026-09-27 — the old "in parallel …
  in seconds" was untrue, see 5.7*) ·
  Discover what fits your criteria (screen on the four assessments) · Automated monitoring
  ("What changed?" when an assessment crosses your threshold). *No plan pill on this row.*

### 5.6 Workflow

**Analyze → Compare → Watch → Monitor**, four cards, with no per-tier limit strips and no
"feeds back into Analyze" line:

1. **Analyze or discover** — start from tickers you already follow, or find new ones by
   screening the universe on the four assessments. (Discover is folded in here; it is not its
   own step.)
2. **Compare** — rank stocks side by side, computed in parallel.
3. **Watch & re-evaluate** — save watchlists and re-score a whole list in one run.
4. **Monitor & automate** — scheduled re-checks, alerts and "What changed?" when scores move.

### 5.7 Pricing

Billing toggle (**Annual**, default, tagged "save ~17%" / **Monthly**). Prices display
**effective-monthly, AlphaSpread-style**: the big number is the discounted monthly rate when
billed annually, with the annual total beneath.

| | Free · Try Intrinsica | **Pro · Deep Stock Analysis** (featured) | Unlimited · Discover & Automate at Scale |
|---|---|---|---|
| Annual | $0/mo — "No card, ever" | **$18.00/mo** · billed annually · $216/yr · save 18% | **$25.00/mo** · billed annually · $300/yr · save 17% |
| Monthly | $0 | $21.99/mo | $29.99/mo |
| For | For the curious investor judging the framework on stocks they already know. | For the serious individual investor researching the stocks they care about. | For investors scanning & monitoring a whole universe or portfolio. |
| CTA | Start free | Choose Pro | Choose Unlimited |

Cards are equal height with the button pinned to the bottom. Pro carries the subtle
`featured` highlight (no "most popular" text).

*Revised 2026-09-29 (brand round).* The green in the pricing section moves to the accent, because green now means a score or a gain:
- the **FREE** badge is set in bold `--accent`;
- in "Compare plans", the included cells (`td.on`: Full, Yes, Up to 3, 100+ (bulk)) are set in **bold (700) teal `--accent`**;
- the plan-card bullets are the teal line check (§4).

*Slimmed 2026-09-27 (user decision).* Each card lists **three** features:
Free — "Every analysis complete — nothing blurred" · "~5 analyses a month · up to 3 tickers
per run" · "1 watchlist of 5 · 6 months of score history"; Pro — "Unlimited analyses — no
monthly cap" · "Up to 10 tickers per run · side-by-side breakdown of 3" · "Watchlists, ~2
years of history, alerts & exports"; Unlimited — "Bulk runs — 100+ tickers in one run,
results stream in as each finishes" · "Screen hundreds of stocks on all four scores" · "Automated monitoring, unlimited
alerts & 'What Changed?'". The "For" line is the who-it's-for line; the Unlimited title
dropped "Monitor" (automated monitoring is part of "Automate") so it fits one line. The
cards share one set of rows, so for-lines, prices, features and buttons stay level across
all three even when a title wraps.

**Canonical plan matrix** — the "Compare plans" table. *(The three who-it's-for cards that
preceded it were removed 2026-09-27; their "who" line moved onto the plan cards.)*

| Feature | Free | Pro | Unlimited |
|---|---|---|---|
| Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk) | Full | Full | Full |
| Breakdown, methodology & calibrations | Full | Full | Full |
| Analyses per month | ~5 | Unlimited | Unlimited |
| Tickers per run *(how many you can enter in one go; re-checking a watchlist always runs the whole list)* | 3 | 10 | 100+ (bulk) |
| Side-by-side breakdown *(full factor tables of 3 companies in one view)* | — | Up to 3 | Up to 3 |
| Watchlists | 1 | 5–10 | Unlimited |
| Stocks per watchlist | 5 | 50 | Unlimited |
| Portfolio analysis | — | Basic | Advanced |
| Score history | 6 months | ~2 years | Full history |
| Score-history charts | 6 months | Yes | Advanced |
| Discovery — screen on the four assessments *(Preview = filters visible, running them locked)* | Preview | Preview | Full |
| Full stock universe | Preview | Preview | Yes |
| Score-change alerts *(told when a score crosses a threshold you set)* | — | 10–20 | Unlimited |
| Automated monitoring *(Intrinsica re-runs your watchlists on a schedule, unprompted)* | — | — | Yes |
| "What Changed?" *(which factor moved a score, this run versus the last)* | — | — | Yes |
| Exports | — | CSV / PDF | Bulk |

~~Closing line: "Free sells the framework · …"~~ *Removed 2026-09-27 (user decision).*

Three deliberate resolutions are encoded in this table:

- **Tickers per run is the only run-size limit; parallelism is never sold** *(user decision
  2026-09-27)*. The analyst engine (`orchestrator/batch.py`) analyzes **3 tickers at a time**
  through a rolling worker pool (`RECALC_CONCURRENCY=3`, with pacing), because more trips
  the data source's per-IP rate limit and slows the whole run. That is a server setting
  shared by every plan, so the former "Bulk / parallel analysis — / — / Yes" row — which
  implied Unlimited runs 100+ at once — was removed. What plans differ in is how many
  tickers you can submit in one run. **Re-checking a saved watchlist runs the whole list,
  whatever the per-run cap** (option (a)), so Pro's 50-stock watchlists are not split into
  10-ticker runs. "Computed in parallel" stays as an engine claim (several tickers at a
  time, three engines inside each), true for the demo's 3. A faster queue could become a
  paid lever once a licensed data provider allows more simultaneous requests.
- **Compare is split in two.** "Tickers per run" is the results grid (3 / 10 / 100+).
  "Side-by-side breakdown" is a separate view **capped at 3 by screen width**, Pro and above.
  This replaces the undeliverable "5–10 side by side".
- **Free is labelled honestly.** It is *not* "the full product, capped" — every analysis is
  complete and nothing is blurred, **but volume, watchlists, history and discovery are capped.**

### 5.8 Footer

Two lines: the modeling-tool / not-personalized-advice disclaimer, and the positioning line.
A short form repeats on the checkout page.

**Share image and page metadata** *(added 2026-09-29; `index.html` has none today)*:
- **The image:** one **static** 1200 × 630 PNG, `public/og-image.png`, on the warm paper background. It shows:
  - the brand mark (about 160 px) and the "Intrinsica" wordmark;
  - the headline "Judge the business. Then judge the price.";
  - one line: "Quality · Moat · Fair Value · Reward/Risk — from the fundamentals, all shown."
- **The meta tags** in `index.html`:
  - `og:title` "Intrinsica — Judge the business. Then judge the price.";
  - `og:description` = the question band's line;
  - `og:image`, `og:type=website`;
  - `twitter:card=summary_large_image`;
  - a matching `<meta name="description">`.
- A per-stock share image waits for the per-stock pages on the backlog.

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

Card values (the grid's, before the 2026-09-27 rework) are **computed from these components in the UI**; the API should not send a
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

`page_view` → `analysis_started` (tickers, count, source) → `analysis_completed`
(duration_ms, count, source) → `breakdown_opened` (ticker, assessment tab) →
`methodology_viewed` (assessment) → `pricing_viewed` → `plan_selected` (plan, billing) →
`checkout_started` (plan, billing) → **`payment_button_clicked`** (plan, billing) →
`email_submitted` (optional).

> **CORRECTION (post-implementation, 2026-09-25) — `source` props added; the event list
> itself did NOT grow.** Three events gained a `source` prop during implementation, each
> because one event name was firing from two places and collapsing distinguishable things
> into one counter. A prop on an existing event is the sanctioned move here; a new event
> is not.
>
> - `analysis_started` and `analysis_completed` carry **`source: 'sample' | 'typed'`**.
>   The page auto-runs a marquee analysis on mount and the compare chip runs three fixed
>   tickers; neither is the visitor's own work. Without this prop every page load emits an
>   analysis nobody asked for, the started→completed step reads ~100% for everyone, and
>   `duration_ms` averages a warm cached lookup against cold multi-ticker runs. `count`
>   does **not** disambiguate them — the sample is one ticker and so is a typed
>   single-ticker run.
> - `free_plan_clicked` carries **`source: 'pricing' | 'checkout'`**. It fires from the
>   pricing CTA *and* the checkout confirm — two different funnel stages. Without this
>   prop, free-path drop-off cannot be computed at all.
>
> **`source` carries different vocabularies on different events**, so never pivot on
> `source` alone; group by `(event, source)`.
>
> The closed list is now enforced two ways: `analytics.test.ts` pins `Object.values(EVENTS)`
> against a hand-transcribed copy of the list below, and `track()` takes a narrowed
> `FunnelEvent` type so an off-spec event name fails the **build**, not just a test.

- **Primary metric:** unique visitors reaching `payment_button_clicked` ÷ unique visitors.
- **`free_plan_clicked` is a separate event** and is excluded from that ratio.
- **Hero rework (2026-09-27): no new events; the list stays at 12.**
  - `breakdown_opened (ticker, assessment)` now fires when a **card tile** or **comparison row** opens the breakdown (§5.2). For a tile, `assessment` is the tile clicked; for a row, the tab currently selected.
  - Nothing opens by itself any more, so every `breakdown_opened` is a real click. Folding it fires nothing, as before.
  - The hero's assessment links are gone, so `methodology_viewed` now fires only from the Framework tabs.
- **`watchlist_clicked` (ticker)** *(added 2026-09-26, user decision — the list grows by
  this one event)*: the star beside each ticker in the result card (§5.2; it was on the grid rows before the 2026-09-27 rework). Watchlists are not
  built; the click answers with a toast — "Watchlists require an Intrinsica account. Start with
  Free. See plans →" (the ticker rides on the event, not in the copy) — that stays 10 s or until
  dismissed. The star carries no lock icon, on purpose: a lock would suppress the very
  clicks this measures. Outside the paid funnel, like `free_plan_clicked`.
- Secondary: plan mix, billing mix, methodology engagement before conversion, drop-off per step.
- De-duplicate server-side by `visitor_id`; `localStorage` is a convenience, never the source
  of truth.

**This list is the whole of it — there is no blanket click or scroll tracking.** Deliberately
not instrumented: scroll depth, nav-link clicks, hovers and tooltip opens, calibration row
expands, individual breakdown tab switches, and the **billing toggle** (decided 2026-09-23 —
the annual/monthly shopping behaviour is not worth the noise; `plan_selected` already carries
the billing period actually chosen). Every extra event has to be de-duplicated and reasoned
about, and broad capture on a page with no accounts is a privacy liability with no payoff.

**Backend (decided 2026-09-23):** events post to **`POST /api/events`** on the existing
FastAPI app — a new `backend/routers/events.py` registered like the other routers
(`app.include_router(events_router, prefix="/api")`), taking a small Pydantic body
(`event`, `visitor_id`, `ts`, `props`). It is fire-and-forget from the client: a failed post
must never block or break the funnel, and the endpoint always returns quickly.

Storage follows the existing persistence pattern (`backend/services/*_sheets.py` → Google
Sheets), appending one row per event to an events sheet — adequate for smoke-test volumes and
immediately analysable in a spreadsheet. Two caveats for the implementation plan: Sheets has
write rate limits, so appends should be **batched / queued rather than one API call per
event**; and if volume makes that awkward, swap the sink for a local append-only file or
SQLite table behind the same endpoint — the route and payload stay unchanged either way.

Abandonment is **derived**, not logged: `checkout_started` minus `payment_button_clicked` for
the same `visitor_id` is the final-step drop-off, so both events must fire reliably.

> **CORRECTION (post-implementation, 2026-09-25) — this formula is wrong computed globally.**
>
> Filter to **`plan != 'Free'`**. The Free path routes through the *same* checkout screen,
> so it fires `checkout_started` — but on the click it fires `free_plan_clicked`, never
> `payment_button_clicked`. Subtracting globally therefore counts **every completed Free
> journey as an abandonment**, which produces a plausible-looking wrong number rather than
> an obviously broken one.
>
> This is why `checkout_started` carries `plan` on every path that fires it. Do **not**
> "fix" it by adding an event (§9's list is closed) or by dropping `checkout_started` for
> Free (that loses the Free funnel entirely).
>
> Related: **nothing de-duplicates server-side.** `backend/routers/events.py` appends one
> row per event, so "de-duplicate server-side by `visitor_id`" above is an instruction
> about how to **count** when analysing the sheet, not a description of what the endpoint
> does. Count distinct `visitor_id`; the primary metric is unique *visitors*, not events.

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
- **Contract:** a golden-file test per sample ticker asserting each card headline equals the
  value derived from the breakdown components, so the two cannot drift.
- **Component:**
  - the result card's tiles view and comparison view;
  - the tier captions;
  - the sample pill vs "Your analysis";
  - loading inside the card;
  - a failed tile or cell;
  - the star inside the card;
  - a tile click opening the breakdown on that tile's tab, and a row click opening that ticker; clicking again or Close folding it; nothing auto-opening;
  - a failed run keeping the previous card;
  - the question band and the tab-pair labels;
  - the billing toggle updating both the card prices and the checkout total;
  - checkout state reset on re-entry.
  *(Hero rework 2026-09-27: the tests for the hero assessment links, the pipeline strip and the grid rows are removed with those elements.)*
  - *(Brand round 2026-09-29.)* The Framework rows:
    - they render collapsed, with the question and the weight;
    - a click opens one row, and the rows toggle independently;
    - an open row shows the chips and the High / Low line;
    - the scale strip or the Fair Value line is shown.
  - The brand mark renders in the nav, and no mark appears on the card or the rows.
  - The watch and close buttons render icons, keeping their accessible names.
  - The reveal on scroll:
    - elements get the hidden class only once the script runs;
    - they become visible when they intersect;
    - the hero is never hidden;
    - nothing is hidden under reduced motion.
- **Content guards** *(2026-09-29)*:
  - `framework.test.ts` pins the new row shape (`question`, `hi`, `lo`, weight) for every category of all four assessments;
  - a test pins the "Intrinsica's own method." paragraph and asserts the phrase "no single agreed" is gone;
  - a test asserts `index.html` carries the og/twitter tags and that `public/og-image.png` exists.
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

*Status 2026-09-27:* the shipped page uses **AAPL** (`SAMPLE` in `LandingPage.tsx`). It now opens the hero card, currently at a −53% gap. The hero rework keeps AAPL; changing the ticker is a one-constant change if it is revisited.

## 13. Implementation notes

- **The repo-wide rename "Agent Stock" → "Intrinsica"** (docs, frontend copy, backend strings,
  page titles, metadata) is part of this work item and has not been done.
- Build the landing page as a new route tree under `frontend/src/pages`, with the results grid,
  the breakdown and the methodology panel as separate components — the mock's single-file
  structure is a prototype, not the target architecture.
- Port the mock's CSS tokens into the Tailwind theme rather than copying the raw stylesheet.
- Analytics wiring (§9) and the copy-guard lint (§11) land with the page, not after it.

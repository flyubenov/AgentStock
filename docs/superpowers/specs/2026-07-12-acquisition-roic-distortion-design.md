# Acquisition-Distortion Adjustment for Section II (+ Beta Cap)

**Date:** 2026-07-12
**Status:** Approved
**Area:** `backend/screener` (scoring), `frontend` (display)

## Problem

The Screener rated AMD **6.6**, understating a business that scores strongly nearly
everywhere. The drag is entirely **Section II (Returns on Capital) = 3.6** at 30%
weight. Its sub-scores:

| Sub-score | Value | Band score |
|---|---|---|
| ROIC (TTM) | 5.1% | 4.0 |
| ROIC (5y avg) | 2.6% | 2.0 |
| ROIC − WACC spread | −11.76 | 0.0 |
| ROTE | 20.5% | 8.5 |

Two independent distortions, both artifacts rather than real weakness:

1. **The Xilinx acquisition (~$49B, all-stock, Feb 2022).** Purchase-accounting loads
   the balance sheet with goodwill/intangibles: **Goodwill & Intangibles = $41.8B of
   $66.2B Invested Capital (63%)**. ROIC is hit from both sides — the denominator
   (invested capital) is inflated by the deal price tag, and the numerator (EBIT) is
   depressed by ~$1.2B/yr of intangible **amortization**. ROIC reads 5.1% when the
   underlying economic return is ~13.8%. The tell: **ROTE (which uses *tangible* book
   value, excluding the deal price tag) reads a healthy 20.5%** — the two twin metrics
   disagree solely on whether the acquisition price tag is counted.

2. **An inflated beta.** yfinance reports AMD's beta as **2.469**, pushing WACC to
   **16.9%**. That is stale/aggressive (a realistic beta is ~1.6–1.8). The unrealistic
   hurdle pins the spread sub-score at 0.

The existing `_earnings_distorted` guard detects the same trailing-vs-forward P/E signal
(185 vs 42 = 4.4×) but (a) only excludes EPS growth from **Section I**, and (b) is gated
on `eps_cagr ≤ 0`, so it never fires for AMD (EPS CAGR = +46.7%). Nothing addresses the
Section II ROIC distortion.

## Approach (chosen)

**Option 1 — Tangible-capital ROIC (recompute) + beta cap.** Correct the distorted
metric rather than delete it (Option 2, "exclude and lean on ROTE", was rejected as too
generous — it would let Section II rest on the flattering 20.5% ROTE alone, ignoring that
the honest tangible ROIC is only ~14%).

### A. Beta cap (input fix)

In `metrics.py::wacc`, cap the beta feeding cost-of-equity at **`BETA_CEILING = 2.0`**:

```python
beta = min(beta, BETA_CEILING)
```

- Applies globally; no gating. Only bites when reported beta > 2.0.
- Can only lower an inflated WACC hurdle, never raise it.
- Most companies (beta 0.5–1.8) are unaffected. Affects only high-beta outliers, whose
  spread sub-score gets a slightly easier — and more realistic — hurdle.
- Changes both `m.wacc` and `m.roic_wacc_spread`.

### B. Tangible-capital ROIC substitution

**Detection gate — `_acquisition_distorted(m)` fires only when ALL hold:**

1. `goodwill_intangible_share >= GOODWILL_SHARE_FLOOR` (0.30) — a large past
   acquisition sits on the books.
2. `trailing_pe / forward_pe > DEPRESSED_PE_RATIO` (reuse existing 1.5) — earnings are
   amortization-depressed and the market prices a recovery (distinguishes an
   amortization trough from a serial over-payer genuinely destroying value).
3. `roic_ex_goodwill > roic_ttm` — strict "can only ever help, never hurt" guard,
   matching the philosophy of the existing distortion adjustments.

Deliberately **not** gated on `eps_cagr <= 0` (that gate is what stops the *earnings*
adjustment firing for a fast-grower like AMD, and it must not apply here).

**New metrics in `metrics.py` (all None-safe, from data already fetched):**

- `roic_ex_goodwill` (TTM): `EBIT × (1 − tax) / (Invested Capital − Goodwill&Intangibles)`
  → AMD ≈ **13.8%**
- `roic_5y_ex_goodwill`: same formula per year, averaged over available years
  → AMD ≈ **9.9%** (dragged by the 2023 integration trough — legitimately)
- `goodwill_intangible_share`: `Goodwill&Intangibles / Invested Capital` → AMD ≈ **0.63**

Goodwill & intangibles is taken from the balance-sheet row
`"Goodwill And Other Intangible Assets"` when present, else `Goodwill +
Other Intangible Assets`.

**Wiring in `scoring.py::section_scores`:** when `_acquisition_distorted(m)`, Section II
scores `roic_ex_goodwill`, `roic_5y_ex_goodwill`, and a recomputed spread
(`roic_ex_goodwill − m.wacc`) in place of the reported ROIC trio. ROTE is untouched.
Sub-score count is unchanged (substitution, not exclusion).

### C. Breakdown + UI

Record a `roic_adjustment` entry in the `score()` breakdown, reusing the existing
`SectorAdjustment` card shape (`profile`, `excluded` = substituted-metric labels, `note`)
plus the reported-vs-tangible ROIC numbers and the goodwill share:

```json
"roic_adjustment": {
  "profile": "TECH_GROWTH",
  "excluded": ["ROIC (TTM)", "ROIC (5y avg)", "ROIC − WACC spread"],
  "reported_roic": 5.1,
  "tangible_roic": 13.8,
  "goodwill_intangible_share": 0.63,
  "note": "..."
}
```

Rendered via the existing `AdjustmentCard` — one new line in `ScreenerPanel.tsx` (title
"Acquisition Adjustment") and one optional field in `types.ts::ScoreBreakdown`.

## Expected outcome

Section II: 3.6 → **~5.4** (ROIC 6.5, ROIC-5y 4.0, spread 2.5, ROTE 8.5).
Quality Score: **6.6 → ~7.2** — honest, not inflated. AMD's real tangible ROIC (~14%) is
good but not elite, and the 2023 Xilinx-integration trough legitimately weighs on the
5-year figure.

## Scope / generality

Not an AMD-only patch — applies to any large-acquisition name whose goodwill dominates
invested capital while earnings are amortization-depressed (much of pharma; post-VMware
AVGO already noted in memory). Tightly gated so normal companies are untouched.

## Testing

- `_acquisition_distorted` detection: fires for an AMD-like name; does NOT fire for a
  normal (low-goodwill) name, nor for a goodwill-heavy name without the P/E recovery
  signal (a genuine over-payer).
- Section II lift: distorted name scores Section II higher than the same metrics scored
  raw.
- Beta cap: a beta > 2.0 produces a capped WACC / improved spread; a normal beta is
  unchanged.
- End-to-end AMD-like: Quality ≈ 7.2, `roic_adjustment` recorded, NOT routed through the
  pre-profit branch, not capped.

## Non-goals

- No change to the Fair-Value engine.
- No change to ROTE, Sections I/III/IV, or the existing earnings/capex/sector
  adjustments.
- The beta ceiling (2.0) and goodwill floor (0.30) are fixed constants, not configurable.

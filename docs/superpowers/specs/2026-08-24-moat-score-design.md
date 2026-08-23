# Moat Score — Design Spec

- **Date:** 2026-08-24
- **Status:** Design approved in brainstorming; awaiting spec review → implementation plan.
- **Author:** f_lub (with Claude)

## 1. Summary

Add a **Moat Score**: a single number, 0–100, measuring one thing only —
**the durability of a company's economic profit**. It quantifies whether a
business earns returns above its cost of capital *and whether that excess has
persisted and stayed stable*, i.e. whether competition has failed to compete it
away.

The score is a **pure scoring function over metrics the Screener pipeline
already computes**. It does not fetch any new data, does not run as a fourth
independent pipeline, and is displayed as one additional sortable/filterable
column in the Database grid, next to Quality.

### Why it is distinct from the Quality Score

The Quality Score is a broad "is this a good, healthy, well-run, growing
business?" composite. Only ~half of it is moat-relevant (its Section II returns
+ the margin parts of Section I); the rest rewards growth, low leverage,
buybacks, insider ownership, and shareholder yield — all orthogonal to whether a
moat exists. Critically, the single most defining property of a moat —
*durability/consistency of excess returns* — is the part Quality captures
worst (it scores the *level* of ROIC, never its *stability across a cycle*).
The Moat Score isolates exactly that missing signal.

### Design decisions (settled)

1. **Character:** strict, pure durability-of-economic-profit. No growth,
   leverage, dilution, or stewardship terms (those stay in Quality).
2. **Lookback:** 5 years (realistic given yfinance statement depth).
3. **Output:** a numeric score, 0–100, only. **No** categorical bands
   (Wide/Narrow/None etc.).
4. **Architecture:** rides the Screener pipeline; zero additional yfinance I/O.
5. **UI:** one column in the Database grid, next to Quality.

## 2. Non-goals / out of scope

- **Not** a moat *source* classifier (brand, switching costs, network effects,
  cost advantage, efficient scale). Financial statements measure the *symptom*
  of a moat, not its cause; the score is honest about being a symptom measure.
- **Not** a moat-*trend* score (whether the moat is strengthening/eroding beyond
  the light non-erosion term inside margin durability).
- **No** categorical rating labels.
- **No** ticker-detail Moat panel for now (grid column only).
- **No** change to how FV or Quality are computed.
- The **fetch-once shared-data refactor** across all three pipelines (see §9) is
  a noted follow-up, explicitly **out of scope** for this work.

## 3. The model

Internal scale is **100 points**, split across three pillars. Each metric maps
directly to its point allocation via bands. The headline is the sum of earned
points over available points, renormalized to 100 when a metric is unavailable
or excluded (see §4).

| Pillar | Metric | Points |
|---|---|---|
| **A. Economic-profit magnitude** | A1 ROIC level (5y avg) | 20 |
| *(40)* | A2 Economic spread, ROIC − WACC (spot & 5y blended) | 20 |
| **B. Economic-profit durability** | B1 Persistence — % of years ROIC > WACC | 25 |
| *(50)* | B2 Consistency — low ROIC variability (5y) | 10 |
| | B3 Margin durability — stability + non-erosion (gross/op) | 15 |
| **C. Cash-backing** | C1 FCF conversion (ROIC → real cash) | 10 |

Net weighting: **Magnitude 40 / Durability 50 / Cash-backing 10** — durability
is the largest pillar, matching the "pure durability" intent.

### 3.1 Bands (proposed defaults; tunable — see §11)

All thresholds are constants in `moat/scoring.py`.

**A1 — ROIC level, 5y avg (max 20)** — `score_high` on 5y-avg ROIC %:

| 5y ROIC | Points |
|---|---|
| > 25% | 20 |
| 20–25% | 17 |
| 15–20% | 13 |
| 12–15% | 8 |
| 8–12% | 4 |
| < 8% | 0 |

**A2 — Economic spread, ROIC − WACC (max 20)** — on the blend
`0.5·spot_spread + 0.5·(roic_5y_avg − wacc)` (pp):

| Spread (pp) | Points |
|---|---|
| ≥ 15 | 20 |
| 10–15 | 16 |
| 5–10 | 11 |
| 0–5 | 5 |
| < 0 | 0 |

**B1 — Persistence (max 25)** — `points = 25 · (years with annual ROIC > WACC ÷
years available)`. With ~4–5 years of data this is coarse (5/5 = 25, 4/5 = 20,
3/5 = 15, …), which is acceptable and honest. **Approximation:** we hold only a
*spot* WACC (beta-driven), not historical WACC, so every year is tested against
today's WACC (or the FINANCIAL cost-of-equity for banks). Documented in code.

**B2 — Consistency (max 10)** — `score_low` on the coefficient of variation
`CoV = stdev(roic_series) / mean(roic_series)` (only when `mean > 0`; if
`mean ≤ 0`, consistency is meaningless → 0 points and the gate in §4.1 will fire
anyway):

| CoV | Points |
|---|---|
| ≤ 0.10 | 10 |
| ≤ 0.20 | 8 |
| ≤ 0.35 | 5 |
| ≤ 0.50 | 3 |
| > 0.50 | 0 |

**B3 — Margin durability (max 15)** — the mean of up to three components, scaled
to 15. Emphasis is on *stability + non-erosion*, not the absolute level (a flat
70/71/69/72/70 gross-margin series beats an eroding 70/64/57/51/45 even at the
same current level):

- **Gross-margin stability** — `score_low` on stdev of the gross-margin series
  (pp). Requires the statement "Gross Profit" row; omitted if unavailable.
- **Operating-margin stability** — `score_low` on stdev of the op-margin series
  (pp).
- **Non-erosion** — `score_high` on margin trajectory (latest − oldest, pp),
  reusing the existing `op_margin_trajectory` and a new `gross_margin_trajectory`.

Each component scores 0–10 on its bands; the subscore is
`15 · mean(components) / 10`.

**C1 — FCF conversion (max 10)** — `score_high` on `fcf_ttm / ebitda_ttm`:

| FCF/EBITDA | Points |
|---|---|
| ≥ 0.90 | 10 |
| ≥ 0.70 | 8 |
| ≥ 0.50 | 6 |
| ≥ 0.30 | 3 |
| < 0.30 (or ≤ 0) | 0 |

## 4. Structural rules

### 4.1 Economic-profit gate

A moat is *durable excess return*. If a company has **no durable excess return**
— `roic_5y_avg ≤ wacc` (or `rote_5y_avg ≤ FINANCIAL_COE` for financials, §4.2) —
it is capped in the low range regardless of the other pillars:
`moat_score = min(moat_score, MOAT_GATE_CEIL)` with a proposed
`MOAT_GATE_CEIL = 35`. This hard-codes the definition (mirrors the Quality
pipeline's `UNPROFITABLE_CEIL`). A negative-ROIC / pre-profit company therefore
lands low, not blank (the signal *is* "no financial moat").

### 4.2 Distortion reuse (inherited from the Screener)

- **Acquisition-distorted names** (`_acquisition_distorted`, e.g. AMD/SNPS):
  magnitude, persistence, and consistency use the **tangible** ROIC series
  (`roic_ex_goodwill` / `roic_5y_ex_goodwill` and the ex-goodwill annual
  series), so goodwill/amortization from a past deal is not misread as a weak
  moat. Reuses the existing `screener.scoring` predicate.
- **Financials** (`profile == "FINANCIALS"`): ROIC via EBIT/invested-capital is
  a poor frame for a bank, so the whole ROIC axis switches to **return on
  tangible equity vs cost of equity**: A1 scores `rote_5y_avg` (level), A2 the
  spread `rote_5y_avg − FINANCIAL_COE` (0.085), and B1/B2 run over the
  `rote_series` instead of the ROIC series. This is a **deliberate Moat design
  choice**, not inherited — the Quality pipeline keeps ROIC for banks and merely
  zeroes its balance-sheet section. Flagged for validation against real bank
  tickers (§11).

### 4.3 Exclusions & renormalization

- **C1 FCF conversion is excluded** (and its 10 points drop out of the
  denominator) for `FINANCIAL` and heavy-capex-distorted names
  (`_heavy_capex_distortion`) — for a lender or a data-centre builder, FCF
  conversion is structurally distorted, exactly as the Quality pipeline already
  excludes their FCF metrics.
- Any metric that is `None` (missing statement data) is dropped from both the
  earned and the available point totals, and the score is renormalized to 100
  over what remains: `moat = 100 · earned / available`.

### 4.4 Coverage floor

If fewer than **`MOAT_MIN_YEARS = 3`** annual ROIC observations exist, or fewer
than a minimum set of pillars can be scored, `moat_score = None` and the grid
column shows blank (a young IPO simply has no durability history yet). Mirrors
the Screener's `MIN_SCORED_SUBSCORES` convention.

## 5. New derived metrics (all from data already fetched)

Every input already exists in the fetched `income` / `balance` / `cashflow`
statements or in `ScreenerMetrics`. The following are **stored** (some are
already computed in-scope in `screener/metrics.py` but currently discarded):

Added to `ScreenerMetrics` (or a companion structure the moat module reads):

- `roic_series: list[float]` — per-year ROIC (the `annual` list already built at
  `metrics.py` compute time).
- `roic_series_ex_goodwill: list[float]` — the `annual_ex` list (already built).
- `rote_series: list[float]` — per-year return on tangible equity (Net Income ÷
  Tangible Book Value), for the financials variant (§4.2). Both rows are already
  in the fetched income statement + balance sheet.
- `rote_5y_avg: float | None` — mean of `rote_series` (the financials analogue of
  `roic_5y_avg`).
- `gross_margin_series: list[float]` — from statement Gross Profit / Total
  Revenue, when the Gross Profit row is present.
- `op_margin_series: list[float]` — from statement Operating Income / Total
  Revenue.
- `gross_margin_trajectory: float | None` — latest − oldest gross margin (pp),
  twin of the existing `op_margin_trajectory`.

No new fields are needed for A1/A2/C1 — `roic_5y_avg`, `roic_wacc_spread`,
`wacc`, `fcf`, `ebitda` already exist.

## 6. Architecture

Moat rides the Screener pipeline as a **pure scoring module**:

```
backend/moat/
  __init__.py
  metrics.py    # durability derivations (persistence, CoV, margin stability)
                # computed from ScreenerInputs / ScreenerMetrics series
  scoring.py    # the 40/50/10 model, bands, gate, exclusions, renormalization
  models.py     # MoatResult (or fold moat_score into ScreenerResult — see §6.1)
```

### 6.1 Wiring

- `screener/metrics.py` extended to **store** the series listed in §5 (they are
  already computed or one line away from it).
- `screener/engine.py`: after `score(...)` produces the quality score, call
  `moat.scoring.score(metrics, profile)` from the **same `metrics` object** —
  no new fetch, one extra in-memory computation. Attach `moat_score` (and an
  optional `moat_breakdown` for future detail use) to the result.
- **Persistence:** `moat_score` is written to the Screener's Sheets record and
  **mirrored into the Database row** exactly as `quality_score` is today
  (`orchestrator/batch.py` already upserts the screener result; add the moat
  column to the same write path).

### 6.2 Frontend

- `frontend/src/types.ts`: add `moat_score` to `TickerResult`; add a
  `moatScoreColor(...)` helper (color ramp; a 0–100 analogue of
  `qualityScoreColor`).
- `frontend/src/pages/Database.tsx`: add a **Moat** column immediately after
  Quality — sortable (extend `SortKey`) and range-filterable (extend `Filters`,
  `EMPTY_FILTERS`, serialization, `rowMatches`, and the header `FilterHeader` +
  `RangeFilter`, following the existing Quality/R-R column pattern exactly).
- No ticker-detail changes in this scope.

## 7. Data flow & performance

- **Zero additional yfinance round-trips.** Moat consumes the `ScreenerMetrics`
  the Screener pipeline already builds. The one added cost per ticker is a small
  in-memory computation (CoV, persistence count, margin stdevs).
- Current reality (context, not changed here): the three pipelines each call
  their own fetch helpers, but every fetch is `@lru_cache(maxsize=256)` keyed by
  ticker (`services/yahoo.py`, `services/statements.py`), so raw network pulls
  are de-duplicated per process. Moat adds nothing to this.

## 8. Edge cases

- **Negative / pre-profit ROIC:** gate (§4.1) caps low; not blank.
- **< 3 years of data:** `moat_score = None` (blank column).
- **Missing Gross Profit row:** gross-margin stability + trajectory components of
  B3 are dropped; B3 scores on op-margin components only (renormalized within
  B3).
- **Financials:** ROTE − FINANCIAL_COE variant; FCF conversion excluded.
- **Heavy-capex reinvestors:** FCF conversion excluded, renormalized.
- **Acquisition-distorted:** tangible ROIC series used throughout.
- **WACC unavailable** (no beta): spread/persistence terms that need WACC are
  dropped and renormalized; if too little remains, coverage floor → None.

## 9. Follow-up (out of scope, noted)

Introduce a per-ticker "fetch once, pass a shared data context to all pipelines"
refactor, replacing the current reliance on `lru_cache` coincidence and removing
the genuine double-pull in `_fetch_ev_ebitda_history_sync` (which re-fetches
`income_stmt` / `balance_sheet` / 6y-monthly price under its own `yf.Ticker`
rather than the cached `fetch_*` helpers). This is a larger refactor touching
FV, Screener, and Risk-Reward, to be done on its own branch.

## 10. Testing

- **Unit — `moat/metrics.py`:** persistence fraction, CoV, margin stdev /
  trajectory over synthetic series (including short series, all-negative,
  single-year).
- **Unit — `moat/scoring.py`:** each band boundary; pillar renormalization when
  a metric is None; the economic-profit gate; the financials ROTE variant; the
  acquisition ex-goodwill path; the heavy-capex / financial FCF exclusion.
- **Golden cases:** a wide-moat name (high stable spread → high 80s/90s), a
  no-moat commodity/cyclical (spread ≈ 0 → gated low), an eroding-margin name
  (B3 drags it below a stable peer at equal current margins), a pre-profit
  burner (gated low), a bank (ROTE variant produces a sane score).
- **Regression:** Quality, FV, and R-R outputs are byte-identical (Moat only
  *reads* the metrics; storing new series must not change existing scores).
- Full suite must stay green (currently ~520 tests).

## 11. Open / tunable knobs

Recorded so the plan can sweep them against real tickers:

- **Band thresholds** for A1/A2/B1/B2/B3/C1 (defaults in §3.1).
- **`MOAT_GATE_CEIL`** (default 35).
- **`MOAT_MIN_YEARS`** (default 3).
- **A1 vs A2 balance** (currently 20/20; the external model weighted ROIC level
  above spread — a level-heavier 22/18 is defensible for robustness since WACC is
  noisy).
- **Persistence hurdle** — spot WACC vs a fixed hurdle (e.g. 10%). Default: spot
  WACC (ROTE→FINANCIAL_COE for banks).
- **Display scale** — stored/displayed as 0–100 (matches the point model);
  trivially rescalable to /10 for visual parity with Quality if preferred later.

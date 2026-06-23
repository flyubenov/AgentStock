# DCF Real-FCF + EV Exit-Multiple Compression — Design Spec

**Date:** 2026-06-24
**Status:** Approved (brainstorming) — pending spec review
**Project:** Agent Stock
**Amends:** `2026-06-21-fair-value-batch-refactor-design.md` (supersedes decision #6; adjusts decisions #1 and #3)

## Goal

Make composite fair values realistic for high-quality mega-caps by fixing the two
sources of over-valuation diagnosed on MSFT (which currently reads **+129%** above
price, a fair value of ~$868 vs a ~$374 price):

1. The DCF cash-flow base used the `info`-dict free cash flow, which for MSFT is
   roughly **half** the real figure ($37B vs the true ~$71.6B), and the capex→CFO
   rule then swapped in raw **operating** cash flow ($170B) with **zero** capex
   deducted — inflating the DCF to ~$1,126.
2. The EV/EBITDA model grows EBITDA at the scenario rate for 10 years and then
   applies **today's premium multiple** (15.5×) to the year-10 EBITDA — holding a
   growth-premium multiple across a decade of realized growth — inflating it to
   ~$859.

After this change MSFT lands at **~$337 (−10%)**, i.e. roughly fair / modestly
undervalued.

## Background: what's being kept

- **Growth stays constant per scenario** for all 10 explicit years; 3% terminal
  growth applies only to the perpetuity. This is already how the model works and is
  **not** changing — no "growth fade." Each scenario's growth rate is a deliberate
  assumption that holds for the whole explicit window.
- Classifier, per-type weights, the EV-pick rule (EV/EBITDA-vs-EV/Sales fold),
  scenario *construction* (offsets ±5/−4, [2%,20%] base band, 2% pessimistic floor),
  and all other models are unchanged except where stated below.

## Resolved design decisions

### D1 — Delete the capex→CFO rule
Remove the capex→CFO rule entirely (original spec decision #6): delete
`engine.dcf_cashflow_base`, the `CAPEX_CFO_GATE` constant, and the `cashflow_base`
override path in `models.calc_dcf`. The DCF base is **always** `fin["fcf_ttm"]`. No
capex-conditional logic remains in the DCF.

### D2 — DCF base = real FCF from the cashflow statement
`fin["fcf_ttm"]` is sourced from the company's cashflow statement instead of the
unreliable `info`-dict figure, in priority order:
1. the statement's **"Free Cash Flow"** row (latest period), else
2. **"Operating Cash Flow" + "Capital Expenditure"** from the statement
   (yfinance reports Capital Expenditure as a **negative** number, so this is
   OCF − |capex|), else
3. the existing `info`-dict `freeCashflow` (current behavior), if the statement is
   unavailable (e.g. funds/ADRs).

This requires a **second yfinance fetch** per ticker (the cashflow statement),
mirroring the existing rate-limit retry + per-ticker cache used for the info dict.

### D3 — EV/EBITDA exit-multiple compression (company-specific)
At the 10-year exit, compress the EV/EBITDA multiple toward a fundamentally-justified
mature level derived from the model's **own** terminal assumptions:

```
F = (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE − TERMINAL_GROWTH)   # = 1.03/0.07 = 14.714
conversion       = real_FCF / EBITDA                            # company-specific
conversion_clamped = clamp(conversion, 0.40, 0.65)
justified_exit   = conversion_clamped × F                       # ≈ 5.9× … 9.6×
exit_multiple    = min(current_multiple, EV_EBITDA_CAP, justified_exit)
```

Rationale: a mature business growing at the 3% terminal rate, discounted at 10%, is
worth `F = 14.7×` its terminal **cash flow**; expressed against EBITDA that is
`conversion × F`. The clamp keeps a temporarily depressed or inflated conversion
from producing an absurd exit multiple. `min(current, …)` guarantees the rule only
ever **compresses** a premium multiple and **never inflates** an already-cheap stock.

MSFT: conversion 0.388 → floored to 0.40 → justified 5.9× → exit `min(15.5, 20, 5.9) = 5.9×`.

### D4 — EV/Sales exit-multiple compression (fixed mature)
EV/Sales uses a **fixed** mature multiple, not company-specific conversion:

```
exit_multiple = min(current_multiple, EV_SALES_CAP, MATURE_EV_SALES)   # MATURE_EV_SALES = 2.0
```

Rationale: EV/Sales exists specifically for early-growth, often **negative-FCF**
companies; their *current* FCF conversion is meaningless or negative and would gut
the model for exactly the firms it targets. `MATURE_EV_SALES = 2.0` corresponds to a
~0.13 mature FCF/Sales margin × F. Same never-inflate property via `min`.

### D5 — Lower the optimistic growth ceiling 25% → 20%
In `build_scenarios`, change `optimistic = min(base + 0.05, 0.25)` to
`min(base + 0.05, 0.20)`. The base band [2%, 20%], the pessimistic floor (2%), and
the ±5/−4 offsets are unchanged.

Side effect (intended): for the fastest growers whose base is already at the 20% cap
(e.g. MSFT), optimistic = realistic = 20%, so the optimistic leg collapses onto
realistic. Slower growers (base < 15%) keep a normal optimistic > realistic spread.

## Architecture / files changed

### `backend/services/yahoo.py`
- Add `fetch_ticker_cashflow(ticker) -> dict | None`: async wrapper around a cached
  `_fetch_cashflow_sync(ticker)` that calls `yf.Ticker(ticker).cashflow` and returns
  a small dict of the latest-period rows we need:
  `{"free_cash_flow", "operating_cash_flow", "capital_expenditure"}` (any missing row
  → `None` value). Returns `None` if the statement is empty/unavailable. Mirror the
  `_fetch_sync` rate-limit retry/backoff and `lru_cache` pattern.
- Add `real_fcf(cashflow: dict | None, info_fcf: float | None) -> float | None`
  implementing the D2 priority order.

### `backend/valuation/engine.py`
- Delete `dcf_cashflow_base` and `CAPEX_CFO_GATE`.
- `build_scenarios`: optimistic ceiling 0.25 → 0.20 (D5).
- `evaluate`: remove `cf_base = dcf_cashflow_base(fin)`; call `m.calc_dcf(fin, growth)`.
- `run(ticker)`: after `fin = extract_financials(info)`, `cf = await fetch_ticker_cashflow(ticker)`;
  `rf = real_fcf(cf, fin.get("fcf_ttm"))`; if `rf is not None: fin["fcf_ttm"] = rf`.
  Then `evaluate(fin)` as before. `evaluate` and the model functions stay pure
  (they only read `fin`), so static-fixture unit tests are unaffected.

### `backend/valuation/models.py`
- Add constants:
  `MATURE_MULTIPLE_FACTOR = (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)`,
  `EBITDA_CONV_FLOOR = 0.40`, `EBITDA_CONV_CAP = 0.65`, `MATURE_EV_SALES = 2.0`.
- Add `_compressed_exit_multiple(current_mult, conversion, conv_lo, conv_hi) -> float`
  returning `min(current_mult, clamp(conversion, conv_lo, conv_hi) * MATURE_MULTIPLE_FACTOR)`.
- `calc_dcf(fin, growth)`: drop the `cashflow_base` parameter; base is always
  `fin.get("fcf_ttm")`.
- `calc_ev_ebitda(fin, growth)`: compute `conversion = fcf / ebitda` when
  `fcf` (= `fin["fcf_ttm"]`) is present and `ebitda > 0`; exit multiple =
  `_compressed_exit_multiple(min(current, EV_EBITDA_CAP), conversion, EBITDA_CONV_FLOOR, EBITDA_CONV_CAP)`.
  If FCF is missing or EBITDA ≤ 0, fall back to the existing `min(current, EV_EBITDA_CAP)`
  (no compression possible without a conversion).
- `calc_ev_sales(fin, growth)`: exit multiple = `min(current, EV_SALES_CAP, MATURE_EV_SALES)`.
- `calc_sotp(fin)` already uses the EV/EBITDA spot multiple with a 0.85 discount; it is
  a single-point (non-projected) estimate and is **left unchanged** — the exit
  compression applies only to the 10-year-projected EV models.

## Edge cases / guards
- **Missing real FCF** (statement unavailable) → `fin["fcf_ttm"]` keeps the info-dict
  value; DCF and EV/EBITDA conversion both use it (current behavior).
- **Negative / very low conversion** (depressed or negative FCF) → clamped to the
  0.40 floor, so the EV/EBITDA exit multiple never collapses to ~0.
- **EBITDA ≤ 0** → no conversion; EV/EBITDA falls back to the plain cap (and the
  EV-pick rule already routes negative-EBITDA names to EV/Sales for the types that
  weight both).
- **Capital Expenditure sign**: treat the statement's Capital Expenditure as signed;
  FCF fallback = OCF + capex (capex is negative).

## Testing
Backend (pytest, static fixtures — no live yfinance):
- `test_yahoo`: `real_fcf` priority — (a) uses the statement FCF row, (b) falls back
  to OCF + (negative) capex, (c) falls back to info FCF when cashflow is `None`.
- `test_models`:
  - **Remove** `test_dcf_uses_cashflow_base_override` (param deleted).
  - DCF base now reads `fin["fcf_ttm"]` (existing DCF tests already do).
  - EV/EBITDA exit compression: with `fcf`+`ebitda` set so conversion < current/F,
    fair value drops vs the uncompressed multiple; conversion clamp at floor/cap;
    `min` never inflates a cheap stock (current 8× with high conversion stays 8×).
  - EV/Sales exit compressed to `MATURE_EV_SALES` when current > 2×; unchanged when
    current ≤ 2×.
  - Existing EV cap tests (no `fcf_ttm` in fixture) still pass via the fallback path.
- `test_engine`:
  - **Remove** the three `test_dcf_cashflow_base_*` tests; remove `dcf_cashflow_base` usage.
  - Update `test_build_scenarios_capped`: optimistic is now `min(0.25, 0.20) = 0.20`
    (so a raw-0.56 fixture → pess 0.16 / real 0.20 / **opt 0.20**).
  - `evaluate` still blends correctly with the compressed EV leg on a fixture.
- `test_engine_run` (integration): mock **both** `fetch_ticker_info` and
  `fetch_ticker_cashflow`; assert `fin["fcf_ttm"]` is taken from the cashflow
  statement and the resulting `TickerResult` is `completed`.

## Validation target
MSFT (price ~$374) under the full change: DCF ~$405, EV/EBITDA ~$282 (exit 5.9×),
P/E ~$313 → **composite ~$337 (−10%)**, down from +129%. Spot-check a slower grower
(base < 15%, so the optimistic spread is preserved) and a thin-margin / EV/Sales name
(fixed 2× mature exit) to confirm the changes behave sensibly outside the mega-cap case.

## Out of scope (future)
- Stock-type-dependent growth bands (e.g. a higher cap for GROWTH than CYCLICAL).
- Normalizing the EV/EBITDA conversion across the cycle (D3 uses the current,
  possibly depressed, conversion — clamped — by design).
- Revisiting the conversion floor (0.40) as a tunable if mega-caps with temporarily
  low FCF conversion read too cheap.

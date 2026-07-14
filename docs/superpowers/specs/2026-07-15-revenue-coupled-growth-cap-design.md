# Revenue-coupled growth cap — design

**Date:** 2026-07-15
**Branch:** `feat/revenue-coupled-growth-cap`
**Status:** Approved, pending implementation plan

## Problem

The valuation engine caps the near-term growth rate used by every projection
model at a hard constant of `0.20` (`build_scenarios`, `backend/valuation/engine.py:62`).
That constant feeds the DCF, EV/EBITDA, EV/Sales, FCFE and RIM legs, and it is the
single most powerful lever in the model: for a name held flat for a 3–5 year window
before the size-coupled fade, fair value is nearly exponential in this rate.

For genuine hyper-growers (e.g. AppLovin/APP at ~59–70% revenue growth, NVDA at
~65%) the flat `0.20` refuses to extend *any* extra credit for demonstrably faster
compounding, so their fair value is systematically understated relative to a
disciplined view. Sensitivity on APP (live data):

| Growth cap | APP fair value | vs price |
|---|---|---|
| 0.20 (current) | $349 | −22% |
| 0.25 | $423 | −6% |
| 0.30 | $514 | +14% |

The goal is to hand hyper-growers a *modest, bounded* increment of growth credit
without loosening the model's conservative bias or re-inflating the mega-caps the
size-coupled fade was built to tame.

## Non-goals

- Not raising the cap for ordinary (< 20% growth) names — they stay at `0.20`.
- Not changing the size-coupled fade schedule (`_fade_hold_years` / `_faded_rate`).
- Not plumbing new data across modules (no screener → valuation dependency).
- Not touching the P/E leg (it does not use `build_scenarios`).

## Design

### Cap function

Replace the constant `0.20` in `build_scenarios` with a gentle, revenue-coupled,
profitability-gated cap:

```python
GROWTH_CAP_BASE  = 0.20   # unchanged floor / default
GROWTH_CAP_CEIL  = 0.25   # new ceiling
GROWTH_CAP_SLOPE = 0.125  # +1pp of cap per 8pp of growth; ceiling reached at g = 0.60

def _growth_cap(g: float) -> float:
    return min(GROWTH_CAP_CEIL, GROWTH_CAP_BASE + GROWTH_CAP_SLOPE * max(0.0, g - GROWTH_CAP_BASE))
```

Curve (flat 0.20 until growth passes 20%, linear ramp, saturates at g = 60%):

| Revenue growth g | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 100% |
|---|---|---|---|---|---|---|---|---|
| Growth cap | 0.200 | 0.200 | 0.213 | 0.225 | 0.238 | 0.250 | 0.250 | 0.250 |

Read as: *every 8 percentage points of revenue growth above 20% buys 1 point of
extra cap, topping out at 25%.* Even a 70%+ grower earns only +5pp over today's
constant.

### Growth source

`g` is sourced **statement-YoY first, info fallback**:

```python
g = fin.get("revenue_growth_stmt")
if g is None:
    g = fin.get("revenue_growth") or 0.0
```

This matches the recent statement-primary direction of the codebase (Rule-of-40,
statement revenue-growth commits). `revenue_growth_stmt` is populated for
forward-tier names during `run()` from the EV/EBITDA history reconstruction; other
names fall back to info `revenueGrowth`.

The **0.25 ceiling is the ultimate backstop against a noisy-high growth reading**:
even IREN's 168% statement growth yields only a 0.25 cap. The growth source cannot
push the cap past the ceiling.

### Profitability gate

The elevated cap applies only when the business is demonstrating economics —
otherwise the name stays pinned at `0.20`. Operating margin is not available in the
valuation `fin` dict (it is a screener metric), so the gate reuses the exact
cash-generation signal the engine's capex-reroute already uses (`engine.py:110`):

```python
def _cap_eligible(fin: dict) -> bool:
    fcf = fin.get("fcf_ttm")
    if fcf is not None and fcf > 0:
        return True
    ebitda = fin.get("ebitda_ttm") or 0
    ocf = fin.get("ocf_ttm")
    if ocf is None:
        ocf = fin.get("operating_cashflow")   # info fallback
    return ebitda > 0 and ocf is not None and ocf > 0
```

- FCF-positive names qualify (e.g. APP).
- Pure cash-burners (FCF < 0 and OCF ≤ 0) stay at `0.20`.
- Capex-reroute names (FCF < 0 but EBITDA > 0 and OCF > 0, e.g. IREN) qualify —
  the deliberate inclusion chosen during design: they are operationally
  cash-generative, so extending growth credit is consistent with the engine's
  existing treatment of them.

### Integration point in `build_scenarios`

`build_scenarios(fin, distorted_cap=0.20)` computes the cap once, then uses it in
place of both literal `0.20`s (the `base` clamp and the `optimistic` ceiling). The
pessimistic `0.02` floor is unchanged.

```python
cap = GROWTH_CAP_BASE
if distorted_cap >= GROWTH_CAP_BASE and _cap_eligible(fin):
    g = fin.get("revenue_growth_stmt")
    if g is None:
        g = fin.get("revenue_growth") or 0.0
    cap = _growth_cap(g)

if _earnings_distorted(fin):
    raw = min(fin.get("revenue_growth") or 0, distorted_cap)
else:
    raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
           or fin.get("revenue_growth_stmt") or 0.07)
base = max(0.02, min(float(raw), cap))
return {
    "optimistic": min(base + 0.05, cap),
    "realistic": base,
    "pessimistic": max(base - 0.04, 0.02),
}
```

## Interactions & safety

- **DDM / perpetuity isolation.** The elevated cap applies **only on the normal
  bounded-horizon path**, gated by `distorted_cap >= GROWTH_CAP_BASE`. The DDM path
  passes `distorted_cap = SUSTAINABLE_CEIL (0.039)`, so it keeps the `0.20` clamp
  and Gordon growth can never approach the discount rate. (`calc_ddm` also
  self-clamps growth to `DISCOUNT_RATE − 0.01 = 0.09` internally, so the DDM is
  double-protected.)
- **Distorted-earnings names** (negative earnings growth, positive revenue — e.g.
  ABBV/ETN). Their `raw` is already pre-capped at `distorted_cap`, so they do not
  receive the elevated cap. Deliberate: these are recovery names, not hyper-growers.
- **Universal application.** No mega-cap size carve-out (design decision). NVDA
  receives the largest lift because its hyper-growth earns the long flat hold, but
  it still lands below price (see below), so the signal direction is preserved.
- **Ceiling caps the blast radius.** The whole mechanism can lift a leg's growth by
  at most 5pp (0.20 → 0.25).

## Verified anchor impact (live data, final design)

| Behaviour | Tickers | ΔFV |
|---|---|---|
| Inert (growth ≤ 20% or negative) | HOOD, MSFT, KLAC, NFLX, TSLA, ETN | 0% |
| Small lift (growth 22–34%) | META +1%, AVGO +2%, AMD +4% | small |
| Hyper-growers lifted | APP +21% (→ −5.8% vs px), NVDA +25% (→ −14%), IREN +32% (→ −47.5%) | large |

**No anchor flips to a false "undervalued."** The closest is APP at −5.8% vs price;
every other name stays clearly below price. This is the key safety property.

## Testing plan (TDD)

1. **Cap function unit tests** — curve points (g = 10/20/30/60/70% →
   0.200/0.200/0.213/0.250/0.250), ceiling saturation above g = 60%, sub-20% floor.
2. **Profitability gate tests** — FCF-positive qualifies; pure burner (FCF < 0,
   OCF < 0) pinned at 0.20; capex-reroute shape (FCF < 0, EBITDA > 0, OCF > 0)
   qualifies via the OCF branch, with the `operating_cashflow` info fallback.
3. **Growth-source test** — statement YoY preferred over info; info fallback when
   `revenue_growth_stmt` absent; the 0.25 ceiling holds under an absurdly high
   growth reading.
4. **DDM isolation test** — a dividend name's DDM growth stays ≤ 0.20 even when its
   bounded-horizon cap is elevated.
5. **Distorted-earnings test** — an ABBV/ETN-shaped name does not receive the
   elevated cap.
6. **Anchor regression guards** — APP lifts (~+21%); sub-20% anchors
   (KLAC / MSFT / NFLX) unchanged. Locked as guard tests so future changes cannot
   silently move them.

## Files touched

- `backend/valuation/engine.py` — cap constants + `_growth_cap` + `_cap_eligible`
  helpers + updated `build_scenarios`.
- `backend/tests/` — the tests above (valuation-engine test module).

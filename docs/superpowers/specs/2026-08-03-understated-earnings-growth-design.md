# Understated-earnings-growth guard (`_earnings_understated`)

**Date:** 2026-08-03
**Session:** NFLX-NXT-growth-source
**Status:** Design approved; ready for implementation plan (TDD).
**Relates to:** `_earnings_non_operating` ([[bwxt-non-operating-growth-source]]), `_forward_target_pe` ([[hood-pe-growth-source-fix]]), the scenario-band work ([[scenario-growth-band]]).

## Problem

`build_scenarios` in `backend/valuation/engine.py` derives the realistic growth rate for the DCF / EV-EBITDA / P-E legs. Its final `else` branch takes the yfinance quarterly `earnings_growth` first, unconditionally. Four existing guards intercept cases where that quarterly figure is misleadingly **high** or wrong-signed (`_earnings_distorted`, `_earnings_non_operating`, `_earnings_inflated`, `_earnings_outpaces_revenue`). **None handle the mirror case: a quarterly `earnings_growth` that is misleadingly LOW** — an understated single-quarter print that drags the whole multi-year projection below the company's demonstrated annual trajectory.

Two live names exhibit this, both reading too bearish:

| Ticker | tier | quarterly `earnings_growth` | annual net-income growth | annual op-income growth | live baseline FV / pct |
|---|---|---|---|---|---|
| **NFLX** | GROWTH | 11.1% | 26.1% | 27.9% | $51.06 / −30.4% |
| **NXT** | MID_CAP | 2.9% | 15.1% | 9.1% | $49.71 / −45.2% |

In both, the quarterly print sits below **both** annual statement earnings lines while forward EPS is rising — the signature of an understated quarterly figure, not a real slowdown.

## Detector — `_earnings_understated(fin) -> bool`

Gateless statement-corroboration. Fires iff **all** hold:

- `earnings_growth` is not None and `> 0`
- `net_income_growth_stmt` and `op_income_growth_stmt` are both present and `> 0`
- `net_income_growth_stmt > earnings_growth` **and** `op_income_growth_stmt > earnings_growth` (both annual lines exceed the quarterly print)
- `forward_eps` and `eps_ttm` present and `forward_eps > eps_ttm`

No numeric gap threshold. The "both annual lines exceed eg" corroboration is the sole discriminator; a live 20-name sweep (`sweep_corroboration.py`) shows it fires on exactly `{NFLX, NXT}` and nothing else. `forward_eps > eps_ttm` confirms the forward direction agrees and validates that a re-source upward is warranted.

**Why gateless (design decision, reversing the earlier `> GROWTH_TRUST_FLOOR 0.10` cut):** the 0.10 gap was never the discriminator — corroboration alone already isolated NFLX 1/30. The gap only *excluded* NXT (its gap is 0.062, below 0.10) without protecting any canary. Dropping it removes a knob rather than adding one, and the re-source (below) is self-limiting, so no gap is needed to bound over-correction.

Both statement fields are already populated by the existing EV/EBITDA-history fetch (`engine.py` ~725–726). **No new fetch, no new constant.**

## Placement & precedence

New `elif _earnings_understated(fin):` — the **5th** guard, immediately before the final `else`, after `_earnings_outpaces_revenue`. The four existing guards keep priority. Mutually exclusive with `_earnings_non_operating` by construction (that requires `op_income_growth_stmt <= 0`; this requires `> 0`). Verified live: CRM/CSCO (`_outpaces_revenue`) and BWXT (`_non_operating`) are byte-identical under the guard, confirming precedence.

## Re-source

```
raw = min(net_income_growth_stmt, op_income_growth_stmt)
```

Then the existing clamp is unchanged: `base = max(0.02, min(raw, cap))`, and the scenario band builds off `base` exactly as today (`_band_growth_signal` is untouched — it already reads `revenue_growth_stmt`, so the optimistic/pessimistic offsets are unaffected beyond the moved realistic base).

**Why `min(ni, op)` (reversing the earlier forward-implied pick):**
- **Serves both tickers.** Forward-implied (`trailing_pe/forward_pe − 1`) works for NFLX (0.200) but breaks NXT (0.499 → clamped to the cap → ~$117, absurd). `min(ni,op)` lands both correctly.
- **Symmetric with the detector** — the guard fires on `eg < min(ni,op)`, so the re-source quantity *is* the detector quantity. One concept.
- **Self-limiting.** The correction magnitude equals the gap `min(ni,op) − eg`, so a name that barely trips corroboration gets a proportionally tiny, correct-direction nudge. This is why no separate over-correction guard is needed.
- **Conservative + robust.** Takes the lower annual earnings line (NXT: op 9.1% over ni 15.1%), and unlike forward-implied it cannot be inflated by a depressed trailing EPS (retires the AVGO-style residual risk of the earlier design).

## Expected outcomes (measured live, 2026-08-03)

| Ticker | fires? | `min(ni,op)` | FV before → after | pct before → after |
|---|---|---|---|---|
| NFLX | ✅ | 0.261 (caps to ~0.20–0.25) | $51.06 → **$73.93** | −30.4% → +0.8% |
| NXT | ✅ | 0.091 | $49.71 → **$63.35** | −45.2% → −30.1% |

NFLX becomes ~fairly valued; NXT stays a modest SELL (correct — it is genuinely richly priced even at its ~9% operating-growth reality). Exact NXT landing is data-drift-sensitive (−23% to −30% across fetch days as the higher re-sourced growth amplifies input changes); the verdict (stays SELL) is robust.

## Blast radius

Live-measured across 20 sweep names + an 11-name FV harness (`blast_nflx.py`). The detector fires on exactly `{NFLX, NXT}`; every other name is byte-identical (Δ 0.00%): **KLAC, AMD, V, ANET, NBIS, IREN, CRM, CSCO, BWXT** (and AVGO/MU/MA/UNH/MMM/CDNS/NVDA/GOOGL/META fail corroboration in the sweep). Re-source has zero effect on non-firing names, so the only path to a canary regression is the detector, which the sweep bounds. No new constant, no new fetch.

## Testing (for the plan)

- Unit: `_earnings_understated` fires on NFLX-shaped and NXT-shaped synthetic `fin`; does **not** fire when either annual line is ≤ eg, when either is ≤ 0, when `forward_eps ≤ eps_ttm`, or when `eg ≤ 0`.
- Unit: precedence — a `fin` that would satisfy both `_earnings_understated` and an earlier guard is handled by the earlier guard.
- Unit: re-source sets realistic `base = max(0.02, min(min(ni,op), cap))`.
- Regression: full suite green (baseline 421 tests); canaries IREN/NBIS/KLAC unmoved.
- Live re-confirm (out of band): `sweep_corroboration.py` + `blast_nflx.py`.

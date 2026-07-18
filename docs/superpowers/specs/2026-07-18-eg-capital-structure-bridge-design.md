# Funding-gap correction for the forward EV-multiple equity bridge

**Date:** 2026-07-18
**Branch:** `fix/eg-capital-structure-bridge`
**Motivating ticker:** CRWV (CoreWeave)

## Problem

The forward EV-multiple legs (`calc_ev_sales`, and the capex-reroute `calc_ev_ebitda`)
project revenue/EBITDA out `HORIZON` years, apply an exit multiple to get a **year-10
enterprise value**, then bridge to equity by subtracting **today's** net debt and dividing
by **today's** share count:

```
equity_per_share = (future_EV − net_debt_today) / shares_today
```

For a company that funds its growth by *raising external capital* — deeply FCF-negative,
already highly levered — this overstates equity. To reach the projected revenue the company
must deploy capital it does not have, financed by more debt and/or more shares. By year 10
neither net debt nor share count resembles today's. Subtracting a small "today" debt from a
large "future" enterprise manufactures phantom upside.

CRWV is the pathological case: net debt **$32.9B** (82% of a $39.9B market cap, 10.9× EBITDA),
FCF **−$7.25B/yr**, revenue growing 111.6%. The model projects revenue $8.3B → $128B over 10
years, applies a 2.0× sales multiple ($256B EV), subtracts only today's $32.9B, and prints a
realistic EV/Sales value of **$173/sh** and a composite **$113.79 (+55% "undervalued")**.

The distortion lives specifically in the **forward** legs. `calc_sotp` is a *spot* breakup
value (today's EBITDA × multiple − today's net debt) with no forward projection, so freezing
today's net debt there is internally consistent — **SOTP is out of scope**.

## Approach (chosen: A — cumulative funding-gap)

A cash-burning company must raise every dollar it burns; that raised capital becomes a claim
ahead of today's equity. So instead of freezing net debt, accrete onto it the **cumulative
external funding the burn requires** over the projection horizon.

The burn is estimated from the company's own FCF margin, faded from today's (deeply negative)
toward a mature terminal margin:

```
m0        = fcf_ttm / rev0                 # rev0 = run-rate revenue when available, else TTM
margin_t  = m0                       for t ≤ HOLD           (or HOLD ≥ HORIZON → flat)
          = m0 + (m_term − m0)·(t−HOLD)/(HORIZON−HOLD)      otherwise
R_t       = rev0 · Π_{s≤t}(1 + faded_rate(g, hold, s))     # same revenue path the leg projects
funding_gap = Σ_t max(0, −margin_t · R_t)                  # negative-FCF years only; no paydown credit
exit_net_debt = net_debt_today + funding_gap
```

The correction is **self-gating**: when `fcf_ttm ≥ 0` the gap is zero and the leg is
unchanged, so every FCF-positive name (KLAC, ANET, NVDA, KO, JPM, V, AVGO, SNPS, …) is
provably untouched. Only trailing-FCF-negative names that reach a forward EV-multiple leg move.

### Chosen calibration ("Base")

| Constant | Value | Rationale |
|----------|-------|-----------|
| starting margin basis | run-rate (`rev0 = revenue_run_rate or revenue_ttm`) | consistent with the base the leg projects from; CRWV m0 = −87% (vs −116% on TTM) |
| `FUNDING_TERMINAL_FCF_MARGIN` | `0.10` | defensible mature free-cash margin for a capital-intensive GPU-rental business (constant GPU refresh — not a 20%+ hyperscaler) |
| `FUNDING_FADE_HOLD` | `2` | CRWV is mid-buildout; the burn does not inflect immediately |

Resulting CRWV outcome: cumulative burn ≈ $113B → exit net debt ≈ $146B → EV/Sales avg ≈ $72
→ composite ≈ **$62 (−15%, modestly overvalued)**. Flips the +55% signal to fairly-valued-to-
modestly-overvalued, matching the intent.

The constants are named and centralized so recalibration (Lenient 15%/linear, Conservative
0%/hold-2, or a TTM basis) is a one-line change.

## Design

New pure helper in `backend/valuation/models.py`:

```python
def exit_net_debt(fin, rev0, growth, hold, net_debt) -> float:
    """net_debt_today + cumulative external funding the burn requires over HORIZON.
    Returns net_debt unchanged when fcf_ttm >= 0 or inputs are missing (self-gating)."""
```

- `fcf_ttm` from `fin`; `rev0` and `growth`/`hold` passed by the caller so the burn's revenue
  path exactly matches the leg's own projection.
- Nominal (undiscounted) sum: `exit_net_debt` is a year-10 nominal figure, subtracted from the
  year-10 nominal `future_EV`, and the whole per-share equity is discounted afterward — internally
  consistent. Interest on the accreted debt is ignored (a mild conservatism the other direction).

### Call sites

`calc_ev_sales` — projects revenue with flat growth (`hold = HORIZON`):

```python
net_debt = fin.get("net_debt") or 0
scenarios = {k: _scenario_ev_multiple(
        revenue, growth[k], multiple,
        exit_net_debt(fin, revenue, growth[k], HORIZON, net_debt), shares)
    for k in SCENARIO_KEYS}
```

`calc_ev_ebitda` — the burn projects **revenue**, not the leg's EBITDA base; pass the leg's own
`hold` and the revenue base:

```python
rev0 = fin.get("revenue_run_rate") or fin.get("revenue_ttm")
scenarios = {k: _scenario_ev_multiple(
        ebitda, growth[k], multiple,
        exit_net_debt(fin, rev0, growth[k], hold, net_debt), shares, hold)
    for k in SCENARIO_KEYS}
```

`_scenario_ev_multiple` and `_scenario_dcf_equity` are unchanged (DCF is zeroed for the
EARLY_GROWTH names this targets, and the DCF already models cash flows directly).

## Regression scope

Self-gating means the blast radius is exactly the trailing-FCF-negative names on a forward
EV-multiple leg. Required checks:

- **CRWV** — composite ≈ $62 (−15%), the intended flip.
- **NBIS** — EARLY_GROWTH on EV/Sales, also a levered AI-datacenter burner: FV drops (expected,
  desirable). Confirm it stays positive and sensible (memory notes NBIS FV is a wide range).
- **IREN — regression canary.** On the `calc_ev_ebitda` capex-reroute with negative FCF, so it
  *will* be touched. Verify the funding-gap does not over-penalize it into an unreasonable
  decline. **Decision gate:** if IREN over-corrects, scope the correction to `calc_ev_sales`
  only (the CRWV/NBIS cohort) and leave the capex-reroute as-is — those names already carry
  bespoke reroute weighting. Record the outcome.
- **FCF-positive canaries** (KLAC, ANET, NVDA, KO, JPM, V, AVGO, SNPS) — must be **byte-for-byte
  unchanged** (gap = 0). This is the primary safety assertion.
- **TEM / ASTS** — already declined; confirm still declined.

## Testing (TDD)

Unit tests on the pure helper and legs:

1. `exit_net_debt` returns `net_debt` unchanged when `fcf_ttm >= 0` (self-gating).
2. `exit_net_debt` returns `net_debt` unchanged when `rev0` or `fcf_ttm` is missing.
3. `exit_net_debt` accretes a positive gap for a burner; gap grows as terminal margin falls and
   as hold lengthens (monotonicity).
4. A synthetic CRWV-like fixture: composite drops from > price to modestly below price.
5. A synthetic FCF-positive fixture on EV/Sales: leg value identical with and without the change.
6. Full suite green (currently 311 tests); no unrelated movement.

# EV/EBITDA terminal-multiple temper for thin-gross-margin forward-tier names

**Date:** 2026-09-10
**Status:** Design approved in brainstorm; awaiting spec review → implementation plan.
**Pipeline:** Fair Value only (Quality / Moat / R-R untouched — different code paths).
**Origin:** FN (Fabrinet) validation — see `.claude/memory/fn-ev-ebitda-terminal-multiple-temper.md`.

## Problem

For a forward-tier name (`FORWARD_TIERS = {MEGA_CAP, LARGE_CAP, MID_CAP, GROWTH}`) the EV/EBITDA
leg anchors to a historical-median multiple (`ev_ebitda_hist`) and projects EBITDA forward,
applying that multiple as the **year-10 terminal exit multiple**. The multiple is bounded by
`_ev_ebitda_ceiling` (`valuation/models.py:206`), which lifts a durable multiple from the base
`EV_EBITDA_CAP = 20` toward a top (`EV_EBITDA_CAP_CEIL = 30`, mega 25) on
**`max(g_frac, q_frac)`** — the greater of a revenue-growth fraction and an FCF/EBITDA-conversion
fraction.

Because the lift is `max(...)`, **demonstrated growth alone can grant the full premium ceiling
regardless of business quality.** A thin-margin, capital-intensive contract manufacturer growing
fast is handed the same ~30x terminal ceiling as a high-margin software franchise.

**Worked case — FN (GROWTH, optical EMS):** revenue growth 44.6% → `g_frac = 1.0` → ceiling 30x,
so its historical multiple 25.97x passes uncapped. FV = **$769.56 (+82.6%)**, driven by the
EV/EBITDA leg ($927.8 @ 0.70 weight). A 26x *terminal* (mature-state) multiple for a business with
**~12% gross margin / ~10% operating margin** is an AI-cycle peak, not a mature franchise multiple.
Defensible center ≈ $480–550.

Full FCF-conversion compression (`_compressed_exit_multiple`) is **not** the fix: FN's ~0.6%
trailing conversion is *deliberate growth capex* (capex ≈ 3.75× D&A), so compression floors it to
~5.9x → FV ~$210, over-penalizing exactly the reinvestment the rest of the system deliberately
excludes from scoring (`_heavy_capex_distortion` in Quality and Moat). The trigger must not be
capex/conversion.

## Scope

**In:** temper the durable-branch terminal EV/EBITDA multiple for thin-**gross**-margin forward-tier
names. **Out (remain separate WATCH items, per user decision):**
[[wdc-spinoff-ev-ebitda-history-contamination]] (contaminated *base* + trough-spiked multiple) and
[[cf-cyclical-peak-dcf-overvaluation]] (CYCLICAL peak *base+growth* in the DCF leg — not a
forward-tier / not this code path).

## Signal — gross margin (chosen by full-universe sweep)

A premium terminal EV/EBITDA multiple is the market paying for a *franchise* (durable pricing power).
The cleanest franchise-vs-commodity discriminator is **trailing gross margin**:

- **Operating margin fails** — depressed by stock-based comp / acquisition amortization, so it
  wrongly flags SaaS franchises as commodities (sweep: WDAY −21%, NOW −18%, SNPS −15%, PANW −10%).
- **ROIC (5y) fails worse** — depressed by cash-heavy / acquisitive balance sheets, so it docks the
  widest moats (sweep: ISRG −20%, AVGO −11%, ORCL −27%, CDNS −7%, VEEV −20%, CRM −14%).
- **Gross margin is immune to both.** Sweep result: of 16 names it moves, **only FN changes
  investment verdict**; every gross-margin ≥ 50% franchise is byte-unchanged (0.0%).

Sweep artifacts: `docs/analysis/2026-09-09-ev-ebitda-temper/` (`temper_sweep.py`, `temper_out.csv`).
Read-only; monkeypatches `models._ev_ebitda_ceiling`; `CONCURRENCY=1` (shared-global race).

## Action — temper the durable ceiling

In `_ev_ebitda_ceiling`, blend the current growth-coupled ceiling toward a mature anchor by a
gross-margin quality fraction. **Only the `durable=True` branch** is touched (forward tiers with a
reconstructable historical multiple); the spot / non-durable path (EARLY_GROWTH, IREN capex-reroute)
returns `EV_EBITDA_CAP` unchanged, as today.

```
q_gm     = ramp(gross_margin_fraction, GM_TEMPER_LO=0.25, GM_TEMPER_HI=0.50)   # 0 = commodity, 1 = franchise
growth_ceiling = EV_EBITDA_CAP + max(g_frac, q_frac) * (top - EV_EBITDA_CAP)   # unchanged current formula
ceiling  = MATURE_EBITDA_MULT + q_gm * (growth_ceiling - MATURE_EBITDA_MULT)
```

- `q_gm = 1` (gross ≥ 50%): franchise → `ceiling = growth_ceiling` → **identical to today**.
- `q_gm = 0` (gross ≤ 25%): commodity → `ceiling = MATURE_EBITDA_MULT`.
- Ramp band 0.25–0.50 chosen so software/medtech/semis (60–90% gross) are fully exempt and true
  thin-gross manufacturers (FN 12%, autos, EMS) are fully tempered.

### Mature anchor — derived, not hardcoded

```
MATURE_EBITDA_MULT = QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR      # 0.90 * 14.714 ≈ 13.24x
```

Reuses two existing constants (`models.py`). Economic meaning: a matured commodity business whose
growth-capex surge has ended (capex → maintenance ≈ D&A) converts ~90% of EBITDA to cash
(`QUALITY_CONV_HI`), capitalized at the model's own Gordon factor (`MATURE_MULTIPLE_FACTOR =
(1+g)/(r−g)`). Independent of FN; cross-checks against where mature thin-gross manufacturers/EMS
trade (~6–13x). It moves automatically if those model assumptions are ever retuned.

## Data flow — source gross margin into `fin`

`_ev_ebitda_ceiling` gains a `gross_margin: float | None = None` parameter (fraction). `calc_ev_ebitda`
reads `fin.get("gross_margin")` and passes it. `engine.run()` sources it beside the existing
WACC/ROIC block (`valuation/engine.py:798-801`):

```
met = compute_metrics(sinp)
fin["wacc"] = met.wacc
fin["roic_wacc_spread"] = met.roic_wacc_spread
fin["roic_5y_avg"] = met.roic_5y_avg
fin["gross_margin"] = met.gross_margin        # NEW — percent; convert to fraction at use site
```

`met.gross_margin` is the TTM scalar (percent), confirmed populated (FN 12.0, CDNS 85.9, NOW 74.8,
BWXT 22.1) and materially identical to the swept `gross_margin_series[0]`.

## Neutral fallback / backward compatibility

`gross_margin` absent (screener fetch failed; synthetic-input unit tests; `evaluate(fin)` called
directly) → `q_gm = 1.0` → `ceiling = growth_ceiling` → **byte-identical to current behavior**. This
mirrors the existing neutral-rate fallback and preserves pipeline independence. `ramp(None, …)`
returns 1.0 by contract.

## Blast radius (measured, `MATURE ≈ 13x`)

16 names move; **FN is the only verdict change** (+84% → +7% vs price; FV $769 → ~$447). All other
movers were already SELL (temper deepens an existing SELL — verdict-neutral: BWXT −59%→−68%,
TSLA −87%→−89%, ETN −26%→−32%) or negligible at the band edge (AAPL/AMD/SHOP < 2%). Every
gross-margin ≥ 50% franchise: 0.0%.

**Canaries verified unmoved:** KLAC, ANET, NBIS, IREN (IREN/NBIS on the non-durable path).
**Canaries that move but stay verdict-neutral (re-confirm in regression):** BWXT
([[bwxt-non-operating-growth-source]]) −21%, ETN ([[distorted-earnings-dual-cap]]) −8% — both
already SELL.

## Testing (TDD)

1. **Green first:** `pytest` from `backend/` passes before any change.
2. **Unit — `_ev_ebitda_ceiling`:**
   - thin gross (0.12) + high growth + durable → ceiling == `MATURE_EBITDA_MULT` (not 30).
   - high gross (0.80) + high growth + durable → ceiling == current growth ceiling (unchanged).
   - `gross_margin=None` + durable → ceiling == current growth ceiling (identity fallback).
   - `durable=False` → returns `EV_EBITDA_CAP` regardless of gross margin (spot path untouched).
   - band edges: gross 0.25 → q_gm 0; gross 0.50 → q_gm 1.
3. **Unit — `MATURE_EBITDA_MULT`** equals `QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR` (guards against
   a future hardcode drift).
4. **Integration — `evaluate(fin)`:** FN-shaped synthetic fin (thin gross, high growth, hist
   multiple ~26x) → EV/EBITDA leg multiple floors at ~13x; software-shaped (high gross) → unchanged.
5. **Regression:** full suite green; re-validate FN (+82.6% → ~fair) and confirm KLAC/ANET/NBIS/IREN
   byte-unchanged and BWXT/ETN still SELL.

## Non-goals

- No change to the historical-multiple reconstruction (`ev_ebitda_history_ewma`), the compression
  path, the growth scenarios, weights, or any non-forward-tier path.
- No WDC base-contamination guard; no CF cyclical normalization (separate specs).

## Files touched

- `valuation/models.py` — add `MATURE_EBITDA_MULT` constant; add `gross_margin` param to
  `_ev_ebitda_ceiling` + the temper blend; thread it through `calc_ev_ebitda`.
- `valuation/engine.py` — source `fin["gross_margin"] = met.gross_margin` in `run()`.
- `backend/tests/` — new unit + integration + regression tests per above.

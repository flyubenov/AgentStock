---
name: wacc-mos-moat-margin-design
description: "DESIGN CHECKPOINT (not yet implemented) -- WACC-driven FV discount rate, ROIC-WACC-spread-driven moat-adjusted margin replacing flat MOS=0.90, and an incremental-ROIC-on-reinvested-capital Quality metric. Next step: live sweep to calibrate pivots, then TDD."
metadata:
  node_type: memory
  type: project
---

# Status: DESIGN ONLY -- nothing in this file has been implemented yet

Session context: user supplied a Buffett-style investment-philosophy article ("The
Illusion of the Cheap Asset") and asked for a comparison against Agent Stock's Quality
Score and Fair Value methodology. That comparison surfaced four candidate improvements
(numbered #1-#4 in conversation). User has since directed the shape of #1-#3 and
confirmed #4; this file is the checkpoint before running the calibration sweep, so work
can resume on a different machine.

## The article's core theses (for context, in case this file is read cold)
1. Growth is an input to intrinsic value (DCF), not a separate "style" opposed to value.
2. Margin of safety done right = (a) conservative assumptions baked INTO the model, and
   (b) quality/moat as the real shield against permanent capital loss -- NOT a flat
   percentage haircut on the final number (Buffett: paying up for a wonderful business
   beats a fair business at a wonderful price).
3. Circle of competence = honesty about what you can forecast (predictability), not
   product familiarity.

## What's already true of Agent Stock (baseline, verified in code this session)
- FV has NO separate growth/value split -- one number per ticker via `classify()` tiers
  (`valuation/classifier.py`), growth embedded directly in DCF/multiple projections. Good
  alignment with thesis 1.
- Conservatism-in-assumptions machinery already exists and is good: `GROWTH_CAP_BASE=0.20`,
  `GROWTH_CAP_CEIL=0.25`, `_fade_hold_years` (fades toward `TERMINAL_GROWTH=0.03`), and the
  whole distorted/inflated/non-operating/outpaces/understated earnings-guard family in
  `valuation/engine.py`.
- Gap found: `MOS = 0.90` (`valuation/models.py`) is a FLAT 10% haircut applied via
  `_apply_mos()` to every leg of every company, regardless of quality -- structurally the
  same mechanism as the "mechanical 30% discount" the article calls self-deception, just a
  smaller number.
- Gap found: `DISCOUNT_RATE = 0.10` (`valuation/models.py`) is a flat constant for the DCF/
  EV-EBITDA/DDM discounting, used for every company except `FINANCIAL_COE = 0.085`
  (FINANCIAL tier override, a separately-tuned constant -- see `opfi-rim-roe-cap-gap.md`,
  do not disturb). **`beta` is never referenced anywhere in `valuation/*.py`.**
- Meanwhile `screener/metrics.py`'s `wacc()` ALREADY computes a proper beta-adjusted cost
  of equity (`cost_equity = rf + beta * ERP`, with `BETA_CEILING` capping an inflated beta
  downward-only) for Quality's `roic_wacc_spread` (Section II) -- and that WACC never
  leaves the Quality module. Two pipelines computing/discarding the exact signal FV needs.
- Quality's Section II (`roic_ttm`, `roic_5y_avg`, `roic_wacc_spread`, `rote`) is a
  reasonable quantitative moat/durability proxy already -- the 5y-avg version specifically
  checks persistence, not a single good year.

## User's directed design (confirmed this session)

**#1 -- Discount rate driven by WACC/beta (replacing flat `DISCOUNT_RATE=0.10`).**
**#2/#3 -- Margin of safety driven by ROIC-WACC spread (replacing flat `MOS=0.90`), NOT
the same lever as #1** (discount rate compounds over the horizon and prices *market* risk
via beta; MOS is a one-time terminal multiplier and should instead price *fundamental/
business* risk via ROIC-WACC spread -- deliberately different signals so the two don't
double-count the same input). User leans toward Option B (spread + durability) but wants
an OR-style combination of "Option A: spot spread clears a HIGH bar" and "Option B: 5-year
durability spread clears a LOWER bar" -- whichever qualifies is enough for the smaller
discount.

**Refined to avoid a hard cliff** (lesson from the STRL EWMA work this session: a binary
monotonic-switch design had the biggest single-ticker effect but the least predictable
blast radius; a smooth ramp was safer and nearly as effective) -- two independent smooth
ramps, take the MORE FAVORABLE (max), not a binary AND/OR gate:

```
ramp_A = _ramp(roic_wacc_spread,            lo=0,  hi=15, at_lo=0.0, at_hi=1.0)  # spot, harder bar
ramp_B = _ramp(roic_5y_avg - current_wacc,  lo=0,  hi=5,  at_lo=0.0, at_hi=1.0)  # durability, easier bar
mos = MOS_FLOOR + max(ramp_A, ramp_B) * (MOS_CEIL - MOS_FLOOR)
# proposed: MOS_FLOOR=0.75, MOS_CEIL=0.98 (today's flat 0.90 sits near the middle)
```

Pivot choice (0/15 for spot, 0/5 for durability) anchors to Quality's OWN already-calibrated
`SPREAD_BANDS = [(10,10), (5,8), (0,5.5), (-5,2.5)]` (`screener/scoring.py`) -- the durability
ramp's `hi=5` matches Quality's own "very good" breakpoint; the spot ramp's `hi=15` sits
ABOVE Quality's own top bucket (10), reflecting that a single-year number needs to be more
extreme than a proven one to count alone. **These pivots are a starting proposal, not
final -- the live sweep (next step) is meant to test/adjust them against real data.**

**Known approximation, flagged deliberately, not silently:** there is no true 5-year WACC
series (would need historical risk-free rate + beta, not fetched) -- `ramp_B` uses
`roic_5y_avg` against the CURRENT wacc as a pragmatic stand-in for a durable spread. Worth
re-examining if the sweep shows this behaves oddly for names whose beta/rates moved a lot.

**Known, accepted interaction, not a bug to pre-emptively fix:** a high-beta AND
high-ROIC-spread name gets pulled two directions (higher discount rate from beta, smaller
MOS haircut from spread) -- a real tension (market prices it as risky, fundamentals say
durable), not something to artificially net out. Watch for it in the sweep, don't suppress it.

**Architecture decision (preserves the documented pipeline-independence property):** FV
must NOT call into Quality's live result (would break "each pipeline independently
runnable and failure-isolated" -- see `orchestrator/batch.py`'s per-pipeline gather).
Instead, `valuation/engine.py` imports and reuses the SAME `wacc()`/`roic()` functions
from `screener/metrics.py` (single source of truth, no duplicated math) and computes its
OWN WACC/spread from statement data it fetches itself -- same reuse shape as the R-R
statement-gap-guard fix this session (`StatementSeries` + `fetch_income_stmt`/
`fetch_balance_sheet` reused across pipelines, no runtime cross-pipeline dependency).

**Mechanical prerequisite:** `_ramp()` currently lives in `valuation/engine.py`;
relocate it to `valuation/models.py` (the lower layer both the discount-rate code and the
MOS code will sit in) so both can use it without a circular import. Pure relocation, no
behavior change -- update `engine.py` to import it from `models` afterward.

**Discount-rate specifics:** reuse `BETA_CEILING` (same constant Quality already applies,
downward-only cap) when computing WACC for FV. Add a floor so WACC can't collapse toward/
below `TERMINAL_GROWTH` (mirrors RIM's existing `g = min(TERMINAL_GROWTH, coe - 0.01)`
guard -- needed because DDM/RIM's Gordon-growth denominator is `(rate - g)` and must stay
positive). `FINANCIAL_COE=0.085` stays a hard override for the FINANCIAL tier's book-value
legs, untouched -- a separately-tuned, memory-documented constant.

## #4 -- Incremental ROIC on reinvested capital (Quality Section II, confirmed to build)

Data already fetched, no new source needed -- `inc.value("EBIT", i)` and
`bal.value("Invested Capital", i)` are available per-year in `compute_metrics`
(`screener/metrics.py`), same window `roic_5y_avg` already spans.

```
incremental_roic = (EBIT_latest*(1-tax) - EBIT_oldest*(1-tax)) / (IC_latest - IC_oldest)
```

Answers the See's Candies question directly: not "return on capital already deployed" but
"what does a NEW dollar of reinvested capital earn." Needed guard: exclude (-> `None`, not
a wild ratio) when `|IC_latest - IC_oldest|` is too small relative to `IC_latest` (a
capital-light compounder buying back stock instead of reinvesting would otherwise blow up
the ratio) -- mirrors the existing "exclude rather than divide-by-noise" pattern already
used elsewhere in this file. Slot into Section II alongside roic_ttm/roic_5y_avg/spread/
rote (same family: a return metric, not a capital-allocation-policy metric). Bands need
live calibration, same as everything else here.

## Next step (in progress / about to run when this file is written)

Live sweep across a representative basket -- wide-moat compounders (high spot AND durable
spread), "proven-durable-but-modest" names (lower spot, good 5y), high-beta/high-quality
names (to observe the accepted tension above), weak-ROIC laggards, and FINANCIAL-tier
names (to confirm `FINANCIAL_COE` truly stays untouched) -- to pin real numbers for:
`ramp_A`'s `0/15`, `ramp_B`'s `0/5`, `MOS_FLOOR/CEIL` (`0.75/0.98`), the WACC floor, and
the incremental-ROIC exclusion threshold and bands, BEFORE any TDD. Mirrors the STRL EWMA
sweep methodology (build `fin`/`ScreenerMetrics` once, vary just the parameter under test,
measure before/after live, no mocking).

## Once the sweep lands, the implementation order should be:
1. Relocate `_ramp` engine.py -> models.py (mechanical, test-covered already, do first).
2. WACC-driven discount rate (touches `calc_dcf`, `calc_ev_ebitda`'s horizon discounting,
   `calc_ddm`'s Gordon denominator) -- reuses `wacc()`/`roic()` from `screener.metrics`.
3. Moat-adjusted MOS ramp (touches `_apply_mos` call sites via a new signature carrying
   the spread inputs, or a module-level "current MOS" set once per `evaluate()` call --
   design TBD when implementing, since `_apply_mos` is currently a pure, argument-free
   helper called from ~7 places).
4. Incremental ROIC on reinvested capital (Quality Section II, independent of 1-3, can be
   done in parallel/either order).

Each of 2-4 needs: failing tests first (TDD), a full blast-radius sweep across the
existing 481+ test/canary universe (IREN, NBIS, KLAC recurring canaries; FINANCIAL-tier
canaries AXP/JPM/OPFI specifically for #2 given `opfi-rim-roe-cap-gap.md`), and a memory
write-up on landing, same discipline as every other fix this session.

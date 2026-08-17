---
name: wacc-mos-moat-margin-design
description: "DESIGN CHECKPOINT (not yet implemented) -- WACC-driven FV discount rate, ROIC-WACC-spread-driven moat-adjusted margin replacing flat MOS=0.90, and an incremental-ROIC-on-reinvested-capital Quality metric. Next step: live sweep to calibrate pivots, then TDD."
metadata: 
  node_type: memory
  type: project
  originSessionId: ab39a665-b1a3-474c-8aff-036288d4b0a8
  modified: 2026-08-17T14:02:08.535Z
---

# Status: SPEC WRITTEN + COMMITTED (2026-08-17) -- not yet implemented

## UPDATE 2026-08-17 -- brainstorm session: scope narrowed, spec committed, NEXT = writing-plans

Ran `superpowers:brainstorming` over the four candidate improvements. **Decisions this
session:**
- **Scope narrowed to the FV cluster only: #1 (discount rate) + #2/#3 (moat-adjusted MOS),
  as ONE combined session on this branch `wacc-mos-moat-margin-design`.** #4 (incremental
  ROIC) is DROPPED from this scope entirely -- deferred to a separate track/branch, not
  part of this work. (User first mis-clicked "#4 own branch", then explicitly said ignore
  #4 completely for now.)
- **Conceptual backbone approved: two ORTHOGONAL quality signals** -- discount rate keyed to
  MARKET risk (beta/WACC), MOS keyed to BUSINESS-DURABILITY risk (ROIC-WACC spread). Keeping
  both is complementary (not the article's "redundant stacked discount") *because* the
  signals often disagree (low-beta-no-moat utility vs high-beta-wide-moat compounder); the
  double-count only bites when they agree, and tight bounded bands keep that modest.
- **#1 = blend+bound (confirmed, not raw swap):** `used_rate = 0.5*0.10 + 0.5*company_WACC`
  clamped ~[7%,13%]. Blend weight + band width are sweep-calibrated starting proposals.
- **#2/#3 MOS = decided EMPIRICALLY, not pre-committed.** Build BOTH variants behind one
  seam -- (A) nudged MOS ~[0.85,0.95] tilted by ROIC-WACC spread, (B) drop MOS entirely and
  lean on the quality rate + existing caps/fades/guards -- then sweep and pick on which is
  more defensible for AVERAGE/MEDIOCRE-beta names. Key insight that made it empirical:
  dropping MOS is not a uniform +11% lift once #1 is live -- high-beta/low-quality names get
  the harsher rate offsetting the removed haircut (~wash), low-beta/high-quality names STACK
  (materially cheaper), and beta~1 mediocre names get the full +11% with no quality
  justification under B (Variant A's near-flat MOS still protects them). That average-name
  behavior is the crux the sweep resolves.
- **Robustness (approved):** missing/distorted signal (no beta, captive-finance-inflated
  WACC) -> BOTH levers fall back toward the neutral flat prior (10% / 0.90), never punitive.
  Fixes the Finding-3 sweep bug (missing beta -> worst-case floor for V/CRWV).
- **Architecture (approved):** FV recomputes its OWN WACC/spread by reusing `screener.metrics`
  as a library (NOT a cross-pipeline call to Quality's live output) -- preserves failure
  isolation; single-source math. PLUS expose the per-company rate + MOS used in the FV
  breakdown so the number stays auditable / reconcilable by `validating-agent-stock`.
- **Captive-finance (approved):** BOUND-ONLY for this work (tight bands cap Ford/GM's effect
  on both levers); do NOT re-derive `wacc()`'s debt weighting here -- logged as a separate
  known gap (it also touches Quality's calibration).

**Spec written + committed:** `docs/superpowers/specs/2026-08-17-fv-quality-discount-mos-design.md`
(commit `f62e10b`). User is reviewing it. **NEXT STEP: on user approval of the spec, invoke
`superpowers:writing-plans` to produce the implementation plan** (then TDD per §7; sweep
basket + the 4 things it must resolve are in spec §5, incl. GM which was untested in the
first sweep, and the OPFI-saturation caveat to flag prominently on landing).

The original design notes + the 2026-08-13 live-sweep findings below are still valid inputs
to the tech plan (Findings 1-4 in particular; Finding 5 / incremental-ROIC is now OUT of scope).

## UPDATE 2026-08-17 (later) -- ran the §5 sweep, TWO ROUNDS, 60 names / 8 categories. OPEN DECISION on DIVIDEND tier.

Broadened §5 in the spec (committed) to require: as many memory tickers as possible, >=2 per
classification, explicit three-way per-ticker comparison. Then ACTUALLY RAN it (scratchpad
`fv_quality_sweep.py` round-1, `fv_quality_sweep2.py` round-2; outputs `sweep_out.txt` /
`sweep2_out.txt`). Harness method: capture the fully-prepared `fin` from `engine.run` via an
`engine.evaluate` wrapper, then re-run the SAME `evaluate(fin)` under patched
`models.DISCOUNT_RATE`/`models.MOS`; round-2 also wraps `models.calc_ddm` to give ONLY the
perpetuity leg a higher floored rate (DDM guard). GOTCHA fixed: patching DISCOUNT_RATE breaks
engine's FINANCIAL `coe == DISCOUNT_RATE` sentinel -> pin `cost_of_equity=FINANCIAL_COE` onto
`fin` for FINANCIAL names before patching. Coverage: GROWTH 21, MEGA 6, LARGE 2, MID 7,
EARLY_GROWTH 6, DIVIDEND 7, FINANCIAL 9; PRE_PROFIT (MARA/RIOT) + ASTS structurally decline
(no FV). Caveat carried: MATURE_MULTIPLE_FACTOR stays import-bound to 0.10 (EV/EBITDA ceilings only).

**ROUND-1 (three-way: baseline vs A=qual-rate+qual-MOS vs B=qual-rate+no-MOS; blend 0.5, band
7-13%, MOS 0.85-0.95) -> TWO conclusions:**
- **MOS decision = Variant A (nudged MOS), SETTLED by evidence.** B (drop-MOS) over-lifts
  mediocre-beta / weak-spread names with no quality basis: CRM (+1.2 spread) reads +58% cheap
  under B; MBLY (-13.5 spread) lifted to -17 under B; CCL/CEG similar. A's 0.85 floor keeps a
  safety margin exactly there. High-quality names: A~=B (AAPL A-B only -3.4). The durability
  ramp also correctly rescued SNPS (spot spread -5.7 trough from Ansys, but 5y durable -> MOS 0.95).
- **BIG problem surfaced: the RATE lever, even bounded 7-13%, over-inflates low-beta / low-WACC
  DDM-heavy names.** F +122pp (base -31->+91), VZ +90, PG +48, PEP +36, MCD/ABBV/JNJ/KO ~+18-20.
  Cause: DDM Gordon `(rate-g)` denominator is hypersensitive at the low end; the 7% floor doesn't
  tame it. Ford = captive-finance 4% WACC floored to 7% and STILL doubles (GM is fine, -46->-46,
  because it isn't DDM-dominated). Working-as-designed parts: high-beta correctly harsher
  (NVDA -14->-29, AMD, MU, TEM, IREN); neutral fallback holds (V/CRWV no-beta, all lenders
  no-spread -> MOS 0.90); FINANCIAL rate-invariant (book legs on FINANCIAL_COE).

**ROUND-2 (RECALIBRATION user asked for, across ALL categories: gentler blend 0.3 + higher floor
8.5% + DDM guard = perpetuity leg floored 9% + nudged Variant-A MOS; shown as baseline vs one
recal combo):** tames the blowups -- F +122->+36, VZ +90->+29, PEP +36->+23; also softens the
high-beta side (NVDA -14.4->-7.7) and makes JNJ/KO a milder +11. **Everything now sits inside
~+/-12pp EXCEPT the DIVIDEND tier, which still moves +12 to +36pp** (F +36, VZ +29, PEP +23,
PG +18, NKE +15, MCD +14, ABBV +12). FINANCIAL fully rate-invariant (Delta 0 except OPFI +9.4,
the flagged saturation caveat). Read: PG/KO/JNJ/MCD moving toward fair is arguably CORRECT
(fixes the flat-10%-over-penalizes-blue-chips bias the BWXT memo flagged); Ford +36 is still a
captive-finance DISTORTION not genuine safety; VZ +29 (SELL->BUY flip) is the aggressive one.

**OPEN DECISION (next session) -- how to treat the DIVIDEND tier / captive-finance.** Presented
4 options, USER WANTED TO CLARIFY THE QUESTIONS FIRST (not yet answered): (A) accept the
blue-chip re-rating as intended + fix Ford/GM captive-finance WACC AT SOURCE in `wacc()`
(exclude non-operating finance-arm debt -- the bigger §6 change, touches Quality's shared
`wacc()`); (B) damp DIVIDEND further (DDM floor 9->9.5%, band floor 8.5->9%) -- simple but also
blunts the wanted PG/KO/JNJ correction; (C) accept round-2 as-is (calibration proposal, TDD +
final blast-radius pass still follow); (D) re-sweep more DIVIDEND-focused combos. **Everything
else about the design is settled** (Variant A MOS; blend 0.3 / floor 8.5 / DDM guard 9% as the
working rate calibration; neutral fallback; FINANCIAL untouched; recompute-not-call). NEXT after
this decision: writing-plans, then TDD. Note: I offered to clarify (why DIVIDEND moves so much;
what fixing Ford at source entails + its Quality blast radius; correct-re-rating vs distortion;
whether these calibration numbers are even the ones to lock) -- resume there.

Scratchpad temp scripts removed from `backend/` on save; reproducible from the params above.

---

# Status (original): DESIGN ONLY -- nothing in this file has been implemented yet

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

---

# SWEEP RESULTS (2026-08-13) -- ran once, found real problems, STILL NOT IMPLEMENTED

Basket: wide-moat durable (AAPL, MSFT, COST, V, MA), durable-modest (KO, PG, JNJ, MCD),
high-beta/high-quality (NVDA, PLTR, CRWV, MU), weak-ROIC laggards (WBD, F, CCL, GE),
FINANCIAL canaries (JPM, AXP, OPFI). Script: `/tmp/wacc_mos_sweep.py` (not committed --
temp, reproducible from this file). Method: built `fin`/`ScreenerInputs` once per ticker,
compared baseline `engine.evaluate()` (flat `DISCOUNT_RATE=0.10`, flat `MOS=0.90`) against
(a) WACC-only, (b) proposed-MOS-only, (c) both combined -- via direct, sequential
module-attribute reassignment of `models.DISCOUNT_RATE`/`models.MOS` (safe because this
sweep is NOT run under asyncio.gather concurrency, unlike the R-R sweep earlier this
session which needed to avoid `unittest.mock.patch` for exactly that reason).

## Finding 1 -- CRITICAL: raw WACC as an unbounded DCF discount rate is dangerous

**F (Ford) broke it: FV -31.3% -> +301.2%.** Cause: `wacc()`'s debt/equity blend uses
`info.get("totalDebt")` unconditionally. Ford's `totalDebt=$163.3B` vs `marketCap=$57.3B`
(debt is 2.8x market cap) -- almost entirely Ford Credit's captive-finance auto-loan book,
not operating leverage. That drags the blended WACC to ~4%, and halving a 10-year discount
rate compounds into an enormous PV inflation. **The same raw fraction is safe when it
feeds a saturating `score_high()` (Quality's current use) and dangerous when it multiplies
an unbounded 10-year discount factor (FV's proposed use) -- same signal, very different
risk exposure depending on where it's plugged in.** GM likely shares this shape (also
carries a captive-finance arm) -- not yet tested, should be in the next sweep.

## Finding 2 -- even "normal" low-beta blue chips show swings far bigger than expected

| Ticker | beta-implied WACC | Baseline pct | WACC-only pct |
|---|---|---|---|
| KO | 6.1% | -41.1% | -0.9% |
| JNJ | 5.5% | -54.0% | +0.1% |
| PG | 6.1% | -44.8% | +25.6% |
| MCD | 5.8% | -20.3% | +25.7% |
| NVDA (high beta, for contrast) | 14.7% | -14.6% | -44.8% (correct direction) |

A full swap to raw CAPM WACC would re-rate almost the entire low-beta blue-chip universe
from "overvalued" to "roughly fair or cheap" -- a MUCH bigger, more sweeping recalibration
than intended (not STRL-sized; potentially reshapes MEGA_CAP/LARGE_CAP broadly).
High-beta names (NVDA) correctly move the OTHER way (more overvalued) -- that part of the
mechanism works as designed.

**Recommendation (not yet implemented, needs a decision):** blend rather than replace --
`used_rate = 0.5*DISCOUNT_RATE + 0.5*wacc_capped`, PLUS a tight floor/ceiling around
today's 10% (proposed 7%-13%, not the raw CAPM range) so beta nudges the rate rather than
overriding it. This also neutralizes Ford-style blowups without needing to fix `wacc()`'s
debt-weighting itself (a separate, real problem -- captive-finance debt inflating the debt
weight -- that a tight band makes moot for THIS purpose, though it may still distort
Quality's own ROIC-WACC spread for Ford-like names, out of scope here). Open question for
next session: blend+bound (safer, smaller blast radius) vs. fix `wacc()`'s debt treatment
directly (exclude non-operating captive-finance debt, more "correct" but a bigger, separate
change touching Quality's existing calibration too).

## Finding 3 -- bug (not a design choice): missing data defaults to the WORST MOS

V and CRWV both had `beta=None` -> `wacc()` returns `None` -> spread inputs are `None` ->
sweep's ramp code treated missing spread as the ramp's floor (`0.0`) -> **MOS_FLOOR (0.75,
the harshest haircut) applied to V, a genuine wide-moat compounder, purely because of a
data gap, not weak quality.** Must fix: fall back to today's flat `0.90` (neutral) when
spread inputs are unavailable, mirroring the "don't punish for missing data" principle
already used elsewhere (R-R's coverage floor, the analyst-weight floor). This is a
straightforward fix, not a design fork -- do it regardless of the WACC blend/bound decision.

## Finding 4 -- OPFI's moat-margin swing reintroduces a known, already-flagged tension

OPFI spread is enormous (85% spot, 68.6% durability) -> both ramps saturate -> FV
**+68.9% -> +84.0%** (more undervalued). But `opfi-rim-roe-cap-gap.md` already documents
OPFI's real ROE as exceptional AND facing an unmodelable regulatory tail (state APR caps)
the quant model structurally can't see. A moat-margin mechanism that makes OPFI look even
cheaper compounds a name already flagged as having a real, non-fundamental risk. Not
necessarily wrong (Quality's Section II score is a legitimate signal) but worth being
deliberate about -- flag prominently in the eventual PR/memory, don't let it pass silently.
FINANCIAL-tier confirmed correctly UNAFFECTED by the WACC/discount-rate change (JPM/AXP/
OPFI's `wacc_variant_pct == base_pct` -- `FINANCIAL_COE` override holds), but IS affected
by the MOS change (JPM -14.7%->-28.9%, AXP -46.1%->-55.1%) -- correct/expected, since MOS
applies to P/B/RIM legs too and was never meant to be FINANCIAL-exempt (only the discount
RATE override is FINANCIAL-specific).

## Finding 5 -- #4 Incremental ROIC validates well once a script bug was fixed

Original sweep script used a strict `n-1` "oldest year" index, which is `None` for most
tickers (statement history commonly has a gap in the oldest fetched year) and silently
returned `None` for names that should have resolved (AAPL, MSFT, etc). Fixed by walking
from the back to the last **available** (non-`None`) year for both EBIT and Invested
Capital independently (mirrors `latest_statement_ebitda`'s existing "walk to first
non-None" pattern, just from the other end) -- **this fix belongs in the real
implementation, not just the sweep script.**

Re-run results:

| Bucket | Ticker | Incremental ROIC | Read |
|---|---|---|---|
| Wide-moat | MSFT 27.3%, COST 29.0%, MA 89.1% | capital-light, high marginal returns -- correct |
| Durable | KO 29.0%, PG 24.6%, JNJ 87.9%, MCD 32.7% | all strong, sensible |
| High-beta/quality | NVDA 87.8%, PLTR 32.2%, **CRWV 0.2%** | CRWV correctly reads near-zero -- heavy build-out capex not yet converting to NOPAT, exactly the nuance the metric should catch |
| Laggards | WBD -35.4%, F -35.4%, GE -36.9%, **CCL -318.5%** | negative = destroying value on the margin (intended); CCL magnitude is a small-EBIT-base noise artifact |
| Financials | JPM/AXP `None` (correct -- EBIT/Invested Capital isn't meaningful for lenders), **OPFI 426.3%** (noise, should ALSO be `None`) |

**Two fixes needed before shipping, both cheap:**
1. **Exclude FINANCIAL-profile names outright.** This closes an ALREADY-DOCUMENTED latent
   gap from `opfi-rim-roe-cap-gap.md`: *"ROIC not excluded from FINANCIALS Section II
   though structurally distorted for lenders"* -- a two-for-one fix.
2. **Add a magnitude guard on the EBIT base** (not just relative ΔIC size) to stop
   CCL/OPFI-style small-absolute-base blowups, then convert to a banded `score_high()`-style
   score like its Section II neighbors rather than exposing a raw, unbounded percentage.

## Where this leaves things -- decisions needed before implementation resumes

1. **WACC discount rate:** blend+bound (my recommendation, safer/smaller blast radius) vs.
   fix `wacc()`'s debt-weighting for captive-finance names (more "correct," bigger,
   separate change, also touches Quality's existing calibration) -- undecided, needs a
   session to pick and then re-sweep the chosen approach specifically against F, GM (untested),
   and the blue-chip set above before TDD.
2. **MOS missing-data fallback:** straightforward bug fix (-> 0.90 neutral), no decision
   needed, just do it when implementing.
3. **OPFI-style saturation tension:** no action proposed, just flag prominently when this
   ships so it's a visible, acknowledged tradeoff rather than a silent side effect.
4. **Incremental ROIC:** fix the "last-available-year" walk (not just `n-1`), exclude
   FINANCIAL profile, add an EBIT-magnitude guard, then band it like its neighbors. This
   piece is otherwise ready for TDD independent of the WACC/MOS decisions above (items 1-3
   don't block it).


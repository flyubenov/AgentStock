# FV Quality Cluster — Quality-Adjusted Discount Rate & Margin of Safety

**Date:** 2026-08-17
**Branch:** `wacc-mos-moat-margin-design`
**Status:** Design approved — ready for tech planning (writing-plans)
**Scope:** Fair Value pipeline only (`valuation/*`), reusing `screener.metrics` as a library. Quality Score pipeline output is unchanged. Item #4 (incremental ROIC) is explicitly **out of scope** for this work.

---

## 1. Motivation

A Buffett-style investment article ("The Illusion of the Cheap Asset") was compared against Agent Stock's Fair Value and Quality methodology. The comparison surfaced that Agent Stock applies **two flat, quality-blind discounts** to every company:

- `DISCOUNT_RATE = 0.10` — a flat cost of capital used to discount the DCF / EV-EBITDA / DDM legs, identical for a 9.5/10 wide-moat compounder and a 3/10 leveraged cyclical. `beta` is never referenced anywhere in the valuation pipeline.
- `MOS = 0.90` — a flat 10% haircut multiplied onto every leg of every company, structurally the same "mechanical discount" the article criticizes, just a smaller number than the strawman 30%.

Meanwhile, the Quality pipeline (`screener/metrics.py`) **already computes** a proper beta-adjusted, per-company WACC (`wacc()`) and ROIC−WACC spread — and then discards them before they can reach the valuation engine. Two pipelines compute exactly the signal FV needs and throw it away.

The article's core thesis: **quality is the real margin of safety** — a durable, high-return business earns a gentler discount and needs less of a mechanical haircut, because the safety comes from the business's durability, not from a blanket percentage cut. This work operationalizes that thesis while deliberately avoiding the article's own warning against *stacking redundant mechanical discounts*.

## 2. Goals / Non-goals

**Goals**
- Make the discount rate quality-sensitive, keyed to **market risk** (beta / WACC).
- Make (or remove) the margin-of-safety haircut, keyed to **business durability** (ROIC−WACC spread) — final form decided empirically (§4).
- Keep the effect of both levers **bounded** — no single distorted input or systematic sector bias may swing the model far more than intended.
- Preserve the documented pipeline **failure-isolation** property.
- Keep the resulting FV **auditable** — expose the per-company inputs actually used.

**Non-goals**
- No change to the Quality Score / Section II. Item #4 (incremental ROIC on reinvested capital) is deferred to a separate track and is not part of this spec.
- No re-derivation of `wacc()`'s internal debt weighting (see §6, Known Gaps).
- No change to the FINANCIAL tier's separately-tuned cost of equity.

## 3. Conceptual backbone — two orthogonal quality signals

The two levers are deliberately keyed to **different, orthogonal** signals so that keeping both is complementary rather than redundant:

| Lever | Flat prior today | Nudged within (starting proposal) | Driven by | Captures |
|---|---|---|---|---|
| Discount rate | 10% | ~7%–13% | beta / WACC | **Market** risk — how the market prices volatility |
| Margin of safety | 0.90 (10% haircut) | ~0.85–0.95 (15%–5% haircut) | ROIC−WACC spread | **Business durability** — how durable the fundamentals actually are |

These signals frequently **disagree** — a boring utility has low beta but no moat; a volatile wide-moat compounder has high beta but huge durability. When they disagree, keeping both levers is the whole point: the model can express "the market fears this, but the fundamentals are durable," which is precisely the Buffett insight. The feared "double-count" only bites when beta and spread *agree* (low-beta + wide-moat), and the tight bounded bands keep that combined lift modest. Both levers keep their flat prior and let the quality factor **nudge** — not swing — around it.

## 4. Design

### 4.1 Quality-adjusted discount rate (#1)

- Replace the flat 10% with a **bounded nudge**: blend the flat prior partway toward the company's own beta-driven WACC, then clamp to a tight band around 10%. Starting proposal: `used_rate = 0.5 × 0.10 + 0.5 × company_WACC`, clamped to ~[7%, 13%] (blend weight and band width calibrated in the sweep, §5).
- **Rationale for bound-and-blend, not raw swap:** the live sweep proved a raw per-company WACC is dangerous — Ford's captive-finance debt drove its WACC to ~4%, inflating its FV to +301%, and even calm low-beta blue chips (KO/JNJ/PG/MCD) swung 40–80 percentage points. Blending toward the flat prior and clamping keeps the *direction* of the idea (lower-risk → gentler discount, higher-risk → harsher) without letting one distorted input or a systematically low-beta sector re-rate the whole model.
- The FINANCIAL tier's cost of equity override remains a hard, untouched override — only its book-value legs, at their separately-tuned rate.

### 4.2 Margin of safety (#2/#3) — built as a switchable choice, decided by sweep

Two variants are implemented behind the **same seam**, and the choice between them is made **empirically**, not pre-committed:

- **Variant A — nudged MOS:** the flat 0.90 is tilted within a tight band (~0.85–0.95) by the ROIC−WACC spread. Higher durability → smaller haircut. Average / mediocre names keep a residual safety margin near 0.90.
- **Variant B — no MOS:** drop the haircut entirely; the quality-adjusted discount rate plus the existing conservative-assumption machinery (growth caps, growth fades, and the distorted/inflated/non-operating/outpaces/understated earnings guards) carry all conservatism.

**Why this is an empirical decision, not a philosophical one:** removing the flat 0.90 in isolation lifts every FV by ~11%, but combined with the quality rate the net effect varies by company — for high-beta / low-quality names the harsher rate offsets the removed haircut (roughly a wash), while for low-beta / high-quality names the gentler rate *stacks* with the removed haircut (materially cheaper). The genuine open question is what happens to **average, beta≈1, mediocre-quality** names: under Variant B their rate barely moves, so they receive the full +11% lift with no quality justification; under Variant A the near-flat MOS still protects them. The sweep decides which behavior is more defensible.

**Decision criterion:** across the canon basket, which variant produces more defensible fair values for average / mediocre-beta names, without introducing unjustified BUY signals or losing warranted conservatism.

### 4.3 Robustness — missing or distorted signals fall back to neutral

- When the quality signal is unavailable (no beta → WACC is `None`) or structurally distorted, **both levers fall back toward the neutral flat prior** (10% rate, 0.90 MOS) — never to a punitive extreme. This fixes the sweep bug where a missing beta defaulted genuine wide-moat names (V, CRWV) to the worst-case haircut purely from a data gap.
- Captive-finance WACC distortion (Ford/GM) now touches *both* levers (the rate directly, and the MOS via the spread), but the tight bounded bands cap its effect on each. This is handled by bounding, not by re-deriving `wacc()` (see §6).

### 4.4 Architecture

- FV computes its **own** WACC and ROIC−WACC spread from statement data it already fetches, by **reusing the `screener.metrics` functions as a shared library**. It does **not** call the Quality pipeline's live result. This preserves the documented failure-isolation property (each pipeline independently runnable and failure-isolated in the orchestrator's per-pipeline gather) while keeping the WACC/ROIC math single-source (no duplicated formulas).
- **Transparency:** the per-company discount rate and MOS actually used are surfaced in the FV breakdown, so the number stays auditable and the `validating-agent-stock` skill can reconcile it. FV becomes quality-dependent by design; exposing the inputs keeps it interpretable.
- The threading mechanism (how per-company rate/MOS reach the leg calculators) is an implementation detail deferred to tech planning; the constraint is that it must be **concurrency-safe** (batch evaluates tickers in a thread pool — no shared mutable module state) and should follow the existing precedent for threading a per-company rate through the pipeline.

## 5. Calibration & sweep plan

All band widths, the blend weight, the MOS band, and the pivot points are **starting proposals**, not final. Before implementation is finalized, a live sweep across a representative basket pins the real numbers, mirroring the STRL-EWMA and scenario-growth-band sweep discipline (build inputs once per ticker, vary only the parameter under test, measure before/after live, no mocking).

**Basket must include:**
- Wide-moat durable compounders (high spot *and* durable spread): AAPL, MSFT, COST, V, MA.
- Durable-but-modest names (lower spot, good 5y): KO, PG, JNJ, MCD.
- High-beta / high-quality (to observe the accepted orthogonal tension): NVDA, PLTR, CRWV, MU.
- Weak-ROIC laggards: WBD, GE.
- Captive-finance distortion cases (the #1 blowup class): **F and GM specifically** — GM was untested in the first sweep and must be included.
- FINANCIAL canaries (confirm the COE override stays untouched by the rate change and behaves as intended under the MOS change): JPM, AXP, OPFI.

**The sweep must resolve, before final calibration:**
1. Blend weight and band width for the discount rate (proposal: 0.5 blend, ~[7%, 13%]).
2. MOS band width for Variant A (proposal: ~[0.85, 0.95]) **and** the Variant A vs Variant B decision (§4.2), judged on the average/mediocre-name evidence.
3. That the neutral-fallback robustness rule (§4.3) fires for missing-beta names.
4. That F/GM are bounded (no +301%-style blowup) under the chosen band.

**OPFI note to flag prominently when this ships:** OPFI's ROIC−WACC spread saturates, so a moat-adjusted MOS makes it look even cheaper — in tension with the already-documented regulatory-tail-risk caveat (`opfi-rim-roe-cap-gap.md`). Not necessarily wrong, but must be an acknowledged, visible tradeoff, not a silent side effect.

## 6. Known gaps / out of scope

- **`wacc()` captive-finance debt weighting is not fixed here.** `wacc()` blends in `totalDebt` unconditionally, which is distorted for names with a captive-finance arm (Ford/GM). This work *bounds* the impact rather than fixing the root cause, because a real fix also touches the Quality pipeline's existing ROIC−WACC-spread calibration — a larger, separate change. Logged as a standalone known gap.
- **No true 5-year WACC series.** Any durability signal uses `roic_5y_avg` against the *current* WACC as a pragmatic stand-in; there is no historical risk-free-rate/beta series to build a true 5y spread. Re-examine only if the sweep shows odd behavior for names whose beta/rates moved a lot.
- **Item #4 (incremental ROIC on reinvested capital)** is deferred to a separate track/branch and is not part of this spec.

## 7. Testing & landing discipline

- TDD: failing tests first for the rate blend, the neutral fallback, and whichever MOS variant is chosen.
- Full blast-radius sweep across the existing 481+ test/canon universe; recurring canaries IREN, NBIS, KLAC; FINANCIAL-tier canaries JPM/AXP/OPFI specifically given the MOS lever now touches book-value legs.
- Inline Opus code review (not the paid ultra review — see `no-paid-features-without-approval.md`).
- Memory write-up on landing.

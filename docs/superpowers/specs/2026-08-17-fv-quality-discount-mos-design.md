# FV Quality Cluster — Quality-Adjusted Discount Rate & Margin of Safety

**Date:** 2026-08-17 (calibration closed 2026-08-21)
**Branch:** `wacc-mos-moat-margin-design`
**Status:** **Design fully settled — all calibration decisions closed (2026-08-21). Ready for tech planning (writing-plans).**
**Scope:** Fair Value pipeline (`valuation/*`), reusing `screener.metrics` as a library, **plus one source-level fix inside `screener.metrics.wacc()`** (the Option A captive-finance correction, §4.5) that is shared by the Quality pipeline. The Quality Score's *structure* is unchanged; the only Quality-visible effect is the corrected WACC feeding `roic_wacc_spread` (blast radius measured near-nil — §5). Item #4 (incremental ROIC) is explicitly **out of scope**.

**Settled decisions (2026-08-21), superseding the "decided by sweep" language below:**
- Discount rate: `clamp(0.7×0.10 + 0.3×company_WACC, 0.085, 0.13)`; DDM perpetuity leg floored separately at 9%. **No beta floor** (VZ path (i) — low-beta blue chips legitimately earn a low hurdle).
- MOS: **Variant A** (nudged 0.85–0.95 on ROIC−WACC durability). Variant B (drop-MOS) rejected.
- **Option A** captive-finance WACC fix adopted (§4.5).

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
- No change to the Quality Score's *scoring structure* / Section II bands. Item #4 (incremental ROIC on reinvested capital) is deferred to a separate track and is not part of this spec. (The Option A `wacc()` fix does change the WACC that Quality's `roic_wacc_spread` sees — an intended correction with a near-nil measured blast radius, §5 — not a scoring-logic change.)
- No broader re-derivation of `wacc()` beyond the targeted captive-finance correction in §4.5.
- No change to the FINANCIAL tier's separately-tuned cost of equity (and the §4.5 fix explicitly excludes financials).

## 3. Conceptual backbone — two orthogonal quality signals

The two levers are deliberately keyed to **different, orthogonal** signals so that keeping both is complementary rather than redundant:

| Lever | Flat prior today | Nudged within (starting proposal) | Driven by | Captures |
|---|---|---|---|---|
| Discount rate | 10% | ~7%–13% | beta / WACC | **Market** risk — how the market prices volatility |
| Margin of safety | 0.90 (10% haircut) | ~0.85–0.95 (15%–5% haircut) | ROIC−WACC spread | **Business durability** — how durable the fundamentals actually are |

These signals frequently **disagree** — a boring utility has low beta but no moat; a volatile wide-moat compounder has high beta but huge durability. When they disagree, keeping both levers is the whole point: the model can express "the market fears this, but the fundamentals are durable," which is precisely the Buffett insight. The feared "double-count" only bites when beta and spread *agree* (low-beta + wide-moat), and the tight bounded bands keep that combined lift modest. Both levers keep their flat prior and let the quality factor **nudge** — not swing — around it.

## 4. Design

### 4.1 Quality-adjusted discount rate (#1) — SETTLED

- Replace the flat 10% with a **bounded nudge**: blend the flat prior partway toward the company's own beta-driven WACC, then clamp to a tight band. **Settled form:** `used_rate = clamp(0.7 × 0.10 + 0.3 × company_WACC, 0.085, 0.13)`. The gentler 0.3 blend weight and 8.5% floor (vs the original 0.5 / 7% proposal) were chosen because round-1's aggressive settings over-inflated low-WACC DDM-heavy names (F +122pp, VZ +90pp); round-2 tamed these to a contained band.
- **DDM guard:** the Gordon perpetuity leg (`calc_ddm`) uses a separate, higher floor of **9%** on its discount rate, because `(rate − g)` in the denominator is hypersensitive at low rates. The DCF/EV legs keep the fuller rate benefit.
- **No beta floor (VZ path (i), settled):** ultra-low-beta blue chips (VZ β=0.23 → ~4.8% cost of equity) are *accepted* — they legitimately earn a low hurdle, and the 8.5% band floor + 9% DDM floor already cap the benefit. VZ moving toward BUY is the model correctly saying it is cheap on these fundamentals, not a bug.
- **Rationale for bound-and-blend, not raw swap:** the live sweep proved a raw per-company WACC is dangerous — Ford's captive-finance debt drove its WACC to ~4%, inflating its FV, and even calm low-beta blue chips (KO/JNJ/PG/MCD) swung 40–80 percentage points. Blending toward the flat prior and clamping keeps the *direction* of the idea without letting one distorted input or a systematically low-beta sector re-rate the whole model.
- The FINANCIAL tier's cost of equity override remains a hard, untouched override — its book-value legs use `FINANCIAL_COE`, making the tier rate-invariant to this change (confirmed in the sweep: all financials Δ0).

### 4.2 Margin of safety (#2/#3) — SETTLED: Variant A (nudged MOS)

**Settled form:** `used_mos = 0.85 + ramp × 0.10`, where `ramp = clamp(max(spread_pp/15, (roic5_pct − wacc_pct)/5), 0, 1)` — i.e. the flat 0.90 is nudged within [0.85, 0.95] by business durability (the ROIC−WACC spot spread, or the 5-year-ROIC-vs-current-WACC durability ramp, whichever is stronger). Higher durability → smaller haircut. When both signals are missing → neutral 0.90 (§4.3).

**Why Variant A over Variant B (drop-MOS), decided empirically:** removing the flat 0.90 in isolation lifts every FV by ~11%, but combined with the quality rate the net varies — for high-beta / low-quality names the harsher rate offsets the removed haircut (a wash), while for low-beta / high-quality names the gentler rate *stacks* (materially cheaper). The sweep showed **drop-MOS over-lifts average / mediocre-beta names with no quality basis** (e.g. CRM +58% on a thin spread, MBLY on a negative spread), whose rate barely moves so they'd get the full +11% unjustified. Variant A's near-flat MOS protects exactly these names while the durability ramp still correctly rewards the strong ones (it rescued SNPS). Variant B is **rejected**.

### 4.3 Robustness — missing or distorted signals fall back to neutral

- When the quality signal is unavailable (no beta → WACC is `None`) or structurally distorted, **both levers fall back toward the neutral flat prior** (10% rate, 0.90 MOS) — never to a punitive extreme. This fixes the sweep bug where a missing beta defaulted genuine wide-moat names (V, CRWV) to the worst-case haircut purely from a data gap.
- Captive-finance WACC distortion (Ford/GM) is fixed **at the source** in `wacc()` (§4.5), so it no longer distorts either lever. The bounded bands remain the second line of defence for any residual or unforeseen distortion.

### 4.4 Option A — captive-finance WACC fix at source (SETTLED)

The distortion: yfinance's `info['totalDebt']` lumps a captive-finance arm's match-funded lending debt (Ford Credit, GM Financial) in with industrial leverage. For Ford this is ~$163B of debt at a **0.5% implied after-tax cost** (the finance arm's interest is booked against finance *revenue*, not the "Interest Expense" line, so `interest/totalDebt` collapses) against ~$57B equity — dragging WACC to ~4% and, unfixed, inflating Ford's FV by +36pp.

**Detection is classifier-free — it keys on the distortion *signature*, not the industry string.** This is deliberate: TSLA is also classified "Auto Manufacturers" yet has a 0.01 debt-weight and a healthy 13.7% WACC, so an industry hardcode would misfire (and miss any non-auto captive lender). Inside `wacc()`, **for non-financials only** (`sector != "Financial Services"`):

1. **Cost-of-debt floor:** `cost_debt = max(cost_debt, risk_free × (1 − tax))` — no large borrower actually funds at 0.5% after tax; this rejects the finance-arm artifact.
2. **Debt-weight cap:** `w_debt = min(debt/(debt+equity), 0.50)` — match-funded finance debt must not dominate the equity hurdle. `wacc = (1 − w_debt) × cost_equity + w_debt × cost_debt`.

Financials are excluded because they are legitimately debt-funded and the FV tier already routes them through `FINANCIAL_COE`; excluding them also keeps their Quality `roic_wacc_spread` untouched.

This is a **true source fix**: it corrects the shared `wacc()`, so both the new FV discount rate *and* the Quality pipeline's `roic_wacc_spread` see an honest industrial WACC. The sweep (§5) confirms the fix is surgical — Ford's WACC 4.1%→8.6% pulls its FV blowup back (recal +4.7 → −24.8, Δ−29.5pp), the blue-chip re-rating (PG/KO/JNJ/MCD/ABBV) is preserved (≤0.4pp), and the **Quality blast radius is near-nil** (only GM −0.10 across all 60 names).

### 4.5 Architecture

- FV computes its **own** WACC and ROIC−WACC spread from statement data it already fetches, by **reusing the `screener.metrics` functions as a shared library**. It does **not** call the Quality pipeline's live result. This preserves the documented failure-isolation property (each pipeline independently runnable and failure-isolated in the orchestrator's per-pipeline gather) while keeping the WACC/ROIC math single-source (no duplicated formulas).
- **Transparency:** the per-company discount rate and MOS actually used are surfaced in the FV breakdown, so the number stays auditable and the `validating-agent-stock` skill can reconcile it. FV becomes quality-dependent by design; exposing the inputs keeps it interpretable.
- The threading mechanism (how per-company rate/MOS reach the leg calculators) is an implementation detail deferred to tech planning; the constraint is that it must be **concurrency-safe** (batch evaluates tickers in a thread pool — no shared mutable module state) and should follow the existing precedent for threading a per-company rate through the pipeline.

## 5. Calibration & sweep — COMPLETE (2026-08-21)

**Outcome (all resolved — see §4 for the settled forms):** rate = `clamp(0.7×0.10 + 0.3×WACC, 0.085, 0.13)` + 9% DDM-perpetuity floor; MOS = Variant A `0.85 + ramp×0.10`; Option A captive-finance fix adopted; no beta floor (VZ accepted). Headline numbers: Ford's +36pp DIVIDEND blowup fixed to +6.7 vs today (WACC 4.1→8.6%), blue-chip re-rating (PG/KO/JNJ/MCD/ABBV) preserved, Quality blast radius near-nil (only GM −0.10 across 60 names), all financials rate-invariant, neutral fallback held (V/CRWV/lenders). Repro scripts in the session scratchpad: `fv_quality_sweep.py` (three-way), `fv_quality_sweep2.py` (round-2 recal), `captive_probe.py` + `optionA_sweep.py` (Option A). The plan that was executed is retained below for provenance.

All band widths, the blend weight, the MOS band, and the pivot points were **starting proposals**; a live sweep across a representative basket pinned the real numbers, mirroring the STRL-EWMA and scenario-growth-band sweep discipline (build inputs once per ticker, vary only the parameter under test, measure before/after live, no mocking).

**Coverage (breadth requirement):** the sweep runs across **as many of the memory canary tickers as possible — ideally every ticker referenced across `.claude/memory/`** — and MUST cover **at least two tickers per classification category** produced by `classify()` (GROWTH, MEGA_CAP, LARGE_CAP, MID_CAP, EARLY_GROWTH, DIVIDEND, FINANCIAL, CYCLICAL, ASSET_HEAVY, and the PRE_PROFIT decline path), so no tier's behavior is inferred from a single name. The named buckets below are the minimum must-includes on top of that breadth.

**Three-way comparison (the headline output):** for every ticker, report **three columns side by side** so the A-vs-B choice is unambiguous — (0) baseline (flat 10% / flat 0.90), (1) **quality-rate + quality-MOS** (Variant A: blend+bound rate + ROIC−WACC-spread MOS), (2) **quality-rate + no-MOS** (Variant B: blend+bound rate + MOS dropped). The report must make the **difference between columns (1) and (2)** clearly visible per ticker and per classification, with particular attention to average / mediocre-beta names where the two variants diverge most.

**Basket must include (minimum, on top of the per-category breadth above):**
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

- ~~`wacc()` captive-finance debt weighting is not fixed here.~~ **RESOLVED (2026-08-21):** now fixed at source via Option A (§4.4). The measured Quality blast radius of touching the shared `wacc()` turned out to be near-nil (only GM −0.10 across 60 names), so the "larger, separate change" concern that originally deferred this did not materialize.
- **No true 5-year WACC series.** Any durability signal uses `roic_5y_avg` against the *current* WACC as a pragmatic stand-in; there is no historical risk-free-rate/beta series to build a true 5y spread. Re-examine only if the sweep shows odd behavior for names whose beta/rates moved a lot.
- **Item #4 (incremental ROIC on reinvested capital)** is deferred to a separate track/branch and is not part of this spec.

## 7. Testing & landing discipline

- TDD: failing tests first for the rate blend (0.7/0.3, clamp 8.5–13%), the 9% DDM-perpetuity floor, the neutral fallback (missing beta → 10%/0.90), Variant A MOS (0.85–0.95 durability ramp), and the Option A `wacc()` fix (cost-of-debt floor + 0.50 debt-weight cap, non-financials only; Ford/GM WACC lifts, TSLA/financials untouched).
- Full blast-radius sweep across the existing 481+ test/canon universe; recurring canaries IREN, NBIS, KLAC; FINANCIAL-tier canaries JPM/AXP/OPFI specifically given the MOS lever now touches book-value legs. Assert the Quality pipeline stays within the measured blast radius (only GM's score moves) so the shared-`wacc()` change is caught if it regresses.
- Inline Opus code review (not the paid ultra review — see `no-paid-features-without-approval.md`).
- Memory write-up on landing.

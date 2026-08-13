---
name: opfi-rim-roe-cap-gap
description: OPFI FV/Quality validated as SOUND (left as-is); logs the RIM-lacks-ROE-cap asymmetry as a known gap + a TODO to brainstorm a proper ROE-fade for RIM
metadata: 
  node_type: memory
  type: project
  originSessionId: b5a02239-c606-41f1-85c3-1d321ae001c2
  modified: 2026-08-13T00:00:00.000Z
---

**UPDATE 2026-08-13 — FIXED (flat mirror cap, no brainstorm; user explicitly chose this
over the fade design below).** Re-validating OPFI months later found the gap had WIDENED,
not settled: price fell $9.24→$6.86 while trailing EPS kept compounding ($2.03→$3.01), so
RIM's uncapped `eps/bvps` rose from ~71% to **~105%**, pushing composite FV from
$12.10/+31% to **$14.73/+114.77%** off the SAME uncapped-ROE mechanism logged below.
User asked to close it with the plain mirror (not the fade) and confirm blast radius stays
FINANCIAL-only. Implemented exactly as this file already speced: `calc_rim` (models.py)
now caps `roe = min(eps/bvps, ROE_PB_CAP_MULT * coe)` before running the flat 10-year PV,
same constant/rationale as `calc_pb`'s existing guard, no new knob.

**Result:** OPFI RIM leg $21.80→$5.96, composite **$14.73→$7.605 (+114.77%→+10.86%)** —
near-fair now. Quality 9.7 untouched (FV-only change, no shared code).

**Blast radius, live-verified via `valuation.engine.run`/`evaluate`:** structurally bounded
to the FINANCIAL tier by construction — RIM's weight is 0 everywhere else, and
`engine.evaluate`'s dispatch loop (`if weight <= 0: continue`) never even calls `calc_rim`
off that tier, so no other stock_type can be touched regardless of what the function
returns. Within FINANCIAL, only names whose `eps/bvps` exceeds `3.0*coe` are affected:
swept JPM (17.7%), SYF (21.1%), COF (11.0%), BAC (11.2%), MS (18.5%), GS (17.7%) — all
below the 25.5% cap (at `FINANCIAL_COE=0.085`), byte-identical. **AXP is the one other name
that moves** — exactly the canary this file predicted below (~33% raw ROE): RIM leg
$162.57 (uncapped) → $127.51 (capped), a real but "modest haircut" (composite stays SELL,
−46.3% either way, P/B already applied an equivalent cap to AXP before this fix). Two names
total move (OPFI, AXP); everything else in the swept basket (V, AAPL, NVDA, PLTR, KLAC,
NBIS, IREN — non-FINANCIAL, `rim_leg=None`, structurally inert) unchanged.

**Tests:** `test_models.py` (3 new: normal-ROE match to manual PV, OPFI-shaped capped case,
missing-input null) + `test_engine.py` (1 new: bank-fixture distorted-ROE RIM guard,
mirroring the existing P/B guard test). 485 backend tests pass (was 481).

**The fade idea below is NOT implemented** — the flat mirror was judged sufficient once the
user confirmed a bounded blast radius was the priority over precision; a proper ROE-fade
for RIM remains a valid future enhancement if a name's real, sustainably-high ROE needs a
less blunt treatment than a hard clip, but is no longer an open gap blocking anything.

---

Validated OPFI (OppFi, subprime installment lender, FINANCIAL tier) on 2026-07-22. **No code change — both numbers left as-is** by user decision; two gaps logged for later.

**FV $12.10 / +31% "undervalued" — DEFENSIBLE, left as-is.** Driven by the book/ROE legs (P/B 0.35 + RIM 0.45 = 80% weight); P/E leg is inert (`eps×trailing_pe ≈ price`, so it's just `price×0.9 = $8.32`). It is NOT a data bug: OPFI is an Up-C company that collapsed to a single share class in April 2026, so yfinance is messy, but the errors OFFSET — yfinance understates book (`bvps $2.862` vs real YE2025 equity $308.9M / ~86.2M sh ≈ **$3.58**) which pushes the legs down, while it overstates ROE (RIM's `eps/bvps = 2.03/2.862 = 70.9%` vs real GAAP `$146M/$308.9M ≈ 47%`, adjusted 51.5%) which pushes RIM up. Rebuilding the composite on *consistent real inputs* still lands ~$12.1–12.8. So the +31% is a faithful read of a genuinely high-ROE (~47%) lender at ~2.6× real book / ~5× earnings; what the quant model can't see is the regulatory tail (state APR caps on ~160% APR loans) that keeps the market at ~5×. Model limitation, not a bug.

**KNOWN GAP (NOW FIXED — see UPDATE above) — RIM applied no ROE cap, P/B did.** `calc_pb` (models.py:531) caps `roe = min(roe, ROE_PB_CAP_MULT(3.0) × coe)` = 25.5% for FINANCIALS "so a distorted, unsustainable ROE can't run the multiple away" — but `calc_rim` (models.py:546) used raw `roe = eps/bvps` UNCAPPED, and RIM is the highest-weighted leg. Mirroring the cap into RIM: RIM $14.99→$5.96, **composite $12.10→$8.03** on raw inputs (or ~$9.63 on corrected inputs) — flips BUY→fair. Blast radius: cap only binds FINANCIAL names with `eps/bvps > 25.5%`; normal banks (JPM ~15%) never touch it; **AXP is the canary** (~30% ROE — modest haircut, and P/B already caps it identically). FV-only, Quality unaffected.

**TODO — brainstorm a proper ROE-fade for RIM** (superpowers:brainstorming; DEFERRED, not blocking — see UPDATE above). The RIM implementation holds `(roe − coe)` FLAT for all 10 years and even grows book at g — no fade. Standard RIM fades ROE toward COE. A fade is the more correct fix than a flat cap (it would let a real 47% ROE contribute early but decay, instead of hard-clipping to 25.5%). Design forks to weigh: fade rate/half-life, whether to fade to COE or to a sector-sustainable ROE, reuse of an existing decay pattern (`_fade_hold_years` shape?). New mechanism ⇒ brainstorm, not a normal-session mirror. See [[app-serves-persisted-rows-not-live-compute]], [[financial-coe-growth-pb]].

**Quality 9.7 (highest ever) — SOUND, left as-is.** Section II 10.0 (roic 94%/rote 45%/spread 83%), I 9.0 (held down by revenue_cagr 9.65% despite eps_cagr 170% low-base artifact), IV 10.0 (shares_cagr −32% buybacks, insider own 60.5%, shareholder_yield 6%). Even stripping the distorted inputs the score barely moves — ROTE 45% alone maxes Section II. The score faithfully measures *fundamentals*, which ARE exceptional; it is structurally blind to durability/regulatory risk, so "9.7 = best in universe" overstates durability vs a moat compounder at 9.0. LATENT GAP (inconsequential here, worth noting): ROIC is structurally meaningless for a lender (same rationale that excludes FCF/OCF/leverage for FINANCIALS in scoring.py) yet 3 of Section II's 4 metrics are ROIC-derived and NOT excluded — ROTE happens to carry OPFI to 10.0 anyway, so no OPFI impact, but a lower-ROTE lender could be flattered by a distorted 90%+ ROIC.


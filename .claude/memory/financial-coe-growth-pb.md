---
name: financial-coe-growth-pb
description: FINANCIAL bucket read ~30% overvalued; fixed with bank COE 8.5% on book legs + growth-adjusted justified P/B + ROE guard; JPM $242->$294
metadata: 
  node_type: memory
  type: project
  originSessionId: f489c33f-af9d-46a1-b04e-fa1b1e9fd068
---

The FINANCIAL valuation bucket read systematically ~30% overvalued (JPM −30%, BAC −30%, WFC −26%, C −36% vs price) because both book-value legs — P/B (0.35) and RIM (0.45), i.e. 80% of the blend — discounted at the flat `DISCOUNT_RATE = 0.10`, and `calc_pb` used a zero-growth `ROE/r` multiple.

**Fix (DONE + MERGED to master no-ff `71edda1` on 2026-07-15, 254 tests pass, live-verified):**
1. `models.FINANCIAL_COE = 0.085`; `calc_pb` rewritten to read `fin['cost_of_equity']` (default `DISCOUNT_RATE`) and use the growth-adjusted `(ROE−g)/(COE−g)` with `g = min(TERMINAL_GROWTH, COE−0.01)`. At ROE==COE the multiple is exactly 1.0, so the two old `calc_pb` tests stayed green.
2. `engine.evaluate` gates `cost_of_equity = FINANCIAL_COE` for `stock_type == "FINANCIAL"` (on a copy; RIM already reads `cost_of_equity`, so this lifts both legs).
3. Distorted-ROE guard `models.ROE_PB_CAP_MULT = 3.0`: caps the ROE fed to `calc_pb` at 3×COE (25.5%), so a thin-book artifact (ALL 45% ROE) can't run the P/B multiple away. Clips ALL (+139%→+85% vs price) and AXP; leaves every healthy bank (ROE<25.5%) untouched.

**Why:** a lower, bank-appropriate cost of equity + a growth term is the higher-leverage lever than a P/B-only tweak (it hits 0.80 of the blend vs 0.35). Beta-based CAPM was rejected — bank betas ≈1 land COE back at ~10% and even lower GS/MS/SYF.

**How to apply / gotcha:** `services/yahoo.extract_financials` **hardcodes `cost_of_equity: 0.10`**, so the live pipeline never sends `None`. An `is None`-only gate silently no-ops live (RIM stuck at 0.10, JPM came out $255 not $294). The gate must treat `None` **or** `== DISCOUNT_RATE` as "unset". Always live-verify a COE change through `engine.run`, not just unit tests whose fixtures omit the field.

**Live result:** JPM $242→$294 (−15%), bank bucket +13–20%, C/AIG/SOFI rise modestly (COE lift outweighs growth-P/B markdown, no sign flips). COF stays broken (−97%, bad Discover-acquisition input — out of scope). Residual deep discounts on GS/MS/AXP (−27 to −42%) live in the P/E leg + RIM ROE, not COE/PB. Related: [[distorted-earnings-dual-cap]], [[payment-network-misclassification]], [[amd-acquisition-roic-distortion]].

---
name: size-coupled-growth-fade
description: "Why/how the valuation engine fades growth by market-cap band, and the EV/Sales gap it leaves"
metadata: 
  node_type: memory
  type: project
  originSessionId: ffa1ddc2-d81f-4c11-a231-33666ae7a851
---

The engine over-valued mega-caps because DCF + EV/EBITDA held near-term growth
flat for the full 10y horizon (META +73%, MSFT +62%, GOOGL +72% vs price, mid-2026).
Fixed in commit 075d1a3 with two decoupled changes:

1. **Size-coupled growth fade** (`models.py` `_faded_rate`/`_fade_hold_years`): growth
   is held for a market-cap-keyed number of years, then decays linearly to
   TERMINAL_GROWTH (3%) by HORIZON. Bands: **>= $1T → hold 0** (fade from yr1),
   **>= $150B → hold 3**, **< $150B → hold 5**. Applied to DCF and EV/EBITDA legs only.
2. **Classification ceiling** (`classifier.py`): GROWTH rule now requires market_cap
   < $1T, so $1T+ names label LARGE_CAP (META/MSFT/GOOGL were mislabeled GROWTH).

**Why:** base-rate drag — a $2T company can't compound 20% for a decade. Fade speed is
keyed to market cap *directly*, not the tier, because the tiers aren't size-ordered
(keying to tier backfired: mega-caps sat in GROWTH and would've faded least).

**How to apply:** thresholds ($1T/$150B) and holds (0/3/5) are the user-approved knobs.
Result: META -7%, MSFT -17%, GOOGL -6%; sub-$1T growers preserved (ADBE +64%);
low-growth names barely move.

**Growth-aware relief (commit fe75959):** the pure size-keying over-faded mega-caps
that are *also* genuine hyper-growers (AVGO crushed to $132, NVDA to $104). Fixed:
`_fade_hold_years(market_cap, revenue_growth)` now waives the size penalty when a
mega-cap grows above `MEGA_CAP_GROWTH_RELIEF` (0.40) — it reverts to the small-cap
hold (5y) instead of hold-0 ("grows like a grower → fades like one"). 40% was chosen
to relieve AVGO (48%)/NVDA (85%) but NOT META (33%), which stays the faded
overvaluation case. Paired with forward-EPS P/E normalization (see
[[avgo-forward-eps-pe]]). Result: AVGO 132→212, NVDA 104→151; META/MSFT/GOOGL/AAPL
unchanged.

**Known limitation:** the fade only touches DCF + EV/EBITDA. Thin-margin names
(EBITDA margin < 8%, e.g. COST at 4.7%) route through `pick_ev_multiple` to the
**EV/Sales** leg, which is NOT faded — so COST reads +14% instead of a faded value.
A conversion-compression "lever" was prototyped and deliberately dropped (knife-edge
at the 0.40 FCF/EBITDA floor; redundant with the fade). Related:
[[klac-growth-undervaluation]], [[distorted-earnings-dual-cap]].

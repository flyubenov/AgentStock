---
name: distorted-earnings-dual-cap
description: "Why distorted-earnings growth is capped at 0.20 for DCF/EV but SUSTAINABLE_CEIL for DDM, and that forward tiers keep their P/E leg"
metadata: 
  node_type: memory
  type: project
  originSessionId: ffa1ddc2-d81f-4c11-a231-33666ae7a851
---

The `_earnings_distorted` guard (negative GAAP earnings growth while revenue
grows) was over-punishing one-off-charge names like ETN: it floored DCF/EV
growth at the 3.9% `SUSTAINABLE_CEIL` AND dropped the P/E leg, crushing ETN to
$112 vs a ~$234 fair value. Fixed in commit e1f9ec9.

The 3.9% ceiling only ever existed to stop the **DDM perpetuity** from
overshooting Gordon growth (r-g). It must NOT bound the bounded-horizon legs
(DCF/EV/EBITDA/PE), which can carry the real revenue rate. So:

1. `build_scenarios(fin, distorted_cap=0.20)` — distorted names now source growth
   from revenue under the **normal 0.20 cap** (default). DCF/EV/PE use this.
2. **DDM is dispatched explicitly** in `evaluate` with
   `build_scenarios(fin, distorted_cap=SUSTAINABLE_CEIL)` so its perpetuity is
   unchanged (ABBV's DDM leg stayed at 267; a naive cap-removal doubled it to 593).
3. The P/E-drop guard now **skips forward tiers** (`stock_type in FORWARD_TIERS`):
   they value P/E off the *forward* multiple, robust to a one-off trailing charge.
   Non-forward tiers (e.g. DIVIDEND/ABBV) still drop the trailing P/E.

**Why:** ETN's distortion was a one-off charge masking real ~12-17% growth;
the guard treated it like a structural decline.

**Known limitation:** the sign of `earnings_growth` can't tell a one-off charge
(ETN) from a structural cliff (ABBV — Humira patent loss). ABBV's DCF leg rose
116->184 as a side effect (still modest: faded to 3% terminal, ~0.39 weight, DDM
dominates). Distinguishing the two needs a magnitude/source signal beyond the
sign. Related: [[size-coupled-growth-fade]].

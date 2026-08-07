---
name: revenue-coupled-growth-cap
description: "DONE + MERGED to master (no-ff 9ce8020) — dynamic growth cap (0.20→0.25) replacing the flat 0.20 in build_scenarios; 229 tests pass, APP live FV $349→$423"
metadata: 
  node_type: memory
  type: project
  originSessionId: f864a523-1eae-4d6e-a999-72b060eec317
---

Replacing the flat `0.20` near-term growth cap in `build_scenarios`
(`backend/valuation/engine.py`) with a gentle, revenue-coupled, profitability-gated
cap so genuine hyper-growers (APP, NVDA, IREN) earn a bounded increment of growth
credit. Motivated by validating APP: FV $349 (−22% vs price) was conservative
because the flat 0.20 refuses any credit for its 59–70% growth.

**Status as of 2026-07-15:** IMPLEMENTED. All 4 TDD tasks committed on
branch `feat/revenue-coupled-growth-cap` (implemented inline, not via subagents —
small single-file change): 117697e `_growth_cap`, 5ade1bb `_cap_eligible`,
ff2b439 wire into build_scenarios, 6ac11f0 e2e guard. Full suite 229 passed
(was 213; +16 new tests), no regressions. Live end-to-end confirmation against the
merged engine: APP cap→0.250, FV $422.88 (−5.8% vs px, was $349/−22%), no false
"undervalued" flip; KLAC (11.8% growth) untouched at cap 0.118.
**MERGED to master @9ce8020 (no-ff) on 2026-07-15.** Full suite 229 passed on master. Done.

- Spec: `docs/superpowers/specs/2026-07-15-revenue-coupled-growth-cap-design.md` @691508f
- Plan: `docs/superpowers/plans/2026-07-15-revenue-coupled-growth-cap.md` @db131d8

**Design decisions (locked, from AskUserQuestion):**
- Shape: `cap = min(0.25, 0.20 + 0.125*(g-0.20))` — gentle, ceiling reached at g=60%.
- Growth source: statement YoY (`revenue_growth_stmt`) primary, info `revenue_growth` fallback.
- Universal: NO mega-cap carve-out (user chose this; NVDA gets +25% but stays −14% vs price).
- Profitability gate: `fcf_ttm>0 OR (ebitda_ttm>0 AND ocf_ttm>0)` — op_margin isn't in the
  valuation fin dict, so reused the capex-reroute OCF signal (`engine.py:110`). Includes
  IREN-type capex-reroute names (+32%, stays −47% vs price).

**Safety invariants baked into the plan:**
- Elevated cap only on the normal path (`distorted_cap >= 0.20`); DDM path keeps 0.20.
- Distorted-earnings names (ABBV/ETN) unaffected (raw pre-capped at distorted_cap).
- 0.25 ceiling is the backstop against noisy-high growth.
- Existing build_scenarios tests stay green: their fixtures lack cash-flow fields, so the
  gate fails closed → cap stays 0.20. Do NOT add cash-flow fields to those fixtures.

**Verified live-data anchor impact (sweep):** APP +21%, NVDA +25%, IREN +32%, AMD +4%,
AVGO +2%, META +1%; sub-20% growers (HOOD/MSFT/KLAC/NFLX/TSLA/ETN) unchanged; no anchor
flips to "undervalued". Sweep scripts in the session scratchpad (not committed).

Related: [[size-coupled-growth-fade]] (the cap interacts with the fade duration),
[[hood-pe-growth-source-fix]], [[iren-opmargin-capex-reroute]] (source of the OCF gate).

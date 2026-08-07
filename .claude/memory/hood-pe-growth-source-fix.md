---
name: hood-pe-growth-source-fix
description: "HOOD FV too low ($19) because the P/E leg's PEG target collapsed on a noisy 2.7% yfinance earningsGrowth; fixed by sourcing PEG growth from bounded revenue growth when earnings growth is small-but-contradicted."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f67cc83-7660-438a-a388-4f38f8e00117
---

HOOD screened at FV **$19.47** vs a ~$110 price. The P/E leg was **$10.01**: for
forward tiers (GROWTH/LARGE_CAP/MID_CAP) `_forward_target_pe` builds the target
multiple as `min(forward_pe, earnings_growth% × PEG_CEILING[2.0])`, and yfinance's
trailing `info['earningsGrowth']` for HOOD was **2.7%** — a single-quarter YoY noise
value badly contradicted by ~49% revenue growth. That collapsed the target to 5.4×
(`$2.06 EPS × 5.4 × 0.90 MOS = $10.01`). The old revenue-growth fallback only fired
when earnings growth was `<= 0`, so a small positive noise value was used verbatim.

**Fix** (`backend/valuation/models.py`, `_forward_target_pe`): also substitute bounded
`revenue_growth` when `0 < earnings_growth < GROWTH_TRUST_FLOOR (0.10)` **and**
`revenue_growth > earnings_growth × GROWTH_REVENUE_RATIO (3.0)`. Chose **revenue
growth** (bounded) over forward-EPS-implied growth on purpose — the latter blows up
names with a sky-high forward P/E (TSLA: 134% × forward_pe 153 → $355). Surgical
trigger (Option B): HOOD fires (P/E leg $10.01→$56, blend $19.47→$28.72); **TSLA**
(earnings 8.3%, revenue 15.8% doesn't clear 3×) and **QCOM** (173%, above floor) stay
on the identical code path, unchanged.

TDD on branch `fix/pe-leg-growth-source`: 1 RED (HOOD) + 4 regression guards (incl. a
nonpositive/missing-revenue guard added after code review). **DONE + MERGED to master**
(no-ff merge dd3cef9, commits bb2490c + 1f3b043), 213 tests pass, not pushed. Code
review (high) surfaced no blocking bugs — the two logged risks are the accepted design:
the ratio-only trigger can inflate the P/E target for a name genuinely trading margin
for revenue growth, and it uses the noisy info `revenue_growth` rather than the cleaner
`revenue_growth_stmt` the engine prefers elsewhere (deliberate: bounded/conservative).
Out of scope and left alone: the EV/Sales
`MATURE_EV_SALES = 2.0` cap (still the biggest drag on HOOD at 0.40 weight — a
deliberate mean-reversion design choice, not a data defect) and the AVGO EPS-base
logic. HOOD's Quality Score 6.3 was validated as correct (no change). Same class as
[[iren-opmargin-capex-reroute]] (broken yfinance info field); pairs with
[[avgo-forward-eps-pe]] (the EPS-base half of the same leg).

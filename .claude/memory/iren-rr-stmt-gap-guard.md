---
name: iren-rr-stmt-gap-guard
description: R-R growth/burn slots trusted info.revenueGrowth/operatingMargins unconditionally; a statement-corroboration gap guard fixes capex-heavy crypto miners without disturbing CORZ/APLD's genuine business-transition divergence
metadata:
  node_type: memory
  type: project
---

Validating IREN's R-R (reported 0.61-0.62, "Risk-Favored") surfaced that `growth`/`burn`
used the SAME broken `info.revenueGrowth`/`operatingMargins` feed already documented and
fixed for IREN in FV/Quality ([[iren-opmargin-capex-reroute]]) — but R-R is a fully
isolated module (`backend/risk_reward/`) and never got the equivalent fix. `growth` scored
1.0/5 off `revenueGrowth = -0.0` (real statement YoY +167.7%); `burn` scored 5.0/5 (worst)
off `operatingMargins = -64.5%` (real statement operating margin +4.4%).

**Design fork surfaced by the blast-radius sweep (mandatory before touching anything):**
an unconditional statement-primary swap (mirroring screener/metrics.py's `op_margin`/
`revenue_growth_yoy`, which IS unconditional) fixes IREN and 5 sibling crypto miners
(MARA, RIOT, CLSK, CIFR, WULF — same shape: info reads a flat/negative growth artifact
while the statement shows real growth) but ALSO flips two peers in the *same* subsector the
*wrong* direction: **CORZ** (info revenueGrowth +108.8% vs statement **-37.5%** — a real
2023-24 mining->AI-hosting business-mix transition, not a feed bug; info operatingMargins
+6.9% vs statement **-70.4%**, a real GAAP operating loss/impairment) and **APLD** (info
+406.6% vs statement +5.6%, likely a quarter that inflected ahead of the trailing annual
print). Unlike IREN, there's no data-grounded reason to prefer either basis for these two —
correcting them would mask real risk (CORZ) or manufacture a downgrade from noise (APLD).
This is the same failure mode class FV's `_earnings_distorted`/`_earnings_non_operating`
guards exist to prevent, and R-R has none of that guard machinery.

**Fix (directional, self-limiting score-gap guard, `risk_reward/scoring.py`):**
`_stmt_gap_override` compares the statement-sourced score against the info-chain-resolved
score on the SAME 1-5 scale and overrides ONLY when statement is materially more
favorable — `growth`: statement score higher (info understates growth); `burn`: info
score higher (info overstates risk) — never the opposite direction. New source keys
`revenue_growth_stmt`/`operating_margin_stmt` (statement Total Revenue YoY / Operating
Income÷Total Revenue, same math as screener/metrics.py, reusing `StatementSeries` +
`fetch_income_stmt`) feed the guard ONLY — never added to the slots' normal fallback
chains. New config constant `CONFIG.stmt_gap_min = 1.0` (shared for both slots).

**Live-measured threshold placement (23-name basket: IREN + 10 crypto/AI-compute-adjacent
+ 12 general canaries), gap = |stmt_score - info_score| on the shared 1-5 scale:**
true positives (must fire) 1.48-4.00 (RIOT lowest, IREN/MARA/CLSK/CIFR at 4.00); largest
false-positive candidate (must NOT fire) is CRWV's burn gap 0.80. `1.0` sits with wide
margin on both sides — not a knife-edge tune. CORZ/APLD are excluded structurally by the
SIGN of the gap (statement reads worse, not better), no per-name carve-out needed.

**Live result:** IREN ratio **0.622 -> 0.854** (Reward 2.807->3.56, Risk 4.513->4.30),
tier **Risk-Favored -> Balanced**. `growth` source `revenue_growth` -> `revenue_growth_stmt`
(score 1.0->5.0); `burn` source `operating_margin` -> `operating_margin_stmt` (score
5.0->2.41).

**Blast radius, live-verified via `risk_reward.engine.run` (not a probe) across all 23
names:** `growth` override fires ONLY for IREN, MARA, RIOT, CLSK, CIFR, WULF (all move
toward Balanced/less-Risk-Favored, no over-correction observed). `burn` override fires
ONLY for IREN in this basket. CORZ, APLD, NBIS, KLAC, AAPL, NVDA, PLTR, CRWV, TEM, BWXT,
NFLX, AMD, ANET, V, MU, SNPS are byte-identical (still `revenue_growth`/`operating_margin`
sourced) — the fork case is provably neutralized, not just asserted.

FV/Quality untouched (R-R change; isolated module, no shared code path). 492 backend tests
pass (was 481; +9 new for the guard + 2 for the `risk_reward/data.py` statement wiring).

Process note: `superpowers:brainstorming` isn't mounted in this checkout; the design fork
(unconditional swap vs. guarded/targeted) was resolved by running the live score-gap
measurement directly and picking the threshold from the data rather than convening a formal
brainstorm — recorded here so a future session doesn't need to re-derive it.

Related: [[iren-opmargin-capex-reroute]] (the FV/Quality-side fix for the same broken
`info` feed — this is R-R's isolated-module counterpart, NOT a shared fix), M5 (leverage
negative-equity gap, still unfixed, same broad pattern of a risk-axis sign artifact).

# Validating-Agent-Stock Skill — Risk-Reward Extension — Design Spec

**Date:** 2026-08-08
**Branch:** `validate-risk-reward` (from `master` @ `7008ab3`)
**Status:** Approved design; ready for implementation planning.

## 1. Objective

Extend the existing `validating-agent-stock` skill so it can validate the **Risk-Reward
(R-R) ratio** — the third scoring pipeline shipped by the Risk-Reward Rating Engine
(merged to `master` @ `7008ab3`). Today the skill and its harness know only the two
original pipelines (Fair Value + Quality Score). This adds R-R as a first-class, but
**on-demand**, validation target.

The deliverable is documentation + a harness change, **not** any change to the R-R engine
itself. A known R-R engine gap (the M5 negative-`debtToEquity` case) is *documented as a
trap*, not fixed here; fixing it would be a separate, validation-driven task that this
extended skill would then drive.

## 2. What makes R-R different (the framing that drives the design)

Fair Value is judged against market/DCF reality; Quality against business fundamentals.
**R-R has no external market truth** — the ratio is a *constructed index*: `Reward ÷ Risk`
of twelve interpolated 1–5 metric scores across two axes, with config-set anchors and
weights, clamped to `[0.2, 5.0]` and mapped to a tier. So "validating an R-R ratio" is not
"is this the right market number"; it is three things, in priority order:

1. **Internal correctness (primary).** Given a ticker, is the ratio computed correctly from
   *its* inputs — right metric sourcing/fallbacks, right anchor applied to each metric,
   coverage floor honored, reward/risk axes + clamp + tier faithful.
2. **Tier face-validity, with a grounded qualitative read (secondary).** Does the tier
   (Asymmetric Upside … Balanced … Value Trap) tell a sensible story for the company — is
   the reward-heavy / risk-heavy split defensible, or an artifact of one mis-scored metric?
3. **Anchor/weight calibration (also in scope).** Are the *global* config anchors + weights
   well-tuned so ratios across the whole universe are sensible (e.g. the known M5 gap, the
   analyst-weight ramp bounds). Blast radius = every ticker.

Two cross-cutting facts about R-R that the skill must state, because they change how a
validator reasons:

- **R-R is fully isolated** from Fair Value and Quality Score. An R-R change cannot move an
  FV or Quality number, and vice-versa. This bounds blast radius in a way FV/Quality changes
  are not bounded.
- **R-R is config-driven.** Anchors, weights, tier bounds, clamp, and the analyst-weight
  knobs all live in `backend/risk_reward/config.py`. Many R-R "fixes" are therefore a config
  re-tune (global blast radius) rather than deep logic.

## 3. Trigger and flow (on-demand + light cross-reference)

- The skill's **triggers expand** so it *fires* on R-R questions ("is X's R-R ratio right?",
  "why is this a Value Trap?", "does this R-R look fair?").
- The **full R-R recipe** (reading `risk-reward-validation.md`, doing the reconciliation +
  qualitative read) runs **only when the question is about R-R**. FV/Quality questions are
  answered as they are today — the agent does not run the R-R recipe unprompted.
- **Light cross-reference:** because the harness now always computes R-R cheaply (§4), an
  FV/Quality answer *may* add a **one-line** R-R cross-reference (ratio + tier) when it is
  relevant — especially when it *contradicts* the FV/Quality verdict (e.g. FV says "cheap"
  but R-R says "Value Trap"). This is a sanity flag, never a full R-R validation.

## 4. Harness change — `validate_ticker.py`

The harness (`.claude/skills/validating-agent-stock/validate_ticker.py`) currently runs
`fv_run` + `sc_run` via `asyncio.gather` and dumps FV + Quality (+ raw inputs under
`--inputs`). It stays a **read-only** live probe. Changes:

- Import and add `risk_reward.engine.run` to the `gather` (three pipelines now).
- Emit a new top-level **`RISK_REWARD`** block, always present, containing the full
  `RiskRewardResult.model_dump()`:
  - `ratio`, `tier`, `reward_score`, `risk_score`, `actionable_insight`, `status`, `errors`
  - **`metric_scores`** — the per-slot dict (each metric's `raw` / `source` / `score` /
    `weight` / `dropped`). This is the reconciliation core: which of the twelve metrics are
    active, which source/fallback fired, which anchor each hit, and the weight (including the
    dynamic analyst weight).
  - **`raw_snapshot`** — price, peg, d/e, dist-from-200MA, dist-from-52W-high, rsi, vol.
- Under the **existing `--inputs` flag**, add an **`rr_source_inputs`** dict: the exact
  yfinance `info` fields R-R consumes, so every metric's sourcing and the analyst weight are
  cross-checkable. Must include the analyst-weight inputs (`numberOfAnalystOpinions`,
  `targetHighPrice`, `targetLowPrice`, `targetMeanPrice`) and the risk-axis raw fields
  (`debtToEquity`, `totalDebt`, `totalCash`, `ebitda`, `operatingMargins`, `profitMargins`,
  `currentRatio`, `quickRatio`, `beta`), plus the reward-axis raw fields (`pegRatio`,
  `trailingPegRatio`, `forwardPE`, `priceToSalesTrailing12Months`, `revenueGrowth`,
  `earningsGrowth`, `returnOnEquity`, `returnOnAssets`, `fiftyTwoWeekHigh`).
- Cost: one extra live call (R-R's daily-history fetch; `info` is already cached). Acceptable
  for an interactive read-only probe, and it makes the §3 cross-reference free.

The harness docstring updates from "Runs BOTH pipelines" to "Runs ALL THREE pipelines".

## 5. `SKILL.md` spine edits (kept lean)

Only short, cross-cutting changes go in `SKILL.md`; the depth lives in the new reference
(§6). Specifically:

- **Frontmatter `description`:** add R-R triggers so the skill fires on R-R questions.
- **Overview (line ~10):** "two-pipeline" → "three-pipeline"; name R-R alongside FV/Quality.
- **Core principle:** add a companion line — the R-R ratio is a *constructed index with no
  market truth*; validate internal correctness + whether the tier's story matches the
  company (contrast with "a fair value is a range").
- **"When to use":** add the R-R triggers; keep "When NOT to use" intact.
- **Codebase map:** add R-R rows — `risk_reward/engine.py` `run(ticker)`,
  `risk_reward/scoring.py` `build_metric_scores` / `aggregate`, `risk_reward/config.py`
  (anchors/weights/tiers), `services/risk_reward_sheets.py` (persist + col R mirror).
- **Two cross-cutting facts inline:** R-R is **isolated** from FV/Quality (bounds blast
  radius) and **config-driven** (anchors/weights in `config.py`).
- **Harness section:** note it now runs all three and dumps the `RISK_REWARD` block.
- **Pointer:** "**Validating a Risk-Reward ratio? Read `risk-reward-validation.md`.**" plus
  the one-line-cross-reference guidance from §3.

The FV/Quality reasoning in `SKILL.md` is otherwise unchanged — an FV or Quality validation
reads and behaves exactly as it does today.

## 6. New reference — `risk-reward-validation.md`

A self-contained companion, read only when the question is about R-R. Sections:

1. **What R-R is / what "validate" means.** The two axes, the twelve metrics, interpolation
   anchors, clamp `[0.2, 5.0]`, tier map, coverage floor (`≥2` active reward AND `≥2` active
   risk, else `insufficient_data` → N/A). Restate: no market truth ⇒ validation = internal
   correctness (priority) + tier face-validity + optional anchor calibration.

2. **Reconciliation recipe (internal correctness — the priority).**
   - Run the harness; read the `RISK_REWARD` block (and `rr_source_inputs` under `--inputs`).
   - Reconcile the composite: `reward_score` = weighted average of *active* (non-dropped)
     reward metrics with weights **renormalized to the active set**; `risk_score` likewise;
     `ratio = clamp(reward_score / risk_score, 0.2, 5.0)`; `tier = map(ratio)`.
   - Per-metric check for each of the twelve slots: which source/fallback fired, which anchor
     triple applied, is the `raw` value right (cross-check against `rr_source_inputs` /
     reality), is the interpolation correct. Watch dropped slots and the coverage floor.
   - Localize the driver: which metric(s) / which axis moved the ratio. Classify the cause as
     a **data** problem (bad input), a **config** problem (an anchor/weight that mis-fits), or
     a **logic** problem (a guard/fallback).
   - To probe logic on synthetic inputs with no network: call the pure cores directly —
     `risk_reward.scoring.build_metric_scores(inputs)` and
     `risk_reward.scoring.aggregate(scores)`.

3. **The qualitative read (data-grounded + analyst judgment).** Assemble the company story
   from data already dumped, then enrich with domain judgment, **labeling every claim**:
   - **Reward axis** (valuation, growth, profitability, analyst upside, discount, RSI) →
     the growth-potential / upside story.
   - **Risk axis** (leverage, burn, liquidity, volatility, trend, beta) → the risks / issues.
   - **Moat** is *not* an R-R metric — read it from the **Quality pipeline's Section II**
     (ROIC, ROIC−WACC, ROTE), which the harness already dumps, plus profitability.
   - **FV inputs** → valuation context.
   - Tag each line **DATA** (traceable to a dumped number) vs **JUDGMENT** (analyst knowledge
     of the business / sector / competitive position). Then answer the user's real question:
     does the tier's reward-heavy / risk-heavy story *correspond* to that qualitative
     picture — is the ratio **trustworthy**, or is the tier an artifact of one mis-scored
     metric?

4. **R-R traps catalog** (the R-R-specific gotchas a validator must know):
   - **Confidence-scaled analyst weight** (`weight = 0.08 + 0.10·c`, `c = min(coverage,
     agreement)`): coverage from `numberOfAnalystOpinions`, agreement from target dispersion;
     **missing inputs collapse `c` → the 8% floor** (pre-profit / thin-coverage names sit at
     the floor by design, not a bug). Cross-check with `numberOfAnalystOpinions` + the target
     spread.
   - **Coverage floor → N/A** (`status = insufficient_data`): a legitimate outcome for thin
     data, never a fabricated ratio — not a bug.
   - **Negative-PEG guard** (shipped `3963fea`): a non-positive PEG now falls through to
     earnings-yield instead of saturating valuation reward at 5.0.
   - **M5 — KNOWN UNFIXED GAP:** a negative `debtToEquity` (negative equity) saturates the
     leverage risk score to the *safest* 1.0 — the risk-axis mirror of the PEG bug. Flag it
     when validating a negative-equity name; it is documented, not fixed here.
   - **Sign artifacts on the risk axis** generally (negative denominators reading as benign).
   - Shared input traps as they hit R-R metrics: statement-vs-`info` basis, split distortion,
     quarterly-vs-annual growth.

5. **The R-R worked-example rule.** Any proposed R-R change must be pinned to numbers: the
   exact metric / anchor / weight / guard (symbol + file), its **current → proposed value**,
   and the **before → after `ratio` + `reward_score` + `risk_score` + `tier`**, *measured*
   by re-running `build_metric_scores` + `aggregate` on the live inputs with the value/anchor
   swapped (a read-only monkey-patch probe — don't estimate). State the blast radius:
   - R-R changes are **FV/Quality-neutral** (isolated).
   - An **input fix** corrects ~one ticker; a **config anchor/weight change has a GLOBAL blast
     radius** — it moves every ticker, so it requires a read-only universe sweep before it is
     proposed.

6. **Calibration / optimize flow (only if a real gap is confirmed).** Mirror `SKILL.md`'s
   existing optimize discipline, specialized for R-R's three lever kinds:
   - **Input lever** (fix a broken/stale/wrong-basis R-R input) — low blast radius, ~one
     ticker.
   - **Config lever** (re-tune an anchor triple / weight / ramp bound in `config.py`) —
     **global** blast radius; sweep the universe, confirm canaries don't regress.
   - **Logic lever** (a new guard/fallback, like the PEG guard, or the M5 fix) — TDD it.
   Reuse-before-inventing; establish green `pytest` first; TDD the change; re-validate the
   ticker and canaries; record the fix in memory (which anchors were tuned against which
   inputs, which tickers were verified unmoved).

## 7. Verification

There is **no backend engine change**, so `pytest` is unaffected; the harness is a read-only
probe. Verification is:

- Run the extended `validate_ticker.py` live on a few contrasting tickers — a healthy
  profitable name, a pre-profit burner, and a name that returns `insufficient_data` / N/A —
  and confirm the `RISK_REWARD` block is correct: the reconciliation math holds
  (`reward/risk → ratio → tier`), the per-metric `source`/`anchor`/`score` are right, and
  `rr_source_inputs` (under `--inputs`) contains the analyst-weight and risk-axis fields.
- Dry-run the qualitative read on one ticker to confirm it stays grounded (every claim tagged
  DATA vs JUDGMENT) and that the trustworthiness verdict follows from the evidence.
- Confirm an FV-only and a Quality-only question still read/behave exactly as before, with at
  most the optional one-line R-R cross-reference.

## 8. Non-goals

- **Not** fixing the M5 negative-`debtToEquity` gap (documented as a trap only).
- **Not** changing the R-R engine, its config, or any FV/Quality behavior.
- **Not** adding external/news data fetches — the qualitative read is data-grounded +
  analyst judgment, no new sources.
- **Not** always-on three-pipeline validation — R-R deep-validates on demand.

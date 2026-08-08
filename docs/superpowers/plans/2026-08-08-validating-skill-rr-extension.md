# Validating-Agent-Stock R-R Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `validating-agent-stock` skill so it validates the Risk-Reward (R-R) ratio — the third pipeline — on demand, via a harness change and two documentation files.

**Architecture:** Three self-contained changes under `.claude/skills/validating-agent-stock/`: (1) the read-only harness `validate_ticker.py` gains the R-R pipeline and dumps a `RISK_REWARD` block; (2) a new `risk-reward-validation.md` reference holds the deep R-R recipe, qualitative read, traps, and calibration flow; (3) `SKILL.md` gets lean spine edits (three-pipeline framing, R-R codebase-map rows, a pointer to the reference, and the on-demand + one-line-cross-reference policy). No backend engine change.

**Tech Stack:** Python 3.14 (the harness is a standalone read-only script that locates `backend/` itself and calls existing engine functions live via yfinance); Markdown for the skill docs. There is NO unit-test framework for the skill harness — verification is a live run of the harness plus documentation content checklists, exactly as the spec's §7 prescribes.

## Global Constraints

- **Docs + harness only. No backend engine change.** Do not touch `backend/risk_reward/`, `backend/valuation/`, `backend/screener/`, or any FV/Quality behavior. `pytest` is not run or affected by this plan.
- **The M5 negative-`debtToEquity` gap is DOCUMENTED as a trap, NOT fixed here.** (A negative D/E saturates the leverage risk score to the safest 1.0 — the risk-axis mirror of the negative-PEG bug.)
- **The harness stays a READ-ONLY probe** — it only calls existing engine functions on live data and never writes Sheets.
- **On-demand policy:** the full R-R recipe runs only when the question is about R-R; FV/Quality validations behave exactly as today, plus an optional one-line R-R cross-reference.
- **Qualitative read is data-grounded + analyst judgment, every claim labeled DATA vs JUDGMENT, with NO new data fetches.** Moat is read from the Quality pipeline's Section II (ROIC / ROIC−WACC / ROTE), since it is not an R-R metric.
- **Source of truth for content:** `docs/superpowers/specs/2026-08-08-validating-skill-rr-extension-design.md` (committed `2e2f885`). Where this plan enumerates required content, it must match that spec.
- **Commits** append the two standard trailers (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and `Claude-Session: …`). Commit commands below omit them for brevity — add them.
- **Running the harness:** use the backend's Python (the one that runs `cd backend && python -m pytest`). The harness locates `backend/` itself, so it can be invoked from the repo root:
  `python ".claude/skills/validating-agent-stock/validate_ticker.py" <TICKER> [--inputs]`

---

### Task 1: Harness — add the R-R pipeline and the `RISK_REWARD` block

**Files:**
- Modify: `.claude/skills/validating-agent-stock/validate_ticker.py`

**Interfaces:**
- Consumes: `risk_reward.engine.run(ticker) -> RiskRewardResult` (async; returns a result even on failure — `status` in `completed`/`insufficient_data`/`failed` — it does not raise for normal data gaps). `services.yahoo.fetch_ticker_info(ticker)` (already imported in the harness; cached per process).
- Produces: the harness JSON dump gains a top-level `RISK_REWARD` key (the full `RiskRewardResult.model_dump()`) on every run, and an `INPUTS.rr_source_inputs` dict when `--inputs` is passed. FV and QUALITY output are unchanged.

- [ ] **Step 1: Add the R-R engine import**

Next to the existing engine imports (after `from screener.engine import run as sc_run`), add:

```python
from risk_reward.engine import run as rr_run            # noqa: E402
```

- [ ] **Step 2: Add the R-R source-input field list**

Below the imports (module scope), add the exact `info` fields the R-R engine consumes, used for the `--inputs` cross-check dump:

```python
# The yfinance info fields the Risk-Reward engine reads, dumped under --inputs so
# every R-R metric's sourcing (and the confidence-scaled analyst weight) is
# cross-checkable against the raw values.
_RR_INFO_FIELDS = [
    # reward axis
    "pegRatio", "trailingPegRatio", "forwardPE", "priceToSalesTrailing12Months",
    "revenueGrowth", "earningsGrowth", "returnOnEquity", "returnOnAssets",
    "targetMeanPrice", "targetHighPrice", "targetLowPrice", "numberOfAnalystOpinions",
    "fiftyTwoWeekHigh",
    # risk axis
    "debtToEquity", "totalDebt", "totalCash", "ebitda",
    "operatingMargins", "profitMargins", "currentRatio", "quickRatio", "beta",
]
```

- [ ] **Step 3: Extend `main` to run R-R and dump the `RISK_REWARD` block**

Replace the body of `async def main(ticker: str, with_inputs: bool):` with the three-pipeline version. Add `rr_run(ticker)` to the `gather`, dump its `model_dump()` under `RISK_REWARD`, and add `rr_source_inputs` under the `--inputs` branch:

```python
async def main(ticker: str, with_inputs: bool):
    fv, sc, rr = await asyncio.gather(fv_run(ticker), sc_run(ticker), rr_run(ticker))
    out = {
        "FV": fv.model_dump(),
        "QUALITY": {
            "quality_score": sc.quality_score,
            "sector": sc.sector,
            "sector_profile": sc.sector_profile,
            "section_scores": sc.section_scores,
            "score_breakdown": sc.score_breakdown,
            "status": sc.status,
            "errors": sc.errors,
        },
        # Third pipeline. The full result: ratio, tier, reward_score, risk_score,
        # actionable_insight, per-slot metric_scores (raw/source/score/weight/dropped),
        # raw_snapshot, status, errors. See risk-reward-validation.md for the recipe.
        "RISK_REWARD": rr.model_dump(),
    }
    if with_inputs:
        out["INPUTS"] = await dump_inputs(ticker)
        info = await fetch_ticker_info(ticker)   # cached per process
        out["INPUTS"]["rr_source_inputs"] = {k: info.get(k) for k in _RR_INFO_FIELDS}
    print(json.dumps(out, indent=2, default=str))
```

- [ ] **Step 4: Update the module docstring**

Change the opening docstring from "Runs BOTH pipelines live" to reflect three, e.g. first line: `"""Single-ticker validation harness for Agent Stock — runs ALL THREE pipelines."""` and update the body sentence that says "Runs BOTH pipelines live (yfinance) for one ticker" to "Runs all three pipelines live (yfinance) for one ticker" and mention the Risk-Reward breakdown alongside the FV breakdown and Quality sections.

- [ ] **Step 5: Verify live — the three-pipeline dump on a healthy name**

Run (from repo root): `python ".claude/skills/validating-agent-stock/validate_ticker.py" KLAC --inputs`
Expected: JSON with top-level keys `FV`, `QUALITY`, `RISK_REWARD`, `INPUTS`. Confirm:
- `RISK_REWARD.ratio`, `.tier`, `.reward_score`, `.risk_score`, `.status` are present.
- `RISK_REWARD.metric_scores` has the twelve slots (valuation, growth, profitability, analyst_upside, discount, rsi, leverage, burn, liquidity, volatility, trend, beta), each with `raw`/`source`/`score`/`weight`/`dropped`.
- Reconciliation holds: the ratio equals `clamp(reward_score / risk_score, 0.2, 5.0)` rounded, and `reward_score`/`risk_score` are the renormalized weighted averages of the active (non-dropped) metrics on each axis.
- `INPUTS.rr_source_inputs` contains the analyst-weight fields (`numberOfAnalystOpinions`, `targetHighPrice`, `targetLowPrice`, `targetMeanPrice`) and the risk-axis fields (`debtToEquity`, `currentRatio`, `beta`).
- `FV` and `QUALITY` blocks are still present and well-formed (unchanged shape).

- [ ] **Step 6: Verify live — a pre-profit burner and the N/A path**

Run: `python ".claude/skills/validating-agent-stock/validate_ticker.py" IREN` and `... NBIS`
Expected: `RISK_REWARD` present for each; note the reward/risk mix differs (burn/volatility elevated). If either returns `status: "insufficient_data"` with `ratio: null`, confirm the harness passes that through faithfully (blank ratio, no fabricated number). (The coverage-floor N/A path is already unit-covered by the engine's `test_insufficient_data_when_thin`; the harness's only job is to surface `status`/`ratio` verbatim, which is visible on any dump.)

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/validating-agent-stock/validate_ticker.py
git commit -m "feat(validate-skill): harness runs all three pipelines + RISK_REWARD block"
```

---

### Task 2: New reference — `risk-reward-validation.md`

**Files:**
- Create: `.claude/skills/validating-agent-stock/risk-reward-validation.md`

**Interfaces:**
- Consumes: the harness `RISK_REWARD` block + `rr_source_inputs` from Task 1; the R-R engine's pure cores `risk_reward.scoring.build_metric_scores(inputs)` and `risk_reward.scoring.aggregate(scores)` (for synthetic/no-network probes).
- Produces: the self-contained R-R validation reference that `SKILL.md` (Task 3) points to. No other task depends on its internal headings, but Task 3's pointer must match this file's name.

This is a documentation deliverable. Write the file with the six sections below, each carrying the specific, concrete content listed. Content must match spec §6 of `docs/superpowers/specs/2026-08-08-validating-skill-rr-extension-design.md` (read it before writing). Do not leave any section as a stub.

- [ ] **Step 1: Write the reference file**

Create `.claude/skills/validating-agent-stock/risk-reward-validation.md` with these sections and required content:

1. **`# Validating a Risk-Reward Ratio`** intro — one paragraph: R-R = `Reward ÷ Risk` of twelve interpolated 1–5 metric scores across two axes, clamped `[0.2, 5.0]`, mapped to a tier; **no external market truth** (contrast FV↔market/DCF, Quality↔fundamentals), so validation = internal correctness (priority) + tier face-validity + optional anchor calibration. State the two cross-cutting facts: R-R is **isolated** from FV/Quality, and **config-driven** (`backend/risk_reward/config.py`).

2. **`## The metric roster`** — a compact table of the twelve metrics with axis, source→fallback chain, and the `(a5, a3, a1)` anchor triple, so a validator can see which anchor each metric hit. Reward: valuation (`pegRatio`/`trailingPegRatio` → `1/forwardPE` → `1/priceToSales`; guarded so non-positive PEG falls through), growth (`revenueGrowth`→`earningsGrowth`), profitability (`returnOnEquity`→`returnOnAssets`), analyst_upside (`(targetMean−price)/price`), discount (dist below 52W high), rsi. Risk: leverage (`debtToEquity`→net-debt/EBITDA), burn (`operatingMargins`→`profitMargins`), liquidity (`currentRatio`→`quickRatio`), volatility (annualized σ), trend (price vs 200MA), beta. Note the coverage floor: `≥2` active reward AND `≥2` active risk, else `insufficient_data` → N/A.

3. **`## Reconciliation recipe (internal correctness — the priority)`** — the numbered procedure:
   1. Run the harness (`validate_ticker.py <T> --inputs`); read the `RISK_REWARD` block and `rr_source_inputs`.
   2. Reconcile the composite: `reward_score` = weighted average of *active* (non-dropped) reward metrics with weights **renormalized to the active set**; `risk_score` likewise; `ratio = clamp(reward_score/risk_score, 0.2, 5.0)`; `tier = map(ratio)` (≥2.0 Asymmetric Upside · ≥1.3 Reward-Favored · ≥0.8 Balanced · ≥0.5 Risk-Favored · else Value Trap).
   3. Per-metric check for each of the twelve slots: which `source`/fallback fired, which anchor triple, is `raw` right (cross-check vs `rr_source_inputs` / reality), is the interpolation correct. Watch dropped slots + the coverage floor.
   4. Localize the driver: which metric(s)/axis moved the ratio. Classify **data** (bad input) vs **config** (an anchor/weight that mis-fits) vs **logic** (a guard/fallback) problem.
   5. No-network logic probe: call `risk_reward.scoring.build_metric_scores(inputs)` then `risk_reward.scoring.aggregate(scores)` on synthetic inputs.

4. **`## The qualitative read (data-grounded + judgment)`** — instruct: assemble the company story from dumped data, then enrich with domain judgment, **labeling every claim DATA vs JUDGMENT**. Map: reward axis → growth/upside story; risk axis → risks/issues; **moat → Quality Section II (ROIC / ROIC−WACC / ROTE) from the harness `QUALITY.section_scores`** (moat is not an R-R metric); FV inputs → valuation context. End with the trustworthiness verdict: does the tier's reward-heavy/risk-heavy story *correspond* to that picture, or is it an artifact of one mis-scored metric? Include a short worked illustration (e.g. the IREN-style example: growth 5/5 DATA → capex-heavy JUDGMENT; ROIC−WACC DATA → narrow-moat JUDGMENT; burn/leverage DATA → funding-gap JUDGMENT; ⇒ is the "Value Trap" tier trustworthy?).

5. **`## R-R traps`** — the catalog, each as a short labeled entry:
   - **Confidence-scaled analyst weight:** `weight = 0.08 + 0.10·c`, `c = min(coverage, agreement)`; coverage from `numberOfAnalystOpinions` (ramp 0 at ≤3 → 1 at ≥20), agreement from target dispersion `(targetHigh−targetLow)/targetMean` (1 at ≤20% → 0 at ≥80%); **missing inputs collapse `c` → the 8% floor** — pre-profit/thin-coverage names sit at the floor by design, not a bug. Cross-check with `numberOfAnalystOpinions` + the target spread in `rr_source_inputs`.
   - **Coverage floor → N/A** (`status = insufficient_data`): legitimate thin-data outcome, never a fabricated ratio — not a bug.
   - **Negative-PEG guard** (shipped `3963fea`): a non-positive PEG falls through to earnings-yield instead of saturating valuation reward at 5.0.
   - **M5 — KNOWN UNFIXED GAP:** a negative `debtToEquity` (negative equity) saturates the leverage risk score to the *safest* 1.0 — the risk-axis mirror of the PEG bug. Flag it on negative-equity names; documented, not fixed.
   - **Sign artifacts on the risk axis** generally (negative denominators reading as benign).
   - **Shared input traps** as they hit R-R metrics: statement-vs-`info` basis, split distortion, quarterly-vs-annual growth.

6. **`## Proposing an R-R change (worked-example rule + calibration)`** — any proposed change is pinned to numbers: the exact metric/anchor/weight/guard (symbol + file), **current → proposed value**, and **before → after `ratio` + `reward_score` + `risk_score` + `tier`**, *measured* by re-running `build_metric_scores` + `aggregate` on the live inputs with the value/anchor swapped (read-only monkey-patch probe — don't estimate). Blast radius: R-R changes are **FV/Quality-neutral**; an **input fix** ≈ one ticker, a **config anchor/weight change is GLOBAL** (sweep the universe before proposing). Then the three lever kinds — input / config / logic — and: establish green `pytest` first, reuse-before-inventing, TDD the change, re-validate the ticker + canaries (IREN/NBIS/KLAC), record the fix in memory.

- [ ] **Step 2: Verify content completeness**

Re-read the file against this checklist — every item must be present and concrete (no stub, no "TBD"):
- All six sections present with the headings above.
- The metric-roster table lists all twelve metrics with axis + source chain + anchors, and states the coverage floor.
- The reconciliation recipe has the five numbered steps including the renormalization rule and the `build_metric_scores`/`aggregate` no-network probe.
- The qualitative-read section maps reward/risk/moat/valuation sources, mandates DATA-vs-JUDGMENT labeling, and ends on the trustworthiness verdict, with a worked illustration.
- The traps catalog includes the analyst weight, coverage-floor N/A, negative-PEG guard, **the M5 gap explicitly marked KNOWN/UNFIXED**, sign artifacts, and shared input traps.
- The worked-example rule requires before→after ratio+axes+tier measured (not estimated), states R-R is FV/Quality-neutral, and distinguishes input (one ticker) vs config (global) blast radius.

- [ ] **Step 3: Verify by dry-running the recipe live**

Run `python ".claude/skills/validating-agent-stock/validate_ticker.py" IREN --inputs`, then follow the reference's reconciliation recipe against that output: confirm the steps are followable end-to-end (you can identify the active metrics, reconcile reward/risk → ratio → tier, and locate the driver) and that a short qualitative read comes out grounded (each line traceable to a dumped number or clearly tagged JUDGMENT). This is a followability check of the doc, not a code test — fix any step in the reference that doesn't line up with the real harness output.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/validating-agent-stock/risk-reward-validation.md
git commit -m "docs(validate-skill): risk-reward-validation reference (recipe, qualitative read, traps)"
```

---

### Task 3: `SKILL.md` spine edits

**Files:**
- Modify: `.claude/skills/validating-agent-stock/SKILL.md`

**Interfaces:**
- Consumes: the `risk-reward-validation.md` file created in Task 2 (the pointer must match its name) and the harness `RISK_REWARD` output from Task 1.
- Produces: the updated skill spine. No later task depends on it.

Keep edits lean and surgical — the FV/Quality reasoning stays intact; only add the cross-cutting R-R facts and the pointer. Read the current `SKILL.md` first and match its voice/format.

- [ ] **Step 1: Expand the trigger surface**

In the frontmatter `description`, add R-R triggers so the skill fires on R-R questions — append phrasing like: *…or the newly added Risk-Reward (R-R) ratio ("is X's R-R right?", "why is this a Value Trap?", "does this R-R look fair?")*. In the **"When to use"** list, add a bullet for R-R ratio/tier questions. Leave "When NOT to use" unchanged.

- [ ] **Step 2: Reframe two → three pipelines + core principle**

- Overview (the "two-pipeline Python app" line): change to "three-pipeline" and name Risk-Reward alongside Fair Value and Quality.
- Core principle: add a companion sentence — unlike a fair value (a range around a market/DCF truth), the **R-R ratio is a constructed index with no external market truth**; validate its internal correctness and whether the tier's story matches the company.

- [ ] **Step 3: Add R-R to the codebase map + the two cross-cutting facts**

Add rows to the codebase-map table:
- Risk-Reward — live: `backend/risk_reward/engine.py` → `run(ticker)` → `RiskRewardResult`
- R-R scoring/aggregation: `backend/risk_reward/scoring.py` → `build_metric_scores`, `aggregate`
- R-R config (anchors/weights/tiers/clamp): `backend/risk_reward/config.py`
- R-R persistence (tab + Database col R mirror): `backend/services/risk_reward_sheets.py`

Immediately after the table, add two short facts: R-R is **fully isolated** from Fair Value and Quality Score (an R-R change cannot move an FV/Quality number, and vice-versa — this bounds blast radius), and R-R is **config-driven** (anchors/weights/tiers in `config.py`, so many R-R fixes are a config re-tune with global blast radius).

- [ ] **Step 4: Note the harness now runs three, and add the pointer + cross-reference policy**

- In the "Run one ticker" harness section, note that `validate_ticker.py` now runs all three pipelines and dumps a `RISK_REWARD` block (ratio, tier, reward/risk scores, per-metric `metric_scores`, `raw_snapshot`), with `--inputs` adding `rr_source_inputs`.
- Add a short pointer block: **"Validating a Risk-Reward ratio? Read `risk-reward-validation.md`"** (in this skill dir) — it carries the full R-R recipe, the qualitative read, the traps, and the calibration flow. State the on-demand policy: run the R-R recipe **only when the question is about R-R**; an FV/Quality validation may add a **one-line** R-R cross-reference (ratio + tier from the harness dump) when it is relevant or contradicts the FV/Quality verdict, but does not run the full R-R recipe unprompted.

- [ ] **Step 5: Verify content + that FV/Quality guidance is unchanged**

Re-read `SKILL.md` and confirm:
- The description + "When to use" now fire on R-R questions.
- "two-pipeline" no longer appears (now three); the core principle carries the constructed-index line.
- The codebase map has the four R-R rows; the isolated + config-driven facts are present.
- The harness section mentions the `RISK_REWARD` block; the pointer to `risk-reward-validation.md` and the on-demand + one-line-cross-reference policy are present.
- The existing FV and Quality sections (validation recipe, worked-example rule, optimize flow, common mistakes) are otherwise **unchanged** — no FV/Quality behavior was altered.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/validating-agent-stock/SKILL.md
git commit -m "docs(validate-skill): three-pipeline spine + R-R map, facts, pointer"
```

---

## Notes for the executor

- This plan produces no backend change and runs no `pytest`. Verification is the live harness runs (Task 1 Steps 5–6, Task 2 Step 3) and the documentation checklists (Task 2 Step 2, Task 3 Step 5).
- If a live harness run fails because a chosen ticker's data is unavailable that day, substitute another ticker of the same character (healthy profitable / pre-profit burner) — the point is to exercise the dump shape and reconciliation, not a specific name.
- Do not switch branches. Work stays on `validate-risk-reward`. (An automated memory-snapshot routine has previously switched branches mid-session; if you find yourself on `master`, stop and report.)

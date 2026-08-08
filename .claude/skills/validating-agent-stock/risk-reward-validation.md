# Validating a Risk-Reward Ratio

Risk-Reward (R-R) is Agent Stock's third pipeline (`backend/risk_reward/`). It scores twelve
raw metrics — six **reward** ones, six **risk** ones — onto a 1–5 scale by piecewise-linear
interpolation against a per-metric anchor triple, averages each axis (weighted, renormalized
to whichever metrics actually resolved), and reports `ratio = clamp(reward_score / risk_score,
0.2, 5.0)` mapped to a tier (Asymmetric Upside / Reward-Favored / Balanced / Risk-Favored /
Value Trap). If fewer than 2 reward metrics or fewer than 2 risk metrics resolve, the pipeline
declines with `status = "insufficient_data"` rather than fabricate a ratio from a thin sample
(the coverage floor).

**R-R has no external market truth to check against.** FV can be sanity-checked against a
DCF/market multiple; Quality against fundamentals. R-R's ratio is a self-referential composite
of interpolated scores — there is no independent "correct ratio" for a ticker. Validation is
therefore, in priority order: **(1) internal correctness** — did the pipeline compute what its
own logic says it should from the real inputs — **(2) tier face-validity** — does the
reward-heavy/risk-heavy story the tier tells match the company's actual situation — and
optionally **(3) anchor calibration**, only once a real gap is proven.

Two facts govern every R-R validation:

- **R-R is isolated.** It shares no code path with FV (`valuation/`) or Quality
  (`screener/`) — `backend/risk_reward/` is its own module, its own Sheets column, its own
  failure-isolated gather task. A change here cannot move FV or Quality, and vice versa.
- **R-R is config-driven.** Every anchor, weight, tier boundary, and clamp lives in one file,
  `backend/risk_reward/config.py` (`CONFIG = RiskRewardConfig()`). If a ratio looks wrong,
  the first question is which line in that file produced it.

## The metric roster

All twelve slots, in `REWARD_SLOTS + RISK_SLOTS` order from `config.py`. "Source → fallback"
is the order `sources[slot]` tries; the first source that resolves a real value wins (`chosen`
in `build_metric_scores`). Anchors are `(a5, a3, a1)` — the raw values that map to scores 5, 3,
and 1 respectively (`score_metric` sorts them internally, so direction is whichever way the
values actually order; values beyond the extremes saturate at 1 or 5).

| Slot | Axis | Weight | Source → fallback chain | Anchor `(a5, a3, a1)` per source |
|---|---|---|---|---|
| `valuation` | reward | 0.18 | `peg` → `earnings_yield` (`1/forwardPE`) → `ps_yield` (`1/priceToSalesTrailing12Months`) | peg `(1.0, 1.5, 3.0)` · earnings_yield `(0.08, 0.05, 0.02)` · ps_yield `(0.5, 0.1667, 0.0667)` |
| `growth` | reward | 0.18 | `revenue_growth` (`info.revenueGrowth`) → `earnings_growth` (`info.earningsGrowth`) | both `(0.25, 0.10, 0.0)` |
| `profitability` | reward | 0.12 | `roe` (`returnOnEquity`) → `roa` (`returnOnAssets`) | roe `(0.20, 0.12, 0.05)` · roa `(0.12, 0.06, 0.02)` |
| `analyst_upside` | reward | **dynamic**, see § R-R traps | `analyst_upside` = `(targetMeanPrice − price) / price` | `(0.30, 0.10, 0.0)` |
| `discount` | reward | 0.24 | `discount` = `(high_52w − price) / high_52w` | `(0.25, 0.12, 0.03)` |
| `rsi` | reward | 0.16 | `rsi` (computed series, `RR_RSI_PERIOD` default 14) | `(30.0, 50.0, 70.0)` |
| `leverage` | risk | 0.18 | `debt_to_equity` (`info.debtToEquity`, a **percent**, e.g. `148.804` = 149%) → `net_debt_ebitda` = `(totalDebt − totalCash) / ebitda`, only if `ebitda > 0` | debt_to_equity `(150.0, 90.0, 40.0)` · net_debt_ebitda `(4.0, 2.5, 1.0)` |
| `burn` | risk | 0.15 | `operating_margin` (`operatingMargins`) → `profit_margin` (`profitMargins`) | both `(-0.15, 0.0, 0.15)` |
| `liquidity` | risk | 0.12 | `current_ratio` → `quick_ratio` | both `(0.9, 1.3, 2.0)` |
| `volatility` | risk | 0.22 | `volatility` (annualized σ, `RR_VOL_ANNUALIZATION` default 252, over `RR_HISTORY_PERIOD` default `1y`) | `(0.70, 0.40, 0.20)` |
| `trend` | risk | 0.18 | `trend` = `(price − ma_200) / ma_200` | `(-0.15, 0.0, 0.08)` |
| `beta` | risk | 0.15 | `beta` (`info.beta`) | `(2.0, 1.2, 0.8)` |

**Gotcha to note while reading this table:** `CONFIG.weights["analyst_upside"]` is `0.12`, but
`build_metric_scores` never uses it — for that one slot it always substitutes the
confidence-scaled weight from `_analyst_weight` (§ R-R traps). The `0.12` in `config.py` is
dead for that slot; don't validate against it.

**Coverage floor:** `CONFIG.min_reward = 2` and `CONFIG.min_risk = 2`. `aggregate()` requires
at least 2 active (non-dropped, score-bearing) reward metrics **and** at least 2 active risk
metrics; short of either, it returns `status = "insufficient_data"`, `ratio = None`,
`tier = None` instead of averaging a 1-metric axis into a misleadingly precise number.

## Reconciliation recipe (internal correctness — the priority)

1. **Run the harness.** `python .claude/skills/validating-agent-stock/validate_ticker.py <T>
   --inputs`. Read the `RISK_REWARD` block (`ratio`, `tier`, `reward_score`, `risk_score`,
   `actionable_insight`, `metric_scores`, `raw_snapshot`, `status`, `errors`) and, under
   `--inputs`, `INPUTS.rr_source_inputs` — the raw `info` fields every R-R source extractor
   reads (`pegRatio`, `forwardPE`, `revenueGrowth`, `debtToEquity`, `beta`, …).

2. **Reconcile the composite.** For each axis, `_axis_average` in `risk_reward/scoring.py`
   takes only the metrics with `dropped = False` and `score is not None`, and computes a
   weighted average with **weights renormalized to that active subset** (it does *not*
   divide by 1.0 — it divides by `sum(ms.weight for ms in active)`). So:
   `reward_score = Σ(score·weight over active reward metrics) / Σ(weight over active reward
   metrics)`, and `risk_score` likewise over the risk slots. Then
   `ratio = clamp(reward_score / risk_score, 0.2, 5.0)` (`CONFIG.ratio_clamp`), and
   `tier = tier_for(ratio)` walks `CONFIG.tiers` top-down: `≥2.0` Asymmetric Upside,
   `≥1.3` Reward-Favored, `≥0.8` Balanced, `≥0.5` Risk-Favored, else Value Trap. Recompute
   this by hand from the dumped `metric_scores` and confirm it matches the reported
   `ratio`/`tier` — a mismatch means a bug in the aggregation, not the inputs.

3. **Per-metric check**, for each of the twelve slots: which `source` fired (first one in the
   fallback chain that returned a non-`None`, finite value — check `metric_scores[slot].source`
   against the roster's fallback order), which anchor triple applied (look it up by that
   `source` name, not the slot name — e.g. `valuation` scored via `earnings_yield` uses the
   `earnings_yield` anchors, not `peg`'s), is `raw` right (cross-check `metric_scores[slot].raw`
   against `rr_source_inputs` / restated reality — e.g. is `debtToEquity` really ~149% or is
   it a stale/wrong-basis feed), and is the interpolation correct (hand-check
   `score_metric(raw, a5, a3, a1)` — piecewise-linear between `(a1,1)`, `(a3,3)`, `(a5,5)`,
   saturating past the extremes). Watch for `dropped = True` slots (all sources in the chain
   returned `None`) and whether that pushes an axis toward the coverage floor.

4. **Localize the driver.** Which metric(s) — and which axis — moved the ratio away from
   "Balanced"? Classify the cause: **data** (the raw input feeding the winning source is
   wrong/stale/wrong-basis), **config** (the anchor triple or weight for that slot doesn't
   fit this kind of company), or **logic** (a guard/fallback chose the wrong source, or should
   exist and doesn't — see § R-R traps for the one guard that already exists (negative-PEG)
   and the one that's a known, still-missing gap (M5)).

5. **No-network logic probe.** To test the scoring logic itself on synthetic inputs — no
   yfinance call — build a `risk_reward.models.RiskRewardInputs` by hand and call the two pure
   cores directly:

   ```python
   from risk_reward.models import RiskRewardInputs
   from risk_reward.scoring import build_metric_scores, aggregate

   inp = RiskRewardInputs(
       ticker="TEST", info={"debtToEquity": -50.0, "pegRatio": None, ...},
       company_name=None, price=100.0, high_52w=120.0, ma_200=95.0, ma_50=98.0,
       rsi=45.0, volatility=0.35,
   )
   scores = build_metric_scores(inp)      # dict[slot -> MetricScore]
   agg = aggregate(scores)                # Aggregation(reward, risk, ratio, tier, insight, status)
   ```

   This is the fastest way to pin a hypothesis (e.g. "does a negative `debtToEquity` really
   saturate `leverage` to the safest score?") without waiting on live data.

## The qualitative read (data-grounded + judgment)

Internal correctness (above) tells you the pipeline computed its own formula right. It does
not tell you whether the *story* the tier implies is true of the company. Build that story from
the data already dumped by the harness, then enrich with domain judgment — and **label every
claim `DATA` (traceable to a dumped number) or `JUDGMENT` (analyst knowledge of the business,
sector, or competitive position)**. Never blend the two silently.

- **Reward axis** (`valuation`, `growth`, `profitability`, `analyst_upside`, `discount`,
  `rsi`) → the growth-potential / upside story: is the company actually cheap and growing,
  or is one metric (e.g. a broken `revenueGrowth` feed) dragging reward down/up in a way that
  contradicts the other five?
- **Risk axis** (`leverage`, `burn`, `liquidity`, `volatility`, `trend`, `beta`) → the risks
  and issues: real balance-sheet stress, or a sign artifact / stale feed making a healthy
  company look distressed (or vice versa)?
- **Moat is not an R-R metric.** R-R has no competitive-position slot. Read it from the
  **Quality pipeline's Section II** (capital efficiency: ROIC, ROIC−WACC, ROTE) via the
  harness's `QUALITY.section_scores["II"]` — a low Section II score is `DATA` for "capital
  efficiency is currently weak"; whether that reflects a genuinely narrow moat or a
  temporary build-out phase is `JUDGMENT`.
- **FV inputs** (the harness's `FV` block — `fair_value`, `price_vs_fair_value_pct`,
  `stock_type`) → valuation context: does the FV pipeline's independent verdict (over/under
  fair value) agree or disagree with R-R's reward-heavy/risk-heavy lean? They're isolated
  pipelines reading overlapping raw data, so agreement is corroborating, not circular.

End on the **trustworthiness verdict**: does the tier's reward-heavy / risk-heavy story
*correspond* to this qualitative picture, or is the tier an artifact of one mis-scored metric
that a human would discount?

### Worked illustration (IREN, live dry-run — see § below for the full trace)

- Reward 2.75/5, Risk 4.47/5 → ratio 0.61 → **Risk-Favored**.
- `discount` 5.0/5 and `analyst_upside` 5.0/5 (target mean $81.73 vs price $41.23, +98% implied)
  are `DATA` — the stock trades far below both its 52-week high and consensus target.
- `growth` scored 1.0/5 off `revenueGrowth = -0.0` — `DATA`, but this is the *same* broken
  `info.revenueGrowth` feed the FV pipeline already works around for IREN (memory:
  `iren-opmargin-capex-reroute` — statement revenue growth is actually **+168%**, not 0%).
  So reward's weakest input is a feed artifact, not a real growth problem —
  `JUDGMENT`: reward is probably understated.
- `burn` scored 5.0/5 (worst) off `operatingMargins = -64.5%` — `DATA`, but the *same* memory
  entry documents this figure as broken too (statement operating margin is **+4.4%**). So
  risk's single biggest metric (weight 0.15, near-saturated) is also feed-distorted —
  `JUDGMENT`: risk is probably overstated for the same reason reward is understated.
- `leverage` scored 4.96/5 off `debtToEquity = 148.8%` — `DATA`, and this one is *not* a known
  feed artifact; IREN carries real, heavy debt from its data-center buildout. `JUDGMENT`:
  this part of the risk read is genuine.
- Quality `Section II = 0.75/10` — `DATA` (weak capital efficiency); consistent with a
  capex-heavy, pre-scale infrastructure build-out rather than an established moat —
  `JUDGMENT`.
- FV pipeline (isolated, independent read): `price_vs_fair_value_pct = -43.5%` — `DATA` —
  FV also reads IREN as overvalued at $41.23 (fair value $23.31), which is directional
  agreement with R-R's risk-heavy lean, but via a completely different (DCF/multiples)
  mechanism, not shared code.

**Verdict on this illustration:** the Risk-Favored tier is directionally trustworthy (real
leverage, real FV disagreement) but its exact magnitude is inflated on both legs by the same
known `info` feed artifact (operating margin, revenue growth) — reward is understated and risk
is overstated by the *same* broken input, so the two errors partially offset in the ratio but
neither `metric_scores` entry should be taken as precise. This is exactly the kind of finding
§3 step 4 (localize the driver → classify data vs config vs logic) is for.

## R-R traps

- **Confidence-scaled analyst weight.** `analyst_upside`'s weight is *not* the static
  `0.12` in `config.py` — `build_metric_scores` always computes it as
  `weight = analyst_weight_floor + analyst_weight_span · c = 0.08 + 0.10·c`
  (`_analyst_weight` in `scoring.py`), where `c = min(coverage, agreement)`
  (`_analyst_confidence`): **coverage** ramps 0→1 as `numberOfAnalystOpinions` goes
  `analyst_coverage_lo=3` → `analyst_coverage_hi=20`; **agreement** ramps 1→0 as target-price
  dispersion `(targetHigh − targetLow) / targetMean` goes `analyst_spread_lo=0.20` →
  `analyst_spread_hi=0.80`. **Any missing input (no `numberOfAnalystOpinions`, or a missing/
  inverted target range) collapses its factor to 0**, and `min(coverage, agreement)` then
  collapses `c` to 0 → the weight floor `0.08`. Pre-profit or thin-coverage names sitting at
  the 8% floor is by design, not a bug. Cross-check with `rr_source_inputs`'
  `numberOfAnalystOpinions`, `targetHighPrice`, `targetLowPrice`, `targetMeanPrice`.
- **Coverage floor → N/A** (`status = "insufficient_data"`): fewer than 2 active metrics on
  either axis is a legitimate thin-data outcome — the pipeline correctly refuses to fabricate
  a ratio from 1 metric. Never read this as a defect; confirm which slots dropped and why
  (source chain exhausted) before concluding anything is wrong.
- **Negative-PEG guard (shipped `3963fea`).** The `peg` extractor is
  `_pos(info.get("pegRatio")) or _pos(info.get("trailingPegRatio"))`, and `_pos` returns
  `None` for any non-positive value. A pre-profit name with a negative PEG (negative earnings
  ÷ positive growth) therefore falls through the `valuation` fallback chain to
  `earnings_yield` (or `ps_yield`) instead of being interpolated as if `peg` were a real
  number — which, before the fix, saturated valuation reward at 5.0 (a pre-profit name reading
  as maximally cheap purely from a sign artifact).
- **M5 — KNOWN, UNFIXED GAP.** `leverage`'s primary source `debt_to_equity` has anchors
  `(150.0, 90.0, 40.0)` — `score_metric` sorts these to `(40,1), (90,3), (150,5)`, so any raw
  value `≤ 40` saturates the score at **1 (safest)**. A company with **negative equity**
  reports a negative `debtToEquity` (e.g. `-50`), which is `≤ 40` and therefore scores
  leverage risk as the *safest* possible reading — exactly backwards, since negative equity is
  a severe risk signal, not a benign one. This is the risk-axis mirror of the PEG bug above,
  and it is **not fixed**: the extractor has no `_pos`-style guard, and no fallback to
  `net_debt_ebitda` is forced when `debtToEquity` is negative. Flag it explicitly whenever
  validating a negative-equity name; do not "fix" it as part of an unrelated task without the
  user's buy-in (mirroring the PEG fix — same guard shape, `debt_to_equity` extractor in
  `SOURCE_EXTRACTORS`, `scoring.py` — is the obvious lever if this is ever taken on).
- **Sign artifacts on the risk axis generally.** M5 is one instance of a broader pattern:
  a risk metric built from a ratio with a variable-sign denominator can read a bad situation
  as good. Before trusting any risk-axis score near its saturated extreme, check the sign of
  both the raw value and (where relevant) its denominator — `net_debt_ebitda` shares this
  shape (guarded — `_net_debt_ebitda` returns `None` when `ebitda ≤ 0`, so it's safe — but
  it's the pattern to check on any *new* risk metric).
- **Shared input traps**, as they hit R-R specifically: `info` vs statement basis (IREN's
  `operatingMargins`/`revenueGrowth` above — `-64.5%`/`0%` in `info` vs `+4.4%`/`+168%` in the
  statements), split-distorted history feeding `rsi`/`volatility`/`trend` (all derived from
  price history), and quarterly-vs-annual growth conflated in `revenueGrowth`/`earningsGrowth`
  (yfinance's `revenueGrowth` is quarterly YoY, not annual — same trap the FV pipeline already
  documents).

## Proposing an R-R change (worked-example rule + calibration)

Any proposed R-R change — an anchor, a weight, a guard, a fallback order — is pinned to
concrete, *measured* numbers, exactly like an FV/Quality proposal in the main skill:

- **What changes:** the exact metric / anchor / weight / guard, named by symbol and file
  (e.g. `CONFIG.anchors["debt_to_equity"]` in `backend/risk_reward/config.py`, or a new guard
  in `SOURCE_EXTRACTORS["debt_to_equity"]` in `backend/risk_reward/scoring.py`), its
  **current value → proposed value**.
- **Before → after, measured, not estimated:** re-run `build_metric_scores(inp)` +
  `aggregate(scores)` on the *live* inputs for the ticker in question, with the value/anchor
  swapped via a read-only probe — pass an alternate config (`RiskRewardConfig` is
  `frozen=True`, so `model_copy(update=...)` makes a new instance rather than mutating the
  shared `CONFIG` singleton):

  ```python
  from risk_reward.config import CONFIG
  from risk_reward.scoring import build_metric_scores, aggregate

  scores = build_metric_scores(inp)          # inp = live RiskRewardInputs for the ticker
  before = aggregate(scores)

  probe_cfg = CONFIG.model_copy(update={
      "anchors": {**CONFIG.anchors, "discount": (0.50, 0.12, 0.03)}   # a5: 0.25 -> 0.50
  })
  scores2 = build_metric_scores(inp, cfg=probe_cfg)
  after = aggregate(scores2, cfg=probe_cfg)
  # report: ratio, reward_score, risk_score, tier BEFORE vs AFTER
  ```

  Live-verified on IREN's real inputs (reconstructed from the harness's `--inputs` dump):
  raising the `discount` anchor's `a5` from `0.25` to `0.50` un-saturates its score (IREN's
  raw discount is `0.4636`, previously `≥ a5=0.25` so pinned at `5.0`) —
  `discount` score `5.0 → 4.809`, `reward_score` `2.7474 → 2.6996`, `risk_score` unchanged
  `4.4691`, `ratio` `0.6148 → 0.6041`, **tier unchanged** (`Risk-Favored` in both cases — the
  anchor widening moved the ratio but not far enough to cross the `0.5`/`0.8` tier boundary).
  This is the shape every proposal must report — a change that *doesn't* flip the tier is as
  reportable as one that does. Guessing the direction or magnitude is not acceptable — the
  whole point of the pure cores existing is that this probe is cheap and exact.
- **Blast radius, quantified:**
  - R-R changes are **FV/Quality-neutral** — isolated pipeline, isolated module. State this
    explicitly so the reviewer doesn't go looking for FV/Quality movement that can't happen.
  - An **input lever** (fix a broken/stale/wrong-basis raw value feeding one ticker, e.g. a
    ticker-specific data-source override) has low blast radius — it corrects roughly one
    ticker.
  - A **config lever** (retune an anchor triple, a weight, `ratio_clamp`, a tier boundary, the
    analyst-weight floor/span/coverage/spread knobs) is **GLOBAL** — it runs for every ticker
    that reaches that slot. Sweep a read-only universe pass (same discipline as FV/Quality)
    before proposing it, and confirm the canaries (below) don't regress.
  - A **logic lever** (a new guard/fallback — e.g. the shipped PEG guard, or an eventual M5
    fix) needs the same TDD discipline as an FV/Quality guard.
- **Reuse before inventing:** before adding a new guard shape, check whether an existing one
  already solves a structurally similar problem — the PEG guard (`_pos`, fall through the
  fallback chain on a bad sign) is the template for any future sign-artifact fix, including
  M5.
- **Process, mirroring the main skill:** establish `pytest` green first (`backend/`,
  `asyncio_mode=auto`); TDD the change (failing test pinning the desired
  `build_metric_scores`/`aggregate` behavior → minimal change → full suite green); re-validate
  the target ticker *and* the recurring regression canaries — **IREN, NBIS, KLAC** — with the
  live harness; record the fix in memory (which anchors were tuned against which raw values,
  which tickers were verified unmoved), same as every other Agent Stock fix.

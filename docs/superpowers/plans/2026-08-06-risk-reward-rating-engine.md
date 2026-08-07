# Risk-Reward Rating Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third, fully isolated per-ticker scoring pipeline that rates a stock's reward-versus-risk tradeoff at the current price as a single clamped ratio, shown in the Results and Database grids and computed on every calculation.

**Architecture:** A new `backend/risk_reward/` package (config, models, indicators, scoring, data, engine) computes `Reward ÷ Risk` where each axis is a weighted average of 1–5 interpolated metric scores, with technicals distributed into both axes. It mirrors the existing `screener/` package exactly: its own Sheets tab plus one mirrored Database column, wired as an independent `asyncio.gather` task in `orchestrator/batch._run_one` so its failure can never affect Fair Value or Quality Score. The frontend reads the ratio the same way it reads Quality Score (nested object from batch results, mirrored number from the Database).

**Tech Stack:** Python 3.14, FastAPI, yfinance, pydantic 2.13, pytest (`asyncio_mode=auto`); React + TypeScript + Vite frontend (typecheck via `npm run build`).

## Global Constraints

- **Total isolation from Fair Value and Quality Score.** `risk_reward/` must not import from `valuation/` or `screener/`, and must never read or write the Fair Value or Quality Score columns/cells. A Risk-Reward failure must never fail the FV or Screener pipelines.
- **Defaults to N/A**, never a fabricated number. Thin data → `status="insufficient_data"`, `ratio=None`.
- **Zero hardcoding of thresholds/weights.** All anchors, weights, tier boundaries, clamp, and coverage floor live in `risk_reward/config.py` as one `RiskRewardConfig` object. Operational knobs (RSI period, history window, annualization) read from `os.getenv` in field defaults. (We deliberately use a frozen `pydantic.BaseModel` + `os.getenv` rather than `pydantic-settings`, which is not installed — matches the codebase's existing config idiom and adds no dependency.)
- **All yfinance access goes through `services/yf_pool.run_yf`** (the dedicated pool) — never the default executor.
- **Ratio clamp** `[0.2, 5.0]`, neutral `1.0`. **Coverage floor:** need ≥2 active Reward metrics AND ≥2 active Risk metrics, else N/A.
- **Every commit** appends the two standard trailers (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and `Claude-Session: …`) per the repo's git guidance. Commit commands below omit them for brevity — add them.
- Backend tests run from `backend/` with `python -m pytest`. Frontend changes are verified with `npm run build` from `frontend/`.

---

### Task 1: Config module

**Files:**
- Create: `backend/risk_reward/__init__.py` (empty)
- Create: `backend/risk_reward/config.py`
- Test: `backend/tests/test_risk_reward_config.py`

**Interfaces:**
- Produces:
  - `RiskRewardConfig` (frozen `BaseModel`) with fields: `weights: dict[str, float]`, `axis: dict[str, str]`, `sources: dict[str, list[str]]`, `anchors: dict[str, tuple[float, float, float]]`, `ratio_clamp: tuple[float, float]`, `tiers: list[tuple[float, str]]`, `min_reward: int`, `min_risk: int`, `rsi_period: int`, `vol_annualization: float`, `history_period: str`.
  - `REWARD_SLOTS: list[str]`, `RISK_SLOTS: list[str]` (module constants).
  - `CONFIG: RiskRewardConfig` (module-level singleton).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_config.py
from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS


def test_axis_weights_each_sum_to_one():
    rw = sum(CONFIG.weights[s] for s in REWARD_SLOTS)
    kw = sum(CONFIG.weights[s] for s in RISK_SLOTS)
    assert round(rw, 6) == 1.0
    assert round(kw, 6) == 1.0


def test_every_source_has_anchors_and_every_slot_has_sources():
    for slot in REWARD_SLOTS + RISK_SLOTS:
        assert CONFIG.axis[slot] in ("reward", "risk")
        assert CONFIG.sources[slot], f"{slot} has no source chain"
        for src in CONFIG.sources[slot]:
            assert src in CONFIG.anchors, f"missing anchors for {src}"


def test_clamp_and_floor_defaults():
    assert CONFIG.ratio_clamp == (0.2, 5.0)
    assert CONFIG.min_reward == 2 and CONFIG.min_risk == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_reward'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/risk_reward/config.py
from __future__ import annotations
import os
from pydantic import BaseModel, ConfigDict

REWARD_SLOTS = ["valuation", "growth", "profitability", "analyst_upside", "discount", "rsi"]
RISK_SLOTS = ["leverage", "burn", "liquidity", "volatility", "trend", "beta"]


class RiskRewardConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Per-metric weights within each axis (each axis sums to 1.0).
    weights: dict[str, float] = {
        "valuation": 0.18, "growth": 0.18, "profitability": 0.12,
        "analyst_upside": 0.12, "discount": 0.24, "rsi": 0.16,
        "leverage": 0.18, "burn": 0.15, "liquidity": 0.12,
        "volatility": 0.22, "trend": 0.18, "beta": 0.15,
    }
    axis: dict[str, str] = {
        **{s: "reward" for s in REWARD_SLOTS},
        **{s: "risk" for s in RISK_SLOTS},
    }
    # Fallback chains: the first source that yields a value scores the slot.
    sources: dict[str, list[str]] = {
        "valuation": ["peg", "earnings_yield", "ps_yield"],
        "growth": ["revenue_growth", "earnings_growth"],
        "profitability": ["roe", "roa"],
        "analyst_upside": ["analyst_upside"],
        "discount": ["discount"],
        "rsi": ["rsi"],
        "leverage": ["debt_to_equity", "net_debt_ebitda"],
        "burn": ["operating_margin", "profit_margin"],
        "liquidity": ["current_ratio", "quick_ratio"],
        "volatility": ["volatility"],
        "trend": ["trend"],
        "beta": ["beta"],
    }
    # (a5, a3, a1): the raw values mapping to scores 5, 3, 1. Direction is encoded
    # by the ordering (reward anchors decrease, danger anchors increase).
    anchors: dict[str, tuple[float, float, float]] = {
        "peg": (1.0, 1.5, 3.0),
        "earnings_yield": (0.08, 0.05, 0.02),   # 1/forwardPE
        "ps_yield": (0.5, 0.1667, 0.0667),      # 1/priceToSales
        "revenue_growth": (0.25, 0.10, 0.0),
        "earnings_growth": (0.25, 0.10, 0.0),
        "roe": (0.20, 0.12, 0.05),
        "roa": (0.12, 0.06, 0.02),
        "analyst_upside": (0.30, 0.10, 0.0),
        "discount": (0.25, 0.12, 0.03),
        "rsi": (30.0, 50.0, 70.0),
        "debt_to_equity": (150.0, 90.0, 40.0),  # yfinance reports D/E as a percent
        "net_debt_ebitda": (4.0, 2.5, 1.0),
        "operating_margin": (-0.15, 0.0, 0.15),
        "profit_margin": (-0.15, 0.0, 0.15),
        "current_ratio": (0.9, 1.3, 2.0),
        "quick_ratio": (0.9, 1.3, 2.0),
        "volatility": (0.70, 0.40, 0.20),
        "trend": (-0.15, 0.0, 0.08),
        "beta": (2.0, 1.2, 0.8),
    }
    ratio_clamp: tuple[float, float] = (0.2, 5.0)
    tiers: list[tuple[float, str]] = [
        (2.0, "Asymmetric Upside"), (1.3, "Reward-Favored"),
        (0.8, "Balanced"), (0.5, "Risk-Favored"), (0.0, "Value Trap"),
    ]
    min_reward: int = 2
    min_risk: int = 2
    rsi_period: int = int(os.getenv("RR_RSI_PERIOD", "14"))
    vol_annualization: float = float(os.getenv("RR_VOL_ANNUALIZATION", "252"))
    history_period: str = os.getenv("RR_HISTORY_PERIOD", "1y")


CONFIG = RiskRewardConfig()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/__init__.py backend/risk_reward/config.py backend/tests/test_risk_reward_config.py
git commit -m "feat(risk-reward): config with anchors, weights, tiers"
```

---

### Task 2: Data models

**Files:**
- Create: `backend/risk_reward/models.py`
- Test: `backend/tests/test_risk_reward_models.py`

**Interfaces:**
- Produces:
  - `RiskRewardInputs` (dataclass): `ticker: str`, `info: dict`, `company_name: str | None`, `price: float | None`, `high_52w: float | None`, `ma_200: float | None`, `ma_50: float | None`, `rsi: float | None`, `volatility: float | None`.
  - `MetricScore` (BaseModel): `raw: float | None`, `source: str | None`, `score: float | None`, `weight: float`, `dropped: bool`.
  - `RiskRewardResult` (BaseModel): `ticker`, `company_name`, `current_price`, `last_evaluated`, `ratio`, `tier`, `reward_score`, `risk_score`, `actionable_insight`, `metric_scores: dict[str, MetricScore]`, `raw_snapshot: dict`, `status: Literal["completed","insufficient_data","failed"]`, `errors: list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_models.py
from risk_reward.models import RiskRewardInputs, MetricScore, RiskRewardResult


def test_metric_score_defaults_and_dump():
    ms = MetricScore(raw=1.2, source="peg", score=4.0, weight=0.18, dropped=False)
    assert ms.model_dump()["source"] == "peg"


def test_result_dumps_nested_metric_scores():
    r = RiskRewardResult(
        ticker="AAPL", ratio=1.85, tier="Reward-Favored",
        reward_score=4.1, risk_score=2.2, status="completed",
        metric_scores={"valuation": MetricScore(raw=1.1, source="peg", score=4.2, weight=0.18)},
    )
    d = r.model_dump()
    assert d["metric_scores"]["valuation"]["score"] == 4.2
    assert d["status"] == "completed"


def test_inputs_holds_derived_indicators():
    inp = RiskRewardInputs(ticker="AAPL", info={}, company_name=None, price=100.0,
                           high_52w=130.0, ma_200=110.0, ma_50=105.0, rsi=45.0, volatility=0.3)
    assert inp.ma_200 == 110.0 and inp.rsi == 45.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_reward.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/risk_reward/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel


@dataclass
class RiskRewardInputs:
    ticker: str
    info: dict
    company_name: str | None
    price: float | None
    high_52w: float | None
    ma_200: float | None
    ma_50: float | None
    rsi: float | None
    volatility: float | None


class MetricScore(BaseModel):
    raw: float | None = None
    source: str | None = None
    score: float | None = None
    weight: float = 0.0
    dropped: bool = False


class RiskRewardResult(BaseModel):
    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    last_evaluated: str | None = None
    ratio: float | None = None
    tier: str | None = None
    reward_score: float | None = None
    risk_score: float | None = None
    actionable_insight: str | None = None
    metric_scores: dict[str, MetricScore] = {}
    raw_snapshot: dict = {}
    status: Literal["completed", "insufficient_data", "failed"] = "completed"
    errors: list[str] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/models.py backend/tests/test_risk_reward_models.py
git commit -m "feat(risk-reward): inputs/metric-score/result models"
```

---

### Task 3: Interpolation scorer

**Files:**
- Create: `backend/risk_reward/scoring.py`
- Test: `backend/tests/test_risk_reward_scoring.py`

**Interfaces:**
- Produces: `score_metric(raw: float | None, a5: float, a3: float, a1: float) -> float | None` — linear interpolation across breakpoints `[(a1,1),(a3,3),(a5,5)]`, saturating beyond the extremes, `None` for `None`/`NaN`/non-numeric.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_scoring.py
import math
from risk_reward.scoring import score_metric


def test_exact_anchors_reward_direction():
    # PEG: lower is better -> a5=1.0, a3=1.5, a1=3.0
    assert score_metric(1.0, 1.0, 1.5, 3.0) == 5.0
    assert score_metric(1.5, 1.0, 1.5, 3.0) == 3.0
    assert score_metric(3.0, 1.0, 1.5, 3.0) == 1.0


def test_linear_between_anchors():
    # PRD example: PEG 1.25 -> 4.0
    assert score_metric(1.25, 1.0, 1.5, 3.0) == 4.0


def test_saturates_beyond_extremes():
    assert score_metric(0.2, 1.0, 1.5, 3.0) == 5.0   # cheaper than a5
    assert score_metric(9.0, 1.0, 1.5, 3.0) == 1.0   # pricier than a1


def test_danger_direction_increasing_anchors():
    # D/E: higher is worse -> a5=150, a3=90, a1=40
    assert score_metric(150.0, 150.0, 90.0, 40.0) == 5.0
    assert score_metric(40.0, 150.0, 90.0, 40.0) == 1.0
    assert score_metric(200.0, 150.0, 90.0, 40.0) == 5.0


def test_none_and_nan_return_none():
    assert score_metric(None, 1.0, 1.5, 3.0) is None
    assert score_metric(math.nan, 1.0, 1.5, 3.0) is None
    assert score_metric("x", 1.0, 1.5, 3.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'score_metric'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/risk_reward/scoring.py
from __future__ import annotations


def score_metric(raw, a5: float, a3: float, a1: float) -> float | None:
    """Map a raw metric value to a score in [1, 5] by piecewise-linear interpolation
    across the breakpoints [(a1, 1), (a3, 3), (a5, 5)]. Direction-agnostic: works
    whether higher raw is better (reward) or worse (danger). Values beyond the
    extreme anchors saturate. None/NaN/non-numeric -> None (metric is dropped)."""
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    pts = sorted([(float(a1), 1.0), (float(a3), 3.0), (float(a5), 5.0)])
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return s1
            return s0 + (s1 - s0) * (x - x0) / (x1 - x0)
    return None  # unreachable given the bounds checks above
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_scoring.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/scoring.py backend/tests/test_risk_reward_scoring.py
git commit -m "feat(risk-reward): linear-interpolation metric scorer"
```

---

### Task 4: Technical indicators

**Files:**
- Create: `backend/risk_reward/indicators.py`
- Test: `backend/tests/test_risk_reward_indicators.py`

**Interfaces:**
- Produces (all take an ordered oldest→newest tuple/list of closes):
  - `sma(closes, period: int) -> float | None`
  - `rsi(closes, period: int = 14) -> float | None` (Wilder smoothing)
  - `realized_vol(closes, annualization: float = 252.0) -> float | None` (annualized σ of daily log returns)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_indicators.py
import math
from risk_reward.indicators import sma, rsi, realized_vol


def test_sma_last_n():
    assert sma([1, 2, 3, 4, 5], 3) == 4.0            # mean(3,4,5)
    assert sma([1, 2], 3) is None                     # not enough data


def test_rsi_all_gains_is_100():
    closes = list(range(1, 20))                        # strictly rising
    assert rsi(closes, 14) == 100.0


def test_rsi_needs_period_plus_one():
    assert rsi([1, 2, 3], 14) is None


def test_rsi_midrange_for_alternating():
    closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11]
    val = rsi(closes, 14)
    assert val is not None and 40 <= val <= 60


def test_realized_vol_zero_for_flat_series():
    assert realized_vol([5, 5, 5, 5]) == 0.0


def test_realized_vol_positive_and_annualized():
    closes = [100, 101, 99, 102, 98, 103]
    v = realized_vol(closes, 252)
    assert v is not None and v > 0
    assert realized_vol([100]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_indicators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_reward.indicators'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/risk_reward/indicators.py
from __future__ import annotations
import math
import statistics


def sma(closes, period: int) -> float | None:
    if not closes or len(closes) < period or period <= 0:
        return None
    window = closes[-period:]
    return float(statistics.fmean(window))


def rsi(closes, period: int = 14) -> float | None:
    """Wilder's RSI. Needs at least period+1 closes. Returns 100 when there are no
    losses over the smoothed window, else 100 - 100/(1+RS)."""
    if not closes or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes, closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = statistics.fmean(gains[:period])
    avg_loss = statistics.fmean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def realized_vol(closes, annualization: float = 252.0) -> float | None:
    """Annualized standard deviation of daily log returns. Needs >= 2 closes."""
    if not closes or len(closes) < 2:
        return None
    returns = []
    for prev, cur in zip(closes, closes[1:]):
        if prev and prev > 0 and cur and cur > 0:
            returns.append(math.log(cur / prev))
    if len(returns) < 2:
        return None
    if len(set(returns)) == 1:
        sd = 0.0
    else:
        sd = statistics.stdev(returns)
    return float(sd * math.sqrt(annualization))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_indicators.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/indicators.py backend/tests/test_risk_reward_indicators.py
git commit -m "feat(risk-reward): SMA/RSI/realized-vol indicators"
```

---

### Task 5: Metric extraction

**Files:**
- Modify: `backend/risk_reward/scoring.py` (add extraction below `score_metric`)
- Test: `backend/tests/test_risk_reward_extraction.py`

**Interfaces:**
- Consumes: `RiskRewardInputs`, `MetricScore` (Task 2); `score_metric` (Task 3); `CONFIG`, `REWARD_SLOTS`, `RISK_SLOTS` (Task 1).
- Produces:
  - `SOURCE_EXTRACTORS: dict[str, Callable[[RiskRewardInputs], float | None]]` — one extractor per source key in `CONFIG.anchors`.
  - `build_metric_scores(inp: RiskRewardInputs, cfg: RiskRewardConfig = CONFIG) -> dict[str, MetricScore]` — one entry per slot in `REWARD_SLOTS + RISK_SLOTS`; walks the slot's source chain, scores the first non-None raw with that source's anchors, and marks the slot `dropped=True` (score/raw/source None) when the whole chain misses.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_extraction.py
from risk_reward.models import RiskRewardInputs
from risk_reward.scoring import build_metric_scores


def _inputs(info=None, **kw):
    base = dict(ticker="X", info=info or {}, company_name=None, price=100.0,
                high_52w=130.0, ma_200=110.0, ma_50=105.0, rsi=35.0, volatility=0.30)
    base.update(kw)
    return RiskRewardInputs(**base)


def test_valuation_uses_peg_when_present():
    ms = build_metric_scores(_inputs(info={"pegRatio": 1.0}))
    assert ms["valuation"].source == "peg"
    assert ms["valuation"].score == 5.0
    assert ms["valuation"].dropped is False


def test_valuation_falls_back_to_earnings_yield():
    # no PEG, forwardPE 12.5 -> earnings yield 0.08 -> score 5
    ms = build_metric_scores(_inputs(info={"forwardPE": 12.5}))
    assert ms["valuation"].source == "earnings_yield"
    assert ms["valuation"].score == 5.0


def test_slot_dropped_when_no_source_resolves():
    ms = build_metric_scores(_inputs(info={}))
    assert ms["valuation"].dropped is True
    assert ms["valuation"].score is None
    assert ms["valuation"].weight > 0  # weight retained for reference


def test_discount_and_trend_from_price_and_ma():
    ms = build_metric_scores(_inputs(info={}))
    # discount = (130-100)/130 = 0.2308 -> between a3=0.12 and a5=0.25 -> ~4.6
    assert ms["discount"].source == "discount"
    assert 4.0 <= ms["discount"].score <= 5.0
    # trend = (100-110)/110 = -0.0909 -> between a3=0 and a5=-0.15 (danger) -> ~4.2
    assert ms["trend"].source == "trend"
    assert ms["trend"].score is not None


def test_leverage_percent_debt_to_equity():
    ms = build_metric_scores(_inputs(info={"debtToEquity": 150.0}))
    assert ms["leverage"].source == "debt_to_equity"
    assert ms["leverage"].score == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_extraction.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_metric_scores'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/risk_reward/scoring.py`:

```python
from collections.abc import Callable
from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS, RiskRewardConfig
from risk_reward.models import RiskRewardInputs, MetricScore


def _pos(v):
    """Return v as float if it is a positive finite number, else None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f > 0 else None


def _ratio(num, den):
    d = _pos(den)
    return (num / d) if (d is not None and num is not None) else None


SOURCE_EXTRACTORS: dict[str, Callable[[RiskRewardInputs], float | None]] = {
    # reward
    "peg": lambda i: i.info.get("pegRatio") or i.info.get("trailingPegRatio"),
    "earnings_yield": lambda i: _ratio(1.0, i.info.get("forwardPE")),
    "ps_yield": lambda i: _ratio(1.0, i.info.get("priceToSalesTrailing12Months")),
    "revenue_growth": lambda i: i.info.get("revenueGrowth"),
    "earnings_growth": lambda i: i.info.get("earningsGrowth"),
    "roe": lambda i: i.info.get("returnOnEquity"),
    "roa": lambda i: i.info.get("returnOnAssets"),
    "analyst_upside": lambda i: _ratio((i.info.get("targetMeanPrice") or 0) - (i.price or 0), i.price)
                                if i.info.get("targetMeanPrice") and i.price else None,
    "discount": lambda i: ((i.high_52w - i.price) / i.high_52w)
                          if (i.high_52w and i.price and i.high_52w > 0) else None,
    "rsi": lambda i: i.rsi,
    # risk
    "debt_to_equity": lambda i: i.info.get("debtToEquity"),
    "net_debt_ebitda": lambda i: _net_debt_ebitda(i),
    "operating_margin": lambda i: i.info.get("operatingMargins"),
    "profit_margin": lambda i: i.info.get("profitMargins"),
    "current_ratio": lambda i: i.info.get("currentRatio"),
    "quick_ratio": lambda i: i.info.get("quickRatio"),
    "volatility": lambda i: i.volatility,
    "trend": lambda i: ((i.price - i.ma_200) / i.ma_200)
                       if (i.price and i.ma_200 and i.ma_200 > 0) else None,
    "beta": lambda i: i.info.get("beta"),
}


def _net_debt_ebitda(i: RiskRewardInputs):
    ebitda = i.info.get("ebitda")
    if not ebitda or ebitda <= 0:
        return None
    total_debt = i.info.get("totalDebt") or 0
    total_cash = i.info.get("totalCash") or 0
    return (total_debt - total_cash) / ebitda


def build_metric_scores(inp: RiskRewardInputs,
                        cfg: RiskRewardConfig = CONFIG) -> dict[str, MetricScore]:
    out: dict[str, MetricScore] = {}
    for slot in REWARD_SLOTS + RISK_SLOTS:
        weight = cfg.weights[slot]
        chosen = None
        for src in cfg.sources[slot]:
            raw = SOURCE_EXTRACTORS[src](inp)
            score = score_metric(raw, *cfg.anchors[src])
            if score is not None:
                chosen = MetricScore(raw=float(raw), source=src, score=score,
                                     weight=weight, dropped=False)
                break
        out[slot] = chosen or MetricScore(raw=None, source=None, score=None,
                                          weight=weight, dropped=True)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_extraction.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/scoring.py backend/tests/test_risk_reward_extraction.py
git commit -m "feat(risk-reward): metric extraction with fallback chains"
```

---

### Task 6: Axis aggregation → ratio, tier, insight

**Files:**
- Modify: `backend/risk_reward/scoring.py` (add aggregation below extraction)
- Test: `backend/tests/test_risk_reward_aggregation.py`

**Interfaces:**
- Consumes: `MetricScore` dict from `build_metric_scores` (Task 5); `CONFIG`, `REWARD_SLOTS`, `RISK_SLOTS` (Task 1).
- Produces:
  - `Aggregation` (dataclass): `reward: float | None`, `risk: float | None`, `ratio: float | None`, `tier: str | None`, `insight: str | None`, `status: str` (`"completed"` or `"insufficient_data"`).
  - `tier_for(ratio: float, cfg: RiskRewardConfig = CONFIG) -> str`
  - `aggregate(scores: dict[str, MetricScore], cfg: RiskRewardConfig = CONFIG) -> Aggregation`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_aggregation.py
from risk_reward.models import MetricScore
from risk_reward.config import REWARD_SLOTS, RISK_SLOTS, CONFIG
from risk_reward.scoring import aggregate, tier_for


def _scores(reward_val, risk_val, n_reward=6, n_risk=6):
    out = {}
    for idx, slot in enumerate(REWARD_SLOTS):
        dropped = idx >= n_reward
        out[slot] = MetricScore(raw=1.0, source="x", score=None if dropped else reward_val,
                                weight=CONFIG.weights[slot], dropped=dropped)
    for idx, slot in enumerate(RISK_SLOTS):
        dropped = idx >= n_risk
        out[slot] = MetricScore(raw=1.0, source="x", score=None if dropped else risk_val,
                                weight=CONFIG.weights[slot], dropped=dropped)
    return out


def test_ratio_reward_over_risk():
    agg = aggregate(_scores(4.0, 2.0))
    assert agg.status == "completed"
    assert round(agg.reward, 3) == 4.0 and round(agg.risk, 3) == 2.0
    assert round(agg.ratio, 3) == 2.0
    assert agg.tier == "Asymmetric Upside"


def test_clamp_upper_and_lower():
    assert aggregate(_scores(5.0, 1.0)).ratio == 5.0    # 5.0 exactly at clamp
    assert aggregate(_scores(1.0, 5.0)).ratio == 0.2    # 0.2 at clamp


def test_renormalizes_when_metrics_dropped():
    # only 3 reward + 3 risk active, all equal -> averages unaffected, still scored
    agg = aggregate(_scores(3.0, 3.0, n_reward=3, n_risk=3))
    assert agg.status == "completed"
    assert round(agg.ratio, 3) == 1.0
    assert agg.tier == "Balanced"


def test_coverage_floor_reward():
    agg = aggregate(_scores(4.0, 2.0, n_reward=1, n_risk=6))
    assert agg.status == "insufficient_data"
    assert agg.ratio is None and agg.tier is None


def test_coverage_floor_risk():
    agg = aggregate(_scores(4.0, 2.0, n_reward=6, n_risk=1))
    assert agg.status == "insufficient_data"


def test_tier_boundaries():
    assert tier_for(2.0) == "Asymmetric Upside"
    assert tier_for(1.3) == "Reward-Favored"
    assert tier_for(0.8) == "Balanced"
    assert tier_for(0.5) == "Risk-Favored"
    assert tier_for(0.3) == "Value Trap"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_aggregation.py -v`
Expected: FAIL with `ImportError: cannot import name 'aggregate'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/risk_reward/scoring.py`:

```python
from dataclasses import dataclass


@dataclass
class Aggregation:
    reward: float | None
    risk: float | None
    ratio: float | None
    tier: str | None
    insight: str | None
    status: str


def _axis_average(scores, slots) -> tuple[float | None, int]:
    """Weighted average over the active (non-dropped) metrics in `slots`, with the
    active weights renormalized to sum to 1. Returns (average, active_count)."""
    active = [scores[s] for s in slots if not scores[s].dropped and scores[s].score is not None]
    total_w = sum(ms.weight for ms in active)
    if not active or total_w <= 0:
        return None, len(active)
    avg = sum(ms.score * ms.weight for ms in active) / total_w
    return avg, len(active)


def tier_for(ratio: float, cfg: RiskRewardConfig = CONFIG) -> str:
    for floor, label in cfg.tiers:
        if ratio >= floor:
            return label
    return cfg.tiers[-1][1]


def _insight(tier: str, reward: float, risk: float) -> str:
    lean = "reward outweighs risk" if reward >= risk else "risk outweighs reward"
    return f"{tier}: {lean} (reward {reward:.1f} vs risk {risk:.1f} on a 1-5 scale)."


def aggregate(scores: dict[str, MetricScore],
              cfg: RiskRewardConfig = CONFIG) -> Aggregation:
    reward, n_reward = _axis_average(scores, REWARD_SLOTS)
    risk, n_risk = _axis_average(scores, RISK_SLOTS)
    if n_reward < cfg.min_reward or n_risk < cfg.min_risk or reward is None or risk is None:
        return Aggregation(reward=reward, risk=risk, ratio=None, tier=None,
                           insight=None, status="insufficient_data")
    lo, hi = cfg.ratio_clamp
    ratio = max(lo, min(hi, reward / risk))
    tier = tier_for(ratio, cfg)
    return Aggregation(reward=reward, risk=risk, ratio=ratio, tier=tier,
                       insight=_insight(tier, reward, risk), status="completed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_aggregation.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/scoring.py backend/tests/test_risk_reward_aggregation.py
git commit -m "feat(risk-reward): axis aggregation, clamp, tiers, coverage floor"
```

---

### Task 7: Data fetch

**Files:**
- Modify: `backend/services/statements.py` (add `fetch_price_daily`)
- Create: `backend/risk_reward/data.py`
- Test: `backend/tests/test_risk_reward_data.py`

**Interfaces:**
- Consumes: `RiskRewardInputs` (Task 2); `sma`, `rsi`, `realized_vol` (Task 4); `CONFIG` (Task 1); `services.yahoo.fetch_ticker_info`, `services.yf_pool.run_yf`.
- Produces:
  - `services.statements.fetch_price_daily(ticker: str) -> tuple[float, ...]` — oldest→newest daily closes over `CONFIG.history_period` (best-effort; empty tuple on failure).
  - `risk_reward.data.fetch_risk_reward_inputs(ticker: str) -> RiskRewardInputs | None` — `None` only when the info fetch itself fails.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_data.py
import pytest
from unittest.mock import patch
from risk_reward import data
from risk_reward.models import RiskRewardInputs

_CLOSES = tuple(float(x) for x in range(1, 261))  # 260 rising closes


@pytest.mark.asyncio
async def test_assembles_inputs_and_indicators():
    info = {"symbol": "AAPL", "shortName": "Apple", "currentPrice": 260.0,
            "fiftyTwoWeekHigh": 300.0}
    with patch("risk_reward.data.fetch_ticker_info", return_value=info), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES):
        inp = await data.fetch_risk_reward_inputs("AAPL")
    assert isinstance(inp, RiskRewardInputs)
    assert inp.price == 260.0 and inp.high_52w == 300.0
    assert inp.ma_200 is not None and inp.ma_50 is not None
    assert inp.rsi == 100.0            # strictly rising series
    assert inp.volatility is not None


@pytest.mark.asyncio
async def test_price_and_high_fall_back_to_history():
    with patch("risk_reward.data.fetch_ticker_info", return_value={"symbol": "X"}), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES):
        inp = await data.fetch_risk_reward_inputs("X")
    assert inp.price == 260.0          # last close
    assert inp.high_52w == 260.0       # max close


@pytest.mark.asyncio
async def test_returns_none_when_info_fetch_fails():
    with patch("risk_reward.data.fetch_ticker_info", side_effect=RuntimeError("boom")):
        inp = await data.fetch_risk_reward_inputs("X")
    assert inp is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_reward.data'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/services/statements.py` (next to `fetch_price_monthly`):

```python
def fetch_price_daily(ticker: str, period: str = "1y") -> tuple[float, ...]:
    """Oldest->newest daily closes over `period` (best-effort). Mirrors
    fetch_price_monthly but at daily interval for the Risk-Reward indicators."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d", timeout=_HISTORY_TIMEOUT)
        if hist is None or hist.empty:
            return tuple()
        return tuple(float(x) for x in hist["Close"].tolist() if x == x)
    except Exception:
        return tuple()
```

Create `backend/risk_reward/data.py`:

```python
from __future__ import annotations
from services.yahoo import fetch_ticker_info
from services.statements import fetch_price_daily
from services.yf_pool import run_yf
from risk_reward.config import CONFIG
from risk_reward.indicators import sma, rsi, realized_vol
from risk_reward.models import RiskRewardInputs


async def fetch_risk_reward_inputs(ticker: str) -> RiskRewardInputs | None:
    t = ticker.upper()
    try:
        info = await fetch_ticker_info(t)
    except Exception:
        return None

    closes = await run_yf(fetch_price_daily, t, CONFIG.history_period)
    last_close = closes[-1] if closes else None
    price = info.get("currentPrice") or info.get("regularMarketPrice") or last_close
    high_52w = info.get("fiftyTwoWeekHigh") or (max(closes) if closes else None)

    return RiskRewardInputs(
        ticker=t, info=info,
        company_name=info.get("shortName") or info.get("longName"),
        price=price, high_52w=high_52w,
        ma_200=sma(closes, 200), ma_50=sma(closes, 50),
        rsi=rsi(closes, CONFIG.rsi_period),
        volatility=realized_vol(closes, CONFIG.vol_annualization),
    )
```

Note: `run_yf(fetch_price_daily, t, CONFIG.history_period)` passes the period through; confirm `run_yf` forwards *args (it does — it wraps `loop.run_in_executor`). The test patches `risk_reward.data.fetch_price_daily` and `fetch_ticker_info`, so `run_yf` runs the mock in the pool.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_data.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/statements.py backend/risk_reward/data.py backend/tests/test_risk_reward_data.py
git commit -m "feat(risk-reward): daily-history fetch + inputs assembly"
```

---

### Task 8: Engine `run(ticker)`

**Files:**
- Create: `backend/risk_reward/engine.py`
- Test: `backend/tests/test_risk_reward_engine.py`

**Interfaces:**
- Consumes: `fetch_risk_reward_inputs` (Task 7); `build_metric_scores`, `aggregate` (Tasks 5–6); `RiskRewardResult` (Task 2).
- Produces: `run(ticker: str) -> RiskRewardResult` (async). `status="failed"` when inputs can't be fetched; `"insufficient_data"` when the coverage floor isn't met; `"completed"` otherwise. Mirrors `screener.engine.run`'s shape.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_engine.py
import pytest
from unittest.mock import patch
from risk_reward import engine
from risk_reward.models import RiskRewardInputs


def _inputs(info):
    return RiskRewardInputs(ticker="X", info=info, company_name="X Corp", price=100.0,
                            high_52w=130.0, ma_200=110.0, ma_50=105.0, rsi=35.0, volatility=0.30)


_RICH = {"pegRatio": 1.1, "revenueGrowth": 0.22, "returnOnEquity": 0.19,
         "targetMeanPrice": 130.0, "debtToEquity": 60.0, "operatingMargins": 0.20,
         "currentRatio": 1.8, "beta": 1.1}


@pytest.mark.asyncio
async def test_completed_result_has_ratio_and_tier():
    with patch("risk_reward.engine.fetch_risk_reward_inputs", return_value=_inputs(_RICH)):
        res = await engine.run("X")
    assert res.status == "completed"
    assert res.ratio is not None and res.tier is not None
    assert res.reward_score is not None and res.risk_score is not None
    assert res.raw_snapshot.get("current_price") == 100.0
    assert res.company_name == "X Corp"


@pytest.mark.asyncio
async def test_insufficient_data_when_thin():
    # only one reward source (peg) and one risk source (beta) resolve
    with patch("risk_reward.engine.fetch_risk_reward_inputs",
               return_value=RiskRewardInputs(ticker="X", info={"pegRatio": 1.1, "beta": 1.1},
                   company_name=None, price=None, high_52w=None, ma_200=None,
                   ma_50=None, rsi=None, volatility=None)):
        res = await engine.run("X")
    assert res.status == "insufficient_data"
    assert res.ratio is None


@pytest.mark.asyncio
async def test_failed_when_inputs_none():
    with patch("risk_reward.engine.fetch_risk_reward_inputs", return_value=None):
        res = await engine.run("X")
    assert res.status == "failed"
    assert res.errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_reward.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/risk_reward/engine.py
from __future__ import annotations
from datetime import datetime, timezone
from risk_reward.data import fetch_risk_reward_inputs
from risk_reward.scoring import build_metric_scores, aggregate
from risk_reward.models import RiskRewardResult


def _snapshot(inp) -> dict:
    de = inp.info.get("debtToEquity")
    return {
        "current_price": inp.price,
        "peg_ratio": inp.info.get("pegRatio") or inp.info.get("trailingPegRatio"),
        "debt_to_equity": de,
        "rsi": inp.rsi,
        "volatility": inp.volatility,
        "dist_from_200ma_pct": ((inp.price - inp.ma_200) / inp.ma_200 * 100)
                               if (inp.price and inp.ma_200 and inp.ma_200 > 0) else None,
        "dist_from_52w_high_pct": ((inp.high_52w - inp.price) / inp.high_52w * 100)
                                  if (inp.high_52w and inp.price and inp.high_52w > 0) else None,
    }


async def run(ticker: str) -> RiskRewardResult:
    t = ticker.upper()
    inp = await fetch_risk_reward_inputs(t)
    if inp is None:
        return RiskRewardResult(ticker=t, status="failed",
                                errors=["yfinance data unavailable"])
    scores = build_metric_scores(inp)
    agg = aggregate(scores)
    now = datetime.now(timezone.utc).isoformat()
    return RiskRewardResult(
        ticker=t, company_name=inp.company_name, current_price=inp.price,
        last_evaluated=now, ratio=agg.ratio, tier=agg.tier,
        reward_score=agg.reward, risk_score=agg.risk,
        actionable_insight=agg.insight, metric_scores=scores,
        raw_snapshot=_snapshot(inp), status=agg.status, errors=[],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_engine.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/risk_reward/engine.py backend/tests/test_risk_reward_engine.py
git commit -m "feat(risk-reward): engine run(ticker) -> RiskRewardResult"
```

---

### Task 9: Sheets persistence (tab + Database mirror)

**Files:**
- Create: `backend/services/risk_reward_sheets.py`
- Modify: `backend/routers/database.py` (also delete the Risk-Reward row on ticker delete)
- Test: `backend/tests/test_risk_reward_sheets.py`

**Interfaces:**
- Consumes: `RiskRewardResult` (Task 2); `services.sheets` helpers `_get_service`, `_sheet_id`, `_execute`, `_run_sheets`, `delete_ticker_row`.
- Produces:
  - `upsert_risk_reward_result(r: RiskRewardResult) -> None` (async) — writes the `Risk-Reward` tab row and mirrors the ratio to Database column `R`.
  - `read_risk_reward() -> list[RiskRewardResult]`, `read_risk_reward_one(ticker) -> RiskRewardResult | None`.
  - `delete_risk_reward_row(ticker) -> bool`.
  - `DATABASE_RR_COL = "R"`, `_RR_TAB = "Risk-Reward"`.

Study `backend/services/screener_sheets.py` first — this task mirrors its structure (`_result_to_row`, `_row_to_result`, `_ensure_*_sheet`, `_col_range`, `_upsert_sync`, `_mirror_*`). Key difference: the mirror target column is `R` (Q is the Quality Score mirror), and the row schema is the Risk-Reward fields.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_reward_sheets.py
from risk_reward.models import RiskRewardResult, MetricScore
from services import risk_reward_sheets as rrs


def test_row_round_trip_preserves_ratio_and_tier():
    r = RiskRewardResult(
        ticker="AAPL", company_name="Apple", last_evaluated="2026-08-06T00:00:00Z",
        ratio=1.85, tier="Reward-Favored", reward_score=4.1, risk_score=2.2,
        actionable_insight="ok", status="completed",
        metric_scores={"valuation": MetricScore(raw=1.1, source="peg", score=4.2, weight=0.18)},
        raw_snapshot={"current_price": 175.4},
    )
    row = rrs._result_to_row(r)
    back = rrs._row_to_result(row)
    assert back.ticker == "AAPL"
    assert back.ratio == 1.85
    assert back.tier == "Reward-Favored"
    assert back.reward_score == 4.1 and back.risk_score == 2.2


def test_na_result_writes_blank_ratio():
    r = RiskRewardResult(ticker="X", status="insufficient_data")
    row = rrs._result_to_row(r)
    back = rrs._row_to_result(row)
    assert back.ratio is None


def test_mirror_column_is_R():
    assert rrs.DATABASE_RR_COL == "R"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_risk_reward_sheets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.risk_reward_sheets'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/risk_reward_sheets.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from risk_reward.models import RiskRewardResult, MetricScore
from services.sheets import (
    _get_service, _sheet_id, _execute, _run_sheets, delete_ticker_row,
)

_RR_TAB = "Risk-Reward"
DATABASE_RR_COL = "R"

_HEADERS = [
    "Ticker", "Company", "Last Evaluated", "Ratio", "Tier",
    "Reward Score", "Risk Score", "Actionable Insight",
    "Metric Scores", "Raw Snapshot", "Status",
]


def _num(v):
    return v if isinstance(v, (int, float)) else ""


def _result_to_row(r: RiskRewardResult) -> list:
    ms = {k: v.model_dump() for k, v in (r.metric_scores or {}).items()}
    return [
        r.ticker, r.company_name or "",
        r.last_evaluated or datetime.now(timezone.utc).isoformat(),
        _num(r.ratio), r.tier or "", _num(r.reward_score), _num(r.risk_score),
        r.actionable_insight or "", json.dumps(ms), json.dumps(r.raw_snapshot or {}),
        r.status,
    ]


def _to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


def _parse_json(v) -> dict:
    if not v:
        return {}
    try:
        p = json.loads(v)
        return p if isinstance(p, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_to_result(row: list) -> RiskRewardResult:
    row = list(row) + [""] * (len(_HEADERS) - len(row))
    ms = {k: MetricScore(**v) for k, v in _parse_json(row[8]).items()}
    return RiskRewardResult(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        ratio=_to_float(row[3]), tier=row[4] or None,
        reward_score=_to_float(row[5]), risk_score=_to_float(row[6]),
        actionable_insight=row[7] or None, metric_scores=ms,
        raw_snapshot=_parse_json(row[9]), status=row[10] or "completed",
    )


def _col_range() -> str:
    end = chr(ord("A") + len(_HEADERS) - 1)  # 11 cols -> "K"
    return f"{_RR_TAB}!A:{end}"


def _ensure_rr_sheet(svc, sheet_id: str) -> None:
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    props = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
    if _RR_TAB not in props:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _RR_TAB}}}]}))
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
            valueInputOption="RAW", body={"values": [_HEADERS]}))
        return
    first = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!1:1")).get("values", [])
    row1 = first[0] if first else []
    if row1 and row1[0] == _HEADERS[0]:
        if row1 != _HEADERS:
            _execute(svc.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
                valueInputOption="RAW", body={"values": [_HEADERS]}))
        return
    if row1:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {"range": {
                "sheetId": props[_RR_TAB]["sheetId"], "dimension": "ROWS",
                "startIndex": 0, "endIndex": 1}, "inheritFromBefore": False}}]}))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
        valueInputOption="RAW", body={"values": [_HEADERS]}))


def _mirror_ratio(svc, sheet_id: str, ticker: str, ratio) -> None:
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"Database!{DATABASE_RR_COL}1",
        valueInputOption="RAW", body={"values": [["Risk-Reward"]]}))
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A")).get("values", [])
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == ticker.upper():
            _execute(svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"Database!{DATABASE_RR_COL}{i + 1}",
                valueInputOption="RAW", body={"values": [[_num(ratio)]]}))
            return


def _upsert_sync(r: RiskRewardResult) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_rr_sheet(svc, sheet_id)
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!A:A")).get("values", [])
    target = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == r.ticker.upper():
            target = i + 1
            break
    new_row = _result_to_row(r)
    if target is None:
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A:A",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}))
    else:
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A{target}",
            valueInputOption="RAW", body={"values": [new_row]}))
    _mirror_ratio(svc, sheet_id, r.ticker, r.ratio)


async def upsert_risk_reward_result(r: RiskRewardResult) -> None:
    await _run_sheets(_upsert_sync, r)


def _read_sync() -> list[RiskRewardResult]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=_col_range()))
    except Exception as e:
        if "Unable to parse range" in str(e):
            _ensure_rr_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    return [_row_to_result(r) for r in rows[1:]] if len(rows) >= 2 else []


async def read_risk_reward() -> list[RiskRewardResult]:
    return await _run_sheets(_read_sync)


async def read_risk_reward_one(ticker: str) -> RiskRewardResult | None:
    for r in await read_risk_reward():
        if r.ticker.upper() == ticker.upper():
            return r
    return None


async def delete_risk_reward_row(ticker: str) -> bool:
    return await delete_ticker_row(_RR_TAB, ticker)
```

Then wire the delete into `backend/routers/database.py`:

```python
# add to imports
from services.risk_reward_sheets import read_risk_reward_one, delete_risk_reward_row

# inside delete_ticker(...), extend the removed dict:
            "risk_reward": await delete_risk_reward_row(t),

# add a read endpoint mirroring get_screener:
@router.get("/risk-reward/{ticker}")
async def get_risk_reward(ticker: str):
    try:
        r = await read_risk_reward_one(ticker)
        if r is None:
            return {"error": f"No risk-reward record for {ticker.upper()}"}
        return r.model_dump()
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_risk_reward_sheets.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/risk_reward_sheets.py backend/routers/database.py backend/tests/test_risk_reward_sheets.py
git commit -m "feat(risk-reward): Sheets tab + Database column-R mirror + delete wiring"
```

---

> **Endpoint — reconciling spec §11 (deliberate deviation).** Spec §11 called for a
> compute-on-demand `GET /api/analysis/risk-reward/{ticker}` in `routers/analysis.py`
> plus a reserved `sector_override` param. The plan instead ships a **read** endpoint
> `GET /api/risk-reward/{ticker}` in `routers/database.py` (Task 9), for three reasons:
> (1) it mirrors the existing Screener read `GET /api/screener/{ticker}` — which also
> lives in `database.py` and reads persisted rows — so the frontend detail page consumes
> Risk-Reward exactly as it consumes the Screener, with no expensive recompute on every
> tab open; (2) compute-on-demand is already provided by `POST /ticker/{ticker}/recalculate`,
> which flows through `_run_one` and, after Task 11, computes, persists, **and returns**
> the `risk_reward` payload; (3) `sector_override` is a spec §14 "future / not in v1"
> item (accepted but unused), so it is intentionally omitted from v1. Net effect: the
> spec's user-facing capability (fetch a ticker's Risk-Reward on demand) is fully covered;
> only the route shape and read-vs-recompute split differ, chosen for codebase consistency.
> There is no separate endpoint task; the frontend tasks below consume `GET /api/risk-reward/{ticker}`.

### Task 10: Database read — column R → `DatabaseRow.risk_reward_ratio`

**Files:**
- Modify: `backend/models.py:24-25` (`DatabaseRow`)
- Modify: `backend/services/sheets.py:241-260` (`_row_to_database_row`), `backend/services/sheets.py:263-279` (`_read_database_sync` range)
- Test: `backend/tests/test_sheets_rr_read.py`

**Interfaces:**
- Consumes: the Database column-`R` mirror written by `upsert_risk_reward_result` (Task 9).
- Produces: `DatabaseRow.risk_reward_ratio: float | None`; `read_database()` now populates it. The `/api/database` grid payload (`routers/database.py:get_database`) carries `risk_reward_ratio` on every row for the Database grid (Task 13).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_sheets_rr_read.py`:

```python
from services.sheets import _row_to_database_row


def test_database_row_parses_risk_reward_ratio_from_col_r():
    # 7 identity/valuation cols (0-6) + 9 model cols (7-15) + Q quality (16) + R ratio (17)
    row = ["AAPL", "Apple", "2026-01-01", "GROWTH", "200", "180", "10",
           "", "", "", "", "", "", "", "", "",        # 9 model columns
           "8.5",                                       # col Q — quality score
           "1.85"]                                      # col R — risk-reward ratio
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio == 1.85
    assert dr.quality_score == 8.5


def test_database_row_missing_risk_reward_is_none():
    # A legacy short row (pre-Risk-Reward) must pad cleanly to None, not IndexError.
    row = ["MSFT", "Microsoft", "2026-01-01", "GROWTH", "300", "290", "3"]
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio is None
    assert dr.quality_score is None


def test_database_row_blank_risk_reward_cell_is_none():
    row = ["NBIS", "Nebius", "2026-01-01", "EARLY_GROWTH", "", "100", "",
           "", "", "", "", "", "", "", "", "", "7.0", ""]  # col R blank (N/A)
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sheets_rr_read.py -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'risk_reward_ratio'` (field not yet on `DatabaseRow`) / index padding stops at 17.

- [ ] **Step 3: Write minimal implementation**

In `backend/models.py`, extend `DatabaseRow`:

```python
class DatabaseRow(TickerResult):
    quality_score: float | None = None
    risk_reward_ratio: float | None = None
```

In `backend/services/sheets.py`, widen the pad and parse col R (index 17) in `_row_to_database_row`:

```python
def _row_to_database_row(row: list) -> DatabaseRow:
    row = list(row) + [""] * (18 - len(row))  # pad to include col R (index 17)

    def safe_float(val):
        try:
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    breakdown = {}
    for i, mid in enumerate(_MODEL_COLS):
        fv = safe_float(row[7 + i])
        if fv is not None:
            breakdown[mid] = {"fair_value": fv}
    return DatabaseRow(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        stock_type=row[3] or None, fair_value=safe_float(row[4]),
        current_price=safe_float(row[5]), price_vs_fair_value_pct=safe_float(row[6]),
        fair_value_breakdown=breakdown, quality_score=safe_float(row[16]),
        risk_reward_ratio=safe_float(row[17]),
    )
```

And widen the read range in `_read_database_sync`:

```python
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Database!A:R",      # was A:Q — now includes the Risk-Reward mirror
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sheets_rr_read.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/services/sheets.py backend/tests/test_sheets_rr_read.py
git commit -m "feat(risk-reward): read Database column-R mirror into DatabaseRow.risk_reward_ratio"
```

---

### Task 11: Orchestrator — third isolated pipeline in `_run_one`

**Files:**
- Modify: `backend/orchestrator/batch.py:1-9` (imports), `backend/orchestrator/batch.py:30-79` (`_run_one`)
- Test: `backend/tests/test_batch_risk_reward.py`

**Interfaces:**
- Consumes: `risk_reward.engine.run` (Task 8), `services.risk_reward_sheets.upsert_risk_reward_result` (Task 9).
- Produces: every `_run_one` payload gains a `risk_reward` key (a `RiskRewardResult.model_dump()` or `None`), exactly mirroring the existing `screener` key. The Risk-Reward pipeline is failure-isolated: a raise or a `status="failed"` from it never blocks FV or the screener, and never changes `fv_failed`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_batch_risk_reward.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
import asyncio
from orchestrator import batch
from models import TickerResult
from screener.models import ScreenerResult
from risk_reward.models import RiskRewardResult


@pytest.mark.asyncio
async def test_risk_reward_attached_to_payload():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    rr = RiskRewardResult(ticker="AAPL", status="completed", ratio=1.85,
                          tier="Reward-Favored", reward_score=4.1, risk_score=2.2)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("AAPL")
    assert out["result"]["risk_reward"]["ratio"] == 1.85
    assert out["result"]["risk_reward"]["tier"] == "Reward-Favored"
    assert out["result"]["screener"]["quality_score"] == 8.4  # unaffected
    up_rr.assert_awaited_once()


@pytest.mark.asyncio
async def test_risk_reward_failure_is_isolated():
    # RR raising must not fail FV, must not fail the screener, and must not set fv_failed.
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(side_effect=ValueError("rr down"))), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("AAPL")
    assert out["fv_failed"] is False
    assert out["result"]["fair_value"] == 180.0
    assert out["result"]["screener"]["quality_score"] == 8.4
    assert out["result"]["risk_reward"] is None
    assert any("risk_reward" in e for e in out["result"]["errors"])
    up_rr.assert_not_awaited()  # never upsert a failed pipeline


@pytest.mark.asyncio
async def test_insufficient_data_rr_is_not_upserted():
    # A coverage-floor N/A (status="insufficient_data") is attached but NOT persisted.
    fv = TickerResult(ticker="ZZ", status="completed", fair_value=10.0, current_price=9.0)
    sc = ScreenerResult(ticker="ZZ", status="completed", quality_score=5.0)
    rr = RiskRewardResult(ticker="ZZ", status="insufficient_data")
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("ZZ")
    assert out["result"]["risk_reward"]["status"] == "insufficient_data"
    up_rr.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_batch_risk_reward.py -v`
Expected: FAIL — `AttributeError: module 'orchestrator.batch' has no attribute 'risk_reward_run'`.

- [ ] **Step 3: Write minimal implementation**

Add the imports to `backend/orchestrator/batch.py` (top, next to the screener imports):

```python
from risk_reward.engine import run as risk_reward_run
from services.risk_reward_sheets import upsert_risk_reward_result
```

Rewrite `_run_one` to fan a third task and attach its dump. The Risk-Reward block goes
**after** the screener block and **before** the `if fv_dump is None:` error-merge, so
its errors land in the emitted payload:

```python
async def _run_one(ticker: str) -> dict:
    """Run all three pipelines for one ticker; upsert FV first (so the Database row
    exists for the Q/R mirrors), then the screener, then risk-reward. No pipeline's
    failure aborts another — each is gathered with return_exceptions and its write is
    independently guarded."""
    fv_task = asyncio.create_task(engine_run(ticker))
    sc_task = asyncio.create_task(screener_run(ticker))
    rr_task = asyncio.create_task(risk_reward_run(ticker))
    fv_res, sc_res, rr_res = await asyncio.gather(
        fv_task, sc_task, rr_task, return_exceptions=True)

    errors = []
    fv_dump = None
    if isinstance(fv_res, Exception):
        errors.append(f"fair_value: {fv_res}")
    else:
        fv_dump = fv_res.model_dump()
        if fv_res.status != "failed" or fv_res.current_price is not None:
            try:
                await upsert_result(fv_res)
            except Exception as e:
                errors.append(f"sheets_write: {e}")

    sc_dump = None
    if isinstance(sc_res, Exception):
        errors.append(f"screener: {sc_res}")
    else:
        sc_dump = sc_res.model_dump()
        if sc_res.status != "failed":
            try:
                await upsert_screener_result(sc_res)
            except Exception as e:
                errors.append(f"screener_write: {e}")

    # Risk-Reward: a third, fully isolated pipeline. Only a "completed" result is
    # persisted — a "failed" (no data) or "insufficient_data" (coverage floor) result
    # is attached to the payload but never written, so the mirror column stays blank
    # rather than showing a fabricated ratio.
    rr_dump = None
    if isinstance(rr_res, Exception):
        errors.append(f"risk_reward: {rr_res}")
    else:
        rr_dump = rr_res.model_dump()
        if rr_res.status == "completed":
            try:
                await upsert_risk_reward_result(rr_res)
            except Exception as e:
                errors.append(f"risk_reward_write: {e}")

    if fv_dump is None:
        fv_dump = TickerResult(ticker=ticker.upper(), status="failed", errors=errors).model_dump()
    else:
        fv_dump.setdefault("errors", []).extend(errors)
    fv_dump["screener"] = sc_dump
    fv_dump["risk_reward"] = rr_dump
    fv_failed = fv_dump.get("status") == "failed"
    return {"result": fv_dump, "fv_failed": fv_failed}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_batch_risk_reward.py tests/test_batch_screener.py -v`
Expected: PASS (new 3 + existing screener batch tests still green — the screener key is unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/batch.py backend/tests/test_batch_risk_reward.py
git commit -m "feat(risk-reward): third isolated pipeline in batch._run_one (attach + guarded upsert)"
```

---

### Task 12: Frontend types — `RiskRewardResult` + helpers

**Files:**
- Modify: `frontend/src/types.ts` (add interfaces, extend `TickerResult`, add helpers)

**Interfaces:**
- Consumes: the `risk_reward` payload key (Task 11) and `risk_reward_ratio` grid field (Task 10).
- Produces: `RiskRewardResult`/`RiskRewardMetricScore` interfaces; `TickerResult.risk_reward?` (nested, Results grid) and `TickerResult.risk_reward_ratio?` (mirrored number, Database grid); helpers `riskRewardRatio()`, `riskRewardColor()`, `riskRewardBadgeClass()`, `riskRewardTier()`. Tasks 13–14 consume these.

- [ ] **Step 1: Add the interfaces and extend `TickerResult`**

There is no frontend unit runner in this repo; the verification gate for every frontend
task is a clean `npm run build` (tsc typecheck + vite build). Add to `frontend/src/types.ts`:

```typescript
export interface RiskRewardMetricScore {
  raw: number | null
  source: string | null
  score: number | null
  weight: number
  dropped: boolean
}

export interface RiskRewardResult {
  ticker: string
  company_name: string | null
  last_evaluated: string | null
  ratio: number | null
  tier: string | null
  reward_score: number | null
  risk_score: number | null
  actionable_insight: string | null
  metric_scores: Record<string, RiskRewardMetricScore>
  raw_snapshot: Record<string, number | null>
  status: 'completed' | 'insufficient_data' | 'failed'
  errors: string[]
}
```

Extend `TickerResult` (add the two fields after `screener?`):

```typescript
  screener?: ScreenerResult | null
  risk_reward?: RiskRewardResult | null      // nested object — Results grid + detail
  risk_reward_ratio?: number | null          // mirrored number — Database grid
```

- [ ] **Step 2: Add the helpers**

Append to `frontend/src/types.ts`. The color bands match the spec's tier cutoffs
(≥2.0 Asymmetric Upside · 1.3 Reward-Favored · 0.8 Balanced · 0.5 Risk-Favored · <0.5 Value Trap):

```typescript
/** The Results grid carries the nested object; the Database grid carries the
 *  mirrored number. One helper reads whichever is present. */
export function riskRewardRatio(
  r: { risk_reward?: RiskRewardResult | null; risk_reward_ratio?: number | null },
): number | null {
  return r.risk_reward?.ratio ?? r.risk_reward_ratio ?? null
}

export function riskRewardTier(ratio: number | null | undefined): string | null {
  if (ratio == null) return null
  if (ratio >= 2.0) return 'Asymmetric Upside'
  if (ratio >= 1.3) return 'Reward-Favored'
  if (ratio >= 0.8) return 'Balanced'
  if (ratio >= 0.5) return 'Risk-Favored'
  return 'Value Trap'
}

export function riskRewardColor(ratio: number | null | undefined): string {
  if (ratio == null) return 'text-slate-400'
  if (ratio >= 2.0) return 'text-green-400'
  if (ratio >= 1.3) return 'text-blue-400'
  if (ratio >= 0.8) return 'text-yellow-400'
  return 'text-red-400'
}

export function riskRewardBadgeClass(ratio: number | null | undefined): string {
  if (ratio == null) return 'bg-slate-800 text-slate-300'
  if (ratio >= 2.0) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (ratio >= 1.3) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (ratio >= 0.8) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}
```

- [ ] **Step 3: Verify the typecheck/build passes**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors. (Nothing consumes the new symbols yet — this
step only proves the types compile.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(risk-reward): frontend RiskRewardResult types + ratio/tier/color helpers"
```

---

### Task 13: Frontend grids — Risk-Reward column in Results and Database

**Files:**
- Modify: `frontend/src/pages/Results.tsx` (SortKey, `sortVal`, header, cell, CSV export)
- Modify: `frontend/src/pages/Database.tsx` (SortKey, `Filters`, header + `RangeFilter`, cell, `rowMatches`, `sortVal`)
- Modify: `frontend/src/lib/watchlists.ts` (`SerializedFilters` gains `riskReward`)

**Interfaces:**
- Consumes: `riskRewardRatio`, `riskRewardColor` (Task 12); `risk_reward` nested (Results) and `risk_reward_ratio` mirrored (Database).
- Produces: a sortable **R/R** column in both grids; a range filter + watchlist persistence for it in Database.

- [ ] **Step 1: Results.tsx — sort key, header, cell, CSV**

Extend the import and `SortKey`:

```typescript
import { fvGapColor, fvGapLabel, qualityScoreColor, riskRewardColor, riskRewardRatio } from '../types'

type SortKey = 'fair_value' | 'price_vs_fair_value_pct' | 'ticker' | 'quality_score' | 'risk_reward'
```

Extend `sortVal` to resolve the nested ratio:

```typescript
  const sortVal = (r: TickerResult): string | number | null | undefined =>
    sortKey === 'quality_score' ? r.screener?.quality_score
    : sortKey === 'risk_reward' ? riskRewardRatio(r)
    : r[sortKey]
```

Add the header cell immediately after the Quality `<th>`:

```tsx
              <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('risk_reward')}>R/R</th>
```

Add the body cell immediately after the Quality `<td>`:

```tsx
                <td className={`py-2 px-2 text-right font-mono text-xs ${riskRewardColor(riskRewardRatio(r))}`}>
                  {riskRewardRatio(r) != null ? riskRewardRatio(r)!.toFixed(2) : '—'}
                </td>
```

Extend the CSV export — header and row (place the new field next to Quality Score):

```typescript
    const headers = ['Ticker', 'Company', 'Stock Type', 'Quality Score', 'Risk-Reward', 'Fair Value', 'Price', 'FV Gap%', 'Verdict']
    const rows = sorted.map(r => [
      r.ticker, r.company_name, r.stock_type,
      r.screener?.quality_score, riskRewardRatio(r), r.fair_value, r.current_price, r.price_vs_fair_value_pct,
      fvGapLabel(r.price_vs_fair_value_pct),
    ])
```

- [ ] **Step 2: watchlists.ts — extend `SerializedFilters`**

```typescript
export interface SerializedFilters {
  tickers: string[]
  stockTypes: string[]
  quality: NumRange
  gap: NumRange
  riskReward: NumRange
}
```

- [ ] **Step 3: Database.tsx — filter model, sort, header, cell**

Extend the import and `SortKey`:

```typescript
import { fvGapColor, qualityScoreColor, riskRewardColor, riskRewardRatio } from '../types'

type SortKey = 'quality' | 'fair_value' | 'price_vs_fair_value_pct' | 'risk_reward'
```

Extend `ColKey`, the `Filters` type, `EMPTY_FILTERS`, and the (de)serializers:

```typescript
type ColKey = 'ticker' | 'stockType' | 'quality' | 'gap' | 'riskReward'
type Filters = {
  tickers: Set<string>
  stockTypes: Set<string>
  quality: NumRange
  gap: NumRange
  riskReward: NumRange
}

const EMPTY_FILTERS: Filters = {
  tickers: new Set(),
  stockTypes: new Set(),
  quality: { min: null, max: null },
  gap: { min: null, max: null },
  riskReward: { min: null, max: null },
}

const serializeFilters = (f: Filters): SerializedFilters => ({
  tickers: [...f.tickers].sort(),
  stockTypes: [...f.stockTypes].sort(),
  quality: f.quality,
  gap: f.gap,
  riskReward: f.riskReward,
})

const deserializeFilters = (s: Partial<SerializedFilters> | undefined): Filters => ({
  tickers: new Set(s?.tickers ?? []),
  stockTypes: new Set(s?.stockTypes ?? []),
  quality: s?.quality ?? { min: null, max: null },
  gap: s?.gap ?? { min: null, max: null },
  riskReward: s?.riskReward ?? { min: null, max: null },
})
```

Extend `colActive`, `rowMatches`, and `sortVal`:

```typescript
  const colActive = {
    ticker: filters.tickers.size > 0,
    stockType: filters.stockTypes.size > 0,
    quality: rangeActive(filters.quality),
    gap: rangeActive(filters.gap),
    riskReward: rangeActive(filters.riskReward),
  }
```

```typescript
  const rowMatches = (r: TickerResult): boolean => {
    if (filters.tickers.size && !filters.tickers.has(r.ticker)) return false
    if (filters.stockTypes.size && !filters.stockTypes.has(r.stock_type ?? NONE)) return false
    if (!inRange(r.quality_score, filters.quality)) return false
    if (!inRange(r.price_vs_fair_value_pct, filters.gap)) return false
    if (!inRange(riskRewardRatio(r), filters.riskReward)) return false
    return true
  }
```

```typescript
  const sortVal = (r: TickerResult, key: SortKey): number | null => {
    if (key === 'quality') return r.quality_score ?? null
    if (key === 'risk_reward') return riskRewardRatio(r)
    return r[key] ?? null
  }
```

Add the header cell immediately after the Quality `<th>` (mirrors the Quality funnel+sort header):

```tsx
                <th className="text-right py-2 px-2">
                  <FilterHeader
                    label={<span className="cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('risk_reward')}>R/R</span>}
                    active={colActive.riskReward}
                    open={openFilter === 'riskReward'}
                    align="right"
                    onToggle={() => toggleFilter('riskReward')}
                  >
                    <RangeFilter value={filters.riskReward} step="0.1" onChange={v => setFilters(f => ({ ...f, riskReward: v }))} />
                  </FilterHeader>
                </th>
```

Add the body cell immediately after the Quality `<td>`:

```tsx
                  <td className={`py-2 px-2 text-right font-mono text-xs ${riskRewardColor(riskRewardRatio(r))}`}>
                    {riskRewardRatio(r) != null ? riskRewardRatio(r)!.toFixed(2) : '—'}
                  </td>
```

- [ ] **Step 4: Verify the build passes**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Results.tsx frontend/src/pages/Database.tsx frontend/src/lib/watchlists.ts
git commit -m "feat(risk-reward): sortable R/R column in Results + Database (filter + watchlist persistence)"
```

---

### Task 14: Frontend detail — Risk-Reward breakdown panel + tab

**Files:**
- Create: `frontend/src/components/RiskRewardPanel.tsx`
- Modify: `frontend/src/pages/TickerDetail.tsx` (third tab, lazy fetch)

**Interfaces:**
- Consumes: `RiskRewardResult`, `riskRewardBadgeClass`, `riskRewardTier` (Task 12); the read endpoint `GET /api/risk-reward/{ticker}` (Task 9).
- Produces: a `RiskRewardPanel` component; a `risk_reward` tab on the ticker detail page that shows the ratio, tier, reward/risk axis scores, the actionable insight, and the per-metric table.

- [ ] **Step 1: Create the panel component**

`frontend/src/components/RiskRewardPanel.tsx`:

```tsx
import type { RiskRewardResult } from '../types'
import { riskRewardBadgeClass, riskRewardTier } from '../types'

/** Order the metric rows reward-axis-first, then risk-axis, then any extras. */
const REWARD_SLOTS = ['valuation', 'growth', 'profitability', 'analyst_upside', 'discount', 'rsi']
const RISK_SLOTS = ['leverage', 'burn', 'liquidity', 'volatility', 'trend', 'beta']  // matches config.RISK_SLOTS order

function fmt(v: number | null, digits = 2): string {
  return v == null ? '—' : v.toFixed(digits)
}

export default function RiskRewardPanel({ result }: { result: RiskRewardResult }) {
  if (result.status === 'insufficient_data') {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        Not enough covered metrics to compute a Risk-Reward rating for this ticker.
      </div>
    )
  }
  if (result.status === 'failed' || result.ratio == null) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        No Risk-Reward data for this ticker yet.
      </div>
    )
  }

  const slots = [...REWARD_SLOTS, ...RISK_SLOTS]
  const known = new Set(slots)
  const rows = [
    ...slots.filter(s => result.metric_scores[s]),
    ...Object.keys(result.metric_scores).filter(s => !known.has(s)),
  ]

  return (
    <div className="space-y-6">
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-3xl font-bold font-mono text-slate-100">{fmt(result.ratio)}</div>
            <div className="text-xs text-slate-500 mt-1">Reward ÷ Risk</div>
          </div>
          <span className={`rounded font-mono font-semibold inline-flex items-center px-3 py-1.5 text-sm ${riskRewardBadgeClass(result.ratio)}`}>
            {result.tier || riskRewardTier(result.ratio)}
          </span>
        </div>
        <div className="flex gap-8 mt-4 text-sm font-mono">
          <div><span className="text-slate-500">Reward </span><span className="text-green-400">{fmt(result.reward_score)}</span><span className="text-slate-600"> /5</span></div>
          <div><span className="text-slate-500">Risk </span><span className="text-red-400">{fmt(result.risk_score)}</span><span className="text-slate-600"> /5</span></div>
        </div>
        {result.actionable_insight && (
          <p className="text-sm text-slate-400 mt-4">{result.actionable_insight}</p>
        )}
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
              <th className="text-left py-2 px-4">Metric</th>
              <th className="text-left py-2 px-2">Source</th>
              <th className="text-right py-2 px-2">Raw</th>
              <th className="text-right py-2 px-2">Score</th>
              <th className="text-right py-2 px-4">Weight</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(slot => {
              const m = result.metric_scores[slot]
              return (
                <tr key={slot} className={`border-b border-[#1e1e2a] ${m.dropped ? 'opacity-40' : ''}`}>
                  <td className="py-2 px-4 text-slate-300 font-mono text-xs">{slot}</td>
                  <td className="py-2 px-2 text-slate-500 font-mono text-xs">{m.source || '—'}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">{fmt(m.raw)}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">{m.dropped ? '—' : fmt(m.score, 1)}</td>
                  <td className="py-2 px-4 text-right font-mono text-xs text-slate-500">{(m.weight * 100).toFixed(0)}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire the tab into TickerDetail.tsx**

Add the import, a third tab id, lazy state + fetch, and render. Replace the tab-state
and tab-list wiring in `frontend/src/pages/TickerDetail.tsx`:

```tsx
import type { TickerResult, ScreenerResult, RiskRewardResult } from '../types'
import { fvBadgeClass, fvGapLabel } from '../types'
import FairValuePanel from '../components/FairValuePanel'
import ScreenerPanel from '../components/ScreenerPanel'
import RiskRewardPanel from '../components/RiskRewardPanel'
```

```tsx
  const [tab, setTab] = useState<'fv' | 'screener' | 'risk_reward'>('fv')
  const [screener, setScreener] = useState<ScreenerResult | null>(result?.screener ?? null)
  const [riskReward, setRiskReward] = useState<RiskRewardResult | null>(result?.risk_reward ?? null)

  useEffect(() => {
    if (tab === 'screener' && !screener && result?.ticker) {
      fetch(`${API}/api/screener/${result.ticker}`)
        .then(r => r.json())
        .then(d => { if (!d.error) setScreener(d as ScreenerResult) })
        .catch(() => {})
    }
    if (tab === 'risk_reward' && !riskReward && result?.ticker) {
      fetch(`${API}/api/risk-reward/${result.ticker}`)
        .then(r => r.json())
        .then(d => { if (!d.error) setRiskReward(d as RiskRewardResult) })
        .catch(() => {})
    }
  }, [tab, screener, riskReward, result])
```

Extend the tab-button list (the `.map` over tab ids) and its label:

```tsx
        {(['fv', 'screener', 'risk_reward'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-sm ${tab === t ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
          >
            {t === 'fv' ? 'Fair Value' : t === 'screener' ? 'Screener' : 'Risk-Reward'}
          </button>
        ))}
```

Replace the panel-render block so the third tab renders its panel:

```tsx
      {tab === 'fv' ? (
        <FairValuePanel result={result} />
      ) : tab === 'screener' ? (
        screener ? (
          <ScreenerPanel result={screener} />
        ) : (
          <div className="text-slate-500 text-sm py-8 text-center">
            No screener data for this ticker yet.
          </div>
        )
      ) : riskReward ? (
        <RiskRewardPanel result={riskReward} />
      ) : (
        <div className="text-slate-500 text-sm py-8 text-center">
          No Risk-Reward data for this ticker yet.
        </div>
      )}
```

- [ ] **Step 3: Verify the build passes**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors.

- [ ] **Step 4: Manual smoke check (optional but recommended)**

Start backend (`cd backend && uvicorn main:app --reload`) and frontend (`cd frontend && npm run dev`),
recalculate one ticker, and confirm the **R/R** column appears in both grids and the
**Risk-Reward** tab renders the ratio, tier, axis scores, insight, and per-metric table.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/RiskRewardPanel.tsx frontend/src/pages/TickerDetail.tsx
git commit -m "feat(risk-reward): ticker-detail Risk-Reward breakdown panel + tab"
```

---

## Completion

After Task 14, the Risk-Reward Rating Engine is end-to-end: an isolated backend pipeline
(`backend/risk_reward/`) computing a clamped Reward ÷ Risk ratio, persisted to its own
`Risk-Reward` Sheets tab with a mirrored Database column `R`, surfaced through
`GET /api/risk-reward/{ticker}` and the batch payload's `risk_reward` key, and rendered as
a sortable **R/R** column in both grids plus a full breakdown tab — with the Fair Value and
Quality Score pipelines untouched and Risk-Reward defaulting to N/A on thin data.

Full backend gate: `cd backend && python -m pytest`
Full frontend gate: `cd frontend && npm run build`

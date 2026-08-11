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
    # Statement-annual growth/margin (Total Revenue YoY, Operating Income / Total
    # Revenue), same basis as screener/metrics.py's revenue_growth_yoy / op_margin.
    # Feeds the growth/burn statement-corroboration guard in scoring.py ONLY — never
    # a blanket replacement for info's quarterly-YoY figures (see
    # [[iren-rr-stmt-gap-guard]]). None when the statement fetch is unavailable.
    revenue_growth_stmt: float | None = None
    operating_margin_stmt: float | None = None


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

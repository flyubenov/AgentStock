from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class TickerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    last_evaluated: str | None = None
    stock_type: str | None = None
    fair_value: float | None = None
    price_vs_fair_value_pct: float | None = None
    fair_value_breakdown: dict = {}
    status: Literal["completed", "failed"] = "completed"
    errors: list[str] = []


class AnalyseRequest(BaseModel):
    tickers: list[str] = []
    sheets_url: str | None = None


class JobStatus(BaseModel):
    job_id: str
    total: int
    completed: int
    failed: int
    status: Literal["running", "completed", "failed", "cancelled"]
    results: list[TickerResult] = []

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class AgentResult(BaseModel):
    agent_name: str
    ticker: str
    raw_score: float | None = None
    normalised_score: float | None = None
    recommendation: str | None = None
    rationale: str | None = None
    raw_response: str = ""
    report: str = ""
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class FairValueResult(BaseModel):
    ticker: str
    method_name: str
    pre_mos_value: float | None = None
    post_mos_value: float | None = None
    methods_breakdown: dict = {}
    data_sources: list[str] = []
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class TickerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    last_evaluated: str | None = None
    buffett_munger_score: float | None = None
    lynch_garp_score: float | None = None
    growth_analyzer_score: float | None = None
    business_engine_score: float | None = None
    canslim_score: float | None = None
    pre_screener_score: float | None = None
    overall_final_score: float | None = None
    overall_label: str | None = None
    fair_value_gemini: float | None = None
    fair_value_calculator_1: float | None = None
    fair_value_calculator_2: float | None = None
    blended_fair_value: float | None = None
    price_vs_fair_value_pct: float | None = None
    agent_results: dict[str, AgentResult] = {}
    fair_value_results: dict[str, FairValueResult] = {}
    status: Literal["completed", "partial", "failed"] = "completed"
    errors: list[str] = []


class AnalyseRequest(BaseModel):
    tickers: list[str] = []
    sheets_url: str | None = None
    mode: Literal["live", "batch"] = "batch"


class JobStatus(BaseModel):
    job_id: str
    total: int
    completed: int
    failed: int
    status: Literal["running", "completed", "failed", "cancelled"]
    results: list[TickerResult] = []


class BatchJobFile(BaseModel):
    job_id: str
    batch_id: str
    tickers: list[str]
    failed_prefetch: list[str] = []
    status: Literal["processing", "completed", "cancelled"] = "processing"
    submitted_at: str

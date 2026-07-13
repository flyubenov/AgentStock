from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel


@dataclass
class StatementSeries:
    years: list[int]
    rows: dict[str, list[float | None]]

    @classmethod
    def from_dict(cls, d: dict | None) -> "StatementSeries | None":
        if not d:
            return None
        return cls(years=list(d["years"]), rows=dict(d["rows"]))

    def series(self, label: str) -> list[float | None]:
        return self.rows.get(label, [])

    def value(self, label: str, idx: int) -> float | None:
        s = self.rows.get(label)
        if not s or idx >= len(s):
            return None
        return s[idx]

    def latest(self, label: str) -> float | None:
        return self.value(label, 0)


@dataclass
class ScreenerInputs:
    ticker: str
    info: dict
    income: StatementSeries | None
    balance: StatementSeries | None
    cashflow: StatementSeries | None
    price_monthly: tuple[float, ...]
    risk_free: float | None


class ScreenerMetrics(BaseModel):
    # Section I (percent)
    revenue_cagr_3y: float | None = None
    eps_cagr_3y: float | None = None
    fcf_cagr_3y: float | None = None
    fcf_margin: float | None = None
    op_margin: float | None = None
    op_margin_trajectory: float | None = None
    gross_margin: float | None = None
    # Section II (percent; spread in pp)
    roic_ttm: float | None = None
    roic_5y_avg: float | None = None
    wacc: float | None = None
    roic_wacc_spread: float | None = None
    rote: float | None = None
    # Section II — acquisition-distortion variants (ROIC on tangible invested
    # capital, i.e. excluding goodwill & intangibles): used in place of the reported
    # ROIC when a large past acquisition inflates invested capital and amortization
    # depresses EBIT (see _acquisition_distorted).
    roic_ex_goodwill: float | None = None
    roic_5y_ex_goodwill: float | None = None
    goodwill_intangible_share: float | None = None
    # Section III (ratios; tangible_bv_per_share is currency)
    net_debt_ebitda: float | None = None
    net_debt_fcf: float | None = None
    ocf_capex: float | None = None
    tangible_bv_per_share: float | None = None
    # Section IV (percent, except earnings_quality ratio)
    shares_cagr_3y: float | None = None
    sbc_pct_rev: float | None = None
    earnings_quality: float | None = None
    insider_ownership: float | None = None
    shareholder_yield: float | None = None
    # Section V — reference only (not scored)
    trailing_pe: float | None = None
    forward_pe: float | None = None
    peg: float | None = None
    price_fcf: float | None = None
    price_sales: float | None = None
    fcf_yield: float | None = None
    owner_earnings_yield: float | None = None
    price_cagr_3y: float | None = None
    price_cagr_5y: float | None = None
    # raw inputs used by cap rules / dual-check
    net_income: float | None = None
    fcf: float | None = None
    revenue_growth: float | None = None
    revenue_growth_yoy: float | None = None   # statement latest-FY vs prior-FY (percent)
    total_cash: float | None = None
    net_debt: float | None = None
    ebitda: float | None = None
    sector: str | None = None


class ScreenerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    last_evaluated: str | None = None
    quality_score: float | None = None
    sector: str | None = None
    sector_profile: str | None = None
    section_scores: dict[str, float | None] = {}
    metrics: dict = {}
    score_breakdown: dict = {}
    status: Literal["completed", "failed"] = "completed"
    errors: list[str] = []

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
        # Statement-annual variants (see [[iren-rr-stmt-gap-guard]]): same basis/anchors
        # as their info-sourced counterparts (revenue YoY as a fraction, operating
        # margin as a fraction) — only the raw source differs (annual statement vs.
        # info's quarterly-YoY / TTM). Used ONLY by the gap guard in scoring.py, never
        # part of a slot's normal fallback chain.
        "revenue_growth_stmt": (0.25, 0.10, 0.0),
        "operating_margin_stmt": (-0.15, 0.0, 0.15),
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

    # Confidence-scaled Analyst-upside weight (Task 5 computes it per ticker):
    #   c = min(coverage, agreement) in [0,1];  weight = floor + span*c  ->  [0.08, 0.18]
    #   coverage  ramps 0 -> 1 as numberOfAnalystOpinions goes lo -> hi
    #   agreement ramps 1 -> 0 as target dispersion goes spread_lo -> spread_hi
    analyst_weight_floor: float = 0.08
    analyst_weight_span: float = 0.10
    analyst_coverage_lo: float = 3.0
    analyst_coverage_hi: float = 20.0
    analyst_spread_lo: float = 0.20
    analyst_spread_hi: float = 0.80

    # Statement-corroboration gap guard for growth/burn (see [[iren-rr-stmt-gap-guard]]):
    # info's revenueGrowth (quarterly YoY) / operatingMargins can read a flat/negative
    # growth or deeply-negative margin artifact for capex-heavy crypto miners (IREN,
    # MARA, RIOT, CLSK, CIFR, WULF) while the statement shows a materially better
    # reality. Override ONLY when the statement-sourced score beats info's by >= this
    # many points on the shared 1-5 scale (growth: statement higher; burn: info higher,
    # i.e. info overstates risk) — directional and self-limiting, so a name where info
    # reads BETTER than the statement (CORZ, APLD — a real business-transition/impairment
    # divergence, not a feed artifact) is structurally excluded, no per-name carve-out.
    # Live-swept 1.0 sits clear of the largest false-positive candidate (CRWV burn gap
    # 0.80) and well below the smallest true positive (RIOT growth gap 1.48).
    stmt_gap_min: float = 1.0


CONFIG = RiskRewardConfig()

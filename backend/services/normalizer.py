from __future__ import annotations
from models import AgentResult


def normalise_buffett_munger(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_lynch_garp(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_growth_stock(raw: float) -> float:
    """(score / 100) × 5, clamped [1, 5]."""
    return max(1.0, min(5.0, (raw / 100) * 5))


def normalise_business_engine(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_canslim(raw: float) -> float:
    """((score − 7) / 28) × 4 + 1, clamped [1, 5]."""
    return max(1.0, min(5.0, ((raw - 7) / 28) * 4 + 1))


def normalise_pre_screener(raw: float) -> float:
    """Direct 1–5 scale (score derived by derive_pre_screener; clamp to valid range)."""
    return max(1.0, min(5.0, raw))


def derive_pre_screener(recommendation: str | None, growth_potential: str | None, financial_state: str | None) -> float:
    """
    1. Map recommendation: BUY=5, HOLD=3, SELL=1
    2. Apply Growth Potential: High=+0, Moderate=−0.5, Low=−1.0
    3. Apply Financial State: Bad=−0.5, otherwise 0
    4. Clamp [1, 5]
    """
    rec = (recommendation or "").upper()
    base = {"BUY": 5.0, "HOLD": 3.0, "SELL": 1.0}.get(rec, 3.0)

    growth = (growth_potential or "").lower()
    if "low" in growth:
        base -= 1.0
    elif "moderate" in growth:
        base -= 0.5

    fin = (financial_state or "").lower()
    if "bad" in fin:
        base -= 0.5

    return max(1.0, min(5.0, base))


_NORMALIZERS = {
    "buffett_munger": normalise_buffett_munger,
    "lynch_garp": normalise_lynch_garp,
    "growth_stock": normalise_growth_stock,
    "business_engine": normalise_business_engine,
    "canslim": normalise_canslim,
    "pre_screener": normalise_pre_screener,
}


def apply_normalisation(agent_name: str, result: AgentResult) -> AgentResult:
    """Mutate AgentResult to set normalised_score from raw_score."""
    key = agent_name.lower().replace("-", "_").replace(" ", "_")
    if key in _NORMALIZERS and result.raw_score is not None:
        result.normalised_score = round(_NORMALIZERS[key](result.raw_score), 2)
    return result

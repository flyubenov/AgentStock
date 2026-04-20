from __future__ import annotations
from models import AgentResult, FairValueResult, TickerResult
from datetime import datetime, timezone


_SCORE_LABEL_MAP = [
    (4.5, "Strong Buy"),
    (3.5, "Buy"),
    (2.5, "Hold / Watch"),
    (1.5, "Underperform"),
    (0.0, "Sell / Avoid"),
]


def score_label(score: float | None) -> str | None:
    if score is None:
        return None
    for threshold, label in _SCORE_LABEL_MAP:
        if score >= threshold:
            return label
    return "Sell / Avoid"


_AGENT_SCORE_MAP = {
    "buffett_munger": "buffett_munger_score",
    "lynch_garp": "lynch_garp_score",
    "growth_stock": "growth_analyzer_score",
    "business_engine": "business_engine_score",
    "canslim": "canslim_score",
    "pre_screener": "pre_screener_score",
}

_FV_MAP = {
    "gemini_fv": "fair_value_gemini",
    "calculator_1": "fair_value_calculator_1",
    "calculator_2": "fair_value_calculator_2",
}


def aggregate(
    ticker: str,
    company_name: str | None,
    current_price: float | None,
    agent_results: dict[str, AgentResult],
    fv_results: dict[str, FairValueResult],
) -> TickerResult:
    result = TickerResult(
        ticker=ticker,
        company_name=company_name,
        current_price=current_price,
        last_evaluated=datetime.now(timezone.utc).isoformat(),
        agent_results=agent_results,
        fair_value_results=fv_results,
    )

    # Map individual agent scores
    for agent_key, field in _AGENT_SCORE_MAP.items():
        ar = agent_results.get(agent_key)
        if ar and ar.normalised_score is not None:
            setattr(result, field, ar.normalised_score)

    # Overall final score = simple average of available normalised scores
    scores = [
        getattr(result, field)
        for field in _AGENT_SCORE_MAP.values()
        if getattr(result, field) is not None
    ]
    if scores:
        result.overall_final_score = round(sum(scores) / len(scores), 2)
        result.overall_label = score_label(result.overall_final_score)

    # Map fair value results
    for fv_key, field in _FV_MAP.items():
        fvr = fv_results.get(fv_key)
        if fvr and fvr.post_mos_value is not None:
            setattr(result, field, fvr.post_mos_value)

    # Blended fair value = average of available post-MOS values
    fv_values = [
        getattr(result, f)
        for f in ["fair_value_gemini", "fair_value_calculator_1", "fair_value_calculator_2"]
        if getattr(result, f) is not None
    ]
    if fv_values:
        result.blended_fair_value = round(sum(fv_values) / len(fv_values), 2)

    # Price vs fair value %
    if result.blended_fair_value and current_price and current_price > 0:
        result.price_vs_fair_value_pct = round(
            (result.blended_fair_value - current_price) / current_price * 100, 2
        )

    # Status
    failed_agents = sum(1 for ar in agent_results.values() if ar.status == "failed")
    total_agents = len(agent_results)
    if failed_agents == 0 and total_agents > 0:
        result.status = "completed"
    elif failed_agents == total_agents:
        result.status = "failed"
    else:
        result.status = "partial"

    result.errors = [
        f"{k}: {v.error}"
        for k, v in {**agent_results, **fv_results}.items()
        if v.status == "failed" and v.error
    ]

    return result

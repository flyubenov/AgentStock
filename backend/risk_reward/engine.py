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

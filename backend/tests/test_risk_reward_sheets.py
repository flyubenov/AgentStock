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

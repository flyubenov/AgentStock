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

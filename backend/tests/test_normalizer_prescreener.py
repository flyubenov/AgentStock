from services.normalizer import apply_normalisation
from models import AgentResult


def test_pre_screener_normalisation_sets_normalised_score():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=4.0)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 4.0


def test_pre_screener_normalisation_clamps_above_5():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=5.5)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 5.0


def test_pre_screener_normalisation_clamps_below_1():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=0.5)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 1.0


def test_other_agents_unaffected():
    ar = AgentResult(agent_name="buffett_munger", ticker="AAPL", raw_score=4.0)
    result = apply_normalisation("buffett_munger", ar)
    assert result.normalised_score == 4.0

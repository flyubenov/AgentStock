from agents.base_agent import BaseAgent


def _make_agent() -> BaseAgent:
    agent = object.__new__(BaseAgent)
    return agent


def test_parse_score_returns_three_tuple():
    agent = _make_agent()
    response = "Analysis.\nSCORE: 3.5\nRECOMMENDATION: BUY\nRATIONALE: Strong moat but valuation is stretched."
    score, rec, rationale = agent.parse_score(response)
    assert score == 3.5
    assert rec == "BUY"
    assert rationale == "Strong moat but valuation is stretched."


def test_parse_score_handles_missing_rationale():
    agent = _make_agent()
    response = "SCORE: 4.0\nRECOMMENDATION: WATCHLIST"
    score, rec, rationale = agent.parse_score(response)
    assert score == 4.0
    assert rec == "WATCHLIST"
    assert rationale is None


def test_parse_score_handles_missing_score():
    agent = _make_agent()
    response = "No score here."
    score, rec, rationale = agent.parse_score(response)
    assert score is None
    assert rec is None
    assert rationale is None

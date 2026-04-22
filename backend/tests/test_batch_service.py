from services.batch_service import build_batch_requests, _parse_custom_id


def test_build_batch_requests_generates_six_per_ticker():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    assert len(requests) == 6


def test_build_batch_requests_encodes_custom_id():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    ids = {r["custom_id"] for r in requests}
    assert "job123__AAPL__buffett_munger" in ids
    assert "job123__AAPL__canslim" in ids
    assert "job123__AAPL__pre_screener" in ids


def test_build_batch_requests_haiku_agents_have_no_tools():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    haiku_agents = {"canslim", "lynch_garp", "pre_screener"}
    for req in requests:
        _, _, agent_name = _parse_custom_id(req["custom_id"])
        if agent_name in haiku_agents:
            assert "tools" not in req["params"] or req["params"].get("tools") == []


def test_parse_custom_id():
    job_id, ticker, agent_name = _parse_custom_id("job123__AAPL__buffett_munger")
    assert job_id == "job123"
    assert ticker == "AAPL"
    assert agent_name == "buffett_munger"


def test_build_batch_requests_multiple_tickers():
    blocks = {"AAPL": "data1", "MSFT": "data2"}
    requests = build_batch_requests("job1", blocks)
    assert len(requests) == 12  # 2 tickers × 6 agents

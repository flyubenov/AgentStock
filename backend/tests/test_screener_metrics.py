from screener.models import StatementSeries, ScreenerMetrics, ScreenerResult


def test_statement_series_lookups():
    s = StatementSeries.from_dict({"years": [2025, 2024, 2023],
                                   "rows": {"Total Revenue": [100.0, 90.0, None]}})
    assert s.latest("Total Revenue") == 100.0
    assert s.value("Total Revenue", 1) == 90.0
    assert s.value("Total Revenue", 2) is None
    assert s.value("Missing", 0) is None
    assert s.series("Total Revenue") == [100.0, 90.0, None]


def test_statement_series_from_none():
    assert StatementSeries.from_dict(None) is None


def test_models_default_to_none():
    m = ScreenerMetrics()
    assert m.roic_ttm is None and m.revenue_cagr_3y is None
    r = ScreenerResult(ticker="AAPL")
    assert r.quality_score is None and r.status == "completed" and r.errors == []

import pytest
from screener.models import StatementSeries, ScreenerMetrics, ScreenerResult
from screener.metrics import cagr, series_cagr, price_cagr, pct


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


def test_cagr_basic_and_guards():
    assert cagr(100.0, 133.1, 3) == pytest.approx(0.10, abs=1e-4)
    assert cagr(0, 100.0, 3) is None       # non-positive start
    assert cagr(100.0, -5.0, 3) is None    # non-positive end
    assert cagr(100.0, 110.0, 0) is None   # zero years


def test_series_cagr_uses_available_span():
    # 5 points, span 3 -> compare index0 vs index3 over 3 years
    s = [161.05, 146.41, 133.1, 121.0, 110.0]
    assert series_cagr(s, 3) == pytest.approx(0.10, abs=1e-4)
    # only 3 points, span 5 -> falls back to 2-year span
    assert series_cagr([121.0, 110.0, 100.0], 5) == pytest.approx(0.10, abs=1e-4)
    assert series_cagr([100.0], 3) is None
    assert series_cagr([None, 100.0, 121.0], 2) is None  # latest missing


def test_price_cagr_and_pct():
    months = [float(100 * (1.10 ** (i / 12))) for i in range(37)]  # 36 mo -> +10%/yr
    assert price_cagr(months, 3) == pytest.approx(0.10, abs=1e-3)
    assert price_cagr([100.0], 3) is None
    assert pct(0.153) == pytest.approx(15.3)
    assert pct(None) is None

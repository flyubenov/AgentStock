from valuation.classifier import classify


def test_financial_sector_is_financial():
    fin = {"sector": "Financial Services"}
    assert classify(fin)["stock_type"] == "FINANCIAL"


def test_real_estate_is_asset_heavy():
    fin = {"sector": "Real Estate"}
    assert classify(fin)["stock_type"] == "ASSET_HEAVY"


def test_small_negative_ebitda_is_asset_heavy():
    fin = {"sector": "Technology", "ebitda_ttm": -5_000_000, "market_cap": 1_000_000_000}
    assert classify(fin)["stock_type"] == "ASSET_HEAVY"


def test_conglomerate_industry():
    fin = {"sector": "Industrials", "industry": "Conglomerates"}
    assert classify(fin)["stock_type"] == "CONGLOMERATE"


def test_conglomerate_keyword_in_summary():
    fin = {"sector": "Industrials", "long_business_summary": "A diversified holding company."}
    assert classify(fin)["stock_type"] == "CONGLOMERATE"


def test_early_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.35, "eps_ttm": -1.2, "ebitda_ttm": 10}
    assert classify(fin)["stock_type"] == "EARLY_GROWTH"


def test_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.18, "eps_ttm": 3.0, "dividend_yield": 0.0}
    assert classify(fin)["stock_type"] == "GROWTH"


def test_dividend():
    fin = {"sector": "Consumer Defensive", "dividend_yield": 0.04, "payout_ratio": 0.6}
    assert classify(fin)["stock_type"] == "DIVIDEND"


def test_cyclical_sector():
    fin = {"sector": "Energy"}
    assert classify(fin)["stock_type"] == "CYCLICAL"


def test_large_cap_default():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0, "dividend_yield": 0.005}
    assert classify(fin)["stock_type"] == "LARGE_CAP"


def test_method_weights_shape():
    res = classify({"sector": "Financial Services"})
    assert res["method_weights"]["rim"] == {"enabled": True, "weight": 0.45}
    assert res["method_weights"]["dcf"] == {"enabled": False, "weight": 0.0}

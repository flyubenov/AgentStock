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


def test_subsidiaries_boilerplate_is_not_conglomerate():
    # "together with its subsidiaries" is generic SEC boilerplate, not a
    # conglomerate signal. Regression: KLAC was misclassified as CONGLOMERATE.
    fin = {
        "sector": "Technology",
        "industry": "Semiconductor Equipment & Materials",
        "long_business_summary": (
            "KLA Corporation, together with its subsidiaries, designs, "
            "manufactures, and markets process control and yield management "
            "solutions for the semiconductor and related industries."
        ),
        "revenue_growth": 0.115,
        "eps_ttm": 3.52,
        "dividend_yield": 0.008,
    }
    assert classify(fin)["stock_type"] == "GROWTH"


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


def test_crypto_miner_not_financial():
    # yfinance tags bitcoin miners / data-center operators "Financial Services";
    # the de-financialize override must skip FINANCIAL for them.
    fin = {
        "sector": "Financial Services",
        "long_business_summary": (
            "The company operates data centers and bitcoin mining facilities, "
            "converting capacity to AI compute."
        ),
        "market_cap": 16_000_000_000,
    }
    assert classify(fin)["stock_type"] != "FINANCIAL"


def test_real_bank_still_financial():
    fin = {
        "sector": "Financial Services",
        "long_business_summary": "A regional bank providing deposit and loan services.",
    }
    assert classify(fin)["stock_type"] == "FINANCIAL"

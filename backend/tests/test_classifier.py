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


def test_trillion_dollar_grower_is_large_cap():
    # A $1T+ fast grower is a LARGE_CAP, not GROWTH (regression: META/MSFT/GOOGL
    # were mislabeled GROWTH; the GROWTH rule now has a mega-cap ceiling).
    fin = {"sector": "Technology", "revenue_growth": 0.15, "eps_ttm": 20.0,
           "ebitda_ttm": 100_000_000_000, "dividend_yield": 0.0,
           "market_cap": 1_400_000_000_000}
    assert classify(fin)["stock_type"] == "LARGE_CAP"


def test_sub_trillion_grower_stays_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.15, "eps_ttm": 5.0,
           "ebitda_ttm": 20_000_000_000, "dividend_yield": 0.0,
           "market_cap": 300_000_000_000}
    assert classify(fin)["stock_type"] == "GROWTH"


def test_dividend():
    fin = {"sector": "Consumer Defensive", "dividend_yield": 0.04, "payout_ratio": 0.6}
    assert classify(fin)["stock_type"] == "DIVIDEND"


def test_cyclical_sector():
    fin = {"sector": "Energy"}
    assert classify(fin)["stock_type"] == "CYCLICAL"


def test_large_cap_default():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005, "market_cap": 500_000_000_000}
    assert classify(fin)["stock_type"] == "LARGE_CAP"


def test_mid_cap_below_threshold():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005, "market_cap": 20_000_000_000}
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_missing_market_cap_defaults_mid_cap():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005}
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_mid_cap_weights_shape():
    res = classify({"sector": "Technology", "eps_ttm": 5.0, "market_cap": 20_000_000_000})
    assert res["method_weights"]["dcf"]["weight"] == 0.45
    assert res["method_weights"]["ev_sales"]["weight"] == 0.15
    assert res["method_weights"]["sotp"]["weight"] == 0.0


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


def test_lender_offering_crypto_stays_financial():
    # SOFI-like: a genuine lender (industry "Credit Services") whose summary mentions a
    # crypto product. The core-financial industry keeps it FINANCIAL despite the crypto
    # keywords — regression: SOFI was ejected to EARLY_GROWTH, then declined (no FV) by
    # the DCF pre-profit guard on its structurally-negative lender FCF.
    fin = {
        "sector": "Financial Services",
        "industry": "Credit Services",
        "long_business_summary": (
            "SoFi offers lending and financial services products, including SoFi Crypto, "
            "a new digital asset trading platform."
        ),
        "revenue_growth": 0.42,
    }
    assert classify(fin)["stock_type"] == "FINANCIAL"


def test_crypto_name_without_lending_industry_not_financial():
    # Guard against over-broadening: a Financial-Services-tagged crypto/data-center name
    # that is NOT a core-financial industry still gets the keyword override.
    fin = {
        "sector": "Financial Services",
        "industry": "Capital Markets",
        "long_business_summary": "A cryptocurrency exchange and digital asset platform.",
        "revenue_growth": 0.42,
    }
    assert classify(fin)["stock_type"] != "FINANCIAL"


def _payment_network_fin(**over):
    # Visa-shape: asset-light transaction network tagged "Credit Services", no loan book.
    fin = {
        "sector": "Financial Services", "industry": "Credit Services",
        "long_business_summary": (
            "Visa operates as a payment technology company. It operates VisaNet, a "
            "transaction processing network that enables authorization, clearing, and "
            "settlement of payment transactions, and Visa Direct for money movement."
        ),
        "revenue_growth": 0.171, "eps_ttm": 11.43,
        "dividend_yield": 0.0075, "market_cap": 677_000_000_000,
    }
    fin.update(over)
    return fin


def test_payment_network_reclassified_out_of_financial():
    # V/MA: a pure payment network must NOT get the book-value (P/B + RIM) methods —
    # book value is trivial vs earning power. Falls through to the size/growth rules.
    assert classify(_payment_network_fin())["stock_type"] == "GROWTH"


def test_payment_network_above_trillion_is_large_cap():
    # Documents the GROWTH vs LARGE_CAP boundary: a >$1T network fails the GROWTH
    # size gate and lands in the LARGE_CAP size default.
    assert classify(_payment_network_fin(market_cap=1_200_000_000_000))["stock_type"] == "LARGE_CAP"


def test_network_lender_hybrid_stays_financial():
    # AXP-shape: operates a payments network BUT also carries a real loan book
    # (deposits + non-card lending), so book methods still apply -> stays FINANCIAL.
    fin = {
        "sector": "Financial Services", "industry": "Credit Services",
        "long_business_summary": (
            "American Express operates as an integrated payments company, offering "
            "credit and charge cards, and banking and financing products including "
            "deposits and non-card lending, as well as network services."
        ),
        "revenue_growth": 0.09, "eps_ttm": 14.0,
        "dividend_yield": 0.011, "market_cap": 242_000_000_000,
    }
    assert classify(fin)["stock_type"] == "FINANCIAL"


def test_pure_lender_credit_services_stays_financial():
    # SYF-shape: a genuine consumer lender with no network language stays FINANCIAL.
    fin = {
        "sector": "Financial Services", "industry": "Credit Services",
        "long_business_summary": (
            "A consumer financial services company providing credit cards, installment "
            "loans, and deposit products including certificates of deposit."
        ),
        "revenue_growth": 0.05,
    }
    assert classify(fin)["stock_type"] == "FINANCIAL"

import pytest

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


def test_conglomerates_industry_no_longer_conglomerate_dividend():
    # HON-like: the old rule-3 "Conglomerates" industry no longer captures. A
    # mature payer falls through to DIVIDEND (yield > 2.5%, payout > 40%).
    fin = {
        "sector": "Industrials", "industry": "Conglomerates",
        "dividend_yield": 0.0414, "payout_ratio": 0.741,
        "revenue_growth": 0.024, "eps_ttm": 12.53,
    }
    assert classify(fin)["stock_type"] == "DIVIDEND"


def test_conglomerates_industry_no_longer_conglomerate_midcap():
    # MMM-like: yield 1.83% < 2.5% skips DIVIDEND, not cyclical, $88B < $100B -> MID_CAP.
    fin = {
        "sector": "Industrials", "industry": "Conglomerates",
        "dividend_yield": 0.0183, "payout_ratio": 0.572,
        "revenue_growth": 0.025, "eps_ttm": 5.19,
        "trailing_pe": 32.9, "market_cap": 88_000_000_000,
    }
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_diversified_holding_keyword_no_longer_conglomerate():
    # The old summary keyword ("diversified holding company") no longer triggers
    # CONGLOMERATE; the name falls through to the size default.
    fin = {
        "sector": "Industrials",
        "long_business_summary": "A diversified holding company.",
        "eps_ttm": 5.0, "market_cap": 20_000_000_000,
    }
    assert classify(fin)["stock_type"] == "MID_CAP"


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


def test_early_growth_weights_no_sotp():
    # SOTP was removed entirely (dead code). EARLY_GROWTH's dcf/ev_sales still carry
    # the tier at the redistributed ratio.
    res = classify({"sector": "Technology", "revenue_growth": 0.35, "eps_ttm": -1.2,
                    "ebitda_ttm": 10})
    w = res["method_weights"]
    assert "sotp" not in w
    assert w["dcf"]["weight"] == pytest.approx(0.4667, abs=1e-4)
    assert w["ev_sales"]["weight"] == pytest.approx(0.5333, abs=1e-4)


def test_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.18, "eps_ttm": 3.0, "dividend_yield": 0.0}
    assert classify(fin)["stock_type"] == "GROWTH"


def test_trillion_dollar_grower_is_mega_cap():
    # A $1T+ fast grower is a MEGA_CAP, not GROWTH (regression: META/MSFT/GOOGL
    # were mislabeled GROWTH; the GROWTH rule has a mega-cap ceiling). The >$1T
    # size default is its own MEGA_CAP tier, distinct from the $100B-$1T LARGE_CAP.
    fin = {"sector": "Technology", "revenue_growth": 0.15, "eps_ttm": 20.0,
           "ebitda_ttm": 100_000_000_000, "dividend_yield": 0.0,
           "market_cap": 1_400_000_000_000}
    assert classify(fin)["stock_type"] == "MEGA_CAP"


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
    assert "sotp" not in res["method_weights"]


def test_mega_cap_weights_shape():
    # MEGA_CAP (>$1T) leans slightly more on DCF than LARGE_CAP (.55 vs .50) and
    # trims P/E (.10 vs .15); the EV leg matches LARGE_CAP (.35) and there is no
    # standalone EV/Sales weight (pick_ev_multiple would fold it into EV/EBITDA
    # for the healthy-margin names this tier holds).
    res = classify({"sector": "Technology", "eps_ttm": 5.0,
                    "market_cap": 2_000_000_000_000})
    assert res["stock_type"] == "MEGA_CAP"
    assert res["method_weights"]["dcf"]["weight"] == 0.55
    assert res["method_weights"]["ev_ebitda"]["weight"] == 0.35
    assert res["method_weights"]["pe"]["weight"] == 0.10
    assert res["method_weights"]["ev_sales"]["weight"] == 0.0


def test_large_cap_stays_below_trillion():
    # The $100B-$1T band remains LARGE_CAP; only >$1T crosses into MEGA_CAP.
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005, "market_cap": 900_000_000_000}
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


def test_payment_network_above_trillion_is_mega_cap():
    # Documents the GROWTH vs MEGA_CAP boundary: a >$1T network fails the GROWTH
    # size gate and lands in the MEGA_CAP size default (>$1T tier).
    assert classify(_payment_network_fin(market_cap=1_200_000_000_000))["stock_type"] == "MEGA_CAP"


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

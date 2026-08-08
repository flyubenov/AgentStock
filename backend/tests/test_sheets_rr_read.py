from services.sheets import _row_to_database_row


def test_database_row_parses_risk_reward_ratio_from_col_r():
    # 7 identity/valuation cols (0-6) + 9 model cols (7-15) + Q quality (16) + R ratio (17)
    row = ["AAPL", "Apple", "2026-01-01", "GROWTH", "200", "180", "10",
           "", "", "", "", "", "", "", "", "",        # 9 model columns
           "8.5",                                       # col Q — quality score
           "1.85"]                                      # col R — risk-reward ratio
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio == 1.85
    assert dr.quality_score == 8.5


def test_database_row_missing_risk_reward_is_none():
    # A legacy short row (pre-Risk-Reward) must pad cleanly to None, not IndexError.
    row = ["MSFT", "Microsoft", "2026-01-01", "GROWTH", "300", "290", "3"]
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio is None
    assert dr.quality_score is None


def test_database_row_blank_risk_reward_cell_is_none():
    row = ["NBIS", "Nebius", "2026-01-01", "EARLY_GROWTH", "", "100", "",
           "", "", "", "", "", "", "", "", "", "7.0", ""]  # col R blank (N/A)
    dr = _row_to_database_row(row)
    assert dr.risk_reward_ratio is None

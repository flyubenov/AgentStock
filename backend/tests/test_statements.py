import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch
from services.statements import _statement_to_dict, fetch_treasury_10y


def _df():
    cols = [datetime(2025, 9, 30), datetime(2024, 9, 30), datetime(2023, 9, 30)]
    return pd.DataFrame(
        {cols[0]: [100.0, 40.0], cols[1]: [90.0, float("nan")], cols[2]: [80.0, 30.0]},
        index=["Total Revenue", "EBITDA"],
    )


def test_statement_to_dict_orders_years_desc_and_maps_nan_to_none():
    out = _statement_to_dict(_df())
    assert out["years"] == [2025, 2024, 2023]
    assert out["rows"]["Total Revenue"] == [100.0, 90.0, 80.0]
    assert out["rows"]["EBITDA"] == [40.0, None, 30.0]  # NaN -> None


def test_statement_to_dict_empty_is_none():
    assert _statement_to_dict(None) is None
    assert _statement_to_dict(pd.DataFrame()) is None


def test_fetch_treasury_10y_converts_percent_to_fraction():
    # ^TNX quotes the 10y yield in percent (4.57 = 4.57%); the fetch must return the
    # fraction 0.0457, not 0.000457 (the old /1000 bug understated the risk-free 10x
    # and collapsed every WACC / ROIC-spread score).
    fetch_treasury_10y.cache_clear()
    hist = pd.DataFrame({"Close": [4.50, 4.57]})
    with patch("services.statements.yf.Ticker") as ticker:
        ticker.return_value.history.return_value = hist
        assert fetch_treasury_10y() == pytest.approx(0.0457, abs=1e-6)
    fetch_treasury_10y.cache_clear()

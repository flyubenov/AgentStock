import pandas as pd
from datetime import datetime
from services.statements import _statement_to_dict


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

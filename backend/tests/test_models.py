import pytest
from valuation import models as m

GROWTH = {"optimistic": 0.12, "realistic": 0.07, "pessimistic": 0.03}


def test_nav_is_exact():
    # bvps=10, net_debt=0 -> fv = 10 * 0.90
    fin = {"book_value_per_share": 10.0, "net_debt": 0, "shares_outstanding": 1_000}
    r = m.calc_nav(fin)
    assert r["fair_value"] == pytest.approx(9.0)
    assert r["has_scenarios"] is False


def test_pb_justified_is_exact():
    # roe=0.10, discount=0.10 -> justifiedPB=1.0 -> fv = 10 * 1.0 * 0.90
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.10}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(9.0)


def test_pb_floor_justified_pb_at_0_1():
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.0}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(10.0 * 0.1 * 0.90)


def test_missing_inputs_return_null():
    assert m.calc_dcf({"fcf_ttm": None, "shares_outstanding": 1000}, GROWTH)["fair_value"] is None
    assert m.calc_ev_ebitda({"ebitda_ttm": None, "ev_ebitda": 10, "shares_outstanding": 1}, GROWTH)["fair_value"] is None
    assert m.calc_pe({"eps_ttm": 0, "payout_ratio": 0.5}, GROWTH)["fair_value"] is None
    assert m.calc_ddm({"dividend_rate": 0}, GROWTH)["fair_value"] is None


def test_ev_ebitda_multiple_is_capped():
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    capped = m.calc_ev_ebitda({**base, "ev_ebitda": 50.0}, GROWTH)["fair_value"]
    at_cap = m.calc_ev_ebitda({**base, "ev_ebitda": 20.0}, GROWTH)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_ev_sales_multiple_is_capped():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    capped = m.calc_ev_sales({**base, "ev_sales": 20.0}, GROWTH)["fair_value"]
    at_cap = m.calc_ev_sales({**base, "ev_sales": 8.0}, GROWTH)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_dcf_scenarios_ordered_for_positive_inputs():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    s = m.calc_dcf(fin, GROWTH)["scenarios"]
    assert s["optimistic"] > s["realistic"] > s["pessimistic"] > 0




def test_composite_weighted_average():
    results = {
        "a": {"fair_value": 100.0, "weight": 0.75},
        "b": {"fair_value": 50.0, "weight": 0.25},
        "c": {"fair_value": None, "weight": 0.5},  # dropped
    }
    assert m.composite(results) == pytest.approx((100 * 0.75 + 50 * 0.25) / 1.0)


def test_composite_empty_is_none():
    assert m.composite({"a": {"fair_value": None, "weight": 0.5}}) is None


def test_ev_ebitda_exit_compressed_by_conversion():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 15.0, "net_debt": 0, "shares_outstanding": 100_000}
    uncompressed = m.calc_ev_ebitda(base, GROWTH)["fair_value"]                      # no fcf -> cap path, 15x
    compressed = m.calc_ev_ebitda({**base, "fcf_ttm": 400_000}, GROWTH)["fair_value"]  # conv 0.40 -> ~5.89x
    assert compressed < uncompressed


def test_ev_ebitda_compression_floors_conversion():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 15.0, "net_debt": 0, "shares_outstanding": 100_000}
    very_low = m.calc_ev_ebitda({**base, "fcf_ttm": 10_000}, GROWTH)["fair_value"]   # conv 0.01 -> floor 0.40
    at_floor = m.calc_ev_ebitda({**base, "fcf_ttm": 400_000}, GROWTH)["fair_value"]  # conv 0.40
    assert very_low == pytest.approx(at_floor)


def test_ev_ebitda_compression_never_inflates_cheap():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 5.0, "net_debt": 0, "shares_outstanding": 100_000}
    cheap = m.calc_ev_ebitda({**base, "fcf_ttm": 650_000}, GROWTH)["fair_value"]  # conv 0.65 -> 9.56x, min keeps 5x
    no_fcf = m.calc_ev_ebitda(base, GROWTH)["fair_value"]                          # cap path -> 5x
    assert cheap == pytest.approx(no_fcf)


def test_ev_sales_exit_compressed_to_mature():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    high = m.calc_ev_sales({**base, "ev_sales": 6.0}, GROWTH)["fair_value"]       # -> mature 2x
    at_mature = m.calc_ev_sales({**base, "ev_sales": 2.0}, GROWTH)["fair_value"]
    assert high == pytest.approx(at_mature)

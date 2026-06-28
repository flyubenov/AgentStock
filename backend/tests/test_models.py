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
    assert m.calc_pe({"eps_ttm": 0, "trailing_pe": 20})["fair_value"] is None
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


def test_pe_caps_at_mature_multiple():
    # trailing P/E above the cap -> reverts to MATURE_PE_CAP
    fv = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 35.0})["fair_value"]
    assert fv == pytest.approx(10.0 * m.MATURE_PE_CAP * m.MOS)


def test_pe_keeps_trailing_below_cap():
    # trailing P/E below the cap -> never inflates, keep trailing
    fv = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 12.0})["fair_value"]
    assert fv == pytest.approx(10.0 * 12.0 * m.MOS)


def test_pe_null_on_nonpositive_eps():
    assert m.calc_pe({"eps_ttm": 0, "trailing_pe": 20.0})["fair_value"] is None
    assert m.calc_pe({"eps_ttm": -2.0, "trailing_pe": 20.0})["fair_value"] is None


def test_pe_null_on_missing_trailing_pe():
    assert m.calc_pe({"eps_ttm": 5.0, "trailing_pe": None})["fair_value"] is None
    assert m.calc_pe({"eps_ttm": 5.0, "trailing_pe": 0})["fair_value"] is None


def test_pe_is_single_value():
    r = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 18.0})
    assert r["has_scenarios"] is False
    assert r["scenarios"]["optimistic"] == r["scenarios"]["pessimistic"] == r["fair_value"]


# -- forward P/E (PEG-capped) --------------------------------------------------
def test_pe_forward_targets_forward_pe():
    # forward P/E below the PEG ceiling -> forward P/E binds (not trailing/mature)
    fin = {"eps_ttm": 10.0, "trailing_pe": 50.0, "forward_pe": 30.0, "earnings_growth": 0.20}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * 30.0 * m.MOS)


def test_pe_forward_peg_ceiling_binds():
    # forward P/E above the PEG ceiling -> ceiling (growth% * PEG_CEILING) binds
    fin = {"eps_ttm": 10.0, "trailing_pe": 70.0, "forward_pe": 50.0, "earnings_growth": 0.10}
    peg_cap = 0.10 * 100 * m.PEG_CEILING   # = 20x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * peg_cap * m.MOS)


def test_pe_forward_uses_revenue_growth_when_earnings_missing():
    fin = {"eps_ttm": 10.0, "forward_pe": 50.0, "earnings_growth": None, "revenue_growth": 0.10}
    peg_cap = 0.10 * 100 * m.PEG_CEILING   # = 20x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * peg_cap * m.MOS)


def test_pe_forward_falls_back_to_mature_without_forward_pe():
    # no forward P/E -> revert to the mature trailing path
    fin = {"eps_ttm": 10.0, "trailing_pe": 35.0, "forward_pe": None, "earnings_growth": 0.30}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * m.MATURE_PE_CAP * m.MOS)


def test_pe_forward_falls_back_to_mature_without_growth_signal():
    # forward P/E present but no positive growth signal -> mature cap bounds it
    fin = {"eps_ttm": 10.0, "trailing_pe": 35.0, "forward_pe": 40.0,
           "earnings_growth": None, "revenue_growth": 0}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * m.MATURE_PE_CAP * m.MOS)


def test_pe_forward_never_inflates_above_forward():
    # PEG ceiling generous, forward low -> forward still bounds (never inflate)
    fin = {"eps_ttm": 10.0, "trailing_pe": 60.0, "forward_pe": 18.0, "earnings_growth": 0.40}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * 18.0 * m.MOS)


def test_pe_non_forward_unchanged_with_forward_present():
    # default path ignores forward P/E entirely -> mature trailing cap
    fin = {"eps_ttm": 10.0, "trailing_pe": 35.0, "forward_pe": 50.0, "earnings_growth": 0.30}
    fv = m.calc_pe(fin)["fair_value"]
    assert fv == pytest.approx(10.0 * m.MATURE_PE_CAP * m.MOS)


# -- EV/EBITDA: compression toggle + historical-median multiple ----------------
def test_ev_ebitda_compress_false_skips_compression():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 15.0, "net_debt": 0,
            "shares_outstanding": 100_000, "fcf_ttm": 400_000}  # conv 0.40 -> compresses normally
    compressed = m.calc_ev_ebitda(base, GROWTH)["fair_value"]
    uncompressed = m.calc_ev_ebitda(base, GROWTH, compress=False)["fair_value"]
    uncompressed_15x = m.calc_ev_ebitda({k: v for k, v in base.items() if k != "fcf_ttm"}, GROWTH)["fair_value"]
    assert uncompressed > compressed
    assert uncompressed == pytest.approx(uncompressed_15x)


def test_ev_ebitda_still_caps_at_20():
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000, "fcf_ttm": 600_000}
    capped = m.calc_ev_ebitda({**base, "ev_ebitda": 50.0}, GROWTH, compress=False)["fair_value"]
    at_cap = m.calc_ev_ebitda({**base, "ev_ebitda": 20.0}, GROWTH, compress=False)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_ev_ebitda_hist_multiple_overrides_current():
    # hist_multiple replaces the current trailing multiple entirely
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 50.0, "net_debt": 0, "shares_outstanding": 100_000}
    at_hist = m.calc_ev_ebitda(base, GROWTH, hist_multiple=12.0, compress=False)["fair_value"]
    at_12_direct = m.calc_ev_ebitda({**base, "ev_ebitda": 12.0}, GROWTH, compress=False)["fair_value"]
    assert at_hist == pytest.approx(at_12_direct)


def test_ev_ebitda_hist_multiple_still_capped_at_20():
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    over_cap = m.calc_ev_ebitda(base, GROWTH, hist_multiple=30.0, compress=False)["fair_value"]
    at_cap = m.calc_ev_ebitda(base, GROWTH, hist_multiple=20.0, compress=False)["fair_value"]
    assert over_cap == pytest.approx(at_cap)

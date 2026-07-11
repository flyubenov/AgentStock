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


# -- size-coupled growth fade --------------------------------------------------
def test_fade_hold_years_bands():
    assert m._fade_hold_years(2_000_000_000_000) == m.FADE_HOLD_MEGA   # >= $1T
    assert m._fade_hold_years(300_000_000_000) == m.FADE_HOLD_LARGE    # >= $150B
    assert m._fade_hold_years(40_000_000_000) == m.FADE_HOLD_MID       # < $150B
    assert m._fade_hold_years(None) == m.FADE_HOLD_MID                 # missing -> smallest band


def test_faded_rate_holds_then_decays_to_terminal():
    # hold 3: years 1-3 keep g_start, year HORIZON lands on TERMINAL_GROWTH
    assert m._faded_rate(0.20, 3, 1) == pytest.approx(0.20)
    assert m._faded_rate(0.20, 3, 3) == pytest.approx(0.20)
    assert m._faded_rate(0.20, 3, m.HORIZON) == pytest.approx(m.TERMINAL_GROWTH)
    assert 0.20 > m._faded_rate(0.20, 3, 6) > m.TERMINAL_GROWTH  # mid-fade is between
    # hold >= HORIZON disables the fade (flat growth)
    assert m._faded_rate(0.20, m.HORIZON, m.HORIZON) == pytest.approx(0.20)


def test_dcf_fade_is_more_aggressive_for_mega_caps():
    # identical company, different size -> mega ($2T) fades growth sooner -> lower FV
    base = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    mega = m.calc_dcf({**base, "market_cap": 2_000_000_000_000}, GROWTH)["fair_value"]
    small = m.calc_dcf({**base, "market_cap": 40_000_000_000}, GROWTH)["fair_value"]
    assert mega < small


def test_fade_relief_for_high_growth_mega_cap():
    # A mega-cap (>= $1T) still growing very fast keeps the small-cap hold (the
    # size penalty is a base-rate-drag proxy that doesn't apply while the growth
    # is demonstrably there, e.g. AVGO/NVDA on the AI ramp).
    mc = 2_000_000_000_000
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF) == m.FADE_HOLD_MID
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF - 0.01) == m.FADE_HOLD_MEGA
    assert m._fade_hold_years(mc, None) == m.FADE_HOLD_MEGA   # no growth signal -> full fade


def test_dcf_fade_relieved_for_high_growth_mega_cap():
    # Same $2T company: a 45% grower fades gentler (higher FV) than a flat one.
    base = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "market_cap": 2_000_000_000_000}
    fast = m.calc_dcf({**base, "revenue_growth": 0.45}, GROWTH)["fair_value"]
    flat = m.calc_dcf({**base, "revenue_growth": 0.05}, GROWTH)["fair_value"]
    assert fast > flat


def test_ev_ebitda_fade_is_more_aggressive_for_mega_caps():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 12.0, "net_debt": 0, "shares_outstanding": 100_000}
    mega = m.calc_ev_ebitda({**base, "market_cap": 2_000_000_000_000}, GROWTH, compress=False)["fair_value"]
    small = m.calc_ev_ebitda({**base, "market_cap": 40_000_000_000}, GROWTH, compress=False)["fair_value"]
    assert mega < small




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


def test_pe_forward_normalizes_depressed_trailing_eps():
    # Trailing EPS depressed by amortization (trailing P/E >> forward P/E, e.g.
    # AVGO post-VMware): the forward leg values off forward EPS, not the
    # depressed trailing figure. trailing_pe/forward_pe = 3.2 > DEPRESSED_PE_RATIO.
    fin = {"eps_ttm": 6.0, "forward_eps": 19.0, "trailing_pe": 62.0,
           "forward_pe": 19.2, "earnings_growth": 0.85}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(19.0 * 19.2 * m.MOS)   # forward EPS, not 6.0


def test_pe_forward_keeps_trailing_eps_when_not_depressed():
    # Healthy name (trailing P/E close to forward P/E): forward EPS is NOT
    # substituted even when present, so the leg stays on trailing EPS.
    fin = {"eps_ttm": 27.0, "forward_eps": 36.0, "trailing_pe": 20.5,
           "forward_pe": 15.5, "earnings_growth": 0.62}   # ratio 1.32 < 1.5
    peg_cap = 0.62 * 100 * m.PEG_CEILING
    target = min(15.5, peg_cap)
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(27.0 * target * m.MOS)   # trailing EPS retained


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


def test_ev_ebitda_hist_base_projects_statement_ebitda_not_info_ebitda():
    # The historical median multiple is reconstructed from statement EBITDA, which
    # can differ ~2x from yfinance info['ebitda'] (content amortization at NFLX).
    # When a hist base is supplied, the leg must project THAT base, not ebitda_ttm.
    fin = {"ebitda_ttm": 14_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    with_base = m.calc_ev_ebitda(fin, GROWTH, hist_multiple=10.0,
                                 hist_ebitda_base=30_000_000, compress=False)["fair_value"]
    # equivalent to running with the statement EBITDA as the outright base
    direct = m.calc_ev_ebitda({**fin, "ebitda_ttm": 30_000_000}, GROWTH,
                              hist_multiple=10.0, compress=False)["fair_value"]
    info_base = m.calc_ev_ebitda(fin, GROWTH, hist_multiple=10.0, compress=False)["fair_value"]
    assert with_base == pytest.approx(direct)
    assert with_base > info_base  # the bigger statement base lifts the leg


def test_ev_ebitda_hist_base_ignored_without_hist_multiple():
    # A stray base with no hist_multiple must not hijack the current-multiple path.
    fin = {"ebitda_ttm": 14_000_000, "ev_ebitda": 12.0, "net_debt": 0,
           "shares_outstanding": 100_000}
    with_base = m.calc_ev_ebitda(fin, GROWTH, hist_ebitda_base=30_000_000,
                                 compress=False)["fair_value"]
    plain = m.calc_ev_ebitda(fin, GROWTH, compress=False)["fair_value"]
    assert with_base == pytest.approx(plain)

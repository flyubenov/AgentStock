import pytest
from valuation import models as m

GROWTH = {"optimistic": 0.12, "realistic": 0.07, "pessimistic": 0.03}


def test_nav_is_exact():
    # bvps=10, net_debt=0 -> fv = 10 * 0.90
    fin = {"book_value_per_share": 10.0, "net_debt": 0, "shares_outstanding": 1_000}
    r = m.calc_nav(fin)
    assert r["fair_value"] == pytest.approx(9.0)
    assert r["has_scenarios"] is False


def test_nav_ignores_net_debt():
    # NAV = bvps * MOS. book_value_per_share is already equity (assets - all
    # liabilities, debt included), so net debt must NOT be subtracted again.
    # A net-debt name and a net-cash name with the same bvps get the same NAV.
    net_debt = {"book_value_per_share": 10.0, "net_debt": 5_000, "shares_outstanding": 1_000}
    net_cash = {"book_value_per_share": 10.0, "net_debt": -2_000, "shares_outstanding": 1_000}
    assert m.calc_nav(net_debt)["fair_value"] == pytest.approx(9.0)
    assert m.calc_nav(net_cash)["fair_value"] == pytest.approx(9.0)


def test_pb_justified_is_exact():
    # roe=0.10, discount=0.10 -> justifiedPB=1.0 -> fv = 10 * 1.0 * 0.90
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.10}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(9.0)


def test_pb_floor_justified_pb_at_0_1():
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.0}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(10.0 * 0.1 * 0.90)


def test_pb_roe_equals_coe_is_one_times_book():
    # Invariant: at ROE == COE the growth-adjusted P/B is exactly 1.0, for any COE.
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.085,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(90.0)   # 100 * 1.0 * 0.90


def test_pb_growth_adjusted_at_bank_coe():
    # roe 0.178, coe 0.085, g 0.03 -> (0.178-0.03)/(0.085-0.03) = 2.69090909
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.178,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(242.1818, abs=1e-3)


def test_pb_defaults_to_discount_rate_when_coe_absent():
    # No cost_of_equity -> COE = DISCOUNT_RATE (0.10): (0.178-0.03)/(0.10-0.03)=2.11428
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.178}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(190.2857, abs=1e-3)


def test_pb_lower_coe_lifts_value_for_roe_above_coe():
    hi = m.calc_pb({"book_value_per_share": 100.0, "return_on_equity": 0.178,
                    "cost_of_equity": 0.10})["fair_value"]
    lo = m.calc_pb({"book_value_per_share": 100.0, "return_on_equity": 0.178,
                    "cost_of_equity": 0.085})["fair_value"]
    assert lo > hi


def test_pb_distorted_roe_is_capped():
    # roe 0.452 (ALL-like), coe 0.085, cap 3x -> ROE clipped to 0.255
    # justified = (0.255-0.03)/(0.085-0.03) = 4.09090909 -> 100 * 4.0909 * 0.90
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.452,
           "cost_of_equity": 0.085}
    capped = m.calc_pb(fin)["fair_value"]
    assert capped == pytest.approx(368.1818, abs=1e-3)
    # strictly below what the uncapped ROE would have produced
    uncapped_pb = (0.452 - 0.03) / (0.085 - 0.03)
    assert capped < 100.0 * uncapped_pb * 0.90


def test_pb_floor_holds_at_bank_coe_for_subgrowth_roe():
    # roe 0.02 < g -> justified negative -> floored at 0.1 -> 100 * 0.1 * 0.90
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.02,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(9.0)


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


def test_dcf_scenarios_ordered_for_positive_inputs():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    s = m.calc_dcf(fin, GROWTH)["scenarios"]
    assert s["optimistic"] > s["realistic"] > s["pessimistic"] > 0


# -- DCF forward run-rate rebase (severe post-acquisition earnings trough) ------
def test_rebased_dcf_base_fires_on_deep_trough():
    # Forward EPS ~3.9x trailing (SNPS post-Ansys signature): trailing FCF is a trough,
    # so the base is the forward run-rate owner earnings (forward EPS x shares).
    fin = {"forward_eps": 17.26, "eps_ttm": 4.39, "shares_outstanding": 191_500_000,
           "fcf_ttm": 1_349_000_000}
    assert m.rebased_dcf_base(fin) == pytest.approx(17.26 * 191_500_000)


def test_rebased_dcf_base_skips_shallow_trough():
    # Forward EPS only ~1.3x trailing -> normal forward growth, not a trough.
    fin = {"forward_eps": 5.7, "eps_ttm": 4.39, "shares_outstanding": 191_500_000,
           "fcf_ttm": 1_349_000_000}
    assert m.rebased_dcf_base(fin) is None


def test_rebased_dcf_base_skips_ongoing_amortization_trough():
    # CDNS-like: forward EPS ~2.2x trailing from ONGOING acquisition amortization / SBC
    # add-backs, but trailing FCF is representative (no just-closed mega-deal). Below the
    # severe-trough ratio (2.5) -> no rebase; the DCF keeps its trailing-FCF base. Only a
    # partial-consolidation collapse (SNPS ~3.9x) clears the bar.
    fin = {"forward_eps": 9.66, "eps_ttm": 4.39, "shares_outstanding": 272_000_000,
           "fcf_ttm": 1_590_000_000, "revenue_ttm": 5_530_000_000}   # ratio 2.2
    assert m.rebased_dcf_base(fin) is None


def test_rebased_dcf_base_only_helps():
    # Deep-trough ratio, but the forward run-rate base is below trailing FCF -> keep
    # trailing FCF (the rebase can only ever lift the base, never lower it).
    fin = {"forward_eps": 17.26, "eps_ttm": 4.39, "shares_outstanding": 191_500_000,
           "fcf_ttm": 5_000_000_000}
    assert m.rebased_dcf_base(fin) is None


def test_rebased_dcf_base_needs_positive_data():
    assert m.rebased_dcf_base({"forward_eps": 17.0, "eps_ttm": 0,
                               "shares_outstanding": 1e6, "fcf_ttm": 1e6}) is None
    assert m.rebased_dcf_base({"forward_eps": None, "eps_ttm": 4.0,
                               "shares_outstanding": 1e6, "fcf_ttm": 1e6}) is None


def test_rebased_dcf_base_rejects_impossible_net_margin():
    # AVGO-like glitched forward-EPS feed: forward run-rate earnings exceed revenue (a
    # >100% net margin is impossible), so the forward figure is unreliable -> no rebase
    # (the DCF keeps its representative trailing-FCF base).
    fin = {"forward_eps": 19.65, "eps_ttm": 4.5, "shares_outstanding": 4_700_000_000,
           "fcf_ttm": 26_900_000_000, "revenue_ttm": 60_000_000_000}  # run-rate 92.4B > 60B
    assert m.rebased_dcf_base(fin) is None
    # Same deep trough but a sane forward margin (run-rate < revenue) -> rebase fires.
    ok = {"forward_eps": 17.26, "eps_ttm": 4.39, "shares_outstanding": 191_500_000,
          "fcf_ttm": 1_349_000_000, "revenue_ttm": 8_680_000_000}
    assert m.rebased_dcf_base(ok) == pytest.approx(17.26 * 191_500_000)


def test_dcf_base_override_replaces_fcf_base():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    base_leg = m.calc_dcf(fin, GROWTH)["fair_value"]
    over_leg = m.calc_dcf(fin, GROWTH, base_override=3_000_000)["fair_value"]
    assert over_leg == pytest.approx(3 * base_leg)   # net_debt 0 -> exactly linear in base


def test_dcf_value_cap_limits_each_scenario():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    uncapped = m.calc_dcf(fin, GROWTH)["scenarios"]
    cap = (uncapped["realistic"] + uncapped["pessimistic"]) / 2   # between pess and real
    capped = m.calc_dcf(fin, GROWTH, value_cap=cap)["scenarios"]
    assert capped["optimistic"] == pytest.approx(cap)                    # was above -> capped
    assert capped["realistic"] == pytest.approx(cap)                     # was above -> capped
    assert capped["pessimistic"] == pytest.approx(uncapped["pessimistic"])  # below -> untouched


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


def test_fade_relief_for_high_growth_large_cap():
    # The $150B-$1T band mirrors the mega valve: a fast grower there keeps the
    # small-cap hold (FADE_HOLD_MID) instead of the faster mid-band fade. Restores
    # monotonicity -- a mid-band grower must not fade harder than smaller AND larger
    # peers at the same rate (e.g. PLTR at ~$317B / ~85% growth).
    mc = 300_000_000_000
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF) == m.FADE_HOLD_MID
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF - 0.01) == m.FADE_HOLD_LARGE
    assert m._fade_hold_years(mc, None) == m.FADE_HOLD_LARGE   # no growth signal -> mid-band fade


def test_fade_hold_years_monotonic_at_high_growth():
    # At a fixed high growth rate, a larger company never holds LONGER than a smaller
    # one: small (<$150B) == large ($150B-$1T) == mega (>=$1T) all == FADE_HOLD_MID.
    g = 0.50
    small = m._fade_hold_years(40_000_000_000, g)
    large = m._fade_hold_years(300_000_000_000, g)
    mega = m._fade_hold_years(2_000_000_000_000, g)
    assert small == large == mega == m.FADE_HOLD_MID


def test_dcf_fade_relieved_for_high_growth_large_cap():
    # Same $300B company: a 45% grower fades gentler (higher FV) than a flat one.
    base = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "market_cap": 300_000_000_000}
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


def test_pe_forward_overrides_noise_earnings_growth_with_revenue():
    # HOOD shape: tiny-positive earnings growth badly contradicted by strong revenue
    # growth -> source growth from revenue (bounded), not the 2.7% noise value.
    fin = {"eps_ttm": 2.06, "trailing_pe": 53.3, "forward_pe": 36.0,
           "earnings_growth": 0.027, "revenue_growth": 0.151}
    target = min(36.0, 0.151 * 100 * m.PEG_CEILING)   # = 30.2x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(2.06 * target * m.MOS)


def test_pe_forward_keeps_healthy_earnings_growth_below_floor():
    # TSLA shape: earnings growth is below the floor but revenue growth does NOT
    # clear the ratio (0.158 !> 0.083*3) -> earnings growth is kept, leg unchanged.
    fin = {"eps_ttm": 2.58, "trailing_pe": 358.9, "forward_pe": 153.0,
           "earnings_growth": 0.083, "revenue_growth": 0.158}
    target = min(153.0, 0.083 * 100 * m.PEG_CEILING)  # = 16.6x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(2.58 * target * m.MOS)


def test_pe_forward_keeps_high_earnings_growth_above_floor():
    # QCOM shape: earnings growth well above the floor is always trusted, even when
    # revenue growth is negative -> no override, forward_pe binds.
    fin = {"eps_ttm": 9.31, "trailing_pe": 19.76, "forward_pe": 16.71,
           "earnings_growth": 1.73, "revenue_growth": -0.035}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(9.31 * 16.71 * m.MOS)


def test_pe_forward_override_needs_material_ratio():
    # Guard the ratio: revenue only modestly above earnings growth must NOT override.
    fin = {"eps_ttm": 10.0, "trailing_pe": 40.0, "forward_pe": 30.0,
           "earnings_growth": 0.05, "revenue_growth": 0.10}   # 0.10 !> 0.05*3
    target = min(30.0, 0.05 * 100 * m.PEG_CEILING)   # = 10x, off earnings growth
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * target * m.MOS)


def test_pe_forward_override_ignores_nonpositive_revenue_under_floor():
    # Small-positive earnings growth under the floor but revenue growth is negative
    # (or missing) -> override must NOT fire; the earnings-growth signal is kept.
    target = min(30.0, 0.05 * 100 * m.PEG_CEILING)   # = 10x, off earnings growth
    neg = {"eps_ttm": 10.0, "trailing_pe": 40.0, "forward_pe": 30.0,
           "earnings_growth": 0.05, "revenue_growth": -0.20}
    assert m.calc_pe(neg, forward=True)["fair_value"] == pytest.approx(10.0 * target * m.MOS)
    missing = {"eps_ttm": 10.0, "trailing_pe": 40.0, "forward_pe": 30.0,
               "earnings_growth": 0.05, "revenue_growth": None}
    assert m.calc_pe(missing, forward=True)["fair_value"] == pytest.approx(10.0 * target * m.MOS)


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


def test_ev_ebitda_spot_multiple_caps_at_20_even_with_growth():
    # A SPOT trailing multiple (not a durable historical median) is never granted the
    # growth-coupled lift — it could be a one-quarter EBITDA dip — so it caps at 20 even
    # for a fast grower.
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "fcf_ttm": 600_000, "revenue_growth_stmt": 0.40}
    capped = m.calc_ev_ebitda({**base, "ev_ebitda": 50.0}, GROWTH, compress=False)["fair_value"]
    at_cap = m.calc_ev_ebitda({**base, "ev_ebitda": 20.0}, GROWTH, compress=False)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_ev_ebitda_hist_multiple_overrides_current():
    # hist_multiple replaces the current trailing multiple entirely
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 50.0, "net_debt": 0, "shares_outstanding": 100_000}
    at_hist = m.calc_ev_ebitda(base, GROWTH, hist_multiple=12.0, compress=False)["fair_value"]
    at_12_direct = m.calc_ev_ebitda({**base, "ev_ebitda": 12.0}, GROWTH, compress=False)["fair_value"]
    assert at_hist == pytest.approx(at_12_direct)


def test_ev_ebitda_hist_multiple_capped_at_20_without_growth():
    # With no demonstrated-growth signal the durable median still caps at the 20 base
    # ceiling (the growth-coupled lift only fires for a genuine grower).
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    over_cap = m.calc_ev_ebitda(base, GROWTH, hist_multiple=30.0, compress=False)["fair_value"]
    at_cap = m.calc_ev_ebitda(base, GROWTH, hist_multiple=20.0, compress=False)["fair_value"]
    assert over_cap == pytest.approx(at_cap)


def test_ev_ebitda_durable_median_lifted_by_growth():
    # A genuine grower's durable historical median survives above the 20 base ceiling,
    # up to the 30x terminal ceiling — the ANET fix (27.5x median no longer clamped to 20).
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "revenue_growth_stmt": 0.30}
    at_275 = m.calc_ev_ebitda(base, GROWTH, hist_multiple=27.5, compress=False)["fair_value"]
    at_20 = m.calc_ev_ebitda(base, GROWTH, hist_multiple=20.0, compress=False)["fair_value"]
    at_30_direct = m.calc_ev_ebitda(base, GROWTH, hist_multiple=27.5, compress=False)["fair_value"]
    assert at_275 > at_20                      # the median is no longer clamped to 20
    assert at_275 == pytest.approx(at_30_direct)


def test_ev_ebitda_durable_median_trimmed_to_terminal_ceiling():
    # An extreme median (NVDA-shape peak-era multiple) is trimmed to the 30x terminal
    # ceiling, not extrapolated forever.
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "revenue_growth_stmt": 0.45}
    over = m.calc_ev_ebitda(base, GROWTH, hist_multiple=45.0, compress=False)["fair_value"]
    at_ceiling = m.calc_ev_ebitda(base, GROWTH, hist_multiple=30.0, compress=False)["fair_value"]
    assert over == pytest.approx(at_ceiling)


def test_ev_ebitda_ceiling_ramps_with_growth():
    assert m._ev_ebitda_ceiling(0.05, durable=True) == pytest.approx(20.0)   # below G_LO
    assert m._ev_ebitda_ceiling(0.20, durable=True) == pytest.approx(25.0)   # midpoint
    assert m._ev_ebitda_ceiling(0.30, durable=True) == pytest.approx(30.0)   # at G_HI
    assert m._ev_ebitda_ceiling(0.80, durable=True) == pytest.approx(30.0)   # saturated
    assert m._ev_ebitda_ceiling(0.30, durable=False) == pytest.approx(20.0)  # spot never lifts
    assert m._ev_ebitda_ceiling(None, durable=True) == pytest.approx(20.0)   # unknown growth


def test_ev_ebitda_ceiling_lifted_by_quality_at_low_growth():
    # A durable high-conversion franchise (CDNS: 0.79 FCF/EBITDA) earns a PARTIAL lift at a
    # modest growth rate — the moat premium is credited on quality, not only on growth, but a
    # merely-good conversion isn't maxed. Growth alone (14%) would give ~22x.
    growth_only = m._ev_ebitda_ceiling(0.14, durable=True)                       # ~22
    with_quality = m._ev_ebitda_ceiling(0.14, durable=True, conversion=0.79)     # ~25.6
    assert with_quality > growth_only
    assert with_quality == pytest.approx(25.6)


def test_ev_ebitda_ceiling_quality_takes_the_greater_fraction():
    # ceiling rides max(growth_frac, quality_frac): a fast grower with weak conversion still
    # gets the growth lift; conversion below the QUALITY_CONV_LO floor adds nothing.
    assert m._ev_ebitda_ceiling(0.30, durable=True, conversion=0.50) == pytest.approx(30.0)  # growth wins
    assert m._ev_ebitda_ceiling(0.05, durable=True, conversion=0.50) == pytest.approx(20.0)  # neither clears
    assert m._ev_ebitda_ceiling(0.20, durable=True, conversion=0.775) == pytest.approx(25.0) # tie at midpoints


def test_ev_ebitda_quality_lift_respects_mega_ceiling():
    # quality can't push a mega-cap above its lower 25x terminal ceiling.
    assert m._ev_ebitda_ceiling(0.10, durable=True, mega=True, conversion=0.90) == pytest.approx(25.0)


def test_ev_ebitda_quality_lift_needs_a_durable_median():
    # a spot (non-durable) trailing multiple is never lifted, however high the conversion.
    assert m._ev_ebitda_ceiling(0.14, durable=False, conversion=0.90) == pytest.approx(20.0)


def test_ev_ebitda_ceiling_is_lower_for_mega_caps():
    # A >$1T franchise gets a lower terminal ceiling (25x vs 30x) — a sustained mega-cap
    # premium multiple is a stronger claim than a mid-cap one (size base-rate drag).
    assert m._ev_ebitda_ceiling(0.30, durable=True, mega=True) == pytest.approx(25.0)
    assert m._ev_ebitda_ceiling(0.80, durable=True, mega=True) == pytest.approx(25.0)  # saturated lower
    assert m._ev_ebitda_ceiling(0.20, durable=True, mega=True) == pytest.approx(22.5)  # midpoint
    # a mega-cap's durable median is trimmed to 25x, below the 30x a mid-cap would keep
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "revenue_growth_stmt": 0.45}
    mega = m.calc_ev_ebitda({**base, "market_cap": 3_000_000_000_000}, GROWTH,
                            hist_multiple=45.0, compress=False)["fair_value"]
    midcap = m.calc_ev_ebitda({**base, "market_cap": 200_000_000_000}, GROWTH,
                              hist_multiple=45.0, compress=False)["fair_value"]
    assert mega < midcap


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


# -- current run-rate revenue base --------------------------------------------
def test_run_rate_revenue_annualizes_latest_quarter_for_hyper_grower():
    # NBIS: TTM ($873M) is a trailing AVERAGE centred ~6 months back, so it lags the
    # current run-rate ($399M latest quarter -> $1.596B) by 83% on a name doubling every
    # two quarters. Projecting growth from TTM starts the model below today's actual.
    q = (399.0e6, 227.7e6, 146.1e6, 100.7e6, 50.9e6)
    assert m.run_rate_revenue(q, 873.5e6, 6.839) == pytest.approx(1596.0e6)


def test_run_rate_revenue_declines_seasonal_slow_grower():
    # A retailer's Q4 annualises 60% above TTM, but at 5% YoY growth TTM does NOT lag —
    # the gap is seasonality, and annualising a seasonal peak would inflate the base.
    # The growth gate is what separates "TTM is stale" from "Q4 is big".
    q = (400.0, 200.0, 200.0, 200.0)
    assert m.run_rate_revenue(q, 1000.0, 0.05) is None


def test_run_rate_revenue_is_only_help():
    # A decelerating name's run-rate falls BELOW TTM; never lower the base.
    q = (200.0, 300.0, 300.0, 300.0)
    assert m.run_rate_revenue(q, 1100.0, 0.60) is None


def test_run_rate_revenue_needs_complete_inputs():
    assert m.run_rate_revenue(None, 1000.0, 2.0) is None
    assert m.run_rate_revenue((), 1000.0, 2.0) is None
    assert m.run_rate_revenue((None,), 1000.0, 2.0) is None
    assert m.run_rate_revenue((0.0,), 1000.0, 2.0) is None
    assert m.run_rate_revenue((100.0,), None, 2.0) is None
    assert m.run_rate_revenue((100.0,), 1000.0, None) is None


def test_calc_ev_sales_projects_from_run_rate_when_present():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "ev_sales": 2.0}
    ttm_based = m.calc_ev_sales(base, GROWTH)["fair_value"]
    rr_based = m.calc_ev_sales({**base, "revenue_run_rate": 2_000_000}, GROWTH)["fair_value"]
    # net_debt = 0 -> the leg is linear in the base, so doubling it doubles the value
    assert rr_based == pytest.approx(ttm_based * 2)


def test_calc_ev_sales_falls_back_to_ttm_without_run_rate():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "ev_sales": 2.0}
    assert m.calc_ev_sales({**base, "revenue_run_rate": None}, GROWTH)["fair_value"] == \
        pytest.approx(m.calc_ev_sales(base, GROWTH)["fair_value"])


# -- funding-gap correction (exit_net_debt) ------------------------------------
def test_exit_net_debt_self_gates_on_nonnegative_fcf():
    # FCF >= 0 -> self-funding -> net debt unchanged (the primary safety property).
    assert m.exit_net_debt({"fcf_ttm": 5e8}, 1e9, 0.10, m.HORIZON, 2e9) == 2e9
    assert m.exit_net_debt({"fcf_ttm": 0.0}, 1e9, 0.10, m.HORIZON, 2e9) == 2e9


def test_exit_net_debt_self_gates_on_missing_inputs():
    assert m.exit_net_debt({"fcf_ttm": None}, 1e9, 0.10, m.HORIZON, 2e9) == 2e9
    assert m.exit_net_debt({"fcf_ttm": -1e9}, None, 0.10, m.HORIZON, 2e9) == 2e9
    assert m.exit_net_debt({"fcf_ttm": -1e9}, 0.0, 0.10, m.HORIZON, 2e9) == 2e9


def test_exit_net_debt_accretes_the_burn():
    # A burner's exit net debt exceeds today's by the cumulative funding gap.
    nd = m.exit_net_debt({"fcf_ttm": -5e8}, 1e9, 0.10, m.HORIZON, 2e9)
    assert nd > 2e9


def test_exit_net_debt_more_burn_when_terminal_margin_lower():
    fin = {"fcf_ttm": -5e8}
    lenient = m.exit_net_debt(fin, 1e9, 0.10, m.HORIZON, 0.0, m_term=0.15)
    strict = m.exit_net_debt(fin, 1e9, 0.10, m.HORIZON, 0.0, m_term=0.0)
    assert strict > lenient  # a lower terminal FCF margin -> larger cumulative burn


def test_exit_net_debt_floors_extreme_transient_burn():
    # A -230% transient burn on a tiny revenue base is floored at the sustained-burn cap, so
    # its gap equals that of a name burning exactly at the floor (not the runaway raw margin).
    extreme = m.exit_net_debt({"fcf_ttm": -2.3e9}, 1e9, 0.30, m.HORIZON, 0.0)   # m0 -230% -> floor
    at_floor = m.exit_net_debt({"fcf_ttm": -1e9}, 1e9, 0.30, m.HORIZON, 0.0)    # m0 -100% == floor
    assert extreme == pytest.approx(at_floor)


def test_exit_net_debt_floor_leaves_moderate_burner_untouched():
    # A burner above the floor (e.g. -50%) is unaffected by it: overriding the floor lower
    # changes nothing, confirming the clamp only bites the extreme transient names.
    fin = {"fcf_ttm": -5e8}  # m0 = -50% on rev0 1e9
    default = m.exit_net_debt(fin, 1e9, 0.30, m.HORIZON, 0.0)
    deeper_floor = m.exit_net_debt(fin, 1e9, 0.30, m.HORIZON, 0.0, burn_floor=-3.0)
    assert default == pytest.approx(deeper_floor)


def test_exit_net_debt_more_burn_when_hold_longer():
    fin = {"fcf_ttm": -5e8}
    short = m.exit_net_debt(fin, 1e9, 0.10, m.HORIZON, 0.0, fade_hold=0)
    long_ = m.exit_net_debt(fin, 1e9, 0.10, m.HORIZON, 0.0, fade_hold=4)
    assert long_ > short  # holding the deep burn longer before fading -> larger gap


def test_ev_sales_funding_gap_gates_on_positive_fcf():
    # A self-funding name (positive FCF) is byte-for-byte identical to the frozen bridge.
    base = {"revenue_run_rate": 8e9, "revenue_ttm": 8e9, "ev_sales": 5.0,
            "net_debt": 10e9, "shares_outstanding": 1e8}
    frozen = m.calc_ev_sales(base, GROWTH)["fair_value"]                  # no fcf key
    positive = m.calc_ev_sales({**base, "fcf_ttm": 1e9}, GROWTH)["fair_value"]
    assert positive == pytest.approx(frozen)


def test_ev_sales_funding_gap_lowers_a_burner():
    base = {"revenue_run_rate": 8e9, "revenue_ttm": 8e9, "ev_sales": 5.0,
            "net_debt": 10e9, "shares_outstanding": 1e8}
    frozen = m.calc_ev_sales(base, GROWTH)["fair_value"]
    burner = m.calc_ev_sales({**base, "fcf_ttm": -5e9}, GROWTH)["fair_value"]
    assert burner < frozen


def test_ev_ebitda_leg_not_funding_gap_adjusted():
    # Scoping guard: the funding-gap correction is confined to the EARLY_GROWTH forward-sales
    # bridge and must NOT touch the EV/EBITDA capex-reroute leg (IREN regime). A burner and a
    # non-burner therefore price this leg identically — the trailing FCF only feeds the exit
    # multiple's compression, never the net-debt bridge here.
    base = {"ebitda_ttm": 1e9, "ev_ebitda": 12.0, "net_debt": 5e9,
            "shares_outstanding": 1e8, "revenue_run_rate": 4e9, "revenue_ttm": 4e9}
    frozen = m.calc_ev_ebitda(base, GROWTH, compress=False)["fair_value"]
    burner = m.calc_ev_ebitda({**base, "fcf_ttm": -3e9}, GROWTH, compress=False)["fair_value"]
    assert burner == pytest.approx(frozen)

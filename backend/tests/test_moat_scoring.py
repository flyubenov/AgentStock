import pytest
from screener.models import ScreenerMetrics
from moat import scoring
from moat.scoring import score, A1_ROIC_BANDS, A2_SPREAD_BANDS


def test_band_tables_are_descending_and_cover_expected_points():
    # A1 top band awards 20; A2 top band awards 20
    assert A1_ROIC_BANDS[0] == (25, 20)
    assert A2_SPREAD_BANDS[0] == (15, 20)
    # thresholds strictly descending (score_high scans top-down)
    for bands in (A1_ROIC_BANDS, A2_SPREAD_BANDS):
        thr = [t for t, _ in bands]
        assert thr == sorted(thr, reverse=True)


def _wide_moat_metrics():
    # high, stable ROIC well above WACC
    m = ScreenerMetrics()
    m.roic_5y_avg = 30.0
    m.roic_ttm = 31.0
    m.wacc = 9.0
    m.roic_wacc_spread = 22.0
    m.roic_series = [31.0, 30.0, 29.0, 30.0, 30.0]
    return m


def test_magnitude_only_score_is_renormalized_to_100():
    # With only A1+A2 computable, a top-band name earns 40/40 -> 100 before other pillars.
    m = _wide_moat_metrics()
    # blank out everything the later pillars would read so only A1/A2 score
    m.gross_margin_series = []
    m.op_margin_series = []
    m.fcf = None
    m.ebitda = None
    val, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["A1"] == 20
    assert bd["pillars"]["A2"] == 20
    # magnitude alone renormalizes to 100 (durability/cash unavailable here);
    # coverage floor is satisfied (5 years, >=3 pillars now that B1/B2/B3 land).
    assert val is not None


def test_coverage_floor_returns_none_for_short_history():
    m = _wide_moat_metrics()
    m.roic_series = [30.0, 31.0]           # only 2 years < MOAT_MIN_YEARS
    val, bd = score(m, "TECH_GROWTH")
    assert val is None
    assert bd["moat_score"] is None


def test_persistence_pillar_scales_with_years_above_hurdle():
    m = _wide_moat_metrics()          # 5 years all ~30% vs wacc 9% -> 5/5 above
    _, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["B1"] == pytest.approx(25.0)     # 25 * 5/5


def test_eroding_margins_score_below_stable_peer_at_equal_level():
    stable = _wide_moat_metrics()
    stable.gross_margin_series = [70.0, 71.0, 69.0, 72.0, 70.0]
    stable.op_margin_series = [30.0, 31.0, 29.0, 30.0, 30.0]
    stable.gross_margin_trajectory = 0.0
    stable.op_margin_trajectory = 0.0

    eroding = _wide_moat_metrics()
    eroding.gross_margin_series = [70.0, 64.0, 57.0, 51.0, 45.0]
    eroding.op_margin_series = [30.0, 24.0, 18.0, 12.0, 8.0]
    eroding.gross_margin_trajectory = -25.0
    eroding.op_margin_trajectory = -22.0

    _, sbd = score(stable, "TECH_GROWTH")
    _, ebd = score(eroding, "TECH_GROWTH")
    assert sbd["pillars"]["B3"] > ebd["pillars"]["B3"]


def test_b3_drops_gross_component_when_gross_series_missing():
    m = _wide_moat_metrics()
    m.gross_margin_series = []          # no Gross Profit row
    m.gross_margin_trajectory = None
    m.op_margin_series = [30.0, 31.0, 29.0, 30.0, 30.0]
    m.op_margin_trajectory = 0.0
    _, bd = score(m, "TECH_GROWTH")
    assert "B3" in bd["pillars"]        # still scored on op-margin components only


def _no_moat_metrics():
    # ROIC below WACC every year: no durable excess return
    m = ScreenerMetrics()
    m.roic_5y_avg = 6.0
    m.roic_ttm = 6.0
    m.wacc = 9.0
    m.roic_wacc_spread = -3.0
    m.roic_series = [6.0, 5.0, 7.0, 6.0, 6.0]
    m.gross_margin_series = [40.0, 40.0, 40.0, 40.0, 40.0]
    m.op_margin_series = [10.0, 10.0, 10.0, 10.0, 10.0]
    m.gross_margin_trajectory = 0.0
    m.op_margin_trajectory = 0.0
    m.fcf = 50.0
    m.ebitda = 100.0
    return m


def test_gate_caps_no_durable_excess_names():
    m = _no_moat_metrics()
    val, bd = score(m, "INDUSTRIAL_CYCLICAL")
    assert bd["gated"] is True
    assert val is not None and val <= scoring.MOAT_GATE_CEIL


def test_fcf_conversion_excluded_for_financials():
    m = _wide_moat_metrics()
    m.rote = 22.0
    m.rote_5y_avg = 21.0
    m.rote_series = [22.0, 21.0, 20.0, 21.0, 21.0]
    m.fcf = 50.0
    m.ebitda = 100.0
    _, bd = score(m, "FINANCIALS")
    assert "C1" not in bd["pillars"]
    assert "C1 FCF conversion" in bd["excluded"]
    assert bd["variant"] == "FINANCIAL_ROTE"


def test_fcf_conversion_scored_for_normal_company():
    m = _wide_moat_metrics()
    m.gross_margin_series = [70.0, 70.0, 70.0, 70.0, 70.0]
    m.op_margin_series = [30.0, 30.0, 30.0, 30.0, 30.0]
    m.gross_margin_trajectory = 0.0
    m.op_margin_trajectory = 0.0
    m.fcf = 95.0
    m.ebitda = 100.0                    # 0.95 conversion -> top band
    _, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["C1"] == 10


def test_bank_produces_sane_score_on_rote_axis():
    m = ScreenerMetrics()
    m.rote = 16.0
    m.rote_5y_avg = 15.0
    m.rote_series = [16.0, 15.0, 14.0, 15.0, 15.0]
    m.roic_5y_avg = None               # ROIC frame irrelevant for a bank
    m.wacc = None
    val, bd = score(m, "FINANCIALS")
    assert val is not None
    assert bd["gated"] is False        # ROTE 15% > COE 8.5%

"""The breakdown's Data column. The engines emit bare floats in three different
units — Quality in percent (31.9), Reward/Risk mostly as fractions (0.164), and
yfinance's debt-to-equity in percent again (78.4) — so every expectation below pins
the UNIT, not only the digits. A formatter that forgot to scale a fraction would
print "0.2%" for a 16% growth rate and fail here."""
import pytest

from landing.contract import build_ticker_payload
from landing.figures import moat_figure, quality_figure, rr_figure
from moat.scoring import score
from tests.test_landing_contract import _result
from tests.test_moat_scoring import _wide_moat_metrics


@pytest.mark.parametrize("label,raw,expected", [
    ("Operating margin", 31.97, "32%"),                 # already percent: not scaled
    ("Gross margin", 8.66, "8.7%"),
    ("Revenue growth (3-yr)", 1.81, "+1.8% / yr"),
    ("FCF growth (3-yr)", -3.94, "−3.9% / yr"),
    ("Operating-margin trajectory", 1.68, "+1.7 pp"),
    ("Economic spread (ROIC - WACC)", -1.3, "−1.3 pp"),
    ("Net debt / EBITDA", 0.373, "0.4×"),
    ("Net debt / EBITDA", -0.92, "Net cash"),           # more cash than debt
    ("Operating cash flow / capex", 8.77, "8.8×"),
    ("Earnings quality (FCF / net income)", 0.995, "1.0×"),
    ("Share-count trend (3-yr)", -2.77, "−2.8% / yr"),
])
def test_quality_figures_carry_their_unit(label, raw, expected):
    assert quality_figure(label, raw) == expected


@pytest.mark.parametrize("source,raw,expected", [
    ("revenue_growth", 0.164, "Revenue +16%"),          # a fraction: scaled by 100
    ("roe", 1.4875, "ROE 149%"),
    ("analyst_upside", -0.0377, "−3.8% to target"),
    ("discount", 0.0124, "1.2% below high"),
    ("debt_to_equity", 78.4, "D/E 0.8"),                # yfinance percent -> ratio
    ("net_debt_ebitda", 0.4, "0.4× EBITDA"),
    ("net_debt_ebitda", -1.2, "Net cash"),
    ("operating_margin", 0.326, "33% op margin"),
    ("volatility", 0.246, "25% ann."),
    ("trend", 0.187, "+19% vs 200-day"),
    ("peg", 2.7, "PEG 2.7"),
    ("rsi", 65.7, "66"),
    ("beta", 1.085, "β 1.08"),
])
def test_reward_risk_figures_follow_the_source_that_scored_the_slot(source, raw, expected):
    assert rr_figure(source, raw) == expected


def test_the_same_slot_formats_differently_when_it_falls_back_to_another_source():
    # valuation is scored by PEG when there is one, by earnings yield when not — the
    # unit follows the source, never the slot.
    assert rr_figure("peg", 0.05) == "PEG 0.1"
    assert rr_figure("earnings_yield", 0.05) == "Earnings yield 5.0%"


@pytest.mark.parametrize("raw", [None, float("nan"), float("inf")])
def test_a_missing_or_non_finite_figure_is_none_never_text(raw):
    assert quality_figure("Operating margin", raw) is None
    assert rr_figure("roe", raw) is None
    assert moat_figure("A1", raw) is None


def test_moat_figures():
    assert moat_figure("A1", 55.2) == "55%"
    assert moat_figure("A2", 11.0) == "+11 pp"
    assert moat_figure("B1", {"fraction": 0.9, "years": 10}) == "9 of 10 yrs"
    assert moat_figure("B2", 0.12) == "12% variation"
    assert moat_figure("C1", 0.955) == "96% of EBITDA"


def test_moat_scoring_records_the_input_behind_each_pillar():
    _, bd = score(_wide_moat_metrics(), "TECH_GROWTH")
    inputs = bd["inputs"]
    # Every scored pillar has its input recorded, and the recorded persistence is
    # the same fraction B1 was scored from (25 points per full persistence).
    assert set(bd["pillars"]) <= set(inputs)
    assert inputs["B1"]["fraction"] * 25 == pytest.approx(bd["pillars"]["B1"])


def test_the_contract_ships_a_display_string_per_row():
    r = _result()
    r["screener"]["moat_breakdown"]["inputs"] = {"A1": 55.0, "A2": 40.0,
                                                 "B1": {"fraction": 1.0, "years": 10}}
    r["risk_reward"]["metric_scores"]["discount"]["source"] = "discount"
    p = build_ticker_payload(r)
    margins = p["quality"]["categories"][0]["metrics"]
    assert margins[1]["display"] == "0.5%"          # fixture raw 0.46 is percent units
    moat = {f["label"]: f for f in p["moat"]["factors"]}
    assert moat["ROIC level"]["display"] == "55%"
    assert moat["ROIC level"]["group"] == "Magnitude"
    assert moat["Persistence of economic profit"]["group"] == "Durability"
    assert moat["Persistence of economic profit"]["display"] == "10 of 10 yrs"
    discount = next(f for f in p["reward_risk"]["reward"] if f["label"] == "Discount to 52-week high")
    assert discount["display"] == "5.0% below high"

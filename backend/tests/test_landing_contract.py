import math
import re

import pytest
from landing.contract import build_ticker_payload
from landing.labels import ERROR_LABELS, EXCLUSION_LABELS, GENERIC_ERROR_LABEL, humanize


def _result(**over) -> dict:
    base = {
        "ticker": "AAPL", "company_name": "Apple Inc.", "current_price": 232.0,
        "stock_type": "MEGA_CAP", "fair_value": 211.0, "price_vs_fair_value_pct": -9.05,
        "fair_value_breakdown": {
            "dcf": {"fair_value": 205.0, "weight": 0.55},
            "ev_ebitda": {"fair_value": 220.0, "weight": 0.35},
            "pe": {"fair_value": 208.0, "weight": 0.10},
        },
        "status": "completed", "errors": [],
        "screener": {
            "quality_score": 9.1, "sector_profile": "TECH_GROWTH",
            # I=8.0 (mean of the two metric_details scores below), and with
            # weights 35/30/15/20, this set is chosen so 9.1 is exactly what these
            # categories roll up to (0.35*8 + 0.30*10 + 0.15*10 + 0.20*9 = 9.1) — the
            # rollup-equals-headline test below only means something if the fixture's
            # own numbers actually add up.
            "section_scores": {"I": 8.0, "II": 10.0, "III": 10.0, "IV": 9.0},
            "score_breakdown": {"section_weights": {"I": 0.35, "II": 0.30,
                                                    "III": 0.15, "IV": 0.20}},
            "metric_details": {
                "I": [{"label": "Revenue growth (3-yr)", "raw": 0.08, "score": 6.0,
                       "excluded": False, "excluded_by": None},
                      {"label": "Gross margin", "raw": 0.46, "score": 10.0,
                       "excluded": False, "excluded_by": None}],
                "II": [], "III": [], "IV": [],
            },
            "moat_score": 90.0,
            "moat_breakdown": {"pillars": {"A1": 18.0, "A2": 17.0, "B1": 25.0},
                               "maxima": {"A1": 20, "A2": 20, "B1": 25},
                               "gated": False, "excluded": []},
        },
        "risk_reward": {
            "ratio": 0.9, "tier": "Balanced", "reward_score": 2.8, "risk_score": 3.1,
            "metric_scores": {
                "discount": {"raw": 0.05, "score": 2.0, "weight": 0.24, "dropped": False},
                "volatility": {"raw": 0.3, "score": 3.0, "weight": 0.22, "dropped": False},
            },
            "status": "completed",
        },
    }
    base.update(over)
    return base


def test_headline_values_are_carried_through():
    p = build_ticker_payload(_result())
    assert p["ticker"] == "AAPL"
    assert p["quality"]["score"] == 9.1
    assert p["moat"]["score"] == 90.0
    assert p["fair_value"]["value"] == 211.0
    assert p["reward_risk"]["ratio"] == 0.9


def test_no_internal_classifier_code_survives():
    p = build_ticker_payload(_result())
    assert p["quality"]["profile_label"] == "Tech / Growth"
    assert p["fair_value"]["type_label"] == "Mega Cap"
    assert "TECH_GROWTH" not in repr(p)
    assert "MEGA_CAP" not in repr(p)


def test_metric_weights_split_the_category_weight_evenly():
    p = build_ticker_payload(_result())
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    assert cat["weight_pct"] == 35.0
    assert [m["weight_pct"] for m in cat["metrics"]] == [17.5, 17.5]


def test_an_excluded_metric_is_zero_weighted_and_the_rest_reweight():
    r = _result()
    r["screener"]["metric_details"]["I"].append(
        {"label": "FCF margin", "raw": None, "score": None,
         "excluded": True, "excluded_by": "Financials basis"})
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    excluded = [m for m in cat["metrics"] if m["excluded"]]
    active = [m for m in cat["metrics"] if not m["excluded"]]
    assert [m["weight_pct"] for m in excluded] == [0.0]
    assert sum(m["weight_pct"] for m in active) == pytest.approx(35.0)


def test_an_excluded_metric_reweights_a_realistic_seven_metric_section():
    """The 2-metric case above divides evenly (35/2); Section I on a real ticker has
    7 metrics (screener/scoring.py's section_metric_details), where 35/6 does not
    round cleanly. This is the shape a real payload actually has."""
    r = _result()
    r["screener"]["metric_details"]["I"] = [
        {"label": f"Metric {i}", "raw": 1.0, "score": 5.0,
         "excluded": False, "excluded_by": None}
        for i in range(6)
    ] + [{"label": "FCF margin", "raw": None, "score": None,
          "excluded": True, "excluded_by": "Financials basis"}]
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    excluded = [m for m in cat["metrics"] if m["excluded"]]
    active = [m for m in cat["metrics"] if not m["excluded"]]
    assert len(active) == 6
    assert [m["weight_pct"] for m in excluded] == [0.0]
    assert all(m["weight_pct"] == pytest.approx(35.0 / 6, abs=0.01) for m in active)
    # Six independently-rounded 5.83s land a couple hundredths short of 35.0 — real
    # rounding drift, not a bug, hence the abs tolerance rather than an exact sum.
    assert sum(m["weight_pct"] for m in active) == pytest.approx(35.0, abs=0.05)


def test_the_quality_headline_equals_what_its_categories_roll_up_to():
    """The grid shows the headline and the breakdown shows the categories; if these two
    could disagree, the page would be lying about its own arithmetic."""
    p = build_ticker_payload(_result())
    rolled = sum(c["score"] * c["weight_pct"] / 100 for c in p["quality"]["categories"])
    assert rolled == pytest.approx(p["quality"]["score"], abs=0.05)


def test_fair_value_methods_carry_value_weight_and_contribution():
    p = build_ticker_payload(_result())
    dcf = next(m for m in p["fair_value"]["methods"] if m["label"] == "Discounted cash flow")
    assert dcf["weight_pct"] == 55.0
    assert dcf["contribution"] == pytest.approx(205.0 * 0.55)
    assert sum(m["contribution"] for m in p["fair_value"]["methods"]) == pytest.approx(211.0, abs=0.5)


def test_moat_factor_weight_is_its_share_of_the_available_points():
    p = build_ticker_payload(_result())
    a1 = next(f for f in p["moat"]["factors"] if f["label"].startswith("ROIC level"))
    assert (a1["points"], a1["max_points"]) == (18.0, 20)
    # weight_pct is rounded to 2dp like every sibling weight field, so compare with a
    # tolerance rather than to the unrounded 20/65*100.
    assert a1["weight_pct"] == pytest.approx(20 / 65 * 100, abs=0.01)


def test_reward_and_risk_factors_are_split_by_axis():
    r = _result()
    # Two active slots per axis, not one: with only one active slot its effective
    # share is trivially 100% regardless of how weight_pct is computed, which would
    # make this assertion pass no matter what. discount (0.24) + valuation (0.18) on
    # the reward axis, volatility (0.22) + leverage (0.18) on the risk axis actually
    # exercises the renormalization.
    r["risk_reward"]["metric_scores"] = {
        "discount": {"raw": 0.05, "score": 2.0, "weight": 0.24, "dropped": False},
        "valuation": {"raw": 1.0, "score": 4.0, "weight": 0.18, "dropped": False},
        "volatility": {"raw": 0.3, "score": 3.0, "weight": 0.22, "dropped": False},
        "leverage": {"raw": 1.5, "score": 3.5, "weight": 0.18, "dropped": False},
    }
    p = build_ticker_payload(r)
    assert sorted(f["label"] for f in p["reward_risk"]["reward"]) == \
        sorted(["Discount to 52-week high", "Valuation"])
    assert sorted(f["label"] for f in p["reward_risk"]["risk"]) == \
        sorted(["Volatility", "Leverage"])
    reward = {f["label"]: f for f in p["reward_risk"]["reward"]}
    risk = {f["label"]: f for f in p["reward_risk"]["risk"]}
    # 0.24/(0.24+0.18) = 57.14%, 0.18/(0.24+0.18) = 42.86%
    assert reward["Discount to 52-week high"]["weight_pct"] == pytest.approx(57.14, abs=0.01)
    assert reward["Valuation"]["weight_pct"] == pytest.approx(42.86, abs=0.01)
    assert sum(f["weight_pct"] for f in p["reward_risk"]["reward"]) == pytest.approx(100.0, abs=0.01)
    # 0.22/(0.22+0.18) = 55.0%, 0.18/(0.22+0.18) = 45.0%
    assert risk["Volatility"]["weight_pct"] == pytest.approx(55.0, abs=0.01)
    assert risk["Leverage"]["weight_pct"] == pytest.approx(45.0, abs=0.01)
    assert sum(f["weight_pct"] for f in p["reward_risk"]["risk"]) == pytest.approx(100.0, abs=0.01)


# --- Review Focus 1: one engine fails, the others do not ---
def test_a_missing_engine_becomes_null_not_a_crash():
    p = build_ticker_payload(_result(screener=None, risk_reward=None))
    assert p["quality"] is None and p["moat"] is None and p["reward_risk"] is None
    assert p["fair_value"]["value"] == 211.0


def test_a_synthetic_failure_dict_never_crashes():
    """Task 6 feeds build_ticker_payload the bare failure shape orchestrator.batch
    produces for a ticker whose engine run raised — no screener/risk_reward/fair_value
    keys at all."""
    p = build_ticker_payload({"ticker": "ZZZZ", "errors": ["boom"], "status": "failed"})
    assert p["ticker"] == "ZZZZ"
    assert p["quality"] is None and p["moat"] is None and p["reward_risk"] is None
    assert p["fair_value"] is None
    assert p["errors"] == ["boom"]


# --- Review Focus 2: no fair value ---
def test_a_declined_fair_value_yields_no_value_and_no_gap():
    p = build_ticker_payload(_result(fair_value=None, price_vs_fair_value_pct=None,
                                     fair_value_breakdown={}))
    assert p["fair_value"] is None
    assert p["price"] == 232.0


def test_a_gap_is_never_computed_without_a_price():
    """contract.py does not compute the gap itself — it passes `price_vs_fair_value_pct`
    through unchanged. The actual "never divide by a missing price" invariant lives
    upstream at valuation/engine.py:717-718 (`pct = None` unless `current_price`); this
    test only guards that the passthrough doesn't invent a value when the fixture, like
    the real engine, sends None."""
    p = build_ticker_payload(_result(current_price=None, price_vs_fair_value_pct=None))
    assert p["fair_value"]["gap_pct"] is None


def test_humanize_falls_back_to_title_case_for_an_unmapped_code():
    assert humanize("SOME_NEW_TYPE") == "Some New Type"
    assert humanize(None) is None


# --- Controller addition 1: excluded_by is a key, not display copy ---
def test_excluded_by_is_humanized_on_a_metric():
    r = _result()
    r["screener"]["metric_details"]["I"].append(
        {"label": "FCF margin", "raw": None, "score": None,
         "excluded": True, "excluded_by": "Heavy-capex FCF exclusion"})
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    fcf = next(m for m in cat["metrics"] if m["label"] == "FCF margin")
    # Assert the exact mapped string, not just inequality to the raw reason — a typo
    # in EXCLUSION_LABELS would still satisfy `!=` and pass silently.
    assert fcf["excluded_by"] == EXCLUSION_LABELS["Heavy-capex FCF exclusion"]
    assert "Heavy-capex FCF exclusion" not in repr(p)


def test_an_unmapped_exclusion_reason_passes_through_raw():
    r = _result()
    r["screener"]["metric_details"]["I"].append(
        {"label": "Some new metric", "raw": None, "score": None,
         "excluded": True, "excluded_by": "Some brand-new reason"})
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    m = next(m for m in cat["metrics"] if m["label"] == "Some new metric")
    assert m["excluded_by"] == "Some brand-new reason"


def test_calibrations_never_carry_a_raw_internal_reason_string():
    r = _result()
    r["screener"]["score_breakdown"]["capex_adjustment"] = {"profile": "TECH_GROWTH"}
    p = build_ticker_payload(r)
    # Assert the expected calibration is actually present (this would pass against an
    # empty list otherwise, proving nothing) and that its raw reason string is gone.
    assert EXCLUSION_LABELS["Heavy-capex FCF exclusion"] in p["calibrations"]
    assert "Heavy-capex FCF exclusion" not in p["calibrations"]


# --- Controller addition 3: max_points stays non-null ---
def test_a_moat_pillar_without_a_maximum_is_omitted_not_nulled():
    r = _result()
    r["screener"]["moat_breakdown"] = {
        "pillars": {"A1": 18.0, "A2": 17.0, "ZZ": 5.0},
        "maxima": {"A1": 20, "A2": 20},
        "gated": False, "excluded": [],
    }
    p = build_ticker_payload(r)
    labels = [f["label"] for f in p["moat"]["factors"]]
    assert all(f["max_points"] is not None for f in p["moat"]["factors"])
    assert len(p["moat"]["factors"]) == 2


# --- Fix round 1, item 1: reward/risk weight_pct is an EFFECTIVE share, not nominal ---
def test_a_dropped_reward_slot_gets_zero_weight_and_the_axis_still_sums_to_100():
    r = _result()
    r["risk_reward"]["metric_scores"] = {
        # discount and rsi are both REWARD_SLOTS; rsi is dropped (weight still
        # nonzero, per risk_reward/scoring.py's build_metric_scores) and must render
        # at 0.0, not its nominal config weight — with discount then picking up the
        # entire reward axis (100%), not just its own nominal share.
        "discount": {"raw": 0.05, "score": 2.0, "weight": 0.24, "dropped": False},
        "rsi": {"raw": None, "score": None, "weight": 0.16, "dropped": True},
        "volatility": {"raw": 0.3, "score": 3.0, "weight": 0.22, "dropped": False},
    }
    p = build_ticker_payload(r)
    reward = {f["label"]: f for f in p["reward_risk"]["reward"]}
    assert reward["RSI (14-day)"]["weight_pct"] == 0.0
    assert reward["RSI (14-day)"]["dropped"] is True
    assert reward["Discount to 52-week high"]["weight_pct"] == pytest.approx(100.0)
    assert sum(f["weight_pct"] for f in p["reward_risk"]["reward"]) == pytest.approx(100.0)


def test_reward_axis_weights_sum_to_100_with_no_drops_despite_dynamic_analyst_weight():
    r = _result()
    r["risk_reward"]["metric_scores"] = {
        "valuation": {"raw": 1.0, "score": 4.0, "weight": 0.18, "dropped": False},
        "growth": {"raw": 0.1, "score": 3.0, "weight": 0.18, "dropped": False},
        "profitability": {"raw": 0.1, "score": 3.0, "weight": 0.12, "dropped": False},
        # a per-ticker confidence-scaled weight, not the static 0.12 config default —
        # the axis still must renormalize to 100% around whatever this actually is.
        "analyst_upside": {"raw": 0.1, "score": 3.0, "weight": 0.145, "dropped": False},
        "discount": {"raw": 0.05, "score": 2.0, "weight": 0.24, "dropped": False},
        "rsi": {"raw": 50.0, "score": 3.0, "weight": 0.16, "dropped": False},
    }
    p = build_ticker_payload(r)
    # abs tolerance: six independently-rounded percentages can drift a few hundredths
    # from 100 even when the underlying fractions sum to exactly 1.
    assert sum(f["weight_pct"] for f in p["reward_risk"]["reward"]) == pytest.approx(100.0, abs=0.05)


# --- Fix round 1, item 3: moat.excluded must not leak raw pillar codes ---
def test_moat_excluded_pillar_codes_are_humanized():
    r = _result()
    r["screener"]["moat_breakdown"]["excluded"] = ["B3 margin durability", "C1 FCF conversion"]
    p = build_ticker_payload(r)
    assert p["moat"]["excluded"] == ["Margin durability", "Free-cash-flow conversion"]
    assert not re.search(r"\b[A-C][0-9]\b", repr(p["moat"]))


# --- Fix round 1, item 4: the headline's divergence from the composite is visible ---
def test_fundamentals_composite_is_exposed_alongside_the_headline():
    p = build_ticker_payload(_result())
    r2 = _result()
    r2["screener"]["score_breakdown"]["fundamentals_composite"] = 9.1
    p2 = build_ticker_payload(r2)
    assert p["quality"]["fundamentals_composite"] is None  # not in the base fixture
    assert p2["quality"]["fundamentals_composite"] == 9.1


def test_calibrations_surface_the_roic_and_pre_profit_recalibrations():
    r = _result()
    r["screener"]["score_breakdown"]["roic_adjustment"] = {"profile": "TECH_GROWTH"}
    r["screener"]["score_breakdown"]["pre_profit"] = {"applied": True, "capped": True}
    p = build_ticker_payload(r)
    assert "ROIC on tangible capital" in p["calibrations"]
    assert "Pre-profit growth blend" in p["calibrations"]
    assert "Unprofitable cap" in p["calibrations"]


# --- Fix round 1, item 5: NaN/Inf never reach the payload ---
def test_nan_and_inf_never_reach_the_payload_as_raw_or_score():
    r = _result()
    r["screener"]["metric_details"]["I"][0]["raw"] = float("nan")
    r["screener"]["metric_details"]["I"][0]["score"] = float("inf")
    r["risk_reward"]["metric_scores"]["discount"]["raw"] = float("nan")
    r["risk_reward"]["metric_scores"]["discount"]["score"] = float("-inf")
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    m = next(m for m in cat["metrics"] if m["label"] == "Revenue growth (3-yr)")
    assert m["raw"] is None and m["score"] is None
    reward_discount = next(f for f in p["reward_risk"]["reward"]
                           if f["label"] == "Discount to 52-week high")
    assert reward_discount["raw"] is None and reward_discount["score"] is None
    dump = repr(p)
    assert "nan" not in dump.lower() and "inf" not in dump.lower()


# --- Fix round 1, item 6: errors never carry exception text ---
def test_public_errors_never_leak_exception_text():
    p = build_ticker_payload(_result(errors=[
        "sheets_write: KeyError('some_internal_column')",
        "screener: ValueError(\"division by zero\")",
    ]))
    assert p["errors"] == [ERROR_LABELS["sheets_write"], ERROR_LABELS["screener"]]
    for e in p["errors"]:
        assert "KeyError" not in e and "ValueError" not in e
        assert "some_internal_column" not in e and "division by zero" not in e


def test_an_unknown_error_prefix_falls_back_to_the_generic_label():
    p = build_ticker_payload(_result(errors=["some_future_subsystem: boom"]))
    assert p["errors"] == [GENERIC_ERROR_LABEL]
    assert "boom" not in p["errors"][0]


def test_a_plain_engine_message_with_no_prefix_passes_through_unchanged():
    """The engines' own decline reasons (e.g. valuation/engine.py's composite-
    non-positive message, screener/engine.py's "insufficient data...") carry no
    "subsystem: " prefix and are already reader-safe copy, not exception text."""
    p = build_ticker_payload(_result(errors=["insufficient data for a quality score"]))
    assert p["errors"] == ["insufficient data for a quality score"]

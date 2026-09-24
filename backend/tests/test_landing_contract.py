import pytest
from landing.contract import build_ticker_payload
from landing.labels import humanize


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
    assert a1["weight_pct"] == pytest.approx(20 / 65 * 100)


def test_reward_and_risk_factors_are_split_by_axis():
    p = build_ticker_payload(_result())
    assert [f["label"] for f in p["reward_risk"]["reward"]] == ["Discount to 52-week high"]
    assert [f["label"] for f in p["reward_risk"]["risk"]] == ["Volatility"]
    assert p["reward_risk"]["reward"][0]["weight_pct"] == 24.0


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
    assert fcf["excluded_by"] != "Heavy-capex FCF exclusion"
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

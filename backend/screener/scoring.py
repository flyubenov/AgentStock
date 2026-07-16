from __future__ import annotations
from screener.models import ScreenerMetrics


def score_high(value: float | None, bands: list[tuple[float, float]], below: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value >= thr:
            return sc
    return below


def score_low(value: float | None, bands: list[tuple[float, float]], above: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value <= thr:
            return sc
    return above


def leverage_score(r: float | None, pivot: float | None) -> float | None:
    if r is None or pivot is None:
        return None
    if r <= 0:
        return 10.0
    if r <= 0.5 * pivot:
        return 9.0
    if r <= pivot:
        return 7.0
    if r <= 1.4 * pivot:
        return 4.5
    if r <= 1.8 * pivot:
        return 2.0
    return 0.0


PROFILES: dict[str, dict] = {
    "TECH_GROWTH":         {"w": (0.35, 0.30, 0.15, 0.20), "P": 2.5, "Q": 3.0},
    "BALANCED":            {"w": (0.30, 0.30, 0.20, 0.20), "P": 2.5, "Q": 3.0},
    "DEFENSIVE_INCOME":    {"w": (0.15, 0.25, 0.35, 0.25), "P": 4.5, "Q": 6.0},
    "INDUSTRIAL_CYCLICAL": {"w": (0.25, 0.30, 0.30, 0.15), "P": 3.0, "Q": 4.0},
    "FINANCIALS":          {"w": (0.35, 0.40, 0.00, 0.25), "P": None, "Q": None},
    "REIT":                {"w": (0.30, 0.20, 0.25, 0.25), "P": 6.5, "Q": 8.0},
}

SECTOR_TO_PROFILE: dict[str, str] = {
    "technology": "TECH_GROWTH",
    "communication services": "BALANCED",
    "consumer cyclical": "BALANCED",
    "healthcare": "BALANCED",
    "utilities": "DEFENSIVE_INCOME",
    "consumer defensive": "DEFENSIVE_INCOME",
    "industrials": "INDUSTRIAL_CYCLICAL",
    "basic materials": "INDUSTRIAL_CYCLICAL",
    "energy": "INDUSTRIAL_CYCLICAL",
    "financial services": "FINANCIALS",
    "real estate": "REIT",
}


def base_profile(sector: str | None) -> str:
    return SECTOR_TO_PROFILE.get((sector or "").strip().lower(), "BALANCED")


def apply_nudge(base: str, m: ScreenerMetrics) -> str:
    # 1. Growth override: BALANCED + strong revenue growth + net cash -> TECH_GROWTH
    if base == "BALANCED" and (m.revenue_cagr_3y or 0) >= 15.0 and (m.net_debt is not None and m.net_debt < 0):
        return "TECH_GROWTH"
    # 2. Special-profile data-fit fallback: FINANCIALS/REIT that operate like a
    #    normal company (material positive EBITDA, normal leverage, real op margin).
    if base in ("FINANCIALS", "REIT"):
        if (m.ebitda is not None and m.ebitda > 0
                and m.net_debt_ebitda is not None and m.net_debt_ebitda < 4
                and m.op_margin is not None):
            return "BALANCED"
    return base


ROIC_BANDS = [(20, 10), (15, 8.5), (10, 6.5), (5, 4), (0, 2)]
SPREAD_BANDS = [(10, 10), (5, 8), (0, 5.5), (-5, 2.5)]
ROTE_BANDS = [(25, 10), (20, 8.5), (15, 7), (10, 5), (5, 3)]
GROWTH_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (2, 3), (0, 1.5)]
FCF_CAGR_BANDS = [(15, 10), (10, 8), (5, 6), (0, 4)]
FCF_MARGIN_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (0, 3)]
MARGIN_LEVEL_BANDS = [(25, 10), (15, 8), (8, 6), (0, 3)]
TRAJECTORY_BANDS = [(2, 10), (0, 7), (-2, 4)]
GROSS_MARGIN_BANDS = [(60, 10), (40, 8), (25, 6), (10, 4)]
OCF_CAPEX_BANDS = [(5, 10), (3, 8), (2, 6), (1.5, 4), (1, 2)]
SHARES_BANDS = [(-3, 10), (-1, 8.5), (0, 7), (1, 5), (3, 3)]   # score_low
SBC_BANDS = [(2, 10), (5, 8), (10, 6), (15, 3.5), (20, 1.5)]   # score_low
EQ_BANDS = [(1.2, 10), (1.0, 8.5), (0.8, 6), (0.6, 4)]
INSIDER_BANDS = [(10, 10), (5, 8), (2, 6), (0.5, 4)]
YIELD_BANDS = [(6, 10), (4, 8.5), (2, 6.5), (0, 4)]


def _mean(vals: list[float | None]) -> float | None:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else None


FCF_EBITDA_FLOOR = 0.15


def _heavy_capex_distortion(m: ScreenerMetrics) -> bool:
    """Operationally profitable, healthy EBITDA, but trailing FCF is a negligible
    (or negative) fraction of EBITDA because capex is eating it (e.g. AMZN's AWS/AI
    data-centre build-out). The FCF-derived metrics are then unrepresentative and
    excluded from scoring — the same principle as the FINANCIALS FCF/OCF exclusion,
    and mirroring the Fair-Value pipeline's capex-distorted DCF reroute.

    An operating loss is NOT treated here: that is a genuine pre-profit burn, which
    the pre-profit growth/runway branch handles separately."""
    if m.ebitda is None or m.ebitda <= 0 or m.fcf is None:
        return False
    if m.op_margin is not None and m.op_margin < 0:
        return False
    return m.fcf < FCF_EBITDA_FLOOR * m.ebitda


# Trailing earnings are treated as distorted when the trailing P/E runs far above the
# forward P/E (trailing_pe / forward_pe > DEPRESSED_PE_RATIO): the market is pricing a
# large earnings recovery, i.e. today's GAAP earnings are depressed by acquisition
# amortization or a one-off / patent-cliff trough (ABBV post-Humira, AVGO post-VMware).
# The trailing-EPS growth metric then measures the accounting trough, not the business,
# so it is excluded from Section I. This mirrors the Fair-Value engine's forward-EPS
# swap (same DEPRESSED_PE_RATIO constant).
DEPRESSED_PE_RATIO = 1.5


def _earnings_distorted(m: ScreenerMetrics) -> bool:
    tpe, fpe = m.trailing_pe, m.forward_pe
    if tpe is None or fpe is None or tpe <= 0 or fpe <= 0:
        return False
    if tpe / fpe <= DEPRESSED_PE_RATIO:
        return False
    # A high trailing-over-forward P/E can also mean earnings are *growing* fast
    # (forward EPS > trailing) — an NVDA-type, not a trough. There the negative-CAGR
    # rescue must NOT fire, or we would drop a legitimately strong growth signal. Only
    # exclude when the trailing EPS-growth metric is actually depressed (<= 0), so the
    # adjustment can only ever remove a drag, never a boost.
    return m.eps_cagr_3y is not None and m.eps_cagr_3y <= 0


# A large past acquisition (e.g. AMD/Xilinx) distorts ROIC from both sides: goodwill &
# intangibles inflate the invested-capital denominator, and their amortization depresses
# the EBIT numerator. The reported ROIC then measures the deal price tag, not the
# operating business — while ROTE (tangible book) reads far healthier. When that is the
# case, Section II scores a ROIC computed on tangible invested capital instead. Gated so
# a serial over-payer genuinely destroying value is NOT rescued: earnings must be
# amortization-depressed with a priced-in recovery (trailing P/E >> forward P/E), and the
# adjustment can only ever raise the ROIC, never lower it.
GOODWILL_SHARE_FLOOR = 0.30

# When a company's tangible (ex-goodwill) ROIC already clears its cost of capital while
# its reported ROIC sits below it, that crossover is itself direct evidence the reported
# weakness is an acquisition artifact — so a smaller goodwill share is sufficient proof
# and the floor drops from 0.30 to 0.15. AMD keeps qualifying via the 0.30 floor: its
# ex-goodwill ROIC (13.8) is still below its beta-capped WACC (14.5), so it has no
# crossover. VST does (reported 7.8 < WACC 9.6 <= ex-goodwill 10.1) at 0.23 goodwill share.
GOODWILL_SHARE_FLOOR_XOVER = 0.15


def _wacc_crossover(m: ScreenerMetrics) -> bool:
    if m.roic_ttm is None or m.roic_ex_goodwill is None or m.wacc is None:
        return False
    return m.roic_ttm < m.wacc <= m.roic_ex_goodwill


def _effective_goodwill_floor(m: ScreenerMetrics) -> float:
    return GOODWILL_SHARE_FLOOR_XOVER if _wacc_crossover(m) else GOODWILL_SHARE_FLOOR


def _acquisition_distorted(m: ScreenerMetrics) -> bool:
    if (m.goodwill_intangible_share is None
            or m.goodwill_intangible_share < _effective_goodwill_floor(m)):
        return False
    if m.roic_ex_goodwill is None or m.roic_ttm is None:
        return False
    # can only ever help, never hurt
    if m.roic_ex_goodwill <= m.roic_ttm:
        return False
    # amortization-depressed earnings with a priced-in recovery (reuses the same
    # trailing/forward P/E signal as _earnings_distorted, but WITHOUT its eps_cagr<=0
    # gate — a fast-growing acquirer like AMD has a positive EPS CAGR yet is still
    # carrying acquisition amortization).
    tpe, fpe = m.trailing_pe, m.forward_pe
    if tpe is None or fpe is None or tpe <= 0 or fpe <= 0:
        return False
    return tpe / fpe > DEPRESSED_PE_RATIO


# A just-closed acquisition whose goodwill & intangibles DOMINATE invested capital
# (e.g. SNPS after the ~$35B Ansys deal, ~95%) distorts the trailing statements from
# both ends: they carry the FULL deal — acquisition debt and intangible amortization —
# but only a partial-period stub of the acquired company's EBITDA / operating income.
# So the trailing operating margin is amortization-depressed and the leverage ratios are
# full post-deal debt measured against pre-consolidation EBITDA / FCF. This is distinct
# from a normal acquirer that long since digested a deal (AMD 0.63, VST 0.23 goodwill
# share): those keep their trailing margin & leverage. The threshold is set above AMD's
# 0.63 so only a balance-sheet-dominating fresh deal qualifies.
DOMINANT_ACQUISITION_GOODWILL_SHARE = 0.70


def _dominant_acquisition(m: ScreenerMetrics) -> bool:
    """A fresh, balance-sheet-dominating acquisition (see the constant above). Requires
    the acquisition-distortion signal (goodwill-inflated ROIC + priced-in P/E recovery)
    AND goodwill/intangibles being the overwhelming majority of invested capital — so a
    genuine write-down / value-destroyer (no P/E recovery) or a long-digested normal
    acquirer does not qualify."""
    if not _acquisition_distorted(m):
        return False
    s = m.goodwill_intangible_share
    return s is not None and s >= DOMINANT_ACQUISITION_GOODWILL_SHARE


def _acq_margin_distorted(m: ScreenerMetrics) -> bool:
    """Operating margin (and its trajectory) are amortization-depressed by a dominant
    fresh acquisition ONLY when the trajectory actually collapsed post-deal (< 0). A
    name whose margin is still improving despite the deal is not currently margin-
    distorted, so the metric is kept — the adjustment can only ever remove a drag."""
    return (_dominant_acquisition(m)
            and m.op_margin_trajectory is not None and m.op_margin_trajectory < 0)


def _acq_leverage_distorted(m: ScreenerMetrics) -> bool:
    """Leverage ratios are overstated by a dominant fresh acquisition ONLY when the name
    actually levered up for the deal (net-levered). A net-cash acquirer's favourable
    leverage score is real, not a mismatch artifact, so it is kept — the adjustment can
    only ever remove a drag, never lower a good score (e.g. AMD stays net-cash-scored)."""
    return (_dominant_acquisition(m)
            and m.net_debt_ebitda is not None and m.net_debt_ebitda > 0)


def _section_iii(m: ScreenerMetrics, profile: str, heavy_capex: bool = False,
                 exclude_acq_leverage: bool = False) -> float | None:
    p = PROFILES[profile]
    # leverage_score reads a non-positive ratio as net cash (10/10). That inference only
    # holds when the *numerator* is negative. A negative ratio produced by a negative
    # *denominator* means the opposite: real debt with no EBITDA / FCF to service it
    # (TEM: +$635M net debt over -$185M EBITDA = -3.43, scored 10/10). The ratio carries
    # no leverage information there, so leave it unscored. A None denominator is
    # unknown, not negative — keep the existing behaviour.
    nde = (leverage_score(m.net_debt_ebitda, p["P"])
           if (m.ebitda is None or m.ebitda > 0) else None)
    ndf = (leverage_score(m.net_debt_fcf, p["Q"])
           if (m.fcf is None or m.fcf > 0) else None)
    ocf = score_high(m.ocf_capex, OCF_CAPEX_BANDS, 0)
    if exclude_acq_leverage:
        # A dominant fresh acquisition's full debt measured against pre-consolidation
        # trailing EBITDA / FCF overstates leverage -> judge the balance sheet on the
        # undistorted OCF / CapEx coverage instead.
        nde = None
        ndf = None
    elif heavy_capex:
        # Capex is deliberately consuming FCF, so the FCF-derived coverage/leverage
        # metrics are unrepresentative -> judge the balance sheet on EBITDA leverage.
        ndf = None
        ocf = None
    # Balance-Sheet Dual-Check: FCF-based debt looks far worse than EBITDA-based
    # AND EBITDA leverage is healthy (<2.5) -> treat ND/FCF as capex-cycle noise.
    elif (nde is not None and ndf is not None and m.net_debt_ebitda is not None
            and m.net_debt_ebitda < 2.5 and ndf < nde - 2):
        ndf = None  # drop the noisy metric
    return _mean([nde, ndf, ocf])


def section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float | None]:
    # For a lender/insurer, free-cash-flow and operating-cash-flow derived metrics are
    # structurally distorted (loan originations dominate cash flows), so they are
    # excluded from scoring — the same principle already applied to the Section III
    # leverage metrics (zero weight for FINANCIALS). A heavy-capex reinvestor whose
    # capex eats its FCF gets the same treatment for the FCF-derived metrics.
    is_fin = profile == "FINANCIALS"
    heavy_capex = _heavy_capex_distortion(m)
    exclude_fcf = is_fin or heavy_capex
    # Depressed trailing GAAP EPS (amortization / patent-cliff trough) makes the
    # trailing EPS-growth metric measure the accounting trough, not the business.
    exclude_eps_growth = _earnings_distorted(m)
    # A dominant fresh acquisition's intangible amortization depresses the operating
    # margin and collapses its trajectory (see _acq_margin_distorted) — the same
    # amortization that the ROIC adjustment strips from the Section II numerator.
    exclude_acq_margin = _acq_margin_distorted(m)
    section_i = _mean([
        score_high(m.revenue_cagr_3y, GROWTH_BANDS, 0),
        None if exclude_eps_growth else score_high(m.eps_cagr_3y, GROWTH_BANDS, 0),
        None if exclude_fcf else score_high(m.fcf_cagr_3y, FCF_CAGR_BANDS, 1),
        None if exclude_fcf else score_high(m.fcf_margin, FCF_MARGIN_BANDS, 0),
        None if exclude_acq_margin else score_high(m.op_margin, MARGIN_LEVEL_BANDS, 0),
        None if exclude_acq_margin else score_high(m.op_margin_trajectory, TRAJECTORY_BANDS, 1),
        score_high(m.gross_margin, GROSS_MARGIN_BANDS, 2),
    ])
    # Acquisition-distorted names score ROIC (and its WACC spread) on tangible invested
    # capital, so goodwill/amortization from a past deal isn't read as poor capital
    # efficiency. ROTE (already tangible-based) is unchanged.
    if _acquisition_distorted(m):
        roic_ttm_val = m.roic_ex_goodwill
        roic_5y_val = m.roic_5y_ex_goodwill if m.roic_5y_ex_goodwill is not None else m.roic_5y_avg
        spread_val = (m.roic_ex_goodwill - m.wacc) if (m.wacc is not None) else m.roic_wacc_spread
    else:
        roic_ttm_val, roic_5y_val, spread_val = m.roic_ttm, m.roic_5y_avg, m.roic_wacc_spread
    section_ii = _mean([
        score_high(roic_ttm_val, ROIC_BANDS, 0),
        score_high(roic_5y_val, ROIC_BANDS, 0),
        score_high(spread_val, SPREAD_BANDS, 0),
        score_high(m.rote, ROTE_BANDS, 1),
    ])
    section_iv = _mean([
        score_low(m.shares_cagr_3y, SHARES_BANDS, 1),
        score_low(m.sbc_pct_rev, SBC_BANDS, 0),
        None if is_fin else score_high(m.earnings_quality, EQ_BANDS, 1.5),
        score_high(m.insider_ownership, INSIDER_BANDS, 2),
        score_high(m.shareholder_yield, YIELD_BANDS, 1.5),
    ])
    return {"I": section_i, "II": section_ii,
            "III": _section_iii(m, profile, heavy_capex,
                                exclude_acq_leverage=_acq_leverage_distorted(m)),
            "IV": section_iv}


MIN_SCORED_SUBSCORES = 6


def _count_subscores(m: ScreenerMetrics, profile: str) -> int:
    p = PROFILES[profile]
    candidates = [
        m.revenue_cagr_3y, m.eps_cagr_3y, m.fcf_cagr_3y, m.fcf_margin,
        m.op_margin, m.op_margin_trajectory, m.gross_margin,
        m.roic_ttm, m.roic_5y_avg, m.roic_wacc_spread, m.rote,
        m.ocf_capex,
        m.shares_cagr_3y, m.sbc_pct_rev, m.earnings_quality,
        m.insider_ownership, m.shareholder_yield,
    ]
    n = sum(1 for c in candidates if c is not None)
    if p["P"] is not None:
        n += sum(1 for c in (m.net_debt_ebitda, m.net_debt_fcf) if c is not None)
    return n


RULE_OF_40_GROWTH_CAP = 100.0


def _rule_of_40(m: ScreenerMetrics) -> float | None:
    # Statement YoY first (info revenue_growth can be broken, e.g. IREN's 0.0);
    # then info growth; then the 3y CAGR. Explicit None checks so a real 0% holds.
    if m.revenue_growth_yoy is not None:
        g = m.revenue_growth_yoy
    elif m.revenue_growth is not None:
        g = m.revenue_growth
    else:
        g = m.revenue_cagr_3y
    # Use an operating (profitability) margin, not FCF margin: a company in a heavy
    # investment phase drives FCF margin far below -100% (capex >> nascent revenue),
    # which would collapse the Rule of 40 and mislabel an elite growth story as a
    # failure. Fall back to FCF margin only when operating margin is unavailable.
    margin = m.op_margin if m.op_margin is not None else m.fcf_margin
    if g is None or margin is None:
        return None
    # Cap the growth contribution so a tiny-revenue-base hyper-growth rate can't
    # dominate the metric either.
    return min(g, RULE_OF_40_GROWTH_CAP) + margin


def _runway_months(m: ScreenerMetrics) -> float | None:
    if m.fcf is None or m.fcf >= 0:
        return float("inf")
    if m.total_cash is None:
        return None
    monthly_burn = abs(m.fcf) / 12.0
    return m.total_cash / monthly_burn if monthly_burn > 0 else float("inf")


# Unprofitable Cap Rule tunables
UNPROFITABLE_CEIL = 8.0          # any negative NI/FCF name is capped here
PP_BLEND_WEIGHT = 0.4            # weight of the pre-profit growth score vs sections
IMMINENT_RUNWAY_MONTHS = 12.0    # below this, liquidity risk hard-caps the score
IMMINENT_CEIL = 5.0
R40_BANDS = [(60, 10), (40, 8.5), (20, 6), (0, 4)]         # score_high, below -> 2
RUNWAY_BANDS = [(36, 10), (24, 8), (18, 6), (12, 4)]       # months, below -> 2


def _pre_profit_growth_score(r40: float | None, runway: float | None) -> float | None:
    """Score a pre-profit company on Rule of 40 + Cash Runway (1..10), the mean of
    whichever sub-scores are available."""
    parts: list[float | None] = []
    if r40 is not None:
        parts.append(score_high(r40, R40_BANDS, 2))
    if runway is not None:
        parts.append(10.0 if runway == float("inf") else score_high(runway, RUNWAY_BANDS, 2))
    return _mean(parts)


def score(m: ScreenerMetrics, sector: str | None):
    """Return (quality_score, section_scores, profile, breakdown). `breakdown`
    explains how the headline was derived — the section composite and, for
    unprofitable names, the pre-profit growth blend that adjusts it."""
    profile = apply_nudge(base_profile(sector), m)
    if _count_subscores(m, profile) < MIN_SCORED_SUBSCORES:
        return None, {}, profile, {}

    sections = section_scores(m, profile)
    weights = dict(zip(("I", "II", "III", "IV"), PROFILES[profile]["w"]))

    # renormalize weights over sections that produced a score
    active = {k: weights[k] for k in sections if sections[k] is not None and weights[k] > 0}
    total_w = sum(active.values())
    if total_w <= 0:
        return None, sections, profile, {}
    composite = sum(sections[k] * (w / total_w) for k, w in active.items())

    breakdown: dict = {
        "fundamentals_composite": round(composite, 2),
        "section_weights": {k: round(w / total_w, 3) for k, w in active.items()},
        "pre_profit": None,
        "final": None,
    }
    if profile == "FINANCIALS":
        breakdown["sector_adjustment"] = {
            "profile": "FINANCIALS",
            "excluded": ["FCF Margin", "FCF CAGR", "Earnings Quality (OCF/NI)",
                         "Leverage (Net Debt / EBITDA & FCF)"],
            "note": ("Free-cash-flow, operating-cash-flow and leverage metrics are "
                     "excluded — structurally distorted for lenders."),
        }
    elif _heavy_capex_distortion(m):
        breakdown["capex_adjustment"] = {
            "profile": profile,
            "excluded": ["FCF Margin", "FCF CAGR", "OCF / CapEx", "Net Debt / FCF"],
            "note": ("Trailing free cash flow is a negligible share of EBITDA because "
                     "capex is heavily reinvested (e.g. data-centre build-out), so the "
                     "FCF-derived metrics are excluded — deliberate reinvestment isn't "
                     "scored as balance-sheet weakness."),
        }
    if _acquisition_distorted(m):
        breakdown["roic_adjustment"] = {
            "profile": profile,
            "excluded": ["ROIC (TTM)", "ROIC (5y avg)", "ROIC − WACC spread"],
            "reported_roic": round(m.roic_ttm, 1) if m.roic_ttm is not None else None,
            "tangible_roic": round(m.roic_ex_goodwill, 1) if m.roic_ex_goodwill is not None else None,
            "goodwill_intangible_share": (round(m.goodwill_intangible_share, 2)
                                          if m.goodwill_intangible_share is not None else None),
            "note": ("A large past acquisition loads goodwill & intangibles onto invested "
                     "capital while its amortization depresses EBIT, so reported ROIC "
                     "understates the operating business. ROIC and its WACC spread are "
                     "scored on tangible invested capital (ex goodwill) instead."),
        }
    if _dominant_acquisition(m):
        excluded: list[str] = []
        if _acq_margin_distorted(m):
            excluded += ["Operating Margin", "Operating-Margin Trajectory"]
        if _acq_leverage_distorted(m):
            excluded += ["Net Debt / EBITDA", "Net Debt / FCF"]
        if excluded:
            breakdown["acquisition_consolidation_adjustment"] = {
                "profile": profile,
                "excluded": excluded,
                "goodwill_intangible_share": (round(m.goodwill_intangible_share, 2)
                                              if m.goodwill_intangible_share is not None else None),
                "note": ("A just-closed acquisition whose goodwill & intangibles dominate "
                         "invested capital: the trailing statements carry the full deal "
                         "(acquisition debt and intangible amortization) but only a partial "
                         "period of the acquired company's EBITDA / operating income. The "
                         "amortization-depressed operating margin and the mismatched leverage "
                         "ratios (full debt over pre-consolidation EBITDA / FCF) are excluded — "
                         "the same amortization the ROIC adjustment strips from Section II."),
            }
    if _earnings_distorted(m):
        breakdown["earnings_adjustment"] = {
            "excluded": ["EPS CAGR (3y)"],
            "trailing_pe": round(m.trailing_pe, 1) if m.trailing_pe else None,
            "forward_pe": round(m.forward_pe, 1) if m.forward_pe else None,
            "note": ("Trailing GAAP EPS is depressed (trailing P/E far above forward P/E) "
                     "by acquisition amortization or a one-off / patent-cliff trough, so the "
                     "trailing EPS-growth metric is excluded — it measures the accounting "
                     "trough, not the business."),
        }

    final = composite
    # Unprofitable Cap Rule (Gem): a company with negative net income OR negative FCF
    # is capped at 8.0.
    unprofitable = ((m.net_income is not None and m.net_income < 0)
                    or (m.fcf is not None and m.fcf < 0))
    # Pre-profit growth branch: only when the company is *operationally* unprofitable
    # (operating loss). A profitable company with negative FCF — a lender's loan-book
    # growth, or a heavy capex build — is investing, not burning toward insolvency, so
    # it is NOT routed through the runway/blend logic (which would misread the loan
    # outflows as an imminent cash-out).
    operating_loss = ((m.op_margin is not None and m.op_margin < 0)
                      or (m.op_margin is None and m.net_income is not None and m.net_income < 0))
    if operating_loss:
        r40 = _rule_of_40(m)
        runway = _runway_months(m)
        growth = _pre_profit_growth_score(r40, runway)
        capped = False
        if growth is not None:
            final = PP_BLEND_WEIGHT * growth + (1 - PP_BLEND_WEIGHT) * composite
        if runway is not None and runway < IMMINENT_RUNWAY_MONTHS:
            final, capped = min(final, IMMINENT_CEIL), True
        breakdown["pre_profit"] = {
            "applied": growth is not None,
            "rule_of_40": round(r40, 1) if r40 is not None else None,
            "runway_months": (None if runway is None else
                              ("inf" if runway == float("inf") else round(runway, 1))),
            "growth_score": round(growth, 2) if growth is not None else None,
            "blend_weight": PP_BLEND_WEIGHT,
            "capped": capped,
        }
    if unprofitable and final > UNPROFITABLE_CEIL:
        final = UNPROFITABLE_CEIL
        if breakdown["pre_profit"]:
            breakdown["pre_profit"]["capped"] = True

    final = max(1.0, min(10.0, final))
    breakdown["final"] = round(final, 1)
    return round(final, 1), sections, profile, breakdown

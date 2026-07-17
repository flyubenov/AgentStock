from __future__ import annotations

DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10
MOS = 0.90
EV_EBITDA_CAP = 20.0
# Growth-coupled ceiling for the EV/EBITDA exit multiple. EV_EBITDA_CAP is the ceiling for
# a slow/no-growth name (and the flat cap the SOTP path still uses); a genuine grower earns
# a higher ceiling so a DURABLE premium multiple — a reconstructed historical median the
# market has paid for years — survives instead of being clamped to a mature-business level.
# ANET's 27.5x median was silently clamped to 20x, single-handedly pricing the leg $27/sh
# low. The lift above EV_EBITDA_CAP is granted ONLY against that durable median (hist path),
# never a spot trailing multiple, which can be a one-quarter EBITDA dip. Linear ramp from
# EV_EBITDA_CAP at EV_EBITDA_CAP_G_LO growth to EV_EBITDA_CAP_CEIL at EV_EBITDA_CAP_G_HI.
#
# The ceiling is a TERMINAL exit multiple applied ~10 years out, so it must stay defensible
# as a mature-franchise level even for a name whose reconstructed median sits far higher.
# ANET's 27.5x median clears the 30x mid/large ceiling untouched — a genuine grower keeps its
# durable multiple, while a hyper-growth name's peak median is trimmed to the terminal ceiling
# rather than extrapolated forever.
#
# Mega-caps (>= MEGA_CAP_FLOOR) get a LOWER 25x ceiling: a >$1T franchise sustaining a 30x
# EBITDA multiple all the way to the terminal year is a far stronger claim than a $200B one
# (base-rate drag — the same size penalty the growth fade applies via _fade_hold_years).
# NVDA's peak-era median reads ~fairly valued at 25x but flips to undervalued at 30x, so the
# size-scaled ceiling keeps the mega-cap terminal multiple honest.
#
# The lift toward that ceiling is coupled to the GREATER of growth and QUALITY. Growth-only
# was the flip side of the ANET fix: it mean-reverted a low-growth compounder whose premium
# is moat/quality-driven, not growth-driven (CDNS grows 14% but the market has durably paid
# 40x+ for the EDA-duopoly franchise; growth-only compressed its 43.8x median to 22x, pricing
# it -33%). Quality is read from FCF/EBITDA conversion (the same EBITDA_CONV_FLOOR/CAP band the
# compression logic uses, and the textbook fundamental basis of an EV/EBITDA multiple) — NOT
# ROE, which is goodwill-distorted for an acquirer and would understate exactly these names.
# So a durable high-conversion franchise keeps its premium terminal multiple independent of
# its growth rate, while a low-conversion or non-durable name still compresses.
#
# The quality band is deliberately TIGHTER than the compression band (EBITDA_CONV_FLOOR/CAP
# 0.40-0.65): most asset-light software clears 0.65, so reusing it would hand nearly every
# durable software name the full ceiling and effectively bypass the growth-coupling. The
# quality lift starts only at QUALITY_CONV_LO (where a mature FCF-conversion premium begins to
# be genuinely distinctive) and reaches full lift at QUALITY_CONV_HI (near-total conversion).
# CDNS (0.79) then earns a PARTIAL lift (~25.6x) rather than the full 30x — moat credited, but
# not maxed on a merely-good conversion.
EV_EBITDA_CAP_CEIL = 30.0
EV_EBITDA_CAP_CEIL_MEGA = 25.0
EV_EBITDA_CAP_G_LO = 0.10
EV_EBITDA_CAP_G_HI = 0.30
QUALITY_CONV_LO = 0.65
QUALITY_CONV_HI = 0.90
MATURE_MULTIPLE_FACTOR = (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)  # = 14.714...
EBITDA_CONV_FLOOR = 0.40
EBITDA_CONV_CAP = 0.65
MATURE_EV_SALES = 2.0
MATURE_PE_CAP = 21.0
# Banks / lenders / insurers are financed at a lower cost of equity than the flat
# DISCOUNT_RATE default; the FINANCIAL bucket discounts its book-value legs (P/B, RIM)
# at FINANCIAL_COE. Gated to stock_type == "FINANCIAL" in engine.evaluate.
FINANCIAL_COE = 0.085
# Distorted-ROE guard for the justified P/B leg: a growth-adjusted multiple with a low
# COE amplifies an unsustainable ROE (e.g. ALL's ~45% off a thin post-buyback book).
# Cap the ROE used in calc_pb at this multiple of the COE (3.0 x 0.085 = 25.5%).
ROE_PB_CAP_MULT = 3.0
PEG_CEILING = 2.0  # GROWTH tier: forward P/E may run up to growth% * this before capping
# yfinance's trailing `earningsGrowth` is a single-quarter YoY figure that can print a
# tiny positive value on a genuinely fast-growing name (e.g. HOOD 2.7% against ~49%
# revenue growth), collapsing the PEG target multiple. When earnings growth is below
# GROWTH_TRUST_FLOOR *and* revenue growth exceeds it by GROWTH_REVENUE_RATIO, source the
# PEG growth from the bounded revenue figure instead. Guarded so a healthy signal
# (TSLA 8.3% — revenue doesn't clear the ratio; QCOM 173% — above the floor) is untouched.
GROWTH_TRUST_FLOOR = 0.10
GROWTH_REVENUE_RATIO = 3.0

# Size-coupled growth fade: larger companies face base-rate drag (a $2T company
# cannot compound a high rate for a decade the way a small one can), so their
# near-term growth fades to TERMINAL_GROWTH sooner. `hold` = years growth is held
# flat before a linear decay to TERMINAL_GROWTH by HORIZON.
MEGA_CAP_FLOOR = 1_000_000_000_000       # >= $1T  -> fade from year 1
LARGE_CAP_FADE_FLOOR = 150_000_000_000   # >= $150B -> hold 3 years, then fade
FADE_HOLD_MEGA = 0
FADE_HOLD_LARGE = 3
FADE_HOLD_MID = 5
# A mega-cap still compounding above this revenue-growth rate keeps the small-cap
# hold: the size penalty is a base-rate-drag proxy that doesn't apply while the
# growth is demonstrably there (e.g. AVGO/NVDA on the AI ramp).
MEGA_CAP_GROWTH_RELIEF = 0.40
# Trailing P/E this many times the forward P/E flags trailing EPS as depressed
# (e.g. acquisition amortization at AVGO post-VMware) -> value the forward P/E
# leg off forward EPS instead of the depressed trailing figure.
DEPRESSED_PE_RATIO = 1.5
# Forward EPS this many times trailing EPS flags a SEVERE earnings trough — the
# signature of a just-closed transformative acquisition whose trailing FCF carries the
# full deal cost but only a stub of the acquired earnings (e.g. SNPS post-Ansys, forward
# EPS ~3.9x trailing). The trailing-FCF DCF base is then unrepresentative of the combined
# company, so the DCF is rebased onto forward run-rate owner earnings. Deliberately much
# stronger than DEPRESSED_PE_RATIO (which only swaps the P/E leg's EPS): rebasing the DCF
# base is far more consequential. Set high enough to exclude ONGOING acquisition
# amortization / SBC add-backs (CDNS/AVGO ~2.2-3.2x, where trailing FCF is representative)
# and fire only on a partial-consolidation collapse where FCF itself is depressed.
TROUGH_REBASE_RATIO = 2.5

ALL_METHODS = ["dcf", "fcfe", "ev_ebitda", "pe", "ev_sales", "ddm", "pb", "rim", "sotp", "nav"]
SCENARIO_MODELS = {"dcf", "fcfe", "ev_ebitda", "ev_sales", "ddm", "rim"}
APPROX_METHODS = {"sotp", "nav"}
SCENARIO_KEYS = ("optimistic", "realistic", "pessimistic")


# -- helpers -------------------------------------------------------------------
def _pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def _apply_mos(value: float) -> float:
    return value * MOS


def _avg(scenarios: dict) -> float | None:
    vals = [v for v in scenarios.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def _null_result(has_scenarios: bool) -> dict:
    return {
        "scenarios": {"optimistic": None, "realistic": None, "pessimistic": None},
        "fair_value": None,
        "weight": 0.0,
        "has_scenarios": has_scenarios,
    }


def _ev_ebitda_ceiling(growth: float | None, durable: bool, mega: bool = False,
                       conversion: float | None = None) -> float:
    """Growth/quality-coupled ceiling for the EV/EBITDA exit multiple (see EV_EBITDA_CAP_CEIL).
    Returns the flat EV_EBITDA_CAP for a spot (non-durable) trailing multiple. For a durable
    historical median the ceiling ramps toward the terminal top (EV_EBITDA_CAP_CEIL_MEGA for a
    mega-cap, else EV_EBITDA_CAP_CEIL) on the GREATER of two fractions:
      - growth:  demonstrated revenue growth from EV_EBITDA_CAP_G_LO to _G_HI, and
      - quality: FCF/EBITDA conversion from QUALITY_CONV_LO to QUALITY_CONV_HI.
    A durable high-conversion franchise thus keeps its premium multiple even at a modest growth
    rate (CDNS), while a low-conversion / low-growth / non-durable name compresses to the base."""
    if not durable:
        return EV_EBITDA_CAP
    top = EV_EBITDA_CAP_CEIL_MEGA if mega else EV_EBITDA_CAP_CEIL
    g_frac = (0.0 if growth is None or growth <= EV_EBITDA_CAP_G_LO
              else min(1.0, (growth - EV_EBITDA_CAP_G_LO) / (EV_EBITDA_CAP_G_HI - EV_EBITDA_CAP_G_LO)))
    q_frac = 0.0
    if conversion is not None and QUALITY_CONV_HI > QUALITY_CONV_LO:
        q_frac = max(0.0, min(1.0, (conversion - QUALITY_CONV_LO) / (QUALITY_CONV_HI - QUALITY_CONV_LO)))
    return EV_EBITDA_CAP + max(g_frac, q_frac) * (top - EV_EBITDA_CAP)


def _compressed_exit_multiple(current_mult: float, conversion: float, conv_lo: float, conv_hi: float) -> float:
    """Compress the exit multiple toward a fundamentally-justified mature level:
    justified = clamp(conversion, lo, hi) * MATURE_MULTIPLE_FACTOR. Never inflates —
    returns min(current_mult, justified)."""
    conv = max(conv_lo, min(conversion, conv_hi))
    return min(current_mult, conv * MATURE_MULTIPLE_FACTOR)


def _fade_hold_years(market_cap: float | None, revenue_growth: float | None = None) -> int:
    """Years near-term growth is held before fading to TERMINAL_GROWTH, keyed to
    size: mega-caps (>= $1T) fade immediately, mid/small names hold growth longer.
    A mega-cap still growing above MEGA_CAP_GROWTH_RELIEF keeps the small-cap hold
    (its size penalty is waived while the hyper-growth is demonstrably present)."""
    mc = market_cap or 0
    if mc >= MEGA_CAP_FLOOR:
        if (revenue_growth or 0) >= MEGA_CAP_GROWTH_RELIEF:
            return FADE_HOLD_MID
        return FADE_HOLD_MEGA
    if mc >= LARGE_CAP_FADE_FLOOR:
        return FADE_HOLD_LARGE
    return FADE_HOLD_MID


def _faded_rate(g_start: float, hold: int, year: int) -> float:
    """Growth in `year` (1-indexed): g_start through `hold` years, then a linear
    decay to TERMINAL_GROWTH by HORIZON. hold >= HORIZON means no fade (flat)."""
    if year <= hold or hold >= HORIZON:
        return g_start
    return g_start + (TERMINAL_GROWTH - g_start) * (year - hold) / (HORIZON - hold)


def _scenario_dcf_equity(cf: float, growth: float, net_debt: float, shares: float,
                         hold: int = HORIZON) -> float:
    total = 0.0
    cf_t = cf
    for t in range(1, HORIZON + 1):
        cf_t *= (1 + _faded_rate(growth, hold, t))
        total += _pv(cf_t, DISCOUNT_RATE, t)
    tv = cf_t * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    total += _pv(tv, DISCOUNT_RATE, HORIZON)
    return _apply_mos((total - net_debt) / shares)


def _scenario_ev_multiple(base: float, growth: float, multiple: float, net_debt: float,
                          shares: float, hold: int = HORIZON) -> float:
    projected = base
    for t in range(1, HORIZON + 1):
        projected *= (1 + _faded_rate(growth, hold, t))
    future_ev = projected * multiple
    return _apply_mos((future_ev - net_debt) / shares / (1 + DISCOUNT_RATE) ** HORIZON)


# -- DCF (FCFF) ----------------------------------------------------------------
def rebased_dcf_base(fin: dict) -> float | None:
    """Forward run-rate owner-earnings base (forward EPS x shares) for the DCF when a
    name is in a SEVERE earnings trough — forward EPS >= TROUGH_REBASE_RATIO x trailing
    EPS (both positive). This is the just-closed transformative-acquisition signature
    (e.g. SNPS post-Ansys): trailing FCF carries the full deal cost but only a stub of the
    acquired earnings, so it understates the combined company. For these mature franchises
    FCF ~ owner earnings, so forward EPS x shares (the analyst combined run-rate) is the
    representative base. Only-help: returns the base only when it exceeds trailing FCF,
    else None (the caller keeps the trailing-FCF base)."""
    feps, teps = fin.get("forward_eps"), fin.get("eps_ttm")
    shares, fcf = fin.get("shares_outstanding"), fin.get("fcf_ttm")
    revenue = fin.get("revenue_ttm")
    if not feps or not teps or teps <= 0 or not shares:
        return None
    if feps < TROUGH_REBASE_RATIO * teps:
        return None
    base = feps * shares
    # Economic sanity: forward run-rate NET earnings cannot exceed revenue (a >100% net
    # margin is impossible). This rejects a glitched forward-EPS feed — e.g. a split-
    # mangled value (AVGO's implied ~$92B > ~$75B revenue) — before it can inflate the
    # base. A representative-FCF name mislabelled by the ratio alone is caught here.
    if revenue is not None and revenue > 0 and base > revenue:
        return None
    if fcf is not None and base <= fcf:
        return None
    return base


def calc_dcf(fin: dict, growth: dict, base_override: float | None = None,
            value_cap: float | None = None) -> dict:
    """FCFF DCF. base_override replaces the trailing-FCF base (used to rebase onto forward
    run-rate owner earnings for a severe post-acquisition trough); value_cap bounds each
    per-share scenario (used to cap the rebased leg at the trustworthy forward-P/E anchor
    so it can't run above every other signal)."""
    base = base_override if base_override is not None else fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if base is None or not shares:
        return _null_result(True)
    net_debt = fin.get("net_debt") or 0
    hold = _fade_hold_years(fin.get("market_cap"), fin.get("revenue_growth"))
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares, hold) for k in SCENARIO_KEYS}
    if value_cap is not None:
        scenarios = {k: (min(v, value_cap) if v is not None else None) for k, v in scenarios.items()}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- FCFE DCF (dormant) --------------------------------------------------------
def calc_fcfe(fin: dict, growth: dict) -> dict:
    fcf = fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if fcf is None or not shares:
        return _null_result(True)
    tax_rate = fin.get("effective_tax_rate")
    tax_rate = 0.21 if tax_rate is None else tax_rate
    interest_adj = (fin.get("interest_expense") or 0) * (1 - tax_rate)
    fcfe = fcf - interest_adj
    scenarios = {k: _scenario_dcf_equity(fcfe, growth[k], 0, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/EBITDA -----------------------------------------------------------------
def calc_ev_ebitda(fin: dict, growth: dict, hist_multiple: float | None = None,
                   hist_ebitda_base: float | None = None, compress: bool = True) -> dict:
    """EV/EBITDA exit-multiple valuation.

    hist_multiple: when provided, a historical-median EV/EBITDA replaces the
        current trailing multiple (the forward-tier "anchor to history" basis).
    hist_ebitda_base: the statement EBITDA the historical median was built from.
        When anchoring to hist_multiple, the projection base must be on the SAME
        EBITDA definition as that multiple — yfinance's info['ebitda'] (ebitda_ttm)
        can differ ~2x from statement EBITDA (content amortization at NFLX), and
        multiplying the narrow base by a multiple derived from the broad one halves
        the leg. Ignored unless hist_multiple is also supplied.
    compress: when True (default), the exit multiple is compressed toward a mature
        FCF-conversion-justified level. Forward tiers pass compress=False — a
        historical median (or the GROWTH full multiple) is already a mature level.
    """
    ebitda = fin.get("ebitda_ttm")
    shares = fin.get("shares_outstanding")
    multiple = hist_multiple if hist_multiple is not None else fin.get("ev_ebitda")
    if hist_multiple is not None and hist_ebitda_base is not None and hist_ebitda_base > 0:
        ebitda = hist_ebitda_base
    if ebitda is None or multiple is None or not shares:
        return _null_result(True)
    # A durable historical median (hist_multiple) earns a growth-coupled ceiling; a spot
    # trailing multiple keeps the flat EV_EBITDA_CAP. Demonstrated growth drives the lift.
    g_demo = fin.get("revenue_growth_stmt")
    if g_demo is None:
        g_demo = fin.get("revenue_growth")
    mega = (fin.get("market_cap") or 0) >= MEGA_CAP_FLOOR
    # Quality signal for the ceiling: trailing FCF/EBITDA conversion (read from fin, not the
    # local `ebitda` which may already be the hist statement base).
    fcf_ttm, ebitda_ttm = fin.get("fcf_ttm"), fin.get("ebitda_ttm")
    conversion = (fcf_ttm / ebitda_ttm
                  if (fcf_ttm is not None and ebitda_ttm and ebitda_ttm > 0) else None)
    multiple = min(multiple, _ev_ebitda_ceiling(
        g_demo, durable=hist_multiple is not None, mega=mega, conversion=conversion))
    fcf = fin.get("fcf_ttm")
    if compress and fcf is not None and ebitda > 0:
        conversion = fcf / ebitda
        multiple = _compressed_exit_multiple(multiple, conversion, EBITDA_CONV_FLOOR, EBITDA_CONV_CAP)
    net_debt = fin.get("net_debt") or 0
    hold = _fade_hold_years(fin.get("market_cap"), fin.get("revenue_growth"))
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares, hold) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/Sales ------------------------------------------------------------------
# Below this trailing YoY revenue growth, TTM is treated as a fair proxy for today's
# revenue and the base is left alone. The gate is what separates "TTM is stale" from
# "the latest quarter is seasonally big": a retailer's Q4 annualises well above TTM, but
# at single-digit growth TTM does NOT lag, and annualising a seasonal peak would inflate
# the base. Only a genuine hyper-grower clears this.
RUN_RATE_GROWTH_FLOOR = 0.50


def run_rate_revenue(quarters, revenue_ttm: float | None,
                     revenue_growth: float | None) -> float | None:
    """Today's annualised revenue run-rate (latest quarter x 4), or None to keep TTM.

    TTM is the sum of the last four quarters, so it represents revenue centred ~6 months
    ago, not today. For a mature name that lag is worth ~2% and is irrelevant; for a
    hyper-grower it is enormous (NBIS: TTM $873M vs a $1.596B run-rate, 83% low), and the
    EV/Sales leg then compounds growth from a base already behind today's actual —
    understating the value on the base as well as the capped rate.

    `quarters` is latest-first quarterly revenue. Two guards: the growth gate above, and
    only-help — a decelerating name's run-rate falls below TTM and must never lower the
    base (same only-help contract as rebased_dcf_base).

    This is NOT double-counting against the growth rate: `revenue_growth` is trailing and
    only selects the base and the cap, while the projection runs FORWARD from t=0. Using a
    more accurate t=0 is a correction, not extra growth.
    """
    if not quarters or revenue_ttm is None or revenue_growth is None:
        return None
    if revenue_growth <= RUN_RATE_GROWTH_FLOOR:
        return None
    latest = quarters[0]
    if latest is None or latest <= 0:
        return None
    run_rate = latest * 4
    return run_rate if run_rate > revenue_ttm else None


def calc_ev_sales(fin: dict, growth: dict) -> dict:
    # Project from the current run-rate when one was derived (see run_rate_revenue);
    # otherwise TTM. Explicit None check so a genuine 0 can never fall through to TTM.
    revenue = fin.get("revenue_run_rate")
    if revenue is None:
        revenue = fin.get("revenue_ttm")
    multiple = fin.get("ev_sales")
    shares = fin.get("shares_outstanding")
    if revenue is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, MATURE_EV_SALES)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(revenue, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/E (capped market multiple) ----------------------------------------------
def _forward_target_pe(fin: dict) -> float | None:
    """Forward-tier target: forward P/E capped by a PEG ceiling (growth% * PEG_CEILING).
    The PEG growth is sourced from earnings growth, but re-sourced from bounded revenue
    growth when earnings growth is an unreliable small-positive value badly contradicted
    by much stronger revenue growth (see GROWTH_TRUST_FLOOR / GROWTH_REVENUE_RATIO), and
    falls back to revenue growth outright when earnings growth is missing or <= 0.
    Returns None when forward P/E or a positive growth signal is unavailable, so the
    caller can fall back to the mature trailing-P/E path."""
    fpe = fin.get("forward_pe")
    if not fpe or fpe <= 0:
        return None
    g = fin.get("earnings_growth")
    rev_g = fin.get("revenue_growth") or 0
    # A small-but-positive trailing earnings-growth figure badly contradicted by much
    # stronger revenue growth is treated as an unreliable single-quarter yfinance
    # artifact -> source growth from the bounded revenue figure instead.
    if g is not None and 0 < g < GROWTH_TRUST_FLOOR and rev_g > g * GROWTH_REVENUE_RATIO:
        g = rev_g
    if g is None or g <= 0:
        g = rev_g
    if g <= 0:
        return None
    return min(fpe, g * 100 * PEG_CEILING)


def _normalized_forward_eps(fin: dict, trailing_eps: float) -> float:
    """Value the forward P/E leg off forward EPS when trailing earnings are
    depressed (trailing P/E far above forward P/E, e.g. acquisition amortization
    at AVGO post-VMware). Otherwise keep trailing EPS. Never lowers the EPS."""
    feps = fin.get("forward_eps")
    tpe, fpe = fin.get("trailing_pe"), fin.get("forward_pe")
    if (feps and feps > trailing_eps and tpe and fpe and fpe > 0
            and tpe / fpe > DEPRESSED_PE_RATIO):
        return feps
    return trailing_eps


def calc_pe(fin: dict, forward: bool = False) -> dict:
    eps = fin.get("eps_ttm")
    if eps is None or eps <= 0:
        return _null_result(False)
    if forward:
        eps = _normalized_forward_eps(fin, eps)
    target_pe = _forward_target_pe(fin) if forward else None
    if target_pe is None:
        trailing_pe = fin.get("trailing_pe")
        if trailing_pe is None or trailing_pe <= 0:
            return _null_result(False)
        target_pe = min(trailing_pe, MATURE_PE_CAP)
    fv = _apply_mos(eps * target_pe)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv,
            "weight": 0.0, "has_scenarios": False}


# -- DDM (Gordon growth) -------------------------------------------------------
def calc_ddm(fin: dict, growth: dict) -> dict:
    div = fin.get("dividend_rate")
    if div is None or div <= 0:
        return _null_result(True)

    def scenario_ddm(g: float) -> float | None:
        capped_g = min(g, DISCOUNT_RATE - 0.01)
        if DISCOUNT_RATE <= capped_g:
            return None
        return _apply_mos(div * (1 + capped_g) / (DISCOUNT_RATE - capped_g))

    scenarios = {k: scenario_ddm(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/B (justified, growth-adjusted) ------------------------------------------
def calc_pb(fin: dict) -> dict:
    """Justified P/B = (ROE - g) / (COE - g), the growth-adjusted Gordon form.

    COE is the leg's discount rate: fin['cost_of_equity'] when supplied (the
    FINANCIAL bucket sets FINANCIAL_COE in engine.evaluate), else DISCOUNT_RATE.
    g is bounded strictly below COE. At ROE == COE the multiple is exactly 1.0.
    The ROE input is capped at ROE_PB_CAP_MULT x COE so a distorted, unsustainable
    ROE (thin-book insurer artifact) can't run the multiple away."""
    bvps = fin.get("book_value_per_share")
    roe = fin.get("return_on_equity")
    if bvps is None or roe is None:
        return _null_result(False)
    coe = fin.get("cost_of_equity") or DISCOUNT_RATE
    roe = min(roe, ROE_PB_CAP_MULT * coe)
    g = min(TERMINAL_GROWTH, coe - 0.01)
    justified_pb = (roe - g) / (coe - g)
    fv = _apply_mos(bvps * max(justified_pb, 0.1))
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv,
            "weight": 0.0, "has_scenarios": False}


# -- RIM (residual income) -----------------------------------------------------
def calc_rim(fin: dict, growth: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    eps = fin.get("eps_ttm")
    if bvps is None or eps is None:
        return _null_result(True)
    coe = fin.get("cost_of_equity") or 0.10
    roe = eps / bvps if bvps > 0 else 0

    def scenario_rim(g: float) -> float:
        total = 0.0
        bv = bvps
        for t in range(1, HORIZON + 1):
            bv_prev = bv
            bv = bv * (1 + g)
            total += _pv(bv_prev * (roe - coe), coe, t)
        return _apply_mos(bvps + total)

    scenarios = {k: scenario_rim(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- SOTP (EV/EBITDA with 15% conglomerate discount) ---------------------------
def calc_sotp(fin: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    # A non-positive EBITDA or multiple cannot yield a meaningful EV/EBITDA-based SOTP:
    # ebitda * multiple would either reconstruct ~current EV via a double-negative
    # (circular, and it defeats the cap below) or push the leg negative.
    if (ebitda is None or ebitda <= 0
            or multiple is None or multiple <= 0 or not shares):
        return _null_result(False)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    ev = ebitda * multiple
    fv = _apply_mos((ev - net_debt) / shares * 0.85)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- NAV (book value adjusted for net debt per share) --------------------------
def calc_nav(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    shares = fin.get("shares_outstanding")
    if bvps is None or not shares:
        return _null_result(False)
    net_debt = fin.get("net_debt") or 0
    fv = _apply_mos(bvps - net_debt / shares)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- composite -----------------------------------------------------------------
def composite(results: dict) -> float | None:
    """Weighted average over results whose fair_value is not None and weight > 0."""
    total = 0.0
    total_weight = 0.0
    for r in results.values():
        if r.get("fair_value") is not None and r.get("weight", 0) > 0:
            total += r["fair_value"] * r["weight"]
            total_weight += r["weight"]
    return total / total_weight if total_weight > 0 else None

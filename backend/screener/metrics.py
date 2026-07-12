from __future__ import annotations
from collections.abc import Sequence
from screener.models import ScreenerInputs, ScreenerMetrics, StatementSeries


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def series_cagr(series: list[float | None], span: int) -> float | None:
    if not series or len(series) < 2:
        return None
    end = series[0]
    idx = min(span, len(series) - 1)
    return cagr(series[idx], end, idx)


def price_cagr(monthly: Sequence[float], years: int) -> float | None:
    if not monthly or len(monthly) < 2:
        return None
    end = monthly[-1]
    months_back = years * 12
    idx = max(0, len(monthly) - 1 - months_back)
    span_years = (len(monthly) - 1 - idx) / 12
    if span_years <= 0:
        return None
    return _cagr_frac(monthly[idx], end, span_years)


def _cagr_frac(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def pct(x: float | None) -> float | None:
    return None if x is None else x * 100.0


ERP = 0.05  # equity risk premium (assumed constant)
DEFAULT_RISK_FREE = 0.043
# yfinance occasionally reports a stale/aggressive beta (e.g. AMD's 2.47, reflecting its
# 2022 crash window) that inflates the cost-of-equity hurdle and pins the ROIC-WACC
# spread sub-score at zero. Cap the beta feeding WACC: a beta above 2.0 is already
# "very risky", and pushing beyond it is usually noise rather than signal. Can only
# lower an over-stated hurdle, never raise it; normal betas (0.5-1.8) are untouched.
BETA_CEILING = 2.0


def _tax_rate(income: StatementSeries | None) -> float:
    if income is None:
        return 0.21
    t = income.latest("Tax Rate For Calcs")
    if t is None or t < 0 or t > 0.6:
        return 0.21
    return t


def roic(ebit: float | None, tax_rate: float, invested_capital: float | None) -> float | None:
    if ebit is None or invested_capital is None or invested_capital <= 0:
        return None
    return ebit * (1 - tax_rate) / invested_capital


def goodwill_intangibles(bal: StatementSeries | None, idx: int) -> float | None:
    """Goodwill + other intangible assets for a given year. Prefers the combined
    balance-sheet row; falls back to summing the components. Returns None when
    neither is reported (a company with no material acquisitions)."""
    if bal is None:
        return None
    combined = bal.value("Goodwill And Other Intangible Assets", idx)
    if combined is not None:
        return combined
    gw = bal.value("Goodwill", idx)
    intang = bal.value("Other Intangible Assets", idx)
    if gw is None and intang is None:
        return None
    return (gw or 0.0) + (intang or 0.0)


def wacc(inp: ScreenerInputs, tax_rate: float) -> float | None:
    info = inp.info
    beta = info.get("beta")
    if beta is None:
        return None
    beta = min(beta, BETA_CEILING)
    rf = inp.risk_free if inp.risk_free is not None else DEFAULT_RISK_FREE
    cost_equity = rf + beta * ERP
    debt = info.get("totalDebt") or 0.0
    equity = info.get("marketCap") or 0.0
    total = debt + equity
    if total <= 0:
        return cost_equity
    interest = None
    if inp.income is not None:
        interest = inp.income.latest("Interest Expense")
    cost_debt = (abs(interest) / debt) * (1 - tax_rate) if (interest and debt > 0) else 0.0
    return (equity / total) * cost_equity + (debt / total) * cost_debt


def compute_metrics(inp: ScreenerInputs) -> ScreenerMetrics:
    m = ScreenerMetrics()
    info = inp.info
    inc, bal, cf = inp.income, inp.balance, inp.cashflow
    tax = _tax_rate(inc)

    # --- Section II ---
    if inc is not None and bal is not None:
        m.roic_ttm = pct(roic(inc.latest("EBIT"), tax, bal.latest("Invested Capital")))
        annual = []
        annual_ex = []  # ROIC on tangible invested capital (ex goodwill & intangibles)
        for i in range(len(inc.years)):
            ic = bal.value("Invested Capital", i)
            r = roic(inc.value("EBIT", i), tax, ic)
            if r is not None:
                annual.append(r)
            gwi = goodwill_intangibles(bal, i)
            if ic is not None and gwi is not None:
                r_ex = roic(inc.value("EBIT", i), tax, ic - gwi)
                if r_ex is not None:
                    annual_ex.append(r_ex)
        if annual:
            m.roic_5y_avg = pct(sum(annual) / len(annual))
        if annual_ex:
            m.roic_5y_ex_goodwill = pct(sum(annual_ex) / len(annual_ex))
        ic0 = bal.latest("Invested Capital")
        gwi0 = goodwill_intangibles(bal, 0)
        if ic0 is not None and gwi0 is not None:
            m.roic_ex_goodwill = pct(roic(inc.latest("EBIT"), tax, ic0 - gwi0))
            if ic0 > 0:
                m.goodwill_intangible_share = gwi0 / ic0
        ni = inc.latest("Net Income")
        tbv = bal.latest("Tangible Book Value")
        if ni is not None and tbv and tbv > 0:
            m.rote = ni / tbv * 100.0
    w = wacc(inp, tax)
    m.wacc = pct(w)
    if m.roic_ttm is not None and w is not None:
        m.roic_wacc_spread = m.roic_ttm - w * 100.0

    # --- Section III ---
    net_debt = bal.latest("Net Debt") if bal is not None else None
    if net_debt is None and info.get("totalDebt") is not None:
        net_debt = (info.get("totalDebt") or 0.0) - (info.get("totalCash") or 0.0)
    m.net_debt = net_debt
    m.ebitda = info.get("ebitda")
    if net_debt is not None and m.ebitda:
        m.net_debt_ebitda = net_debt / m.ebitda
    fcf = cf.latest("Free Cash Flow") if cf is not None else info.get("freeCashflow")
    m.fcf = fcf
    if net_debt is not None and fcf:
        m.net_debt_fcf = net_debt / fcf
    if cf is not None:
        ocf = cf.latest("Operating Cash Flow")
        capex = cf.latest("Capital Expenditure")
        if ocf is not None and capex:
            m.ocf_capex = ocf / abs(capex)
    if bal is not None:
        tbv = bal.latest("Tangible Book Value")
        shares = bal.latest("Ordinary Shares Number") or info.get("sharesOutstanding")
        if tbv is not None and shares:
            m.tangible_bv_per_share = tbv / shares

    # --- Section I ---
    if inc is not None:
        m.revenue_cagr_3y = pct(series_cagr(inc.series("Total Revenue"), 3))
        m.eps_cagr_3y = pct(series_cagr(inc.series("Diluted EPS"), 3))
    if cf is not None:
        m.fcf_cagr_3y = pct(series_cagr(cf.series("Free Cash Flow"), 3))
    revenue = (inc.latest("Total Revenue") if inc else None) or info.get("totalRevenue")
    if fcf is not None and revenue:
        m.fcf_margin = fcf / revenue * 100.0
    m.op_margin = pct(info.get("operatingMargins"))
    m.gross_margin = pct(info.get("grossMargins"))
    if inc is not None and revenue:
        # operating-margin trajectory: latest OM minus OM at oldest available year (pp)
        oi_old = inc.value("Operating Income", min(3, len(inc.years) - 1))
        rev_old = inc.value("Total Revenue", min(3, len(inc.years) - 1))
        oi_new = inc.latest("Operating Income")
        if oi_old is not None and rev_old and oi_new is not None and revenue:
            m.op_margin_trajectory = (oi_new / revenue - oi_old / rev_old) * 100.0

    # --- Section IV ---
    if inc is not None:
        shares_series = inc.series("Diluted Average Shares")
        m.shares_cagr_3y = pct(series_cagr(shares_series, 3))
    if cf is not None and revenue:
        sbc = cf.latest("Stock Based Compensation")
        if sbc is not None:
            m.sbc_pct_rev = abs(sbc) / revenue * 100.0
    if cf is not None:
        ocf = cf.latest("Operating Cash Flow")
        ni = inc.latest("Net Income") if inc else None
        if ocf is not None and ni and abs(ni) > 1e-6:
            m.earnings_quality = ocf / ni
    m.insider_ownership = pct(info.get("heldPercentInsiders"))
    mktcap = info.get("marketCap")
    if cf is not None and mktcap:
        buyback = cf.latest("Repurchase Of Capital Stock") or 0.0
        divs = cf.latest("Cash Dividends Paid") or 0.0
        m.shareholder_yield = (abs(buyback) + abs(divs)) / mktcap * 100.0

    # --- Section V (reference, not scored) ---
    m.trailing_pe = info.get("trailingPE")
    m.forward_pe = info.get("forwardPE")
    m.peg = info.get("trailingPegRatio")
    m.price_sales = info.get("priceToSalesTrailing12Months")
    ev = info.get("enterpriseValue")
    if fcf and mktcap:
        m.price_fcf = mktcap / fcf if fcf > 0 else None
    if fcf is not None and ev:
        m.fcf_yield = fcf / ev * 100.0
    if m.fcf_yield is not None and inp.risk_free is not None:
        m.owner_earnings_yield = m.fcf_yield - inp.risk_free * 100.0
    m.price_cagr_3y = pct(price_cagr(inp.price_monthly, 3))
    m.price_cagr_5y = pct(price_cagr(inp.price_monthly, 5))

    # --- raw cap-rule inputs ---
    m.net_income = inc.latest("Net Income") if inc else None
    m.revenue_growth = pct(info.get("revenueGrowth"))
    m.total_cash = info.get("totalCash")

    m.sector = info.get("sector")
    return m

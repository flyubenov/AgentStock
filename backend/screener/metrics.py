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


def wacc(inp: ScreenerInputs, tax_rate: float) -> float | None:
    info = inp.info
    beta = info.get("beta")
    if beta is None:
        return None
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
        for i in range(len(inc.years)):
            r = roic(inc.value("EBIT", i), tax, bal.value("Invested Capital", i))
            if r is not None:
                annual.append(r)
        if annual:
            m.roic_5y_avg = pct(sum(annual) / len(annual))
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

    m.sector = info.get("sector")
    return m

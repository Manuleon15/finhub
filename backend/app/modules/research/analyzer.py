"""Equity Research Analyzer — calcula métricas de calidad financiera.

Métricas calculadas:
- ROIC (Return on Invested Capital)
- FCF Margin (Free Cash Flow / Revenue)
- Debt-to-Equity
- Gross Margin
- Operating Margin
- Current Ratio
- Earnings Yield (E/P)
- Revenue Growth
- FCF Growth
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.data_providers.yahoo import get_ticker_info, get_financials

logger = logging.getLogger("finhub.analyzer")


# Nombres alternativos que puede usar yfinance/yahooquery para cada campo
# (varían según el proveedor y a veces entre tickers).
FIELD_CANDIDATES: Dict[str, List[str]] = {
    "net_income": [
        "Net Income",
        "NetIncome",
        "Net Income Common Stockholders",
        "Net Income Applicable To Common Shares",
    ],
    "revenue": ["Total Revenue", "TotalRevenue", "Revenue"],
    "gross_profit": ["Gross Profit", "GrossProfit"],
    "ebit": ["EBIT", "Ebit", "Operating Income"],
    "operating_cash_flow": [
        "Operating Cash Flow",
        "OperatingCashFlow",
        "Total Cash From Operating Activities",
        "Cash Flow From Continuing Operating Activities",
    ],
    "capital_expenditure": ["Capital Expenditure", "CapitalExpenditure", "Purchase Of PPE"],
    "cash": [
        "Cash And Cash Equivalents",
        "CashAndCashEquivalents",
        "Cash",
        "Cash Cash Equivalents And Short Term Investments",
    ],
    "total_debt": ["Total Debt", "TotalDebt", "Long Term Debt"],
    "total_equity": [
        "Stockholders Equity",
        "StockholdersEquity",
        "Total Equity Gross Minority Interest",
        "Total Stockholder Equity",
    ],
    "total_assets": ["Total Assets", "TotalAssets"],
    "current_assets": ["Total Current Assets", "Current Assets", "TotalCurrentAssets"],
    "current_liabilities": ["Total Current Liabilities", "Current Liabilities", "TotalCurrentLiabilities"],
    "shares_outstanding": [
        "Diluted Average Shares",
        "Basic Average Shares",
        "Ordinary Shares Number",
        "Share Issued",
    ],
}


def _find_field(
    financials: Dict[str, Any],
    statement: str,
    candidates: List[str],
    year_offset: int = 0,
) -> Optional[float]:
    """Busca el primer campo disponible (de una lista de nombres alternativos)
    para un año concreto. year_offset=0 -> año más reciente."""
    stmt = financials.get(statement, {})
    if not stmt:
        return None
    years = sorted(stmt.keys(), reverse=True)
    if year_offset >= len(years):
        return None
    year_data = stmt[years[year_offset]] or {}
    for name in candidates:
        val = year_data.get(name)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _find_field_any_year(
    financials: Dict[str, Any],
    statement: str,
    candidates: List[str],
) -> Optional[float]:
    """Como _find_field, pero recorre todos los años disponibles (del más
    reciente al más antiguo) hasta encontrar un valor. Útil como último
    fallback cuando no importa de qué año venga el dato."""
    stmt = financials.get(statement, {})
    if not stmt:
        return None
    for year in sorted(stmt.keys(), reverse=True):
        year_data = stmt[year] or {}
        for name in candidates:
            val = year_data.get(name)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
    return None


def get_capex(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "cash_flow", FIELD_CANDIDATES["capital_expenditure"], year_offset)


def get_cash(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "balance_sheet", FIELD_CANDIDATES["cash"], year_offset)


def get_operating_cf(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "cash_flow", FIELD_CANDIDATES["operating_cash_flow"], year_offset)


def get_revenue(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "income_statement", FIELD_CANDIDATES["revenue"], year_offset)


def get_total_debt(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "balance_sheet", FIELD_CANDIDATES["total_debt"], year_offset)


def get_total_equity(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "balance_sheet", FIELD_CANDIDATES["total_equity"], year_offset)


def get_total_assets(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    return _find_field(financials, "balance_sheet", FIELD_CANDIDATES["total_assets"], year_offset)


def get_fcf(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    """Free Cash Flow = Operating Cash Flow - Capex (valor absoluto)."""
    ocf = get_operating_cf(financials, year_offset)
    capex = get_capex(financials, year_offset)
    if ocf is not None and capex is not None:
        return ocf - abs(capex)
    return None


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """División segura que maneja None y división por cero."""
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def get_metric(
    financials: Dict[str, Any],
    statement: str,
    metric_name: str,
    year_offset: int = 0,
) -> Optional[float]:
    """Extrae una métrica específica de los estados financieros.

    Args:
        financials: dict de get_financials()
        statement: "income_statement" | "balance_sheet" | "cash_flow"
        metric_name: nombre de la fila en yfinance
        year_offset: 0 = año más reciente, 1 = anterior, etc.
    """
    stmt = financials.get(statement, {})
    if not stmt:
        return None

    years = sorted(stmt.keys(), reverse=True)
    if year_offset >= len(years):
        return None

    year_data = stmt[years[year_offset]]
    val = year_data.get(metric_name)
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
    return None


def calculate_roic(financials: Dict[str, Any], info: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """ROIC = NOPAT / (Total Debt + Total Equity)

    NOPAT = Operating Income * (1 - tax_rate)
    Aproximación: usamos EBIT como proxy de Operating Income
    Tax rate aproximado: 21% (US corporate tax rate)
    """
    ebit = get_metric(financials, "income_statement", "EBIT", 0)
    total_debt = get_metric(financials, "balance_sheet", "Total Debt", 0)
    total_equity = get_metric(financials, "balance_sheet", "Stockholders Equity", 0)

    # Respaldo: si el estado financiero en crudo no trae el campo (frecuente
    # en empresas extranjeras con nombres de línea distintos), usar los
    # ratios ya calculados que trae el propio proveedor.
    info = info or {}
    if total_debt is None and info.get("total_debt") is not None:
        total_debt = info["total_debt"]

    if ebit is None or (total_debt is None and total_equity is None):
        if info.get("return_on_equity") is not None:
            # ROE como aproximación de última instancia (no es ROIC exacto,
            # pero es mejor que N/A cuando no hay datos de EBIT/deuda).
            return round(info["return_on_equity"], 4)
        return None

    tax_rate = 0.21
    nopat = ebit * (1 - tax_rate)
    invested_capital = (total_debt or 0) + (total_equity or 0)

    if invested_capital == 0:
        return None

    roic = nopat / invested_capital
    return round(roic, 4)


def calculate_fcf_margin(financials: Dict[str, Any], info: Dict[str, Any]) -> Optional[float]:
    """FCF Margin = Free Cash Flow / Revenue"""
    # Intentar desde cash_flow statement primero
    ocf = get_metric(financials, "cash_flow", "Operating Cash Flow", 0)
    capex = get_metric(financials, "cash_flow", "Capital Expenditure", 0)

    if ocf is not None and capex is not None:
        fcf = ocf - abs(capex)
    elif info.get("free_cash_flow") is not None:
        fcf = info["free_cash_flow"]
    else:
        return None

    revenue = get_metric(financials, "income_statement", "Total Revenue", 0)
    if revenue is None and info.get("total_revenue"):
        revenue = info["total_revenue"]

    if revenue is None or revenue == 0:
        return None

    return round(fcf / revenue, 4)


def calculate_debt_to_equity(financials: Dict[str, Any], info: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """Debt-to-Equity = Total Debt / Stockholders Equity"""
    total_debt = get_metric(financials, "balance_sheet", "Total Debt", 0)
    equity = get_metric(financials, "balance_sheet", "Stockholders Equity", 0)

    if total_debt is None or equity is None or equity == 0:
        # yfinance a veces usa "Total Debt" vs "Long Term Debt"
        total_debt = get_metric(financials, "balance_sheet", "Long Term Debt", 0)

    result = safe_div(total_debt, equity)
    if result is not None:
        return result

    # Respaldo: ratio ya calculado por el proveedor (yfinance suele darlo
    # en tanto por ciento, ej. 45.2 = 45.2%; lo pasamos a razón decimal).
    info = info or {}
    if info.get("debt_to_equity") is not None:
        raw = info["debt_to_equity"]
        return round(raw / 100, 4) if raw > 5 else round(raw, 4)

    return None


def calculate_gross_margin(financials: Dict[str, Any], info: Dict[str, Any]) -> Optional[float]:
    """Gross Margin = Gross Profit / Revenue"""
    # El ratio que ya trae el proveedor es más fiable que reconstruirlo a
    # mano (los nombres de línea en los estados financieros en crudo
    # varían mucho, sobre todo en empresas que no reportan en USD/GAAP).
    if info.get("gross_margins") is not None:
        return round(info["gross_margins"], 4)

    gross_profit = get_metric(financials, "income_statement", "Gross Profit", 0)
    revenue = get_metric(financials, "income_statement", "Total Revenue", 0)

    if gross_profit is None and info.get("gross_profits"):
        gross_profit = info["gross_profits"]
    if revenue is None and info.get("total_revenue"):
        revenue = info["total_revenue"]

    return safe_div(gross_profit, revenue)


def calculate_revenue_growth(financials: Dict[str, Any], info: Dict[str, Any]) -> Optional[float]:
    """Revenue Growth YoY = (Revenue_actual - Revenue_anterior) / Revenue_anterior"""
    revenue_current = get_metric(financials, "income_statement", "Total Revenue", 0)
    revenue_prev = get_metric(financials, "income_statement", "Total Revenue", 1)

    if revenue_current is not None and revenue_prev is not None and revenue_prev != 0:
        return round((revenue_current - revenue_prev) / abs(revenue_prev), 4)

    # Fallback a info de yfinance
    if info.get("revenue_growth") is not None:
        return round(info["revenue_growth"], 4)

    return None


def calculate_fcf_growth(financials: Dict[str, Any]) -> Optional[float]:
    """FCF Growth YoY"""
    def get_fcf(offset: int) -> Optional[float]:
        ocf = get_metric(financials, "cash_flow", "Operating Cash Flow", offset)
        capex = get_metric(financials, "cash_flow", "Capital Expenditure", offset)
        if ocf is not None and capex is not None:
            return ocf - abs(capex)
        return None

    fcf_current = get_fcf(0)
    fcf_prev = get_fcf(1)

    if fcf_current is not None and fcf_prev is not None and fcf_prev != 0:
        return round((fcf_current - fcf_prev) / abs(fcf_prev), 4)

    return None


def calculate_earnings_yield(info: Dict[str, Any]) -> Optional[float]:
    """Earnings Yield = 1 / PE ratio (E/P)"""
    pe = info.get("pe_ratio")
    if pe is not None and pe > 0:
        return round(1 / pe, 4)
    return None


def calculate_fcf_yield(financials: Dict[str, Any], info: Dict[str, Any]) -> Optional[float]:
    """FCF Yield = FCF / Market Cap"""
    ocf = get_metric(financials, "cash_flow", "Operating Cash Flow", 0)
    capex = get_metric(financials, "cash_flow", "Capital Expenditure", 0)

    if ocf is not None and capex is not None:
        fcf = ocf - abs(capex)
    elif info.get("free_cash_flow") is not None:
        fcf = info["free_cash_flow"]
    else:
        return None

    market_cap = info.get("market_cap")
    if market_cap is None or market_cap == 0:
        return None

    return round(fcf / market_cap, 4)


def classify_debt(debt_to_equity: Optional[float]) -> str:
    """Clasifica el nivel de deuda."""
    if debt_to_equity is None:
        return "N/A"
    if debt_to_equity < 0.3:
        return "Low"
    if debt_to_equity < 0.6:
        return "Moderate"
    if debt_to_equity < 1.0:
        return "High"
    return "Very High"


def analyze_company(ticker: str) -> Dict[str, Any]:
    """Análisis completo de calidad financiera de una empresa.

    Args:
        ticker: símbolo bursátil (ej. MSFT)

    Returns:
        dict con business_overview, financial_quality, y métricas raw.
    """
    logger.info(f"Analizando {ticker}...")

    info = get_ticker_info(ticker)
    financials = get_financials(ticker)

    if "error" in info:
        return {"ticker": ticker.upper(), "error": info["error"]}

    # Calcular todas las métricas
    roic = calculate_roic(financials, info)
    fcf_margin = calculate_fcf_margin(financials, info)
    debt_to_equity = calculate_debt_to_equity(financials, info)
    gross_margin = calculate_gross_margin(financials, info)
    revenue_growth = calculate_revenue_growth(financials, info)
    fcf_growth = calculate_fcf_growth(financials)
    earnings_yield = calculate_earnings_yield(info)
    fcf_yield = calculate_fcf_yield(financials, info)

    # Business Overview
    business_overview = {
        "name": info.get("name", ticker),
        "ticker": ticker.upper(),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "description": info.get("description", ""),
        "country": info.get("country", ""),
        "website": info.get("website", ""),
        "employees": info.get("employees"),
        "market_cap": info.get("market_cap"),
        "price": info.get("price"),
        "currency": info.get("currency", "USD"),
    }

    # Financial Quality
    financial_quality = {
        "roic": roic,
        "roic_label": f"{roic*100:.1f}%" if roic is not None else "N/A",
        "fcf_margin": fcf_margin,
        "fcf_margin_label": f"{fcf_margin*100:.1f}%" if fcf_margin is not None else "N/A",
        "debt_to_equity": debt_to_equity,
        "debt_label": classify_debt(debt_to_equity),
        "gross_margin": gross_margin,
        "gross_margin_label": f"{gross_margin*100:.1f}%" if gross_margin is not None else "N/A",
        "revenue_growth": revenue_growth,
        "revenue_growth_label": f"{revenue_growth*100:.1f}%" if revenue_growth is not None else "N/A",
        "fcf_growth": fcf_growth,
        "fcf_growth_label": f"{fcf_growth*100:.1f}%" if fcf_growth is not None else "N/A",
        "current_ratio": info.get("current_ratio"),
        "operating_margin": info.get("operating_margins"),
        "profit_margin": info.get("profit_margins"),
        "return_on_equity": info.get("return_on_equity"),
    }

    # Valuation metrics
    valuation = {
        "pe_ratio": info.get("pe_ratio"),
        "forward_pe": info.get("forward_pe"),
        "pb_ratio": info.get("pb_ratio"),
        "ev_to_revenue": info.get("ev_to_revenue"),
        "ev_to_ebitda": info.get("ev_to_ebitda"),
        "peg_ratio": info.get("peg_ratio"),
        "eps": info.get("eps"),
        "book_value_per_share": info.get("book_value_per_share"),
        "earnings_yield": earnings_yield,
        "fcf_yield": fcf_yield,
        "dividend_yield": info.get("dividend_yield"),
        "target_mean_price": info.get("target_mean_price"),
        "analyst_recommendation": info.get("recommendation"),
    }

    return {
        "ticker": ticker.upper(),
        "business_overview": business_overview,
        "financial_quality": financial_quality,
        "valuation": valuation,
        "raw_info": info,
        "raw_financials": financials,
    }

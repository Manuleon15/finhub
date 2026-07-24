"""DCF (Discounted Cash Flow) — valoración por escenarios bear/base/bull.

Modelo:
1. Proyecta Free Cash Flow a 5 años con tasa de crecimiento por escenario
2. Calcula WACC desde beta + risk-free rate + market premium
3. Terminal Value con Gordon Growth Model
4. Descuenta todo al presente con WACC
5. Divide por shares outstanding → precio por acción intrínseco

Escenarios:
- Bear: crecimiento conservador, terminal growth bajo, WACC alto
- Base: crecimiento medio, terminal growth medio, WACC medio
- Bull: crecimiento optimista, terminal growth alto, WACC bajo
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, Tuple

from app.core.data_providers.yahoo import get_ticker_info, get_financials
from app.modules.research.analyzer import get_metric

logger = logging.getLogger("finhub.dcf")

# Parámetros del modelo (configurables)
RISK_FREE_RATE = 0.045  # 10Y Treasury ~4.5%
MARKET_RISK_PREMIUM = 0.05  # 5% premium
TAX_RATE = 0.21  # Corporate tax rate US

# Ajustes por escenario
SCENARIOS = {
    "bear": {
        "growth_adjustment": -0.05,  # 5pp menos que el histórico
        "terminal_growth": 0.015,  # 1.5%
        "wacc_adjustment": 0.02,  # +2pp WACC (más conservador)
        "margin_adjustment": -0.03,  # -3pp márgenes
    },
    "base": {
        "growth_adjustment": 0.0,
        "terminal_growth": 0.025,  # 2.5%
        "wacc_adjustment": 0.0,
        "margin_adjustment": 0.0,
    },
    "bull": {
        "growth_adjustment": 0.03,  # 3pp más
        "terminal_growth": 0.035,  # 3.5%
        "wacc_adjustment": -0.01,  # -1pp WACC
        "margin_adjustment": 0.02,  # +2pp márgenes
    },
}


def calculate_wacc(
    info: Dict[str, Any],
    financials: Dict[str, Any],
    wacc_adjustment: float = 0.0,
) -> float:
    """Calcula WACC (Weighted Average Cost of Capital).

    WACC = (E/V) * Cost of Equity + (D/V) * Cost of Debt * (1 - tax)

    Cost of Equity (CAPM) = Risk-free + Beta * Market Premium
    Cost of Debt = Risk-free + 1.5% (spread corporativo aproximado)
    """
    beta = info.get("beta")
    if beta is None or beta <= 0:
        beta = 1.0  # Default si no hay beta

    # Cost of Equity (CAPM)
    cost_of_equity = RISK_FREE_RATE + beta * MARKET_RISK_PREMIUM

    # Cost of Debt (aproximación)
    cost_of_debt = RISK_FREE_RATE + 0.015  # spread corporativo base

    # Pesos
    market_cap = info.get("market_cap") or 0
    total_debt = get_metric(financials, "balance_sheet", "Total Debt", 0) or 0
    if total_debt == 0:
        total_debt = get_metric(financials, "balance_sheet", "Long Term Debt", 0) or 0

    total_value = market_cap + total_debt
    if total_value == 0:
        return cost_of_equity + wacc_adjustment  # Fallback: solo equity

    weight_equity = market_cap / total_value
    weight_debt = total_debt / total_value

    wacc = (weight_equity * cost_of_equity) + (
        weight_debt * cost_of_debt * (1 - TAX_RATE)
    )

    # Aplicar ajuste de escenario
    wacc += wacc_adjustment

    # WACC razonable entre 6% y 15%
    wacc = max(0.06, min(0.15, wacc))

    logger.debug(f"WACC: {wacc:.4f} (beta={beta}, CoE={cost_of_equity:.4f})")
    return wacc


def get_fcf(financials: Dict[str, Any], year_offset: int = 0) -> Optional[float]:
    """Obtiene FCF de un año específico."""
    ocf = get_metric(financials, "cash_flow", "Operating Cash Flow", year_offset)
    capex = get_metric(financials, "cash_flow", "Capital Expenditure", year_offset)

    if ocf is not None and capex is not None:
        return ocf - abs(capex)
    return None


def project_fcf(
    base_fcf: float,
    historical_growth: Optional[float],
    revenue_growth: Optional[float],
    margin_adjustment: float,
    scenario_growth_adj: float,
    years: int = 5,
) -> list[float]:
    """Proyecta FCF a N años.

    Usa el crecimiento histórico de FCF o revenue growth como base,
    ajustado por el escenario.
    """
    # Determinar tasa de crecimiento base
    if historical_growth is not None and not math.isnan(historical_growth):
        base_growth = historical_growth
    elif revenue_growth is not None and not math.isnan(revenue_growth):
        base_growth = revenue_growth
    else:
        base_growth = 0.08  # Default 8% si no hay datos

    # Ajustar por escenario
    growth_rate = base_growth + scenario_growth_adj

    # Limitar a un rango razonable (-5% a 30%)
    growth_rate = max(-0.05, min(0.30, growth_rate))

    # Aplicar ajuste de margen al FCF base
    adjusted_fcf = base_fcf * (1 + margin_adjustment)

    # Proyectar
    projected = []
    current_fcf = adjusted_fcf
    for _ in range(years):
        current_fcf = current_fcf * (1 + growth_rate)
        projected.append(current_fcf)

    return projected


def calculate_terminal_value(
    final_fcf: float,
    terminal_growth: float,
    wacc: float,
) -> float:
    """Terminal Value con Gordon Growth Model.

    TV = FCF_n * (1 + g) / (WACC - g)
    """
    if wacc <= terminal_growth:
        # Si WACC <= growth, modelo no funciona. Usar WACC + 2% como floor
        wacc = terminal_growth + 0.02

    tv = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    return tv


def discount_to_present(
    cash_flows: list[float],
    wacc: float,
    terminal_value: float,
) -> Tuple[float, float]:
    """Descuenta FCFs y Terminal Value al presente.

    Returns: (pv_fcf_sum, pv_terminal_value)
    """
    pv_fcf_sum = 0.0
    for i, fcf in enumerate(cash_flows, start=1):
        pv = fcf / ((1 + wacc) ** i)
        pv_fcf_sum += pv

    # Terminal value se descuenta desde el último año
    pv_tv = terminal_value / ((1 + wacc) ** len(cash_flows))

    return pv_fcf_sum, pv_tv


def run_dcf(ticker: str) -> Dict[str, Any]:
    """Ejecuta DCF completo con 3 escenarios.

    Returns:
        dict con bear, base, bull (cada uno con price_per_share, wacc,
        growth_rate, terminal_value, y desglose), plus recommendation.
    """
    logger.info(f"Ejecutando DCF para {ticker}...")

    info = get_ticker_info(ticker)
    financials = get_financials(ticker)

    if "error" in info:
        return {"ticker": ticker.upper(), "error": info["error"]}

    # FCF base (año más reciente)
    base_fcf = get_fcf(financials, 0)
    if base_fcf is None:
        # Fallback a info
        base_fcf = info.get("free_cash_flow")

    if base_fcf is None or base_fcf <= 0:
        return {
            "ticker": ticker.upper(),
            "error": "No se pudo obtener FCF. La empresa puede tener FCF negativo.",
            "note": "DCF requiere FCF positivo. Considera valoración por múltiplos.",
        }

    # Datos para proyección
    from app.modules.research.analyzer import calculate_fcf_growth, calculate_revenue_growth

    fcf_growth = calculate_fcf_growth(financials)
    revenue_growth = calculate_revenue_growth(financials, info)

    # Shares outstanding
    shares = info.get("shares_outstanding")
    if shares is None or shares <= 0:
        return {"ticker": ticker.upper(), "error": "No se pudo obtener shares outstanding."}

    # Precio actual para comparar
    current_price = info.get("price", 0)

    results = {}

    for scenario_name, params in SCENARIOS.items():
        # WACC
        wacc = calculate_wacc(info, financials, params["wacc_adjustment"])

        # Proyectar FCF
        projected_fcfs = project_fcf(
            base_fcf=base_fcf,
            historical_growth=fcf_growth,
            revenue_growth=revenue_growth,
            margin_adjustment=params["margin_adjustment"],
            scenario_growth_adj=params["growth_adjustment"],
            years=5,
        )

        # Terminal Value
        final_fcf = projected_fcfs[-1]
        tv = calculate_terminal_value(final_fcf, params["terminal_growth"], wacc)

        # Descontar al presente
        pv_fcf, pv_tv = discount_to_present(projected_fcfs, wacc, tv)

        # Enterprise Value = PV(FCF) + PV(TV)
        ev = pv_fcf + pv_tv

        # Equity Value = EV - Net Debt + Cash
        total_debt = get_metric(financials, "balance_sheet", "Total Debt", 0) or 0
        if total_debt == 0:
            total_debt = get_metric(financials, "balance_sheet", "Long Term Debt", 0) or 0
        total_cash = get_metric(financials, "balance_sheet", "Cash And Cash Equivalents", 0) or 0
        if total_cash == 0:
            total_cash = info.get("total_cash") or 0

        net_debt = total_debt - total_cash
        equity_value = ev - net_debt

        # Precio por acción
        price_per_share = equity_value / shares if shares > 0 else 0

        # Upside/downside vs precio actual
        if current_price and current_price > 0:
            upside = round((price_per_share - current_price) / current_price, 4)
        else:
            upside = None

        results[scenario_name] = {
            "price_per_share": round(price_per_share, 2),
            "wacc": round(wacc, 4),
            "wacc_label": f"{wacc*100:.1f}%",
            "growth_rate": round(params["growth_adjustment"], 4),
            "terminal_growth": params["terminal_growth"],
            "terminal_growth_label": f"{params['terminal_growth']*100:.1f}%",
            "projected_fcfs": [round(f, 0) for f in projected_fcfs],
            "terminal_value": round(tv, 0),
            "pv_fcf": round(pv_fcf, 0),
            "pv_terminal": round(pv_tv, 0),
            "enterprise_value": round(ev, 0),
            "equity_value": round(equity_value, 0),
            "net_debt": round(net_debt, 0),
            "upside_vs_current": upside,
            "upside_label": f"{upside*100:+.1f}%" if upside is not None else "N/A",
        }

    return {
        "ticker": ticker.upper(),
        "current_price": current_price,
        "base_fcf": round(base_fcf, 0),
        "shares_outstanding": shares,
        "fcf_growth_historical": fcf_growth,
        "revenue_growth": revenue_growth,
        "scenarios": results,
        "model_assumptions": {
            "risk_free_rate": RISK_FREE_RATE,
            "market_risk_premium": MARKET_RISK_PREMIUM,
            "tax_rate": TAX_RATE,
            "projection_years": 5,
        },
    }


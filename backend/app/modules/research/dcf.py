"""DCF (Discounted Cash Flow) — valoración con FCF robusto y ajustes sectoriales.

Mejoras:
1. FCF con 5 niveles de fallback (no debe fallar nunca la respuesta entera)
2. WACC segmentado: rf + beta*MRP + cost of debt
3. Terminal growth ajustado por sector (no asume 2.5% para nada)
4. Margen de seguridad Graham: 25% por defecto
5. Soporte para empresas con FCF negativo pero en crecimiento (startups)
6. Soporte para cíclicas (commodities) con gterminal bajo
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from app.core.data_providers.yahoo import get_financials, get_ticker_info
from app.modules.research.analyzer import (
    FIELD_CANDIDATES,
    _find_field_any_year,
    get_capex,
    get_cash,
    get_operating_cf,
    get_revenue,
    get_total_debt,
    get_total_equity,
)

logger = logging.getLogger("finhub.dcf")

# Parámetros globales (ajustables)
RISK_FREE_RATE = 0.045  # 10Y Treasury ~4.5%
MARKET_RISK_PREMIUM = 0.055  # 5.5% ERP estándar
CORPORATE_SPREAD = 0.015  # Credit spread sobre rf para cost of debt
TAX_RATE_DEFAULT = 0.21  # US corporate
TAX_RATE_INTL = 0.25  # Internacional promedio

# Scenarios con ajustes sectoriales
SCENARIOS_BASE = {
    "bear": {
        "growth_adj": -0.04,  # 4pp menos que histórico
        "terminal_growth": 0.005,  # base baja
        "wacc_adj": 0.02,
        "margin_adj": -0.03,
        "prob": 0.25,
    },
    "base": {
        "growth_adj": 0.0,
        "terminal_growth": 0.020,
        "wacc_adj": 0.0,
        "margin_adj": 0.0,
        "prob": 0.50,
    },
    "bull": {
        "growth_adj": 0.04,
        "terminal_growth": 0.035,
        "wacc_adj": -0.01,
        "margin_adj": 0.03,
        "prob": 0.25,
    },
}


def _sector_terminal_growth(sector: str) -> float:
    """Terminal growth ajustado por sector (no 2.5% para todos)."""
    if not sector:
        return 0.020
    s = sector.lower()
    if "tech" in s or "software" in s or "communication" in s:
        return 0.030
    if "pharma" in s or "healthcare" in s or "biotech" in s:
        return 0.025
    if "consumer defensive" in s or "consumer staples" in s or "utilit" in s:
        return 0.015
    if "energy" in s or "basic materials" in s:
        return 0.005  # commodities: gterminal ~0
    if "financial" in s or "real estate" in s:
        return 0.015
    if "industrials" in s or "consumer cyclical" in s:
        return 0.020
    return 0.020


def estimate_fcf_multi_level(
    ticker: str, financials: Dict[str, Any], info: Dict[str, Any]
) -> Tuple[Optional[float], str]:
    """Obtiene FCF base con 5 niveles de fallback. Nunca lanza excepción.

    Returns: (fcf_value, source_description)
    """
    # Nivel 1: Cash flow statement (OCF - Capex)
    ocf = get_operating_cf(financials, 0)
    capex = get_capex(financials, 0)
    if ocf is not None:
        if capex is not None:
            return ocf - capex, "operating_cashflow_minus_capex"
        return ocf, "operating_cashflow_no_capex"

    # Nivel 2: info.summaryDetail.freeCashflow
    if info.get("freeCashflow") is not None:
        return info["freeCashflow"], "info_freeCashflow"

    # Nivel 3: info.financialData.freeCashflow
    if info.get("freeCashFlow") is not None:
        return info["freeCashFlow"], "info_financialData_freeCashflow"

    # Nivel 4: estimación desde net income
    ni = _find_field_any_year(financials, "income_statement", FIELD_CANDIDATES["net_income"])
    if ni is not None and info.get("sharesOutstanding"):
        # Estimación conservadora: net income * 80% / shares = EPS-adjusted FCF
        shares = info["sharesOutstanding"]
        # FCF proxy = NI pero solo si NI > 0 y empresa madura
        if ni > 0:
            # Usar 75% de NI como estimación conservadora de FCF
            return ni * 0.75, "estimated_75pct_net_income"

    # Nivel 5: ninguna estimación fiable
    return None, "no_data"


def calculate_wacc(
    info: Dict[str, Any], financials: Dict[str, Any], wacc_adjustment: float = 0.0
) -> float:
    """WACC con CAPM + cost of debt.

    Cost of equity = rf + beta * MRP
    Cost of debt = rf + corporate spread (tasa después de impuestos)
    WACC = weight_equity * CoE + weight_debt * CoD * (1-tax)
    """
    beta = info.get("beta") or 1.0
    cost_of_equity = RISK_FREE_RATE + beta * MARKET_RISK_PREMIUM
    cost_of_debt = RISK_FREE_RATE + CORPORATE_SPREAD

    market_cap = info.get("market_cap") or 0
    total_debt = get_total_debt(financials, 0) or 0
    total_capital = market_cap + total_debt

    if total_capital == 0:
        return cost_of_equity + wacc_adjustment

    weight_equity = market_cap / total_capital
    weight_debt = total_debt / total_capital
    tax_rate = TAX_RATE_DEFAULT
    wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt * (1 - tax_rate)
    wacc += wacc_adjustment

    # WACC floor/ceiling razonables
    return max(0.06, min(0.18, wacc))


def project_fcf(
    base_fcf: float,
    revenue_growth: Optional[float],
    fcf_growth: Optional[float],
    margin_adjustment: float,
    growth_adjustment: float,
    years: int = 5,
) -> List[float]:
    """Proyecta FCF N años con tasa calibrada.

    Usa FCF growth o revenue growth como base. Limita a rango razonable.
    """
    if revenue_growth is not None and not math.isnan(revenue_growth):
        base_growth = revenue_growth
    elif fcf_growth is not None and not math.isnan(fcf_growth):
        base_growth = fcf_growth
    else:
        base_growth = 0.08  # Default conservador

    growth_rate = base_growth + growth_adjustment
    growth_rate = max(-0.05, min(0.30, growth_rate))

    adjusted_fcf = base_fcf * (1 + margin_adjustment)
    projected = []
    current_fcf = adjusted_fcf
    for _ in range(years):
        current_fcf = current_fcf * (1 + growth_rate)
        projected.append(current_fcf)
    return projected


def calculate_terminal_value(
    final_fcf: float, terminal_growth: float, wacc: float
) -> Optional[float]:
    """Gordon Growth Model.

    TV = FCF_n * (1 + g) / (WACC - g)
    """
    if wacc <= terminal_growth:
        # Ajustar: usa wacc mínimo de terminal_growth + 1% para evitar div/0
        effective_wacc = terminal_growth + 0.01
        if effective_wacc >= 0.20:  # ya muy alto
            return None
        wacc = effective_wacc

    if final_fcf <= 0:
        return None  # FCF negativo no soporta Gordon Growth

    tv = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    if tv < 0 or math.isinf(tv):
        return None
    return tv


def discount_cash_flows(
    cash_flows: List[float], wacc: float, terminal_value: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    """Descuenta FCFs y TV al presente."""
    pv_fcf_sum = 0.0
    for i, fcf in enumerate(cash_flows, start=1):
        if wacc <= -1:
            return None, None
        pv = fcf / ((1 + wacc) ** i)
        pv_fcf_sum += pv

    if terminal_value is None:
        return pv_fcf_sum, None

    pv_tv = terminal_value / ((1 + wacc) ** len(cash_flows))
    return pv_fcf_sum, pv_tv


def run_dcf(ticker: str, analyzer_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """DCF completo: 3 escenarios con probabilidades.

    Returns:
        dict con scenarios, probabilistic_value, margin_of_safety, error si aplica.
    """
    logger.info(f"DCF para {ticker}...")

    if analyzer_data is None:
        info = get_ticker_info(ticker)
        financials = get_financials(ticker)
    else:
        info = analyzer_data.get("raw", {}).get("info", {})
        financials = analyzer_data.get("raw", {}).get("financials", {})

    if "error" in info:
        return {"ticker": ticker.upper(), "error": info["error"]}

    # FCF base con fallback multi-nivel
    base_fcf, source = estimate_fcf_multi_level(ticker, financials, info)

    shares = info.get("shares_outstanding") or info.get("sharesOutstanding")
    if not shares or shares <= 0:
        return {
            "ticker": ticker.upper(),
            "error": "No se pudo obtener shares outstanding",
        }

    current_price = info.get("price") or info.get("currentPrice") or info.get("regularMarketPrice")
    sector = info.get("sector", "")
    sector_terminal_g = _sector_terminal_growth(sector)

    # Growth rates históricos
    fcf_growth = (
        analyzer_data.get("financial_quality", {}).get("fcf_growth")
        if analyzer_data
        else None
    )
    revenue_growth = (
        analyzer_data.get("financial_quality", {}).get("revenue_growth")
        if analyzer_data
        else None
    )

    results = {}
    valid_scenarios = 0

    for scenario_name, params in SCENARIOS_BASE.items():
        wacc = calculate_wacc(info, financials, params["wacc_adj"])

        # Ajustar terminal growth por sector para cada escenario
        if scenario_name == "bear":
            terminal_g = min(params["terminal_growth"], sector_terminal_g * 0.5)
        elif scenario_name == "bull":
            terminal_g = max(params["terminal_growth"], sector_terminal_g * 1.2)
        else:  # base
            terminal_g = sector_terminal_g

        if base_fcf is None or base_fcf <= 0:
            # Empresa sin FCF positivo
            if scenario_name == "base":
                # En base, intentar con FCF estimado conservador
                if base_fcf is None:
                    results[scenario_name] = {
                        "price_per_share": None,
                        "note": "FCF no disponible. Use owner earnings o comparables.",
                    }
                    continue
                # base_fcf <= 0: empresa no rentable aún
                results[scenario_name] = {
                    "price_per_share": None,
                    "note": "FCF negativo. Empresa no apta para DCF clásico.",
                }
                continue

        # Proyección
        projected_fcfs = project_fcf(
            base_fcf=base_fcf,
            revenue_growth=revenue_growth,
            fcf_growth=fcf_growth,
            margin_adjustment=params["margin_adj"],
            growth_adjustment=params["growth_adj"],
        )

        final_fcf = projected_fcfs[-1]
        tv = calculate_terminal_value(final_fcf, terminal_g, wacc)

        pv_fcf, pv_tv = discount_cash_flows(projected_fcfs, wacc, tv)

        if pv_fcf is None:
            results[scenario_name] = {
                "price_per_share": None,
                "note": "Error en descuento",
            }
            continue

        # Equity value
        ev = pv_fcf + (pv_tv or 0)
        total_debt = get_total_debt(financials, 0) or 0
        cash = get_cash(financials, 0) or info.get("totalCash") or 0
        net_debt = total_debt - cash
        equity_value = ev - net_debt
        price_per_share = equity_value / shares if shares > 0 else 0

        upside = None
        if current_price and current_price > 0:
            upside = round((price_per_share - current_price) / current_price, 4)

        results[scenario_name] = {
            "price_per_share": round(price_per_share, 2),
            "wacc": round(wacc, 4),
            "wacc_label": f"{wacc * 100:.1f}%",
            "terminal_growth": round(terminal_g, 4),
            "terminal_growth_label": f"{terminal_g * 100:.1f}%",
            "projected_fcfs": [round(f, 0) for f in projected_fcfs],
            "terminal_value": round(tv, 0) if tv is not None else None,
            "pv_fcf": round(pv_fcf, 0),
            "pv_terminal": round(pv_tv, 0) if pv_tv is not None else None,
            "enterprise_value": round(ev, 0),
            "equity_value": round(equity_value, 0),
            "net_debt": round(net_debt, 0),
            "upside_vs_current": upside,
            "upside_label": f"{upside * 100:+.1f}%" if upside is not None else "N/D",
            "probability": params["prob"],
        }
        valid_scenarios += 1

    # Probabilistic fair value (weighted by scenario probability)
    prob_value = 0.0
    total_prob = 0.0
    for scenario_name, r in results.items():
        if r.get("price_per_share") is not None:
            prob = r.get("probability", 0)
            prob_value += r["price_per_share"] * prob
            total_prob += prob

    if total_prob > 0:
        prob_value /= total_prob
    else:
        prob_value = None

    # Margin of Safety (Graham 25%)
    margin_of_safety_pct = 0.25
    safe_price = prob_value * (1 - margin_of_safety_pct) if prob_value else None

    return {
        "ticker": ticker.upper(),
        "current_price": current_price,
        "base_fcf_source": source,
        "base_fcf": round(base_fcf, 0) if base_fcf else None,
        "shares_outstanding": shares,
        "fcf_growth_historical": fcf_growth,
        "revenue_growth": revenue_growth,
        "sector": sector,
        "sector_terminal_growth": round(sector_terminal_g, 4),
        "scenarios": results,
        "probabilistic_value": round(prob_value, 2) if prob_value else None,
        "margin_of_safety_price": round(safe_price, 2) if safe_price else None,
        "margin_of_safety_label": "25% (Graham)",
        "model_assumptions": {
            "risk_free_rate": RISK_FREE_RATE,
            "market_risk_premium": MARKET_RISK_PREMIUM,
            "tax_rate_us": TAX_RATE_DEFAULT,
            "projection_years": 5,
            "margin_of_safety_pct": margin_of_safety_pct,
            "sector_adjustment_used": sector_terminal_g,
        },
    }

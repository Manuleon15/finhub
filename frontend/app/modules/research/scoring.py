"""Scoring y recomendación BUY/HOLD/SELL.

Algoritmo de 0-100 basado en dos dimensiones:
1. Calidad financiera (0-50 puntos): ROIC, FCF margin, deuda, márgenes, crecimiento
2. Valoración (0-50 puntos): DCF upside, FCF yield, earnings yield, PEG

Resultado:
- Score >= 70 → BUY
- Score 50-69 → HOLD
- Score < 50 → SELL
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("finhub.scoring")


def score_quality(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Puntúa la calidad financiera (0-50).

    Criterios:
    - ROIC > 15% → excelente; > 10% → bueno; > 5% → acceptable
    - FCF Margin > 20% → excelente; > 10% → bueno; > 0% → acceptable
    - Debt/Equity < 0.3 → excelente; < 0.6 → bueno; < 1.0 → acceptable
    - Gross Margin > 50% → excelente; > 30% → bueno; > 0% → acceptable
    - Revenue Growth > 15% → excelente; > 5% → bueno; > 0% → acceptable
    """
    score = 0
    breakdown = {}

    # ROIC (0-12 puntos)
    roic = metrics.get("roic")
    if roic is not None:
        if roic > 0.20:
            score += 12
            breakdown["roic"] = {"points": 12, "max": 12, "label": "Excelente (>20%)"}
        elif roic > 0.15:
            score += 10
            breakdown["roic"] = {"points": 10, "max": 12, "label": "Muy bueno (>15%)"}
        elif roic > 0.10:
            score += 7
            breakdown["roic"] = {"points": 7, "max": 12, "label": "Bueno (>10%)"}
        elif roic > 0.05:
            score += 4
            breakdown["roic"] = {"points": 4, "max": 12, "label": "Acceptable (>5%)"}
        else:
            score += 0
            breakdown["roic"] = {"points": 0, "max": 12, "label": "Pobre (<5%)"}
    else:
        breakdown["roic"] = {"points": 0, "max": 12, "label": "N/A"}

    # FCF Margin (0-10 puntos)
    fcf_margin = metrics.get("fcf_margin")
    if fcf_margin is not None:
        if fcf_margin > 0.20:
            score += 10
            breakdown["fcf_margin"] = {"points": 10, "max": 10, "label": "Excelente (>20%)"}
        elif fcf_margin > 0.10:
            score += 7
            breakdown["fcf_margin"] = {"points": 7, "max": 10, "label": "Bueno (>10%)"}
        elif fcf_margin > 0.05:
            score += 5
            breakdown["fcf_margin"] = {"points": 5, "max": 10, "label": "Acceptable (>5%)"}
        elif fcf_margin > 0:
            score += 2
            breakdown["fcf_margin"] = {"points": 2, "max": 10, "label": "Marginal (>0%)"}
        else:
            breakdown["fcf_margin"] = {"points": 0, "max": 10, "label": "Negativo"}
    else:
        breakdown["fcf_margin"] = {"points": 0, "max": 10, "label": "N/A"}

    # Debt to Equity (0-10 puntos)
    d_e = metrics.get("debt_to_equity")
    if d_e is not None:
        if d_e < 0.3:
            score += 10
            breakdown["debt"] = {"points": 10, "max": 10, "label": "Deuda baja (<0.3)"}
        elif d_e < 0.6:
            score += 7
            breakdown["debt"] = {"points": 7, "max": 10, "label": "Deuda moderada (<0.6)"}
        elif d_e < 1.0:
            score += 4
            breakdown["debt"] = {"points": 4, "max": 10, "label": "Deuda alta (<1.0)"}
        else:
            breakdown["debt"] = {"points": 0, "max": 10, "label": "Deuda muy alta (>1.0)"}
    else:
        breakdown["debt"] = {"points": 0, "max": 10, "label": "N/A"}

    # Gross Margin (0-8 puntos)
    gm = metrics.get("gross_margin")
    if gm is not None:
        if gm > 0.50:
            score += 8
            breakdown["gross_margin"] = {"points": 8, "max": 8, "label": "Excelente (>50%)"}
        elif gm > 0.30:
            score += 5
            breakdown["gross_margin"] = {"points": 5, "max": 8, "label": "Bueno (>30%)"}
        elif gm > 0.15:
            score += 3
            breakdown["gross_margin"] = {"points": 3, "max": 8, "label": "Acceptable (>15%)"}
        else:
            breakdown["gross_margin"] = {"points": 0, "max": 8, "label": "Bajo (<15%)"}
    else:
        breakdown["gross_margin"] = {"points": 0, "max": 8, "label": "N/A"}

    # Revenue Growth (0-10 puntos)
    rg = metrics.get("revenue_growth")
    if rg is not None:
        if rg > 0.15:
            score += 10
            breakdown["revenue_growth"] = {"points": 10, "max": 10, "label": "Excelente (>15%)"}
        elif rg > 0.05:
            score += 7
            breakdown["revenue_growth"] = {"points": 7, "max": 10, "label": "Bueno (>5%)"}
        elif rg > 0:
            score += 4
            breakdown["revenue_growth"] = {"points": 4, "max": 10, "label": "Positivo (>0%)"}
        else:
            breakdown["revenue_growth"] = {"points": 0, "max": 10, "label": "Negativo"}
    else:
        breakdown["revenue_growth"] = {"points": 0, "max": 10, "label": "N/A"}

    return {"score": score, "max": 50, "breakdown": breakdown}


def score_valuation(dcf_data: Dict[str, Any], valuation_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Puntúa la valoración (0-50).

    Criterios:
    - DCF upside (base case): > 30% → muy infravalorada; > 10% → infravalorada
    - FCF Yield: > 5% → bueno; > 3% → acceptable
    - PEG Ratio: < 1 → bueno; < 2 → acceptable
    - Earnings Yield vs Risk-free: > 6% → bueno
    """
    score = 0
    breakdown = {}

    # DCF upside base case (0-20 puntos)
    base_scenario = dcf_data.get("scenarios", {}).get("base", {})
    base_upside = base_scenario.get("upside_vs_current")

    if base_upside is not None:
        if base_upside > 0.30:
            score += 20
            breakdown["dcf_upside"] = {"points": 20, "max": 20, "label": "Muy infravalorada (>30% upside)"}
        elif base_upside > 0.15:
            score += 15
            breakdown["dcf_upside"] = {"points": 15, "max": 20, "label": "Infravalorada (>15% upside)"}
        elif base_upside > 0.05:
            score += 10
            breakdown["dcf_upside"] = {"points": 10, "max": 20, "label": "Ligeramente infravalorada (>5%)"}
        elif base_upside > -0.10:
            score += 5
            breakdown["dcf_upside"] = {"points": 5, "max": 20, "label": "Justamente valorada (±10%)"}
        else:
            breakdown["dcf_upside"] = {"points": 0, "max": 20, "label": "Sobrevalorada (<-10%)"}
    else:
        breakdown["dcf_upside"] = {"points": 0, "max": 20, "label": "N/A"}

    # FCF Yield (0-10 puntos)
    fcf_yield = valuation_metrics.get("fcf_yield")
    if fcf_yield is not None:
        if fcf_yield > 0.05:
            score += 10
            breakdown["fcf_yield"] = {"points": 10, "max": 10, "label": "Excelente (>5%)"}
        elif fcf_yield > 0.03:
            score += 7
            breakdown["fcf_yield"] = {"points": 7, "max": 10, "label": "Bueno (>3%)"}
        elif fcf_yield > 0.01:
            score += 4
            breakdown["fcf_yield"] = {"points": 4, "max": 10, "label": "Acceptable (>1%)"}
        else:
            breakdown["fcf_yield"] = {"points": 0, "max": 10, "label": "Bajo (<1%)"}
    else:
        breakdown["fcf_yield"] = {"points": 0, "max": 10, "label": "N/A"}

    # PEG Ratio (0-10 puntos)
    peg = valuation_metrics.get("peg_ratio")
    if peg is not None and peg > 0:
        if peg < 1.0:
            score += 10
            breakdown["peg"] = {"points": 10, "max": 10, "label": "Excelente (<1.0)"}
        elif peg < 1.5:
            score += 7
            breakdown["peg"] = {"points": 7, "max": 10, "label": "Bueno (<1.5)"}
        elif peg < 2.0:
            score += 4
            breakdown["peg"] = {"points": 4, "max": 10, "label": "Acceptable (<2.0)"}
        else:
            breakdown["peg"] = {"points": 0, "max": 10, "label": "Caro (>2.0)"}
    else:
        breakdown["peg"] = {"points": 0, "max": 10, "label": "N/A"}

    # Earnings Yield (0-10 puntos)
    ey = valuation_metrics.get("earnings_yield")
    if ey is not None:
        if ey > 0.06:
            score += 10
            breakdown["earnings_yield"] = {"points": 10, "max": 10, "label": "Excelente (>6%)"}
        elif ey > 0.04:
            score += 7
            breakdown["earnings_yield"] = {"points": 7, "max": 10, "label": "Bueno (>4%)"}
        elif ey > 0.025:
            score += 4
            breakdown["earnings_yield"] = {"points": 4, "max": 10, "label": "Acceptable (>2.5%)"}
        else:
            breakdown["earnings_yield"] = {"points": 0, "max": 10, "label": "Bajo (<2.5%)"}
    else:
        breakdown["earnings_yield"] = {"points": 0, "max": 10, "label": "N/A"}

    return {"score": score, "max": 50, "breakdown": breakdown}


def get_recommendation(total_score: int) -> Dict[str, str]:
    """Convierte score numérico en recomendación."""
    if total_score >= 70:
        return {
            "action": "BUY",
            "label": "Comprar",
            "color": "green",
            "description": "Calidad financiera sólida y valoración atractiva.",
        }
    elif total_score >= 50:
        return {
            "action": "HOLD",
            "label": "Mantener",
            "color": "yellow",
            "description": "Empresa razonable pero valoración justa. Monitorizar.",
        }
    else:
        return {
            "action": "SELL",
            "label": "Vender / Evitar",
            "color": "red",
            "description": "Calidad cuestionable o sobrevalorada. Caución.",
        }


def calculate_score(
    analyzer_data: Dict[str, Any],
    dcf_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Calcula score completo y recomendación.

    Args:
        analyzer_data: output de analyzer.analyze_company()
        dcf_data: output de dcf.run_dcf()

    Returns:
        dict con quality_score, valuation_score, total_score, recommendation.
    """
    quality_metrics = analyzer_data.get("financial_quality", {})
    valuation_metrics = analyzer_data.get("valuation", {})

    quality = score_quality(quality_metrics)
    valuation = score_valuation(dcf_data, valuation_metrics)

    total = quality["score"] + valuation["score"]
    recommendation = get_recommendation(total)

    return {
        "quality_score": quality,
        "valuation_score": valuation,
        "total_score": total,
        "max_score": 100,
        "recommendation": recommendation,
    }


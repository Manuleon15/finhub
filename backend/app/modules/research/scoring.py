"""Scoring modular con modelos combinables tipo InvestingPro.

El usuario activa/desactiva modelos y asigna pesos custom.
Por defecto: combinador de ponderación de los 5 modelos de value investing + DCF.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("finhub.scoring")

# Verdicts ordenados (peor → mejor)
VERDICT_RANK = {
    "STRONG_SELL": 1,
    "SELL": 2,
    "HOLD": 3,
    "BUY": 4,
    "STRONG_BUY": 5,
}

# Score thresholds (0-100) para verdict final global
THRESHOLDS = {
    "STRONG_BUY": 80,
    "BUY": 65,
    "HOLD": 50,
    "SELL": 35,
    "STRONG_SELL": 0,
}

ACTION_TO_COLOR = {
    "STRONG_BUY": "green",
    "BUY": "green",
    "HOLD": "yellow",
    "SELL": "red",
    "STRONG_SELL": "red",
}

ACTION_TO_LABEL = {
    "STRONG_BUY": "Compra fuerte",
    "BUY": "Comprar",
    "HOLD": "Mantener",
    "SELL": "Vender",
    "STRONG_SELL": "Vender / Evitar",
}


def build_quality_score_breakdown(
    roic: Optional[float],
    fcf_margin: Optional[float],
    debt_to_equity: Optional[float],
    gross_margin: Optional[float],
    revenue_growth: Optional[float],
) -> Dict[str, Any]:
    """Sub-score de calidad financiera pura (sin DCF).

    Peso total: 0-30 puntos. Se suma al score de modelos para el cálculo total.
    """
    breakdown = {}

    # ROIC (0-8)
    if roic is not None:
        if roic > 0.20:
            pts = 8
            label = "Excelente (>20%)"
        elif roic > 0.15:
            pts = 6
            label = "Muy bueno (>15%)"
        elif roic > 0.10:
            pts = 4
            label = "Bueno (>10%)"
        elif roic > 0.05:
            pts = 2
            label = "Acceptable (>5%)"
        else:
            pts = 0
            label = "Bajo (<5%)"
        breakdown["roic"] = {"points": pts, "max": 8, "label": label}
    else:
        breakdown["roic"] = {"points": 0, "max": 8, "label": "N/D"}

    # FCF Margin (0-7)
    if fcf_margin is not None:
        if fcf_margin > 0.20:
            pts = 7
            label = "Excelente (>20%)"
        elif fcf_margin > 0.10:
            pts = 5
            label = "Bueno (>10%)"
        elif fcf_margin > 0.05:
            pts = 3
            label = "Acceptable (>5%)"
        elif fcf_margin > 0:
            pts = 1
            label = "Marginal (>0%)"
        else:
            pts = 0
            label = "Negativo"
        breakdown["fcf_margin"] = {"points": pts, "max": 7, "label": label}
    else:
        breakdown["fcf_margin"] = {"points": 0, "max": 7, "label": "N/D"}

    # Debt to Equity (0-5)
    if debt_to_equity is not None:
        if debt_to_equity < 0.3:
            pts = 5
            label = "Deuda baja (<0.3)"
        elif debt_to_equity < 0.6:
            pts = 3
            label = "Deuda moderada (<0.6)"
        elif debt_to_equity < 1.0:
            pts = 1
            label = "Deuda alta (<1.0)"
        else:
            pts = 0
            label = "Deuda muy alta (>1.0)"
        breakdown["debt"] = {"points": pts, "max": 5, "label": label}
    else:
        breakdown["debt"] = {"points": 0, "max": 5, "label": "N/D"}

    # Gross Margin (0-5)
    if gross_margin is not None:
        if gross_margin > 0.50:
            pts = 5
            label = "Excelente (>50%)"
        elif gross_margin > 0.30:
            pts = 3
            label = "Bueno (>30%)"
        elif gross_margin > 0.15:
            pts = 1
            label = "Acceptable (>15%)"
        else:
            pts = 0
            label = "Bajo (<15%)"
        breakdown["gross_margin"] = {"points": pts, "max": 5, "label": label}
    else:
        breakdown["gross_margin"] = {"points": 0, "max": 5, "label": "N/D"}

    # Revenue growth (0-5)
    if revenue_growth is not None:
        if revenue_growth > 0.15:
            pts = 5
            label = "Excelente (>15%)"
        elif revenue_growth > 0.05:
            pts = 3
            label = "Bueno (>5%)"
        elif revenue_growth > 0:
            pts = 1
            label = "Positivo (>0%)"
        else:
            pts = 0
            label = "Negativo"
        breakdown["revenue_growth"] = {"points": pts, "max": 5, "label": label}
    else:
        breakdown["revenue_growth"] = {"points": 0, "max": 5, "label": "N/D"}

    total = sum(v["points"] for v in breakdown.values())
    return {"score": total, "max": 30, "breakdown": breakdown}


def compute_final_verdict(composite_score: float) -> Dict[str, Any]:
    """Convierte score 0-100 en verdict final."""
    if composite_score >= THRESHOLDS["STRONG_BUY"]:
        action = "STRONG_BUY"
    elif composite_score >= THRESHOLDS["BUY"]:
        action = "BUY"
    elif composite_score >= THRESHOLDS["HOLD"]:
        action = "HOLD"
    elif composite_score >= THRESHOLDS["SELL"]:
        action = "SELL"
    else:
        action = "STRONG_SELL"

    return {
        "action": action,
        "label": ACTION_TO_LABEL[action],
        "color": ACTION_TO_COLOR[action],
        "verdict": action,
    }


def compute_composite_score(
    quality_breakdown: Dict[str, Any],
    valuation_models_result: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Score final = quality_score + weighted valuation_models_score.

    Quality aporta 0-30 puntos.
    Valuation_models aportan 0-70 puntos (escala basada en verdicts).
    """
    quality_total = quality_breakdown["score"] / quality_breakdown["max"]  # 0-1

    # Si hay modelos de valoración, calculamos su score ponderado a escala 0-1
    if valuation_models_result and valuation_models_result.get("models"):
        models = valuation_models_result["models"]
        used_weights = (
            weights if weights else valuation_models_result.get("weights", {})
        )
        # Si no hay pesos custom, usar los del combiner (que ya normalizó)
        if not used_weights:
            # Fallback igual al combiner: 6 modelos reparten 1.0
            n = len(models)
            used_weights = {m: 1.0 / n for m in models} if n > 0 else {}

        weighted_verdict_score = 0.0
        for model_name, r in models.items():
            verdict = r.get("verdict", "HOLD")
            rank = VERDICT_RANK.get(verdict, 3)
            # 1-5 → 0-1
            normalized = (rank - 1) / 4
            weighted_verdict_score += normalized * used_weights.get(model_name, 0)

        composite = (
            quality_total * 30 + weighted_verdict_score * 70
        ) * (1.0)  # max 100
    else:
        # Solo quality: multiplicar a 100
        composite = quality_total * 100
        weighted_verdict_score = 0

    composite = round(min(100, max(0, composite)), 1)
    verdict = compute_final_verdict(composite)

    return {
        "composite_score": composite,
        "quality_contribution": round(quality_total * 30, 1),
        "valuation_contribution": round(weighted_verdict_score * 70, 1),
        "verdict": verdict,
    }


def build_score_from_analyzer_and_models(
    analyzer_data: Dict[str, Any],
    valuation_models_result: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Score completo para mostrar en el dashboard.

    Devuelve un dict con score final, breakdown de quality, modelos verdict,
    y verdict global final con explicación.
    """
    fq = analyzer_data.get("financial_quality", {})

    quality_breakdown = build_quality_score_breakdown(
        roic=fq.get("roic"),
        fcf_margin=fq.get("fcf_margin"),
        debt_to_equity=fq.get("debt_to_equity"),
        gross_margin=fq.get("gross_margin"),
        revenue_growth=fq.get("revenue_growth"),
    )

    composite = compute_composite_score(
        quality_breakdown=quality_breakdown,
        valuation_models_result=valuation_models_result,
        weights=weights,
    )

    buy_signals = 0
    sell_signals = 0
    if valuation_models_result and valuation_models_result.get("models"):
        for m, r in valuation_models_result["models"].items():
            v = r.get("verdict", "HOLD")
            if v in ("BUY", "STRONG_BUY"):
                buy_signals += 1
            elif v in ("SELL", "STRONG_SELL"):
                sell_signals += 1

    models_summary = []
    if valuation_models_result and valuation_models_result.get("models"):
        for name, r in valuation_models_result["models"].items():
            models_summary.append(
                {"model": name, "verdict": r.get("verdict"), "weight": r.get("weight", 0)}
            )

    explanation_parts = [
        f"Score combinado: {composite['composite_score']:.0f}/100.",
        f"Quality: {quality_breakdown['score']}/{quality_breakdown['max']} pts.",
    ]
    if valuation_models_result and valuation_models_result.get("models"):
        explanation_parts.append(
            f"Modelos: {len(valuation_models_result['models'])} activos, "
            f"{buy_signals} BUY, {sell_signals} SELL."
        )

    return {
        "quality_score": quality_breakdown,
        "valuation_models": (
            valuation_models_result.get("models", {}) if valuation_models_result else {}
        ),
        "composite": composite,
        "recommendation": {
            **composite["verdict"],
            "score": composite["composite_score"],
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "explanation": " ".join(explanation_parts),
        },
        "models_summary": models_summary,
    }

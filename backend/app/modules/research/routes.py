"""Routes del Equity Research Terminal con modelos combinables."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.data_providers.yahoo import get_financials, get_ticker_info
from app.modules.research.analyzer import analyze_company
from app.modules.research.dcf import run_dcf
from app.modules.research.scoring import build_score_from_analyzer_and_models
from app.modules.research.valuation_models import run_all_valuation_models

logger = logging.getLogger("finhub.research.routes")

router = APIRouter()

# Lista de modelos disponibles para el combiner
AVAILABLE_MODELS = [
    "dcf",
    "graham",
    "magic_formula",
    "piotroski",
    "altman_z",
    "owner_earnings",
]


def clean_ticker(raw: str) -> str:
    """Limpia input: MSFT$ → MSFT, ' msft\n' → MSFT.

    - Quita $, %, espacios
    - Mayúsculas
    - Valida que solo tenga letras (o . para BRK.B)
    """
    t = raw.strip().upper()
    t = t.replace("$", "").replace("%", "").replace(" ", "")
    if not re.match(r"^[A-Z]{1,6}(\.[A-Z])?$", t):
        # Permitir cualquier formato alphanumérico razonable
        if not re.match(r"^[A-Z0-9.\-]{1,10}$", t):
            raise ValueError(f"Ticker inválido: {raw}")
    return t


@router.get("/analyze")
def analyze(
    ticker: str = Query(..., description="Ticker a analizar, ej. MSFT"),
    models: Optional[str] = Query(
        None,
        description="Modelos separados por coma. Si no, todos. Ej: dcf,graham,piotroski",
    ),
):
    """Análisis completo con modelos de value investing combinables.

    Query params:
      - ticker: símbolo (MSFT, AAPL, NVO, etc.)
      - models: lista CSV de modelos a usar. Default todos.
    """
    try:
        clean_t = clean_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"Análisis solicitado para {clean_t}, modelos={models or 'todos'}")

    # 1) Analyzer con fallbacks robustos
    try:
        analyzer_data = analyze_company(clean_t)
        if "error" in analyzer_data:
            raise HTTPException(
                status_code=404, detail=f"Error: {analyzer_data['error']}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Analyzer error para {clean_t}")
        raise HTTPException(
            status_code=503,
            detail=f"No se pudieron obtener datos de {clean_t}: {str(e)[:200]}",
        )

    # 2) DCF con FCF robusto
    try:
        dcf_data = run_dcf(clean_t, analyzer_data=analyzer_data)
        if "error" in dcf_data:
            dcf_data = {
                "ticker": clean_t,
                "error": dcf_data["error"],
                "scenarios": {},
            }
    except Exception as e:
        logger.exception(f"DCF error para {clean_t}")
        dcf_data = {"ticker": clean_t, "error": str(e)[:200], "scenarios": {}}

    # 3) Modelos de value investing
    enabled_models = None
    if models:
        requested = [m.strip() for m in models.split(",") if m.strip()]
        invalid = [m for m in requested if m not in AVAILABLE_MODELS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Modelos inválidos: {invalid}. Válidos: {AVAILABLE_MODELS}",
            )
        enabled_models = requested

    try:
        valuation_result = run_all_valuation_models(
            ticker=clean_t,
            analyzer_data=analyzer_data,
            dcf_data=dcf_data,
            enabled_models=enabled_models,
        )
    except Exception as e:
        logger.exception(f"Valuation models error para {clean_t}")
        valuation_result = {"models": {}, "composite_verdict": {}}

    # 4) Scoring modular
    try:
        scoring = build_score_from_analyzer_and_models(
            analyzer_data=analyzer_data,
            valuation_models_result=valuation_result,
        )
    except Exception as e:
        logger.exception(f"Scoring error para {clean_t}")
        scoring = {
            "recommendation": {
                "action": "HOLD",
                "label": "Datos insuficientes",
                "color": "yellow",
                "score": 0,
                "explanation": f"Error: {str(e)[:200]}",
            }
        }

    return {
        "ticker": clean_t,
        "enabled_models": list(valuation_result.get("models", {}).keys()) if valuation_result.get("models") else enabled_models or AVAILABLE_MODELS,
        "available_models": AVAILABLE_MODELS,
        "business_overview": analyzer_data["business_overview"],
        "financial_quality": analyzer_data["financial_quality"],
        "valuation": analyzer_data["valuation"],
        "dcf": dcf_data,
        "valuation_models": valuation_result.get("models", {}),
        "valuation_weights": valuation_result.get("weights", {}),
        "composite_verdict": valuation_result.get("composite_verdict", {}),
        "scoring": scoring,
    }


@router.get("/quick")
def quick_analysis(ticker: str = Query(..., description="Ticker, ej. MSFT")):
    """Análisis rápido solo con métricas clave."""
    try:
        clean_t = clean_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        analyzer_data = analyze_company(clean_t)
        if "error" in analyzer_data:
            raise HTTPException(
                status_code=404, detail=f"Error: {analyzer_data['error']}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Quick error para {clean_t}")
        raise HTTPException(status_code=503, detail=str(e)[:200])

    fq = analyzer_data["financial_quality"]
    val = analyzer_data["valuation"]
    return {
        "ticker": clean_t,
        "name": analyzer_data["business_overview"]["name"],
        "price": analyzer_data["business_overview"].get("price"),
        "sector": analyzer_data["business_overview"].get("sector"),
        "industry": analyzer_data["business_overview"].get("industry"),
        "country": analyzer_data["business_overview"].get("country"),
        "market_cap": analyzer_data["business_overview"].get("market_cap"),
        "roic": fq.get("roic_label"),
        "fcf_margin": fq.get("fcf_margin_label"),
        "gross_margin": fq.get("gross_margin_label"),
        "operating_margin": fq.get("operating_margin_label"),
        "net_margin": fq.get("net_margin_label"),
        "debt": fq.get("debt_label"),
        "debt_to_equity": fq.get("debt_to_equity"),
        "current_ratio": fq.get("current_ratio"),
        "revenue_growth": fq.get("revenue_growth_label"),
        "fcf_growth": fq.get("fcf_growth_label"),
        "earnings_growth": fq.get("earnings_growth_label"),
        "beta": fq.get("beta"),
        "eps": val.get("eps"),
        "bvps": val.get("book_value_per_share"),
        "pe_ratio": val.get("pe_ratio"),
        "pb_ratio": val.get("pb_ratio"),
        "peg_ratio": val.get("peg_ratio"),
        "ev_to_revenue": val.get("ev_to_revenue"),
        "ev_to_ebitda": val.get("ev_to_ebitda"),
        "fcf_yield": val.get("fcf_yield_label"),
        "earnings_yield": val.get("earnings_yield_label"),
        "dividend_yield": val.get("dividend_yield"),
        "target_price": val.get("target_mean_price"),
        "analyst_recommendation": val.get("analyst_recommendation"),
    }


@router.get("/models")
def list_models():
    """Lista los modelos de value investing disponibles."""
    return {
        "models": [
            {
                "id": "dcf",
                "name": "DCF (Discounted Cash Flow)",
                "description": "Valor intrínseco descontando FCFs futuros. Ajustado por sector.",
                "default_weight": 0.20,
            },
            {
                "id": "graham",
                "name": "Graham Number",
                "description": "sqrt(22.5 × EPS × BVPS). Precio máximo Graham-style.",
                "default_weight": 0.15,
            },
            {
                "id": "magic_formula",
                "name": "Magic Formula (Greenblatt)",
                "description": "Combina earnings yield alto + ROIC alto.",
                "default_weight": 0.20,
            },
            {
                "id": "piotroski",
                "name": "Piotroski F-Score",
                "description": "9 criterios de fortaleza financiera. 0-9.",
                "default_weight": 0.15,
            },
            {
                "id": "altman_z",
                "name": "Altman Z-Score",
                "description": "Predice bancarrota en 2 años. Z>2.99 seguro.",
                "default_weight": 0.10,
            },
            {
                "id": "owner_earnings",
                "name": "Owner Earnings (Buffett)",
                "description": "OCF - capex. Dinero que el dueño podría llevarse.",
                "default_weight": 0.20,
            },
        ]
    }

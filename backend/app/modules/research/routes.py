"""Routes del Equity Research Terminal."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.modules.research.analyzer import analyze_company
from app.modules.research.dcf import run_dcf
from app.modules.research.scoring import calculate_score

logger = logging.getLogger("finhub.research.routes")

router = APIRouter()


@router.get("/analyze")
def analyze(ticker: str = Query(..., description="Ticker a analizar, ej. MSFT")):
    """Análisis completo de una empresa.

    Devuelve:
    - business_overview: nombre, sector, descripción, market cap
    - financial_quality: ROIC, FCF margin, debt, márgenes, crecimiento
    - valuation: PE, PB, EV/Revenue, PEG, earnings yield, FCF yield
    - dcf: bear/base/bull con precio intrínseco y upside
    - scoring: score 0-100 + recomendación BUY/HOLD/SELL
    """
    ticker = ticker.upper().strip()
    logger.info(f"Análisis solicitado para {ticker}")

    # 1. Análisis de calidad
    try:
        analyzer_data = analyze_company(ticker)
        if "error" in analyzer_data:
            raise HTTPException(
                status_code=404,
                detail=f"Error analizando {ticker}: {analyzer_data['error']}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error inesperado en analyzer para {ticker}")
        raise HTTPException(
            status_code=503,
            detail=f"No se pudieron obtener datos de {ticker} desde Yahoo Finance. "
                   f"Esto puede ser rate limiting o un problema temporal. Intenta en unos minutos. "
                   f"Detalle técnico: {str(e)[:200]}",
        )

    # 2. DCF
    try:
        dcf_data = run_dcf(ticker)
        if "error" in dcf_data:
            logger.warning(f"DCF no disponible para {ticker}: {dcf_data.get('error')}")
            dcf_data = {
                "ticker": ticker,
                "error": dcf_data.get("error", "DCF no disponible"),
                "scenarios": {},
            }
    except Exception as e:
        logger.exception(f"Error en DCF para {ticker}")
        dcf_data = {
            "ticker": ticker,
            "error": f"DCF no pudo calcularse: {str(e)[:200]}",
            "scenarios": {},
        }

    # 3. Scoring
    try:
        scoring = calculate_score(analyzer_data, dcf_data)
    except Exception as e:
        logger.exception(f"Error en scoring para {ticker}")
        scoring = {
            "total_score": 0,
            "max_score": 100,
            "recommendation": {
                "action": "HOLD",
                "label": "Datos insuficientes",
                "color": "yellow",
                "description": "No se pudo calcular el scoring. Verifica la conexión.",
            },
        }

    return {
        "ticker": ticker,
        "business_overview": analyzer_data["business_overview"],
        "financial_quality": analyzer_data["financial_quality"],
        "valuation": analyzer_data["valuation"],
        "dcf": dcf_data,
        "scoring": scoring,
    }


@router.get("/quick")
def quick_analysis(ticker: str = Query(..., description="Ticker, ej. MSFT")):
    """Análisis rápido — solo métricas clave, sin DCF."""
    ticker = ticker.upper().strip()

    try:
        analyzer_data = analyze_company(ticker)
        if "error" in analyzer_data:
            raise HTTPException(
                status_code=404,
                detail=f"Error: {analyzer_data['error']}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error inesperado en quick para {ticker}")
        raise HTTPException(
            status_code=503,
            detail=f"No se pudieron obtener datos de {ticker} desde Yahoo Finance. "
                   f"Posible rate limiting. Intenta en unos minutos. "
                   f"Detalle: {str(e)[:200]}",
        )

    fq = analyzer_data["financial_quality"]
    val = analyzer_data["valuation"]

    return {
        "ticker": ticker,
        "name": analyzer_data["business_overview"]["name"],
        "price": analyzer_data["business_overview"].get("price"),
        "sector": analyzer_data["business_overview"].get("sector"),
        "roic": fq.get("roic_label"),
        "fcf_margin": fq.get("fcf_margin_label"),
        "debt": fq.get("debt_label"),
        "gross_margin": fq.get("gross_margin_label"),
        "revenue_growth": fq.get("revenue_growth_label"),
        "pe_ratio": val.get("pe_ratio"),
        "peg_ratio": val.get("peg_ratio"),
        "fcf_yield": val.get("fcf_yield"),
        "dividend_yield": val.get("dividend_yield"),
        "target_price": val.get("target_mean_price"),
        "analyst_recommendation": val.get("analyst_recommendation"),
    }

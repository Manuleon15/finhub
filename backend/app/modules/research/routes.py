"""Routes del Equity Research Terminal."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.modules.research.analyzer import analyze_company
from app.modules.research.dcf import run_dcf
from app.modules.research.scoring import calculate_score

logger = logging.getLogger("finhub.research.routes")

router = APIRouter()


@router.get("/analyze")
def analyze(ticker: str = Query(..., description="Ticker a analizar, ej. MSFT")) -> Dict[str, Any]:
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
    analyzer_data = analyze_company(ticker)
    if "error" in analyzer_data:
        raise HTTPException(status_code=404, detail=f"Error analizando {ticker}: {analyzer_data['error']}")

    # 2. DCF
    dcf_data = run_dcf(ticker)
    if "error" in dcf_data:
        # Si DCF falla (FCF negativo, etc.), continuar sin él
        logger.warning(f"DCF no disponible para {ticker}: {dcf_data.get('error')}")
        dcf_data = {
            "ticker": ticker,
            "error": dcf_data.get("error", "DCF no disponible"),
            "scenarios": {},
        }

    # 3. Scoring
    scoring = calculate_score(analyzer_data, dcf_data)

    return {
        "ticker": ticker,
        "business_overview": analyzer_data["business_overview"],
        "financial_quality": analyzer_data["financial_quality"],
        "valuation": analyzer_data["valuation"],
        "dcf": dcf_data,
        "scoring": scoring,
    }


@router.get("/quick")
def quick_analysis(ticker: str = Query(..., description="Ticker, ej. MSFT")) -> Dict[str, Any]:
    """Análisis rápido — solo métricas clave, sin DCF. Más rápido."""
    ticker = ticker.upper().strip()

    analyzer_data = analyze_company(ticker)
    if "error" in analyzer_data:
        raise HTTPException(status_code=404, detail=f"Error: {analyzer_data['error']}")

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


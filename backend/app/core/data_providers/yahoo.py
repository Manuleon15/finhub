"""Wrapper de yfinance con manejo robusto de errores.

Proporciona una interfaz limpia para obtener datos financieros
de Yahoo Finance. Todos los calls se cachean para evitar rate limiting.
Maneja fallos de yfinance devolviendo dicts con 'error' en lugar de explotar.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

import yfinance as yf

logger = logging.getLogger("finhub.yahoo")

# Cache simple en memoria: {key: (timestamp, value)}
_cache: Dict[str, tuple[float, Any]] = {}
CACHE_TTL = 900  # 15 minutos


def _get_cached(key: str) -> Optional[Any]:
    """Obtiene valor del cache si no ha expirado."""
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < CACHE_TTL:
            logger.debug(f"Cache hit: {key}")
            return val
        else:
            del _cache[key]
    return None


def _set_cached(key: str, value: Any) -> None:
    """Guarda valor en cache."""
    _cache[key] = (time.time(), value)


def clear_cache() -> None:
    """Limpia todo el cache."""
    _cache.clear()


def _safe_yfinance_call(callable_fn, ticker: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta una llamada a yfinance capturando TODOS los errores.

    Devuelve un dict con 'error' si algo falla, o el resultado si funciona.
    """
    try:
        result = callable_fn()
        if result is None or (isinstance(result, dict) and not result):
            return {"ticker": ticker.upper(), "error": "Yahoo devolvió respuesta vacía"}
        return result
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error para {ticker}: {e}")
        return {"ticker": ticker.upper(), "error": "Yahoo devolvió JSON inválido (rate limit?)"}
    except Exception as e:
        err_msg = str(e)[:200]
        logger.error(f"Error en yfinance para {ticker}: {type(e).__name__}: {err_msg}")
        return {"ticker": ticker.upper(), "error": f"{type(e).__name__}: {err_msg}"}


def get_ticker_info(ticker: str) -> Dict[str, Any]:
    """Obtiene info general de un ticker."""
    cache_key = f"info_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    def fetch():
        t = yf.Ticker(ticker)
        # Forzar descarga que puede fallar silenciosamente
        info = t.info
        if not info or len(info) < 5:
            raise ValueError("Yahoo devolvió info vacía o demasiado pequeña")

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency", "USD"),
            "description": info.get("longBusinessSummary", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country", ""),
            "total_revenue": info.get("totalRevenue"),
            "gross_profits": info.get("grossProfits"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "peg_ratio": info.get("pegRatio"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "target_mean_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        }

    result = _safe_yfinance_call(fetch, ticker, {})
    if "error" not in result:
        _set_cached(cache_key, result)
    return result


def get_financials(ticker: str) -> Dict[str, Any]:
    """Obtiene estados financieros anuales."""
    cache_key = f"financials_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    def fetch():
        t = yf.Ticker(ticker)
        income = t.financials
        balance = t.balance_sheet
        cashflow = t.cashflow

        def df_to_dict(df):
            if df is None or df.empty:
                return {}
            result = {}
            for col in df.columns:
                year_str = str(col.year) if hasattr(col, "year") else str(col)
                result[year_str] = {}
                for idx in df.index:
                    val = df.loc[idx, col]
                    try:
                        if hasattr(val, "item"):
                            val = val.item()
                        elif isinstance(val, float) and val != val:  # NaN
                            val = None
                    except Exception:
                        val = None
                    result[year_str][str(idx)] = val
            return result

        return {
            "ticker": ticker.upper(),
            "income_statement": df_to_dict(income),
            "balance_sheet": df_to_dict(balance),
            "cash_flow": df_to_dict(cashflow),
        }

    result = _safe_yfinance_call(fetch, ticker, {})
    if "error" not in result and result.get("income_statement"):
        _set_cached(cache_key, result)
    return result


def get_price_history(ticker: str, period: str = "1y") -> Dict[str, Any]:
    """Obtiene historial de precios."""
    cache_key = f"price_{ticker}_{period}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    def fetch():
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return {"ticker": ticker.upper(), "dates": [], "prices": []}

        return {
            "ticker": ticker.upper(),
            "dates": [str(d.date()) for d in hist.index],
            "open": [round(float(v), 2) for v in hist["Open"]],
            "high": [round(float(v), 2) for v in hist["High"]],
            "low": [round(float(v), 2) for v in hist["Low"]],
            "close": [round(float(v), 2) for v in hist["Close"]],
            "volume": [int(v) for v in hist["Volume"]],
        }

    result = _safe_yfinance_call(fetch, ticker, {})
    if "error" not in result and result.get("dates"):
        _set_cached(cache_key, result)
    return result

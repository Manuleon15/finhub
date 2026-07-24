"""Wrapper de yfinance con cache TTL.

Proporciona una interfaz limpia para obtener datos financieros
de Yahoo Finance. Todos los calls se cachean para evitar rate limiting.
"""

from __future__ import annotations

import time
import logging
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


def get_ticker_info(ticker: str) -> Dict[str, Any]:
    """Obtiene info general de un ticker.

    Returns dict con: name, sector, industry, market_cap, pe_ratio,
    pb_ratio, dividend_yield, beta, price, currency, description.
    """
    cache_key = f"info_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info

        result = {
            "ticker": ticker.upper(),
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", None),
            "enterprise_value": info.get("enterpriseValue", None),
            "pe_ratio": info.get("trailingPE", None),
            "forward_pe": info.get("forwardPE", None),
            "pb_ratio": info.get("priceToBook", None),
            "dividend_yield": info.get("dividendYield", None),
            "beta": info.get("beta", None),
            "price": info.get("currentPrice", info.get("regularMarketPrice", None)),
            "currency": info.get("currency", "USD"),
            "description": info.get("longBusinessSummary", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees", None),
            "country": info.get("country", ""),
            # Datos financieros clave
            "total_revenue": info.get("totalRevenue", None),
            "gross_profits": info.get("grossProfits", None),
            "gross_margins": info.get("grossMargins", None),
            "operating_margins": info.get("operatingMargins", None),
            "profit_margins": info.get("profitMargins", None),
            "return_on_equity": info.get("returnOnEquity", None),
            "return_on_assets": info.get("returnOnAssets", None),
            "debt_to_equity": info.get("debtToEquity", None),
            "current_ratio": info.get("currentRatio", None),
            "quick_ratio": info.get("quickRatio", None),
            "total_cash": info.get("totalCash", None),
            "total_debt": info.get("totalDebt", None),
            "free_cash_flow": info.get("freeCashflow", None),
            "operating_cash_flow": info.get("operatingCashflow", None),
            "revenue_growth": info.get("revenueGrowth", None),
            "earnings_growth": info.get("earningsGrowth", None),
            "peg_ratio": info.get("pegRatio", None),
            "ev_to_revenue": info.get("enterpriseToRevenue", None),
            "ev_to_ebitda": info.get("enterpriseToEbitda", None),
            "shares_outstanding": info.get("sharesOutstanding", None),
            "target_mean_price": info.get("targetMeanPrice", None),
            "recommendation": info.get("recommendationKey", None),
        }

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error obteniendo info de {ticker}: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}


def get_financials(ticker: str) -> Dict[str, Any]:
    """Obtiene estados financieros anuales (income, balance, cashflow).

    Returns dict con los últimos 4 años de:
    - income_statement (revenue, gross profit, net income, EBIT, etc.)
    - balance_sheet (total assets, liabilities, equity, debt, cash)
    - cash_flow (operating CF, capex, FCF)
    """
    cache_key = f"financials_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        t = yf.Ticker(ticker)

        # Income statement
        income = t.financials
        balance = t.balance_sheet
        cashflow = t.cashflow

        def df_to_dict(df) -> Dict[str, Any]:
            """Convierte un DataFrame de yfinance a dict."""
            if df is None or df.empty:
                return {}
            result = {}
            for col in df.columns:
                year_str = str(col.year) if hasattr(col, "year") else str(col)
                result[year_str] = {}
                for idx in df.index:
                    val = df.loc[idx, col]
                    # Convertir numpy types a Python nativos
                    try:
                        if hasattr(val, "item"):
                            val = val.item()
                        elif isinstance(val, float):
                            if val != val:  # NaN check
                                val = None
                    except Exception:
                        val = None
                    result[year_str][str(idx)] = val
            return result

        result = {
            "ticker": ticker.upper(),
            "income_statement": df_to_dict(income),
            "balance_sheet": df_to_dict(balance),
            "cash_flow": df_to_dict(cashflow),
        }

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error obteniendo financials de {ticker}: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}


def get_price_history(ticker: str, period: str = "1y") -> Dict[str, Any]:
    """Obtiene historial de precios.

    Args:
        ticker: símbolo bursátil
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

    Returns dict con listas de dates, open, high, low, close, volume.
    """
    cache_key = f"price_{ticker}_{period}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)

        if hist.empty:
            return {"ticker": ticker.upper(), "dates": [], "prices": []}

        result = {
            "ticker": ticker.upper(),
            "dates": [str(d.date()) for d in hist.index],
            "open": [round(float(v), 2) for v in hist["Open"]],
            "high": [round(float(v), 2) for v in hist["High"]],
            "low": [round(float(v), 2) for v in hist["Low"]],
            "close": [round(float(v), 2) for v in hist["Close"]],
            "volume": [int(v) for v in hist["Volume"]],
        }

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error obteniendo prices de {ticker}: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}


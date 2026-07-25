"""Wrapper de yfinance/yahooquery con manejo robusto de errores.

Usa yfinance como principal con fallback a yahooquery.
Maneja TODOS los errores devolviendo dicts con 'error' en lugar de explotar.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("finhub.yahoo")

# Cache simple en memoria: {key: (timestamp, value)}
_cache: Dict[str, tuple[float, Any]] = {}
CACHE_TTL = 900  # 15 minutos


def _get_cached(key: str) -> Optional[Any]:
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
        else:
            del _cache[key]
    return None


def _set_cached(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def clear_cache() -> None:
    _cache.clear()


def _try_yahooquery(ticker: str) -> Optional[Dict[str, Any]]:
    """Intenta con yahooquery. Retorna None si falla."""
    try:
        from yahooquery import Ticker as YQTicker

        t = YQTicker(ticker)
        summary = t.summary_detail
        profile = t.asset_profile
        financials = t.financial_data

        s = summary.get(ticker, {}) or {}
        p = profile.get(ticker, {}) or {}
        f = financials.get(ticker, {}) or {}

        return {
            "ticker": ticker.upper(),
            "name": p.get("longName") or s.get("shortName") or ticker,
            "sector": p.get("sector", "N/A"),
            "industry": p.get("industry", "N/A"),
            "market_cap": s.get("marketCap"),
            "enterprise_value": f.get("enterpriseValue"),
            "pe_ratio": s.get("trailingPE"),
            "forward_pe": s.get("forwardPE"),
            "pb_ratio": s.get("priceToBook"),
            "dividend_yield": s.get("dividendYield"),
            "beta": s.get("beta"),
            "price": s.get("regularMarketPrice") or s.get("previousClose"),
            "currency": s.get("currency", "USD"),
            "description": p.get("longBusinessSummary", ""),
            "website": p.get("website", ""),
            "country": p.get("country", ""),
            "total_revenue": f.get("totalRevenue"),
            "gross_margins": f.get("grossMargins"),
            "operating_margins": f.get("operatingMargins"),
            "profit_margins": f.get("profitMargins"),
            "return_on_equity": f.get("returnOnEquity"),
            "debt_to_equity": f.get("debtToEquity"),
            "current_ratio": f.get("currentRatio"),
            "total_cash": f.get("totalCash"),
            "total_debt": f.get("totalDebt"),
            "free_cash_flow": f.get("freeCashflow"),
            "operating_cash_flow": f.get("operatingCashflow"),
            "revenue_growth": f.get("revenueGrowth"),
            "earnings_growth": f.get("earningsGrowth"),
            "shares_outstanding": s.get("sharesOutstanding"),
            "target_mean_price": f.get("targetMeanPrice"),
            "recommendation": f.get("recommendationKey"),
        }
    except Exception as e:
        logger.warning(f"yahooquery falló para {ticker}: {e}")
        return None


def _safe_yfinance_call(callable_fn, ticker: str) -> Dict[str, Any]:
    try:
        result = callable_fn()
        if result is None or (isinstance(result, dict) and not result):
            return {"ticker": ticker.upper(), "error": "data provider vacío"}
        return result
    except Exception as e:
        err_msg = str(e)[:300]
        if "429" in err_msg or "Too Many Requests" in err_msg:
            return {"ticker": ticker.upper(), "error": "Rate limit. Espera 30 min."}
        if "Expecting value" in err_msg or "JSONDecodeError" in err_msg:
            return {"ticker": ticker.upper(), "error": "JSON inválido del data provider."}
        return {"ticker": ticker.upper(), "error": f"{type(e).__name__}: {err_msg}"}


def get_ticker_info(ticker: str) -> Dict[str, Any]:
    cache_key = f"info_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # 1) Intentar yahooquery (más robusto)
    result = _try_yahooquery(ticker)
    if result and "error" not in result:
        _set_cached(cache_key, result)
        return result

    # 2) Fallback a yfinance
    try:
        import yfinance as yf

        def fetch():
            t = yf.Ticker(ticker)
            info = t.info
            if not info or len(info) < 5:
                raise ValueError("Yahoo info vacía")

            return {
                "ticker": ticker.upper(),
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "beta": info.get("beta"),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "currency": info.get("currency", "USD"),
                "dividend_yield": info.get("dividendYield"),
                "free_cash_flow": info.get("freeCashflow"),
                "revenue_growth": info.get("revenueGrowth"),
            }

        result = _safe_yfinance_call(fetch, ticker)
        if "error" not in result:
            _set_cached(cache_key, result)
        return result
    except ImportError:
        return {"ticker": ticker.upper(), "error": "Ningún data provider disponible"}


def get_financials(ticker: str) -> Dict[str, Any]:
    """Placeholder que devuelve estructura mínima."""
    return {"ticker": ticker.upper(), "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}


def get_price_history(ticker: str, period: str = "1y") -> Dict[str, Any]:
    return {"ticker": ticker.upper(), "dates": [], "prices": []}

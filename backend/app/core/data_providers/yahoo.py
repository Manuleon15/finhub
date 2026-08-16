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


def _df_to_year_dict(df) -> Dict[str, Dict[str, Any]]:
    """Convierte un DataFrame de yfinance (filas=conceptos, columnas=fechas)
    a {"2024": {"Net Income": 123.0, ...}, "2023": {...}, ...}.

    yfinance devuelve NaN para huecos; los convertimos a None para que
    el resto del código (get_metric, _find_field...) los trate como
    "dato no disponible" de forma consistente.
    """
    if df is None or df.empty:
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for col in df.columns:
        try:
            year_key = str(col.year) if hasattr(col, "year") else str(col)
        except Exception:
            year_key = str(col)

        year_data: Dict[str, Any] = {}
        for row_name, value in df[col].items():
            if value is None:
                year_data[row_name] = None
                continue
            try:
                fval = float(value)
                year_data[row_name] = None if fval != fval else fval  # fval != fval -> NaN
            except (TypeError, ValueError):
                year_data[row_name] = None

        # Si ya existe ese año (p.ej. mismo año en anual y trimestral), no lo pisamos
        if year_key not in result:
            result[year_key] = year_data
        else:
            result[year_key].update({k: v for k, v in year_data.items() if v is not None})

    return result


def get_financials(ticker: str) -> Dict[str, Any]:
    """Obtiene income statement, balance sheet y cash flow (anuales) vía yfinance.

    Devuelve SIEMPRE la estructura esperada por el resto del código
    (income_statement / balance_sheet / cash_flow, cada uno un dict
    {"2024": {...campo: valor...}, "2023": {...}}), incluso si falla
    la descarga — en ese caso, vacío en vez de reventar.
    """
    cache_key = f"financials_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    empty = {"ticker": ticker.upper(), "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    try:
        import yfinance as yf

        t = yf.Ticker(ticker)

        # yfinance expone .financials / .balance_sheet / .cashflow (anual)
        income_df = t.financials
        balance_df = t.balance_sheet
        cashflow_df = t.cashflow

        result = {
            "ticker": ticker.upper(),
            "income_statement": _df_to_year_dict(income_df),
            "balance_sheet": _df_to_year_dict(balance_df),
            "cash_flow": _df_to_year_dict(cashflow_df),
        }

        # Si las tres vienen vacías, tratarlo como fallo (no cachear vacío)
        if not any([result["income_statement"], result["balance_sheet"], result["cash_flow"]]):
            logger.warning(f"get_financials({ticker}): yfinance devolvió estados financieros vacíos")
            return empty

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"get_financials({ticker}) falló: {e}")
        return empty


def get_price_history(ticker: str, period: str = "1y") -> Dict[str, Any]:
    return {"ticker": ticker.upper(), "dates": [], "prices": []}


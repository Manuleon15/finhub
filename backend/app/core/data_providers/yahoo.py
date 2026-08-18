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
CACHE_TTL = 900  # 15 minutos — precio, ratios, etc. (cambian a diario)
FINANCIALS_CACHE_TTL = 6 * 3600  # 6 horas — estados financieros (no cambian intradía;
# refrescarlos cada 15 min solo gasta peticiones contra Yahoo sin necesidad,
# y es justo lo que provoca el 429 Too Many Requests al probar varios tickers seguidos)


def _get_cached(key: str, ttl: int = CACHE_TTL) -> Optional[Any]:
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < ttl:
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

        # Módulo adicional para EPS/book value/PEG — en un try aparte para
        # que, si este módulo concreto falla, no tire abajo todo lo demás.
        k: Dict[str, Any] = {}
        try:
            key_stats = t.key_stats
            k = key_stats.get(ticker, {}) or {}
        except Exception:
            k = {}

        price = s.get("regularMarketPrice") or s.get("previousClose")

        return {
            "ticker": ticker.upper(),
            "name": p.get("longName") or s.get("shortName") or ticker,
            "sector": p.get("sector", "N/A"),
            "industry": p.get("industry", "N/A"),
            "market_cap": s.get("marketCap"),
            "enterprise_value": f.get("enterpriseValue") or k.get("enterpriseValue"),
            "pe_ratio": s.get("trailingPE"),
            "forward_pe": s.get("forwardPE") or k.get("forwardPE"),
            "pb_ratio": s.get("priceToBook") or k.get("priceToBook"),
            "peg_ratio": k.get("pegRatio"),
            "ev_to_revenue": k.get("enterpriseToRevenue"),
            "ev_to_ebitda": k.get("enterpriseToEbitda"),
            "eps": k.get("trailingEps"),
            "book_value_per_share": k.get("bookValue"),
            "dividend_yield": s.get("dividendYield"),
            "beta": s.get("beta"),
            "price": price,
            "current_price": price,
            "currency": s.get("currency", "USD"),
            "description": p.get("longBusinessSummary", ""),
            "website": p.get("website", ""),
            "country": p.get("country", ""),
            "employees": p.get("fullTimeEmployees"),
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
            "shares_outstanding": s.get("sharesOutstanding") or k.get("sharesOutstanding"),
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


def _fetch_yfinance_info(ticker: str) -> Dict[str, Any]:
    """Fetch de datos vía yfinance. Lanza excepción si falla (la maneja el caller)."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info
    if not info or len(info) < 5:
        raise ValueError("Yahoo info vacía")

    price = info.get("currentPrice") or info.get("regularMarketPrice")

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "description": info.get("longBusinessSummary", ""),
        "website": info.get("website", ""),
        "country": info.get("country", ""),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "peg_ratio": info.get("pegRatio") or info.get("trailingPegRatio"),
        "ev_to_revenue": info.get("enterpriseToRevenue"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "beta": info.get("beta"),
        "price": price,
        "current_price": price,
        "eps": info.get("trailingEps"),
        "book_value_per_share": info.get("bookValue"),
        "currency": info.get("currency", "USD"),
        "dividend_yield": info.get("dividendYield"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "total_revenue": info.get("totalRevenue"),
        "free_cash_flow": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "target_mean_price": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
    }


def get_ticker_info(ticker: str) -> Dict[str, Any]:
    cache_key = f"info_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # 1) yahooquery (rápido, pero le faltan varios campos: PEG, EV/Revenue,
    #    EV/EBITDA, EPS, book value...)
    yq_result = _try_yahooquery(ticker)
    if yq_result and "error" in yq_result:
        yq_result = None

    # 2) yfinance — SOLO si yahooquery falló del todo, o si le faltan campos
    #    importantes que solo trae yfinance. Antes se llamaba siempre a
    #    ambos proveedores por cada análisis, lo que duplicaba las
    #    peticiones a Yahoo y hacía mucho más fácil toparse con el rate
    #    limit (429 Too Many Requests) al probar varios tickers seguidos.
    FIELDS_ONLY_IN_YFINANCE = ["peg_ratio", "ev_to_revenue", "ev_to_ebitda", "eps", "book_value_per_share"]
    needs_yfinance_gapfill = (
        not yq_result
        or any(yq_result.get(f) is None for f in FIELDS_ONLY_IN_YFINANCE)
    )

    yf_result: Optional[Dict[str, Any]] = None
    yf_error: Optional[Dict[str, Any]] = None
    if needs_yfinance_gapfill:
        try:
            yf_result = _safe_yfinance_call(lambda: _fetch_yfinance_info(ticker), ticker)
            if "error" in yf_result:
                yf_error = yf_result
                yf_result = None
        except ImportError:
            yf_error = {"ticker": ticker.upper(), "error": "yfinance no disponible"}

    if not yq_result and not yf_result:
        # Ninguna de las dos fuentes ha funcionado
        return yf_error or {"ticker": ticker.upper(), "error": "Ningún data provider disponible"}

    if yq_result and yf_result:
        # Combinar: yahooquery manda, pero cualquier campo que le falte
        # (y no en el otro sentido) se rellena con yfinance.
        merged = dict(yq_result)
        for key, val in yf_result.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        result = merged
    else:
        result = yq_result or yf_result

    _set_cached(cache_key, result)
    return result


# Nombres de campo a comprobar en el diagnóstico de get_financials (no se
# importa de analyzer.py para evitar un import circular entre ambos módulos).
FIELD_CANDIDATES_CASHFLOW_CHECK = [
    "Operating Cash Flow",
    "OperatingCashFlow",
    "Total Cash From Operating Activities",
    "Cash Flow From Continuing Operating Activities",
]


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
    cached = _get_cached(cache_key, ttl=FINANCIALS_CACHE_TTL)
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

        # Diagnóstico: qué años llegaron y si los campos clave que usa el
        # resto del código (OCF, Capex...) realmente están presentes con
        # ese nombre exacto. Esto es lo que hay que mirar en la terminal
        # si el DCF o las métricas de calidad salen raras.
        cf_years = sorted(result["cash_flow"].keys(), reverse=True)
        if cf_years:
            sample_year = cf_years[0]
            sample_fields = result["cash_flow"][sample_year]
            has_ocf = any(
                sample_fields.get(c) is not None for c in FIELD_CANDIDATES_CASHFLOW_CHECK
            )
            logger.info(
                f"get_financials({ticker}): cash_flow años={cf_years} "
                f"| campos año {sample_year}: {list(sample_fields.keys())[:8]}... "
                f"| ¿tiene OCF reconocible?: {has_ocf}"
            )
        else:
            logger.warning(f"get_financials({ticker}): cash_flow vacío (income/balance sí llegaron)")

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"get_financials({ticker}) falló: {e}")
        return empty


def get_price_history(ticker: str, period: str = "1y") -> Dict[str, Any]:
    return {"ticker": ticker.upper(), "dates": [], "prices": []}

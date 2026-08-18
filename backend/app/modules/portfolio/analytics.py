"""Analítica de riesgo y métricas premium del portfolio.

Estilo getquin / Investing Pro:
- Sharpe ratio, Sortino ratio, volatilidad anualizada
- Max drawdown, beta vs S&P 500, alpha, correlación
- Concentración (HHI), diversificación efectiva
- Recomendaciones accionables de mejora
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.portfolio.models import Position

logger = logging.getLogger("finhub.portfolio.analytics")

# Tasa libre de riesgo para Sharpe (US 10Y ~4.5% / 12 = mensual)
RISK_FREE_RATE = 0.045
TRADING_DAYS = 252

# Niveles de concentración por HHI
def _hhi_label(hhi: float) -> str:
    if hhi < 0.15:
        return "Bien diversificada"
    if hhi < 0.25:
        return "Moderadamente concentrada"
    if hhi < 0.40:
        return "Concentrada"
    return "Muy concentrada"


def _fetch_price_history(ticker: str, period: str = "1y") -> List[float]:
    """Devuelve lista de precios de cierre de yfinance."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            return []
        return [float(v) for v in hist["Close"].tolist()]
    except Exception:
        return []


def _returns_from_prices(prices: List[float]) -> List[float]:
    """Convierte precios en retornos diarios."""
    rets = []
    for i in range(1, len(prices)):
        if prices[i-1] and prices[i-1] > 0:
            rets.append((prices[i] / prices[i-1]) - 1)
    return rets


def _annualized_vol(returns: List[float]) -> Optional[float]:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def _sharpe(returns: List[float], rf_daily: float) -> Optional[float]:
    if len(returns) < 2:
        return None
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / len(excess)
    var = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
    if var == 0:
        return None
    sd = math.sqrt(var)
    return (mean / sd) * math.sqrt(TRADING_DAYS)


def _sortino(returns: List[float], rf_daily: float) -> Optional[float]:
    if len(returns) < 2:
        return None
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / len(excess)
    downside = [min(r, 0) for r in excess]
    downside_var = sum(d * d for d in downside) / len(downside)
    if downside_var == 0:
        return None
    downside_dev = math.sqrt(downside_var)
    return (mean / downside_dev) * math.sqrt(TRADING_DAYS)


def _max_drawdown(prices: List[float]) -> Optional[float]:
    if len(prices) < 2:
        return None
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (p - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _beta_alpha(port_returns: List[float], bench_returns: List[float], rf_daily: float) -> Dict[str, Optional[float]]:
    """Beta y alpha vs benchmark (S&P 500), con el mismo rango de fechas."""
    n = min(len(port_returns), len(bench_returns))
    if n < 2:
        return {"beta": None, "alpha": None, "correlation": None}

    pr = port_returns[-n:]
    br = bench_returns[-n:]

    mean_pr = sum(pr) / n
    mean_br = sum(br) / n

    cov = sum((pr[i] - mean_pr) * (br[i] - mean_br) for i in range(n)) / (n - 1)
    var_br = sum((br[i] - mean_br) ** 2 for i in range(n)) / (n - 1)

    if var_br == 0:
        return {"beta": None, "alpha": None, "correlation": None}

    beta = cov / var_br
    alpha = (mean_pr - mean_br * beta) * TRADING_DAYS  # alpha anualizado

    # Correlación
    sd_pr = math.sqrt(sum((r - mean_pr) ** 2 for r in pr) / (n - 1)) if n > 1 else 0
    sd_br = math.sqrt(var_br)
    correlation = (cov / (sd_pr * sd_br)) if (sd_pr and sd_br) else None

    return {
        "beta": round(beta, 2),
        "alpha": round(alpha, 4),
        "correlation": round(correlation, 3) if correlation is not None else None,
    }


def _concentration(weights: List[float]) -> float:
    """Índice HHI = suma de pesos al cuadrado."""
    return sum(w * w for w in weights)


def _effective_n(hhi: float) -> float:
    return 1 / hhi if hhi > 0 else 0


def _recommendations(kpis: Dict[str, Any], beta: Optional[float], hhi: float,
                     sortino: Optional[float], total: float) -> List[str]:
    """Recomendaciones accionables de mejora de cartera."""
    recs = []

    # Concentración
    if hhi >= 0.25:
        biggest = max(kpis.get("top_positions", []), key=lambda x: x["pct"], default=None)
        if biggest:
            recs.append(
                f"⚠️ Concentración alta: {biggest['ticker']} pesa un "
                f"{biggest['pct']*100:.1f}% de la cartera. Considera rebalancear "
                f"para reducir riesgo (ideal <15% por posición)."
            )
    else:
        recs.append("✅ Diversificación razonable. Mantén la distribución actual.")

    # Beta
    if beta is not None:
        if beta > 1.2:
            recs.append(
                f"⚠️ Beta {beta:.2f}: la cartera es más volátil que el mercado. "
                f"En caídas del 10% podrías esperar -{beta*10:.0f}%."
            )
        elif beta < 0.8:
            recs.append(
                f"ℹ️ Beta {beta:.2f}: cartera defensiva, menos volatilidad que el mercado."
            )
        else:
            recs.append(f"✅ Beta {beta:.2f}: riesgo de mercado equilibrado.")

    # Sortino bajo
    if sortino is not None and sortino < 1:
        recs.append(
            "⚠️ Retorno ajustado a riesgo bajo (Sortino < 1). "
            "Considera recoger beneficios en posiciones muy sobrevaloradas "
            "o añadir activos con mejor perfil riesgo-retorno."
        )

    # Cash / concentración sectorial (usamos kpis si viene)
    sector = kpis.get("top_sector")
    if sector and sector["pct"] > 0.40:
        recs.append(
            f"⚠️ Sector {sector['sector']} concentra {sector['pct']*100:.0f}%. "
            f"Diversifica hacia otros sectores para reducir riesgo idiosincrático."
        )

    if total and total > 0:
        recs.append(
            "ℹ️ Revisa el preview de IRPF: vender posiciones en positivo "
            "acumulado puede tener impacto fiscal. Planifica con antelación."
        )

    return recs


# ======================= ENDPOINT PRINCIPAL =======================

def portfolio_analytics(db: Session) -> Dict[str, Any]:
    """Analítica completa: riesgos, retornos, concentración, recomendaciones."""
    positions = db.query(Position).all()
    if not positions:
        return {"error": "No hay posiciones", "has_data": False}

    total = sum(p.market_value or 0 for p in positions)
    if total <= 0:
        return {"error": "Valor total 0", "has_data": False}

    # Benchmark S&P 500 (^GSPC) — 1 año
    bench_prices = _fetch_price_history("^GSPC", "1y")
    bench_returns = _returns_from_prices(bench_prices)
    bench_annual_ret = None
    if bench_prices and len(bench_prices) > 1:
        bench_annual_ret = (bench_prices[-1] / bench_prices[0]) - 1

    # Recopilar retornos del portfolio: media ponderada de cada posición
    rf_daily = RISK_FREE_RATE / TRADING_DAYS
    all_ret_series: List[List[float]] = []
    weights = []
    pos_analytics = []

    for p in positions:
        mv = p.market_value or 0
        w = mv / total
        weights.append(w)
        prices = _fetch_price_history(p.ticker, "1y")
        rets = _returns_from_prices(prices)
        pos_analytics.append({
            "ticker": p.ticker,
            "weight": round(w, 4),
            "vol_annual": round(_annualized_vol(rets), 4) if rets else None,
            "max_drawdown": round(_max_drawdown(prices), 4) if prices else None,
            "annual_return_est": round((prices[-1]/prices[0]-1), 4) if len(prices)>1 else None,
        })
        if rets:
            all_ret_series.append(rets)

    # Serie combinada del portfolio (promedio de retornos por día, ponderado por peso simple)
    # Aproximación: alinear por el mínimo largo común
    if all_ret_series:
        min_len = min(len(r) for r in all_ret_series)
        port_returns = []
        for i in range(min_len):
            day_rets = []
            for j, rs in enumerate(all_ret_series):
                day_rets.append(rs[i - (len(rs) - min_len)] if i >= len(rs) - min_len else rs[i])
            # filtrar Nones
            valid = [r for r in day_rets if r is not None]
            port_returns.append(sum(valid)/len(valid) if valid else 0.0)
    else:
        port_returns = []

    vol = _annualized_vol(port_returns)
    sharpe = _sharpe(port_returns, rf_daily)
    sortino = _sortino(port_returns, rf_daily)
    max_dd = None
    # max drawdown del portfolio requiere precios; aproximar desde retornos
    if port_returns:
        cum = 1.0
        peak = 1.0
        dd = 0.0
        for r in port_returns:
            cum *= (1 + r)
            peak = max(peak, cum)
            dd = min(dd, (cum - peak)/peak)
        max_dd = dd

    beta_alpha = _beta_alpha(port_returns, bench_returns, rf_daily)

    # Retorno anual del portfolio (estimado)
    port_annual_ret = None
    if port_returns:
        prod = 1.0
        for r in port_returns:
            prod *= (1 + r)
        port_annual_ret = prod - 1

    hhi = _concentration(weights)
    eff_n = _effective_n(hhi)

    # Top posiciones y sector (para recomendaciones)
    top_positions = sorted(
        [{"ticker": p.ticker, "pct": (p.market_value or 0)/total} for p in positions],
        key=lambda x: -x["pct"]
    )[:5]

    kpis_for_recs = {"top_positions": top_positions}

    recs = _recommendations(
        kpis_for_recs, beta_alpha.get("beta"), hhi, sortino, total
    )

    return {
        "has_data": True,
        "risk_metrics": {
            "volatility_annual": round(vol, 4) if vol is not None else None,
            "volatility_label": f"{vol*100:.1f}%" if vol is not None else "N/D",
            "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,
            "sortino_ratio": round(sortino, 2) if sortino is not None else None,
            "max_drawdown": round(max_dd, 4) if max_dd is not None else None,
            "max_drawdown_label": f"{max_dd*100:.1f}%" if max_dd is not None else "N/D",
        },
        "benchmark": {
            "name": "S&P 500",
            "ticker": "^GSPC",
            "annual_return": round(bench_annual_ret, 4) if bench_annual_ret is not None else None,
            "annual_return_label": f"{bench_annual_ret*100:.1f}%" if bench_annual_ret is not None else "N/D",
            "portfolio_annual_return": round(port_annual_ret, 4) if port_annual_ret is not None else None,
            "portfolio_annual_return_label": f"{port_annual_ret*100:.1f}%" if port_annual_ret is not None else "N/D",
            "beta_vs_sp500": beta_alpha.get("beta"),
            "alpha_vs_sp500": beta_alpha.get("alpha"),
            "correlation": beta_alpha.get("correlation"),
            "outperformance": (
                round((port_annual_ret - bench_annual_ret), 4)
                if port_annual_ret is not None and bench_annual_ret is not None else None
            ),
        },
        "concentration": {
            "hhi": round(hhi, 4),
            "effective_n": round(eff_n, 1),
            "label": _hhi_label(hhi),
            "top_positions": [
                {"ticker": x["ticker"], "pct": round(x["pct"], 4)} for x in top_positions
            ],
        },
        "positions": pos_analytics,
        "recommendations": recs,
        "disclaimer": (
            "Métricas calculadas con datos de cierre diarios de Yahoo Finance (1 año). "
            "No es asesoramiento financiero."
        ),
    }

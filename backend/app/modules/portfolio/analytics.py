"""Analítica premium del portfolio — complementa al Excel.

Tres capas:
1) METRICAS DE EXCEL (funcionan YA, sin Yahoo): beta ponderada, dividend yield,
   P&L sobre coste, concentración sectorial, IRPF. Con comentario de analista.
2) METRICAS DE RIESGO (requieren histórico Yahoo, con batch+caché): Sharpe,
   Sortino, volatilidad, max drawdown, beta vs S&P 500.
3) COMENTARIOS DE ANALISTA: redacta una nota profesional con tus números reales.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.portfolio.models import Position, Transaction

logger = logging.getLogger("finhub.portfolio.analytics")

RISK_FREE_RATE = 0.045
TRADING_DAYS = 252
HISTORY_CACHE_TTL = 12 * 3600  # 12h

# Cache de históricos: ticker -> (timestamp, [prices])
_HISTORY_CACHE: Dict[str, tuple[float, List[float]]] = {}

# ======================= 1) MÉTRICAS DE EXCEL (sin Yahoo) =======================

def _sector_exposure(positions, total) -> List[Dict[str, Any]]:
    mapa: Dict[str, float] = {}
    for p in positions:
        s = p.sector or "Sin sector"
        mapa[s] = mapa.get(s, 0) + (p.market_value or 0)
    return [
        {"sector": s, "value": round(v, 2), "pct": round(v / total, 4) if total else 0}
        for s, v in sorted(mapa.items(), key=lambda x: -x[1])
    ]


def _beta_ponderada(positions, total) -> Optional[float]:
    num = sum((p.beta or 0) * (p.market_value or 0) for p in positions if p.beta is not None)
    den = sum((p.market_value or 0) for p in positions if p.beta is not None)
    return round(num / den, 2) if den else None


def _dividend_yield_cartera(positions, total) -> Optional[float]:
    divs = sum((p.dividend_per_share or 0) * p.quantity for p in positions)
    return round(divs / total, 4) if total else None


def _concentracion(positions, total) -> Dict[str, Any]:
    pesos = [(p.market_value or 0) / total for p in positions] if total else []
    hhi = sum(w * w for w in pesos)
    eff_n = 1 / hhi if hhi > 0 else 0
    if hhi < 0.15:
        label = "Bien diversificada"
    elif hhi < 0.25:
        label = "Moderadamente concentrada"
    elif hhi < 0.40:
        label = "Concentrada"
    else:
        label = "Muy concentrada"
    top = sorted(
        [{"ticker": p.ticker, "pct": (p.market_value or 0) / total} for p in positions],
        key=lambda x: -x["pct"],
    )[:5]
    return {"hhi": round(hhi, 4), "effective_n": round(eff_n, 1), "label": label, "top": top}


def _retorno_sobre_coste(positions) -> Optional[float]:
    mv = sum(p.market_value or 0 for p in positions)
    cb = sum(p.cost_basis or 0 for p in positions)
    return round((mv - cb) / cb, 4) if cb else None


# ======================= 2) HISTÓRICO (batch + caché) =======================

def _fetch_history_batch(tickers: List[str]) -> Dict[str, List[float]]:
    """Trae históricos en UNA llamada batch por ticker, con caché de 12h."""
    result: Dict[str, List[float]] = {}
    now = time.time()

    # Filtra los que ya están en caché
    to_fetch = []
    for t in tickers:
        if t in _HISTORY_CACHE:
            ts, prices = _HISTORY_CACHE[t]
            if now - ts < HISTORY_CACHE_TTL:
                result[t] = prices
                continue
        to_fetch.append(t)

    if not to_fetch:
        return result

    try:
        import yfinance as yf
        # Descarga en lote (reduce número de llamadas y riesgo de 429)
        data = yf.download(to_fetch, period="1y", progress=False, group_by="ticker", threads=True)
        for t in to_fetch:
            try:
                if len(to_fetch) == 1:
                    closes = data["Close"].dropna().tolist()
                else:
                    closes = data[t]["Close"].dropna().tolist()
                prices = [float(x) for x in closes]
                result[t] = prices
                _HISTORY_CACHE[t] = (now, prices)
            except Exception:
                result[t] = []
                _HISTORY_CACHE[t] = (now, [])
    except Exception as e:
        logger.warning(f"Fallo histórico batch: {e}")

    return result


def _returns(prices: List[float]) -> List[float]:
    return [(prices[i] / prices[i-1]) - 1 for i in range(1, len(prices)) if prices[i-1] > 0]


def _metrics_from_returns(rets: List[float], rf_daily: float) -> Dict[str, Optional[float]]:
    if len(rets) < 2:
        return {"vol": None, "sharpe": None, "sortino": None, "max_dd": None, "annual": None}

    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    vol = math.sqrt(var) * math.sqrt(TRADING_DAYS)

    excess = [r - rf_daily for r in rets]
    mean_ex = sum(excess) / len(excess)
    var_ex = sum((r - mean_ex) ** 2 for r in excess) / (len(excess) - 1)
    sharpe = (mean_ex / math.sqrt(var_ex)) * math.sqrt(TRADING_DAYS) if var_ex else None

    downside = [min(r, 0) for r in excess]
    dvar = sum(d * d for d in downside) / len(downside)
    sortino = (mean_ex / math.sqrt(dvar)) * math.sqrt(TRADING_DAYS) if dvar else None

    cum, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        cum *= (1 + r)
        peak = max(peak, cum)
        mdd = min(mdd, (cum - peak) / peak)
    max_dd = mdd

    prod = 1.0
    for r in rets:
        prod *= (1 + r)
    annual = prod - 1

    return {"vol": vol, "sharpe": sharpe, "sortino": sortino, "max_dd": max_dd, "annual": annual}


# ======================= 3) COMENTARIO DE ANALISTA =======================

def _comentario_analista(analytics: Dict[str, Any]) -> Dict[str, str]:
    """Redacta una nota de investigación profesional con los números reales."""
    analytics = analytics.get("excel_metrics", analytics)
    conc = analytics["concentration"]
    beta = analytics["beta_ponderada"]
    yld = analytics["dividend_yield"]
    roc = analytics["retorno_sobre_coste"]
    sector = analytics["top_sector"]
    perf = analytics.get("performance", {})

    buenas = []
    riesgos = []
    accion = []

    # Diversificación
    if conc["hhi"] < 0.15:
        buenas.append(
            f"La cartera muestra una diversificación sólida (HHI {conc['hhi']:.2f}, "
            f"{conc['effective_n']} posiciones efectivas), lo que reduce el riesgo idiosincrático."
        )
    else:
        top = conc["top"][0] if conc["top"] else {}
        riesgos.append(
            f"Existe concentración significativa: {top.get('ticker','?')} representa "
            f"~{top.get('pct',0)*100:.0f}% de la cartera. Posiciones dominantes amplifican la volatilidad."
        )

    # Beta
    if beta is not None:
        if beta > 1.2:
            riesgos.append(
                f"La beta ponderada de {beta:.2f} indica una cartera agresiva: "
                f"más sensible que el mercado. Ante un retroceso del 10% del S&P 500, "
                f"cabría esperar un movimiento aproximado del {beta*10:.0f}%."
            )
            accion.append("Valorar reducir exposición en nombres de alta beta si el horizonte es corto.")
        elif beta < 0.8:
            buenas.append(
                f"Con beta {beta:.2f}, la cartera es más defensiva que el mercado, "
                f"lo que la protege en correcciones amplias."
            )
        else:
            buenas.append(
                f"La beta ponderada de {beta:.2f} sitúa la cartera en línea con el mercado, "
                f"sin un sesgo direccional excesivo."
            )

    # Retorno sobre coste
    if roc is not None:
        if roc > 0.2:
            buenas.append(
                f"El retorno no realizado sobre el coste es del {roc*100:.1f}%, "
                f"una plusvalía latente significativa que confirma buena selección de activos."
            )
        elif roc < -0.1:
            riesgos.append(
                f"El retorno sobre coste es {roc*100:.1f}%. Varias posiciones están en pérdida: "
                f"conviene distinguir entre correcciones temporales y deterioro fundamental."
            )
            accion.append("Revisar posiciones en pérdida estructural y considerar stop-loss racionales.")

    # Concentración sectorial
    if sector and sector["pct"] > 0.40:
        riesgos.append(
            f"El sector {sector['sector']} concentra el {sector['pct']*100:.0f}% de la cartera. "
            f"Riesgo de correlación elevado si ese sector se corrige."
        )
        accion.append("Diversificar hacia sectores anticíclicos (consumo defensivo, utilities, salud).")

    # Yield
    if yld is not None and yld > 0.02:
        buenas.append(
            f"La rentabilidad por dividendo de la cartera es del {yld*100:.1f}%, "
            f"un colchón de ingresos pasivos que reduce la dependencia de la revalorización."
        )

    # Performance vs benchmark
    if perf.get("sharpe") is not None:
        if perf["sharpe"] > 1:
            buenas.append(
                f"El Sharpe de {perf['sharpe']:.2f} indica retorno ajustado a riesgo "
                f"sólido frente al capital asumido."
            )
        elif perf["sharpe"] < 0:
            riesgos.append(
                f"El Sharpe negativo ({perf['sharpe']:.2f}) muestra que el retorno no compensa "
                f"la volatilidad en el periodo analizado."
            )

    # Veredicto
    if len(buenas) > len(riesgos):
        resumen = "Perfil saludable con margen de mejora en concentración."
    elif len(riesgos) > len(buenas):
        resumen = "Cartera con riesgos acotables: prioriza diversificación y revisión de posiciones."
    else:
        resumen = "Cartera equilibrada. Los ajustes propuestos refuerzan el perfil riesgo-retorno."

    return {
        "resumen": resumen,
        "fortalezas": buenas,
        "riesgos": riesgos,
        "recomendaciones": accion,
        "nota": (
            "Comentario generado automáticamente a partir de tus posiciones y datos de mercado. "
            "No constituye asesoramiento financiero."
        ),
    }


# ======================= ENDPOINT =======================

def portfolio_analytics(db: Session) -> Dict[str, Any]:
    positions = db.query(Position).all()
    transactions = db.query(Transaction).all()
    if not positions:
        return {"has_data": False, "error": "No hay posiciones"}

    total = sum(p.market_value or 0 for p in positions)
    if total <= 0:
        return {"has_data": False, "error": "Valor total 0"}

    # --- Capa 1: métricas de Excel (siempre disponibles) ---
    sector_exposure = _sector_exposure(positions, total)
    beta = _beta_ponderada(positions, total)
    yld = _dividend_yield_cartera(positions, total)
    conc = _concentracion(positions, total)
    roc = _retorno_sobre_coste(positions)
    realized = sum(t.realized_pl or 0 for t in transactions)

    # --- Capa 2: histórico batch + métricas de riesgo (si Yahoo responde) ---
    tickers = [p.ticker for p in positions if p.currency != "CRYPTO"]
    tickers.append("^GSPC")
    hist = _fetch_history_batch(list(dict.fromkeys(tickers)))
    rf_daily = RISK_FREE_RATE / TRADING_DAYS

    # Portfolio returns (media de retornos diarios por posición, simple)
    series = []
    bench = hist.get("^GSPC", [])
    bench_rets = _returns(bench)
    for t in [x for x in tickers if x != "^GSPC"]:
        pr = hist.get(t, [])
        r = _returns(pr)
        if r and len(series) == 0:
            series = r
        elif r:
            n = min(len(series), len(r))
            series = [series[i] + r[i] for i in range(n)]
    if series:
        n = sum(1 for t in [x for x in tickers if x != "^GSPC"] if hist.get(t))
        series = [x / n for x in series] if n else []

    perf = _metrics_from_returns(series, rf_daily) if series else {}
    bench_perf = _metrics_from_returns(bench_rets, rf_daily) if bench_rets else {}

    # Beta vs S&P 500
    beta_sp = alpha = corr = None
    if series and bench_rets:
        n = min(len(series), len(bench_rets))
        s, b = series[-n:], bench_rets[-n:]
        ms, mb = sum(s)/n, sum(b)/n
        cov = sum((s[i]-ms)*(b[i]-mb) for i in range(n))/(n-1)
        varb = sum((b[i]-mb)**2 for i in range(n))/(n-1)
        if varb:
            beta_sp = round(cov/varb, 2)
            alpha = round((ms - mb*beta_sp)*TRADING_DAYS, 4)
            sd_s = math.sqrt(sum((x-ms)**2 for x in s)/(n-1)) if n>1 else 0
            sd_b = math.sqrt(varb)
            corr = round(cov/(sd_s*sd_b), 3) if (sd_s and sd_b) else None

    # Ensamblar
    payload = {
        "has_data": True,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "excel_metrics": {
            "beta_ponderada": beta,
            "dividend_yield": yld,
            "dividend_yield_label": f"{yld*100:.1f}%" if yld is not None else "N/D",
            "retorno_sobre_coste": roc,
            "retorno_sobre_coste_label": f"{roc*100:.1f}%" if roc is not None else "N/D",
            "realized_pl": round(realized, 2),
            "concentration": conc,
            "sector_exposure": sector_exposure,
            "top_sector": sector_exposure[0] if sector_exposure else None,
        },
        "risk_metrics": {
            "volatility_annual": round(perf.get("vol", 0), 4) if perf.get("vol") else None,
            "volatility_label": f"{perf['vol']*100:.1f}%" if perf.get("vol") else "N/D",
            "sharpe_ratio": round(perf["sharpe"], 2) if perf.get("sharpe") is not None else None,
            "sortino_ratio": round(perf["sortino"], 2) if perf.get("sortino") is not None else None,
            "max_drawdown": round(perf["max_dd"], 4) if perf.get("max_dd") is not None else None,
            "max_drawdown_label": f"{perf['max_dd']*100:.1f}%" if perf.get("max_dd") is not None else "N/D",
        },
        "benchmark": {
            "name": "S&P 500",
            "portfolio_annual": round(perf["annual"], 4) if perf.get("annual") is not None else None,
            "portfolio_annual_label": f"{perf['annual']*100:.1f}%" if perf.get("annual") is not None else "N/D",
            "sp500_annual": round(bench_perf["annual"], 4) if bench_perf.get("annual") is not None else None,
            "sp500_annual_label": f"{bench_perf['annual']*100:.1f}%" if bench_perf.get("annual") is not None else "N/D",
            "beta_vs_sp500": beta_sp,
            "alpha_vs_sp500": alpha,
            "correlation": corr,
        },
    }

    # Comentario de analista
    payload["analyst_comment"] = _comentario_analista(payload)

    return payload

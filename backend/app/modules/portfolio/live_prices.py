"""Actualización de precios en vivo para el portfolio.

Refresca current_price de cada posición usando yfinance con cache de 60s.
Permite que la pantalla se actualice sola sin tocar nada.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.modules.portfolio.models import Position

logger = logging.getLogger("finhub.live_prices")

# Cache: ticker -> (timestamp, price)
_PRICE_CACHE: Dict[str, tuple[float, Optional[float]]] = {}
CACHE_TTL = 60  # refresco cada 60s


def _fetch_price(ticker: str) -> Optional[float]:
    """Obtiene precio de yfinance (con cache de 60s y tolerante a fallos)."""
    now = time.time()
    if ticker in _PRICE_CACHE:
        ts, price = _PRICE_CACHE[ticker]
        if now - ts < CACHE_TTL:
            return price

    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.last_price
        if price is None:
            # fallback
            price = t.info.get("regularMarketPrice") or t.info.get("currentPrice")
        _PRICE_CACHE[ticker] = (now, price)
        return price
    except Exception as e:
        logger.warning(f"No se pudo actualizar {ticker}: {e}")
        _PRICE_CACHE[ticker] = (now, None)
        return None


def refresh_all_prices(db: Session) -> Dict[str, Any]:
    """Actualiza current_price de todas las posiciones. Devuelve resumen."""
    positions = db.query(Position).all()
    updated, failed = 0, 0

    for p in positions:
        # Saltar cripto por ahora (requiere Coinbase, otro provider)
        if p.currency == "CRYPTO":
            continue
        price = _fetch_price(p.ticker)
        if price is not None and price > 0:
            p.current_price = round(float(price), 4)
            updated += 1
        else:
            failed += 1

    db.commit()
    return {"updated": updated, "failed": failed, "total": len(positions)}


@router_noop = None  # placeholder para no romper imports

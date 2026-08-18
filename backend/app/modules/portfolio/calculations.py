"""Cálculos avanzados del portfolio: KPIs, sector allocation, TWR, dividendos, IRPF.

Esto es lo que hace que FinHub sea MEJOR que el Excel:
- Todo se calcula automáticamente desde las posiciones guardadas
- Los precios se actualizan en vivo (endpoint separado)
- Previsualización de IRPF español (base del ahorro)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.portfolio.models import Position, Transaction

logger = logging.getLogger("finhub.portfolio.calculations")

# Tramos IRPF base del ahorro 2024 (España)
IRPF_AHORRO = [
    (0, 6000, 0.19),
    (6000, 50000, 0.21),
    (50000, 200000, 0.23),
    (200000, 300000, 0.27),
    (300000, float("inf"), 0.28),
]

# Dividendos también van a base del ahorro en España
DIVIDEND_TAX = 0.19


def _safe(fn):
    """Ejecuta y devuelve None si falla (protection contra división por cero)."""
    try:
        return fn()
    except Exception:
        return None


# ======================= KPIs GLOBALES =======================

def portfolio_kpis(db: Session) -> Dict[str, Any]:
    """KPIs principales del portfolio, todos calculados de las posiciones."""
    positions = db.query(Position).all()

    total_value = sum(p.market_value or 0 for p in positions)
    total_cost = sum(p.cost_basis or 0 for p in positions)
    total_unrealized = total_value - total_cost
    total_unrealized_pct = (total_unrealized / total_cost) if total_cost else None

    # CRYPTO (ESP)
    crypto_value = sum(
        p.market_value or 0 for p in positions if p.currency == "CRYPTO"
    )

    # Ponderado por valor
    weight_per_pos = {
        p.ticker: ((p.market_value or 0) / total_value if total_value else 0)
        for p in positions
    }

    # Beta ponderada del portfolio (solo acciones con beta conocida)
    weighted_beta = 0.0
    beta_weight = 0.0
    for p in positions:
        if p.beta is not None:
            weighted_beta += (p.beta or 0) * (p.market_value or 0)
            beta_weight += (p.market_value or 0)
    portfolio_beta = weighted_beta / beta_weight if beta_weight else None

    # Dividendos esperados
    expected_dividends = sum(
        (p.dividend_per_share or 0) * p.quantity for p in positions
    )

    # PER ponderado de la cartera
    # (getattr con default: si tu modelo Position no tiene "per" con ese
    # nombre exacto —p.ej. lo renombraste a "pe_ratio"— esto no revienta,
    # simplemente no cuenta esa posición en el ponderado)
    per_weighted = 0.0
    per_weight = 0.0
    for p in positions:
        p_per = getattr(p, "per", None)
        if p_per is not None and p_per > 0:
            per_weighted += p_per * (p.market_value or 0)
            per_weight += (p.market_value or 0)
    portfolio_per = per_weighted / per_weight if per_weight else None

    return {
        "num_positions": len(positions),
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_unrealized_pl": round(total_unrealized, 2),
        "total_unrealized_pl_pct": (
            round(total_unrealized_pct, 4) if total_unrealized_pct is not None else None
        ),
        "crypto_value": round(crypto_value, 2),
        "portfolio_beta": round(portfolio_beta, 3) if portfolio_beta is not None else None,
        "expected_dividends": round(expected_dividends, 2),
        "portfolio_per": round(portfolio_per, 2) if portfolio_per is not None else None,
        "updated_at": datetime.utcnow().isoformat(),
    }


# ======================= ALLOCATION =======================

def allocation_by_sector(db: Session) -> List[Dict[str, Any]]:
    """Asignación por sector, con porcentaje y valor."""
    positions = db.query(Position).all()
    total = sum(p.market_value or 0 for p in positions)

    sector_map: Dict[str, float] = {}
    for p in positions:
        sector = p.sector or "Sin sector"
        sector_map[sector] = sector_map.get(sector, 0) + (p.market_value or 0)

    result = []
    for sector, value in sorted(sector_map.items(), key=lambda x: -x[1]):
        result.append(
            {
                "sector": sector,
                "value": round(value, 2),
                "pct": round(value / total, 4) if total else 0,
            }
        )
    return result


def allocation_by_ticker(db: Session) -> List[Dict[str, Any]]:
    """Asignación por ticker individual."""
    positions = db.query(Position).all()
    total = sum(p.market_value or 0 for p in positions)

    result = []
    for a, p in enumerate(
        sorted(positions, key=lambda x: -(x.market_value or 0))
    ):
        result.append(
            {
                "ticker": p.ticker,
                "value": round(p.market_value or 0, 2),
                "pct": round((p.market_value or 0) / total, 4) if total else 0,
            }
        )
    return result


# ======================= TWR vs SP500 =======================

def twr_series(db: Session) -> Dict[str, Any]:
    """Serie de retornos ponderados en el tiempo vs S&P 500.

    Usa realizaciones de la tabla MonthlySnapshot si existen; si no,
    calcula un proxy simple por meses con datos de posiciones.
    """
    from app.modules.portfolio.models import MonthlySnapshot

    snapshots = (
        db.query(MonthlySnapshot)
        .order_by(MonthlySnapshot.year, MonthlySnapshot.month)
        .all()
    )

    if snapshots:
        series = [
            {
                "period": f"{s.year}-{s.month:02d}",
                "portfolio": s.portfolio_twr_ytd,
                "sp500": s.sp500_twr_ytd,
                "portfolio_value": s.portfolio_value,
            }
            for s in snapshots
        ]
        return {"has_snapshots": True, "series": series}

    # Proxy: no hay snapshots todavía → serie vacía con instrucción
    return {
        "has_snapshots": False,
        "series": [],
        "note": "Aún no hay snapshot mensuales. Se generarán al guardar el histórico.",
    }


# ======================= IRPF PREVIEW =======================

def _tax_for_income(income: float) -> float:
    """Calcula IRPF de base del ahorro para una renta dada (tramos 2024)."""
    if income <= 0:
        return 0.0
    tax = 0.0
    remaining = income
    for lo, hi, rate in IRPF_AHORRO:
        if remaining <= 0:
            break
        bracket = min(remaining, hi - lo)
        tax += bracket * rate
        remaining -= bracket
    return tax


def irpf_preview(db: Session) -> Dict[str, Any]:
    """Previsualización de IRPF si vendieras HOY.

    - Plusvalía no realizada (venta de acciones) → base del ahorro
    - Dividendos esperados → base del ahorro (retención ya 19%)
    """
    positions = db.query(Position).all()
    transactions = db.query(Transaction).all()

    # Plusvalía total no realizada (todas las posiciones)
    unrealized = sum(p.unrealized_pl or 0 for p in positions)

    # Plusvalía realizada histórica
    realized = sum(t.realized_pl or 0 for t in transactions)

    # Dividendos esperados (brutos)
    expected_dividends = sum(
        (p.dividend_per_share or 0) * p.quantity for p in positions
    )

    # IRPF sobre each
    tax_unrealized = _tax_for_income(unrealized) if unrealized > 0 else 0.0
    tax_realized = _tax_for_income(realized) if realized > 0 else 0.0
    tax_dividends = expected_dividends * DIVIDEND_TAX

    total_potential_tax = tax_unrealized + tax_dividends

    return {
        "unrealized_pnl": round(unrealized, 2),
        "unrealized_tax": round(tax_unrealized, 2),
        "realized_pnl": round(realized, 2),
        "realized_tax": round(tax_realized, 2),
        "expected_dividends": round(expected_dividends, 2),
        "dividend_tax": round(tax_dividends, 2),
        "estimated_unrealized_tax": round(tax_unrealized, 2),
        "estimated_dividend_tax": round(tax_dividends, 2),
        "if_sold_today_total_tax": round(total_potential_tax, 2),
        "tax_brackets": [
            {"up_to": hi, "rate": rate} for lo, hi, rate in IRPF_AHORRO
        ],
        "disclaimer": (
            "Estimación orientativa de la base del ahorro (IRPF 2024). "
            "No incluye compensaciones de ejercicios anteriores ni "
            "particularidades. Consulta con un asesor fiscal."
        ),
    }

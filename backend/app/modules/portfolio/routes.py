"""Routes del Portfolio Tracker — KPIs, allocation, TWR vs SP500, IRPF, precios en vivo."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.portfolio.calculations import (
    allocation_by_sector,
    allocation_by_ticker,
    irpf_preview,
    portfolio_kpis,
    twr_series,
)
from app.modules.portfolio.importer import parse_portfolio_excel
from app.modules.portfolio.models import Position, Transaction
from app.modules.portfolio.analytics import portfolio_analytics


logger = logging.getLogger("finhub.portfolio.routes")

router = APIRouter()


# ======================= IMPORT =======================

@router.post("/import")
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Solo .xlsx/.xlsm")

    content = await file.read()
    result = parse_portfolio_excel(content)
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    positions_imported = 0
    for pos_data in result["positions"]:
        existing = db.query(Position).filter(Position.ticker == pos_data["ticker"]).first()
        if existing:
            for f, v in pos_data.items():
                setattr(existing, f, v)
        else:
            db.add(Position(**pos_data))
        positions_imported += 1

    transactions_imported = 0
    for tx in result["transactions"]:
        dup = (
            db.query(Transaction)
            .filter(
                Transaction.ticker == tx["ticker"],
                Transaction.realized_pl == tx["realized_pl"],
                Transaction.notes == tx["notes"],
            )
            .first()
        )
        if dup:
            continue
        db.add(Transaction(**tx))
        transactions_imported += 1

    db.commit()
    return {
        "positions_imported": positions_imported,
        "transactions_imported": transactions_imported,
        "warnings": result["warnings"],
    }


# ======================= POSICIONES =======================

def _position_to_dict(p: Position) -> dict:
    return {
        "id": p.id,
        "ticker": p.ticker,
        "name": p.name,
        "quantity": p.quantity,
        "avg_price": p.avg_price,
        "current_price": p.current_price,
        "target_price": p.target_price,
        "beta": p.beta,
        "dividend_per_share": p.dividend_per_share,
        "realized_pl": p.realized_pl,
        "currency": p.currency,
        "sector": p.sector,
        "market_value": p.market_value,
        "cost_basis": p.cost_basis,
        "unrealized_pl": p.unrealized_pl,
        "unrealized_pl_pct": p.unrealized_pl_pct,
    }


@router.get("/positions")
def list_positions(db: Session = Depends(get_db)) -> List[dict]:
    positions = db.query(Position).order_by(Position.ticker).all()
    return [_position_to_dict(p) for p in positions]


@router.delete("/positions/{ticker}")
def delete_position(ticker: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.ticker == ticker.upper()).first()
    if not pos:
        raise HTTPException(status_code=404, detail=f"No existe {ticker}")
    db.delete(pos)
    db.commit()
    return {"deleted": ticker.upper()}


# ======================= MÉTRICAS (getquin/InvestingPro style) =======================

@router.get("/kpis")
def kpis(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """KPIs globales: valor, G/P, beta ponderada, PER, dividendos."""
    return portfolio_kpis(db)


@router.get("/allocation")
def allocation(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Allocation por sector y por ticker (para gráficos donut)."""
    return {
        "by_sector": allocation_by_sector(db),
        "by_ticker": allocation_by_ticker(db),
    }


@router.get("/performance")
def performance(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """TWR del portfolio vs S&P 500 (serie mensual)."""
    return twr_series(db)


@router.get("/irpf")
def irpf(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Preview de IRPF (base del ahorro) si vendieras hoy."""
    return irpf_preview(db)


@router.get("/overview")
def portfolio_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Todo en una llamada para el dashboard: KPIs + allocation + performance + IRPF."""
    return {
        "kpis": portfolio_kpis(db),
        "allocation": {
            "by_sector": allocation_by_sector(db),
            "by_ticker": allocation_by_ticker(db),
        },
        "performance": twr_series(db),
        "irpf": irpf_preview(db),
    }


from app.modules.portfolio.live_prices import refresh_all_prices

@router.post("/refresh-prices")
def refresh_prices(db: Session = Depends(get_db)):
    """Actualiza los precios de todas las posiciones ahora mismo."""
    result = refresh_all_prices(db)
    return {"status": "ok", **result}


# ======================= SUMMARY (compat con frontend) =======================

@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Summary para el frontend actual (compatibilidad)."""
    k = portfolio_kpis(db)
    positions = db.query(Position).all()
    total_realized = sum(t.realized_pl or 0 for t in db.query(Transaction).all())
    return {
        "num_positions": k["num_positions"],
        "total_value": k["total_value"],
        "total_cost": k["total_cost"],
        "total_unrealized_pl": k["total_unrealized_pl"],
        "total_unrealized_pl_pct": k["total_unrealized_pl_pct"],
        "total_realized_pl": round(total_realized, 2),
    }


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    """Métricas de riesgo premium: Sharpe, Sortino, drawdown, beta, concentración."""
    return portfolio_analytics(db)




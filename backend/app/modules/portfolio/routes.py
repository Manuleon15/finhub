"""Routes del Portfolio Tracker — completo."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.portfolio.analytics import portfolio_analytics
from app.modules.portfolio.calculations import (
    allocation_by_sector,
    allocation_by_ticker,
    irpf_preview,
    portfolio_kpis,
    twr_series,
)
from app.modules.portfolio.importer import parse_portfolio_excel
from app.modules.portfolio.live_prices import refresh_all_prices
from app.modules.portfolio.models import MonthlySnapshot, Position, Transaction

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

    pos_count = 0
    for pos_data in result["positions"]:
        existing = db.query(Position).filter(Position.ticker == pos_data["ticker"]).first()
        if existing:
            for f, v in pos_data.items():
                setattr(existing, f, v)
        else:
            db.add(Position(**pos_data))
        pos_count += 1

    tx_count = 0
    for tx in result["transactions"]:
        dup = db.query(Transaction).filter(
            Transaction.ticker == tx["ticker"],
            Transaction.realized_pl == tx["realized_pl"],
        ).first()
        if dup:
            continue
        db.add(Transaction(**tx))
        tx_count += 1

    # Guardar snapshots mensuales
    snap_count = 0
    for s in result.get("monthly_snapshots", []):
        exists = db.query(MonthlySnapshot).filter(
            MonthlySnapshot.year == s["year"],
            MonthlySnapshot.month == s["month"],
        ).first()
        if exists:
            exists.portfolio_value = s["portfolio_value"] or 0
            exists.portfolio_twr_month = s["portfolio_twr_month"]
            exists.sp500_twr_month = s["sp500_twr_month"]
        else:
            db.add(MonthlySnapshot(**s))
        snap_count += 1

    db.commit()
    return {
        "positions_imported": pos_count,
        "transactions_imported": tx_count,
        "monthly_snapshots_saved": snap_count,
        "warnings": result["warnings"],
    }


# ======================= POSICIONES =======================

def _pos_dict(p: Position) -> dict:
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
def positions(db: Session = Depends(get_db)) -> List[dict]:
    return [_pos_dict(p) for p in db.query(Position).order_by(Position.ticker).all()]


@router.delete("/positions/{ticker}")
def delete_position(ticker: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.ticker == ticker.upper()).first()
    if not pos:
        raise HTTPException(status_code=404, detail=f"No existe {ticker}")
    db.delete(pos)
    db.commit()
    return {"deleted": ticker.upper()}


# ======================= MÉTRICAS =======================

@router.get("/kpis")
def kpis(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return portfolio_kpis(db)


@router.get("/allocation")
def allocation(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"by_sector": allocation_by_sector(db), "by_ticker": allocation_by_ticker(db)}


@router.get("/performance")
def performance(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return twr_series(db)


@router.get("/irpf")
def irpf(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return irpf_preview(db)


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    k = portfolio_kpis(db)
    realized = sum(t.realized_pl or 0 for t in db.query(Transaction).all())
    return {
        "num_positions": k["num_positions"],
        "total_value": k["total_value"],
        "total_cost": k["total_cost"],
        "total_unrealized_pl": k["total_unrealized_pl"],
        "total_unrealized_pl_pct": k["total_unrealized_pl_pct"],
        "total_realized_pl": round(realized, 2),
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {
        "kpis": portfolio_kpis(db),
        "allocation": {
            "by_sector": allocation_by_sector(db),
            "by_ticker": allocation_by_ticker(db),
        },
        "performance": twr_series(db),
        "irpf": irpf_preview(db),
    }


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return portfolio_analytics(db)


@router.post("/refresh-prices")
def refresh_prices(db: Session = Depends(get_db)):
    return {"status": "ok", **refresh_all_prices(db)}

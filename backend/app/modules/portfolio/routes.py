"""Routes del Portfolio Tracker."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.portfolio.importer import parse_portfolio_excel
from app.modules.portfolio.models import Position, Transaction

logger = logging.getLogger("finhub.portfolio.routes")

router = APIRouter()


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
        "market_value": p.market_value,
        "cost_basis": p.cost_basis,
        "unrealized_pl": p.unrealized_pl,
        "unrealized_pl_pct": p.unrealized_pl_pct,
    }


@router.post("/import")
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Sube tu Excel de portfolio. Reemplaza (upsert por ticker) las posiciones
    y añade las transacciones nuevas encontradas en las hojas MOVIMIENTOS.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xlsx/.xlsm")

    content = await file.read()
    result = parse_portfolio_excel(content)

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    positions_imported = 0
    for pos_data in result["positions"]:
        existing = db.query(Position).filter(Position.ticker == pos_data["ticker"]).first()
        if existing:
            for field, value in pos_data.items():
                setattr(existing, field, value)
        else:
            db.add(Position(**pos_data))
        positions_imported += 1

    transactions_imported = 0
    for tx_data in result["transactions"]:
        # Evitar duplicar si ya se importó exactamente esta transacción antes
        dup = (
            db.query(Transaction)
            .filter(
                Transaction.ticker == tx_data["ticker"],
                Transaction.realized_pl == tx_data["realized_pl"],
                Transaction.notes == tx_data["notes"],
            )
            .first()
        )
        if dup:
            continue
        db.add(Transaction(**tx_data))
        transactions_imported += 1

    db.commit()

    return {
        "positions_imported": positions_imported,
        "transactions_imported": transactions_imported,
        "warnings": result["warnings"],
    }


@router.get("/positions")
def list_positions(db: Session = Depends(get_db)) -> List[dict]:
    positions = db.query(Position).order_by(Position.ticker).all()
    return [_position_to_dict(p) for p in positions]


@router.get("/summary")
def portfolio_summary(db: Session = Depends(get_db)) -> dict:
    positions = db.query(Position).all()

    total_value = sum(p.market_value or 0 for p in positions)
    total_cost = sum(p.cost_basis or 0 for p in positions)
    total_unrealized = total_value - total_cost
    total_unrealized_pct = (total_unrealized / total_cost) if total_cost else None

    total_realized = (
        db.query(Transaction).all()
    )
    realized_sum = sum(t.realized_pl or 0 for t in total_realized)

    return {
        "num_positions": len(positions),
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_unrealized_pl": round(total_unrealized, 2),
        "total_unrealized_pl_pct": round(total_unrealized_pct, 4) if total_unrealized_pct is not None else None,
        "total_realized_pl": round(realized_sum, 2),
    }


@router.delete("/positions/{ticker}")
def delete_position(ticker: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.ticker == ticker.upper()).first()
    if not pos:
        raise HTTPException(status_code=404, detail=f"No existe posición para {ticker}")
    db.delete(pos)
    db.commit()
    return {"deleted": ticker.upper()}

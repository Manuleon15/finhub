"""Modelos SQLAlchemy del Portfolio Tracker.

Tres tablas:
- Account: cuenta/broker (IBKR, TR, etc.) — opcional, útil si operas en varios sitios.
- Position: posición actual por ticker (lo que hoy tienes en la pestaña "DATOS INVERSIONES").
- Transaction: histórico de compra/venta (lo que hoy tienes en "MOVIMIENTOS 2025/2026").
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Account(Base):
    """Cuenta o broker (IBKR, Trade Republic, etc.). Opcional."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    broker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    positions: Mapped[list["Position"]] = relationship(back_populates="account")


class Position(Base):
    """Posición actual en un activo. Una fila por ticker (se sobreescribe al reimportar)."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    ticker: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # precio de compra medio
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pl: Mapped[float | None] = mapped_column(Float, nullable=True)  # P/G realizadas

    currency: Mapped[str] = mapped_column(String(10), default="USD")
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    account: Mapped["Account | None"] = relationship(back_populates="positions")

    # --- Propiedades calculadas (no se guardan en DB) ---
    @property
    def market_value(self) -> float | None:
        if self.current_price is None:
            return None
        return round(self.quantity * self.current_price, 2)

    @property
    def cost_basis(self) -> float | None:
        if self.avg_price is None:
            return None
        return round(self.quantity * self.avg_price, 2)

    @property
    def unrealized_pl(self) -> float | None:
        mv, cb = self.market_value, self.cost_basis
        if mv is None or cb is None:
            return None
        return round(mv - cb, 2)

    @property
    def unrealized_pl_pct(self) -> float | None:
        cb = self.cost_basis
        pl = self.unrealized_pl
        if cb is None or pl is None or cb == 0:
            return None
        return round(pl / cb, 4)


class Transaction(Base):
    """Movimiento histórico: compra o venta de un ticker."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    tx_type: Mapped[str] = mapped_column(String(10))  # "buy" | "sell"

    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pl: Mapped[float | None] = mapped_column(Float, nullable=True)

    date: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)



class MonthlySnapshot(Base):
    """Snapshot mensual del portfolio para el gráfico TWR vs S&P 500."""

    __tablename__ = "monthly_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)  # 1-12
    portfolio_value: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_twr_month: Mapped[float] = mapped_column(Float, default=0.0)
    sp500_twr_month: Mapped[float] = mapped_column(Float, default=0.0)
    invested_in_period: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_twr_ytd: Mapped[float] = mapped_column(Float, default=0.0)
    sp500_twr_ytd: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String, default="USD")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


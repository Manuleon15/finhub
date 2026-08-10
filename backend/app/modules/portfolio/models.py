"""Modelos SQLAlchemy para el Portfolio Tracker.

Tablas:
- Account: cuentas de broker (IBKR, Quantfury, Trade Republic, etc.)
- Position: posición abierta
- Transaction: movimientos (compra, venta, dividendo)
- MonthlySnapshot: snapshot mensual para TWR vs SP500
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    broker: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    positions: Mapped[list["Position"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    buy_price: Mapped[float] = mapped_column(Float)
    buy_date: Mapped[date] = mapped_column(Date, default=date.today)
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    beta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    per: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dividend_per_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    target_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["Account"] = relationship(back_populates="positions")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="position")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    position_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("positions.id"), nullable=True, index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    type: Mapped[str] = mapped_column(String(16))  # buy, sell, dividend
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    position: Mapped[Optional["Position"]] = relationship(back_populates="transactions")


class MonthlySnapshot(Base):
    __tablename__ = "monthly_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    portfolio_value: Mapped[float] = mapped_column(Float)
    portfolio_twr_month: Mapped[float] = mapped_column(Float)
    sp500_twr_month: Mapped[float] = mapped_column(Float)
    invested_in_period: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_twr_ytd: Mapped[float] = mapped_column(Float)
    sp500_twr_ytd: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

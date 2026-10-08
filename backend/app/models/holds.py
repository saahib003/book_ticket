"""Temporary seat reservations."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SeatHold(db.Model):
    __tablename__ = "seat_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    items: Mapped[list["HoldItem"]] = relationship(back_populates="hold", cascade="all, delete-orphan")


class HoldItem(db.Model):
    __tablename__ = "hold_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    hold_id: Mapped[str] = mapped_column(ForeignKey("seat_holds.id"), nullable=False)
    show_seat_id: Mapped[int] = mapped_column(ForeignKey("show_seats.id"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    hold: Mapped[SeatHold] = relationship(back_populates="items")
    show_seat: Mapped["ShowSeat"] = relationship(back_populates="hold_items")
    __table_args__ = (db.UniqueConstraint("hold_id", "show_seat_id", name="uq_hold_items_hold_seat"),)


class IdempotencyRecord(db.Model):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (db.UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_idempotency_scope"),)


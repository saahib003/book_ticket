"""Bookings, payments, webhook deduplication, and outbox records."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Booking(db.Model):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=False, index=True)
    hold_id: Mapped[str] = mapped_column(ForeignKey("seat_holds.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_PAYMENT", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    items: Mapped[list["BookingItem"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    show: Mapped["Show"] = relationship()
    __table_args__ = (db.UniqueConstraint("user_id", "idempotency_key", name="uq_bookings_user_idempotency"),)


class BookingItem(db.Model):
    __tablename__ = "booking_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    show_seat_id: Mapped[int] = mapped_column(ForeignKey("show_seats.id"), nullable=False)
    seat_label: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    booking: Mapped[Booking] = relationship(back_populates="items")
    __table_args__ = (db.UniqueConstraint("booking_id", "show_seat_id", name="uq_booking_items_booking_seat"),)


class Payment(db.Model):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="SIMULATED")
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="INITIATED", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    booking: Mapped[Booking] = relationship(back_populates="payments")


class WebhookEvent(db.Model):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_event_id: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RECEIVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutboxEvent(db.Model):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BookingAuditLog(db.Model):
    __tablename__ = "booking_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    booking_id: Mapped[str] = mapped_column(String(36), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_EMAIL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

"""Catalogue and scheduling models. Availability is added later on show_seats."""

from datetime import datetime, timezone

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Venue(db.Model):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    auditoriums: Mapped[list["Auditorium"]] = relationship(back_populates="venue", cascade="all, delete-orphan")


class Auditorium(db.Model):
    __tablename__ = "auditoriums"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    venue: Mapped[Venue] = relationship(back_populates="auditoriums")
    seats: Mapped[list["Seat"]] = relationship(back_populates="auditorium", cascade="all, delete-orphan")
    shows: Mapped[list["Show"]] = relationship(back_populates="auditorium")

    __table_args__ = (db.UniqueConstraint("venue_id", "name", name="uq_auditoriums_venue_name"),)


class Seat(db.Model):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(primary_key=True)
    auditorium_id: Mapped[int] = mapped_column(ForeignKey("auditoriums.id"), nullable=False, index=True)
    row_label: Mapped[str] = mapped_column(String(10), nullable=False)
    seat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="STANDARD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    auditorium: Mapped[Auditorium] = relationship(back_populates="seats")
    __table_args__ = (db.UniqueConstraint("auditorium_id", "row_label", "seat_number", name="uq_seats_location"),)


class Event(db.Model):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    shows: Mapped[list["Show"]] = relationship(back_populates="event")


class Show(db.Model):
    __tablename__ = "shows"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    auditorium_id: Mapped[int] = mapped_column(ForeignKey("auditoriums.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED", index=True)

    event: Mapped[Event] = relationship(back_populates="shows")
    auditorium: Mapped[Auditorium] = relationship(back_populates="shows")
    show_seats: Mapped[list["ShowSeat"]] = relationship(back_populates="show", cascade="all, delete-orphan")
    __table_args__ = (db.Index("ix_shows_event_starts_at", "event_id", "starts_at"), db.Index("ix_shows_auditorium_starts_at", "auditorium_id", "starts_at"))


class ShowSeat(db.Model):
    """Inventory for one physical seat during one show."""

    __tablename__ = "show_seats"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=False, index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    show: Mapped[Show] = relationship(back_populates="show_seats")
    seat: Mapped[Seat] = relationship()
    hold_items: Mapped[list["HoldItem"]] = relationship(back_populates="show_seat")
    __table_args__ = (db.UniqueConstraint("show_id", "seat_id", name="uq_show_seats_show_seat"), db.Index("ix_show_seats_show_status", "show_id", "status"))

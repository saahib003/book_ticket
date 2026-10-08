"""Read APIs for events and scheduled shows."""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_

from app.auth.routes import require_admin
from app.common.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from app.extensions import db
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue

catalogue_bp = Blueprint("catalogue", __name__, url_prefix="/api/v1")


class EventWriteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=5000)
    category: str = Field(min_length=1, max_length=50)
    language: str = Field(min_length=1, max_length=50)
    duration_minutes: int = Field(gt=0, le=1440)


class VenueWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=500)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class AuditoriumWriteRequest(BaseModel):
    venue_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    row_labels: list[str] = Field(min_length=1, max_length=26)
    seats_per_row: int = Field(gt=0, le=100)


class ShowWriteRequest(BaseModel):
    event_id: int = Field(gt=0)
    auditorium_id: int = Field(gt=0)
    starts_at: datetime
    ends_at: datetime
    booking_opens_at: datetime
    booking_closes_at: datetime
    price: str = Field(default="250.00", pattern=r"^\d+(\.\d{1,2})?$")


def admin_failure(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@catalogue_bp.post("/admin/venues")
def admin_create_venue():
    failure = require_admin()
    if failure:
        return failure
    try:
        body = VenueWriteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return admin_failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)
    venue = Venue(**body.model_dump())
    db.session.add(venue)
    db.session.commit()
    return jsonify({"venue": {"id": venue.id, "name": venue.name, "city": venue.city, "address": venue.address, "timezone": venue.timezone}}), 201


@catalogue_bp.post("/admin/auditoriums")
def admin_create_auditorium():
    failure = require_admin()
    if failure:
        return failure
    try:
        body = AuditoriumWriteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return admin_failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)
    if not db.session.get(Venue, body.venue_id):
        return admin_failure("VENUE_NOT_FOUND", "Venue not found.", 404)
    auditorium = Auditorium(venue_id=body.venue_id, name=body.name)
    for row in body.row_labels:
        if not row.strip() or len(row) > 10:
            return admin_failure("VALIDATION_ERROR", "Row labels must be non-empty and at most 10 characters.", 400)
        for number in range(1, body.seats_per_row + 1):
            auditorium.seats.append(Seat(row_label=row.strip().upper(), seat_number=number, category="STANDARD"))
    db.session.add(auditorium)
    db.session.commit()
    return jsonify({"auditorium": {"id": auditorium.id, "venue_id": auditorium.venue_id, "name": auditorium.name, "seat_count": len(auditorium.seats)}}), 201


@catalogue_bp.post("/admin/shows")
def admin_create_show():
    failure = require_admin()
    if failure:
        return failure
    try:
        body = ShowWriteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return admin_failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)
    if body.ends_at <= body.starts_at or body.booking_closes_at <= body.booking_opens_at:
        return admin_failure("INVALID_SCHEDULE", "Show and booking windows must have a positive duration.", 400)
    event = db.session.get(Event, body.event_id)
    auditorium = db.session.get(Auditorium, body.auditorium_id)
    if not event or event.status != "ACTIVE":
        return admin_failure("EVENT_NOT_FOUND", "Event not found.", 404)
    if not auditorium:
        return admin_failure("AUDITORIUM_NOT_FOUND", "Auditorium not found.", 404)
    if not auditorium.seats:
        return admin_failure("AUDITORIUM_EMPTY", "An auditorium must contain active seats.", 422)
    show = Show(
        event_id=body.event_id,
        auditorium_id=body.auditorium_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        booking_opens_at=body.booking_opens_at,
        booking_closes_at=body.booking_closes_at,
    )
    show.show_seats = [ShowSeat(seat=seat, price=body.price) for seat in auditorium.seats if seat.active]
    db.session.add(show)
    db.session.commit()
    cache_delete(f"catalogue:event:{body.event_id}:shows")
    return jsonify({"show": show_response(show), "seat_count": len(show.show_seats)}), 201


@catalogue_bp.post("/admin/events")
def admin_create_event():
    failure = require_admin()
    if failure:
        return failure
    try:
        body = EventWriteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return admin_failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)
    event = Event(**body.model_dump())
    db.session.add(event)
    db.session.commit()
    cache_delete_pattern("catalogue:events:*")
    return jsonify({"event": event_response(event)}), 201


@catalogue_bp.patch("/admin/events/<int:event_id>")
def admin_update_event(event_id: int):
    failure = require_admin()
    if failure:
        return failure
    event = db.session.get(Event, event_id)
    if not event:
        return admin_failure("EVENT_NOT_FOUND", "Event not found.", 404)
    try:
        body = EventWriteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return admin_failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)
    for key, value in body.model_dump().items():
        setattr(event, key, value)
    db.session.commit()
    cache_delete(f"catalogue:event:{event_id}")
    cache_delete_pattern("catalogue:events:*")
    return jsonify({"event": event_response(event)}), 200


@catalogue_bp.delete("/admin/events/<int:event_id>")
def admin_deactivate_event(event_id: int):
    failure = require_admin()
    if failure:
        return failure
    event = db.session.get(Event, event_id)
    if not event:
        return admin_failure("EVENT_NOT_FOUND", "Event not found.", 404)
    event.status = "INACTIVE"
    db.session.commit()
    cache_delete(f"catalogue:event:{event_id}", f"catalogue:event:{event_id}:shows")
    cache_delete_pattern("catalogue:events:*")
    return "", 204


def event_response(event: Event) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "language": event.language,
        "duration_minutes": event.duration_minutes,
        "status": event.status,
    }


def show_response(show: Show) -> dict:
    return {
        "id": show.id,
        "event_id": show.event_id,
        "event_title": show.event.title,
        "venue": {"id": show.auditorium.venue.id, "name": show.auditorium.venue.name, "city": show.auditorium.venue.city},
        "auditorium": {"id": show.auditorium.id, "name": show.auditorium.name},
        "starts_at": show.starts_at.isoformat(),
        "ends_at": show.ends_at.isoformat(),
        "booking_opens_at": show.booking_opens_at.isoformat(),
        "booking_closes_at": show.booking_closes_at.isoformat(),
        "status": show.status,
    }


@catalogue_bp.get("/events")
def list_events():
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 20, type=int), 1), 100)
    cache_key = f"catalogue:events:{request.query_string.decode()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200
    query = db.select(Event).where(Event.status == "ACTIVE")
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Event.title.ilike(pattern), Event.description.ilike(pattern)))
    if category := request.args.get("category"):
        query = query.where(Event.category == category)
    if language := request.args.get("language"):
        query = query.where(Event.language == language)
    if city := request.args.get("city", "").strip():
        pattern = f"%{city}%"
        query = query.join(Event.shows).join(Show.auditorium).join(Auditorium.venue).where(
            Show.status == "SCHEDULED", Venue.city.ilike(pattern)
        ).distinct()

    total = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    events = db.session.scalars(query.order_by(Event.id).offset((page - 1) * page_size).limit(page_size)).all()
    response = {"items": [event_response(event) for event in events], "page": page, "page_size": page_size, "total": total}
    cache_set(cache_key, response, current_app.config["EVENT_CACHE_TTL_SECONDS"])
    return jsonify(response), 200


@catalogue_bp.get("/cities")
def list_cities():
    """Return cities that currently have active events with scheduled shows."""
    cities = db.session.scalars(
        db.select(Venue.city)
        .join(Auditorium)
        .join(Show)
        .join(Event)
        .where(Event.status == "ACTIVE", Show.status == "SCHEDULED")
        .distinct()
        .order_by(Venue.city)
    ).all()
    return jsonify({"items": cities}), 200


@catalogue_bp.get("/events/<int:event_id>")
def event_detail(event_id: int):
    cache_key = f"catalogue:event:{event_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200
    event = db.session.get(Event, event_id)
    if not event or event.status != "ACTIVE":
        return jsonify({"error": {"code": "EVENT_NOT_FOUND", "message": "Event not found."}}), 404
    response = {"event": event_response(event)}
    cache_set(cache_key, response, current_app.config["EVENT_CACHE_TTL_SECONDS"])
    return jsonify(response), 200


@catalogue_bp.get("/events/<int:event_id>/shows")
def event_shows(event_id: int):
    cache_key = f"catalogue:event:{event_id}:shows"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200
    event = db.session.get(Event, event_id)
    if not event or event.status != "ACTIVE":
        return jsonify({"error": {"code": "EVENT_NOT_FOUND", "message": "Event not found."}}), 404
    shows = db.session.scalars(db.select(Show).where(Show.event_id == event_id, Show.status == "SCHEDULED").order_by(Show.starts_at)).all()
    response = {"event": event_response(event), "items": [show_response(show) for show in shows]}
    cache_set(cache_key, response, current_app.config["SHOW_CACHE_TTL_SECONDS"])
    return jsonify(response), 200


@catalogue_bp.get("/shows/<int:show_id>")
def show_detail(show_id: int):
    show = db.session.get(Show, show_id)
    if not show or show.status != "SCHEDULED" or show.event.status != "ACTIVE":
        return jsonify({"error": {"code": "SHOW_NOT_FOUND", "message": "Show not found."}}), 404
    return jsonify({"show": show_response(show)}), 200


@catalogue_bp.get("/shows/<int:show_id>/seats")
def show_seats(show_id: int):
    cache_key = f"catalogue:show:{show_id}:seats"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200
    show = db.session.get(Show, show_id)
    if not show or show.status != "SCHEDULED" or show.event.status != "ACTIVE":
        return jsonify({"error": {"code": "SHOW_NOT_FOUND", "message": "Show not found."}}), 404
    inventory = db.session.scalars(
        db.select(ShowSeat).where(ShowSeat.show_id == show_id).order_by(ShowSeat.seat_id)
    ).all()
    response = {
        "show_id": show_id,
        "items": [
            {
                "show_seat_id": item.id,
                "seat_id": item.seat_id,
                "row_label": item.seat.row_label,
                "seat_number": item.seat.seat_number,
                "category": item.seat.category,
                "price": str(item.price),
                "status": item.status,
                "version": item.version,
            }
            for item in inventory
        ],
    }
    cache_set(cache_key, response, current_app.config["SEAT_MAP_CACHE_TTL_SECONDS"])
    return jsonify(response), 200

"""Concurrency-safe seat hold endpoint."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from flask import Blueprint, current_app, jsonify, request, g
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError

from app.auth.routes import require_access_token
from app.common.cache import cache_delete
from app.extensions import db
from app.models import HoldItem, IdempotencyRecord, SeatHold, Show, ShowSeat
from app.security.rate_limit import enforce_rate_limit
from app.realtime import publish_seat_status

holds_bp = Blueprint("holds", __name__, url_prefix="/api/v1")


class HoldRequest(BaseModel):
    show_seat_ids: list[int] = Field(min_length=1, max_length=10)


def failure(code: str, message: str, status: int, details: dict | None = None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def canonical_hash(body: HoldRequest) -> str:
    encoded = json.dumps(sorted(set(body.show_seat_ids)), separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def hold_response(hold: SeatHold) -> dict:
    return {
        "hold_id": hold.id,
        "show_id": hold.show_id,
        "status": hold.status,
        "expires_at": hold.expires_at.isoformat(),
        "show_seat_ids": [item.show_seat_id for item in hold.items],
        "total": str(sum((item.price for item in hold.items), start=0)),
    }


@holds_bp.post("/shows/<int:show_id>/holds")
def create_hold(show_id: int):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    blocked = enforce_rate_limit("hold", current_app.config["HOLD_RATE_LIMIT"], current_app.config["RATE_LIMIT_WINDOW_SECONDS"], identity=f"user:{g.current_user.id}")
    if blocked:
        return blocked
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return failure("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.", 400)
    try:
        body = HoldRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)

    seat_ids = sorted(set(body.show_seat_ids))
    if len(seat_ids) != len(body.show_seat_ids):
        return failure("DUPLICATE_SEAT_IDS", "Each seat may appear only once.", 400)
    request_hash = canonical_hash(body)

    existing = db.session.scalar(db.select(IdempotencyRecord).where(
        IdempotencyRecord.user_id == g.current_user.id,
        IdempotencyRecord.operation == "CREATE_HOLD",
        IdempotencyRecord.idempotency_key == key,
    ))
    if existing:
        if existing.request_hash != request_hash:
            return failure("IDEMPOTENCY_KEY_REUSED", "The key was used with a different request.", 409)
        return jsonify(existing.response_json), existing.status_code

    now = datetime.now(timezone.utc)
    show = db.session.get(Show, show_id)
    if not show or show.status != "SCHEDULED":
        return failure("SHOW_NOT_FOUND", "Show not found.", 404)
    if now < show.booking_opens_at or now > show.booking_closes_at:
        return failure("BOOKING_CLOSED", "Booking is not currently open for this show.", 422)

    # Lock every requested row in ascending order. This is the critical
    # invariant preventing two concurrent requests from both seeing AVAILABLE.
    seats = db.session.scalars(
        db.select(ShowSeat)
        .where(ShowSeat.show_id == show_id, ShowSeat.id.in_(seat_ids))
        .order_by(ShowSeat.id)
        .with_for_update()
    ).all()
    if len(seats) != len(seat_ids):
        return failure("INVALID_SHOW_SEAT", "One or more seats do not belong to this show.", 400)

    # Lazy expiry runs under the same row locks, so an expired hold cannot race
    # with a new hold for the same inventory row.
    for seat in seats:
        if seat.status == "HELD":
            active_hold = db.session.scalar(db.select(SeatHold).join(HoldItem).where(
                HoldItem.show_seat_id == seat.id, SeatHold.status == "ACTIVE"
            ).with_for_update())
            if active_hold and active_hold.expires_at <= now:
                active_hold.status = "EXPIRED"
                seat.status = "AVAILABLE"
                seat.version += 1

    unavailable = [seat.id for seat in seats if seat.status != "AVAILABLE"]
    if unavailable:
        db.session.rollback()
        return failure("SEATS_UNAVAILABLE", "One or more selected seats are no longer available.", 409, {"unavailable_show_seat_ids": unavailable})

    expires_at = now + timedelta(seconds=current_app.config.get("HOLD_DURATION_SECONDS", 300))
    hold = SeatHold(user_id=g.current_user.id, show_id=show_id, expires_at=expires_at)
    for seat in seats:
        hold.items.append(HoldItem(show_seat=seat, price=seat.price))
        seat.status = "HELD"
        seat.version += 1
    db.session.add(hold)
    db.session.flush()
    response_body = hold_response(hold)
    db.session.add(IdempotencyRecord(user_id=g.current_user.id, operation="CREATE_HOLD", idempotency_key=key, request_hash=request_hash, response_json=response_body, status_code=201))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.scalar(db.select(IdempotencyRecord).where(IdempotencyRecord.user_id == g.current_user.id, IdempotencyRecord.operation == "CREATE_HOLD", IdempotencyRecord.idempotency_key == key))
        if existing and existing.request_hash == request_hash:
            return jsonify(existing.response_json), existing.status_code
        return failure("IDEMPOTENCY_KEY_REUSED", "The key was used with a different request.", 409)

    try:
        current_app.extensions["redis"].setex(f"hold:{hold.id}", int((expires_at - now).total_seconds()), str(g.current_user.id))
    except Exception:
        # Redis is a TTL hint. A failed hint must not undo a committed hold.
        current_app.logger.warning("Could not write Redis TTL hint for hold %s", hold.id)
    cache_delete(f"catalogue:show:{show_id}:seats")
    publish_seat_status(show_id, seat_ids, "HELD", max(seat.version for seat in seats))
    return jsonify(response_body), 201


@holds_bp.get("/holds/<hold_id>")
def get_hold(hold_id: str):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    hold = db.session.get(SeatHold, hold_id)
    if not hold or hold.user_id != g.current_user.id:
        return failure("HOLD_NOT_FOUND", "Hold not found.", 404)
    return jsonify(hold_response(hold)), 200


@holds_bp.delete("/holds/<hold_id>")
def release_hold(hold_id: str):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    hold = db.session.scalar(db.select(SeatHold).where(SeatHold.id == hold_id).with_for_update())
    if not hold or hold.user_id != g.current_user.id:
        return failure("HOLD_NOT_FOUND", "Hold not found.", 404)
    if hold.status != "ACTIVE":
        return jsonify(hold_response(hold)), 200

    seat_ids = sorted(item.show_seat_id for item in hold.items)
    seats = db.session.scalars(db.select(ShowSeat).where(ShowSeat.id.in_(seat_ids)).order_by(ShowSeat.id).with_for_update()).all()
    for seat in seats:
        if seat.status == "HELD":
            seat.status = "AVAILABLE"
            seat.version += 1
    hold.status = "RELEASED"
    db.session.commit()
    try:
        current_app.extensions["redis"].delete(f"hold:{hold.id}")
    except Exception:
        current_app.logger.warning("Could not remove Redis TTL hint for hold %s", hold.id)
    cache_delete(f"catalogue:show:{hold.show_id}:seats")
    publish_seat_status(hold.show_id, seat_ids, "AVAILABLE", max((seat.version for seat in seats), default=0))
    return jsonify(hold_response(hold)), 200

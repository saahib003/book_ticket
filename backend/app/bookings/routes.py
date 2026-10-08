"""Pending booking, simulated payment, and atomic confirmation workflows."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError

from app.auth.routes import require_access_token
from app.common.cache import cache_delete
from app.extensions import db
from app.models import Booking, BookingAuditLog, BookingItem, HoldItem, OutboxEvent, Payment, SeatHold, ShowSeat, WebhookEvent
from app.realtime import publish_seat_status

bookings_bp = Blueprint("bookings", __name__, url_prefix="/api/v1")


class CreateBookingRequest(BaseModel):
    hold_id: str = Field(min_length=36, max_length=36)


class CreatePaymentRequest(BaseModel):
    booking_id: str = Field(min_length=36, max_length=36)


def failure(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def is_expired(value) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)


def booking_response(booking: Booking) -> dict:
    return {"booking_id": booking.id, "booking_reference": booking.booking_reference, "show_id": booking.show_id, "status": booking.status, "amount": str(booking.amount), "currency": booking.currency, "items": [{"show_seat_id": item.show_seat_id, "seat_label": item.seat_label, "unit_price": str(item.unit_price), "is_active": item.is_active} for item in booking.items]}


@bookings_bp.post("/bookings")
def create_booking():
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return failure("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.", 400)
    try:
        body = CreateBookingRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)

    existing = db.session.scalar(db.select(Booking).where(Booking.user_id == g.current_user.id, Booking.idempotency_key == key))
    if existing:
        return jsonify(booking_response(existing)), 200

    hold = db.session.scalar(db.select(SeatHold).where(SeatHold.id == body.hold_id).with_for_update())
    if not hold or hold.user_id != g.current_user.id:
        return failure("HOLD_NOT_FOUND", "Hold not found.", 404)
    if hold.status != "ACTIVE" or is_expired(hold.expires_at):
        return failure("HOLD_EXPIRED", "The hold is no longer active.", 422)

    items = sorted(hold.items, key=lambda item: item.show_seat_id)
    amount = sum((item.price for item in items), start=0)
    booking = Booking(booking_reference=f"BK-{uuid4().hex[:10].upper()}", user_id=g.current_user.id, show_id=hold.show_id, hold_id=hold.id, status="PENDING_PAYMENT", amount=amount, currency="INR", idempotency_key=key)
    for item in items:
        seat = item.show_seat.seat
        booking.items.append(BookingItem(show_seat_id=item.show_seat_id, seat_label=f"{seat.row_label}{seat.seat_number}", unit_price=item.price))
    db.session.add(booking)
    db.session.commit()
    return jsonify(booking_response(booking)), 201


@bookings_bp.post("/payments")
def create_payment():
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return failure("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.", 400)
    try:
        body = CreatePaymentRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return failure("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)

    existing = db.session.scalar(db.select(Payment).where(Payment.idempotency_key == key))
    if existing:
        return jsonify({"payment_id": existing.id, "booking_id": existing.booking_id, "status": existing.status, "amount": str(existing.amount), "currency": existing.currency}), 200
    booking = db.session.get(Booking, body.booking_id)
    if not booking or booking.user_id != g.current_user.id:
        return failure("BOOKING_NOT_FOUND", "Booking not found.", 404)
    if booking.status != "PENDING_PAYMENT":
        return failure("BOOKING_NOT_PAYABLE", "Booking is not awaiting payment.", 422)
    payment = Payment(booking_id=booking.id, amount=booking.amount, currency=booking.currency, status="INITIATED", idempotency_key=key, provider=current_app.config["PAYMENT_PROVIDER"])
    if payment.provider == "RAZORPAY":
        if not current_app.config["RAZORPAY_KEY_ID"] or not current_app.config["RAZORPAY_KEY_SECRET"]:
            return failure("PAYMENT_PROVIDER_NOT_CONFIGURED", "Razorpay credentials are not configured.", 503)
        try:
            import razorpay
            client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]))
            order = client.order.create(data={"amount": int(booking.amount * 100), "currency": booking.currency, "receipt": booking.booking_reference})
            payment.provider_order_id = order["id"]
        except Exception:
            db.session.rollback()
            return failure("PAYMENT_PROVIDER_UNAVAILABLE", "Razorpay could not create an order.", 503)
    db.session.add(payment)
    db.session.commit()
    return jsonify({"payment_id": payment.id, "booking_id": payment.booking_id, "status": payment.status, "amount": str(payment.amount), "currency": payment.currency, "provider": payment.provider, "provider_order_id": payment.provider_order_id, "razorpay_key_id": current_app.config["RAZORPAY_KEY_ID"] if payment.provider == "RAZORPAY" else None}), 201


@bookings_bp.post("/payments/<payment_id>/simulate")
def simulate_payment(payment_id: str):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.booking.user_id != g.current_user.id:
        return failure("PAYMENT_NOT_FOUND", "Payment not found.", 404)
    outcome = (request.get_json(silent=True) or {}).get("outcome", "success").upper()
    if outcome not in {"SUCCESS", "FAILED"}:
        return failure("INVALID_PAYMENT_OUTCOME", "Outcome must be SUCCESS or FAILED.", 400)
    return process_payment_event(payment_id, outcome, f"sim-{uuid4()}")


@bookings_bp.post("/payments/<payment_id>/verify")
def verify_payment(payment_id: str):
    """Verify the Checkout response before applying the existing confirmation flow."""
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.booking.user_id != g.current_user.id or payment.provider != "RAZORPAY":
        return failure("PAYMENT_NOT_FOUND", "Payment not found.", 404)
    body = request.get_json(silent=True) or {}
    order_id = str(body.get("razorpay_order_id", ""))
    payment_id_from_provider = str(body.get("razorpay_payment_id", ""))
    signature = str(body.get("razorpay_signature", ""))
    if order_id != payment.provider_order_id or not payment_id_from_provider or not signature:
        return failure("INVALID_PAYMENT_RESPONSE", "The Razorpay payment response is incomplete or mismatched.", 400)
    expected = hmac.new(current_app.config["RAZORPAY_KEY_SECRET"].encode(), f"{payment.provider_order_id}|{payment_id_from_provider}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return failure("INVALID_PAYMENT_SIGNATURE", "Razorpay signature verification failed.", 400)
    payment.provider_payment_id = payment_id_from_provider
    return process_payment_event(payment_id, "SUCCESS", f"razorpay-handler-{payment_id_from_provider}", provider="RAZORPAY")


@bookings_bp.post("/webhooks/payments")
def payment_webhook():
    payload = request.get_json(silent=True) or {}
    payment_id = payload.get("payment_id")
    event_id = request.headers.get("Provider-Event-Id") or payload.get("provider_event_id")
    outcome = str(payload.get("outcome", "")).upper()
    if not payment_id or not event_id or outcome not in {"SUCCESS", "FAILED"}:
        return failure("INVALID_PAYMENT_WEBHOOK", "payment_id, provider event ID, and valid outcome are required.", 400)
    return process_payment_event(payment_id, outcome, event_id)


@bookings_bp.post("/webhooks/razorpay")
def razorpay_webhook():
    """Verify and process Razorpay's server-to-server webhook."""
    raw_body = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    if not secret or not signature:
        return failure("INVALID_RAZORPAY_WEBHOOK", "Webhook signature is required.", 400)
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return failure("INVALID_RAZORPAY_WEBHOOK", "Webhook signature verification failed.", 400)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return failure("INVALID_RAZORPAY_WEBHOOK", "Webhook body must be valid JSON.", 400)
    event_type = payload.get("event", "")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    provider_order_id = entity.get("order_id")
    payment = db.session.scalar(db.select(Payment).where(Payment.provider_order_id == provider_order_id))
    if not payment:
        return failure("PAYMENT_NOT_FOUND", "Razorpay order is not known to this application.", 404)
    outcome = "SUCCESS" if event_type in {"payment.captured", "order.paid"} else "FAILED" if event_type == "payment.failed" else None
    if not outcome:
        return jsonify({"ignored": True}), 200
    provider_event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest()
    payment.provider_payment_id = entity.get("id") or payment.provider_payment_id
    return process_payment_event(payment.id, outcome, provider_event_id, provider="RAZORPAY", payload=payload)


def process_payment_event(payment_id: str, outcome: str, provider_event_id: str, provider: str = "SIMULATED", payload: dict | None = None):
    existing_event = db.session.scalar(db.select(WebhookEvent).where(WebhookEvent.provider_event_id == provider_event_id))
    if existing_event:
        payment = db.session.get(Payment, payment_id)
        return jsonify({"payment_id": payment_id, "status": payment.status if payment else "UNKNOWN", "duplicate": True}), 200

    payment = db.session.scalar(db.select(Payment).where(Payment.id == payment_id).with_for_update())
    if not payment:
        return failure("PAYMENT_NOT_FOUND", "Payment not found.", 404)
    booking = db.session.scalar(db.select(Booking).where(Booking.id == payment.booking_id).with_for_update())
    hold = db.session.scalar(db.select(SeatHold).where(SeatHold.id == booking.hold_id).with_for_update())
    event = WebhookEvent(provider_event_id=provider_event_id, provider=provider, event_type=f"PAYMENT_{outcome}", payload=payload or {"payment_id": payment_id, "outcome": outcome}, status="PROCESSING")
    db.session.add(event)

    if outcome == "FAILED":
        payment.status = "FAILED"
        payment.failure_reason = "Simulated payment failure"
        if booking.status == "PENDING_PAYMENT":
            booking.status = "PAYMENT_FAILED"
        event.status = "PROCESSED"
        event.processed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"payment_id": payment.id, "booking_id": booking.id, "status": payment.status}), 200

    seat_ids = sorted(item.show_seat_id for item in booking.items)
    seats = db.session.scalars(db.select(ShowSeat).where(ShowSeat.id.in_(seat_ids)).order_by(ShowSeat.id).with_for_update()).all()
    now = datetime.now(timezone.utc)
    if booking.status != "PENDING_PAYMENT" or hold.status != "ACTIVE" or is_expired(hold.expires_at) or any(seat.status != "HELD" for seat in seats):
        payment.status = "REFUND_REQUIRED"
        booking.status = "EXPIRED"
        event.status = "PROCESSED"
        event.processed_at = now
        db.session.commit()
        return jsonify({"payment_id": payment.id, "booking_id": booking.id, "status": payment.status}), 200

    payment.status = "SUCCESS"
    payment.provider_payment_id = f"sim-payment-{uuid4().hex}"
    booking.status = "CONFIRMED"
    hold.status = "CONFIRMED"
    for seat in seats:
        seat.status = "BOOKED"
        seat.version += 1
    db.session.add(BookingAuditLog(booking_id=booking.id, action="CONFIRMED", previous_status="PENDING_PAYMENT", new_status="CONFIRMED", metadata_json={"payment_id": payment.id}))
    db.session.add(OutboxEvent(event_type="BOOKING_CONFIRMED", aggregate_type="BOOKING", aggregate_id=booking.id, payload={"booking_id": booking.id, "user_id": booking.user_id}))
    event.status = "PROCESSED"
    event.processed_at = now
    db.session.commit()
    cache_delete(f"catalogue:show:{booking.show_id}:seats")
    publish_seat_status(booking.show_id, seat_ids, "BOOKED", max((seat.version for seat in seats), default=0))
    return jsonify({"payment_id": payment.id, "booking_id": booking.id, "status": payment.status}), 200


@bookings_bp.get("/bookings")
def list_bookings():
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    bookings = db.session.scalars(db.select(Booking).where(Booking.user_id == g.current_user.id).order_by(Booking.created_at.desc())).all()
    return jsonify({"items": [booking_response(booking) for booking in bookings]}), 200


@bookings_bp.get("/bookings/<booking_id>")
def get_booking(booking_id: str):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != g.current_user.id:
        return failure("BOOKING_NOT_FOUND", "Booking not found.", 404)
    return jsonify(booking_response(booking)), 200


@bookings_bp.post("/bookings/<booking_id>/cancel")
def cancel_booking(booking_id: str):
    auth_failure = require_access_token()
    if auth_failure:
        return auth_failure
    booking = db.session.scalar(db.select(Booking).where(Booking.id == booking_id).with_for_update())
    if not booking or booking.user_id != g.current_user.id:
        return failure("BOOKING_NOT_FOUND", "Booking not found.", 404)
    if booking.status != "CONFIRMED":
        return failure("BOOKING_NOT_CANCELLABLE", "Only confirmed bookings can be cancelled.", 422)
    if booking.show.starts_at <= datetime.now(timezone.utc):
        return failure("CANCELLATION_CLOSED", "This show can no longer be cancelled.", 422)

    seat_ids = sorted(item.show_seat_id for item in booking.items if item.is_active)
    seats = db.session.scalars(db.select(ShowSeat).where(ShowSeat.id.in_(seat_ids)).order_by(ShowSeat.id).with_for_update()).all()
    for item in booking.items:
        item.is_active = False
    for seat in seats:
        seat.status = "AVAILABLE"
        seat.version += 1
    booking.status = "CANCELLED"
    db.session.add(BookingAuditLog(booking_id=booking.id, action="CANCELLED", previous_status="CONFIRMED", new_status="CANCELLED", metadata_json={}))
    db.session.add(OutboxEvent(event_type="BOOKING_CANCELLED", aggregate_type="BOOKING", aggregate_id=booking.id, payload={"booking_id": booking.id, "user_id": booking.user_id}))
    db.session.commit()
    cache_delete(f"catalogue:show:{booking.show_id}:seats")
    publish_seat_status(booking.show_id, seat_ids, "AVAILABLE", max((seat.version for seat in seats), default=0))
    return jsonify(booking_response(booking)), 200

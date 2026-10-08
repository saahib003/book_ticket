from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import Mock

from app.extensions import db
from app.factory import create_app
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue


@pytest.fixture
def booking_client():
    app = create_app("testing")
    app.extensions["redis"] = Mock()
    app.extensions["redis"].incr.return_value = 1
    with app.app_context():
        db.create_all()
        venue = Venue(name="Booking Venue", city="Bengaluru", address="1 Main Road")
        auditorium = Auditorium(name="Screen 1", venue=venue)
        seats = [Seat(row_label="A", seat_number=number) for number in range(1, 4)]
        auditorium.seats.extend(seats)
        event = Event(title="Booking Event", description="Test", category="MUSIC", language="English", duration_minutes=120)
        now = datetime.now(timezone.utc)
        show = Show(event=event, auditorium=auditorium, starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, minutes=120), booking_opens_at=now - timedelta(minutes=1), booking_closes_at=now + timedelta(days=1))
        show.show_seats = [ShowSeat(seat=seat, price="250.00") for seat in seats]
        db.session.add_all([venue, event, show])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def register(client, email):
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery", "full_name": "Customer"})
    return response.get_json()["access_token"]


def create_hold(client, token, seat_id=1):
    return client.post("/api/v1/shows/1/holds", json={"show_seat_ids": [seat_id]}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"hold-{seat_id}"})


def create_booking(client, token, hold_id):
    return client.post("/api/v1/bookings", json={"hold_id": hold_id}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"booking-{hold_id}"})


def create_payment(client, token, booking_id):
    return client.post("/api/v1/payments", json={"booking_id": booking_id}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"payment-{booking_id}"})


def test_successful_payment_confirms_booking_and_is_idempotent(booking_client):
    token = register(booking_client, "buyer@example.com")
    hold = create_hold(booking_client, token).get_json()
    booking = create_booking(booking_client, token, hold["hold_id"]).get_json()
    payment = create_payment(booking_client, token, booking["booking_id"]).get_json()

    success = booking_client.post("/api/v1/webhooks/payments", json={"payment_id": payment["payment_id"], "outcome": "SUCCESS", "provider_event_id": "sim-success"})
    duplicate = booking_client.post("/api/v1/webhooks/payments", json={"payment_id": payment["payment_id"], "outcome": "SUCCESS", "provider_event_id": "sim-success"})

    assert success.status_code == 200
    assert success.get_json()["status"] == "SUCCESS"
    assert duplicate.status_code == 200
    assert booking_client.get(f"/api/v1/shows/1/seats").get_json()["items"][0]["status"] == "BOOKED"


def test_failed_payment_does_not_book_seat(booking_client):
    token = register(booking_client, "failed@example.com")
    hold = create_hold(booking_client, token, 2).get_json()
    booking = create_booking(booking_client, token, hold["hold_id"]).get_json()
    payment = create_payment(booking_client, token, booking["booking_id"]).get_json()
    response = booking_client.post(f"/api/v1/payments/{payment['payment_id']}/simulate", json={"outcome": "failed"}, headers={"Authorization": f"Bearer {token}"})

    assert response.get_json()["status"] == "FAILED"
    assert booking_client.get("/api/v1/shows/1/seats").get_json()["items"][1]["status"] == "HELD"


def test_booking_history_and_cancellation_release_inventory(booking_client):
    token = register(booking_client, "cancel@example.com")
    hold = create_hold(booking_client, token, 3).get_json()
    booking = create_booking(booking_client, token, hold["hold_id"]).get_json()
    payment = create_payment(booking_client, token, booking["booking_id"]).get_json()
    booking_client.post(f"/api/v1/payments/{payment['payment_id']}/simulate", json={"outcome": "SUCCESS"}, headers={"Authorization": f"Bearer {token}"})

    history = booking_client.get("/api/v1/bookings", headers={"Authorization": f"Bearer {token}"})
    cancelled = booking_client.post(f"/api/v1/bookings/{booking['booking_id']}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert history.status_code == 200
    assert history.get_json()["items"][0]["status"] == "CONFIRMED"
    assert cancelled.status_code == 200
    assert cancelled.get_json()["status"] == "CANCELLED"
    assert booking_client.get("/api/v1/shows/1/seats").get_json()["items"][2]["status"] == "AVAILABLE"

from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import Mock

from app.extensions import db
from app.factory import create_app
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue


@pytest.fixture
def hold_client():
    app = create_app("testing")
    app.extensions["redis"] = Mock()
    app.extensions["redis"].incr.return_value = 1
    with app.app_context():
        db.create_all()
        venue = Venue(name="Hold Venue", city="Bengaluru", address="1 Main Road")
        auditorium = Auditorium(name="Screen 1", venue=venue)
        seats = [Seat(row_label="A", seat_number=number) for number in range(1, 4)]
        auditorium.seats.extend(seats)
        event = Event(title="Hold Event", description="Test", category="MUSIC", language="English", duration_minutes=120)
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


def hold(client, token, seat_ids, key):
    return client.post("/api/v1/shows/1/holds", json={"show_seat_ids": seat_ids}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key})


def test_hold_is_atomic_and_idempotent(hold_client):
    token = register(hold_client, "one@example.com")
    first = hold(hold_client, token, [1, 2], "hold-1")
    retry = hold(hold_client, token, [2, 1], "hold-1")

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.get_json() == first.get_json()
    assert first.get_json()["total"] == "500.00"


def test_idempotency_key_cannot_change_request(hold_client):
    token = register(hold_client, "one@example.com")
    assert hold(hold_client, token, [1], "hold-1").status_code == 201
    response = hold(hold_client, token, [2], "hold-1")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_second_user_cannot_hold_same_seat(hold_client):
    first_token = register(hold_client, "one@example.com")
    second_token = register(hold_client, "two@example.com")
    assert hold(hold_client, first_token, [1], "hold-1").status_code == 201
    response = hold(hold_client, second_token, [1], "hold-2")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SEATS_UNAVAILABLE"


def test_redis_failure_does_not_rollback_database_hold(hold_client):
    token = register(hold_client, "redis-down@example.com")
    hold_client.application.extensions["redis"].setex.side_effect = ConnectionError("Redis offline")
    response = hold(hold_client, token, [2], "redis-down-hold")

    assert response.status_code == 201
    assert hold_client.get("/api/v1/shows/1/seats").get_json()["items"][1]["status"] == "HELD"


def test_multi_seat_conflict_rolls_back_available_seat(hold_client):
    first_token = register(hold_client, "rollback-one@example.com")
    second_token = register(hold_client, "rollback-two@example.com")
    assert hold(hold_client, first_token, [1], "rollback-first").status_code == 201
    response = hold(hold_client, second_token, [1, 2], "rollback-second")

    assert response.status_code == 409
    seats = hold_client.get("/api/v1/shows/1/seats").get_json()["items"]
    assert seats[0]["status"] == "HELD"
    assert seats[1]["status"] == "AVAILABLE"

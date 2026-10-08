import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.extensions import db
from app.factory import create_app
from app.models import User


@pytest.fixture
def admin_client():
    app = create_app("testing")
    app.extensions["redis"] = Mock()
    app.extensions["redis"].incr.return_value = 1
    app.extensions["redis"].scan_iter.return_value = iter(())
    with app.app_context():
        db.create_all()
        yield app.test_client(), app
        db.session.remove()
        db.drop_all()


def register(client, email):
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery", "full_name": "Catalogue Manager"})
    return response.get_json()["access_token"], response.get_json()["user"]["id"]


def event_payload(title="New Learning Event"):
    return {"title": title, "description": "Managed by an administrator.", "category": "TALK", "language": "English", "duration_minutes": 90}


def test_customer_cannot_manage_events(admin_client):
    client, _ = admin_client
    token, _ = register(client, "customer-admin-test@example.com")
    response = client.post("/api/v1/admin/events", json=event_payload(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ADMIN_REQUIRED"


def test_admin_can_create_update_and_deactivate_event(admin_client):
    client, app = admin_client
    token, user_id = register(client, "admin-test@example.com")
    with app.app_context():
        db.session.get(User, user_id).role = "ADMIN"
        db.session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/admin/events", json=event_payload(), headers=headers)
    assert created.status_code == 201
    event_id = created.get_json()["event"]["id"]

    updated = client.patch(f"/api/v1/admin/events/{event_id}", json=event_payload("Updated Learning Event"), headers=headers)
    assert updated.status_code == 200
    assert updated.get_json()["event"]["title"] == "Updated Learning Event"

    removed = client.delete(f"/api/v1/admin/events/{event_id}", headers=headers)
    assert removed.status_code == 204
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404


def test_admin_can_create_venue_auditorium_and_show_inventory(admin_client):
    client, app = admin_client
    token, user_id = register(client, "admin-schedule-test@example.com")
    with app.app_context():
        db.session.get(User, user_id).role = "ADMIN"
        db.session.commit()
    headers = {"Authorization": f"Bearer {token}"}

    event = client.post("/api/v1/admin/events", json=event_payload("Scheduled Event"), headers=headers).get_json()["event"]
    venue = client.post("/api/v1/admin/venues", json={"name": "Admin Venue", "city": "Bengaluru", "address": "1 Test Road", "timezone": "Asia/Kolkata"}, headers=headers)
    assert venue.status_code == 201
    auditorium = client.post("/api/v1/admin/auditoriums", json={"venue_id": venue.get_json()["venue"]["id"], "name": "Screen A", "row_labels": ["A", "B"], "seats_per_row": 3}, headers=headers)
    assert auditorium.status_code == 201

    start = datetime.now(timezone.utc) + timedelta(days=1)
    show = client.post("/api/v1/admin/shows", json={"event_id": event["id"], "auditorium_id": auditorium.get_json()["auditorium"]["id"], "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=2)).isoformat(), "booking_opens_at": (start - timedelta(days=1)).isoformat(), "booking_closes_at": (start + timedelta(days=1)).isoformat(), "price": "350.00"}, headers=headers)
    assert show.status_code == 201
    assert show.get_json()["seat_count"] == 6

    seats = client.get(f"/api/v1/shows/{show.get_json()['show']['id']}/seats")
    assert seats.status_code == 200
    assert len(seats.get_json()["items"]) == 6
    assert {seat["price"] for seat in seats.get_json()["items"]} == {"350.00"}

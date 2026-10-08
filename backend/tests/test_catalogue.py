from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.factory import create_app
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue


@pytest.fixture
def catalogue_client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        venue = Venue(name="Central Venue", city="Bengaluru", address="1 Main Road")
        auditorium = Auditorium(name="Screen 1", venue=venue)
        seats = [Seat(row_label="A", seat_number=number) for number in range(1, 4)]
        auditorium.seats.extend(seats)
        now = datetime.now(timezone.utc)
        active = Event(title="Concert Alpha", description="Live music", category="MUSIC", language="English", duration_minutes=120)
        second = Event(title="Movie Beta", description="A film", category="MOVIE", language="Hindi", duration_minutes=140)
        show = Show(event=active, auditorium=auditorium, starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, minutes=120), booking_opens_at=now, booking_closes_at=now + timedelta(days=1))
        show.show_seats = [ShowSeat(seat=seat, price="250.00") for seat in seats]
        db.session.add_all([venue, active, second, show])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_events_support_search_and_pagination(catalogue_client):
    response = catalogue_client.get("/api/v1/events?search=concert&page=1&page_size=1")

    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert [event["title"] for event in body["items"]] == ["Concert Alpha"]


def test_events_support_city_filter_and_city_list(catalogue_client):
    filtered = catalogue_client.get("/api/v1/events?city=bengaluru")
    assert filtered.status_code == 200
    assert [event["title"] for event in filtered.get_json()["items"]] == ["Concert Alpha"]

    cities = catalogue_client.get("/api/v1/cities")
    assert cities.status_code == 200
    assert cities.get_json()["items"] == ["Bengaluru"]


def test_event_shows_include_venue_and_auditorium(catalogue_client):
    response = catalogue_client.get("/api/v1/events/1/shows")

    assert response.status_code == 200
    show = response.get_json()["items"][0]
    assert show["venue"]["city"] == "Bengaluru"
    assert show["auditorium"]["name"] == "Screen 1"


def test_missing_or_inactive_event_returns_not_found(catalogue_client):
    assert catalogue_client.get("/api/v1/events/999").status_code == 404


def test_show_seat_map_returns_show_specific_inventory(catalogue_client):
    response = catalogue_client.get("/api/v1/shows/1/seats")

    assert response.status_code == 200
    items = response.get_json()["items"]
    assert len(items) == 3
    assert items[0]["status"] == "AVAILABLE"
    assert items[0]["price"] == "250.00"


def test_database_operational_failure_returns_dependency_unavailable(catalogue_client, monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("SELECT", {}, RuntimeError("database offline"))

    monkeypatch.setattr(db.session, "scalars", fail)
    response = catalogue_client.get("/api/v1/events")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"

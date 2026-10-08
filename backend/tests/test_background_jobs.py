from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.factory import create_app
from app.models import Auditorium, Event, HoldItem, Seat, SeatHold, Show, ShowSeat, User, Venue
from app.tasks.holds import cleanup_expired_holds


def test_cleanup_expired_hold_releases_seat(monkeypatch):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        user = User(email="expired@example.com", password_hash="not-used", full_name="Expired User")
        venue = Venue(name="Cleanup Venue", city="Bengaluru", address="1 Main Road")
        auditorium = Auditorium(name="Screen 1", venue=venue)
        seat = Seat(row_label="A", seat_number=1, auditorium=auditorium)
        event = Event(title="Cleanup Event", description="Test", category="TEST", language="English", duration_minutes=60)
        now = datetime.now(timezone.utc)
        show = Show(event=event, auditorium=auditorium, starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, minutes=60), booking_opens_at=now - timedelta(hours=1), booking_closes_at=now + timedelta(days=1))
        show_seat = ShowSeat(show=show, seat=seat, price="100.00", status="HELD")
        db.session.add_all([user, venue, event, show, show_seat])
        db.session.flush()
        hold = SeatHold(user_id=user.id, show_id=show.id, expires_at=now - timedelta(minutes=1), status="ACTIVE")
        hold.items.append(HoldItem(show_seat_id=show_seat.id, price="100.00"))
        db.session.add(hold)
        db.session.commit()

        monkeypatch.setattr("app.tasks.holds.create_app", lambda: app)
        assert cleanup_expired_holds.run() == 1
        db.session.expire_all()
        assert db.session.get(SeatHold, hold.id).status == "EXPIRED"
        assert db.session.get(ShowSeat, show_seat.id).status == "AVAILABLE"

        db.session.remove()
        db.drop_all()

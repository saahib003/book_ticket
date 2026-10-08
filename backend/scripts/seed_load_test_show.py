"""Create an isolated 100-seat show for repeatable load experiments."""

from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.factory import create_app
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue


TITLE = "Load Test System Design Live"

app = create_app()
with app.app_context():
    existing = db.session.scalar(db.select(Event).where(Event.title == TITLE))
    if existing and existing.shows:
        show = existing.shows[0]
        available = db.session.scalar(
            db.select(db.func.count(ShowSeat.id)).where(
                ShowSeat.show_id == show.id, ShowSeat.status == "AVAILABLE"
            )
        )
        print(f"Existing load-test show id={show.id}, available_seats={available}")
    else:
        venue = Venue(
            name="Load Test Screens",
            city="Bengaluru",
            address="2 Benchmark Street",
            timezone="Asia/Kolkata",
        )
        auditorium = Auditorium(name="Load Test Screen", venue=venue)
        seats = []
        for row in "ABCDEFGHIJ":
            for number in range(1, 11):
                seat = Seat(row_label=row, seat_number=number, category="STANDARD")
                auditorium.seats.append(seat)
                seats.append(seat)
        event = Event(
            title=TITLE,
            description="Isolated inventory for repeatable load and failure testing.",
            category="TEST",
            language="English",
            duration_minutes=120,
        )
        now = datetime.now(timezone.utc)
        show = Show(
            event=event,
            auditorium=auditorium,
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2, minutes=120),
            booking_opens_at=now - timedelta(minutes=1),
            booking_closes_at=now + timedelta(days=2),
        )
        show.show_seats = [ShowSeat(seat=seat, price="250.00") for seat in seats]
        db.session.add_all([venue, event, show])
        db.session.commit()
        print(f"Inserted load-test event id={event.id}, show id={show.id}, seats={len(seats)}")

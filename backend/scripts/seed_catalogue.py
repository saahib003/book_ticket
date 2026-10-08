"""Insert an idempotent multi-city catalogue for local learning."""

from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.factory import create_app
from app.common.cache import cache_delete_pattern
from app.models import Auditorium, Event, Seat, Show, ShowSeat, Venue


app = create_app()
with app.app_context():
    cities = [
        ("Padhaii Screens Bengaluru", "Bengaluru", "1 Learning Street"),
        ("Padhaii Screens Mumbai", "Mumbai", "22 Knowledge Avenue"),
        ("Padhaii Screens Delhi", "New Delhi", "7 Discovery Road"),
    ]
    venues = []
    for name, city, address in cities:
        venue = db.session.scalar(db.select(Venue).where(Venue.name == name, Venue.city == city))
        if not venue:
            venue = Venue(name=name, city=city, address=address, timezone="Asia/Kolkata")
            db.session.add(venue)
            db.session.flush()
        auditorium = db.session.scalar(db.select(Auditorium).where(Auditorium.venue_id == venue.id, Auditorium.name == "Screen 1"))
        if not auditorium:
            auditorium = Auditorium(name="Screen 1", venue=venue)
            for row in "ABCDEF":
                for number in range(1, 11):
                    auditorium.seats.append(Seat(row_label=row, seat_number=number, category="STANDARD"))
            db.session.add(auditorium)
            db.session.flush()
        venues.append((venue, auditorium))

    event_specs = [
        ("System Design Live", "A practical learning event about scalable systems.", "TALK", "English", 120),
        ("The Last Algorithm", "A suspense drama about a programmer solving one impossible problem.", "MOVIE", "English", 140),
        ("Rhythm of India", "A live celebration of music, dance, and stories from across India.", "CONCERT", "Hindi", 150),
        ("Future Founders", "Meet builders sharing honest lessons from their startup journeys.", "WORKSHOP", "English", 90),
    ]
    events = []
    for title, description, category, language, duration in event_specs:
        event = db.session.scalar(db.select(Event).where(Event.title == title))
        if not event:
            event = Event(title=title, description=description, category=category, language=language, duration_minutes=duration)
            db.session.add(event)
            db.session.flush()
        events.append(event)

    now = datetime.now(timezone.utc)
    created_shows = 0
    for event_index, event in enumerate(events):
        for city_index, (venue, auditorium) in enumerate(venues):
            exists = db.session.scalar(db.select(Show).where(Show.event_id == event.id, Show.auditorium_id == auditorium.id))
            if exists:
                # Keep untouched history safe, but make an unused local demo
                # show bookable when the seed is run on a later day.
                if exists.booking_closes_at <= now and not any(item.status in {"BOOKED", "HELD"} for item in exists.show_seats):
                    starts = now + timedelta(days=1 + event_index * 2, hours=city_index * 3)
                    exists.starts_at = starts
                    exists.ends_at = starts + timedelta(minutes=event.duration_minutes)
                    exists.booking_opens_at = now
                    exists.booking_closes_at = starts - timedelta(minutes=15)
                continue
            starts = now + timedelta(days=1 + event_index * 2, hours=city_index * 3)
            ends = starts + timedelta(minutes=event.duration_minutes)
            show = Show(event=event, auditorium=auditorium, starts_at=starts, ends_at=ends, booking_opens_at=now, booking_closes_at=starts - timedelta(minutes=15))
            show.show_seats = [ShowSeat(seat=seat, price="250.00") for seat in auditorium.seats if seat.active]
            db.session.add(show)
            created_shows += 1

    db.session.commit()
    cache_delete_pattern("catalogue:*")
    print(f"Catalogue ready: {len(events)} events, {len(venues)} cities, created {created_shows} new shows.")

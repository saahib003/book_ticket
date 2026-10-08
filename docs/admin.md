# Admin catalogue management

## What and why

Authentication identifies a user. Authorization decides whether that user may
perform a privileged action. A customer may browse and book; an administrator
may manage catalogue data. Separating these checks prevents a valid customer
token from becoming permission to change the entire catalogue.

## Current API

All endpoints require `Authorization: Bearer <access-token>` and a user whose
database role is `ADMIN`:

- `POST /api/v1/admin/events` creates an active event.
- `PATCH /api/v1/admin/events/{id}` replaces its editable fields.
- `DELETE /api/v1/admin/events/{id}` deactivates it without deleting history.
- `POST /api/v1/admin/venues` creates a venue.
- `POST /api/v1/admin/auditoriums` creates rows of physical seats for a venue.
- `POST /api/v1/admin/shows` schedules an event and materializes one
  `show_seat` inventory row per active auditorium seat.

Event writes validate title, category, language, description, and duration with
Pydantic. After commit, related catalogue caches are invalidated. Deactivation
is a soft delete because historical bookings should retain their references.

Show-seat materialization is done in the same database transaction as show
creation. A physical auditorium seat is reusable across shows, but each show
gets independent status, price, and version fields. Therefore booking a seat
for tonight does not book that physical seat for tomorrow's show.

The frontend displays an Admin workspace only when `/users/me` reports the
`ADMIN` role. The protected create flow is deliberately ordered:

1. Create an event and note its returned event ID.
2. Create a venue and note its returned venue ID.
3. Create an auditorium using the venue ID; this also creates physical seats.
4. Schedule a show using the event ID and auditorium ID; this materializes
   show-specific inventory.

The customer page loads `/cities` for its location selector and sends the
selected city as a `city` filter to `/events`. The seed script creates three
cities and multiple future shows idempotently, so running it again does not
duplicate them.

## Learning commands

Run the authorization tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_admin.py -q
```

The test creates a normal customer and an administrator, proving that the same
authentication mechanism can produce different authorization outcomes.

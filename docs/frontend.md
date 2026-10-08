# Frontend learning guide

The frontend is a React and TypeScript single-page application. Its job is to
present catalogue and inventory state, collect user intent, and call the API.
It is not the authority for seat ownership. The API and PostgreSQL decide
whether a hold or booking is valid.

## User flow

```text
Events -> Event shows -> Seat map -> Hold -> Payment -> Booking history
```

1. `GET /events` loads searchable active events.
2. Selecting an event calls `GET /events/{event_id}/shows`.
3. Selecting a show calls `GET /shows/{show_id}/seats`.
4. The browser keeps selected seat IDs as temporary UI state.
5. Hold sends the selected IDs with a fresh `Idempotency-Key`.
6. Checkout creates a pending booking, creates a payment, and calls the
   simulated success endpoint. Each write has its own idempotency key.
7. Booking history calls `GET /bookings`; cancellation calls the protected
   cancel endpoint and reloads history and seats.
8. A one-second countdown watches `hold.expires_at`. When it reaches zero, the
   UI clears its temporary selection and reloads the authoritative seat map.

## Why state is separated

- `events`, `shows`, and `seats` are server state loaded from the API.
- `selected` is user intent and can be discarded safely.
- `hold` represents a server-created temporary reservation and includes its
  expiry time.
- `busy` prevents confusing duplicate clicks while a request is in flight.
- `eventsLoading` distinguishes an empty catalogue from a request still in
  progress.
- `message` exposes validation, conflict, and recovery feedback to the learner.

The UI disables seats after a hold is created, but this is only a usability
choice. The backend still revalidates the hold in a database transaction,
because a browser can be stale or malicious.

## Realtime behavior

When a show is selected, the browser joins `show:{show_id}` through
Socket.IO. A `SEAT_STATUS_CHANGED` event causes a complete seat-map reload.
The event is an invalidation signal, not an authoritative seat update. This
handles missed messages and reconnects safely.

## Commands

```powershell
cd frontend
npm install
npm run dev -- --host=127.0.0.1
npm run build
```

`npm run build` runs TypeScript compilation and Vite production bundling. A
successful build proves the frontend types and bundle are valid; a browser
smoke test additionally verifies visual layout and live API interaction.

Run `npm test` to execute Vitest. The first tests cover framework-independent
booking rules: countdown behavior after partial seconds, expiry clamping at
zero, and the ten-seat maximum. Keeping these rules in a small domain module
makes them fast to test and prevents UI rendering details from hiding business
behavior.

## Current verification

The production build passes after the browse, show-selection, booking-history,
cancellation, countdown, loading-state, and responsive-layout changes. Browser smoke testing could not
run in the current session because no browser surface was available; the API
and build checks were still completed.

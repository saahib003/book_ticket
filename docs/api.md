# API contracts

All application routes use `/api/v1`.

## Authentication

- `POST /auth/register` creates a customer and returns a user, access token,
  and refresh token.
- `POST /auth/login` authenticates an active user and returns the same token
  pair.
- `POST /auth/refresh` rotates a refresh token. The previous token is revoked.
- `POST /auth/logout` revokes the supplied refresh token and returns `204`.
- `GET /users/me` requires `Authorization: Bearer <access-token>`.

Authentication failures return an object with an `error.code` and message.
Passwords are never included in responses.

## Catalogue

- `GET /events` supports `page`, `page_size`, `search`, `category`, `language`,
  and `city` query parameters.
- `GET /cities` returns cities with active events and scheduled shows.
- `GET /events/{id}` returns an active event.
- `GET /events/{id}/shows` returns scheduled shows with venue and auditorium
  details.
- `GET /shows/{id}` returns one scheduled show.
- `GET /shows/{id}/seats` returns show-specific seat inventory, price, status,
  and version. This is display data; hold creation revalidates in the database.
- `POST /shows/{id}/holds` requires a bearer token and `Idempotency-Key`, and
  atomically holds up to ten available seats for five minutes.
- `GET /holds/{id}` and `DELETE /holds/{id}` allow the owner to inspect or
  release a hold.
- `POST /bookings` creates a pending booking from an owned active hold.
- `GET /bookings` and `GET /bookings/{id}` return booking history and details.
- `POST /payments` starts a payment using the configured provider. In
  `SIMULATED` mode, `POST /payments/{id}/simulate` produces an outcome. In
  `RAZORPAY` mode, the response contains a provider order for Checkout and
  `POST /payments/{id}/verify` validates the Checkout signature.
- `POST /webhooks/payments` remains the simulated callback; production-style
  Razorpay callbacks use `POST /webhooks/razorpay`.
- `POST /bookings/{id}/cancel` releases eligible confirmed seats while
  preserving booking history.

## Example customer sequence

Register:

```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{"email":"customer@example.com","password":"correct horse battery","full_name":"Customer"}
```

Hold seats:

```http
POST /api/v1/shows/1/holds
Authorization: Bearer <access-token>
Idempotency-Key: hold-001
Content-Type: application/json
```

```json
{"show_seat_ids":[1,2]}
```

The response includes `hold_id`, `expires_at`, and the price total. A retry
with the same key and body returns the same response. A different body with
the same key returns `409 IDEMPOTENCY_KEY_REUSED`.

Create a booking with the returned hold ID, start payment with the booking ID,
then simulate success. Booking confirmation changes payment, booking, hold,
show seats, audit history, and the outbox event atomically.

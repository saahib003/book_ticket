# Razorpay Test Mode integration

## What changed

The project supports two payment providers:

- `SIMULATED` remains the default for automated tests and offline learning.
- `RAZORPAY` creates a real Razorpay Test Mode order and opens Razorpay
  Standard Checkout in the browser.

The booking flow is still controlled by our application:

1. The server creates a PostgreSQL seat hold.
2. The server creates a `PENDING_PAYMENT` booking.
3. The server creates a Razorpay order using the booking amount.
4. React opens Checkout using the returned `order_id`.
5. React sends Razorpay's payment ID, order ID, and signature to the server.
6. Flask verifies the HMAC signature with the secret key.
7. The existing locked, atomic confirmation flow marks the booking confirmed.

The browser never receives `RAZORPAY_KEY_SECRET`.

## Configure Test Mode

Copy the backend environment template if needed:

```powershell
cd D:\saavran\padhaii\System_Design\backend
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

Set these values in `backend/.env` using Test Mode credentials from the
Razorpay Dashboard:

```env
PAYMENT_PROVIDER=RAZORPAY
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_test_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

Never commit `.env`, live keys, or webhook secrets. The frontend receives only
the public Test Mode key ID from the backend payment response.

Apply the payment migration:

```powershell
cd D:\saavran\padhaii\System_Design\backend
.\.venv\Scripts\alembic.exe upgrade head
```

## Checkout and verification endpoints

`POST /api/v1/payments` creates an internal payment plus a Razorpay order. The
amount is calculated from the booking and converted from rupees to paise on the
server.

`POST /api/v1/payments/{payment_id}/verify` accepts the Checkout response. It
checks that the provider order belongs to our payment and verifies:

```text
HMAC_SHA256(our_provider_order_id + "|" + razorpay_payment_id, key_secret)
```

Only a valid signature reaches the booking confirmation transaction.

## Webhooks

Configure this endpoint in Razorpay Test Mode:

```text
POST https://your-public-host/api/v1/webhooks/razorpay
```

Subscribe to `payment.captured`, `payment.failed`, and `order.paid`. The
endpoint verifies `X-Razorpay-Signature` against the raw request body and
deduplicates events using `x-razorpay-event-id` or a body hash.

For local development, a public HTTPS tunnel is required for Razorpay to reach
the laptop. The browser handler gives fast user feedback; the webhook is the
reliable server-to-server path when the browser closes or loses connectivity.

## Test checklist

- Use Razorpay Test Mode, never Live Mode.
- Confirm the generated order amount equals the booking amount in paise.
- Complete a test Checkout payment.
- Confirm the booking only after backend signature verification.
- Send the same webhook twice and confirm it is processed once.
- Change one signature character and confirm HTTP `400`.
- Let the hold expire before payment and confirm the payment becomes
  `REFUND_REQUIRED` rather than booking an unavailable seat.
- Keep the simulator enabled in automated tests so tests do not depend on an
  external payment service.

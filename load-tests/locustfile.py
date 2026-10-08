"""Small, safe Locust workload for the ticket-booking API."""

import os
import uuid

from locust import HttpUser, between, task


PASSWORD = "correct horse battery"
SHOW_ID = int(os.getenv("LOAD_SHOW_ID", "1"))
SEAT_IDS = [int(value) for value in os.getenv("LOAD_SEAT_IDS", "").split(",") if value]


class TicketBookingUser(HttpUser):
    """Browse frequently; exercise writes less frequently."""

    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.email = f"load-{uuid.uuid4()}@example.com"
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": PASSWORD, "full_name": "Load Tester"},
            name="auth/register",
        )
        if response.status_code != 201:
            self.stop(True)
            return
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        seat_map = self.client.get(f"/api/v1/shows/{SHOW_ID}/seats", name="catalogue/show-seats-on-start")
        discovered = [item["show_seat_id"] for item in seat_map.json().get("items", []) if item["status"] == "AVAILABLE"]
        self.seat_ids = SEAT_IDS or discovered

    @task(5)
    def browse_events(self):
        self.client.get("/api/v1/events?page=1&page_size=20", name="catalogue/events")

    @task(5)
    def read_seat_map(self):
        self.client.get(f"/api/v1/shows/{SHOW_ID}/seats", name="catalogue/show-seats")

    @task(3)
    def create_short_hold(self):
        seat_id = self.seat_ids[uuid.uuid4().int % len(self.seat_ids)]
        with self.client.post(
            f"/api/v1/shows/{SHOW_ID}/holds",
            json={"show_seat_ids": [seat_id]},
            headers={**self.headers, "Idempotency-Key": f"load-hold-{uuid.uuid4()}"},
            name="holds/create",
            catch_response=True,
        ) as response:
            # A 409 means contention worked; it is not infrastructure failure.
            if response.status_code in {201, 409}:
                response.success()

    @task(1)
    def complete_booking(self):
        seat_id = self.seat_ids[uuid.uuid4().int % len(self.seat_ids)]
        with self.client.post(
            f"/api/v1/shows/{SHOW_ID}/holds",
            json={"show_seat_ids": [seat_id]},
            headers={**self.headers, "Idempotency-Key": f"load-booking-hold-{uuid.uuid4()}"},
            name="holds/create-for-booking",
            catch_response=True,
        ) as response:
            if response.status_code == 409:
                response.success()
            if response.status_code != 201:
                return
            hold_id = response.json()["hold_id"]
        booking = self.client.post(
            "/api/v1/bookings",
            json={"hold_id": hold_id},
            headers={**self.headers, "Idempotency-Key": f"load-booking-{uuid.uuid4()}"},
            name="bookings/create",
        )
        if booking.status_code != 201:
            return
        payment = self.client.post(
            "/api/v1/payments",
            json={"booking_id": booking.json()["booking_id"]},
            headers={**self.headers, "Idempotency-Key": f"load-payment-{uuid.uuid4()}"},
            name="payments/create",
        )
        if payment.status_code == 201:
            self.client.post(
                f"/api/v1/payments/{payment.json()['payment_id']}/simulate",
                json={"outcome": "SUCCESS"},
                headers=self.headers,
                name="payments/simulate-success",
            )

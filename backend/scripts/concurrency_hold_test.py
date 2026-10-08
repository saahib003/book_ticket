"""Run the required 100-request hot-seat hold experiment against the API."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
SHOW_ID = os.getenv("LOAD_SHOW_ID", "2")
SHOW_SEAT_ID = os.getenv("LOAD_SHOW_SEAT_ID", "11")


def request(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    try:
        with urlopen(Request(BASE_URL + path, data=body, headers=request_headers, method=method), timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


email = f"concurrency-{uuid4()}@example.com"
status, registered = request("POST", "/api/v1/auth/register", {"email": email, "password": "correct horse battery", "full_name": "Concurrency Tester"})
if status != 201:
    raise SystemExit(f"Could not create experiment user: {status} {registered}")
token = registered["access_token"]


def attempt(index: int):
    return request("POST", f"/api/v1/shows/{SHOW_ID}/holds", {"show_seat_ids": [SHOW_SEAT_ID]}, {"Authorization": f"Bearer {token}", "Idempotency-Key": f"concurrency-{index}-{uuid4()}"})


started = time.perf_counter()
with ThreadPoolExecutor(max_workers=100) as executor:
    results = list(executor.map(attempt, range(100)))
elapsed_ms = (time.perf_counter() - started) * 1000
winners = [body for status, body in results if status == 201]
conflicts = [body for status, body in results if status == 409]
unexpected = [(status, body) for status, body in results if status not in (201, 409)]

print(f"attempts=100 winners={len(winners)} conflicts={len(conflicts)} unexpected={len(unexpected)} elapsed_ms={elapsed_ms:.1f}")
if winners:
    hold_id = winners[0]["hold_id"]
    cleanup_status, _ = request("DELETE", f"/api/v1/holds/{hold_id}", headers={"Authorization": f"Bearer {token}"})
    print(f"cleanup_status={cleanup_status}")
if unexpected or len(winners) != 1 or len(conflicts) != 99:
    raise SystemExit(1)

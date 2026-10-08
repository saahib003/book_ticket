import pytest
from unittest.mock import Mock

from app.extensions import db
from app.factory import create_app
from app.models import User


@pytest.fixture
def client():
    app = create_app("testing")
    app.extensions["redis"] = Mock()
    app.extensions["redis"].incr.return_value = 1
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_register_returns_tokens_and_hides_password(client):
    response = client.post("/api/v1/auth/register", json={"email": "A@EXAMPLE.COM", "password": "correct horse battery", "full_name": "A Customer"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "a@example.com"
    assert body["access_token"] and body["refresh_token"]
    assert "password" not in body["user"]


def test_duplicate_registration_is_rejected(client):
    payload = {"email": "user@example.com", "password": "correct horse battery", "full_name": "A Customer"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_login_and_protected_profile(client):
    payload = {"email": "user@example.com", "password": "correct horse battery", "full_name": "A Customer"}
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    token = login.get_json()["access_token"]

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == payload["email"]


def test_invalid_password_and_missing_token_fail(client):
    payload = {"email": "user@example.com", "password": "correct horse battery", "full_name": "A Customer"}
    client.post("/api/v1/auth/register", json=payload)
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "wrong"}).status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401


def test_refresh_rotates_token_and_logout_revokes_new_token(client):
    payload = {"email": "user@example.com", "password": "correct horse battery", "full_name": "A Customer"}
    registered = client.post("/api/v1/auth/register", json=payload).get_json()
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]})

    assert refreshed.status_code == 200
    assert refreshed.get_json()["refresh_token"] != registered["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}).status_code == 401

    new_refresh = refreshed.get_json()["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401


def test_login_rate_limit_returns_429(client):
    client.application.extensions["redis"].incr.return_value = 6
    response = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrong"})

    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "RATE_LIMITED"

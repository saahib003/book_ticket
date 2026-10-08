"""HTTP endpoints for the authentication lifecycle."""

from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from pydantic import ValidationError

from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.security import (
    create_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.extensions import db
from app.models.auth import RefreshToken, User
from app.security.rate_limit import enforce_rate_limit

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1")


def error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def token_pair(user: User) -> tuple[str, str]:
    access = create_token(user.id, "access", timedelta(minutes=current_app.config["ACCESS_TOKEN_MINUTES"]))
    refresh = create_token(user.id, "refresh", timedelta(days=current_app.config["REFRESH_TOKEN_DAYS"]))
    db.session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=current_app.config["REFRESH_TOKEN_DAYS"]),
        )
    )
    return access, refresh


@auth_bp.post("/auth/register")
def register():
    blocked = enforce_rate_limit("register", current_app.config["LOGIN_RATE_LIMIT"], current_app.config["RATE_LIMIT_WINDOW_SECONDS"])
    if blocked:
        return blocked
    try:
        body = RegisterRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)

    email = str(body.email).lower()
    if db.session.scalar(db.select(User).where(User.email == email)):
        return error("EMAIL_ALREADY_REGISTERED", "An account with this email already exists.", 409)

    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name)
    db.session.add(user)
    db.session.flush()
    access, refresh = token_pair(user)
    db.session.commit()
    return jsonify({"user": user_response(user), "access_token": access, "refresh_token": refresh}), 201


@auth_bp.post("/auth/login")
def login():
    blocked = enforce_rate_limit("login", current_app.config["LOGIN_RATE_LIMIT"], current_app.config["RATE_LIMIT_WINDOW_SECONDS"])
    if blocked:
        return blocked
    try:
        body = LoginRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", exc.errors()[0]["msg"], 400)

    user = db.session.scalar(db.select(User).where(User.email == str(body.email).lower()))
    if not user or user.status != "ACTIVE" or not verify_password(user.password_hash, body.password):
        return error("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)

    access, refresh = token_pair(user)
    db.session.commit()
    return jsonify({"user": user_response(user), "access_token": access, "refresh_token": refresh}), 200


@auth_bp.post("/auth/refresh")
def refresh():
    token = (request.get_json(silent=True) or {}).get("refresh_token")
    if not token:
        return error("INVALID_REFRESH_TOKEN", "A refresh token is required.", 401)
    try:
        payload = decode_token(token, "refresh")
    except jwt.InvalidTokenError:
        return error("INVALID_REFRESH_TOKEN", "The refresh token is invalid or expired.", 401)

    record = db.session.scalar(db.select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token)))
    expires_at = record.expires_at.replace(tzinfo=timezone.utc) if record and record.expires_at.tzinfo is None else (record.expires_at if record else None)
    if not record or record.revoked_at or expires_at <= datetime.now(timezone.utc):
        return error("INVALID_REFRESH_TOKEN", "The refresh token is revoked or expired.", 401)
    user = db.session.get(User, int(payload["sub"]))
    if not user or user.status != "ACTIVE":
        return error("INVALID_REFRESH_TOKEN", "The user session is no longer active.", 401)

    record.revoked_at = datetime.now(timezone.utc)
    access, new_refresh = token_pair(user)
    db.session.commit()
    return jsonify({"access_token": access, "refresh_token": new_refresh}), 200


@auth_bp.post("/auth/logout")
def logout():
    token = (request.get_json(silent=True) or {}).get("refresh_token")
    if token:
        record = db.session.scalar(db.select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token)))
        if record and not record.revoked_at:
            record.revoked_at = datetime.now(timezone.utc)
            db.session.commit()
    return "", 204


def require_access_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return error("AUTHENTICATION_REQUIRED", "A bearer access token is required.", 401)
    try:
        payload = decode_token(header[7:], "access")
    except jwt.InvalidTokenError:
        return error("INVALID_ACCESS_TOKEN", "The access token is invalid or expired.", 401)
    user = db.session.get(User, int(payload["sub"]))
    if not user or user.status != "ACTIVE":
        return error("INVALID_ACCESS_TOKEN", "The user session is no longer active.", 401)
    g.current_user = user
    return None


def require_admin():
    """Authenticate the caller and require the ADMIN role."""
    failure = require_access_token()
    if failure:
        return failure
    if g.current_user.role != "ADMIN":
        return error("ADMIN_REQUIRED", "Administrator access is required.", 403)
    return None


@auth_bp.get("/users/me")
def me():
    failure = require_access_token()
    if failure:
        return failure
    return jsonify({"user": user_response(g.current_user)}), 200


def user_response(user: User) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}

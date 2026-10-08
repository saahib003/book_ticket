"""Password and token operations for authentication."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_token(user_id: int, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": token_type, "jti": str(uuid4()), "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload

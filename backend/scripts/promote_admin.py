"""Promote an existing local account to ADMIN for development."""

import sys

from app.extensions import db
from app.factory import create_app
from app.models.auth import User


if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/promote_admin.py email@example.com")

app = create_app()
with app.app_context():
    email = sys.argv[1].strip().lower()
    user = db.session.scalar(db.select(User).where(User.email == email))
    if not user:
        raise SystemExit(f"No account found for {email}. Register it first.")
    user.role = "ADMIN"
    db.session.commit()
    print(f"Promoted {email} to ADMIN. Sign in again to receive the role in the UI.")

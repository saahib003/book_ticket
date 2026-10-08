"""Alembic environment configured from the Flask application settings."""

from logging.config import fileConfig

from alembic import context
from flask import current_app

from app.extensions import db
from app.factory import create_app
from app.models import User, RefreshToken  # noqa: F401 - register model metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata


def get_database_url() -> str:
    """Use the same URL as Flask so app and migrations cannot drift."""
    return current_app.config["SQLALCHEMY_DATABASE_URI"]


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = db.engine.connect()
    try:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


flask_app = create_app()
with flask_app.app_context():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()

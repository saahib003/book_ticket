"""create catalogue and scheduling tables

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("venues", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("city", sa.String(100), nullable=False), sa.Column("address", sa.String(500), nullable=False), sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_venues_city", "venues", ["city"])
    op.create_table("auditoriums", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.UniqueConstraint("venue_id", "name", name="uq_auditoriums_venue_name"))
    op.create_index("ix_auditoriums_venue_id", "auditoriums", ["venue_id"])
    op.create_table("seats", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("auditorium_id", sa.Integer(), sa.ForeignKey("auditoriums.id"), nullable=False), sa.Column("row_label", sa.String(10), nullable=False), sa.Column("seat_number", sa.Integer(), nullable=False), sa.Column("category", sa.String(30), nullable=False, server_default="STANDARD"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.UniqueConstraint("auditorium_id", "row_label", "seat_number", name="uq_seats_location"))
    op.create_index("ix_seats_auditorium_id", "seats", ["auditorium_id"])
    op.create_table("events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(250), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("category", sa.String(50), nullable=False), sa.Column("language", sa.String(50), nullable=False), sa.Column("duration_minutes", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_events_title", "events", ["title"])
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_table("shows", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False), sa.Column("auditorium_id", sa.Integer(), sa.ForeignKey("auditoriums.id"), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False), sa.Column("booking_opens_at", sa.DateTime(timezone=True), nullable=False), sa.Column("booking_closes_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED"))
    op.create_index("ix_shows_event_id", "shows", ["event_id"])
    op.create_index("ix_shows_auditorium_id", "shows", ["auditorium_id"])
    op.create_index("ix_shows_status", "shows", ["status"])
    op.create_index("ix_shows_event_starts_at", "shows", ["event_id", "starts_at"])
    op.create_index("ix_shows_auditorium_starts_at", "shows", ["auditorium_id", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_shows_auditorium_starts_at", table_name="shows")
    op.drop_index("ix_shows_event_starts_at", table_name="shows")
    op.drop_index("ix_shows_status", table_name="shows")
    op.drop_index("ix_shows_auditorium_id", table_name="shows")
    op.drop_index("ix_shows_event_id", table_name="shows")
    op.drop_table("shows")
    for index in ("ix_events_status", "ix_events_category", "ix_events_title"):
        op.drop_index(index, table_name="events")
    op.drop_table("events")
    op.drop_index("ix_seats_auditorium_id", table_name="seats")
    op.drop_table("seats")
    op.drop_index("ix_auditoriums_venue_id", table_name="auditoriums")
    op.drop_table("auditoriums")
    op.drop_index("ix_venues_city", table_name="venues")
    op.drop_table("venues")


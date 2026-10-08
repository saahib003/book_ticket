"""create seat holds and idempotency records

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("seat_holds", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_seat_holds_user_id", "seat_holds", ["user_id"])
    op.create_index("ix_seat_holds_show_id", "seat_holds", ["show_id"])
    op.create_index("ix_seat_holds_status", "seat_holds", ["status"])
    op.create_index("ix_seat_holds_expires_at", "seat_holds", ["expires_at"])
    op.create_table("hold_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("hold_id", sa.String(36), sa.ForeignKey("seat_holds.id"), nullable=False), sa.Column("show_seat_id", sa.Integer(), sa.ForeignKey("show_seats.id"), nullable=False), sa.Column("price", sa.Numeric(10, 2), nullable=False), sa.UniqueConstraint("hold_id", "show_seat_id", name="uq_hold_items_hold_seat"))
    op.create_table("idempotency_records", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("operation", sa.String(50), nullable=False), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("response_json", sa.JSON(), nullable=False), sa.Column("status_code", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_idempotency_scope"))


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("hold_items")
    for index in ("ix_seat_holds_expires_at", "ix_seat_holds_status", "ix_seat_holds_show_id", "ix_seat_holds_user_id"):
        op.drop_index(index, table_name="seat_holds")
    op.drop_table("seat_holds")


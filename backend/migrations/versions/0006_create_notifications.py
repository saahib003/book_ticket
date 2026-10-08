"""create simulated notification records

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("notifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_id", sa.String(36), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("booking_id", sa.String(36), nullable=False), sa.Column("channel", sa.String(30), nullable=False, server_default="SIMULATED_EMAIL"), sa.Column("status", sa.String(20), nullable=False, server_default="SENT"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("event_id"))
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")


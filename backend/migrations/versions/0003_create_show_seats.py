"""create show-specific inventory

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "show_seats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False),
        sa.Column("seat_id", sa.Integer(), sa.ForeignKey("seats.id"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("show_id", "seat_id", name="uq_show_seats_show_seat"),
    )
    op.create_index("ix_show_seats_show_id", "show_seats", ["show_id"])
    op.create_index("ix_show_seats_seat_id", "show_seats", ["seat_id"])
    op.create_index("ix_show_seats_status", "show_seats", ["status"])
    op.create_index("ix_show_seats_show_status", "show_seats", ["show_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_show_seats_show_status", table_name="show_seats")
    op.drop_index("ix_show_seats_status", table_name="show_seats")
    op.drop_index("ix_show_seats_seat_id", table_name="show_seats")
    op.drop_index("ix_show_seats_show_id", table_name="show_seats")
    op.drop_table("show_seats")


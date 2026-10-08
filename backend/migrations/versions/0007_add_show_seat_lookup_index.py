"""add show and seat lookup index

Revision ID: 0007
Revises: 0006
"""

from alembic import op


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_show_seats_show_id_seat_id",
        "show_seats",
        ["show_id", "seat_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_show_seats_show_id_seat_id", table_name="show_seats")

"""add provider order id for external payment orders

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("provider_order_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint("uq_payments_provider_order_id", "payments", ["provider_order_id"])


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_order_id", "payments", type_="unique")
    op.drop_column("payments", "provider_order_id")

"""create bookings, payments, webhooks, audit, and outbox records

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("bookings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("booking_reference", sa.String(30), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False), sa.Column("hold_id", sa.String(36), sa.ForeignKey("seat_holds.id"), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_PAYMENT"), sa.Column("amount", sa.Numeric(10, 2), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("booking_reference"), sa.UniqueConstraint("hold_id"), sa.UniqueConstraint("user_id", "idempotency_key", name="uq_bookings_user_idempotency"))
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_show_id", "bookings", ["show_id"])
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_table("booking_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False), sa.Column("show_seat_id", sa.Integer(), sa.ForeignKey("show_seats.id"), nullable=False), sa.Column("seat_label", sa.String(30), nullable=False), sa.Column("unit_price", sa.Numeric(10, 2), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("booking_id", "show_seat_id", name="uq_booking_items_booking_seat"))
    op.create_table("payments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False), sa.Column("provider", sa.String(50), nullable=False, server_default="SIMULATED"), sa.Column("provider_payment_id", sa.String(100), nullable=True), sa.Column("amount", sa.Numeric(10, 2), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("status", sa.String(30), nullable=False, server_default="INITIATED"), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("failure_reason", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("provider_payment_id"), sa.UniqueConstraint("idempotency_key"))
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_table("webhook_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider_event_id", sa.String(150), nullable=False), sa.Column("provider", sa.String(50), nullable=False), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="RECEIVED"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True), sa.UniqueConstraint("provider_event_id"))
    op.create_table("outbox_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("aggregate_type", sa.String(50), nullable=False), sa.Column("aggregate_id", sa.String(36), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("available_at", sa.DateTime(timezone=True), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_table("booking_audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False), sa.Column("action", sa.String(100), nullable=False), sa.Column("previous_status", sa.String(30), nullable=True), sa.Column("new_status", sa.String(30), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_booking_audit_logs_booking_id", "booking_audit_logs", ["booking_id"])


def downgrade() -> None:
    op.drop_index("ix_booking_audit_logs_booking_id", table_name="booking_audit_logs")
    op.drop_table("booking_audit_logs")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("booking_items")
    for index in ("ix_bookings_status", "ix_bookings_show_id", "ix_bookings_user_id"):
        op.drop_index(index, table_name="bookings")
    op.drop_table("bookings")


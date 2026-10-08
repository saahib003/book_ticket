"""At-least-once transactional outbox consumer."""

from datetime import datetime, timezone

from celery import shared_task

from app.extensions import db
from app.factory import create_app
from app.models import Notification, OutboxEvent


@shared_task(name="outbox.process_pending", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_pending_outbox(batch_size: int = 100) -> int:
    app = create_app()
    processed = 0
    with app.app_context():
        with db.session.begin():
            events = db.session.scalars(
                db.select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING", OutboxEvent.available_at <= datetime.now(timezone.utc))
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).all()
            for event in events:
                event.status = "PROCESSING"
                if event.event_type in {"BOOKING_CONFIRMED", "BOOKING_CANCELLED"}:
                    if not db.session.scalar(db.select(Notification).where(Notification.event_id == event.id)):
                        db.session.add(Notification(event_id=event.id, user_id=event.payload["user_id"], booking_id=event.payload["booking_id"]))
                event.status = "PROCESSED"
                event.processed_at = datetime.now(timezone.utc)
                processed += 1
    return processed


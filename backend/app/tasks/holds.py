"""Scheduled cleanup for expired holds."""

from datetime import datetime, timezone

from celery import shared_task

from app.extensions import db
from app.factory import create_app
from app.models import SeatHold, ShowSeat
from app.common.cache import cache_delete
from app.realtime import publish_seat_status


@shared_task(name="holds.cleanup_expired", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def cleanup_expired_holds(batch_size: int = 100) -> int:
    """Release one claimed batch; retries are safe because state transitions are idempotent."""
    app = create_app()
    released = 0
    with app.app_context():
        now = datetime.now(timezone.utc)
        with db.session.begin():
            holds = db.session.scalars(
                db.select(SeatHold)
                .where(SeatHold.status == "ACTIVE", SeatHold.expires_at <= now)
                .order_by(SeatHold.expires_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).all()
            for hold in holds:
                seat_ids = sorted(item.show_seat_id for item in hold.items)
                seats = db.session.scalars(
                    db.select(ShowSeat).where(ShowSeat.id.in_(seat_ids)).order_by(ShowSeat.id).with_for_update()
                ).all()
                for seat in seats:
                    if seat.status == "HELD":
                        seat.status = "AVAILABLE"
                        seat.version += 1
                hold.status = "EXPIRED"
                released += 1
                db.session.flush()
                cache_delete(f"catalogue:show:{hold.show_id}:seats")
                publish_seat_status(hold.show_id, seat_ids, "AVAILABLE", max((seat.version for seat in seats), default=0))
    return released

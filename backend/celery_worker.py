"""Celery worker and Beat configuration."""

from celery import Celery

from app.factory import create_app

app = create_app()
celery = Celery("ticket_booking", broker=app.config["CELERY_BROKER_URL"], backend=app.config["CELERY_RESULT_BACKEND"])
celery.conf.update(
    timezone="UTC",
    task_track_started=True,
    beat_schedule={
        "cleanup-expired-holds": {"task": "holds.cleanup_expired", "schedule": 30.0},
    },
)
celery.conf.include = ["app.tasks.holds", "app.tasks.outbox"]

"""Health endpoints used by local development and future deployment probes."""

from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy import text

from app.extensions import db
from app.common.metrics import metrics_payload

health_bp = Blueprint("health", __name__)


@health_bp.get("/metrics")
def metrics():
    """Expose local Prometheus metrics for learning and load experiments."""
    return Response(metrics_payload(), mimetype="text/plain; version=0.0.4")


@health_bp.get("/health/live")
def liveness():
    """Process-level probe: no dependency call is made here."""
    return jsonify({"status": "ok", "check": "liveness"}), 200


@health_bp.get("/health/ready")
def readiness():
    """Dependency probe: reports degraded readiness instead of claiming success."""
    checks = {}
    ready = True

    try:
        db.session.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception:
        db.session.rollback()
        checks["postgresql"] = "unavailable"
        ready = False

    try:
        redis_client = current_app.extensions["redis"]
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        ready = False

    return jsonify({"status": "ok" if ready else "not_ready", "checks": checks}), (
        200 if ready else 503
    )

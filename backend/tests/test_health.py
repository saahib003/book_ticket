from unittest.mock import Mock

from app.factory import create_app
from app.extensions import db
from app.models import User


def test_liveness_does_not_require_dependencies():
    app = create_app("testing")
    response = app.test_client().get("/health/live")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "check": "liveness"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_readiness_reports_dependency_failure_without_hiding_it():
    app = create_app("testing")
    app.extensions["redis"] = Mock()
    app.extensions["redis"].ping.side_effect = ConnectionError("Redis offline")
    response = app.test_client().get("/health/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "not_ready",
        "checks": {"postgresql": "ok", "redis": "unavailable"},
    }

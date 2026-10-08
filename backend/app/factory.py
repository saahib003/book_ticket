"""Flask application factory."""

import os
import time

import redis
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from sqlalchemy.exc import OperationalError

from app.config import CONFIG_BY_ENV
from app.extensions import db
from app.health import health_bp
from app.auth.routes import auth_bp
from app.catalogue.routes import catalogue_bp
from app.holds.routes import holds_bp
from app.bookings.routes import bookings_bp
from app.realtime import socketio
from app.common.metrics import REQUEST_LATENCY, REQUESTS


def create_app(config_name: str | None = None) -> Flask:
    """Create an isolated Flask app, which keeps tests and future workers safe."""
    app = Flask(__name__)
    selected_env = config_name or os.getenv("APP_ENV", "development")
    app.config.from_object(CONFIG_BY_ENV.get(selected_env, CONFIG_BY_ENV["development"]))
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGIN"]}})
    socketio_options = {
        "cors_allowed_origins": [app.config["CORS_ORIGIN"]],
        # Keep the Windows development server compatible with the Redis
        # message queue. Production deployment can use a gevent worker after
        # adding the required monkey patch before importing the app.
        "async_mode": "threading",
    }
    # The test client requires in-process transport; runtime workers use Redis
    # so separate workers can coordinate Socket.IO events.
    if selected_env != "testing":
        socketio_options["message_queue"] = app.config["SOCKETIO_REDIS_URL"]
    socketio.init_app(app, **socketio_options)

    db.init_app(app)
    app.extensions["redis"] = redis.Redis.from_url(
        app.config["REDIS_URL"],
        decode_responses=True,
        socket_timeout=app.config["REDIS_SOCKET_TIMEOUT"],
        socket_connect_timeout=app.config["REDIS_SOCKET_CONNECT_TIMEOUT"],
    )
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(catalogue_bp)
    app.register_blueprint(holds_bp)
    app.register_blueprint(bookings_bp)

    @app.before_request
    def start_request_timer():
        g.request_started_at = time.perf_counter()

    @app.after_request
    def record_request_metrics(response):
        endpoint = request.endpoint or "unknown"
        elapsed = time.perf_counter() - getattr(g, "request_started_at", time.perf_counter())
        REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, endpoint).observe(elapsed)
        return response

    @app.errorhandler(OperationalError)
    def handle_database_operational_error(error):
        """Fail clearly when PostgreSQL is unavailable or cannot be reached."""
        db.session.rollback()
        app.logger.warning("Database dependency unavailable: %s", error.__class__.__name__)
        return jsonify({
            "error": {
                "code": "DEPENDENCY_UNAVAILABLE",
                "message": "The database is temporarily unavailable.",
            }
        }), 503

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app

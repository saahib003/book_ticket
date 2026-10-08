"""Environment-backed application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Shared defaults. Secrets and dependency URLs are never hard-coded."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-only-jwt-secret-change-me-32-bytes")
    ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
    REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://ticket_app:ticket_app@127.0.0.1:5432/ticket_booking",
    )
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "1"))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"connect_timeout": DB_CONNECT_TIMEOUT},
        "pool_pre_ping": True,
        "pool_timeout": 1,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.25"))
    REDIS_SOCKET_CONNECT_TIMEOUT = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "0.25"))
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "16384"))
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")
    LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
    HOLD_RATE_LIMIT = int(os.getenv("HOLD_RATE_LIMIT", "20"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    EVENT_CACHE_TTL_SECONDS = int(os.getenv("EVENT_CACHE_TTL_SECONDS", "600"))
    SHOW_CACHE_TTL_SECONDS = int(os.getenv("SHOW_CACHE_TTL_SECONDS", "180"))
    SEAT_MAP_CACHE_TTL_SECONDS = int(os.getenv("SEAT_MAP_CACHE_TTL_SECONDS", "5"))
    SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", "redis://localhost:6379/3")
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "SIMULATED").upper()
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")


class DevelopmentConfig(Config):
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {}
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class ProductionConfig(Config):
    DEBUG = False


CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

"""
OnePay — Application factory
All routes live in blueprints:
  blueprints/auth.py     — register, login, logout, password reset
  blueprints/payments.py — dashboard, create link, status, history
  blueprints/public.py   — verify page, preview API, polling, health
"""
# ruff: noqa: E402  (warnings must be silenced before other imports)
import hashlib
import logging
import os
import secrets
import uuid
import warnings
from datetime import datetime, timedelta, timezone

# Silence warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message=".*Python version 3.9 past its end of life.*")

from flask import Flask, g, jsonify, redirect, render_template, request, session

from blueprints.api_keys import api_keys_bp
from blueprints.auth import auth_bp
from blueprints.invoices import invoices_bp
from blueprints.payment_actions import payment_actions_bp
from blueprints.payments import payments_bp
from blueprints.public import public_bp
from blueprints.webhooks import webhooks_bp
from config import Config
from core.exceptions import OnePayError
from database import init_db

# Huey task queue (for worker command: huey_consumer app.huey)
from services.task_queue import huey

# ── Logging ────────────────────────────────────────────────────────────────────


class RequestIdFilter(logging.Filter):
    """Inject request_id from Flask g into every log record."""

    def filter(self, record):
        try:
            from flask import g

            record.request_id = g.get("request_id", "-")
        except RuntimeError:
            record.request_id = "-"
        return True


def _configure_logging():
    """
    Use JSON structured logging in production, plain text in debug.
    JSON logs are easier to ingest in log aggregators (CloudWatch, Datadog, etc.)
    """
    from core.logging_filters import CorrelationIdFilter, SensitiveDataFilter

    request_id_filter = RequestIdFilter()
    correlation_id_filter = CorrelationIdFilter()
    sensitive_filter = SensitiveDataFilter()

    if Config.DEBUG:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  [%(request_id)s]  [%(correlation_id)s]  %(name)s — %(message)s"
            )
        )
        handler.addFilter(request_id_filter)
        handler.addFilter(correlation_id_filter)
        handler.addFilter(sensitive_filter)
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.DEBUG)
    else:
        try:
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler()
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(request_id)s %(correlation_id)s %(name)s %(message)s"
            )
            handler.setFormatter(formatter)
            handler.addFilter(request_id_filter)
            handler.addFilter(correlation_id_filter)
            handler.addFilter(sensitive_filter)
            root = logging.getLogger()
            root.handlers = [handler]
            root.setLevel(logging.INFO)
        except ImportError:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s  %(levelname)-8s  [%(request_id)s]  [%(correlation_id)s]  %(name)s — %(message)s"
                )
            )
            handler.addFilter(request_id_filter)
            handler.addFilter(correlation_id_filter)
            handler.addFilter(sensitive_filter)
            root = logging.getLogger()
            root.handlers = [handler]
            root.setLevel(logging.INFO)


_configure_logging()
logger = logging.getLogger(__name__)

# ── App factory ────────────────────────────────────────────────────────────────


def _setup_talisman(app: Flask) -> None:
    """Configure Flask-Talisman security headers for production."""
    if Config.TESTING or Config.DEBUG:
        return
    from flask_talisman import Talisman
    csp = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdn.tailwindcss.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com", "https://fonts.googleapis.com"],
        "img-src": ["'self'", "data:", "https://lh3.googleusercontent.com"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
    Talisman(app, force_https=Config.ENFORCE_HTTPS, strict_transport_security=Config.ENFORCE_HTTPS,
             strict_transport_security_max_age=31536000, strict_transport_security_include_subdomains=True,
             strict_transport_security_preload=True, content_security_policy=csp,
             referrer_policy="strict-origin-when-cross-origin")


def _setup_debug_query_monitoring(app: Flask) -> None:
    """Register SQLAlchemy query counter for development."""
    if not Config.DEBUG:
        return
    from sqlalchemy import event as _sa_event

    from database import engine as _engine

    @_sa_event.listens_for(_engine, "before_cursor_execute")
    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        if not hasattr(g, "_query_count"):
            g._query_count = 0
        g._query_count += 1

    @app.after_request
    def _log_query_count(response):
        count = getattr(g, "_query_count", 0)
        if count > Config.QUERY_COUNT_WARN_THRESHOLD:
            logger.warning("High query count | endpoint=%s count=%d threshold=%d",
                           request.endpoint, count, Config.QUERY_COUNT_WARN_THRESHOLD)
        return response


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["DEBUG"] = Config.DEBUG
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=Config.ENFORCE_HTTPS,
        SESSION_COOKIE_DOMAIN=None,
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=Config.PERMANENT_SESSION_LIFETIME),
        SESSION_TIMEOUT_AUTHENTICATED=Config.SESSION_TIMEOUT_AUTHENTICATED,
        SESSION_TIMEOUT_UNAUTHENTICATED=Config.SESSION_TIMEOUT_UNAUTHENTICATED,
    )
    Config.validate()
    app.config["BOOT_TIME"] = datetime.now(timezone.utc).isoformat()

    from core.error_handlers import register_error_handlers
    from core.middleware import register_middleware
    register_middleware(app)
    register_error_handlers(app)

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1")
    app.register_blueprint(payments_bp, url_prefix="/api/v1")
    app.register_blueprint(payment_actions_bp, url_prefix="/api/v1")
    app.register_blueprint(invoices_bp, url_prefix="/api/v1")
    app.register_blueprint(api_keys_bp, url_prefix="/api/v1")
    app.register_blueprint(webhooks_bp, url_prefix="/api/v1")

    _setup_talisman(app)
    init_db()
    _setup_debug_query_monitoring(app)

    import threading

    from core.background import start_background_threads
    _shutdown_event = threading.Event()
    app._shutdown_event = _shutdown_event
    start_background_threads(_shutdown_event)

    return app

# ── Entry point ────────────────────────────────────────────────────────────────
# Module-level app instance for gunicorn (gunicorn app:app)
# create_app() is also importable directly for testing.

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)

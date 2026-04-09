"""
OnePay — Error handler registration.
Extracted from app.py to reduce create_app() complexity.
"""
import logging

from flask import Flask, g, jsonify, render_template, request, session

from config import Config
from core.exceptions import OnePayError

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """Register all error handlers on the app."""

    @app.errorhandler(OnePayError)
    def handle_onepay_error(error: OnePayError):
        logger.error(
            "OnePay error | code=%s message=%s correlation_id=%s",
            error.error_code, error.message, g.get("correlation_id"),
        )
        return jsonify({
            "success": False,
            "message": error.message,
            "error_code": error.error_code,
        }), error.status_code

    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(
            "Not found | path=%s method=%s correlation_id=%s",
            request.path, request.method, g.get("correlation_id"),
        )
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "The requested resource was not found",
            }), 404
        return render_template("base.html"), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        from core.ip import client_ip
        logger.warning(
            "Request too large | ip=%s path=%s correlation_id=%s",
            client_ip(), request.path, g.get("correlation_id"),
        )
        return jsonify({
            "success": False,
            "error": "REQUEST_TOO_LARGE",
            "message": "Request too large (max 1MB)",
            "max_size_mb": 1,
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        _log_500(error)
        _rollback_db()
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred. Please try again later.",
            }), 500
        return render_template("base.html"), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        logger.warning(
            "Forbidden | path=%s method=%s correlation_id=%s",
            request.path, request.method, g.get("correlation_id"),
        )
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "error": "FORBIDDEN",
                "message": "You don't have permission to access this resource",
            }), 403
        return render_template("base.html"), 403

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        from core.ip import client_ip
        logger.error(
            "Unexpected error | correlation_id=%s error=%s",
            g.get("correlation_id"), str(error),
            exc_info=True,
            extra={
                "url": request.url,
                "method": request.method,
                "ip": client_ip(),
                "user_id": session.get("user_id"),
            },
        )
        _rollback_db()
        if app.config.get("DEBUG"):
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "message": str(error),
                    "type": type(error).__name__,
                }), 500
        else:
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "message": "An internal error occurred. Please try again later.",
                }), 500
        return render_template("base.html"), 500


def _log_500(error) -> None:
    if Config.DEBUG:
        logger.error(
            "Internal server error | correlation_id=%s error=%s",
            g.get("correlation_id"), error, exc_info=True,
        )
    else:
        logger.error(
            "Internal server error | correlation_id=%s error=%s",
            g.get("correlation_id"), str(error)[:200],
        )


def _rollback_db() -> None:
    try:
        from database import get_db
        with get_db() as db:
            db.rollback()
    except Exception:
        logger.exception("Unhandled exception in error handler rollback")

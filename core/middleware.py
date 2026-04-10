"""
OnePay — Request/response middleware registration.
Extracted from app.py to reduce create_app() complexity.
"""
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import Flask, g, redirect, request, session

from config import Config

logger = logging.getLogger(__name__)


def register_middleware(app: Flask) -> None:
    """Register all before_request / after_request hooks on the app."""
    _register_before_request(app)
    _register_after_request(app)
    _register_context_processors(app)


def _register_before_request(app: Flask) -> None:
    _register_security_checks(app)
    _register_session_management(app)


def _register_security_checks(app: Flask) -> None:
    @app.before_request
    def verify_production_config():
        if os.getenv("APP_ENV") == "production":
            assert not app.config["DEBUG"], "DEBUG must be False in production"
            assert app.config["SESSION_COOKIE_SECURE"], "SESSION_COOKIE_SECURE must be True in production"
            assert Config.ENFORCE_HTTPS, "HTTPS must be enforced in production"

    @app.before_request
    def inject_correlation_id():
        g.correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.before_request
    def inject_request_id():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def authenticate_api_key():
        from core.api_auth import validate_api_key
        from core.audit import log_event
        from core.ip import client_ip
        from database import get_db

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
            is_valid, user_id = validate_api_key(api_key)
            if is_valid:
                g.api_key_authenticated = True
                g.user_id = user_id
                g.api_key = api_key
                with get_db() as db:
                    log_event(db, "api_key.used", user_id=user_id, ip_address=client_ip(), detail={"endpoint": request.endpoint})

    @app.before_request
    def enforce_https():
        if not Config.ENFORCE_HTTPS or Config.DEBUG:
            return None
        if request.is_secure:
            return None
        if Config.TRUST_X_FORWARDED_PROTO and (request.headers.get("X-Forwarded-Proto") or "").lower() == "https":
            return None
        return redirect(request.url.replace("http://", "https://", 1), code=301)


def _register_session_management(app: Flask) -> None:
    @app.before_request
    def invalidate_old_sessions():
        if app.config.get("TESTING"):
            return None
        boot_time = app.config.get("BOOT_TIME")
        if session.get("_boot") != boot_time:
            session.clear()
            session["_boot"] = boot_time
            return
        _check_session_max_age()
        _check_session_inactivity()
        session["_last_activity"] = datetime.now(timezone.utc).isoformat()

    @app.before_request
    def validate_session_binding():
        if app.config.get("TESTING"):
            return None
        from core.ip import client_ip
        if "user_id" not in session:
            return None
        result = _check_ip_binding(client_ip())
        if result is not None:
            return result
        return _check_ua_binding()


def _check_session_max_age() -> None:
    session_created = session.get("_created")
    if not session_created:
        return
    try:
        created_dt = datetime.fromisoformat(session_created)
        if datetime.now(timezone.utc) - created_dt > timedelta(days=7):
            if session.get("user_id"):
                logger.info("Session expired (max age) | user=%s", session.get("username"))
            session.clear()
    except (ValueError, TypeError):
        pass


def _check_session_inactivity() -> None:
    last_activity = session.get("_last_activity")
    if not last_activity:
        return
    try:
        last_active_dt = datetime.fromisoformat(last_activity)
        timeout_minutes = (
            Config.SESSION_TIMEOUT_AUTHENTICATED
            if session.get("user_id")
            else Config.SESSION_TIMEOUT_UNAUTHENTICATED
        )
        if datetime.now(timezone.utc) - last_active_dt > timedelta(minutes=timeout_minutes):
            if session.get("user_id"):
                logger.info("Session expired (inactivity) | user=%s", session.get("username"))
            session.clear()
    except (ValueError, TypeError):
        pass


def _check_ip_binding(current_ip: str):
    session_ip = session.get("_ip")
    if not session_ip or session_ip == current_ip:
        return None

    def _is_private(ip: str) -> bool:
        return (
            ip.startswith("10.")
            or ip.startswith("127.")
            or ip.startswith("192.168.")
            or (ip.startswith("172.") and ip.split(".")[1].isdigit()
                and 16 <= int(ip.split(".")[1]) <= 31)
        )

    if _is_private(session_ip) and _is_private(current_ip):
        logger.warning(
            "Session IP changed within private network | user=%s from=%s to=%s",
            session.get("username"), session_ip, current_ip,
        )
        session["_ip"] = current_ip
        return None

    logger.warning(
        "Session IP mismatch | user=%s session_ip=%s current_ip=%s",
        session.get("username"), session_ip, current_ip,
    )
    session.clear()
    return redirect("/login")


def _check_ua_binding():
    session_ua = session.get("_user_agent")
    current_ua = request.headers.get("User-Agent", "")[:200]
    if session_ua and session_ua != current_ua:
        logger.warning("Session UA mismatch | user=%s", session.get("username"))
        session.clear()
        return redirect("/login")
    return None


def _register_after_request(app: Flask) -> None:
    @app.after_request
    def add_request_id_header(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Correlation-ID"] = g.get("correlation_id", "")
        return response

    @app.after_request
    def add_cache_headers(response):
        if not request.path.startswith("/static/"):
            return response
        filename = request.path[len("/static/"):]
        parts = filename.rsplit(".", 2)
        if len(parts) == 3 and len(parts[1]) == 8 and parts[1].isalnum():
            response.headers["Cache-Control"] = "public, max-age=31536000"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        if response.direct_passthrough:
            response.direct_passthrough = False
        etag = '"' + hashlib.sha256(response.get_data()).hexdigest()[:32] + '"'
        response.headers["ETag"] = etag
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            response = response.__class__(status=304)
            response.headers["ETag"] = etag
        return response

    @app.after_request
    def set_security_headers(response):
        nonce = g.get("csp_nonce", "")
        response.headers.setdefault(
            "Content-Security-Policy",
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'nonce-{nonce}' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://accounts.google.com/gsi/ https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com https://accounts.google.com; "
            "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "connect-src 'self' https://accounts.google.com https://*.google.com; "
            "frame-src https://accounts.google.com https://*.google.com; "
            "child-src https://accounts.google.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';",
        )
        if request.endpoint not in ["auth.login_page", "auth.register_page"]:
            response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), camera=(), microphone=(), payment=(), usb=(), "
            "magnetometer=(), gyroscope=(), accelerometer=(), "
            "ambient-light-sensor=(), autoplay=(), encrypted-media=(), "
            "picture-in-picture=(), sync-xhr=(), fullscreen=(), "
            "interest-cohort=()",
        )
        if request.endpoint not in ["auth.login_page", "auth.register_page"]:
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("X-Download-Options", "noopen")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault(
            "X-Content-Security-Policy",
            response.headers.get("Content-Security-Policy", ""),
        )
        response.headers.setdefault("Expect-CT", "max-age=86400, enforce")
        if Config.ENFORCE_HTTPS:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response


def _register_context_processors(app: Flask) -> None:
    import json
    import os as _os

    _asset_manifest: dict = {}

    def _load_asset_manifest() -> dict:
        if not _asset_manifest:
            manifest_path = _os.path.join(app.root_path, "static", "manifest.json")
            try:
                with open(manifest_path) as f:
                    _asset_manifest.update(json.load(f))
            except (FileNotFoundError, ValueError):
                pass
        return _asset_manifest

    @app.context_processor
    def inject_hashed_assets():
        manifest = _load_asset_manifest()

        def hashed_url(filename: str) -> str:
            from flask import url_for as _url_for
            hashed_path = manifest.get(filename, filename)
            return _url_for("static", filename=hashed_path)

        return {"hashed_url": hashed_url}

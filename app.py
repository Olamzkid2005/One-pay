"""
OnePay — Application factory
All routes live in blueprints:
  blueprints/auth.py     — register, login, logout, password reset
  blueprints/payments.py — dashboard, create link, status, history
  blueprints/public.py   — verify page, preview API, polling, health
"""
import logging
import uuid
from datetime import timedelta, datetime, timezone

from flask import Flask, request, redirect, g, jsonify, render_template, session

from config import Config
from database import init_db
from blueprints.auth import auth_bp
from blueprints.payments import payments_bp
from blueprints.public import public_bp
from blueprints.invoices import invoices_bp
from blueprints.api_keys import api_keys_bp
from blueprints.webhooks import webhooks_bp

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
    from core.logging_filters import SensitiveDataFilter
    
    request_id_filter = RequestIdFilter()
    sensitive_filter = SensitiveDataFilter()
    
    if Config.DEBUG:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  [%(request_id)s]  %(name)s — %(message)s"
        ))
        handler.addFilter(request_id_filter)
        handler.addFilter(sensitive_filter)
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.DEBUG)
    else:
        try:
            from pythonjsonlogger import jsonlogger
            handler   = logging.StreamHandler()
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(request_id)s %(name)s %(message)s"
            )
            handler.setFormatter(formatter)
            handler.addFilter(request_id_filter)
            handler.addFilter(sensitive_filter)
            root = logging.getLogger()
            root.handlers = [handler]
            root.setLevel(logging.INFO)
        except ImportError:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-8s  [%(request_id)s]  %(name)s — %(message)s"
            ))
            handler.addFilter(request_id_filter)
            handler.addFilter(sensitive_filter)
            root = logging.getLogger()
            root.handlers = [handler]
            root.setLevel(logging.INFO)

_configure_logging()
logger = logging.getLogger(__name__)

# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["DEBUG"]      = Config.DEBUG
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1MB max request size
    app.config.update(
        SESSION_COOKIE_HTTPONLY  = True,
        SESSION_COOKIE_SAMESITE  = "Lax",  # Better compatibility while maintaining security
        SESSION_COOKIE_SECURE    = Config.ENFORCE_HTTPS,
        SESSION_COOKIE_DOMAIN    = None,  # Restrict to exact domain (no subdomains)
        SESSION_PERMANENT        = True,
        PERMANENT_SESSION_LIFETIME = timedelta(hours=Config.PERMANENT_SESSION_LIFETIME),
        SESSION_TIMEOUT_AUTHENTICATED = Config.SESSION_TIMEOUT_AUTHENTICATED,
        SESSION_TIMEOUT_UNAUTHENTICATED = Config.SESSION_TIMEOUT_UNAUTHENTICATED,
    )

    Config.validate()

    # Boot timestamp — used to invalidate sessions from before this restart
    BOOT_TIME = datetime.now(timezone.utc).isoformat()
    app.config["BOOT_TIME"] = BOOT_TIME

    # ── Production config verification ────────────────────────────────────────
    @app.before_request
    def verify_production_config():
        """Runtime assertion to prevent DEBUG in production."""
        import os
        if os.getenv("APP_ENV") == "production":
            assert not app.config["DEBUG"], "DEBUG must be False in production"
            assert app.config["SESSION_COOKIE_SECURE"], "SESSION_COOKIE_SECURE must be True in production"
            assert Config.ENFORCE_HTTPS, "HTTPS must be enforced in production"

    # ── Request ID tracing ─────────────────────────────────────────────────────
    @app.before_request
    def inject_request_id():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # ── API Key Authentication ─────────────────────────────────────────────────
    @app.before_request
    def authenticate_api_key():
        """Check for API key in Authorization header"""
        from core.api_auth import validate_api_key
        from core.audit import log_event
        from core.ip import client_ip
        from database import get_db
        
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]  # Remove 'Bearer ' prefix
            is_valid, user_id = validate_api_key(api_key)
            
            if is_valid:
                g.api_key_authenticated = True
                g.user_id = user_id
                g.api_key = api_key
                
                # Log API key usage
                with get_db() as db:
                    log_event(db, "api_key.used", user_id=user_id, 
                             ip_address=client_ip(),
                             detail={"endpoint": request.endpoint})

    @app.after_request
    def add_request_id_header(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response

    # ── Invalidate pre-restart sessions ───────────────────────────────────────
    @app.before_request
    def invalidate_old_sessions():
        """Clear any session that was created before this app boot."""
        # Skip validation in test mode
        if app.config.get('TESTING'):
            return None
        
        boot_time = app.config.get("BOOT_TIME")
        if session.get("_boot") != boot_time:
            session.clear()
            session["_boot"] = boot_time
            return
        
        # Absolute maximum session lifetime (7 days)
        session_created = session.get("_created")
        if session_created:
            try:
                created_dt = datetime.fromisoformat(session_created)
                max_age = timedelta(days=7)
                if datetime.now(timezone.utc) - created_dt > max_age:
                    if session.get("user_id"):
                        logger.info("Session expired due to maximum age | user=%s", session.get("username"))
                    session.clear()
                    return
            except (ValueError, TypeError):
                pass
        
        # Session inactivity timeout - applies to ALL sessions
        last_activity = session.get("_last_activity")
        if last_activity:
            try:
                last_active_dt = datetime.fromisoformat(last_activity)
                # Different timeout for authenticated vs unauthenticated sessions
                timeout_minutes = Config.SESSION_TIMEOUT_AUTHENTICATED if session.get("user_id") else Config.SESSION_TIMEOUT_UNAUTHENTICATED
                if datetime.now(timezone.utc) - last_active_dt > timedelta(minutes=timeout_minutes):
                    if session.get("user_id"):
                        logger.info("Session expired due to inactivity | user=%s", session.get("username"))
                    session.clear()
                    return
            except (ValueError, TypeError):
                pass
        
        # Update last activity timestamp for all sessions
        session["_last_activity"] = datetime.now(timezone.utc).isoformat()

    # ── Session binding validation (defense-in-depth against session fixation) ─
    @app.before_request
    def validate_session_binding():
        """Validate session is bound to same IP and User-Agent."""
        # Skip validation in test mode
        if app.config.get('TESTING'):
            return None
        
        from core.ip import client_ip
        
        if "user_id" in session:
            # Check IP binding
            session_ip = session.get("_ip")
            current_ip = client_ip()
            if session_ip and session_ip != current_ip:
                def _is_private(ip: str) -> bool:
                    return ip.startswith("10.") or ip.startswith("127.") or ip.startswith("192.168.") or (ip.startswith("172.") and ip.split(".")[1].isdigit() and 16 <= int(ip.split(".")[1]) <= 31)
                if _is_private(session_ip) and _is_private(current_ip):
                    logger.warning("Session IP changed within private network | user=%s from=%s to=%s", session.get("username"), session_ip, current_ip)
                    session["_ip"] = current_ip
                else:
                    logger.warning("Session IP mismatch | user=%s session_ip=%s current_ip=%s", session.get("username"), session_ip, current_ip)
                    session.clear()
                    return redirect("/login")
            
            # Check User-Agent binding
            session_ua = session.get("_user_agent")
            current_ua = request.headers.get("User-Agent", "")[:200]
            if session_ua and session_ua != current_ua:
                logger.warning("Session User-Agent mismatch | user=%s",
                              session.get("username"))
                session.clear()
                return redirect("/login")

    # ── HTTPS enforcement ──────────────────────────────────────────────────────
    @app.before_request
    def enforce_https():
        if not Config.ENFORCE_HTTPS or Config.DEBUG:
            return None
        if request.is_secure:
            return None
        if Config.TRUST_X_FORWARDED_PROTO:
            if (request.headers.get("X-Forwarded-Proto") or "").lower() == "https":
                return None
        return redirect(request.url.replace("http://", "https://", 1), code=301)


    # ── Security response headers ──────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        """
        Add defence-in-depth HTTP security headers to every response.

        Content-Security-Policy: restricts what the browser can load.
          - default-src 'self': only same-origin resources by default
          - script-src 'self' 'unsafe-inline': allows inline JS (needed for
            the CSRF token injected via Jinja into <script> blocks).
            For stronger protection, replace 'unsafe-inline' with a nonce.
          - style-src 'self' 'unsafe-inline' fonts.googleapis.com: allows
            inline styles and Google Fonts.
        X-Frame-Options: DENY prevents the verify page being clickjacked.
        X-Content-Type-Options: nosniff prevents MIME-type sniffing.
        Referrer-Policy: no-referrer-when-downgrade avoids leaking URLs.
        Permissions-Policy: disables unnecessary browser features.
        X-XSS-Protection: enables browser XSS filter (legacy browsers).
        X-Download-Options: prevents IE from executing downloads in site context.
        """
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://accounts.google.com/gsi/ https://accounts.google.com; "
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
        
        # X-Frame-Options: Don't set DENY on login/register pages (Google OAuth needs popups)
        # CSP frame-ancestors 'none' provides equivalent protection
        if request.endpoint not in ['auth.login_page', 'auth.register_page']:
            response.headers.setdefault("X-Frame-Options", "DENY")
        
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", 
            "geolocation=(), camera=(), microphone=(), payment=(), usb=(), magnetometer=()")
        
        # Cross-Origin-Opener-Policy: Don't use same-origin on login/register (blocks OAuth popups)
        if request.endpoint not in ['auth.login_page', 'auth.register_page']:
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        
        # Removed Cross-Origin-Embedder-Policy as it blocks CDN resources
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("X-Download-Options", "noopen")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        
        # Additional headers for maximum compatibility
        response.headers.setdefault("X-Content-Security-Policy", response.headers.get("Content-Security-Policy", ""))
        response.headers.setdefault("Expect-CT", "max-age=86400, enforce")
        
        # HSTS header (defense-in-depth, also set by Talisman)
        if Config.ENFORCE_HTTPS:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload"
            )
        
        return response

    # ── Blueprints ─────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(api_keys_bp)
    app.register_blueprint(webhooks_bp)

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors with a friendly message."""
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "The requested resource was not found"
            }), 404
        return render_template('base.html'), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle requests that exceed MAX_CONTENT_LENGTH."""
        logger.warning("Request too large | ip=%s path=%s", client_ip(), request.path)
        return jsonify({
            "success": False,
            "error": "REQUEST_TOO_LARGE",
            "message": "Request too large (max 1MB)",
            "max_size_mb": 1
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors without exposing stack traces."""
        # Only log full trace in debug mode
        if Config.DEBUG:
            logger.error("Internal server error: %s", error, exc_info=True)
        else:
            logger.error("Internal server error: %s", str(error)[:200])
        
        # Rollback any pending database transactions
        try:
            from database import get_db
            with get_db() as db:
                db.rollback()
        except Exception:
            pass
        
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred. Please try again later."
            }), 500
        
        return render_template('base.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 errors."""
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": "FORBIDDEN",
                "message": "You don't have permission to access this resource"
            }), 403
        return render_template('base.html'), 403

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """
        Catch-all handler for unexpected exceptions.
        VULN-007 FIX: Prevents stack trace leakage in production.
        """
        from core.ip import client_ip
        
        # Log full error server-side with context
        logger.error(
            "Unexpected error: %s",
            str(error),
            exc_info=True,
            extra={
                "url": request.url,
                "method": request.method,
                "ip": client_ip(),
                "user_id": session.get("user_id")
            }
        )
        
        # Rollback any pending database transactions
        try:
            from database import get_db
            with get_db() as db:
                db.rollback()
        except Exception:
            pass
        
        # Return generic error to client (no details in production)
        if app.config.get('DEBUG'):
            # In development, include error details for debugging
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "message": str(error),
                    "type": type(error).__name__
                }), 500
            return render_template('base.html'), 500
        else:
            # In production, generic message only
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "message": "An internal error occurred. Please try again later."
                }), 500
            return render_template('base.html'), 500

    # ── Security headers (Talisman) ────────────────────────────────────────────
    if not Config.TESTING and not Config.DEBUG:
        from flask_talisman import Talisman
        
        csp = {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"],
            "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdn.tailwindcss.com"],
            "font-src": ["'self'", "https://fonts.gstatic.com", "https://fonts.googleapis.com"],
            "img-src": ["'self'", "data:", "https://lh3.googleusercontent.com"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
        }

        Talisman(
            app,
            force_https=Config.ENFORCE_HTTPS,
            strict_transport_security=Config.ENFORCE_HTTPS,
            strict_transport_security_max_age=31536000,
            strict_transport_security_include_subdomains=True,
            strict_transport_security_preload=True,
            content_security_policy=csp,
            referrer_policy="strict-origin-when-cross-origin",
        )

    # ── Database ───────────────────────────────────────────────────────────────
    init_db()

    # ── Background threads ─────────────────────────────────────────────────────
    import threading
    import time
    from database import get_db
    from services.webhook import retry_failed_webhooks
    from services.security_monitor import detect_suspicious_activity
    
    try:
        from app_cleanup import start_cleanup_threads
    except ImportError:
        # app_cleanup module not available (e.g., in test environment)
        def start_cleanup_threads():
            pass
    
    def _webhook_retry_loop():
        """Background thread that retries failed webhook deliveries."""
        # Wait a bit for DB to be fully initialized
        time.sleep(5)
        while True:
            try:
                with get_db() as db:
                    retry_failed_webhooks(db)
            except Exception as e:
                logger.error("Webhook retry loop error: %s", e)
            time.sleep(60)
    
    def _security_monitor_loop():
        """Background thread that monitors for suspicious activity patterns."""
        # Wait a bit for DB to be fully initialized
        time.sleep(10)
        while True:
            try:
                with get_db() as db:
                    alerts = detect_suspicious_activity(db)
                    # Alerts are automatically logged by detect_suspicious_activity
                    if alerts:
                        logger.info("Security monitoring detected %d alerts", len(alerts))
            except Exception as e:
                logger.error("Security monitoring error: %s", e)
            time.sleep(300)  # Every 5 minutes
    
    webhook_thread = threading.Thread(
        target=_webhook_retry_loop,
        daemon=True,
        name="webhook-retry"
    )
    webhook_thread.start()
    logger.info("Webhook retry thread started")
    
    # Start security monitoring thread (VULN-011 fix)
    security_monitor_thread = threading.Thread(
        target=_security_monitor_loop,
        daemon=True,
        name="security-monitor"
    )
    security_monitor_thread.start()
    logger.info("Security monitoring thread started")
    
    # Start cleanup threads for audit logs and rate limits
    start_cleanup_threads()

    return app


# ── Entry point ────────────────────────────────────────────────────────────────
# Module-level app instance for gunicorn (gunicorn app:app)
# create_app() is also importable directly for testing.

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)

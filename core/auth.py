"""
OnePay — Session helpers and auth utilities.
Blueprints import from here instead of from app.py,
eliminating the circular import workaround.
"""
import hmac
import re
import secrets

from flask import session, redirect, url_for


# ── CSRF ──────────────────────────────────────────────────────────────────────

def get_csrf_token() -> str:
    """
    Return the CSRF token for the current session, creating one if needed.
    Embed in HTML forms and send as X-CSRFToken header on JSON POSTs.
    """
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def is_valid_csrf_token(submitted: str | None) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    expected = session.get("csrf_token")
    if not expected or not submitted:
        return False
    return hmac.compare_digest(expected, submitted)


def validate_csrf_with_origin() -> tuple[bool, str | None]:
    """
    Validate CSRF token with additional Origin/Referer header check for defense-in-depth.
    
    Returns:
        (is_valid, error_message)
    """
    from flask import request
    
    # Check CSRF token first
    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return False, "CSRF validation failed"
    
    # Additional Origin/Referer validation for JSON APIs
    if request.content_type == 'application/json':
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        
        # At least one must be present
        if not origin and not referer:
            return False, "Missing Origin or Referer header"
        
        # Validate Origin if present
        if origin:
            from urllib.parse import urlparse
            try:
                parsed_origin = urlparse(origin)
                request_host = request.host
                
                # Allow same-origin requests
                if parsed_origin.netloc != request_host:
                    return False, "Origin mismatch"
            except Exception:
                return False, "Invalid Origin header"
        
        # Validate Referer if Origin not present
        elif referer:
            from urllib.parse import urlparse
            try:
                parsed_referer = urlparse(referer)
                request_host = request.host
                
                # Allow same-origin requests
                if parsed_referer.netloc != request_host:
                    return False, "Referer mismatch"
            except Exception:
                return False, "Invalid Referer header"
    
    return True, None


# ── Session ───────────────────────────────────────────────────────────────────

def current_user_id() -> int | None:
    """Get user ID from session OR API key
    
    Returns:
        int | None: User ID if authenticated via session or API key, None otherwise
    """
    from flask import g
    
    # Check API key first (stored in g.user_id by middleware)
    if hasattr(g, 'api_key_authenticated') and g.api_key_authenticated:
        return g.user_id
    
    # Fall back to session
    return session.get("user_id")


def current_username() -> str | None:
    return session.get("username")


def login_required_redirect():
    """Redirect unauthenticated users to the login page, preserving the intended destination."""
    from flask import request
    next_url = request.path if request.path != "/" else None
    return redirect(url_for("auth.login_page", next=next_url) if next_url else url_for("auth.login_page"))


# ── Validation ────────────────────────────────────────────────────────────────

def valid_username(username: str) -> bool:
    """3–30 chars, letters/digits/underscores only."""
    return bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', username))


def valid_tx_ref(tx_ref: str) -> bool:
    """Uppercase letters, digits, hyphens — 10 to 60 chars."""
    return bool(re.match(r'^[A-Z0-9\-]{10,60}$', tx_ref))

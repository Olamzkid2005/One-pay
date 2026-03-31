"""
OnePay — Auth blueprint
Handles: register, login, logout, password reset, account settings
"""
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, render_template, session, redirect, url_for, flash, jsonify

from config import Config
from database import get_db
from models.user import User
from services.rate_limiter import check_rate_limit
from services.security import generate_reset_token, validate_webhook_url
from services.email import send_password_reset
from services.google_oauth import GoogleTokenValidator, GoogleProfileExtractor
from core.auth import (
    get_csrf_token, is_valid_csrf_token,
    current_user_id, current_username,
    valid_username,
)
from core.ip import client_ip
from core.responses import error
from core.audit import log_event

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def _regenerate_session_secure(user_id: int, username: str):
    """
    Securely regenerate session to prevent session fixation attacks.
    
    Flask's default signed cookie sessions don't have server-side state,
    so we ensure the session ID changes by clearing and adding a unique
    regeneration token that forces a new signature.
    
    Additionally binds session to IP and User-Agent for defense-in-depth.
    """
    from flask import current_app
    
    # Clear old session completely
    session.clear()
    
    # CRITICAL: Set permanent FIRST before adding any data
    # This ensures the session cookie has the correct lifetime
    session.permanent = True
    session.modified = True
    
    # Add regeneration marker to force new session ID/signature
    session["_regenerated"] = secrets.token_urlsafe(16)
    
    # Generate new CSRF token
    session["csrf_token"] = secrets.token_urlsafe(32)
    
    # Set user data
    session["user_id"] = user_id
    session["username"] = username
    session["_boot"] = current_app.config.get("BOOT_TIME")
    session["_created"] = datetime.now(timezone.utc).isoformat()
    session["_last_activity"] = datetime.now(timezone.utc).isoformat()
    
    # Bind session to IP and User-Agent (defense-in-depth against session fixation)
    session["_ip"] = client_ip()
    session["_user_agent"] = request.headers.get("User-Agent", "")[:200]


def _regenerate_session_secure_minimal():
    """
    Regenerate session without user data - for pre-authentication use.
    
    CRITICAL: Use this BEFORE user lookup in OAuth flows to prevent
    session fixation attacks where attacker pre-sets victim's session.
    """
    from flask import current_app
    
    # Clear old session completely
    session.clear()
    
    # Set permanent and modified flags
    session.permanent = True
    session.modified = True
    
    # Add regeneration marker to force new session ID/signature
    session["_regenerated"] = secrets.token_urlsafe(16)
    
    # Generate new CSRF token
    session["csrf_token"] = secrets.token_urlsafe(32)
    
    # Set session metadata (no user data yet)
    session["_boot"] = current_app.config.get("BOOT_TIME")
    session["_created"] = datetime.now(timezone.utc).isoformat()
    session["_last_activity"] = datetime.now(timezone.utc).isoformat()
    
    # Bind session to IP and User-Agent
    session["_ip"] = client_ip()
    session["_user_agent"] = request.headers.get("User-Agent", "")[:200]


# ── Register ───────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register_page():
    if current_user_id():
        return redirect(url_for("payments.dashboard"))

    if request.method == "GET":
        return render_template("register.html", csrf_token=get_csrf_token())

    username  = (request.form.get("username") or "").strip()
    email     = (request.form.get("email") or "").strip().lower()
    password  = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

    if not valid_username(username):
        flash("Username must be 3–30 characters: letters, digits, underscores only.", "error")
        return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        flash("Please enter a valid email address.", "error")
        return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

    # Validate password strength (VULN-006 fix)
    from services.password_validator import validate_password_strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        flash(error_msg, "error")
        return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

    if password != password2:
        flash("Passwords do not match.", "error")
        return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

    with get_db() as db:
        # Global rate limit to prevent distributed attacks
        if not check_rate_limit(db, "register:global", limit=100, window_secs=3600):
            flash("Service temporarily unavailable — please try again later.", "error")
            return render_template("register.html", csrf_token=get_csrf_token())
        
        # Rate limit registration to prevent spam and account enumeration
        if not check_rate_limit(db, f"register:{client_ip()}", limit=3, window_secs=3600):
            flash("Too many registration attempts — please wait before trying again.", "error")
            return render_template("register.html", csrf_token=get_csrf_token())
        
        # Check for duplicate username
        if db.query(User).filter(User.username == username).first():
            flash("That username is already taken.", "error")
            return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

        # Check for duplicate email
        if db.query(User).filter(User.email == email).first():
            flash("That email address is already registered.", "error")
            return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.add(user)
            db.flush()
            db.refresh(user)
        except Exception as e:
            logger.error("Registration DB error: %s", e, exc_info=True)
            flash("Something went wrong — please try again.", "error")
            return render_template("register.html", username=username, email=email, csrf_token=get_csrf_token())

        # Regenerate session completely to prevent session fixation attacks
        _regenerate_session_secure(user.id, user.username)
        
        log_event(db, "merchant.registered", user_id=user.id, ip_address=client_ip(), detail={"username": username})
        logger.info("New merchant registered: %s", username)
        flash(f"Welcome, {username}! Your account has been created.", "success")
        return redirect(url_for("payments.dashboard"))


# ── Login ──────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user_id():
        return redirect(url_for("payments.dashboard"))

    if request.method == "GET":
        return render_template("login.html", csrf_token=get_csrf_token())

    # CSRF first — before touching the DB or rate limiter
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("login.html", username=username, csrf_token=get_csrf_token())

    with get_db() as db:
        if not check_rate_limit(db, f"login:{client_ip()}", limit=5, window_secs=60, critical=True):
            flash("Too many login attempts — please wait a minute.", "error")
            return render_template("login.html", csrf_token=get_csrf_token())

        user = db.query(User).filter(User.username == username).first()

        if not user or not user.is_active:
            flash("Incorrect username or password.", "error")
            return render_template("login.html", username=username, csrf_token=get_csrf_token())

        if user.is_locked():
            flash("Account temporarily locked due to too many failed attempts. Try again later.", "error")
            return render_template("login.html", csrf_token=get_csrf_token())

        if not user.check_password(password):
            user.record_failed_login(Config.LOGIN_MAX_ATTEMPTS, Config.LOCKOUT_DURATION_SECS)
            log_event(db, "merchant.login_failed", user_id=user.id, ip_address=client_ip(), detail={"username": username})
            flash("Incorrect username or password.", "error")
            return render_template("login.html", username=username, csrf_token=get_csrf_token())

        user.record_successful_login()
        
        # Regenerate session completely to prevent session fixation attacks
        _regenerate_session_secure(user.id, user.username)
        
        log_event(db, "merchant.login", user_id=user.id, ip_address=client_ip(), detail={"username": username})
        logger.info("Merchant logged in: %s", username)
        next_url = request.args.get("next") or url_for("payments.dashboard")
        return redirect(next_url)


# ── Logout ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    from flask import make_response
    username = current_username()
    session.clear()
    logger.info("Merchant logged out: %s", username)
    flash("You have been logged out.", "info")
    response = make_response(redirect(url_for("auth.login_page")))
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return response


# ── Forgot password ────────────────────────────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Password reset request handler.
    
    SECURITY (VULN-004): Implements strict rate limiting and constant-time response
    to prevent username enumeration and distributed attacks.
    """
    if request.method == "GET":
        return render_template("forgot_password.html", csrf_token=get_csrf_token())

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("forgot_password.html", csrf_token=get_csrf_token())

    username = (request.form.get("username") or "").strip()
    
    # Start timing for constant-time response
    import time
    start_time = time.perf_counter()

    with get_db() as db:
        # VULN-004 FIX: Much stricter global limit (10/hour instead of 50/hour)
        if not check_rate_limit(db, "reset:global", limit=10, window_secs=3600):
            # Add delay before error
            time.sleep(0.5 + secrets.randbelow(500) / 1000.0)
            flash("Service temporarily unavailable — please try again later.", "error")
            return render_template("forgot_password.html", csrf_token=get_csrf_token())
        
        # VULN-004 FIX: Stricter IP limit (1 per 15 minutes instead of 2 per 10 minutes)
        if not check_rate_limit(db, f"reset:{client_ip()}", limit=1, window_secs=900):
            time.sleep(0.5 + secrets.randbelow(500) / 1000.0)
            flash("Too many reset attempts. Please wait 15 minutes.", "error")
            return render_template("forgot_password.html", csrf_token=get_csrf_token())
        
        # VULN-004 FIX: Username limit with constant-time response
        username_limited = False
        if username:
            username_limited = not check_rate_limit(
                db, f"reset:user:{username}", limit=1, window_secs=3600
            )
        
        # Query user (always, even if rate limited)
        user = db.query(User).filter(User.username == username).first() if username else None
        
        # Send email only if user exists AND not rate limited
        if user and user.is_active and not username_limited:
            token = generate_reset_token()
            user.reset_token = token
            user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            
            # Send email if user has email, otherwise log to console
            if user.email:
                send_password_reset(user.email, reset_url)
            else:
                logger.info("Password reset link for %s (no email): %s", username, reset_url)
        
        # VULN-004 FIX: Constant-time response to prevent timing-based enumeration
        elapsed = time.perf_counter() - start_time
        target_delay = 0.5  # 500ms baseline
        jitter = secrets.randbelow(200) / 1000.0  # 0-200ms jitter
        remaining = max(0, target_delay + jitter - elapsed)
        time.sleep(remaining)

    # CRITICAL: Always same message to prevent user enumeration
    flash("If that username exists, a reset link has been sent to the registered email address.", "info")
    return redirect(url_for("auth.login_page"))


# ── Reset password ─────────────────────────────────────────────────────────────

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    def _invalid():
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.login_page"))

    # Add rate limiting on token validation to prevent brute-force
    with get_db() as db:
        if not check_rate_limit(db, f"reset_validate:{client_ip()}", limit=10, window_secs=300):
            flash("Too many attempts — please wait before trying again.", "error")
            return redirect(url_for("auth.login_page"))

    if request.method == "GET":
        with get_db() as db:
            user = db.query(User).filter(User.reset_token == token).first()
            if not user or not user.reset_token_expires_at:
                return _invalid()
            expires = user.reset_token_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                return _invalid()
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    password  = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    # Validate password strength (VULN-006 fix)
    from services.password_validator import validate_password_strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        flash(error_msg, "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    if password != password2:
        flash("Passwords do not match.", "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    with get_db() as db:
        user = db.query(User).filter(User.reset_token == token).first()
        if not user or not user.reset_token_expires_at:
            return _invalid()
        expires = user.reset_token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return _invalid()

        # Check if new password is same as current password
        if user.check_password(password):
            flash("New password cannot be the same as your current password.", "error")
            return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

        user.set_password(password)
        user.reset_token            = None
        user.reset_token_expires_at = None
        user.record_successful_login()
        logger.info("Password reset completed for: %s", user.username)

    flash("Password updated — please sign in.", "success")
    return redirect(url_for("auth.login_page"))


# ── Account settings ───────────────────────────────────────────────────────────

@auth_bp.route("/api/account/settings", methods=["POST"])
def update_settings():
    if not current_user_id():
        return error("Authentication required", "UNAUTHENTICATED", 401)

    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)

    # Skip CSRF for API key authenticated requests
    from core.api_auth import is_api_key_authenticated
    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not is_valid_csrf_token(csrf_header):
            return error("CSRF validation failed", "CSRF_ERROR", 403)

    data        = request.get_json(silent=True) or {}
    raw_webhook = data.get("webhook_url", "")
    webhook_url = validate_webhook_url(raw_webhook) if raw_webhook else None

    if raw_webhook and not webhook_url:
        return error("Invalid webhook URL — must be a public HTTPS URL", "VALIDATION_ERROR", 400)

    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            return error("User not found", "NOT_FOUND", 404)
        
        old_webhook = user.webhook_url
        user.webhook_url = webhook_url
        
        # Audit log for settings changes
        log_event(db, "settings.updated", user_id=current_user_id(), ip_address=client_ip(),
                  detail={"old_webhook": old_webhook or "none", "new_webhook": webhook_url or "none"})
        
        logger.info("Webhook URL updated for merchant: %s", user.username)

    return jsonify({"success": True, "message": "Settings updated", "webhook_url": webhook_url})


# ── Google OAuth ───────────────────────────────────────────────────────────────

@auth_bp.route("/auth/google/config", methods=["GET"])
def google_config():
    """
    Provide Google OAuth client configuration to frontend.
    Returns enabled status and client_id if OAuth is configured.
    """
    client_id = Config.GOOGLE_CLIENT_ID
    
    if not client_id:
        return jsonify({"enabled": False})
    
    return jsonify({
        "enabled": True,
        "client_id": client_id
    })


@auth_bp.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """
    Handle Google OAuth callback.
    Receives ID token from frontend, validates it, and creates/links user account.
    """
    # Validate Content-Type
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    
    data = request.get_json(silent=True) or {}
    credential = data.get("credential", "").strip()
    csrf_token = data.get("csrf_token", "")
    
    # Validate CSRF token
    if not is_valid_csrf_token(csrf_token):
        return error("Session expired. Please refresh and try again.", "CSRF_ERROR", 403)
    
    # Validate credential is present
    if not credential:
        return error("Missing credential", "INVALID_REQUEST", 400)
    
    with get_db() as db:
        # Apply rate limiting (5 requests per IP per 60 seconds)
        if not check_rate_limit(db, f"google_oauth:{client_ip()}", limit=5, window_secs=60, critical=True):
            log_event(db, "oauth.rate_limit_exceeded", ip_address=client_ip(), 
                     detail={"provider": "google"})
            return error("Too many authentication attempts. Please wait and try again.", 
                        "RATE_LIMIT_EXCEEDED", 429)
        
        try:
            # Validate token
            client_id = Config.GOOGLE_CLIENT_ID
            if not client_id:
                logger.error("Google OAuth not configured (missing GOOGLE_CLIENT_ID)")
                return error("Google authentication is not available.", "SERVICE_UNAVAILABLE", 503)
            
            validator = GoogleTokenValidator(client_id)
            token_payload = validator.validate_token(credential)
            
            # SECURITY FIX (VULN-001): Regenerate session IMMEDIATELY after token validation
            # This MUST happen BEFORE any user lookup or account creation to prevent session fixation
            # Attacker cannot pre-set victim's session because session is regenerated here
            _regenerate_session_secure_minimal()
            
            # Extract profile
            profile = GoogleProfileExtractor.extract_profile(token_payload)
            
            # Check if user exists by google_id
            user = User.find_by_google_id(db, profile['google_id'])
            
            if user:
                # User exists with this Google ID - log them in
                # Session already regenerated above, just set user data
                session["user_id"] = user.id
                session["username"] = user.username
                log_event(db, "oauth.login", user_id=user.id, ip_address=client_ip(),
                         detail={"provider": "google", "email": profile['email']})
                logger.info("Google OAuth login: %s", user.username)
                return jsonify({"success": True, "redirect_url": url_for("payments.dashboard")})
            
            # User doesn't exist by google_id - check by email
            user = User.find_by_email(db, profile['email'])
            
            if user:
                # Email exists - check if already linked to different Google account
                if user.google_id and user.google_id != profile['google_id']:
                    log_event(db, "oauth.account_conflict", user_id=user.id, ip_address=client_ip(),
                             detail={"provider": "google", "email": profile['email']})
                    return error("This email is already linked to a different Google account.", 
                                "ACCOUNT_CONFLICT", 409)
                
                # Link Google account to existing user
                user.link_google_account(
                    profile['google_id'],
                    profile['profile_picture_url'],
                    profile['full_name']
                )
                db.flush()
                
                # Session already regenerated above, just set user data
                session["user_id"] = user.id
                session["username"] = user.username
                log_event(db, "oauth.account_linked", user_id=user.id, ip_address=client_ip(),
                         detail={"provider": "google", "email": profile['email']})
                logger.info("Google account linked to existing user: %s", user.username)
                flash(f"Welcome back, {user.username}! Your Google account has been linked.", "success")
                return jsonify({"success": True, "redirect_url": url_for("payments.dashboard")})
            
            # No existing user - create new account
            user = User.create_from_google(db, profile)
            db.flush()
            db.refresh(user)
            
            # Session already regenerated above, just set user data
            session["user_id"] = user.id
            session["username"] = user.username
            log_event(db, "oauth.account_created", user_id=user.id, ip_address=client_ip(),
                     detail={"provider": "google", "email": profile['email'], "username": user.username})
            logger.info("New user created via Google OAuth: %s", user.username)
            flash(f"Welcome, {user.username}! Your account has been created.", "success")
            return jsonify({"success": True, "redirect_url": url_for("payments.dashboard")})
            
        except ValueError as e:
            # Token validation or profile extraction failed
            error_msg = str(e)
            log_event(db, "oauth.authentication_failed", ip_address=client_ip(),
                     detail={"provider": "google", "error": error_msg})
            logger.warning("Google OAuth authentication failed: %s | ip=%s", error_msg, client_ip())
            
            # Return user-friendly error message
            if "not verified" in error_msg.lower():
                return error("Please verify your email address with Google before signing in.", 
                            "UNVERIFIED_EMAIL", 401)
            else:
                return error("Authentication failed. Please try again.", "INVALID_TOKEN", 401)
        
        except Exception as e:
            # Unexpected error
            logger.error("Google OAuth unexpected error: %s | ip=%s", str(e), client_ip(), exc_info=True)
            log_event(db, "oauth.internal_error", ip_address=client_ip(),
                     detail={"provider": "google", "error": "Internal error"})
            return error("An error occurred. Please try again later.", "INTERNAL_ERROR", 500)


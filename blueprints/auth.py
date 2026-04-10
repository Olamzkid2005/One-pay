"""
OnePay — Auth blueprint
Handles: register, login, logout, password reset, account settings
"""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

import requests
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import Config
from core.audit import log_event
from core.auth import (
    current_user_id,
    current_username,
    get_csrf_token,
    is_valid_csrf_token,
    valid_username,
)
from core.decorators import rate_limit
from core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from core.ip import client_ip
from core.responses import error
from database import get_db
from models.user import User
from services.email import send_password_reset
from services.github_oauth import GitHubOAuthService
from services.google_oauth import GoogleProfileExtractor, GoogleTokenValidator
from services.rate_limiter import check_rate_limit
from services.security import generate_reset_token, validate_webhook_url
from services.validators import validate_email, validate_phone

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


def _validate_registration_inputs(username: str, raw_email: str, password: str, password2: str):
    """
    Validate registration form inputs.
    Returns (email, error_message) — email is None if invalid.
    """
    from services.password_validator import validate_password_strength

    email = validate_email(raw_email)

    if not valid_username(username):
        return None, "Username must be 3–30 characters: letters, digits, underscores only."
    if not email:
        return None, "Please enter a valid email address."

    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return email, error_msg
    if password != password2:
        return email, "Passwords do not match."
    return email, None


@auth_bp.route("/register", methods=["GET", "POST"])
def register_page():
    if current_user_id():
        return redirect(url_for("payments.dashboard"))

    if request.method == "GET":
        return render_template("register.html", csrf_token=get_csrf_token())

    username = (request.form.get("username") or "").strip()
    raw_email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    def _re_render(msg=None):
        if msg:
            flash(msg, "error")
        return render_template("register.html", username=username, email=raw_email, csrf_token=get_csrf_token())

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        return _re_render("Session expired — please refresh and try again.")

    email, err = _validate_registration_inputs(username, raw_email, password, password2)
    if err:
        return _re_render(err)

    with get_db() as db:
        if not check_rate_limit(db, "register:global", limit=100, window_secs=3600):
            return _re_render("Service temporarily unavailable — please try again later.")
        if not check_rate_limit(db, f"register:{client_ip()}", limit=3, window_secs=3600):
            return _re_render("Too many registration attempts — please wait before trying again.")
        if db.query(User).filter(User.username == username).first():
            return _re_render("That username is already taken.")
        if db.query(User).filter(User.email == email).first():
            return _re_render("That email address is already registered.")

        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.add(user)
            db.flush()
            db.refresh(user)
        except Exception as e:
            logger.error("Registration failed | username=%s error=%s", username, e, exc_info=True)
            return _re_render("Unable to create account. Please try again later.")

        _regenerate_session_secure(user.id, user.username)
        log_event(db, "merchant.registered", user_id=user.id, ip_address=client_ip(), detail={"username": username})
        logger.info("New merchant registered: %s", username)
        flash(f"Welcome, {username}! Your account has been created.", "success")
        return redirect(url_for("payments.dashboard"))


# ── Login ──────────────────────────────────────────────────────────────────────


def _handle_login_2fa(db, user, username: str):
    """Send 2FA code and redirect to verify page."""
    from services.email import send_2fa_code
    otp_code = str(secrets.randbelow(1000000)).zfill(6)
    user.email_otp = otp_code
    user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    send_2fa_code(user.email, otp_code)
    session["pre_2fa_user_id"] = user.id
    log_event(db, "2fa.code_sent", user_id=user.id, ip_address=client_ip(), detail={"username": username})
    return redirect(url_for("auth.verify_2fa"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user_id():
        return redirect(url_for("payments.dashboard"))
    if request.method == "GET":
        return render_template("login.html", csrf_token=get_csrf_token())

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

        if getattr(user, "two_factor_enabled", False):
            return _handle_login_2fa(db, user, username)

        _regenerate_session_secure(user.id, user.username)
        log_event(db, "merchant.login", user_id=user.id, ip_address=client_ip(), detail={"username": username})
        logger.info("Merchant logged in: %s", username)
        return redirect(request.args.get("next") or url_for("payments.dashboard"))


# ── Logout ─────────────────────────────────────────────────────────────────────


@auth_bp.route("/logout")
def logout():
    from flask import make_response

    username = current_username()
    session.clear()
    logger.info("Merchant logged out: %s", username)
    flash("You have been logged out.", "info")
    response = make_response(redirect(url_for("auth.login_page")))
    response.headers["Clear-Site-Data"] = "cache, cookies, storage, executionContexts"
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
            username_limited = not check_rate_limit(db, f"reset:user:{username}", limit=1, window_secs=3600)

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
    flash(
        "If that username exists, a reset link has been sent to the registered email address.",
        "info",
    )
    return redirect(url_for("auth.login_page"))


# ── Reset password ─────────────────────────────────────────────────────────────


def verify_captcha(token: str) -> bool:
    """Verify hCaptcha token."""
    if not Config.HCAPTCHA_SECRET_KEY:
        logger.warning("HCAPTCHA_SECRET_KEY not configured, skipping verification")
        return True
    try:
        response = requests.post(
            "https://hcaptcha.com/siteverify",
            data={"secret": Config.HCAPTCHA_SECRET_KEY, "response": token},
            timeout=10
        )
        return response.json().get("success", False)
    except Exception as e:
        logger.error("CAPTCHA verification failed: %s", e)
        return False


def _get_valid_reset_user(db, token: str):
    """Return user if reset token is valid and not expired, else None."""
    user = db.query(User).filter(User.reset_token == token).first()
    if not user or not user.reset_token_expires_at:
        return None
    expires = user.reset_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return None
    return user


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    def _invalid():
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.login_page"))

    with get_db() as db:
        if not check_rate_limit(db, f"reset_validate:{client_ip()}", limit=10, window_secs=300):
            flash("Too many attempts — please wait before trying again.", "error")
            return redirect(url_for("auth.login_page"))

    if request.method == "GET":
        with get_db() as db:
            if not _get_valid_reset_user(db, token):
                return _invalid()
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    # Verify CAPTCHA if enabled
    if Config.HCAPTCHA_ENABLED:
        captcha_token = request.form.get("h-captcha-response")
        if not captcha_token or not verify_captcha(captcha_token):
            flash("CAPTCHA verification failed. Please try again.", "error")
            return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    from services.password_validator import validate_password_strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        flash(error_msg, "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    if password != password2:
        flash("Passwords do not match.", "error")
        return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

    with get_db() as db:
        user = _get_valid_reset_user(db, token)
        if not user:
            return _invalid()
        if user.check_password(password):
            flash("New password cannot be the same as your current password.", "error")
            return render_template("reset_password.html", token=token, csrf_token=get_csrf_token())

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires_at = None
        user.record_successful_login()
        logger.info("Password reset completed for: %s", user.username)

    flash("Password updated — please sign in.", "success")
    return redirect(url_for("auth.login_page"))


# ── Account settings ───────────────────────────────────────────────────────────


@auth_bp.route("/account/settings", methods=["POST"])
def update_settings():
    if not current_user_id():
        raise AuthenticationError()

    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    # Skip CSRF for API key authenticated requests
    from core.api_auth import is_api_key_authenticated

    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not is_valid_csrf_token(csrf_header):
            raise AuthorizationError("CSRF validation failed")

    data = request.get_json(silent=True) or {}
    raw_webhook = data.get("webhook_url", "")
    webhook_url = validate_webhook_url(raw_webhook) if raw_webhook else None

    if raw_webhook and not webhook_url:
        raise ValidationError("Invalid webhook URL — must be a public HTTPS URL")

    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            raise ValidationError("User not found")

        old_webhook = user.webhook_url
        user.webhook_url = webhook_url

        # Audit log for settings changes
        log_event(
            db,
            "settings.updated",
            user_id=current_user_id(),
            ip_address=client_ip(),
            detail={
                "old_webhook": old_webhook or "none",
                "new_webhook": webhook_url or "none",
            },
        )

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

    return jsonify({"enabled": True, "client_id": client_id})


def _handle_oauth_2fa_or_login(db, user, provider: str, profile: dict):
    """Handle 2FA check or direct login for OAuth flows. Returns JSON response or None."""
    if getattr(user, "two_factor_enabled", False):
        from services.email import send_2fa_code
        otp_code = str(secrets.randbelow(1000000)).zfill(6)
        user.email_otp = otp_code
        user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        send_2fa_code(user.email, otp_code)
        session["pre_2fa_user_id"] = user.id
        log_event(db, "2fa.code_sent", user_id=user.id, ip_address=client_ip(), detail={"provider": provider})
        return jsonify({"success": True, "redirect_url": url_for("auth.verify_2fa")})
    session["user_id"] = user.id
    session["username"] = user.username
    return None


def _resolve_google_user(db, profile: dict):
    """
    Find or create a user from a Google OAuth profile.
    Returns (user, event_name, flash_message).
    Raises OnePayError on account conflict.
    """
    from core.exceptions import OnePayError

    user = User.find_by_google_id(db, profile["google_id"])
    if user:
        return user, "oauth.login", None

    user = User.find_by_email(db, profile["email"])
    if user:
        if user.google_id and user.google_id != profile["google_id"]:
            log_event(db, "oauth.account_conflict", user_id=user.id, ip_address=client_ip(),
                      detail={"provider": "google", "email": profile["email"]})
            raise OnePayError("This email is already linked to a different Google account.", "ACCOUNT_CONFLICT", 409)
        user.link_google_account(profile["google_id"], profile["profile_picture_url"], profile["full_name"])
        db.flush()
        return user, "oauth.account_linked", f"Welcome back, {user.username}! Your Google account has been linked."

    user = User.create_from_google(db, profile)
    db.flush()
    db.refresh(user)
    return user, "oauth.account_created", f"Welcome, {user.username}! Your account has been created."


@auth_bp.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """Handle Google OAuth callback."""
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    data = request.get_json(silent=True) or {}
    credential = data.get("credential", "").strip()
    if not is_valid_csrf_token(data.get("csrf_token", "")):
        raise AuthorizationError("Session expired. Please refresh and try again.")
    if not credential:
        raise ValidationError("Missing credential")

    with get_db() as db:
        if not check_rate_limit(db, f"google_oauth:{client_ip()}", limit=5, window_secs=60, critical=True):
            log_event(db, "oauth.rate_limit_exceeded", ip_address=client_ip(), detail={"provider": "google"})
            from core.exceptions import OnePayError
            raise OnePayError("Too many authentication attempts. Please wait and try again.", "RATE_LIMIT_EXCEEDED", 429)

        try:
            client_id = Config.GOOGLE_CLIENT_ID
            if not client_id:
                from core.exceptions import OnePayError
                raise OnePayError("Google authentication is not available.", "SERVICE_UNAVAILABLE", 503)

            token_payload = GoogleTokenValidator(client_id).validate_token(credential)
            _regenerate_session_secure_minimal()
            profile = GoogleProfileExtractor.extract_profile(token_payload)

            user, event_name, flash_msg = _resolve_google_user(db, profile)
            resp = _handle_oauth_2fa_or_login(db, user, "google", profile)
            if resp:
                return resp

            detail = {"provider": "google", "email": profile["email"]}
            if event_name == "oauth.account_created":
                detail["username"] = user.username
            log_event(db, event_name, user_id=user.id, ip_address=client_ip(), detail=detail)
            logger.info("Google OAuth %s: %s", event_name, user.username)
            if flash_msg:
                flash(flash_msg, "success")
            return jsonify({"success": True, "redirect_url": url_for("payments.dashboard")})

        except ValueError as e:
            error_msg = str(e)
            logger.warning("Google OAuth validation failed | ip=%s error=%s", client_ip(), error_msg)
            log_event(db, "oauth.authentication_failed", ip_address=client_ip(), detail={"provider": "google", "error": error_msg})
            if "not verified" in error_msg.lower():
                raise AuthenticationError("Please verify your email address with Google before signing in.")
            raise AuthenticationError("Authentication failed. Please try again.")

        except OnePayError:
            raise

        except Exception as e:
            logger.error("Google OAuth error | ip=%s error=%s", client_ip(), e, exc_info=True)
            log_event(db, "oauth.internal_error", ip_address=client_ip(), detail={"provider": "google", "error": "Internal error"})
            from core.exceptions import OnePayError
            raise OnePayError("An error occurred. Please try again later.", "INTERNAL_ERROR", 500)


# ── 2FA Verification ──────────────────────────────────────────────────────────


@auth_bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    pre_2fa_user_id = session.get("pre_2fa_user_id")
    if not pre_2fa_user_id:
        return redirect(url_for("auth.login_page"))

    if request.method == "GET":
        return render_template("verify_2fa.html", csrf_token=get_csrf_token())

    if not is_valid_csrf_token(request.form.get("csrf_token")):
        flash("Session expired — please refresh and try again.", "error")
        return render_template("verify_2fa.html", csrf_token=get_csrf_token())

    code1 = request.form.get("code1", "")
    code2 = request.form.get("code2", "")
    code3 = request.form.get("code3", "")
    code4 = request.form.get("code4", "")
    code5 = request.form.get("code5", "")
    code6 = request.form.get("code6", "")

    code = f"{code1}{code2}{code3}{code4}{code5}{code6}".strip()

    with get_db() as db:
        # Rate limit by both IP and user ID to prevent distributed brute-force attacks
        ip_limiter_key = f"2fa:{client_ip()}"
        user_limiter_key = f"2fa_user:{pre_2fa_user_id}"

        if not check_rate_limit(db, ip_limiter_key, limit=5, window_secs=60, critical=True, use_memory=False) or not check_rate_limit(
            db, user_limiter_key, limit=5, window_secs=60, critical=True, use_memory=False
        ):
            flash("Too many attempts — please wait a minute.", "error")
            return render_template("verify_2fa.html", csrf_token=get_csrf_token())

        user = db.query(User).filter(User.id == pre_2fa_user_id).first()
        if not user:
            session.clear()
            return redirect(url_for("auth.login_page"))

        if user.is_2fa_locked():
            flash(
                "Account temporarily locked due to too many failed 2FA attempts. Try again later.",
                "error",
            )
            return render_template("verify_2fa.html", csrf_token=get_csrf_token())

        if not user.email_otp or not user.email_otp_expires_at:
            flash("Invalid or expired code.", "error")
            return render_template("verify_2fa.html", csrf_token=get_csrf_token())

        expires = user.email_otp_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires or user.email_otp != code:
            user.record_failed_2fa()
            log_event(
                db,
                "2fa.failed",
                user_id=user.id,
                ip_address=client_ip(),
                detail={"attempts": user.failed_2fa_attempts},
            )
            flash("Invalid or expired code.", "error")
            return render_template("verify_2fa.html", csrf_token=get_csrf_token())

        user.email_otp = None
        user.email_otp_expires_at = None
        user.record_successful_2fa()

        _regenerate_session_secure(user.id, user.username)
        log_event(db, "2fa.success", user_id=user.id, ip_address=client_ip())

        return redirect(url_for("payments.dashboard"))


# ── GitHub OAuth ───────────────────────────────────────────────────────────────


@auth_bp.route("/auth/github/login", methods=["GET"])
def github_login():
    try:
        url = GitHubOAuthService.get_auth_url()
        return redirect(url)
    except Exception:
        flash("GitHub login is currently unavailable.", "error")
        return redirect(url_for("auth.login_page"))


def _resolve_github_user(db, profile: dict):
    """Find or create user from GitHub profile. Returns (user, event, flash_msg)."""
    user = User.find_by_github_id(db, profile["github_id"])
    if user:
        return user, "oauth.login", None

    user = User.find_by_email(db, profile["email"])
    if user:
        user.link_github_account(profile["github_id"], profile["profile_picture_url"], profile["full_name"])
        db.flush()
        return user, "oauth.account_linked", f"Welcome back, {user.username}! Your GitHub account has been linked."

    user = User.create_from_github(db, profile)
    db.flush()
    db.refresh(user)
    return user, "oauth.account_created", f"Welcome, {user.username}! Your account has been created."


@auth_bp.route("/auth/github/callback", methods=["GET"])
def github_callback():
    code = request.args.get("code")
    if not code:
        flash("GitHub login failed -- no code provided.", "error")
        return redirect(url_for("auth.login_page"))

    with get_db() as db:
        if not check_rate_limit(db, f"github_oauth:{client_ip()}", limit=5, window_secs=60, critical=True):
            flash("Too many authentication attempts. Please wait.", "error")
            return redirect(url_for("auth.login_page"))

        try:
            _regenerate_session_secure_minimal()
            token = GitHubOAuthService.exchange_code_for_token(code)
            profile = GitHubOAuthService.get_user_profile(token)

            user, event_name, flash_msg = _resolve_github_user(db, profile)
            resp = _handle_oauth_2fa_or_login(db, user, "github", profile)
            if resp:
                return resp

            _regenerate_session_secure(user.id, user.username)
            log_event(db, event_name, user_id=user.id, ip_address=client_ip(), detail={"provider": "github"})
            if flash_msg:
                flash(flash_msg, "success")
            return redirect(url_for("payments.dashboard"))

        except Exception as e:
            logger.error("GitHub OAuth error | ip=%s error=%s", client_ip(), e, exc_info=True)
            flash("Authentication failed. Please try again.", "error")
            return redirect(url_for("auth.login_page"))


# ── 2FA Settings ───────────────────────────────────────────────────────────────


@auth_bp.route("/account/2fa/disable", methods=["POST"])
def disable_2fa():
    """
    Disable two-factor authentication for the current user.

    Sets two_factor_enabled to False (Requirement 4.4).
    """
    if not current_user_id():
        raise AuthenticationError()

    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    from core.api_auth import is_api_key_authenticated

    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not is_valid_csrf_token(csrf_header):
            raise AuthorizationError("CSRF validation failed")

    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            raise ValidationError("User not found")

        user.two_factor_enabled = False

        log_event(
            db,
            "2fa.disabled",
            user_id=current_user_id(),
            ip_address=client_ip(),
            detail={"username": user.username},
        )

        logger.info("2FA disabled for user: %s", user.username)

    return jsonify({"success": True, "message": "Two-factor authentication has been disabled"})

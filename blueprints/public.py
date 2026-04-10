"""
OnePay — Public blueprint
Handles: verify page, preview API, transfer-status polling, health check
No login required — these are customer-facing routes.
"""

import json
import logging
from datetime import datetime, timezone

import sqlalchemy
from flask import (
    Blueprint,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
)

from config import Config
from core.audit import log_event
from core.auth import valid_tx_ref
from core.exceptions import AuthenticationError, AuthorizationError, ProviderError, ValidationError
from core.ip import client_ip
from core.responses import error, rate_limited
from database import engine, get_db
from models.transaction import Transaction, TransactionStatus
from models.user import User
from services.korapay import KoraPayError, korapay
from services.rate_limiter import check_rate_limit, cleanup_old_rate_limits
from services.security import verify_hash_token

logger = logging.getLogger(__name__)
public_bp = Blueprint("public", __name__)


# ── Root route ────────────────────────────────────────────────────────────────


@public_bp.route("/")
def index():
    """Root route - redirect to dashboard if authenticated, otherwise to login."""
    from flask import redirect, session

    if session.get("user_id"):
        return redirect("/api/v1/", code=302)
    return redirect("/api/v1/login", code=302)


# ── Login route alias ─────────────────────────────────────────────────────────


@public_bp.route("/login")
def login():
    """Redirect /login to the actual login endpoint."""
    return redirect("/api/v1/login", code=301)


# ── Register route alias ──────────────────────────────────────────────────────


@public_bp.route("/register")
def register():
    """Redirect /register to the actual register endpoint."""
    return redirect("/api/v1/register", code=301)


# ── security.txt route (RFC 9116) ───────────────────────────────────────────────────


@public_bp.route("/.well-known/security.txt")
def security_txt():
    """Serve security.txt file for RFC 9116 compliance."""
    from flask import send_from_directory
    return send_from_directory("static/.well-known", "security.txt")


# ── Google OAuth route aliases ─────────────────────────────────────────────────


@public_bp.route("/auth/google/config", methods=["GET"])
def google_config():
    """Proxy /auth/google/config to the actual OAuth config endpoint."""
    from blueprints.auth import google_config as _google_config
    return _google_config()


@public_bp.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """Proxy /auth/google/callback to the actual OAuth callback endpoint."""
    from blueprints.auth import google_callback as _google_callback
    return _google_callback()


# ── API route aliases (frontend uses /api/ prefix but routes are at /api/v1/) ──
# Direct proxies instead of 307 redirects — fetch doesn't reliably follow
# 307 redirects for POST requests with JSON bodies.


@public_bp.route("/api/payments/link", methods=["POST"])
def api_create_payment_link():
    from blueprints.payments import create_payment_link
    return create_payment_link()


@public_bp.route("/api/payments/status/<tx_ref>", methods=["GET"])
def api_payment_status(tx_ref):
    from blueprints.payments import transaction_status
    return transaction_status(tx_ref)


@public_bp.route("/api/payments/history", methods=["GET"])
def api_payment_history():
    from blueprints.payments import transaction_history
    return transaction_history()


@public_bp.route("/api/account/settings", methods=["GET", "POST"])
def api_account_settings():
    from blueprints.auth import update_settings
    return update_settings()


@public_bp.route("/api/payments/reissue/<tx_ref>", methods=["POST"])
def api_payment_reissue(tx_ref):
    from blueprints.payments import reissue_payment_link
    return reissue_payment_link(tx_ref)


@public_bp.route("/api/payments/receipt/<tx_ref>", methods=["GET"])
def api_payment_receipt(tx_ref):
    from blueprints.payment_actions import download_receipt
    return download_receipt(tx_ref)


@public_bp.route("/api/payments/receipt/<tx_ref>/preview", methods=["GET"])
def api_payment_receipt_preview(tx_ref):
    from blueprints.payment_actions import preview_receipt_html
    return preview_receipt_html(tx_ref)


@public_bp.route("/api/settings/webhook", methods=["POST"])
def api_settings_webhook():
    from blueprints.payments import update_webhook_settings
    return update_webhook_settings()


@public_bp.route("/api/payments/summary", methods=["GET"])
def api_payment_summary():
    from blueprints.payments import payment_summary
    return payment_summary()


@public_bp.route("/api/invoices", methods=["GET"])
def api_invoices_list():
    from blueprints.invoices import list_invoices
    return list_invoices()


@public_bp.route("/api/invoices/<invoice_number>/download", methods=["GET"])
def api_invoice_download(invoice_number):
    from blueprints.invoices import download_invoice
    return download_invoice(invoice_number)


@public_bp.route("/api/invoices/<invoice_number>/send", methods=["POST"])
def api_invoice_send(invoice_number):
    from blueprints.invoices import send_invoice
    return send_invoice(invoice_number)


@public_bp.route("/api/invoices/settings", methods=["GET", "POST"])
def api_invoices_settings():
    from flask import request as _req

    from blueprints.invoices import get_invoice_settings, update_invoice_settings
    if _req.method == "POST":
        return update_invoice_settings()
    return get_invoice_settings()


# ── Pay page (clean URL — hash validated server-side) ─────────────────────────


def _validate_pay_page_transaction(db, tx_ref: str) -> tuple:
    """
    Validate transaction for pay page. Returns (t, link_error, qr_payment_url, qr_virtual_account).
    """
    t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
    if not t:
        logger.warning("Transaction not found | tx_ref=%s ip=%s", tx_ref, client_ip())
        return None, "This payment link was not found. Please request a new one.", None, None

    qr_payment_url = t.qr_code_payment_url
    qr_virtual_account = t.qr_code_virtual_account

    hash_valid = verify_hash_token(tx_ref, t.amount, t.expires_at, t.hash_token)
    if not hash_valid:
        logger.warning("Hash validation failed | tx_ref=%s ip=%s", tx_ref, client_ip())
        return t, "This payment link is invalid or has been tampered with.", qr_payment_url, qr_virtual_account
    if t.is_expired():
        logger.info("Transaction expired | tx_ref=%s", tx_ref)
        return t, "This payment link has expired. Please request a new one.", qr_payment_url, qr_virtual_account

    return t, "", qr_payment_url, qr_virtual_account


def _confirm_transfer_and_notify(db, t_locked, tx_ref: str) -> object:
    """Confirm transfer via KoraPay and send notifications. Returns JSON response."""
    from services.webhook import deliver_webhook, send_payment_notification_emails, sync_invoice_on_transaction_update

    result = korapay.confirm_transfer(tx_ref)
    if result.get("responseCode", "") != "00":
        return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

    t_locked.transfer_confirmed = True
    t_locked.status = TransactionStatus.VERIFIED
    db.flush()

    if t_locked.webhook_url:
        deliver_webhook(db, t_locked)

    sync_invoice_on_transaction_update(db, t_locked)

    user_for_email = db.query(User).filter(User.id == t_locked.user_id).first()
    if user_for_email:
        send_payment_notification_emails(db, t_locked, user_for_email)

    log_event(db, "transfer_confirmed", t_locked.user_id, tx_ref=tx_ref,
              detail={"tx_ref": tx_ref, "amount": str(t_locked.amount)})
    return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})


@public_bp.route("/pay/<tx_ref>")
def pay_page(tx_ref):
    try:
        logger.info("pay_page accessed | tx_ref=%s ip=%s", tx_ref, client_ip())
        return_url = ""

        if not valid_tx_ref(tx_ref):
            return render_template("verify.html", tx_ref=tx_ref, return_url="",
                                   link_error="Invalid transaction reference format.",
                                   qr_code_payment_url=None, qr_code_virtual_account=None)

        with get_db() as db:
            if not check_rate_limit(db, f"verify_page:{client_ip()}",
                                    Config.RATE_LIMIT_VERIFY_PAGE_ATTEMPTS,
                                    window_secs=Config.RATE_LIMIT_VERIFY_PAGE_WINDOW_SECS):
                return render_template("verify.html", tx_ref=tx_ref, return_url="",
                                       link_error="Too many verification attempts — please wait and try again.",
                                       qr_code_payment_url=None, qr_code_virtual_account=None)

            t, link_error, qr_payment_url, qr_virtual_account = _validate_pay_page_transaction(db, tx_ref)
            if t and t.return_url:
                return_url = t.return_url

        if link_error:
            logger.warning("Pay page rejected | ip=%s tx_ref=%s error=%s", client_ip(), tx_ref, link_error)
            return render_template("verify.html", tx_ref=tx_ref, return_url=return_url,
                                   link_error=link_error, qr_code_payment_url=None, qr_code_virtual_account=None)

        session[f"pay_access_{tx_ref}"] = True
        logger.info("Pay page accepted | ip=%s tx_ref=%s", client_ip(), tx_ref)

        response = make_response(render_template("verify.html", tx_ref=tx_ref, return_url=return_url,
                                                  link_error="", qr_code_payment_url=qr_payment_url,
                                                  qr_code_virtual_account=qr_virtual_account))
        if return_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(return_url)
                if parsed.netloc:
                    response.headers["Content-Security-Policy"] = f"frame-ancestors 'self' https://{parsed.netloc}"
            except Exception as e:
                logger.warning("Failed to parse return_url for frame protection: %s", e)
        return response

    except Exception as e:
        logger.error("Exception in pay_page | tx_ref=%s error=%s", tx_ref, e, exc_info=True)
        return render_template("verify.html", tx_ref=tx_ref, return_url="",
                               link_error="Internal server error",
                               qr_code_payment_url=None, qr_code_virtual_account=None)


# ── Verified page ───────────────────────────────────────────────────────────────


@public_bp.route("/verified/<tx_ref>")
def verified_page(tx_ref):
    """Show verified page if transaction is confirmed, otherwise redirect to pay page."""
    if not valid_tx_ref(tx_ref):
        return redirect("/pay/invalid", code=301)

    with get_db() as db:
        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not t:
            return redirect("/pay/invalid", code=301)

        # If not yet confirmed, redirect to pay page to start polling
        if not t.transfer_confirmed:
            return redirect(f"/pay/{tx_ref}", code=302)

        # Already confirmed - show verified page
        return render_template(
            "verified.html", tx_ref=tx_ref, return_url=t.return_url or ""
        )


# ── Legacy verify route — redirect to clean URL ────────────────────────────────


@public_bp.route("/verify/<tx_ref>")
@public_bp.route("/verify/<tx_ref>/<hash_in_path>")
def verify_page(tx_ref, hash_in_path=None):
    """Backwards-compatible redirect to the clean /pay/ URL."""
    from flask import redirect

    return redirect(f"/pay/{tx_ref}", code=301)


# ── Preview API ────────────────────────────────────────────────────────────────


@public_bp.route("/api/payments/preview/<tx_ref>", methods=["GET"])
def get_preview(tx_ref):
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not t:
            raise ValidationError("Transaction not found")

        # Access control: session token set by pay_page, OR re-validate hash from DB
        # (fallback covers cookie-disabled browsers and direct API calls with valid links)
        if not session.get(f"pay_access_{tx_ref}"):
            if not verify_hash_token(tx_ref, t.amount, t.expires_at, t.hash_token):
                raise AuthorizationError("Access denied")
            # Grant session access for subsequent poll calls
            session[f"pay_access_{tx_ref}"] = True

        return jsonify(
            {
                "success": True,
                "tx_ref": t.tx_ref,
                "amount": str(t.amount),
                "currency": t.currency,
                "description": t.description,
                "expires_at": t.expires_at_utc_iso(),
                "is_expired": t.is_expired(),
                "is_used": t.is_used,
                "status": t.effective_status_value(),
                "virtual_account_number": t.virtual_account_number,
                "virtual_bank_name": t.virtual_bank_name,
                "virtual_account_name": t.virtual_account_name,
                "transfer_confirmed": t.transfer_confirmed,
                "qr_code_payment_url": t.qr_code_payment_url,
                "qr_code_virtual_account": t.qr_code_virtual_account,
            }
        )


# ── Transfer status polling ────────────────────────────────────────────────────


@public_bp.route("/api/payments/transfer-status/<tx_ref>", methods=["GET"])
def transfer_status(tx_ref):
    """Poll transfer confirmation status."""
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")
    if not session.get(f"pay_access_{tx_ref}"):
        raise AuthorizationError("Access denied")

    ip = client_ip()
    with get_db() as db:
        if not check_rate_limit(db, f"poll:{ip}", Config.RATE_LIMIT_VERIFY):
            return rate_limited()

        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not t:
            raise ValidationError("Transaction not found")
        if t.transfer_confirmed:
            return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})
        if t.is_used:
            return jsonify({"success": False, "status": "used", "tx_ref": tx_ref})
        if t.is_expired():
            if t.status != TransactionStatus.EXPIRED:
                t.status = TransactionStatus.EXPIRED
                db.flush()
                from services.webhook import sync_invoice_on_transaction_update
                sync_invoice_on_transaction_update(db, t)
            return jsonify({"success": False, "status": "expired", "tx_ref": tx_ref})

        if not korapay.is_transfer_configured():
            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

        t_locked = (
            db.query(Transaction).filter(Transaction.tx_ref == tx_ref)
            .with_for_update().first()
        )
        if not t_locked:
            raise ValidationError("Transaction not found")
        if t_locked.transfer_confirmed:
            return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})

        try:
            return _confirm_transfer_and_notify(db, t_locked, tx_ref)
        except KoraPayError as e:
            logger.error("KoraPay error during transfer confirmation | tx_ref=%s error=%s", tx_ref, e)
            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

        except KoraPayError as e:
            logger.error("KoraPay error confirming transfer %s: %s", tx_ref, e)
            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})


# ── KoraPay Webhook ────────────────────────────────────────────────────────────


def _forward_to_voicepay(t, reference: str) -> None:
    """Forward confirmed payment to VoicePay if applicable (best-effort)."""
    from config import Config
    if not (Config.VOICEPAY_WEBHOOK_ENABLED and reference.startswith("VP-BILL-")):
        return
    try:
        from services.voicepay_webhook import build_voicepay_payload, send_voicepay_webhook
        if Config.KORAPAY_USE_SANDBOX and Config.VOICEPAY_WEBHOOK_URL_SANDBOX:
            webhook_url = Config.VOICEPAY_WEBHOOK_URL_SANDBOX
            webhook_secret = Config.VOICEPAY_WEBHOOK_SECRET_SANDBOX
        else:
            webhook_url = Config.VOICEPAY_WEBHOOK_URL
            webhook_secret = Config.VOICEPAY_WEBHOOK_SECRET
        result = send_voicepay_webhook(
            payload=build_voicepay_payload(t),
            webhook_url=webhook_url,
            secret=webhook_secret,
            timeout=Config.VOICEPAY_WEBHOOK_TIMEOUT_SECS,
            max_retries=Config.VOICEPAY_WEBHOOK_MAX_RETRIES,
        )
        if result.get("success"):
            logger.info("VoicePay webhook delivered | ref=%s status_code=%d", reference, result.get("status_code"))
        else:
            logger.warning("VoicePay webhook delivery failed | ref=%s error=%s", reference, result.get("error"))
    except Exception as e:
        logger.error("VoicePay webhook forwarding error | ref=%s error=%s", reference, e, exc_info=True)


def _parse_and_verify_korapay_webhook(db, ip: str) -> tuple:
    """
    Parse, validate and verify a KoraPay webhook request.
    Returns (payload, event, data, reference, status, amount) or raises.
    """
    from services.korapay import verify_korapay_webhook_signature

    signature = request.headers.get("x-korapay-signature")
    if not signature:
        logger.warning("Webhook missing signature | ip=%s", ip)
        log_event(db, "webhook.signature_missing", None, detail={"ip": ip})
        raise AuthenticationError("Missing signature")

    try:
        raw_body = request.get_data(as_text=False)
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Webhook invalid JSON | ip=%s", ip)
        raise ValidationError("Invalid JSON")

    if "data" not in payload:
        logger.warning("Webhook missing data object | ip=%s", ip)
        raise ValidationError("Missing data object")

    if not verify_korapay_webhook_signature(payload, signature):
        logger.warning("Webhook signature invalid | ip=%s ref=%s", ip, payload.get("data", {}).get("reference", "unknown"))
        log_event(db, "webhook.signature_failed", None, {"ip": ip, "reference": payload.get("data", {}).get("reference")})
        raise AuthenticationError("Invalid signature")

    data = payload["data"]
    return payload, payload.get("event"), data, data.get("reference"), data.get("status"), data.get("amount")


def _process_korapay_charge_success(db, t, reference: str) -> None:
    """Confirm transaction and trigger downstream actions."""
    from services.webhook import deliver_webhook, sync_invoice_on_transaction_update

    t.transfer_confirmed = True
    t.status = TransactionStatus.VERIFIED
    t.is_used = True
    db.flush()

    _forward_to_voicepay(t, reference)
    if t.webhook_url:
        deliver_webhook(db, t)
    sync_invoice_on_transaction_update(db, t)
    log_event(db, "payment.confirmed_via_webhook", t.user_id, {"tx_ref": reference, "amount": str(t.amount)})
    logger.info("Webhook processed successfully | ref=%s", reference)


@public_bp.route("/api/webhooks/korapay", methods=["POST"])
def korapay_webhook():
    """Receive payment notifications from KoraPay."""
    ip = client_ip()

    with get_db() as db:
        if not check_rate_limit(db, f"webhook:korapay:{ip}", limit=100, window_secs=60):
            logger.warning("Webhook rate limit exceeded | ip=%s", ip)
            from core.exceptions import OnePayError
            raise OnePayError("Rate limit exceeded", "RATE_LIMIT", 429)

        payload, event, data, reference, status, amount = _parse_and_verify_korapay_webhook(db, ip)

        t = db.query(Transaction).filter(Transaction.tx_ref == reference).first()
        if not t:
            logger.warning("Webhook transaction not found | ref=%s ip=%s", reference, ip)
            raise ValidationError("Transaction not found")

        if amount != int(t.amount * 100):
            logger.warning("Webhook amount mismatch | ref=%s expected=%d got=%d", reference, int(t.amount * 100), amount)
            raise ValidationError("Amount mismatch")

        if t.transfer_confirmed:
            logger.info("Webhook for already confirmed transaction | ref=%s", reference)
            return jsonify({"success": True, "tx_ref": reference}), 200

        if event == "charge.success" and status == "success":
            _process_korapay_charge_success(db, t, reference)
            return jsonify({"success": True, "tx_ref": reference}), 200

        logger.info("Webhook received but not processed | event=%s status=%s ref=%s", event, status, reference)
        return jsonify({"success": True, "tx_ref": reference}), 200


# ── Health check ───────────────────────────────────────────────────────────────


@public_bp.route("/health", methods=["GET"])
def health():
    """Comprehensive health check with dependency status"""
    db_ok = _check_database()

    try:
        with get_db() as db:
            cleanup_old_rate_limits(db)
            # Cleanup old audit logs (90 day retention)
            from core.audit import cleanup_old_audit_logs

            cleanup_old_audit_logs(db, retention_days=90)
    except Exception as e:
        logger.warning("Health check cleanup error: %s", e)

    # Check KoraPay configuration status
    korapay_ok = korapay.is_configured()
    korapay_transfer_ok = korapay.is_transfer_configured()
    mock_mode = not korapay_ok  # Mock mode when not configured

    # Get KoraPay health metrics
    korapay_metrics = korapay.get_health_metrics()

    # Get KoraPay base URL (without credentials)
    from config import Config

    korapay_base_url = Config.KORAPAY_BASE_URL
    korapay_environment = "sandbox" if Config.KORAPAY_USE_SANDBOX else "production"

    # Build checks structure
    checks = {
        "database": db_ok,
        "korapay": korapay_ok,
    }

    all_healthy = all(v for v in checks.values() if v is not None)
    status_code = 200 if all_healthy else 503

    return jsonify(
        {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            # Legacy fields for backward compatibility
            "app": "OnePay",
            "database": "ok" if db_ok else "error",
            "korapay": "ok" if korapay_ok else "not_configured",
            "korapay_configured": korapay_transfer_ok,
            "mock_mode": mock_mode,
            "korapay_base_url": korapay_base_url,
            "korapay_environment": korapay_environment,
            "korapay_metrics": korapay_metrics,
        }
    ), status_code


def _check_database() -> bool:
    """Check database connectivity"""
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Health check DB error: %s", e)
        return False

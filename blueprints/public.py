"""
OnePay — Public blueprint
Handles: verify page, preview API, transfer-status polling, health check
No login required — these are customer-facing routes.
"""
import logging
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, render_template, session, make_response

from config import Config
from database import engine, get_db
from models.transaction import Transaction, TransactionStatus
from models.user import User
from services.rate_limiter import check_rate_limit, cleanup_old_rate_limits
from services.security import verify_hash_token
from services.korapay import korapay, KoraPayError
from core.auth import valid_tx_ref
from core.ip import client_ip
from core.responses import error, rate_limited
from core.audit import log_event
import sqlalchemy

logger = logging.getLogger(__name__)
public_bp = Blueprint("public", __name__)


# ── Pay page (clean URL — hash validated server-side) ─────────────────────────

@public_bp.route("/pay/<tx_ref>")
def pay_page(tx_ref):
    try:
        logger.info("pay_page accessed | tx_ref=%s ip=%s", tx_ref, client_ip())
        return_url = ""
        link_error = ""

        if not valid_tx_ref(tx_ref):
            link_error = "Invalid transaction reference format."
            logger.warning("Invalid tx_ref format | tx_ref=%s ip=%s", tx_ref, client_ip())
            return render_template("verify.html", tx_ref=tx_ref,
                                   return_url=return_url, link_error=link_error,
                                   qr_code_payment_url=None,
                                   qr_code_virtual_account=None)

        with get_db() as db:
            if not check_rate_limit(
                db, f"verify_page:{client_ip()}",
                Config.RATE_LIMIT_VERIFY_PAGE_ATTEMPTS,
                window_secs=Config.RATE_LIMIT_VERIFY_PAGE_WINDOW_SECS,
            ):
                link_error = "Too many verification attempts — please wait and try again."
                logger.warning("Rate limit exceeded | tx_ref=%s ip=%s", tx_ref, client_ip())
                return render_template("verify.html", tx_ref=tx_ref,
                                       return_url=return_url, link_error=link_error,
                                       qr_code_payment_url=None,
                                       qr_code_virtual_account=None)

            t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

            # Initialize QR variables to None by default
            qr_payment_url = None
            qr_virtual_account = None

            if not t:
                link_error = "This payment link was not found. Please request a new one."
                logger.warning("Transaction not found | tx_ref=%s ip=%s", tx_ref, client_ip())
            else:
                logger.info("Transaction found | tx_ref=%s user_id=%s status=%s", 
                           tx_ref, t.user_id, t.status.value if t.status else 'None')
                # Store QR code values before session ends
                qr_payment_url = t.qr_code_payment_url
                qr_virtual_account = t.qr_code_virtual_account
                
                logger.debug("QR data for %s: payment=%s, va=%s", 
                           tx_ref, 
                           "Yes" if qr_payment_url else "No",
                           "Yes" if qr_virtual_account else "No")
                
                if t.return_url:
                    return_url = t.return_url
                    
                # Validate hash server-side — customer never sees it
                hash_valid = verify_hash_token(tx_ref, t.amount, t.expires_at, t.hash_token)
                logger.debug("Hash validation | tx_ref=%s valid=%s amount=%s expires=%s", 
                            tx_ref, hash_valid, t.amount, t.expires_at)
                
                if not hash_valid:
                    link_error = "This payment link is invalid or has been tampered with."
                    logger.warning("Hash validation failed | tx_ref=%s ip=%s amount=%s", 
                                 tx_ref, client_ip(), t.amount)
                elif t.is_expired():
                    link_error = "This payment link has expired. Please request a new one."
                    logger.info("Transaction expired | tx_ref=%s expires_at=%s", 
                               tx_ref, t.expires_at)
                else:
                    logger.info("Transaction valid | tx_ref=%s", tx_ref)

        if link_error:
            logger.warning("Pay page rejected | ip=%s tx_ref=%s error=%s", 
                         client_ip(), tx_ref, link_error)
            return render_template("verify.html", tx_ref=tx_ref,
                                   return_url=return_url, link_error=link_error,
                                   qr_code_payment_url=None,
                                   qr_code_virtual_account=None)
        else:
            # Grant this browser session access to poll/preview this specific tx_ref
            session[f"pay_access_{tx_ref}"] = True
            logger.info("Pay page accepted | ip=%s tx_ref=%s", client_ip(), tx_ref)

        logger.debug("Rendering payment page | payment_qr=%s va_qr=%s", 
                   "Yes" if qr_payment_url else "No",
                   "Yes" if qr_virtual_account else "No")

        # VULN-018 fix: Allow embedding only from merchant's return_url domain
        response = make_response(render_template("verify.html", tx_ref=tx_ref,
                               return_url=return_url, link_error=link_error,
                               qr_code_payment_url=qr_payment_url,
                               qr_code_virtual_account=qr_virtual_account))
        
        # If transaction has return_url, allow framing from that domain only
        if return_url:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(return_url)
                if parsed.netloc:
                    # Override global X-Frame-Options for this specific page
                    response.headers["X-Frame-Options"] = f"ALLOW-FROM https://{parsed.netloc}"
                    # Modern browsers use CSP frame-ancestors
                    response.headers["Content-Security-Policy"] = \
                        f"frame-ancestors 'self' https://{parsed.netloc}"
                    logger.debug("Clickjacking protection: allowing frames from %s", parsed.netloc)
            except Exception as e:
                logger.warning("Failed to parse return_url for frame protection: %s", e)
        
        return response
    
    except Exception as e:
        logger.error("Exception in pay_page | tx_ref=%s error=%s", tx_ref, e, exc_info=True)
        # Fallback render
        return render_template("verify.html", tx_ref=tx_ref,
                               return_url="", link_error="Internal server error",
                               qr_code_payment_url=None,
                               qr_code_virtual_account=None)


# ── Verified page ───────────────────────────────────────────────────────────────

@public_bp.route("/verified/<tx_ref>")
def verified_page(tx_ref):
    """Show verified page if transaction is confirmed, otherwise redirect to pay page."""
    if not valid_tx_ref(tx_ref):
        return redirect("/pay/invalid", code=301)

    from flask import redirect

    with get_db() as db:
        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not t:
            return redirect("/pay/invalid", code=301)

        # If not yet confirmed, redirect to pay page to start polling
        if not t.transfer_confirmed:
            return redirect(f"/pay/{tx_ref}", code=302)

        # Already confirmed - show verified page
        return render_template("verified.html",
                               tx_ref=tx_ref,
                               return_url=t.return_url or "")


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
        return error("Invalid transaction reference format", "INVALID_REF", 400)

    with get_db() as db:
        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not t:
            return error("Transaction not found", "NOT_FOUND", 404)

        # Access control: session token set by pay_page, OR re-validate hash from DB
        # (fallback covers cookie-disabled browsers and direct API calls with valid links)
        if not session.get(f"pay_access_{tx_ref}"):
            if not verify_hash_token(tx_ref, t.amount, t.expires_at, t.hash_token):
                return error("Access denied", "FORBIDDEN", 403)
            # Grant session access for subsequent poll calls
            session[f"pay_access_{tx_ref}"] = True

        return jsonify({
            "success":     True,
            "tx_ref":      t.tx_ref,
            "amount":      str(t.amount),
            "currency":    t.currency,
            "description": t.description,
            "expires_at":  t.expires_at_utc_iso(),
            "is_expired":  t.is_expired(),
            "is_used":     t.is_used,
            "status":      t.effective_status_value(),
            "virtual_account_number": t.virtual_account_number,
            "virtual_bank_name":      t.virtual_bank_name,
            "virtual_account_name":   t.virtual_account_name,
            "transfer_confirmed":     t.transfer_confirmed,
            "qr_code_payment_url":     t.qr_code_payment_url,
            "qr_code_virtual_account": t.qr_code_virtual_account,
        })


# ── Transfer status polling ────────────────────────────────────────────────────

@public_bp.route("/api/payments/transfer-status/<tx_ref>", methods=["GET"])
def transfer_status(tx_ref):
    """
    Poll transfer confirmation status.
    
    Security: Rate limited to 20 requests per minute per IP to prevent DoS.
    Frontend implements additional client-side polling cap (60 polls max).
    Uses optimistic locking to prevent race conditions.
    """
    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)

    # Only allow browsers that loaded the /pay/ page for this tx_ref
    if not session.get(f"pay_access_{tx_ref}"):
        return error("Access denied", "FORBIDDEN", 403)

    ip = client_ip()

    with get_db() as db:
        if not check_rate_limit(db, f"poll:{ip}", Config.RATE_LIMIT_VERIFY):
            return rate_limited()

        # Fast path: Fetch transaction WITHOUT locking to check status quickly
        t = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        
        if not t:
            return error("Transaction not found", "NOT_FOUND", 404)

        # Fast path: already confirmed
        if t.transfer_confirmed:
            return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})

        # Fast path: already used or expired
        if t.is_used:
            return jsonify({"success": False, "status": "used", "tx_ref": tx_ref})

        if t.is_expired():
            # Update status if not already expired
            if t.status != TransactionStatus.EXPIRED:
                t.status = TransactionStatus.EXPIRED
                db.flush()
                
                # Sync invoice status if invoice exists
                from services.webhook import sync_invoice_on_transaction_update
                sync_invoice_on_transaction_update(db, t)
            return jsonify({"success": False, "status": "expired", "tx_ref": tx_ref})

        # Check if KoraPay transfer confirmation is configured
        if not korapay.is_transfer_configured():
            logger.debug("KoraPay transfer confirmation not configured")
            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

        # Optimistic locking: Acquire row lock to prevent race conditions
        t_locked = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).with_for_update().first()
        
        if not t_locked:
            return error("Transaction not found", "NOT_FOUND", 404)

        # Double-check after lock acquisition: another request may have confirmed it
        if t_locked.transfer_confirmed:
            return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})

        # Call KoraPay to confirm transfer
        try:
            result = korapay.confirm_transfer(tx_ref)
            response_code = result.get("responseCode", "")
            
            if response_code == "00":
                # Transfer confirmed
                t_locked.transfer_confirmed = True
                t_locked.status = TransactionStatus.VERIFIED
                db.flush()

                # Deliver webhook if configured
                if t_locked.webhook_url:
                    from services.webhook import deliver_webhook
                    deliver_webhook(db, t_locked)

                # Sync invoice status and send notification emails
                from services.webhook import sync_invoice_on_transaction_update, send_payment_notification_emails
                sync_invoice_on_transaction_update(db, t_locked)

                # Send payment notification emails (merchant + customer)
                user_for_email = db.query(User).filter(User.id == t_locked.user_id).first()
                if user_for_email:
                    send_payment_notification_emails(db, t_locked, user_for_email)

                log_event(db, "transfer_confirmed", t_locked.user_id,
                         tx_ref=tx_ref, detail={"tx_ref": tx_ref, "amount": str(t_locked.amount)})
                
                return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})
            else:
                # Transfer still pending
                return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})
                
        except KoraPayError as e:
            logger.error("KoraPay error confirming transfer %s: %s", tx_ref, e)
            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

# ── KoraPay Webhook ────────────────────────────────────────────────────────────

@public_bp.route("/api/webhooks/korapay", methods=["POST"])
def korapay_webhook():
    """
    Receive payment notifications from KoraPay.
    
    Security: HMAC-SHA256 signature verification on data object only.
    Rate limited: 100 requests/min per IP.
    Idempotent: Multiple deliveries of same webhook are safe.
    
    Requirements: 9.1-9.45
    """
    ip = client_ip()
    
    with get_db() as db:
        # Rate limiting: 100 requests/min per IP
        if not check_rate_limit(db, f"webhook:korapay:{ip}", limit=100, window_secs=60):
            logger.warning("Webhook rate limit exceeded | ip=%s", ip)
            return error("Rate limit exceeded", "RATE_LIMIT", 429)
        
        # Extract signature header
        signature = request.headers.get("x-korapay-signature")
        if not signature:
            logger.warning("Webhook missing signature | ip=%s", ip)
            log_event(db, "webhook.signature_missing", None, detail={"ip": ip})
            return error("Missing signature", "UNAUTHORIZED", 401)
        
        # Get raw request body for signature verification
        try:
            raw_body = request.get_data(as_text=False)
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.warning("Webhook invalid JSON | ip=%s", ip)
            return error("Invalid JSON", "BAD_REQUEST", 400)
        
        # Validate payload has data object
        if "data" not in payload:
            logger.warning("Webhook missing data object | ip=%s", ip)
            return error("Missing data object", "BAD_REQUEST", 400)
        
        # Verify signature using webhook signature verification function
        from services.korapay import verify_korapay_webhook_signature
        if not verify_korapay_webhook_signature(payload, signature):
            logger.warning("Webhook signature invalid | ip=%s ref=%s", 
                         ip, payload.get("data", {}).get("reference", "unknown"))
            log_event(db, "webhook.signature_failed", None, 
                     {"ip": ip, "reference": payload.get("data", {}).get("reference")})
            return error("Invalid signature", "UNAUTHORIZED", 401)
        
        # Extract webhook data
        event = payload.get("event")
        data = payload["data"]
        reference = data.get("reference")
        status = data.get("status")
        amount = data.get("amount")
        
        # Query transaction by reference
        t = db.query(Transaction).filter(Transaction.tx_ref == reference).first()
        if not t:
            logger.warning("Webhook transaction not found | ref=%s ip=%s", reference, ip)
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Validate amount matches (KoraPay sends amount in Naira)
        expected_amount = int(t.amount)  # Transaction amount is Decimal in Naira
        if amount != expected_amount:
            logger.warning("Webhook amount mismatch | ref=%s expected=%d got=%d", 
                         reference, expected_amount, amount)
            return error("Amount mismatch", "BAD_REQUEST", 400)
        
        # Check if already confirmed (idempotency)
        if t.transfer_confirmed:
            logger.info("Webhook for already confirmed transaction | ref=%s", reference)
            return jsonify({"success": True, "tx_ref": reference}), 200
        
        # Process charge.success event
        if event == "charge.success" and status == "success":
            # Update transaction status
            t.transfer_confirmed = True
            t.status = TransactionStatus.VERIFIED
            t.is_used = True
            db.flush()
            
            # Deliver webhook if configured
            if t.webhook_url:
                from services.webhook import deliver_webhook
                deliver_webhook(db, t)
            
            # Sync invoice status
            from services.webhook import sync_invoice_on_transaction_update
            sync_invoice_on_transaction_update(db, t)
            
            # Log audit event
            log_event(db, "payment.confirmed_via_webhook", t.user_id, 
                     {"tx_ref": reference, "amount": str(t.amount)})
            
            logger.info("Webhook processed successfully | ref=%s", reference)
            return jsonify({"success": True, "tx_ref": reference}), 200
        else:
            # Other events or statuses - acknowledge but don't process
            logger.info("Webhook received but not processed | event=%s status=%s ref=%s", 
                       event, status, reference)
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
    except Exception:
        pass

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

    return jsonify({
        "status":              "healthy" if all_healthy else "unhealthy",
        "checks":              checks,
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "version":             "1.0.0",
        # Legacy fields for backward compatibility
        "app":                 "OnePay",
        "database":            "ok" if db_ok else "error",
        "korapay":             "ok" if korapay_ok else "not_configured",
        "korapay_configured":  korapay_transfer_ok,
        "mock_mode":           mock_mode,
        "korapay_base_url":    korapay_base_url,
        "korapay_environment":  korapay_environment,
        "korapay_metrics":     korapay_metrics
    }), status_code


def _check_database() -> bool:
    """Check database connectivity"""
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Health check DB error: %s", e)
        return False

"""
OnePay — Public blueprint
Handles: verify page, preview API, transfer-status polling, health check
No login required — these are customer-facing routes.
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, render_template, session, make_response

from config import Config
from database import engine, get_db
from models.transaction import Transaction, TransactionStatus
from services.rate_limiter import check_rate_limit, cleanup_old_rate_limits
from services.security import verify_hash_token
from services.quickteller import quickteller, QuicktellerError
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

        # Fetch transaction WITHOUT locking to check status quickly
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

        if not quickteller.is_transfer_configured():
            return jsonify({"success": False, "status": "error", "message": "Transfer not configured"})

        # Check with payment provider (external API call - no lock held)
        try:
            result = quickteller.confirm_transfer(tx_ref)
            response_code = result.get("responseCode", "")

            if response_code == "00":
                # Payment confirmed - now acquire lock to update
                t_locked = db.query(Transaction).filter(
                    Transaction.tx_ref == tx_ref,
                    Transaction.transfer_confirmed == False  # Optimistic check
                ).with_for_update().first()
                
                # Double-check: another request might have confirmed it
                if not t_locked or t_locked.transfer_confirmed:
                    logger.info("transfer-status: already confirmed by another request | tx_ref=%s", tx_ref)
                    return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})
                
                # We won the race - update the transaction
                now_utc = datetime.now(timezone.utc)
                t_locked.transfer_confirmed = True
                t_locked.is_used = True
                t_locked.status = TransactionStatus.VERIFIED
                t_locked.verified_at = now_utc
                db.flush()
                
                log_event(db, "payment.confirmed", user_id=t_locked.user_id, 
                          tx_ref=tx_ref, ip_address=ip, 
                          detail={"amount": str(t_locked.amount)})
                
                # Deliver webhook (still within transaction for consistency)
                if t_locked.webhook_url and not t_locked.webhook_delivered:
                    from services.webhook import deliver_webhook
                    deliver_webhook(db, t_locked)
                
                # Sync invoice status if invoice exists
                from services.webhook import sync_invoice_on_transaction_update
                sync_invoice_on_transaction_update(db, t_locked)
                
                # Send payment notification emails (merchant + customer if enabled)
                from services.webhook import send_payment_notification_emails
                from models.user import User
                user = db.query(User).filter(User.id == t_locked.user_id).first()
                if user:
                    send_payment_notification_emails(db, t_locked, user)

                logger.info("transfer-status confirmed | ip=%s tx_ref=%s", ip, tx_ref)
                return jsonify({"success": True, "status": "confirmed", "tx_ref": tx_ref})

            return jsonify({"success": False, "status": "pending", "tx_ref": tx_ref})

        except QuicktellerError as e:
            logger.error("confirm_transfer error for %s: %s", tx_ref, e)
            return jsonify({"success": False, "status": "error",
                            "message": "Could not reach payment provider"}), 200


# ── Health check ───────────────────────────────────────────────────────────────

@public_bp.route("/health", methods=["GET"])
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
    except Exception as e:
        db_ok = False
        logger.error("Health check DB error: %s", e)

    try:
        with get_db() as db:
            cleanup_old_rate_limits(db)
            # Cleanup old audit logs (90 day retention)
            from core.audit import cleanup_old_audit_logs
            cleanup_old_audit_logs(db, retention_days=90)
    except Exception:
        pass

    mock_mode = not quickteller.is_configured()
    return jsonify({
        "status":              "healthy" if db_ok else "degraded",
        "app":                 "OnePay",
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "database":            "ok" if db_ok else "error",
        "quickteller":         quickteller.is_configured(),
        "transfer_configured": quickteller.is_transfer_configured(),
        "mock_mode":           mock_mode,
    })

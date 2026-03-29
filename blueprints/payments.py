"""
OnePay — Payments blueprint
Handles: dashboard, create link, status, history (merchant-facing)
"""
import logging
import re
import html
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from sqlalchemy import func, case

from config import Config
from database import get_db
from models.transaction import Transaction, TransactionStatus
from models.user import User
from models.audit_log import AuditLog
from services.rate_limiter import check_rate_limit
from services.security import (
    generate_tx_reference, generate_hash_token,
    generate_expiration_time, validate_return_url, validate_webhook_url,
)
from services.quickteller import quickteller, QuicktellerError
from services.qr_code import qr_service
from services.invoice import invoice_service
from services.email import send_invoice_email
from models.invoice import InvoiceSettings
from core.auth import (
    get_csrf_token, is_valid_csrf_token,
    current_user_id, current_username,
    login_required_redirect, valid_tx_ref,
)
from core.ip import client_ip
from core.responses import error, rate_limited, unauthenticated
from core.audit import log_event

logger = logging.getLogger(__name__)
payments_bp = Blueprint("payments", __name__)

PAGE_SIZE = 20
MAX_EXPORT_ROWS = 1000


def _safe(val, maxlen=255):
    """
    Strip, escape HTML, remove control characters, and validate length.
    Returns None if empty after sanitization or exceeds max length.
    
    VULN-008 FIX: Reject if exceeds maxlen instead of truncating.
    """
    if not val:
        return None
    
    # Convert to string and strip whitespace
    sanitized = str(val).strip()
    
    # VULN-008 FIX: Reject if exceeds max length (don't truncate)
    if len(sanitized) > maxlen:
        return None
    
    # Remove null bytes and other control characters (except newlines/tabs)
    sanitized = ''.join(c for c in sanitized if c == '\n' or c == '\t' or (ord(c) >= 32 and ord(c) != 127))
    
    # HTML escape
    sanitized = html.escape(sanitized)
    
    return sanitized if sanitized else None


_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$')
_PHONE_RE = re.compile(r'^\+?[0-9\s\-\(\)]{7,20}$')


def _safe_email(val) -> str | None:
    v = _safe(val, 255)
    if not v:
        return None
    return v if _EMAIL_RE.match(v) else None


def _safe_phone(val) -> str | None:
    v = _safe(val, 20)
    if not v:
        return None
    return v if _PHONE_RE.match(v) else None


# ── Dashboard ──────────────────────────────────────────────────────────────────

@payments_bp.route("/")
def dashboard():
    if not current_user_id():
        return login_required_redirect()
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        webhook_url = user.webhook_url if user else ""
        profile_picture = user.profile_picture_url if user else None
    return render_template(
        "index.html",
        username=current_username(),
        profile_picture=profile_picture,
        csrf_token=get_csrf_token(),
        webhook_url=webhook_url or "",
        link_expiry_minutes=Config.LINK_EXPIRATION_MINUTES,
        active_page="create",
    )


@payments_bp.route("/settings")
def settings():
    if not current_user_id():
        return login_required_redirect()
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        webhook_url = user.webhook_url if user else ""
        profile_picture = user.profile_picture_url if user else None
        
        # Load invoice settings for current user (Requirement 11.1)
        invoice_settings = db.query(InvoiceSettings).filter(
            InvoiceSettings.user_id == current_user_id()
        ).first()
        
        # Render template while session is still active
        return render_template(
            "settings.html",
            username=current_username(),
            profile_picture=profile_picture,
            csrf_token=get_csrf_token(),
            webhook_url=webhook_url or "",
            invoice_settings=invoice_settings,
            active_page="settings",
        )


@payments_bp.route("/check-status")
def check_status():
    if not current_user_id():
        return login_required_redirect()
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        profile_picture = user.profile_picture_url if user else None
    return render_template(
        "check_status.html",
        username=current_username(),
        profile_picture=profile_picture,
        csrf_token=get_csrf_token(),
        active_page="check_status",
    )


@payments_bp.route("/history")
def history():
    if not current_user_id():
        return login_required_redirect()
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        profile_picture = user.profile_picture_url if user else None
    return render_template(
        "history.html",
        username=current_username(),
        profile_picture=profile_picture,
        csrf_token=get_csrf_token(),
        active_page="history",
    )


@payments_bp.route("/invoices")
def invoices():
    if not current_user_id():
        return login_required_redirect()
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        profile_picture = user.profile_picture_url if user else None
    return render_template(
        "invoices.html",
        username=current_username(),
        profile_picture=profile_picture,
        csrf_token=get_csrf_token(),
        active_page="invoices",
    )


# ── Update webhook settings ────────────────────────────────────────────────────

@payments_bp.route("/api/settings/webhook", methods=["POST"])
def update_webhook_settings():
    # VULN-007 FIX: Validate Content-Type for JSON API
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    if not current_user_id():
        return unauthenticated()
    
    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    
    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)
    
    data = request.get_json(silent=True) or {}
    webhook_url = validate_webhook_url(data.get("webhook_url", ""))
    
    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            return error("User not found", "NOT_FOUND", 404)
        
        user.webhook_url = webhook_url
        db.flush()
        
        log_event(db, "settings.webhook_updated", user_id=current_user_id(), ip_address=client_ip(),
                  detail={"webhook_url": webhook_url or "removed"})
        
        logger.info("Webhook settings updated | user=%s", current_username())
        
        return jsonify({
            "success": True,
            "message": "Webhook settings updated successfully",
            "webhook_url": webhook_url or ""
        })


# ── Export transactions ────────────────────────────────────────────────────────

@payments_bp.route("/api/payments/export", methods=["GET"])
def export_transactions():
    if not current_user_id():
        return unauthenticated()
    
    import csv
    from io import StringIO
    from flask import make_response
    
    with get_db() as db:
        # Rate limit CSV export to prevent resource exhaustion
        if not check_rate_limit(db, f"export:{current_user_id()}", limit=5, window_secs=300):
            return rate_limited()
        
        transactions = (
            db.query(Transaction)
            .filter(Transaction.user_id == current_user_id())
            .order_by(Transaction.created_at.desc())
            .limit(MAX_EXPORT_ROWS)
            .all()
        )
        
        # Create CSV
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['Reference', 'Amount', 'Currency', 'Status', 'Description', 'Customer Email', 'Created At', 'Expires At'])
        
        for tx in transactions:
            writer.writerow([
                tx.tx_ref,
                str(tx.amount),
                tx.currency,
                tx.status.value if hasattr(tx.status, 'value') else str(tx.status),
                tx.description or '',
                tx.customer_email or '',
                tx.created_at.isoformat() if tx.created_at else '',
                tx.expires_at.isoformat() if tx.expires_at else ''
            ])

        # Add truncation note if limit was reached
        if len(transactions) == MAX_EXPORT_ROWS:
            writer.writerow(['Note: Export limited to most recent 1000 transactions', '', '', '', '', '', '', ''])

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = f"attachment; filename=onepay_transactions_{current_username()}.csv"
        output.headers["Content-type"] = "text/csv"
        
        return output


# ── Analytics summary ──────────────────────────────────────────────────────────

@payments_bp.route("/api/payments/summary", methods=["GET"])
def payment_summary():
    if not current_user_id():
        return unauthenticated()
    
    with get_db() as db:
        # Rate limit expensive aggregation queries
        if not check_rate_limit(db, f"summary:{current_user_id()}", limit=20, window_secs=60):
            return rate_limited()
        
        user_id = current_user_id()
        
        # Current month start
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        
        logging.info(f"Summary request - Current time: {now}, Month start: {month_start}")
        
        # All-time stats
        all_time = db.query(
            func.coalesce(func.sum(case(
                (Transaction.status == TransactionStatus.VERIFIED, Transaction.amount),
                else_=0
            )), 0).label('total_verified_amount'),
            func.count(Transaction.id).label('total_links'),
            func.sum(case(
                (Transaction.status == TransactionStatus.VERIFIED, 1),
                else_=0
            )).label('total_verified'),
            func.sum(case(
                (Transaction.status == TransactionStatus.EXPIRED, 1),
                else_=0
            )).label('total_expired'),
        ).filter(Transaction.user_id == user_id).first()
        
        # This month stats
        this_month = db.query(
            func.coalesce(func.sum(case(
                (Transaction.status == TransactionStatus.VERIFIED, Transaction.amount),
                else_=0
            )), 0).label('total_verified_amount'),
            func.count(Transaction.id).label('total_links'),
            func.sum(case(
                (Transaction.status == TransactionStatus.VERIFIED, 1),
                else_=0
            )).label('total_verified'),
        ).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= month_start
        ).first()
        
        logging.info(f"This month verified amount: {this_month.total_verified_amount}, count: {this_month.total_verified}")
        
        # Calculate conversion rates
        all_time_rate = 0
        if all_time.total_links > 0:
            all_time_rate = round((all_time.total_verified or 0) / all_time.total_links * 100, 1)
        
        this_month_rate = 0
        if this_month.total_links > 0:
            this_month_rate = round((this_month.total_verified or 0) / this_month.total_links * 100, 1)
        
        return jsonify({
            "success": True,
            "all_time": {
                "total_collected": str(all_time.total_verified_amount or 0),
                "total_links": all_time.total_links or 0,
                "total_verified": all_time.total_verified or 0,
                "total_expired": all_time.total_expired or 0,
                "conversion_rate": all_time_rate,
            },
            "this_month": {
                "total_collected": str(this_month.total_verified_amount or 0),
                "total_links": this_month.total_links or 0,
                "total_verified": this_month.total_verified or 0,
                "conversion_rate": this_month_rate,
            },
        })


# ── Create payment link ────────────────────────────────────────────────────────

@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    # VULN-007 FIX: Validate Content-Type for JSON API
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    if not current_user_id():
        return unauthenticated()

    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)

    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)

    with get_db() as db:
        rate_key = f"link:user:{current_user_id()}"
        if not check_rate_limit(db, rate_key, Config.RATE_LIMIT_LINK_CREATE):
            return rate_limited()

        data = request.get_json(silent=True) or {}

        # ── Idempotency ────────────────────────────────────────────────────────
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if idempotency_key:
            # Sanitize and truncate FIRST to prevent ReDoS
            idempotency_key = idempotency_key[:255].replace('\x00', '').strip()
            # Simple validation without complex regex
            if not idempotency_key or not all(c.isalnum() or c in '-_' for c in idempotency_key):
                return error("X-Idempotency-Key must be alphanumeric with hyphens/underscores (1-255 chars)", "VALIDATION_ERROR", 400)
        if idempotency_key:
            existing = db.query(Transaction).filter(
                Transaction.idempotency_key == idempotency_key,
                Transaction.user_id == current_user_id(),
            ).first()
            if existing:
                base_url    = request.host_url.rstrip("/")
                payment_url = f"{base_url}/pay/{existing.tx_ref}"
                logger.info("Idempotent link returned | merchant=%s ref=%s", current_username(), existing.tx_ref)
                return jsonify({
                    "success":     True,
                    "message":     "Existing payment link returned (idempotent)",
                    "tx_ref":      existing.tx_ref,
                    "payment_url": payment_url,
                    "amount":      str(existing.amount),
                    "currency":    existing.currency,
                    "description": existing.description,
                    "expires_at":  existing.expires_at_utc_iso(),
                    "virtual_account_number": existing.virtual_account_number,
                    "virtual_bank_name":      existing.virtual_bank_name,
                    "virtual_account_name":   existing.virtual_account_name,
                    "qr_code_payment_url":     existing.qr_code_payment_url,
                    "qr_code_virtual_account": existing.qr_code_virtual_account,
                }), 200

        # ── Validate amount ────────────────────────────────────────────────────
        raw_amount = data.get("amount")
        if not raw_amount:
            return error("amount is required", "VALIDATION_ERROR", 400)
        try:
            from decimal import InvalidOperation, ROUND_HALF_UP
            amount = Decimal(str(raw_amount))
            # Reject negative zero, NaN, infinity
            if amount <= 0 or not amount.is_finite():
                return error("amount must be a positive finite number", "VALIDATION_ERROR", 400)
            if amount > Decimal("100000000.00"):
                return error("amount exceeds maximum allowed (100,000,000.00)", "VALIDATION_ERROR", 400)
            # Normalize to remove trailing zeros and enforce 2 decimal places
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (ValueError, TypeError, ArithmeticError, InvalidOperation):
            return error("amount must be a valid number", "VALIDATION_ERROR", 400)

        tx_ref     = generate_tx_reference()
        expires_at = generate_expiration_time()
        hash_token = generate_hash_token(tx_ref, amount, expires_at)

        user = db.query(User).filter(User.id == current_user_id()).first()
        per_link_webhook = validate_webhook_url(data.get("webhook_url", ""))
        webhook_url = per_link_webhook or (user.webhook_url if user else None)

        # Validate description length
        description = _safe(data.get("description"))
        if description and len(description) > 255:
            return error("Description too long (max 255 characters)", "VALIDATION_ERROR", 400)

        transaction = Transaction(
            tx_ref          = tx_ref,
            idempotency_key = idempotency_key,
            user_id         = current_user_id(),
            amount          = amount,
            currency        = str(data.get("currency", "NGN")).upper()[:3],
            description     = description,
            customer_email  = _safe_email(data.get("customer_email")),
            customer_phone  = _safe_phone(data.get("customer_phone")),
            return_url      = validate_return_url(data.get("return_url")),
            webhook_url     = webhook_url,
            hash_token      = hash_token,
            expires_at      = expires_at,
        )

        if quickteller.is_transfer_configured():
            amount_kobo = int(round(amount * 100))
            try:
                va = quickteller.create_virtual_account(
                    transaction_reference = tx_ref,
                    amount_kobo           = amount_kobo,
                    account_name          = transaction.description or "OnePay Payment",
                )
                transaction.virtual_account_number = va.get("accountNumber")
                transaction.virtual_bank_name      = va.get("bankName")
                transaction.virtual_account_name   = va.get("accountName")
            except QuicktellerError as e:
                logger.warning("Virtual account creation failed: %s", e)
        else:
            logger.debug("Transfer not configured — skipping virtual account creation (mock mode)")

        db.add(transaction)
        db.flush()
        db.refresh(transaction)

        # Build payment URL BEFORE generating QR codes
        base_url    = request.host_url.rstrip("/")
        payment_url = f"{base_url}/pay/{tx_ref}"

        # Generate QR codes
        try:
            # QR code for payment URL
            transaction.qr_code_payment_url = qr_service.generate_payment_qr(
                payment_url=payment_url,
                amount=str(amount),
                description=description,
                style="rounded"
            )
            
            # QR code for virtual account (if available)
            if (transaction.virtual_account_number and 
                transaction.virtual_bank_name and 
                transaction.virtual_account_name):
                transaction.qr_code_virtual_account = qr_service.generate_virtual_account_qr(
                    account_number=transaction.virtual_account_number,
                    bank_name=transaction.virtual_bank_name,
                    account_name=transaction.virtual_account_name,
                    amount=str(amount)
                )
            
            db.flush()  # Save QR codes to database
            logger.debug("QR codes generated for transaction %s", tx_ref)
            
        except Exception as e:
            logger.warning("QR code generation failed for %s: %s", tx_ref, e)
            # Continue without QR codes - they're optional

        # ── Invoice Creation (Requirement 10.1, 10.2) ──────────────────────────
        invoice_number = None
        try:
            # Check if user has invoice settings
            invoice_settings = db.query(InvoiceSettings).filter(
                InvoiceSettings.user_id == current_user_id()
            ).first()
            
            if invoice_settings:
                # Create invoice automatically
                invoice = invoice_service.create_invoice(
                    db=db,
                    transaction=transaction,
                    user=user,
                    settings=invoice_settings
                )
                invoice_number = invoice.invoice_number
                
                logger.info(
                    "Invoice created automatically | invoice_number=%s tx_ref=%s",
                    invoice_number, tx_ref
                )
                
                # If auto_send_email enabled and customer_email provided, send invoice
                if invoice_settings.auto_send_email and transaction.customer_email:
                    try:
                        # Generate PDF
                        pdf_bytes = invoice_service.generate_invoice_pdf(
                            invoice=invoice,
                            transaction=transaction,
                            payment_url=payment_url
                        )
                        
                        # Send email with payment_url and QR code
                        email_sent = send_invoice_email(
                            to_email=transaction.customer_email,
                            invoice=invoice,
                            pdf_bytes=pdf_bytes,
                            payment_url=payment_url,
                            qr_code_data_uri=transaction.qr_code_payment_url
                        )
                        
                        if email_sent:
                            from models.invoice import InvoiceStatus
                            invoice.status = InvoiceStatus.SENT
                            invoice.email_sent = True
                            invoice.email_sent_at = datetime.now(timezone.utc)
                            invoice.sent_at = datetime.now(timezone.utc)
                            db.flush()
                            
                            logger.info(
                                "Invoice emailed automatically | invoice_number=%s to=%s",
                                invoice_number, transaction.customer_email
                            )
                        else:
                            logger.warning(
                                "Invoice email failed | invoice_number=%s to=%s",
                                invoice_number, transaction.customer_email
                            )
                    except Exception as email_error:
                        # Log error but don't fail payment link creation
                        logger.error(
                            "Invoice email generation/sending failed | invoice_number=%s error=%s",
                            invoice_number, email_error
                        )
                        # Continue - invoice created, email failed
        except Exception as invoice_error:
            # Log error but don't fail payment link creation (graceful degradation)
            logger.error(
                "Invoice creation failed for tx_ref=%s | error=%s",
                tx_ref, invoice_error
            )
            # Continue without invoice - payment link still works

        log_event(db, "link.created", user_id=current_user_id(), tx_ref=tx_ref, ip_address=client_ip(), 
                  detail={"amount": str(amount), "currency": transaction.currency})

        logger.info("Payment link created | merchant=%s ref=%s amount=%s", current_username(), tx_ref, amount)

        response_data = {
            "success":     True,
            "message":     "Payment link created successfully",
            "tx_ref":      tx_ref,
            "payment_url": payment_url,
            "amount":      str(amount),
            "currency":    transaction.currency,
            "description": transaction.description,
            "expires_at":  transaction.expires_at_utc_iso(),
            "virtual_account_number": transaction.virtual_account_number,
            "virtual_bank_name":      transaction.virtual_bank_name,
            "virtual_account_name":   transaction.virtual_account_name,
            "qr_code_payment_url":     transaction.qr_code_payment_url,
            "qr_code_virtual_account": transaction.qr_code_virtual_account,
        }
        
        # Include invoice_number in response if invoice was created
        if invoice_number:
            response_data["invoice_number"] = invoice_number
        
        return jsonify(response_data), 201


# ── Transaction status ─────────────────────────────────────────────────────────

@payments_bp.route("/api/payments/status/<tx_ref>", methods=["GET"])
def transaction_status(tx_ref):
    if not current_user_id():
        return unauthenticated()
    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)

    # Add random jitter to mask timing differences (VULN-005 fix)
    import time
    import secrets
    jitter = secrets.randbelow(40) / 1000.0  # 0-40ms
    time.sleep(0.01 + jitter)  # Base 10ms + jitter

    with get_db() as db:
        # Rate limit status checks to prevent enumeration (VULN-005 fix)
        if not check_rate_limit(db, f"status:{current_user_id()}", limit=100, window_secs=60):
            return rate_limited()
        
        # Query with user_id filter to prevent enumeration (VULN-005 fix)
        t = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref,
            Transaction.user_id == current_user_id()  # Filter in query
        ).first()
        
        if not t:
            # Same error for both "not found" and "unauthorized"
            return error("Transaction not found", "NOT_FOUND", 404)
        
        return jsonify({"success": True, **t.to_dict()})


# ── Transaction history (paginated) ───────────────────────────────────────────

@payments_bp.route("/api/payments/history", methods=["GET"])
def transaction_history():
    if not current_user_id():
        return unauthenticated()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    offset = (page - 1) * PAGE_SIZE

    with get_db() as db:
        total = db.query(Transaction).filter(
            Transaction.user_id == current_user_id()
        ).count()

        transactions = (
            db.query(Transaction)
            .filter(Transaction.user_id == current_user_id())
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
            .all()
        )

        return jsonify({
            "success":      True,
            "transactions": [t.to_dict() for t in transactions],
            "pagination": {
                "page":        page,
                "page_size":   PAGE_SIZE,
                "total":       total,
                "total_pages": max(1, -(-total // PAGE_SIZE)),
                "has_next":    offset + PAGE_SIZE < total,
                "has_prev":    page > 1,
            },
        })


# ── Re-issue expired link ──────────────────────────────────────────────────────

@payments_bp.route("/api/payments/reissue/<tx_ref>", methods=["POST"])
def reissue_payment_link(tx_ref):
    # VULN-007 FIX: Validate Content-Type for JSON API
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    if not current_user_id():
        return unauthenticated()

    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)

    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)

    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)

    with get_db() as db:
        # Fetch original transaction
        original = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        
        if not original:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Verify ownership
        if original.user_id != current_user_id():
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Don't re-issue verified transactions
        if original.status == TransactionStatus.VERIFIED or original.transfer_confirmed:
            return error("Cannot re-issue a verified transaction", "ALREADY_VERIFIED", 400)
        
        # Generate new transaction with same details
        new_tx_ref = generate_tx_reference()
        new_expires_at = generate_expiration_time()
        new_hash_token = generate_hash_token(new_tx_ref, original.amount, new_expires_at)
        
        new_transaction = Transaction(
            tx_ref=new_tx_ref,
            user_id=current_user_id(),
            amount=original.amount,
            currency=original.currency,
            description=original.description,
            customer_email=original.customer_email,
            customer_phone=original.customer_phone,
            return_url=original.return_url,
            webhook_url=original.webhook_url,
            hash_token=new_hash_token,
            expires_at=new_expires_at,
        )
        
        # Try to create virtual account if configured
        if quickteller.is_transfer_configured():
            amount_kobo = int(round(original.amount * 100))
            try:
                va = quickteller.create_virtual_account(
                    transaction_reference=new_tx_ref,
                    amount_kobo=amount_kobo,
                    account_name=original.description or "OnePay Payment",
                )
                new_transaction.virtual_account_number = va.get("accountNumber")
                new_transaction.virtual_bank_name = va.get("bankName")
                new_transaction.virtual_account_name = va.get("accountName")
            except QuicktellerError as e:
                logger.warning("Virtual account creation failed on reissue: %s", e)
        else:
            logger.debug("Transfer not configured — skipping virtual account creation (mock mode)")
        
        db.add(new_transaction)
        db.flush()
        db.refresh(new_transaction)
        
        log_event(db, "link.reissued", user_id=current_user_id(), tx_ref=new_tx_ref, ip_address=client_ip(),
                  detail={"original_tx_ref": tx_ref, "amount": str(original.amount)})
        
        base_url = request.host_url.rstrip("/")
        payment_url = f"{base_url}/pay/{new_tx_ref}"
        
        logger.info("Payment link re-issued | merchant=%s original=%s new=%s", 
                    current_username(), tx_ref, new_tx_ref)
        
        return jsonify({
            "success": True,
            "message": "Payment link re-issued successfully",
            "tx_ref": new_tx_ref,
            "payment_url": payment_url,
            "amount": str(new_transaction.amount),
            "currency": new_transaction.currency,
            "description": new_transaction.description,
            "expires_at": new_transaction.expires_at_utc_iso(),
            "virtual_account_number": new_transaction.virtual_account_number,
            "virtual_bank_name": new_transaction.virtual_bank_name,
            "virtual_account_name": new_transaction.virtual_account_name,
        }), 201



# ── Audit log for transaction ─────────────────────────────────────────────────

@payments_bp.route("/api/payments/audit/<tx_ref>", methods=["GET"])
def transaction_audit(tx_ref):
    if not current_user_id():
        return unauthenticated()
    
    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)
    
    with get_db() as db:
        # Rate limit audit log access
        if not check_rate_limit(db, f"audit:{current_user_id()}", limit=20, window_secs=60):
            return rate_limited()
        
        # Verify ownership
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        if transaction.user_id != current_user_id():
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Fetch audit logs for this transaction
        logs = db.query(AuditLog).filter(
            AuditLog.tx_ref == tx_ref
        ).order_by(AuditLog.created_at.asc()).all()
        
        return jsonify({
            "success": True,
            "tx_ref": tx_ref,
            "audit_logs": [log.to_dict() for log in logs],
        })



# ── Expired payment link page ─────────────────────────────────────────────────

@payments_bp.route("/expired/<tx_ref>")
def expired_link(tx_ref):
    """Display expired payment link page to customer"""
    if not valid_tx_ref(tx_ref):
        return render_template("expired.html", reference="Invalid", transaction_id="N/A"), 404
    
    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction:
            return render_template("expired.html", reference="Not Found", transaction_id=tx_ref), 404
        
        return render_template(
            "expired.html",
            reference=transaction.description or tx_ref,
            transaction_id=tx_ref
        )


# ── Download receipt ───────────────────────────────────────────────────────────

@payments_bp.route("/api/payments/receipt/<tx_ref>", methods=["GET"])
def download_receipt(tx_ref):
    """Generate and download a PDF receipt for a transaction"""
    if not current_user_id():
        return error("Authentication required", "UNAUTHENTICATED", 401)
    
    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)
    
    with get_db() as db:
        # Rate limit receipt generation
        if not check_rate_limit(db, f"receipt:{current_user_id()}", limit=10, window_secs=60):
            return rate_limited()
        
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Verify ownership
        if transaction.user_id != current_user_id():
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Generate PDF receipt
        from services.pdf_receipt import generate_receipt_pdf
        from flask import make_response, send_file
        import io
        
        try:
            pdf_bytes = generate_receipt_pdf(transaction)
            
            # Create response with PDF
            response = make_response(pdf_bytes)
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Content-Disposition"] = f"attachment; filename=OnePay_Receipt_{tx_ref}.pdf"
            
            logger.info("PDF receipt downloaded | user=%s tx_ref=%s", current_username(), tx_ref)
            return response
            
        except Exception as e:
            logger.error("PDF receipt generation failed | user=%s tx_ref=%s error=%s", 
                        current_username(), tx_ref, e)
            return error("Failed to generate receipt", "PDF_GENERATION_ERROR", 500)


@payments_bp.route("/api/payments/receipt/<tx_ref>/preview", methods=["GET"])
def preview_receipt_html(tx_ref):
    """Generate and return HTML preview of receipt (for debugging/testing)"""
    if not current_user_id():
        return error("Authentication required", "UNAUTHENTICATED", 401)
    
    if not valid_tx_ref(tx_ref):
        return error("Invalid transaction reference format", "INVALID_REF", 400)
    
    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        if transaction.user_id != current_user_id():
            return error("Transaction not found", "NOT_FOUND", 404)
        
        from services.pdf_receipt import generate_receipt_html
        from flask import make_response
        
        try:
            html = generate_receipt_html(transaction)
            
            response = make_response(html)
            response.headers["Content-Type"] = "text/html"
            return response
            
        except Exception as e:
            logger.error("Receipt HTML preview failed | user=%s tx_ref=%s error=%s",
                        current_username(), tx_ref, e)
            return error("Failed to generate preview", "PREVIEW_ERROR", 500)

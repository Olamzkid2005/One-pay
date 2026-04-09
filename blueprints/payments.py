"""
OnePay — Payments blueprint
Handles: dashboard, create link, status, history (merchant-facing)
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from config import Config
from core.audit import log_event
from core.auth import (
    current_user_id,
    current_username,
    get_csrf_token,
    is_valid_csrf_token,
    login_required_redirect,
    valid_tx_ref,
)
from core.decorators import rate_limit
from core.exceptions import AuthenticationError, AuthorizationError, ProviderError, ValidationError
from core.ip import client_ip
from core.responses import error, rate_limited, unauthenticated
from database import get_db
from models.audit_log import AuditLog
from models.invoice import InvoiceSettings
from models.transaction import Transaction, TransactionStatus
from models.user import User
from services.cache import cache_delete, cache_get, cache_set
from services.email import send_invoice_email
from services.invoice import invoice_service
from services.korapay import KoraPayError, korapay
from services.qr_code import qr_service
from services.rate_limiter import check_rate_limit
from services.security import (
    generate_expiration_time,
    generate_hash_token,
    generate_tx_reference,
    validate_return_url,
    validate_webhook_url,
)
from services.validators import validate_email, validate_phone

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
    sanitized = "".join(
        c
        for c in sanitized
        if c == "\n" or c == "\t" or (ord(c) >= 32 and ord(c) != 127)
    )

    # HTML escape
    sanitized = html.escape(sanitized)

    return sanitized if sanitized else None


def _safe_email(val) -> Optional[str]:
    """Validate and normalize email using centralized validator."""
    v = _safe(val, 255)
    if not v:
        return None
    return validate_email(v)


def _safe_phone(val) -> Optional[str]:
    """Validate and normalize phone using centralized validator."""
    v = _safe(val, 20)
    if not v:
        return None
    return validate_phone(v)


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
        invoice_settings = (
            db.query(InvoiceSettings)
            .filter(InvoiceSettings.user_id == current_user_id())
            .first()
        )

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


# ── Update webhook settings ────────────────────────────────────────────────────


@payments_bp.route("/settings/webhook", methods=["POST"])
def update_webhook_settings():
    # VULN-007 FIX: Validate Content-Type for JSON API
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")
    if not current_user_id():
        return unauthenticated()

    # Skip CSRF for API key authenticated requests
    from core.api_auth import is_api_key_authenticated

    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get(
            "X-CSRF-Token"
        )
        if not is_valid_csrf_token(csrf_header):
            raise AuthorizationError("CSRF validation failed")

    data = request.get_json(silent=True) or {}
    webhook_url = validate_webhook_url(data.get("webhook_url", ""))

    with get_db() as db:
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            raise ValidationError("User not found")

        user.webhook_url = webhook_url
        with db.begin_nested():
            db.flush()

        log_event(
            db,
            "settings.webhook_updated",
            user_id=current_user_id(),
            ip_address=client_ip(),
            detail={"webhook_url": webhook_url or "removed"},
        )

        logger.info("Webhook settings updated | user=%s", current_username())

        return jsonify(
            {
                "success": True,
                "message": "Webhook settings updated successfully",
                "webhook_url": webhook_url or "",
            }
        )


# ── Export transactions ────────────────────────────────────────────────────────


@rate_limit("export:{user_id}", limit=5, window_secs=300)
@payments_bp.route("/payments/export", methods=["GET"])
def export_transactions():
    if not current_user_id():
        return unauthenticated()

    import csv
    from io import StringIO

    from flask import make_response

    with get_db() as db:
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
        writer.writerow(
            [
                "Reference",
                "Amount",
                "Currency",
                "Status",
                "Description",
                "Customer Email",
                "Created At",
                "Expires At",
            ]
        )

        for tx in transactions:
            writer.writerow(
                [
                    tx.tx_ref,
                    str(tx.amount),
                    tx.currency,
                    tx.status.value if hasattr(tx.status, "value") else str(tx.status),
                    tx.description or "",
                    tx.customer_email or "",
                    tx.created_at.isoformat() if tx.created_at else "",
                    tx.expires_at.isoformat() if tx.expires_at else "",
                ]
            )

        # Add truncation note if limit was reached
        if len(transactions) == MAX_EXPORT_ROWS:
            writer.writerow(
                [
                    "Note: Export limited to most recent 1000 transactions",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = (
        f"attachment; filename=onepay_transactions_{current_username()}.csv"
    )
    output.headers["Content-type"] = "text/csv"

    return output


# ── Analytics summary ──────────────────────────────────────────────────────────


def _build_chart_data(db, user_id: int, now, thirty_days_ago) -> dict:
    """Build 30-day chart data with daily revenue aggregation."""
    import datetime as dt_module
    try:
        from database import engine as _engine
        dialect = _engine.dialect.name
        if dialect == "sqlite":
            day_expr = func.strftime("%Y-%m-%d", Transaction.created_at).label("day")
        else:
            day_expr = func.to_char(Transaction.created_at, "YYYY-MM-DD").label("day")

        daily_stats = (
            db.query(day_expr, func.sum(Transaction.amount).label("total"))
            .filter(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.VERIFIED,
                Transaction.created_at >= thirty_days_ago,
            )
            .group_by("day")
            .all()
        )
        daily_dict = {row.day: float(row.total or 0) for row in daily_stats}
    except Exception as e:
        logging.error("Chart data aggregation failed | user_id=%s error=%s", user_id, e)
        daily_dict = {}

    labels, values = [], []
    for i in range(29, -1, -1):
        date_val = now - dt_module.timedelta(days=i)
        labels.append(date_val.strftime("%b %d"))
        values.append(daily_dict.get(date_val.strftime("%Y-%m-%d"), 0.0))
    return {"labels": labels, "dataset": values}


@rate_limit("summary:{user_id}", limit=20, window_secs=60)
@payments_bp.route("/payments/summary", methods=["GET"])
def payment_summary():
    if not current_user_id():
        return unauthenticated()

    user_id = current_user_id()
    cache_key = f"payment_summary:{user_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)

    with get_db() as db:
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        all_time = (
            db.query(
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.VERIFIED, Transaction.amount), else_=0)), 0).label("total_verified_amount"),
                func.count(Transaction.id).label("total_links"),
                func.sum(case((Transaction.status == TransactionStatus.VERIFIED, 1), else_=0)).label("total_verified"),
                func.sum(case((Transaction.status == TransactionStatus.EXPIRED, 1), else_=0)).label("total_expired"),
            )
            .filter(Transaction.user_id == user_id)
            .first()
        )

        this_month = (
            db.query(
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.VERIFIED, Transaction.amount), else_=0)), 0).label("total_verified_amount"),
                func.count(Transaction.id).label("total_links"),
                func.sum(case((Transaction.status == TransactionStatus.VERIFIED, 1), else_=0)).label("total_verified"),
            )
            .filter(Transaction.user_id == user_id, Transaction.created_at >= month_start)
            .first()
        )

        all_time_rate = round((all_time.total_verified or 0) / all_time.total_links * 100, 1) if all_time.total_links > 0 else 0
        this_month_rate = round((this_month.total_verified or 0) / this_month.total_links * 100, 1) if this_month.total_links > 0 else 0

        result = {
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
            "chart_data": _build_chart_data(db, user_id, now, thirty_days_ago),
        }
        cache_set(cache_key, result, ttl=60)
        return jsonify(result)


# ── Create payment link ────────────────────────────────────────────────────────


def _validate_idempotency_key(raw_key: Optional[str]) -> Optional[str]:
    """Sanitize and validate X-Idempotency-Key header value."""
    if not raw_key:
        return None
    key = raw_key[:255].replace("\x00", "").strip()
    if not key or not all(c.isalnum() or c in "-_" for c in key):
        raise ValidationError(
            "X-Idempotency-Key must be alphanumeric with hyphens/underscores (1-255 chars)"
        )
    return key


def _check_idempotent_existing(db, idempotency_key: str, user_id: int):
    """Return existing transaction if idempotency key already used, else None."""
    if not idempotency_key:
        return None
    return (
        db.query(Transaction)
        .filter(
            Transaction.idempotency_key == idempotency_key,
            Transaction.user_id == user_id,
        )
        .first()
    )


def _parse_amount(raw_amount) -> Decimal:
    """Parse and validate payment amount."""
    from decimal import ROUND_HALF_UP, InvalidOperation

    if not raw_amount:
        raise ValidationError("amount is required")
    try:
        amount = Decimal(str(raw_amount))
        if amount <= 0 or not amount.is_finite():
            raise ValidationError("amount must be a positive finite number")
        if amount > Decimal("100000000.00"):
            raise ValidationError("amount exceeds maximum allowed (100,000,000.00)")
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ArithmeticError, InvalidOperation):
        raise ValidationError("amount must be a valid number")


def _attach_virtual_account(db, transaction: Transaction, amount: Decimal) -> None:
    """Create KoraPay virtual account and attach to transaction."""
    if not korapay.is_transfer_configured():
        return
    amount_kobo = int(round(amount * 100))
    try:
        va = korapay.create_virtual_account(
            transaction_reference=transaction.tx_ref,
            amount_kobo=amount_kobo,
            account_name=f"{current_username()} - OnePay Payment",
        )
        transaction.virtual_account_number = va.get("accountNumber")
        transaction.virtual_bank_name = va.get("bankName")
        transaction.virtual_account_name = va.get("accountName")
        logger.info(
            "Virtual account created | ref=%s acct=%s",
            transaction.tx_ref, va.get("accountNumber"),
        )
    except KoraPayError as e:
        logger.error("Virtual account creation failed: %s", e)
        raise ProviderError("Payment provider unavailable", provider="KoraPay")


def _generate_qr_codes(transaction: Transaction, payment_url: str, amount: Decimal, description: Optional[str]) -> None:
    """Generate QR codes for payment URL and virtual account (best-effort)."""
    try:
        transaction.qr_code_payment_url = qr_service.generate_payment_qr(
            payment_url=payment_url,
            amount=str(amount),
            description=description,
            style="rounded",
        )
        if (
            transaction.virtual_account_number
            and transaction.virtual_bank_name
            and transaction.virtual_account_name
        ):
            transaction.qr_code_virtual_account = qr_service.generate_virtual_account_qr(
                account_number=transaction.virtual_account_number,
                bank_name=transaction.virtual_bank_name,
                account_name=transaction.virtual_account_name,
                amount=str(amount),
            )
        logger.debug("QR codes generated for transaction %s", transaction.tx_ref)
    except Exception:
        logger.warning("QR code generation failed | tx_ref=%s", transaction.tx_ref)


def _auto_create_invoice(db, transaction: Transaction, user: User, payment_url: str) -> Optional[str]:
    """Auto-create invoice and optionally email it. Returns invoice_number or None."""
    try:
        invoice_settings = (
            db.query(InvoiceSettings)
            .filter(InvoiceSettings.user_id == current_user_id())
            .first()
        )
        if not invoice_settings:
            return None

        invoice = invoice_service.create_invoice(
            db=db, transaction=transaction, user=user, settings=invoice_settings
        )
        logger.info(
            "Invoice created automatically | invoice_number=%s tx_ref=%s",
            invoice.invoice_number, transaction.tx_ref,
        )

        if invoice_settings.auto_send_email and transaction.customer_email:
            _try_send_invoice_email(db, invoice, transaction, payment_url)

        return invoice.invoice_number
    except Exception as e:
        logger.error("Invoice creation failed for tx_ref=%s | error=%s", transaction.tx_ref, e)
        return None


def _try_send_invoice_email(db, invoice, transaction: Transaction, payment_url: str) -> None:
    """Send invoice email (best-effort, never raises)."""
    try:
        pdf_bytes = invoice_service.generate_invoice_pdf(
            invoice=invoice, transaction=transaction, payment_url=payment_url,
        )
        email_sent = send_invoice_email(
            to_email=transaction.customer_email,
            invoice=invoice,
            pdf_bytes=pdf_bytes,
            payment_url=payment_url,
            qr_code_data_uri=transaction.qr_code_payment_url,
        )
        if email_sent:
            from models.invoice import InvoiceStatus
            with db.begin_nested():
                invoice.status = InvoiceStatus.SENT
                invoice.email_sent = True
                invoice.email_sent_at = datetime.now(timezone.utc)
                invoice.sent_at = datetime.now(timezone.utc)
                db.flush()
            logger.info(
                "Invoice emailed automatically | invoice_number=%s to=%s",
                invoice.invoice_number, transaction.customer_email,
            )
        else:
            logger.warning(
                "Invoice email failed | invoice_number=%s to=%s",
                invoice.invoice_number, transaction.customer_email,
            )
    except Exception as e:
        logger.error(
            "Invoice email failed | invoice_number=%s error=%s",
            invoice.invoice_number, e,
        )


@payments_bp.route("/payments/link", methods=["POST"])
def create_payment_link():
    if request.content_type != "application/json":
        from core.exceptions import OnePayError
        raise OnePayError("Content-Type must be application/json", "UNSUPPORTED_MEDIA_TYPE", 415)
    if not current_user_id():
        return unauthenticated()

    from core.api_auth import is_api_key_authenticated
    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not is_valid_csrf_token(csrf_header):
            raise AuthorizationError("CSRF validation failed")

    with get_db() as db:
        from flask import g
        if is_api_key_authenticated():
            rate_key, limit = f"api_link:{g.api_key}", Config.RATE_LIMIT_API_LINK_CREATE
        else:
            rate_key, limit = f"link:user:{current_user_id()}", Config.RATE_LIMIT_LINK_CREATE
        if not check_rate_limit(db, rate_key, limit):
            return rate_limited()

        data = request.get_json(silent=True) or {}
        idempotency_key = _validate_idempotency_key(request.headers.get("X-Idempotency-Key"))

        existing = _check_idempotent_existing(db, idempotency_key, current_user_id())
        if existing:
            base_url = request.host_url.rstrip("/")
            logger.info("Idempotent link returned | merchant=%s ref=%s", current_username(), existing.tx_ref)
            return jsonify({
                "success": True,
                "message": "Existing payment link returned (idempotent)",
                "tx_ref": existing.tx_ref,
                "payment_url": f"{base_url}/pay/{existing.tx_ref}",
                "amount": str(existing.amount),
                "currency": existing.currency,
                "description": existing.description,
                "expires_at": existing.expires_at_utc_iso(),
                "virtual_account_number": existing.virtual_account_number,
                "virtual_bank_name": existing.virtual_bank_name,
                "virtual_account_name": existing.virtual_account_name,
                "qr_code_payment_url": existing.qr_code_payment_url,
                "qr_code_virtual_account": existing.qr_code_virtual_account,
            }), 200

        amount = _parse_amount(data.get("amount"))
        tx_ref = generate_tx_reference()
        expires_at = generate_expiration_time()
        hash_token = generate_hash_token(tx_ref, amount, expires_at)

        user = db.query(User).filter(User.id == current_user_id()).first()
        per_link_webhook = validate_webhook_url(data.get("webhook_url", ""))
        webhook_url = per_link_webhook or (user.webhook_url if user else None)

        description = _safe(data.get("description"))
        if description and len(description) > 255:
            raise ValidationError("Description too long (max 255 characters)")

        transaction = Transaction(
            tx_ref=tx_ref,
            idempotency_key=idempotency_key,
            user_id=current_user_id(),
            amount=amount,
            currency=str(data.get("currency", "NGN")).upper()[:3],
            description=description,
            customer_email=_safe_email(data.get("customer_email")),
            customer_phone=_safe_phone(data.get("customer_phone")),
            return_url=validate_return_url(data.get("return_url")),
            webhook_url=webhook_url,
            hash_token=hash_token,
            expires_at=expires_at,
        )

        _attach_virtual_account(db, transaction, amount)
        db.add(transaction)
        db.flush()
        db.refresh(transaction)
        cache_delete(f"payment_summary:{current_user_id()}")

        base_url = request.host_url.rstrip("/")
        payment_url = f"{base_url}/pay/{tx_ref}"

        _generate_qr_codes(transaction, payment_url, amount, description)
        invoice_number = _auto_create_invoice(db, transaction, user, payment_url)

        log_event(
            db, "link.created",
            user_id=current_user_id(), tx_ref=tx_ref, ip_address=client_ip(),
            detail={"amount": str(amount), "currency": transaction.currency},
        )
        logger.info("Payment link created | merchant=%s ref=%s amount=%s", current_username(), tx_ref, amount)
        if tx_ref.startswith("VP-BILL-"):
            logger.info(
                "VoicePay payment link created | tx_ref=%s merchant=%s amount=₦%.2f description=%s",
                tx_ref, current_username(), float(amount), description or "N/A",
            )

        response_data = {
            "success": True,
            "message": "Payment link created successfully",
            "tx_ref": tx_ref,
            "payment_url": payment_url,
            "amount": str(amount),
            "currency": transaction.currency,
            "description": transaction.description,
            "expires_at": transaction.expires_at_utc_iso(),
            "virtual_account_number": transaction.virtual_account_number,
            "virtual_bank_name": transaction.virtual_bank_name,
            "virtual_account_name": transaction.virtual_account_name,
            "qr_code_payment_url": transaction.qr_code_payment_url,
            "qr_code_virtual_account": transaction.qr_code_virtual_account,
        }
        if invoice_number:
            response_data["invoice_number"] = invoice_number
        return jsonify(response_data), 201


# ── Transaction status ─────────────────────────────────────────────────────────


@rate_limit("status:{user_id}", limit=100, window_secs=60)
@payments_bp.route("/payments/status/<tx_ref>", methods=["GET"])
def transaction_status(tx_ref):
    """
    Get transaction status by reference.

    SECURITY (VULN-003): Implements constant-time response to prevent timing attacks
    that could enumerate valid transaction references.
    """
    if not current_user_id():
        return unauthenticated()

    # Start timing for constant-time response
    import secrets
    import time

    start_time = time.perf_counter()

    if not valid_tx_ref(tx_ref):
        # Add delay to match DB query time
        elapsed = time.perf_counter() - start_time
        target_delay = 0.05  # 50ms baseline
        jitter = secrets.randbelow(40) / 1000.0  # 0-40ms jitter
        remaining = max(0, target_delay + jitter - elapsed)
        time.sleep(remaining)
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        # Query with user_id filter to prevent enumeration
        t = (
            db.query(Transaction)
            .filter(
                Transaction.tx_ref == tx_ref, Transaction.user_id == current_user_id()
            )
            .first()
        )

        # Calculate elapsed time
        elapsed = time.perf_counter() - start_time

        if not t:
            # Add delay to match successful query time
            target_delay = 0.05  # 50ms baseline
            jitter = secrets.randbelow(40) / 1000.0  # 0-40ms jitter
            remaining = max(0, target_delay + jitter - elapsed)
            time.sleep(remaining)
            # Same error for both "not found" and "unauthorized"
            raise ValidationError("Transaction not found")

        # VoicePay-specific logging
        if t.tx_ref.startswith("VP-BILL-"):
            logger.info(
                "VoicePay status check | tx_ref=%s status=%s merchant=%s",
                t.tx_ref,
                t.status.value if t.status else "UNKNOWN",
                current_username(),
            )

        # Add jitter to successful responses too
        jitter = secrets.randbelow(40) / 1000.0
        time.sleep(jitter)

        return jsonify({"success": True, **t.to_dict()})


# ── Transaction history (paginated) ───────────────────────────────────────────


@payments_bp.route("/payments/history", methods=["GET"])
def transaction_history():
    if not current_user_id():
        return unauthenticated()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    offset = (page - 1) * PAGE_SIZE

    with get_db() as db:
        total = (
            db.query(Transaction)
            .filter(Transaction.user_id == current_user_id())
            .count()
        )

        transactions = (
            db.query(Transaction)
            .options(selectinload(Transaction.invoice))
            .filter(Transaction.user_id == current_user_id())
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "transactions": [t.to_dict() for t in transactions],
                "pagination": {
                    "page": page,
                    "page_size": PAGE_SIZE,
                    "total": total,
                    "total_pages": max(1, -(-total // PAGE_SIZE)),
                    "has_next": offset + PAGE_SIZE < total,
                    "has_prev": page > 1,
                },
            }
        )


# ── Re-issue expired link ──────────────────────────────────────────────────────


@payments_bp.route("/payments/reissue/<tx_ref>", methods=["POST"])
def reissue_payment_link(tx_ref):
    # VULN-007 FIX: Validate Content-Type for JSON API
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")
    if not current_user_id():
        return unauthenticated()

    # Skip CSRF for API key authenticated requests
    from core.api_auth import is_api_key_authenticated

    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get(
            "X-CSRF-Token"
        )
        if not is_valid_csrf_token(csrf_header):
            raise AuthorizationError("CSRF validation failed")

    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        # Fetch original transaction
        original = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not original:
            raise ValidationError("Transaction not found")

        # Verify ownership
        if original.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        # Don't re-issue verified transactions
        if original.status == TransactionStatus.VERIFIED or original.transfer_confirmed:
            raise ValidationError("Cannot re-issue a verified transaction")

        # Generate new transaction with same details
        new_tx_ref = generate_tx_reference()
        new_expires_at = generate_expiration_time()
        new_hash_token = generate_hash_token(
            new_tx_ref, original.amount, new_expires_at
        )

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

        # Create virtual account with KoraPay
        if korapay.is_transfer_configured():
            amount_kobo = int(round(original.amount * 100))
            try:
                va = korapay.create_virtual_account(
                    transaction_reference=new_tx_ref,
                    amount_kobo=amount_kobo,
                    account_name=f"{current_username()} - OnePay Payment",
                )
                # Store virtual account details
                new_transaction.virtual_account_number = va.get("accountNumber")
                new_transaction.virtual_bank_name = va.get("bankName")
                new_transaction.virtual_account_name = va.get("accountName")
                logger.info(
                    "Virtual account created for reissue | ref=%s acct=%s",
                    new_tx_ref,
                    va.get("accountNumber"),
                )
            except KoraPayError as e:
                logger.error("Virtual account creation failed for reissue: %s", e)
                raise ProviderError("Payment provider unavailable", provider="KoraPay")

        db.add(new_transaction)
        db.flush()
        db.refresh(new_transaction)

        log_event(
            db,
            "link.reissued",
            user_id=current_user_id(),
            tx_ref=new_tx_ref,
            ip_address=client_ip(),
            detail={"original_tx_ref": tx_ref, "amount": str(original.amount)},
        )

        base_url = request.host_url.rstrip("/")
        payment_url = f"{base_url}/pay/{new_tx_ref}"

        logger.info(
            "Payment link re-issued | merchant=%s original=%s new=%s",
            current_username(),
            tx_ref,
            new_tx_ref,
        )

        return jsonify(
            {
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
            }
        ), 201


# ── Audit log for transaction ─────────────────────────────────────────────────


@rate_limit("audit:{user_id}", limit=20, window_secs=60)
@payments_bp.route("/payments/audit/<tx_ref>", methods=["GET"])
def transaction_audit(tx_ref):
    if not current_user_id():
        return unauthenticated()

    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        # Verify ownership
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction:
            raise ValidationError("Transaction not found")

        if transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        # Fetch audit logs for this transaction
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.tx_ref == tx_ref)
            .order_by(AuditLog.created_at.asc())
            .all()
        )

        return jsonify(
            {
                "success": True,
                "tx_ref": tx_ref,
                "audit_logs": [log.to_dict() for log in logs],
            }
        )


# ── Expired payment link page ─────────────────────────────────────────────────


@payments_bp.route("/expired/<tx_ref>")
def expired_link(tx_ref):
    """Display expired payment link page to customer"""
    if not valid_tx_ref(tx_ref):
        return render_template(
            "expired.html", reference="Invalid", transaction_id="N/A"
        ), 404

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction:
            return render_template(
                "expired.html", reference="Not Found", transaction_id=tx_ref
            ), 404

        return render_template(
            "expired.html",
            reference=transaction.description or tx_ref,
            transaction_id=tx_ref,
        )


# ── Download receipt ───────────────────────────────────────────────────────────


@rate_limit("receipt:{user_id}", limit=10, window_secs=60)
@payments_bp.route("/payments/receipt/<tx_ref>", methods=["GET"])
def download_receipt(tx_ref):
    """Generate and download a PDF receipt for a transaction"""
    if not current_user_id():
        raise AuthenticationError()

    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not transaction:
            raise ValidationError("Transaction not found")

        # Verify ownership
        if transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        # Generate PDF receipt
        import io

        from flask import make_response, send_file

        from services.pdf_receipt import generate_receipt_pdf

        try:
            pdf_bytes = generate_receipt_pdf(transaction)

            # Create response with PDF
            response = make_response(pdf_bytes)
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Content-Disposition"] = (
                f"attachment; filename=OnePay_Receipt_{tx_ref}.pdf"
            )

            logger.info(
                "PDF receipt downloaded | user=%s tx_ref=%s", current_username(), tx_ref
            )
            return response

        except Exception as e:
            logger.error(
                "PDF receipt generation failed | user=%s tx_ref=%s error=%s",
                current_username(),
                tx_ref,
                e,
            )
            from core.exceptions import OnePayError
            raise OnePayError("Unable to generate receipt. Please try again later.", "RECEIPT_ERROR", 500)


@payments_bp.route("/payments/receipt/<tx_ref>/preview", methods=["GET"])
def preview_receipt_html(tx_ref):
    """Generate and return HTML preview of receipt (for debugging/testing)"""
    if not current_user_id():
        raise AuthenticationError()

    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not transaction:
            raise ValidationError("Transaction not found")

        if transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        from flask import make_response

        from services.pdf_receipt import generate_receipt_html

        try:
            html = generate_receipt_html(transaction)

            response = make_response(html)
            response.headers["Content-Type"] = "text/html"
            return response

        except Exception as e:
            logger.error(
                "Receipt HTML preview failed | user=%s tx_ref=%s error=%s",
                current_username(),
                tx_ref,
                e,
            )
            from core.exceptions import OnePayError
            raise OnePayError("Unable to generate preview. Please try again later.", "PREVIEW_ERROR", 500)


@payments_bp.route("/payments/refund/<tx_ref>", methods=["POST"])
def initiate_refund(tx_ref):
    """
    Initiate a refund for a verified transaction.

    Request body:
        {
            "amount": 1000,  # Optional, full refund if omitted
            "reason": "Customer request"  # Optional
        }

    Returns:
        {
            "success": true,
            "refund_reference": "REFUND-...",
            "status": "processing"
        }
    """
    # Authentication required
    if not current_user_id():
        raise AuthenticationError()

    # Validate transaction reference format
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    # Parse request body
    data = request.get_json() or {}
    refund_amount = data.get("amount")
    refund_reason = data.get("reason")

    with get_db() as db:
        # Find transaction
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not transaction:
            raise ValidationError("Transaction not found")

        # Verify ownership
        if transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        # Validate transaction is VERIFIED
        if transaction.status != TransactionStatus.VERIFIED:
            raise ValidationError("Cannot refund transaction that is not verified")

        # Check if already refunded
        from models.refund import Refund

        existing_refund = (
            db.query(Refund).filter(Refund.transaction_id == transaction.id).first()
        )

        if existing_refund:
            raise ValidationError("Transaction has already been refunded")

        try:
            # Call KoraPay to initiate refund
            refund_data = korapay.initiate_refund(
                payment_reference=tx_ref,
                refund_reference=None,  # Auto-generate
                amount=refund_amount,
                reason=refund_reason,
            )

            # Create refund record in database
            refund_amount_val = refund_data.get("amount")
            if refund_amount_val is None:
                from core.exceptions import OnePayError
                raise OnePayError("Unable to process refund. Please contact support.", "REFUND_ERROR", 500)
            refund = Refund(
                transaction_id=transaction.id,
                refund_reference=refund_data["reference"],
                amount=Decimal(str(refund_amount_val)),
                currency=refund_data["currency"],
                status=refund_data["status"],
                reason=refund_reason,
            )
            db.add(refund)

            log_event(
                db,
                "payment.refund_initiated",
                user_id=current_user_id(),
                ip_address=client_ip(),
                detail={
                    "tx_ref": tx_ref,
                    "refund_reference": refund_data["reference"],
                    "amount": refund_data["amount"],
                    "reason": refund_reason,
                },
            )

            db.commit()

            logger.info(
                "Refund initiated | user=%s tx_ref=%s refund_ref=%s amount=%s",
                current_username(),
                tx_ref,
                refund_data["reference"],
                refund_data["amount"],
            )

            return jsonify(
                {
                    "success": True,
                    "refund_reference": refund_data["reference"],
                    "status": refund_data["status"],
                    "amount": refund_data["amount"],
                    "currency": refund_data["currency"],
                }
            ), 200

        except KoraPayError as e:
            logger.error(
                "Refund initiation failed | user=%s tx_ref=%s error=%s",
                current_username(),
                tx_ref,
                str(e),
            )
            raise ProviderError("Unable to process refund. Please try again later.", provider="KoraPay", original_error=str(e))
        except Exception as e:
            logger.error(
                "Unexpected error during refund | user=%s tx_ref=%s error=%s",
                current_username(),
                tx_ref,
                str(e),
            )
            db.rollback()
            from core.exceptions import OnePayError
            raise OnePayError("An unexpected error occurred", "INTERNAL_ERROR", 500)

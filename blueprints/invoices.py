"""
OnePay — Invoices blueprint
Handles: invoice creation, retrieval, download, email, and settings
"""

import logging

from flask import Blueprint, jsonify, render_template, request

from core.auth import (
    current_user_id,
    current_username,
    get_csrf_token,
    login_required_redirect,
)
from core.exceptions import AuthenticationError, ProviderError, ValidationError
from core.responses import error, rate_limited, unauthenticated
from database import get_db
from models.user import User
from services.rate_limiter import check_rate_limit
from services.validators import validate_email, validate_phone

logger = logging.getLogger(__name__)
invoices_bp = Blueprint("invoices", __name__)


# ── Create invoice ─────────────────────────────────────────────────────────────


def _maybe_send_invoice_email_on_create(db, invoice, transaction, settings, data: dict) -> None:
    """Send invoice email if auto_send_email is enabled and conditions are met."""
    from datetime import datetime, timezone

    from models.invoice import InvoiceStatus
    from services.email import send_invoice_email
    from services.invoice import invoice_service

    auto_send = data.get("auto_send_email", False)
    if not (auto_send and settings and settings.auto_send_email and transaction.customer_email):
        return
    try:
        base_url = request.host_url.rstrip("/")
        payment_url = f"{base_url}/pay/{transaction.tx_ref}"
        pdf_bytes = invoice_service.generate_invoice_pdf(invoice=invoice, transaction=transaction, payment_url=payment_url)
        email_sent = send_invoice_email(
            to_email=transaction.customer_email, invoice=invoice, pdf_bytes=pdf_bytes,
            payment_url=payment_url, qr_code_data_uri=transaction.qr_code_payment_url,
        )
        if email_sent:
            invoice.status = InvoiceStatus.SENT
            invoice.sent_at = datetime.now(timezone.utc)
            db.flush()
            logger.info("Invoice email sent | invoice=%s to=%s", invoice.invoice_number, transaction.customer_email)
        else:
            logger.warning("Invoice email failed | invoice=%s to=%s", invoice.invoice_number, transaction.customer_email)
    except Exception as e:
        logger.error("Failed to send invoice email | invoice=%s error=%s", invoice.invoice_number, e)


@invoices_bp.route("/invoices/create", methods=["POST"])
def create_invoice():
    """Create invoice for an existing transaction"""
    if not current_user_id():
        return unauthenticated()

    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    with get_db() as db:
        if not check_rate_limit(db, f"invoice_create:{current_user_id()}", limit=20, window_secs=60):
            return rate_limited()

        data = request.get_json(silent=True) or {}
        transaction_reference = data.get("transaction_reference")
        if not transaction_reference:
            raise ValidationError("transaction_reference is required")

        from models.transaction import Transaction
        transaction = db.query(Transaction).filter(Transaction.tx_ref == transaction_reference).first()
        if not transaction or transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        from core.audit import log_event
        from models.invoice import Invoice, InvoiceSettings
        from services.invoice import invoice_service

        existing_invoice = db.query(Invoice).filter(Invoice.transaction_id == transaction.id).first()
        if existing_invoice:
            logger.info("Existing invoice returned (idempotent) | invoice=%s tx_ref=%s user_id=%d",
                        existing_invoice.invoice_number, transaction_reference, current_user_id())
            return jsonify({"success": True, "invoice": {
                "invoice_number": existing_invoice.invoice_number,
                "transaction_reference": transaction.tx_ref,
                "amount": str(existing_invoice.amount),
                "currency": existing_invoice.currency,
                "status": existing_invoice.status.value if hasattr(existing_invoice.status, "value") else str(existing_invoice.status),
                "created_at": existing_invoice.created_at_utc_iso(),
                "download_url": f"/api/invoices/{existing_invoice.invoice_number}/download",
            }}), 200

        from models.user import User
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            raise ValidationError("User not found")

        settings = db.query(InvoiceSettings).filter(InvoiceSettings.user_id == current_user_id()).first()

        with db.begin_nested():
            try:
                invoice = invoice_service.create_invoice(db=db, transaction=transaction, user=user, settings=settings)
                db.flush()
                log_event(db=db, event="invoice.created", user_id=current_user_id(), tx_ref=transaction.tx_ref,
                          ip_address=request.remote_addr,
                          detail={"invoice_number": invoice.invoice_number, "amount": str(invoice.amount), "currency": invoice.currency})
            except Exception as e:
                db.rollback()
                logger.error("Failed to create invoice | user_id=%s error=%s", current_user_id(), e)
                from core.exceptions import OnePayError
                raise OnePayError("Unable to create invoice. Please try again later.", "INVOICE_CREATION_FAILED", 500)

            _maybe_send_invoice_email_on_create(db, invoice, transaction, settings, data)

            return jsonify({"success": True, "invoice": {
                "invoice_number": invoice.invoice_number,
                "transaction_reference": transaction.tx_ref,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
                "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
                "created_at": invoice.created_at_utc_iso(),
                "download_url": f"/api/invoices/{invoice.invoice_number}/download",
            }}), 201


# ── Invoice page (HTML) and API list ─────────────────────────────────────────


@invoices_bp.route("/invoices", methods=["GET"])
def invoices_page():
    """Render the invoices HTML page or return JSON API response"""
    if not current_user_id():
        return login_required_redirect()

    # Return JSON only for direct /api/ path (not /api/v1/)
    # This allows /api/v1/invoices to render HTML while /api/invoices returns JSON
    # Use request.path which is just the path without query string
    if request.path == "/api/invoices":
        return list_invoices()

    # Otherwise render HTML page
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


# ── List invoices (API) ────────────────────────────────────────────────────────


def _format_invoice_list_item(invoice) -> dict:
    """Format a single invoice for list response."""
    return {
        "invoice_number": invoice.invoice_number,
        "transaction_reference": invoice.transaction.tx_ref if invoice.transaction else None,
        "customer_email": invoice.customer_email,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
        "created_at": invoice.created_at_utc_iso(),
        "paid_at": invoice.paid_at_utc_iso() if invoice.paid_at else None,
    }


def _parse_list_params() -> tuple[int, int, str, str]:
    """Parse and validate list query params. Returns (page, page_size, status_filter, sort)."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (ValueError, TypeError):
        raise ValidationError("Invalid pagination parameters")
    if page < 1:
        raise ValidationError("Page must be >= 1")
    page_size = min(max(page_size, 1), 100)
    sort = request.args.get("sort", "created_desc")
    valid_sorts = ["created_desc", "created_asc", "amount_desc", "amount_asc"]
    if sort not in valid_sorts:
        raise ValidationError(f"Invalid sort parameter. Must be one of: {', '.join(valid_sorts)}")
    return page, page_size, request.args.get("status"), sort


@invoices_bp.route("/invoices/list", methods=["GET"])
def list_invoices():
    """List invoices with pagination and filtering"""
    if not current_user_id():
        return unauthenticated()

    with get_db() as db:
        if not check_rate_limit(db, f"invoice_list:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()

        page, page_size, status_filter, sort = _parse_list_params()

        from core.audit import log_event
        from services.invoice import invoice_service

        try:
            invoices, total_count = invoice_service.get_invoice_history(
                db=db, user_id=current_user_id(), status=status_filter,
                page=page, page_size=page_size, sort=sort,
            )
            log_event(db=db, event="invoice.list", user_id=current_user_id(), ip_address=request.remote_addr,
                      detail={"page": page, "page_size": page_size, "status_filter": status_filter,
                              "sort": sort, "result_count": len(invoices)})
            total_pages = (total_count + page_size - 1) // page_size
            return jsonify({
                "success": True,
                "invoices": [_format_invoice_list_item(inv) for inv in invoices],
                "pagination": {"page": page, "page_size": page_size, "total_pages": total_pages, "total_count": total_count},
            }), 200
        except Exception as e:
            logger.error("Invoice list failed | user_id=%d error=%s", current_user_id(), e)
            from core.exceptions import OnePayError
            raise OnePayError("Unable to retrieve invoices. Please try again later.", "INVOICE_LIST_FAILED", 500)


# ── Get invoice details ────────────────────────────────────────────────────────


def _format_invoice_detail(invoice, base_url: str) -> dict:
    """Format full invoice detail for API response."""
    payment_link = f"{base_url}/verify/{invoice.transaction.tx_ref}" if invoice.transaction else None
    status_val = invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status)
    return {
        "invoice_number": invoice.invoice_number,
        "transaction_reference": invoice.transaction.tx_ref if invoice.transaction else None,
        "amount": str(invoice.amount), "currency": invoice.currency,
        "description": invoice.description, "customer_email": invoice.customer_email,
        "customer_phone": invoice.customer_phone, "business_name": invoice.business_name,
        "business_address": invoice.business_address, "business_tax_id": invoice.business_tax_id,
        "business_logo_url": invoice.business_logo_url, "payment_terms": invoice.payment_terms,
        "status": status_val, "created_at": invoice.created_at_utc_iso(),
        "sent_at": invoice.sent_at_utc_iso() if invoice.sent_at else None,
        "paid_at": invoice.paid_at_utc_iso() if invoice.paid_at else None,
        "payment_link": payment_link,
        "download_url": f"/api/invoices/{invoice.invoice_number}/download",
    }


@invoices_bp.route("/invoices/<invoice_number>", methods=["GET"])
def get_invoice(invoice_number):
    """Get detailed invoice information"""
    if not current_user_id():
        return unauthenticated()

    with get_db() as db:
        if not check_rate_limit(db, f"invoice_get:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()

        invoice, _ = _get_invoice_and_transaction(db, invoice_number)

        from core.audit import log_event
        log_event(db=db, event="invoice.viewed", user_id=current_user_id(),
                  tx_ref=invoice.transaction.tx_ref if invoice.transaction else None,
                  ip_address=request.remote_addr,
                  detail={"invoice_number": invoice.invoice_number,
                          "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status)})

        base_url = request.host_url.rstrip("/")
        return jsonify({"success": True, "invoice": _format_invoice_detail(invoice, base_url)}), 200


# ── Download invoice PDF ───────────────────────────────────────────────────────


def _get_invoice_and_transaction(db, invoice_number: str):
    """Fetch invoice and its transaction, raising on errors."""
    import re

    from models.transaction import Transaction
    from services.invoice import invoice_service

    if not re.match(r"^INV-\d{4}-\d{6}$", invoice_number):
        raise ValidationError("Invalid invoice number format")
    invoice = invoice_service.get_invoice_by_number(db=db, invoice_number=invoice_number, user_id=current_user_id())
    if not invoice:
        raise ValidationError("Invoice not found")
    transaction = db.query(Transaction).filter(Transaction.id == invoice.transaction_id).first()
    if not transaction:
        from core.exceptions import OnePayError
        raise OnePayError("Unable to process invoice. Please contact support.", "INVOICE_ERROR", 500)
    return invoice, transaction


def _generate_invoice_pdf_response(invoice, transaction, invoice_number: str):
    """Generate PDF and return Flask response."""
    from flask import make_response

    from core.audit import log_event
    from services.invoice import invoice_service

    base_url = request.host_url.rstrip("/")
    payment_url = f"{base_url}/verify/{transaction.tx_ref}"
    try:
        pdf_bytes = invoice_service.generate_invoice_pdf(invoice=invoice, transaction=transaction, payment_url=payment_url)
        log_event(db=None, event="invoice.downloaded", user_id=current_user_id(), tx_ref=transaction.tx_ref,
                  ip_address=request.remote_addr, detail={"invoice_number": invoice.invoice_number, "pdf_size_bytes": len(pdf_bytes)})
        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{invoice_number}.pdf"'
        response.headers["Content-Length"] = len(pdf_bytes)
        logger.info("Invoice PDF downloaded | invoice=%s user_id=%d size=%d bytes", invoice.invoice_number, current_user_id(), len(pdf_bytes))
        return response, payment_url, pdf_bytes
    except TimeoutError as e:
        logger.error("PDF generation timeout | invoice=%s error=%s", invoice.invoice_number, e)
        from core.exceptions import OnePayError
        raise OnePayError("Unable to generate invoice PDF. Please try again later.", "PDF_TIMEOUT", 500)
    except Exception as e:
        logger.error("PDF generation failed | invoice=%s error=%s", invoice.invoice_number, e)
        from core.exceptions import OnePayError
        raise OnePayError("Unable to generate invoice PDF. Please try again later.", "PDF_ERROR", 500)


@invoices_bp.route("/invoices/<invoice_number>/download", methods=["GET"])
def download_invoice(invoice_number):
    """Download invoice as PDF"""
    if not current_user_id():
        return unauthenticated()
    with get_db() as db:
        if not check_rate_limit(db, f"invoice_download:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()
        invoice, transaction = _get_invoice_and_transaction(db, invoice_number)
        response, _, _ = _generate_invoice_pdf_response(invoice, transaction, invoice_number)
        return response


@invoices_bp.route("/invoices/<invoice_number>/send", methods=["POST"])
def send_invoice(invoice_number):
    """Send invoice via email to customer"""
    if not current_user_id():
        return unauthenticated()
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    with get_db() as db:
        if not check_rate_limit(db, f"invoice_email:{current_user_id()}", limit=10, window_secs=60):
            return rate_limited()

        invoice, transaction = _get_invoice_and_transaction(db, invoice_number)

        data = request.get_json(silent=True) or {}
        recipient_email = data.get("recipient_email") or invoice.customer_email
        if not recipient_email:
            raise ValidationError("No recipient email available")

        from models.user import User
        merchant = db.query(User).filter(User.id == current_user_id()).first()
        merchant_email = merchant.email if merchant else None

        _, payment_url, pdf_bytes = _generate_invoice_pdf_response(invoice, transaction, invoice_number)

        from datetime import datetime, timezone

        from core.audit import log_event
        from models.invoice import InvoiceStatus
        from services.email import send_invoice_email

        try:
            email_sent = send_invoice_email(
                to_email=recipient_email, invoice=invoice, pdf_bytes=pdf_bytes,
                payment_url=payment_url, qr_code_data_uri=transaction.qr_code_payment_url,
                merchant_email=merchant_email,
            )
            if not email_sent:
                from core.exceptions import OnePayError
                raise OnePayError("Unable to send invoice email. Please try again later.", "EMAIL_ERROR", 500)

            invoice.status = InvoiceStatus.SENT
            invoice.sent_at = datetime.now(timezone.utc)
            db.flush()
            log_event(db=db, event="invoice.emailed", user_id=current_user_id(), tx_ref=transaction.tx_ref,
                      ip_address=request.remote_addr,
                      detail={"invoice_number": invoice.invoice_number, "recipient_email": recipient_email, "sent_at": invoice.sent_at.isoformat()})
            logger.info("Invoice email sent | invoice=%s to=%s user_id=%d", invoice.invoice_number, recipient_email, current_user_id())
            return jsonify({"success": True, "message": "Invoice sent successfully", "sent_to": recipient_email, "sent_at": invoice.sent_at_utc_iso()}), 200

        except Exception as e:
            logger.error("Invoice email failed | invoice=%s user_id=%d error=%s", invoice.invoice_number, current_user_id(), e)
            from core.exceptions import OnePayError
            raise OnePayError("Unable to send invoice. Please try again later.", "INVOICE_SEND_ERROR", 500)


# ── Get invoice settings ───────────────────────────────────────────────────────


@invoices_bp.route("/invoices/settings", methods=["GET"])
def get_invoice_settings():
    """Get merchant invoice settings"""
    if not current_user_id():
        return unauthenticated()

    with get_db() as db:
        # Rate limit: 50 requests per minute
        if not check_rate_limit(
            db, f"invoice_settings_get:{current_user_id()}", limit=50, window_secs=60
        ):
            return rate_limited()

        from models.invoice import InvoiceSettings

        # Fetch or create default settings for current user
        settings = (
            db.query(InvoiceSettings)
            .filter(InvoiceSettings.user_id == current_user_id())
            .first()
        )

        if not settings:
            # Create default settings
            settings = InvoiceSettings(
                user_id=current_user_id(),
                default_payment_terms="Payment due upon receipt",
                auto_send_email=False,
            )
            db.add(settings)
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(
                    "Failed to create default invoice settings | user_id=%d error=%s",
                    current_user_id(), e
                )
                settings = InvoiceSettings(
                    user_id=current_user_id(),
                    default_payment_terms="Payment due upon receipt",
                    auto_send_email=False,
                )

            logger.info(
                "Default invoice settings created | user_id=%d", current_user_id()
            )

        # Return settings as JSON
        return jsonify({"success": True, "settings": settings.to_dict()}), 200


# ── Update invoice settings ────────────────────────────────────────────────────


def _validate_logo_url(raw_logo_url: str, user_id: int) -> str:
    """Validate logo URL with SSRF protection. Returns sanitized URL or raises ValidationError."""
    import html as _html
    from urllib.parse import urlparse

    import requests

    from services.url_validator import validate_url_for_ssrf

    def _safe_str(val, maxlen=500):
        if not val:
            return None
        s = str(val).strip()
        s = "".join(c for c in s if c == "\n" or c == "\t" or (ord(c) >= 32 and ord(c) != 127))
        return _html.escape(s)[:maxlen] if s else None

    logo_url = _safe_str(raw_logo_url)
    if not logo_url:
        return None

    is_valid, resolved_ip, error_msg = validate_url_for_ssrf(logo_url)
    if not is_valid:
        logger.warning(
            "Logo URL SSRF validation failed | user_id=%d url=%s error=%s",
            user_id, logo_url, error_msg,
        )
        raise ValidationError("The provided logo URL is not valid or accessible")

    try:
        parsed = urlparse(logo_url)
        ip_url = f"{parsed.scheme}://{resolved_ip}{parsed.path}"
        if parsed.query:
            ip_url += f"?{parsed.query}"
        response = requests.head(ip_url, headers={"Host": parsed.hostname}, timeout=5, allow_redirects=True)
        if response.status_code != 200:
            raise ValidationError(f"Logo URL is not accessible (HTTP {response.status_code})")
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(ct in content_type for ct in ["image/png", "image/jpeg", "image/jpg", "image/svg+xml"]):
            raise ValidationError("Logo URL must return a valid image format (PNG, JPG, or SVG)")
        return logo_url
    except requests.Timeout:
        raise ValidationError("Logo URL request timed out - URL may be inaccessible")
    except requests.RequestException as e:
        logger.error("Logo URL validation failed | user_id=%d url=%s error=%s", user_id, logo_url, e)
        raise ValidationError("Logo URL is not accessible")


def _upsert_invoice_settings(db, settings, data: dict, fields: dict):
    """Create or update InvoiceSettings record from validated field dict."""
    from models.invoice import InvoiceSettings

    if not settings:
        settings = InvoiceSettings(
            user_id=fields["user_id"],
            business_name=fields.get("business_name"),
            business_address=fields.get("business_address"),
            business_tax_id=fields.get("business_tax_id"),
            business_logo_url=fields.get("business_logo_url"),
            default_payment_terms=fields.get("default_payment_terms") or "Payment due upon receipt",
            auto_send_email=fields.get("auto_send_email") or False,
        )
        db.add(settings)
    else:
        for key in ("business_name", "business_address", "business_tax_id",
                    "business_logo_url", "default_payment_terms", "auto_send_email"):
            if fields.get(key) is not None:
                setattr(settings, key, fields[key])
    return settings


def _safe_settings_field(val, maxlen: int = 255) -> str:
    """Sanitize a settings text field."""
    import html
    if not val:
        return None
    s = str(val).strip()
    s = "".join(c for c in s if c == "\n" or c == "\t" or (ord(c) >= 32 and ord(c) != 127))
    return html.escape(s)[:maxlen] if s else None


@invoices_bp.route("/invoices/settings", methods=["POST"])
def update_invoice_settings():
    """Update merchant invoice settings"""
    if not current_user_id():
        return unauthenticated()
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")

    with get_db() as db:
        if not check_rate_limit(db, f"invoice_settings_update:{current_user_id()}", limit=10, window_secs=60):
            return rate_limited()

        from core.audit import log_event
        from models.invoice import InvoiceSettings

        data = request.get_json(silent=True) or {}
        auto_send_email = data.get("auto_send_email")
        if auto_send_email is not None and not isinstance(auto_send_email, bool):
            raise ValidationError("auto_send_email must be a boolean value")

        business_logo_url = _validate_logo_url(data["business_logo_url"], current_user_id()) if data.get("business_logo_url") else None

        fields = {
            "user_id": current_user_id(),
            "business_name": _safe_settings_field(data.get("business_name"), 255),
            "business_address": _safe_settings_field(data.get("business_address"), 1000),
            "business_tax_id": _safe_settings_field(data.get("business_tax_id"), 100),
            "business_logo_url": business_logo_url,
            "default_payment_terms": _safe_settings_field(data.get("default_payment_terms"), 500),
            "auto_send_email": auto_send_email,
        }

        settings = db.query(InvoiceSettings).filter(InvoiceSettings.user_id == current_user_id()).first()
        settings = _upsert_invoice_settings(db, settings, data, fields)

        try:
            db.commit()
            log_event(db=db, event="invoice.settings_updated", user_id=current_user_id(), ip_address=request.remote_addr,
                      detail={"business_name": settings.business_name, "has_logo": bool(settings.business_logo_url), "auto_send_email": settings.auto_send_email})
            logger.info("Invoice settings updated | user_id=%d", current_user_id())
            return jsonify({"success": True, "message": "Invoice settings updated successfully", "settings": settings.to_dict()}), 200
        except Exception as e:
            db.rollback()
            logger.error("Invoice settings update failed | user_id=%d error=%s", current_user_id(), e)
            from core.exceptions import OnePayError
            raise OnePayError("Unable to update settings. Please try again later.", "SETTINGS_ERROR", 500)

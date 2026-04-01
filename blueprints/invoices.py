"""
OnePay — Invoices blueprint
Handles: invoice creation, retrieval, download, email, and settings
"""
import logging

from flask import Blueprint, request, jsonify

from database import get_db
from services.rate_limiter import check_rate_limit
from core.auth import (
    current_user_id,
    login_required_redirect,
)
from core.responses import error, rate_limited, unauthenticated

logger = logging.getLogger(__name__)
invoices_bp = Blueprint("invoices", __name__)


# ── Create invoice ─────────────────────────────────────────────────────────────

@invoices_bp.route("/invoices/create", methods=["POST"])
def create_invoice():
    """Create invoice for an existing transaction"""
    if not current_user_id():
        return unauthenticated()
    
    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    
    with get_db() as db:
        # Rate limit: 20 requests per minute
        if not check_rate_limit(db, f"invoice_create:{current_user_id()}", limit=20, window_secs=60):
            return rate_limited()
        
        data = request.get_json(silent=True) or {}
        
        # Validate transaction_reference parameter
        transaction_reference = data.get("transaction_reference")
        if not transaction_reference:
            return error("transaction_reference is required", "VALIDATION_ERROR", 400)
        
        # Fetch transaction
        from models.transaction import Transaction
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == transaction_reference
        ).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # Verify transaction ownership
        if transaction.user_id != current_user_id():
            return error("Transaction not found", "NOT_FOUND", 404)  # Security through obscurity
        
        # Check if invoice already exists (idempotency)
        from models.invoice import Invoice, InvoiceSettings
        from services.invoice import invoice_service
        from core.audit import log_event
        
        existing_invoice = db.query(Invoice).filter(
            Invoice.transaction_id == transaction.id
        ).first()
        
        if existing_invoice:
            # Idempotent - return existing invoice
            logger.info(
                "Existing invoice returned (idempotent) | invoice=%s tx_ref=%s user_id=%d",
                existing_invoice.invoice_number, transaction_reference, current_user_id()
            )
            
            return jsonify({
                "success": True,
                "invoice": {
                    "invoice_number": existing_invoice.invoice_number,
                    "transaction_reference": transaction.tx_ref,
                    "amount": str(existing_invoice.amount),
                    "currency": existing_invoice.currency,
                    "status": existing_invoice.status.value if hasattr(existing_invoice.status, 'value') else str(existing_invoice.status),
                    "created_at": existing_invoice.created_at_utc_iso(),
                    "download_url": f"/api/invoices/{existing_invoice.invoice_number}/download"
                }
            }), 200
        
        # Fetch user and settings
        from models.user import User
        user = db.query(User).filter(User.id == current_user_id()).first()
        if not user:
            return error("User not found", "NOT_FOUND", 404)
        
        settings = db.query(InvoiceSettings).filter(
            InvoiceSettings.user_id == current_user_id()
        ).first()
        
        # Create invoice using InvoiceService
        try:
            invoice = invoice_service.create_invoice(
                db=db,
                transaction=transaction,
                user=user,
                settings=settings
            )
            
            db.commit()
            
            # Add audit logging
            log_event(
                db=db,
                event="invoice.created",
                user_id=current_user_id(),
                tx_ref=transaction.tx_ref,
                ip_address=request.remote_addr,
                detail={
                    "invoice_number": invoice.invoice_number,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency
                }
            )
            
            # Optionally send email if auto_send_email enabled
            auto_send_email = data.get("auto_send_email", False)
            if auto_send_email and settings and settings.auto_send_email and transaction.customer_email:
                try:
                    # Generate PDF
                    base_url = request.host_url.rstrip("/")
                    payment_url = f"{base_url}/pay/{transaction.tx_ref}"
                    pdf_bytes = invoice_service.generate_invoice_pdf(
                        invoice=invoice,
                        transaction=transaction,
                        payment_url=payment_url
                    )
                    
                    # Send email
                    from services.email import send_invoice_email
                    email_sent = send_invoice_email(
                        to_email=transaction.customer_email,
                        invoice=invoice,
                        pdf_bytes=pdf_bytes,
                        payment_url=payment_url,
                        qr_code_data_uri=transaction.qr_code_payment_url
                    )
                    
                    if email_sent:
                        from models.invoice import InvoiceStatus
                        from datetime import datetime, timezone
                        invoice.status = InvoiceStatus.SENT
                        invoice.sent_at = datetime.now(timezone.utc)
                        db.commit()
                        
                        logger.info(
                            "Invoice email sent | invoice=%s to=%s",
                            invoice.invoice_number, transaction.customer_email
                        )
                    else:
                        logger.warning(
                            "Invoice email failed | invoice=%s to=%s",
                            invoice.invoice_number, transaction.customer_email
                        )
                except Exception as e:
                    logger.error(
                        "Failed to send invoice email | invoice=%s error=%s",
                        invoice.invoice_number, e
                    )
                    # Don't fail the request - invoice was created successfully
            
            # Return invoice details with download URL
            return jsonify({
                "success": True,
                "invoice": {
                    "invoice_number": invoice.invoice_number,
                    "transaction_reference": transaction.tx_ref,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency,
                    "status": invoice.status.value if hasattr(invoice.status, 'value') else str(invoice.status),
                    "created_at": invoice.created_at_utc_iso(),
                    "download_url": f"/api/invoices/{invoice.invoice_number}/download"
                }
            }), 201
            
        except Exception as e:
            db.rollback()
            logger.error(
                "Invoice creation failed | tx_ref=%s user_id=%d error=%s",
                transaction_reference, current_user_id(), e
            )
            return error("Failed to create invoice", "INTERNAL_ERROR", 500)


# ── List invoices ──────────────────────────────────────────────────────────────

@invoices_bp.route("/invoices", methods=["GET"])
def list_invoices():
    """List invoices with pagination and filtering"""
    if not current_user_id():
        return unauthenticated()
    
    with get_db() as db:
        # Rate limit: 50 requests per minute
        if not check_rate_limit(db, f"invoice_list:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()
        
        # Parse pagination parameters
        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
        except (ValueError, TypeError):
            return error("Invalid pagination parameters", "VALIDATION_ERROR", 400)
        
        # Validate page and page_size
        if page < 1:
            return error("Page must be >= 1", "VALIDATION_ERROR", 400)
        
        # Limit page_size to 100
        page_size = min(page_size, 100)
        if page_size < 1:
            return error("Page size must be >= 1", "VALIDATION_ERROR", 400)
        
        # Parse optional status filter
        status_filter = request.args.get('status')
        
        # Parse optional sort parameter
        sort = request.args.get('sort', 'created_desc')
        
        # Validate sort parameter
        valid_sorts = ['created_desc', 'created_asc', 'amount_desc', 'amount_asc']
        if sort not in valid_sorts:
            return error(f"Invalid sort parameter. Must be one of: {', '.join(valid_sorts)}", 
                        "VALIDATION_ERROR", 400)
        
        # Get invoice history using service
        from services.invoice import invoice_service
        from core.audit import log_event
        
        try:
            invoices, total_count = invoice_service.get_invoice_history(
                db=db,
                user_id=current_user_id(),
                status=status_filter,
                page=page,
                page_size=page_size,
                sort=sort
            )
            
            # Add audit logging
            log_event(
                db=db,
                event="invoice.list",
                user_id=current_user_id(),
                ip_address=request.remote_addr,
                detail={
                    "page": page,
                    "page_size": page_size,
                    "status_filter": status_filter,
                    "sort": sort,
                    "result_count": len(invoices)
                }
            )
            
            # Format response
            invoice_list = []
            for invoice in invoices:
                invoice_list.append({
                    "invoice_number": invoice.invoice_number,
                    "transaction_reference": invoice.transaction.tx_ref if invoice.transaction else None,
                    "customer_email": invoice.customer_email,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency,
                    "status": invoice.status.value if hasattr(invoice.status, 'value') else str(invoice.status),
                    "created_at": invoice.created_at_utc_iso(),
                    "paid_at": invoice.paid_at_utc_iso() if invoice.paid_at else None
                })
            
            # Calculate pagination metadata
            total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
            
            return jsonify({
                "success": True,
                "invoices": invoice_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "total_count": total_count
                }
            }), 200
            
        except Exception as e:
            logger.error(
                "Invoice list failed | user_id=%d error=%s",
                current_user_id(), e
            )
            return error("Failed to retrieve invoices", "INTERNAL_ERROR", 500)


# ── Get invoice details ────────────────────────────────────────────────────────

@invoices_bp.route("/invoices/<invoice_number>", methods=["GET"])
def get_invoice(invoice_number):
    """Get detailed invoice information"""
    if not current_user_id():
        return unauthenticated()
    
    with get_db() as db:
        # Rate limit: 50 requests per minute
        if not check_rate_limit(db, f"invoice_get:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()
        
        # Validate invoice_number format (INV-YYYY-NNNNNN)
        import re
        if not re.match(r'^INV-\d{4}-\d{6}$', invoice_number):
            return error("Invalid invoice number format", "VALIDATION_ERROR", 400)
        
        # Fetch invoice with ownership verification
        from services.invoice import invoice_service
        from core.audit import log_event
        
        invoice = invoice_service.get_invoice_by_number(
            db=db,
            invoice_number=invoice_number,
            user_id=current_user_id()
        )
        
        if not invoice:
            return error("Invoice not found", "NOT_FOUND", 404)
        
        # Add audit logging
        log_event(
            db=db,
            event="invoice.viewed",
            user_id=current_user_id(),
            tx_ref=invoice.transaction.tx_ref if invoice.transaction else None,
            ip_address=request.remote_addr,
            detail={
                "invoice_number": invoice.invoice_number,
                "status": invoice.status.value if hasattr(invoice.status, 'value') else str(invoice.status)
            }
        )
        
        # Build payment link URL
        base_url = request.host_url.rstrip("/")
        payment_link = None
        if invoice.transaction:
            payment_link = f"{base_url}/verify/{invoice.transaction.tx_ref}"
        
        # Return detailed invoice information
        return jsonify({
            "success": True,
            "invoice": {
                "invoice_number": invoice.invoice_number,
                "transaction_reference": invoice.transaction.tx_ref if invoice.transaction else None,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
                "description": invoice.description,
                "customer_email": invoice.customer_email,
                "customer_phone": invoice.customer_phone,
                "business_name": invoice.business_name,
                "business_address": invoice.business_address,
                "business_tax_id": invoice.business_tax_id,
                "business_logo_url": invoice.business_logo_url,
                "payment_terms": invoice.payment_terms,
                "status": invoice.status.value if hasattr(invoice.status, 'value') else str(invoice.status),
                "created_at": invoice.created_at_utc_iso(),
                "sent_at": invoice.sent_at_utc_iso() if invoice.sent_at else None,
                "paid_at": invoice.paid_at_utc_iso() if invoice.paid_at else None,
                "payment_link": payment_link,
                "download_url": f"/api/invoices/{invoice.invoice_number}/download"
            }
        }), 200


# ── Download invoice PDF ───────────────────────────────────────────────────────

@invoices_bp.route("/invoices/<invoice_number>/download", methods=["GET"])
def download_invoice(invoice_number):
    """Download invoice as PDF"""
    if not current_user_id():
        return unauthenticated()
    
    with get_db() as db:
        # Rate limit: 50 requests per minute
        if not check_rate_limit(db, f"invoice_download:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()
        
        # Validate invoice_number format (INV-YYYY-NNNNNN)
        import re
        if not re.match(r'^INV-\d{4}-\d{6}$', invoice_number):
            return error("Invalid invoice number format", "VALIDATION_ERROR", 400)
        
        # Fetch invoice with ownership verification
        from services.invoice import invoice_service
        from core.audit import log_event
        
        invoice = invoice_service.get_invoice_by_number(
            db=db,
            invoice_number=invoice_number,
            user_id=current_user_id()
        )
        
        if not invoice:
            return error("Invoice not found", "NOT_FOUND", 404)
        
        # Fetch associated transaction
        from models.transaction import Transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == invoice.transaction_id
        ).first()
        
        if not transaction:
            logger.error(
                "Transaction not found for invoice | invoice=%s transaction_id=%d",
                invoice.invoice_number, invoice.transaction_id
            )
            return error("Transaction not found", "INTERNAL_ERROR", 500)
        
        # Generate PDF using InvoiceService
        try:
            # Build payment URL
            base_url = request.host_url.rstrip("/")
            payment_url = f"{base_url}/verify/{transaction.tx_ref}"
            
            # Generate PDF
            pdf_bytes = invoice_service.generate_invoice_pdf(
                invoice=invoice,
                transaction=transaction,
                payment_url=payment_url
            )
            
            # Add audit logging
            log_event(
                db=db,
                event="invoice.downloaded",
                user_id=current_user_id(),
                tx_ref=transaction.tx_ref,
                ip_address=request.remote_addr,
                detail={
                    "invoice_number": invoice.invoice_number,
                    "pdf_size_bytes": len(pdf_bytes)
                }
            )
            
            # Set appropriate headers and stream PDF
            from flask import make_response
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{invoice_number}.pdf"'
            response.headers['Content-Length'] = len(pdf_bytes)
            
            logger.info(
                "Invoice PDF downloaded | invoice=%s user_id=%d size=%d bytes",
                invoice.invoice_number, current_user_id(), len(pdf_bytes)
            )
            
            return response
            
        except TimeoutError as e:
            logger.error(
                "PDF generation timeout | invoice=%s user_id=%d error=%s",
                invoice.invoice_number, current_user_id(), e
            )
            return error("PDF generation timed out", "PDF_GENERATION_TIMEOUT", 500)
        except Exception as e:
            logger.error(
                "PDF generation failed | invoice=%s user_id=%d error=%s",
                invoice.invoice_number, current_user_id(), e
            )
            return error("Failed to generate PDF", "PDF_GENERATION_ERROR", 500)


# ── Send invoice via email ─────────────────────────────────────────────────────

@invoices_bp.route("/invoices/<invoice_number>/send", methods=["POST"])
def send_invoice(invoice_number):
    """Send invoice via email to customer"""
    if not current_user_id():
        return unauthenticated()
    
    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    
    with get_db() as db:
        # Rate limit: 10 requests per minute
        if not check_rate_limit(db, f"invoice_email:{current_user_id()}", limit=10, window_secs=60):
            return rate_limited()
        
        # Validate invoice_number format (INV-YYYY-NNNNNN)
        import re
        if not re.match(r'^INV-\d{4}-\d{6}$', invoice_number):
            return error("Invalid invoice number format", "VALIDATION_ERROR", 400)
        
        # Fetch invoice with ownership verification
        from services.invoice import invoice_service
        from core.audit import log_event
        
        invoice = invoice_service.get_invoice_by_number(
            db=db,
            invoice_number=invoice_number,
            user_id=current_user_id()
        )
        
        if not invoice:
            return error("Invoice not found", "NOT_FOUND", 404)
        
        # Parse optional recipient_email parameter
        data = request.get_json(silent=True) or {}
        recipient_email = data.get("recipient_email")
        
        # Use invoice customer_email if no recipient specified
        if not recipient_email:
            recipient_email = invoice.customer_email
        
        # Validate recipient email exists
        if not recipient_email:
            return error("No recipient email available", "VALIDATION_ERROR", 400)
        
        # Get merchant email for BCC (merchant receives a copy)
        from models.user import User
        merchant = db.query(User).filter(User.id == current_user_id()).first()
        merchant_email = merchant.email if merchant else None
        
        # Fetch associated transaction
        from models.transaction import Transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == invoice.transaction_id
        ).first()
        
        if not transaction:
            logger.error(
                "Transaction not found for invoice | invoice=%s transaction_id=%d",
                invoice.invoice_number, invoice.transaction_id
            )
            return error("Transaction not found", "INTERNAL_ERROR", 500)
        
        # Generate PDF
        try:
            # Build payment URL
            base_url = request.host_url.rstrip("/")
            payment_url = f"{base_url}/verify/{transaction.tx_ref}"
            
            # Generate PDF
            pdf_bytes = invoice_service.generate_invoice_pdf(
                invoice=invoice,
                transaction=transaction,
                payment_url=payment_url
            )
            
            # Send email using email service
            from services.email import send_invoice_email
            from models.invoice import InvoiceStatus
            from datetime import datetime, timezone
            
            email_sent = send_invoice_email(
                to_email=recipient_email,
                invoice=invoice,
                pdf_bytes=pdf_bytes,
                payment_url=payment_url,
                qr_code_data_uri=transaction.qr_code_payment_url,
                merchant_email=merchant_email
            )
            
            if email_sent:
                # Update invoice status to sent
                invoice.status = InvoiceStatus.SENT
                invoice.sent_at = datetime.now(timezone.utc)
                db.commit()
                
                # Add audit logging
                log_event(
                    db=db,
                    event="invoice.emailed",
                    user_id=current_user_id(),
                    tx_ref=transaction.tx_ref,
                    ip_address=request.remote_addr,
                    detail={
                        "invoice_number": invoice.invoice_number,
                        "recipient_email": recipient_email,
                        "sent_at": invoice.sent_at.isoformat()
                    }
                )
                
                logger.info(
                    "Invoice email sent | invoice=%s to=%s user_id=%d",
                    invoice.invoice_number, recipient_email, current_user_id()
                )
                
                return jsonify({
                    "success": True,
                    "message": "Invoice sent successfully",
                    "sent_to": recipient_email,
                    "sent_at": invoice.sent_at_utc_iso()
                }), 200
            else:
                # Email failed
                logger.error(
                    "Invoice email failed | invoice=%s to=%s user_id=%d",
                    invoice.invoice_number, recipient_email, current_user_id()
                )
                return error("Failed to send invoice email", "EMAIL_DELIVERY_FAILED", 500)
                
        except TimeoutError as e:
            logger.error(
                "PDF generation timeout for email | invoice=%s user_id=%d error=%s",
                invoice.invoice_number, current_user_id(), e
            )
            return error("PDF generation timed out", "PDF_GENERATION_TIMEOUT", 500)
        except Exception as e:
            logger.error(
                "Invoice email failed | invoice=%s user_id=%d error=%s",
                invoice.invoice_number, current_user_id(), e
            )
            return error("Failed to send invoice", "INTERNAL_ERROR", 500)


# ── Get invoice settings ───────────────────────────────────────────────────────

@invoices_bp.route("/invoices/settings", methods=["GET"])
def get_invoice_settings():
    """Get merchant invoice settings"""
    if not current_user_id():
        return unauthenticated()
    
    with get_db() as db:
        # Rate limit: 50 requests per minute
        if not check_rate_limit(db, f"invoice_settings_get:{current_user_id()}", limit=50, window_secs=60):
            return rate_limited()
        
        from models.invoice import InvoiceSettings
        
        # Fetch or create default settings for current user
        settings = db.query(InvoiceSettings).filter(
            InvoiceSettings.user_id == current_user_id()
        ).first()
        
        if not settings:
            # Create default settings
            settings = InvoiceSettings(
                user_id=current_user_id(),
                default_payment_terms="Payment due upon receipt",
                auto_send_email=False
            )
            db.add(settings)
            db.commit()
            
            logger.info(
                "Default invoice settings created | user_id=%d",
                current_user_id()
            )
        
        # Return settings as JSON
        return jsonify({
            "success": True,
            "settings": settings.to_dict()
        }), 200


# ── Update invoice settings ────────────────────────────────────────────────────

@invoices_bp.route("/invoices/settings", methods=["POST"])
def update_invoice_settings():
    """Update merchant invoice settings"""
    if not current_user_id():
        return unauthenticated()
    
    # Validate Content-Type to prevent CSRF via form submission
    if request.content_type != 'application/json':
        return error("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
    
    with get_db() as db:
        # Rate limit: 10 requests per minute
        if not check_rate_limit(db, f"invoice_settings_update:{current_user_id()}", limit=10, window_secs=60):
            return rate_limited()
        
        from models.invoice import InvoiceSettings
        from core.audit import log_event
        from services.security import validate_webhook_url
        import html
        
        # Parse request data
        data = request.get_json(silent=True) or {}
        
        # Sanitize text inputs using existing helper
        def _safe(val, maxlen=255):
            """Strip, escape HTML, remove control characters, and truncate"""
            if not val:
                return None
            sanitized = str(val).strip()
            sanitized = ''.join(c for c in sanitized if c == '\n' or c == '\t' or (ord(c) >= 32 and ord(c) != 127))
            sanitized = html.escape(sanitized)
            return sanitized[:maxlen] if sanitized else None
        
        # Validate and sanitize fields
        business_name = _safe(data.get("business_name"), 255)
        business_address = _safe(data.get("business_address"), 1000)
        business_tax_id = _safe(data.get("business_tax_id"), 100)
        default_payment_terms = _safe(data.get("default_payment_terms"), 500)
        
        # Validate logo URL if provided
        business_logo_url = None
        raw_logo_url = data.get("business_logo_url")
        if raw_logo_url:
            # Sanitize and validate URL format
            logo_url = _safe(raw_logo_url, 500)
            if logo_url:
                # Use webhook URL validator as it checks for HTTPS and public hosts
                validated_url = validate_webhook_url(logo_url)
                if not validated_url:
                    return error(
                        "Invalid logo URL - must be a public HTTPS URL",
                        "VALIDATION_ERROR",
                        400
                    )
                
                # Validate URL is accessible and returns an image
                try:
                    import requests
                    response = requests.head(validated_url, timeout=5, allow_redirects=True)
                    
                    # Check if URL is accessible
                    if response.status_code != 200:
                        return error(
                            f"Logo URL is not accessible (HTTP {response.status_code})",
                            "VALIDATION_ERROR",
                            400
                        )
                    
                    # Check content type is an image
                    content_type = response.headers.get('Content-Type', '').lower()
                    valid_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
                    if not any(ct in content_type for ct in valid_types):
                        return error(
                            "Logo URL must return a valid image format (PNG, JPG, or SVG)",
                            "VALIDATION_ERROR",
                            400
                        )
                    
                    business_logo_url = validated_url
                    
                except requests.Timeout:
                    return error(
                        "Logo URL request timed out - URL may be inaccessible",
                        "VALIDATION_ERROR",
                        400
                    )
                except requests.RequestException as e:
                    logger.error(
                        "Logo URL validation failed | user_id=%d url=%s error=%s",
                        current_user_id(), validated_url, e
                    )
                    return error(
                        "Logo URL is not accessible",
                        "VALIDATION_ERROR",
                        400
                    )
        
        # Validate auto_send_email is boolean
        auto_send_email = data.get("auto_send_email")
        if auto_send_email is not None and not isinstance(auto_send_email, bool):
            return error(
                "auto_send_email must be a boolean value",
                "VALIDATION_ERROR",
                400
            )
        
        # Fetch or create settings record
        settings = db.query(InvoiceSettings).filter(
            InvoiceSettings.user_id == current_user_id()
        ).first()
        
        if not settings:
            # Create new settings record
            settings = InvoiceSettings(
                user_id=current_user_id(),
                business_name=business_name,
                business_address=business_address,
                business_tax_id=business_tax_id,
                business_logo_url=business_logo_url,
                default_payment_terms=default_payment_terms or "Payment due upon receipt",
                auto_send_email=auto_send_email if auto_send_email is not None else False
            )
            db.add(settings)
        else:
            # Update existing settings
            if business_name is not None:
                settings.business_name = business_name
            if business_address is not None:
                settings.business_address = business_address
            if business_tax_id is not None:
                settings.business_tax_id = business_tax_id
            if business_logo_url is not None:
                settings.business_logo_url = business_logo_url
            if default_payment_terms is not None:
                settings.default_payment_terms = default_payment_terms
            if auto_send_email is not None:
                settings.auto_send_email = auto_send_email
        
        try:
            db.commit()
            
            # Add audit logging
            log_event(
                db=db,
                event="invoice.settings_updated",
                user_id=current_user_id(),
                ip_address=request.remote_addr,
                detail={
                    "business_name": settings.business_name,
                    "has_logo": bool(settings.business_logo_url),
                    "auto_send_email": settings.auto_send_email
                }
            )
            
            logger.info(
                "Invoice settings updated | user_id=%d",
                current_user_id()
            )
            
            return jsonify({
                "success": True,
                "message": "Invoice settings updated successfully",
                "settings": settings.to_dict()
            }), 200
            
        except Exception as e:
            db.rollback()
            logger.error(
                "Invoice settings update failed | user_id=%d error=%s",
                current_user_id(), e
            )
            return error("Failed to update invoice settings", "INTERNAL_ERROR", 500)

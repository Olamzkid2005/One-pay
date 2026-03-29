"""
OnePay — Invoice Service
Handles invoice generation, PDF rendering, and invoice operations.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.invoice import Invoice, InvoiceSettings, InvoiceStatus
from models.transaction import Transaction
from models.user import User

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service for invoice operations."""
    
    def generate_invoice_number(self, db: Session) -> str:
        """
        Generate unique sequential invoice number: INV-YYYY-NNNNNN
        
        Handles concurrent invoice creation with retry logic.
        
        Args:
            db: Database session
            
        Returns:
            Invoice number string (e.g., "INV-2026-000001")
            
        Raises:
            RuntimeError: If unable to generate unique number after retries
        """
        current_year = datetime.now(timezone.utc).year
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Get the highest invoice number
                result = db.execute(
                    select(func.max(Invoice.invoice_number))
                ).scalar()
                
                if result:
                    # Extract sequence number from format INV-YYYY-NNNNNN
                    parts = result.split('-')
                    if len(parts) == 3:
                        last_sequence = int(parts[2])
                        next_sequence = last_sequence + 1
                    else:
                        # Fallback if format is unexpected
                        next_sequence = 1
                else:
                    # First invoice ever
                    next_sequence = 1
                
                # Format: INV-YYYY-NNNNNN
                invoice_number = f"INV-{current_year}-{next_sequence:06d}"
                
                logger.debug(
                    "Generated invoice number: %s (attempt %d/%d)",
                    invoice_number, attempt + 1, max_retries
                )
                
                return invoice_number
                
            except Exception as e:
                logger.warning(
                    "Invoice number generation attempt %d failed: %s",
                    attempt + 1, e
                )
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Failed to generate invoice number after {max_retries} attempts"
                    ) from e
        
        raise RuntimeError("Failed to generate invoice number")
    
    def create_invoice(
        self,
        db: Session,
        transaction: Transaction,
        user: User,
        settings: Optional[InvoiceSettings] = None
    ) -> Invoice:
        """
        Create invoice from transaction with merchant settings.
        
        Args:
            db: Database session
            transaction: Transaction to create invoice for
            user: User (merchant) creating the invoice
            settings: Optional invoice settings (fetched if not provided)
            
        Returns:
            Created Invoice object
            
        Raises:
            IntegrityError: If invoice already exists for transaction
        """
        # Fetch settings if not provided
        if settings is None:
            settings = db.query(InvoiceSettings).filter(
                InvoiceSettings.user_id == user.id
            ).first()
        
        # Generate unique invoice number with retry logic
        max_retries = 3
        invoice = None
        
        for attempt in range(max_retries):
            try:
                invoice_number = self.generate_invoice_number(db)
                
                # Create invoice with denormalized data
                invoice = Invoice(
                    invoice_number=invoice_number,
                    transaction_id=transaction.id,
                    user_id=user.id,
                    amount=transaction.amount,
                    currency=transaction.currency,
                    description=transaction.description,
                    customer_email=transaction.customer_email,
                    customer_phone=transaction.customer_phone,
                    # Merchant branding from settings (snapshot at creation)
                    business_name=settings.business_name if settings else None,
                    business_address=settings.business_address if settings else None,
                    business_tax_id=settings.business_tax_id if settings else None,
                    business_logo_url=settings.business_logo_url if settings else None,
                    payment_terms=settings.default_payment_terms if settings else "Payment due upon receipt",
                    status=InvoiceStatus.DRAFT,
                )
                
                db.add(invoice)
                db.flush()
                db.refresh(invoice)
                
                logger.info(
                    "Invoice created | invoice_number=%s tx_ref=%s user_id=%d",
                    invoice.invoice_number, transaction.tx_ref, user.id
                )
                
                return invoice
                
            except IntegrityError as e:
                db.rollback()
                
                # Check if it's a duplicate invoice_number (race condition)
                if "invoice_number" in str(e).lower() or "unique" in str(e).lower():
                    logger.warning(
                        "Invoice number collision on attempt %d/%d, retrying...",
                        attempt + 1, max_retries
                    )
                    if attempt == max_retries - 1:
                        raise RuntimeError(
                            "Failed to create invoice after multiple retries due to number collision"
                        ) from e
                    continue
                else:
                    # Different integrity error (e.g., duplicate transaction_id)
                    raise
        
        raise RuntimeError("Failed to create invoice")
    
    def get_invoice_by_number(
        self,
        db: Session,
        invoice_number: str,
        user_id: int
    ) -> Optional[Invoice]:
        """
        Retrieve invoice with ownership verification.
        
        Args:
            db: Database session
            invoice_number: Invoice number to retrieve
            user_id: User ID for ownership verification
            
        Returns:
            Invoice object if found and owned by user, None otherwise
        """
        invoice = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number,
            Invoice.user_id == user_id
        ).first()
        
        if invoice:
            logger.debug(
                "Invoice retrieved | invoice_number=%s user_id=%d",
                invoice_number, user_id
            )
        else:
            logger.debug(
                "Invoice not found or unauthorized | invoice_number=%s user_id=%d",
                invoice_number, user_id
            )
        
        return invoice
    
    def get_invoice_history(
        self,
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = 'created_desc'
    ) -> tuple[List[Invoice], int]:
        """
        Get paginated invoice history with optional status filter and sorting.
        
        Args:
            db: Database session
            user_id: User ID to filter invoices
            status: Optional status filter (draft, sent, paid, expired, cancelled)
            page: Page number (1-indexed)
            page_size: Number of results per page (max 100)
            sort: Sort order (created_desc, created_asc, amount_desc, amount_asc)
            
        Returns:
            Tuple of (invoices list, total count)
        """
        # Limit page_size to 100
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        # Build query with eager loading of transaction relationship
        from sqlalchemy.orm import joinedload
        query = db.query(Invoice).options(
            joinedload(Invoice.transaction)
        ).filter(Invoice.user_id == user_id)
        
        # Apply status filter if provided
        if status:
            try:
                status_enum = InvoiceStatus(status.lower())
                query = query.filter(Invoice.status == status_enum)
            except ValueError:
                logger.warning("Invalid status filter: %s", status)
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if sort == 'created_asc':
            query = query.order_by(Invoice.created_at.asc())
        elif sort == 'amount_desc':
            query = query.order_by(Invoice.amount.desc())
        elif sort == 'amount_asc':
            query = query.order_by(Invoice.amount.asc())
        else:  # Default: created_desc
            query = query.order_by(Invoice.created_at.desc())
        
        # Get paginated results
        invoices = query.offset(offset).limit(page_size).all()
        
        logger.debug(
            "Invoice history retrieved | user_id=%d status=%s page=%d sort=%s count=%d total=%d",
            user_id, status, page, sort, len(invoices), total_count
        )
        
        return invoices, total_count
    
    def sync_invoice_status(
        self,
        db: Session,
        invoice: Invoice,
        transaction: Transaction
    ) -> None:
        """
        Update invoice status based on transaction status.
        
        Args:
            db: Database session
            invoice: Invoice to update
            transaction: Associated transaction
        """
        from models.transaction import TransactionStatus
        
        old_status = invoice.status
        
        # Update status based on transaction status
        if transaction.status == TransactionStatus.VERIFIED:
            invoice.status = InvoiceStatus.PAID
            if not invoice.paid_at:
                invoice.paid_at = datetime.now(timezone.utc)
        elif transaction.status == TransactionStatus.EXPIRED:
            invoice.status = InvoiceStatus.EXPIRED
        
        # Only log if status changed
        if invoice.status != old_status:
            db.flush()
            logger.info(
                "Invoice status synced | invoice_number=%s old_status=%s new_status=%s",
                invoice.invoice_number, old_status.value, invoice.status.value
            )
    
    def render_invoice_html(
        self,
        invoice: Invoice,
        transaction: Transaction,
        payment_url: Optional[str] = None
    ) -> str:
        """
        Render invoice to HTML using Jinja2 template.
        
        Args:
            invoice: Invoice object to render
            transaction: Associated transaction
            payment_url: Optional payment link URL
            
        Returns:
            Rendered HTML string
            
        Raises:
            Exception: If template rendering fails
        """
        from flask import render_template
        import base64
        import requests
        from io import BytesIO
        
        try:
            # Prepare template context
            context = {
                'invoice': invoice,
                'transaction': transaction,
                'payment_url': payment_url,
                'current_date': datetime.now(timezone.utc),
            }
            
            # Embed QR code from transaction if available
            if transaction.qr_code_payment_url:
                context['qr_code_data_uri'] = transaction.qr_code_payment_url
            
            # Embed logo as base64 data URI if URL provided
            if invoice.business_logo_url:
                try:
                    # Fetch logo with timeout
                    response = requests.get(
                        invoice.business_logo_url,
                        timeout=5,
                        headers={'User-Agent': 'OnePay-Invoice-Generator/1.0'}
                    )
                    response.raise_for_status()
                    
                    # Validate content type
                    content_type = response.headers.get('content-type', '').lower()
                    if any(img_type in content_type for img_type in ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']):
                        # Convert to base64 data URI
                        logo_base64 = base64.b64encode(response.content).decode()
                        context['logo_data_uri'] = f"data:{content_type};base64,{logo_base64}"
                        logger.debug("Logo embedded successfully for invoice %s", invoice.invoice_number)
                    else:
                        logger.warning(
                            "Invalid logo content type: %s for invoice %s",
                            content_type, invoice.invoice_number
                        )
                except requests.RequestException as e:
                    logger.warning(
                        "Failed to fetch logo for invoice %s: %s",
                        invoice.invoice_number, e
                    )
                    # Continue without logo (graceful degradation)
                except Exception as e:
                    logger.warning(
                        "Unexpected error fetching logo for invoice %s: %s",
                        invoice.invoice_number, e
                    )
                    # Continue without logo (graceful degradation)
            
            # Render template
            html = render_template('invoice.html', **context)
            
            logger.debug("Invoice HTML rendered successfully | invoice_number=%s", invoice.invoice_number)
            return html
            
        except Exception as e:
            logger.error(
                "Failed to render invoice HTML | invoice_number=%s error=%s",
                invoice.invoice_number, e
            )
            raise
    
    def generate_invoice_pdf(
        self,
        invoice: Invoice,
        transaction: Transaction,
        payment_url: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF from invoice HTML using xhtml2pdf (Windows-compatible).
        
        Args:
            invoice: Invoice object to generate PDF for
            transaction: Associated transaction
            payment_url: Optional payment link URL
            
        Returns:
            PDF binary data
            
        Raises:
            Exception: If PDF generation fails
        """
        from xhtml2pdf import pisa
        from io import BytesIO
        
        try:
            # Render HTML
            html_content = self.render_invoice_html(invoice, transaction, payment_url)
            
            # Create PDF buffer
            pdf_buffer = BytesIO()
            
            # Generate PDF from HTML
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_buffer,
                encoding='utf-8'
            )
            
            # Check for errors
            if pisa_status.err:
                raise Exception(f"PDF generation error: {pisa_status.err} errors occurred")
            
            # Get PDF bytes
            pdf_bytes = pdf_buffer.getvalue()
            pdf_buffer.close()
            
            # Check PDF size (warn if > 5MB)
            pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
            if pdf_size_mb > 5:
                logger.warning(
                    "Large PDF generated | invoice_number=%s size=%.2fMB",
                    invoice.invoice_number, pdf_size_mb
                )
            
            logger.info(
                "PDF generated successfully | invoice_number=%s size=%.2fKB",
                invoice.invoice_number, len(pdf_bytes) / 1024
            )
            
            return pdf_bytes
                
        except Exception as e:
            logger.error(
                "PDF generation failed | invoice_number=%s error=%s",
                invoice.invoice_number, e
            )
            raise


# Global instance
invoice_service = InvoiceService()

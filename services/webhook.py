"""
OnePay — Webhook delivery service.

Delivers payment confirmation events to merchant-configured URLs.
Signs each payload with HMAC-SHA256 so merchants can verify authenticity.

Payload example:
    {
        "event":   "payment.confirmed",
        "tx_ref":  "ONEPAY-...",
        "amount":  "1000.00",
        "currency":"NGN",
        "status":  "verified",
        "verified_at": "2024-01-01T12:00:00+00:00"
    }

Signature header:
    X-OnePay-Signature: sha256=<hex_digest>

Merchants verify with:
    expected = hmac.new(secret, payload_bytes, sha256).hexdigest()
    hmac.compare_digest(expected, header.removeprefix("sha256="))
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import requests

from config import Config

logger = logging.getLogger(__name__)


def _sign_payload(payload_bytes: bytes) -> str:
    """Return 'sha256=<hex>' signature over the raw payload bytes.
    Uses WEBHOOK_SECRET if set, falls back to HMAC_SECRET.
    """
    secret = Config.WEBHOOK_SECRET or Config.HMAC_SECRET
    sig = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


def _send_with_retries(url: str, payload_bytes: bytes, headers: dict, tx_ref: str) -> bool:
    """
    POST payload to url with exponential backoff retries.
    Returns True on success (HTTP < 300), False after all attempts fail.
    
    Security: Validates URL and DNS on EVERY attempt to prevent DNS rebinding attacks.
    """
    from services.security import validate_webhook_url
    from urllib.parse import urlparse
    import socket
    import ipaddress
    
    # Initial URL validation
    if not validate_webhook_url(url):
        logger.error("Webhook URL failed security validation | tx_ref=%s url=%s", tx_ref, url)
        return False
    
    hostname = urlparse(url).hostname
    if not hostname:
        logger.error("Webhook URL has no hostname | tx_ref=%s url=%s", tx_ref, url)
        return False
    
    last_error = None
    for attempt in range(1, Config.WEBHOOK_MAX_RETRIES + 1):
        try:
            # DNS rebinding protection: resolve and validate DNS on EVERY attempt
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
                logger.error("Webhook DNS rebinding detected | tx_ref=%s url=%s ip=%s attempt=%d", 
                            tx_ref, url, ip, attempt)
                last_error = f"DNS rebinding detected: {ip}"
                if attempt < Config.WEBHOOK_MAX_RETRIES:
                    time.sleep(2 ** attempt)  # Longer backoff after security violation
                continue
            
            logger.debug("Webhook DNS validated | tx_ref=%s hostname=%s ip=%s attempt=%d", 
                        tx_ref, hostname, ip, attempt)
            
            # Proceed with request
            resp = requests.post(
                url, 
                data=payload_bytes, 
                headers=headers,
                timeout=Config.WEBHOOK_TIMEOUT_SECS,
                allow_redirects=False,  # Prevent redirect-based SSRF
                stream=True  # Stream response to check size
            )
            
            # Check response size before reading
            content_length = resp.headers.get('Content-Length')
            if content_length and int(content_length) > 1024 * 1024:  # 1MB limit
                logger.warning("Webhook response too large | tx_ref=%s size=%s", tx_ref, content_length)
                resp.close()
                last_error = "Response too large"
                if attempt < Config.WEBHOOK_MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))
                continue
            
            if resp.status_code < 300:
                logger.info("Webhook delivered | tx_ref=%s url=%s status=%d attempt=%d",
                            tx_ref, url, resp.status_code, attempt)
                resp.close()
                return True
            last_error = f"HTTP {resp.status_code}"
            logger.warning("Webhook attempt %d failed | tx_ref=%s status=%d",
                           attempt, tx_ref, resp.status_code)
            resp.close()
        except socket.gaierror as e:
            last_error = f"DNS resolution failed: {e}"
            logger.warning("Webhook DNS error attempt %d | tx_ref=%s error=%s", attempt, tx_ref, e)
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.warning("Webhook attempt %d error | tx_ref=%s error=%s", attempt, tx_ref, e)

        if attempt < Config.WEBHOOK_MAX_RETRIES:
            # Exponential backoff with jitter: 2^attempt + random(0, 1)
            import random
            delay = (2 ** attempt) + random.random()
            time.sleep(delay)

    logger.error("Webhook delivery failed after %d attempts | tx_ref=%s last_error=%s",
                 Config.WEBHOOK_MAX_RETRIES, tx_ref, last_error)
    return False


def deliver_webhook_from_dict(wh_data: dict) -> bool:
    """
    Deliver a webhook from a plain dict snapshot.
    Safe to call from a daemon thread after the DB session has closed.

    wh_data keys: webhook_url, tx_ref, amount, currency, description,
                  status, verified_at
    """
    url = wh_data.get("webhook_url")
    if not url:
        return False

    payload = {
        "event":       "payment.confirmed",
        "tx_ref":      wh_data.get("tx_ref"),
        "amount":      wh_data.get("amount"),
        "currency":    wh_data.get("currency"),
        "description": wh_data.get("description"),
        "status":      wh_data.get("status"),
        "verified_at": wh_data.get("verified_at"),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type":       "application/json",
        "X-OnePay-Signature": _sign_payload(payload_bytes),
        "User-Agent":         "OnePay-Webhook/1.0",
    }
    return _send_with_retries(url, payload_bytes, headers, wh_data.get("tx_ref", "?"))


def deliver_webhook(db, transaction) -> bool:
    """
    Deliver a webhook for a confirmed transaction (ORM object variant).
    Updates transaction.webhook_* fields in place — caller must commit.
    Always increments webhook_attempts.
    """
    from core.audit import log_event
    
    url = transaction.webhook_url
    if not url:
        return False

    # Increment attempts
    transaction.webhook_attempts = (transaction.webhook_attempts or 0) + 1

    payload = {
        "event":       "payment.confirmed",
        "tx_ref":      transaction.tx_ref,
        "amount":      str(transaction.amount),
        "currency":    transaction.currency,
        "description": transaction.description,
        "status":      transaction.effective_status_value(),
        "verified_at": transaction.verified_at_utc_iso(),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type":       "application/json",
        "X-OnePay-Signature": _sign_payload(payload_bytes),
        "User-Agent":         "OnePay-Webhook/1.0",
    }

    try:
        success = _send_with_retries(url, payload_bytes, headers, transaction.tx_ref)
        if success:
            transaction.webhook_delivered    = True
            transaction.webhook_delivered_at = datetime.now(timezone.utc)
            transaction.webhook_last_error   = None
            log_event(db, "webhook.delivered", user_id=transaction.user_id, tx_ref=transaction.tx_ref,
                      detail={"url": url, "attempts": transaction.webhook_attempts})
        else:
            transaction.webhook_delivered = False
            transaction.webhook_last_error = "Delivery failed after all retries"
            log_event(db, "webhook.failed", user_id=transaction.user_id, tx_ref=transaction.tx_ref,
                      detail={"url": url, "attempts": transaction.webhook_attempts, "error": "max_retries"})
        return success
    except Exception as e:
        transaction.webhook_delivered = False
        transaction.webhook_last_error = str(e)[:500]
        log_event(db, "webhook.failed", user_id=transaction.user_id, tx_ref=transaction.tx_ref,
                  detail={"url": url, "attempts": transaction.webhook_attempts, "error": str(e)[:200]})
        logger.error("Webhook delivery exception | tx_ref=%s error=%s", transaction.tx_ref, e)
        return False


def retry_failed_webhooks(db):
    """
    Retry webhook delivery for all failed webhooks that haven't exceeded max attempts.
    Called periodically by background thread.
    Commits after each attempt to preserve progress across crashes.
    """
    from models.transaction import Transaction
    
    # Find all transactions with pending webhooks
    pending = db.query(Transaction).filter(
        Transaction.webhook_url.isnot(None),
        Transaction.webhook_delivered == False,
        Transaction.webhook_attempts < Config.WEBHOOK_MAX_RETRIES,
        Transaction.transfer_confirmed == True,
    ).all()
    
    if not pending:
        return
    
    logger.info("Retrying %d failed webhooks", len(pending))
    
    for transaction in pending:
        try:
            deliver_webhook(db, transaction)
            db.commit()
        except Exception as e:
            logger.error("Webhook retry error | tx_ref=%s error=%s", transaction.tx_ref, e)
            db.rollback()


def sync_invoice_on_transaction_update(db, transaction):
    """
    Synchronize invoice status when transaction status changes.
    Called from webhook handler after transaction update.
    
    Updates invoice status based on transaction status:
    - verified → paid (with paid_at timestamp)
    - expired → expired
    
    Args:
        db: Database session
        transaction: Transaction object with updated status
    """
    from models.invoice import Invoice, InvoiceStatus
    from models.transaction import TransactionStatus
    from core.audit import log_event
    
    # Query invoice by transaction_id
    invoice = db.query(Invoice).filter(
        Invoice.transaction_id == transaction.id
    ).first()
    
    if not invoice:
        # No invoice for this transaction - this is normal
        return
    
    old_status = invoice.status
    
    # Update invoice status based on transaction status
    if transaction.status == TransactionStatus.VERIFIED:
        invoice.status = InvoiceStatus.PAID
        if not invoice.paid_at:
            invoice.paid_at = datetime.now(timezone.utc)
    elif transaction.status == TransactionStatus.EXPIRED:
        invoice.status = InvoiceStatus.EXPIRED
    
    # Only log if status changed
    if invoice.status != old_status:
        db.flush()
        
        # Add audit logging
        log_event(
            db,
            "invoice.status_synced",
            user_id=transaction.user_id,
            tx_ref=transaction.tx_ref,
            detail={
                "invoice_number": invoice.invoice_number,
                "old_status": old_status.value,
                "new_status": invoice.status.value,
            }
        )
        
        logger.info(
            "Invoice status synced | invoice_number=%s tx_ref=%s old_status=%s new_status=%s",
            invoice.invoice_number, transaction.tx_ref, old_status.value, invoice.status.value
        )



def send_payment_notification_emails(db, transaction, user):
    """
    Send payment notification emails after payment confirmation.
    
    Orchestrates email sending for both merchant and customer:
    1. Check if invoice exists, create if not
    2. Generate invoice PDF
    3. Send merchant notification email (always)
    4. Send customer invoice email (if auto_send_email enabled and customer_email exists)
    5. Update invoice status to paid
    
    Args:
        db: Database session
        transaction: Transaction object (verified payment)
        user: User object (merchant)
        
    Side Effects:
        - Creates invoice if not exists
        - Sends merchant notification email
        - Sends customer invoice email (conditionally)
        - Updates invoice status to paid
        - Logs all operations
        
    Error Handling:
        - All operations wrapped in try-except to prevent blocking payment
        - Errors logged but not raised
        - Graceful degradation on PDF generation failure
    """
    from models.invoice import Invoice, InvoiceSettings
    from services.invoice import invoice_service
    from services.email import send_merchant_notification_email, send_invoice_email
    from core.audit import log_event
    
    try:
        # Step 1: Check if invoice exists for this transaction
        invoice = db.query(Invoice).filter(
            Invoice.transaction_id == transaction.id
        ).first()
        
        # Step 2: Create invoice if not exists
        if not invoice:
            try:
                invoice = invoice_service.create_invoice(
                    db=db,
                    transaction=transaction,
                    user=user,
                    settings=None  # Will be fetched inside create_invoice
                )
                db.commit()
                
                log_event(
                    db,
                    "invoice.auto_created",
                    user_id=user.id,
                    tx_ref=transaction.tx_ref,
                    detail={"invoice_number": invoice.invoice_number}
                )
                
                logger.info(
                    "Invoice auto-created for payment | invoice_number=%s tx_ref=%s",
                    invoice.invoice_number, transaction.tx_ref
                )
            except Exception as e:
                logger.error(
                    "Failed to create invoice for payment | tx_ref=%s error=%s",
                    transaction.tx_ref, e
                )
                db.rollback()
                # Continue without invoice - merchant still gets notification
                invoice = None
        
        # Step 3: Generate invoice PDF (graceful degradation on failure)
        pdf_bytes = None
        if invoice:
            try:
                # Generate payment URL for invoice (use transaction's existing payment URL if available)
                payment_url = None
                if hasattr(transaction, 'payment_url') and transaction.payment_url:
                    payment_url = transaction.payment_url
                
                pdf_bytes = invoice_service.generate_invoice_pdf(
                    invoice=invoice,
                    transaction=transaction,
                    payment_url=payment_url
                )
                
                logger.info(
                    "Invoice PDF generated | invoice_number=%s size=%d bytes",
                    invoice.invoice_number, len(pdf_bytes)
                )
            except Exception as e:
                logger.error(
                    "Failed to generate invoice PDF | invoice_number=%s error=%s",
                    invoice.invoice_number if invoice else "N/A", e
                )
                # Continue without PDF - emails will be sent without attachment
                pdf_bytes = None
        
        # Step 4: Send merchant notification email (always)
        try:
            merchant_email_sent = send_merchant_notification_email(
                to_email=user.email,
                transaction=transaction,
                invoice=invoice,
                pdf_bytes=pdf_bytes
            )
            
            if merchant_email_sent:
                log_event(
                    db,
                    "email.merchant_notification_sent",
                    user_id=user.id,
                    tx_ref=transaction.tx_ref,
                    detail={
                        "invoice_number": invoice.invoice_number if invoice else None,
                        "merchant_email": user.email
                    }
                )
                logger.info(
                    "Merchant notification email sent | tx_ref=%s merchant_email=%s",
                    transaction.tx_ref, user.email
                )
            else:
                logger.warning(
                    "Merchant notification email failed | tx_ref=%s merchant_email=%s",
                    transaction.tx_ref, user.email
                )
        except Exception as e:
            logger.error(
                "Exception sending merchant notification | tx_ref=%s error=%s",
                transaction.tx_ref, e
            )
            # Continue - don't block payment confirmation
        
        # Step 5: Send customer invoice email (if auto_send_email enabled and customer_email exists)
        if invoice and transaction.customer_email:
            try:
                # Check auto_send_email setting
                settings = db.query(InvoiceSettings).filter(
                    InvoiceSettings.user_id == user.id
                ).first()
                
                if settings and settings.auto_send_email:
                    # Generate payment URL (use transaction's existing payment URL if available)
                    payment_url = None
                    if hasattr(transaction, 'payment_url') and transaction.payment_url:
                        payment_url = transaction.payment_url
                    
                    # Generate QR code data URI if available
                    qr_code_data_uri = None
                    if transaction.qr_code_payment_url:
                        qr_code_data_uri = transaction.qr_code_payment_url
                    
                    customer_email_sent = send_invoice_email(
                        to_email=transaction.customer_email,
                        invoice=invoice,
                        pdf_bytes=pdf_bytes,
                        payment_url=payment_url,
                        qr_code_data_uri=qr_code_data_uri,
                        merchant_email=user.email  # BCC merchant
                    )
                    
                    if customer_email_sent:
                        log_event(
                            db,
                            "email.customer_invoice_sent",
                            user_id=user.id,
                            tx_ref=transaction.tx_ref,
                            detail={
                                "invoice_number": invoice.invoice_number,
                                "customer_email": transaction.customer_email
                            }
                        )
                        logger.info(
                            "Customer invoice email sent | tx_ref=%s customer_email=%s",
                            transaction.tx_ref, transaction.customer_email
                        )
                    else:
                        logger.warning(
                            "Customer invoice email failed | tx_ref=%s customer_email=%s",
                            transaction.tx_ref, transaction.customer_email
                        )
                else:
                    logger.debug(
                        "Customer email not sent (auto_send_email disabled) | tx_ref=%s",
                        transaction.tx_ref
                    )
            except Exception as e:
                logger.error(
                    "Exception sending customer invoice | tx_ref=%s error=%s",
                    transaction.tx_ref, e
                )
                # Continue - don't block payment confirmation
        
        # Step 6: Update invoice status to paid
        if invoice:
            try:
                from models.invoice import InvoiceStatus
                invoice.status = InvoiceStatus.PAID
                if not invoice.paid_at:
                    invoice.paid_at = datetime.now(timezone.utc)
                db.commit()
                
                logger.info(
                    "Invoice status updated to paid | invoice_number=%s",
                    invoice.invoice_number
                )
            except Exception as e:
                logger.error(
                    "Failed to update invoice status | invoice_number=%s error=%s",
                    invoice.invoice_number if invoice else "N/A", e
                )
                db.rollback()
                # Continue - don't block payment confirmation
    
    except Exception as e:
        logger.error(
            "Unexpected error in send_payment_notification_emails | tx_ref=%s error=%s",
            transaction.tx_ref, e
        )
        # Don't raise - payment confirmation should not be blocked by email failures

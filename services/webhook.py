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
from typing import Optional

import requests

from config import Config
from services.cache import cache_delete

logger = logging.getLogger(__name__)


def _get_correlation_id() -> Optional[str]:
    """Return the current request's correlation ID, or None outside request context."""
    try:
        from flask import g

        return g.get("correlation_id")
    except RuntimeError:
        return None


def verify_inbound_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature for inbound webhooks.

    Uses constant-time comparison to prevent timing attacks.
    Extracts signature from request headers and compares against
    computed HMAC using INBOUND_WEBHOOK_SECRET.

    Args:
        payload: Raw request body as bytes
        signature: Signature header value (format: "sha256=<hex>")

    Returns:
        bool: True if signature is valid, False otherwise

    **Validates: Requirements 1.2**
    """
    if not signature or not signature.startswith("sha256="):
        logger.warning("Invalid signature format | signature=%s", signature[:20] if signature else "None")
        return False

    # Extract hex digest from "sha256=<hex>" format
    received_sig = signature[7:]

    # Compute HMAC-SHA256 using configured secret
    secret = Config.INBOUND_WEBHOOK_SECRET
    if not secret:
        logger.error("INBOUND_WEBHOOK_SECRET not configured")
        return False

    computed_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(received_sig, computed_sig)

    if not is_valid:
        logger.warning("Signature verification failed | received=%s computed=%s", received_sig[:8], computed_sig[:8])

    return is_valid


def check_webhook_idempotency(db, webhook_id: str, source: str) -> bool:
    """
    Check if webhook has already been processed.

    Args:
        db: Database session
        webhook_id: Unique webhook identifier
        source: Webhook source (korapay, voicepay, etc.)

    Returns:
        bool: True if webhook already processed, False otherwise

    **Validates: Requirements 2.1, 2.2**
    """
    from models.webhook_idempotency import WebhookIdempotency

    existing = (
        db.query(WebhookIdempotency)
        .filter(WebhookIdempotency.id == webhook_id)
        .filter(WebhookIdempotency.source == source)
        .first()
    )

    return existing is not None


def store_webhook_idempotency(db, webhook_id: str, source: str, tx_ref: str = None):
    """
    Store webhook identifier to prevent duplicate processing.

    Args:
        db: Database session
        webhook_id: Unique webhook identifier
        source: Webhook source (korapay, voicepay, etc.)
        tx_ref: Associated transaction reference (optional)

    **Validates: Requirements 2.3, 2.4**
    """
    from models.webhook_idempotency import WebhookIdempotency

    idempotency_record = WebhookIdempotency(id=webhook_id, source=source, tx_ref=tx_ref)

    db.add(idempotency_record)
    db.flush()

    logger.debug("Webhook idempotency stored | webhook_id=%s source=%s tx_ref=%s", webhook_id, source, tx_ref)


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


def _blacklist_webhook(url: str, reason: str):
    """Add webhook URL to blacklist."""
    try:
        from database import get_db
        from models.webhook_blacklist import WebhookBlacklist

        with get_db() as db:
            existing = db.query(WebhookBlacklist).filter(WebhookBlacklist.url == url).first()

            if existing:
                existing.attempts += 1
                existing.reason = reason
            else:
                blacklist_entry = WebhookBlacklist(url=url, reason=reason)
                db.add(blacklist_entry)

            logger.warning("Webhook blacklisted | url=%s reason=%s", url, reason)
    except Exception as e:
        logger.error("Failed to blacklist webhook | url=%s error=%s", url, e)


def _resolve_and_validate_ip(url: str, hostname: str, tx_ref: str, attempt: int) -> Optional[str]:
    """
    Resolve hostname to IP and validate it's not private/internal.
    Returns resolved IP string, or None if blocked (and blacklists the URL).
    """
    from core.network_security import is_restricted_ip, resolve_hostname_with_ttl

    # Use the centralized network security module for DNS resolution with TTL
    ip, err = resolve_hostname_with_ttl(hostname, url, require_safe_ttl=False)
    if err or not ip:
        logger.warning("Webhook DNS resolution failed | tx_ref=%s url=%s error=%s", tx_ref, url, err)
        _blacklist_webhook(url, f"DNS resolution failed: {err}")
        return None

    # Check if IP is restricted (private, AWS metadata, etc.)
    restriction = is_restricted_ip(ip)
    if restriction:
        logger.error("Webhook IP blocked | tx_ref=%s url=%s ip=%s reason=%s", tx_ref, url, ip, restriction)
        _blacklist_webhook(url, f"Restricted IP: {restriction}")
        return None

    logger.debug("Webhook DNS validated | tx_ref=%s hostname=%s ip=%s attempt=%d", tx_ref, hostname, ip, attempt)
    return ip


def _post_to_ip(url: str, ip: str, payload_bytes: bytes, headers: dict) -> object:
    """POST payload to the resolved IP address with Host header."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    ip_url = urlunparse(
        (
            parsed.scheme,
            ip if not parsed.port else f"{ip}:{parsed.port}",
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    request_headers = headers.copy()
    request_headers["Host"] = parsed.hostname
    return requests.post(
        ip_url,
        data=payload_bytes,
        headers=request_headers,
        timeout=Config.WEBHOOK_TIMEOUT_SECS,
        allow_redirects=False,
        stream=True,
    )


def _check_webhook_response(resp, url: str, tx_ref: str, attempt: int) -> tuple[bool, bool, str]:
    """
    Inspect webhook HTTP response.
    Returns (success, should_abort, last_error).
    - success=True: delivered
    - should_abort=True: blacklisted, stop retrying
    - last_error: error string if failed
    """
    if 300 <= resp.status_code < 400:
        location = resp.headers.get("Location", "")
        if location:
            logger.warning("Webhook redirect detected | tx_ref=%s url=%s location=%s", tx_ref, url, location)
            _blacklist_webhook(url, f"Redirect to {location}")
            resp.close()
            return False, True, "redirect"
    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > 1024 * 1024:
        logger.warning("Webhook response too large | tx_ref=%s size=%s", tx_ref, content_length)
        resp.close()
        return False, False, "Response too large"
    if resp.status_code < 300:
        logger.info("Webhook delivered | tx_ref=%s url=%s status=%d attempt=%d", tx_ref, url, resp.status_code, attempt)
        resp.close()
        return True, False, ""
    last_error = f"HTTP {resp.status_code}"
    logger.warning("Webhook attempt %d failed | tx_ref=%s status=%d", attempt, tx_ref, resp.status_code)
    resp.close()
    return False, False, last_error


def _send_with_retries(url: str, payload_bytes: bytes, headers: dict, tx_ref: str) -> bool:
    """
    POST payload to url with exponential backoff retries.
    Returns True on success (HTTP < 300), False after all attempts fail.
    """
    import socket
    from urllib.parse import urlparse

    from database import get_db
    from models.webhook_blacklist import WebhookBlacklist
    from services.security import validate_webhook_url

    try:
        with get_db() as db:
            blacklisted = db.query(WebhookBlacklist).filter(WebhookBlacklist.url == url).first()
            if blacklisted:
                logger.error("Webhook URL is blacklisted | tx_ref=%s url=%s reason=%s", tx_ref, url, blacklisted.reason)
                return False
    except Exception as e:
        logger.error("Blacklist check failed: %s", e)

    if not validate_webhook_url(url):
        _blacklist_webhook(url, "Failed URL validation")
        logger.error("Webhook URL failed security validation | tx_ref=%s url=%s", tx_ref, url)
        return False

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        _blacklist_webhook(url, "No hostname")
        logger.error("Webhook URL has no hostname | tx_ref=%s url=%s", tx_ref, url)
        return False

    last_error = None
    for attempt in range(1, Config.WEBHOOK_MAX_RETRIES + 1):
        try:
            ip = _resolve_and_validate_ip(url, hostname, tx_ref, attempt)
            if ip is None:
                return False

            resp = _post_to_ip(url, ip, payload_bytes, headers)
            success, abort, last_error = _check_webhook_response(resp, url, tx_ref, attempt)
            if success:
                return True
            if abort:
                return False
            if last_error == "Response too large" and attempt < Config.WEBHOOK_MAX_RETRIES:
                time.sleep(2 ** (attempt - 1))
            continue

        except socket.gaierror as e:
            last_error = f"DNS resolution failed: {e}"
            logger.warning("Webhook DNS error attempt %d | tx_ref=%s error=%s", attempt, tx_ref, e)
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.warning("Webhook attempt %d error | tx_ref=%s error=%s", attempt, tx_ref, e)

        if attempt < Config.WEBHOOK_MAX_RETRIES:
            import secrets

            delay = (2**attempt) + (secrets.randbelow(1000) / 1000)
            time.sleep(delay)

    logger.error(
        "Webhook delivery failed after %d attempts | tx_ref=%s last_error=%s",
        Config.WEBHOOK_MAX_RETRIES,
        tx_ref,
        last_error,
    )
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
        "event": "payment.confirmed",
        "tx_ref": wh_data.get("tx_ref"),
        "amount": wh_data.get("amount"),
        "currency": wh_data.get("currency"),
        "description": wh_data.get("description"),
        "status": wh_data.get("status"),
        "verified_at": wh_data.get("verified_at"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-OnePay-Signature": _sign_payload(payload_bytes),
        "User-Agent": "OnePay-Webhook/1.0",
    }
    correlation_id = _get_correlation_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    return _send_with_retries(url, payload_bytes, headers, wh_data.get("tx_ref", "?"))


def queue_webhook_delivery(wh_data: dict) -> bool:
    """
    Queue webhook delivery via task queue with fallback to thread-based delivery.

    Uses Huey task queue when available (production/staging).
    Falls back to thread-based delivery in development for simplicity.

    Args:
        wh_data: Dict with webhook_url, tx_ref, amount, currency, status, etc.

    Returns:
        bool: True if queued/dispatched successfully, False otherwise

    **Validates: Requirements 10.2, 10.5**
    """
    # Check if Huey is available and not in immediate mode
    try:
        from services.task_queue import deliver_webhook_task, huey

        # In immediate mode (debug), just call directly for testing
        if huey.immediate:
            logger.debug("Huey in immediate mode, delivering webhook directly")
            result = deliver_webhook_task(wh_data)
            return result.result if hasattr(result, "result") else result

        # Queue the task for async processing
        result = deliver_webhook_task(wh_data)
        logger.info("Webhook delivery queued | tx_ref=%s task_id=%s", wh_data.get("tx_ref"), result.id)
        return True

    except ImportError:
        # Huey not configured - fall back to thread-based delivery
        logger.warning("Huey not available, using thread-based webhook delivery")
        try:
            import threading

            thread = threading.Thread(target=deliver_webhook_from_dict, args=(wh_data,))
            thread.daemon = True
            thread.start()
            logger.info("Webhook delivery dispatched via thread | tx_ref=%s", wh_data.get("tx_ref"))
            return True
        except Exception as e:
            logger.error("Failed to dispatch webhook via thread: %s", e)
            return False


def _update_webhook_transaction(db, transaction, success: bool, url: str, error: str = None) -> None:
    """Update transaction webhook fields and log audit event."""
    from core.audit import log_event

    if success:
        transaction.webhook_delivered = True
        transaction.webhook_delivered_at = datetime.now(timezone.utc)
        transaction.webhook_last_error = None
        cache_delete(f"payment_summary:{transaction.user_id}")
        log_event(
            db,
            "webhook.delivered",
            user_id=transaction.user_id,
            tx_ref=transaction.tx_ref,
            detail={"url": url, "attempts": transaction.webhook_attempts},
        )
    else:
        transaction.webhook_delivered = False
        transaction.webhook_last_error = error or "Delivery failed after all retries"
        log_event(
            db,
            "webhook.failed",
            user_id=transaction.user_id,
            tx_ref=transaction.tx_ref,
            detail={"url": url, "attempts": transaction.webhook_attempts, "error": error or "max_retries"},
        )


def deliver_webhook(db, transaction) -> bool:
    """Deliver a webhook for a confirmed transaction. Updates transaction fields in place."""
    url = transaction.webhook_url
    if not url:
        return False

    transaction.webhook_attempts = (transaction.webhook_attempts or 0) + 1

    payload = {
        "event": "payment.confirmed",
        "tx_ref": transaction.tx_ref,
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "description": transaction.description,
        "status": transaction.effective_status_value(),
        "verified_at": transaction.verified_at_utc_iso(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-OnePay-Signature": _sign_payload(payload_bytes),
        "User-Agent": "OnePay-Webhook/1.0",
    }
    correlation_id = _get_correlation_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    try:
        success = _send_with_retries(url, payload_bytes, headers, transaction.tx_ref)
        _update_webhook_transaction(db, transaction, success, url)
        return success
    except Exception as e:
        transaction.webhook_delivered = False
        transaction.webhook_last_error = str(e)[:500]
        _update_webhook_transaction(db, transaction, False, url, str(e)[:200])
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
    pending = (
        db.query(Transaction)
        .filter(
            Transaction.webhook_url.isnot(None),
            Transaction.webhook_delivered == False,
            Transaction.webhook_attempts < Config.WEBHOOK_MAX_RETRIES,
            Transaction.transfer_confirmed == True,
        )
        .all()
    )

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
    from core.audit import log_event
    from models.invoice import Invoice, InvoiceStatus
    from models.transaction import TransactionStatus

    # Query invoice by transaction_id
    invoice = db.query(Invoice).filter(Invoice.transaction_id == transaction.id).first()

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

        # Invalidate payment summary cache on invoice/transaction status update (Requirement 11.5)
        cache_delete(f"payment_summary:{transaction.user_id}")

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
            },
        )

        logger.info(
            "Invoice status synced | invoice_number=%s tx_ref=%s old_status=%s new_status=%s",
            invoice.invoice_number,
            transaction.tx_ref,
            old_status.value,
            invoice.status.value,
        )


def _ensure_invoice_exists(db, transaction, user) -> object:
    """Get or create invoice for transaction. Returns invoice or None."""
    from core.audit import log_event
    from models.invoice import Invoice
    from services.invoice import invoice_service

    invoice = db.query(Invoice).filter(Invoice.transaction_id == transaction.id).first()
    if invoice:
        return invoice
    try:
        invoice = invoice_service.create_invoice(db=db, transaction=transaction, user=user, settings=None)
        db.flush()
        log_event(
            db,
            "invoice.auto_created",
            user_id=user.id,
            tx_ref=transaction.tx_ref,
            detail={"invoice_number": invoice.invoice_number},
        )
        logger.info(
            "Invoice auto-created for payment | invoice_number=%s tx_ref=%s", invoice.invoice_number, transaction.tx_ref
        )
        return invoice
    except Exception as e:
        logger.error("Failed to create invoice for payment | tx_ref=%s error=%s", transaction.tx_ref, e)
        db.rollback()
        return None


def _generate_pdf_for_notification(invoice, transaction) -> Optional[bytes]:
    """Generate PDF for invoice notification. Returns bytes or None on failure."""
    from services.invoice import invoice_service

    if not invoice:
        return None
    try:
        payment_url = getattr(transaction, "qr_code_payment_url", None)
        pdf_bytes = invoice_service.generate_invoice_pdf(
            invoice=invoice, transaction=transaction, payment_url=payment_url
        )
        logger.info("Invoice PDF generated | invoice_number=%s size=%d bytes", invoice.invoice_number, len(pdf_bytes))
        return pdf_bytes
    except Exception as e:
        logger.error(
            "Failed to generate invoice PDF | invoice_number=%s error=%s",
            invoice.invoice_number if invoice else "N/A",
            e,
        )
        return None


def _send_merchant_email(db, transaction, user, invoice, pdf_bytes) -> None:
    """Send merchant notification email (best-effort)."""
    from core.audit import log_event
    from services.email import send_merchant_notification_email

    try:
        sent = send_merchant_notification_email(
            to_email=user.email, transaction=transaction, invoice=invoice, pdf_bytes=pdf_bytes
        )
        if sent:
            log_event(
                db,
                "email.merchant_notification_sent",
                user_id=user.id,
                tx_ref=transaction.tx_ref,
                detail={"invoice_number": invoice.invoice_number if invoice else None, "merchant_email": user.email},
            )
            logger.info(
                "Merchant notification email sent | tx_ref=%s merchant_email=%s", transaction.tx_ref, user.email
            )
        else:
            logger.warning(
                "Merchant notification email failed | tx_ref=%s merchant_email=%s", transaction.tx_ref, user.email
            )
    except Exception as e:
        logger.error("Exception sending merchant notification | tx_ref=%s error=%s", transaction.tx_ref, e)


def _send_customer_email(db, transaction, user, invoice, pdf_bytes) -> None:
    """Send customer invoice email if auto_send_email is enabled (best-effort)."""
    from core.audit import log_event
    from models.invoice import InvoiceSettings
    from services.email import send_invoice_email

    if not (invoice and transaction.customer_email):
        return
    try:
        settings = db.query(InvoiceSettings).filter(InvoiceSettings.user_id == user.id).first()
        if not (settings and settings.auto_send_email):
            logger.debug("Customer email not sent (auto_send_email disabled) | tx_ref=%s", transaction.tx_ref)
            return
        payment_url = getattr(transaction, "payment_url", None)
        qr_code_data_uri = getattr(transaction, "qr_code_payment_url", None)
        sent = send_invoice_email(
            to_email=transaction.customer_email,
            invoice=invoice,
            pdf_bytes=pdf_bytes,
            payment_url=payment_url,
            qr_code_data_uri=qr_code_data_uri,
            merchant_email=user.email,
        )
        if sent:
            log_event(
                db,
                "email.customer_invoice_sent",
                user_id=user.id,
                tx_ref=transaction.tx_ref,
                detail={"invoice_number": invoice.invoice_number, "customer_email": transaction.customer_email},
            )
            logger.info(
                "Customer invoice email sent | tx_ref=%s customer_email=%s",
                transaction.tx_ref,
                transaction.customer_email,
            )
        else:
            logger.warning(
                "Customer invoice email failed | tx_ref=%s customer_email=%s",
                transaction.tx_ref,
                transaction.customer_email,
            )
    except Exception as e:
        logger.error("Exception sending customer invoice | tx_ref=%s error=%s", transaction.tx_ref, e)


def send_payment_notification_emails(db, transaction, user) -> None:
    """Send payment notification emails after payment confirmation."""
    try:
        invoice = _ensure_invoice_exists(db, transaction, user)
        pdf_bytes = _generate_pdf_for_notification(invoice, transaction)
        _send_merchant_email(db, transaction, user, invoice, pdf_bytes)
        _send_customer_email(db, transaction, user, invoice, pdf_bytes)

        if invoice:
            try:
                from models.invoice import InvoiceStatus

                invoice.status = InvoiceStatus.PAID
                if not invoice.paid_at:
                    invoice.paid_at = datetime.now(timezone.utc)
                db.flush()
                logger.info("Invoice status updated to paid | invoice_number=%s", invoice.invoice_number)
            except Exception as e:
                logger.error(
                    "Failed to update invoice status | invoice_number=%s error=%s",
                    invoice.invoice_number if invoice else "N/A",
                    e,
                )
                db.rollback()
    except Exception as e:
        logger.error("Unexpected error in send_payment_notification_emails | tx_ref=%s error=%s", transaction.tx_ref, e)

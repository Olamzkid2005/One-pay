"""
OnePay — Email delivery service (transport layer).
Sends emails via SMTP. Uses email_templates.py for content.
"""

import logging
import re
import smtplib
import time
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import Config
from services.email_templates import (
    build_2fa_email,
    build_invoice_email,
    build_merchant_notification_email,
    build_password_reset_email,
)

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_address(to_email: str) -> bool:
    """Return True if email is safe to use, False if invalid or injection attempt."""
    if not to_email or "\n" in to_email or "\r" in to_email:
        return False
    return bool(_EMAIL_RE.match(to_email))


def _smtp_send(msg: MIMEMultipart) -> None:
    """Send a pre-built MIME message via configured SMTP server."""
    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10) as server:
        if Config.MAIL_USE_TLS:
            server.starttls()
        if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.send_message(msg)


def _attach_pdf(msg: MIMEMultipart, pdf_bytes: bytes, filename: str) -> None:
    """Attach a PDF to a MIME message."""
    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(attachment)


def _retry_send(send_fn, label: str, max_attempts: int = 3) -> bool:
    """Call send_fn up to max_attempts times with exponential backoff. Returns success."""
    backoff = [1, 2, 4]
    for attempt in range(max_attempts):
        try:
            send_fn()
            return True
        except Exception as e:
            logger.error("%s failed attempt %d/%d: %s", label, attempt + 1, max_attempts, e)
            if attempt < max_attempts - 1:
                time.sleep(backoff[attempt])
    return False


def send_password_reset(to_email: str, reset_url: str) -> bool:
    """Send a password reset email. Returns True if sent, False otherwise."""
    if not _validate_email_address(to_email):
        logger.error("Invalid email address for password reset: %s", to_email[:50])
        return False

    if not Config.MAIL_USERNAME:
        logger.info("Password reset link for %s: %s", to_email, reset_url)
        return True

    text_body, html_body = build_password_reset_email(reset_url)

    def _send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your OnePay password"
        msg["From"] = Config.MAIL_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        _smtp_send(msg)

    success = _retry_send(_send, f"password reset to {to_email}", max_attempts=1)
    if success:
        logger.info("Password reset email sent to %s", to_email)
    else:
        logger.error("Failed to send password reset email to %s", to_email)
        logger.info("Password reset link for %s: %s", to_email, reset_url)
    return success


def send_invoice_email(
    to_email: str,
    invoice,
    pdf_bytes: bytes,
    payment_url: str,
    qr_code_data_uri: Optional[str] = None,
    merchant_email: Optional[str] = None,
) -> bool:
    """Send invoice PDF via email with retry logic."""
    if not _validate_email_address(to_email):
        error_msg = f"Invalid email address: {to_email[:50]}"
        logger.error(error_msg)
        invoice.email_attempts += 1
        invoice.email_last_error = error_msg
        return False

    if not Config.MAIL_USERNAME:
        logger.info("Invoice email (dev mode) | invoice=%s to=%s", invoice.invoice_number, to_email)
        invoice.email_sent = True
        invoice.email_sent_at = datetime.now(timezone.utc)
        invoice.email_attempts += 1
        return True

    text_body, html_body = build_invoice_email(invoice, payment_url, qr_code_data_uri)

    def _send() -> None:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Invoice {invoice.invoice_number} from {invoice.business_name or 'OnePay'}"
        msg["From"] = Config.MAIL_FROM
        msg["To"] = to_email
        if merchant_email and merchant_email != to_email:
            msg["Bcc"] = merchant_email
        alt = MIMEMultipart("alternative")
        msg.attach(alt)
        alt.attach(MIMEText(text_body, "plain"))
        alt.attach(MIMEText(html_body, "html"))
        _attach_pdf(msg, pdf_bytes, f"{invoice.invoice_number}.pdf")
        _smtp_send(msg)

    success = _retry_send(_send, f"invoice email {invoice.invoice_number}")
    invoice.email_attempts += 1
    if success:
        invoice.email_sent = True
        invoice.email_sent_at = datetime.now(timezone.utc)
        invoice.email_last_error = None
        logger.info("Invoice email sent | invoice=%s to=%s", invoice.invoice_number, to_email)
    else:
        invoice.email_last_error = "Failed after max retries"
        logger.error("Invoice email failed after max retries | invoice=%s", invoice.invoice_number)
    return success


def send_merchant_notification_email(to_email: str, transaction, invoice, pdf_bytes: Optional[bytes]) -> bool:
    """Send payment notification email to merchant."""
    if not _validate_email_address(to_email):
        logger.error("Invalid merchant email: %s", to_email[:50])
        return False

    if not Config.MAIL_USERNAME:
        logger.info("Merchant notification (dev mode) | tx_ref=%s to=%s", transaction.tx_ref, to_email)
        return True

    text_body, html_body = build_merchant_notification_email(transaction, invoice, pdf_bytes)

    def _send() -> None:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Payment Received - {transaction.tx_ref}"
        msg["From"] = Config.MAIL_FROM
        msg["To"] = to_email
        alt = MIMEMultipart("alternative")
        msg.attach(alt)
        alt.attach(MIMEText(text_body, "plain"))
        alt.attach(MIMEText(html_body, "html"))
        if pdf_bytes:
            filename = f"{invoice.invoice_number}.pdf" if invoice else "invoice.pdf"
            _attach_pdf(msg, pdf_bytes, filename)
        _smtp_send(msg)

    success = _retry_send(_send, f"merchant notification {transaction.tx_ref}")
    if success:
        logger.info("Merchant notification sent | tx_ref=%s to=%s", transaction.tx_ref, to_email)
    else:
        logger.error("Merchant notification failed after max retries | tx_ref=%s", transaction.tx_ref)
    return success


def send_2fa_code(to_email: str, code: str) -> bool:
    """Send a 2FA verification code email."""
    if not _validate_email_address(to_email):
        return False

    if not Config.MAIL_USERNAME:
        logger.info("2FA code sent (dev mode) | to=%s", to_email)
        return True

    text_body, html_body = build_2fa_email(code)

    def _send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{code} is your OnePay verification code"
        msg["From"] = Config.MAIL_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        _smtp_send(msg)

    success = _retry_send(_send, f"2FA code to {to_email}", max_attempts=1)
    if success:
        logger.info("2FA code sent to %s", to_email)
    else:
        logger.error("Failed to send 2FA email to %s", to_email)
        logger.info("Fallback 2FA Code for %s: %s", to_email, code)
    return success

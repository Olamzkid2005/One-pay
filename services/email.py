"""
OnePay — Email delivery service
Sends password reset emails and invoice emails via SMTP.
"""
import logging
import smtplib
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)


def send_password_reset(to_email: str, reset_url: str) -> bool:
    """
    Send a password reset email to the merchant.
    
    If MAIL_USERNAME is not configured, logs the reset URL to console
    (preserves dev behaviour). Email failure never crashes the auth flow.
    
    Returns True if sent successfully, False otherwise.
    """
    # Validate email format and reject header injection attempts
    if not to_email or '\n' in to_email or '\r' in to_email:
        logger.error("Invalid email address (header injection attempt): %s", to_email[:50])
        return False
    
    import re
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', to_email):
        logger.error("Invalid email format: %s", to_email[:50])
        return False
    
    if not Config.MAIL_USERNAME:
        logger.info("Password reset link for %s: %s", to_email, reset_url)
        return True
    
    try:
        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your OnePay password"
        msg["From"] = Config.MAIL_FROM
        msg["To"] = to_email
        
        # Plain text body
        text_body = f"""
Hello,

You requested a password reset for your OnePay merchant account.

Click the link below to set a new password:
{reset_url}

This link expires in 30 minutes.

If you didn't request this, you can safely ignore this email.

— OnePay Team
"""
        
        # HTML body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #24292f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0969da; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }}
        .content {{ background: #f6f8fa; padding: 30px; border-radius: 0 0 6px 6px; }}
        .button {{ display: inline-block; background: #0969da; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #57606a; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">OnePay</h1>
        </div>
        <div class="content">
            <h2>Reset your password</h2>
            <p>You requested a password reset for your OnePay merchant account.</p>
            <p>Click the button below to set a new password:</p>
            <a href="{reset_url}" class="button">Reset Password</a>
            <p style="color: #57606a; font-size: 14px;">This link expires in 30 minutes.</p>
            <p style="color: #57606a; font-size: 14px;">If you didn't request this, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>OnePay — Secure Payment Links</p>
        </div>
    </div>
</body>
</html>
"""
        
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Send via SMTP
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info("Password reset email sent to %s", to_email)
        return True
        
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", to_email, e)
        # Fallback: log the URL so dev can still reset
        logger.info("Password reset link for %s: %s", to_email, reset_url)
        return False


def send_invoice_email(
    to_email: str,
    invoice,
    pdf_bytes: bytes,
    payment_url: str,
    qr_code_data_uri: Optional[str] = None,
    merchant_email: Optional[str] = None
) -> bool:
    """
    Send invoice PDF via email with retry logic.
    
    Args:
        to_email: Recipient email address (customer)
        invoice: Invoice object with invoice details
        pdf_bytes: PDF binary data to attach
        payment_url: Payment link URL
        qr_code_data_uri: Optional QR code as data URI
        merchant_email: Optional merchant email to BCC (receives copy)
        
    Returns:
        True if sent successfully, False otherwise
        
    Side Effects:
        Updates invoice.email_sent, email_sent_at, email_attempts, email_last_error
    """
    # Validate email format and reject header injection attempts
    if not to_email or '\n' in to_email or '\r' in to_email:
        error_msg = f"Invalid email address (header injection attempt): {to_email[:50]}"
        logger.error(error_msg)
        invoice.email_attempts += 1
        invoice.email_last_error = error_msg
        return False
    
    import re
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', to_email):
        error_msg = f"Invalid email format: {to_email[:50]}"
        logger.error(error_msg)
        invoice.email_attempts += 1
        invoice.email_last_error = error_msg
        return False
    
    # Dev mode: log and return success if no mail config
    if not Config.MAIL_USERNAME:
        logger.info(
            "Invoice email (dev mode) | invoice=%s to=%s payment_url=%s",
            invoice.invoice_number, to_email, payment_url
        )
        invoice.email_sent = True
        invoice.email_sent_at = datetime.now(timezone.utc)
        invoice.email_attempts += 1
        return True
    
    # Retry logic with exponential backoff
    max_attempts = 3
    backoff_delays = [60, 300, 900]  # 1min, 5min, 15min
    
    for attempt in range(max_attempts):
        try:
            # Build email
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Invoice {invoice.invoice_number} from {invoice.business_name or 'OnePay'}"
            msg["From"] = Config.MAIL_FROM
            msg["To"] = to_email
            
            # BCC merchant if provided (merchant gets a copy)
            if merchant_email and merchant_email != to_email:
                msg["Bcc"] = merchant_email
            
            # Create alternative container for text/html
            msg_alternative = MIMEMultipart("alternative")
            msg.attach(msg_alternative)
            
            # Plain text body
            text_body = f"""
Hello,

Please find attached invoice {invoice.invoice_number} for {invoice.currency} {invoice.amount}.

Description: {invoice.description or 'N/A'}

You can pay online using this link:
{payment_url}

Payment Terms: {invoice.payment_terms or 'Payment due upon receipt'}

Thank you for your business!

— {invoice.business_name or 'OnePay'}
Powered by OnePay
"""
            
            # HTML body with QR code if available
            qr_code_html = ""
            if qr_code_data_uri:
                qr_code_html = f"""
                <div style="text-align: center; margin: 20px 0;">
                    <p style="color: #57606a; font-size: 14px; margin-bottom: 10px;">Scan to pay:</p>
                    <img src="{qr_code_data_uri}" alt="Payment QR Code" style="max-width: 200px; border: 1px solid #d0d7de; border-radius: 6px;" />
                </div>
"""
            
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #24292f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0969da; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }}
        .content {{ background: #f6f8fa; padding: 30px; border-radius: 0 0 6px 6px; }}
        .invoice-summary {{ background: white; padding: 20px; border-radius: 6px; margin: 20px 0; border: 1px solid #d0d7de; }}
        .invoice-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f6f8fa; }}
        .invoice-row:last-child {{ border-bottom: none; font-weight: bold; }}
        .button {{ display: inline-block; background: #0969da; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #57606a; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">{invoice.business_name or 'OnePay'}</h1>
        </div>
        <div class="content">
            <h2>Invoice {invoice.invoice_number}</h2>
            
            <div class="invoice-summary">
                <div class="invoice-row">
                    <span>Description:</span>
                    <span>{invoice.description or 'N/A'}</span>
                </div>
                <div class="invoice-row">
                    <span>Amount:</span>
                    <span>{invoice.currency} {invoice.amount}</span>
                </div>
                <div class="invoice-row">
                    <span>Status:</span>
                    <span>{invoice.status.value if hasattr(invoice.status, 'value') else str(invoice.status)}</span>
                </div>
            </div>
            
            <p>Please find the complete invoice attached as a PDF.</p>
            
            <p>You can pay online by clicking the button below:</p>
            <a href="{payment_url}" class="button">Pay Invoice</a>
            
            {qr_code_html}
            
            <p style="color: #57606a; font-size: 14px; margin-top: 30px;">
                <strong>Payment Terms:</strong> {invoice.payment_terms or 'Payment due upon receipt'}
            </p>
        </div>
        <div class="footer">
            <p>{invoice.business_name or 'OnePay'} — Powered by OnePay</p>
        </div>
    </div>
</body>
</html>
"""
            
            msg_alternative.attach(MIMEText(text_body, "plain"))
            msg_alternative.attach(MIMEText(html_body, "html"))
            
            # Attach PDF
            pdf_attachment = MIMEBase("application", "pdf")
            pdf_attachment.set_payload(pdf_bytes)
            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={invoice.invoice_number}.pdf"
            )
            msg.attach(pdf_attachment)
            
            # Send via SMTP
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10) as server:
                if Config.MAIL_USE_TLS:
                    server.starttls()
                if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                    server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
            
            # Success - update invoice tracking
            invoice.email_sent = True
            invoice.email_sent_at = datetime.now(timezone.utc)
            invoice.email_attempts += 1
            invoice.email_last_error = None
            
            logger.info(
                "Invoice email sent | invoice=%s to=%s attempt=%d",
                invoice.invoice_number, to_email, attempt + 1
            )
            return True
            
        except Exception as e:
            error_msg = str(e)
            invoice.email_attempts += 1
            invoice.email_last_error = error_msg
            
            logger.error(
                "Invoice email failed | invoice=%s to=%s attempt=%d/%d error=%s",
                invoice.invoice_number, to_email, attempt + 1, max_attempts, error_msg
            )
            
            # If not last attempt, wait with exponential backoff
            if attempt < max_attempts - 1:
                delay = backoff_delays[attempt]
                logger.info(
                    "Retrying invoice email in %d seconds | invoice=%s",
                    delay, invoice.invoice_number
                )
                time.sleep(delay)
            else:
                # Max attempts reached
                logger.error(
                    "Invoice email failed after %d attempts | invoice=%s",
                    max_attempts, invoice.invoice_number
                )
                return False
    
    return False


def send_merchant_notification_email(
    to_email: str,
    transaction,
    invoice,
    pdf_bytes: Optional[bytes]
) -> bool:
    """
    Send payment notification email to merchant.
    
    Args:
        to_email: Merchant email address
        transaction: Transaction object with payment details
        invoice: Invoice object (may be None if generation failed)
        pdf_bytes: Invoice PDF bytes (may be None if generation failed)
        
    Returns:
        True if sent successfully, False otherwise
        
    Email Content:
        - Subject: "Payment Received - {tx_ref}"
        - Body: Transfer details table (amount, currency, customer, timestamp)
        - Attachment: Invoice PDF (if available)
        - Retry: 3 attempts with exponential backoff (1min, 5min, 15min)
    """
    # Validate email format and reject header injection attempts
    if not to_email or '\n' in to_email or '\r' in to_email:
        logger.error("Invalid email address (header injection attempt): %s", to_email[:50])
        return False
    
    import re
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', to_email):
        logger.error("Invalid email format: %s", to_email[:50])
        return False
    
    # Dev mode: log and return success if no mail config
    if not Config.MAIL_USERNAME:
        logger.info(
            "Merchant notification email (dev mode) | tx_ref=%s to=%s amount=%s %s",
            transaction.tx_ref, to_email, transaction.amount, transaction.currency
        )
        return True
    
    # Retry logic with exponential backoff
    max_attempts = 3
    backoff_delays = [60, 300, 900]  # 1min, 5min, 15min
    
    for attempt in range(max_attempts):
        try:
            # Build email
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Payment Received - {transaction.tx_ref}"
            msg["From"] = Config.MAIL_FROM
            msg["To"] = to_email
            
            # Create alternative container for text/html
            msg_alternative = MIMEMultipart("alternative")
            msg.attach(msg_alternative)
            
            # Format timestamp
            verified_at_str = "N/A"
            if transaction.verified_at:
                verified_at = transaction.verified_at
                if verified_at.tzinfo is None:
                    verified_at = verified_at.replace(tzinfo=timezone.utc)
                verified_at_str = verified_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Plain text body
            text_body = f"""
Hello,

You have received a payment!

Transfer Details:
------------------
Transaction Reference: {transaction.tx_ref}
Amount: {transaction.currency} {transaction.amount}
Customer Email: {transaction.customer_email or 'N/A'}
Payment Timestamp: {verified_at_str}
Description: {transaction.description or 'N/A'}

"""
            
            if invoice:
                text_body += f"Invoice Number: {invoice.invoice_number}\n"
            
            if pdf_bytes:
                text_body += "\nPlease find the invoice attached as a PDF.\n"
            else:
                text_body += "\nNote: Invoice PDF could not be generated.\n"
            
            text_body += """
Thank you for using OnePay!

— OnePay Team
"""
            
            # HTML body
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #24292f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0969da; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }}
        .content {{ background: #f6f8fa; padding: 30px; border-radius: 0 0 6px 6px; }}
        .details-table {{ background: white; padding: 20px; border-radius: 6px; margin: 20px 0; border: 1px solid #d0d7de; }}
        .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f6f8fa; }}
        .detail-row:last-child {{ border-bottom: none; }}
        .detail-label {{ font-weight: 600; color: #57606a; }}
        .detail-value {{ color: #24292f; }}
        .footer {{ text-align: center; color: #57606a; font-size: 12px; margin-top: 20px; }}
        .success-badge {{ background: #1a7f37; color: white; padding: 4px 12px; border-radius: 12px; font-size: 14px; display: inline-block; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Payment Received</h1>
            <span class="success-badge">✓ Confirmed</span>
        </div>
        <div class="content">
            <h2>Transfer Details</h2>
            
            <div class="details-table">
                <div class="detail-row">
                    <span class="detail-label">Transaction Reference:</span>
                    <span class="detail-value">{transaction.tx_ref}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amount:</span>
                    <span class="detail-value">{transaction.currency} {transaction.amount}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Customer Email:</span>
                    <span class="detail-value">{transaction.customer_email or 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Payment Timestamp:</span>
                    <span class="detail-value">{verified_at_str}</span>
                </div>
"""
            
            if transaction.description:
                html_body += f"""
                <div class="detail-row">
                    <span class="detail-label">Description:</span>
                    <span class="detail-value">{transaction.description}</span>
                </div>
"""
            
            if invoice:
                html_body += f"""
                <div class="detail-row">
                    <span class="detail-label">Invoice Number:</span>
                    <span class="detail-value">{invoice.invoice_number}</span>
                </div>
"""
            
            html_body += """
            </div>
"""
            
            if pdf_bytes:
                html_body += """
            <p>Please find the invoice attached as a PDF.</p>
"""
            else:
                html_body += """
            <p style="color: #d29922;"><strong>Note:</strong> Invoice PDF could not be generated.</p>
"""
            
            html_body += """
        </div>
        <div class="footer">
            <p>OnePay — Secure Payment Links</p>
        </div>
    </div>
</body>
</html>
"""
            
            msg_alternative.attach(MIMEText(text_body, "plain"))
            msg_alternative.attach(MIMEText(html_body, "html"))
            
            # Attach PDF if available
            if pdf_bytes:
                pdf_attachment = MIMEBase("application", "pdf")
                pdf_attachment.set_payload(pdf_bytes)
                encoders.encode_base64(pdf_attachment)
                filename = f"{invoice.invoice_number}.pdf" if invoice else "invoice.pdf"
                pdf_attachment.add_header(
                    "Content-Disposition",
                    f"attachment; filename={filename}"
                )
                msg.attach(pdf_attachment)
            
            # Send via SMTP
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10) as server:
                if Config.MAIL_USE_TLS:
                    server.starttls()
                if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                    server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
            
            logger.info(
                "Merchant notification email sent | tx_ref=%s to=%s attempt=%d",
                transaction.tx_ref, to_email, attempt + 1
            )
            return True
            
        except Exception as e:
            error_msg = str(e)
            
            logger.error(
                "Merchant notification email failed | tx_ref=%s to=%s attempt=%d/%d error=%s",
                transaction.tx_ref, to_email, attempt + 1, max_attempts, error_msg
            )
            
            # If not last attempt, wait with exponential backoff
            if attempt < max_attempts - 1:
                delay = backoff_delays[attempt]
                logger.info(
                    "Retrying merchant notification email in %d seconds | tx_ref=%s",
                    delay, transaction.tx_ref
                )
                time.sleep(delay)
            else:
                # Max attempts reached
                logger.error(
                    "Merchant notification email failed after %d attempts | tx_ref=%s",
                    max_attempts, transaction.tx_ref
                )
                return False
    
    return False

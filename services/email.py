"""
OnePay — Email delivery service
Sends password reset emails via SMTP.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

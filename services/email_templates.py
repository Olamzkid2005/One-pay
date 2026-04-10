"""
OnePay — Email templates.

Separates HTML/CSS templates from the email sending logic.
This makes the email service testable and allows templates to be modified
without touching the transport code.
"""

from typing import Optional

_CSS_INVOICE = (
    "body { font-family: sans-serif; color: #24292f; }\n"
    ".container { max-width: 600px; margin: 0 auto; padding: 20px; }\n"
    ".header { background: #0969da; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }\n"
    ".content { background: #f6f8fa; padding: 30px; border-radius: 0 0 6px 6px; }\n"
    ".row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f6f8fa; }\n"
    ".btn { display: inline-block; background: #0969da; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }\n"
)

_CSS_MERCHANT = (
    "body { font-family: sans-serif; color: #24292f; }\n"
    ".container { max-width: 600px; margin: 0 auto; padding: 20px; }\n"
    ".header { background: #0969da; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }\n"
    ".content { background: #f6f8fa; padding: 30px; border-radius: 0 0 6px 6px; }\n"
    ".row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f6f8fa; }\n"
    ".badge { background: #1a7f37; color: white; padding: 4px 12px; border-radius: 12px; font-size: 14px; display: inline-block; margin: 10px 0; }\n"
)


def build_password_reset_email(reset_url: str) -> tuple[str, str]:
    """Build password reset email body."""
    text = (
        f"\nHello,\n\nYou requested a password reset for your OnePay account.\n\n"
        f"Reset link: {reset_url}\n\nExpires in 30 minutes.\n\n— OnePay Team\n"
    )
    html = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>\n'
        f'<body style="font-family:sans-serif;color:#24292f;padding:20px">\n'
        f"<h2>Reset your OnePay password</h2>\n"
        f"<p>Click the link below to set a new password:</p>\n"
        f'<a href="{reset_url}" style="display:inline-block;background:#0969da;color:white;'
        f'padding:12px 24px;text-decoration:none;border-radius:6px">Reset Password</a>\n'
        f'<p style="color:#57606a;font-size:14px">This link expires in 30 minutes.</p>\n'
        f"</body></html>"
    )
    return text, html


def build_invoice_email(
    invoice,
    payment_url: str,
    qr_code_data_uri: Optional[str] = None,
) -> tuple[str, str]:
    """Build invoice email body."""
    text = (
        f"\nHello,\n\nPlease find attached invoice {invoice.invoice_number} "
        f"for {invoice.currency} {invoice.amount}.\n\n"
        f"Description: {invoice.description or 'N/A'}\n\n"
        f"Pay online: {payment_url}\n\n"
        f"Payment Terms: {invoice.payment_terms or 'Payment due upon receipt'}\n\n"
        f"Thank you!\n— {invoice.business_name or 'OnePay'}\n"
    )

    qr_html = (
        f'<div style="text-align:center;margin:20px 0">'
        f'<img src="{qr_code_data_uri}" alt="QR" style="max-width:200px"/></div>'
        if qr_code_data_uri
        else ""
    )
    status_val = invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status)
    html = (
        f'<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        f"<style>{_CSS_INVOICE}</style></head>\n"
        f'<body><div class="container">\n'
        f'<div class="header"><h1 style="margin:0">{invoice.business_name or "OnePay"}</h1></div>\n'
        f'<div class="content">\n'
        f"<h2>Invoice {invoice.invoice_number}</h2>\n"
        f'<div style="background:white;padding:20px;border-radius:6px;border:1px solid #d0d7de">\n'
        f'<div class="row"><span>Description:</span><span>{invoice.description or "N/A"}</span></div>\n'
        f'<div class="row"><span>Amount:</span><span>{invoice.currency} {invoice.amount}</span></div>\n'
        f'<div class="row"><span>Status:</span><span>{status_val}</span></div>\n'
        f"</div>\n"
        f"<p>Invoice attached as PDF.</p>\n"
        f'<a href="{payment_url}" class="btn">Pay Invoice</a>\n'
        f"{qr_html}\n"
        f'<p style="color:#57606a;font-size:14px">'
        f"<strong>Payment Terms:</strong> {invoice.payment_terms or 'Payment due upon receipt'}</p>\n"
        f"</div>\n"
        f'<div style="text-align:center;color:#57606a;font-size:12px;margin-top:20px">\n'
        f"<p>{invoice.business_name or 'OnePay'} — Powered by OnePay</p>\n"
        f"</div></div></body></html>"
    )
    return text, html


def build_merchant_notification_email(
    transaction,
    invoice,
    pdf_bytes: Optional[bytes],
) -> tuple[str, str]:
    """Build merchant payment notification email."""
    from datetime import datetime, timezone

    verified_at_str = "N/A"
    if transaction.verified_at:
        vat = transaction.verified_at
        if vat.tzinfo is None:
            vat = vat.replace(tzinfo=timezone.utc)
        verified_at_str = vat.strftime("%Y-%m-%d %H:%M:%S UTC")

    inv_line_txt = f"Invoice Number: {invoice.invoice_number}\n" if invoice else ""
    pdf_note_txt = "Invoice PDF attached.\n" if pdf_bytes else "Note: Invoice PDF could not be generated.\n"
    text = (
        f"\nHello,\n\nYou have received a payment!\n\n"
        f"Transaction Reference: {transaction.tx_ref}\n"
        f"Amount: {transaction.currency} {transaction.amount}\n"
        f"Customer Email: {transaction.customer_email or 'N/A'}\n"
        f"Payment Timestamp: {verified_at_str}\n"
        f"Description: {transaction.description or 'N/A'}\n"
        f"{inv_line_txt}\n{pdf_note_txt}\n— OnePay Team\n"
    )

    desc_row = (
        f'<div class="row"><span>Description:</span><span>{transaction.description}</span></div>'
        if transaction.description
        else ""
    )
    inv_row = f'<div class="row"><span>Invoice:</span><span>{invoice.invoice_number}</span></div>' if invoice else ""
    pdf_note_html = (
        "<p>Invoice PDF attached.</p>"
        if pdf_bytes
        else '<p style="color:#d29922"><strong>Note:</strong> Invoice PDF could not be generated.</p>'
    )
    html = (
        f'<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        f"<style>{_CSS_MERCHANT}</style></head>\n"
        f'<body><div class="container">\n'
        f'<div class="header">\n'
        f'<h1 style="margin:0">Payment Received</h1>\n'
        f'<span class="badge">&#10003; Confirmed</span>\n'
        f"</div>\n"
        f'<div class="content">\n'
        f"<h2>Transfer Details</h2>\n"
        f'<div style="background:white;padding:20px;border-radius:6px;border:1px solid #d0d7de">\n'
        f'<div class="row"><span>Reference:</span><span>{transaction.tx_ref}</span></div>\n'
        f'<div class="row"><span>Amount:</span><span>{transaction.currency} {transaction.amount}</span></div>\n'
        f'<div class="row"><span>Customer:</span><span>{transaction.customer_email or "N/A"}</span></div>\n'
        f'<div class="row"><span>Timestamp:</span><span>{verified_at_str}</span></div>\n'
        f"{desc_row}\n{inv_row}\n"
        f"</div>\n"
        f"{pdf_note_html}\n"
        f"</div>\n"
        f'<div style="text-align:center;color:#57606a;font-size:12px;margin-top:20px">\n'
        f"<p>OnePay — Secure Payment Links</p>\n"
        f"</div></div></body></html>"
    )
    return text, html


def build_2fa_email(code: str) -> tuple[str, str]:
    """Build 2FA verification code email."""
    text = f"Your OnePay verification code is: {code}\nExpires in 10 minutes."
    html = (
        f'<html><body style="font-family:sans-serif;padding:20px">\n'
        f"<h2>OnePay Authentication</h2>\n"
        f"<p>Your verification code is:</p>\n"
        f'<h1 style="font-size:32px;letter-spacing:5px;color:#418fff">{code}</h1>\n'
        f"<p>Expires in 10 minutes.</p>\n"
        f"</body></html>"
    )
    return text, html

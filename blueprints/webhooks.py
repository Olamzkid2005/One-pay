"""Inbound webhook receiver for payment status updates"""
import hmac
import hashlib
from flask import Blueprint

webhooks_bp = Blueprint("webhooks", __name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC signature from inbound webhook
    
    Args:
        payload: Raw request body as bytes
        signature: Signature header value (format: "sha256=<hex>")
        secret: Shared secret for HMAC verification
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature.startswith('sha256='):
        return False
    
    expected_sig = signature[7:]  # Remove "sha256=" prefix
    computed_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_sig, computed_sig)

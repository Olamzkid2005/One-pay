"""Inbound webhook receiver for payment status updates"""
import hmac
import hashlib
import logging
from flask import Blueprint, request, jsonify

webhooks_bp = Blueprint("webhooks", __name__)
logger = logging.getLogger(__name__)


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


@webhooks_bp.route("/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates from external services"""
    from config import Config
    from database import get_db
    from models.transaction import Transaction
    from core.responses import error
    from core.ip import client_ip
    
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    if not verify_webhook_signature(request.data, signature, Config.INBOUND_WEBHOOK_SECRET):
        logger.warning("Invalid webhook signature | ip=%s", client_ip())
        return error("Invalid signature", "UNAUTHORIZED", 401)
    
    # Parse payload
    data = request.get_json(silent=True) or {}
    tx_ref = data.get("tx_ref")
    status = data.get("status")
    
    if not tx_ref or not status:
        return error("Missing required fields", "VALIDATION_ERROR", 400)
    
    # Update transaction
    with get_db() as db:
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref
        ).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        transaction.status = status
        db.flush()
        
        logger.info("Webhook processed | tx_ref=%s status=%s", tx_ref, status)
        
        return jsonify({"success": True, "tx_ref": tx_ref})

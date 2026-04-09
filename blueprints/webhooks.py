"""Inbound webhook receiver for payment status updates"""

import hashlib
import hmac
import logging

from flask import Blueprint, jsonify, request

from core.exceptions import AuthenticationError, ValidationError

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
    if not signature.startswith("sha256="):
        return False

    expected_sig = signature[7:]  # Remove "sha256=" prefix
    computed_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


@webhooks_bp.route("/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates from external services"""
    from config import Config
    from core.ip import client_ip
    from core.responses import error
    from database import get_db
    from models.transaction import Transaction, TransactionStatus
    from services.webhook import check_webhook_idempotency, store_webhook_idempotency

    # Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    if not verify_webhook_signature(
        request.data, signature, Config.INBOUND_WEBHOOK_SECRET
    ):
        logger.warning("Invalid webhook signature | ip=%s", client_ip())
        raise AuthenticationError("Invalid signature")

    # Parse payload
    data = request.get_json(silent=True) or {}
    tx_ref = data.get("tx_ref")
    status = data.get("status")

    if not tx_ref or not status:
        raise ValidationError("Missing required fields")

    # Check idempotency - extract unique identifier from payload
    webhook_id = data.get("webhook_id") or data.get("event_id") or tx_ref
    source = data.get("source", "unknown")

    # Update transaction
    with get_db() as db:
        # Check if webhook already processed
        if check_webhook_idempotency(db, webhook_id, source):
            logger.info(
                "Duplicate webhook detected | webhook_id=%s tx_ref=%s source=%s",
                webhook_id,
                tx_ref,
                source,
            )
            return jsonify({"success": True, "tx_ref": tx_ref}), 200

        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()

        if not transaction:
            raise ValidationError("Transaction not found")

        try:
            transaction.status = TransactionStatus(status)
        except ValueError:
            logger.warning("Invalid transaction status from webhook: %s", status)
            raise ValidationError("Invalid status")
        db.flush()

        # Store webhook identifier after successful processing
        store_webhook_idempotency(db, webhook_id, source, tx_ref)

        logger.info("Webhook processed | tx_ref=%s status=%s webhook_id=%s", tx_ref, status, webhook_id)

        return jsonify({"success": True, "tx_ref": tx_ref})

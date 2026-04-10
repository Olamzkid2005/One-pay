"""
OnePay — Payment Actions blueprint
Handles: audit logs, expired links, receipts, refunds
Split from payments.py to keep file size manageable.
"""
import logging
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request

from core.audit import log_event
from core.auth import current_user_id, current_username, valid_tx_ref
from core.decorators import rate_limit
from core.exceptions import AuthenticationError, ProviderError, ValidationError
from core.ip import client_ip
from core.responses import unauthenticated
from database import get_db
from models.audit_log import AuditLog
from models.transaction import Transaction, TransactionStatus
from services.korapay import KoraPayError, korapay

logger = logging.getLogger(__name__)
payment_actions_bp = Blueprint("payment_actions", __name__)


# ── Audit log for transaction ─────────────────────────────────────────────────


@rate_limit("audit:{user_id}", limit=20, window_secs=60)
@payment_actions_bp.route("/payments/audit/<tx_ref>", methods=["GET"])
def transaction_audit(tx_ref):
    if not current_user_id():
        return unauthenticated()
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction or transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.tx_ref == tx_ref)
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        return jsonify({"success": True, "tx_ref": tx_ref, "audit_logs": [log.to_dict() for log in logs]})


# ── Expired payment link page ─────────────────────────────────────────────────


@payment_actions_bp.route("/expired/<tx_ref>")
def expired_link(tx_ref):
    """Display expired payment link page to customer"""
    if not valid_tx_ref(tx_ref):
        return render_template("expired.html", reference="Invalid", transaction_id="N/A"), 404

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction:
            return render_template("expired.html", reference="Not Found", transaction_id=tx_ref), 404
        return render_template("expired.html", reference=transaction.description or tx_ref, transaction_id=tx_ref)


# ── Download receipt ───────────────────────────────────────────────────────────


@rate_limit("receipt:{user_id}", limit=10, window_secs=60)
@payment_actions_bp.route("/payments/receipt/<tx_ref>", methods=["GET"])
def download_receipt(tx_ref):
    """Generate and download a PDF receipt for a transaction"""
    if not current_user_id():
        raise AuthenticationError()
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction or transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        from flask import make_response

        from services.pdf_receipt import generate_receipt_pdf

        try:
            pdf_bytes = generate_receipt_pdf(transaction)
            response = make_response(pdf_bytes)
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Content-Disposition"] = f"attachment; filename=OnePay_Receipt_{tx_ref}.pdf"
            logger.info("PDF receipt downloaded | user=%s tx_ref=%s", current_username(), tx_ref)
            return response
        except Exception as e:
            logger.error("PDF receipt generation failed | user=%s tx_ref=%s error=%s", current_username(), tx_ref, e)
            from core.exceptions import OnePayError
            raise OnePayError("Unable to generate receipt. Please try again later.", "RECEIPT_ERROR", 500)


@payment_actions_bp.route("/payments/receipt/<tx_ref>/preview", methods=["GET"])
def preview_receipt_html(tx_ref):
    """Return HTML preview of receipt"""
    if not current_user_id():
        raise AuthenticationError()
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction or transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")

        from flask import make_response

        from services.pdf_receipt import generate_receipt_html

        try:
            html = generate_receipt_html(transaction)
            response = make_response(html)
            response.headers["Content-Type"] = "text/html"
            return response
        except Exception as e:
            logger.error("Receipt HTML preview failed | user=%s tx_ref=%s error=%s", current_username(), tx_ref, e)
            from core.exceptions import OnePayError
            raise OnePayError("Unable to generate preview. Please try again later.", "PREVIEW_ERROR", 500)


# ── Refund ─────────────────────────────────────────────────────────────────────


@payment_actions_bp.route("/payments/refund/<tx_ref>", methods=["POST"])
def initiate_refund(tx_ref):
    """Initiate a refund for a verified transaction."""
    if not current_user_id():
        raise AuthenticationError()
    if not valid_tx_ref(tx_ref):
        raise ValidationError("Invalid transaction reference format")

    data = request.get_json() or {}
    refund_amount = data.get("amount")
    refund_reason = data.get("reason")

    with get_db() as db:
        transaction = db.query(Transaction).filter(Transaction.tx_ref == tx_ref).first()
        if not transaction or transaction.user_id != current_user_id():
            raise ValidationError("Transaction not found")
        if transaction.status != TransactionStatus.VERIFIED:
            raise ValidationError("Cannot refund transaction that is not verified")

        from models.refund import Refund
        if db.query(Refund).filter(Refund.transaction_id == transaction.id).first():
            raise ValidationError("Transaction has already been refunded")

        try:
            refund_data = korapay.initiate_refund(
                payment_reference=tx_ref, refund_reference=None,
                amount=refund_amount, reason=refund_reason,
            )
            refund_amount_val = refund_data.get("amount")
            if refund_amount_val is None:
                from core.exceptions import OnePayError
                raise OnePayError("Unable to process refund. Please contact support.", "REFUND_ERROR", 500)

            refund = Refund(
                transaction_id=transaction.id,
                refund_reference=refund_data["reference"],
                amount=Decimal(str(refund_amount_val)),
                currency=refund_data["currency"],
                status=refund_data["status"],
                reason=refund_reason,
            )
            db.add(refund)
            log_event(db, "payment.refund_initiated", user_id=current_user_id(), ip_address=client_ip(),
                      detail={"tx_ref": tx_ref, "refund_reference": refund_data["reference"],
                              "amount": refund_data["amount"], "reason": refund_reason})
            db.commit()
            logger.info("Refund initiated | user=%s tx_ref=%s refund_ref=%s", current_username(), tx_ref, refund_data["reference"])
            return jsonify({"success": True, "refund_reference": refund_data["reference"],
                            "status": refund_data["status"], "amount": refund_data["amount"],
                            "currency": refund_data["currency"]}), 200

        except KoraPayError as e:
            logger.error("Refund initiation failed | user=%s tx_ref=%s error=%s", current_username(), tx_ref, str(e))
            raise ProviderError("Unable to process refund. Please try again later.", provider="KoraPay", original_error=str(e))
        except Exception as e:
            logger.error("Unexpected error during refund | user=%s tx_ref=%s error=%s", current_username(), tx_ref, str(e))
            db.rollback()
            from core.exceptions import OnePayError
            raise OnePayError("An unexpected error occurred", "INTERNAL_ERROR", 500)

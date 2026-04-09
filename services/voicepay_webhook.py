"""
VoicePay Webhook Service

Handles forwarding payment confirmations from OnePay to VoicePay
with HMAC-SHA256 signature verification.
"""
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)

# Prometheus metrics (optional - gracefully handle if not installed)
try:
    from prometheus_client import Counter, Histogram

    voicepay_webhooks_sent = Counter(
        'voicepay_webhooks_sent_total',
        'Total number of webhooks sent to VoicePay',
        ['status']  # success, failure
    )

    voicepay_webhook_duration = Histogram(
        'voicepay_webhook_duration_seconds',
        'Time taken to deliver webhook to VoicePay',
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    )

    voicepay_webhook_retries = Counter(
        'voicepay_webhook_retries_total',
        'Total number of webhook retry attempts'
    )

    voicepay_payment_amount = Histogram(
        'voicepay_payment_amount_naira',
        'Payment amounts from VoicePay transactions',
        buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
    )

    METRICS_ENABLED = True
except ImportError:
    logger.warning("prometheus_client not installed - VoicePay metrics disabled")
    METRICS_ENABLED = False


def generate_voicepay_signature(payload: dict, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for VoicePay webhook payload.

    Args:
        payload: Webhook payload dict
        secret: Shared secret for HMAC generation

    Returns:
        Hex-encoded HMAC-SHA256 signature

    Example:
        >>> payload = {"event": "payment.verified", "tx_ref": "VP-123"}
        >>> secret = "my-secret-key"
        >>> sig = generate_voicepay_signature(payload, secret)
        >>> len(sig)
        64
    """
    # Serialize payload with sorted keys for deterministic output
    message = json.dumps(payload, sort_keys=True)

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature



def build_voicepay_payload(transaction) -> dict:
    """
    Build VoicePay webhook payload from transaction.

    Args:
        transaction: Transaction model instance

    Returns:
        Dict with VoicePay webhook payload structure
    """
    # Track payment amount metric
    if METRICS_ENABLED:
        voicepay_payment_amount.observe(float(transaction.amount))

    payload = {
        "event": "payment.verified",
        "tx_ref": transaction.tx_ref,
        "amount": float(transaction.amount),
        "currency": transaction.currency or "NGN",
        "status": transaction.status.value if hasattr(transaction.status, 'value') else str(transaction.status),
        "verified_at": transaction.verified_at.isoformat() if transaction.verified_at else None,
        "customer_email": transaction.customer_email,
        "description": transaction.description
    }

    return payload



def _voicepay_retry_delay(attempt: int) -> float:
    return (2 ** (attempt - 1)) + (secrets.randbelow(500) / 1000)


def _voicepay_record_metrics(start_time: float, success: bool) -> None:
    if not METRICS_ENABLED:
        return
    duration = time.time() - start_time
    voicepay_webhook_duration.observe(duration)
    voicepay_webhooks_sent.labels(status="success" if success else "failure").inc()


def send_voicepay_webhook(
    payload: dict,
    webhook_url: str,
    secret: str,
    timeout: int = 10,
    max_retries: int = 3,
) -> dict:
    """Send webhook to VoicePay with HMAC signature and exponential backoff retries."""
    start_time = time.time()
    signature = generate_voicepay_signature(payload, secret)
    headers = {
        "Content-Type": "application/json",
        "X-OnePay-Signature": signature,
        "User-Agent": "OnePay-Webhook/1.0",
    }
    try:
        from flask import g
        correlation_id = g.get("correlation_id")
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
    except RuntimeError:
        pass

    tx_ref = payload.get("tx_ref")
    last_error = None

    for attempt in range(1, max_retries + 1):
        if attempt > 1 and METRICS_ENABLED:
            voicepay_webhook_retries.inc()
        try:
            logger.info("Sending VoicePay webhook | tx_ref=%s attempt=%d/%d url=%s", tx_ref, attempt, max_retries, webhook_url)
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout, verify=True)
            logger.info("VoicePay webhook response | tx_ref=%s status=%d", tx_ref, response.status_code)

            if 200 <= response.status_code < 300:
                _voicepay_record_metrics(start_time, True)
                return {"success": True, "status_code": response.status_code, "tx_ref": tx_ref, "response": response.json() if response.content else {}}

            if response.status_code >= 500 and attempt < max_retries:
                delay = _voicepay_retry_delay(attempt)
                logger.warning("VoicePay webhook server error, retry in %.1fs | tx_ref=%s status=%d", delay, tx_ref, response.status_code)
                time.sleep(delay)
                continue

            _voicepay_record_metrics(start_time, False)
            return {"success": False, "status_code": response.status_code, "tx_ref": tx_ref, "error": f"HTTP {response.status_code}"}

        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = _voicepay_retry_delay(attempt)
                logger.warning("VoicePay webhook network error, retry in %.1fs | tx_ref=%s", delay, tx_ref)
                time.sleep(delay)
                continue
        except Exception as e:
            last_error = str(e)
            logger.error("VoicePay webhook unexpected error | tx_ref=%s error=%s", tx_ref, str(e))
            break

    _voicepay_record_metrics(start_time, False)
    return {"success": False, "status_code": 0, "tx_ref": tx_ref, "error": f"Failed after {max_retries} attempts: {last_error}"}

"""
VoicePay Webhook Service

Handles forwarding payment confirmations from OnePay to VoicePay
with HMAC-SHA256 signature verification.
"""
import logging
import json
import hmac
import hashlib
import requests
from typing import Dict, Optional
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


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



def send_voicepay_webhook(
    payload: dict,
    webhook_url: str,
    secret: str,
    timeout: int = 10,
    max_retries: int = 3
) -> dict:
    """
    Send webhook to VoicePay with HMAC signature.
    
    Args:
        payload: Webhook payload dict
        webhook_url: VoicePay webhook URL
        secret: Shared secret for HMAC signature
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict with delivery result:
        {
            "success": bool,
            "status_code": int,
            "tx_ref": str,
            "response": dict,
            "error": str (if failed)
        }
    """
    import time
    import random
    
    # Generate signature
    signature = generate_voicepay_signature(payload, secret)
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-OnePay-Signature": signature,
        "User-Agent": "OnePay-Webhook/1.0"
    }
    
    # Retry logic with exponential backoff
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Sending VoicePay webhook | tx_ref=%s attempt=%d/%d url=%s",
                payload.get("tx_ref"),
                attempt,
                max_retries,
                webhook_url
            )
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout,
                verify=True
            )
            
            # Log response
            logger.info(
                "VoicePay webhook response | tx_ref=%s status=%d",
                payload.get("tx_ref"),
                response.status_code
            )
            
            # Check if successful (2xx status code)
            if 200 <= response.status_code < 300:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "tx_ref": payload.get("tx_ref"),
                    "response": response.json() if response.content else {}
                }
            
            # Server error - retry
            if response.status_code >= 500 and attempt < max_retries:
                delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                logger.warning(
                    "VoicePay webhook server error, retry in %.1fs | tx_ref=%s status=%d",
                    delay,
                    payload.get("tx_ref"),
                    response.status_code
                )
                time.sleep(delay)
                continue
            
            # Client error or final attempt - return failure
            return {
                "success": False,
                "status_code": response.status_code,
                "tx_ref": payload.get("tx_ref"),
                "error": f"HTTP {response.status_code}"
            }
            
        except requests.Timeout as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                logger.warning(
                    "VoicePay webhook timeout, retry in %.1fs | tx_ref=%s",
                    delay,
                    payload.get("tx_ref")
                )
                time.sleep(delay)
                continue
                
        except requests.ConnectionError as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                logger.warning(
                    "VoicePay webhook connection error, retry in %.1fs | tx_ref=%s",
                    delay,
                    payload.get("tx_ref")
                )
                time.sleep(delay)
                continue
        
        except Exception as e:
            last_error = str(e)
            logger.error(
                "VoicePay webhook unexpected error | tx_ref=%s error=%s",
                payload.get("tx_ref"),
                str(e)
            )
            break
    
    # All retries failed
    return {
        "success": False,
        "status_code": 0,
        "tx_ref": payload.get("tx_ref"),
        "error": f"Failed after {max_retries} attempts: {last_error}"
    }

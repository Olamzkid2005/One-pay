# VoicePay Integration Implementation Plan

**Goal:** Implement OnePay enhancements required for VoicePay integration as merchant payment gateway

**Architecture:** Add VoicePay-specific webhook forwarding, signature generation, environment configuration, monitoring, and documentation while maintaining backward compatibility with existing OnePay functionality.

**Tech Stack:** Python/Flask, KoraPay API, HMAC-SHA256 signatures, SQLAlchemy, Prometheus metrics

**Timeline:** 9-14 days (5 phases)

**Principles:** DRY, YAGNI, TDD, Frequent commits, Security-first

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [File Structure](#file-structure)
3. [Phase 1: Configuration & Environment Setup](#phase-1-configuration--environment-setup)
4. [Phase 2: VoicePay Webhook Service](#phase-2-voicepay-webhook-service)
5. [Phase 3: Integration & Testing](#phase-3-integration--testing)
6. [Phase 4: Monitoring & Logging](#phase-4-monitoring--logging)
7. [Phase 5: Documentation](#phase-5-documentation)
8. [Deployment Checklist](#deployment-checklist)

---

## Current State Analysis

### ✅ Already Implemented
- Payment link creation API (`POST /api/v1/payment-links`)
- Payment status verification API (`GET /api/v1/payment-links/{tx_ref}`)
- Virtual account generation via KoraPay
- Webhook infrastructure (KoraPay inbound webhooks)
- API key authentication (`core/api_auth.py`)
- Metadata support in payment links
- Transaction reference handling
- Payment link expiration
- Comprehensive logging and monitoring
- Webhook retry mechanism (`services/webhook.py`)
- Audit logging (`core/audit.py`)

### ⚠️ Needs Implementation
1. VoicePay webhook forwarding (OnePay → VoicePay)
2. HMAC signature generation for VoicePay webhooks
3. VoicePay-specific environment configuration
4. VoicePay-specific logging and metrics
5. Integration documentation
6. Testing infrastructure
7. VoicePay API key generation
8. Bill category documentation

---

## File Structure

### Files to Create
- `services/voicepay_webhook.py` - VoicePay webhook forwarding service
- `docs/VOICEPAY_INTEGRATION.md` - Integration guide
- `docs/VOICEPAY_WEBHOOK_GUIDE.md` - Webhook documentation
- `docs/VOICEPAY_BILL_CATEGORIES.md` - Bill categories reference
- `tests/integration/test_voicepay_integration.py` - Integration tests
- `tests/unit/test_voicepay_webhook.py` - Unit tests for webhook service
- `grafana/dashboards/voicepay-integration.json` - Monitoring dashboard
- `prometheus/alerts/voicepay.yml` - Alert rules

### Files to Modify
- `config.py` - Add VoicePay environment variables
- `.env.example` - Document VoicePay configuration
- `blueprints/webhooks.py` - Integrate VoicePay webhook forwarding
- `blueprints/payments.py` - Add VoicePay-specific logging
- `README.md` - Add VoicePay integration section
- `CHANGELOG.md` - Document VoicePay integration

---

## Phase 1: Configuration & Environment Setup

**Duration:** 1-2 days

**Goal:** Set up environment variables, configuration validation, and API key generation for VoicePay integration.

---

### Task 1.1: Add VoicePay Configuration to config.py

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Write failing test for VoicePay config validation**

Create test file first:

```python
# tests/unit/test_voicepay_config.py
import pytest
import os
from config import BaseConfig, ProductionConfig

def test_voicepay_config_exists():
    """Test that VoicePay configuration variables exist"""
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_URL')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_SECRET')
    assert hasattr(BaseConfig, 'VOICEPAY_API_KEY')

def test_voicepay_webhook_url_format():
    """Test that VoicePay webhook URL is valid HTTPS in production"""
    # Set production environment
    os.environ['APP_ENV'] = 'production'
    os.environ['VOICEPAY_WEBHOOK_URL'] = 'http://voicepay.ng/webhook'
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()

def test_voicepay_webhook_secret_length():
    """Test that VoicePay webhook secret meets minimum length"""
    os.environ['APP_ENV'] = 'production'
    os.environ['VOICEPAY_WEBHOOK_SECRET'] = 'short'
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_voicepay_config.py -v`
Expected: FAIL with "AttributeError: type object 'BaseConfig' has no attribute 'VOICEPAY_WEBHOOK_URL'"

- [ ] **Step 3: Add VoicePay configuration to BaseConfig**


```python
# config.py - Add to BaseConfig class after WEBHOOK_MAX_RETRIES

# ── VoicePay Integration ──────────────────────────────────────────────
VOICEPAY_WEBHOOK_URL = os.getenv("VOICEPAY_WEBHOOK_URL", "")
VOICEPAY_WEBHOOK_SECRET = os.getenv("VOICEPAY_WEBHOOK_SECRET", "")
VOICEPAY_API_KEY = os.getenv("VOICEPAY_API_KEY", "")

# Sandbox configuration
VOICEPAY_WEBHOOK_URL_SANDBOX = os.getenv("VOICEPAY_WEBHOOK_URL_SANDBOX", "")
VOICEPAY_WEBHOOK_SECRET_SANDBOX = os.getenv("VOICEPAY_WEBHOOK_SECRET_SANDBOX", "")

# Webhook timeout and retry settings
VOICEPAY_WEBHOOK_TIMEOUT_SECS = int(os.getenv("VOICEPAY_WEBHOOK_TIMEOUT_SECS", "10"))
VOICEPAY_WEBHOOK_MAX_RETRIES = int(os.getenv("VOICEPAY_WEBHOOK_MAX_RETRIES", "3"))

# Enable/disable VoicePay webhook forwarding
VOICEPAY_WEBHOOK_ENABLED = os.getenv("VOICEPAY_WEBHOOK_ENABLED", "true").lower() == "true"
```

- [ ] **Step 4: Add VoicePay validation to BaseConfig.validate()**

```python
# config.py - Add to BaseConfig.validate() method after Google OAuth validation

# Check VoicePay configuration in production
if app_env == "production" and cls.VOICEPAY_WEBHOOK_ENABLED:
    if not cls.VOICEPAY_WEBHOOK_URL:
        errors.append("VOICEPAY_WEBHOOK_URL is required when VoicePay integration is enabled")
    elif not cls.VOICEPAY_WEBHOOK_URL.startswith("https://"):
        errors.append("VOICEPAY_WEBHOOK_URL must use HTTPS in production")
    
    if not cls.VOICEPAY_WEBHOOK_SECRET:
        errors.append("VOICEPAY_WEBHOOK_SECRET is required when VoicePay integration is enabled")
    elif len(cls.VOICEPAY_WEBHOOK_SECRET) < 32:
        errors.append("VOICEPAY_WEBHOOK_SECRET too short (minimum 32 characters)")
    elif "change-this" in cls.VOICEPAY_WEBHOOK_SECRET.lower():
        errors.append("VOICEPAY_WEBHOOK_SECRET contains placeholder value")
    
    if not cls.VOICEPAY_API_KEY:
        warnings.append("VOICEPAY_API_KEY not set - VoicePay will need to generate this")
    elif len(cls.VOICEPAY_API_KEY) < 32:
        errors.append("VOICEPAY_API_KEY too short (minimum 32 characters)")
    
    # Validate secrets are unique
    if cls.VOICEPAY_WEBHOOK_SECRET and cls.VOICEPAY_WEBHOOK_SECRET == cls.HMAC_SECRET:
        errors.append("VOICEPAY_WEBHOOK_SECRET and HMAC_SECRET must be different")
    if cls.VOICEPAY_WEBHOOK_SECRET and cls.VOICEPAY_WEBHOOK_SECRET == cls.KORAPAY_WEBHOOK_SECRET:
        errors.append("VOICEPAY_WEBHOOK_SECRET and KORAPAY_WEBHOOK_SECRET must be different")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_voicepay_config.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit configuration changes**

```bash
git add config.py tests/unit/test_voicepay_config.py
git commit -m "feat: add VoicePay configuration with validation"
```

---

### Task 1.2: Update .env.example with VoicePay Configuration

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add VoicePay section to .env.example**

```bash
# .env.example - Add after GOOGLE_REDIRECT_URI section

# ── VoicePay Integration ──────────────────────────────────────────────
# Webhook URL where OnePay will send payment confirmations
VOICEPAY_WEBHOOK_URL=https://voicepay.ng/api/webhooks/onepay
VOICEPAY_WEBHOOK_SECRET=generate_with_python_secrets_token_hex_32

# Sandbox configuration for testing
VOICEPAY_WEBHOOK_URL_SANDBOX=https://sandbox.voicepay.ng/api/webhooks/onepay
VOICEPAY_WEBHOOK_SECRET_SANDBOX=generate_with_python_secrets_token_hex_32

# API key for VoicePay to authenticate with OnePay
# Generate this using: python -c "import secrets; print(secrets.token_urlsafe(32))"
VOICEPAY_API_KEY=

# Webhook timeout and retry settings
VOICEPAY_WEBHOOK_TIMEOUT_SECS=10
VOICEPAY_WEBHOOK_MAX_RETRIES=3

# Enable/disable VoicePay webhook forwarding (true/false)
VOICEPAY_WEBHOOK_ENABLED=true
```

- [ ] **Step 2: Commit .env.example changes**

```bash
git add .env.example
git commit -m "docs: add VoicePay configuration to .env.example"
```

---

### Task 1.3: Generate VoicePay API Key

**Files:**
- Create: `scripts/generate_voicepay_api_key.py`

- [ ] **Step 1: Write script to generate VoicePay API key**

```python
# scripts/generate_voicepay_api_key.py
"""
Generate API key for VoicePay integration.

This script creates a dedicated API key for VoicePay to authenticate
with OnePay's payment link creation and status check endpoints.

Usage:
    python scripts/generate_voicepay_api_key.py --email voicepay@example.com --name "VoicePay Integration"
"""
import sys
import argparse
from database import get_db
from models.user import User
from models.api_key import APIKey

def generate_voicepay_api_key(email: str, name: str) -> str:
    """
    Generate API key for VoicePay user.
    
    Args:
        email: Email address for VoicePay user account
        name: Descriptive name for the API key
        
    Returns:
        Generated API key string
    """
    with get_db() as db:
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"Error: User with email {email} not found")
            print("Please create the user account first")
            sys.exit(1)
        
        # Generate API key
        api_key_obj = APIKey.generate(
            db=db,
            user_id=user.id,
            name=name,
            rate_limit_override=100  # 100 requests/minute for VoicePay
        )
        
        print(f"\n✅ VoicePay API Key Generated Successfully")
        print(f"━" * 60)
        print(f"User: {user.email}")
        print(f"Name: {name}")
        print(f"API Key: {api_key_obj.key}")
        print(f"Rate Limit: 100 requests/minute")
        print(f"━" * 60)
        print(f"\n⚠️  IMPORTANT: Save this API key securely!")
        print(f"Add to VoicePay's .env file:")
        print(f"ONEPAY_API_KEY={api_key_obj.key}")
        print(f"\nThis key will not be shown again.\n")
        
        return api_key_obj.key

def main():
    parser = argparse.ArgumentParser(
        description="Generate API key for VoicePay integration"
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address for VoicePay user account"
    )
    parser.add_argument(
        "--name",
        default="VoicePay Integration",
        help="Descriptive name for the API key"
    )
    
    args = parser.parse_args()
    generate_voicepay_api_key(args.email, args.name)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test API key generation script**

Run: `python scripts/generate_voicepay_api_key.py --email test@voicepay.ng --name "VoicePay Test"`
Expected: API key generated and displayed

- [ ] **Step 3: Commit API key generation script**

```bash
git add scripts/generate_voicepay_api_key.py
git commit -m "feat: add VoicePay API key generation script"
```

---


## Phase 2: VoicePay Webhook Service

**Duration:** 2-3 days

**Goal:** Implement webhook forwarding service that sends payment confirmations from OnePay to VoicePay with HMAC signature.

---

### Task 2.1: Create VoicePay Webhook Service

**Files:**
- Create: `services/voicepay_webhook.py`
- Create: `tests/unit/test_voicepay_webhook.py`

- [ ] **Step 1: Write failing test for webhook signature generation**

```python
# tests/unit/test_voicepay_webhook.py
import pytest
import json
import hmac
import hashlib
from services.voicepay_webhook import generate_voicepay_signature, send_voicepay_webhook

def test_generate_voicepay_signature():
    """Test HMAC-SHA256 signature generation for VoicePay webhooks"""
    payload = {
        "event": "payment.verified",
        "tx_ref": "VP-BILL-123-1234567890",
        "amount": 9000.00
    }
    secret = "test-secret-key-32-characters-long"
    
    signature = generate_voicepay_signature(payload, secret)
    
    # Verify signature format (64 hex characters)
    assert len(signature) == 64
    assert all(c in '0123456789abcdef' for c in signature)
    
    # Verify signature is correct
    message = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    assert signature == expected

def test_generate_voicepay_signature_deterministic():
    """Test that signature generation is deterministic"""
    payload = {"event": "payment.verified", "tx_ref": "TEST-123"}
    secret = "test-secret"
    
    sig1 = generate_voicepay_signature(payload, secret)
    sig2 = generate_voicepay_signature(payload, secret)
    
    assert sig1 == sig2

def test_generate_voicepay_signature_different_payloads():
    """Test that different payloads produce different signatures"""
    secret = "test-secret"
    
    sig1 = generate_voicepay_signature({"tx_ref": "TEST-1"}, secret)
    sig2 = generate_voicepay_signature({"tx_ref": "TEST-2"}, secret)
    
    assert sig1 != sig2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_voicepay_webhook.py::test_generate_voicepay_signature -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.voicepay_webhook'"

- [ ] **Step 3: Implement signature generation function**

```python
# services/voicepay_webhook.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_voicepay_webhook.py::test_generate_voicepay_signature -v`
Expected: PASS

- [ ] **Step 5: Write failing test for webhook sending**

```python
# tests/unit/test_voicepay_webhook.py - Add to existing file

def test_build_voicepay_payload():
    """Test building VoicePay webhook payload from transaction"""
    from models.transaction import Transaction
    from decimal import Decimal
    
    # Create mock transaction
    transaction = Transaction(
        tx_ref="VP-BILL-123-1234567890",
        amount=Decimal("9000.00"),
        status="VERIFIED",
        customer_email="user@voicepay.ng",
        description="DSTV Premium Subscription",
        metadata={
            "source": "voicepay",
            "user_id": "123",
            "bill_type": "dstv"
        }
    )
    transaction.paid_at = datetime(2026, 4, 1, 10, 30, 0)
    
    from services.voicepay_webhook import build_voicepay_payload
    payload = build_voicepay_payload(transaction)
    
    # Verify payload structure
    assert payload["event"] == "payment.verified"
    assert payload["tx_ref"] == "VP-BILL-123-1234567890"
    assert payload["amount"] == 9000.00
    assert payload["currency"] == "NGN"
    assert payload["status"] == "VERIFIED"
    assert payload["customer_email"] == "user@voicepay.ng"
    assert payload["description"] == "DSTV Premium Subscription"
    assert payload["metadata"]["source"] == "voicepay"
    assert payload["metadata"]["user_id"] == "123"
    assert "paid_at" in payload
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/unit/test_voicepay_webhook.py::test_build_voicepay_payload -v`
Expected: FAIL with "ImportError: cannot import name 'build_voicepay_payload'"

- [ ] **Step 7: Implement payload building function**

```python
# services/voicepay_webhook.py - Add after generate_voicepay_signature

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
        "currency": "NGN",
        "status": transaction.status,
        "paid_at": transaction.paid_at.isoformat() if transaction.paid_at else None,
        "customer_email": transaction.customer_email,
        "description": transaction.description,
        "metadata": transaction.metadata or {}
    }
    
    return payload
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/unit/test_voicepay_webhook.py::test_build_voicepay_payload -v`
Expected: PASS

- [ ] **Step 9: Write failing test for webhook delivery**

```python
# tests/unit/test_voicepay_webhook.py - Add to existing file

import responses

@responses.activate
def test_send_voicepay_webhook_success():
    """Test successful webhook delivery to VoicePay"""
    from services.voicepay_webhook import send_voicepay_webhook
    
    # Mock VoicePay webhook endpoint
    responses.add(
        responses.POST,
        "https://voicepay.ng/api/webhooks/onepay",
        json={"success": True, "tx_ref": "VP-123"},
        status=200
    )
    
    payload = {
        "event": "payment.verified",
        "tx_ref": "VP-123",
        "amount": 9000.00
    }
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret"
    )
    
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["tx_ref"] == "VP-123"

@responses.activate
def test_send_voicepay_webhook_failure():
    """Test webhook delivery failure handling"""
    from services.voicepay_webhook import send_voicepay_webhook
    
    # Mock VoicePay webhook endpoint with error
    responses.add(
        responses.POST,
        "https://voicepay.ng/api/webhooks/onepay",
        json={"error": "Internal server error"},
        status=500
    )
    
    payload = {"event": "payment.verified", "tx_ref": "VP-123"}
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret"
    )
    
    assert result["success"] is False
    assert result["status_code"] == 500
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/unit/test_voicepay_webhook.py::test_send_voicepay_webhook_success -v`
Expected: FAIL with "ImportError: cannot import name 'send_voicepay_webhook'"

- [ ] **Step 11: Implement webhook sending function**


```python
# services/voicepay_webhook.py - Add after build_voicepay_payload

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
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `pytest tests/unit/test_voicepay_webhook.py -v`
Expected: PASS (all tests green)

- [ ] **Step 13: Commit VoicePay webhook service**

```bash
git add services/voicepay_webhook.py tests/unit/test_voicepay_webhook.py
git commit -m "feat: implement VoicePay webhook forwarding service with HMAC signatures"
```

---

### Task 2.2: Integrate VoicePay Webhook into KoraPay Webhook Handler

**Files:**
- Modify: `blueprints/webhooks.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_voicepay_integration.py
import pytest
import json
import hmac
import hashlib
from app import create_app
from database import get_db
from models.transaction import Transaction
from decimal import Decimal

@pytest.fixture
def app():
    """Create test app"""
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

def test_korapay_webhook_forwards_to_voicepay(client, monkeypatch):
    """Test that KoraPay webhook triggers VoicePay webhook"""
    from config import Config
    
    # Track VoicePay webhook calls
    voicepay_calls = []
    
    def mock_send_voicepay_webhook(payload, webhook_url, secret, **kwargs):
        voicepay_calls.append({
            "payload": payload,
            "webhook_url": webhook_url,
            "secret": secret
        })
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_voicepay_webhook
    )
    
    # Create test transaction
    with get_db() as db:
        transaction = Transaction(
            tx_ref="VP-BILL-123-1234567890",
            amount=Decimal("9000.00"),
            status="PENDING",
            customer_email="user@voicepay.ng",
            description="DSTV Premium",
            metadata={"source": "voicepay", "user_id": "123"}
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-123-1234567890",
            "status": "success",
            "amount": 9000
        }
    }
    
    # Generate KoraPay signature
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    korapay_signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Send webhook
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": korapay_signature}
    )
    
    assert response.status_code == 200
    
    # Verify VoicePay webhook was called
    assert len(voicepay_calls) == 1
    assert voicepay_calls[0]["payload"]["tx_ref"] == "VP-BILL-123-1234567890"
    assert voicepay_calls[0]["payload"]["event"] == "payment.verified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_voicepay_integration.py::test_korapay_webhook_forwards_to_voicepay -v`
Expected: FAIL (VoicePay webhook not called)

- [ ] **Step 3: Add VoicePay webhook forwarding to KoraPay webhook handler**

```python
# blueprints/webhooks.py - Modify existing KoraPay webhook handler

# Add import at top of file
from services.voicepay_webhook import build_voicepay_payload, send_voicepay_webhook

# Find the KoraPay webhook handler (likely around line 50-100)
# Add this code after transaction status is updated to VERIFIED

# After: transaction.status = "VERIFIED"
# Add:

# Forward to VoicePay if transaction has VoicePay metadata
if Config.VOICEPAY_WEBHOOK_ENABLED and transaction.metadata:
    source = transaction.metadata.get("source")
    if source == "voicepay":
        logger.info(
            "Forwarding payment confirmation to VoicePay | tx_ref=%s",
            transaction.tx_ref
        )
        
        # Build VoicePay payload
        voicepay_payload = build_voicepay_payload(transaction)
        
        # Determine webhook URL (sandbox vs production)
        if Config.KORAPAY_USE_SANDBOX:
            webhook_url = Config.VOICEPAY_WEBHOOK_URL_SANDBOX or Config.VOICEPAY_WEBHOOK_URL
            webhook_secret = Config.VOICEPAY_WEBHOOK_SECRET_SANDBOX or Config.VOICEPAY_WEBHOOK_SECRET
        else:
            webhook_url = Config.VOICEPAY_WEBHOOK_URL
            webhook_secret = Config.VOICEPAY_WEBHOOK_SECRET
        
        # Send webhook (async in background to not block KoraPay response)
        try:
            result = send_voicepay_webhook(
                payload=voicepay_payload,
                webhook_url=webhook_url,
                secret=webhook_secret,
                timeout=Config.VOICEPAY_WEBHOOK_TIMEOUT_SECS,
                max_retries=Config.VOICEPAY_WEBHOOK_MAX_RETRIES
            )
            
            if result["success"]:
                logger.info(
                    "VoicePay webhook delivered successfully | tx_ref=%s",
                    transaction.tx_ref
                )
            else:
                logger.error(
                    "VoicePay webhook delivery failed | tx_ref=%s error=%s",
                    transaction.tx_ref,
                    result.get("error")
                )
        except Exception as e:
            logger.error(
                "VoicePay webhook exception | tx_ref=%s error=%s",
                transaction.tx_ref,
                str(e)
            )
```

- [ ] **Step 4: Run integration test to verify it passes**

Run: `pytest tests/integration/test_voicepay_integration.py::test_korapay_webhook_forwards_to_voicepay -v`
Expected: PASS

- [ ] **Step 5: Commit webhook integration**

```bash
git add blueprints/webhooks.py tests/integration/test_voicepay_integration.py
git commit -m "feat: integrate VoicePay webhook forwarding into KoraPay webhook handler"
```

---


### Task 2.3: Add VoicePay-Specific Logging

**Files:**
- Modify: `blueprints/payments.py`

- [ ] **Step 1: Add VoicePay source detection to payment link creation**

```python
# blueprints/payments.py - In create_payment_link() function
# After metadata is extracted, add:

# Detect VoicePay source
is_voicepay = metadata and metadata.get("source") == "voicepay"

if is_voicepay:
    logger.info(
        "VoicePay payment link created | tx_ref=%s user_id=%s bill_type=%s amount=₦%.2f",
        tx_ref,
        metadata.get("user_id"),
        metadata.get("bill_type"),
        float(amount)
    )
```

- [ ] **Step 2: Add VoicePay logging to transaction status endpoint**

```python
# blueprints/payments.py - In transaction_status() function
# After transaction is retrieved, add:

# Log VoicePay status checks
if transaction.metadata and transaction.metadata.get("source") == "voicepay":
    logger.info(
        "VoicePay status check | tx_ref=%s status=%s user_id=%s",
        tx_ref,
        transaction.status,
        transaction.metadata.get("user_id")
    )
```

- [ ] **Step 3: Commit logging enhancements**

```bash
git add blueprints/payments.py
git commit -m "feat: add VoicePay-specific logging to payment endpoints"
```

---

## Phase 3: Integration & Testing

**Duration:** 3-5 days

**Goal:** Comprehensive testing of VoicePay integration including unit tests, integration tests, and end-to-end scenarios.

---

### Task 3.1: End-to-End Integration Tests

**Files:**
- Modify: `tests/integration/test_voicepay_integration.py`

- [ ] **Step 1: Write test for complete payment flow**

```python
# tests/integration/test_voicepay_integration.py - Add to existing file

def test_voicepay_complete_payment_flow(client, monkeypatch):
    """Test complete VoicePay payment flow from creation to confirmation"""
    from config import Config
    import time
    
    # Track webhook deliveries
    webhook_deliveries = []
    
    def mock_send_webhook(payload, webhook_url, secret, **kwargs):
        webhook_deliveries.append(payload)
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_webhook
    )
    
    # Step 1: Create payment link (VoicePay → OnePay)
    create_payload = {
        "amount": 9000.00,
        "description": "DSTV Premium Subscription",
        "customer_email": "user@voicepay.ng",
        "customer_name": "John Doe",
        "tx_ref": f"VP-BILL-123-{int(time.time())}",
        "metadata": {
            "source": "voicepay",
            "user_id": "123",
            "bill_type": "dstv",
            "package": "premium"
        }
    }
    
    response = client.post(
        "/api/v1/payment-links",
        json=create_payload,
        headers={"Authorization": f"Bearer {Config.VOICEPAY_API_KEY}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "virtual_account_number" in data["data"]
    
    tx_ref = data["data"]["tx_ref"]
    
    # Step 2: Simulate payment (User transfers money)
    # This would happen externally via bank transfer
    
    # Step 3: Simulate KoraPay webhook (KoraPay → OnePay)
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": tx_ref,
            "status": "success",
            "amount": 9000
        }
    }
    
    # Generate signature
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": signature}
    )
    
    assert response.status_code == 200
    
    # Step 4: Verify VoicePay webhook was sent (OnePay → VoicePay)
    assert len(webhook_deliveries) == 1
    webhook = webhook_deliveries[0]
    assert webhook["event"] == "payment.verified"
    assert webhook["tx_ref"] == tx_ref
    assert webhook["amount"] == 9000.00
    assert webhook["status"] == "VERIFIED"
    assert webhook["metadata"]["source"] == "voicepay"
    
    # Step 5: Verify transaction status
    response = client.get(
        f"/api/v1/payment-links/{tx_ref}",
        headers={"Authorization": f"Bearer {Config.VOICEPAY_API_KEY}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "VERIFIED"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_voicepay_integration.py::test_voicepay_complete_payment_flow -v`
Expected: PASS

- [ ] **Step 3: Write test for non-VoicePay transactions**

```python
# tests/integration/test_voicepay_integration.py - Add to existing file

def test_non_voicepay_transaction_no_webhook(client, monkeypatch):
    """Test that non-VoicePay transactions don't trigger VoicePay webhook"""
    webhook_calls = []
    
    def mock_send_webhook(payload, webhook_url, secret, **kwargs):
        webhook_calls.append(payload)
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_webhook
    )
    
    # Create regular OnePay transaction (no VoicePay metadata)
    with get_db() as db:
        transaction = Transaction(
            tx_ref="ONEPAY-REGULAR-123",
            amount=Decimal("5000.00"),
            status="PENDING",
            customer_email="user@example.com",
            description="Regular payment",
            metadata={"source": "web"}  # Not VoicePay
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "ONEPAY-REGULAR-123",
            "status": "success",
            "amount": 5000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": signature}
    )
    
    assert response.status_code == 200
    
    # Verify VoicePay webhook was NOT called
    assert len(webhook_calls) == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_voicepay_integration.py::test_non_voicepay_transaction_no_webhook -v`
Expected: PASS

- [ ] **Step 5: Write test for webhook failure handling**

```python
# tests/integration/test_voicepay_integration.py - Add to existing file

def test_voicepay_webhook_failure_handling(client, monkeypatch):
    """Test that webhook failures are logged but don't block KoraPay response"""
    def mock_send_webhook_failure(payload, webhook_url, secret, **kwargs):
        return {
            "success": False,
            "status_code": 500,
            "tx_ref": payload["tx_ref"],
            "error": "VoicePay server error"
        }
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_webhook_failure
    )
    
    # Create VoicePay transaction
    with get_db() as db:
        transaction = Transaction(
            tx_ref="VP-BILL-FAIL-123",
            amount=Decimal("9000.00"),
            status="PENDING",
            customer_email="user@voicepay.ng",
            description="Test payment",
            metadata={"source": "voicepay", "user_id": "123"}
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-FAIL-123",
            "status": "success",
            "amount": 9000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # KoraPay webhook should still succeed even if VoicePay webhook fails
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": signature}
    )
    
    assert response.status_code == 200
    
    # Verify transaction was still marked as VERIFIED
    with get_db() as db:
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == "VP-BILL-FAIL-123"
        ).first()
        assert transaction.status == "VERIFIED"
```

- [ ] **Step 6: Run all integration tests**

Run: `pytest tests/integration/test_voicepay_integration.py -v`
Expected: PASS (all tests green)

- [ ] **Step 7: Commit integration tests**

```bash
git add tests/integration/test_voicepay_integration.py
git commit -m "test: add comprehensive VoicePay integration tests"
```

---

### Task 3.2: Webhook Signature Validation Tests

**Files:**
- Create: `tests/unit/test_voicepay_signature.py`

- [ ] **Step 1: Write signature validation tests**

```python
# tests/unit/test_voicepay_signature.py
import pytest
import json
import hmac
import hashlib
from services.voicepay_webhook import generate_voicepay_signature

def test_signature_with_special_characters():
    """Test signature generation with special characters in payload"""
    payload = {
        "description": "Payment for DSTV: Premium Package (₦9,000)",
        "customer_name": "O'Brien & Sons Ltd.",
        "tx_ref": "VP-BILL-123"
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    
    # Verify signature is valid hex
    assert len(sig) == 64
    assert all(c in '0123456789abcdef' for c in sig)

def test_signature_with_unicode():
    """Test signature generation with Unicode characters"""
    payload = {
        "customer_name": "José García",
        "description": "Paiement pour électricité",
        "tx_ref": "VP-BILL-456"
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    assert len(sig) == 64

def test_signature_with_nested_objects():
    """Test signature generation with nested metadata"""
    payload = {
        "tx_ref": "VP-BILL-789",
        "metadata": {
            "user": {
                "id": "123",
                "name": "John Doe"
            },
            "bill": {
                "type": "dstv",
                "package": "premium"
            }
        }
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    assert len(sig) == 64

def test_signature_key_order_independence():
    """Test that signature is same regardless of key order in dict"""
    secret = "test-secret-key"
    
    payload1 = {"a": 1, "b": 2, "c": 3}
    payload2 = {"c": 3, "a": 1, "b": 2}
    payload3 = {"b": 2, "c": 3, "a": 1}
    
    sig1 = generate_voicepay_signature(payload1, secret)
    sig2 = generate_voicepay_signature(payload2, secret)
    sig3 = generate_voicepay_signature(payload3, secret)
    
    assert sig1 == sig2 == sig3

def test_signature_with_empty_values():
    """Test signature generation with empty/null values"""
    payload = {
        "tx_ref": "VP-BILL-000",
        "description": "",
        "metadata": None,
        "amount": 0
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    assert len(sig) == 64
```

- [ ] **Step 2: Run signature validation tests**

Run: `pytest tests/unit/test_voicepay_signature.py -v`
Expected: PASS (all tests green)

- [ ] **Step 3: Commit signature tests**

```bash
git add tests/unit/test_voicepay_signature.py
git commit -m "test: add comprehensive signature validation tests"
```

---


### Task 3.3: Error Scenario Testing

**Files:**
- Create: `tests/integration/test_voicepay_error_scenarios.py`

- [ ] **Step 1: Write test for missing VoicePay configuration**

```python
# tests/integration/test_voicepay_error_scenarios.py
import pytest
from app import create_app

def test_missing_voicepay_webhook_url(monkeypatch):
    """Test behavior when VOICEPAY_WEBHOOK_URL is not configured"""
    monkeypatch.setenv("VOICEPAY_WEBHOOK_URL", "")
    monkeypatch.setenv("VOICEPAY_WEBHOOK_ENABLED", "true")
    
    # Should log warning but not crash
    app = create_app()
    assert app is not None

def test_invalid_voicepay_webhook_url(client, monkeypatch):
    """Test handling of invalid VoicePay webhook URL"""
    def mock_send_webhook_invalid_url(payload, webhook_url, secret, **kwargs):
        import requests
        raise requests.ConnectionError("Invalid URL")
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_webhook_invalid_url
    )
    
    # Create VoicePay transaction
    with get_db() as db:
        transaction = Transaction(
            tx_ref="VP-BILL-INVALID-URL",
            amount=Decimal("9000.00"),
            status="PENDING",
            customer_email="user@voicepay.ng",
            metadata={"source": "voicepay"}
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook - should not crash
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-INVALID-URL",
            "status": "success",
            "amount": 9000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": signature}
    )
    
    # Should still return success (webhook failure doesn't block)
    assert response.status_code == 200

def test_voicepay_webhook_timeout(client, monkeypatch):
    """Test handling of VoicePay webhook timeout"""
    import requests
    
    def mock_send_webhook_timeout(payload, webhook_url, secret, **kwargs):
        raise requests.Timeout("Request timed out")
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_webhook_timeout
    )
    
    # Create VoicePay transaction
    with get_db() as db:
        transaction = Transaction(
            tx_ref="VP-BILL-TIMEOUT",
            amount=Decimal("9000.00"),
            status="PENDING",
            customer_email="user@voicepay.ng",
            metadata={"source": "voicepay"}
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-TIMEOUT",
            "status": "success",
            "amount": 9000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": signature}
    )
    
    # Should still succeed
    assert response.status_code == 200
```

- [ ] **Step 2: Run error scenario tests**

Run: `pytest tests/integration/test_voicepay_error_scenarios.py -v`
Expected: PASS (all tests green)

- [ ] **Step 3: Commit error scenario tests**

```bash
git add tests/integration/test_voicepay_error_scenarios.py
git commit -m "test: add VoicePay error scenario tests"
```

---

## Phase 4: Monitoring & Logging

**Duration:** 2-3 days

**Goal:** Add comprehensive monitoring, metrics, and alerting for VoicePay integration.

---

### Task 4.1: Add Prometheus Metrics

**Files:**
- Modify: `services/voicepay_webhook.py`

- [ ] **Step 1: Add metrics tracking to webhook service**

```python
# services/voicepay_webhook.py - Add at top after imports

from prometheus_client import Counter, Histogram, Gauge

# Prometheus metrics
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
```

- [ ] **Step 2: Instrument webhook sending function**

```python
# services/voicepay_webhook.py - Modify send_voicepay_webhook function
# Add at the beginning of the function:

import time
start_time = time.time()

# Add before each retry:
if attempt > 1:
    voicepay_webhook_retries.inc()

# Add at successful return:
duration = time.time() - start_time
voicepay_webhook_duration.observe(duration)
voicepay_webhooks_sent.labels(status='success').inc()

# Add at failure return:
duration = time.time() - start_time
voicepay_webhook_duration.observe(duration)
voicepay_webhooks_sent.labels(status='failure').inc()

# Add in build_voicepay_payload to track payment amounts:
voicepay_payment_amount.observe(float(transaction.amount))
```

- [ ] **Step 3: Test metrics collection**

```python
# tests/unit/test_voicepay_metrics.py
import pytest
from prometheus_client import REGISTRY

def test_voicepay_metrics_exist():
    """Test that VoicePay metrics are registered"""
    metric_names = [m.name for m in REGISTRY.collect()]
    
    assert 'voicepay_webhooks_sent_total' in metric_names
    assert 'voicepay_webhook_duration_seconds' in metric_names
    assert 'voicepay_webhook_retries_total' in metric_names
    assert 'voicepay_payment_amount_naira' in metric_names
```

- [ ] **Step 4: Run metrics tests**

Run: `pytest tests/unit/test_voicepay_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit metrics implementation**

```bash
git add services/voicepay_webhook.py tests/unit/test_voicepay_metrics.py
git commit -m "feat: add Prometheus metrics for VoicePay webhooks"
```

---

### Task 4.2: Create Grafana Dashboard

**Files:**
- Create: `grafana/dashboards/voicepay-integration.json`

- [ ] **Step 1: Create Grafana dashboard JSON**

```json
{
  "dashboard": {
    "title": "VoicePay Integration",
    "tags": ["voicepay", "webhooks", "payments"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "VoicePay Webhook Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(voicepay_webhooks_sent_total{status=\"success\"}[5m]) / rate(voicepay_webhooks_sent_total[5m]) * 100"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "VoicePay Webhooks Sent (Rate)",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(voicepay_webhooks_sent_total{status=\"success\"}[5m])",
            "legendFormat": "Success"
          },
          {
            "expr": "rate(voicepay_webhooks_sent_total{status=\"failure\"}[5m])",
            "legendFormat": "Failure"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "VoicePay Webhook Latency (p95)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(voicepay_webhook_duration_seconds_bucket[5m]))"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0}
      },
      {
        "id": 4,
        "title": "VoicePay Payment Volume",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(voicepay_payment_amount_naira_sum[5m]))"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 5,
        "title": "VoicePay Webhook Retries",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(voicepay_webhook_retries_total[5m])"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ]
  }
}
```

- [ ] **Step 2: Commit Grafana dashboard**

```bash
git add grafana/dashboards/voicepay-integration.json
git commit -m "feat: add Grafana dashboard for VoicePay integration monitoring"
```

---

### Task 4.3: Create Prometheus Alert Rules

**Files:**
- Create: `prometheus/alerts/voicepay.yml`

- [ ] **Step 1: Create alert rules**

```yaml
# prometheus/alerts/voicepay.yml
groups:
  - name: voicepay_integration
    interval: 30s
    rules:
      - alert: VoicePayWebhookHighFailureRate
        expr: |
          (
            rate(voicepay_webhooks_sent_total{status="failure"}[5m])
            /
            rate(voicepay_webhooks_sent_total[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: warning
          component: voicepay
        annotations:
          summary: "VoicePay webhook failure rate above 10%"
          description: "{{ $value | humanizePercentage }} of VoicePay webhooks are failing"
      
      - alert: VoicePayWebhookHighLatency
        expr: |
          histogram_quantile(0.95, rate(voicepay_webhook_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
          component: voicepay
        annotations:
          summary: "VoicePay webhook latency is high"
          description: "P95 latency is {{ $value }}s (threshold: 5s)"
      
      - alert: VoicePayWebhookDown
        expr: |
          rate(voicepay_webhooks_sent_total{status="success"}[5m]) == 0
          and
          rate(voicepay_webhooks_sent_total{status="failure"}[5m]) > 0
        for: 10m
        labels:
          severity: critical
          component: voicepay
        annotations:
          summary: "VoicePay webhook endpoint appears to be down"
          description: "No successful webhook deliveries in 10 minutes"
      
      - alert: VoicePayHighRetryRate
        expr: |
          rate(voicepay_webhook_retries_total[5m]) > 0.5
        for: 5m
        labels:
          severity: warning
          component: voicepay
        annotations:
          summary: "High VoicePay webhook retry rate"
          description: "Webhook retry rate is {{ $value }} retries/sec"
```

- [ ] **Step 2: Commit alert rules**

```bash
git add prometheus/alerts/voicepay.yml
git commit -m "feat: add Prometheus alert rules for VoicePay integration"
```

---


## Phase 5: Documentation

**Duration:** 2-3 days

**Goal:** Create comprehensive documentation for VoicePay integration including API guides, webhook documentation, and bill categories.

---

### Task 5.1: Create VoicePay Integration Guide

**Files:**
- Create: `docs/VOICEPAY_INTEGRATION.md`

- [ ] **Step 1: Write integration guide**

```markdown
# VoicePay Integration Guide

## Overview

OnePay serves as the merchant payment gateway for VoicePay, handling bill payments (DSTV, electricity, airtime) and invoice generation through virtual bank accounts.

## Architecture

```
VoicePay → OnePay API → KoraPay → Bank Transfer → KoraPay Webhook → OnePay → VoicePay Webhook
```

## Authentication

VoicePay authenticates with OnePay using API key authentication:

```bash
Authorization: Bearer YOUR_API_KEY
```

### Obtaining API Key

Contact OnePay support to generate a dedicated API key for your VoicePay integration.

## API Endpoints

### 1. Create Payment Link

**Endpoint:** `POST /api/v1/payment-links`

**Request:**
```json
{
  "amount": 9000.00,
  "description": "DSTV Premium Subscription",
  "customer_email": "user@voicepay.ng",
  "customer_name": "John Doe",
  "tx_ref": "VP-BILL-123-1234567890",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "bill_type": "dstv",
    "package": "premium"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "payment_url": "https://onepay.ng/pay/abc123",
    "tx_ref": "VP-BILL-123-1234567890",
    "virtual_account_number": "1234567890",
    "virtual_bank_name": "Wema Bank",
    "account_name": "OnePay - John Doe",
    "qr_code_url": "https://onepay.ng/qr/abc123.png",
    "amount": 9000.00,
    "expires_at": "2026-04-01T12:00:00Z"
  }
}
```

### 2. Check Payment Status

**Endpoint:** `GET /api/v1/payment-links/{tx_ref}`

**Response:**
```json
{
  "status": "success",
  "data": {
    "tx_ref": "VP-BILL-123-1234567890",
    "status": "VERIFIED",
    "amount": 9000.00,
    "paid_at": "2026-04-01T10:30:00Z",
    "customer_email": "user@voicepay.ng",
    "description": "DSTV Premium Subscription"
  }
}
```

**Status Values:**
- `PENDING` - Payment link created, awaiting payment
- `VERIFIED` - Payment confirmed
- `EXPIRED` - Payment link expired
- `FAILED` - Payment failed

## Webhook Notifications

OnePay sends webhook notifications to VoicePay when payments are confirmed.

### Webhook Payload

```json
{
  "event": "payment.verified",
  "tx_ref": "VP-BILL-123-1234567890",
  "amount": 9000.00,
  "currency": "NGN",
  "status": "VERIFIED",
  "paid_at": "2026-04-01T10:30:00Z",
  "customer_email": "user@voicepay.ng",
  "description": "DSTV Premium Subscription",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "bill_type": "dstv"
  }
}
```

### Webhook Security

Webhooks include an HMAC-SHA256 signature in the `X-OnePay-Signature` header.

**Verification (Python):**
```python
import hmac
import hashlib
import json

def verify_onepay_webhook(payload: dict, signature: str, secret: str) -> bool:
    message = json.dumps(payload, sort_keys=True)
    expected_signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

## Metadata Fields

VoicePay should include these metadata fields:

```json
{
  "source": "voicepay",
  "user_id": "123",
  "whatsapp_id": "2348012345678",
  "bill_type": "dstv",
  "package": "premium",
  "biometric_score": 0.92,
  "voice_verified": true
}
```

## Transaction Reference Format

VoicePay transaction references should follow this format:

```
VP-BILL-{user_id}-{timestamp}
Example: VP-BILL-123-1711958400
```

## Rate Limits

- Payment link creation: 100 requests/minute
- Status checks: 500 requests/minute

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error message"
}
```

### Common Error Codes

- `UNAUTHORIZED` - Invalid or missing API key
- `VALIDATION_ERROR` - Invalid request parameters
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `NOT_FOUND` - Transaction not found
- `EXPIRED` - Payment link expired

## Testing

### Sandbox Environment

- Base URL: `https://sandbox.onepay.ng`
- Use sandbox API key
- Virtual accounts are simulated

### Production Environment

- Base URL: `https://api.onepay.ng`
- Use production API key
- Real bank transfers

## Support

- Technical Support: support@onepay.ng
- Slack: #onepay-voicepay-integration
- Documentation: https://docs.onepay.ng
```

- [ ] **Step 2: Commit integration guide**

```bash
git add docs/VOICEPAY_INTEGRATION.md
git commit -m "docs: add VoicePay integration guide"
```

---

### Task 5.2: Create Webhook Documentation

**Files:**
- Create: `docs/VOICEPAY_WEBHOOK_GUIDE.md`

- [ ] **Step 1: Write webhook guide**

```markdown
# VoicePay Webhook Guide

## Overview

OnePay sends webhook notifications to VoicePay when payment confirmations are received from KoraPay.

## Webhook Flow

```
1. User transfers money to virtual account
2. KoraPay detects payment
3. KoraPay sends webhook to OnePay
4. OnePay verifies payment
5. OnePay sends webhook to VoicePay
```

## Webhook Endpoint

VoicePay must provide a webhook endpoint:

```
POST https://voicepay.ng/api/webhooks/onepay
```

## Webhook Payload

### Payment Verified Event

```json
{
  "event": "payment.verified",
  "tx_ref": "VP-BILL-123-1234567890",
  "amount": 9000.00,
  "currency": "NGN",
  "status": "VERIFIED",
  "paid_at": "2026-04-01T10:30:00Z",
  "customer_email": "user@voicepay.ng",
  "description": "DSTV Premium Subscription",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "bill_type": "dstv",
    "package": "premium"
  }
}
```

### Field Descriptions

- `event` - Event type (always "payment.verified")
- `tx_ref` - Transaction reference from payment link creation
- `amount` - Payment amount in Naira
- `currency` - Currency code (always "NGN")
- `status` - Payment status (always "VERIFIED" for this event)
- `paid_at` - ISO 8601 timestamp of payment confirmation
- `customer_email` - Customer email address
- `description` - Payment description
- `metadata` - Custom metadata from payment link creation

## Security

### HMAC Signature Verification

Every webhook includes an HMAC-SHA256 signature in the `X-OnePay-Signature` header.

**Verification Steps:**

1. Extract signature from header
2. Serialize payload with sorted keys
3. Compute HMAC-SHA256 with shared secret
4. Compare signatures using constant-time comparison

**Python Example:**

```python
import hmac
import hashlib
import json
from flask import request, jsonify

@app.route('/api/webhooks/onepay', methods=['POST'])
def receive_onepay_webhook():
    # Get signature from header
    signature = request.headers.get('X-OnePay-Signature', '')
    
    # Get payload
    payload = request.get_json()
    
    # Verify signature
    if not verify_signature(payload, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Process webhook
    process_payment_confirmation(payload)
    
    return jsonify({'success': True, 'tx_ref': payload['tx_ref']})

def verify_signature(payload: dict, signature: str) -> bool:
    # Serialize with sorted keys
    message = json.dumps(payload, sort_keys=True)
    
    # Compute expected signature
    expected = hmac.new(
        ONEPAY_WEBHOOK_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(signature, expected)
```

**Node.js Example:**

```javascript
const crypto = require('crypto');

function verifySignature(payload, signature) {
  // Serialize with sorted keys
  const message = JSON.stringify(payload, Object.keys(payload).sort());
  
  // Compute expected signature
  const expected = crypto
    .createHmac('sha256', process.env.ONEPAY_WEBHOOK_SECRET)
    .update(message)
    .digest('hex');
  
  // Constant-time comparison
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}
```

### IP Whitelisting (Optional)

For additional security, whitelist OnePay's server IPs:

- Production: `[To be provided]`
- Sandbox: `[To be provided]`

## Retry Logic

OnePay retries failed webhook deliveries:

- Maximum retries: 3
- Retry delay: Exponential backoff (2^n seconds)
- Timeout: 10 seconds per attempt

## Response Requirements

VoicePay webhook endpoint should:

1. Respond within 10 seconds
2. Return HTTP 200 for success
3. Return 4xx/5xx for errors (triggers retry)

**Success Response:**

```json
{
  "success": true,
  "tx_ref": "VP-BILL-123-1234567890"
}
```

## Idempotency

Webhooks may be delivered multiple times. VoicePay should:

1. Use `tx_ref` as idempotency key
2. Ignore duplicate webhooks
3. Return success for duplicates

**Example:**

```python
def process_payment_confirmation(payload):
    tx_ref = payload['tx_ref']
    
    # Check if already processed
    if is_already_processed(tx_ref):
        logger.info(f"Duplicate webhook ignored: {tx_ref}")
        return
    
    # Process payment
    mark_payment_as_confirmed(tx_ref)
    notify_user(payload)
    
    # Mark as processed
    mark_as_processed(tx_ref)
```

## Testing

### Sandbox Webhooks

Test webhook delivery in sandbox:

```bash
curl -X POST https://sandbox.voicepay.ng/api/webhooks/onepay \
  -H "Content-Type: application/json" \
  -H "X-OnePay-Signature: YOUR_SIGNATURE" \
  -d '{
    "event": "payment.verified",
    "tx_ref": "VP-BILL-TEST-123",
    "amount": 9000.00,
    "currency": "NGN",
    "status": "VERIFIED",
    "paid_at": "2026-04-01T10:30:00Z",
    "customer_email": "test@voicepay.ng",
    "description": "Test payment",
    "metadata": {
      "source": "voicepay",
      "user_id": "test-123"
    }
  }'
```

### Webhook Signature Generator

Use this script to generate test signatures:

```python
import hmac
import hashlib
import json

def generate_test_signature(payload, secret):
    message = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

# Example
payload = {
    "event": "payment.verified",
    "tx_ref": "VP-BILL-TEST-123",
    "amount": 9000.00
}
secret = "your-webhook-secret"

signature = generate_test_signature(payload, secret)
print(f"X-OnePay-Signature: {signature}")
```

## Monitoring

Monitor webhook delivery:

- Success rate
- Latency
- Retry rate
- Error rate

## Troubleshooting

### Webhook Not Received

1. Check VoicePay webhook URL is configured in OnePay
2. Verify webhook endpoint is accessible
3. Check firewall rules
4. Review OnePay logs for delivery attempts

### Signature Verification Fails

1. Verify shared secret matches
2. Check payload serialization (sorted keys)
3. Ensure UTF-8 encoding
4. Use constant-time comparison

### Duplicate Webhooks

1. Implement idempotency using `tx_ref`
2. Log duplicate deliveries
3. Return success for duplicates

## Support

- Technical Support: support@onepay.ng
- Webhook Issues: webhooks@onepay.ng
- Slack: #onepay-voicepay-integration
```

- [ ] **Step 2: Commit webhook guide**

```bash
git add docs/VOICEPAY_WEBHOOK_GUIDE.md
git commit -m "docs: add VoicePay webhook guide with security examples"
```

---

### Task 5.3: Create Bill Categories Documentation

**Files:**
- Create: `docs/VOICEPAY_BILL_CATEGORIES.md`

- [ ] **Step 1: Write bill categories documentation**

```markdown
# VoicePay Bill Categories

## Overview

OnePay supports various bill payment categories through KoraPay integration. This document lists available categories and required metadata.

## Supported Categories

### Phase 1 (MVP)

#### 1. DSTV Subscriptions

**Bill Type:** `dstv`

**Packages:**
- Compact: ₦10,500/month
- Compact Plus: ₦16,600/month
- Premium: ₦24,500/month
- Premium Asia: ₦29,300/month

**Required Metadata:**
```json
{
  "bill_type": "dstv",
  "provider": "DSTV Nigeria",
  "package": "premium",
  "smartcard_number": "1234567890",
  "customer_name": "John Doe"
}
```

#### 2. Electricity Bills

**Bill Type:** `electricity`

**Providers:**
- EKEDC (Eko Electricity)
- IKEDC (Ikeja Electric)
- AEDC (Abuja Electricity)
- PHED (Port Harcourt Electricity)

**Required Metadata:**
```json
{
  "bill_type": "electricity",
  "provider": "EKEDC",
  "meter_number": "12345678901",
  "meter_type": "prepaid",
  "customer_name": "John Doe",
  "customer_address": "123 Main St, Lagos"
}
```

#### 3. Airtime Top-Up

**Bill Type:** `airtime`

**Providers:**
- MTN
- Airtel
- Glo
- 9mobile

**Required Metadata:**
```json
{
  "bill_type": "airtime",
  "provider": "MTN",
  "phone_number": "08012345678",
  "amount": 1000
}
```

### Phase 2 (Future)

#### 4. Water Bills

**Bill Type:** `water`

**Providers:**
- Lagos Water Corporation
- Abuja Water Board

**Required Metadata:**
```json
{
  "bill_type": "water",
  "provider": "Lagos Water Corporation",
  "account_number": "1234567890",
  "customer_name": "John Doe"
}
```

#### 5. Internet Subscriptions

**Bill Type:** `internet`

**Providers:**
- Spectranet
- Smile
- Swift

**Required Metadata:**
```json
{
  "bill_type": "internet",
  "provider": "Spectranet",
  "account_number": "1234567890",
  "package": "unlimited",
  "customer_name": "John Doe"
}
```

#### 6. Cable TV (Other)

**Bill Type:** `cable_tv`

**Providers:**
- GOtv
- Startimes

**Required Metadata:**
```json
{
  "bill_type": "cable_tv",
  "provider": "GOtv",
  "smartcard_number": "1234567890",
  "package": "max",
  "customer_name": "John Doe"
}
```

## Metadata Validation

### Required Fields (All Categories)

- `bill_type` - Category identifier
- `provider` - Service provider name
- `customer_name` - Customer name

### Optional Fields

- `customer_email` - Customer email
- `customer_phone` - Customer phone number
- `customer_address` - Customer address

## Amount Ranges

### Minimum Amounts

- DSTV: ₦2,000
- Electricity: ₦1,000
- Airtime: ₦100
- Water: ₦500
- Internet: ₦1,000
- Cable TV: ₦500

### Maximum Amounts

- All categories: ₦999,999

## Example Payment Link Creation

```json
{
  "amount": 24500.00,
  "description": "DSTV Premium Subscription - March 2026",
  "customer_email": "user@voicepay.ng",
  "customer_name": "John Doe",
  "tx_ref": "VP-BILL-123-1711958400",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "whatsapp_id": "2348012345678",
    "bill_type": "dstv",
    "provider": "DSTV Nigeria",
    "package": "premium",
    "smartcard_number": "1234567890",
    "customer_name": "John Doe",
    "voice_verified": true,
    "biometric_score": 0.95
  }
}
```

## Provider Codes

### DSTV Packages

- `compact` - DSTV Compact
- `compact_plus` - DSTV Compact Plus
- `premium` - DSTV Premium
- `premium_asia` - DSTV Premium Asia

### Electricity Providers

- `EKEDC` - Eko Electricity Distribution Company
- `IKEDC` - Ikeja Electric
- `AEDC` - Abuja Electricity Distribution Company
- `PHED` - Port Harcourt Electricity Distribution

### Meter Types

- `prepaid` - Prepaid meter
- `postpaid` - Postpaid meter

## Validation Rules

1. `bill_type` must be one of supported categories
2. `provider` must be valid for the bill type
3. `amount` must be within allowed range
4. Account/meter/smartcard numbers must be numeric
5. Phone numbers must be 11 digits (Nigerian format)

## Error Codes

- `INVALID_BILL_TYPE` - Unsupported bill category
- `INVALID_PROVIDER` - Unknown provider
- `INVALID_AMOUNT` - Amount outside allowed range
- `MISSING_METADATA` - Required metadata field missing
- `INVALID_ACCOUNT_NUMBER` - Invalid account/meter/smartcard number

## Support

For questions about bill categories:
- Email: billing@onepay.ng
- Slack: #onepay-voicepay-integration
```

- [ ] **Step 2: Commit bill categories documentation**

```bash
git add docs/VOICEPAY_BILL_CATEGORIES.md
git commit -m "docs: add VoicePay bill categories reference"
```

---

### Task 5.4: Update Main README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add VoicePay section to README**

```markdown
# README.md - Add after existing integrations section

## VoicePay Integration

OnePay serves as the merchant payment gateway for VoicePay, a voice-authenticated payment system.

### Features

- Payment link creation with virtual bank accounts
- Webhook notifications for payment confirmations
- Support for bill payments (DSTV, electricity, airtime)
- HMAC-SHA256 signature verification
- Comprehensive monitoring and alerting

### Documentation

- [Integration Guide](docs/VOICEPAY_INTEGRATION.md)
- [Webhook Guide](docs/VOICEPAY_WEBHOOK_GUIDE.md)
- [Bill Categories](docs/VOICEPAY_BILL_CATEGORIES.md)

### Configuration

```bash
# VoicePay webhook settings
VOICEPAY_WEBHOOK_URL=https://voicepay.ng/api/webhooks/onepay
VOICEPAY_WEBHOOK_SECRET=your_secret_here
VOICEPAY_API_KEY=voicepay_api_key_here
```

See [.env.example](.env.example) for complete configuration.
```

- [ ] **Step 2: Commit README updates**

```bash
git add README.md
git commit -m "docs: add VoicePay integration section to README"
```

---

### Task 5.5: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add VoicePay integration to CHANGELOG**

```markdown
# CHANGELOG.md - Add at top

## [1.6.0] - 2026-04-01

### Added - VoicePay Integration

- VoicePay webhook forwarding service with HMAC-SHA256 signatures
- VoicePay-specific configuration and environment variables
- VoicePay API key generation script
- Comprehensive VoicePay integration tests
- Prometheus metrics for VoicePay webhooks
- Grafana dashboard for VoicePay monitoring
- Prometheus alert rules for VoicePay integration
- VoicePay integration documentation
- VoicePay webhook guide with security examples
- VoicePay bill categories reference

### Changed

- Enhanced KoraPay webhook handler to forward to VoicePay
- Added VoicePay-specific logging to payment endpoints
- Updated configuration validation for VoicePay settings

### Security

- HMAC-SHA256 signature generation for VoicePay webhooks
- Webhook signature validation with constant-time comparison
- Separate secrets for VoicePay and KoraPay webhooks
```

- [ ] **Step 2: Commit CHANGELOG updates**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for VoicePay integration"
```

---


## Deployment Checklist

### Pre-Deployment (Sandbox)

- [ ] **Configuration**
  - [ ] Generate VoicePay webhook secret (32+ characters)
  - [ ] Add `VOICEPAY_WEBHOOK_URL_SANDBOX` to .env
  - [ ] Add `VOICEPAY_WEBHOOK_SECRET_SANDBOX` to .env
  - [ ] Set `VOICEPAY_WEBHOOK_ENABLED=true`
  - [ ] Verify configuration with `python -c "from config import Config; Config.validate()"`

- [ ] **API Key Generation**
  - [ ] Create VoicePay sandbox user account
  - [ ] Generate VoicePay sandbox API key
  - [ ] Share API key with VoicePay team securely
  - [ ] Document API key in secure location

- [ ] **Testing**
  - [ ] Run all unit tests: `pytest tests/unit/test_voicepay*.py -v`
  - [ ] Run all integration tests: `pytest tests/integration/test_voicepay*.py -v`
  - [ ] Test payment link creation with VoicePay metadata
  - [ ] Test webhook delivery to VoicePay sandbox
  - [ ] Verify webhook signature validation
  - [ ] Test error scenarios (timeout, invalid URL, etc.)
  - [ ] Verify non-VoicePay transactions don't trigger webhooks

- [ ] **Monitoring Setup**
  - [ ] Import Grafana dashboard
  - [ ] Configure Prometheus alert rules
  - [ ] Test alert notifications
  - [ ] Verify metrics are being collected

- [ ] **Documentation Review**
  - [ ] Review integration guide with VoicePay team
  - [ ] Review webhook guide with VoicePay team
  - [ ] Review bill categories documentation
  - [ ] Confirm API endpoints and formats
  - [ ] Verify code examples work

### Sandbox Integration Testing (with VoicePay)

- [ ] **End-to-End Flow**
  - [ ] VoicePay creates payment link via OnePay API
  - [ ] OnePay returns virtual account details
  - [ ] Simulate bank transfer (KoraPay sandbox)
  - [ ] KoraPay sends webhook to OnePay
  - [ ] OnePay forwards webhook to VoicePay
  - [ ] VoicePay verifies webhook signature
  - [ ] VoicePay confirms payment received

- [ ] **Error Scenarios**
  - [ ] Invalid API key
  - [ ] Missing required fields
  - [ ] Invalid transaction reference format
  - [ ] Expired payment link
  - [ ] Webhook delivery failure
  - [ ] Webhook signature mismatch

- [ ] **Performance Testing**
  - [ ] Load test payment link creation (100 req/min)
  - [ ] Load test status checks (500 req/min)
  - [ ] Measure webhook delivery latency
  - [ ] Verify retry mechanism works

### Pre-Production Deployment

- [ ] **Security Review**
  - [ ] Verify all secrets are unique and strong (32+ characters)
  - [ ] Confirm HTTPS enforcement in production
  - [ ] Review webhook signature implementation
  - [ ] Verify no secrets in logs
  - [ ] Check rate limiting configuration
  - [ ] Review error messages (no sensitive data leakage)

- [ ] **Configuration**
  - [ ] Generate production VoicePay webhook secret
  - [ ] Add `VOICEPAY_WEBHOOK_URL` to production .env
  - [ ] Add `VOICEPAY_WEBHOOK_SECRET` to production .env
  - [ ] Verify `KORAPAY_USE_SANDBOX=false`
  - [ ] Verify `ENFORCE_HTTPS=true`
  - [ ] Run production config validation

- [ ] **API Key Generation**
  - [ ] Create VoicePay production user account
  - [ ] Generate VoicePay production API key
  - [ ] Share API key with VoicePay team via secure channel
  - [ ] Document API key in password manager

- [ ] **Database**
  - [ ] Run database migrations
  - [ ] Verify transaction table has metadata column
  - [ ] Test transaction queries with VoicePay metadata
  - [ ] Backup database before deployment

### Production Deployment

- [ ] **Deployment**
  - [ ] Deploy code to production
  - [ ] Verify application starts successfully
  - [ ] Check logs for errors
  - [ ] Verify configuration loaded correctly
  - [ ] Test health check endpoint

- [ ] **Smoke Tests**
  - [ ] Create test payment link (small amount)
  - [ ] Verify virtual account generated
  - [ ] Make test payment
  - [ ] Verify webhook delivered to VoicePay
  - [ ] Verify payment status updated
  - [ ] Check monitoring dashboards

- [ ] **Monitoring**
  - [ ] Verify Grafana dashboard shows data
  - [ ] Verify Prometheus metrics being collected
  - [ ] Test alert notifications
  - [ ] Set up on-call rotation
  - [ ] Document incident response procedures

### Post-Deployment

- [ ] **Communication**
  - [ ] Notify VoicePay team of production deployment
  - [ ] Share production API endpoint
  - [ ] Share monitoring dashboard URL
  - [ ] Provide support contact information

- [ ] **Documentation**
  - [ ] Update deployment documentation
  - [ ] Document rollback procedures
  - [ ] Create runbook for common issues
  - [ ] Update architecture diagrams

- [ ] **Monitoring**
  - [ ] Monitor webhook success rate (target: >99%)
  - [ ] Monitor webhook latency (target: <2s p95)
  - [ ] Monitor payment volume
  - [ ] Monitor error rates
  - [ ] Review logs for issues

### Week 1 Post-Launch

- [ ] **Daily Checks**
  - [ ] Review webhook delivery metrics
  - [ ] Check for failed webhooks
  - [ ] Review error logs
  - [ ] Monitor payment volume
  - [ ] Check alert notifications

- [ ] **Weekly Review**
  - [ ] Analyze webhook success rate
  - [ ] Review latency trends
  - [ ] Identify optimization opportunities
  - [ ] Gather feedback from VoicePay team
  - [ ] Update documentation based on learnings

---

## Rollback Plan

### If Issues Detected

1. **Disable VoicePay Webhook Forwarding**
   ```bash
   # Set in production .env
   VOICEPAY_WEBHOOK_ENABLED=false
   
   # Restart application
   systemctl restart onepay
   ```

2. **Verify Existing Functionality**
   - Test regular OnePay payment links
   - Verify KoraPay webhooks still work
   - Check non-VoicePay transactions

3. **Investigate Issue**
   - Review application logs
   - Check webhook delivery logs
   - Review error messages
   - Analyze metrics

4. **Fix and Redeploy**
   - Fix identified issue
   - Test in sandbox
   - Deploy fix to production
   - Re-enable VoicePay webhooks

### Complete Rollback

If major issues require complete rollback:

1. **Disable VoicePay Integration**
   ```bash
   VOICEPAY_WEBHOOK_ENABLED=false
   ```

2. **Revert Code Changes**
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

3. **Deploy Previous Version**
   ```bash
   ./scripts/deploy.py --version <previous-version>
   ```

4. **Notify Stakeholders**
   - Inform VoicePay team
   - Provide estimated fix timeline
   - Document issues encountered

---

## Success Metrics

### Technical Metrics

- **Webhook Success Rate:** >99%
- **Webhook Latency (p95):** <2 seconds
- **API Response Time (p95):** <500ms
- **Error Rate:** <0.1%
- **Uptime:** >99.9%

### Business Metrics

- **Payment Volume:** Track daily/weekly/monthly
- **Average Payment Amount:** Monitor trends
- **Payment Success Rate:** >95%
- **Time to Confirmation:** <5 minutes average

### Monitoring Alerts

- Webhook failure rate >1%
- Webhook latency >5 seconds
- No successful webhooks for 10 minutes
- High retry rate (>0.5 retries/sec)
- API error rate >1%

---

## Support & Maintenance

### Support Channels

- **Email:** support@onepay.ng
- **Slack:** #onepay-voicepay-integration
- **Phone:** [To be provided]
- **On-call:** [Rotation schedule]

### Maintenance Windows

- **Planned Maintenance:** Notify VoicePay 48 hours in advance
- **Emergency Maintenance:** Notify immediately
- **Maintenance Window:** Sundays 2:00 AM - 4:00 AM WAT

### SLA

- **Uptime:** 99.9%
- **Response Time:** <1 hour for critical issues
- **Resolution Time:** <4 hours for critical issues

### Incident Response

1. **Detection:** Monitoring alerts or user report
2. **Assessment:** Determine severity and impact
3. **Communication:** Notify VoicePay team
4. **Investigation:** Identify root cause
5. **Resolution:** Implement fix
6. **Verification:** Confirm issue resolved
7. **Post-mortem:** Document lessons learned

---

## Appendix

### A. Environment Variables Reference

```bash
# VoicePay Integration
VOICEPAY_WEBHOOK_URL=https://voicepay.ng/api/webhooks/onepay
VOICEPAY_WEBHOOK_SECRET=<32+ character secret>
VOICEPAY_API_KEY=<VoicePay API key>
VOICEPAY_WEBHOOK_URL_SANDBOX=https://sandbox.voicepay.ng/api/webhooks/onepay
VOICEPAY_WEBHOOK_SECRET_SANDBOX=<sandbox secret>
VOICEPAY_WEBHOOK_TIMEOUT_SECS=10
VOICEPAY_WEBHOOK_MAX_RETRIES=3
VOICEPAY_WEBHOOK_ENABLED=true
```

### B. API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/payment-links` | POST | Create payment link |
| `/api/v1/payment-links/{tx_ref}` | GET | Check payment status |
| `/api/v1/webhooks/korapay` | POST | Receive KoraPay webhooks |

### C. Webhook Events

| Event | Description | Trigger |
|-------|-------------|---------|
| `payment.verified` | Payment confirmed | KoraPay confirms transfer |

### D. Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `UNAUTHORIZED` | Invalid API key | 401 |
| `VALIDATION_ERROR` | Invalid request | 400 |
| `NOT_FOUND` | Transaction not found | 404 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `INTERNAL_ERROR` | Server error | 500 |

### E. Useful Commands

```bash
# Generate webhook secret
python -c "import secrets; print(secrets.token_hex(32))"

# Generate API key
python scripts/generate_voicepay_api_key.py --email voicepay@example.com

# Run tests
pytest tests/unit/test_voicepay*.py -v
pytest tests/integration/test_voicepay*.py -v

# Check configuration
python -c "from config import Config; Config.validate()"

# View logs
tail -f /var/log/onepay/app.log | grep VoicePay

# Check metrics
curl http://localhost:9090/metrics | grep voicepay
```

### F. Contact Information

**OnePay Team:**
- Technical Lead: [Name, Email]
- DevOps: [Name, Email]
- Support: support@onepay.ng

**VoicePay Team:**
- Technical Lead: [Name, Email]
- Integration Contact: [Name, Email]
- Support: support@voicepay.ng

---

## Document Version

**Version:** 1.0  
**Last Updated:** April 1, 2026  
**Status:** Ready for Implementation  
**Author:** OnePay Engineering Team

---

## Next Steps

After reviewing this plan:

1. **Approval:** Get stakeholder approval
2. **Timeline:** Confirm 9-14 day timeline
3. **Resources:** Assign team members to tasks
4. **Kickoff:** Schedule kickoff meeting
5. **Execution:** Begin Phase 1 implementation

**Ready to execute tasks?** Start with Phase 1, Task 1.1.

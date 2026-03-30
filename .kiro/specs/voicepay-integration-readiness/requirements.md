# Requirements Document: VoicePay Integration Readiness

## Introduction

OnePay is a payment platform that currently uses session-based authentication (Flask-Login with cookies) designed for browser-based interactions. VoicePay is a WhatsApp-based payment service that needs to integrate with OnePay via machine-to-machine (M2M) API calls. This feature adds the necessary authentication, security, and webhook capabilities to enable VoicePay and other external services to integrate with OnePay without requiring browser sessions.

The readiness assessment identified 8 gaps, with 3 critical blockers that must be implemented for M2M integration to work. This requirements document covers all critical and high-priority features needed for production-ready integration.

## Glossary

- **API_Key**: A secret token used to authenticate machine-to-machine requests without browser sessions
- **API_Key_Manager**: The system component responsible for creating, storing, validating, and revoking API keys
- **Authentication_System**: The system that verifies the identity of users or services making requests
- **CSRF_Validator**: The system component that validates Cross-Site Request Forgery tokens
- **Webhook_Receiver**: The system component that receives and processes inbound webhook notifications from external services
- **HMAC_Verifier**: The system component that validates HMAC-SHA256 signatures on webhook payloads
- **Rate_Limiter**: The system component that enforces request rate limits to prevent abuse
- **M2M_Client**: A machine-to-machine client (like VoicePay) that makes API requests without a browser
- **Session_Auth**: Session-based authentication using cookies (current OnePay authentication method)
- **Payment_Link**: A unique URL that allows customers to pay a specific amount
- **Transaction**: A payment record in OnePay's database
- **Merchant**: A OnePay user who creates payment links and receives payments
- **Virtual_Account**: A temporary bank account number generated for a specific payment

## Requirements

### Requirement 1: API Key Authentication

**User Story:** As a VoicePay developer, I want to authenticate API requests using an API key, so that I can integrate with OnePay without maintaining browser sessions.

#### Database Schema

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 hash of API key
    key_prefix VARCHAR(20) NOT NULL,        -- First 8 chars for identification
    name VARCHAR(100),                      -- User-friendly name like "VoicePay Production"
    scopes TEXT,                            -- JSON array of allowed operations
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_api_keys_user_id (user_id),
    INDEX idx_api_keys_key_hash (key_hash)
);
```

#### API Key Format

- **Format:** `onepay_live_{64-character-hex-string}`
- **Example:** `onepay_live_a1b2c3d4e5f6...` (total 76 characters)
- **Entropy:** 256 bits (64 hex characters = 32 bytes)
- **Generation:** Use `secrets.token_hex(32)` for cryptographically secure random generation

#### Storage Format

- **key_hash:** SHA256 hash of the full API key (never store plaintext)
- **key_prefix:** First 8 characters of the API key (e.g., "onepay_l") for display purposes
- **Hashing:** `hashlib.sha256(api_key.encode('utf-8')).hexdigest()`

#### Authentication Flow

```python
# Request format
Authorization: Bearer onepay_live_a1b2c3d4e5f6...

# Validation steps:
# 1. Extract API key from Authorization header
# 2. Compute SHA256 hash of provided key
# 3. Query database for matching key_hash
# 4. Use hmac.compare_digest() for constant-time comparison
# 5. Check is_active and expires_at
# 6. Update last_used_at timestamp
# 7. Set current_user_id() from api_key.user_id
```

#### Acceptance Criteria

1. THE API_Key_Manager SHALL generate API keys with the format "onepay_live_{64-character-hex-string}"
2. WHEN an API key is generated, THE API_Key_Manager SHALL store only the SHA256 hash of the key in the database
3. THE API_Key_Manager SHALL store the first 8 characters of the API key as a prefix for identification
4. WHEN an API request includes an Authorization header with format "Bearer {api_key}", THE Authentication_System SHALL validate the API key
5. WHEN an API key is validated, THE Authentication_System SHALL perform constant-time comparison of the hash to prevent timing attacks using hmac.compare_digest()
6. IF an API key is valid, THEN THE Authentication_System SHALL set the authenticated user context for the request
7. IF an API key is invalid, THEN THE Authentication_System SHALL return HTTP 401 with error code "INVALID_API_KEY"
8. WHEN an API key is used, THE API_Key_Manager SHALL update the last_used_at timestamp
9. IF an API key has an expires_at timestamp in the past, THEN THE Authentication_System SHALL reject the key with error code "API_KEY_EXPIRED"
10. IF an API key has is_active set to false, THEN THE Authentication_System SHALL reject the key with error code "API_KEY_REVOKED"

#### Integration Points

- **File:** `core/auth.py` - Add `is_api_key_authenticated()` and `get_api_key_id()` helpers
- **File:** `services/api_auth.py` (NEW) - API key generation and validation logic
- **File:** `models/api_key.py` (NEW) - SQLAlchemy model for api_keys table
- **File:** `alembic/versions/YYYYMMDD_add_api_keys.py` (NEW) - Database migration

### Requirement 2: API Key Management Interface

**User Story:** As a merchant, I want to create and manage API keys through the settings page, so that I can control which services can access my OnePay account.

#### UI Location

- **Page:** Settings page (`/settings` route in `blueprints/payments.py`)
- **Template:** `templates/settings.html` (extend existing template)
- **Section:** Add new "API Keys" section below webhook settings

#### UI Components

**API Keys List Table:**
```html
<table class="api-keys-table">
  <thead>
    <tr>
      <th>Name</th>
      <th>Key Prefix</th>
      <th>Scopes</th>
      <th>Last Used</th>
      <th>Created</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <!-- Display: name, key_prefix (e.g., "onepay_l..."), scopes, last_used_at, created_at -->
    <!-- Actions: Revoke button -->
  </tbody>
</table>
```

**Create API Key Button:**
- Label: "Create API Key"
- Opens modal dialog with form

**Create API Key Modal:**
```html
<form id="create-api-key-form">
  <label>Name (optional):
    <input type="text" name="name" placeholder="VoicePay Production" maxlength="100">
  </label>
  
  <label>Scopes (select at least one):
    <input type="checkbox" name="scopes" value="payments:create"> Create payment links
    <input type="checkbox" name="scopes" value="payments:read"> Read payment status
    <input type="checkbox" name="scopes" value="webhooks:receive"> Receive webhooks
  </label>
  
  <label>Expiration (optional):
    <input type="date" name="expires_at">
  </label>
  
  <button type="submit">Generate API Key</button>
</form>
```

**Show API Key Once Dialog:**
```html
<div class="api-key-display-modal">
  <h3>⚠️ Save Your API Key</h3>
  <p>This is the only time you'll see this key. Copy it now and store it securely.</p>
  
  <div class="api-key-value">
    <code id="api-key-text">onepay_live_a1b2c3d4e5f6...</code>
    <button onclick="copyToClipboard()">Copy</button>
  </div>
  
  <p class="warning">
    ⚠️ This key cannot be retrieved again. If you lose it, you'll need to create a new one.
  </p>
  
  <button onclick="closeModal()">I've Saved My Key</button>
</div>
```

**Revoke Confirmation Dialog:**
```html
<div class="revoke-confirmation-modal">
  <h3>Revoke API Key?</h3>
  <p>Key: <code>{key_prefix}...</code> ({name})</p>
  <p>This action cannot be undone. Any services using this key will immediately lose access.</p>
  
  <button onclick="confirmRevoke()">Yes, Revoke</button>
  <button onclick="cancelRevoke()">Cancel</button>
</div>
```

#### API Endpoints

**List API Keys:**
```
GET /api/settings/api-keys
Authorization: Session (current_user_id)
X-CSRF-Token: {csrf_token}

Response 200:
{
  "success": true,
  "api_keys": [
    {
      "id": 1,
      "name": "VoicePay Production",
      "key_prefix": "onepay_l",
      "scopes": ["payments:create", "payments:read"],
      "last_used_at": "2026-03-29T10:30:00Z",
      "created_at": "2026-03-01T08:00:00Z",
      "expires_at": null,
      "is_active": true
    }
  ]
}
```

**Create API Key:**
```
POST /api/settings/api-keys
Content-Type: application/json
Authorization: Session (current_user_id)
X-CSRF-Token: {csrf_token}

Request:
{
  "name": "VoicePay Production",
  "scopes": ["payments:create", "payments:read"],
  "expires_at": "2027-03-01T00:00:00Z"  // optional
}

Response 201:
{
  "success": true,
  "api_key": "onepay_live_a1b2c3d4e5f6...",  // ONLY returned once
  "key_id": 1,
  "key_prefix": "onepay_l",
  "message": "API key created. Save it now - you won't see it again."
}
```

**Revoke API Key:**
```
DELETE /api/settings/api-keys/{key_id}
Content-Type: application/json
Authorization: Session (current_user_id)
X-CSRF-Token: {csrf_token}

Response 200:
{
  "success": true,
  "message": "API key revoked successfully"
}

Response 404:
{
  "success": false,
  "error": "API key not found",
  "code": "NOT_FOUND"
}
```

#### Acceptance Criteria

1. WHEN a merchant navigates to the settings page, THE API_Key_Manager SHALL display all active API keys with their prefix, name, scopes, and last_used_at timestamp
2. WHEN a merchant clicks "Create API Key", THE API_Key_Manager SHALL generate a new API key and display the full key exactly once
3. THE API_Key_Manager SHALL display a warning that the API key cannot be retrieved again after the dialog is closed
4. WHEN creating an API key, THE API_Key_Manager SHALL allow the merchant to specify a human-readable name
5. WHEN creating an API key, THE API_Key_Manager SHALL allow the merchant to select scopes from: "payments:create", "payments:read", "webhooks:receive"
6. WHERE an expiration date is specified, THE API_Key_Manager SHALL store the expires_at timestamp
7. WHEN a merchant clicks "Revoke" on an API key, THE API_Key_Manager SHALL set is_active to false
8. THE API_Key_Manager SHALL require CSRF token validation for all API key management operations
9. THE API_Key_Manager SHALL never display the full API key after initial creation (only prefix)
10. THE API_Key_Manager SHALL provide a "Copy to Clipboard" button in the show-once dialog

#### Integration Points

- **File:** `blueprints/payments.py` - Add routes for `/api/settings/api-keys`
- **File:** `templates/settings.html` - Add API Keys section
- **File:** `static/js/settings.js` (NEW) - JavaScript for API key management UI

### Requirement 3: CSRF Bypass for API Key Authentication

**User Story:** As a VoicePay developer, I want API key authenticated requests to skip CSRF validation, so that I don't need to obtain CSRF tokens for M2M communication.

#### Implementation Details

**Modify CSRF validation in all POST endpoints:**

```python
# Current pattern (blueprints/payments.py, line 280):
csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
if not is_valid_csrf_token(csrf_header):
    return error("CSRF validation failed", "CSRF_ERROR", 403)

# New pattern:
if not is_api_key_authenticated():
    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)
```

**Helper function in core/auth.py:**

```python
def is_api_key_authenticated() -> bool:
    """Return True if current request is authenticated via API key."""
    return hasattr(g, 'api_key_id') and g.api_key_id is not None

def get_api_key_id() -> int | None:
    """Return the API key ID for the current request, or None."""
    return getattr(g, 'api_key_id', None)
```

**Middleware to check API key before CSRF:**

```python
# File: core/api_auth_middleware.py (NEW)

@app.before_request
def check_api_key_auth():
    """Check for API key authentication before processing request."""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate API key
        from services.api_auth import validate_api_key
        user_id, key_id = validate_api_key(api_key)
        
        if user_id:
            # Set API key authentication context
            g.api_key_id = key_id
            g.api_key_user_id = user_id
            # Set session-compatible context for existing code
            session['user_id'] = user_id
            session['username'] = get_username_by_id(user_id)
```

#### Affected Endpoints

All POST endpoints that currently require CSRF validation:

1. `/api/payments/link` (create payment link)
2. `/api/payments/reissue/<tx_ref>` (reissue expired link)
3. `/api/settings/webhook` (update webhook settings)
4. `/api/settings/api-keys` (create API key)
5. `/api/settings/api-keys/{key_id}` (revoke API key - DELETE method)

#### Acceptance Criteria

1. WHEN a request is authenticated via API key, THE CSRF_Validator SHALL skip CSRF token validation
2. WHEN a request is authenticated via session, THE CSRF_Validator SHALL require CSRF token validation
3. THE CSRF_Validator SHALL check for API key authentication before checking for CSRF tokens
4. FOR ALL endpoints that currently require CSRF validation, the CSRF bypass SHALL apply when API key authenticated
5. THE Authentication_System SHALL set g.api_key_id and g.api_key_user_id when API key is valid
6. THE Authentication_System SHALL maintain backward compatibility with session-based authentication

#### Integration Points

- **File:** `core/auth.py` - Add `is_api_key_authenticated()` and `get_api_key_id()` helpers
- **File:** `core/api_auth_middleware.py` (NEW) - API key authentication middleware
- **File:** `blueprints/payments.py` - Modify CSRF checks in all POST endpoints
- **File:** `blueprints/auth.py` - No changes needed (login/register remain session-only)

### Requirement 4: Inbound Webhook Receiver

**User Story:** As a VoicePay developer, I want to send payment status updates to OnePay via webhook, so that OnePay knows when a payment has been confirmed through VoicePay.

#### Endpoint Specification

**URL:** `/api/webhooks/payment-status`  
**Method:** POST  
**Authentication:** HMAC signature verification (no API key or session required)

#### Request Format

**Headers:**
```
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac_hex_digest>
X-Webhook-Timestamp: 1711234567  # Unix timestamp
```

**Body:**
```json
{
  "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
  "status": "VERIFIED",
  "timestamp": 1711234567,
  "amount": "1000.00",
  "currency": "NGN"
}
```

#### HMAC Signature Verification

**Algorithm:** HMAC-SHA256  
**Secret:** Environment variable `INBOUND_WEBHOOK_SECRET`  
**Payload:** Raw request body (bytes)

```python
# Signature computation (VoicePay side):
import hmac
import hashlib

payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
signature = hmac.new(
    INBOUND_WEBHOOK_SECRET.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

headers = {
    'X-Webhook-Signature': f'sha256={signature}',
    'X-Webhook-Timestamp': str(int(time.time()))
}
```

```python
# Signature verification (OnePay side):
import hmac
import hashlib

def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify HMAC signature using constant-time comparison."""
    if not signature_header.startswith('sha256='):
        return False
    
    provided_signature = signature_header[7:]  # Remove "sha256=" prefix
    
    expected_signature = hmac.new(
        Config.INBOUND_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, provided_signature)
```

#### Response Formats

**Success (200):**
```json
{
  "success": true,
  "message": "Payment status updated",
  "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
  "status": "VERIFIED"
}
```

**Invalid Signature (401):**
```json
{
  "success": false,
  "error": "Invalid webhook signature",
  "code": "INVALID_SIGNATURE"
}
```

**Transaction Not Found (404):**
```json
{
  "success": false,
  "error": "Transaction not found",
  "code": "TRANSACTION_NOT_FOUND"
}
```

**Invalid Payload (400):**
```json
{
  "success": false,
  "error": "Invalid JSON payload",
  "code": "INVALID_PAYLOAD"
}
```

**Webhook Too Old (401):**
```json
{
  "success": false,
  "error": "Webhook timestamp too old (>5 minutes)",
  "code": "WEBHOOK_TOO_OLD"
}
```

**Webhook Already Processed (409):**
```json
{
  "success": false,
  "error": "Webhook already processed",
  "code": "WEBHOOK_ALREADY_PROCESSED"
}
```

#### Transaction Status Mapping

| Webhook Status | OnePay TransactionStatus | Action |
|----------------|-------------------------|--------|
| VERIFIED | TransactionStatus.VERIFIED | Set verified_at, trigger invoice sync |
| FAILED | TransactionStatus.FAILED | Update status only |
| EXPIRED | TransactionStatus.EXPIRED | Update status only |

#### Implementation Details

```python
# File: blueprints/webhooks.py (NEW)

from flask import Blueprint, request, jsonify
from database import get_db
from models.transaction import Transaction, TransactionStatus
from services.webhook import sync_invoice_on_transaction_update
from core.audit import log_event
from core.ip import client_ip
import hmac
import hashlib
import time

webhooks_bp = Blueprint("webhooks", __name__)

@webhooks_bp.route("/api/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates from external services (e.g., VoicePay)."""
    
    # 1. Verify HMAC signature
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        return jsonify({
            "success": False,
            "error": "Missing X-Webhook-Signature header",
            "code": "MISSING_SIGNATURE"
        }), 401
    
    if not verify_webhook_signature(request.data, signature):
        log_event(None, "webhook.inbound.invalid_signature", 
                  ip_address=client_ip(), detail={"signature": signature[:20]})
        return jsonify({
            "success": False,
            "error": "Invalid webhook signature",
            "code": "INVALID_SIGNATURE"
        }), 401
    
    # 2. Verify timestamp (replay protection)
    timestamp_header = request.headers.get("X-Webhook-Timestamp")
    if timestamp_header:
        try:
            webhook_time = int(timestamp_header)
            current_time = int(time.time())
            
            # Reject if older than 5 minutes
            if current_time - webhook_time > 300:
                return jsonify({
                    "success": False,
                    "error": "Webhook timestamp too old (>5 minutes)",
                    "code": "WEBHOOK_TOO_OLD"
                }), 401
            
            # Reject if more than 1 minute in future
            if webhook_time - current_time > 60:
                return jsonify({
                    "success": False,
                    "error": "Webhook timestamp in future",
                    "code": "WEBHOOK_TIMESTAMP_INVALID"
                }), 401
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid timestamp format",
                "code": "INVALID_TIMESTAMP"
            }), 400
    
    # 3. Parse payload
    try:
        data = request.get_json()
    except Exception:
        return jsonify({
            "success": False,
            "error": "Invalid JSON payload",
            "code": "INVALID_PAYLOAD"
        }), 400
    
    tx_ref = data.get("tx_ref")
    status = data.get("status")
    
    # 4. Validate tx_ref format
    if not tx_ref or not tx_ref.startswith("ONEPAY-"):
        return jsonify({
            "success": False,
            "error": "Invalid tx_ref format",
            "code": "INVALID_TX_REF"
        }), 400
    
    # 5. Validate status
    valid_statuses = ["VERIFIED", "FAILED", "EXPIRED"]
    if status not in valid_statuses:
        return jsonify({
            "success": False,
            "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            "code": "INVALID_STATUS"
        }), 400
    
    # 6. Update transaction
    with get_db() as db:
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref
        ).first()
        
        if not transaction:
            return jsonify({
                "success": False,
                "error": "Transaction not found",
                "code": "TRANSACTION_NOT_FOUND"
            }), 404
        
        # Map webhook status to TransactionStatus enum
        status_map = {
            "VERIFIED": TransactionStatus.VERIFIED,
            "FAILED": TransactionStatus.FAILED,
            "EXPIRED": TransactionStatus.EXPIRED
        }
        
        old_status = transaction.status
        transaction.status = status_map[status]
        
        if status == "VERIFIED":
            transaction.verified_at = datetime.now(timezone.utc)
        
        db.flush()
        
        # Trigger invoice synchronization
        sync_invoice_on_transaction_update(db, transaction)
        
        # Log audit event
        log_event(db, "webhook.inbound.processed", 
                  user_id=transaction.user_id, tx_ref=tx_ref,
                  detail={"old_status": old_status.value, "new_status": status})
        
        logger.info("Inbound webhook processed | tx_ref=%s status=%s", tx_ref, status)
        
        return jsonify({
            "success": True,
            "message": "Payment status updated",
            "tx_ref": tx_ref,
            "status": status
        }), 200
```

#### Acceptance Criteria

1. THE Webhook_Receiver SHALL expose an endpoint at "/api/webhooks/payment-status" accepting POST requests
2. WHEN a webhook is received, THE HMAC_Verifier SHALL validate the X-Webhook-Signature header
3. THE HMAC_Verifier SHALL compute HMAC-SHA256 of the raw request body using the shared webhook secret
4. THE HMAC_Verifier SHALL use constant-time comparison to prevent timing attacks
5. IF the signature is invalid, THEN THE Webhook_Receiver SHALL return HTTP 401 with error code "INVALID_SIGNATURE"
6. IF the signature is valid, THEN THE Webhook_Receiver SHALL parse the JSON payload
7. THE Webhook_Receiver SHALL extract tx_ref and status from the payload
8. THE Webhook_Receiver SHALL validate that tx_ref matches the format "ONEPAY-{16-hex-chars}"
9. THE Webhook_Receiver SHALL validate that status is one of: "VERIFIED", "FAILED", "EXPIRED"
10. WHEN a valid webhook is received, THE Webhook_Receiver SHALL update the transaction status in the database
11. WHEN a transaction is updated to VERIFIED, THE Webhook_Receiver SHALL set verified_at to the current UTC timestamp
12. WHEN a transaction status is updated, THE Webhook_Receiver SHALL trigger the invoice synchronization process
13. IF the tx_ref does not exist, THEN THE Webhook_Receiver SHALL return HTTP 404 with error code "TRANSACTION_NOT_FOUND"
14. IF the webhook payload is invalid JSON, THEN THE Webhook_Receiver SHALL return HTTP 400 with error code "INVALID_PAYLOAD"
15. THE Webhook_Receiver SHALL log all webhook attempts with tx_ref, status, and signature validation result

#### Integration Points

- **File:** `blueprints/webhooks.py` (NEW) - Inbound webhook receiver
- **File:** `services/webhook.py` - Reuse `sync_invoice_on_transaction_update()` function (already exists)
- **File:** `app.py` - Register webhooks_bp blueprint
- **File:** `config.py` - Add INBOUND_WEBHOOK_SECRET configuration

### Requirement 5: Webhook Secret Configuration

**User Story:** As a system administrator, I want to configure separate webhook secrets for inbound and outbound webhooks, so that compromising one secret doesn't compromise both directions.

#### Environment Variables

**Required Variables:**

```bash
# .env file
INBOUND_WEBHOOK_SECRET=<64-character-hex-string>  # For receiving webhooks FROM VoicePay
WEBHOOK_SECRET=<64-character-hex-string>          # For sending webhooks TO merchants (existing)
HMAC_SECRET=<64-character-hex-string>             # For general HMAC operations (existing)
```

**Generation Command:**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### Validation Rules

**Startup Validation (in config.py or app.py):**

```python
def validate_webhook_secrets():
    """Validate webhook secrets at application startup."""
    
    # 1. Check INBOUND_WEBHOOK_SECRET exists
    inbound_secret = os.getenv('INBOUND_WEBHOOK_SECRET')
    if not inbound_secret:
        raise ValueError("INBOUND_WEBHOOK_SECRET environment variable is required")
    
    # 2. Check minimum length (32 characters = 128 bits)
    if len(inbound_secret) < 32:
        raise ValueError("INBOUND_WEBHOOK_SECRET must be at least 32 characters long")
    
    # 3. Check for placeholder values
    placeholder_values = ['change-this', 'changeme', 'secret', 'password', 'test']
    if any(placeholder in inbound_secret.lower() for placeholder in placeholder_values):
        raise ValueError("INBOUND_WEBHOOK_SECRET contains placeholder text - use a secure random value")
    
    # 4. Check uniqueness (different from other secrets)
    webhook_secret = os.getenv('WEBHOOK_SECRET')
    hmac_secret = os.getenv('HMAC_SECRET')
    
    if inbound_secret == webhook_secret:
        raise ValueError("INBOUND_WEBHOOK_SECRET must be different from WEBHOOK_SECRET")
    
    if inbound_secret == hmac_secret:
        raise ValueError("INBOUND_WEBHOOK_SECRET must be different from HMAC_SECRET")
    
    logger.info("Webhook secrets validated successfully")

# Call at startup
validate_webhook_secrets()
```

#### Configuration File Updates

**File: config.py**

```python
class Config:
    # Existing secrets
    HMAC_SECRET = os.getenv("HMAC_SECRET", "change-this-in-production")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or HMAC_SECRET
    
    # NEW: Inbound webhook secret
    INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET")
    
    # Validate at class initialization
    @classmethod
    def validate(cls):
        """Validate configuration at startup."""
        if not cls.INBOUND_WEBHOOK_SECRET:
            raise ValueError("INBOUND_WEBHOOK_SECRET required")
        
        if len(cls.INBOUND_WEBHOOK_SECRET) < 32:
            raise ValueError("INBOUND_WEBHOOK_SECRET must be at least 32 characters")
        
        if 'change-this' in cls.INBOUND_WEBHOOK_SECRET.lower():
            raise ValueError("INBOUND_WEBHOOK_SECRET contains placeholder text")
        
        if cls.INBOUND_WEBHOOK_SECRET == cls.WEBHOOK_SECRET:
            raise ValueError("INBOUND_WEBHOOK_SECRET must differ from WEBHOOK_SECRET")
        
        if cls.INBOUND_WEBHOOK_SECRET == cls.HMAC_SECRET:
            raise ValueError("INBOUND_WEBHOOK_SECRET must differ from HMAC_SECRET")
```

**File: .env.example**

```bash
# Webhook Secrets
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"

# Secret for receiving webhooks FROM external services (VoicePay)
INBOUND_WEBHOOK_SECRET=change-this-to-64-char-hex-string

# Secret for sending webhooks TO merchants (existing)
WEBHOOK_SECRET=change-this-to-64-char-hex-string

# General HMAC secret (existing)
HMAC_SECRET=change-this-to-64-char-hex-string
```

#### Acceptance Criteria

1. THE Authentication_System SHALL read the inbound webhook secret from environment variable "INBOUND_WEBHOOK_SECRET"
2. IF INBOUND_WEBHOOK_SECRET is not set, THEN THE Authentication_System SHALL fail startup with error "INBOUND_WEBHOOK_SECRET required"
3. THE Authentication_System SHALL validate that INBOUND_WEBHOOK_SECRET is at least 32 characters long
4. THE Authentication_System SHALL validate that INBOUND_WEBHOOK_SECRET does not contain the placeholder text "change-this"
5. THE Authentication_System SHALL validate that INBOUND_WEBHOOK_SECRET is different from HMAC_SECRET and WEBHOOK_SECRET
6. THE Authentication_System SHALL log successful validation at startup
7. THE Authentication_System SHALL fail fast (exit with error) if validation fails

#### Integration Points

- **File:** `config.py` - Add INBOUND_WEBHOOK_SECRET and validation
- **File:** `app.py` - Call Config.validate() at startup
- **File:** `.env.example` - Document INBOUND_WEBHOOK_SECRET
- **File:** `docs/DEPLOYMENT.md` - Add webhook secret generation instructions

### Requirement 6: API Rate Limiting

**User Story:** As a system administrator, I want separate rate limits for API key authenticated requests, so that M2M clients can make more requests than web UI users without hitting limits.

#### Rate Limit Configuration

**API Key Limits (Higher):**
- Payment link creation: 100 requests per 60 seconds per API key
- Payment status check: 200 requests per 60 seconds per API key
- Payment history: 100 requests per 60 seconds per API key

**Session Limits (Lower):**
- Payment link creation: 10 requests per 60 seconds per user
- Payment status check: 100 requests per 60 seconds per user
- Payment history: 20 requests per 60 seconds per user

#### Rate Limit Key Format

```python
# API key authenticated requests
rate_key = f"api_link:{api_key_id}"           # For payment link creation
rate_key = f"api_status:{api_key_id}"         # For status checks
rate_key = f"api_history:{api_key_id}"        # For history

# Session authenticated requests
rate_key = f"link:user:{user_id}"             # For payment link creation (existing)
rate_key = f"status:{user_id}"                # For status checks (existing)
rate_key = f"history:{user_id}"               # For history
```

#### Implementation Pattern

**File: blueprints/payments.py**

```python
# Example: create_payment_link() endpoint

@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    # ... authentication checks ...
    
    with get_db() as db:
        # Determine rate limit based on authentication method
        if is_api_key_authenticated():
            rate_key = f"api_link:{get_api_key_id()}"
            rate_limit = 100  # Higher limit for API keys
        else:
            rate_key = f"link:user:{current_user_id()}"
            rate_limit = 10   # Lower limit for web UI
        
        if not check_rate_limit(db, rate_key, limit=rate_limit, window_secs=60):
            return rate_limited()
        
        # ... rest of endpoint logic ...
```

```python
# Example: transaction_status() endpoint

@payments_bp.route("/api/payments/status/<tx_ref>", methods=["GET"])
def transaction_status(tx_ref):
    # ... authentication checks ...
    
    with get_db() as db:
        # Determine rate limit based on authentication method
        if is_api_key_authenticated():
            rate_key = f"api_status:{get_api_key_id()}"
            rate_limit = 200  # Higher limit for API keys
        else:
            rate_key = f"status:{current_user_id()}"
            rate_limit = 100  # Lower limit for web UI
        
        if not check_rate_limit(db, rate_key, limit=rate_limit, window_secs=60):
            return rate_limited()
        
        # ... rest of endpoint logic ...
```

#### Rate Limit Response Format

**HTTP 429 Too Many Requests:**

```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 45  // seconds until window resets
}
```

**Headers:**

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711234567  // Unix timestamp
Retry-After: 45  // seconds
```

#### Configuration File Updates

**File: config.py**

```python
class Config:
    # Existing rate limits (for web UI)
    RATE_LIMIT_LINK_CREATE = 10      # per 60 seconds
    RATE_LIMIT_STATUS_CHECK = 100    # per 60 seconds
    
    # NEW: API key rate limits (higher)
    RATE_LIMIT_API_LINK_CREATE = 100    # per 60 seconds
    RATE_LIMIT_API_STATUS_CHECK = 200   # per 60 seconds
    RATE_LIMIT_API_HISTORY = 100        # per 60 seconds
```

#### Acceptance Criteria

1. WHEN a payment link creation request is authenticated via API key, THE Rate_Limiter SHALL apply a limit of 100 requests per 60 seconds per API key
2. WHEN a payment link creation request is authenticated via session, THE Rate_Limiter SHALL apply a limit of 10 requests per 60 seconds per user
3. THE Rate_Limiter SHALL use the rate limit key format "api_link:{api_key_id}" for API key requests
4. THE Rate_Limiter SHALL use the rate limit key format "link:user:{user_id}" for session requests
5. WHEN a payment status check request is authenticated via API key, THE Rate_Limiter SHALL apply a limit of 200 requests per 60 seconds per API key
6. WHEN a payment status check request is authenticated via session, THE Rate_Limiter SHALL apply a limit of 100 requests per 60 seconds per user
7. WHEN rate limit is exceeded, THE Rate_Limiter SHALL return HTTP 429 with "RATE_LIMIT_EXCEEDED" error code
8. THE Rate_Limiter SHALL include X-RateLimit-* headers in all responses
9. THE Rate_Limiter SHALL include Retry-After header in 429 responses

#### Integration Points

- **File:** `blueprints/payments.py` - Update rate limiting in all endpoints
- **File:** `services/rate_limiter.py` - Already supports flexible rate limits (no changes needed)
- **File:** `config.py` - Add API rate limit constants
- **File:** `core/responses.py` - Update rate_limited() to include headers

### Requirement 7: API Versioning

**User Story:** As a VoicePay developer, I want API endpoints to include a version prefix, so that OnePay can make breaking changes without affecting my integration.

#### URL Structure

**Current (Unversioned):**
- `/api/payments/link`
- `/api/payments/status/<tx_ref>`
- `/api/payments/history`
- `/api/webhooks/payment-status`

**New (Versioned):**
- `/api/v1/payments/link`
- `/api/v1/payments/status/<tx_ref>`
- `/api/v1/payments/history`
- `/api/v1/webhooks/payment-status`

#### Implementation Details

**Blueprint Registration:**

```python
# File: app.py

# Register blueprints with version prefix
app.register_blueprint(payments_bp, url_prefix="/api/v1")
app.register_blueprint(webhooks_bp, url_prefix="/api/v1")

# Maintain backward compatibility with unversioned endpoints
app.register_blueprint(payments_bp, url_prefix="/api")
app.register_blueprint(webhooks_bp, url_prefix="/api")
```

**Deprecation Warning Middleware:**

```python
# File: core/api_versioning.py (NEW)

@app.before_request
def check_api_version():
    """Log deprecation warning for unversioned API requests."""
    path = request.path
    
    # Check if this is an API request without version
    if path.startswith('/api/') and not path.startswith('/api/v'):
        logger.warning(
            "Deprecated unversioned API endpoint used | path=%s ip=%s user_agent=%s",
            path, client_ip(), request.headers.get('User-Agent', 'unknown')
        )
        
        # Add deprecation header to response
        @after_this_request
        def add_deprecation_header(response):
            response.headers['X-API-Deprecation'] = 'Unversioned endpoints deprecated. Use /api/v1/* instead.'
            response.headers['X-API-Version'] = 'v1'
            return response
```

**Response Headers:**

All API responses include:
```
X-API-Version: v1
```

Unversioned endpoint responses also include:
```
X-API-Deprecation: Unversioned endpoints deprecated. Use /api/v1/* instead.
```

#### Acceptance Criteria

1. THE Authentication_System SHALL register all API endpoints under the URL prefix "/api/v1"
2. THE Authentication_System SHALL continue to support unversioned endpoints "/api/*" for backward compatibility
3. WHEN a request is made to an unversioned endpoint, THE Authentication_System SHALL log a deprecation warning
4. THE Authentication_System SHALL include an "X-API-Version: v1" header in all API responses
5. THE Authentication_System SHALL include an "X-API-Deprecation" header in responses to unversioned endpoints
6. THE Authentication_System SHALL log the user agent and IP address for unversioned API requests

#### Integration Points

- **File:** `app.py` - Register blueprints with version prefix
- **File:** `core/api_versioning.py` (NEW) - Deprecation warning middleware
- **File:** `docs/API.md` (NEW) - API documentation with versioned endpoints

### Requirement 8: API Key Scope Enforcement

**User Story:** As a merchant, I want to restrict API keys to specific operations, so that a compromised key has limited impact.

#### Scope Definitions

**Available Scopes:**

| Scope | Description | Allowed Endpoints |
|-------|-------------|-------------------|
| `payments:create` | Create payment links | POST /api/v1/payments/link |
| `payments:read` | Read payment status and history | GET /api/v1/payments/status/<tx_ref><br>GET /api/v1/payments/history |
| `webhooks:receive` | Receive inbound webhooks | POST /api/v1/webhooks/payment-status |

#### Scope Storage Format

**Database Column:** `api_keys.scopes` (TEXT)  
**Format:** JSON array of scope strings

```sql
-- Example values:
'["payments:create", "payments:read"]'
'["payments:create"]'
'["payments:create", "payments:read", "webhooks:receive"]'
```

#### Scope Validation Logic

```python
# File: services/api_auth.py

def check_scope(api_key_id: int, required_scope: str) -> bool:
    """Check if API key has required scope."""
    with get_db() as db:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        
        if not api_key:
            return False
        
        # Parse scopes from JSON
        import json
        try:
            scopes = json.loads(api_key.scopes) if api_key.scopes else []
        except json.JSONDecodeError:
            logger.error("Invalid scopes JSON for API key %d", api_key_id)
            return False
        
        return required_scope in scopes

def require_scope(scope: str):
    """Decorator to enforce scope requirement on endpoints."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_api_key_authenticated():
                # Session-authenticated requests bypass scope checks
                return f(*args, **kwargs)
            
            api_key_id = get_api_key_id()
            if not check_scope(api_key_id, scope):
                return jsonify({
                    "success": False,
                    "error": f"API key missing required scope: {scope}",
                    "code": "INSUFFICIENT_SCOPE"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

#### Endpoint Scope Requirements

**File: blueprints/payments.py**

```python
@payments_bp.route("/api/v1/payments/link", methods=["POST"])
@require_scope("payments:create")
def create_payment_link():
    # ... endpoint logic ...

@payments_bp.route("/api/v1/payments/status/<tx_ref>", methods=["GET"])
@require_scope("payments:read")
def transaction_status(tx_ref):
    # ... endpoint logic ...

@payments_bp.route("/api/v1/payments/history", methods=["GET"])
@require_scope("payments:read")
def transaction_history():
    # ... endpoint logic ...
```

**File: blueprints/webhooks.py**

```python
@webhooks_bp.route("/api/v1/webhooks/payment-status", methods=["POST"])
@require_scope("webhooks:receive")
def receive_payment_status():
    # ... endpoint logic ...
```

#### Error Response Format

**HTTP 403 Forbidden:**

```json
{
  "success": false,
  "error": "API key missing required scope: payments:create",
  "code": "INSUFFICIENT_SCOPE",
  "required_scope": "payments:create",
  "available_scopes": ["payments:read"]
}
```

#### Acceptance Criteria

1. WHEN an API key is created with scope "payments:create", THE Authentication_System SHALL allow POST requests to "/api/v1/payments/link"
2. WHEN an API key is created with scope "payments:read", THE Authentication_System SHALL allow GET requests to "/api/v1/payments/status/*" and "/api/v1/payments/history"
3. WHEN an API key is created with scope "webhooks:receive", THE Authentication_System SHALL allow POST requests to "/api/v1/webhooks/payment-status"
4. IF an API key does not have the required scope for an endpoint, THEN THE Authentication_System SHALL return HTTP 403 with error code "INSUFFICIENT_SCOPE"
5. THE Authentication_System SHALL validate scopes before processing the request
6. THE Authentication_System SHALL store scopes as a JSON array in the database
7. THE Authentication_System SHALL allow multiple scopes per API key
8. THE Authentication_System SHALL bypass scope checks for session-authenticated requests
9. THE Authentication_System SHALL include required_scope and available_scopes in error responses

#### Integration Points

- **File:** `services/api_auth.py` - Add `check_scope()` and `require_scope()` decorator
- **File:** `blueprints/payments.py` - Add `@require_scope()` to endpoints
- **File:** `blueprints/webhooks.py` - Add `@require_scope()` to webhook endpoint
- **File:** `models/api_key.py` - Add scopes field to model

### Requirement 9: API Key Security Properties

**User Story:** As a security engineer, I want API keys to be cryptographically secure and properly protected, so that they cannot be guessed or compromised through timing attacks.

#### Acceptance Criteria

1. FOR ALL generated API keys, the key SHALL contain at least 256 bits of entropy (64 hex characters)
2. FOR ALL API key validation operations, the comparison SHALL use constant-time comparison to prevent timing attacks
3. FOR ALL API keys stored in the database, only the SHA256 hash SHALL be stored (never the plaintext key)
4. WHEN an API key is generated, THE API_Key_Manager SHALL use a cryptographically secure random number generator
5. THE API_Key_Manager SHALL never log the full API key value (only the prefix)

### Requirement 10: Webhook Replay Protection

**User Story:** As a security engineer, I want to prevent webhook replay attacks, so that an attacker cannot reuse captured webhook payloads.

#### Replay Protection Mechanisms

**1. Timestamp Validation:**
- Webhook payload includes `timestamp` field (Unix timestamp)
- Reject webhooks older than 5 minutes
- Reject webhooks more than 1 minute in the future
- Timestamp is included in HMAC signature computation

**2. Signature Caching:**
- Store processed webhook signatures in cache for 10 minutes
- Use Redis or in-memory cache
- Key format: `webhook_sig:{signature_hash}`
- Reject duplicate signatures

#### Implementation Details

**Timestamp Validation:**

```python
# File: blueprints/webhooks.py

import time

def validate_webhook_timestamp(timestamp: int) -> tuple[bool, str]:
    """
    Validate webhook timestamp to prevent replay attacks.
    
    Returns:
        (is_valid, error_message)
    """
    current_time = int(time.time())
    
    # Reject if older than 5 minutes (300 seconds)
    if current_time - timestamp > 300:
        return False, "WEBHOOK_TOO_OLD"
    
    # Reject if more than 1 minute in future (60 seconds)
    if timestamp - current_time > 60:
        return False, "WEBHOOK_TIMESTAMP_INVALID"
    
    return True, None
```

**Signature Caching:**

```python
# File: services/webhook_cache.py (NEW)

import hashlib
from datetime import timedelta

# In-memory cache (use Redis in production)
_webhook_signature_cache = {}
_cache_lock = threading.Lock()

def is_signature_processed(signature: str) -> bool:
    """Check if webhook signature has been processed before."""
    sig_hash = hashlib.sha256(signature.encode('utf-8')).hexdigest()
    
    with _cache_lock:
        return sig_hash in _webhook_signature_cache

def mark_signature_processed(signature: str):
    """Mark webhook signature as processed."""
    sig_hash = hashlib.sha256(signature.encode('utf-8')).hexdigest()
    expiry = time.time() + 600  # 10 minutes
    
    with _cache_lock:
        _webhook_signature_cache[sig_hash] = expiry
        
        # Cleanup expired entries
        expired = [k for k, v in _webhook_signature_cache.items() if v < time.time()]
        for k in expired:
            del _webhook_signature_cache[k]
```

**HMAC with Timestamp:**

```python
# VoicePay side (signature generation):
import hmac
import hashlib
import time
import json

timestamp = int(time.time())
payload = {
    "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
    "status": "VERIFIED",
    "timestamp": timestamp,
    "amount": "1000.00",
    "currency": "NGN"
}

# Serialize payload (timestamp included)
payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

# Compute HMAC
signature = hmac.new(
    INBOUND_WEBHOOK_SECRET.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

headers = {
    'X-Webhook-Signature': f'sha256={signature}',
    'X-Webhook-Timestamp': str(timestamp)
}
```

**Complete Validation Flow:**

```python
# File: blueprints/webhooks.py

@webhooks_bp.route("/api/v1/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates with replay protection."""
    
    # 1. Verify HMAC signature
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        return jsonify({
            "success": False,
            "error": "Missing X-Webhook-Signature header",
            "code": "MISSING_SIGNATURE"
        }), 401
    
    # 2. Check for duplicate signature (replay attack)
    if is_signature_processed(signature):
        logger.warning("Duplicate webhook signature detected | sig=%s", signature[:20])
        return jsonify({
            "success": False,
            "error": "Webhook already processed",
            "code": "WEBHOOK_ALREADY_PROCESSED"
        }), 409
    
    # 3. Verify signature
    if not verify_webhook_signature(request.data, signature):
        return jsonify({
            "success": False,
            "error": "Invalid webhook signature",
            "code": "INVALID_SIGNATURE"
        }), 401
    
    # 4. Parse payload
    try:
        data = request.get_json()
    except Exception:
        return jsonify({
            "success": False,
            "error": "Invalid JSON payload",
            "code": "INVALID_PAYLOAD"
        }), 400
    
    # 5. Validate timestamp
    timestamp = data.get("timestamp")
    if not timestamp:
        return jsonify({
            "success": False,
            "error": "Missing timestamp field",
            "code": "MISSING_TIMESTAMP"
        }), 400
    
    is_valid, error_code = validate_webhook_timestamp(timestamp)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": f"Invalid timestamp: {error_code}",
            "code": error_code
        }), 401
    
    # 6. Mark signature as processed
    mark_signature_processed(signature)
    
    # 7. Process webhook
    # ... rest of webhook processing logic ...
```

#### Acceptance Criteria

1. WHEN a webhook payload is received, THE Webhook_Receiver SHALL extract a timestamp field from the payload
2. THE Webhook_Receiver SHALL reject webhooks with timestamps older than 5 minutes with error code "WEBHOOK_TOO_OLD"
3. THE Webhook_Receiver SHALL reject webhooks with timestamps more than 1 minute in the future with error code "WEBHOOK_TIMESTAMP_INVALID"
4. THE HMAC_Verifier SHALL include the timestamp in the HMAC signature computation
5. THE Webhook_Receiver SHALL store processed webhook signatures in a cache for 10 minutes
6. IF a webhook signature has been processed before, THEN THE Webhook_Receiver SHALL return HTTP 409 with error code "WEBHOOK_ALREADY_PROCESSED"
7. THE Webhook_Receiver SHALL use SHA256 hash of signature as cache key
8. THE Webhook_Receiver SHALL periodically clean up expired cache entries
9. THE Webhook_Receiver SHALL log replay attack attempts with signature prefix

#### Integration Points

- **File:** `blueprints/webhooks.py` - Add timestamp and signature validation
- **File:** `services/webhook_cache.py` (NEW) - Signature caching logic
- **File:** `config.py` - Add WEBHOOK_SIGNATURE_CACHE_TTL = 600 (10 minutes)

### Requirement 11: Health Check Endpoint

**User Story:** As a VoicePay developer, I want to check if OnePay is operational before making requests, so that I can handle downtime gracefully.

#### Acceptance Criteria

1. THE Authentication_System SHALL expose an endpoint at "/health" accepting GET requests
2. THE Authentication_System SHALL not require authentication for the health check endpoint
3. WHEN the health check endpoint is called, THE Authentication_System SHALL check database connectivity
4. WHEN the health check endpoint is called, THE Authentication_System SHALL check Quickteller API connectivity
5. IF all checks pass, THEN THE Authentication_System SHALL return HTTP 200 with status "healthy"
6. IF any check fails, THEN THE Authentication_System SHALL return HTTP 503 with status "unhealthy"
7. THE Authentication_System SHALL include individual check results in the response body
8. THE Authentication_System SHALL include a timestamp in ISO 8601 format in the response

### Requirement 12: Request ID Tracing

**User Story:** As a developer debugging issues, I want correlation IDs to trace requests across OnePay and VoicePay, so that I can follow a request through both systems.

#### Acceptance Criteria

1. WHEN a request includes an X-Request-ID header, THE Authentication_System SHALL use that value as the request ID
2. WHEN a request does not include an X-Request-ID header, THE Authentication_System SHALL generate a new UUID v4 as the request ID
3. THE Authentication_System SHALL include the request ID in all log messages for that request
4. THE Authentication_System SHALL include an X-Request-ID header in all API responses
5. WHEN OnePay makes an outbound webhook call, THE Authentication_System SHALL include the X-Request-ID header

### Requirement 13: API Documentation Endpoint

**User Story:** As a VoicePay developer, I want to access OpenAPI documentation for OnePay's API, so that I can understand available endpoints and their parameters.

#### Acceptance Criteria

1. THE Authentication_System SHALL expose an endpoint at "/api/docs" serving Swagger UI
2. THE Authentication_System SHALL expose an endpoint at "/api/openapi.json" serving the OpenAPI 3.0 specification
3. THE Authentication_System SHALL not require authentication for the documentation endpoints
4. THE OpenAPI specification SHALL document all /api/v1/* endpoints
5. THE OpenAPI specification SHALL include request/response schemas for all endpoints
6. THE OpenAPI specification SHALL document authentication requirements (API key or session)
7. THE OpenAPI specification SHALL document rate limits for each endpoint
8. THE OpenAPI specification SHALL include example requests and responses

### Requirement 14: Audit Logging for API Key Operations

**User Story:** As a security auditor, I want all API key operations to be logged, so that I can detect suspicious activity.

#### Acceptance Criteria

1. WHEN an API key is created, THE API_Key_Manager SHALL log an audit event with type "api_key.created"
2. WHEN an API key is revoked, THE API_Key_Manager SHALL log an audit event with type "api_key.revoked"
3. WHEN an API key authentication fails, THE Authentication_System SHALL log an audit event with type "api_key.auth_failed"
4. WHEN an API key is used successfully, THE Authentication_System SHALL log an audit event with type "api_key.auth_success"
5. THE API_Key_Manager SHALL include the API key prefix, user_id, and IP address in all audit events
6. THE API_Key_Manager SHALL never include the full API key in audit logs

### Requirement 15: Backward Compatibility

**User Story:** As an existing OnePay merchant, I want my current session-based authentication to continue working, so that the new API key feature doesn't break my existing workflow.

#### Acceptance Criteria

1. THE Authentication_System SHALL continue to support session-based authentication for all existing endpoints
2. THE Authentication_System SHALL continue to require CSRF tokens for session-authenticated requests
3. THE Authentication_System SHALL allow both API key and session authentication on the same endpoint
4. THE Authentication_System SHALL prioritize API key authentication if both Authorization header and session cookie are present
5. FOR ALL existing endpoints, the behavior SHALL remain unchanged when using session authentication

## Non-Functional Requirements

### Security

1. THE Authentication_System SHALL use TLS 1.2 or higher for all API communications in production
2. THE Authentication_System SHALL validate all input parameters to prevent injection attacks
3. THE Authentication_System SHALL use parameterized queries for all database operations
4. THE Authentication_System SHALL not expose stack traces or internal error details in API responses
5. THE Authentication_System SHALL implement rate limiting on all authentication endpoints to prevent brute force attacks

### Performance

1. THE Authentication_System SHALL validate API keys in less than 50 milliseconds at the 95th percentile
2. THE Webhook_Receiver SHALL process inbound webhooks in less than 200 milliseconds at the 95th percentile
3. THE Rate_Limiter SHALL check rate limits in less than 20 milliseconds at the 95th percentile

### Reliability

1. THE Authentication_System SHALL have 99.9% uptime for API key validation
2. THE Webhook_Receiver SHALL retry failed database operations up to 3 times with exponential backoff
3. THE Rate_Limiter SHALL fall back to in-memory rate limiting if the database is unavailable

### Observability

1. THE Authentication_System SHALL log all authentication attempts with outcome (success/failure)
2. THE Webhook_Receiver SHALL log all inbound webhooks with signature validation result
3. THE API_Key_Manager SHALL emit metrics for API key creation, revocation, and usage
4. THE Rate_Limiter SHALL emit metrics for rate limit hits and misses

## Correctness Properties

### Property 1: API Key Uniqueness (Invariant)
FOR ALL API keys k1 and k2 in the system, IF k1 ≠ k2, THEN hash(k1) ≠ hash(k2) with probability > 1 - 2^-128

### Property 2: Authentication Idempotence
FOR ALL valid API keys k, validating k multiple times SHALL return the same result (authenticated user context)

### Property 3: CSRF Bypass Correctness
FOR ALL requests r, IF r is authenticated via API key, THEN CSRF validation SHALL be skipped
AND IF r is authenticated via session, THEN CSRF validation SHALL be required

### Property 4: Webhook Signature Verification (Round-Trip)
FOR ALL webhook payloads p and secrets s, IF signature = HMAC-SHA256(p, s), THEN verify(p, signature, s) SHALL return true

### Property 5: Rate Limit Monotonicity
FOR ALL rate limit keys k, the request count within a window SHALL never decrease (only increase or reset to 0 at window boundary)

### Property 6: Scope Enforcement Completeness
FOR ALL API keys k with scopes S, FOR ALL endpoints e, IF e requires scope s AND s ∉ S, THEN request SHALL be rejected with HTTP 403

### Property 7: Timing Attack Resistance
FOR ALL API key validation operations, the execution time SHALL not vary based on the position of the first differing byte in the hash comparison

### Property 8: Replay Attack Prevention
FOR ALL webhook payloads p with signature sig, IF p has been processed before, THEN processing p again SHALL be rejected with HTTP 409

## Testing Guidance

## Testing Guidance

### Critical Test Cases

#### 1. API Key Generation Tests

**Test: Generate API Key with Valid Format**
```python
def test_generate_api_key_format():
    """API key should match format: onepay_live_{64-hex-chars}"""
    api_key = generate_api_key()
    
    assert api_key.startswith("onepay_live_")
    assert len(api_key) == 76  # "onepay_live_" (12) + 64 hex chars
    assert all(c in '0123456789abcdef' for c in api_key[12:])
```

**Test: API Key Storage (Hash Only)**
```python
def test_api_key_storage_hash_only():
    """Only SHA256 hash should be stored, never plaintext"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id, name="Test Key")
        
        # Verify plaintext key not in database
        db_key = db.query(APIKey).filter(APIKey.user_id == user.id).first()
        assert db_key.key_hash != api_key  # Not plaintext
        assert len(db_key.key_hash) == 64  # SHA256 hex digest
        assert db_key.key_prefix == api_key[:8]  # First 8 chars stored
```

**Test: API Key Uniqueness**
```python
def test_api_key_uniqueness():
    """Each generated API key should be unique"""
    keys = [generate_api_key() for _ in range(1000)]
    assert len(keys) == len(set(keys))  # No duplicates
```

#### 2. API Key Authentication Tests

**Test: Valid API Key Authentication**
```python
def test_valid_api_key_authentication():
    """Valid API key should authenticate successfully"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id, scopes=["payments:create"])
        
        response = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00", "currency": "NGN"}
        )
        
        assert response.status_code == 201
        assert response.json["success"] is True
```

**Test: Invalid API Key Rejection**
```python
def test_invalid_api_key_rejection():
    """Invalid API key should return 401 INVALID_API_KEY"""
    response = client.post(
        "/api/v1/payments/link",
        headers={"Authorization": "Bearer onepay_live_invalid"},
        json={"amount": "1000.00"}
    )
    
    assert response.status_code == 401
    assert response.json["code"] == "INVALID_API_KEY"
```

**Test: Expired API Key Rejection**
```python
def test_expired_api_key_rejection():
    """Expired API key should return 401 API_KEY_EXPIRED"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(
            db, user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        response = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00"}
        )
        
        assert response.status_code == 401
        assert response.json["code"] == "API_KEY_EXPIRED"
```

**Test: Revoked API Key Rejection**
```python
def test_revoked_api_key_rejection():
    """Revoked API key (is_active=false) should return 401 API_KEY_REVOKED"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id)
        
        # Revoke key
        db_key = db.query(APIKey).filter(APIKey.user_id == user.id).first()
        db_key.is_active = False
        db.commit()
        
        response = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00"}
        )
        
        assert response.status_code == 401
        assert response.json["code"] == "API_KEY_REVOKED"
```

#### 3. CSRF Bypass Tests

**Test: API Key Skips CSRF Validation**
```python
def test_api_key_skips_csrf():
    """API key authenticated requests should skip CSRF validation"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id, scopes=["payments:create"])
        
        # No X-CSRF-Token header
        response = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00"}
        )
        
        assert response.status_code == 201  # Success without CSRF token
```

**Test: Session Requires CSRF Validation**
```python
def test_session_requires_csrf():
    """Session authenticated requests should require CSRF token"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'testuser'
        sess['csrf_token'] = 'valid_token'
    
    # Missing X-CSRF-Token header
    response = client.post(
        "/api/v1/payments/link",
        json={"amount": "1000.00"}
    )
    
    assert response.status_code == 403
    assert response.json["code"] == "CSRF_ERROR"
```

#### 4. Webhook Signature Tests

**Test: Valid Webhook Signature**
```python
def test_valid_webhook_signature():
    """Valid HMAC signature should be accepted"""
    payload = {
        "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
        "status": "VERIFIED",
        "timestamp": int(time.time())
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        Config.INBOUND_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/payment-status",
        headers={
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": str(payload["timestamp"])
        },
        json=payload
    )
    
    assert response.status_code == 200
    assert response.json["success"] is True
```

**Test: Invalid Webhook Signature**
```python
def test_invalid_webhook_signature():
    """Invalid HMAC signature should return 401 INVALID_SIGNATURE"""
    payload = {
        "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
        "status": "VERIFIED",
        "timestamp": int(time.time())
    }
    
    response = client.post(
        "/api/v1/webhooks/payment-status",
        headers={
            "X-Webhook-Signature": "sha256=invalid_signature",
            "X-Webhook-Timestamp": str(payload["timestamp"])
        },
        json=payload
    )
    
    assert response.status_code == 401
    assert response.json["code"] == "INVALID_SIGNATURE"
```

#### 5. Webhook Replay Protection Tests

**Test: Duplicate Webhook Rejection**
```python
def test_duplicate_webhook_rejection():
    """Duplicate webhook signature should return 409 WEBHOOK_ALREADY_PROCESSED"""
    payload = {
        "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
        "status": "VERIFIED",
        "timestamp": int(time.time())
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        Config.INBOUND_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Timestamp": str(payload["timestamp"])
    }
    
    # First request succeeds
    response1 = client.post("/api/v1/webhooks/payment-status", headers=headers, json=payload)
    assert response1.status_code == 200
    
    # Second request with same signature rejected
    response2 = client.post("/api/v1/webhooks/payment-status", headers=headers, json=payload)
    assert response2.status_code == 409
    assert response2.json["code"] == "WEBHOOK_ALREADY_PROCESSED"
```

**Test: Old Webhook Rejection**
```python
def test_old_webhook_rejection():
    """Webhook older than 5 minutes should return 401 WEBHOOK_TOO_OLD"""
    old_timestamp = int(time.time()) - 400  # 6 minutes 40 seconds ago
    
    payload = {
        "tx_ref": "ONEPAY-A1B2C3D4E5F6G7H8",
        "status": "VERIFIED",
        "timestamp": old_timestamp
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        Config.INBOUND_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/webhooks/payment-status",
        headers={
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": str(old_timestamp)
        },
        json=payload
    )
    
    assert response.status_code == 401
    assert response.json["code"] == "WEBHOOK_TOO_OLD"
```

#### 6. Rate Limiting Tests

**Test: API Key Higher Rate Limit**
```python
def test_api_key_higher_rate_limit():
    """API key should have higher rate limit than session"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id, scopes=["payments:create"])
        
        # Make 11 requests (exceeds session limit of 10)
        for i in range(11):
            response = client.post(
                "/api/v1/payments/link",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"amount": f"{1000 + i}.00"}
            )
            
            if i < 10:
                assert response.status_code == 201  # Success
            # 11th request still succeeds (API limit is 100)
        
        assert response.status_code == 201
```

**Test: Session Rate Limit Enforcement**
```python
def test_session_rate_limit():
    """Session should hit rate limit at 10 requests"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'testuser'
        sess['csrf_token'] = 'valid_token'
    
    # Make 11 requests
    for i in range(11):
        response = client.post(
            "/api/v1/payments/link",
            headers={"X-CSRF-Token": "valid_token"},
            json={"amount": f"{1000 + i}.00"}
        )
        
        if i < 10:
            assert response.status_code == 201  # Success
        else:
            assert response.status_code == 429  # Rate limited
            assert response.json["code"] == "RATE_LIMIT_EXCEEDED"
```

#### 7. Scope Enforcement Tests

**Test: Insufficient Scope Rejection**
```python
def test_insufficient_scope_rejection():
    """API key without required scope should return 403 INSUFFICIENT_SCOPE"""
    with get_db() as db:
        user = create_test_user(db)
        # Create key with only payments:read scope
        api_key = create_api_key(db, user.id, scopes=["payments:read"])
        
        # Try to create payment link (requires payments:create)
        response = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00"}
        )
        
        assert response.status_code == 403
        assert response.json["code"] == "INSUFFICIENT_SCOPE"
        assert "payments:create" in response.json["error"]
```

**Test: Multiple Scopes**
```python
def test_multiple_scopes():
    """API key with multiple scopes should access all allowed endpoints"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(
            db, user.id,
            scopes=["payments:create", "payments:read"]
        )
        
        # Can create payment link
        response1 = client.post(
            "/api/v1/payments/link",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"amount": "1000.00"}
        )
        assert response1.status_code == 201
        
        tx_ref = response1.json["tx_ref"]
        
        # Can read payment status
        response2 = client.get(
            f"/api/v1/payments/status/{tx_ref}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response2.status_code == 200
```

#### 8. Timing Attack Prevention Tests

**Test: Constant-Time API Key Comparison**
```python
def test_constant_time_api_key_comparison():
    """API key validation should use constant-time comparison"""
    import time
    
    with get_db() as db:
        user = create_test_user(db)
        valid_key = create_api_key(db, user.id)
        
        # Test with keys that differ at different positions
        invalid_keys = [
            "onepay_live_" + "0" * 64,  # Differs at first char
            valid_key[:-1] + "0",        # Differs at last char
            valid_key[:32] + "0" * 32,   # Differs in middle
        ]
        
        timings = []
        for invalid_key in invalid_keys:
            start = time.perf_counter()
            response = client.post(
                "/api/v1/payments/link",
                headers={"Authorization": f"Bearer {invalid_key}"},
                json={"amount": "1000.00"}
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            assert response.status_code == 401
        
        # Timing variance should be minimal (< 10ms)
        timing_variance = max(timings) - min(timings)
        assert timing_variance < 0.01  # 10ms
```

### Property-Based Tests

#### Round-Trip Property: Webhook Signature

```python
from hypothesis import given, strategies as st

@given(
    tx_ref=st.text(min_size=10, max_size=50),
    status=st.sampled_from(["VERIFIED", "FAILED", "EXPIRED"]),
    timestamp=st.integers(min_value=1000000000, max_value=2000000000)
)
def test_webhook_signature_round_trip(tx_ref, status, timestamp):
    """FOR ALL webhook payloads, sign then verify should return true"""
    payload = {
        "tx_ref": tx_ref,
        "status": status,
        "timestamp": timestamp
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    # Sign
    signature = hmac.new(
        Config.INBOUND_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Verify
    is_valid = verify_webhook_signature(payload_bytes, f"sha256={signature}")
    
    assert is_valid is True
```

#### Idempotence Property: API Key Validation

```python
@given(api_key=st.text(min_size=76, max_size=76))
def test_api_key_validation_idempotence(api_key):
    """FOR ALL API keys, validate multiple times should return same result"""
    result1 = validate_api_key(api_key)
    result2 = validate_api_key(api_key)
    result3 = validate_api_key(api_key)
    
    assert result1 == result2 == result3
```

### Edge Cases

1. **API key with expired timestamp exactly at boundary (5 minutes)**
2. **API key with is_active = false**
3. **Webhook with timestamp exactly at 5-minute boundary**
4. **Webhook with duplicate signature after cache expiry (10 minutes)**
5. **API key without required scope**
6. **Rate limit at exact window boundary (60 seconds)**
7. **Concurrent API key validation requests**
8. **Database unavailable during rate limit check**
9. **Empty scopes array in API key**
10. **API key with null expires_at (never expires)**

### Performance Tests

**Test: API Key Validation Latency**
```python
def test_api_key_validation_latency():
    """API key validation should complete in < 50ms at p95"""
    with get_db() as db:
        user = create_test_user(db)
        api_key = create_api_key(db, user.id)
        
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validate_api_key(api_key)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
        
        p95 = sorted(latencies)[94]  # 95th percentile
        assert p95 < 50  # < 50ms
```

**Test: Webhook Processing Latency**
```python
def test_webhook_processing_latency():
    """Webhook processing should complete in < 200ms at p95"""
    # Similar to above, measure end-to-end webhook processing time
    # Assert p95 < 200ms
```

## Dependencies

1. **Database**: PostgreSQL or SQLite for storing API keys, rate limits, and webhook cache
2. **Cryptography**: Python secrets module for key generation, hashlib for SHA256, hmac for signatures
3. **Web Framework**: Flask for HTTP endpoints and middleware
4. **Environment Variables**: For storing webhook secrets and configuration
5. **Existing OnePay Components**:
   - `core/auth.py` - Session authentication (extend with API key support)
   - `services/rate_limiter.py` - Rate limiting (already supports flexible keys)
   - `services/webhook.py` - Webhook delivery (reuse invoice sync function)
   - `models/user.py` - User model (API keys reference users)
   - `blueprints/payments.py` - Payment endpoints (add API key auth)

## Implementation Order

### Phase 1: Foundation (Days 1-2)

**Day 1: Database and Models**
1. Create `models/api_key.py` - SQLAlchemy model
2. Create Alembic migration for api_keys table
3. Run migration in development
4. Create `services/api_auth.py` - API key generation and validation
5. Write unit tests for API key generation and storage

**Day 2: Authentication Middleware**
1. Create `core/api_auth_middleware.py` - API key authentication
2. Add `is_api_key_authenticated()` helper to `core/auth.py`
3. Modify CSRF validation in `blueprints/payments.py`
4. Write integration tests for API key authentication
5. Write tests for CSRF bypass

### Phase 2: API Key Management UI (Day 3)

**Day 3: Settings Page**
1. Add API key management routes to `blueprints/payments.py`
2. Create `static/js/settings.js` - JavaScript for API key UI
3. Modify `templates/settings.html` - Add API Keys section
4. Write tests for API key CRUD operations
5. Manual testing of UI flows

### Phase 3: Inbound Webhooks (Day 4)

**Day 4: Webhook Receiver**
1. Create `blueprints/webhooks.py` - Inbound webhook endpoint
2. Create `services/webhook_cache.py` - Signature caching
3. Add INBOUND_WEBHOOK_SECRET to `config.py`
4. Add startup validation for webhook secrets
5. Write tests for webhook signature verification
6. Write tests for replay protection

### Phase 4: Rate Limiting and Scopes (Day 5)

**Day 5: Advanced Features**
1. Update rate limiting in `blueprints/payments.py`
2. Add scope enforcement decorator to `services/api_auth.py`
3. Apply `@require_scope()` to all endpoints
4. Add API versioning middleware
5. Write tests for rate limiting and scope enforcement

### Phase 5: Testing and Documentation (Days 6-7)

**Day 6: Integration Testing**
1. End-to-end tests for complete flows
2. Performance tests (latency, throughput)
3. Security tests (timing attacks, replay attacks)
4. Load testing with multiple concurrent requests

**Day 7: Documentation and Deployment**
1. Write API documentation (OpenAPI spec)
2. Update `.env.example` with new variables
3. Update `docs/DEPLOYMENT.md` with migration steps
4. Create VoicePay integration guide
5. Production deployment checklist

## Complete Error Code Reference

### Authentication Errors (401)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| INVALID_API_KEY | 401 | API key not found or hash mismatch | `{"success": false, "error": "Invalid API key", "code": "INVALID_API_KEY"}` |
| API_KEY_EXPIRED | 401 | API key expires_at is in the past | `{"success": false, "error": "API key expired", "code": "API_KEY_EXPIRED"}` |
| API_KEY_REVOKED | 401 | API key is_active is false | `{"success": false, "error": "API key revoked", "code": "API_KEY_REVOKED"}` |
| INVALID_SIGNATURE | 401 | Webhook HMAC signature invalid | `{"success": false, "error": "Invalid webhook signature", "code": "INVALID_SIGNATURE"}` |
| WEBHOOK_TOO_OLD | 401 | Webhook timestamp > 5 minutes old | `{"success": false, "error": "Webhook timestamp too old", "code": "WEBHOOK_TOO_OLD"}` |
| WEBHOOK_TIMESTAMP_INVALID | 401 | Webhook timestamp > 1 minute in future | `{"success": false, "error": "Webhook timestamp in future", "code": "WEBHOOK_TIMESTAMP_INVALID"}` |
| MISSING_SIGNATURE | 401 | X-Webhook-Signature header missing | `{"success": false, "error": "Missing signature header", "code": "MISSING_SIGNATURE"}` |

### Authorization Errors (403)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| INSUFFICIENT_SCOPE | 403 | API key missing required scope | `{"success": false, "error": "API key missing required scope: payments:create", "code": "INSUFFICIENT_SCOPE", "required_scope": "payments:create", "available_scopes": ["payments:read"]}` |
| CSRF_ERROR | 403 | CSRF token invalid or missing (session auth) | `{"success": false, "error": "CSRF validation failed", "code": "CSRF_ERROR"}` |

### Not Found Errors (404)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| TRANSACTION_NOT_FOUND | 404 | tx_ref does not exist in database | `{"success": false, "error": "Transaction not found", "code": "TRANSACTION_NOT_FOUND"}` |
| NOT_FOUND | 404 | Generic not found (API key, user, etc.) | `{"success": false, "error": "Resource not found", "code": "NOT_FOUND"}` |

### Conflict Errors (409)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| WEBHOOK_ALREADY_PROCESSED | 409 | Duplicate webhook signature detected | `{"success": false, "error": "Webhook already processed", "code": "WEBHOOK_ALREADY_PROCESSED"}` |

### Validation Errors (400)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| INVALID_PAYLOAD | 400 | JSON parsing failed or invalid format | `{"success": false, "error": "Invalid JSON payload", "code": "INVALID_PAYLOAD"}` |
| INVALID_TX_REF | 400 | tx_ref format invalid | `{"success": false, "error": "Invalid tx_ref format", "code": "INVALID_TX_REF"}` |
| INVALID_STATUS | 400 | Webhook status not in allowed values | `{"success": false, "error": "Invalid status", "code": "INVALID_STATUS"}` |
| MISSING_TIMESTAMP | 400 | Webhook timestamp field missing | `{"success": false, "error": "Missing timestamp field", "code": "MISSING_TIMESTAMP"}` |
| VALIDATION_ERROR | 400 | Generic validation error | `{"success": false, "error": "Validation failed", "code": "VALIDATION_ERROR"}` |

### Content Type Errors (415)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| INVALID_CONTENT_TYPE | 415 | Content-Type must be application/json | `{"success": false, "error": "Content-Type must be application/json", "code": "INVALID_CONTENT_TYPE"}` |

### Rate Limiting Errors (429)

| Error Code | HTTP Status | Description | Response Example |
|------------|-------------|-------------|------------------|
| RATE_LIMIT_EXCEEDED | 429 | Too many requests in time window | `{"success": false, "error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED", "retry_after": 45}` |

### Error Response Headers

All error responses include:
```
Content-Type: application/json
X-Request-ID: <uuid>
X-API-Version: v1
```

Rate limit errors also include:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711234567
Retry-After: 45
```

## Migration Considerations

### Database Migration Script

**File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`

```python
"""Add API keys table for M2M authentication

Revision ID: add_api_keys_001
Revises: 20260329140000
Create Date: 2026-03-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_api_keys_001'
down_revision = '20260329140000'
branch_labels = None
depends_on = None


def upgrade():
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    
    # Create indexes
    op.create_index('idx_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('idx_api_keys_is_active', 'api_keys', ['is_active'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_api_keys_is_active', table_name='api_keys')
    op.drop_index('idx_api_keys_key_hash', table_name='api_keys')
    op.drop_index('idx_api_keys_user_id', table_name='api_keys')
    
    # Drop table
    op.drop_table('api_keys')
```

### Migration Execution Steps

**1. Generate Migration:**
```bash
# Review auto-generated migration
alembic revision --autogenerate -m "add_api_keys_table"

# Edit migration file to match specification above
```

**2. Test Migration (Development):**
```bash
# Backup database first
cp onepay.db onepay.db.backup

# Run migration
alembic upgrade head

# Verify table created
sqlite3 onepay.db ".schema api_keys"

# Test rollback
alembic downgrade -1

# Re-apply
alembic upgrade head
```

**3. Production Migration:**
```bash
# 1. Backup production database
pg_dump onepay_production > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migration in transaction
alembic upgrade head

# 3. Verify table exists
psql onepay_production -c "\d api_keys"

# 4. Verify indexes
psql onepay_production -c "\di api_keys*"
```

### Backward Compatibility

**Session Authentication (Existing):**
- All existing session-based authentication continues to work
- No changes to login/register/logout flows
- CSRF validation remains required for session requests
- Existing merchants unaffected

**API Endpoints (Existing):**
- Unversioned endpoints (`/api/payments/link`) continue to work
- Deprecation warnings logged but no breaking changes
- Versioned endpoints (`/api/v1/payments/link`) added alongside

**Rate Limiting (Existing):**
- Existing rate limits for session users unchanged
- New rate limits for API keys are separate
- No impact on current merchant usage patterns

### Feature Flags

**Optional: Gradual Rollout**

```python
# File: config.py

class Config:
    # Feature flags
    ENABLE_API_KEY_AUTH = os.getenv('ENABLE_API_KEY_AUTH', 'true').lower() == 'true'
    ENABLE_INBOUND_WEBHOOKS = os.getenv('ENABLE_INBOUND_WEBHOOKS', 'true').lower() == 'true'
```

```python
# File: core/api_auth_middleware.py

@app.before_request
def check_api_key_auth():
    """Check for API key authentication before processing request."""
    if not Config.ENABLE_API_KEY_AUTH:
        return  # Feature disabled
    
    # ... API key authentication logic ...
```

### Rollback Procedures

**If Issues Detected:**

**1. Disable API Key Authentication:**
```bash
# Set environment variable
export ENABLE_API_KEY_AUTH=false

# Restart application
systemctl restart onepay
```

**2. Rollback Database Migration:**
```bash
# Rollback to previous version
alembic downgrade -1

# Verify rollback
psql onepay_production -c "\dt api_keys"  # Should not exist
```

**3. Revert Code Changes:**
```bash
# Revert to previous commit
git revert <commit_hash>

# Deploy previous version
git push origin main
```

### Data Migration

**No data migration required** - this is a new feature with no existing data to migrate.

**Post-Deployment:**
- Merchants must explicitly create API keys (opt-in)
- No automatic API key generation
- Existing integrations continue using session authentication

### Monitoring Post-Deployment

**Metrics to Track:**

1. **API Key Usage:**
   - Number of API keys created per day
   - API key authentication success/failure rate
   - API key usage by endpoint

2. **Performance:**
   - API key validation latency (p50, p95, p99)
   - Rate limit check latency
   - Webhook processing latency

3. **Security:**
   - Failed API key authentication attempts
   - Invalid webhook signatures
   - Replay attack attempts (duplicate signatures)

4. **Errors:**
   - INSUFFICIENT_SCOPE errors
   - INVALID_API_KEY errors
   - WEBHOOK_TOO_OLD errors

**Alerting Thresholds:**

```yaml
# Example: Prometheus alerts
- alert: HighAPIKeyAuthFailureRate
  expr: rate(api_key_auth_failures[5m]) > 10
  annotations:
    summary: "High API key authentication failure rate"

- alert: WebhookReplayAttacks
  expr: rate(webhook_replay_attempts[5m]) > 5
  annotations:
    summary: "Potential webhook replay attack detected"
```

# VoicePay API Integration - Design Document

**Date:** 2026-03-31  
**Goal:** Enable machine-to-machine (M2M) API access to OnePay for VoicePay integration by implementing API key authentication, removing session/CSRF dependencies for API clients, and adding inbound webhook support.

**Architecture:** Add parallel authentication system supporting both session-based (web UI) and API key-based (M2M) authentication. API keys bypass CSRF validation while maintaining security through cryptographic key validation. Inbound webhooks use HMAC signature verification for authenticity.

**Tech Stack:** 
- Python 3.11+ with Flask
- SQLAlchemy ORM for database
- Alembic for migrations
- bcrypt for password hashing
- HMAC-SHA256 for webhook signatures
- PostgreSQL/SQLite database

---

## Problem Statement

OnePay currently uses session-based authentication designed for web browsers. This is incompatible with VoicePay's requirements for:

1. **Service-to-service authentication** - VoicePay cannot maintain browser sessions
2. **Webhook callbacks** - VoicePay needs to send payment confirmations back to OnePay
3. **Programmatic access** - API clients need token-based auth, not cookies

**Current blockers:**
- All API endpoints require session cookies (`current_user_id()` from Flask session)
- All POST endpoints require CSRF tokens tied to sessions
- No API key infrastructure exists
- No inbound webhook receiver endpoint
- Rate limiting tied to session user IDs

---

## Design Decisions

### Scope
**Comprehensive** - All items from readiness assessment including production hardening

### API Key Management UI
**Both locations** - Basic management in Settings page, full features in dedicated API Keys page

### API Key Permissions
**Single scope** - All API keys have full access (simpler, faster to implement)

### Inbound Webhook Authentication
**Shared secret with HMAC-SHA256** - Reuses existing HMAC patterns, no dependency on API key system

### Implementation Approach
**Phased** - Build in logical phases that can be tested independently

---

## Architecture Overview

### Dual Authentication System

We'll add a **parallel authentication system** to OnePay that supports both session-based (existing) and API key-based (new) authentication without disrupting current functionality.

**Key Design Principles:**
1. **Non-breaking changes** - Existing web UI continues to work unchanged
2. **Dual authentication** - Requests can authenticate via session OR API key
3. **Conditional CSRF** - Skip CSRF validation only for API key authenticated requests
4. **Reuse existing patterns** - Follow OnePay's current security model (HMAC, rate limiting, audit logging)

**Authentication Flow:**
```
Incoming Request
    ↓
Check for API Key in Authorization header?
    ↓ YES                           ↓ NO
API Key Auth                    Session Auth (existing)
    ↓                               ↓
Validate key hash               Check session cookie
    ↓                               ↓
Set g.api_key_authenticated     Set g.user_id from session
Set g.user_id from key              ↓
Skip CSRF validation            Require CSRF validation
    ↓                               ↓
    └─────────→ Proceed to endpoint ←─────────┘
```

**Database Changes:**
- New `api_keys` table to store hashed keys
- Links to existing `users` table via `user_id`
- Tracks usage, expiration, active status

**Code Changes:**
- New `core/api_auth.py` module for API key logic
- Modify `core/auth.py` to support dual authentication
- Update all POST endpoints to conditionally skip CSRF
- New blueprint `blueprints/api_keys.py` for management UI
- New blueprint `blueprints/webhooks.py` for inbound webhooks

---

## Phase 1: API Key Infrastructure

### Database Schema

**New table: `api_keys`**

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 of full key
    key_prefix VARCHAR(20) NOT NULL,         -- First 8 chars for display
    name VARCHAR(100),                       -- User-friendly name
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,     -- NULL = never expires
    is_active BOOLEAN DEFAULT TRUE,
    
    INDEX idx_api_keys_user_id (user_id),
    INDEX idx_api_keys_key_hash (key_hash)
);
```

**Key format:** `onepay_live_<64-char-hex>` (total 76 characters)
- Prefix identifies it as OnePay key
- 64 hex chars = 32 bytes of entropy (cryptographically secure)

**Migration file:** `alembic/versions/20260401000002_add_api_keys_table.py`

### Core Authentication Module

**New file: `core/api_auth.py`**

Key functions:
- `generate_api_key()` - Creates new key with secure random bytes
- `hash_api_key(key)` - SHA256 hash for storage
- `validate_api_key(key)` - Checks hash, expiration, active status
- `get_user_from_api_key(key)` - Returns user_id if valid
- `is_api_key_authenticated()` - Check if current request used API key

**Implementation:**

```python
import secrets
import hashlib
from datetime import datetime, timezone
from flask import g
from database import get_db
from models.api_key import APIKey

def generate_api_key() -> str:
    """Generate a new API key with secure random bytes"""
    random_bytes = secrets.token_bytes(32)
    hex_string = random_bytes.hex()
    return f"onepay_live_{hex_string}"

def hash_api_key(key: str) -> str:
    """Hash API key using SHA256"""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

def validate_api_key(key: str) -> tuple[bool, int | None]:
    """
    Validate API key and return (is_valid, user_id)
    Returns (False, None) if invalid
    """
    if not key or not key.startswith('onepay_live_'):
        return False, None
    
    key_hash = hash_api_key(key)
    
    with get_db() as db:
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key:
            return False, None
        
        # Check expiration
        if api_key.expires_at:
            if api_key.expires_at < datetime.now(timezone.utc):
                return False, None
        
        # Update last used timestamp
        api_key.last_used_at = datetime.now(timezone.utc)
        db.flush()
        
        return True, api_key.user_id

def is_api_key_authenticated() -> bool:
    """Check if current request authenticated via API key"""
    return getattr(g, 'api_key_authenticated', False)
```

### Authentication Middleware

**Modify: `app.py`**

Add before_request hook to check for API keys:

```python
@app.before_request
def authenticate_api_key():
    """Check for API key in Authorization header"""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        is_valid, user_id = validate_api_key(api_key)
        
        if is_valid:
            g.api_key_authenticated = True
            g.user_id = user_id
            g.api_key = api_key  # For rate limiting
            
            # Log API key usage
            from core.audit import log_event
            from core.ip import client_ip
            with get_db() as db:
                log_event(db, "api_key.used", user_id=user_id, 
                         ip_address=client_ip(),
                         detail={"endpoint": request.endpoint})
```

**Modify: `core/auth.py`**

Update `current_user_id()` to support both auth methods:

```python
def current_user_id() -> int | None:
    """Get user ID from session OR API key"""
    # Check API key first (stored in g.user_id by middleware)
    if hasattr(g, 'api_key_authenticated') and g.api_key_authenticated:
        return g.user_id
    # Fall back to session
    return session.get("user_id")
```

### CSRF Bypass Logic

**Problem:** Current code requires CSRF tokens on all POST endpoints, but API clients can't obtain CSRF tokens.

**Solution:** Conditionally skip CSRF validation when request is authenticated via API key.

**Pattern to apply to all POST endpoints:**

```python
# Before (current)
@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    if not current_user_id():
        return unauthenticated()
    
    csrf_header = request.headers.get("X-CSRFToken")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)
    
    # ... rest of endpoint

# After (with API key support)
@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    if not current_user_id():
        return unauthenticated()
    
    # Skip CSRF for API key authenticated requests
    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken")
        if not is_valid_csrf_token(csrf_header):
            return error("CSRF validation failed", "CSRF_ERROR", 403)
    
    # ... rest of endpoint
```

**Endpoints to modify:**
- `/api/payments/link` (create payment link)
- `/api/payments/reissue/<tx_ref>` (reissue link)
- `/api/settings/webhook` (update webhook)
- `/api/account/settings` (update account)

**Security note:** API key itself proves authenticity (like CSRF token does for sessions), so skipping CSRF is safe.

---

## Phase 2: API Key Management UI

### Two-Location Strategy

**Location 1: Settings Page (Basic Management)**
- Quick access to generate first API key
- View active key count
- Link to dedicated API Keys page
- Minimal UI footprint

**Location 2: Dedicated API Keys Page (Full Management)**
- Complete list of all API keys
- Generate new keys with custom names
- View key details (masked, prefix only)
- Revoke/delete keys
- See last used timestamp
- Copy key to clipboard (only shown once at creation)

### User Flow

**First-time user:**
1. Navigate to Settings page
2. See "API Keys" section with "Generate API Key" button
3. Click button → modal shows full key (only time it's visible)
4. Copy key, save securely
5. Key now appears in list (masked: `onepay_live_abc12345...`)

**Managing multiple keys:**
1. Navigate to dedicated "API Keys" page from nav menu
2. See table of all keys with columns:
   - Name (editable)
   - Prefix (first 8 chars)
   - Created
   - Last Used
   - Status (Active/Expired)
   - Actions (Revoke/Delete)
3. Generate new key with custom name
4. Revoke compromised keys

### API Endpoints for UI

**New blueprint: `blueprints/api_keys.py`**

```python
# List user's API keys
GET /api/api-keys
Response: {
    "success": true,
    "api_keys": [
        {
            "id": 1,
            "name": "VoicePay Production",
            "key_prefix": "onepay_live_abc12345",
            "created_at": "2026-03-31T10:00:00Z",
            "last_used_at": "2026-03-31T12:30:00Z",
            "expires_at": null,
            "is_active": true
        }
    ]
}

# Generate new API key
POST /api/api-keys
Body: {"name": "VoicePay Production"}
Response: {
    "success": true,
    "api_key": {
        "id": 1,
        "name": "VoicePay Production",
        "api_key": "onepay_live_abc12345...",  # Full key, only shown once
        "key_prefix": "onepay_live_abc12345",
        "created_at": "2026-03-31T10:00:00Z"
    }
}

# Revoke API key
DELETE /api/api-keys/{id}
Response: {"success": true, "message": "API key revoked"}

# Update API key name
PATCH /api/api-keys/{id}
Body: {"name": "New Name"}
Response: {"success": true}
```

### Security Considerations

1. **Key visibility:** Full key shown only once at creation (can't retrieve later)
2. **Audit logging:** All key operations logged (create, revoke, use)
3. **Rate limiting:** Limit key generation (5 per hour per user)
4. **Confirmation:** Require confirmation before revoking active keys
5. **Max keys per user:** Limit to 10 active keys per user

---

## Phase 3: Inbound Webhook Receiver

### Purpose
Allow external services (like VoicePay) to send payment status updates back to OnePay.

### Design

**New blueprint: `blueprints/webhooks.py`**

**Endpoint:**
```python
POST /api/webhooks/payment-status
```

**Authentication:** HMAC-SHA256 signature verification (shared secret approach)

**Request Format:**
```json
{
    "tx_ref": "TXN-ABC123",
    "status": "VERIFIED",
    "amount": "1000.00",
    "currency": "NGN",
    "timestamp": "2026-03-31T12:00:00Z",
    "provider": "voicepay"
}
```

**Headers:**
```
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac-signature>
```

### HMAC Signature Verification

**Signature calculation (VoicePay side):**
```python
import hmac
import hashlib

payload = request.body  # Raw JSON bytes
secret = "shared-secret-key"
signature = hmac.new(
    secret.encode('utf-8'),
    payload,
    hashlib.sha256
).hexdigest()

headers = {
    'X-Webhook-Signature': f'sha256={signature}'
}
```

**Signature verification (OnePay side):**
```python
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC signature from inbound webhook"""
    if not signature.startswith('sha256='):
        return False
    
    expected_sig = signature[7:]  # Remove 'sha256=' prefix
    secret = Config.INBOUND_WEBHOOK_SECRET
    
    computed_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_sig, computed_sig)
```

### Implementation

```python
@webhooks_bp.route("/api/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates from external services"""
    
    # 1. Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    if not verify_webhook_signature(request.data, signature):
        logger.warning("Invalid webhook signature | ip=%s", client_ip())
        return error("Invalid signature", "UNAUTHORIZED", 401)
    
    # 2. Rate limit
    with get_db() as db:
        if not check_rate_limit(db, f"webhook_inbound:{client_ip()}", 
                               limit=100, window_secs=60):
            return rate_limited()
        
        # 3. Parse and validate payload
        data = request.get_json(silent=True) or {}
        tx_ref = data.get("tx_ref")
        status = data.get("status")
        
        if not tx_ref or not status:
            return error("Missing required fields", "VALIDATION_ERROR", 400)
        
        # 4. Update transaction
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref
        ).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        # 5. Update status
        try:
            transaction.status = TransactionStatus(status)
            transaction.verified_at = datetime.now(timezone.utc)
            db.flush()
            
            # 6. Log event
            log_event(db, "webhook.inbound_received", 
                     tx_ref=tx_ref,
                     ip_address=client_ip(),
                     detail={"status": status, "provider": data.get("provider")})
            
            logger.info("Inbound webhook processed | tx_ref=%s status=%s", 
                       tx_ref, status)
            
            return jsonify({"success": True, "tx_ref": tx_ref})
            
        except ValueError:
            return error("Invalid status value", "VALIDATION_ERROR", 400)
```

### Configuration

**New environment variable:**
```bash
INBOUND_WEBHOOK_SECRET=<64-char-hex-secret>
```

**Add to `config.py`:**
```python
INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET", "")
```

### Security Features

1. **HMAC signature** - Prevents unauthorized webhook submissions
2. **Rate limiting** - 100 requests per minute per IP
3. **Audit logging** - All webhook attempts logged
4. **Constant-time comparison** - Prevents timing attacks on signature
5. **IP logging** - Track webhook sources

---

## Phase 4: Production Hardening

### 1. API Versioning

**Change:** Add `/v1/` prefix to all API endpoints

**Implementation:**
```python
# In app.py
app.register_blueprint(payments_bp, url_prefix="/api/v1")
app.register_blueprint(api_keys_bp, url_prefix="/api/v1")
app.register_blueprint(webhooks_bp, url_prefix="/api/v1")
```

**Endpoints become:**
- `/api/v1/payments/link` (was `/api/payments/link`)
- `/api/v1/payments/status/<tx_ref>`
- `/api/v1/api-keys`
- `/api/v1/webhooks/payment-status`

**Backward compatibility:**
- Keep old routes working temporarily
- Add deprecation warnings in responses
- Document migration path

### 2. Separate Rate Limits for API vs Web

**Current:** Single rate limit per user  
**New:** Different limits based on authentication method

```python
# In create_payment_link()
if is_api_key_authenticated():
    rate_key = f"api_link:{g.api_key}"
    limit = Config.RATE_LIMIT_API_LINK_CREATE  # 100/min
else:
    rate_key = f"link:user:{current_user_id()}"
    limit = Config.RATE_LIMIT_LINK_CREATE  # 10/min

if not check_rate_limit(db, rate_key, limit):
    return rate_limited()
```

**New config values:**
```python
RATE_LIMIT_API_LINK_CREATE = int(os.getenv("RATE_LIMIT_API_LINK_CREATE", "100"))
RATE_LIMIT_API_STATUS_CHECK = int(os.getenv("RATE_LIMIT_API_STATUS_CHECK", "500"))
```

### 3. OpenAPI Documentation

**Tool:** Use `flask-swagger-ui` or `flasgger`

**Implementation:**
```python
# In app.py
from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = '/api/docs'
API_URL = '/api/openapi.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "OnePay API"}
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
```

**OpenAPI spec file:** `static/openapi.json`
- Documents all API endpoints
- Request/response schemas
- Authentication methods (Bearer token)
- Example requests

**Key sections:**
- Authentication: Bearer token (API key)
- Endpoints: All `/api/v1/*` routes
- Models: Transaction, APIKey, WebhookPayload
- Error responses: Standard error format

### 4. Enhanced Health Checks

**Current:** Basic `/health` endpoint exists  
**Enhancement:** Check dependencies

```python
@public_bp.route("/health", methods=["GET"])
def health_check():
    """Comprehensive health check"""
    checks = {
        "database": _check_database(),
        "korapay": _check_korapay() if korapay.is_configured() else None,
    }
    
    all_healthy = all(v for v in checks.values() if v is not None)
    status_code = 200 if all_healthy else 503
    
    return jsonify({
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }), status_code

def _check_database() -> bool:
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return True
    except Exception:
        return False

def _check_korapay() -> bool:
    try:
        return korapay.is_transfer_configured()
    except Exception:
        return False
```

---

## Error Handling

### API Key Authentication Errors

**Consistent error responses:**

```json
// Invalid API key format
{
    "success": false,
    "error": "INVALID_API_KEY",
    "message": "API key format is invalid"
}

// API key not found or revoked
{
    "success": false,
    "error": "UNAUTHORIZED",
    "message": "Invalid or revoked API key"
}

// API key expired
{
    "success": false,
    "error": "API_KEY_EXPIRED",
    "message": "API key has expired"
}
```

### Webhook Errors

```json
// Invalid signature
{
    "success": false,
    "error": "UNAUTHORIZED",
    "message": "Invalid webhook signature"
}

// Transaction not found
{
    "success": false,
    "error": "NOT_FOUND",
    "message": "Transaction not found"
}

// Invalid status value
{
    "success": false,
    "error": "VALIDATION_ERROR",
    "message": "Invalid status value"
}
```

### Graceful Degradation

- If API key validation fails, don't expose why (security)
- Log detailed errors server-side for debugging
- Return generic "unauthorized" to client
- Rate limit failed authentication attempts
- Audit log all authentication failures

---

## Testing Strategy

### Unit Tests

**Test files to create:**

1. **`tests/test_api_auth.py`**
   - API key generation format validation
   - Key hashing produces consistent results
   - Expiration checking logic
   - User lookup from valid key
   - Invalid key returns None
   - Expired key returns None

2. **`tests/test_api_key_endpoints.py`**
   - List API keys (authenticated user)
   - Generate new key returns full key once
   - Revoke key marks as inactive
   - Cannot access other user's keys
   - Rate limiting on key generation

3. **`tests/test_csrf_bypass.py`**
   - Session auth requires CSRF token
   - API key auth skips CSRF validation
   - Invalid API key still requires CSRF
   - Missing both auth methods returns 401

4. **`tests/test_inbound_webhooks.py`**
   - Valid HMAC signature accepted
   - Invalid signature rejected (401)
   - Missing signature rejected
   - Transaction status updated correctly
   - Rate limiting enforced
   - Audit log created

### Integration Tests

**Test scenarios:**

1. **End-to-end API key flow:**
   - User generates API key via UI
   - Use key to create payment link
   - Check transaction status with key
   - Revoke key via UI
   - Verify key no longer works (401)

2. **Webhook flow:**
   - VoicePay sends webhook with valid signature
   - OnePay verifies signature
   - Transaction status updated
   - Audit log entry created
   - Response 200 returned

3. **Dual authentication coexistence:**
   - Web UI user creates link (session auth)
   - API client creates link (API key auth)
   - Both transactions visible to user
   - Both auth methods work simultaneously

### Security Tests

1. **API key enumeration prevention:**
   - Same error for invalid/revoked/expired keys
   - Constant-time comparison in validation
   - No timing differences in responses

2. **CSRF bypass security:**
   - Cannot bypass CSRF without valid API key
   - Session requests still require CSRF
   - API key + CSRF both provided works

3. **Webhook replay attacks:**
   - Timestamp validation (reject old webhooks)
   - Duplicate webhook handling (idempotent)
   - Signature cannot be reused

4. **Rate limiting:**
   - API key rate limits enforced separately
   - Webhook rate limits per IP
   - Failed auth attempts rate limited

### Performance Tests

1. **API key validation performance:**
   - Hash lookup < 10ms
   - Database query optimized with indexes
   - No N+1 queries

2. **Concurrent API requests:**
   - Multiple API clients simultaneously
   - No race conditions in rate limiting
   - Transaction updates atomic

---

## Database Model

**New file: `models/api_key.py`**

```python
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from models.base import Base

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), 
                     nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )
    
    def to_dict(self):
        """Safe dict for JSON responses - never exposes full key"""
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }
```

---

## Configuration Changes

**New environment variables:**

```bash
# API Key Settings
API_KEY_MAX_PER_USER=10
API_KEY_GENERATION_RATE_LIMIT=5  # per hour

# Inbound Webhook Settings
INBOUND_WEBHOOK_SECRET=<64-char-hex-secret>

# API Rate Limits (higher than web UI)
RATE_LIMIT_API_LINK_CREATE=100
RATE_LIMIT_API_STATUS_CHECK=500
```

**Add to `config.py`:**

```python
# ── API Keys ──────────────────────────────────────────────────────────
API_KEY_MAX_PER_USER = int(os.getenv("API_KEY_MAX_PER_USER", "10"))
API_KEY_GENERATION_RATE_LIMIT = int(os.getenv("API_KEY_GENERATION_RATE_LIMIT", "5"))

# ── Inbound Webhooks ──────────────────────────────────────────────────
INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET", "")

# ── API Rate Limits ───────────────────────────────────────────────────
RATE_LIMIT_API_LINK_CREATE = int(os.getenv("RATE_LIMIT_API_LINK_CREATE", "100"))
RATE_LIMIT_API_STATUS_CHECK = int(os.getenv("RATE_LIMIT_API_STATUS_CHECK", "500"))
```

**Validation in production:**

```python
# In Config.validate()
if app_env == "production":
    if not cls.INBOUND_WEBHOOK_SECRET:
        errors.append("INBOUND_WEBHOOK_SECRET is required in production")
    elif len(cls.INBOUND_WEBHOOK_SECRET) < 32:
        errors.append("INBOUND_WEBHOOK_SECRET too short (minimum 32 characters)")
```

---

## File Structure

**New files to create:**

```
core/
  api_auth.py                    # API key validation logic

models/
  api_key.py                     # APIKey database model

blueprints/
  api_keys.py                    # API key management endpoints
  webhooks.py                    # Inbound webhook receiver

alembic/versions/
  20260401000002_add_api_keys_table.py  # Database migration

tests/
  test_api_auth.py               # Unit tests for API key logic
  test_api_key_endpoints.py      # Integration tests for API key UI
  test_csrf_bypass.py            # CSRF bypass security tests
  test_inbound_webhooks.py       # Webhook receiver tests

static/
  openapi.json                   # OpenAPI specification

templates/
  api_keys.html                  # Dedicated API keys page
  (modify) settings.html         # Add API keys section
```

**Files to modify:**

```
app.py                           # Add API key middleware, register blueprints
core/auth.py                     # Update current_user_id() for dual auth
config.py                        # Add new configuration values
blueprints/payments.py           # Add CSRF bypass logic to POST endpoints
blueprints/public.py             # Enhance health check endpoint
```

---

## Implementation Timeline

### Phase 1: API Key Infrastructure (3-4 days)
- Day 1: Database migration, APIKey model, core auth logic
- Day 2: Middleware integration, CSRF bypass implementation
- Day 3: Unit tests, integration with existing endpoints
- Day 4: Testing, bug fixes, documentation

### Phase 2: API Key Management UI (2 days)
- Day 5: API endpoints (list, create, revoke)
- Day 6: Frontend UI (Settings section + dedicated page)

### Phase 3: Inbound Webhooks (1 day)
- Day 7: Webhook receiver endpoint, HMAC verification, tests

### Phase 4: Production Hardening (2-3 days)
- Day 8: API versioning, separate rate limits
- Day 9: OpenAPI documentation, enhanced health checks
- Day 10: End-to-end testing, security review

**Total: 8-10 days**

---

## Success Criteria

### Functional Requirements
- ✅ Merchants can generate API keys via UI
- ✅ API clients can authenticate with Bearer token
- ✅ API clients can create payment links without CSRF
- ✅ API clients can check transaction status
- ✅ VoicePay can send payment confirmations via webhook
- ✅ Webhooks verified with HMAC signature
- ✅ Web UI continues to work unchanged

### Non-Functional Requirements
- ✅ API key validation < 10ms
- ✅ No breaking changes to existing endpoints
- ✅ All tests passing (unit + integration)
- ✅ Security audit passed
- ✅ Documentation complete (OpenAPI spec)
- ✅ Production config validated

### Security Requirements
- ✅ API keys hashed in database (SHA256)
- ✅ Full key shown only once at creation
- ✅ CSRF bypass only for valid API keys
- ✅ Webhook signatures verified (HMAC-SHA256)
- ✅ Rate limiting enforced separately for API
- ✅ All operations audit logged

---

## Migration Path for VoicePay

### Step 1: OnePay Deployment (Days 1-10)
1. Deploy Phase 1-3 to staging
2. Generate test API key
3. Share test credentials with VoicePay team
4. Provide API documentation

### Step 2: VoicePay Integration (Parallel)
1. VoicePay implements API key authentication
2. VoicePay implements webhook signing
3. Integration testing in staging environment
4. Load testing with production-like traffic

### Step 3: Production Rollout
1. Deploy OnePay changes to production
2. Generate production API key for VoicePay
3. Share production credentials securely
4. Monitor API usage and error rates
5. VoicePay switches to production endpoint

### Step 4: Monitoring (Ongoing)
- Track API key usage metrics
- Monitor webhook delivery success rate
- Review audit logs for anomalies
- Optimize rate limits based on usage

---

## Risks and Mitigations

### Risk 1: Breaking Existing Web UI
**Mitigation:** 
- Comprehensive integration tests
- Staged rollout (staging → production)
- Feature flag for API key auth
- Rollback plan ready

### Risk 2: API Key Compromise
**Mitigation:**
- Keys hashed in database
- Revocation mechanism available
- Audit logging tracks all usage
- Rate limiting prevents abuse
- User can generate new keys immediately

### Risk 3: Webhook Replay Attacks
**Mitigation:**
- HMAC signature verification
- Timestamp validation
- Idempotent transaction updates
- Rate limiting per IP

### Risk 4: Performance Degradation
**Mitigation:**
- Database indexes on key_hash
- Caching for API key validation
- Separate rate limits for API
- Load testing before production

---

## Rollback Plan

If critical issues arise after deployment:

1. **Immediate:** Disable API key authentication via feature flag
2. **Short-term:** Revert to previous deployment
3. **Data:** API keys table can be dropped without affecting existing data
4. **Web UI:** Continues to work (no changes to session auth)

**Rollback triggers:**
- Web UI authentication broken
- Database performance degraded > 50%
- Security vulnerability discovered
- Critical bug affecting payments

---

## Appendix: Example API Usage

### Generating an API Key (Web UI)

1. Navigate to Settings page
2. Click "Generate API Key" button
3. Enter name: "VoicePay Production"
4. Copy key: `onepay_live_abc123...` (shown once)
5. Save securely

### Creating a Payment Link (API Client)

```bash
curl -X POST https://onepay.example.com/api/v1/payments/link \
  -H "Authorization: Bearer onepay_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "1000.00",
    "currency": "NGN",
    "description": "Voice payment for order #123",
    "customer_email": "customer@example.com"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Payment link created successfully",
  "tx_ref": "TXN-ABC123",
  "payment_url": "https://onepay.example.com/pay/TXN-ABC123",
  "amount": "1000.00",
  "currency": "NGN",
  "expires_at": "2026-03-31T12:05:00Z"
}
```

### Checking Transaction Status (API Client)

```bash
curl -X GET https://onepay.example.com/api/v1/payments/status/TXN-ABC123 \
  -H "Authorization: Bearer onepay_live_abc123..."
```

**Response:**
```json
{
  "success": true,
  "tx_ref": "TXN-ABC123",
  "status": "VERIFIED",
  "amount": "1000.00",
  "currency": "NGN",
  "verified_at": "2026-03-31T12:03:00Z"
}
```

### Sending Webhook (VoicePay → OnePay)

```python
import hmac
import hashlib
import requests
import json

# Prepare payload
payload = {
    "tx_ref": "TXN-ABC123",
    "status": "VERIFIED",
    "amount": "1000.00",
    "currency": "NGN",
    "timestamp": "2026-03-31T12:03:00Z",
    "provider": "voicepay"
}

payload_bytes = json.dumps(payload).encode('utf-8')

# Sign with HMAC
secret = "shared-webhook-secret"
signature = hmac.new(
    secret.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

# Send webhook
response = requests.post(
    "https://onepay.example.com/api/v1/webhooks/payment-status",
    json=payload,
    headers={
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}"
    }
)

print(response.json())
# {"success": true, "tx_ref": "TXN-ABC123"}
```

---

## Conclusion

This design provides a comprehensive solution for VoicePay integration while maintaining OnePay's security standards and existing functionality. The phased approach allows for incremental testing and validation, reducing risk of breaking changes.

**Key Benefits:**
- Non-breaking: Web UI continues to work unchanged
- Secure: API keys hashed, webhooks signed, audit logged
- Scalable: Separate rate limits for API clients
- Maintainable: Follows existing OnePay patterns
- Testable: Comprehensive test coverage

**Next Steps:**
1. Review and approve this design document
2. Create detailed implementation plan (tasks breakdown)
3. Begin Phase 1 implementation
4. Coordinate with VoicePay team on integration timeline


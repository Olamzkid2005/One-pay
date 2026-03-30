# OnePay Readiness Assessment for VoicePay Integration

**Assessment Date:** March 29, 2026  
**OnePay Version:** v1.3.0  
**Assessment Status:** ⚠️ **REQUIRES MODIFICATIONS**

---

## Executive Summary

OnePay is **NOT immediately ready** for VoicePay integration. While the core payment link functionality exists, the authentication model is incompatible with machine-to-machine (M2M) communication. OnePay currently uses **session-based authentication** designed for web browsers, but VoicePay needs **API key or token-based authentication** for service-to-service calls.

**Readiness Score: 6/10**

---

## Critical Blockers (Must Fix Before Integration)

### 1. ❌ **Authentication Model Incompatibility**

**Current State:**
- OnePay uses Flask-Login with session cookies
- Authentication requires browser-based login flow
- CSRF tokens tied to user sessions
- No API key or service account support

**Problem for VoicePay:**
- VoicePay cannot maintain browser sessions
- Cannot perform login flow from WhatsApp webhook context
- CSRF tokens expire and require session management
- No way to authenticate as a "service account"

**Required Changes:**
```python
# MUST ADD: API Key Authentication
# File: services/api_auth.py (NEW FILE)

class APIKeyAuth:
    """
    API key authentication for machine-to-machine communication.
    Allows VoicePay to authenticate without browser sessions.
    """
    
    @staticmethod
    def generate_api_key(user_id: int) -> str:
        """Generate a secure API key for a user"""
        # Format: onepay_live_<64-char-hex>
        return f"onepay_live_{secrets.token_hex(32)}"
    
    @staticmethod
    def validate_api_key(api_key: str) -> Optional[int]:
        """Validate API key and return user_id if valid"""
        # Check format, lookup in database, return user_id
        pass

# MUST ADD: API Key Middleware
# File: core/api_auth_middleware.py (NEW FILE)

def api_key_required(f):
    """Decorator for API endpoints that accept API key auth"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for Authorization: Bearer <api_key> header
        # Validate API key
        # Set current_user_id() from API key
        # Skip CSRF validation for API key requests
        pass
    return decorated_function
```

**Database Changes Required:**
```sql
-- MUST ADD: api_keys table
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 hash of API key
    key_prefix VARCHAR(20) NOT NULL,  -- First 8 chars for identification
    name VARCHAR(100),  -- User-friendly name like "VoicePay Production"
    scopes TEXT,  -- JSON array of allowed operations
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_api_keys_user_id (user_id),
    INDEX idx_api_keys_key_hash (key_hash)
);
```

**Estimated Effort:** 2-3 days

---

### 2. ❌ **CSRF Token Requirement for API Calls**

**Current State:**
- All POST endpoints require CSRF token in header
- CSRF tokens tied to user sessions
- No way to bypass CSRF for authenticated API calls

**Problem for VoicePay:**
- Cannot obtain CSRF token without session
- CSRF is unnecessary for API key authenticated requests (API key itself proves authenticity)

**Required Changes:**
```python
# MUST MODIFY: blueprints/payments.py
# Line 280: create_payment_link()

@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    # BEFORE (current):
    csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(csrf_header):
        return error("CSRF validation failed", "CSRF_ERROR", 403)
    
    # AFTER (required):
    # Skip CSRF validation if authenticated via API key
    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not is_valid_csrf_token(csrf_header):
            return error("CSRF validation failed", "CSRF_ERROR", 403)
```

**Estimated Effort:** 1 day

---

### 3. ❌ **No Webhook Signature Verification for Inbound Webhooks**

**Current State:**
- OnePay sends webhooks TO merchants (outbound)
- OnePay signs outbound webhooks with HMAC
- No endpoint for RECEIVING webhooks FROM external services

**Problem for VoicePay:**
- VoicePay needs to send payment confirmations back to OnePay
- No secure way for OnePay to receive and verify webhooks

**Required Changes:**
```python
# MUST ADD: Inbound webhook receiver
# File: blueprints/webhooks.py (NEW FILE)

@webhooks_bp.route("/api/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """
    Receive payment status updates from external services (e.g., VoicePay).
    Verifies HMAC signature before processing.
    """
    # 1. Verify HMAC signature
    signature = request.headers.get("X-Webhook-Signature")
    if not verify_webhook_signature(request.data, signature):
        return error("Invalid signature", "UNAUTHORIZED", 401)
    
    # 2. Parse payload
    data = request.get_json()
    tx_ref = data.get("tx_ref")
    status = data.get("status")  # VERIFIED, FAILED, etc.
    
    # 3. Update transaction
    with get_db() as db:
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref
        ).first()
        
        if transaction:
            transaction.status = TransactionStatus(status)
            transaction.verified_at = datetime.now(timezone.utc)
            db.flush()
    
    return jsonify({"success": True})
```

**Estimated Effort:** 1 day

---

## Major Issues (Should Fix for Production)

### 4. ⚠️ **Rate Limiting Per User, Not Per API Key**

**Current State:**
- Rate limiting uses `current_user_id()` from session
- No distinction between web UI and API usage

**Problem for VoicePay:**
- VoicePay might hit rate limits quickly if processing many requests
- Need separate rate limits for API vs web UI

**Recommended Changes:**
```python
# SHOULD ADD: Separate rate limits for API keys
RATE_LIMIT_API_LINK_CREATE = 100  # Higher limit for API
RATE_LIMIT_WEB_LINK_CREATE = 10   # Lower limit for web UI

# In create_payment_link():
if is_api_key_authenticated():
    rate_key = f"api_link:{get_api_key_id()}"
    limit = Config.RATE_LIMIT_API_LINK_CREATE
else:
    rate_key = f"link:user:{current_user_id()}"
    limit = Config.RATE_LIMIT_LINK_CREATE
```

**Estimated Effort:** 0.5 days

---

### 5. ⚠️ **No API Versioning**

**Current State:**
- Endpoints like `/api/payments/link` have no version prefix
- Breaking changes would affect all clients

**Problem for VoicePay:**
- Future OnePay updates might break VoicePay integration
- No way to maintain backward compatibility

**Recommended Changes:**
```python
# SHOULD ADD: API versioning
# Current: /api/payments/link
# Recommended: /api/v1/payments/link

# Register blueprint with version prefix
app.register_blueprint(payments_bp, url_prefix="/api/v1")
```

**Estimated Effort:** 0.5 days

---

### 6. ⚠️ **No API Documentation Endpoint**

**Current State:**
- No OpenAPI/Swagger documentation
- No programmatic way to discover API capabilities

**Problem for VoicePay:**
- Developers must read source code to understand API
- No contract for API behavior

**Recommended Changes:**
```python
# SHOULD ADD: OpenAPI documentation
# Use flask-swagger-ui or similar

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

**Estimated Effort:** 1 day

---

## Minor Issues (Nice to Have)

### 7. ℹ️ **No Health Check Endpoint for Dependencies**

**Current State:**
- No `/health` endpoint
- Cannot check if OnePay is operational before making requests

**Recommended Addition:**
```python
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    checks = {
        "database": check_database_connection(),
        "redis": check_redis_connection(),
        "quickteller": check_quickteller_api(),
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return jsonify({
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), status_code
```

**Estimated Effort:** 0.5 days

---

### 8. ℹ️ **No Request ID Tracing**

**Current State:**
- No correlation ID for tracing requests across services
- Difficult to debug issues spanning VoicePay → OnePay

**Recommended Addition:**
```python
# Add X-Request-ID header support
@app.before_request
def add_request_id():
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    g.request_id = request_id

@app.after_request
def inject_request_id(response):
    response.headers['X-Request-ID'] = g.request_id
    return response
```

**Estimated Effort:** 0.5 days

---

## What Works Well (No Changes Needed)

### ✅ **Payment Link Creation Logic**
- Core functionality is solid
- Proper validation, idempotency, error handling
- Virtual account integration works

### ✅ **Transaction Model**
- Well-designed schema
- Proper status enum (PENDING, VERIFIED, FAILED, EXPIRED)
- Timezone-aware timestamps

### ✅ **QR Code Generation**
- Base64 PNG encoding works
- Both payment URL and virtual account QR codes supported

### ✅ **Invoice Integration**
- Auto-generation works
- PDF export functional
- Email delivery implemented

### ✅ **Security Controls**
- HMAC webhook signing (outbound)
- Rate limiting infrastructure
- Input validation and sanitization
- Audit logging

### ✅ **Error Handling**
- Proper HTTP status codes
- Structured error responses
- Graceful degradation

---

## Integration Readiness Checklist

| Requirement | Status | Priority | Effort |
|-------------|--------|----------|--------|
| API Key Authentication | ❌ Missing | **CRITICAL** | 2-3 days |
| Skip CSRF for API Keys | ❌ Missing | **CRITICAL** | 1 day |
| Inbound Webhook Receiver | ❌ Missing | **CRITICAL** | 1 day |
| API Rate Limiting | ⚠️ Needs Work | HIGH | 0.5 days |
| API Versioning | ⚠️ Needs Work | HIGH | 0.5 days |
| API Documentation | ⚠️ Needs Work | MEDIUM | 1 day |
| Health Check Endpoint | ℹ️ Nice to Have | LOW | 0.5 days |
| Request ID Tracing | ℹ️ Nice to Have | LOW | 0.5 days |

**Total Estimated Effort for Critical Items:** 4-5 days  
**Total Estimated Effort for All Items:** 7-9 days

---

## Recommended Implementation Order

### Phase 1: Critical Blockers (Week 1)
1. **Day 1-2:** Implement API key authentication system
   - Create `api_keys` table
   - Add API key generation/validation logic
   - Create API key management UI in settings

2. **Day 3:** Modify CSRF validation to skip for API keys
   - Update all POST endpoints
   - Add `is_api_key_authenticated()` helper

3. **Day 4:** Implement inbound webhook receiver
   - Create `/api/webhooks/payment-status` endpoint
   - Add HMAC signature verification
   - Test with mock payloads

4. **Day 5:** Testing and documentation
   - Write integration tests
   - Document API key usage
   - Create VoicePay integration guide

### Phase 2: Production Hardening (Week 2)
5. **Day 6:** API rate limiting and versioning
6. **Day 7:** API documentation (OpenAPI/Swagger)
7. **Day 8:** Health checks and monitoring
8. **Day 9:** Request tracing and logging improvements
9. **Day 10:** End-to-end integration testing with VoicePay

---

## Alternative Approach: Workaround for Immediate Testing

If you need to test VoicePay integration **before** OnePay modifications are complete, you can use this temporary workaround:

### Option A: Service Account with Session Management

1. Create a dedicated OnePay user account for VoicePay
2. VoicePay performs login once at startup to obtain session cookie
3. Store session cookie in memory and reuse for all requests
4. Obtain CSRF token from login response
5. Refresh session when it expires (detect 401 responses)

**Pros:**
- No OnePay code changes required
- Can start testing immediately

**Cons:**
- Fragile (sessions expire, CSRF tokens rotate)
- Not production-ready
- Security concerns (storing session cookies)
- Race conditions if multiple VoicePay instances

### Option B: Direct Database Access (NOT RECOMMENDED)

VoicePay could write directly to OnePay's database to create transactions.

**Pros:**
- Bypasses authentication entirely

**Cons:**
- **EXTREMELY DANGEROUS** - breaks encapsulation
- No validation, no audit logging
- Database schema changes break VoicePay
- **DO NOT USE IN PRODUCTION**

---

## Conclusion

**OnePay requires 4-5 days of development work** to be production-ready for VoicePay integration. The core payment link functionality is solid, but the authentication model must be adapted for machine-to-machine communication.

**Recommendation:** Implement Phase 1 (Critical Blockers) before proceeding with VoicePay development. This ensures a secure, maintainable integration that won't require major refactoring later.

**Next Steps:**
1. Review this assessment with the OnePay team
2. Prioritize and schedule the required changes
3. Create detailed implementation tasks for each modification
4. Update VoicePay requirements to reflect the actual OnePay API (with API key auth)
5. Begin parallel development once OnePay API key auth is implemented

---

**Assessment Prepared By:** Kiro AI Assistant  
**For:** VoicePay Pilot Integration Project

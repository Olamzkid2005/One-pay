# VoicePay API Integration - Design Summary

## Full Design Document
See complete technical design with all implementation details:
`#[[file:docs/superpowers/specs/2026-03-31-voicepay-api-integration-design.md]]`

## Architecture Overview

### Dual Authentication System
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

## Implementation Phases

### Phase 1: API Key Infrastructure (3-4 days)
- Database migration: `api_keys` table
- Core authentication module: `core/api_auth.py`
- Middleware integration in `app.py`
- CSRF bypass logic in POST endpoints
- Unit tests

### Phase 2: API Key Management UI (2 days)
- API endpoints: `blueprints/api_keys.py`
- Settings page integration
- Dedicated API Keys page
- Frontend UI components

### Phase 3: Inbound Webhook Receiver (1 day)
- Webhook endpoint: `blueprints/webhooks.py`
- HMAC signature verification
- Transaction status updates
- Tests

### Phase 4: Production Hardening (2-3 days)
- API versioning (`/v1/` prefix)
- Separate rate limits
- OpenAPI documentation
- Enhanced health checks

## Key Components

### Database Schema
```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);
```

### API Key Format
`onepay_live_<64-char-hex>` (76 characters total)
- Prefix: `onepay_live_` (identifies as OnePay key)
- Random: 64 hex chars = 32 bytes entropy

### Authentication Flow
1. Check `Authorization: Bearer <key>` header
2. Validate key hash against database
3. Check expiration and active status
4. Set `g.api_key_authenticated = True`
5. Set `g.user_id` from key's user_id
6. Skip CSRF validation for this request

### Webhook Authentication
1. Receive webhook with `X-Webhook-Signature` header
2. Extract signature: `sha256=<hex>`
3. Compute HMAC-SHA256 of request body with shared secret
4. Compare signatures using constant-time comparison
5. Process webhook if valid, reject if invalid

## File Structure

### New Files
```
core/api_auth.py                    # API key validation logic
models/api_key.py                   # APIKey database model
blueprints/api_keys.py              # API key management endpoints
blueprints/webhooks.py              # Inbound webhook receiver
alembic/versions/20260401000002_add_api_keys_table.py
tests/test_api_auth.py
tests/test_api_key_endpoints.py
tests/test_csrf_bypass.py
tests/test_inbound_webhooks.py
static/openapi.json
templates/api_keys.html
```

### Modified Files
```
app.py                              # API key middleware, blueprints
core/auth.py                        # Dual auth in current_user_id()
config.py                           # New config values
blueprints/payments.py              # CSRF bypass logic
blueprints/public.py                # Enhanced health check
templates/settings.html             # API keys section
```

## Configuration

### New Environment Variables
```bash
# API Keys
API_KEY_MAX_PER_USER=10
API_KEY_GENERATION_RATE_LIMIT=5

# Webhooks
INBOUND_WEBHOOK_SECRET=<64-char-hex>

# Rate Limits
RATE_LIMIT_API_LINK_CREATE=100
RATE_LIMIT_API_STATUS_CHECK=500
```

## Security Considerations

1. **API keys hashed** - SHA256 before storage, never plaintext
2. **Key visibility** - Full key shown only once at creation
3. **CSRF bypass** - Only for valid API key auth
4. **Webhook signatures** - HMAC-SHA256 verification
5. **Rate limiting** - Separate limits for API clients
6. **Audit logging** - All operations logged
7. **Constant-time comparison** - Prevents timing attacks

## Testing Strategy

### Unit Tests
- API key generation and validation
- HMAC signature verification
- CSRF bypass logic
- Rate limiting

### Integration Tests
- End-to-end API key flow
- Webhook delivery and processing
- Dual authentication coexistence

### Security Tests
- API key enumeration prevention
- CSRF bypass security
- Webhook replay attacks
- Rate limiting enforcement

## Rollback Plan

1. Disable API key auth via feature flag
2. Revert deployment if critical issues
3. Drop `api_keys` table (no impact on existing data)
4. Web UI continues to work (session auth unchanged)

## Timeline
**Total: 8-10 days**
- Phase 1: 3-4 days
- Phase 2: 2 days
- Phase 3: 1 day
- Phase 4: 2-3 days

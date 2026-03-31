# VoicePay API Integration - Requirements

## Overview
Enable machine-to-machine (M2M) API access to OnePay for VoicePay integration by implementing API key authentication, removing session/CSRF dependencies for API clients, and adding inbound webhook support.

## Design Reference
See complete technical design: `#[[file:docs/superpowers/specs/2026-03-31-voicepay-api-integration-design.md]]`

## Functional Requirements

### FR1: API Key Authentication
- Merchants can generate API keys via web UI
- API keys follow format: `onepay_live_<64-char-hex>` (76 chars total)
- Keys are hashed (SHA256) before storage
- Full key shown only once at creation
- Keys can be named for identification
- Keys can be revoked/deleted by owner
- Maximum 10 active keys per user

### FR2: Dual Authentication System
- Existing session-based auth continues to work unchanged
- New API key-based auth works in parallel
- Requests can authenticate via session OR API key
- `current_user_id()` returns user from either auth method

### FR3: CSRF Bypass for API Clients
- API key authenticated requests skip CSRF validation
- Session authenticated requests still require CSRF tokens
- No breaking changes to existing web UI behavior

### FR4: API Key Management UI
- Settings page: Basic API key management (generate, view count, link to full page)
- Dedicated API Keys page: Full management (list all, generate with names, revoke, view details)
- Display masked keys (prefix only: `onepay_live_abc12345...`)
- Show last used timestamp
- Confirmation before revoking active keys

### FR5: Inbound Webhook Receiver
- Endpoint: `POST /api/v1/webhooks/payment-status`
- Accepts payment status updates from external services
- Updates transaction status in database
- Returns success/error response

### FR6: Webhook Authentication
- HMAC-SHA256 signature verification
- Shared secret configuration via environment variable
- Signature in `X-Webhook-Signature` header format: `sha256=<hex>`
- Constant-time comparison to prevent timing attacks

### FR7: API Versioning
- All API endpoints prefixed with `/v1/`
- Endpoints: `/api/v1/payments/*`, `/api/v1/api-keys/*`, `/api/v1/webhooks/*`
- Backward compatibility maintained temporarily

### FR8: Separate Rate Limiting
- API clients: Higher limits (100/min for link creation, 500/min for status checks)
- Web UI: Existing limits (10/min for link creation)
- Webhook endpoint: 100 requests/min per IP

### FR9: API Documentation
- OpenAPI 3.0 specification
- Interactive docs at `/api/docs`
- Documents all endpoints, schemas, authentication

### FR10: Enhanced Health Checks
- Check database connectivity
- Check Korapay integration status
- Return 200 if healthy, 503 if unhealthy
- Include timestamp and version

## Non-Functional Requirements

### NFR1: Performance
- API key validation completes in < 10ms
- Database queries optimized with indexes
- No N+1 query patterns

### NFR2: Security
- API keys hashed in database (never stored plaintext)
- HMAC signatures verified for webhooks
- All operations audit logged
- Rate limiting enforced
- Failed auth attempts logged and rate limited

### NFR3: Reliability
- No breaking changes to existing functionality
- Graceful error handling
- Idempotent webhook processing
- Transaction updates are atomic

### NFR4: Maintainability
- Follow existing OnePay code patterns
- Comprehensive test coverage (unit + integration)
- Clear error messages
- Audit logging for debugging

## Success Criteria

### Must Have
- ✅ API clients can authenticate with Bearer token
- ✅ API clients can create payment links without CSRF
- ✅ API clients can check transaction status
- ✅ External services can send webhooks with HMAC verification
- ✅ Web UI continues to work unchanged
- ✅ All tests passing

### Should Have
- ✅ OpenAPI documentation available
- ✅ Separate rate limits for API vs web
- ✅ Enhanced health checks
- ✅ API versioning implemented

### Nice to Have
- Metrics dashboard for API usage
- API key usage analytics
- Webhook delivery retry mechanism

## Out of Scope
- Granular API key permissions (all keys have full access)
- API key rotation automation
- Multi-region webhook delivery
- GraphQL API
- Webhook delivery guarantees (at-most-once delivery)

## Constraints
- Must use existing Flask framework
- Must maintain PostgreSQL/SQLite compatibility
- Must not break existing web UI
- Must follow existing security patterns (bcrypt, HMAC, audit logging)
- Implementation timeline: 8-10 days

## Dependencies
- Existing OnePay codebase (Flask, SQLAlchemy, Alembic)
- VoicePay team for integration testing
- Shared webhook secret coordination

## Risks
1. Breaking existing web UI authentication
2. API key compromise
3. Webhook replay attacks
4. Performance degradation

See design document for detailed mitigation strategies.

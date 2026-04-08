# Implementation Plan: OnePay Codebase Improvements

## Overview

This implementation plan breaks down 25 requirements into actionable coding tasks across 6 phases. Each task is designed to be completed in a single work session with clear verification steps.

**Total Requirements**: 25  
**Total Tasks**: 52  
**Estimated Timeline**: 8-10 weeks (revised from 6 weeks based on complexity analysis)  
**Critical Path**: Phase 1 (Security) must complete before other phases  
**Parallel Work**: Phases 2-6 can be worked on concurrently after Phase 1

### Complexity Distribution

- **Small Tasks**: 28 tasks (1-3 hours each)
- **Medium Tasks**: 16 tasks (4-8 hours each)
- **Large Tasks**: 8 tasks (10-16 hours each)

### Effort Summary by Phase

- **Phase 1 (Security)**: 20-30 hours (Critical - must complete first)
- **Phase 2 (Architecture)**: 24-32 hours
- **Phase 3 (Performance)**: 28-36 hours
- **Phase 4 (Frontend)**: 32-40 hours
- **Phase 5 (Developer Experience)**: 12-16 hours
- **Phase 6 (Observability)**: 20-28 hours

**Total Estimated Effort**: 136-182 hours (17-23 developer days)

---

## Phase 1: Security (Critical)

### 1. Webhook Signature Validation (Requirement 1)

- [x] 1.1 Add webhook secret validation at startup
  - Modify `config.py` to validate `INBOUND_WEBHOOK_SECRET` is non-empty
  - Add production check for minimum 32 characters
  - Log critical error and refuse startup if validation fails
  - _Requirements: 1.1, 1.4_
  - **Affected files**: `config.py`, `app.py`
  - **Complexity**: Small

- [x] 1.2 Implement HMAC-SHA256 signature verification
  - Create signature verification function in `services/webhook.py`
  - Extract signature from request headers
  - Compare against computed HMAC using constant-time comparison
  - _Requirements: 1.2_
  - **Affected files**: `services/webhook.py`
  - **Complexity**: Small

- [x] 1.3 Add signature failure handling
  - Return HTTP 401 on signature mismatch
  - Log client IP address on failure
  - _Requirements: 1.3_
  - **Affected files**: `blueprints/webhooks.py`
  - **Complexity**: Small

- [x] 1.4 Write unit tests for webhook signature validation
  - Test valid signature acceptance
  - Test invalid signature rejection
  - Test missing signature handling
  - Test production secret length enforcement
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

### 2. Webhook Idempotency (Requirement 2)

- [x] 2.1 Create WebhookIdempotency model
  - Create `models/webhook_idempotency.py`
  - Define table with id, source, processed_at, tx_ref columns
  - Add index on processed_at
  - _Requirements: 2.3, 2.4_
  - **Affected files**: `models/webhook_idempotency.py`, `models/__init__.py`
  - **Complexity**: Small

- [x] 2.2 Create Alembic migration for webhook_idempotency table
  - Generate migration file
  - Define upgrade/downgrade functions
  - _Requirements: 2.3_
  - **Affected files**: `alembic/versions/`
  - **Complexity**: Small

- [x] 2.3 Implement idempotency check in webhook handler
  - Extract unique identifier from webhook payload
  - Check if identifier exists in database
  - Return HTTP 200 without processing if duplicate
  - Store identifier on successful processing
  - _Requirements: 2.1, 2.2, 2.4_
  - **Affected files**: `blueprints/webhooks.py`, `services/webhook.py`
  - **Complexity**: Medium

- [x] 2.4 Add cleanup task for old idempotency records
  - Add periodic Huey task to delete records older than 24 hours
  - _Requirements: 2.3_
  - **Affected files**: `services/task_queue.py`
  - **Dependencies**: Task 10.1 (Huey setup)
  - **Complexity**: Small

- [x] 2.5 Write unit tests for webhook idempotency
  - Test duplicate detection
  - Test idempotent response
  - Test record expiration
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

### 3. SSRF Prevention for Logo URL Validation (Requirement 3)

- [x] 3.1 Create URL validator service with SSRF protection
  - Create `services/url_validator.py`
  - Implement DNS resolution to IP address
  - Check against private IP ranges (RFC 1918, loopback, link-local, multicast)
  - Return resolved IP for Host header binding
  - _Requirements: 3.1, 3.2, 3.3_
  - **Affected files**: `services/url_validator.py`
  - **Complexity**: Medium

- [x] 3.2 Add DNS rebinding race condition detection
  - Implement TTL check on DNS resolution
  - Log security warning on race condition detection
  - Reject request if race condition suspected
  - _Requirements: 3.4_
  - **Affected files**: `services/url_validator.py`
  - **Complexity**: Large

- [x] 3.3 Integrate URL validator into logo upload
  - Update logo URL validation to use new service
  - Handle validation errors gracefully
  - _Requirements: 3.1, 3.2_
  - **Affected files**: `blueprints/public.py` or relevant blueprint
  - **Complexity**: Small

- [x] 3.4 Write security tests for SSRF prevention
  - Test private IP rejection (10.x, 172.16.x, 192.168.x, 127.x)
  - Test IPv6 loopback and link-local rejection
  - Test DNS rebinding attack vectors
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

### 4. Strong Secret Enforcement (Requirement 21)

- [x] 4.1 Implement secret validation at startup
  - Check SECRET_KEY length >= 32 characters
  - Check HMAC_SECRET length >= 32 characters
  - Check SECRET_KEY != HMAC_SECRET
  - Refuse startup in production, warn in development
  - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_
  - **Affected files**: `config.py`, `app.py`
  - **Complexity**: Small

- [x] 4.2 Write unit tests for secret validation
  - Test short secret rejection
  - Test identical secret rejection
  - Test development vs production behavior
  - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

- [x] 5. Checkpoint - Security phase complete
  - Ensure all security tests pass
  - Verify application starts with valid secrets
  - Verify application refuses startup with invalid secrets
  - Ask the user if questions arise.

---

## Phase 2: Architecture

### 6. Rate Limit Decorator (Requirement 5)

- [x] 6.1 Create rate limit decorator in core/decorators.py
  - Create `core/decorators.py`
  - Implement `@rate_limit(key, limit, window_secs)` decorator
  - Support `{user_id}`, `{ip}`, `{api_key}` placeholders
  - Integrate with existing database-backed rate limiter
  - _Requirements: 5.1, 5.2, 5.5_
  - **Affected files**: `core/decorators.py`
  - **Complexity**: Medium

- [x] 6.2 Add rate limit exceeded response
  - Return HTTP 429 with JSON error body
  - Include Retry-After header
  - _Requirements: 5.3_
  - **Affected files**: `core/decorators.py`
  - **Complexity**: Small

- [x] 6.3 Apply decorator to existing endpoints
  - Replace inline rate limiting with decorator
  - Update auth, payments, and other blueprints
  - _Requirements: 5.4_
  - **Affected files**: `blueprints/auth.py`, `blueprints/payments.py`, `blueprints/api_keys.py`
  - **Complexity**: Small

- [x] 6.4 Write unit tests for rate limit decorator
  - Test rate limit enforcement
  - Test key placeholder resolution
  - Test 429 response format
  - Test Retry-After header
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

### 7. Input Validation Service (Requirement 6)

- [x] 7.1 Create validators service module
  - Create `services/validators.py`
  - Implement `validate_email(email)` with regex and normalization
  - Implement `validate_phone(phone)` with regex and normalization
  - Return normalized value or None
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - **Affected files**: `services/validators.py`
  - **Complexity**: Small

- [x] 7.2 Integrate validators into blueprints
  - Update auth blueprint to use validators
  - Update payments blueprint to use validators
  - Update invoices blueprint to use validators
  - _Requirements: 6.6_
  - **Affected files**: `blueprints/auth.py`, `blueprints/payments.py`, `blueprints/invoices.py`
  - **Complexity**: Small

- [x] 7.3 Write unit tests for validators
  - Test valid email normalization
  - Test invalid email rejection
  - Test valid phone normalization
  - Test invalid phone rejection
  - Test edge cases (empty, too long, special chars)
  - _Requirements: 6.2, 6.3, 6.4, 6.5_

### 8. Custom Exception Hierarchy (Requirement 7)

- [x] 8.1 Create exception classes in core/exceptions.py
  - Create `core/exceptions.py`
  - Define `OnePayError` base class with message, error_code, status_code
  - Define `ValidationError` for input validation failures
  - Define `ProviderError` for external service failures
  - Define `AuthenticationError` for auth failures
  - Define `AuthorizationError` for authorization failures
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - **Affected files**: `core/exceptions.py`
  - **Complexity**: Small

- [x] 8.2 Add global exception handler
  - Register error handler for OnePayError in app.py
  - Return standardized JSON response
  - Log error with correlation ID
  - _Requirements: 7.6_
  - **Affected files**: `app.py`
  - **Complexity**: Small

- [x] 8.3 Migrate existing error handling to use exceptions
  - Update blueprints to raise custom exceptions
  - Remove ad-hoc error response creation
  - _Requirements: 7.6_
  - **Affected files**: `blueprints/auth.py`, `blueprints/payments.py`, `blueprints/public.py`, `blueprints/invoices.py`, `blueprints/api_keys.py`, `blueprints/webhooks.py`
  - **Complexity**: Large

- [x] 8.4 Write unit tests for exception hierarchy
  - Test each exception type
  - Test error codes and status codes
  - Test global handler response format
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

### 9. Task Queue Integration (Requirement 10)

- [x] 9.1 Add Huey dependency and configuration
  - Add huey to requirements.txt
  - Configure Huey in `services/task_queue.py`
  - Use SQLite for task storage (lightweight)
  - Set immediate mode for development
  - _Requirements: 10.1_
  - **Affected files**: `requirements.txt`, `services/task_queue.py`, `config.py`
  - **Complexity**: Small

- [x] 9.2 Create webhook delivery task
  - Define `deliver_webhook_task` with retries
  - Replace thread-based webhook delivery
  - _Requirements: 10.2_
  - **Affected files**: `services/task_queue.py`, `services/webhook.py`
  - **Complexity**: Medium

- [x] 9.3 Create periodic cleanup tasks
  - Define `cleanup_rate_limits` periodic task
  - Define `cleanup_audit_logs` periodic task
  - Use Huey's crontab decorator
  - _Requirements: 10.3_
  - **Affected files**: `services/task_queue.py`
  - **Complexity**: Small

- [x] 9.4 Add worker process configuration
  - Document worker startup command
  - Add to Dockerfile or docker-compose
  - _Requirements: 10.4_
  - **Affected files**: `docker-compose.yml`, `docs/DEPLOYMENT.md`
  - **Complexity**: Small

- [x] 9.5 Maintain backward compatibility for development
  - Keep thread-based fallback when Huey not configured
  - Document both approaches
  - _Requirements: 10.5_
  - **Affected files**: `services/webhook.py`, `config.py`
  - **Complexity**: Small

- [x] 9.6 Write integration tests for task queue
  - Test webhook task execution
  - Test retry behavior
  - Test periodic task scheduling
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 10. Checkpoint - Architecture phase complete
  - Ensure all architecture tests pass
  - Verify rate limiting works with decorator
  - Verify task queue processes webhooks
  - Ask the user if questions arise.

---

## Phase 3: Performance

### 11. Database Indexes (Requirement 8)

- [x] 11.1 Create Alembic migration for transaction indexes
  - Add index on `transactions.created_at`
  - Add index on `transactions.status`
  - Add composite index on `transactions(user_id, created_at)`
  - Add composite index on `transactions(user_id, status)`
  - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - **Affected files**: `alembic/versions/`
  - **Complexity**: Small

- [x] 11.2 Create Alembic migration for audit log indexes
  - Add index on `audit_logs.created_at`
  - Add index on `audit_logs.user_id`
  - _Requirements: 8.5, 8.6_
  - **Affected files**: `alembic/versions/`
  - **Complexity**: Small

- [x] 11.3 Write integration tests for index usage
  - Verify EXPLAIN ANALYZE shows index usage
  - Test query performance improvement
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

### 12. N+1 Query Prevention (Requirement 9)

- [x] 12.1 Audit existing queries for N+1 patterns
  - Identify queries that load related data
  - Document affected endpoints
  - Create audit report with findings
  - _Requirements: 9.1_
  - **Affected files**: All blueprints and services (codebase-wide audit)
  - **Complexity**: Large

- [x] 12.2 Add joinedload/selectinload to queries
  - Update transaction queries to eager load user data
  - Update invoice queries to eager load related data
  - _Requirements: 9.1, 9.2_
  - **Affected files**: `blueprints/history.py`, `blueprints/invoices.py`
  - **Complexity**: Medium

- [x] 12.3 Add query count logging in development
  - Log warning when query count exceeds threshold
  - Add configuration for threshold value
  - _Requirements: 9.3_
  - **Affected files**: `app.py`, `config.py`
  - **Complexity**: Small

- [x] 12.4 Write integration tests for N+1 prevention
  - Assert constant query count regardless of page size
  - Test transaction history endpoint
  - _Requirements: 9.2, 9.4_

### 13. Caching Layer Activation (Requirement 11)

- [x] 13.1 Add caching to payment summary endpoint
  - Check cache before database query
  - Store result in cache on miss
  - Use 60-second TTL
  - _Requirements: 11.1, 11.2, 11.3, 11.4_
  - **Affected files**: `blueprints/payments.py` or relevant blueprint
  - **Complexity**: Small

- [x] 13.2 Implement cache invalidation on transaction changes
  - Invalidate cache when transaction created
  - Invalidate cache when transaction updated
  - _Requirements: 11.5_
  - **Affected files**: `services/webhook.py`, `blueprints/payments.py`
  - **Complexity**: Small

- [x] 13.3 Write integration tests for caching
  - Test cache hit returns cached data
  - Test cache miss queries database
  - Test invalidation clears cache
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

### 14. Database Dialect Consistency (Requirement 12)

- [x] 14.1 Update default development database to PostgreSQL
  - Modify `config.py` to use PostgreSQL in development
  - Update `.env.example` with PostgreSQL URL
  - _Requirements: 12.1_
  - **Affected files**: `config.py`, `.env.example`
  - **Complexity**: Small

- [x] 14.2 Update Docker Compose for local PostgreSQL
  - Add PostgreSQL service to docker-compose.yml
  - Configure volume for data persistence
  - _Requirements: 12.2_
  - **Affected files**: `docker-compose.yml`
  - **Complexity**: Small

- [x] 14.3 Document SQLite to PostgreSQL migration
  - Add migration guide to docs
  - Include common gotchas
  - _Requirements: 12.3_
  - **Affected files**: `docs/README.md` or new doc
  - **Complexity**: Small

- [x] 14.4 Ensure consistent JSON and datetime handling
  - Verify JSON serialization works in PostgreSQL
  - Verify timezone-aware datetime handling
  - _Requirements: 12.4_
  - **Affected files**: `models/*.py`, `config.py`
  - **Complexity**: Small

- [x] 15. Checkpoint - Performance phase complete
  - Run migrations and verify indexes created
  - Verify query performance improvement
  - Verify caching reduces database load
  - Ask the user if questions arise.

---

## Phase 4: Frontend

### 16. Tailwind CSS Build Pipeline (Requirement 13)

- [x] 16.1 Create Tailwind configuration
  - Create `tailwind.config.js`
  - Configure content paths for templates and JS
  - Configure theme extensions
  - _Requirements: 13.1_
  - **Affected files**: `tailwind.config.js`
  - **Complexity**: Small

- [x] 16.2 Create CSS input file
  - Create `static/css/input.css` with Tailwind directives
  - Configure custom fonts if needed
  - _Requirements: 13.1_
  - **Affected files**: `static/css/input.css`
  - **Complexity**: Small

- [x] 16.3 Add build scripts to package.json
  - Add `build:css` script for production build
  - Add `watch:css` script for development
  - Configure minification and purging
  - _Requirements: 13.2, 13.3, 13.4_
  - **Affected files**: `package.json`
  - **Complexity**: Small

- [x] 16.4 Update templates to use built CSS
  - Replace CDN link with local CSS file
  - Test all pages render correctly
  - _Requirements: 13.1_
  - **Affected files**: `templates/base.html`
  - **Complexity**: Small

- [x] 16.5 Verify CSS bundle size
  - Run production build
  - Verify gzipped size < 50KB
  - _Requirements: 13.2_

### 17. JavaScript Extraction (Requirement 14)

- [x] 17.1 Extract inline JavaScript from login.html
  - Create `static/js/login.js`
  - Move inline scripts to external file
  - Add defer attribute to script tag
  - _Requirements: 14.1_
  - **Affected files**: `static/js/login.js`, `templates/login.html`
  - **Complexity**: Small

- [x] 17.2 Add minification for production JS
  - Configure JS minification in build process
  - Add to package.json scripts
  - _Requirements: 14.2_
  - **Affected files**: `package.json`
  - **Complexity**: Small

- [x] 17.3 Implement nonce-based CSP for inline handlers
  - Generate nonce per request
  - Add nonce to allowed inline handlers
  - Update CSP header configuration
  - _Requirements: 14.5_
  - **Affected files**: `app.py`, `templates/base.html`
  - **Complexity**: Medium

- [x] 17.4 Write tests for JavaScript extraction
  - Verify login page functionality
  - Verify form submission works
  - _Requirements: 14.4_

### 18. Form Loading States (Requirement 15)

- [x] 18.1 Create loading state utility module
  - Create `static/js/loading-states.js`
  - Implement button disable/enable functions
  - Implement loading spinner display
  - _Requirements: 15.1, 15.4_
  - **Affected files**: `static/js/loading-states.js`
  - **Complexity**: Small

- [x] 18.2 Add loading states to login form
  - Disable submit button on click
  - Show loading indicator
  - Re-enable on error
  - _Requirements: 15.1, 15.2, 15.3_
  - **Affected files**: `static/js/login.js`
  - **Complexity**: Small

- [x] 18.3 Add loading states to payment forms
  - Apply to all forms making HTTP requests
  - Handle success/error states
  - _Requirements: 15.5_
  - **Affected files**: `static/js/dashboard.js`, relevant templates
  - **Complexity**: Medium

- [x] 18.4 Write tests for loading states
  - Test button disabled during submission
  - Test button re-enabled on error
  - Test double submission prevention
  - _Requirements: 15.1, 15.3, 15.4_

### 19. Accessibility Compliance (Requirement 16)

- [x] 19.1 Add aria-labels to interactive elements
  - Audit all templates for elements without visible text
  - Add aria-label attributes to buttons, links, icons
  - Document accessibility improvements
  - _Requirements: 16.1_
  - **Affected files**: `templates/base.html`, `templates/dashboard_base.html`, `templates/login.html`, `templates/dashboard.html`, and all other templates
  - **Complexity**: Large

- [x] 19.2 Ensure all form inputs have labels
  - Audit all forms for label associations
  - Add labels or aria-labelledby where missing
  - _Requirements: 16.2_
  - **Affected files**: `templates/*.html`
  - **Complexity**: Medium

- [x] 19.3 Add visible focus indicators
  - Add CSS focus styles for all interactive elements
  - Ensure keyboard navigation works
  - _Requirements: 16.3, 16.4_
  - **Affected files**: `static/css/input.css` or `static/css/style.css`
  - **Complexity**: Small

- [x] 19.4 Use semantic HTML elements
  - Replace divs with appropriate semantic elements (nav, main, aside, section, article)
  - Ensure proper heading hierarchy (h1-h6)
  - Add ARIA landmark regions
  - _Requirements: 16.5_
  - **Affected files**: All template files (codebase-wide refactor)
  - **Complexity**: Large

- [x] 19.5 Verify color contrast ratios
  - Audit color contrast against WCAG 2.1 AA
  - Adjust colors where needed
  - _Requirements: 16.6_
  - **Affected files**: `static/css/input.css` or `static/css/style.css`
  - **Complexity**: Small

- [x] 19.6 Write accessibility tests
  - Test keyboard navigation
  - Test screen reader compatibility
  - Test color contrast
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

- [x] 20. Checkpoint - Frontend phase complete
  - Verify CSS bundle size < 50KB
  - Verify all forms have loading states
  - Run accessibility audit
  - Ask the user if questions arise.

---

## Phase 5: Developer Experience

### 21. Local Setup Script (Requirement 17)

- [~] 21.1 Create setup script
  - Create `scripts/setup.sh`
  - Add Python version check
  - Add virtual environment creation
  - Add dependency installation
  - _Requirements: 17.1, 17.2, 17.3_
  - **Affected files**: `scripts/setup.sh`
  - **Complexity**: Small

- [~] 21.2 Add environment file handling
  - Copy `.env.example` to `.env` if not exists
  - _Requirements: 17.4_
  - **Affected files**: `scripts/setup.sh`
  - **Complexity**: Small

- [~] 21.3 Add database migration to setup
  - Start PostgreSQL via Docker
  - Run Alembic migrations
  - _Requirements: 17.5_
  - **Affected files**: `scripts/setup.sh`
  - **Complexity**: Small

- [~] 21.4 Add next steps output
  - Print setup completion message
  - Print instructions for running the app
  - Offer pre-commit hook installation
  - _Requirements: 17.6_
  - **Affected files**: `scripts/setup.sh`
  - **Complexity**: Small

### 22. Pre-Commit Hooks (Requirement 18)

- [~] 22.1 Create pre-commit configuration
  - Create `.pre-commit-config.yaml`
  - Configure ruff for linting
  - Configure ruff for formatting
  - Add trailing whitespace check
  - Add YAML syntax check
  - _Requirements: 18.1, 18.2, 18.3, 18.4_
  - **Affected files**: `.pre-commit-config.yaml`
  - **Complexity**: Small

- [~] 22.2 Add pre-commit installation to setup script
  - Offer to install pre-commit hooks during setup
  - _Requirements: 18.5_
  - **Affected files**: `scripts/setup.sh`
  - **Complexity**: Small

- [~] 22.3 Test pre-commit hooks
  - Verify ruff runs on commit
  - Verify formatting is applied
  - _Requirements: 18.2, 18.3, 18.4_

### 23. Type Checking Configuration (Requirement 19)

- [~] 23.1 Create mypy configuration
  - Create `mypy.ini`
  - Enable strict mode for new code
  - Allow gradual typing for existing code
  - _Requirements: 19.1, 19.2, 19.3_
  - **Affected files**: `mypy.ini`
  - **Complexity**: Small

- [~] 23.2 Document mypy usage
  - Add mypy instructions to README
  - _Requirements: 19.4_
  - **Affected files**: `README.md`
  - **Complexity**: Small

- [~] 23.3 Add mypy to pre-commit hooks
  - Add optional mypy hook to pre-commit config
  - _Requirements: 19.5_
  - **Affected files**: `.pre-commit-config.yaml`
  - **Complexity**: Small

### 24. Test Fixture Isolation (Requirement 20)

- [~] 24.1 Create isolated database fixture
  - Add fixture to `tests/conftest.py`
  - Use transaction rollback for isolation
  - _Requirements: 20.1, 20.2_
  - **Affected files**: `tests/conftest.py`
  - **Complexity**: Small

- [~] 24.2 Add cache reset fixture
  - Create fixture to reset global cache
  - Apply to tests that use cache
  - _Requirements: 20.3_
  - **Affected files**: `tests/conftest.py`
  - **Complexity**: Small

- [~] 24.3 Add rate limiter reset fixture
  - Create fixture to reset rate limiter state
  - Apply to tests that use rate limiting
  - _Requirements: 20.4_
  - **Affected files**: `tests/conftest.py`
  - **Complexity**: Small

- [~] 24.4 Create factory fixtures
  - Add user factory fixture
  - Add transaction factory fixture
  - _Requirements: 20.5_
  - **Affected files**: `tests/conftest.py`
  - **Complexity**: Medium

- [~] 24.5 Write tests for fixture isolation
  - Verify tests don't affect each other
  - Verify cache is reset between tests
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

### 25. Linter Configuration (Requirement 24)

- [~] 25.1 Create pylintrc configuration
  - Create `.pylintrc`
  - Disable warnings conflicting with black
  - Specify project naming conventions
  - _Requirements: 24.1, 24.2, 24.3_
  - **Affected files**: `.pylintrc`
  - **Complexity**: Small

- [~] 25.2 Create pyproject.toml with ruff configuration
  - Create or update `pyproject.toml`
  - Configure ruff rules
  - Ensure compatibility with pre-commit
  - _Requirements: 24.4, 24.5_
  - **Affected files**: `pyproject.toml`
  - **Complexity**: Small

- [ ] 26. Checkpoint - Developer experience phase complete
  - Run setup script on fresh environment
  - Verify pre-commit hooks work
  - Run mypy and verify configuration
  - Ask the user if questions arise.

---

## Phase 6: Observability

### 27. Two-Factor Authentication Fix (Requirement 4)

- [~] 27.1 Fix 2FA verification flow
  - Ensure `two_factor_enabled` check works in login
  - Require 2FA verification before full access
  - _Requirements: 4.1_
  - **Affected files**: `core/auth.py`, `blueprints/auth.py`
  - **Complexity**: Small

- [~] 27.2 Add failed attempt counter for 2FA
  - Increment counter on incorrect code
  - Lock account after 5 failed attempts in 15 minutes
  - _Requirements: 4.2, 4.3_
  - **Affected files**: `blueprints/auth.py`, `models/user.py`
  - **Complexity**: Small

- [~] 27.3 Fix 2FA disable flow
  - Set `two_factor_enabled` to False on disable
  - _Requirements: 4.4_
  - **Affected files**: `blueprints/auth.py` or `blueprints/settings.py`
  - **Complexity**: Small

- [~] 27.4 Add session validation for 2FA page
  - Redirect to login if `pre_2fa_user_id` not in session
  - _Requirements: 4.5_
  - **Affected files**: `blueprints/auth.py`
  - **Complexity**: Small

- [~] 27.5 Write unit tests for 2FA flow
  - Test 2FA required for enabled users
  - Test failed attempt counter
  - Test account lockout
  - Test session validation
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

### 28. Correlation IDs for Logging (Requirement 22)

- [~] 28.1 Add correlation ID generation
  - Generate or extract from `X-Request-ID` header
  - Store in Flask's `g` object
  - _Requirements: 22.1, 22.5_
  - **Affected files**: `app.py`
  - **Complexity**: Small

- [~] 28.2 Add correlation ID to log messages
  - Update logging filter to include correlation ID
  - Apply to all log messages in request context
  - _Requirements: 22.2_
  - **Affected files**: `core/logging_filters.py`
  - **Complexity**: Small

- [~] 28.3 Add correlation ID to response headers
  - Add `X-Correlation-ID` header to all responses
  - _Requirements: 22.3_
  - **Affected files**: `app.py`
  - **Complexity**: Small

- [~] 28.4 Forward correlation ID to external requests
  - Include correlation ID in outgoing HTTP requests
  - _Requirements: 22.4_
  - **Affected files**: `services/korapay.py`, `services/webhook.py`
  - **Complexity**: Small

- [~] 28.5 Write tests for correlation ID tracking
  - Test ID generation
  - Test ID extraction from header
  - Test ID in response header
  - Test ID in logs
  - _Requirements: 22.1, 22.2, 22.3, 22.5_

### 29. Cache-Control Headers (Requirement 23)

- [~] 29.1 Add cache headers to static assets
  - Add `Cache-Control: public, max-age=31536000` to versioned assets
  - Add `Cache-Control: public, max-age=3600` to non-versioned assets
  - _Requirements: 23.1, 23.2_
  - **Affected files**: `app.py`
  - **Complexity**: Small

- [~] 29.2 Add ETag headers to static assets
  - Generate ETag from file content hash
  - Support conditional requests
  - _Requirements: 23.3_
  - **Affected files**: `app.py`
  - **Complexity**: Small

- [~] 29.3 Implement content-based filenames for cache busting
  - Add build step to generate hashed filenames
  - Update template references
  - _Requirements: 23.4_
  - **Affected files**: Build scripts, `templates/base.html`
  - **Complexity**: Medium

- [~] 29.4 Write tests for cache headers
  - Test Cache-Control header presence
  - Test ETag header presence
  - Test conditional request handling
  - _Requirements: 23.1, 23.2, 23.3_

### 30. Error Handling Standardization (Requirement 25)

- [~] 30.1 Define error response format
  - Document standard JSON format: `{success, message, error_code}`
  - Create error code reference
  - _Requirements: 25.1, 25.5_
  - **Affected files**: `docs/API.md` or new doc
  - **Complexity**: Small

- [~] 30.2 Ensure HTTP status codes match error type
  - Audit all error responses
  - Update status codes where needed
  - _Requirements: 25.2_
  - **Affected files**: `blueprints/*.py`, `core/exceptions.py`
  - **Complexity**: Small

- [~] 30.3 Add correlation ID to error logs
  - Ensure all errors logged with correlation ID
  - _Requirements: 25.3_
  - **Affected files**: `app.py`, `core/exceptions.py`
  - **Dependencies**: Task 28.1 (correlation ID generation)
  - **Complexity**: Small

- [~] 30.4 Remove internal details from error messages
  - Audit error messages for internal info
  - Replace with user-friendly messages
  - _Requirements: 25.4_
  - **Affected files**: `blueprints/*.py`, `services/*.py`
  - **Complexity**: Small

- [~] 30.5 Write tests for error handling
  - Test error response format
  - Test status codes
  - Test correlation ID in errors
  - _Requirements: 25.1, 25.2, 25.3, 25.4_

- [ ] 31. Checkpoint - Observability phase complete
  - Verify 2FA flow works correctly
  - Verify correlation IDs appear in logs
  - Verify cache headers on static assets
  - Verify error responses are standardized
  - Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property-based tests are not included as the design document indicates they are not applicable for these infrastructure improvements
- All testing is done via unit tests, integration tests, and security tests with specific attack vectors
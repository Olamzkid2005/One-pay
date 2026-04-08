# Requirements Document: OnePay Codebase Improvements

## Introduction

This document specifies requirements for comprehensive improvements to the OnePay payment processing platform. The improvements address critical security vulnerabilities, architectural deficiencies, code quality issues, frontend performance, and developer experience gaps. Each requirement follows EARS patterns and INCOSE quality rules for clarity and testability.

## Glossary

- **OnePay**: The payment processing platform being improved
- **Webhook**: HTTP callback that delivers payment status updates to merchant-configured URLs
- **Inbound Webhook**: Webhook received from external payment providers (KoraPay, VoicePay)
- **Outbound Webhook**: Webhook sent to merchant-configured URLs
- **TOCTOU**: Time-of-Check-Time-of-Use, a race condition vulnerability
- **SSRF**: Server-Side Request Forgery, a security vulnerability allowing attackers to make requests from the server
- **2FA**: Two-Factor Authentication
- **Idempotency**: Property where an operation produces the same result when executed multiple times
- **Huey**: A lightweight task queue for Python
- **N+1 Query**: A performance anti-pattern where N additional queries are executed for N records
- **ARIA**: Accessible Rich Internet Applications, web accessibility standards
- **CSRF**: Cross-Site Request Forgery
- **Rate Limit**: Restriction on the number of requests a client can make within a time window
- **Correlation ID**: Unique identifier for tracking requests across logs and services

---

## Requirements

### Requirement 1: Webhook Signature Validation

**User Story:** As a security engineer, I want webhook signature validation to enforce non-empty secrets, so that unauthorized parties cannot send payment status updates.

**Priority:** Critical  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** High (security vulnerability if not implemented correctly)  
**Dependencies:** None  
**Affected Components:** `config.py`, `app.py`, `blueprints/webhooks.py`, `services/webhook.py`

#### Acceptance Criteria

1. WHEN the INBOUND_WEBHOOK_SECRET environment variable is empty or unset, THE System SHALL refuse to start and log a critical error message
2. WHEN an inbound webhook request is received, THE Webhook_Handler SHALL verify the HMAC-SHA256 signature using the configured secret
3. WHEN signature verification fails, THE Webhook_Handler SHALL return HTTP 401 Unauthorized and log the client IP address
4. WHERE the APP_ENV is production, THE System SHALL require INBOUND_WEBHOOK_SECRET to be at least 32 characters

---

### Requirement 2: Webhook Idempotency

**User Story:** As a merchant, I want duplicate webhooks to be detected and ignored, so that my payment records remain accurate.

**Priority:** Critical  
**Complexity:** Medium  
**Estimated Effort:** 6-8 hours  
**Risk Level:** High (data integrity issue if not implemented correctly)  
**Dependencies:** Requirement 10 (Task Queue Integration for cleanup)  
**Affected Components:** `models/webhook_idempotency.py`, `blueprints/webhooks.py`, `services/webhook.py`, `alembic/versions/`

#### Acceptance Criteria

1. WHEN an inbound webhook is received, THE Webhook_Handler SHALL extract a unique identifier from the payload
2. WHEN a webhook with a previously-seen identifier is received, THE Webhook_Handler SHALL return HTTP 200 OK without processing the webhook again
3. THE System SHALL store processed webhook identifiers for a minimum of 24 hours
4. WHEN a webhook is processed successfully, THE System SHALL record the webhook identifier with a timestamp

---

### Requirement 3: SSRF Prevention for Logo URL Validation

**User Story:** As a security engineer, I want logo URL validation to prevent SSRF attacks, so that internal resources cannot be accessed through the application.

**Priority:** Critical  
**Complexity:** High  
**Estimated Effort:** 8-12 hours  
**Risk Level:** Critical (SSRF can expose internal infrastructure)  
**Dependencies:** None  
**Affected Components:** `services/url_validator.py`, `blueprints/invoices.py` or relevant blueprint

#### Acceptance Criteria

1. WHEN a logo URL is submitted, THE URL_Validator SHALL resolve the hostname to an IP address before making any HTTP request
2. WHEN the resolved IP address is a private, loopback, link-local, or multicast address, THE URL_Validator SHALL reject the URL
3. WHEN making the HTTP request, THE HTTP_Client SHALL use the resolved IP address directly with the original hostname in the Host header
4. WHEN a DNS resolution race condition is detected, THE System SHALL reject the request and log a security warning

---

### Requirement 4: Two-Factor Authentication Implementation

**User Story:** As a user, I want two-factor authentication to function correctly, so that my account has an additional security layer.

**Priority:** High  
**Complexity:** Medium  
**Estimated Effort:** 6-8 hours  
**Risk Level:** High (authentication bypass if not fixed correctly)  
**Dependencies:** None  
**Affected Components:** `core/auth.py`, `blueprints/auth.py`, `models/user.py`

#### Acceptance Criteria

1. WHEN a user with two_factor_enabled set to True logs in, THE Auth_System SHALL require 2FA verification before granting full access
2. WHEN the 2FA code is incorrect, THE Auth_System SHALL increment a failed attempt counter
3. WHEN failed 2FA attempts exceed 5 within 15 minutes, THE Auth_System SHALL temporarily lock the account
4. WHEN a user disables 2FA, THE System SHALL set two_factor_enabled to False
5. WHERE the 2FA verification page is accessed without a pre_2fa_user_id in session, THE System SHALL redirect to the login page

---

### Requirement 5: Rate Limit Decorator

**User Story:** As a developer, I want a reusable rate limit decorator, so that rate limiting logic is not duplicated across endpoints.

**Priority:** High  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Medium (incorrect implementation could allow abuse)  
**Dependencies:** None  
**Affected Components:** `core/decorators.py`, `blueprints/auth.py`, `blueprints/payments.py`, `blueprints/api_keys.py`

#### Acceptance Criteria

1. THE System SHALL provide a @rate_limit decorator that accepts key, limit, and window_secs parameters
2. WHEN the decorator is applied to a route, THE System SHALL check the rate limit before executing the route handler
3. WHEN the rate limit is exceeded, THE System SHALL return HTTP 429 Too Many Requests with a Retry-After header
4. THE decorator SHALL support both authenticated and anonymous rate limiting keys
5. THE decorator SHALL integrate with the existing database-backed rate limiter

---

### Requirement 6: Input Validation Service

**User Story:** As a developer, I want centralized input validation functions, so that email and phone validation logic is not duplicated.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Low (validation logic already exists, just centralizing)  
**Dependencies:** None  
**Affected Components:** `services/validators.py`, `blueprints/auth.py`, `blueprints/payments.py`, `blueprints/invoices.py`

#### Acceptance Criteria

1. THE System SHALL provide a services/validators.py module with validate_email and validate_phone functions
2. WHEN validate_email is called with an invalid email format, THE function SHALL return None
3. WHEN validate_email is called with a valid email, THE function SHALL return the normalized lowercase email
4. WHEN validate_phone is called with an invalid phone format, THE function SHALL return None
5. WHEN validate_phone is called with a valid phone, THE function SHALL return the normalized phone number
6. THE validators SHALL be used by all blueprints that accept email or phone input

---

### Requirement 7: Custom Exception Hierarchy

**User Story:** As a developer, I want a custom exception hierarchy, so that errors are handled consistently across the application.

**Priority:** Medium  
**Complexity:** High  
**Estimated Effort:** 10-14 hours  
**Risk Level:** Medium (incorrect migration could break error handling)  
**Dependencies:** None  
**Affected Components:** `core/exceptions.py`, `app.py`, all blueprints

#### Acceptance Criteria

1. THE System SHALL define a base OnePayError exception class
2. THE System SHALL define ValidationError for input validation failures
3. THE System SHALL define ProviderError for external service failures
4. THE System SHALL define AuthenticationError for authentication failures
5. THE System SHALL define AuthorizationError for authorization failures
6. WHEN an exception is raised, THE System SHALL include an error code and user-friendly message

---

### Requirement 8: Database Indexes

**User Story:** As a database administrator, I want appropriate indexes on frequently queried columns, so that query performance is acceptable.

**Priority:** High  
**Complexity:** Low  
**Estimated Effort:** 2-3 hours  
**Risk Level:** Low (indexes are additive, can be rolled back easily)  
**Dependencies:** None  
**Affected Components:** `alembic/versions/`, database schema

#### Acceptance Criteria

1. THE System SHALL have an index on transactions.created_at for time-based queries
2. THE System SHALL have an index on transactions.status for status filtering
3. THE System SHALL have a composite index on transactions(user_id, created_at) for user history queries
4. THE System SHALL have a composite index on transactions(user_id, status) for user status filtering
5. THE System SHALL have an index on audit_logs.created_at for log retention queries
6. THE System SHALL have an index on audit_logs.user_id for user audit queries

---

### Requirement 9: N+1 Query Prevention

**User Story:** As a developer, I want N+1 queries eliminated, so that database performance is optimized.

**Priority:** High  
**Complexity:** High  
**Estimated Effort:** 12-16 hours  
**Risk Level:** Medium (incorrect eager loading could cause performance issues)  
**Dependencies:** Requirement 8 (Database Indexes)  
**Affected Components:** All blueprints and services with database queries

#### Acceptance Criteria

1. WHEN loading transactions with related user data, THE System SHALL use SQLAlchemy joinedload or selectinload
2. WHEN displaying transaction history, THE System SHALL execute a constant number of queries regardless of page size
3. THE System SHALL log a warning when a query count threshold is exceeded during development
4. THE System SHALL include query count assertions in integration tests

---

### Requirement 10: Task Queue Integration

**User Story:** As a system administrator, I want background tasks to use a task queue, so that tasks are not duplicated across gunicorn workers.

**Priority:** High  
**Complexity:** Medium  
**Estimated Effort:** 8-10 hours  
**Risk Level:** Medium (incorrect configuration could cause task failures)  
**Dependencies:** None  
**Affected Components:** `services/task_queue.py`, `services/webhook.py`, `config.py`, `docker-compose.yml`

#### Acceptance Criteria

1. THE System SHALL integrate Huey as the task queue backend
2. WHEN a webhook delivery is needed, THE System SHALL enqueue the task instead of spawning a thread
3. WHEN a periodic cleanup task is scheduled, THE System SHALL use Huey's periodic task decorator
4. THE System SHALL provide a separate worker process configuration for production deployment
5. THE System SHALL maintain backward compatibility with the thread-based approach for development

---

### Requirement 11: Caching Layer Activation

**User Story:** As a developer, I want the existing cache service to be used, so that analytics queries do not hit the database on every request.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Low (cache service already exists)  
**Dependencies:** None  
**Affected Components:** `blueprints/payments.py`, `services/webhook.py`, `services/cache.py`

#### Acceptance Criteria

1. WHEN the payment summary endpoint is called, THE System SHALL check the cache before querying the database
2. WHEN the cache contains valid summary data, THE System SHALL return the cached response
3. WHEN the cache is empty or expired, THE System SHALL query the database and store the result in cache
4. THE System SHALL use a cache TTL of 60 seconds for summary data
5. WHEN a transaction is created or updated, THE System SHALL invalidate the relevant cache entries

---

### Requirement 12: Database Dialect Consistency

**User Story:** As a developer, I want consistent database behavior between development and production, so that bugs are caught early.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 2-3 hours  
**Risk Level:** Low (configuration change only)  
**Dependencies:** None  
**Affected Components:** `config.py`, `.env.example`, `docker-compose.yml`, documentation

#### Acceptance Criteria

1. WHERE the APP_ENV is development, THE System SHALL use PostgreSQL by default
2. THE System SHALL provide a Docker Compose configuration for local PostgreSQL
3. THE System SHALL document the migration from SQLite to PostgreSQL for existing developers
4. THE System SHALL use the same JSON and datetime handling across both environments

---

### Requirement 13: Tailwind CSS Build Pipeline

**User Story:** As a user, I want pages to load quickly, so that my experience is responsive.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Low (build pipeline is isolated from runtime)  
**Dependencies:** None  
**Affected Components:** `tailwind.config.js`, `package.json`, `static/css/`, `templates/base.html`

#### Acceptance Criteria

1. THE System SHALL replace Tailwind CDN with a build pipeline
2. THE production CSS bundle SHALL be less than 50KB gzipped
3. THE System SHALL generate CSS during the build process
4. THE System SHALL purge unused CSS classes in production builds
5. THE System SHALL maintain hot-reload capability during development

---

### Requirement 14: JavaScript Extraction

**User Story:** As a developer, I want inline JavaScript extracted to separate files, so that code is maintainable and cacheable.

**Priority:** Low  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Low (functionality should remain unchanged)  
**Dependencies:** None  
**Affected Components:** `static/js/login.js`, `templates/login.html`, `app.py`, `package.json`

#### Acceptance Criteria

1. THE System SHALL extract inline JavaScript from login.html to a separate static/js/login.js file
2. THE extracted JavaScript files SHALL be minified in production
3. THE System SHALL add Cache-Control headers to static JavaScript files
4. THE System SHALL maintain functionality after extraction
5. THE System SHALL use nonce-based CSP for inline event handlers where necessary

---

### Requirement 15: Form Loading States

**User Story:** As a user, I want visual feedback when submitting forms, so that I know my action is being processed.

**Priority:** Medium  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Low (UI enhancement only)  
**Dependencies:** None  
**Affected Components:** `static/js/loading-states.js`, `static/js/login.js`, `static/js/dashboard.js`, templates

#### Acceptance Criteria

1. WHEN a form is submitted, THE System SHALL disable the submit button and show a loading indicator
2. WHEN the form submission succeeds, THE System SHALL navigate to the success page or show a success message
3. WHEN the form submission fails, THE System SHALL re-enable the submit button and show an error message
4. THE System SHALL prevent double submission by tracking the submission state
5. THE System SHALL apply loading states to all forms that make HTTP requests

---

### Requirement 16: Accessibility Compliance

**User Story:** As a user with disabilities, I want the application to be accessible, so that I can use all features.

**Priority:** High  
**Complexity:** High  
**Estimated Effort:** 16-20 hours  
**Risk Level:** Low (accessibility improvements are additive)  
**Dependencies:** None  
**Affected Components:** All template files, CSS files

#### Acceptance Criteria

1. THE System SHALL add aria-label attributes to all interactive elements without visible text
2. THE System SHALL ensure all form inputs have associated labels
3. THE System SHALL provide visible focus indicators for all interactive elements
4. THE System SHALL support keyboard navigation for all interactive components
5. THE System SHALL use semantic HTML elements for headings, landmarks, and lists
6. THE System SHALL ensure color contrast ratios meet WCAG 2.1 AA standards

---

### Requirement 17: Local Setup Script

**User Story:** As a new developer, I want an automated setup script, so that I can start developing quickly.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 2-3 hours  
**Risk Level:** Low (developer tooling only)  
**Dependencies:** Requirement 12 (PostgreSQL setup)  
**Affected Components:** `scripts/setup.sh`

#### Acceptance Criteria

1. THE System SHALL provide a scripts/setup.sh script that sets up the development environment
2. THE setup script SHALL create a Python virtual environment
3. THE setup script SHALL install all dependencies from requirements.txt
4. THE setup script SHALL copy .env.example to .env if .env does not exist
5. THE setup script SHALL run database migrations
6. THE setup script SHALL print next steps for the developer

---

### Requirement 18: Pre-Commit Hooks

**User Story:** As a developer, I want pre-commit hooks, so that code quality issues are caught before commit.

**Priority:** Low  
**Complexity:** Low  
**Estimated Effort:** 1-2 hours  
**Risk Level:** Low (developer tooling only)  
**Dependencies:** None  
**Affected Components:** `.pre-commit-config.yaml`, `scripts/setup.sh`

#### Acceptance Criteria

1. THE System SHALL provide a .pre-commit-config.yaml file
2. THE pre-commit hooks SHALL run ruff for linting
3. THE pre-commit hooks SHALL run black for code formatting
4. THE pre-commit hooks SHALL check for trailing whitespace and YAML syntax
5. THE setup script SHALL offer to install pre-commit hooks

---

### Requirement 19: Type Checking Configuration

**User Story:** As a developer, I want mypy configuration, so that type errors are caught during development.

**Priority:** Low  
**Complexity:** Low  
**Estimated Effort:** 1-2 hours  
**Risk Level:** Low (developer tooling only)  
**Dependencies:** None  
**Affected Components:** `mypy.ini`, `.pre-commit-config.yaml`, `README.md`

#### Acceptance Criteria

1. THE System SHALL provide a mypy.ini configuration file
2. THE mypy configuration SHALL enable strict mode for new code
3. THE mypy configuration SHALL allow gradual typing for existing code
4. THE System SHALL document how to run mypy in the README
5. THE pre-commit hooks SHALL optionally run mypy

---

### Requirement 20: Test Fixture Isolation

**User Story:** As a developer, I want isolated test fixtures, so that tests do not interfere with each other.

**Priority:** High  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Medium (incorrect isolation could cause test failures)  
**Dependencies:** None  
**Affected Components:** `tests/conftest.py`

#### Acceptance Criteria

1. THE System SHALL provide a pytest fixture that creates an isolated test database
2. EACH test SHALL run in a transaction that is rolled back after the test
3. THE System SHALL reset the global cache between tests
4. THE System SHALL reset the global rate limiter state between tests
5. THE System SHALL provide factory fixtures for creating test users and transactions

---

### Requirement 21: Strong Secret Enforcement

**User Story:** As a security engineer, I want weak secrets to fail application startup, so that insecure configurations are not deployed.

**Priority:** Critical  
**Complexity:** Low  
**Estimated Effort:** 2-3 hours  
**Risk Level:** High (security misconfiguration if not implemented correctly)  
**Dependencies:** None  
**Affected Components:** `config.py`, `app.py`

#### Acceptance Criteria

1. WHEN SECRET_KEY is less than 32 characters, THE System SHALL refuse to start
2. WHEN HMAC_SECRET is less than 32 characters, THE System SHALL refuse to start
3. WHEN SECRET_KEY equals HMAC_SECRET, THE System SHALL refuse to start
4. WHERE APP_ENV is development, THE System SHALL log a warning but allow startup
5. WHERE APP_ENV is production, THE System SHALL refuse to start and log a critical error

---

### Requirement 22: Correlation IDs for Logging

**User Story:** As a developer, I want correlation IDs in logs, so that I can trace requests across the system.

**Priority:** Medium  
**Complexity:** Low  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Low (logging enhancement only)  
**Dependencies:** None  
**Affected Components:** `app.py`, `core/logging_filters.py`, `services/korapay.py`, `services/webhook.py`

#### Acceptance Criteria

1. WHEN a request is received, THE System SHALL generate or extract a correlation ID
2. THE System SHALL include the correlation ID in all log messages for that request
3. THE System SHALL return the correlation ID in the X-Correlation-ID response header
4. WHEN an external request is made, THE System SHALL forward the correlation ID
5. THE System SHALL use the X-Request-ID header if present as the correlation ID

---

### Requirement 23: Cache-Control Headers

**User Story:** As a user, I want static assets to be cached, so that pages load faster on repeat visits.

**Priority:** Low  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Low (caching headers are additive)  
**Dependencies:** None  
**Affected Components:** `app.py`, `templates/base.html`, build scripts

#### Acceptance Criteria

1. THE System SHALL add Cache-Control: public, max-age=31536000 to versioned static assets
2. THE System SHALL add Cache-Control: no-cache to HTML pages
3. THE System SHALL add ETag headers to static assets for conditional requests
4. THE System SHALL use content-based filenames for cache busting
5. THE System SHALL configure the web server to serve static assets with appropriate headers

---

### Requirement 24: Linter Configuration

**User Story:** As a developer, I want consistent linter configuration, so that code style is uniform across the team.

**Priority:** Low  
**Complexity:** Low  
**Estimated Effort:** 1-2 hours  
**Risk Level:** Low (developer tooling only)  
**Dependencies:** Requirement 18 (Pre-commit hooks)  
**Affected Components:** `.pylintrc`, `pyproject.toml`

#### Acceptance Criteria

1. THE System SHALL provide a .pylintrc configuration file
2. THE pylintrc SHALL disable warnings that conflict with black formatting
3. THE pylintrc SHALL specify project-specific naming conventions
4. THE System SHALL provide a pyproject.toml with ruff configuration
5. THE linter configuration SHALL be compatible with the pre-commit hooks

---

### Requirement 25: Error Handling Standardization

**User Story:** As a developer, I want standardized error responses, so that clients can handle errors consistently.

**Priority:** Medium  
**Complexity:** Medium  
**Estimated Effort:** 6-8 hours  
**Risk Level:** Medium (incorrect standardization could break API clients)  
**Dependencies:** Requirement 7 (Custom Exception Hierarchy), Requirement 22 (Correlation IDs)  
**Affected Components:** `docs/API.md`, all blueprints, `core/exceptions.py`, `app.py`

#### Acceptance Criteria

1. WHEN an error occurs, THE System SHALL return a JSON response with success, message, and error_code fields
2. THE System SHALL use HTTP status codes appropriate to the error type
3. THE System SHALL log all errors with the correlation ID
4. THE System SHALL not expose internal implementation details in error messages
5. THE System SHALL provide a reference of all error codes in the API documentation
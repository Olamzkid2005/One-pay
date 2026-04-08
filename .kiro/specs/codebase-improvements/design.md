# Design Document: OnePay Codebase Improvements

## Overview

This document provides a comprehensive technical design for 25 improvements to the OnePay payment processing platform. The improvements address security vulnerabilities, architectural deficiencies, code quality issues, frontend performance, and developer experience gaps.

### Design Goals

1. **Security Hardening**: Eliminate vulnerabilities in webhook handling, SSRF prevention, and secret management
2. **Architectural Improvements**: Introduce task queue, caching layer, and proper separation of concerns
3. **Code Quality**: Centralize validation, standardize error handling, and improve testability
4. **Performance**: Optimize database queries, add indexes, and improve frontend load times
5. **Developer Experience**: Automate setup, add pre-commit hooks, and improve type safety

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use Huey for task queue | Lightweight, Redis-free option that integrates with existing Flask app; supports periodic tasks |
| Keep existing cache service | Already implemented with Redis fallback; just needs activation in endpoints |
| Add decorators module | Reusable rate limiting without code duplication across blueprints |
| Create validators service | Centralized email/phone validation used by all blueprints |
| Use Tailwind CLI build | Reduces CSS from ~3MB CDN to <50KB gzipped; enables purging |

---

## Architecture

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Flask Application                       │
├─────────────────────────────────────────────────────────────┤
│  Blueprints: auth, payments, public, invoices, api_keys,    │
│              webhooks                                        │
├─────────────────────────────────────────────────────────────┤
│  Services: cache, rate_limiter, webhook, security, email    │
├─────────────────────────────────────────────────────────────┤
│  Models: User, Transaction, AuditLog, RateLimit, Invoice    │
├─────────────────────────────────────────────────────────────┤
│  Database: SQLite (dev) / PostgreSQL (prod)                 │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Flask Application                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Blueprints: auth, payments, public, invoices, api_keys, webhooks       │
├─────────────────────────────────────────────────────────────────────────┤
│  Decorators: rate_limit, cache_invalidatation, audit_log                │
│  (NEW: core/decorators.py)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Services: cache, rate_limiter, webhook, security, email,               │
│            validators (NEW), task_queue (NEW)                            │
├─────────────────────────────────────────────────────────────────────────┤
│  Exceptions: OnePayError, ValidationError, ProviderError,               │
│              AuthenticationError, AuthorizationError (NEW)               │
├─────────────────────────────────────────────────────────────────────────┤
│  Models: User, Transaction, AuditLog, RateLimit, Invoice,               │
│          WebhookIdempotency (NEW)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Task Queue: Huey (NEW)                                                  │
│  - Webhook delivery worker                                               │
│  - Periodic cleanup tasks                                                │
│  - Cache invalidation                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  Database: PostgreSQL (dev & prod)                                       │
│  - New indexes for performance                                           │
│  - Webhook idempotency table                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```mermaid
graph TB
    subgraph "Frontend"
        A[Tailwind CSS Build] --> B[Static CSS]
        C[JavaScript Modules] --> D[Static JS]
    end

    subgraph "Flask Application"
        E[Blueprints] --> F[Decorators]
        F --> G[Services]
        G --> H[Exceptions]
        G --> I[Models]
    end

    subgraph "Task Queue"
        J[Huey Consumer] --> K[Webhook Tasks]
        J --> L[Cleanup Tasks]
    end

    subgraph "Data Layer"
        I --> M[(PostgreSQL)]
        G --> N[Cache Layer]
    end

    E --> O[HTTP Requests]
    O --> E
    G --> J
```

---

## Components and Interfaces

### 1. Rate Limit Decorator (Requirement 5)

**File**: `core/decorators.py`

```python
from functools import wraps
from flask import request, g, jsonify
from services.rate_limiter import check_rate_limit

def rate_limit(key: str, limit: int, window_secs: int = 60, critical: bool = False):
    """
    Decorator for rate limiting routes.
    
    Args:
        key: Rate limit key template. Supports {user_id}, {ip}, {api_key} placeholders
        limit: Maximum requests allowed in window
        window_secs: Window duration in seconds
        critical: If True, fail closed on DB errors
    
    Usage:
        @rate_limit("link:user:{user_id}", limit=10, window_secs=60)
        def create_link():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from database import get_db
            
            # Resolve key placeholders
            resolved_key = key.format(
                user_id=g.get("user_id", "anon"),
                ip=client_ip(),
                api_key=g.get("api_key", "none")
            )
            
            with get_db() as db:
                if not check_rate_limit(db, resolved_key, limit, window_secs, critical):
                    return jsonify({
                        "success": False,
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please wait and try again.",
                        "retry_after": window_secs
                    }), 429, {"Retry-After": str(window_secs)}
            
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

### 2. Input Validation Service (Requirement 6)

**File**: `services/validators.py`

```python
import re
from typing import Optional

# Pre-compiled patterns for performance
_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{6,14}$')

def validate_email(email: str) -> Optional[str]:
    """
    Validate and normalize email address.
    
    Returns:
        Normalized lowercase email if valid, None otherwise.
    """
    if not email or len(email) > 255:
        return None
    
    email = email.strip().lower()
    
    if not _EMAIL_PATTERN.match(email):
        return None
    
    return email

def validate_phone(phone: str) -> Optional[str]:
    """
    Validate and normalize phone number.
    
    Returns:
        Normalized phone number if valid, None otherwise.
    """
    if not phone or len(phone) > 20:
        return None
    
    # Remove spaces, dashes, parentheses
    phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
    
    if not _PHONE_PATTERN.match(phone):
        return None
    
    return phone
```

### 3. Custom Exception Hierarchy (Requirement 7)

**File**: `core/exceptions.py`

```python
from typing import Optional

class OnePayError(Exception):
    """Base exception for all OnePay errors."""
    
    def __init__(self, message: str, error_code: str, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)

class ValidationError(OnePayError):
    """Input validation failure."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400
        )

class ProviderError(OnePayError):
    """External service (KoraPay, VoicePay) failure."""
    
    def __init__(self, message: str, provider: str, original_error: Optional[str] = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(
            message=message,
            error_code="PROVIDER_ERROR",
            status_code=502
        )

class AuthenticationError(OnePayError):
    """Authentication failure."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )

class AuthorizationError(OnePayError):
    """Authorization failure."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )
```

### 4. Task Queue Integration (Requirement 10)

**File**: `services/task_queue.py`

```python
"""
Huey task queue integration for background processing.

Replaces thread-based webhook delivery and periodic cleanup tasks.
"""

import logging
from huey import SqliteHuey, crontab
from config import Config

logger = logging.getLogger(__name__)

# Initialize Huey with SQLite (lightweight, no Redis dependency)
huey = SqliteHuey(
    filename=Config.HUEY_DB_PATH if hasattr(Config, 'HUEY_DB_PATH') else 'huey.db',
    results=True,
    store_errors=True,
    immediate=Config.DEBUG  # Run tasks synchronously in debug mode
)

@huey.task(retries=3, retry_delay=60)
def deliver_webhook_task(webhook_data: dict):
    """
    Deliver webhook in background with automatic retries.
    
    Args:
        webhook_data: Dict with tx_ref, webhook_url, amount, etc.
    """
    from services.webhook import deliver_webhook_from_dict
    
    try:
        success = deliver_webhook_from_dict(webhook_data)
        if not success:
            raise Exception("Webhook delivery failed")
        logger.info("Webhook delivered | tx_ref=%s", webhook_data.get("tx_ref"))
    except Exception as e:
        logger.error("Webhook task failed | tx_ref=%s error=%s", 
                    webhook_data.get("tx_ref"), e)
        raise

@huey.periodic_task(crontab(minute='*/5'))
def cleanup_rate_limits():
    """Clean up expired rate limit records every 5 minutes."""
    from database import get_db
    from services.rate_limiter import cleanup_old_rate_limits
    
    with get_db() as db:
        deleted = cleanup_old_rate_limits(db, older_than_secs=3600)
        if deleted:
            logger.info("Cleaned up %d rate limit records", deleted)

@huey.periodic_task(crontab(hour='*'))
def cleanup_audit_logs():
    """Clean up audit logs older than 90 days (hourly check)."""
    from database import get_db
    from services.audit_cleanup import cleanup_old_audit_logs
    
    with get_db() as db:
        cleanup_old_audit_logs(db)
```

### 5. Webhook Idempotency Model (Requirement 2)

**File**: `models/webhook_idempotency.py`

```python
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index
from models.base import Base

class WebhookIdempotency(Base):
    """
    Tracks processed webhooks to prevent duplicate processing.
    
    Records expire after 24 hours (handled by cleanup task).
    """
    __tablename__ = "webhook_idempotency"
    
    id = Column(String(255), primary_key=True)  # Webhook identifier
    source = Column(String(50), nullable=False)  # korapay, voicepay, etc.
    processed_at = Column(DateTime(timezone=True), nullable=False, 
                          default=lambda: datetime.now(timezone.utc))
    tx_ref = Column(String(100), nullable=True)  # Associated transaction
    
    __table_args__ = (
        Index("ix_webhook_idempotency_processed", "processed_at"),
    )
```

### 6. SSRF Prevention Service Enhancement (Requirement 3)

**File**: `services/url_validator.py`

```python
"""
Enhanced URL validation with SSRF prevention.

Implements DNS rebinding protection and private IP blocking.
"""

import socket
import ipaddress
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private IP ranges (RFC 1918, RFC 3927, RFC 4291)
PRIVATE_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('224.0.0.0/4'),     # Multicast
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
]

def validate_url_for_ssrf(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL and resolve to safe IP address.
    
    Returns:
        (is_valid, resolved_ip, error_message)
    """
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ('http', 'https'):
            return False, None, "URL must use HTTP or HTTPS"
        
        hostname = parsed.hostname
        if not hostname:
            return False, None, "URL must have a hostname"
        
        # Resolve DNS
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror as e:
            return False, None, f"DNS resolution failed: {e}"
        
        # Check if IP is private/internal
        ip_obj = ipaddress.ip_address(ip)
        
        for network in PRIVATE_NETWORKS:
            if ip_obj in network:
                logger.warning(
                    "SSRF attempt blocked | url=%s hostname=%s ip=%s",
                    url, hostname, ip
                )
                return False, None, f"Private IP address not allowed: {ip}"
        
        return True, ip, None
        
    except Exception as e:
        logger.error("URL validation error | url=%s error=%s", url, e)
        return False, None, f"Validation error: {e}"
```

---

## Data Models

### Database Schema Changes

#### New Tables

```sql
-- Webhook Idempotency (Requirement 2)
CREATE TABLE webhook_idempotency (
    id VARCHAR(255) PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tx_ref VARCHAR(100)
);

CREATE INDEX ix_webhook_idempotency_processed ON webhook_idempotency(processed_at);
```

#### New Indexes (Requirement 8)

```sql
-- Transaction indexes for common query patterns
CREATE INDEX ix_transactions_created_at ON transactions(created_at);
CREATE INDEX ix_transactions_status ON transactions(status);
CREATE INDEX ix_transactions_user_created ON transactions(user_id, created_at);
CREATE INDEX ix_transactions_user_status ON transactions(user_id, status);

-- Audit log indexes for retention queries
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX ix_audit_logs_user_id ON audit_logs(user_id);
```

### Alembic Migration

**File**: `alembic/versions/20260415000000_add_codebase_improvements.py`

```python
"""Add codebase improvements: indexes, webhook idempotency

Revision ID: 20260415000000
"""

from alembic import op
import sqlalchemy as sa

revision = '20260415000000'
down_revision = '20260406000000_add_github_and_2fa'

def upgrade():
    # Create webhook_idempotency table
    op.create_table(
        'webhook_idempotency',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('tx_ref', sa.String(100), nullable=True),
    )
    op.create_index('ix_webhook_idempotency_processed', 
                    'webhook_idempotency', ['processed_at'])
    
    # Add transaction indexes
    op.create_index('ix_transactions_created_at', 'transactions', ['created_at'])
    op.create_index('ix_transactions_status', 'transactions', ['status'])
    op.create_index('ix_transactions_user_created', 'transactions', 
                    ['user_id', 'created_at'])
    op.create_index('ix_transactions_user_status', 'transactions', 
                    ['user_id', 'status'])
    
    # Add audit log indexes
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])

def downgrade():
    op.drop_index('ix_audit_logs_user_id', 'audit_logs')
    op.drop_index('ix_audit_logs_created_at', 'audit_logs')
    op.drop_index('ix_transactions_user_status', 'transactions')
    op.drop_index('ix_transactions_user_created', 'transactions')
    op.drop_index('ix_transactions_status', 'transactions')
    op.drop_index('ix_transactions_created_at', 'transactions')
    op.drop_index('ix_webhook_idempotency_processed', 'webhook_idempotency')
    op.drop_table('webhook_idempotency')
```

---

## Correctness Properties

This feature involves infrastructure improvements, database migrations, and configuration changes. Property-based testing is not applicable for the following reasons:

1. **Database Indexes (Req 8)**: These are declarative DDL statements, not functions with inputs/outputs. Testing is done via integration tests verifying query performance.

2. **Task Queue Integration (Req 10)**: External service integration (Huey) is tested with integration tests and mocks, not property-based tests.

3. **Rate Limit Decorator (Req 5)**: While the decorator has testable logic, the core rate limiting is already tested. The decorator is a thin wrapper tested with example-based unit tests.

4. **Exception Hierarchy (Req 7)**: Simple class definitions with no complex logic. Tested with example-based unit tests.

5. **Validators (Req 6)**: Input validation functions could have property tests, but the validation rules are simple regex matches better suited for example-based tests with edge cases.

6. **SSRF Prevention (Req 3)**: Security-critical logic that should be tested with specific attack vectors (example-based), not randomized inputs.

7. **Frontend Build Pipeline (Req 13-14)**: Build configuration tested with smoke tests.

8. **Pre-commit Hooks (Req 18)**: Configuration files tested with smoke tests.

**Testing Strategy**: All requirements will be validated through:
- Unit tests for specific examples and edge cases
- Integration tests for database migrations and task queue
- Smoke tests for configuration and build pipeline
- Security tests with known attack vectors for SSRF prevention

---

## Error Handling

### Standardized Error Response Format (Requirement 25)

All API errors follow this JSON structure:

```json
{
    "success": false,
    "message": "User-friendly error description",
    "error_code": "VALIDATION_ERROR"
}
```

### Error Code Reference

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `AUTHENTICATION_ERROR` | 401 | Not authenticated |
| `AUTHORIZATION_ERROR` | 403 | Not authorized |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `PROVIDER_ERROR` | 502 | External service failure |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Global Exception Handler

```python
@app.errorhandler(OnePayError)
def handle_onepay_error(error: OnePayError):
    """Handle all OnePay exceptions consistently."""
    logger.error(
        "OnePay error | code=%s message=%s correlation_id=%s",
        error.error_code,
        error.message,
        g.get("correlation_id")
    )
    
    return jsonify({
        "success": False,
        "message": error.message,
        "error_code": error.error_code
    }), error.status_code
```

---

## Testing Strategy

### Unit Tests

- **Validators**: Test email/phone validation with valid/invalid/edge cases
- **Exceptions**: Verify error codes, messages, and status codes
- **Decorators**: Mock rate limiter, test rate limit exceeded response
- **URL Validator**: Test SSRF prevention with known attack vectors

### Integration Tests

- **Database Migrations**: Verify indexes created correctly
- **Task Queue**: Test webhook delivery with Huey in immediate mode
- **Cache Layer**: Verify cache hit/miss behavior
- **N+1 Queries**: Assert query count remains constant with page size

### Security Tests

- **SSRF Prevention**: Test with private IPs, DNS rebinding attempts
- **Webhook Signature**: Test with invalid/missing signatures
- **Secret Validation**: Test startup refusal with weak secrets

### Performance Tests

- **Query Performance**: Verify index usage with EXPLAIN ANALYZE
- **Cache Effectiveness**: Measure cache hit rate
- **CSS Bundle Size**: Verify <50KB gzipped

### Test Fixture Isolation (Requirement 20)

```python
# tests/conftest.py additions

import pytest
from database import get_db, engine
from models.base import Base

@pytest.fixture
def isolated_db():
    """Create isolated test database with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def reset_cache():
    """Reset global cache between tests."""
    from services.cache import reset_cache
    reset_cache()
    yield
    reset_cache()

@pytest.fixture
def reset_rate_limiter():
    """Reset global rate limiter state between tests."""
    from services.rate_limiter import _memory_cache
    _memory_cache.clear()
    yield
    _memory_cache.clear()
```

---

## File Structure for New Modules

```
onepay/
├── core/
│   ├── __init__.py
│   ├── api_auth.py
│   ├── audit.py
│   ├── auth.py
│   ├── decorators.py      # NEW: Rate limit decorator
│   ├── exceptions.py      # NEW: Custom exception hierarchy
│   ├── ip.py
│   ├── logging_filters.py
│   └── responses.py
├── services/
│   ├── __init__.py
│   ├── cache.py
│   ├── rate_limiter.py
│   ├── task_queue.py      # NEW: Huey integration
│   ├── url_validator.py   # NEW: SSRF prevention
│   ├── validators.py      # NEW: Email/phone validation
│   └── webhook.py
├── models/
│   ├── __init__.py
│   ├── webhook_idempotency.py  # NEW: Webhook deduplication
│   └── ...
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── login.js       # NEW: Extracted from login.html
│       ├── dashboard.js
│       └── verify.js
├── scripts/
│   └── setup.sh           # NEW: Local development setup
├── .pre-commit-config.yaml # NEW: Pre-commit hooks
├── mypy.ini               # NEW: Type checking config
├── pyproject.toml         # UPDATE: Ruff configuration
└── tailwind.config.js     # NEW: Tailwind build config
```

---

## Frontend Build Pipeline

### Tailwind CSS Build (Requirement 13)

**File**: `tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['DM Sans', 'sans-serif'],
        'mono': ['DM Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

**Build Command** (added to `package.json`):

```json
{
  "scripts": {
    "build:css": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify",
    "watch:css": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch"
  }
}
```

### JavaScript Extraction (Requirement 14)

Extract inline JavaScript from templates to separate files:

1. `login.html` → `static/js/login.js`
2. Add `defer` attribute to script tags
3. Implement nonce-based CSP for any remaining inline handlers

---

## Configuration Changes

### Environment Variables

```bash
# .env.example additions

# Task Queue
HUEY_DB_PATH=huey.db
HUEY_WORKERS=2

# Cache
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=60

# Database (PostgreSQL for all environments)
DATABASE_URL=postgresql://onepay:password@localhost:5432/onepay

# Secrets (validated on startup)
SECRET_KEY=<min 32 chars>
HMAC_SECRET=<min 32 chars, different from SECRET_KEY>
INBOUND_WEBHOOK_SECRET=<min 32 chars in production>
```

### Docker Compose for Local PostgreSQL (Requirement 12)

```yaml
# docker-compose.yml addition
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: onepay
      POSTGRES_PASSWORD: onepay_dev
      POSTGRES_DB: onepay
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Developer Experience

### Local Setup Script (Requirement 17)

**File**: `scripts/setup.sh`

```bash
#!/bin/bash
set -e

echo "🚀 Setting up OnePay development environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Copy .env if not exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

# Start PostgreSQL
echo "🐘 Starting PostgreSQL..."
docker-compose up -d postgres

# Wait for PostgreSQL
sleep 3

# Run migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Offer to install pre-commit hooks
read -p "🔧 Install pre-commit hooks? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install pre-commit
    pre-commit install
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration"
echo "  2. Run 'source .venv/bin/activate'"
echo "  3. Run 'flask run' or 'python app.py'"
```

### Pre-Commit Hooks (Requirement 18)

**File**: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
        args: [--config-file=mypy.ini]
        pass_filenames: false
```

### Type Checking Configuration (Requirement 19)

**File**: `mypy.ini`

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
no_implicit_optional = True

# Gradual typing for existing code
[mypy-blueprints.*]
disallow_untyped_defs = False

[mypy-models.*]
disallow_untyped_defs = False

[mypy-services.*]
disallow_untyped_defs = False

# Strict mode for new modules
[mypy-core.decorators]
disallow_untyped_defs = True

[mypy-core.exceptions]
disallow_untyped_defs = True

[mypy-services.validators]
disallow_untyped_defs = True
```

---

## Correlation IDs for Logging (Requirement 22)

### Implementation

```python
# app.py addition

import uuid
from flask import g, request

@app.before_request
def inject_correlation_id():
    """Generate or extract correlation ID for request tracing."""
    correlation_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    g.correlation_id = correlation_id

@app.after_request
def add_correlation_id_header(response):
    """Add correlation ID to response headers."""
    response.headers['X-Correlation-ID'] = g.get('correlation_id', '')
    return response

# Update RequestIdFilter to use correlation_id
class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = g.get('correlation_id', '-')
        return True
```

---

## Cache-Control Headers (Requirement 23)

### Implementation

```python
# app.py addition

from flask import send_from_directory
import hashlib

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files with cache headers."""
    response = send_from_directory('static', filename)
    
    # Versioned assets (content hash in filename)
    if '.' in filename and len(filename.split('.')[-1]) == 8:
        # 8-char hash = versioned asset
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    else:
        # Non-versioned assets
        response.headers['Cache-Control'] = 'public, max-age=3600'
    
    # Add ETag
    response.headers['ETag'] = hashlib.md5(
        response.get_data()
    ).hexdigest()
    
    return response
```

---

## Implementation Priority

### Phase 1: Security (Week 1)
1. Webhook signature validation (Req 1)
2. Webhook idempotency (Req 2)
3. SSRF prevention (Req 3)
4. Strong secret enforcement (Req 21)

### Phase 2: Architecture (Week 2)
5. Rate limit decorator (Req 5)
6. Input validation service (Req 6)
7. Custom exceptions (Req 7)
8. Task queue integration (Req 10)

### Phase 3: Performance (Week 3)
9. Database indexes (Req 8)
10. N+1 query prevention (Req 9)
11. Cache layer activation (Req 11)
12. Database dialect consistency (Req 12)

### Phase 4: Frontend (Week 4)
13. Tailwind build pipeline (Req 13)
14. JavaScript extraction (Req 14)
15. Form loading states (Req 15)
16. Accessibility compliance (Req 16)

### Phase 5: Developer Experience (Week 5)
17. Local setup script (Req 17)
18. Pre-commit hooks (Req 18)
19. Type checking config (Req 19)
20. Test fixture isolation (Req 20)
21. Linter configuration (Req 24)

### Phase 6: Observability (Week 6)
22. Correlation IDs (Req 22)
23. Cache-control headers (Req 23)
24. Error handling standardization (Req 25)
25. 2FA implementation fix (Req 4)


---

## Risk Assessment Matrix

| Requirement | Risk Level | Impact | Likelihood | Mitigation Strategy |
|-------------|-----------|--------|------------|---------------------|
| Req 1: Webhook Signature | High | High | Medium | Comprehensive testing with valid/invalid signatures; gradual rollout |
| Req 2: Webhook Idempotency | High | High | Medium | Database transaction isolation; extensive duplicate testing |
| Req 3: SSRF Prevention | Critical | Critical | Low | Security audit; penetration testing; whitelist approach |
| Req 4: 2FA Implementation | High | High | Medium | Thorough testing of all auth flows; backup codes |
| Req 5: Rate Limit Decorator | Medium | Medium | Low | Monitor rate limit metrics; easy rollback to inline checks |
| Req 6: Input Validators | Low | Low | Low | Existing validation logic preserved; gradual migration |
| Req 7: Exception Hierarchy | Medium | Medium | Medium | Comprehensive error handling tests; staged rollout |
| Req 8: Database Indexes | Low | Low | Low | Indexes can be dropped easily; monitor query performance |
| Req 9: N+1 Query Prevention | Medium | Medium | Medium | Query count monitoring; performance benchmarks |
| Req 10: Task Queue Integration | Medium | High | Medium | Fallback to thread-based approach; worker monitoring |
| Req 11: Caching Layer | Low | Low | Low | Cache can be disabled; TTL is conservative |
| Req 12: Database Dialect | Low | Medium | Low | Docker Compose simplifies PostgreSQL setup |
| Req 13: Tailwind Build | Low | Low | Low | Build pipeline is isolated; CDN fallback possible |
| Req 14: JavaScript Extraction | Low | Low | Low | Functionality testing; easy to revert |
| Req 15: Form Loading States | Low | Low | Low | UI enhancement only; no backend changes |
| Req 16: Accessibility | Low | Low | Low | Additive improvements; no breaking changes |
| Req 17: Setup Script | Low | Low | Low | Developer tooling only; no production impact |
| Req 18: Pre-commit Hooks | Low | Low | Low | Optional; can be bypassed with --no-verify |
| Req 19: Type Checking | Low | Low | Low | Optional; doesn't affect runtime |
| Req 20: Test Fixture Isolation | Medium | Low | Medium | Test failures are caught in CI; no production impact |
| Req 21: Secret Enforcement | High | High | Low | Clear error messages; documentation |
| Req 22: Correlation IDs | Low | Low | Low | Logging enhancement only; no functional changes |
| Req 23: Cache-Control Headers | Low | Low | Low | Caching headers are additive; easy to adjust |
| Req 24: Linter Configuration | Low | Low | Low | Developer tooling only; no production impact |
| Req 25: Error Standardization | Medium | Medium | Medium | API client compatibility testing; versioning |

---

## Rollback Procedures

### Phase 1: Security

**Requirement 1: Webhook Signature Validation**
- **Rollback Steps**:
  1. Revert changes to `config.py` and `app.py`
  2. Remove signature verification from `services/webhook.py`
  3. Restart application
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Webhooks process without signature checks

**Requirement 2: Webhook Idempotency**
- **Rollback Steps**:
  1. Run Alembic downgrade to remove `webhook_idempotency` table
  2. Revert changes to `blueprints/webhooks.py`
  3. Remove cleanup task from `services/task_queue.py`
  4. Restart application
- **Rollback Time**: 10 minutes
- **Data Loss Risk**: Idempotency records lost (acceptable)
- **Verification**: Webhooks process without idempotency checks

**Requirement 3: SSRF Prevention**
- **Rollback Steps**:
  1. Revert changes to logo URL validation
  2. Remove `services/url_validator.py`
  3. Restart application
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Logo URLs validate without SSRF checks

**Requirement 21: Strong Secret Enforcement**
- **Rollback Steps**:
  1. Revert changes to `config.py` and `app.py`
  2. Restart application
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Application starts with weak secrets

### Phase 2: Architecture

**Requirement 5: Rate Limit Decorator**
- **Rollback Steps**:
  1. Revert blueprint changes to use inline rate limiting
  2. Remove `core/decorators.py`
  3. Restart application
- **Rollback Time**: 15 minutes
- **Data Loss Risk**: None
- **Verification**: Rate limiting still works via inline checks

**Requirement 7: Custom Exception Hierarchy**
- **Rollback Steps**:
  1. Revert all blueprint changes
  2. Remove global exception handler from `app.py`
  3. Remove `core/exceptions.py`
  4. Restart application
- **Rollback Time**: 30 minutes
- **Data Loss Risk**: None
- **Verification**: Error responses use old format

**Requirement 10: Task Queue Integration**
- **Rollback Steps**:
  1. Stop Huey worker processes
  2. Revert webhook delivery to thread-based approach
  3. Remove periodic tasks
  4. Restart application
- **Rollback Time**: 15 minutes
- **Data Loss Risk**: Queued tasks lost (acceptable)
- **Verification**: Webhooks deliver via threads

### Phase 3: Performance

**Requirement 8: Database Indexes**
- **Rollback Steps**:
  1. Run Alembic downgrade to remove indexes
  2. Restart application (optional)
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Queries work without indexes (slower)

**Requirement 9: N+1 Query Prevention**
- **Rollback Steps**:
  1. Revert query changes to remove eager loading
  2. Restart application
- **Rollback Time**: 20 minutes
- **Data Loss Risk**: None
- **Verification**: Queries execute more times but return same data

**Requirement 11: Caching Layer**
- **Rollback Steps**:
  1. Revert endpoint changes to remove cache checks
  2. Restart application
- **Rollback Time**: 10 minutes
- **Data Loss Risk**: Cache data lost (acceptable)
- **Verification**: Endpoints query database directly

### Phase 4: Frontend

**Requirement 13: Tailwind Build Pipeline**
- **Rollback Steps**:
  1. Revert `templates/base.html` to use CDN
  2. Remove build scripts from `package.json`
  3. No restart needed
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Pages load with CDN CSS

**Requirement 14: JavaScript Extraction**
- **Rollback Steps**:
  1. Revert template changes to use inline JS
  2. Remove extracted JS files
  3. No restart needed
- **Rollback Time**: 10 minutes
- **Data Loss Risk**: None
- **Verification**: Forms work with inline JS

**Requirement 16: Accessibility**
- **Rollback Steps**:
  1. Revert template changes
  2. Revert CSS changes
  3. No restart needed
- **Rollback Time**: 30 minutes
- **Data Loss Risk**: None
- **Verification**: Pages render without accessibility enhancements

### Phase 5: Developer Experience

**Requirement 17-24: DevEx Improvements**
- **Rollback Steps**: Delete created files (scripts, configs)
- **Rollback Time**: 5 minutes
- **Data Loss Risk**: None
- **Verification**: Development continues without new tooling

### Phase 6: Observability

**Requirement 22: Correlation IDs**
- **Rollback Steps**:
  1. Revert changes to `app.py` and logging filters
  2. Restart application
- **Rollback Time**: 10 minutes
- **Data Loss Risk**: None
- **Verification**: Logs work without correlation IDs

**Requirement 25: Error Standardization**
- **Rollback Steps**:
  1. Revert error response format changes
  2. Restart application
- **Rollback Time**: 20 minutes
- **Data Loss Risk**: None
- **Verification**: Errors use old response format

---

## Performance Impact Assessment

### Database Changes

| Change | Expected Impact | Measurement Method |
|--------|----------------|-------------------|
| Add indexes (Req 8) | 30-50% query time reduction | EXPLAIN ANALYZE before/after |
| N+1 prevention (Req 9) | 50-80% query count reduction | Query logging, APM tools |
| Caching layer (Req 11) | 70-90% cache hit rate | Cache metrics, response times |

### Frontend Changes

| Change | Expected Impact | Measurement Method |
|--------|----------------|-------------------|
| Tailwind build (Req 13) | 90% CSS size reduction (3MB → <50KB) | Bundle size analysis |
| JS extraction (Req 14) | 10-20% faster page loads | Lighthouse, WebPageTest |
| Loading states (Req 15) | No performance impact | N/A |

### Architecture Changes

| Change | Expected Impact | Measurement Method |
|--------|----------------|-------------------|
| Task queue (Req 10) | 50-70% faster webhook response | Response time monitoring |
| Rate limit decorator (Req 5) | Negligible (<1ms overhead) | Benchmark tests |
| Exception hierarchy (Req 7) | Negligible (<1ms overhead) | Benchmark tests |

---

## Success Metrics

### Security Metrics (Phase 1)

- **Webhook Signature Validation**: 0 unauthorized webhook attempts succeed
- **Webhook Idempotency**: 0 duplicate transactions created
- **SSRF Prevention**: 0 private IP requests succeed
- **Secret Enforcement**: 100% of production deployments use strong secrets

### Performance Metrics (Phase 3)

- **Database Indexes**: Average query time < 50ms (from 100-200ms)
- **N+1 Prevention**: Query count per request < 5 (from 20-50)
- **Caching**: Cache hit rate > 70% for analytics endpoints

### Frontend Metrics (Phase 4)

- **Tailwind Build**: CSS bundle < 50KB gzipped
- **Accessibility**: WCAG 2.1 AA compliance score > 90%
- **Loading States**: 0 double-submission incidents

### Developer Experience Metrics (Phase 5)

- **Setup Script**: New developer onboarding < 15 minutes
- **Pre-commit Hooks**: Code quality issues caught before commit > 80%
- **Test Isolation**: 0 test interference failures

### Observability Metrics (Phase 6)

- **Correlation IDs**: 100% of requests have correlation IDs in logs
- **Error Standardization**: 100% of API errors follow standard format
- **2FA**: 0 authentication bypass incidents

---

## Dependencies Between Requirements

```mermaid
graph TD
    R1[Req 1: Webhook Signature] --> R21[Req 21: Secret Enforcement]
    R2[Req 2: Webhook Idempotency] --> R10[Req 10: Task Queue]
    R7[Req 7: Exception Hierarchy] --> R25[Req 25: Error Standardization]
    R8[Req 8: Database Indexes] --> R9[Req 9: N+1 Prevention]
    R18[Req 18: Pre-commit Hooks] --> R19[Req 19: Type Checking]
    R18[Req 18: Pre-commit Hooks] --> R24[Req 24: Linter Config]
    R22[Req 22: Correlation IDs] --> R25[Req 25: Error Standardization]
    R12[Req 12: Database Dialect] --> R17[Req 17: Setup Script]
```

**Critical Path**: Req 1 → Req 21 → Req 2 → Req 10 (Security + Architecture foundation)

**Parallel Tracks**:
- Track 1: Req 5, 6, 7 (Code quality improvements)
- Track 2: Req 8, 9, 11 (Performance improvements)
- Track 3: Req 13, 14, 15, 16 (Frontend improvements)
- Track 4: Req 17, 18, 19, 20, 24 (DevEx improvements)

---

## Monitoring and Alerting

### Production Monitoring

**Security Alerts**:
- Webhook signature failures > 10/hour
- SSRF attempts detected
- Weak secret configuration detected at startup

**Performance Alerts**:
- Query time > 100ms (95th percentile)
- Cache hit rate < 50%
- N+1 query pattern detected

**Error Alerts**:
- Error rate > 1% of requests
- 5xx errors > 0.1% of requests
- Task queue failures > 5/hour

### Development Monitoring

**Code Quality Metrics**:
- Pre-commit hook pass rate
- Type checking error count
- Linter warning count

**Test Metrics**:
- Test isolation failure rate
- Test execution time
- Code coverage percentage

---

## Implementation Notes

### Critical Success Factors

1. **Security First**: Complete Phase 1 before moving to other phases
2. **Incremental Rollout**: Deploy changes gradually, monitor metrics
3. **Comprehensive Testing**: All security changes require penetration testing
4. **Documentation**: Update docs alongside code changes
5. **Team Communication**: Notify team before deploying breaking changes

### Common Pitfalls to Avoid

1. **Skipping Tests**: Don't skip optional test tasks - they catch regressions
2. **Incomplete Rollback**: Test rollback procedures before production deployment
3. **Performance Regression**: Benchmark before/after for performance changes
4. **Breaking API Clients**: Maintain backward compatibility for error responses
5. **Configuration Drift**: Keep dev/staging/prod configs in sync

### Post-Implementation Checklist

- [ ] All tests passing (unit, integration, security)
- [ ] Performance benchmarks meet targets
- [ ] Documentation updated
- [ ] Rollback procedure tested
- [ ] Monitoring and alerts configured
- [ ] Team trained on new features
- [ ] Production deployment plan reviewed
- [ ] Incident response plan updated

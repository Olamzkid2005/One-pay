# OnePay — Claude Code Context

OnePay is a secure payment verification and invoice management platform integrating with KoraPay API. It eliminates fake payment confirmations through secure, time-bound payment links and direct transaction verification.

## Project Overview

- **Framework**: Flask 3.x with SQLAlchemy 2.x
- **Python**: 3.9+
- **Database**: SQLite (dev), PostgreSQL (prod via docker-compose)
- **Payment Gateway**: KoraPay (with mock mode for testing)

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env with your credentials

# Run with start script (auto-detects debug/prod)
./start.sh

# Or run directly
python app.py                        # Dev (Flask dev server)
gunicorn app:app --workers 4         # Production

# Docker
docker-compose up --build
```

## Test Commands

```bash
# All tests
pytest

# By category (defined in pytest.ini)
pytest -m unit
pytest -m integration
pytest -m oauth

# Specific file/directory
pytest tests/unit/test_korapay_mock_mode_detection.py

# With coverage
pytest --cov=. --cov-report=term-missing
```

## Architecture

```
app.py              # Flask application factory
config.py           # Environment-based configuration (dev/staging/prod)
database.py         # SQLAlchemy engine & session management

blueprints/         # Route modules
  auth.py           # Register, login, logout, password reset, OAuth
  payments.py      # Dashboard, create link, status, history
  invoices.py       # Invoice CRUD, PDF generation
  public.py         # Verify page, health check, polling
  webhooks.py       # KoraPay webhook handler
  api_keys.py       # API key management

models/             # SQLAlchemy models
  user.py           # User with bcrypt hashing
  transaction.py    # Payment links and verification
  invoice.py        # Invoice lifecycle
  refund.py         # Refund tracking
  api_key.py        # Per-user API keys
  audit_log.py      # Security audit trail
  rate_limit.py     # Rate limit tracking

services/           # Business logic & external integrations
  korapay.py        # KoraPay API (virtual accounts, transfers, refunds)
  cache.py          # Redis-like in-memory caching
  rate_limiter.py   # Rate limiting logic
  email.py          # SMTP email with retry
  webhook.py        # Outbound webhook forwarding
  google_oauth.py   # Google Sign-In
  github_oauth.py   # GitHub OAuth
  invoice.py        # Invoice number generation, formatting
  qr_code.py        # QR code generation
  pdf_receipt.py    # PDF invoice/receipt generation
  security.py       # Security utilities
  sla_monitor.py    # SLA tracking
  voicepay_webhook.py # VoicePay webhook forwarding
  cache.py          # In-memory cache with TTL

core/               # Shared utilities
  responses.py      # Standardized API responses
  logging_filters.py # Request ID injection, sensitive data masking
  ip.py             # IP extraction (handles proxies)
```

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app factory, logging setup, request hooks |
| `config.py` | All environment configuration (150+ settings) |
| `services/korapay.py` | KoraPay API integration with circuit breaker |
| `blueprints/auth.py` | Authentication (37KB - largest file) |
| `tests/unit/test_korapay_*.py` | 16 split test modules for KoraPay service |
| `alembic/versions/` | Database migration scripts |

## Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Configuration

All settings via environment variables (`.env`). Key settings:
- `APP_ENV`: `development` | `staging` | `production`
- `SECRET_KEY`: Flask secret key
- `KORAPAY_SECRET_KEY`: KoraPay API key (use mock mode if empty)
- `DATABASE_URL`: SQLite or PostgreSQL connection string

## Coding Conventions

- **Flask patterns**: Blueprints for routes, services for business logic, models for data
- **Error handling**: Custom exceptions in `services/*.py`, generic error messages to clients
- **Logging**: JSON structured logs in prod, text in dev; request ID injected into all logs
- **Security**: bcrypt passwords, HMAC signatures, rate limiting, CSRF protection
- **Testing**: Unit tests with mocks, integration tests for API flows, Hypothesis for property-based tests
- **Naming**: `snake_case` Python, `Title_Case` classes, `SCREAMING_SNAKE_CASE` constants

## Testing Tips

- KoraPay has a **mock mode**: Set `KORAPAY_SECRET_KEY` empty or < 32 chars to use mock responses
- Tests reload config modules dynamically with `importlib.reload()`
- Mock mode tests use in-memory state (`korapay._mock_poll_counts`, etc.)

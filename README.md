# OnePay

A modern, secure payment verification and invoice management platform that integrates with KoraPay API. OnePay eliminates fake payment confirmations by allowing merchants to generate secure, time-bound payment links, automatically create professional invoices, and verify transactions directly from the payment infrastructure.

## 🚀 Latest Updates (v1.5.5)

### Security Hardening - Critical Vulnerability Fixes
- 🔒 **Session Timeout**: Automatic session expiration (30min authenticated, 60min guest)
- 🛡️ **Security Headers**: Comprehensive headers (CSP, HSTS, X-Frame-Options, etc.)
- ⏱️ **Timing Attack Protection**: Constant-time responses prevent enumeration
- 🚫 **Content-Type Validation**: CSRF protection on all JSON endpoints
- 📏 **Request Size Limits**: 1MB limit prevents memory exhaustion DoS
- 🔇 **Error Handling**: Generic error messages prevent information disclosure
- ✅ **Input Validation**: Length validation on all user inputs
- ⏰ **OAuth Timeout**: Google OAuth requests timeout after 5 seconds

**Security Status**: 8/8 vulnerabilities resolved ✅ | Production Ready 🚀

### Previous Updates (v1.5.0)

### KoraPay Integration - Major Payment Provider Migration
- 💳 **KoraPay Gateway**: Migrated from Quickteller to KoraPay for enhanced payment processing
- 🔒 **Virtual Accounts**: Generate virtual bank accounts for seamless payments
- ⚡ **Circuit Breaker**: Fault-tolerant architecture prevents cascading failures
- 🎯 **Mock Mode**: Test integration without live credentials
- 📊 **SLA Monitoring**: Real-time performance tracking and alerting
- 🗄️ **Redis Caching**: Optimized performance with intelligent caching layer

### Earlier Updates (v1.3.0)
- 🔐 **Google Sign-In**: One-click registration and login with Google accounts
- 🔗 **Account Linking**: Connect existing accounts to Google for easier access
- 🛡️ **Secure Authentication**: Token validation, CSRF protection, rate limiting
- 👤 **Profile Import**: Automatic profile picture and name from Google

### Earlier Updates (v1.2.5)
- 🔒 **Security Audit**: 16/18 vulnerabilities resolved
- 🛡️ **Session Security**: IP and User-Agent binding prevents session hijacking
- 🚫 **SSRF Protection**: Webhook blacklist prevents DNS rebinding attacks
- 📊 **Security Monitoring**: Real-time threat detection running every 5 minutes

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

## Features

### Core Payment Features
- **Secure Payment Links**: Generate time-bound, single-use payment links with automatic expiration
- **KoraPay Integration**: Direct API verification with virtual account generation
- **QR Code Generation**: Automatic QR codes for easy mobile payments
- **Transaction History**: Track all payment links and their verification status
- **Webhook Integration**: Real-time payment notifications via KoraPay webhooks
- **Circuit Breaker Pattern**: Fault tolerance with automatic failover
- **Mock Mode**: Full testing capability without live credentials

### Invoice & Receipt System
- **Automated Invoice Generation**: Auto-create invoices for verified payments
- **Professional PDF Invoices**: Download invoices and receipts as PDF
- **Invoice Management**: Web interface to view, download, and send invoices
- **Business Branding**: Add your logo, tax ID, and payment terms
- **Invoice Status Tracking**: Track invoice lifecycle (DRAFT, SENT, PAID, EXPIRED, CANCELLED)

### Refund Management
- **Partial Refunds**: Support for partial refund amounts
- **Full Refunds**: Complete refund capability
- **Refund Tracking**: Monitor refund status and history
- **Automated Processing**: Streamlined refund workflows

### Performance & Reliability
- **Redis Caching**: Intelligent caching for optimal performance
- **SLA Monitoring**: Real-time performance metrics and alerting
- **Circuit Breaker**: Automatic circuit breaking for fault tolerance
- **Connection Pooling**: Efficient HTTP connection management

### Email Notifications
- **Payment Alerts**: Automatic email notifications for verified payments
- **Merchant Notifications**: Receive payment confirmations with invoice attachments
- **Customer Invoices**: Optionally send invoices to customers via email
- **Retry Logic**: Automatic retry with exponential backoff for failed emails

### UI/UX Features
- **Light/Dark Mode**: Toggle between light and dark themes with persistent preference
- **Collapsible Sidebar**: Responsive sidebar with smooth animations
- **Modern Design**: Clean, professional interface with Material Design icons
- **Mobile Responsive**: Optimized for all screen sizes

### Security & Performance
- **User Authentication**: Secure registration and login with bcrypt password hashing
- **Google OAuth**: One-click sign-in with Google accounts (optional)
- **Session Security**: IP and User-Agent binding prevents session fixation attacks
- **Rate Limiting**: Protection against abuse with configurable rate limits
- **Audit Logging**: Comprehensive logging with retention policy
- **CSRF Protection**: Secure session management and form protection
- **SSRF Prevention**: Webhook blacklist with DNS rebinding detection
- **Security Monitoring**: Real-time threat detection
- **Input Validation**: Comprehensive validation and sanitization
- **Password Strength**: Complexity requirements enforced
- **Production Hardening**: HTTPS enforced, secrets validated

## Tech Stack

- **Backend**: Python 3.x, Flask
- **Database**: SQLite (development), PostgreSQL (production ready)
- **ORM**: SQLAlchemy with Alembic migrations
- **Authentication**: Flask-Login, bcrypt
- **Cache**: Redis
- **API Integration**: KoraPay Payment Gateway
- **Monitoring**: Prometheus metrics, Grafana dashboards
- **Security**: CSRF protection, secure session management, IP tracking

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)
- Redis server (optional, for caching)
- SMTP server (optional, for email notifications)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Olamzkid2005/One-pay.git
cd One-pay
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Generate secret keys:
```bash
python generate_secrets.py
```

6. Initialize the database:
```bash
alembic upgrade head
```

7. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 🎯 Quick Start Guide

### First Time Setup

1. **Register an Account**
   - Navigate to `http://localhost:5000/register`
   - Choose traditional registration or Google Sign-In
   - Create your merchant account

2. **Configure Settings** (Optional)
   - Go to Settings page
   - Add your business name, logo, and tax ID
   - Enable auto-send email for customer invoices

3. **Set Up Google OAuth** (Optional)
   - See [Google OAuth Setup Guide](docs/GOOGLE_OAUTH_SETUP.md)
   - Configure Google Cloud Console
   - Add credentials to `.env` file

4. **Set Up KoraPay** (Required for payments)
   - See [KoraPay Setup Guide](docs/KORAPAY_SETUP.md)
   - Create KoraPay merchant account
   - Add API keys to `.env` file

5. **Create Your First Payment Link**
   - Enter amount and description
   - Click "Generate Payment Link"
   - Share the link with your customer

6. **View Invoice**
   - Once payment is verified, invoice is auto-generated
   - Download as PDF or send via email
   - Track status in Invoices page

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file with the following:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Database
DATABASE_URL=sqlite:///onepay.db

# KoraPay API Configuration
KORAPAY_SECRET_KEY=sk_test_your_secret_key_here
KORAPAY_WEBHOOK_SECRET=your_webhook_secret_here
KORAPAY_BASE_URL=https://api.korapay.com/merchant/api/v1
KORAPAY_USE_SANDBOX=true
KORAPAY_TIMEOUT_SECONDS=30
KORAPAY_CONNECT_TIMEOUT=10
KORAPAY_MAX_RETRIES=3

# Redis Cache (Optional)
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_DEFAULT_TTL=300

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@onepay.com

# Google OAuth Configuration (Optional)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### KoraPay Setup

For KoraPay integration to work:

1. **Create KoraPay Account**
   - Sign up at [KoraPay Dashboard](https://dashboard.korapay.com)
   - Navigate to Settings → API Keys
   - Generate or use existing API key

2. **Configure Webhooks**
   - Go to Settings → Webhooks
   - Add webhook URL: `https://api.onepay.ng/api/webhooks/korapay`
   - Generate and save webhook secret

3. **Environment Configuration**
   - Use `sk_test_` keys for sandbox testing
   - Use `sk_live_` keys for production

See [docs/KORAPAY_SETUP.md](docs/KORAPAY_SETUP.md) for detailed instructions.

### Email Setup

For email notifications to work:

1. **Gmail**: Use App Password (not your regular password)
   - Enable 2FA on your Google account
   - Generate App Password at https://myaccount.google.com/apppasswords
   - Use the generated password in `MAIL_PASSWORD`

2. **Other SMTP Providers**: Update `MAIL_SERVER` and `MAIL_PORT` accordingly

See [EMAIL_SETUP_GUIDE.md](EMAIL_SETUP_GUIDE.md) for detailed instructions.

### Google OAuth Setup

For Google Sign-In to work:

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google+ API

2. **Configure OAuth Consent Screen**
   - Set application name, logo, and support email
   - Add authorized domains

3. **Create OAuth 2.0 Credentials**
   - Create OAuth 2.0 Client ID
   - Add authorized redirect URIs
   - Copy Client ID and Client Secret to `.env`

See [docs/GOOGLE_OAUTH_SETUP.md](docs/GOOGLE_OAUTH_SETUP.md) for detailed instructions.

## Usage

### For Users

1. **Register**: Create an account with email and password, or use Google Sign-In
2. **Configure Settings**: Add your business details, logo, and email preferences
3. **Generate Payment Link**: Enter amount and description to create a secure payment link
4. **Share Link**: Send the generated link to the payer (includes QR code)
5. **Receive Notifications**: Get email alerts when payments are confirmed
6. **Manage Invoices**: View, download, and send professional invoices
7. **Track History**: Monitor all transactions and invoices in your dashboard

### For Developers

See the [API Documentation](docs/README.md) for integration details.

## Project Structure

```
One-pay/
├── app.py                 # Main application entry point
├── config.py              # Configuration management
├── database.py            # Database initialization
├── blueprints/            # Flask blueprints (routes)
│   ├── auth.py           # Authentication routes
│   ├── payments.py       # Payment routes
│   └── public.py         # Public routes
├── models/                # Database models
│   ├── user.py           # User model
│   ├── transaction.py    # Transaction model
│   ├── refund.py         # Refund model
│   ├── audit_log.py      # Audit log model
│   └── rate_limit.py     # Rate limit model
├── services/              # Business logic
│   ├── korapay.py        # KoraPay API integration
│   ├── cache.py          # Redis caching service
│   ├── sla_monitor.py    # SLA monitoring service
│   ├── email.py          # Email service
│   ├── invoice.py         # Invoice generation
│   ├── pdf_receipt.py    # PDF generation
│   ├── qr_code.py        # QR code generation
│   ├── webhook.py        # Webhook handler
│   ├── rate_limiter.py   # Rate limiting
│   ├── security.py       # Security utilities
│   └── google_oauth.py   # Google OAuth service
├── core/                  # Core utilities
│   ├── auth.py           # Authentication helpers
│   ├── responses.py      # Response formatters
│   └── audit.py          # Audit logging
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── alembic/               # Database migrations
├── prometheus/            # Prometheus metrics configuration
├── grafana/               # Grafana dashboards
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Security Features

OnePay implements comprehensive security controls across all layers:

### Authentication & Authorization
- **Password Security**: bcrypt hashing, 12+ character minimum, complexity requirements
- **Session Management**: IP/User-Agent binding, automatic timeout (30min authenticated, 60min guest)
- **Session Timeout Enforcement**: Automatic invalidation of expired sessions on every request
- **Account Protection**: Lockout protection, rate limiting on login and password reset
- **CSRF Protection**: Token validation on all state-changing operations

### Data Protection
- **Input Validation**: Length limits, format validation, Content-Type enforcement
- **Input Length Validation**: Explicit rejection of oversized inputs with clear error messages
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy ORM
- **XSS Prevention**: Template escaping, Content-Security-Policy headers
- **Secrets Management**: Environment variables only, startup validation enforced

### API Security
- **Rate Limiting**: Per-endpoint limits
- **Content-Type Validation**: All JSON endpoints validate Content-Type header (415 on mismatch)
- **Request Size Limits**: 1MB maximum request size prevents memory exhaustion DoS
- **Timing Attack Protection**: Constant-time responses prevent transaction enumeration
- **SSRF Prevention**: Webhook blacklist, DNS rebinding detection, AWS metadata blocking
- **Webhook Security**: HMAC-SHA256 signatures, constant-time comparison
- **Circuit Breaker**: Automatic protection against downstream service failures
- **OAuth Timeout**: Google OAuth requests timeout after 5 seconds

### Monitoring & Logging
- **Security Monitoring**: Background thread detecting brute force, spam, anomalies
- **SLA Monitoring**: Real-time performance metrics with Prometheus
- **Audit Logging**: All security events logged with retention
- **Grafana Dashboards**: Visual monitoring of system health
- **Error Handling**: Generic error messages in production, detailed logs server-side only

### Production Hardening
- **Secret Validation**: Application refuses to start with weak secrets
- **HTTPS Enforcement**: Strict-Transport-Security headers, secure cookies
- **Database Security**: PostgreSQL required in production (SQLite blocked)
- **Security Headers**: Comprehensive CSP, X-Frame-Options, X-Content-Type-Options, HSTS
- **Information Disclosure Prevention**: No stack traces or sensitive data in client responses

## Monitoring & Observability

### Prometheus Metrics
Access metrics at `/metrics` endpoint:
- Request latency and throughput
- Payment transaction metrics
- Cache hit/miss rates
- Circuit breaker state

### Grafana Dashboards
Pre-configured dashboards for:
- Payment flow monitoring
- System performance
- Error rates and alerting
- SLA compliance tracking

## 🧪 Testing

### Run Automated Tests
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/security/

# Run with coverage
pytest --cov=. tests/
```

### Manual Testing
For manual testing procedures, see [tests/MANUAL_TESTING_CHECKLIST.md](tests/MANUAL_TESTING_CHECKLIST.md)

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment instructions.

## Rollback Procedures

If you need to rollback to Quickteller:
See [docs/ROLLBACK.md](docs/ROLLBACK.md) for detailed procedures.

## 📚 Documentation

### User Guides
- [KoraPay Setup Guide](docs/KORAPAY_SETUP.md) - Configure KoraPay integration
- [Rollback Guide](docs/ROLLBACK.md) - Rollback procedures
- [Email Setup Guide](EMAIL_SETUP_GUIDE.md) - Configure email notifications
- [Google OAuth Setup Guide](docs/GOOGLE_OAUTH_SETUP.md) - Configure Google Sign-In
- [Manual Test Guide](docs/MANUAL_TEST_GUIDE.md) - Testing procedures

### Technical Documentation
- [Korapay Integration Summary](docs/Korapay%20Integration%20Summary.md) - Integration details
- [Security Guide](docs/SECURITY.md) - Security features and best practices
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [Webhook Verification](docs/WEBHOOK_VERIFICATION.md) - Webhook setup

### Development
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [API Documentation](docs/README.md) - API reference

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest tests/`)
5. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Message Convention
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📊 Project Status

- **Version**: 1.5.5
- **Status**: Production Ready ✅
- **Payment Provider**: KoraPay ✅
- **Security Audit**: 8/8 vulnerabilities resolved ✅
- **Test Coverage**: Comprehensive test suite ✅

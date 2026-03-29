# One-Pay

A secure payment verification and link generation platform that integrates with Quickteller API. The goal of this system is to eliminate fake payment confirmations by allowing users to generate secure, time-bound payment links and verify transactions directly from the payment infrastructure instead of relying on screenshots.

## Features

### Core Payment Features
- **Secure Payment Links**: Generate time-bound, single-use payment links with automatic expiration
- **Direct API Verification**: Verify transactions directly from Quickteller API, eliminating screenshot fraud
- **QR Code Generation**: Automatic QR codes for easy mobile payments
- **Transaction History**: Track all payment links and their verification status
- **Webhook Integration**: Real-time payment notifications via Quickteller webhooks

### Invoice & Receipt System
- **Automated Invoice Generation**: Auto-create invoices for verified payments
- **Professional PDF Invoices**: Download invoices and receipts as PDF
- **Invoice Management**: Web interface to view, download, and send invoices
- **Business Branding**: Add your logo, tax ID, and payment terms
- **Invoice Status Tracking**: Track invoice lifecycle (DRAFT, SENT, PAID, EXPIRED, CANCELLED)

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
- **Rate Limiting**: Protection against abuse with configurable rate limits
- **Audit Logging**: Comprehensive logging of all security-relevant actions
- **CSRF Protection**: Secure session management and form protection

## Tech Stack

- **Backend**: Python 3.x, Flask
- **Database**: SQLite (development), PostgreSQL (production ready)
- **ORM**: SQLAlchemy with Alembic migrations
- **Authentication**: Flask-Login, bcrypt
- **API Integration**: Quickteller Payment Gateway
- **Security**: CSRF protection, secure session management, IP tracking

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

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
python migrate.py
```

7. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Configuration

Key environment variables in `.env`:

- `SECRET_KEY`: Flask secret key for session management
- `DATABASE_URL`: Database connection string
- `QUICKTELLER_MERCHANT_ID`: Your Quickteller merchant ID
- `QUICKTELLER_API_KEY`: Your Quickteller API key
- `QUICKTELLER_TERMINAL_ID`: Your Quickteller terminal ID
- `MAIL_SERVER`: SMTP server for email notifications
- `MAIL_USERNAME`: Email account username
- `MAIL_PASSWORD`: Email account password

See `.env.example` for all available configuration options.

## Usage

### For Users

1. **Register**: Create an account with email and password
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
│   ├── audit_log.py      # Audit log model
│   └── rate_limit.py     # Rate limit model
├── services/              # Business logic
│   ├── quickteller.py    # Quickteller API integration
│   ├── email.py          # Email service
│   ├── invoice.py        # Invoice generation
│   ├── pdf_receipt.py    # PDF generation
│   ├── qr_code.py        # QR code generation
│   ├── webhook.py        # Webhook handler
│   ├── rate_limiter.py   # Rate limiting
│   └── security.py       # Security utilities
├── core/                  # Core utilities
│   ├── auth.py           # Authentication helpers
│   ├── responses.py      # Response formatters
│   └── audit.py          # Audit logging
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── alembic/               # Database migrations
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Security Features

- Bcrypt password hashing
- CSRF protection on all forms
- Secure session management
- Rate limiting on sensitive endpoints
- IP address tracking and logging
- Webhook signature verification
- SQL injection prevention via ORM
- XSS protection via template escaping

See [SECURITY.md](docs/SECURITY.md) for detailed security information.

## Testing

Run the test suite:
```bash
pytest tests/
```

For manual testing, see [MANUAL_TEST_GUIDE.md](docs/MANUAL_TEST_GUIDE.md)

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment instructions.

## Documentation

- [Security Guide](docs/SECURITY.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Test Plan](docs/TEST_PLAN.md)
- [Upgrade Guide](docs/UPGRADE_GUIDE.md)
- [Webhook Verification](docs/WEBHOOK_VERIFICATION.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [documentation](docs/README.md)

## Acknowledgments

- Quickteller API for payment processing
- Flask framework and community
- All contributors to this project

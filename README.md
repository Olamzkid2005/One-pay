# OnePay

A modern, secure payment verification and invoice management platform that integrates with Quickteller API. OnePay eliminates fake payment confirmations by allowing merchants to generate secure, time-bound payment links, automatically create professional invoices, and verify transactions directly from the payment infrastructure.

## 🚀 Latest Updates (v1.2.0)

- ✨ **Invoice System**: Automatic invoice generation with PDF export
- 📧 **Email Notifications**: Payment alerts with invoice attachments
- 🎨 **Light/Dark Mode**: Beautiful theme toggle with persistent preference
- 📱 **Enhanced UI/UX**: Collapsible sidebar and improved accessibility
- 🔒 **Security**: Enhanced audit logging and email validation

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

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

## 📸 Screenshots

### Dashboard
![Dashboard](https://via.placeholder.com/800x400?text=Dashboard+Screenshot)

### Invoice Management
![Invoices](https://via.placeholder.com/800x400?text=Invoice+Management)

### Light/Dark Mode
![Theme Toggle](https://via.placeholder.com/800x400?text=Light+Dark+Mode)

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)
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
   - Create your merchant account

2. **Configure Settings** (Optional)
   - Go to Settings page
   - Add your business name, logo, and tax ID
   - Enable auto-send email for customer invoices

3. **Create Your First Payment Link**
   - Enter amount and description
   - Click "Generate Payment Link"
   - Share the link with your customer

4. **View Invoice**
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

# Quickteller API
QUICKTELLER_MERCHANT_ID=your-merchant-id
QUICKTELLER_API_KEY=your-api-key
QUICKTELLER_TERMINAL_ID=your-terminal-id
QUICKTELLER_BASE_URL=https://api.quickteller.com

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@onepay.com
```

### Email Setup

For email notifications to work:

1. **Gmail**: Use App Password (not your regular password)
   - Enable 2FA on your Google account
   - Generate App Password at https://myaccount.google.com/apppasswords
   - Use the generated password in `MAIL_PASSWORD`

2. **Other SMTP Providers**: Update `MAIL_SERVER` and `MAIL_PORT` accordingly

See [EMAIL_SETUP_GUIDE.md](EMAIL_SETUP_GUIDE.md) for detailed instructions.

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

## 🧪 Testing

### Run Automated Tests
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_email_notifications.py

# Run with coverage
pytest --cov=. tests/
```

### Test Coverage
- Email notifications: 11 tests
- Invoice system: 20+ tests
- PDF generation: Automated tests
- Integration: End-to-end workflow tests

For manual testing procedures, see [MANUAL_TEST_GUIDE.md](docs/MANUAL_TEST_GUIDE.md)

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment instructions.

## 📚 Documentation

### User Guides
- [Email Setup Guide](EMAIL_SETUP_GUIDE.md) - Configure email notifications
- [Manual Test Guide](docs/MANUAL_TEST_GUIDE.md) - Testing procedures

### Technical Documentation
- [Security Guide](docs/SECURITY.md) - Security features and best practices
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [Test Plan](docs/TEST_PLAN.md) - Testing strategy
- [Upgrade Guide](docs/UPGRADE_GUIDE.md) - Version upgrade instructions
- [Webhook Verification](docs/WEBHOOK_VERIFICATION.md) - Webhook setup
- [QR Code Feature](docs/QR_CODE_FEATURE.md) - QR code implementation

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

- **Version**: 1.2.0
- **Status**: Active Development
- **License**: MIT
- **Python**: 3.8+
- **Last Updated**: March 29, 2026

## 🆘 Support

### Getting Help
- 📖 Check the [documentation](docs/README.md)
- 🐛 [Open an issue](https://github.com/Olamzkid2005/One-pay/issues) on GitHub
- 💬 Review [closed issues](https://github.com/Olamzkid2005/One-pay/issues?q=is%3Aissue+is%3Aclosed) for solutions

### Reporting Bugs
When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Error messages and logs
- Expected vs actual behavior

## 🙏 Acknowledgments

- [Quickteller API](https://www.quickteller.com/) for payment processing
- [Flask](https://flask.palletsprojects.com/) framework and community
- [xhtml2pdf](https://github.com/xhtml2pdf/xhtml2pdf) for PDF generation
- [Tailwind CSS](https://tailwindcss.com/) for styling
- All contributors to this project

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by the OnePay Team**

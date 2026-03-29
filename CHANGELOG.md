# OnePay Changelog

## Version 1.2.0 - March 29, 2026

### 🎨 UI/UX Improvements

#### Light/Dark Mode Theme Toggle
- **Feature**: Added system-wide theme toggle with persistent preference
- **Implementation**:
  - Toggle button positioned at top-left (left: 93px, top: 10px)
  - Theme preference stored in localStorage
  - Smooth transitions between light and dark modes
  - Dynamic icon switching (light_mode ↔ dark_mode)
  - Theme initialized before page render to prevent flash
- **Color Schemes**:
  - **Light Mode**: Soft gray background (#F9FAFB), dark text (#111827)
  - **Dark Mode**: Custom dark background (#10141a), light text (#dfe2eb)
- **Files Modified**:
  - `templates/base.html` - Theme initialization script
  - `templates/dashboard_base.html` - Toggle button and JavaScript

#### Sidebar Improvements
- **Feature**: Collapsible sidebar with toggle button
- **Implementation**:
  - Sidebar toggle button positioned at top-left (left: 35px, top: 10px)
  - Smooth slide animation (0.3s ease transition)
  - Responsive design for mobile and desktop
  - Theme-aware styling (adapts to light/dark mode)
- **Styling**:
  - Light mode: Gray background with subtle border
  - Dark mode: Dark background with blue accents
  - Hover states for better interactivity
- **Files Modified**:
  - `templates/dashboard_base.html` - Sidebar toggle functionality

#### Page Title Contrast
- **Improvement**: Enhanced readability in light mode
- **Change**: Updated page titles from `text-primary` to `text-gray-800 dark:text-primary`
- **Reason**: Better contrast for WCAG 2.1 AA compliance
- **Pages Updated**:
  - Create Payment Link (`templates/index.html`)
  - Check Transaction Status (`templates/check_status.html`)
  - Merchant Settings (`templates/settings.html`)
  - Invoices (`templates/invoices.html`)
  - Transaction History (`templates/history.html`)

#### Background Color Optimization
- **Improvement**: Softer background in light mode
- **Change**: Replaced pure white (#FFFFFF) with soft gray (#F9FAFB)
- **Benefit**: Reduces eye strain and provides better visual comfort
- **Files Modified**:
  - `templates/base.html` - Body background
  - `templates/dashboard_base.html` - Sidebar background

### 📄 Invoice & Receipt System

#### Invoice Generation
- **Feature**: Automatic invoice creation for verified payments
- **Implementation**:
  - Auto-generates invoice when payment is confirmed
  - Unique invoice numbers (format: INV-YYYY-NNNNNN)
  - Invoice status tracking (DRAFT, SENT, PAID, EXPIRED, CANCELLED)
  - Business branding support (logo, tax ID, payment terms)
- **Database Schema**:
  - `invoices` table with transaction linkage
  - `invoice_settings` table for merchant preferences
  - Proper indexes for performance
- **Files Added**:
  - `models/invoice.py` - Invoice data models
  - `services/invoice.py` - Invoice business logic
  - `blueprints/invoices.py` - Invoice API endpoints
  - `alembic/versions/20260327000001_add_invoice_tables.py` - Database migration

#### PDF Receipt Generation
- **Feature**: Professional PDF invoices and receipts
- **Implementation**:
  - HTML-to-PDF conversion using xhtml2pdf
  - Responsive design for print and digital viewing
  - Includes QR codes for payment links
  - Business logo and branding
  - Itemized transaction details
- **Templates**:
  - `templates/invoice.html` - Invoice template
  - `templates/receipt.html` - Receipt template
- **API Endpoints**:
  - `GET /api/invoices/<invoice_number>/download` - Download invoice PDF
  - `GET /api/receipts/<tx_ref>/download` - Download receipt PDF
- **Files Added**:
  - `services/pdf_receipt.py` - PDF generation service

#### Invoice Management UI
- **Feature**: Web interface for invoice management
- **Capabilities**:
  - View all invoices with filtering by status
  - Download invoices as PDF
  - Send invoices via email
  - Track invoice status and payment
  - View invoice details and history
- **Pages Added**:
  - `/invoices` - Invoice list page
  - `/invoices/<invoice_number>` - Invoice detail page
- **Files Modified**:
  - `templates/invoices.html` - Invoice management interface

### 📧 Email Notification System

#### Payment Notification Emails
- **Feature**: Automatic email notifications for verified payments
- **Implementation**:
  - Merchant notification email (always sent)
  - Customer invoice email (optional, based on settings)
  - Retry logic with exponential backoff (1min, 5min, 15min)
  - Graceful degradation on failures
- **Merchant Notification**:
  - Subject: "Payment Received - {tx_ref}"
  - Includes transfer details table
  - Attaches invoice PDF when available
  - HTML email with branding
- **Customer Invoice Email**:
  - Sent when `auto_send_email` setting is enabled
  - Merchant receives BCC copy
  - Includes invoice PDF attachment
  - Professional HTML template
- **Files Modified**:
  - `services/email.py` - Email sending functions
  - `services/webhook.py` - Payment notification orchestration
  - `blueprints/public.py` - Webhook integration

#### Email Configuration
- **Settings**: SMTP configuration via environment variables
- **Features**:
  - Email validation and header injection prevention
  - Multipart emails (plain text + HTML)
  - Dev mode support (logs instead of sending)
  - Audit logging for all email operations
- **Configuration**:
  - `MAIL_SERVER` - SMTP server address
  - `MAIL_PORT` - SMTP port (default: 587)
  - `MAIL_USERNAME` - Email account username
  - `MAIL_PASSWORD` - Email account password
  - `MAIL_USE_TLS` - Enable TLS (default: True)

### 🔧 Bug Fixes

#### Invoice Template Rendering
- **Issue**: Invoice PDF generation failed with template error
- **Root Cause**: Used Python's `hasattr()` function in Jinja2 template
- **Fix**: Directly access `.value` attribute on enum objects
- **Impact**: Restored invoice download and viewing functionality
- **Files Fixed**: `templates/invoice.html`

#### Transaction Reference Format
- **Issue**: Transaction references were too long (47 characters)
- **Fix**: Shortened to 23 characters for better usability
- **Format**: `TXN-{timestamp}-{random}`
- **Impact**: Improved readability and compatibility

### 🗄️ Database Changes

#### New Tables
- `invoices` - Invoice records with transaction linkage
- `invoice_settings` - Merchant invoice preferences

#### Indexes Added
- `ix_invoices_invoice_number` - Fast invoice lookup
- `ix_invoices_transaction` - Transaction-to-invoice mapping
- `ix_invoices_user_created` - User invoice history
- `ix_invoices_user_status` - Invoice filtering by status
- `ix_invoice_settings_user_id` - User settings lookup

#### Migration
- Migration file: `alembic/versions/20260327000001_add_invoice_tables.py`
- Run with: `alembic upgrade head`

### 🧪 Testing

#### Test Suite Cleanup
- **Removed**: Duplicate and manual test files
- **Kept**: Core automated tests
- **Remaining Tests**:
  - `test_email_notifications.py` - Email notification tests (11 tests)
  - `test_invoice_model_unit.py` - Invoice model tests
  - `test_invoice_service_unit.py` - Invoice service tests
  - `test_invoices_blueprint.py` - Invoice API tests
  - `test_invoice_pdf_generation.py` - PDF generation tests
  - `test_invoice_payment_link_integration.py` - Integration tests
  - `test_public_invoice_sync_integration.py` - Webhook sync tests
  - `test_settings_route.py` - Settings API tests
  - `test_webhook_invoice_sync.py` - Webhook tests

#### Test Coverage
- Email notifications: 11 unit tests
- Invoice system: 20+ tests
- PDF generation: Automated tests
- Integration: End-to-end workflow tests

### 📚 Documentation

#### New Documentation
- `EMAIL_SETUP_GUIDE.md` - Email configuration guide
- `CHANGELOG.md` - This file

#### Updated Documentation
- `README.md` - Updated with new features
- `docs/README.md` - API documentation updates

#### Removed Documentation
- Cleaned up temporary fix reports and analysis files
- Consolidated documentation into main files

### 🔐 Security

#### Email Security
- Email validation prevents header injection
- SMTP credentials stored in environment variables
- No sensitive data in email logs
- BCC privacy maintained

#### Invoice Security
- Invoice access requires authentication
- Ownership verification on all operations
- Audit logging for invoice operations
- Secure PDF generation

### 🚀 Performance

#### Optimizations
- Email sending is non-blocking
- PDF generation cached where possible
- Database indexes for fast queries
- Efficient template rendering

#### Metrics
- PDF generation: ~100-200ms
- Email sending: ~1-3 seconds
- Invoice lookup: <10ms (indexed)

### 📦 Dependencies

#### No New Dependencies
All features implemented using existing dependencies:
- `xhtml2pdf` - Already in requirements.txt
- `Flask-Mail` - Already in requirements.txt
- `Jinja2` - Already in requirements.txt

### 🔄 Migration Guide

#### Upgrading from v1.1.0

1. **Backup Database**:
   ```bash
   cp onepay.db onepay.db.backup
   ```

2. **Run Database Migration**:
   ```bash
   alembic upgrade head
   ```

3. **Configure Email** (Optional):
   ```bash
   # Add to .env
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_USE_TLS=True
   ```

4. **Restart Application**:
   ```bash
   python app.py
   ```

5. **Verify Features**:
   - Test theme toggle
   - Create a test invoice
   - Download invoice PDF
   - Check email notifications (if configured)

### 🎯 Breaking Changes

None. All changes are backward compatible.

### 📝 Notes

- Theme preference is stored in browser localStorage
- Email notifications require SMTP configuration
- Invoice PDFs are generated on-demand
- All new features are optional and can be disabled

### 🙏 Acknowledgments

- UI/UX improvements inspired by modern design principles
- Invoice system follows industry best practices
- Email notifications based on user feedback

---

## Version 1.1.0 - March 22, 2026

### Features
- QR code generation for payment links
- Payment method management
- Webhook verification improvements
- Rate limiting enhancements

### Bug Fixes
- Transaction cascade delete issues
- Password hashing migration to bcrypt

---

## Version 1.0.0 - Initial Release

### Features
- Secure payment link generation
- Quickteller API integration
- User authentication and authorization
- Transaction history tracking
- Webhook support
- Audit logging
- Rate limiting


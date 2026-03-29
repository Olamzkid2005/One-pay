# Design Document: Automatic Payment Notification Emails

## Overview

This feature adds automatic email notifications when payments are confirmed via webhook. The system sends two types of emails:

1. **Merchant notification email**: Sent to the merchant when they receive a payment, containing transfer details and an attached invoice PDF
2. **Customer invoice email**: Optionally sent to the customer (controlled by merchant settings), containing the invoice PDF and payment confirmation

The feature integrates with the existing webhook handler (`services/webhook.py`), email service (`services/email.py`), and invoice generation system. A new settings toggle allows merchants to control whether customer invoices are automatically sent.

Key design principles:
- Email delivery failures never block payment confirmation
- Retry logic with exponential backoff for resilience
- Merchant always receives notification regardless of settings
- Customer emails respect the `auto_send_email` toggle
- Graceful degradation if invoice generation fails

## Architecture

### Component Flow

```
Payment Webhook → Webhook Handler → Invoice Check/Creation → Email Delivery
                                          ↓
                                    Invoice Generator
                                          ↓
                                    PDF Generation
                                          ↓
                                    Email Service (with retry)
```

### Integration Points

1. **Webhook Handler** (`services/webhook.py`):
   - Entry point for payment confirmation events
   - Orchestrates invoice creation and email delivery
   - Updates invoice status to "paid" when payment verified
   - Calls new function: `send_payment_notification_emails()`

2. **Email Service** (`services/email.py`):
   - Existing: `send_invoice_email()` - reused for customer emails
   - New: `send_merchant_notification_email()` - merchant payment alerts
   - Both use existing retry logic and SMTP configuration

3. **Invoice Service** (`services/invoice.py`):
   - Existing: `create_invoice()` - creates invoice from transaction
   - Existing: `generate_invoice_pdf()` - generates PDF bytes
   - Used by webhook handler to ensure invoice exists before emailing

4. **Settings Manager** (database + API):
   - Existing: `InvoiceSettings.auto_send_email` boolean field
   - Existing: Settings API endpoint for updates
   - Controls whether customer emails are sent automatically

### Data Flow

1. Payment webhook received → transaction status updated to VERIFIED
2. Check if invoice exists for transaction
3. If no invoice → create invoice using merchant's InvoiceSettings
4. Generate invoice PDF
5. Send merchant notification email (always)
6. If `auto_send_email` enabled AND customer_email exists → send customer invoice email
7. Update invoice status and email tracking fields
8. Log all operations for audit trail

## Components and Interfaces

### 1. Webhook Handler Enhancement

**File**: `services/webhook.py`

**New Function**: `send_payment_notification_emails(db, transaction, user)`

```python
def send_payment_notification_emails(db, transaction, user):
    """
    Send payment notification emails after payment confirmation.
    
    Args:
        db: Database session
        transaction: Verified Transaction object
        user: User (merchant) object
        
    Side Effects:
        - Creates invoice if not exists
        - Sends merchant notification email
        - Sends customer invoice email (if auto_send_email enabled)
        - Updates invoice status and email tracking
        - Logs all operations
        
    Returns:
        None (failures are logged but don't raise exceptions)
    """
```

**Integration**: Called from existing webhook handler after transaction status is updated to VERIFIED.

### 2. Email Service Enhancement

**File**: `services/email.py`

**New Function**: `send_merchant_notification_email(to_email, transaction, invoice, pdf_bytes)`

```python
def send_merchant_notification_email(
    to_email: str,
    transaction,
    invoice,
    pdf_bytes: bytes
) -> bool:
    """
    Send payment notification email to merchant.
    
    Args:
        to_email: Merchant email address
        transaction: Transaction object with payment details
        invoice: Invoice object (may be None if generation failed)
        pdf_bytes: Invoice PDF bytes (may be None if generation failed)
        
    Returns:
        True if sent successfully, False otherwise
        
    Email Content:
        - Subject: "Payment Received - {tx_ref}"
        - Body: Transfer details table (amount, currency, customer, timestamp)
        - Attachment: Invoice PDF (if available)
        - Retry: 3 attempts with exponential backoff (1min, 5min, 15min)
    """
```

**Reused Function**: `send_invoice_email()` - already exists, will be used for customer emails with merchant BCC.

### 3. Invoice Status Synchronization

**File**: `services/webhook.py`

**Existing Function**: `sync_invoice_on_transaction_update(db, transaction)`

This function already exists and handles invoice status updates when transaction status changes. It will be called as part of the webhook flow to update invoice status to "paid" when payment is verified.

### 4. Settings Toggle

**Database**: `InvoiceSettings.auto_send_email` (already exists)

**UI**: Settings page toggle control (already exists in `templates/settings.html`)

**API**: Settings update endpoint (already exists in `blueprints/payments.py`)

No changes needed - the existing infrastructure supports the toggle.

## Data Models

### Invoice Model (Existing)

**File**: `models/invoice.py`

No schema changes required. Existing fields support email tracking:

```python
class Invoice(Base):
    # ... existing fields ...
    
    # Email delivery tracking (already exists)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_attempts = Column(Integer, default=0)
    email_last_error = Column(Text, nullable=True)
```

### InvoiceSettings Model (Existing)

**File**: `models/invoice.py`

No schema changes required. Existing field controls auto-send:

```python
class InvoiceSettings(Base):
    # ... existing fields ...
    
    # Auto-send toggle (already exists)
    auto_send_email = Column(Boolean, default=False)
```

### User Model (Existing)

**File**: `models/user.py`

No schema changes required. Existing email field used for merchant notifications:

```python
class User(Base):
    # ... existing fields ...
    
    email = Column(String(255), unique=True, index=True, nullable=True)
```

## Error Handling

### Email Delivery Failures

**Strategy**: Graceful degradation with retry logic

1. **Retry Logic**: 3 attempts with exponential backoff (1 minute, 5 minutes, 15 minutes)
2. **Failure Handling**: Log error, update invoice tracking fields, continue processing
3. **Never Block Payment**: Email failures never prevent payment confirmation
4. **Audit Trail**: All attempts logged with timestamps and error messages

### Invoice Generation Failures

**Strategy**: Send notification without attachment

1. **PDF Generation Timeout**: Log error, send email without attachment
2. **Invoice Creation Failure**: Log error, send merchant notification with transaction details only
3. **Graceful Degradation**: Merchant always receives notification even if invoice fails

### Missing Data Scenarios

1. **No Merchant Email**: Log warning, skip merchant notification
2. **No Customer Email**: Skip customer notification (expected behavior)
3. **No Invoice Settings**: Create invoice with default settings
4. **SMTP Not Configured**: Log to console (dev mode behavior)

### Validation Errors

1. **Invalid Email Format**: Validate before sending, log error if invalid
2. **Email Header Injection**: Existing validation in `send_invoice_email()` prevents this
3. **Missing Required Fields**: Check before email generation, log error if missing

## Testing Strategy

### Unit Tests

**File**: `tests/test_email_notifications.py`

1. **Merchant Notification Email**:
   - Test email sent with correct subject and content
   - Test PDF attachment included when available
   - Test email sent without attachment when PDF generation fails
   - Test retry logic on SMTP failure
   - Test email validation (invalid format rejected)

2. **Customer Invoice Email**:
   - Test email sent when auto_send_email enabled
   - Test email NOT sent when auto_send_email disabled
   - Test merchant BCC included
   - Test email sent with PDF attachment and QR code
   - Test retry logic on delivery failure

3. **Webhook Integration**:
   - Test `send_payment_notification_emails()` orchestration
   - Test invoice creation when not exists
   - Test invoice status updated to "paid"
   - Test both emails sent in correct order
   - Test graceful degradation on failures

4. **Settings Toggle**:
   - Test auto_send_email defaults to False
   - Test toggle persists to database
   - Test customer emails respect toggle state

### Property-Based Tests

**File**: `tests/test_email_notifications_properties.py`

Property-based tests will be defined after completing the Correctness Properties section below.

### Integration Tests

**File**: `tests/test_webhook_email_integration.py`

1. **End-to-End Flow**:
   - Simulate payment webhook → verify both emails sent
   - Verify invoice created and status updated
   - Verify email tracking fields updated
   - Verify audit log entries created

2. **Error Scenarios**:
   - SMTP failure → verify retry attempts logged
   - PDF generation failure → verify email sent without attachment
   - Missing merchant email → verify graceful skip

### Manual Testing

1. Configure SMTP settings in `.env`
2. Create payment link with customer email
3. Trigger payment webhook (simulate or use test payment)
4. Verify merchant receives notification email
5. Verify customer receives invoice email (if auto_send_email enabled)
6. Check email tracking in database
7. Verify audit log entries


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Merchant Notification Always Sent

*For any* verified payment transaction with a merchant who has an email address, the system SHALL send a payment notification email to the merchant's email address.

**Validates: Requirements 1.1, 1.6**

### Property 2: Merchant Email Subject Format

*For any* merchant notification email, the subject line SHALL match the pattern "Payment Received - {tx_ref}" where tx_ref is the transaction reference.

**Validates: Requirements 1.2**

### Property 3: Merchant Email Contains Transfer Details

*For any* merchant notification email, the email body SHALL contain all of the following transfer details: amount, currency, customer email (if present), transaction reference, and payment timestamp.

**Validates: Requirements 1.3**

### Property 4: Merchant Email Includes PDF Attachment

*For any* merchant notification email where invoice PDF generation succeeds, the email SHALL include the invoice PDF as an attachment.

**Validates: Requirements 1.4**

### Property 5: Email Retry with Exponential Backoff

*For any* email delivery failure (merchant or customer), the Email_Service SHALL retry delivery with exponential backoff delays of 1 minute, 5 minutes, and 15 minutes (3 total attempts).

**Validates: Requirements 1.7, 2.8, 8.2**

### Property 6: Email Delivery Logging

*For any* email delivery attempt (successful or failed), the system SHALL create a log entry containing recipient, status, timestamp, and error message (if failed).

**Validates: Requirements 1.8, 6.9, 8.1**

### Property 7: Customer Email Sent When Enabled

*For any* verified payment transaction where auto_send_email is enabled AND customer_email exists, the system SHALL send an invoice email to the customer's email address.

**Validates: Requirements 2.1, 4.5, 6.3**

### Property 8: Customer Email Requires Customer Address

*For any* verified payment transaction, the system SHALL only send a customer invoice email IF the transaction has a non-null customer_email field.

**Validates: Requirements 2.2**

### Property 9: Customer Email Subject Format

*For any* customer invoice email, the subject line SHALL match the pattern "Invoice {invoice_number} from {business_name}" where invoice_number and business_name are from the invoice record.

**Validates: Requirements 2.3**

### Property 10: Customer Email Includes PDF Attachment

*For any* customer invoice email, the email SHALL include the invoice PDF as an attachment.

**Validates: Requirements 2.4**

### Property 11: Customer Email Contains Confirmation Message

*For any* customer invoice email, the email body SHALL contain a payment confirmation message.

**Validates: Requirements 2.5**

### Property 12: Customer Email Includes Payment URL and QR Code

*For any* customer invoice email, the email body SHALL include both the payment URL and the QR code data URI (if available).

**Validates: Requirements 2.6**

### Property 13: Invoice Auto-Creation Before Email

*For any* verified payment transaction that does not have an associated invoice, the system SHALL create an invoice using the merchant's InvoiceSettings before sending any emails.

**Validates: Requirements 2.7, 6.2**

### Property 14: Invoice Status Updated on Successful Email

*For any* customer invoice email that is successfully delivered, the invoice SHALL have email_sent set to True and email_sent_at set to the delivery timestamp.

**Validates: Requirements 2.9, 9.2**

### Property 15: Download Filename Format

*For any* invoice PDF download, the downloaded filename SHALL match the pattern "{invoice_number}.pdf" where invoice_number is the invoice's number.

**Validates: Requirements 3.4**

### Property 16: Settings Persistence Round-Trip

*For any* boolean value assigned to auto_send_email in InvoiceSettings, saving to the database then querying SHALL return the same boolean value.

**Validates: Requirements 4.3**

### Property 17: Auto-Send Default Value

*For any* newly created InvoiceSettings record, the auto_send_email field SHALL default to False.

**Validates: Requirements 4.4**

### Property 18: Auto-Send Toggle Controls Customer Emails

*For any* verified payment transaction with a customer email, customer invoice emails SHALL be sent if and only if auto_send_email is enabled in the merchant's InvoiceSettings.

**Validates: Requirements 4.5, 4.6**

### Property 19: Merchant Email Independent of Auto-Send

*For any* verified payment transaction, the merchant notification email SHALL be sent regardless of the auto_send_email setting value (enabled or disabled).

**Validates: Requirements 4.7, 6.4**

### Property 20: Settings UI Reflects Current State

*For any* InvoiceSettings record, rendering the settings page SHALL display the auto_send_email toggle in a state that matches the current database value.

**Validates: Requirements 4.8**

### Property 21: Settings Change Audit Logging

*For any* change to the auto_send_email setting, the system SHALL create an audit log entry containing the event type, merchant ID, timestamp, and new value.

**Validates: Requirements 4.10**

### Property 22: Customer Email BCC to Merchant

*For any* customer invoice email where the merchant email differs from the customer email, the email SHALL include the merchant email in the BCC field.

**Validates: Requirements 5.1**

### Property 23: No BCC on Merchant Notifications

*For any* merchant notification email, the email SHALL NOT include a BCC field.

**Validates: Requirements 5.2**

### Property 24: No BCC When Emails Match

*For any* customer invoice email where the merchant email equals the customer email, the email SHALL NOT include a BCC field.

**Validates: Requirements 5.3**

### Property 25: Invoice Existence Check on Webhook

*For any* verified payment webhook, the system SHALL query the database to check if an invoice exists for the transaction before proceeding with email delivery.

**Validates: Requirements 6.1**

### Property 26: PDF Generation Before Emails

*For any* verified payment webhook that triggers email delivery, invoice PDF generation SHALL complete before any email sending operations begin.

**Validates: Requirements 6.5**

### Property 27: Invoice Status Updated to Paid

*For any* verified payment webhook, the associated invoice SHALL have its status updated to "paid" and paid_at timestamp set to the verification time.

**Validates: Requirements 6.7**

### Property 28: Email Failure Does Not Block Payment

*For any* verified payment webhook, email delivery failures (merchant or customer) SHALL NOT prevent the payment verification from completing successfully.

**Validates: Requirements 6.8**

### Property 29: Multipart Email Format

*For any* email sent by the Email_Service, the email SHALL contain both a plain text part and an HTML part (multipart/alternative format).

**Validates: Requirements 7.1**

### Property 30: HTML Email Includes Branding

*For any* email sent by the Email_Service, the HTML part SHALL include the merchant's business_name, and SHALL include business_logo_url if configured.

**Validates: Requirements 7.2**

### Property 31: Customer Email Contains Required Fields

*For any* customer invoice email, the email body SHALL contain all of the following: invoice number, amount, description, payment terms, and payment link with QR code (if available).

**Validates: Requirements 7.4**

### Property 32: Email Footer Branding

*For any* email sent by the Email_Service, the email footer SHALL contain the text "Powered by OnePay".

**Validates: Requirements 7.5**

### Property 33: HTML Content Escaping

*For any* user-provided content included in email HTML (description, business name, customer email), the content SHALL be HTML-escaped to prevent injection attacks.

**Validates: Requirements 7.7**

### Property 34: Email Subject Length Constraint

*For any* email sent by the Email_Service, the subject line SHALL NOT exceed 255 characters.

**Validates: Requirements 7.8**

### Property 35: Email Attempts Counter Increments

*For any* email delivery attempt (successful or failed), the invoice's email_attempts field SHALL increment by 1.

**Validates: Requirements 8.4, 9.1, 9.3**

### Property 36: Last Error Message Stored

*For any* failed email delivery attempt, the invoice's email_last_error field SHALL be updated with the error message from the most recent failure.

**Validates: Requirements 8.5, 9.4**

### Property 37: Email Address Validation Before Delivery

*For any* email address provided to the Email_Service, the system SHALL validate the email format before attempting SMTP delivery, and SHALL reject invalid formats.

**Validates: Requirements 8.7**

### Property 38: Invoice API Includes Email Status

*For any* invoice detail API response, the response SHALL include the email delivery status fields: email_sent, email_sent_at, email_attempts, and email_last_error.

**Validates: Requirements 9.5**

### Property 39: Audit Log for Email Events

*For any* invoice email event (sent or failed), the system SHALL create an audit log entry containing event type, invoice number, recipient, timestamp, and success/failure status.

**Validates: Requirements 9.6**

### Property 40: Invoice Serialization Round-Trip

*For any* invoice created from a transaction and merchant settings, the invoice SHALL store denormalized copies of merchant branding data (business_name, business_address, business_tax_id, business_logo_url, payment_terms), and generating a PDF from the stored invoice SHALL use these denormalized values rather than current merchant settings, ensuring that changes to merchant settings after invoice creation do not affect the invoice PDF content.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.7**


## Error Handling

### Email Delivery Failures

**Retry Strategy**:
- 3 attempts with exponential backoff: 1 minute, 5 minutes, 15 minutes
- Implemented in existing `send_invoice_email()` function
- Each attempt logged with timestamp and error details
- Invoice tracking fields updated: `email_attempts`, `email_last_error`

**Failure Scenarios**:
1. **SMTP Connection Failure**: Retry with backoff, log error after final attempt
2. **Invalid Recipient**: Validate email format before sending, reject immediately if invalid
3. **Timeout**: Log timeout error, retry with backoff
4. **Authentication Failure**: Log error, do not retry (configuration issue)

**Non-Blocking Behavior**:
- Email failures NEVER block payment verification
- Payment webhook completes successfully even if all email attempts fail
- Merchant can manually resend emails from invoice detail page (future enhancement)

### Invoice Generation Failures

**PDF Generation Failure**:
- Log error with full stack trace
- Send merchant notification email WITHOUT attachment
- Include error message in email body: "Invoice PDF generation failed"
- Update invoice `email_last_error` field with generation error

**Invoice Creation Failure**:
- Log error with transaction details
- Send merchant notification with transaction details only (no invoice reference)
- Payment verification still succeeds
- Merchant can manually create invoice later

**Timeout Handling**:
- PDF generation timeout: 30 seconds (configurable)
- Log timeout error
- Send email without attachment
- Mark invoice with generation error

### Missing Data Scenarios

**No Merchant Email**:
- Log warning: "Merchant notification skipped - no email address"
- Continue with customer email (if applicable)
- Payment verification succeeds

**No Customer Email**:
- Skip customer email (expected behavior)
- Log info: "Customer email skipped - no customer_email in transaction"
- Merchant notification still sent

**No Invoice Settings**:
- Create invoice with default settings
- Use business_name from User model if available
- Default payment_terms: "Payment due upon receipt"
- Log info: "Invoice created with default settings"

**SMTP Not Configured**:
- Dev mode behavior: log email details to console
- Log format: "Email (dev mode) | to={recipient} subject={subject}"
- Mark email as "sent" in dev mode for testing
- Production: log error and fail email delivery

### Validation Errors

**Email Format Validation**:
- Regex validation: `^[^@\s]+@[^@\s]+\.[^@\s]+$`
- Header injection prevention: reject emails containing `\n` or `\r`
- Length validation: max 255 characters
- Reject immediately if validation fails, do not retry

**Subject Line Validation**:
- Truncate to 255 characters if exceeds limit
- Log warning if truncation occurs
- HTML-escape all user-provided content in subject

**Attachment Size**:
- PDF size limit: 10MB (typical email attachment limit)
- Log error if PDF exceeds limit
- Send email without attachment if too large

### Audit Trail

**All Operations Logged**:
- Email delivery attempts (success/failure)
- Invoice creation/updates
- Settings changes
- PDF generation (success/failure)

**Log Levels**:
- INFO: Successful operations
- WARNING: Retries, missing data, truncation
- ERROR: Failures after all retries, validation errors
- CRITICAL: Configuration errors (SMTP auth failure)

**Audit Log Entries**:
- Event type: `email.merchant_notification`, `email.customer_invoice`, `invoice.status_synced`
- Metadata: recipient, invoice_number, tx_ref, timestamp, success/failure
- User ID and IP address (where applicable)

## Testing Strategy

### Unit Tests

**Test File**: `tests/test_email_notifications.py`

**Merchant Notification Email Tests**:
1. `test_merchant_notification_sent_on_payment_verification` - Verify email sent when payment verified
2. `test_merchant_notification_subject_format` - Verify subject matches "Payment Received - {tx_ref}"
3. `test_merchant_notification_contains_transfer_details` - Verify all required fields in body
4. `test_merchant_notification_includes_pdf_attachment` - Verify PDF attached when available
5. `test_merchant_notification_without_attachment_on_pdf_failure` - Verify email sent without attachment when PDF fails
6. `test_merchant_notification_email_validation` - Verify invalid emails rejected
7. `test_merchant_notification_retry_on_smtp_failure` - Verify retry logic with backoff

**Customer Invoice Email Tests**:
1. `test_customer_email_sent_when_auto_send_enabled` - Verify email sent when toggle enabled
2. `test_customer_email_not_sent_when_auto_send_disabled` - Verify email NOT sent when toggle disabled
3. `test_customer_email_requires_customer_address` - Verify email only sent if customer_email exists
4. `test_customer_email_subject_format` - Verify subject matches pattern
5. `test_customer_email_includes_pdf_and_qr` - Verify PDF and QR code included
6. `test_customer_email_merchant_bcc` - Verify merchant in BCC when emails differ
7. `test_customer_email_no_bcc_when_emails_match` - Verify no BCC when emails match

**Webhook Integration Tests**:
1. `test_webhook_creates_invoice_if_not_exists` - Verify auto-creation
2. `test_webhook_sends_both_emails` - Verify merchant and customer emails sent
3. `test_webhook_updates_invoice_status_to_paid` - Verify status update
4. `test_webhook_email_failure_does_not_block_payment` - Verify non-blocking behavior
5. `test_webhook_pdf_generation_before_emails` - Verify operation ordering

**Settings Tests**:
1. `test_auto_send_email_defaults_to_false` - Verify default value
2. `test_auto_send_email_persists_to_database` - Verify round-trip
3. `test_settings_ui_reflects_current_state` - Verify UI display
4. `test_settings_change_audit_logged` - Verify audit logging

**Error Handling Tests**:
1. `test_email_attempts_counter_increments` - Verify counter updates
2. `test_last_error_message_stored` - Verify error storage
3. `test_email_validation_before_delivery` - Verify validation
4. `test_html_content_escaping` - Verify XSS prevention
5. `test_subject_length_constraint` - Verify truncation

### Property-Based Tests

**Test File**: `tests/test_email_notifications_properties.py`

**Library**: Hypothesis (Python property-based testing library)

**Configuration**: Minimum 100 iterations per test

**Property Tests**:

1. **Property 1: Merchant Notification Always Sent**
   - Generate: Random verified transactions with merchant emails
   - Test: Merchant email sent for all
   - Tag: `# Feature: auto-payment-notification-emails, Property 1: For any verified payment transaction with a merchant who has an email address, the system SHALL send a payment notification email to the merchant's email address.`

2. **Property 7: Customer Email Sent When Enabled**
   - Generate: Random transactions with auto_send_email=True and customer emails
   - Test: Customer email sent for all
   - Tag: `# Feature: auto-payment-notification-emails, Property 7: For any verified payment transaction where auto_send_email is enabled AND customer_email exists, the system SHALL send an invoice email to the customer's email address.`

3. **Property 16: Settings Persistence Round-Trip**
   - Generate: Random boolean values
   - Test: Save to database, query, verify same value returned
   - Tag: `# Feature: auto-payment-notification-emails, Property 16: For any boolean value assigned to auto_send_email in InvoiceSettings, saving to the database then querying SHALL return the same boolean value.`

4. **Property 18: Auto-Send Toggle Controls Customer Emails**
   - Generate: Random transactions with customer emails, random auto_send values
   - Test: Customer email sent IFF auto_send enabled
   - Tag: `# Feature: auto-payment-notification-emails, Property 18: For any verified payment transaction with a customer email, customer invoice emails SHALL be sent if and only if auto_send_email is enabled in the merchant's InvoiceSettings.`

5. **Property 19: Merchant Email Independent of Auto-Send**
   - Generate: Random transactions, random auto_send values
   - Test: Merchant email always sent regardless of auto_send
   - Tag: `# Feature: auto-payment-notification-emails, Property 19: For any verified payment transaction, the merchant notification email SHALL be sent regardless of the auto_send_email setting value (enabled or disabled).`

6. **Property 33: HTML Content Escaping**
   - Generate: Random strings with HTML special characters
   - Test: All user content HTML-escaped in email output
   - Tag: `# Feature: auto-payment-notification-emails, Property 33: For any user-provided content included in email HTML (description, business name, customer email), the content SHALL be HTML-escaped to prevent injection attacks.`

7. **Property 40: Invoice Serialization Round-Trip**
   - Generate: Random invoice data with merchant branding
   - Test: Create invoice, change settings, generate PDF, verify PDF uses original data
   - Tag: `# Feature: auto-payment-notification-emails, Property 40: For any invoice created from a transaction and merchant settings, the invoice SHALL store denormalized copies of merchant branding data, and generating a PDF from the stored invoice SHALL use these denormalized values rather than current merchant settings.`

### Integration Tests

**Test File**: `tests/test_webhook_email_integration.py`

**End-to-End Scenarios**:
1. Complete payment flow: webhook → invoice creation → both emails sent
2. Email retry flow: SMTP failure → retry attempts → final success/failure
3. PDF generation failure: webhook → email sent without attachment
4. Missing merchant email: webhook → customer email only
5. Auto-send disabled: webhook → merchant email only

**Test Environment**:
- Use in-memory SQLite database
- Mock SMTP server for email capture
- Mock PDF generation for speed
- Real webhook handler and email service code

### Manual Testing Checklist

**Prerequisites**:
1. Configure SMTP settings in `.env`:
   ```
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_FROM=noreply@onepay.com
   ```

2. Create test merchant account with email
3. Configure invoice settings with business branding

**Test Scenarios**:

1. **Merchant Notification Email**:
   - Create payment link with customer email
   - Simulate payment webhook (or use test payment)
   - Verify merchant receives email with:
     - Subject: "Payment Received - {tx_ref}"
     - Transfer details in body
     - Invoice PDF attached
   - Check email tracking in database

2. **Customer Invoice Email (Auto-Send Enabled)**:
   - Enable auto_send_email in settings
   - Create payment link with customer email
   - Trigger payment webhook
   - Verify customer receives email with:
     - Subject: "Invoice {number} from {business}"
     - PDF attached
     - QR code in body
   - Verify merchant receives BCC copy

3. **Customer Email Not Sent (Auto-Send Disabled)**:
   - Disable auto_send_email in settings
   - Create payment link with customer email
   - Trigger payment webhook
   - Verify merchant receives notification
   - Verify customer does NOT receive email

4. **Email Retry on Failure**:
   - Temporarily misconfigure SMTP (wrong password)
   - Trigger payment webhook
   - Verify retry attempts in logs
   - Fix SMTP configuration
   - Verify eventual success or final failure logged

5. **PDF Generation Failure**:
   - Simulate PDF generation error (modify code temporarily)
   - Trigger payment webhook
   - Verify merchant receives email WITHOUT attachment
   - Verify error logged

6. **Settings Toggle**:
   - Navigate to settings page
   - Toggle auto_send_email on/off
   - Verify toggle state persists after page refresh
   - Verify audit log entry created

7. **Invoice Download**:
   - Complete payment
   - Navigate to payment success page
   - Click download link
   - Verify PDF downloads with correct filename
   - Verify link still works after first download

**Verification**:
- Check email inbox for all expected emails
- Verify email content matches requirements
- Check database for email tracking fields
- Review application logs for errors
- Verify audit log entries created


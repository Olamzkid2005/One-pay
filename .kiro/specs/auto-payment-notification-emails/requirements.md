# Requirements Document

## Introduction

This feature adds automatic email notifications when payments are confirmed. Merchants receive notification emails with transfer details and attached invoices/receipts, while customers automatically receive their invoice/receipt via email and can download it. The feature includes a settings toggle allowing merchants to enable/disable automatic email sending.

## Glossary

- **Payment_Confirmation_System**: The webhook handler that processes payment verification events from the payment gateway
- **Email_Service**: The SMTP-based service that sends emails with attachments
- **Invoice_Generator**: The service that creates invoice PDFs for transactions
- **Merchant**: The user who created the payment link and receives payments
- **Customer**: The payer who completes a payment transaction
- **Settings_Manager**: The system component that stores and retrieves merchant preferences
- **Transaction**: A payment link with associated payment details
- **Invoice**: A PDF document containing payment receipt/invoice details
- **Auto_Send_Toggle**: The merchant setting that controls automatic email delivery

## Requirements

### Requirement 1: Merchant Payment Notification Email

**User Story:** As a merchant, I want to receive an email notification when I receive a payment, so that I am immediately aware of successful transactions.

#### Acceptance Criteria

1. WHEN a payment is verified by the Payment_Confirmation_System, THE Email_Service SHALL send a notification email to the Merchant
2. THE notification email SHALL include the subject line "Payment Received - [Transaction Reference]"
3. THE notification email SHALL include transfer details: amount, currency, customer email, transaction reference, and payment timestamp
4. THE notification email SHALL include the Invoice as a PDF attachment
5. IF Invoice generation fails, THEN THE Email_Service SHALL send the notification email without the attachment and log the error
6. THE Email_Service SHALL use the Merchant email address from the user account
7. WHEN email delivery fails, THE Email_Service SHALL retry with exponential backoff (1 minute, 5 minutes, 15 minutes)
8. THE Email_Service SHALL log all email delivery attempts with success/failure status

### Requirement 2: Customer Invoice Email Delivery

**User Story:** As a customer, I want to automatically receive an invoice/receipt via email when my payment is verified, so that I have a record of my transaction.

#### Acceptance Criteria

1. WHEN a payment is verified by the Payment_Confirmation_System, THE Email_Service SHALL send an invoice email to the Customer
2. THE Email_Service SHALL only send customer invoice email IF the Customer email address exists in the Transaction
3. THE invoice email SHALL include the subject line "Invoice [Invoice Number] from [Business Name]"
4. THE invoice email SHALL include the Invoice as a PDF attachment
5. THE invoice email SHALL include a payment confirmation message in the email body
6. THE invoice email SHALL include the payment URL with QR code for reference
7. IF Invoice does not exist for the Transaction, THEN THE Invoice_Generator SHALL create the Invoice before sending email
8. WHEN email delivery fails, THE Email_Service SHALL retry with exponential backoff (1 minute, 5 minutes, 15 minutes)
9. THE Email_Service SHALL update Invoice status to "sent" and record email_sent_at timestamp when successfully delivered

### Requirement 3: Customer Receipt Download

**User Story:** As a customer, I want to automatically download my receipt when payment is verified, so that I have immediate access to my payment record.

#### Acceptance Criteria

1. WHEN a payment is verified and the Customer views the payment confirmation page, THE system SHALL provide a download link for the Invoice PDF
2. THE download link SHALL be prominently displayed on the payment success page
3. WHEN the Customer clicks the download link, THE Invoice_Generator SHALL generate the PDF and initiate browser download
4. THE downloaded file SHALL be named "[Invoice Number].pdf"
5. IF Invoice generation fails, THEN THE system SHALL display an error message and log the failure
6. THE download link SHALL remain accessible on the transaction verification page after initial download

### Requirement 4: Auto-Send Email Settings Toggle

**User Story:** As a merchant, I want to enable or disable automatic invoice email sending, so that I can control when customers receive invoices.

#### Acceptance Criteria

1. THE Settings_Manager SHALL provide an "auto_send_email" boolean setting in InvoiceSettings
2. THE settings page SHALL display a toggle control labeled "Automatically send invoices to customers"
3. WHEN the Merchant changes the auto_send_email setting, THE Settings_Manager SHALL persist the change to the database
4. THE auto_send_email setting SHALL default to False for new merchants
5. WHEN auto_send_email is enabled and a payment is verified, THE Email_Service SHALL send invoice email to Customer
6. WHEN auto_send_email is disabled and a payment is verified, THE Email_Service SHALL NOT send invoice email to Customer
7. THE Merchant notification email SHALL be sent regardless of the auto_send_email setting
8. THE settings page SHALL display the current state of the auto_send_email toggle
9. WHEN the settings API endpoint receives an update request, THE system SHALL validate the request includes valid CSRF token
10. THE Settings_Manager SHALL log all changes to the auto_send_email setting with timestamp and merchant ID

### Requirement 5: Merchant BCC on Customer Invoices

**User Story:** As a merchant, I want to receive a BCC copy when customer invoices are sent, so that I have confirmation of what was delivered to customers.

#### Acceptance Criteria

1. WHEN the Email_Service sends an invoice email to a Customer, THE Email_Service SHALL include the Merchant email in the BCC field
2. THE BCC functionality SHALL only apply to customer invoice emails, not merchant notification emails
3. IF the Merchant email matches the Customer email, THEN THE Email_Service SHALL NOT add a BCC recipient
4. THE Email_Service SHALL use the existing send_invoice_email merchant_email parameter for BCC functionality
5. THE BCC implementation SHALL be transparent to the Customer (not visible in email headers)

### Requirement 6: Payment Confirmation Webhook Integration

**User Story:** As the system, I want to trigger email notifications when the payment webhook confirms a transaction, so that notifications are sent immediately upon payment verification.

#### Acceptance Criteria

1. WHEN the Payment_Confirmation_System receives a verified payment webhook, THE system SHALL check if an Invoice exists for the Transaction
2. IF no Invoice exists, THEN THE Invoice_Generator SHALL create an Invoice using the merchant's InvoiceSettings
3. WHEN auto_send_email is enabled in InvoiceSettings, THE Email_Service SHALL send the customer invoice email
4. THE Payment_Confirmation_System SHALL send the merchant notification email regardless of auto_send_email setting
5. THE system SHALL generate the Invoice PDF before sending any emails
6. IF PDF generation fails, THEN THE system SHALL log the error and send merchant notification without attachment
7. THE webhook handler SHALL update the Invoice status to "paid" and set paid_at timestamp when payment is verified
8. THE webhook handler SHALL not fail the payment verification if email delivery fails
9. THE system SHALL log all email operations (success/failure) for audit purposes

### Requirement 7: Email Template Formatting

**User Story:** As a recipient, I want to receive well-formatted, professional emails, so that the communication is clear and trustworthy.

#### Acceptance Criteria

1. THE Email_Service SHALL send emails in both plain text and HTML formats (multipart/alternative)
2. THE HTML email template SHALL include merchant branding (business name, logo if configured)
3. THE merchant notification email SHALL include a summary table with: transaction reference, amount, currency, customer email, payment timestamp
4. THE customer invoice email SHALL include: invoice number, amount, description, payment terms, and payment link with QR code
5. THE email footer SHALL include "Powered by OnePay" branding
6. THE Email_Service SHALL use the existing email template structure from services/email.py
7. THE Email_Service SHALL escape all user-provided content to prevent HTML injection
8. THE email subject lines SHALL not exceed 255 characters

### Requirement 8: Error Handling and Resilience

**User Story:** As the system, I want to handle email delivery failures gracefully, so that payment processing is not blocked by email issues.

#### Acceptance Criteria

1. WHEN email delivery fails, THE Email_Service SHALL log the error with full details (recipient, error message, timestamp)
2. THE Email_Service SHALL implement retry logic with exponential backoff: 1 minute, 5 minutes, 15 minutes
3. IF all retry attempts fail, THEN THE Email_Service SHALL log final failure and continue without blocking payment confirmation
4. THE Invoice model SHALL track email delivery attempts in email_attempts field
5. THE Invoice model SHALL store the last error message in email_last_error field
6. WHEN PDF generation times out, THE Email_Service SHALL log timeout error and send email without attachment
7. THE system SHALL validate email addresses before attempting delivery to prevent invalid recipient errors
8. IF SMTP configuration is missing (dev mode), THEN THE Email_Service SHALL log email details to console instead of sending

### Requirement 9: Invoice and Email Audit Trail

**User Story:** As a merchant, I want to see the email delivery status for each invoice, so that I can verify customers received their invoices.

#### Acceptance Criteria

1. THE Invoice model SHALL record email_sent boolean flag indicating successful delivery
2. THE Invoice model SHALL record email_sent_at timestamp when email is successfully delivered
3. THE Invoice model SHALL record email_attempts counter tracking total delivery attempts
4. THE Invoice model SHALL record email_last_error text field storing the most recent error message
5. THE invoice detail API endpoint SHALL include email delivery status in the response
6. THE audit log SHALL record all invoice email events with: event type, invoice number, recipient, timestamp, success/failure
7. THE merchant SHALL be able to view email delivery status on the invoices list page
8. THE system SHALL display email delivery errors on the invoice detail page for troubleshooting

### Requirement 10: Round-Trip Invoice Serialization

**User Story:** As a developer, I want to ensure invoice data integrity through serialization, so that invoice PDFs accurately represent the stored data.

#### Acceptance Criteria

1. WHEN an Invoice is created, THE Invoice_Generator SHALL serialize all invoice data to the database
2. WHEN generating an Invoice PDF, THE Invoice_Generator SHALL deserialize data from the database
3. FOR ALL Invoice objects, serializing to database then deserializing for PDF generation SHALL produce equivalent invoice content
4. THE Invoice model SHALL store denormalized merchant branding data (business_name, business_address, business_tax_id, business_logo_url, payment_terms) to preserve historical accuracy
5. THE Invoice_Generator SHALL use the stored denormalized data when generating PDFs, not current merchant settings
6. THE round-trip property SHALL be verified through property-based testing
7. IF merchant settings change after invoice creation, THE Invoice PDF SHALL reflect the settings at creation time, not current settings


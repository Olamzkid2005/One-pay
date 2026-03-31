# Implementation Plan: Invoice Generation

## Overview

Implement a professional invoice generation system that automatically creates PDF invoices for OnePay payment links. The system includes database models for invoices and settings, a service layer for PDF generation and email delivery, REST API endpoints, HTML templates, and integration with existing transaction workflows.

**Current Status:** ⚠️ PARTIAL - Core models, service, and some endpoints done. Tasks 1-7 partially complete, testing and remaining endpoints pending.

## Tasks

- [ ] 1. Create database models and migration
  - [x] 1.1 Create Invoice and InvoiceSettings models in models/invoice.py
    - Define Invoice model with all fields (invoice_number, transaction_id, user_id, amount, currency, description, customer details, merchant branding, status, timestamps, email tracking)
    - Define InvoiceStatus enum (draft, sent, paid, expired, cancelled)
    - Define InvoiceSettings model with merchant customization fields
    - Add composite indexes for query optimization
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 11.1, 12.1_

  - [x]* 1.2 Write property test for Invoice model data completeness
    - **Property 3: Invoice Data Completeness**
    - **Validates: Requirements 1.3, 1.4**

  - [x] 1.3 Create Alembic migration for invoice tables
    - Create migration file: alembic/versions/YYYYMMDDHHMMSS_add_invoice_tables.py
    - Add invoices table with all columns and indexes
    - Add invoice_settings table
    - Add foreign key constraints (CASCADE for transaction, SET NULL for user)
    - Add unique constraint on invoice_number
    - _Requirements: 1.1, 2.1, 2.4_

  - [ ]* 1.4 Write unit tests for Invoice model
    - Test field validation and constraints
    - Test status enum values
    - Test timezone-aware timestamps
    - _Requirements: 1.3, 12.1_

- [ ] 2. Implement invoice service layer
  - [x] 2.1 Create InvoiceService class in services/invoice.py
    - Implement generate_invoice_number() with sequential numbering and retry logic
    - Implement create_invoice() to create invoice from transaction with merchant settings
    - Implement get_invoice_by_number() with ownership verification
    - Implement get_invoice_history() with pagination and filtering
    - Implement sync_invoice_status() for transaction status synchronization
    - _Requirements: 1.1, 2.1, 2.2, 2.4, 2.5, 5.2, 5.3, 6.1, 6.2, 7.2_

  - [ ]* 2.2 Write property test for sequential invoice numbering
    - **Property 2: Sequential Invoice Numbering**
    - **Validates: Requirements 1.2, 2.1, 2.2**

  - [ ]* 2.3 Write property test for concurrent invoice number uniqueness
    - **Property 5: Concurrent Invoice Number Uniqueness**
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 2.4 Write unit tests for InvoiceService
    - Test invoice number generation format and uniqueness
    - Test invoice creation with and without settings
    - Test ownership verification
    - Test pagination and filtering logic
    - _Requirements: 2.1, 2.2, 6.1, 6.2, 7.2_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [-] 4. Implement PDF generation
  - [x] 4.1 Create invoice HTML template in templates/invoice.html
    - Design professional invoice layout with header, body, footer
    - Include OnePay branding and merchant logo placeholder
    - Add invoice metadata section (number, date, status)
    - Add merchant and customer details sections
    - Add itemized charges table
    - Add payment information with QR code placeholder
    - Add print-friendly CSS with A4 page size
    - Add status color coding (draft: gray, sent: blue, paid: green, expired: orange, cancelled: red)
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4_

  - [x] 4.2 Implement PDF generation functions in services/invoice.py
    - Implement render_invoice_html() using Jinja2 template
    - Implement generate_invoice_pdf() using WeasyPrint
    - Add logo embedding as base64 data URI
    - Add QR code embedding from transaction
    - Add timeout handling (10 seconds)
    - Add error handling for PDF generation failures
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 4.5, 5.4, 5.5_

  - [ ]* 4.3 Write property test for PDF generation completeness
    - **Property 6: PDF Generation Completeness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 5.4, 5.5**

  - [ ]* 4.4 Write unit tests for PDF generation
    - Test HTML rendering with template
    - Test PDF generation with WeasyPrint
    - Test logo embedding
    - Test QR code inclusion
    - Test timeout handling
    - _Requirements: 3.1, 3.2, 4.5_

- [ ] 5. Implement email delivery
  - [x] 5.1 Extend email service in services/email.py
    - Add send_invoice_email() function
    - Create plain text email template with invoice details and payment link
    - Create HTML email template with invoice summary and QR code
    - Add PDF attachment handling
    - Add retry logic with exponential backoff (max 3 attempts)
    - Update invoice email tracking fields (email_sent, email_sent_at, email_attempts, email_last_error)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 5.2 Write property test for automatic email delivery
    - **Property 22: Automatic Email Delivery**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

  - [ ]* 5.3 Write unit tests for email delivery
    - Test email content generation
    - Test PDF attachment
    - Test retry logic
    - Test email tracking updates
    - Test failure handling
    - _Requirements: 10.1, 10.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement API endpoints
  - [x] 7.1 Create invoices blueprint in blueprints/invoices.py
    - Create Flask blueprint for invoice routes
    - Add authentication decorator to all routes
    - Add rate limiting to endpoints (creation: 20/min, download: 50/min, email: 10/min, settings: 10/min)
    - _Requirements: 7.1, 7.4_

  - [x] 7.2 Implement POST /api/invoices/create endpoint
    - Validate transaction_reference parameter
    - Verify transaction ownership
    - Check if invoice already exists (idempotency)
    - Create invoice using InvoiceService
    - Optionally send email if auto_send_email enabled
    - Return invoice details with download URL
    - Add audit logging
    - _Requirements: 1.1, 7.2, 7.3, 7.5, 8.1_

  - [ ]* 7.3 Write property test for authentication requirement
    - **Property 13: Authentication Required**
    - **Validates: Requirements 7.1**

  - [ ]* 7.4 Write property test for authorization enforcement
    - **Property 14: Authorization Enforcement**
    - **Validates: Requirements 7.2, 7.3**

  - [x] 7.5 Implement GET /api/invoices endpoint
    - Parse pagination parameters (page, page_size, status, sort)
    - Validate page_size (max 100)
    - Query invoices with filtering and sorting
    - Return paginated results with metadata
    - Add audit logging
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.5_

  - [ ]* 7.6 Write property test for invoice history pagination
    - **Property 10: Invoice History Pagination**
    - **Validates: Requirements 6.1, 6.2, 6.5**

  - [x] 7.7 Implement GET /api/invoices/<invoice_number> endpoint
    - Validate invoice_number format
    - Fetch invoice with ownership verification
    - Return detailed invoice information
    - Add audit logging (invoice.viewed)
    - _Requirements: 7.2, 7.3, 7.5_

  - [x] 7.8 Implement GET /api/invoices/<invoice_number>/download endpoint
    - Fetch invoice with ownership verification
    - Generate PDF using InvoiceService
    - Set appropriate headers (Content-Type, Content-Disposition)
    - Stream PDF binary data
    - Add audit logging (invoice.downloaded)
    - Handle PDF generation errors
    - _Requirements: 3.1, 3.4, 7.2, 7.3, 7.5_

  - [x] 7.9 Implement POST /api/invoices/<invoice_number>/send endpoint
    - Fetch invoice with ownership verification
    - Parse optional recipient_email parameter
    - Generate PDF
    - Send email using InvoiceService
    - Update invoice status to sent if successful
    - Return delivery confirmation
    - Add audit logging (invoice.emailed)
    - _Requirements: 10.1, 10.5, 7.2, 7.3, 7.5_

  - [x] 7.10 Implement GET /api/invoices/settings endpoint
    - Fetch or create default InvoiceSettings for current user
    - Return settings as JSON
    - _Requirements: 11.1_

  - [x] 7.11 Implement POST /api/invoices/settings endpoint
    - Parse and validate settings fields
    - Sanitize text inputs
    - Validate logo URL format and accessibility
    - Update or create InvoiceSettings record
    - Return updated settings
    - Add audit logging (invoice.settings_updated)
    - _Requirements: 11.1, 11.2, 11.3, 11.5, 8.4_

  - [ ]* 7.12 Write property test for input validation
    - **Property 17: Input Validation**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

  - [ ]* 7.13 Write unit tests for API endpoints
    - Test all success cases
    - Test error cases (401, 403, 404, 409, 429, 500)
    - Test validation errors
    - Test rate limiting
    - Test audit logging
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.5_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Integrate with payment link creation
  - [x] 9.1 Extend POST /api/payments/create in blueprints/payments.py
    - After transaction creation, check if user has invoice settings
    - If settings exist, automatically create invoice
    - If auto_send_email enabled and customer_email provided, generate and send invoice
    - Include invoice_number in response
    - Handle invoice creation errors gracefully (log but don't fail payment link creation)
    - _Requirements: 1.1, 10.1, 10.2_

  - [ ]* 9.2 Write property test for invoice creation on payment link
    - **Property 1: Invoice Creation for Payment Links**
    - **Validates: Requirements 1.1, 5.1**

  - [ ]* 9.3 Write integration tests for payment link + invoice flow
    - Test invoice auto-creation when settings exist
    - Test no invoice creation when settings don't exist
    - Test auto-email when enabled
    - Test graceful failure handling
    - _Requirements: 1.1, 10.1_

- [ ] 10. Implement transaction status synchronization
  - [x] 10.1 Add sync_invoice_on_transaction_update() in services/webhook.py
    - Query invoice by transaction_id
    - Update invoice status based on transaction status (verified → paid, expired → expired)
    - Update paid_at timestamp when status changes to paid
    - Add audit logging (invoice.status_synced)
    - _Requirements: 5.2, 5.3, 12.4, 12.5_

  - [x] 10.2 Integrate sync function into existing webhook handler
    - Call sync_invoice_on_transaction_update() after transaction status update
    - Handle case where no invoice exists for transaction
    - _Requirements: 5.2, 5.3_

  - [ ]* 10.3 Write property test for transaction status synchronization
    - **Property 9: Transaction Status Synchronization**
    - **Validates: Requirements 5.2, 5.3, 12.4, 12.5**

  - [ ]* 10.4 Write unit tests for status synchronization
    - Test verified → paid transition
    - Test expired → expired transition
    - Test no change for failed transactions
    - Test no-op when invoice doesn't exist
    - _Requirements: 5.2, 5.3, 12.4, 12.5_

- [x] 11. Create dashboard UI integration
  - [x] 11.1 Create invoices.html template
    - Create invoice list page with table layout
    - Add status badges with color coding
    - Add filter dropdowns (status)
    - Add search input (invoice number, customer email)
    - Add download and resend buttons for each invoice
    - Add pagination controls
    - Use existing dashboard_base.html layout
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 11.2 Add /invoices route in blueprints/payments.py
    - Render invoices.html template
    - Pass invoice data from API endpoint
    - Add authentication requirement
    - _Requirements: 6.1_

  - [x] 11.3 Add "Invoices" navigation link in templates/dashboard_base.html
    - Add link to /invoices route in navigation menu
    - _Requirements: 6.1_

  - [x] 11.4 Add JavaScript for invoice list interactions in static/js/dashboard.js
    - Add AJAX handlers for download button
    - Add AJAX handlers for resend button
    - Add filter and search functionality
    - Add pagination navigation
    - Add status update notifications
    - _Requirements: 6.1, 6.2, 6.4_

- [x] 12. Create settings UI integration
  - [x] 12.1 Extend settings.html template
    - Add "Invoice Settings" section
    - Add form fields (business_name, business_address, business_tax_id, business_logo_url, default_payment_terms, auto_send_email)
    - Add logo preview functionality
    - Add client-side validation
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 12.2 Extend /settings route in blueprints/payments.py
    - Load invoice settings for current user
    - Pass settings to template
    - _Requirements: 11.1_

  - [x] 12.3 Add JavaScript for settings form in static/js/dashboard.js
    - Add AJAX handler for settings form submission
    - Add logo preview on URL input
    - Add client-side validation
    - Add success/error notifications
    - _Requirements: 11.1, 11.5_

- [x] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Add comprehensive property-based tests
  - [ ]* 14.1 Write property test for optional field inclusion
    - **Property 4: Optional Field Inclusion**
    - **Validates: Requirements 1.5**

  - [ ]* 14.2 Write property test for HTML template validity
    - **Property 7: HTML Template Validity**
    - **Validates: Requirements 4.1, 4.2, 4.4**

  - [ ]* 14.3 Write property test for logo embedding
    - **Property 8: Logo Embedding**
    - **Validates: Requirements 4.5**

  - [ ]* 14.4 Write property test for invoice history metadata
    - **Property 11: Invoice History Metadata**
    - **Validates: Requirements 6.3**

  - [ ]* 14.5 Write property test for status filtering
    - **Property 12: Status Filtering**
    - **Validates: Requirements 6.4**

  - [ ]* 14.6 Write property test for rate limiting
    - **Property 15: Rate Limiting**
    - **Validates: Requirements 7.4**

  - [ ]* 14.7 Write property test for audit logging
    - **Property 16: Audit Logging**
    - **Validates: Requirements 7.5**

  - [ ]* 14.8 Write property test for validation error messages
    - **Property 18: Validation Error Messages**
    - **Validates: Requirements 8.5**

  - [ ]* 14.9 Write property test for invoice serialization round-trip
    - **Property 19: Invoice Serialization Round-Trip**
    - **Validates: Requirements 9.5**

  - [ ]* 14.10 Write property test for JSON parsing validation
    - **Property 20: JSON Parsing Validation**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]* 14.11 Write property test for JSON serialization
    - **Property 21: JSON Serialization**
    - **Validates: Requirements 9.4**

  - [ ]* 14.12 Write property test for email failure handling
    - **Property 23: Email Failure Handling**
    - **Validates: Requirements 10.5**

  - [ ]* 14.13 Write property test for invoice settings persistence
    - **Property 24: Invoice Settings Persistence**
    - **Validates: Requirements 11.1, 11.2, 11.3**

  - [ ]* 14.14 Write property test for settings temporal isolation
    - **Property 25: Settings Temporal Isolation**
    - **Validates: Requirements 11.4**

  - [ ]* 14.15 Write property test for logo URL validation
    - **Property 26: Logo URL Validation**
    - **Validates: Requirements 11.5**

  - [ ]* 14.16 Write property test for invoice status lifecycle
    - **Property 27: Invoice Status Lifecycle**
    - **Validates: Requirements 12.1, 12.2**

  - [ ]* 14.17 Write property test for email delivery status update
    - **Property 28: Email Delivery Status Update**
    - **Validates: Requirements 12.3**

- [ ] 15. Add edge case and error handling tests
  - [ ]* 15.1 Write unit tests for edge cases
    - Test year boundary crossing (Dec 31 → Jan 1)
    - Test first invoice ever created
    - Test invoice with no customer email
    - Test invoice with no optional merchant details
    - Test very long descriptions
    - Test special characters in text fields
    - Test large amounts (decimal precision)
    - Test zero-amount rejection
    - _Requirements: 2.1, 8.1, 8.4_

  - [ ]* 15.2 Write unit tests for error conditions
    - Test duplicate invoice creation attempt
    - Test invalid transaction reference
    - Test unauthorized access attempt
    - Test rate limit exceeded
    - Test PDF generation timeout
    - Test email delivery failure
    - Test logo URL inaccessible
    - Test invalid image format
    - Test database constraint violation
    - Test concurrent invoice number collision
    - _Requirements: 2.5, 7.2, 7.3, 7.4, 10.5, 11.5_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based and unit tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation follows OnePay's existing patterns (Flask blueprints, SQLAlchemy ORM, existing services)
- All invoice endpoints require authentication and include audit logging
- PDF generation uses WeasyPrint (already in dependencies)
- Email delivery uses existing services/email.py
- Transaction status synchronization is event-driven via webhook integration

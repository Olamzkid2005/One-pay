# Implementation Plan: Automatic Payment Notification Emails

## Overview

This implementation adds automatic email notifications when payments are confirmed via webhook. The system sends merchant notification emails with transfer details and attached invoices, and optionally sends customer invoice emails based on the merchant's auto_send_email setting. The feature integrates with existing webhook handler, email service, and invoice generation systems.

**Current Status:** ⚠️ PARTIAL - Task 1 (merchant notification email) partially complete. Tasks 2-9 pending.

## Tasks

- [x] 1. Implement merchant notification email function
  - [x] 1.1 Write property test for merchant notification always sent
    - **Property 1: Merchant Notification Always Sent**
    - **Validates: Requirements 1.1, 1.6**
  
  - [x] 1.2 Write unit test for send_merchant_notification_email function
    - Test email sent with correct subject format "Payment Received - {tx_ref}"
    - Test email body contains transfer details (amount, currency, customer email, tx_ref, timestamp)
    - Test PDF attachment included when available
    - Test email sent without attachment when PDF generation fails
    - _Requirements: 1.2, 1.3, 1.4, 1.5_
  
  - [x] 1.3 Implement send_merchant_notification_email in services/email.py
    - Add function with signature: send_merchant_notification_email(to_email, transaction, invoice, pdf_bytes)
    - Build multipart email with plain text and HTML parts
    - Include transfer details table in email body
    - Attach PDF if available, gracefully handle None
    - Use existing retry logic pattern (3 attempts with exponential backoff)
    - Return boolean indicating success/failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7_
  
  - [ ]* 1.4 Write property test for email subject format
    - **Property 2: Merchant Email Subject Format**
    - **Validates: Requirements 1.2**
  
  - [ ]* 1.5 Write property test for transfer details inclusion
    - **Property 3: Merchant Email Contains Transfer Details**
    - **Validates: Requirements 1.3**

- [ ] 2. Implement webhook integration for email notifications
  - [ ] 2.1 Write unit test for send_payment_notification_emails function
    - Test invoice creation when not exists
    - Test merchant email sent always
    - Test customer email sent when auto_send_email enabled
    - Test customer email NOT sent when auto_send_email disabled
    - Test graceful degradation on PDF generation failure
    - Test email failures don't block payment confirmation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.8_
  
  - [ ] 2.2 Implement send_payment_notification_emails in services/webhook.py
    - Add function with signature: send_payment_notification_emails(db, transaction, user)
    - Check if invoice exists for transaction
    - Create invoice if not exists using invoice_service.create_invoice
    - Generate invoice PDF using invoice_service.generate_invoice_pdf
    - Send merchant notification email (always)
    - Check auto_send_email setting from InvoiceSettings
    - Send customer invoice email if auto_send_email enabled AND customer_email exists
    - Update invoice status to "paid" and set paid_at timestamp
    - Wrap all operations in try-except to prevent blocking payment
    - Log all operations for audit trail
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_
  
  - [ ] 2.3 Integrate send_payment_notification_emails into webhook handler
    - Locate existing webhook verification handler in services/webhook.py or blueprints/payments.py
    - Call send_payment_notification_emails after transaction status updated to VERIFIED
    - Ensure call is after sync_invoice_on_transaction_update
    - _Requirements: 6.1_
  
  - [ ]* 2.4 Write property test for invoice auto-creation
    - **Property 13: Invoice Auto-Creation Before Email**
    - **Validates: Requirements 2.7, 6.2**
  
  - [ ]* 2.5 Write property test for email failure non-blocking
    - **Property 28: Email Failure Does Not Block Payment**
    - **Validates: Requirements 6.8**

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Enhance customer invoice email with merchant BCC
  - [ ] 4.1 Write unit test for merchant BCC functionality
    - Test BCC included when merchant email differs from customer email
    - Test no BCC when merchant email equals customer email
    - Test BCC only on customer emails, not merchant notifications
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [ ] 4.2 Update send_invoice_email to use merchant_email parameter for BCC
    - Verify existing merchant_email parameter in send_invoice_email signature
    - Ensure BCC logic: add merchant to BCC only if merchant_email != to_email
    - _Requirements: 5.1, 5.3, 5.4_
  
  - [ ]* 4.3 Write property test for BCC functionality
    - **Property 22: Customer Email BCC to Merchant**
    - **Validates: Requirements 5.1**
  
  - [ ]* 4.4 Write property test for no BCC on merchant notifications
    - **Property 23: No BCC on Merchant Notifications**
    - **Validates: Requirements 5.2**

- [ ] 5. Implement email template formatting
  - [ ]* 5.1 Write unit test for multipart email format
    - Test emails contain both plain text and HTML parts
    - _Requirements: 7.1_
  
  - [ ]* 5.2 Write unit test for HTML email branding
    - Test HTML includes business_name
    - Test HTML includes business_logo_url if configured
    - _Requirements: 7.2_
  
  - [ ]* 5.3 Write unit test for HTML content escaping
    - Test user-provided content is HTML-escaped
    - Test description, business name, customer email escaped
    - _Requirements: 7.7_
  
  - [ ] 5.4 Verify email templates in send_merchant_notification_email
    - Ensure multipart/alternative format (plain text + HTML)
    - Include merchant branding in HTML template
    - Escape all user-provided content using html.escape()
    - Verify subject line truncated to 255 characters
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.7, 7.8_
  
  - [ ]* 5.5 Write property test for HTML content escaping
    - **Property 33: HTML Content Escaping**
    - **Validates: Requirements 7.7**

- [ ] 6. Implement error handling and resilience
  - [ ]* 6.1 Write unit test for retry logic with exponential backoff
    - Test 3 retry attempts with delays: 1min, 5min, 15min
    - Test email_attempts counter increments on each attempt
    - _Requirements: 1.7, 2.8, 8.2, 8.4_
  
  - [ ]* 6.2 Write unit test for email validation
    - Test invalid email format rejected before delivery
    - Test email header injection prevention (newline/carriage return)
    - _Requirements: 8.7_
  
  - [ ]* 6.3 Write unit test for error tracking
    - Test email_last_error updated on failure
    - Test error logged with full details
    - _Requirements: 8.1, 8.4, 8.5_
  
  - [ ] 6.4 Verify error handling in send_merchant_notification_email
    - Ensure retry logic with exponential backoff (1min, 5min, 15min)
    - Validate email format before sending
    - Log all errors with recipient, error message, timestamp
    - Handle SMTP timeouts gracefully
    - _Requirements: 8.1, 8.2, 8.3, 8.7_
  
  - [ ]* 6.5 Write property test for email attempts counter
    - **Property 35: Email Attempts Counter Increments**
    - **Validates: Requirements 8.4, 9.1, 9.3**
  
  - [ ]* 6.6 Write property test for last error message storage
    - **Property 36: Last Error Message Stored**
    - **Validates: Requirements 8.5, 9.4**

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement settings toggle verification
  - [ ]* 8.1 Write unit test for auto_send_email default value
    - Test new InvoiceSettings defaults to auto_send_email=False
    - _Requirements: 4.4_
  
  - [ ]* 8.2 Write unit test for settings persistence
    - Test auto_send_email value persists to database
    - Test round-trip: save then query returns same value
    - _Requirements: 4.3_
  
  - [ ]* 8.3 Write unit test for settings change audit logging
    - Test audit log entry created on auto_send_email change
    - Test log contains event type, merchant ID, timestamp, new value
    - _Requirements: 4.10_
  
  - [ ] 8.4 Verify auto_send_email toggle controls customer emails
    - Review existing settings API endpoint in blueprints/payments.py
    - Verify CSRF validation on settings update
    - Verify audit logging on settings change
    - _Requirements: 4.3, 4.9, 4.10_
  
  - [ ]* 8.5 Write property test for settings persistence round-trip
    - **Property 16: Settings Persistence Round-Trip**
    - **Validates: Requirements 4.3**
  
  - [ ]* 8.6 Write property test for auto-send toggle controls emails
    - **Property 18: Auto-Send Toggle Controls Customer Emails**
    - **Validates: Requirements 4.5, 4.6**
  
  - [ ]* 8.7 Write property test for merchant email independent of auto-send
    - **Property 19: Merchant Email Independent of Auto-Send**
    - **Validates: Requirements 4.7, 6.4**

- [ ] 9. Implement invoice status synchronization
  - [ ]* 9.1 Write unit test for invoice status update on payment
    - Test invoice status updated to "paid" when payment verified
    - Test paid_at timestamp set when payment verified
    - _Requirements: 6.7_
  
  - [ ] 9.2 Verify sync_invoice_on_transaction_update integration
    - Review existing sync_invoice_on_transaction_update function in services/webhook.py
    - Ensure it's called in webhook handler before send_payment_notification_emails
    - Verify invoice status updated to "paid" and paid_at timestamp set
    - _Requirements: 6.7_
  
  - [ ]* 9.3 Write property test for invoice status update
    - **Property 27: Invoice Status Updated to Paid**
    - **Validates: Requirements 6.7**

- [ ] 10. Implement email delivery audit trail
  - [ ]* 10.1 Write unit test for email delivery status tracking
    - Test email_sent flag set to True on success
    - Test email_sent_at timestamp recorded on success
    - Test email_attempts counter incremented
    - Test email_last_error cleared on success
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ]* 10.2 Write unit test for invoice API includes email status
    - Test invoice detail API response includes email_sent, email_sent_at, email_attempts, email_last_error
    - _Requirements: 9.5_
  
  - [ ]* 10.3 Write unit test for audit log for email events
    - Test audit log entry created for email sent event
    - Test audit log entry created for email failed event
    - Test log contains event type, invoice number, recipient, timestamp, status
    - _Requirements: 9.6_
  
  - [ ] 10.4 Verify email tracking fields updated in send_invoice_email
    - Review existing send_invoice_email function in services/email.py
    - Verify email_sent, email_sent_at, email_attempts, email_last_error updated
    - Verify audit logging for email events
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6_
  
  - [ ]* 10.5 Write property test for invoice status updated on successful email
    - **Property 14: Invoice Status Updated on Successful Email**
    - **Validates: Requirements 2.9, 9.2**

- [ ] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Write integration tests
  - [ ]* 12.1 Write integration test for end-to-end payment flow
    - Test: webhook → invoice creation → merchant email → customer email
    - Verify both emails sent with correct content
    - Verify invoice status updated
    - Verify email tracking fields updated
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7_
  
  - [ ]* 12.2 Write integration test for email retry flow
    - Test: SMTP failure → retry attempts → final success/failure
    - Verify retry delays and attempt counter
    - _Requirements: 1.7, 2.8, 8.2_
  
  - [ ]* 12.3 Write integration test for PDF generation failure
    - Test: webhook → PDF fails → email sent without attachment
    - Verify merchant receives notification without PDF
    - Verify error logged
    - _Requirements: 1.5, 6.6_
  
  - [ ]* 12.4 Write integration test for auto-send disabled
    - Test: webhook → auto_send_email=False → merchant email only
    - Verify customer does NOT receive email
    - Verify merchant receives notification
    - _Requirements: 4.6, 4.7_
  
  - [ ]* 12.5 Write integration test for missing customer email
    - Test: webhook → no customer_email → merchant email only
    - Verify customer email skipped gracefully
    - _Requirements: 2.2_

- [ ] 13. Final verification and manual testing
  - [ ] 13.1 Run all unit tests and verify 100% pass
    - Run: pytest tests/test_email_notifications.py -v
    - Expected: All tests pass
  
  - [ ] 13.2 Run all property-based tests and verify pass
    - Run: pytest tests/test_email_notifications_properties.py -v
    - Expected: All property tests pass with 100+ iterations
  
  - [ ] 13.3 Run all integration tests and verify pass
    - Run: pytest tests/test_webhook_email_integration.py -v
    - Expected: All integration tests pass
  
  - [ ] 13.4 Perform manual testing with real SMTP
    - Configure SMTP settings in .env
    - Test merchant notification email delivery
    - Test customer invoice email delivery (auto-send enabled)
    - Test customer email NOT sent (auto-send disabled)
    - Test settings toggle persistence
    - Verify email content matches requirements
    - Verify PDF attachments included
    - Verify email tracking in database
  
  - [ ] 13.5 Review audit logs and error handling
    - Verify all email events logged
    - Verify error messages clear and actionable
    - Verify no sensitive data in logs

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from design document
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Manual testing verifies real-world email delivery
- All email operations use existing retry logic and error handling patterns
- Email failures never block payment confirmation (graceful degradation)
- Merchant notification always sent regardless of auto_send_email setting
- Customer invoice email respects auto_send_email toggle

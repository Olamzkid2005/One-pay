# Implementation Plan: Payment Methods and QR Codes

## Overview

This implementation adds QR code generation and multiple payment methods (bank transfer and card payments) to the OnePay payment verification platform. The implementation extends the existing architecture while maintaining backward compatibility with existing payment links.

## Tasks

- [ ] 1. Database schema and migration
  - Create Alembic migration to add new columns to transactions table
  - Add columns: allowed_payment_methods (JSON), selected_payment_method (String), processing_fee (Numeric), total_amount (Numeric), card_last_four (String), card_brand (String)
  - Set default values for existing records: allowed_payment_methods=['bank_transfer'], selected_payment_method='bank_transfer', processing_fee=0, total_amount=amount
  - Add index on selected_payment_method column
  - Test migration upgrade and downgrade
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 2. Update Transaction model
  - Add new columns to Transaction model in models/transaction.py
  - Update to_dict() method to include payment method fields
  - Handle NULL allowed_payment_methods as ['bank_transfer'] for backward compatibility
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 11.1, 11.3_

- [ ] 3. Implement fee calculation service
  - [ ] 3.1 Create services/fees.py with fee calculation functions
    - Implement calculate_processing_fee(amount, payment_method) returning Decimal
    - Use CARD_PAYMENT_FEE_RATE = Decimal("0.015") for 1.5% fee
    - Round to 2 decimal places using ROUND_HALF_UP
    - Return Decimal("0") for bank_transfer
    - Implement calculate_total_amount(amount, payment_method)
    - _Requirements: 5.1, 5.6, 5.7_
  
  - [ ]* 3.2 Write property test for fee calculation
    - **Property 13: Card Processing Fee Calculation**
    - **Validates: Requirements 5.1, 5.7**
    - Test that card_payment fee is exactly 1.5% of amount, rounded to 2 decimal places using ROUND_HALF_UP
    - Test that bank_transfer fee is 0
    - Use Hypothesis with decimal amounts from 1 to 1,000,000

- [ ] 4. Implement QR code generation service
  - [ ] 4.1 Create services/qr_code.py with QR code functions
    - Install qrcode library (version 7.4.2+) in requirements.txt
    - Implement get_qr_data(transaction, base_url) to build QR data dict
    - Include fields: tx_ref, amount, currency, description, merchant_name, payment_url, expires_at, allowed_payment_methods
    - Include virtual account fields if bank_transfer is allowed
    - Implement size optimization: truncate/omit optional fields if data > 1000 chars
    - Implement generate_qr_code(transaction, base_url) returning base64 data URL
    - Configure QR code: error_correction=M, box_size=10, border=4
    - Return PNG as base64-encoded data URL
    - Implement in-memory caching keyed by tx_ref
    - _Requirements: 1.2, 1.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ]* 4.2 Write property test for QR code round-trip
    - **Property 1: QR Code Round-Trip Preservation**
    - **Validates: Requirements 1.3, 15.3, 15.4, 15.5, 15.6**
    - Test that encoding then decoding QR code produces equivalent payment data
    - Verify tx_ref, amount, currency, payment_url match original
  
  - [ ]* 4.3 Write property test for QR code required fields
    - **Property 2: QR Code Contains Required Fields**
    - **Validates: Requirements 1.2, 9.2, 9.4**
    - Test that QR code data includes all required fields
  
  - [ ]* 4.4 Write unit tests for QR code generation
    - Test QR code generation for valid transaction
    - Test QR code caching behavior
    - Test size optimization when data exceeds capacity
    - Test error handling when generation fails
    - _Requirements: 12.6_

- [ ] 5. Extend Quickteller service for card payments
  - [ ] 5.1 Add card payment configuration to config.py
    - Add QUICKTELLER_CARD_MERCHANT_ID environment variable
    - Add QUICKTELLER_CARD_API_KEY environment variable
    - Add QUICKTELLER_CARD_TERMINAL_ID environment variable
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [ ] 5.2 Extend QuicktellerService in services/quickteller.py
    - Implement is_card_configured() method checking if credentials are set
    - Implement process_card_payment() method for Quickteller Card Payment API
    - Accept parameters: transaction_reference, amount_kobo, card_number, expiry_month, expiry_year, cvv, cardholder_name
    - Return dict with responseCode, responseMessage, transactionReference, cardBrand, last4
    - Transmit card details over HTTPS to Quickteller API
    - Extract card brand and last 4 digits from response
    - _Requirements: 4.1, 4.2, 4.6, 8.1_
  
  - [ ] 5.3 Implement mock mode for card payments
    - Implement _mock_process_card_payment() method
    - Return success (responseCode "00") for card numbers ending in even digits
    - Return failure (responseCode "06") for card numbers ending in odd digits
    - Log clearly when mock mode is active
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_
  
  - [ ]* 5.4 Write property test for mock mode card handling
    - **Property 26: Mock Mode Card Number Handling**
    - **Validates: Requirements 10.2, 10.3, 10.4**
    - Test that even-ending cards return success, odd-ending cards return failure in mock mode

- [ ] 6. Implement card validation utilities
  - [ ] 6.1 Create core/card_validation.py with validation functions
    - Implement validate_luhn(card_number) for Luhn algorithm check
    - Implement validate_expiry_date(month, year) for future date check
    - Implement validate_cvv(cvv) for 3-4 digit format check
    - Implement validate_cardholder_name(name) for presence check
    - _Requirements: 4.3, 4.4, 4.5_
  
  - [ ]* 6.2 Write property test for Luhn validation
    - **Property 7: Card Number Luhn Validation**
    - **Validates: Requirements 4.3**
    - Test that valid Luhn card numbers are accepted, invalid are rejected
  
  - [ ]* 6.3 Write property test for expiry date validation
    - **Property 8: Expiry Date Future Validation**
    - **Validates: Requirements 4.4**
    - Test that future dates are accepted, past/present dates are rejected
  
  - [ ]* 6.4 Write property test for CVV validation
    - **Property 9: CVV Format Validation**
    - **Validates: Requirements 4.5**
    - Test that 3-4 digit CVVs are accepted, other formats are rejected

- [ ] 7. Extend payment link creation API
  - [ ] 7.1 Modify POST /api/payments/link endpoint in blueprints/payments.py
    - Accept optional allowed_payment_methods array in request body
    - Default to ["bank_transfer"] if not provided
    - Validate payment methods are in {"bank_transfer", "card_payment"}
    - Return error INVALID_PAYMENT_METHOD if invalid method provided
    - Return error VALIDATION_ERROR if empty array
    - Store allowed_payment_methods in transaction
    - Include allowed_payment_methods in response
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [ ]* 7.2 Write property test for payment method validation
    - **Property 4: Payment Method Array Validation**
    - **Validates: Requirements 2.1, 2.2, 2.6**
    - Test that only valid payment methods are accepted
  
  - [ ]* 7.3 Write property test for payment method storage
    - **Property 5: Payment Method Storage Round-Trip**
    - **Validates: Requirements 2.5, 7.1**
    - Test that stored payment methods match those specified during creation
  
  - [ ]* 7.4 Write unit tests for link creation
    - Test link creation with single payment method
    - Test link creation with multiple payment methods
    - Test link creation with no payment methods (defaults to bank_transfer)
    - Test link creation with invalid payment method
    - Test backward compatibility (existing integrations work)

- [ ] 8. Implement payment method selection API
  - [ ] 8.1 Create POST /api/payments/select-method/<tx_ref> endpoint
    - Accept payment_method in request body
    - Validate tx_ref is valid and not expired
    - Validate payment_method is in transaction.allowed_payment_methods
    - Return error METHOD_NOT_ALLOWED if method not allowed
    - Update transaction.selected_payment_method
    - Calculate and store processing_fee and total_amount using fee service
    - Return original_amount, processing_fee, total_amount, currency
    - _Requirements: 2.4, 5.1, 5.4, 5.5_
  
  - [ ]* 8.2 Write unit tests for method selection
    - Test selecting valid payment method
    - Test selecting invalid payment method
    - Test selecting method not in allowed list
    - Test fee calculation for card payment
    - Test zero fee for bank transfer
    - Test expired transaction rejection

- [ ] 9. Implement card payment processing API
  - [ ] 9.1 Create POST /api/payments/card-payment/<tx_ref> endpoint
    - Accept card_number, expiry_month, expiry_year, cvv, cardholder_name in request body
    - Require CSRF token validation
    - Implement rate limiting: 5 attempts per 15 minutes per IP using services/rate_limiter.py
    - Validate tx_ref is valid and not expired
    - Validate card_payment is in allowed_payment_methods
    - Validate card details using card_validation functions
    - Return inline validation errors if validation fails
    - Call quickteller.process_card_payment() with card details
    - Update transaction status to "verified" if responseCode is "00"
    - Update transaction status to "failed" if responseCode is not "00"
    - Store card_last_four and card_brand in transaction (never store full card number or CVV)
    - Create audit log entry with transaction reference and outcome (no card details)
    - Return success response or generic error message (don't expose detailed errors)
    - Never log card numbers, CVV, or expiry dates
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 7.3, 7.4, 8.2, 8.3, 8.5, 8.6, 8.7, 8.8_
  
  - [ ]* 9.2 Write property test for successful card payment
    - **Property 10: Successful Card Payment Updates Status**
    - **Validates: Requirements 4.7, 7.3**
    - Test that responseCode "00" updates status to "verified"
  
  - [ ]* 9.3 Write property test for failed card payment
    - **Property 11: Failed Card Payment Updates Status**
    - **Validates: Requirements 4.8, 7.4**
    - Test that non-"00" responseCode updates status to "failed"
  
  - [ ]* 9.4 Write property test for card data not stored
    - **Property 12: Card Data Not Stored**
    - **Validates: Requirements 4.9, 4.10, 8.3**
    - Test that database contains only last 4 digits and card brand, not full card number or CVV
  
  - [ ]* 9.5 Write property test for card data not logged
    - **Property 17: Card Data Not Logged**
    - **Validates: Requirements 8.2**
    - Test that logs don't contain card numbers, CVV, or expiry dates
  
  - [ ]* 9.6 Write property test for rate limiting
    - **Property 18: Card Payment Rate Limiting**
    - **Validates: Requirements 8.5**
    - Test that 6th attempt within 15 minutes is rejected
  
  - [ ]* 9.7 Write property test for audit logging
    - **Property 19: Card Payment Audit Logging**
    - **Validates: Requirements 8.6**
    - Test that audit log contains transaction reference and outcome, not card details
  
  - [ ]* 9.8 Write property test for error messages
    - **Property 20: Card Payment Error Messages**
    - **Validates: Requirements 8.7**
    - Test that error messages don't expose detailed information
  
  - [ ]* 9.9 Write property test for CSRF protection
    - **Property 21: CSRF Protection on Card Payments**
    - **Validates: Requirements 8.8**
    - Test that requests without valid CSRF token are rejected

- [ ] 10. Implement QR code API endpoint
  - [ ] 10.1 Create GET /api/payments/qr-code/<tx_ref> endpoint
    - Validate tx_ref is valid
    - Return 404 if transaction is expired or verified
    - Generate QR code using qr_code service
    - Return cached QR code if available
    - Implement rate limiting: 20 requests per minute per IP
    - Return PNG image with content-type image/png
    - Handle QR generation errors gracefully (log error, return 500)
    - _Requirements: 1.1, 1.5, 1.6, 1.7, 12.5, 12.6_
  
  - [ ]* 10.2 Write property test for QR code visibility
    - **Property 3: QR Code Visibility Based on Transaction State**
    - **Validates: Requirements 1.5, 1.6, 1.7**
    - Test that QR codes are displayed only for pending transactions
  
  - [ ]* 10.3 Write property test for QR code JSON format
    - **Property 22: QR Code JSON Format**
    - **Validates: Requirements 9.1**
    - Test that QR code data is valid JSON
  
  - [ ]* 10.4 Write property test for QR code bank fields
    - **Property 23: QR Code Conditional Bank Fields**
    - **Validates: Requirements 9.3**
    - Test that QR code includes virtual account fields when bank_transfer is allowed
  
  - [ ]* 10.5 Write property test for QR code size optimization
    - **Property 24: QR Code Size Optimization**
    - **Validates: Requirements 9.5, 9.6**
    - Test that optional fields are omitted when data exceeds capacity
  
  - [ ]* 10.6 Write property test for QR code image format
    - **Property 25: QR Code Image Format**
    - **Validates: Requirements 9.7**
    - Test that QR code is PNG with dimensions >= 200x200 pixels

- [ ] 11. Extend payment preview API
  - [ ] 11.1 Modify GET /api/payments/preview/<tx_ref> endpoint
    - Include allowed_payment_methods in response
    - Include processing_fee in response if card_payment selected
    - Include total_amount in response if card_payment selected
    - Handle NULL allowed_payment_methods as ['bank_transfer'] for backward compatibility
    - _Requirements: 2.1, 5.2, 5.3, 11.1, 11.2_
  
  - [ ]* 11.2 Write unit tests for preview API
    - Test preview with single payment method
    - Test preview with multiple payment methods
    - Test preview with legacy transaction (NULL payment methods)
    - Test preview includes fee breakdown for card payments

- [ ] 12. Update payment page template
  - [ ] 12.1 Modify templates/verify.html for payment method display
    - Add QR code section with base64 image display
    - Add payment method selector for multiple methods (tabs UI)
    - Add fee information badges ("No fees" for bank_transfer, "1.5% fee" for card_payment)
    - Add card payment form with fields: card_number, expiry, cvv, cardholder_name
    - Add fee breakdown display showing original amount, processing fee, total
    - Add mock mode banner when in mock mode
    - Show single payment method directly if only one allowed
    - Hide QR code for expired or verified transactions
    - _Requirements: 1.1, 1.5, 1.6, 1.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.5, 14.1, 14.2, 14.3, 14.4, 14.6_
  
  - [ ]* 12.2 Write property test for payment method UI display
    - **Property 6: Payment Method UI Display**
    - **Validates: Requirements 3.1, 3.4**
    - Test that payment page displays UI for all allowed payment methods

- [ ] 13. Update payment page JavaScript
  - [ ] 13.1 Extend static/js/verify.js for payment method selection
    - Implement showPaymentMethodSelector() to create tabs for multiple methods
    - Implement selectPaymentMethod() to call /api/payments/select-method
    - Implement updateFeeBreakdown() to display fee calculation
    - Implement showPaymentForm() to switch between bank transfer and card payment
    - Implement card number formatting (spaces every 4 digits)
    - Implement expiry date formatting (MM/YY)
    - Implement client-side card validation before submission
    - Implement submitCardPayment() to call /api/payments/card-payment
    - Implement error display for validation and payment failures
    - Update polling to handle card payment status
    - _Requirements: 3.4, 3.5, 3.6, 4.3, 4.4, 4.5, 5.2, 14.5_
  
  - [ ]* 13.2 Write property test for dynamic total update
    - **Property 33: Dynamic Total Amount Update**
    - **Validates: Requirements 14.5**
    - Test that displayed total updates when payment method changes

- [ ] 14. Update dashboard for payment method display
  - [ ] 14.1 Modify templates/history.html to show payment method
    - Add "Payment Method" column to transaction table
    - Display "Bank Transfer" or "Card Payment" with icon
    - Show card brand and last 4 digits for card payments
    - Add filter for payment method
    - _Requirements: 7.5_
  
  - [ ] 14.2 Extend CSV export in blueprints/payments.py
    - Add "Payment Method" column
    - Add "Card Brand" column
    - Add "Card Last 4" column
    - Add "Processing Fee" column
    - Add "Total Amount" column
    - _Requirements: 7.6_
  
  - [ ]* 14.3 Write property test for payment method in exports
    - **Property 16: Payment Method in Exports and Webhooks**
    - **Validates: Requirements 7.5, 7.6, 7.7**
    - Test that payment method is included in history, CSV, and webhooks

- [ ] 15. Extend webhook delivery
  - [ ] 15.1 Modify services/webhook.py to include payment method
    - Add selected_payment_method to webhook payload
    - Add processing_fee to webhook payload
    - Add total_amount to webhook payload
    - Add card_brand and card_last_four to webhook payload for card payments
    - Maintain backward compatibility (don't include fields for legacy transactions)
    - _Requirements: 7.7, 11.6_
  
  - [ ]* 15.2 Write unit tests for webhook payload
    - Test webhook includes payment method for new transactions
    - Test webhook includes fee breakdown for card payments
    - Test webhook backward compatibility for legacy transactions

- [ ] 16. Implement comprehensive property-based tests
  - [ ]* 16.1 Write property test for fee breakdown display
    - **Property 14: Fee Breakdown Display**
    - **Validates: Requirements 5.2, 5.3, 14.4**
    - Test that original amount, processing fee, and total are displayed before payment
  
  - [ ]* 16.2 Write property test for fee storage round-trip
    - **Property 15: Fee Storage Round-Trip**
    - **Validates: Requirements 5.4**
    - Test that stored fees match calculated fees after completion
  
  - [ ]* 16.3 Write property test for mock mode logging
    - **Property 27: Mock Mode Logging**
    - **Validates: Requirements 10.6**
    - Test that mock mode is clearly logged
  
  - [ ]* 16.4 Write property test for legacy transaction compatibility
    - **Property 28: Legacy Transaction Backward Compatibility**
    - **Validates: Requirements 11.1, 11.3**
    - Test that NULL payment methods are treated as ['bank_transfer']
  
  - [ ]* 16.5 Write property test for QR code base64 delivery
    - **Property 29: QR Code Base64 Delivery**
    - **Validates: Requirements 12.4**
    - Test that QR code is delivered as base64 data URL
  
  - [ ]* 16.6 Write property test for QR code caching
    - **Property 30: QR Code Caching**
    - **Validates: Requirements 12.5**
    - Test that multiple QR code generations return cached result
  
  - [ ]* 16.7 Write property test for QR code error handling
    - **Property 31: QR Code Generation Error Handling**
    - **Validates: Requirements 12.6**
    - Test that QR generation failure logs error and shows page without QR
  
  - [ ]* 16.8 Write property test for fee information display
    - **Property 32: Fee Information Display**
    - **Validates: Requirements 14.1, 14.2, 14.3**
    - Test that fee information is displayed for each payment method
  
  - [ ]* 16.9 Write property test for amount formatting
    - **Property 34: Amount Formatting**
    - **Validates: Requirements 14.6**
    - Test that amounts are formatted with 2 decimal places

- [ ] 17. Checkpoint - Ensure all tests pass
  - Run all unit tests: `pytest tests/ -v`
  - Run all property-based tests with minimum 100 iterations
  - Verify no errors or warnings in test output
  - Ensure all tests pass, ask the user if questions arise

- [ ] 18. Integration testing
  - [ ]* 18.1 Write integration test for card payment flow
    - Test full flow: create link → select card payment → submit card → verify status
    - Test with mock mode (even/odd card numbers)
    - Test rate limiting enforcement
    - Test audit logging
  
  - [ ]* 18.2 Write integration test for QR code flow
    - Test QR code generation and display
    - Test QR code round-trip encoding/decoding
    - Test QR code caching
    - Test QR code visibility based on transaction state
  
  - [ ]* 18.3 Write integration test for payment method selection
    - Test single method display
    - Test multiple method selection
    - Test fee calculation and display
    - Test method persistence
  
  - [ ]* 18.4 Write integration test for backward compatibility
    - Test legacy transactions work without payment methods
    - Test legacy transactions default to bank_transfer
    - Test legacy transactions in dashboard and exports

- [ ] 19. Security testing
  - [ ]* 19.1 Write security test for card data protection
    - Test card numbers not in database
    - Test card numbers not in logs
    - Test CVV not stored or logged
    - Test only last 4 digits stored
  
  - [ ]* 19.2 Write security test for rate limiting
    - Test card payment rate limit per IP
    - Test rate limit reset after window
  
  - [ ]* 19.3 Write security test for CSRF protection
    - Test card payment requires CSRF token
    - Test invalid token rejected
  
  - [ ]* 19.4 Write security test for input validation
    - Test SQL injection attempts rejected
    - Test XSS attempts sanitized
    - Test invalid card formats rejected

- [ ] 20. Update documentation
  - Update README.md with new features
  - Document new environment variables in .env.example
  - Update API documentation with new endpoints
  - Document payment method selection flow
  - Document card payment integration
  - Document QR code feature
  - Create deployment guide for database migration
  - _Requirements: All_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tests/ -v`
  - Run property-based tests with 100+ iterations
  - Verify all 34 properties pass
  - Check code coverage
  - Verify no security issues
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Security tests validate PCI-DSS compliance measures
- The implementation maintains backward compatibility with existing payment links
- Mock mode enables testing without real Quickteller credentials
- All card data handling follows PCI-DSS security standards

# Requirements Document

## Introduction

This document specifies the requirements for replacing the existing Quickteller/Interswitch payment API integration with KoraPay API across the entire OnePay application. The migration must maintain all existing payment functionalities while ensuring backward compatibility with the database schema, user interfaces, and external integrations. The system currently uses Quickteller for OAuth token management, virtual account creation for bank transfers, transfer confirmation polling, and mock mode support for testing.

## Glossary

- **Payment_Gateway**: The external payment service provider (KoraPay) that processes payment transactions
- **Virtual_Account**: A temporary, single-use bank account number generated for a specific transaction
- **Transaction**: A payment record in the OnePay database with a unique transaction reference
- **Merchant**: A registered OnePay user who creates payment links
- **Customer**: An end-user who makes a payment through a payment link
- **Mock_Mode**: A testing mode that simulates payment provider responses without real API credentials
- **Webhook**: An HTTP callback that notifies the application of payment status changes
- **Transfer_Confirmation**: The process of verifying that a bank transfer has been received
- **OAuth_Token**: An access token used to authenticate API requests to the payment gateway
- **Transaction_Reference**: A unique identifier (tx_ref) for each payment transaction
- **Payment_Link**: A secure, time-bound URL that customers use to make payments
- **Rate_Limiter**: A mechanism that restricts the number of API requests per time period
- **Idempotency**: The property that multiple identical requests produce the same result
- **HMAC_Signature**: A cryptographic signature used to verify webhook authenticity
- **Kobo**: The smallest currency unit in Nigerian Naira (1 Naira = 100 Kobo)
- **Configuration_Service**: The component that manages environment variables and API credentials
- **Database_Schema**: The structure of database tables and relationships
- **Audit_Log**: A record of security-relevant events and actions

## Requirements

### Requirement 1: Remove Quickteller Integration

**User Story:** As a developer, I want to remove all Quickteller-related code and configuration, so that the codebase is clean and ready for KoraPay integration.

#### Acceptance Criteria

1. THE System SHALL remove the Quickteller service module (services/quickteller.py)
2. THE System SHALL remove all Quickteller configuration variables from config.py (QUICKTELLER_CLIENT_ID, QUICKTELLER_CLIENT_SECRET, QUICKTELLER_BASE_URL, MERCHANT_CODE, PAYABLE_CODE, VIRTUAL_ACCOUNT_BASE_URL)
3. THE System SHALL remove all Quickteller environment variable templates from .env.example and .env.production.example
4. THE System SHALL remove all Quickteller import statements from blueprints/payments.py and blueprints/public.py
5. THE System SHALL remove all references to the quickteller service instance from route handlers
6. THE System SHALL preserve the database schema without modifications during removal
7. THE System SHALL preserve all user interface templates without modifications during removal
8. THE System SHALL remove the _mock_poll_counts global state dictionary used for mock mode tracking
9. THE System SHALL remove the QuicktellerError exception class definition
10. THE System SHALL remove the QuicktellerService class and all its methods (_get_auth_header, get_access_token, _mock_create_virtual_account, _mock_confirm_transfer, create_virtual_account, confirm_transfer)
11. THE System SHALL remove the global quickteller service instance
12. THE System SHALL verify no remaining references to "quickteller" or "Quickteller" exist in Python source files after removal
13. THE System SHALL verify no remaining references to "Interswitch" exist in Python source files after removal

### Requirement 2: Research KoraPay API Documentation

**User Story:** As a developer, I want to understand KoraPay's API capabilities and authentication methods, so that I can implement a correct and complete integration.

#### Acceptance Criteria

1. THE Developer SHALL review the KoraPay Pay with Bank documentation at https://developers.korapay.com/docs/pay-with-bank
2. THE Developer SHALL identify the authentication method required by KoraPay (API key, OAuth, Bearer token, or other)
3. THE Developer SHALL identify the API endpoints for virtual account creation with exact URL paths and HTTP methods
4. THE Developer SHALL identify the API endpoints for transfer confirmation/status checking with exact URL paths and HTTP methods
5. THE Developer SHALL identify the webhook payload structure including all fields, data types, and nested objects
6. THE Developer SHALL identify the webhook signature verification method (HMAC algorithm, header name, signature format)
7. THE Developer SHALL identify the API endpoints for refund operations (if supported) with exact URL paths and HTTP methods
8. THE Developer SHALL identify the API endpoints for transaction history retrieval with exact URL paths and HTTP methods
9. THE Developer SHALL document the complete request format for each endpoint including headers, body structure, required fields, and optional fields
10. THE Developer SHALL document the complete response format for each endpoint including success responses, error responses, and all possible status codes
11. THE Developer SHALL identify rate limiting policies including limits per endpoint, time windows, and rate limit headers
12. THE Developer SHALL identify error response formats including error codes, error messages, and error details structure
13. THE Developer SHALL identify the test/sandbox environment configuration including base URLs, test credentials format, and test mode indicators
14. THE Developer SHALL identify the production environment configuration including base URLs and credential requirements
15. THE Developer SHALL identify currency code format (ISO 4217 numeric or alpha codes)
16. THE Developer SHALL identify amount format (kobo/cents or major currency units, integer or decimal)
17. THE Developer SHALL identify timeout recommendations for API requests
18. THE Developer SHALL identify idempotency key support and header format
19. THE Developer SHALL identify pagination format for list endpoints (if applicable)
20. THE Developer SHALL identify webhook retry behavior and failure handling
21. THE Developer SHALL identify supported bank codes and bank name formats for virtual accounts
22. THE Developer SHALL identify virtual account validity period configuration options
23. THE Developer SHALL identify transaction reference format requirements and length limits
24. THE Developer SHALL identify customer information requirements (email, phone, name formats)
25. THE Developer SHALL document all findings in a KoraPay API research document

### Requirement 3: Implement KoraPay Service Module

**User Story:** As a developer, I want a KoraPay service module that encapsulates all API interactions, so that payment logic is centralized and maintainable.

#### Acceptance Criteria

1. THE System SHALL create a new service module at services/korapay.py
2. THE KoraPay_Service SHALL implement authentication using credentials from environment variables (KORAPAY_API_KEY, KORAPAY_SECRET_KEY)
3. THE KoraPay_Service SHALL implement a method to create virtual accounts for transactions with signature: create_virtual_account(transaction_reference: str, amount_kobo: int, account_name: str) -> dict
4. THE KoraPay_Service SHALL implement a method to confirm transfer status with signature: confirm_transfer(transaction_reference: str, _retry: bool = False) -> dict
5. THE KoraPay_Service SHALL implement error handling that raises a KoraPayError exception for API failures
6. THE KoraPay_Service SHALL implement request timeout handling with a 30-second timeout for all API requests
7. THE KoraPay_Service SHALL log all API requests at INFO level including endpoint, method, and transaction reference
8. THE KoraPay_Service SHALL log all API responses at INFO level including status code, response code, and transaction reference
9. THE KoraPay_Service SHALL implement retry logic with exponential backoff for transient failures (5xx errors, timeouts, connection errors)
10. THE KoraPay_Service SHALL retry failed requests up to 3 times with delays of 1 second, 2 seconds, and 4 seconds
11. THE KoraPay_Service SHALL NOT retry client errors (4xx status codes except 429 rate limit)
12. THE KoraPay_Service SHALL validate all API responses for required fields before returning data
13. THE KoraPay_Service SHALL raise KoraPayError with descriptive message when required response fields are missing
14. THE KoraPay_Service SHALL implement a method is_configured() that returns True when API credentials are set
15. THE KoraPay_Service SHALL implement a method is_transfer_configured() that returns True when all required configuration is present
16. THE KoraPay_Service SHALL implement a method _is_mock() that returns True when running without real credentials
17. THE KoraPay_Service SHALL cache authentication tokens if KoraPay uses OAuth (with expiry tracking)
18. THE KoraPay_Service SHALL refresh expired authentication tokens automatically before API requests
19. THE KoraPay_Service SHALL include User-Agent header "OnePay-KoraPay/1.0" in all API requests
20. THE KoraPay_Service SHALL include Content-Type header "application/json" in all POST requests
21. THE KoraPay_Service SHALL include Accept header "application/json" in all requests
22. THE KoraPay_Service SHALL handle JSON decode errors gracefully with descriptive error messages
23. THE KoraPay_Service SHALL handle network connection errors gracefully with descriptive error messages
24. THE KoraPay_Service SHALL handle SSL certificate errors gracefully with descriptive error messages
25. THE KoraPay_Service SHALL validate response status codes and raise appropriate errors for non-2xx responses
26. THE KoraPay_Service SHALL extract error messages from KoraPay error responses and include in exceptions
27. THE KoraPay_Service SHALL implement idempotency by including transaction reference in all requests
28. THE KoraPay_Service SHALL use the requests library for HTTP communication (consistent with existing codebase)
29. THE KoraPay_Service SHALL set allow_redirects=False to prevent redirect-based attacks
30. WHERE Mock_Mode is enabled, THE KoraPay_Service SHALL return simulated responses without making real API calls

### Requirement 4: Implement Mock Mode for Testing

**User Story:** As a developer, I want a mock mode that simulates KoraPay responses, so that I can test the payment flow without real API credentials.

#### Acceptance Criteria

1. WHEN KoraPay credentials are not configured, THE KoraPay_Service SHALL automatically enable Mock_Mode
2. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL log a warning message "MOCK MODE ACTIVE" at startup
3. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL log "[MOCK]" prefix in all mock operation log messages
4. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return a deterministic fake account number based on the transaction reference
5. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL generate account numbers using formula: 3000000000 + (sum of character codes in tx_ref % 999999999)
6. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return bank name "Wema Bank (Demo)"
7. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return account name matching the provided account_name parameter
8. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return validity period of 30 minutes
9. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return response code "Z0" (pending)
10. WHEN creating a virtual account in Mock_Mode, THE KoraPay_Service SHALL return amount in kobo matching the provided amount_kobo parameter
11. WHEN confirming transfer status in Mock_Mode, THE KoraPay_Service SHALL return "Z0" (pending) status for the first 3 polls
12. WHEN confirming transfer status in Mock_Mode for the 4th or subsequent poll, THE KoraPay_Service SHALL return "00" (confirmed) status
13. THE KoraPay_Service SHALL maintain a poll counter dictionary _mock_poll_counts for each transaction reference in Mock_Mode
14. THE KoraPay_Service SHALL increment the poll counter for each confirm_transfer call in Mock_Mode
15. THE KoraPay_Service SHALL clean up poll counters after a transaction is confirmed in Mock_Mode
16. THE KoraPay_Service SHALL log poll count and confirmation threshold in each mock confirm_transfer call
17. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL return responses instantly without network delays
18. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL never make actual HTTP requests to external APIs
19. WHEN Mock_Mode is enabled, THE is_transfer_configured() method SHALL return True to allow UI to display bank details
20. THE Mock_Mode SHALL use constant MOCK_CONFIRM_AFTER = 3 to configure confirmation threshold
21. THE Mock_Mode SHALL support testing the complete payment flow from link creation to confirmation
22. THE Mock_Mode SHALL support testing the polling behavior with multiple status checks
23. THE Mock_Mode SHALL support testing webhook delivery after mock confirmation
24. THE Mock_Mode SHALL support testing email notifications after mock confirmation
25. THE Mock_Mode SHALL generate realistic-looking 10-digit account numbers in Mock_Mode

### Requirement 5: Update Configuration Management

**User Story:** As a system administrator, I want KoraPay configuration variables in environment files, so that I can configure the integration without code changes.

#### Acceptance Criteria

1. THE Configuration_Service SHALL add KORAPAY_API_KEY to config.py with default value empty string
2. THE Configuration_Service SHALL add KORAPAY_SECRET_KEY to config.py with default value empty string
3. THE Configuration_Service SHALL add KORAPAY_BASE_URL to config.py with default value for production environment
4. THE Configuration_Service SHALL add KORAPAY_SANDBOX_URL to config.py with default value for test environment
5. THE Configuration_Service SHALL add KORAPAY_MERCHANT_ID to config.py with default value empty string
6. THE Configuration_Service SHALL add KORAPAY_WEBHOOK_SECRET to config.py with default value empty string (separate from KORAPAY_SECRET_KEY)
7. THE Configuration_Service SHALL add configuration templates to .env.example with placeholder values and descriptive comments
8. THE Configuration_Service SHALL add configuration templates to .env.production.example with placeholder values and security warnings
9. THE Configuration_Service SHALL validate that KoraPay credentials are not placeholder values in production environment
10. THE Configuration_Service SHALL validate that KORAPAY_SECRET_KEY meets minimum length requirement of 32 characters
11. THE Configuration_Service SHALL validate that KORAPAY_WEBHOOK_SECRET meets minimum length requirement of 32 characters
12. THE Configuration_Service SHALL validate that KORAPAY_API_KEY meets minimum length requirement of 32 characters
13. WHERE APP_ENV is "production" and KORAPAY_SECRET_KEY contains "change-this", THE Configuration_Service SHALL abort startup with error message
14. WHERE APP_ENV is "production" and KORAPAY_API_KEY contains "change-this", THE Configuration_Service SHALL abort startup with error message
15. WHERE APP_ENV is "production" and KORAPAY_WEBHOOK_SECRET contains "change-this", THE Configuration_Service SHALL abort startup with error message
16. THE Configuration_Service SHALL validate that KORAPAY_SECRET_KEY is different from KORAPAY_WEBHOOK_SECRET
17. THE Configuration_Service SHALL validate that KORAPAY_SECRET_KEY is different from HMAC_SECRET
18. THE Configuration_Service SHALL validate that KORAPAY_WEBHOOK_SECRET is different from WEBHOOK_SECRET
19. THE Configuration_Service SHALL select KORAPAY_BASE_URL or KORAPAY_SANDBOX_URL based on APP_ENV setting
20. THE Configuration_Service SHALL log configuration validation errors with specific field names and requirements
21. THE Configuration_Service SHALL provide clear error messages for missing required configuration in production
22. THE Configuration_Service SHALL allow empty KoraPay credentials in development and testing environments (for mock mode)
23. THE Configuration_Service SHALL document all KoraPay configuration variables in .env.example with usage examples
24. THE Configuration_Service SHALL document KoraPay sandbox vs production URL differences in .env.example
25. THE Configuration_Service SHALL include instructions for obtaining KoraPay credentials in .env.example comments

### Requirement 6: Update Payment Link Creation

**User Story:** As a merchant, I want to create payment links that use KoraPay virtual accounts, so that customers can make bank transfer payments.

#### Acceptance Criteria

1. WHEN a merchant creates a payment link, THE System SHALL call KoraPay_Service.create_virtual_account() with transaction reference, amount in kobo, and account name
2. WHEN KoraPay returns a virtual account, THE System SHALL store the account number in Transaction.virtual_account_number
3. WHEN KoraPay returns a virtual account, THE System SHALL store the bank name in Transaction.virtual_bank_name
4. WHEN KoraPay returns a virtual account, THE System SHALL store the account name in Transaction.virtual_account_name
5. WHEN KoraPay virtual account creation fails, THE System SHALL return an error response to the merchant with HTTP status 500
6. WHEN KoraPay virtual account creation fails, THE System SHALL log the error at ERROR level with transaction reference and error details
7. WHEN KoraPay virtual account creation fails, THE System SHALL NOT create the transaction record in the database
8. WHEN KoraPay virtual account creation fails, THE System SHALL rollback any database changes
9. THE System SHALL convert the amount from Naira to Kobo before sending to KoraPay by multiplying by 100
10. THE System SHALL validate that the amount in Kobo is an integer value
11. THE System SHALL validate that the amount in Kobo is greater than 0
12. THE System SHALL validate that the amount in Kobo does not exceed 999999999999 (maximum 12 digits)
13. THE System SHALL generate QR codes for the payment link URL using qr_service.generate_payment_qr()
14. THE System SHALL generate QR codes for the virtual account details using qr_service.generate_virtual_account_qr()
15. THE System SHALL store the payment QR code data URI in Transaction.qr_code_payment_url
16. THE System SHALL store the virtual account QR code data URI in Transaction.qr_code_virtual_account
17. THE System SHALL preserve all existing validation logic for amount (must be positive Decimal)
18. THE System SHALL preserve all existing validation logic for description (max 255 characters, sanitized)
19. THE System SHALL preserve all existing validation logic for customer email (valid email format)
20. THE System SHALL preserve all existing validation logic for customer phone (valid phone format)
21. THE System SHALL preserve all existing validation logic for return URL (HTTPS only in production, valid URL format)
22. THE System SHALL preserve all existing validation logic for webhook URL (HTTPS only in production, valid URL format, no private IPs)
23. THE System SHALL maintain idempotency using the existing idempotency_key mechanism
24. WHEN an idempotency key is provided and matches an existing transaction, THE System SHALL return the existing transaction without calling KoraPay
25. THE System SHALL use the account name format "{merchant_username} - OnePay Payment" for virtual accounts
26. THE System SHALL handle KoraPayError exceptions and convert to user-friendly error messages
27. THE System SHALL handle network timeout errors and return "Payment provider unavailable" message
28. THE System SHALL handle JSON decode errors and return "Invalid response from payment provider" message
29. THE System SHALL log successful virtual account creation at INFO level with account number and bank name
30. THE System SHALL maintain the existing rate limit of 10 payment link creations per minute per user

### Requirement 7: Update Transfer Status Polling

**User Story:** As a customer, I want the system to automatically detect when my bank transfer is received, so that my payment is confirmed without manual intervention.

#### Acceptance Criteria

1. WHEN a customer polls transfer status, THE System SHALL call KoraPay_Service.confirm_transfer() with the transaction reference
2. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL update Transaction.transfer_confirmed to True
3. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL update Transaction.status to VERIFIED
4. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL update Transaction.is_used to True
5. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL set Transaction.verified_at to the current UTC timestamp
6. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL deliver the webhook if webhook_url is configured
7. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL send merchant notification email
8. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL send customer invoice email if auto_send_email is enabled
9. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL sync the invoice status to PAID if an invoice exists
10. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL set invoice.paid_at to the current UTC timestamp
11. WHEN KoraPay returns response code "00" (confirmed), THE System SHALL log audit event "payment.confirmed" with user_id, tx_ref, ip_address, and amount
12. WHEN KoraPay returns response code "Z0" (pending), THE System SHALL return JSON response {"success": false, "status": "pending", "tx_ref": "<tx_ref>"}
13. WHEN KoraPay returns response code "Z0" (pending), THE System SHALL NOT update any transaction fields
14. WHEN KoraPay returns an error response code (not "00" or "Z0"), THE System SHALL log the error at ERROR level
15. WHEN KoraPay returns an error response code, THE System SHALL return JSON response {"success": false, "status": "error", "message": "<error_message>"}
16. THE System SHALL use optimistic locking with with_for_update() to prevent race conditions during status updates
17. THE System SHALL query the transaction WITHOUT locking first to check if already confirmed (fast path)
18. WHEN the transaction is already confirmed, THE System SHALL return success response without calling KoraPay API
19. WHEN the transaction is already used, THE System SHALL return JSON response {"success": false, "status": "used", "tx_ref": "<tx_ref>"}
20. WHEN the transaction is expired, THE System SHALL update Transaction.status to EXPIRED if not already expired
21. WHEN the transaction is expired, THE System SHALL sync invoice status to EXPIRED if an invoice exists
22. WHEN the transaction is expired, THE System SHALL return JSON response {"success": false, "status": "expired", "tx_ref": "<tx_ref>"}
23. THE System SHALL acquire the database lock ONLY after confirming payment with KoraPay (minimize lock duration)
24. THE System SHALL double-check transfer_confirmed status after acquiring lock to handle race conditions
25. WHEN another request has already confirmed the transaction, THE System SHALL log "already confirmed by another request" and return success
26. THE System SHALL commit all database changes (transaction update, webhook, invoice sync, audit log) in a single database transaction
27. THE System SHALL rollback all changes if any step fails during confirmation processing
28. THE System SHALL maintain the existing rate limiting of 20 requests per minute per IP address
29. THE System SHALL require session access token set by /pay/ page to prevent unauthorized polling
30. WHEN session access token is missing, THE System SHALL return error response {"error": "Access denied", "code": "FORBIDDEN"} with HTTP status 403
31. THE System SHALL handle KoraPayError exceptions and return error response with status 200 (not 500) to prevent frontend error handling issues
32. THE System SHALL handle database connection errors and return error response with appropriate message
33. THE System SHALL handle concurrent confirmation attempts gracefully without data corruption
34. THE System SHALL log all confirmation attempts at INFO level with tx_ref, ip_address, and result
35. THE System SHALL call sync_invoice_on_transaction_update() after status changes to keep invoice status synchronized

### Requirement 8: Update Health Check Endpoint

**User Story:** As a system administrator, I want the health check endpoint to report KoraPay configuration status, so that I can monitor the integration health.

#### Acceptance Criteria

1. THE Health_Check_Endpoint SHALL replace the "quickteller" field with "korapay" in the JSON response
2. THE Health_Check_Endpoint SHALL replace the "transfer_configured" field with "korapay_configured" in the JSON response
3. THE Health_Check_Endpoint SHALL report True for "korapay" when KoraPay_Service.is_configured() returns True
4. THE Health_Check_Endpoint SHALL report False for "korapay" when KoraPay_Service.is_configured() returns False
5. THE Health_Check_Endpoint SHALL report True for "korapay_configured" when KoraPay_Service.is_transfer_configured() returns True
6. THE Health_Check_Endpoint SHALL report False for "korapay_configured" when KoraPay_Service.is_transfer_configured() returns False
7. THE Health_Check_Endpoint SHALL report True for "mock_mode" when KoraPay credentials are not configured
8. THE Health_Check_Endpoint SHALL report False for "mock_mode" when KoraPay credentials are configured
9. THE Health_Check_Endpoint SHALL preserve the "status" field with values "healthy" or "degraded"
10. THE Health_Check_Endpoint SHALL preserve the "app" field with value "OnePay"
11. THE Health_Check_Endpoint SHALL preserve the "timestamp" field with current UTC timestamp in ISO format
12. THE Health_Check_Endpoint SHALL preserve the "database" field with values "ok" or "error"
13. THE Health_Check_Endpoint SHALL test database connectivity by executing "SELECT 1" query
14. THE Health_Check_Endpoint SHALL set status to "degraded" when database connectivity fails
15. THE Health_Check_Endpoint SHALL set status to "healthy" when database connectivity succeeds
16. THE Health_Check_Endpoint SHALL call cleanup_old_rate_limits() during health check execution
17. THE Health_Check_Endpoint SHALL call cleanup_old_audit_logs() with 90-day retention during health check execution
18. THE Health_Check_Endpoint SHALL handle cleanup errors gracefully without affecting health check response
19. THE Health_Check_Endpoint SHALL log database connectivity errors at ERROR level
20. THE Health_Check_Endpoint SHALL return HTTP status 200 even when status is "degraded"
21. THE Health_Check_Endpoint SHALL include KoraPay base URL in response for debugging (without exposing credentials)
22. THE Health_Check_Endpoint SHALL include KoraPay environment indicator (sandbox/production) in response
23. THE Health_Check_Endpoint SHALL NOT expose any KoraPay API keys or secrets in the response
24. THE Health_Check_Endpoint SHALL NOT expose any sensitive configuration values in the response
25. THE Health_Check_Endpoint SHALL be accessible without authentication (public endpoint)

### Requirement 9: Implement Webhook Signature Verification

**User Story:** As a security engineer, I want webhook requests from KoraPay to be cryptographically verified, so that only authentic payment notifications are processed.

#### Acceptance Criteria

1. THE Webhook_Handler SHALL extract the signature from the KoraPay webhook request headers (header name determined by KoraPay API documentation)
2. THE Webhook_Handler SHALL extract the raw request body as bytes for signature computation
3. THE Webhook_Handler SHALL compute the expected HMAC signature using HMAC-SHA256 algorithm
4. THE Webhook_Handler SHALL use KORAPAY_WEBHOOK_SECRET as the HMAC key for signature computation
5. THE Webhook_Handler SHALL compute HMAC over the raw request body bytes (not parsed JSON)
6. THE Webhook_Handler SHALL compare the received signature with the expected signature using hmac.compare_digest() for constant-time comparison
7. WHEN the signatures do not match, THE Webhook_Handler SHALL reject the webhook request with HTTP status 401 Unauthorized
8. WHEN the signatures do not match, THE Webhook_Handler SHALL return JSON response {"error": "Invalid signature", "code": "UNAUTHORIZED"}
9. WHEN the signatures do not match, THE Webhook_Handler SHALL log a security warning at WARNING level with source IP address
10. WHEN the signatures do not match, THE Webhook_Handler SHALL log audit event "webhook.signature_failed" with IP address and transaction reference
11. WHEN the signatures do not match, THE Webhook_Handler SHALL NOT process the webhook payload
12. WHEN the signatures do not match, THE Webhook_Handler SHALL NOT update any transaction records
13. WHEN the signatures match, THE Webhook_Handler SHALL parse the webhook payload as JSON
14. WHEN the signatures match, THE Webhook_Handler SHALL extract the transaction reference from the payload
15. WHEN the signatures match, THE Webhook_Handler SHALL extract the payment status from the payload
16. WHEN the signatures match, THE Webhook_Handler SHALL extract the amount from the payload
17. WHEN the signatures match, THE Webhook_Handler SHALL extract the currency from the payload
18. WHEN the signatures match, THE Webhook_Handler SHALL extract the timestamp from the payload
19. WHEN the webhook indicates a confirmed payment, THE Webhook_Handler SHALL query the transaction by transaction reference
20. WHEN the transaction does not exist, THE Webhook_Handler SHALL log error and return HTTP status 404
21. WHEN the transaction exists, THE Webhook_Handler SHALL validate that the webhook amount matches the transaction amount
22. WHEN the webhook amount does not match, THE Webhook_Handler SHALL log error and return HTTP status 400
23. WHEN the transaction is already confirmed, THE Webhook_Handler SHALL return HTTP status 200 with success response (idempotent)
24. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL update transaction status to VERIFIED
25. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL set transfer_confirmed to True
26. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL set verified_at to current UTC timestamp
27. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL set is_used to True
28. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL sync invoice status to PAID if invoice exists
29. WHEN the transaction is not yet confirmed, THE Webhook_Handler SHALL log audit event "payment.confirmed_via_webhook"
30. THE Webhook_Handler SHALL implement idempotency by checking transaction status before processing
31. THE Webhook_Handler SHALL handle duplicate webhook deliveries gracefully without errors
32. THE Webhook_Handler SHALL validate that the transaction reference exists before processing
33. THE Webhook_Handler SHALL validate that the webhook payload contains all required fields
34. WHEN required fields are missing, THE Webhook_Handler SHALL return HTTP status 400 with error message listing missing fields
35. THE Webhook_Handler SHALL handle JSON parse errors and return HTTP status 400
36. THE Webhook_Handler SHALL handle database errors and return HTTP status 500
37. THE Webhook_Handler SHALL commit all database changes in a single transaction
38. THE Webhook_Handler SHALL rollback changes if any step fails
39. THE Webhook_Handler SHALL return HTTP status 200 for successfully processed webhooks
40. THE Webhook_Handler SHALL return JSON response {"success": true, "tx_ref": "<tx_ref>"} for successful processing
41. THE Webhook_Handler SHALL NOT expose internal error details in webhook responses
42. THE Webhook_Handler SHALL log all webhook attempts at INFO level with tx_ref, status, and IP address
43. THE Webhook_Handler SHALL be accessible without authentication (public endpoint with signature verification)
44. THE Webhook_Handler SHALL implement rate limiting to prevent webhook flooding attacks
45. THE Webhook_Handler SHALL validate that the webhook timestamp is recent (within 5 minutes) to prevent replay attacks

### Requirement 10: Implement Comprehensive Error Handling

**User Story:** As a developer, I want comprehensive error handling for all KoraPay API interactions, so that failures are logged and users receive helpful error messages.

#### Acceptance Criteria

1. WHEN a KoraPay API request times out after 30 seconds, THE System SHALL log the timeout error at ERROR level with transaction reference and endpoint
2. WHEN a KoraPay API request times out, THE System SHALL return error response {"error": "Payment provider unavailable - please try again", "code": "TIMEOUT"}
3. WHEN a KoraPay API returns HTTP status 400 (Bad Request), THE System SHALL log the error response body at ERROR level
4. WHEN a KoraPay API returns HTTP status 400, THE System SHALL extract the error message from the response body
5. WHEN a KoraPay API returns HTTP status 400, THE System SHALL return error response with the specific error message from KoraPay
6. WHEN a KoraPay API returns HTTP status 401 (Unauthorized), THE System SHALL log "Authentication failed" at ERROR level
7. WHEN a KoraPay API returns HTTP status 401, THE System SHALL return error response {"error": "Payment provider authentication failed", "code": "AUTH_ERROR"}
8. WHEN a KoraPay API returns HTTP status 403 (Forbidden), THE System SHALL log "Access forbidden" at ERROR level
9. WHEN a KoraPay API returns HTTP status 403, THE System SHALL return error response {"error": "Payment provider access denied", "code": "FORBIDDEN"}
10. WHEN a KoraPay API returns HTTP status 404 (Not Found), THE System SHALL log "Resource not found" at ERROR level
11. WHEN a KoraPay API returns HTTP status 404, THE System SHALL return error response {"error": "Transaction not found at payment provider", "code": "NOT_FOUND"}
12. WHEN a KoraPay API returns HTTP status 429 (Rate Limit), THE System SHALL log "Rate limit exceeded" at WARNING level
13. WHEN a KoraPay API returns HTTP status 429, THE System SHALL retry the request after the delay specified in Retry-After header
14. WHEN a KoraPay API returns HTTP status 429 and no Retry-After header, THE System SHALL retry after 60 seconds
15. WHEN a KoraPay API returns HTTP status 500 (Internal Server Error), THE System SHALL log the error at ERROR level
16. WHEN a KoraPay API returns HTTP status 500, THE System SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s)
17. WHEN a KoraPay API returns HTTP status 502 (Bad Gateway), THE System SHALL retry up to 3 times with exponential backoff
18. WHEN a KoraPay API returns HTTP status 503 (Service Unavailable), THE System SHALL retry up to 3 times with exponential backoff
19. WHEN a KoraPay API returns HTTP status 504 (Gateway Timeout), THE System SHALL retry up to 3 times with exponential backoff
20. WHEN all retry attempts fail, THE System SHALL return error response {"error": "Payment provider temporarily unavailable", "code": "SERVICE_UNAVAILABLE"}
21. WHEN a KoraPay API returns invalid JSON, THE System SHALL raise KoraPayError with message "Invalid JSON response from payment provider"
22. WHEN a KoraPay API returns invalid JSON, THE System SHALL log the raw response body at ERROR level (truncated to 500 characters)
23. WHEN a KoraPay API response is missing required field "accountNumber", THE System SHALL raise KoraPayError listing the missing field
24. WHEN a KoraPay API response is missing required field "bankName", THE System SHALL raise KoraPayError listing the missing field
25. WHEN a KoraPay API response is missing required field "responseCode", THE System SHALL raise KoraPayError listing the missing field
26. WHEN a KoraPay API response is missing multiple required fields, THE System SHALL list all missing fields in the error message
27. WHEN network connectivity fails with ConnectionError, THE System SHALL log "Network connection failed" at ERROR level
28. WHEN network connectivity fails, THE System SHALL return error response {"error": "Cannot connect to payment provider", "code": "CONNECTION_ERROR"}
29. WHEN SSL certificate verification fails, THE System SHALL log "SSL certificate verification failed" at ERROR level
30. WHEN SSL certificate verification fails, THE System SHALL return error response {"error": "Payment provider security error", "code": "SSL_ERROR"}
31. WHEN DNS resolution fails, THE System SHALL log "DNS resolution failed" at ERROR level
32. WHEN DNS resolution fails, THE System SHALL return error response {"error": "Cannot reach payment provider", "code": "DNS_ERROR"}
33. THE System SHALL never expose KORAPAY_API_KEY in error messages or logs
34. THE System SHALL never expose KORAPAY_SECRET_KEY in error messages or logs
35. THE System SHALL never expose KORAPAY_WEBHOOK_SECRET in error messages or logs
36. THE System SHALL sanitize all error messages to remove sensitive data before logging
37. THE System SHALL sanitize all error messages to remove sensitive data before returning to users
38. THE System SHALL maintain existing audit logging for all payment-related errors with event type "payment.error"
39. THE System SHALL include transaction reference in all error log messages when available
40. THE System SHALL include HTTP status code in all API error log messages
41. THE System SHALL include endpoint URL in all API error log messages (without query parameters containing sensitive data)
42. THE System SHALL handle unexpected exceptions with try-except blocks and log full stack traces
43. THE System SHALL return generic error messages to users for unexpected exceptions
44. THE System SHALL log detailed error information for debugging while returning safe messages to users
45. THE System SHALL implement circuit breaker pattern to stop calling KoraPay after 10 consecutive failures (optional enhancement)

### Requirement 11: Implement Unit Tests for KoraPay Service

**User Story:** As a developer, I want comprehensive unit tests for the KoraPay service, so that I can verify correct behavior and prevent regressions.

#### Acceptance Criteria

1. THE Test_Suite SHALL include a test test_create_virtual_account_success that verifies successful virtual account creation with mocked HTTP response
2. THE Test_Suite SHALL include a test test_create_virtual_account_timeout that verifies timeout handling raises KoraPayError
3. THE Test_Suite SHALL include a test test_create_virtual_account_400_error that verifies 400 error handling with error message extraction
4. THE Test_Suite SHALL include a test test_create_virtual_account_401_error that verifies authentication error handling
5. THE Test_Suite SHALL include a test test_create_virtual_account_500_error that verifies 500 error triggers retry logic
6. THE Test_Suite SHALL include a test test_create_virtual_account_invalid_json that verifies JSON decode error handling
7. THE Test_Suite SHALL include a test test_create_virtual_account_missing_fields that verifies missing field validation
8. THE Test_Suite SHALL include a test test_confirm_transfer_success_confirmed that verifies successful transfer confirmation with response code "00"
9. THE Test_Suite SHALL include a test test_confirm_transfer_success_pending that verifies pending status with response code "Z0"
10. THE Test_Suite SHALL include a test test_confirm_transfer_timeout that verifies timeout handling
11. THE Test_Suite SHALL include a test test_confirm_transfer_404_error that verifies not found error handling
12. THE Test_Suite SHALL include a test test_confirm_transfer_500_error that verifies retry logic for server errors
13. THE Test_Suite SHALL include a test test_mock_mode_create_virtual_account that verifies mock virtual account creation returns deterministic account number
14. THE Test_Suite SHALL include a test test_mock_mode_confirm_transfer_pending that verifies mock mode returns pending for first 3 polls
15. THE Test_Suite SHALL include a test test_mock_mode_confirm_transfer_confirmed that verifies mock mode returns confirmed on 4th poll
16. THE Test_Suite SHALL include a test test_mock_mode_poll_counter_cleanup that verifies poll counter is cleaned up after confirmation
17. THE Test_Suite SHALL include a test test_is_configured_with_credentials that verifies is_configured() returns True when credentials are set
18. THE Test_Suite SHALL include a test test_is_configured_without_credentials that verifies is_configured() returns False when credentials are empty
19. THE Test_Suite SHALL include a test test_is_transfer_configured_with_all_settings that verifies is_transfer_configured() returns True when all settings present
20. THE Test_Suite SHALL include a test test_is_transfer_configured_mock_mode that verifies is_transfer_configured() returns True in mock mode
21. THE Test_Suite SHALL include a test test_authentication_token_caching that verifies OAuth tokens are cached and reused (if applicable)
22. THE Test_Suite SHALL include a test test_authentication_token_refresh that verifies expired tokens are refreshed automatically (if applicable)
23. THE Test_Suite SHALL include a test test_retry_logic_exponential_backoff that verifies retry delays are 1s, 2s, 4s
24. THE Test_Suite SHALL include a test test_retry_logic_max_attempts that verifies retries stop after 3 attempts
25. THE Test_Suite SHALL include a test test_retry_logic_no_retry_on_4xx that verifies 4xx errors are not retried (except 429)
26. THE Test_Suite SHALL include a test test_rate_limit_429_retry that verifies 429 errors trigger retry with Retry-After header
27. THE Test_Suite SHALL include a test test_error_message_sanitization that verifies API keys are not exposed in error messages
28. THE Test_Suite SHALL include a test test_request_headers that verifies correct headers are sent (User-Agent, Content-Type, Accept, Authorization)
29. THE Test_Suite SHALL include a test test_request_timeout_value that verifies timeout is set to 30 seconds
30. THE Test_Suite SHALL include a test test_amount_conversion_to_kobo that verifies amount is correctly converted from Naira to kobo
31. THE Test_Suite SHALL include a test test_transaction_reference_format that verifies transaction reference is included in requests
32. THE Test_Suite SHALL include a test test_response_validation_required_fields that verifies all required fields are validated
33. THE Test_Suite SHALL include a test test_connection_error_handling that verifies ConnectionError is caught and converted to KoraPayError
34. THE Test_Suite SHALL include a test test_ssl_error_handling that verifies SSLError is caught and converted to KoraPayError
35. THE Test_Suite SHALL include a test test_dns_error_handling that verifies DNS errors are caught and converted to KoraPayError
36. THE Test_Suite SHALL mock all external HTTP requests using unittest.mock.patch or responses library
37. THE Test_Suite SHALL NOT make actual HTTP requests to KoraPay API during unit tests
38. THE Test_Suite SHALL use pytest as the test framework (consistent with existing tests)
39. THE Test_Suite SHALL use fixtures for common test setup (mock config, mock responses)
40. THE Test_Suite SHALL achieve at least 90% code coverage for the KoraPay service module
41. THE Test_Suite SHALL verify code coverage using pytest-cov plugin
42. THE Test_Suite SHALL include docstrings for all test functions explaining what is being tested
43. THE Test_Suite SHALL use descriptive assertion messages for all assertions
44. THE Test_Suite SHALL test both success and failure paths for all public methods
45. THE Test_Suite SHALL be runnable with command: pytest tests/unit/test_korapay_service.py -v

### Requirement 12: Implement Integration Tests

**User Story:** As a developer, I want integration tests that verify the complete payment flow with KoraPay, so that I can ensure end-to-end functionality.

#### Acceptance Criteria

1. THE Integration_Test_Suite SHALL include a test test_create_payment_link_with_virtual_account that creates a payment link and verifies virtual account is created
2. THE Integration_Test_Suite SHALL include a test test_poll_transfer_status_pending that polls status and verifies pending response
3. THE Integration_Test_Suite SHALL include a test test_poll_transfer_status_confirmed that polls status and verifies transaction confirmation
4. THE Integration_Test_Suite SHALL include a test test_webhook_delivery_after_confirmation that verifies webhook is delivered after payment confirmation
5. THE Integration_Test_Suite SHALL include a test test_merchant_email_after_confirmation that verifies merchant notification email is sent
6. THE Integration_Test_Suite SHALL include a test test_customer_email_after_confirmation that verifies customer invoice email is sent when auto_send_email is enabled
7. THE Integration_Test_Suite SHALL include a test test_invoice_generation_after_confirmation that verifies invoice is created and PDF is generated
8. THE Integration_Test_Suite SHALL include a test test_invoice_status_sync_after_confirmation that verifies invoice status is updated to PAID
9. THE Integration_Test_Suite SHALL include a test test_complete_flow_mock_mode that verifies the complete flow from link creation to confirmation in Mock_Mode
10. THE Integration_Test_Suite SHALL include a test test_rate_limiting_on_status_polling that verifies rate limit is enforced (20 requests per minute)
11. THE Integration_Test_Suite SHALL include a test test_optimistic_locking_prevents_race_conditions that verifies concurrent confirmation attempts don't cause data corruption
12. THE Integration_Test_Suite SHALL include a test test_idempotent_webhook_delivery that verifies duplicate webhooks are handled idempotently
13. THE Integration_Test_Suite SHALL include a test test_expired_transaction_handling that verifies expired transactions cannot be confirmed
14. THE Integration_Test_Suite SHALL include a test test_already_used_transaction_handling that verifies already used transactions return appropriate status
15. THE Integration_Test_Suite SHALL include a test test_session_access_control that verifies polling requires session access token from /pay/ page
16. THE Integration_Test_Suite SHALL include a test test_qr_code_generation that verifies QR codes are generated for payment link and virtual account
17. THE Integration_Test_Suite SHALL include a test test_audit_log_creation that verifies audit logs are created for payment confirmation
18. THE Integration_Test_Suite SHALL include a test test_database_rollback_on_error that verifies database changes are rolled back if confirmation fails
19. THE Integration_Test_Suite SHALL include a test test_webhook_signature_verification that verifies webhook signature is validated correctly
20. THE Integration_Test_Suite SHALL include a test test_webhook_invalid_signature_rejection that verifies webhooks with invalid signatures are rejected
21. THE Integration_Test_Suite SHALL include a test test_health_check_reports_korapay_status that verifies health check endpoint reports KoraPay configuration
22. THE Integration_Test_Suite SHALL include a test test_payment_link_creation_with_idempotency_key that verifies idempotency key prevents duplicate links
23. THE Integration_Test_Suite SHALL include a test test_amount_validation that verifies amount validation (positive, within limits)
24. THE Integration_Test_Suite SHALL include a test test_customer_email_validation that verifies customer email format validation
25. THE Integration_Test_Suite SHALL include a test test_webhook_url_validation that verifies webhook URL security validation (no private IPs)
26. THE Integration_Test_Suite SHALL use a test database (SQLite in-memory or separate test database)
27. THE Integration_Test_Suite SHALL clean up test data after each test execution using pytest fixtures
28. THE Integration_Test_Suite SHALL use database transactions with rollback for test isolation
29. THE Integration_Test_Suite SHALL mock external HTTP requests to KoraPay API using responses library or similar
30. THE Integration_Test_Suite SHALL mock email sending to avoid sending real emails during tests
31. THE Integration_Test_Suite SHALL mock webhook delivery to avoid making real HTTP requests during tests
32. THE Integration_Test_Suite SHALL verify database state after each operation (transaction status, invoice status, audit logs)
33. THE Integration_Test_Suite SHALL verify API responses match expected format and status codes
34. THE Integration_Test_Suite SHALL test error paths (API failures, timeouts, invalid data)
35. THE Integration_Test_Suite SHALL test concurrent access scenarios (multiple users, multiple polls)
36. THE Integration_Test_Suite SHALL be runnable with command: pytest tests/integration/test_korapay_flow.py -v
37. THE Integration_Test_Suite SHALL complete execution in under 60 seconds
38. THE Integration_Test_Suite SHALL use pytest fixtures for common setup (test user, test config, mock services)
39. THE Integration_Test_Suite SHALL include docstrings explaining the test scenario and expected outcome
40. THE Integration_Test_Suite SHALL use descriptive test names that explain what is being tested

### Requirement 13: Update Documentation

**User Story:** As a system administrator, I want updated documentation that explains the KoraPay integration, so that I can configure and troubleshoot the system.

#### Acceptance Criteria

1. THE Documentation SHALL update README.md to replace all Quickteller references with KoraPay
2. THE Documentation SHALL update .env.example with KoraPay configuration variable descriptions
3. THE Documentation SHALL create a KoraPay setup guide in docs/KORAPAY_SETUP.md
4. THE Documentation SHALL document the KoraPay API endpoints used by the system
5. THE Documentation SHALL document the webhook signature verification process
6. THE Documentation SHALL document the Mock_Mode behavior and configuration
7. THE Documentation SHALL document error codes and troubleshooting steps
8. THE Documentation SHALL update the deployment guide with KoraPay-specific configuration
9. THE Documentation SHALL document the migration process from Quickteller to KoraPay
10. THE Documentation SHALL include example API requests and responses for debugging

### Requirement 14: Implement Database Migration Safety

**User Story:** As a database administrator, I want the migration to preserve all existing data, so that no transaction history or user data is lost.

#### Acceptance Criteria

1. THE System SHALL NOT modify the Transaction table schema during migration
2. THE System SHALL NOT modify the User table schema during migration
3. THE System SHALL NOT delete or modify any existing transaction records
4. THE System SHALL NOT delete or modify any existing user records
5. THE System SHALL preserve all existing virtual_account_number values in the database
6. THE System SHALL preserve all existing webhook_url values in the database
7. THE System SHALL preserve all existing audit_log entries
8. THE System SHALL verify database integrity before and after migration using checksums
9. WHERE a database backup exists, THE System SHALL create a new backup before migration
10. THE System SHALL provide a rollback procedure in case of migration failure

### Requirement 15: Implement Backward Compatibility

**User Story:** As a merchant, I want the user interface to remain unchanged after the migration, so that I can continue using the system without retraining.

#### Acceptance Criteria

1. THE System SHALL preserve all existing HTML templates without functional changes
2. THE System SHALL preserve all existing JavaScript polling logic for transfer status
3. THE System SHALL preserve all existing CSS styles and layouts
4. THE System SHALL preserve all existing API endpoint URLs and response formats
5. THE System SHALL preserve all existing error messages shown to users
6. THE System SHALL preserve all existing success messages shown to users
7. THE System SHALL preserve the existing QR code generation and display functionality
8. THE System SHALL preserve the existing payment link format and structure
9. THE System SHALL preserve the existing webhook delivery mechanism
10. THE System SHALL preserve the existing email notification templates and content

### Requirement 16: Implement Security Best Practices

**User Story:** As a security engineer, I want the KoraPay integration to follow security best practices, so that payment data and credentials are protected.

#### Acceptance Criteria

1. THE System SHALL store KoraPay API credentials only in environment variables (never hardcoded in source code)
2. THE System SHALL never log KORAPAY_API_KEY in plain text at any log level
3. THE System SHALL never log KORAPAY_SECRET_KEY in plain text at any log level
4. THE System SHALL never log KORAPAY_WEBHOOK_SECRET in plain text at any log level
5. THE System SHALL mask API keys in logs by showing only first 4 and last 4 characters (e.g., "kora_****_1234")
6. THE System SHALL use HTTPS for all KoraPay API requests in production environment
7. THE System SHALL validate KoraPay webhook signatures before processing payments using HMAC-SHA256
8. THE System SHALL use hmac.compare_digest() for signature verification to prevent timing attacks
9. THE System SHALL implement constant-time comparison for all cryptographic operations
10. THE System SHALL implement rate limiting on all KoraPay API endpoints (20 requests per minute per IP)
11. THE System SHALL implement rate limiting on webhook endpoints (100 requests per minute per IP)
12. THE System SHALL sanitize all user input before including in KoraPay API requests using html.escape()
13. THE System SHALL validate all user input for type, format, and length before API requests
14. THE System SHALL validate email addresses using regex pattern before sending to KoraPay
15. THE System SHALL validate phone numbers using regex pattern before sending to KoraPay
16. THE System SHALL validate URLs using urlparse and security checks before sending to KoraPay
17. THE System SHALL validate all KoraPay API responses for expected structure before storing in database
18. THE System SHALL validate all KoraPay API responses for expected data types before storing in database
19. THE System SHALL validate that response amounts match request amounts before confirming payments
20. THE System SHALL validate that response transaction references match request transaction references
21. THE System SHALL log all security-relevant events to audit log with event types: "payment.confirmed", "webhook.signature_failed", "payment.error"
22. THE System SHALL log failed signature verification attempts with source IP address and transaction reference
23. THE System SHALL log rate limit exceeded events with source IP address and endpoint
24. THE System SHALL log authentication failures with source IP address and error details
25. THE System SHALL implement the same CSRF protection for KoraPay endpoints as existing endpoints using X-CSRFToken header validation
26. THE System SHALL implement the same session security (IP binding, User-Agent validation) for KoraPay endpoints as existing endpoints
27. THE System SHALL validate Content-Type header is "application/json" for all JSON API endpoints
28. THE System SHALL reject requests with Content-Type "application/x-www-form-urlencoded" to prevent CSRF via form submission
29. THE System SHALL set secure session cookie flags (HttpOnly, Secure, SameSite=Lax) for all sessions
30. THE System SHALL implement X-Frame-Options header to prevent clickjacking (DENY or SAMEORIGIN)
31. THE System SHALL implement Content-Security-Policy header to prevent XSS attacks
32. THE System SHALL implement X-Content-Type-Options: nosniff header to prevent MIME sniffing
33. THE System SHALL implement Strict-Transport-Security header in production to enforce HTTPS
34. THE System SHALL validate that webhook URLs do not point to private IP addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
35. THE System SHALL validate that webhook URLs do not point to localhost (127.0.0.0/8, ::1)
36. THE System SHALL validate that webhook URLs do not point to link-local addresses (169.254.0.0/16)
37. THE System SHALL validate that webhook URLs do not point to AWS metadata endpoint (169.254.169.254)
38. THE System SHALL implement DNS rebinding protection by validating DNS on every webhook delivery attempt
39. THE System SHALL blacklist webhook URLs that fail security validation permanently
40. THE System SHALL use parameterized queries for all database operations (never string concatenation)
41. THE System SHALL use SQLAlchemy ORM for all database operations to prevent SQL injection
42. THE System SHALL validate that transaction amounts are Decimal type (never float) to prevent rounding errors
43. THE System SHALL validate that transaction amounts are positive and within valid range (0.01 to 9999999999.99)
44. THE System SHALL implement optimistic locking with with_for_update() to prevent race conditions
45. THE System SHALL use database transactions for all multi-step operations to ensure atomicity
46. THE System SHALL rollback database transactions on any error to maintain consistency
47. WHERE APP_ENV is "production", THE System SHALL refuse to start if KORAPAY_SECRET_KEY contains "change-this" or is shorter than 32 characters
48. WHERE APP_ENV is "production", THE System SHALL refuse to start if KORAPAY_API_KEY contains "change-this" or is shorter than 32 characters
49. WHERE APP_ENV is "production", THE System SHALL refuse to start if ENFORCE_HTTPS is not True
50. WHERE APP_ENV is "production", THE System SHALL refuse to start if DEBUG mode is enabled
51. THE System SHALL implement webhook timestamp validation to prevent replay attacks (reject webhooks older than 5 minutes)
52. THE System SHALL implement idempotency for all payment operations using transaction reference as idempotency key
53. THE System SHALL never expose internal error details or stack traces to external users
54. THE System SHALL sanitize all error messages before returning to users to prevent information disclosure
55. THE System SHALL log full error details internally while returning generic messages externally

### Requirement 17: Implement Refund Support

**User Story:** As a merchant, I want to initiate refunds through KoraPay, so that I can return payments to customers when necessary.

#### Acceptance Criteria

1. THE System SHALL implement a refund method in the KoraPay_Service
2. WHEN a merchant initiates a refund, THE System SHALL call the KoraPay refund API endpoint
3. WHEN a refund is successful, THE System SHALL update the Transaction status to indicate refund
4. WHEN a refund is successful, THE System SHALL log the refund event in the audit log
5. WHEN a refund fails, THE System SHALL return an error message to the merchant
6. THE System SHALL validate that a transaction is in VERIFIED status before allowing refund
7. THE System SHALL validate that a transaction has not already been refunded before allowing refund
8. THE System SHALL store the refund reference returned by KoraPay in the database
9. THE System SHALL send email notifications to the merchant and customer when a refund is processed
10. WHERE KoraPay does not support refunds via API, THE System SHALL document the manual refund process

### Requirement 18: Implement Transaction History Retrieval

**User Story:** As a merchant, I want to retrieve transaction history from KoraPay, so that I can reconcile payments with my records.

#### Acceptance Criteria

1. THE System SHALL implement a transaction history method in the KoraPay_Service
2. WHEN a merchant requests transaction history, THE System SHALL call the KoraPay transaction history API endpoint
3. THE System SHALL support filtering transaction history by date range
4. THE System SHALL support filtering transaction history by transaction status
5. THE System SHALL support pagination for large transaction history results
6. THE System SHALL reconcile KoraPay transaction history with local database records
7. WHEN a transaction exists in KoraPay but not in the local database, THE System SHALL log a warning
8. WHEN a transaction status differs between KoraPay and the local database, THE System SHALL log a warning
9. THE System SHALL provide a reconciliation report showing discrepancies
10. WHERE KoraPay does not support transaction history via API, THE System SHALL document the manual reconciliation process

### Requirement 19: Implement Parser and Pretty Printer for KoraPay API Responses

**User Story:** As a developer, I want to parse and format KoraPay API responses consistently, so that data handling is reliable and debuggable.

#### Acceptance Criteria

1. THE Parser SHALL parse KoraPay virtual account creation responses into a VirtualAccount object
2. THE Parser SHALL parse KoraPay transfer confirmation responses into a TransferStatus object
3. THE Parser SHALL parse KoraPay webhook payloads into a WebhookEvent object
4. WHEN a KoraPay response is missing required fields, THE Parser SHALL raise a KoraPayError with the missing field names
5. WHEN a KoraPay response contains invalid data types, THE Parser SHALL raise a KoraPayError with the field name and expected type
6. THE Pretty_Printer SHALL format VirtualAccount objects back into valid KoraPay API response format
7. THE Pretty_Printer SHALL format TransferStatus objects back into valid KoraPay API response format
8. THE Pretty_Printer SHALL format WebhookEvent objects back into valid KoraPay webhook payload format
9. FOR ALL valid VirtualAccount objects, parsing then printing then parsing SHALL produce an equivalent object (round-trip property)
10. FOR ALL valid TransferStatus objects, parsing then printing then parsing SHALL produce an equivalent object (round-trip property)
11. FOR ALL valid WebhookEvent objects, parsing then printing then parsing SHALL produce an equivalent object (round-trip property)
12. THE Parser SHALL validate response structure against the KoraPay API specification
13. THE Pretty_Printer SHALL produce JSON output that matches the KoraPay API specification format

### Requirement 20: Implement Monitoring and Alerting

**User Story:** As a system administrator, I want monitoring and alerting for KoraPay integration health, so that I can detect and respond to issues quickly.

#### Acceptance Criteria

1. THE System SHALL track the success rate of KoraPay API requests using in-memory counters
2. THE System SHALL track the average response time of KoraPay API requests using rolling average
3. THE System SHALL track the number of failed KoraPay API requests per hour using time-windowed counters
4. THE System SHALL track the number of successful virtual account creations per hour
5. THE System SHALL track the number of successful transfer confirmations per hour
6. THE System SHALL track the number of webhook signature verification failures per hour
7. WHEN the KoraPay API success rate falls below 95% over 100 requests, THE System SHALL log a critical alert
8. WHEN the KoraPay API average response time exceeds 5 seconds over 10 requests, THE System SHALL log a warning alert
9. WHEN KoraPay API requests fail more than 10 times in an hour, THE System SHALL log a critical alert
10. WHEN webhook signature verification fails more than 5 times in an hour, THE System SHALL log a security alert
11. THE System SHALL expose KoraPay metrics via the /health endpoint in JSON format
12. THE System SHALL include "korapay_api_success_rate" field in health check response (percentage)
13. THE System SHALL include "korapay_api_avg_response_time" field in health check response (milliseconds)
14. THE System SHALL include "korapay_api_failures_last_hour" field in health check response (count)
15. THE System SHALL include "korapay_api_status" field in health check response ("healthy", "degraded", "down")
16. THE System SHALL set "korapay_api_status" to "healthy" when success rate >= 95% and avg response time < 5s
17. THE System SHALL set "korapay_api_status" to "degraded" when success rate >= 80% or avg response time < 10s
18. THE System SHALL set "korapay_api_status" to "down" when success rate < 80% or more than 10 failures in last hour
19. THE System SHALL log all KoraPay API errors with sufficient context for debugging (endpoint, status code, error message, tx_ref)
20. THE System SHALL log all KoraPay API requests at INFO level with endpoint, method, tx_ref, and response time
21. THE System SHALL integrate with the existing security monitoring system for KoraPay-related security events
22. THE System SHALL log security events with event type prefix "korapay.security." for easy filtering
23. THE System SHALL include request ID in all log messages for request tracing
24. THE System SHALL include user ID in all log messages when available for audit trail
25. THE System SHALL include IP address in all log messages for security analysis
26. THE System SHALL implement structured logging with JSON format for easy parsing
27. THE System SHALL log at appropriate levels: DEBUG for detailed flow, INFO for operations, WARNING for recoverable errors, ERROR for failures, CRITICAL for system issues
28. THE System SHALL never log sensitive data (API keys, secrets, full credit card numbers, passwords) at any log level
29. THE System SHALL implement log rotation to prevent disk space exhaustion (max 100MB per file, keep 10 files)
30. THE System SHALL implement log aggregation tags for filtering (component=korapay, operation=create_account, operation=confirm_transfer)


### Requirement 21: Implement Graceful Degradation and Fallback Mechanisms

**User Story:** As a system administrator, I want the system to handle KoraPay API outages gracefully, so that the application remains partially functional during provider downtime.

#### Acceptance Criteria

1. WHEN KoraPay API is unreachable, THE System SHALL log the outage at ERROR level with timestamp
2. WHEN KoraPay API is unreachable, THE System SHALL return user-friendly error message "Payment provider temporarily unavailable"
3. WHEN KoraPay API is unreachable, THE System SHALL NOT crash or return 500 errors
4. WHEN KoraPay API is unreachable, THE System SHALL allow merchants to view existing transactions
5. WHEN KoraPay API is unreachable, THE System SHALL allow merchants to access dashboard and history
6. WHEN KoraPay API is unreachable, THE System SHALL prevent new payment link creation with clear error message
7. WHEN KoraPay API returns degraded performance (>10s response time), THE System SHALL log warning
8. WHEN KoraPay API returns degraded performance, THE System SHALL continue processing with extended timeout
9. THE System SHALL implement health check that detects KoraPay API availability
10. THE System SHALL cache KoraPay API status for 60 seconds to avoid excessive health checks
11. THE System SHALL display KoraPay status on merchant dashboard (operational, degraded, down)
12. THE System SHALL queue failed webhook deliveries for retry when KoraPay recovers
13. THE System SHALL implement exponential backoff for webhook retries (1min, 5min, 15min)
14. THE System SHALL retry failed webhooks up to 3 times before marking as permanently failed
15. THE System SHALL log all fallback activations for monitoring and alerting

### Requirement 22: Implement Data Migration and Validation

**User Story:** As a database administrator, I want to validate existing transaction data before and after migration, so that no data is lost or corrupted.

#### Acceptance Criteria

1. THE System SHALL create a pre-migration validation script that counts all transactions
2. THE System SHALL create a pre-migration validation script that computes checksum of all transaction data
3. THE System SHALL create a pre-migration validation script that validates all virtual_account_number fields are present
4. THE System SHALL create a pre-migration validation script that validates all amount fields are valid Decimal values
5. THE System SHALL create a pre-migration validation script that exports validation report to file
6. THE System SHALL create a post-migration validation script that verifies transaction count matches pre-migration
7. THE System SHALL create a post-migration validation script that verifies checksum matches pre-migration
8. THE System SHALL create a post-migration validation script that validates all transactions are still accessible
9. THE System SHALL create a post-migration validation script that validates all foreign key relationships are intact
10. THE System SHALL create a rollback script that can revert to Quickteller integration if needed
11. THE System SHALL document the rollback procedure in DEPLOYMENT.md
12. THE System SHALL test the rollback procedure in a staging environment before production deployment
13. THE System SHALL create a database backup before starting migration
14. THE System SHALL verify database backup integrity before proceeding with migration
15. THE System SHALL document the complete migration procedure with step-by-step instructions
16. THE System SHALL include estimated downtime in migration documentation
17. THE System SHALL include rollback decision criteria in migration documentation
18. THE System SHALL validate that no transactions are in "pending" state during migration window
19. THE System SHALL validate that no active payment links exist during migration window
20. THE System SHALL send notification to all merchants before migration maintenance window

### Requirement 23: Implement Performance Optimization

**User Story:** As a developer, I want the KoraPay integration to be performant, so that payment processing is fast and responsive.

#### Acceptance Criteria

1. THE System SHALL complete virtual account creation in under 2 seconds (95th percentile)
2. THE System SHALL complete transfer status polling in under 1 second (95th percentile)
3. THE System SHALL complete webhook processing in under 500 milliseconds (95th percentile)
4. THE System SHALL use database connection pooling to minimize connection overhead
5. THE System SHALL reuse HTTP connections to KoraPay API using requests.Session
6. THE System SHALL implement HTTP keep-alive for KoraPay API requests
7. THE System SHALL cache KoraPay authentication tokens to avoid repeated authentication
8. THE System SHALL use database indexes on transaction.tx_ref for fast lookups
9. THE System SHALL use database indexes on transaction.user_id for fast merchant queries
10. THE System SHALL use database indexes on transaction.created_at for fast history queries
11. THE System SHALL implement query optimization for transaction history pagination
12. THE System SHALL limit transaction history queries to 1000 records per request
13. THE System SHALL implement cursor-based pagination for large result sets
14. THE System SHALL use SELECT specific columns instead of SELECT * for large queries
15. THE System SHALL implement database query result caching for frequently accessed data
16. THE System SHALL use lazy loading for related objects to avoid N+1 query problems
17. THE System SHALL implement batch processing for webhook deliveries (process multiple in parallel)
18. THE System SHALL implement async webhook delivery using background threads
19. THE System SHALL limit concurrent webhook deliveries to 10 to avoid overwhelming the system
20. THE System SHALL implement request timeout of 30 seconds for all KoraPay API calls
21. THE System SHALL implement connection timeout of 10 seconds for KoraPay API connections
22. THE System SHALL log slow queries (>1 second) for performance monitoring
23. THE System SHALL log slow API requests (>5 seconds) for performance monitoring
24. THE System SHALL implement database query profiling in development environment
25. THE System SHALL optimize QR code generation to complete in under 100 milliseconds

### Requirement 24: Implement Comprehensive Logging and Debugging

**User Story:** As a developer, I want comprehensive logging for the KoraPay integration, so that I can debug issues quickly.

#### Acceptance Criteria

1. THE System SHALL log all KoraPay API requests at INFO level with: timestamp, endpoint, method, tx_ref, user_id
2. THE System SHALL log all KoraPay API responses at INFO level with: timestamp, status_code, response_code, tx_ref, duration_ms
3. THE System SHALL log all KoraPay API errors at ERROR level with: timestamp, error_type, error_message, tx_ref, stack_trace
4. THE System SHALL log all webhook deliveries at INFO level with: timestamp, url, tx_ref, attempt_number, status_code
5. THE System SHALL log all webhook signature verification failures at WARNING level with: timestamp, tx_ref, source_ip, signature_received
6. THE System SHALL log all payment confirmations at INFO level with: timestamp, tx_ref, amount, user_id, confirmation_method (poll/webhook)
7. THE System SHALL log all mock mode operations at WARNING level with "[MOCK]" prefix
8. THE System SHALL log all rate limit violations at WARNING level with: timestamp, endpoint, ip_address, limit_exceeded
9. THE System SHALL log all authentication failures at WARNING level with: timestamp, endpoint, error_message
10. THE System SHALL log all database errors at ERROR level with: timestamp, operation, error_message, tx_ref
11. THE System SHALL include correlation ID in all log messages for request tracing
12. THE System SHALL include user_id in all log messages when available for audit trail
13. THE System SHALL include ip_address in all log messages for security analysis
14. THE System SHALL use structured logging with consistent format: [timestamp] [level] [component] [operation] message key=value
15. THE System SHALL implement log levels: DEBUG (detailed flow), INFO (operations), WARNING (recoverable errors), ERROR (failures), CRITICAL (system issues)
16. THE System SHALL never log sensitive data: API keys, secrets, passwords, full credit card numbers, HMAC signatures
17. THE System SHALL mask sensitive data in logs: show first 4 and last 4 characters only
18. THE System SHALL implement log rotation: max 100MB per file, keep 10 files, compress old files
19. THE System SHALL implement separate log files for: application.log, error.log, security.log, korapay.log
20. THE System SHALL implement log aggregation tags for filtering: component=korapay, operation=create_account, operation=confirm_transfer, operation=webhook
21. THE System SHALL log request/response bodies at DEBUG level (with sensitive data masked)
22. THE System SHALL implement request ID generation for tracing requests across services
23. THE System SHALL include request ID in all API responses for debugging
24. THE System SHALL implement log search functionality for debugging (grep-friendly format)
25. THE System SHALL document logging conventions in DEVELOPMENT.md

### Requirement 25: Implement Deployment and Configuration Management

**User Story:** As a DevOps engineer, I want clear deployment procedures for the KoraPay integration, so that I can deploy safely to production.

#### Acceptance Criteria

1. THE System SHALL document the complete deployment procedure in docs/KORAPAY_DEPLOYMENT.md
2. THE System SHALL document all required environment variables with descriptions and examples
3. THE System SHALL document the difference between sandbox and production configuration
4. THE System SHALL document how to obtain KoraPay API credentials
5. THE System SHALL document how to configure webhook endpoints in KoraPay dashboard
6. THE System SHALL document how to test the integration in sandbox environment
7. THE System SHALL document how to verify the integration is working correctly
8. THE System SHALL document the rollback procedure if deployment fails
9. THE System SHALL document the monitoring and alerting setup
10. THE System SHALL document common troubleshooting scenarios and solutions
11. THE System SHALL include a deployment checklist with all required steps
12. THE System SHALL include a pre-deployment verification checklist
13. THE System SHALL include a post-deployment verification checklist
14. THE System SHALL document the estimated deployment time and downtime
15. THE System SHALL document the required database migrations (none expected)
16. THE System SHALL document the required configuration changes
17. THE System SHALL document the required code changes
18. THE System SHALL document the testing procedure for each environment (dev, staging, production)
19. THE System SHALL document the smoke test procedure after deployment
20. THE System SHALL document the performance benchmarks to verify after deployment
21. THE System SHALL implement configuration validation on startup
22. THE System SHALL fail fast on startup if required configuration is missing
23. THE System SHALL log all configuration validation errors with specific field names
24. THE System SHALL implement environment-specific configuration (dev, staging, production)
25. THE System SHALL document the security hardening checklist for production deployment
26. THE System SHALL document the backup and restore procedure
27. THE System SHALL document the disaster recovery procedure
28. THE System SHALL document the incident response procedure for payment failures
29. THE System SHALL document the escalation procedure for critical issues
30. THE System SHALL document the contact information for KoraPay support
